"""
battery_plan.py - husbatteriets plan över dygnet (steg 3): när det lönar sig att ladda, spara
och ladda ur, givet elpriset, husets förväntade last, solprognosen och elbilens laddplan.

Dynamisk programmering över batteriets energi, kvart för kvart. För varje kvart prövas de
avsikter batteriet stöder:

  auto       självförbrukning: täcker husets underskott, tar upp solöverskott
  hold       tar upp solöverskott, laddar inte ur
  idle       varken laddar eller laddar ur
  charge     laddar med full effekt (även från nätet)
  discharge  laddar ur med full effekt (överskott säljs)

Kostnaden per kvart är nätköp × fullt köppris - försäljning × säljintäkt (nordpool.full_buy_cost /
full_sell_income, samma som resten av motorn). Verkningsgraden räknas på vägen in och ut.
Energi kvar vid horisontens slut värderas till vad den sparar senare (25:e percentilen av köppriset × urladdnings-
verkningsgrad, försiktigt satt) - annars skulle planen tömma batteriet bara för att horisonten tar slut.

Gränser: aldrig under reservnivån, aldrig över maxnivån, och aldrig urladdning medan elbilen är
planerad att ladda (töm inte batteriet i bilen - samma regel som battery_control.py).

Ren modul utan I/O, testas i tests/test_battery_plan.py. main.py bygger indata och sparar planen.
"""

import math

DT_H = 0.25                 # kvart
ACTIONS = ("auto", "hold", "idle", "charge", "discharge")


def _battery_power(action, net_kw, pc, pd):
    """Batteriets AC-effekt (kW, + laddar) för en avsikt, före laddnivågränser."""
    if action == "auto":
        return max(-pd, min(pc, -net_kw))
    if action == "hold":
        return max(0.0, min(pc, -net_kw))
    if action == "idle":
        return 0.0
    if action == "charge":
        return pc
    return -pd


def _step(soc, b_kw, lo, hi, eff_c, eff_d):
    """Ny energi (kWh) och faktisk batterieffekt efter att gränserna klippt den."""
    if b_kw >= 0:
        de = b_kw * DT_H * eff_c
        if soc + de > hi:
            de = max(0.0, hi - soc)
            b_kw = de / (DT_H * eff_c) if eff_c else 0.0
    else:
        de = b_kw * DT_H / eff_d
        if soc + de < lo:
            de = min(0.0, lo - soc)
            b_kw = de * eff_d / DT_H
    return soc + de, b_kw


def _cost(grid_kw, buy, sell):
    e = grid_kw * DT_H
    return e * buy if e > 0 else e * sell


def simulate(slots, soc0, actions, capacity, reserve, max_kwh, pc, pd, eff):
    """Kör en given avsiktsserie och returnerar (kostnad, rader). Används för baslinjen."""
    eff_c = eff_d = math.sqrt(eff)
    soc, cost, rows = soc0, 0.0, []
    for s, a in zip(slots, actions):
        net = s["load_kw"] + s.get("ev_kw", 0.0) - s.get("solar_kw", 0.0)
        b = _battery_power(a, net, pc, pd)
        if s.get("ev_kw", 0.0) > 0.1 and b < 0:
            b = 0.0
        soc, b = _step(soc, b, reserve, max_kwh, eff_c, eff_d)
        grid = net + b
        c = _cost(grid, s["buy"], s["sell"])
        cost += c
        rows.append({"t": s["t"], "action": a, "soc_kwh": soc, "battery_kw": b, "grid_kw": grid, "cost": c})
    return cost, rows


def optimize(slots, soc0_kwh, capacity_kwh, reserve_kwh, max_kwh, charge_kw, discharge_kw,
             eff=0.9, allowed=ACTIONS, step_kwh=None, switch_cost=0.10):
    """slots: [{'t', 'buy', 'sell', 'load_kw', 'solar_kw', 'ev_kw'}] (kvartar, i tidsordning).
    switch_cost: kr per lägesbyte - håller planen sammanhängande (färre skrivningar till
    växelriktarens flashminne) i stället för att jaga varje öre mellan kvartspriserna.
    Returnerar {'rows': [...], 'cost': kr, 'baseline_cost': kr (bara auto), 'saving_kr': kr}."""
    if not slots or not capacity_kwh or capacity_kwh <= 0:
        return {"rows": [], "cost": 0.0, "baseline_cost": 0.0, "saving_kr": 0.0}
    acts = [a for a in ACTIONS if a in set(allowed) | {"auto"}]
    A = len(acts)
    eff_c = eff_d = math.sqrt(eff)
    step = step_kwh or max(0.05, capacity_kwh / 100.0)
    lo, hi = max(0.0, reserve_kwh), min(capacity_kwh, max_kwh)
    n_states = int(round(capacity_kwh / step)) + 1
    idx = lambda e: max(0, min(n_states - 1, int(round(e / step))))

    # Energi kvar vid slutet värderas FÖRSIKTIGT (25:e percentilen av köppriset): med medianen
    # blev värdet så högt en dag med dyr kväll att planen hellre hamstrade än använde batteriet.
    buys = sorted(s["buy"] for s in slots)
    terminal_value = buys[len(buys) // 4] * eff_d          # kr per kWh kvar vid slutet

    INF = float("inf")
    # future[i][k] = minsta kostnad framåt från energinivå i när förra kvartens avsikt var acts[k]
    term = [-(i * step) * terminal_value for i in range(n_states)]
    future = [[term[i]] * A for i in range(n_states)]
    choice = []
    for s in reversed(slots):
        net = s["load_kw"] + s.get("ev_kw", 0.0) - s.get("solar_kw", 0.0)
        ev_on = s.get("ev_kw", 0.0) > 0.1
        # utfall per (energinivå, avsikt) är oberoende av förra avsikten - räkna en gång
        trans = []
        for i in range(n_states):
            soc = i * step
            row = []
            for a in acts:
                b = _battery_power(a, net, charge_kw, discharge_kw)
                if ev_on and b < 0:
                    if a == "discharge":
                        row.append(None)
                        continue
                    b = 0.0
                new, b = _step(soc, b, min(lo, soc), hi if soc <= hi else soc, eff_c, eff_d)
                row.append((idx(new), b, net + b, _cost(net + b, s["buy"], s["sell"])))
            trans.append(row)
        cur = [[INF] * A for _ in range(n_states)]
        ch = [[None] * A for _ in range(n_states)]
        for i in range(n_states):
            for prev in range(A):
                best, arg = INF, None
                for k in range(A):
                    t = trans[i][k]
                    if t is None:
                        continue
                    c = t[3] + future[t[0]][k] + (switch_cost if k != prev else 0.0)
                    if c < best - 1e-12:
                        best, arg = c, k
                cur[i][prev], ch[i][prev] = best, arg
        future = cur
        choice.append((ch, trans))
    choice.reverse()

    rows, i, prev = [], idx(soc0_kwh), acts.index("auto")
    total = 0.0
    for s, (ch, trans) in zip(slots, choice):
        k = ch[i][prev]
        nxt, b, grid, c = trans[i][k]
        total += c
        a = acts[k]
        # Ladda med fullt batteri / ladda ur vid reservnivån gör i praktiken ingenting - visa och
        # skicka det som "håll", så planen inte ser ut att ladda i timmar.
        if a in ("charge", "discharge") and abs(b) < 0.05 and "hold" in acts:
            a = "hold"
        rows.append({"t": s["t"], "action": a, "soc_kwh": nxt * step, "battery_kw": round(b, 3),
                     "grid_kw": round(grid, 3), "cost": c, "buy": s["buy"]})
        i, prev = nxt, k
    base_cost, base_rows = simulate(slots, soc0_kwh, ["auto"] * len(slots), capacity_kwh, lo, hi, charge_kw, discharge_kw, eff)
    # Rättvis jämförelse: värdera energin kvar vid slutet lika i båda.
    end_plan = rows[-1]["soc_kwh"] if rows else soc0_kwh
    end_base = base_rows[-1]["soc_kwh"] if base_rows else soc0_kwh
    saving = (base_cost - end_base * terminal_value) - (total - end_plan * terminal_value)
    return {"rows": rows, "cost": total, "baseline_cost": base_cost, "saving_kr": round(saving, 2)}


REASON = {
    "charge": "Planen: laddar nu på billig el inför dyrare timmar",
    "discharge": "Planen: laddar ur nu – dyr timme",
    "hold": "Planen: sparar batteriet till dyrare timmar",
    "idle": "Planen: batteriet vilar",
    "auto": "Planen: självförbrukning",
}


def blocks(rows):
    """Slår ihop kvartar med samma avsikt (utom auto) till sammanhängande pass för planvyn.
    'end' är sista kvartens start; passet slutar 15 min senare."""
    out = []
    for i, r in enumerate(rows):
        if out and out[-1]["action"] == r["action"] and out[-1]["_last"] == i - 1:
            out[-1].update(_last=i, end=r["t"], soc_end=r["soc_kwh"])
        else:
            out.append({"action": r["action"], "start": r["t"], "end": r["t"], "_last": i, "soc_end": r["soc_kwh"]})
    return [{k: v for k, v in b.items() if k != "_last"} for b in out if b["action"] != "auto"]


# ---------------------------------------------------------------- databas (main.py)

def plan_from_db(engine, now, soc_pct, settings, base_profile, supported):
    """Bygger kvartarna från nu till slutet av kända elpriser och kör optimize(). Sparar planen i
    battery_plan_slots. Returnerar resultatet + 'action_now' för pågående kvart."""
    from datetime import timedelta
    from sqlalchemy import text
    import learning
    import nordpool
    import weather

    cap = settings.get("capacity_kwh")
    if not cap or soc_pct is None:
        return None
    q0 = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
    with engine.connect() as c:
        prices = c.execute(text("SELECT time_start, sek_per_kwh FROM elpriser WHERE time_start >= :a AND time_start < :b "
                                "ORDER BY time_start"), {"a": q0, "b": q0 + timedelta(hours=36)}).fetchall()
        try:
            ev = c.execute(text("SELECT t_slot, SUM(kw) FROM ev_plan_slots GROUP BY t_slot")).fetchall()
        except Exception:
            c.rollback()
            ev = []
    ev_kw = {t.replace(tzinfo=now.tzinfo) if t.tzinfo is None else t.astimezone(now.tzinfo): float(kw or 0) for t, kw in ev}
    hourly_price = {}
    for t, p in prices:
        if p is not None:
            hourly_price[t.astimezone(now.tzinfo)] = float(p)
    if not hourly_price:
        return None
    # Kvartspriser; timpriser (äldre dagar) delas upp i fyra kvartar.
    quarters, t = {}, q0
    for ts, p in sorted(hourly_price.items()):
        quarters[ts] = p
    solar_cache = {}

    def solar_at(ts):
        h = ts.replace(minute=0)
        if h not in solar_cache:
            try:
                cloud, _, _, _ = weather.get_weather_at(h)
                solar_cache[h] = (weather.get_smart_solar_w(cloud, h) or 0.0) / 1000.0
            except Exception:
                solar_cache[h] = 0.0
        return solar_cache[h]

    slots, last_p = [], None
    end = max(quarters) + timedelta(minutes=15)
    while t < end:
        p = quarters.get(t, quarters.get(t.replace(minute=0), last_p))
        if p is None:
            break
        last_p = p
        slots.append({"t": t, "buy": nordpool.full_buy_cost(p), "sell": nordpool.full_sell_income(p), "spot": p,
                      "load_kw": learning.predict_base_load(t, base_profile), "solar_kw": solar_at(t),
                      "ev_kw": ev_kw.get(t, 0.0)})
        t += timedelta(minutes=15)
    if not slots:
        return None
    r = optimize(slots, soc_pct / 100.0 * cap, cap, settings["reserve_soc"] / 100.0 * cap, settings["max_soc"] / 100.0 * cap,
                 settings["max_power_w"] / 1000.0, settings["max_power_w"] / 1000.0, eff=settings.get("efficiency", 0.9),
                 allowed=supported)
    try:
        with engine.begin() as c:
            c.execute(text("CREATE TABLE IF NOT EXISTS battery_plan_slots (t_slot TIMESTAMPTZ PRIMARY KEY, action TEXT, "
                           "soc_pct NUMERIC, battery_kw NUMERIC, spot NUMERIC, saving_kr NUMERIC, updated_at TIMESTAMPTZ DEFAULT now())"))
            c.execute(text("DELETE FROM battery_plan_slots"))
            c.execute(text("INSERT INTO battery_plan_slots (t_slot, action, soc_pct, battery_kw, spot, saving_kr) VALUES (:t, :a, :s, :b, :p, :sv)"),
                      [{"t": row["t"], "a": row["action"], "s": round(100.0 * row["soc_kwh"] / cap, 1), "b": row["battery_kw"],
                        "p": sl["spot"], "sv": r["saving_kr"]} for row, sl in zip(r["rows"], slots)])
    except Exception as e:
        print(f"⚠️ Batteriplanen kunde inte sparas: {e}")
    r["action_now"] = r["rows"][0]["action"] if r["rows"] else None
    r["spot_now"] = slots[0]["spot"]
    return r
