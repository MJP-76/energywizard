"""Solis hybrid via Pho3niX90/solis_modbus: RC Force Charge/Discharge + effekt i W, och omskrivning
innan växelriktarens RC Timeout (standard 5 min) släpper tvångsladdningen. Namnen ur integrationens källa."""
from unittest.mock import patch

import yaml

from discovery import discover_house
from drivers.battery_generic import GenericBatteryDriver
from house_config import build_battery_driver
from test_solax_modbus_battery import _builder


def _e(eid, name, dc=None, u=None, st="1"):
    return {"e": eid, "n": name, "a": None, "d": "dev_solis", "dn": "Solis S6-EH3P12K-H", "m": "Solis",
            "mo": "S6-EH3P12K-H", "dc": dc, "u": u, "st": st}


SOLIS = [
    _e("sensor.solis_battery_soc", "Solis Battery SOC", "battery", "%", "62"),
    _e("sensor.solis_battery_power", "Solis Battery Power", "power", "W", "1200"),
    _e("select.solis_storage_mode", "Solis Storage Mode", st="Self-Use"),
    _e("select.solis_rc_force_charge_discharge", "Solis RC Force Charge/Discharge", st="None"),
    _e("number.solis_rc_force_battery_charge_power", "Solis RC Force Battery Charge Power", "power", "W", "1500"),
    _e("number.solis_rc_force_battery_discharge_power", "Solis RC Force Battery Discharge Power", "power", "W", "1500"),
]
RC = "select.solis_rc_force_charge_discharge"


def test_solis_kanns_igen():
    b = discover_house(SOLIS)["battery"]
    gs = b["generic_suggestion"]
    assert b["control_preset"] == "solis_modbus" and gs["keepalive_s"] == 180
    assert gs["modes"] == {"auto": {RC: "None"}, "charge": {RC: "Solis RC Force Battery Charge"},
                           "discharge": {RC: "Solis RC Force Battery Discharge"}}
    assert gs["entities"]["charge_power"] == "number.solis_rc_force_battery_charge_power"
    assert "select.solis_storage_mode" not in str(gs["modes"])          # växelriktarens eget läge rörs aldrig


def test_yaml_ger_styrbar_drivrutin_med_keepalive():
    text = _builder()({"cars": [], "battery": discover_house(SOLIS)["battery"]})
    assert "keepalive_s: 180" in text
    drv = build_battery_driver(yaml.safe_load(text))
    assert drv.supported_intents() == {"auto", "charge", "discharge"}
    assert drv._keepalive == 180


def test_tvangsladdning_skrivs_om_fore_tidsgransen():
    gs = discover_house(SOLIS)["battery"]["generic_suggestion"]
    drv = GenericBatteryDriver(entities=gs["entities"], modes=gs["modes"], keepalive_s=gs["keepalive_s"])
    with patch("homeassistant.get_attribute", return_value=None), \
         patch("homeassistant.set_number", return_value=True) as num, \
         patch("homeassistant.set_select", return_value=True) as sel:
        assert drv.apply_intent("charge", 3000, now=1000)
        num.assert_called_with("number.solis_rc_force_battery_charge_power", 3000)
        sel.assert_called_with(RC, "Solis RC Force Battery Charge")
        sel.reset_mock()
        assert not drv.refresh(now=1000 + 179)                         # för tidigt
        assert drv.refresh(now=1000 + 180)                             # före RC Timeout på 300 s
        sel.assert_called_once_with(RC, "Solis RC Force Battery Charge")
        sel.reset_mock()
        assert drv.apply_intent("auto", now=1300)
        sel.assert_called_once_with(RC, "None")
        assert not drv.refresh(now=5000)                               # auto hålls inte vid liv
