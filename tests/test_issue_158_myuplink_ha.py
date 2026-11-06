"""#158: NIBE via HA:s myUplink-integration ska hittas (givarkoder BT1/BT2/BT3/BT7/BT50), och en nätverksskanners post
för pumpens nätverkskort (NetAlertX, tillverkare "Nibe") får inte tas för värmepumpen."""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

import homeassistant
import house_config
from discovery import discover_house
from drivers.heatpump_ha_entities import HaEntitiesHeatPumpDriver


def ent(e, n, d, dn, m, dc=None, u=None, st="1"):
    return {"e": e, "n": n, "a": None, "d": d, "dn": dn, "m": m, "mo": None, "dc": dc, "u": u, "st": st}


NETALERTX = [ent("device_tracker.nibe_f750", "Nibe F750", "dev_nax", "NetAlertX", "Nibe"),
             ent("sensor.nibe_f750_ip", "IP", "dev_nax", "NetAlertX", "Nibe", st="192.168.1.50")]
F750 = [ent("sensor.f750_cu_utomhustemperatur_40004", "F750 Cu Utomhustemperatur (BT1) (40004)", "dev_f750", "F750 Cu", "NIBE", "temperature", "°C", "2.4"),
        ent("sensor.f750_cu_framledning_40008", "F750 Cu Framledning (BT2) (40008)", "dev_f750", "F750 Cu", "NIBE", "temperature", "°C", "31"),
        ent("sensor.f750_cu_returledning_40012", "F750 Cu Returledning (BT3) (40012)", "dev_f750", "F750 Cu", "NIBE", "temperature", "°C", "27"),
        ent("sensor.f750_cu_bt10", "F750 Cu Köldbärare in (BT10)", "dev_f750", "F750 Cu", "NIBE", "temperature", "°C", "5"),
        ent("sensor.f750_cu_varmvatten_topp_40013", "F750 Cu Varmvatten topp (BT7) (40013)", "dev_f750", "F750 Cu", "NIBE", "temperature", "°C", "50"),
        ent("sensor.f750_cu_rumstemperatur_40033", "F750 Cu Rumstemperatur (BT50) (40033)", "dev_f750", "F750 Cu", "NIBE", "temperature", "°C", "18.2"),
        ent("number.f750_cu_gradminuter_40940", "F750 Cu Gradminuter (40940)", "dev_f750", "F750 Cu", "NIBE", st="-120")]


def test_natverksskannerns_post_ar_ingen_varmepump():
    hp = discover_house(NETALERTX)["heat_pump"]
    assert hp is None or hp.get("source") == "modbus_configured_on_server"


def test_nibe_via_myuplink_hittas_med_givarkoderna():
    hp = discover_house(NETALERTX + F750)["heat_pump"]
    assert hp["driver"] == "ha_entities" and hp["driver_known"]
    assert hp["entities"] == {"outdoor_temp": "sensor.f750_cu_utomhustemperatur_40004", "forward_temp": "sensor.f750_cu_framledning_40008",
                              "return_temp": "sensor.f750_cu_returledning_40012", "water_temp": "sensor.f750_cu_varmvatten_topp_40013",
                              "indoor_temp": "sensor.f750_cu_rumstemperatur_40033", "degree_minutes": "number.f750_cu_gradminuter_40940"}

    root = Path(__file__).resolve().parent.parent
    cwd = os.getcwd()
    os.chdir(root / "webdashboard")
    try:
        mod = sys.modules.get("webdashboard_app")
        if mod is None:
            spec = importlib.util.spec_from_file_location("webdashboard_app", root / "webdashboard" / "app.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["webdashboard_app"] = mod
            spec.loader.exec_module(mod)
        text = mod._build_house_config_yaml({"heat_pump": hp})
    finally:
        os.chdir(cwd)
    assert "# room_target: number.XXX" in text
    cfg = yaml.safe_load(text)
    drv = house_config.build_heat_pump_driver(cfg)
    assert isinstance(drv, HaEntitiesHeatPumpDriver)
    states = {e["e"]: float(e["st"]) for e in F750}
    with patch.object(homeassistant, "_get_numeric_state", side_effect=lambda e: states.get(e)):
        s = drv.read_sensors()
    assert s["outdoor_temp"] == 2.4 and s["indoor_temp"] == 18.2 and s["forward_temp"] == 31 and s["degree_minutes"] == -120
    assert drv.set_room_temp(21) is False                         # inget börvärde valt -> styr inte


def test_rumsborvarde_skrivs_bara_nar_det_valts(monkeypatch):
    import shadow
    monkeypatch.setattr(shadow, "active", lambda: False)
    with patch.object(homeassistant, "set_number", return_value=True) as sn:
        assert HaEntitiesHeatPumpDriver({"room_target": "number.f750_rum"}).set_room_temp(20.5)
    sn.assert_called_once_with("number.f750_rum", 20.5)
