"""#204: bil utan batterinivå (Zeekr) med schema 100 % kl 07 laddade nästan inget; climate-pump utan utegivare
räknades som tappad kontakt."""
import sys
from datetime import datetime
from pathlib import Path
import zoneinfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "smartbox"))
import decisions  # noqa: E402

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")
NOW = datetime(2026, 11, 8, 22, 0, tzinfo=SWE)
SCHED = {"zeekr": {d: {"enabled": True, "target_time": "07:00", "target_soc": 100} for d in range(7)}}


def test_okand_batteriniva_med_schema_planeras():
    t, soc, kwh, _ = decisions.get_car_plan_details(NOW, "zeekr", SCHED, None, 100)
    assert t is not None and t.hour == 7 and soc == 100
    assert kwh == (100 - decisions.UNKNOWN_SOC_ASSUMED) / 100 * 100 * 1.12


def test_okand_batteriniva_utan_schema_som_forut():
    t, _, kwh, _ = decisions.get_car_plan_details(NOW, "zeekr", {}, None, 100)
    assert t is None and kwh == 0


def test_kand_batteriniva_oforandrad():
    _, _, kwh, _ = decisions.get_car_plan_details(NOW, "zeekr", SCHED, 60, 100)
    assert abs(kwh - 40 * 1.12) < 1e-9


def test_pumpen_lever_utan_utegivare():
    src = (Path(__file__).resolve().parents[1] / "smartbox/main.py").read_text()
    assert '_pump_ok = bool(pump_data and pump_data.get("outdoor_temp") is not None)' not in src
    assert "_pump_ok = bool(pump_data) and any(" in src
