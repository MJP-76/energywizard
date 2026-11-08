"""ev_in_meter.py: ser mätaren elbilen? (Energy Pilot-idé, Emil 2026-11-08)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "smartbox"))
import control_alerts  # noqa: E402
import ev_in_meter as em  # noqa: E402


def hist(with_car: bool):
    rows = []
    for d in range(10):
        for h in range(24):
            house = 1.0 + (0.5 if 17 <= h <= 20 else 0)
            ev = 7.0 if h in (1, 2, 3) and d % 2 == 0 else 0.0
            rows.append((h, house + (ev if with_car else 0.0), ev))
    return rows


def test_mataren_ser_bilen():
    ans, r, n = em.detect(hist(True))
    assert ans is True and r == 1.0 and n >= 6


def test_mataren_ser_inte_bilen():
    ans, r, _ = em.detect(hist(False))
    assert ans is False and r == 0.0
    assert "inte" in em.text(ans, r)


def test_for_lite_data_vet_inte():
    assert em.detect(hist(True)[:30])[0] is None


def test_varning_i_bada_granssnitten():
    out = control_alerts.build({"ev_in_meter": json.dumps({"text": em.text(False, 0.05)})})
    assert out[0]["device"] == "Elmätaren"
    assert control_alerts.build({"ev_in_meter": "ok"}) == []
