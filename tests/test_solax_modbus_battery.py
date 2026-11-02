"""Batteristyrning via wills106/homeassistant-solax-modbus: entitetsväljaren känner igen Growatt- och
Solax-varianten, YAML:n går att läsa in och drivrutinen skickar rätt val (lägesnamnen är integrationens egna)."""
from unittest.mock import call, patch

import yaml

from discovery import discover_house
from drivers.battery_generic import GenericBatteryDriver
from house_config import build_battery_driver


def _e(eid, name, dc=None, u=None, st="1"):
    return {"e": eid, "n": name, "a": None, "d": "dev_inv", "dn": "Growatt SPH", "m": "Growatt", "mo": "SPH",
            "dc": dc, "u": u, "st": st}


GROWATT = [
    _e("sensor.growatt_battery_soc", "Growatt Battery SOC", "battery", "%", "64"),
    _e("sensor.growatt_pv_power", "Growatt PV Power", "power", "W", "3200"),
    _e("sensor.growatt_battery_charge_power", "Growatt Battery Charge Power", "power", "W", "1500"),
    _e("sensor.growatt_battery_discharge_power", "Growatt Battery Discharge Power", "power", "W", "0"),
    _e("select.growatt_time_1_mode", "Growatt Time 1 Mode"),
    _e("button.growatt_time_1_update", "Growatt Time 1 Update"),
]

SOLAX = [
    {**_e("sensor.solax_battery_capacity", "Solax Battery Capacity", "battery", "%", "70"), "dn": "SolaX", "m": "SolaX"},
    {**_e("sensor.solax_battery_power_charge", "Solax Battery Power Charge", "power", "W", "-800"), "dn": "SolaX", "m": "SolaX"},
    {**_e("select.solax_charger_use_mode", "Solax Charger Use Mode"), "dn": "SolaX", "m": "SolaX"},
    {**_e("select.solax_manual_mode_select", "Solax Manual Mode Select"), "dn": "SolaX", "m": "SolaX"},
]


def test_growatt_via_solax_modbus_kanns_igen():
    b = discover_house(GROWATT)["battery"]
    gs = b["generic_suggestion"]
    assert b["control_preset"] == "solax_modbus_growatt"
    assert gs["entities"]["mode_select"] == "select.growatt_time_1_mode"
    assert gs["entities"]["mode_apply_button"] == "button.growatt_time_1_update"
    assert gs["entities"]["power_charge"] == "sensor.growatt_battery_charge_power" and "power" not in gs["entities"]
    assert gs["modes"]["auto"] == "Load First" and gs["modes"]["discharge"] == "Grid First"


def test_solax_flera_val_per_lage():
    gs = discover_house(SOLAX)["battery"]["generic_suggestion"]
    assert gs["modes"]["charge"] == {"select.solax_charger_use_mode": "Manual Mode", "select.solax_manual_mode_select": "Force Charge"}
    assert gs["entities"]["power"] == "sensor.solax_battery_power_charge"        # batterieffekt, inte PV


def _builder():
    import importlib.util, os, sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "smartbox"))
    os.environ.setdefault("DASHBOARD_PASSWORD", "hemligt123")
    cwd = Path.cwd()
    os.chdir(root / "webdashboard")
    try:
        mod = sys.modules.get("webdashboard_app")
        if mod is None:
            spec = importlib.util.spec_from_file_location("webdashboard_app", root / "webdashboard" / "app.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["webdashboard_app"] = mod
            spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
    return mod._build_house_config_yaml


def test_yaml_fran_entitetsvaljaren_ger_styrbar_drivrutin():
    """Hela kedjan: förslag -> genererad house_config.yaml -> inläst -> styrbar drivrutin."""
    for ents, preset in ((SOLAX, "solax_modbus_solax"), (GROWATT, "solax_modbus_growatt")):
        text = _builder()({"cars": [], "battery": discover_house(ents)["battery"]})
        assert f"förifyllt för {preset}" in text
        cfg = yaml.safe_load(text)
        drv = build_battery_driver(cfg)
        assert {"auto", "charge", "discharge"} <= drv.supported_intents(), preset


def test_drivrutin_flera_val_och_knapp():
    drv = GenericBatteryDriver(entities={"mode_select": "select.t1", "mode_apply_button": "button.t1"},
                               modes={"auto": "Load First", "discharge": "Grid First"})
    with patch("drivers.battery_generic.homeassistant") as ha:
        ha.set_select.return_value = True; ha.press_button.return_value = True
        assert drv.apply_intent("discharge")
    ha.set_select.assert_called_once_with("select.t1", "Grid First")
    ha.press_button.assert_called_once_with("button.t1")
    multi = GenericBatteryDriver(entities={}, modes={"charge": {"select.a": "Manual Mode", "select.b": "Force Charge"}})
    assert multi.supports_control()
    with patch("drivers.battery_generic.homeassistant") as ha:
        ha.set_select.return_value = True
        assert multi.apply_intent("charge")
    assert ha.set_select.call_args_list == [call("select.a", "Manual Mode"), call("select.b", "Force Charge")]


def test_effekt_fran_separata_sensorer():
    drv = GenericBatteryDriver(entities={"power_charge": "s.c", "power_discharge": "s.d"})
    with patch("drivers.battery_generic.homeassistant") as ha:
        ha._get_numeric_state.side_effect = lambda e: {"s.c": 0.0, "s.d": 2200.0}[e]
        assert drv.read_state()["power_w"] == -2200.0
