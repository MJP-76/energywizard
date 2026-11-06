"""#166/#139: huset räknas negativt när batterisensorn har omvänt tecken - Översikt föreslår "Vänd tecknet", och valet
gäller direkt i drivrutinen (utan omstart) om house_config.yaml inte låser det."""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import homeassistant
from drivers.battery_generic import GenericBatteryDriver

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


def test_forslag_nar_huset_bara_gar_ihop_med_omvant_tecken():
    wd = _wd()
    # som i #166: sol 0,2 + nät 0,4, batteriet "laddar" 1,0 kW -> huset -0,4; vänt +1,6
    h = wd._battery_sign_hint({"pv_power_w": 200, "net_power": 400, "battery_power_w": 1000})
    assert h and h["house_w"] == -400 and h["house_w_flipped"] == 1600
    assert wd._battery_sign_hint({"pv_power_w": 200, "net_power": 1400, "battery_power_w": 1000}) is None   # huset +0,6: ok
    assert wd._battery_sign_hint({"pv_power_w": 0, "net_power": 100, "battery_power_w": 50}) is None       # för liten effekt
    assert wd._battery_sign_hint({"pv_power_w": 200, "net_power": 400, "battery_power_w": None}) is None


def test_valet_i_webben_galler_direkt_om_yaml_inte_last(monkeypatch, tmp_path):
    import ew_settings
    monkeypatch.setattr(ew_settings, "PATH", str(tmp_path / "s.json"))
    ew_settings._cache.update(mtime=None, data={})
    d = GenericBatteryDriver(entities={"power": "sensor.bat_w"})
    with patch.object(homeassistant, "get_power_w", return_value=1000.0), patch.object(homeassistant, "_get_numeric_state", return_value=None):
        assert d.read_state()["power_w"] == 1000.0
        ew_settings.update(battery_power_invert=True)
        assert d.read_state()["power_w"] == -1000.0
        locked = GenericBatteryDriver(entities={"power": "sensor.bat_w"}, power_invert=False)
        assert locked.read_state()["power_w"] == 1000.0                     # låst i house_config.yaml
