"""Planerad last för Predbat (smartbox/planned_load.py). Predbat läser load_forecast som en
STIGANDE kWh-serie och räknar lasten per minut som skillnaden mellan två punkter
(batpred apps/predbat/fetch.py: fetch_extra_load_forecast + get_from_incrementing)."""
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartbox")))

from planned_load import build_forecast, SWE


def _kwh_between(predbat, a, b):
    """Energi mellan a och b enligt den kumulativa serien (linjär interpolation, som Predbats utjämning)."""
    pts = sorted((datetime.fromisoformat(k), v) for k, v in predbat.items())

    def at(t):
        if t <= pts[0][0]:
            return pts[0][1]
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)
        return pts[-1][1]
    return at(b) - at(a)


def _slots(car, start, n, kw):
    return [(car, start + timedelta(minutes=15 * i), kw) for i in range(n)]


NOW = datetime(2026, 11, 2, 1, 50, tzinfo=SWE)


def test_tom_plan_ger_noll_och_tom_serie():
    kw, a = build_forecast([], NOW)
    assert kw == 0 and a["predbat"] == {} and a["slottar"] == [] and a["totalt_kwh"] == 0


def test_en_timme_11_kw_blir_11_kwh_pa_ratt_plats():
    rows = _slots("tesla", datetime(2026, 11, 2, 2, 0), 4, 11.0)
    kw, a = build_forecast(rows, NOW)
    p = a["predbat"]
    t = lambda h, m: datetime(2026, 11, 2, h, m, tzinfo=SWE)
    assert kw == 0                                          # klockan är 01:50, inget laddar nu
    assert abs(_kwh_between(p, t(2, 0), t(3, 0)) - 11.0) < 1e-6
    assert _kwh_between(p, t(1, 50), t(2, 0)) == 0          # ingen energi smetas ut före slotten
    assert _kwh_between(p, t(3, 0), t(4, 0)) == 0
    assert a["totalt_kwh"] == 11.0


def test_serien_ar_stigande_och_har_tidszon():
    rows = _slots("tesla", datetime(2026, 11, 2, 2, 0), 2, 11.0) + _slots("nissan", datetime(2026, 11, 2, 4, 0), 1, 3.7)
    _, a = build_forecast(rows, NOW)
    pts = sorted((datetime.fromisoformat(k), v) for k, v in a["predbat"].items())
    assert all(t.tzinfo is not None for t, _ in pts)        # Predbat kräver tidszon (str2time)
    assert all(v1 >= v0 for (_, v0), (_, v1) in zip(pts, pts[1:]))


def test_lucka_mellan_slottar_far_ingen_energi():
    rows = _slots("tesla", datetime(2026, 11, 2, 2, 0), 1, 11.0) + _slots("nissan", datetime(2026, 11, 2, 4, 0), 1, 3.7)
    _, a = build_forecast(rows, NOW)
    t = lambda h, m: datetime(2026, 11, 2, h, m, tzinfo=SWE)
    assert _kwh_between(a["predbat"], t(2, 15), t(4, 0)) == 0
    assert abs(_kwh_between(a["predbat"], t(4, 0), t(4, 15)) - 3.7 / 4) < 1e-6


def test_tva_bilar_i_samma_slott_summeras():
    rows = [("tesla", datetime(2026, 11, 2, 2, 0), 11.0), ("nissan", datetime(2026, 11, 2, 2, 0), 3.7)]
    _, a = build_forecast(rows, NOW)
    assert a["slottar"] == [{"start": "2026-11-02T02:00+01:00", "slut": "2026-11-02T02:15+01:00",
                             "kw": 14.7, "bilar": ["nissan", "tesla"]}]


def test_pagaende_slott_raknas_bara_for_aterstoden_och_ger_kw_nu():
    rows = _slots("tesla", datetime(2026, 11, 2, 1, 45), 1, 12.0)
    kw, a = build_forecast(rows, NOW)                       # 01:50, 10 min kvar av slotten
    assert kw == 12.0
    assert abs(a["totalt_kwh"] - 2.0) < 1e-6


def test_passerade_slottar_och_nollslottar_tas_bort():
    rows = [("tesla", datetime(2026, 11, 2, 1, 0), 11.0), ("tesla", datetime(2026, 11, 2, 3, 0), 0.0),
            ("tesla", datetime(2026, 11, 2, 3, 15), None)]
    kw, a = build_forecast(rows, NOW)
    assert a["predbat"] == {} and kw == 0


def test_sommartid_naiv_lokaltid_tolkas_som_svensk_tid():
    rows = [("tesla", datetime(2026, 7, 1, 2, 0), 4.0)]
    _, a = build_forecast(rows, datetime(2026, 7, 1, 1, 0, tzinfo=SWE))
    assert a["slottar"][0]["start"] == "2026-07-01T02:00+02:00"
