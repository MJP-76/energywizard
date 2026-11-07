"""Historikvyn (smartbox/energy_history.py): periodgränser i svensk tid och sammanfattningen."""
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartbox")))

from energy_history import SWE, period_start, summarize, RANGES


def test_perioder_borjar_vid_svensk_midnatt():
    now = datetime(2026, 11, 2, 14, 30, tzinfo=SWE)
    assert period_start(now, "today") == datetime(2026, 11, 2, tzinfo=SWE)
    assert period_start(now, "7d") == datetime(2026, 10, 27, tzinfo=SWE)
    assert period_start(now, "30d") == datetime(2026, 10, 4, tzinfo=SWE)


def test_sammanfattning_sol_och_batteri():
    t = {"used_kwh": 12.0, "solar_kwh": 29.0, "bought_kwh": 2.7, "sold_kwh": 14.0, "battery_in_kwh": 5.7, "battery_out_kwh": 0.0}
    txt = summarize(t)
    assert "Solen gav 242 % av det huset använde." in txt
    assert "78 % av förbrukningen täcktes utan att köpa el." in txt
    assert "Batteriet tog in 5.7 kWh och gav tillbaka 0.0 kWh." in txt


def test_sammanfattning_utan_sol_eller_data():
    assert summarize({"used_kwh": 10.0, "solar_kwh": None, "bought_kwh": 10.0}) is None
    assert summarize(None) is None and summarize({"used_kwh": 0}) is None


def test_alla_intervall_har_hinkstorlek():
    assert set(RANGES) == {"24h", "7d", "30d", "1y"}


def test_oandliga_tal_blir_tomma():
    """#186: 'Infinity'/'NaN' i äldre loggrader gjorde att historiken inte gick att skicka som JSON (tom sida)."""
    import energy_history as eh
    assert eh._fin(float("inf")) is None and eh._fin(float("nan")) is None and eh._fin(None) is None
    assert eh._fin(1.5) == 1.5
    from decimal import Decimal
    assert eh._fin(Decimal("Infinity")) is None and eh._fin(Decimal("2.25")) == 2.25
