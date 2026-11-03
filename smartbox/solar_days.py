"""Solprognos per dygn: idag (hela dagen, hittills uppmätt och kvar), imorgon och i övermorgon.

Samma timprognos som motorn och tidslinjen använder (weather.get_smart_solar_w: molnprognosen
från Open-Meteo gånger husets inlärda solprofil per månad och timme), summerad per dygn.
Visas bara när huset har solceller, alltså när produktion har mätts de senaste 14 dagarna.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SWE = ZoneInfo("Europe/Stockholm")
DAY_NAMES = ("today", "tomorrow", "day_after")


def summarize(hourly_w, now, produced_today_kwh=None):
    """hourly_w: {timstart (tz-medveten): W}. Returnerar kWh per dygn och timmarna i kW."""
    now = now.astimezone(SWE)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out = {k + "_kwh": 0.0 for k in DAY_NAMES}
    have = {k: False for k in DAY_NAMES}
    left = 0.0
    hours = []
    for t in sorted(hourly_w):
        w = hourly_w[t]
        if w is None:
            continue
        t = t.astimezone(SWE)
        idx = (t.date() - day0.date()).days
        if not 0 <= idx < len(DAY_NAMES):
            continue
        kwh = max(0.0, float(w)) / 1000.0
        out[DAY_NAMES[idx] + "_kwh"] += kwh
        have[DAY_NAMES[idx]] = True
        if idx == 0:
            end = t + timedelta(hours=1)
            if end > now:                       # kvar av timmen
                left += kwh * min(1.0, (end - max(t, now)).total_seconds() / 3600.0)
        hours.append({"t": t.isoformat(), "kw": round(kwh, 2), "d": idx})
    res = {k: (round(v, 1) if have[k[:-4]] else None) for k, v in out.items()}
    res["today_left_kwh"] = round(left, 1) if have["today"] else None
    res["produced_today_kwh"] = round(produced_today_kwh, 1) if produced_today_kwh is not None else None
    res["hours"] = hours
    return res


def load(conn, now=None):
    """Läser prognosen och dagens produktion ur databasen. None om huset inte har solceller."""
    from sqlalchemy import text
    import weather
    now = (now or datetime.now(SWE)).astimezone(SWE)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        has_pv = conn.execute(text("SELECT 1 FROM sensor_log WHERE pv_power_w > 50 AND timestamp > now() - interval '14 days' LIMIT 1")).fetchone()
    except Exception:
        conn.rollback()
        return None
    if not has_pv:
        return None
    produced = conn.execute(text("SELECT sum(pv_power_w) / 60000.0 FROM sensor_log WHERE timestamp >= :a AND pv_power_w > 0"),
                            {"a": day0}).fetchone()
    try:
        rows = conn.execute(text("SELECT timestamp, cloud_cover FROM weather_forecast WHERE timestamp >= :a AND timestamp < :b "
                                 "ORDER BY timestamp"), {"a": day0, "b": day0 + timedelta(days=3)}).fetchall()
    except Exception:
        conn.rollback()
        rows = []
    profile = None
    try:
        import learning
        profile = learning.get_solar_profile()
    except Exception:
        pass
    hourly = {}
    for ts, cloud in rows:
        t = ts if ts.tzinfo else ts.replace(tzinfo=SWE)
        t = t.astimezone(SWE)
        hourly[t] = weather.get_smart_solar_w(float(cloud or 0.0), t, profile)
    return summarize(hourly, now, float(produced[0]) if produced and produced[0] is not None else None)


def text_line(d):
    """En rad i klartext, t.ex. 'Solen: idag 18 kWh (6 kvar), imorgon 24 kWh'."""
    if not d or d.get("today_kwh") is None:
        return None
    fmt = lambda v: f"{v:.0f}" if v >= 10 else f"{v:.1f}".replace(".", ",")
    parts = [f"idag {fmt(d['today_kwh'])} kWh"]
    if d.get("today_left_kwh") is not None:
        parts[0] += f" ({fmt(d['today_left_kwh'])} kvar)"
    if d.get("tomorrow_kwh") is not None:
        parts.append(f"imorgon {fmt(d['tomorrow_kwh'])} kWh")
    if d.get("day_after_kwh") is not None:
        parts.append(f"i övermorgon {fmt(d['day_after_kwh'])} kWh")
    return "Solprognos: " + ", ".join(parts)
