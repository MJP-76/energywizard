"""Skydd mot flashslitage när exportgränsen skrivs (smartbox/solar_write_guard.py)."""
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartbox")))

from solar_write_guard import should_write

T = datetime(2026, 11, 2, 12, 0)


def test_forsta_skrivningen_gar_alltid():
    assert should_write(100, None, None, T)


def test_samma_varde_skrivs_inte():
    assert not should_write(80, 80, T - timedelta(hours=1), T)


def test_start_och_stopp_av_strypning_gar_direkt():
    assert should_write(87, 100, T, T)                  # börjar strypa
    assert should_write(100, 42, T, T)                  # släpper
    assert should_write(0, 42, T, T)                    # helt stängt


def test_finjustering_vantar_fem_minuter():
    assert not should_write(70, 80, T - timedelta(minutes=2), T)
    assert should_write(70, 80, T - timedelta(minutes=5), T)


def test_sma_andringar_ignoreras():
    assert not should_write(78, 80, T - timedelta(hours=1), T)


def test_en_timme_med_regulator_ger_fa_skrivningar():
    """PI-regulatorn ändrar värdet varje minut i en timme - högst ~13 skrivningar, inte 60."""
    last, at, writes = 100, T - timedelta(hours=1), 0
    vals = [90, 84, 79, 75, 71, 68, 66, 63, 61, 60] * 6
    for m, v in enumerate(vals):
        now = T + timedelta(minutes=m)
        if should_write(v, last, at, now):
            last, at, writes = v, now, writes + 1
    assert writes <= 13
