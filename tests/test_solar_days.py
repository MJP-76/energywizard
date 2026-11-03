"""Solprognos per dygn (smartbox/solar_days.py)."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from solar_days import summarize, text_line

SWE = ZoneInfo("Europe/Stockholm")


def _day(d0, peak_w):
    """Enkel solkurva 06-18 med topp kl 12."""
    return {d0 + timedelta(hours=h): max(0.0, peak_w * (1 - abs(h - 12) / 6)) for h in range(24)}


def test_summerar_per_dygn_och_kvar_idag():
    d0 = datetime(2026, 6, 10, tzinfo=SWE)
    hourly = {**_day(d0, 6000), **_day(d0 + timedelta(days=1), 3000), **_day(d0 + timedelta(days=2), 0)}
    r = summarize(hourly, d0 + timedelta(hours=12, minutes=30), produced_today_kwh=14.2)
    assert r["today_kwh"] == 36.0                  # 6 kW topp: 6 × (1+2+…+5)/6×2 + 6 = 36 kWh
    assert r["tomorrow_kwh"] == 18.0
    assert r["day_after_kwh"] == 0.0
    # Kvar: halva 12-timmen (6 kWh/2) + 13..17
    assert r["today_left_kwh"] == round(3.0 + 5 + 4 + 3 + 2 + 1, 1)
    assert r["produced_today_kwh"] == 14.2
    assert {h["d"] for h in r["hours"]} == {0, 1, 2}


def test_saknade_dygn_blir_none_och_text():
    d0 = datetime(2026, 6, 10, tzinfo=SWE)
    r = summarize(_day(d0, 2000), d0 + timedelta(hours=20))
    assert r["tomorrow_kwh"] is None and r["today_left_kwh"] == 0.0
    assert text_line(r) == "Solprognos: idag 12 kWh (0,0 kvar)"
    assert text_line(None) is None
