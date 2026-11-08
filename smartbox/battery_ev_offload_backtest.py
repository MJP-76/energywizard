"""battery_ev_offload_backtest.py - lönar det sig att husbatteriet täcker husets förbrukning medan elbilen laddar?
(Martins förslag 2026-11-07, Emil bad om simulering med 10, 20, 30 och 40 kWh i sitt hus 2026-11-08.)

Husets egen historik (sensor_log, minutdata -> kvartar): förbrukning utan elbilarna (båda laddboxarna), sol, elbilens laddning och spotpris.
Ett tänkt batteri planeras dygn för dygn med battery_plan.optimize (samma planerare som motorn, med facit för dygnet)
i tre lägen medan bilen laddar:
  block    laddar inte ur alls (EnergyWizard idag)
  offload  täcker bara husets egen förbrukning, aldrig bilen (Martins förslag)
  free     får även ladda bilen (jämförelse)
Kostnad = nätköp × full köpkostnad - försäljning × säljintäkt (nordpool.full_buy_cost/full_sell_income), jämfört med
samma hus utan batteri. Batteriet får inte sälja till nätet (allow_export=False), slitage 0,20 kr per urladdad kWh.

Kör i smartbox-containern:  python battery_ev_offload_backtest.py [kWh ...]
"""
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta

WEAR = 0.20
EFF = 0.90
RESERVE = 0.10


def load_slots():
    import nordpool
    from logger import get_db
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""SELECT date_bin('15 minutes', timestamp, '2026-01-01') q,
                              avg(net_power), avg(COALESCE(pv_power_w, 0)), avg(COALESCE(ev_power_kw, 0) + COALESCE(ev_carport_power_kw, 0)), avg(price)
                       FROM sensor_log WHERE net_power IS NOT NULL AND price IS NOT NULL
                       GROUP BY 1 ORDER BY 1""")
        rows = cur.fetchall()
    days = {}
    for q, net_w, pv_w, ev_kw, spot in rows:
        ev = max(0.0, float(ev_kw))
        solar = max(0.0, float(pv_w)) / 1000.0
        house = max(0.0, float(net_w) / 1000.0 + solar - ev)          # husets förbrukning utan bilen
        loc = q.astimezone(nordpool.SWE_TZ)
        days.setdefault(loc.date(), []).append({"t": q, "load_kw": house, "solar_kw": solar, "ev_kw": ev,
                                                "buy": nordpool.full_buy_cost(float(spot), q),
                                                "sell": nordpool.full_sell_income(float(spot))})
    return {d: s for d, s in days.items() if len(s) >= 88}           # bara nästan hela dygn


def _cost(s, grid):
    e = grid * 0.25
    return e * s["buy"] if e > 0 else e * s["sell"]


def run(args):
    import battery_plan as bp
    cap, mode, days = args
    p = min(10.0, cap / 2.0)
    soc = cap * 0.5
    tot = base = ev_kwh_cov = house_kwh_ev = 0.0
    for d in sorted(days):
        sl = days[d]
        r = bp.optimize(sl, soc, cap, cap * RESERVE, cap, p, p, eff=EFF, cycle_cost=WEAR, allow_export=False,
                        ev_mode=mode, switch_cost=0.0, step_kwh=cap / 80.0)
        for s, row in zip(sl, r["rows"]):
            tot += _cost(s, row["grid_kw"]) + WEAR * max(0.0, -row["battery_kw"]) * 0.25
            base += _cost(s, s["load_kw"] + s["ev_kw"] - s["solar_kw"])
            if s["ev_kw"] > 0.1 and row["battery_kw"] < 0:
                house_kwh_ev += min(-row["battery_kw"], max(0.0, s["load_kw"] - s["solar_kw"])) * 0.25
                ev_kwh_cov += max(0.0, -row["battery_kw"] - max(0.0, s["load_kw"] - s["solar_kw"])) * 0.25
        soc = r["rows"][-1]["soc_kwh"] if r["rows"] else soc
    return cap, mode, round(base - tot), round(house_kwh_ev), round(ev_kwh_cov), soc


def main(caps):
    days = load_slots()
    d0, d1 = min(days), max(days)
    ev_days = sum(1 for s in days.values() if any(x["ev_kw"] > 0.1 for x in s))
    ev_house = sum(max(0.0, x["load_kw"] - x["solar_kw"]) * 0.25 for s in days.values() for x in s if x["ev_kw"] > 0.1)
    print(f"Period {d0} - {d1}: {len(days)} hela dygn, elbilen laddade {ev_days} av dem. Husets egen förbrukning "
          f"medan bilen laddade: {ev_house:.0f} kWh.")
    jobs = [(c, m, days) for c in caps for m in ("block", "offload", "free")]
    with ProcessPoolExecutor(max_workers=2) as ex:
        res = list(ex.map(run, jobs))
    print(f"\n{'Batteri':>8} {'Läge':>8} {'Sparar kr':>10} {'Hus under laddning kWh':>23} {'In i bilen kWh':>15}")
    for cap, mode, save, h, e, _ in res:
        print(f"{cap:>6} kWh {mode:>8} {save:>10} {h:>23} {e:>15}")
    by = {(c, m): s for c, m, s, *_ in res}
    print("\nMartins läge jämfört med idag (kr över perioden, per år):")
    n = len(days)
    for c in caps:
        dlt = by[(c, "offload")] - by[(c, "block")]
        print(f"  {c} kWh: {dlt:+} kr ({dlt * 365 / n:+.0f} kr/år)")


if __name__ == "__main__":
    main([float(x) for x in sys.argv[1:]] or [10.0, 20.0, 30.0, 40.0])
