"""ev_cost.py - vad elbilsladdningen har kostat idag, den här veckan och den här månaden (idé från FTW 0.162).

Energin räknas från uppmätt laddeffekt minut för minut (inte laddboxens sessionsmätare, som hos Easee går i steg
om ungefär 1 kWh). Kostnaden per minut: det som kom från nätet till full köpkostnad (nordpool.full_buy_cost i SQL,
med tidstariff), det som kom från solen till vad den annars hade sålts för (full_sell_income). Saknas loggminuter
(motorn stod still, databasen nere) blir siffran för låg; då markeras perioden som delvis i stället för att se
komplett ut. Samma siffror i appen (Bil) och på webben (Elbil).
"""
from datetime import datetime, timedelta
import zoneinfo

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")
PARTIAL_BELOW = 0.95          # mindre loggad tid än så av perioden -> "delvis"

_SQL = """
WITH x AS (
    SELECT timestamp, net_power, COALESCE(pv_power_w, 0) pv, price,
           (COALESCE(ev_power_kw, 0) + COALESCE(ev_carport_power_kw, 0)) * 1000.0 ev,
           LEAST(extract(epoch FROM lead(timestamp) OVER (ORDER BY timestamp) - timestamp), 120) dt
    FROM sensor_log WHERE timestamp >= :t0 AND net_power IS NOT NULL
), s AS (
    SELECT *, CASE WHEN ev > 50 AND pv > 100 THEN GREATEST(0, LEAST(1, 1 - GREATEST(net_power, 0) / ev)) ELSE 0 END sol
    FROM x WHERE dt IS NOT NULL
)
SELECT p, sum(dt) / 3600.0, sum(dt * ev) / 3600000.0, sum(dt * ev * sol) / 3600000.0,
       sum(dt * ev * ((1 - sol) * {buy} + sol * {sell})) / 3600000.0
FROM (SELECT *, unnest(ARRAY[CASE WHEN timestamp >= :td THEN 'today' END, CASE WHEN timestamp >= :tw THEN 'week' END,
                              CASE WHEN timestamp >= :tm THEN 'month' END]) p FROM s) y
WHERE p IS NOT NULL AND price IS NOT NULL
GROUP BY p"""


def bounds(now: datetime):
    n = now.astimezone(SWE)
    day = n.replace(hour=0, minute=0, second=0, microsecond=0)
    week = day - timedelta(days=day.weekday())
    month = day.replace(day=1)
    return {"today": day, "week": week, "month": month}


def summary(conn, now: datetime | None = None) -> dict:
    """{"today"|"week"|"month": {"kwh", "solar_kwh", "kr", "partial"}} via en SQLAlchemy-anslutning."""
    import nordpool
    from sqlalchemy import text
    now = now or datetime.now(SWE)
    b = bounds(now)
    t0 = min(b.values())
    sql = _SQL.format(buy=nordpool.sql_buy_cost_expr("price", "timestamp"), sell=nordpool.sql_sell_income_expr("price"))
    try:
        rows = {r[0]: r for r in conn.execute(text(sql), {"t0": t0, "td": b["today"], "tw": b["week"], "tm": b["month"]}).all()}
    except Exception:
        conn.rollback()
        return {}
    out = {}
    for k, start in b.items():
        r = rows.get(k)
        span_h = max(1 / 60, (now - start).total_seconds() / 3600.0)
        logged_h = float(r[1] or 0) if r else 0.0
        out[k] = {"kwh": round(float(r[2] or 0), 1) if r else 0.0, "solar_kwh": round(float(r[3] or 0), 1) if r else 0.0,
                  "kr": round(float(r[4] or 0)) if r else 0, "partial": logged_h < span_h * PARTIAL_BELOW and span_h > 0.5}
    return out
