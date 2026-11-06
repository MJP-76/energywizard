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
    assert wd._battery_sign_hint({"pv_power_w": 0, "net_power": 100, "battery_power_w": 50}) is None       # huset positivt
    assert h["flip_ok"] and h["pv_w"] == 200 and h["net_w"] == 400 and h["battery_w"] == 1000


def test_delarna_visas_aven_nar_omvant_tecken_inte_hjalper():
    """#139: huset negativt utan att ett omvänt batteritecken räddar det - visa delarna, ingen knapp."""
    h = _wd()._battery_sign_hint({"pv_power_w": 0, "net_power": -2000, "battery_power_w": 100})
    assert h and not h["flip_ok"] and h["house_w"] == -2100
    h2 = _wd()._battery_sign_hint({"pv_power_w": 300, "net_power": -1500, "battery_power_w": None})
    assert h2 and not h2["flip_ok"] and h2["battery_w"] is None


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


def test_orimlig_batterieffekt_ar_fel_givare_inte_fel_tecken():
    """#139: batteriet visar 18,2 kW - fel givare. Ingen vänd-knapp, tydlig text."""
    h = _wd()._battery_sign_hint({"pv_power_w": 200, "net_power": 400, "battery_power_w": 18200})
    assert h and h["battery_implausible"] and not h["flip_ok"]
    h2 = _wd()._battery_sign_hint({"pv_power_w": 200, "net_power": 400, "battery_power_w": -18200})   # även "urladdning"
    assert h2 and h2["battery_implausible"]


def test_motorn_raknar_inte_in_orimlig_batterieffekt():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "smartbox" / "main.py").read_text(encoding="utf-8")
    assert "_bat_max = max(" in src and "house_consumption_w = solar_prod_w + avg_net - _bat_w" in src
