"""
price_rule_backtest.py - jämför värmepumpens prisregel mot historiken: kronor OCH komfort.

Bakgrund: gpm.py sätter grundläget så här (dynamic_limit = det N:te billigaste kvartspriset
från nordpool.calculate_day_strategy, hysteres = 15 % av dygnets spridning, 5-20 öre):

    NUVARANDE  billigt om pris <= gräns - hysteres, dyrt om pris >= gräns + hysteres,
               annars behåll läget.
    FÖRESLAGEN billigt om pris <= gräns (dvs. bland dygnets N billigaste),
               dyrt om pris >= gräns + hysteres, annars behåll läget.

Den nuvarande regeln kräver att priset ligger en hel hysteres UNDER det N:te billigaste -
en jämn billig natt hamnar då i gråzonen och huset laddas aldrig med billig värme. Den här
modulen räknar ut vad det kostar/sparar i just ditt hus, och vad det gör med innetempen.

Simuleringen (samma för båda reglerna, så det är SKILLNADEN som är intressant):
  - kvart för kvart; termostatens mål = temp_cheap i billigt läge, temp_expensive i dyrt
  - pumpen går när innetempen ligger under målet; uppvärmnings-/avsvalningstakt från husets
    EGNA inlärda modeller (learning.py), samma som mpc.py:s backtest använder
  - Prio 5 "kallt inne": under indoor_min värms det oavsett pris (som gpm.py)
  - gränsen höjs vid snabb avsvalning (+0.10/+0.30 kr), som gpm.py
  - kostnad = pumpens el × fullt köppris (nordpool.full_buy_cost, samma som mpc.py)
Förenklingar (lika för båda): ingen varmvattenproduktion, ingen kompressorspärrtid (Prio 8),
inget solöverskott/effektvakt. Siffrorna är en jämförelse, inte en exakt elräkning.

Körs på servern där historiken finns:
    docker exec smartbox python price_rule_backtest.py --days 90
"""

import argparse
from datetime import datetime, timedelta

QUARTER_H = 0.25


# ---------------------------------------------------------------- rena delar (testas)

def base_modes(prices, limit_for, hysteresis, rule, start_mode="EXPENSIVE"):
    """Grundläge per kvart. limit_for(i) = gränsen för kvart i (inkl. avsvalningstillägg)."""
    mode = start_mode
    out = []
    for i, p in enumerate(prices):
        lim = limit_for(i)
        cheap_at = lim - hysteresis if rule == "nuvarande" else lim
        if p <= cheap_at:
            mode = "CHEAP"
        elif p >= lim + hysteresis:
            mode = "EXPENSIVE"
        out.append(mode)
    return out


def simulate(prices, modes, heat_rate, cool_rate, indoor0, temp_cheap, temp_expensive,
             indoor_min, pump_kw, buy_cost):
    """Kvartsvis simulering. heat_rate(i, temp)/cool_rate(i) i °C/h. Returnerar (sammanfattning, sluttemp)."""
    t = indoor0
    kr = kwh = 0.0
    on_q = cheap_on_q = 0
    below_dh = 0.0
    tmin = t
    tsum = 0.0
    for i, p in enumerate(prices):
        target = temp_cheap if modes[i] == "CHEAP" else temp_expensive
        if t < indoor_min:
            target = max(target, temp_cheap)          # Prio 5: kallt inne -> värm oavsett pris
        on = t < target
        if on:
            t += heat_rate(i, t) * QUARTER_H
            e = pump_kw * QUARTER_H
            kwh += e
            kr += e * buy_cost(p)
            on_q += 1
            cheap_on_q += modes[i] == "CHEAP"
        else:
            t -= cool_rate(i) * QUARTER_H
        tmin = min(tmin, t)
        tsum += t
        below_dh += max(0.0, indoor_min - t) * QUARTER_H
    n = max(1, len(prices))
    return {
        "kr": kr, "kwh": kwh, "pump_h": on_q * QUARTER_H,
        "cheap_quarters": sum(m == "CHEAP" for m in modes), "quarters": len(prices),
        "heat_in_cheap_pct": (100.0 * cheap_on_q / on_q) if on_q else None,
        "min_temp": tmin, "mean_temp": tsum / n, "degree_hours_below_min": below_dh,
    }, t


def merge(a, b):
    """Summerar två simuleringsresultat (dag + dag)."""
    if a is None:
        return dict(b)
    out = {}
    for k in ("kr", "kwh", "pump_h", "cheap_quarters", "quarters", "degree_hours_below_min"):
        out[k] = a[k] + b[k]
    out["min_temp"] = min(a["min_temp"], b["min_temp"])
    out["mean_temp"] = (a["mean_temp"] * a["quarters"] + b["mean_temp"] * b["quarters"]) / max(1, out["quarters"])
    on_a = a["pump_h"] * (a["heat_in_cheap_pct"] or 0) / 100.0
    on_b = b["pump_h"] * (b["heat_in_cheap_pct"] or 0) / 100.0
    out["heat_in_cheap_pct"] = (100.0 * (on_a + on_b) / out["pump_h"]) if out["pump_h"] else None
    return out


def limit_offset(cool_rate_c_per_h):
    """gpm.py: gränsen höjs när huset svalnar snabbt (tvilling-justerad prisgräns)."""
    if cool_rate_c_per_h > 0.15:
        return 0.30
    if cool_rate_c_per_h > 0.05:
        return 0.10
    return 0.0


def run_days(days_data, strategy_fn, cheap_hours, temp_cheap, temp_expensive, indoor_min,
             pump_kw, buy_cost, heat_rate_for, cool_rate_for, indoor0):
    """days_data = [{'day': date, 'prices': [96 kvartspriser], 'outdoor': [24], 'solar': [24]}].
    Kör båda reglerna kontinuerligt över alla dagar. Returnerar {regel: {'total':..., 'per_day': [...]}}."""
    result = {}
    for rule in ("nuvarande", "foreslagen"):
        temp, mode, total, per_day = indoor0, "EXPENSIVE", None, []
        for d in days_data:
            prices = d["prices"]
            strat = strategy_fn(prices, cheap_hours)
            if strat.get("mode") == "comfort" or strat.get("dynamic_limit") is None:
                lim0, hyst = 99.0, 0.0
                modes = ["CHEAP"] * len(prices)                    # billig, platt dag: komfort
            else:
                lim0, hyst = float(strat["dynamic_limit"]), float(strat["hysteresis"])
                modes = base_modes(prices, lambda i: lim0 + limit_offset(cool_rate_for(d, i // 4)),
                                   hyst, rule, start_mode=mode)
            mode = modes[-1] if modes else mode
            r, temp = simulate(prices, modes,
                               lambda i, t: heat_rate_for(d, i // 4, t),
                               lambda i: cool_rate_for(d, i // 4),
                               temp, temp_cheap, temp_expensive, indoor_min, pump_kw, buy_cost)
            per_day.append({"day": d["day"], **r})
            total = merge(total, r)
        result[rule] = {"total": total, "per_day": per_day}
    return result


def format_report(res, days, settings):
    a, b = res["nuvarande"]["total"], res["foreslagen"]["total"]
    if not a:
        return "Inga kompletta dygn att jämföra."

    def row(label, key, fmt, better="lower"):
        va, vb = a[key], b[key]
        if va is None or vb is None:
            return f"  {label:<34}{'–':>12}{'–':>12}"
        diff = vb - va
        return f"  {label:<34}{fmt.format(va):>12}{fmt.format(vb):>12}{('  ' + ('+' if diff > 0 else '') + fmt.format(diff)) if abs(diff) > 1e-9 else ''}"

    lines = [
        f"Prisregel för värmepumpen - {days} dygn historik",
        f"Inställningar: billigt {settings['temp_cheap']} °C, dyrt {settings['temp_expensive']} °C, "
        f"komfortgolv {settings['indoor_min']} °C, {settings['cheap_hours']} billiga timmar/dygn, pump {settings['pump_kw']} kW",
        "",
        f"  {'':<34}{'nuvarande':>12}{'föreslagen':>12}  skillnad",
        row("Värmekostnad (kr)", "kr", "{:.0f}"),
        row("Värme-el (kWh)", "kwh", "{:.0f}"),
        row("Pumpens drifttid (h)", "pump_h", "{:.0f}"),
        row("Kvartar i billigt läge", "cheap_quarters", "{:.0f}"),
        row("Andel av värmen i billigt läge (%)", "heat_in_cheap_pct", "{:.0f}"),
        row("Lägsta innetemp (°C)", "min_temp", "{:.1f}"),
        row("Snitt innetemp (°C)", "mean_temp", "{:.2f}"),
        row("Gradtimmar under komfortgolvet", "degree_hours_below_min", "{:.1f}"),
        "",
        f"  Billiga kvartar som finns att ta: {round(a['quarters'] * settings['cheap_hours'] / 24)} "
        f"({settings['cheap_hours']} h/dygn × {days} dygn)",
        "",
        "Förenklad simulering, samma för båda reglerna: utan varmvatten, kompressorspärr,",
        "solöverskott och effektvakt. Titta på SKILLNADEN, inte de absoluta kronorna.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- databas (på servern)

def _load_days(conn, days):
    import zoneinfo
    swe = zoneinfo.ZoneInfo("Europe/Stockholm")
    today = datetime.now(swe).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    with conn.cursor() as cur:
        for k in range(days, 0, -1):
            d0 = today - timedelta(days=k)
            d1 = d0 + timedelta(days=1)
            cur.execute("SELECT time_start, sek_per_kwh FROM elpriser WHERE time_start >= %s AND time_start < %s "
                        "ORDER BY time_start", (d0, d1))
            pr = [(t, float(p)) for t, p in cur.fetchall() if p is not None]
            if len(pr) == 24:                       # timpriser (före kvartspriserna) -> 4 kvartar var
                pr = [(t + timedelta(minutes=15 * q), p) for t, p in pr for q in range(4)]
            if len(pr) < 92:
                continue
            cur.execute("""SELECT EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Stockholm')::int,
                                  AVG(outdoor_temp), AVG(pv_power_w), AVG(indoor_temp)
                           FROM sensor_log WHERE timestamp >= %s AND timestamp < %s GROUP BY 1""", (d0, d1))
            hourly = {int(h): (o, s, i) for h, o, s, i in cur.fetchall()}
            if sum(1 for h in range(24) if h in hourly and hourly[h][0] is not None) < 20:
                continue
            last_o = next((float(hourly[h][0]) for h in range(24) if h in hourly and hourly[h][0] is not None), 5.0)
            outdoor, solar = [], []
            for h in range(24):
                o, s, _ = hourly.get(h, (None, None, None))
                last_o = float(o) if o is not None else last_o
                outdoor.append(last_o)
                solar.append(float(s) if s is not None else 0.0)
            indoor0 = next((float(hourly[h][2]) for h in range(24) if h in hourly and hourly[h][2] is not None), None)
            out.append({"day": d0.date().isoformat(), "prices": [p for _, p in pr[:96]],
                        "outdoor": outdoor, "solar": solar, "indoor0": indoor0})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Jämför värmepumpens prisregel mot historiken.")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--pump-kw", type=float, default=2.2, help="värmepumpens eleffekt när den går (kW)")
    args = ap.parse_args(argv)

    import learning
    import logger
    import nordpool
    import settings as sm_settings

    cfg = sm_settings.get_settings()
    st = {"temp_cheap": float(cfg.get("temp_cheap", 22.0)), "temp_expensive": float(cfg.get("temp_expensive", 20.0)),
          "indoor_min": float(cfg.get("indoor_min", 19.0)), "cheap_hours": int(cfg.get("cheap_hours_count", 8)),
          "pump_kw": args.pump_kw}
    with logger.get_db() as conn:
        days_data = _load_days(conn, args.days)
    if not days_data:
        print("Hittade inga kompletta dygn med både elpriser och utetemperatur.")
        return 1
    heat_model = learning.get_house_heating_model()
    cool_model = learning.get_house_cooling_rate_model()

    def heat_rate_for(d, h, t):
        return max(0.05, learning.predict_house_heating_rate(d["outdoor"][h], 2.0, t, heat_model)) if heat_model else 0.3

    _cool_cache = {}

    def cool_rate_for(d, h):
        key = (d["day"], h)
        if key not in _cool_cache:
            roll = sum(d["solar"][max(0, h - 2):h + 1]) / len(d["solar"][max(0, h - 2):h + 1])
            _cool_cache[key] = max(0.0, learning.predict_house_cooling_rate(d["outdoor"][h], 2.0, d["solar"][h], roll, h, cool_model))
        return _cool_cache[key]

    indoor0 = next((d["indoor0"] for d in days_data if d["indoor0"] is not None), st["temp_expensive"])
    res = run_days(days_data, nordpool.calculate_day_strategy, st["cheap_hours"], st["temp_cheap"],
                   st["temp_expensive"], st["indoor_min"], st["pump_kw"], nordpool.full_buy_cost,
                   heat_rate_for, cool_rate_for, indoor0)
    print(format_report(res, len(days_data), st))
    print(f"\nModeller: uppvärmning {'husets egen' if heat_model else 'standardvärde 0.3 °C/h'}, "
          f"avsvalning {'husets egen' if cool_model else 'standardvärde'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
