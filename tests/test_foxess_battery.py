"""FoxESS: lokalt via nathanmarlor/foxess_modbus (lägen + effekt i kW) och via molnet med
macxq/foxess-ha (bara lägen). Lägesnamnen är integrationernas egna."""
from unittest.mock import patch

import yaml

from discovery import discover_house
from drivers.battery_generic import GenericBatteryDriver
from house_config import build_battery_driver
from test_solax_modbus_battery import _builder


def _e(eid, name, dc=None, u=None, st="1"):
    return {"e": eid, "n": name, "a": None, "d": "dev_fox", "dn": "FoxESS - Modbus", "m": "FoxESS", "mo": "H3-10",
            "dc": dc, "u": u, "st": st}


MODBUS = [
    _e("sensor.battery_soc", "Battery SoC", "battery", "%", "55"),
    _e("sensor.battery_charge", "Battery Charge", "power", "kW", "1.2"),
    _e("sensor.battery_discharge", "Battery Discharge", "power", "kW", "0"),
    _e("select.work_mode", "Work Mode", st="Self Use"),
    _e("number.force_charge_power", "Force Charge Power", "power", "kW", "10"),
    _e("number.force_discharge_power", "Force Discharge Power", "power", "kW", "10"),
]

CLOUD = [
    {**_e("sensor.foxess_bat_soc", "FoxESS - Bat SoC", "battery", "%", "70"), "dn": "60BH1234567"},
    {**_e("select.foxess_work_mode", "FoxESS - Work Mode", st="Self-Use"), "dn": "60BH1234567"},
]


def test_foxess_modbus_kanns_igen():
    b = discover_house(MODBUS)["battery"]
    gs = b["generic_suggestion"]
    assert b["control_preset"] == "foxess_modbus"
    assert gs["entities"]["mode_select"] == "select.work_mode"
    assert gs["entities"]["charge_power"] == "number.force_charge_power"
    assert gs["modes"] == {"auto": "Self Use", "hold": "Back-up", "charge": "Force Charge", "discharge": "Force Discharge"}


def test_foxess_moln_bara_lagen():
    b = discover_house(CLOUD)["battery"]
    gs = b["generic_suggestion"]
    assert b["control_preset"] == "foxess_cloud"
    assert gs["modes"] == {"auto": "Self-Use", "hold": "Backup"}


def test_yaml_ger_styrbar_drivrutin():
    for ents, preset, want in ((MODBUS, "foxess_modbus", {"auto", "hold", "charge", "discharge"}),
                               (CLOUD, "foxess_cloud", {"auto", "hold"})):
        text = _builder()({"cars": [], "battery": discover_house(ents)["battery"]})
        assert f"förifyllt för {preset}" in text
        drv = build_battery_driver(yaml.safe_load(text))
        assert drv.supported_intents() == want, preset


def test_effekt_skrivs_i_kw_och_hogst_max():
    drv = GenericBatteryDriver(entities={"soc": "sensor.battery_soc", "mode_select": "select.work_mode",
                                         "charge_power": "number.force_charge_power"},
                               modes={"auto": "Self Use", "charge": "Force Charge"})
    attrs = {"unit_of_measurement": "kW", "max": 10.4}
    with patch("homeassistant.get_attribute", side_effect=lambda e, a: attrs.get(a)), \
         patch("homeassistant.set_number", return_value=True) as num, \
         patch("homeassistant.set_select", return_value=True) as sel:
        assert drv.apply_intent("charge", 3500)
        num.assert_called_once_with("number.force_charge_power", 3.5)
        sel.assert_called_once_with("select.work_mode", "Force Charge")
        num.reset_mock()
        drv.apply_intent("charge", 20000)
        num.assert_called_once_with("number.force_charge_power", 10.4)       # inverterns tak


def test_effekt_i_watt_som_forut():
    drv = GenericBatteryDriver(entities={"soc": "s", "mode_select": "select.m", "charge_power": "number.p"},
                               modes={"charge": "Laddning"})
    with patch("homeassistant.get_attribute", return_value=None), \
         patch("homeassistant.set_number", return_value=True) as num, \
         patch("homeassistant.set_select", return_value=True):
        drv.apply_intent("charge", 2499.6)
        num.assert_called_once_with("number.p", 2500)
