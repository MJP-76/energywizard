"""control_journal.py: "Höll vi planen?" - beställt mot faktiskt per enhet (FTW-idé, Emil 2026-11-07)."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "smartbox"))
import control_journal as cj  # noqa: E402

T0 = datetime(2026, 11, 8, 12, 0)


def test_elbil():
    assert cj.check_ev("Tesla", 16, {"current_a": 15})[1] is True
    assert cj.check_ev("Tesla", 16, {"current_a": 10})[1] is False
    assert cj.check_ev("Tesla", 16, {"current_a": 0})[4] == "Laddade inte"
    assert cj.check_ev("Tesla", 0, {"current_a": 0})[1] is True
    assert cj.check_ev("Tesla", 0, {"current_a": 10})[4] == "Laddade trots paus"
    assert cj.check_ev("Tesla", 16, {"current_a": 10}, "Laddboxen håller bilen")[4] == "Laddboxen håller bilen"
    assert cj.check_ev("Tesla", 16, {"current_a": None}) is None


def test_pump_och_batteri():
    assert cj.check_pump(21.0, 20.6)[1] is True
    assert cj.check_pump(21.0, 19.0)[1] is False
    assert cj.check_pump(21.0, None) is None
    assert cj.check_battery("checking", "", "charge") is None
    assert cj.check_battery("not_following", "Laddar inte", "charge")[4] == "Laddar inte"


def rows(seq, dev="Tesla"):
    return [(T0 + timedelta(minutes=i), dev, ok, "16 A", "10 A", None if ok else "Lägre ström") for i, ok in enumerate(seq)]


def test_sammanfattning_andel_och_avvikelser():
    s = cj.summarize(rows([True] * 50 + [False] * 10 + [True] * 40))
    d = s[0]
    assert d["pct"] == 90 and d["deviation_minutes"] == 10 and len(d["deviations"]) == 1
    assert d["deviations"][0]["start"].startswith("2026-11-08T12:50")


def test_korta_avbrott_slas_ihop_enstaka_minuter_ignoreras():
    s = cj.summarize(rows([False] * 5 + [True] * 2 + [False] * 5 + [True] * 10 + [False] + [True] * 10))
    d = s[0]
    assert len(d["deviations"]) == 1 and d["deviations"][0]["minutes"] == 10


def test_ordning_batteri_pump_bilar():
    r = rows([True], "Tesla") + rows([True], "Värmepump") + rows([True], "Husbatteri")
    assert [d["device"] for d in cj.summarize(r)] == ["Husbatteri", "Värmepump", "Tesla"]
