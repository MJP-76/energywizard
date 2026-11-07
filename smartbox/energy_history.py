"""
energy_history.py - historiken för webben och appen: energisummor och effekt över tid.

Inspirerat av FTW:s History-vy (egen implementation):
  - Summor för Idag / 7 dagar / 30 dagar: förbrukat hemma, solel, köpt, sålt (+ batteri).
  - Effekt över tid för nät, sol, hus och batteri: 24 h / 7 d / 30 d / 1 år.
  - Senaste värdena.

Energin räknas TIDSVIKTAT ur sensor_log: varje rads effekt × tiden till nästa rad (max 5
minuter, så att ett avbrott i loggningen inte räknas som timmar på samma effekt). Rätt
oavsett loggintervall.

Teckenkonventioner (samma som resten av projektet):
  net_power        + = köper från nätet, - = säljer (Tibber, mätt vid huvudsäkringen)
  battery_power_w  + = batteriet laddar, - = laddar ur (drivers/battery.py)
  house_consumption_w saknas på äldre rader -> nät + sol - batteri.

DB-frågorna här; de rena hjälpfunktionerna testas i tests/test_energy_history.py.
"""

from datetime import datetime, timedelta
import math
import zoneinfo

from sqlalchemy import text

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")
PERIODS = ("today", "7d", "30d")
RANGES = {"24h": (timedelta(hours=24), "5 minutes"), "7d": (timedelta(days=7), "30 minutes"),
          "30d": (timedelta(days=30), "2 hours"), "1y": (timedelta(days=365), "1 day")}

def _fin(v):
    """float eller None - "Infinity"/"NaN" i äldre loggrader (#171/#186) får inte nå JSON-svaret."""
    if v is None:
        return None
    f = float(v)
    return f if math.isfinite(f) else None


# Rader med oändliga värden räknas inte (numeric 'Infinity' i PostgreSQL 14+)
_OK = "(net_power IS NULL OR net_power::float8 NOT IN ('Infinity','-Infinity','NaN')) AND (pv_power_w IS NULL OR pv_power_w::float8 NOT IN ('Infinity','-Infinity','NaN')) AND (battery_power_w IS NULL OR battery_power_w::float8 NOT IN ('Infinity','-Infinity','NaN')) AND (house_consumption_w IS NULL OR house_consumption_w::float8 NOT IN ('Infinity','-Infinity','NaN'))"

_HOUSE = "COALESCE(house_consumption_w, net_power + COALESCE(pv_power_w, 0) - COALESCE(battery_power_w, 0))"


def period_start(now, period):
    """Början av perioden i svensk tid: idag = midnatt, 7d/30d = midnatt för 6/29 dygn sedan."""
    now = now.astimezone(SWE)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = {"today": 0, "7d": 6, "30d": 29}[period]
    return midnight - timedelta(days=days)


def summarize(t):
    """Läsbar mening om perioden, eller None om det saknas data."""
    if not t or not t.get("used_kwh"):
        return None
    parts = []
    if t.get("solar_kwh"):
        parts.append(f"Solen gav {round(100 * t['solar_kwh'] / t['used_kwh'])} % av det huset använde.")
    if t.get("bought_kwh") is not None and t["used_kwh"] > 0:
        own = max(0.0, 1 - t["bought_kwh"] / t["used_kwh"])
        if t.get("solar_kwh"):
            parts.append(f"{round(100 * own)} % av förbrukningen täcktes utan att köpa el.")
    if t.get("battery_in_kwh") or t.get("battery_out_kwh"):
        parts.append(f"Batteriet tog in {t['battery_in_kwh']:.1f} kWh och gav tillbaka {t['battery_out_kwh']:.1f} kWh.")
    return " ".join(parts) or None


def totals(conn, period, now=None):
    now = now or datetime.now(SWE)
    start = period_start(now, period)
    row = conn.execute(text(f"""
        WITH s AS (
            SELECT net_power, pv_power_w, battery_power_w, {_HOUSE} AS house,
                   LEAST(COALESCE(EXTRACT(EPOCH FROM lead(timestamp) OVER (ORDER BY timestamp) - timestamp), 60), 300) AS dt
            FROM sensor_log WHERE timestamp >= :start AND timestamp <= :now AND {_OK}
        )
        SELECT sum(GREATEST(house, 0) * dt) / 3.6e6, sum(GREATEST(pv_power_w, 0) * dt) / 3.6e6,
               sum(GREATEST(net_power, 0) * dt) / 3.6e6, sum(GREATEST(-net_power, 0) * dt) / 3.6e6,
               sum(GREATEST(battery_power_w, 0) * dt) / 3.6e6, sum(GREATEST(-battery_power_w, 0) * dt) / 3.6e6,
               count(*), bool_or(battery_power_w IS NOT NULL), bool_or(pv_power_w IS NOT NULL)
        FROM s"""), {"start": start, "now": now}).fetchone()
    if not row or not row[6]:
        return None
    r = lambda v: round(_fin(v), 1) if _fin(v) is not None else None
    t = {"used_kwh": r(row[0]), "solar_kwh": r(row[1]) if row[8] else None, "bought_kwh": r(row[2]), "sold_kwh": r(row[3]),
         "battery_in_kwh": r(row[4]) if row[7] else None, "battery_out_kwh": r(row[5]) if row[7] else None,
         "from": start.isoformat()}
    t["summary"] = summarize(t)
    return t


def series(conn, rng, now=None):
    """Medeleffekt per tidshink för nät/sol/hus/batteri (kW). rng: 24h | 7d | 30d | 1y."""
    span, bucket = RANGES[rng]
    now = now or datetime.now(SWE)
    rows = conn.execute(text(f"""
        SELECT date_bin(CAST(:bucket AS interval), timestamp, TIMESTAMPTZ '2000-01-01') AS b,
               avg(net_power), avg(pv_power_w), avg({_HOUSE}), avg(battery_power_w)
        FROM sensor_log WHERE timestamp >= :start AND timestamp <= :now AND {_OK}
        GROUP BY 1 ORDER BY 1"""), {"bucket": bucket, "start": now - span, "now": now}).fetchall()
    kw = lambda v: round(_fin(v) / 1000.0, 2) if _fin(v) is not None else None
    return {"range": rng, "bucket": bucket,
            "t": [b.astimezone(SWE).isoformat() for b, *_ in rows],
            "grid_kw": [kw(x[1]) for x in rows], "solar_kw": [kw(x[2]) for x in rows],
            "house_kw": [kw(x[3]) for x in rows], "battery_kw": [kw(x[4]) for x in rows]}


def latest(conn):
    row = conn.execute(text(f"""SELECT timestamp, net_power, pv_power_w, {_HOUSE}, battery_power_w, battery_soc
                                FROM sensor_log ORDER BY timestamp DESC LIMIT 1""")).fetchone()
    if not row:
        return None
    w = lambda v: round(_fin(v)) if _fin(v) is not None else None
    return {"ts": row[0].astimezone(SWE).isoformat(), "grid_w": w(row[1]), "solar_w": w(row[2]),
            "house_w": w(row[3]), "battery_w": w(row[4]), "battery_soc": w(row[5])}


def history_payload(conn, rng="24h", now=None):
    """Allt historikvyn behöver i ett anrop (webben och appen)."""
    rng = rng if rng in RANGES else "24h"
    return {"ok": True, "totals": {p: totals(conn, p, now) for p in PERIODS},
            "series": series(conn, rng, now), "latest": latest(conn)}
