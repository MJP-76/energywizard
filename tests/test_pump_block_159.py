"""#159: Värmepump-flikens mätvärden - uppmätt COP bara när pumpen använt minst 0,05 kWh senaste timmen."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _wd():
    mod = sys.modules.get("webdashboard_app")
    if mod is None:
        cwd = os.getcwd()
        os.chdir(ROOT / "webdashboard")
        try:
            spec = importlib.util.spec_from_file_location("webdashboard_app", ROOT / "webdashboard" / "app.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["webdashboard_app"] = mod
            spec.loader.exec_module(mod)
        finally:
            os.chdir(cwd)
    return mod


def test_cop_ur_energiloggen():
    b = _wd()._pump_block({"heat_produced_kwh_1h": 0.82, "electric_used_kwh_1h": 0.17, "forward_temp": 35.2, "cop": 3.9})
    assert b["cop_1h"] == 4.8 and b["cop_est"] == 3.9 and b["forward_temp"] == 35.2


def test_ingen_cop_nar_pumpen_knappt_gatt():
    b = _wd()._pump_block({"heat_produced_kwh_1h": 0.01, "electric_used_kwh_1h": 0.01})
    assert b["cop_1h"] is None
    assert _wd()._pump_block({})["cop_1h"] is None
