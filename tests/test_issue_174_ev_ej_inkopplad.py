"""#174: en elbil som inte är inkopplad (laddboxens status 'not_connected') ska inte räknas som laddande - varken av
batteriet, manuellt laddtvång eller kontaktorskyddet."""
from datetime import datetime, timedelta
from pathlib import Path

from gpm import GlobalPriorityManager

MAIN = (Path(__file__).resolve().parent.parent / "smartbox" / "main.py").read_text(encoding="utf-8")


def test_inkopplad_kanner_igen_garo_och_ocpp():
    ns = {}
    src = MAIN[MAIN.index("_NOT_PLUGGED = {"):MAIN.index("def update_soc_tracker")]
    exec(src, ns)
    cc = ns["charger_connected"]
    for st in ("not_connected", "Not connected", "disconnected", "Available", "unknown", None):
        assert cc({"status": st}) is False, st
    for st in ("charging", "awaiting_start", "ready_to_charge", "completed", "Preparing", "SuspendedEV"):
        assert cc({"status": st}) is True, st
    assert cc(None) is False


def test_batteriet_utgar_fran_uppmatt_laddning():
    assert "_ev_on = ev_kw_now > 1.0" in MAIN
    assert 'limit_a", 0) >= EV_MIN_CHARGE_AMPS for v in (gpm_actions' not in MAIN


def _st(connected, **kw):
    return {"now": datetime(2026, 11, 6, 17, 0), "car_ids": ["tesla"], "tesla_connected": connected, "tesla_soc": 60, **kw}


def test_manuellt_tvang_vantar_pa_kabeln():
    a = GlobalPriorityManager().evaluate(_st(False, tesla_force_amps=16))
    assert a.get("tesla_limit_a", 0) == 0
    assert any("inte inkopplad" in l for l in a["log"])
    a2 = GlobalPriorityManager().evaluate(_st(True, tesla_force_amps=16))
    assert a2.get("tesla_limit_a") == 16


def test_kontaktorskyddet_slapper_nar_bilen_inte_ar_inkopplad():
    g = GlobalPriorityManager()
    g.ev_charging_since["tesla"] = datetime(2026, 11, 6, 16, 50)
    a = g.evaluate(_st(False))
    assert not any("BATTERISKYDD" in l for l in a["log"]) and g.ev_charging_since.get("tesla") is None
