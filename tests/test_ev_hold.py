"""ev_hold.py: förklaring när bilen laddar långsammare än vi beställt (FTW-idé, Emil 2026-11-07)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "smartbox"))
import control_alerts  # noqa: E402
import ev_hold  # noqa: E402


def r(**kw):
    base = {"current_a": 10, "output_limit_a": None, "max_limit_a": None, "reason_no_current": None}
    base.update(kw)
    return base


def test_ingen_skillnad_ingen_text():
    assert ev_hold.explain(16, r(current_a=15.2)) is None


def test_pausad_eller_stannad_ingen_text():
    assert ev_hold.explain(0, r()) is None
    assert ev_hold.explain(16, r(current_a=0)) is None      # stannad laddning: egen vakt (main._check_ev_stall)
    assert ev_hold.explain(16, None) is None


def test_lastbalansering_forklaras():
    t = ev_hold.explain(16, r(current_a=10, output_limit_a=10))
    assert "håller bilen på 10 A" in t and "16 A" in t and "lastbalansering" in t


def test_laddboxens_maxgrans():
    t = ev_hold.explain(16, r(current_a=10, output_limit_a=16, max_limit_a=10))
    assert "maxgräns är 10 A" in t


def test_laddboxens_anledning():
    t = ev_hold.explain(16, r(current_a=10, reason_no_current="max_circuit_current_too_low"))
    assert "max circuit current too low" in t


def test_okanda_granser_sags_arligt():
    t = ev_hold.explain(16, r(current_a=10))
    assert "Antingen" in t and "Aktivera" in t


def test_annars_bilen():
    t = ev_hold.explain(16, r(current_a=10, reason_no_current="unknown"))
    assert "bilen som begränsar" in t


def test_kraver_fem_minuter_och_slutar_nar_det_slapper():
    w = ev_hold.HoldWatch()
    assert w.step("a", 16, r(), 0) is None
    assert w.step("a", 16, r(), 4 * 60) is None
    assert w.step("a", 16, r(), 5 * 60) is not None
    assert w.step("a", 16, r(current_a=16), 6 * 60) is None
    assert w.step("a", 16, r(), 7 * 60) is None              # börjar om


def test_kontrollvarning_for_bada_granssnitten():
    ov = {"ev_hold": json.dumps({"Tesla": "Laddboxen håller bilen på 10 A"}), "battery_follow": "ok"}
    out = control_alerts.build(ov)
    assert len(out) == 1 and out[0]["device"] == "Tesla" and out[0]["level"] == "info"
    assert control_alerts.build({"ev_hold": "ok"}) == []
    assert control_alerts.build({"battery_follow": json.dumps({"status": "not_following", "text": "x"})})[0]["device"] == "Husbatteriet"
