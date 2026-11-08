"""
spa_bath_backtest.py - vad badtider för spabadet hade sparat, räknat på husets egen historik (Emil 2026-11-08).

Badets fysik lärs ur sensor_log (minutdata):
  - P   värmarens effekt (kW): median av spa_power_w när värmaren går
  - C   värmekapacitet (kWh/°C): P / uppvärmningstakten (°C/h) + förlusten under uppvärmning
  - k   avsvalning (1/h): Newton, dT/dt = -k (T - ute), skattad när värmaren inte går
Sedan simuleras kvart för kvart, på samma priser och utetemperaturer, för två strategier:
  NU        badet hålls på normaltemperaturen dygnet runt (så som det styrs utan badtider)
  BADTIDER  eco-golvet utanför badtiderna; inför varje badtid värms det på de billigaste kvartarna under de
            sista 24 timmarna så att det är på normaltemperaturen när badtiden börjar; under badtiden hålls det
Kostnad = el × fullt köppris (nordpool.full_buy_cost). Den faktiska, uppmätta kostnaden visas också, som kontroll av
modellen. Jämför skillnaden mellan strategierna, inte de absoluta kronorna.

    docker exec smartbox python spa_bath_backtest.py --days 60
"""
import argparse
import math
from datetime import datetime, timedelta

STEP_H = 0.25


def estimate_physics(rows):
    """rows = [(ts, temp, heating(0/1), power_w, outdoor)] i tidsordning, en per minut. -> (P_kw, C_kwh_per_c, k_per_h)."""
    pw = sorted(r[3] for r in rows if r[2] and r[3] and r[3] > 300)
    p_kw = (pw[len(pw) // 2] / 1000.0) if pw else 3.0
    heat_rates, cool_ks = [], []
    # timvisa skillnader över sträckor där läget (värmer/inte) är detsamma hela timmen
    i = 0
    while i + 60 < len(rows):
        seg = rows[i:i + 61]
        if any(r[1] is None for r in seg) or (seg[-1][0] - seg[0][0]).total_seconds() > 3900:
            i += 30
            continue
        dt_h = (seg[-1][0] - seg[0][0]).total_seconds() / 3600.0
        d_temp = seg[-1][1] - seg[0][1]
        heating = [r[2] for r in seg]
        out = [r[4] for r in seg if r[4] is not None]
        if all(heating) and d_temp > 0.05:
            heat_rates.append(d_temp / dt_h)
        elif not any(heating) and out:
            gap = sum(r[1] for r in seg) / len(seg) - sum(out) / len(out)
            if gap > 5 and d_temp < 0:
                cool_ks.append(-d_temp / dt_h / gap)
        i += 60
    med = lambda xs, d: sorted(xs)[len(xs) // 2] if xs else d
    k = med(cool_ks, 0.004)
    rate = med(heat_rates, 1.5)
    loss_at_heat = k * 30.0                             # ungefärlig förlust (°C/h) när badet är varmt och ute är kallt
    c = p_kw / max(0.2, rate + loss_at_heat)
    return p_kw, c, k, len(heat_rates), len(cool_ks)


def simulate(steps, windows, t_hold, t_low, p_kw, c, k, cost_of, preheat_h=24):
    """steps = [(t, pris, ute)] per kvart. windows = [(start, slut)] (None = håll t_hold hela tiden).
    -> (kWh, kr, kvartar_under_mål_vid_badtidens_start)."""
    n = len(steps)
    heat_plan = [False] * n
    in_win = [False] * n
    if windows is not None:
        idx = {s[0]: i for i, s in enumerate(steps)}
        for ws, we in windows:
            for i, s in enumerate(steps):
                if ws <= s[0] < we:
                    in_win[i] = True
    # Förplanerade uppvärmningskvartar före varje badtid, iterativt tills badet når t_hold i tid
    def run(plan):
        temp, kwh, kr = t_hold, 0.0, 0.0
        temps = []
        for i, (t, price, out) in enumerate(steps):
            out = out if out is not None else 5.0
            loss = k * (temp - out) * c * STEP_H                       # kWh som går förlorat denna kvart
            if windows is None or in_win[i]:
                want = t_hold
            else:
                want = t_low
            need = max(0.0, (want - temp) * c + loss)
            e = min(p_kw * STEP_H, need) if (need > 0 and (windows is None or in_win[i] or temp < t_low)) else 0.0
            if windows is not None and plan[i] and not in_win[i]:
                e = min(p_kw * STEP_H, max(0.0, (t_hold - temp) * c + loss))
            temp += (e - loss) / c
            kwh += e
            kr += e * cost_of(price, t)
            temps.append(temp)
        return kwh, kr, temps
    if windows is not None:
        starts = sorted({ws for ws, _ in windows})
        for _ in range(4000):
            kwh, kr, temps = run(heat_plan)
            short = []
            for ws in starts:
                j = next((i for i, s in enumerate(steps) if s[0] >= ws), None)
                if j is not None and j > 0 and temps[j - 1] < t_hold - 0.3:
                    short.append(j)
            if not short:
                break
            for j in short:                                            # ta den billigaste lediga kvarten före badtiden
                lo = max(0, j - int(preheat_h / STEP_H))
                cand = [i for i in range(lo, j) if not heat_plan[i] and not in_win[i]]
                if cand:
                    heat_plan[min(cand, key=lambda i: (steps[i][1] if steps[i][1] is not None else 9e9, -i))] = True
        kwh, kr, temps = run(heat_plan)
        miss = 0
        for ws in starts:
            j = next((i for i, s in enumerate(steps) if s[0] >= ws), None)
            if j is not None and j > 0 and temps[j - 1] < t_hold - 0.5:
                miss += 1
        return kwh, kr, miss
    kwh, kr, _ = run(heat_plan)
    return kwh, kr, 0


def windows_for(steps, spec):
    """spec = {veckodag: (från_h, till_h)} -> [(start, slut)] över hela perioden."""
    if not steps:
        return []
    out = []
    d = steps[0][0].date()
    while d <= steps[-1][0].date():
        if d.weekday() in spec:
            a, b = spec[d.weekday()]
            tz = steps[0][0].tzinfo
            out.append((datetime(d.year, d.month, d.day, a, tzinfo=tz), datetime(d.year, d.month, d.day, b, tzinfo=tz)))
        d += timedelta(days=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--winter-shift", type=float, default=-8.0, help="vinterscenario: så här många grader kallare ute")
    ap.add_argument("--winter-price", type=float, default=1.5, help="vinterscenario: spotpriset × detta")
    args = ap.parse_args()
    import logger
    import nordpool
    import settings
    cfg = settings.get_settings()
    t_hold = float(cfg.get("spa_normal_temp") or 38.0)
    t_low = float(cfg.get("spa_low_temp") or 30.0)
    with logger.get_db() as conn, conn.cursor() as cur:
        cur.execute("""SELECT timestamp AT TIME ZONE 'Europe/Stockholm', spa_temp, COALESCE(spa_heater_running::int, 0), spa_power_w, outdoor_temp
                       FROM sensor_log WHERE timestamp > now() - make_interval(days => %s) AND spa_temp IS NOT NULL ORDER BY timestamp""", (args.days,))
        rows = [(r[0], float(r[1]), int(r[2] or 0), float(r[3]) if r[3] is not None else None,
                 float(r[4]) if r[4] is not None else None) for r in cur.fetchall()]
        cur.execute("""SELECT date_trunc('hour', timestamp AT TIME ZONE 'Europe/Stockholm') + floor(extract(minute from timestamp)/15) * interval '15 min',
                              avg(price), avg(outdoor_temp)
                       FROM sensor_log WHERE timestamp > now() - make_interval(days => %s) GROUP BY 1 ORDER BY 1""", (args.days,))
        steps = [(r[0], float(r[1]) if r[1] is not None else None, float(r[2]) if r[2] is not None else None) for r in cur.fetchall()]
    import zoneinfo
    swe = zoneinfo.ZoneInfo("Europe/Stockholm")
    rows = [(r[0].replace(tzinfo=swe),) + r[1:] for r in rows]
    steps = [(s[0].replace(tzinfo=swe),) + s[1:] for s in steps]
    p_kw, c, k, n_h, n_c = estimate_physics(rows)
    cost_of = lambda p, t: nordpool.full_buy_cost(p if p is not None else 1.0, t)
    actual_kwh = sum((r[3] or 0) for r in rows if r[2]) / 60000.0
    actual_kr = sum((r[3] or 0) / 60000.0 * cost_of(next((s[1] for s in steps if s[0] <= r[0]), 1.0), r[0]) for r in rows[::15] if r[2]) * 15
    days = max(1.0, (rows[-1][0] - rows[0][0]).total_seconds() / 86400.0) if rows else 1.0
    # Kalibrering: den uppmätta energin är vad badet faktiskt förlorade - justera avsvalningen så att "hålls varmt"
    # i modellen ger samma energi (ett välisolerat eller täckt bad förlorar mindre än skattningen)
    k_raw = k
    for _ in range(6):
        base = simulate(steps, None, t_hold, t_low, p_kw, c, k, cost_of)
        if base[0] <= 0 or actual_kwh <= 0:
            break
        k *= actual_kwh / base[0]
    base = simulate(steps, None, t_hold, t_low, p_kw, c, k, cost_of)
    scen = {
        "Helger 10-18 (aldrig vardagar)": {5: (10, 18), 6: (10, 18)},
        "Helger 10-18 + fre/ons 18-22": {2: (18, 22), 4: (18, 22), 5: (10, 18), 6: (10, 18)},
        "Varje kväll 18-22": {d: (18, 22) for d in range(7)},
    }
    print(f"Spabadet - {days:.0f} dygn historik. Normal {t_hold:.1f} °C, eco-golv {t_low:.1f} °C.")
    print(f"Inlärt: värmare {p_kw:.1f} kW, värmekapacitet {c:.2f} kWh/°C, avsvalning k={k:.4f}/h "
          f"({n_h} uppvärmningstimmar, {n_c} avsvalningstimmar)")
    print(f"Uppmätt: {actual_kwh:.0f} kWh, ca {actual_kr:.0f} kr. Avsvalningen kalibrerad mot det: k={k:.4f}/h (skattad {k_raw:.4f})")
    print(f"\n{'strategi':38s} {'kWh':>7s} {'kr':>7s} {'kr/mån':>7s} {'sparar':>8s} {'missade starter':>16s}")
    print(f"{'NU: hålls varmt dygnet runt (modell)':38s} {base[0]:7.0f} {base[1]:7.0f} {base[1] / days * 30:7.0f} {'':>8s} {'':>16s}")
    for name, spec in scen.items():
        kwh, kr, miss = simulate(steps, windows_for(steps, spec), t_hold, t_low, p_kw, c, k, cost_of)
        print(f"{name:38s} {kwh:7.0f} {kr:7.0f} {kr / days * 30:7.0f} {100 * (1 - kr / base[1]):7.0f}% {miss:>16d}")
    # Hur lågt lönar det sig att låta badet sjunka mellan badtiderna? (helgerna som exempel)
    wk = windows_for(steps, scen["Helger 10-18 (aldrig vardagar)"])
    print("\nEco-golv (hur lågt badet får sjunka mellan badtiderna), helger 10-18:")
    for low in (30.0, 25.0, 20.0, 15.0):
        kwh, kr, miss = simulate(steps, wk, t_hold, low, p_kw, c, k, cost_of)
        print(f"  {low:4.0f} °C  {kwh:6.0f} kWh  {kr / days * 30:5.0f} kr/mån  sparar {100 * (1 - kr / base[1]):3.0f}%  missade starter {miss}")
    # Vinter: kallare ute, dyrare el, ingen solel att värma med (solel ingår inte i modellen ovan heller)
    w_steps = [(t, None if p is None else p * args.winter_price, None if o is None else o + args.winter_shift) for t, p, o in steps]
    wb = simulate(w_steps, None, t_hold, t_low, p_kw, c, k, cost_of)
    print(f"\nVINTER (ute {args.winter_shift:+.0f} °C, spot ×{args.winter_price:.1f}):")
    print(f"{'NU: hålls varmt dygnet runt':38s} {wb[0]:7.0f} {wb[1]:7.0f} {wb[1] / days * 30:7.0f}")
    for name, spec in scen.items():
        kwh, kr, miss = simulate(w_steps, windows_for(w_steps, spec), t_hold, t_low, p_kw, c, k, cost_of)
        print(f"{name:38s} {kwh:7.0f} {kr:7.0f} {kr / days * 30:7.0f} {100 * (1 - kr / wb[1]):7.0f}% {miss:>16d}")
    print("\nModell: Newton-avsvalning mot utetemperaturen, kalibrerad mot uppmätt energi; uppvärmning på de billigaste "
          "kvartarna inom 24 h före badtiden. Solel räknas inte (den gör badtider ännu bättre sommartid, inte vintertid).")


if __name__ == "__main__":
    main()
