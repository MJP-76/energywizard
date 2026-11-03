"""HomeWizard (HA:s inbyggda homewizard-integration): P1-mätaren som elmätare med ström per fas, och
Plug-In Battery som styrs via 'Battery group charging strategy' på P1-mätaren. Alternativen är HA:s interna
nycklar (zero, zero_charge_only, standby, to_full), inte visningsnamnen."""
from unittest.mock import patch

import yaml

from discovery import discover_house
from house_config import build_battery_driver
from test_solax_modbus_battery import _builder


def _e(eid, name, dev, model, dc=None, u=None, st="1"):
    return {"e": eid, "n": name, "a": None, "d": dev, "dn": f"HomeWizard {model}", "m": "HomeWizard", "mo": model,
            "dc": dc, "u": u, "st": st}


P1 = [
    _e("sensor.p1_meter_power_phase_1", "P1 Meter Power phase 1", "dev_p1", "HWE-P1", "power", "W", "800"),
    _e("sensor.p1_meter_battery_group_power", "P1 Meter Battery group power", "dev_p1", "HWE-P1", "power", "W", "-300"),
    _e("sensor.p1_meter_power", "P1 Meter Power", "dev_p1", "HWE-P1", "power", "W", "1500"),
    _e("sensor.p1_meter_current_phase_1", "P1 Meter Current phase 1", "dev_p1", "HWE-P1", "current", "A", "4.1"),
    _e("sensor.p1_meter_current_phase_2", "P1 Meter Current phase 2", "dev_p1", "HWE-P1", "current", "A", "2.0"),
    _e("sensor.p1_meter_current_phase_3", "P1 Meter Current phase 3", "dev_p1", "HWE-P1", "current", "A", "1.2"),
    _e("select.p1_meter_battery_group_charging_strategy", "P1 Meter Battery group charging strategy", "dev_p1", "HWE-P1", st="zero"),
]
BAT = [
    _e("sensor.plug_in_battery_state_of_charge", "Plug-In Battery State of charge", "dev_bat", "HWE-BAT", "battery", "%", "55"),
    _e("sensor.plug_in_battery_power", "Plug-In Battery Power", "dev_bat", "HWE-BAT", "power", "W", "-300"),
]


def test_p1_som_elmatare_med_totaleffekt_och_strom_per_fas():
    pm = discover_house(P1)["power_meter"]
    assert pm["driver"] == "power_w"
    assert pm["entities"] == {"power_w": "sensor.p1_meter_power", "current_l1": "sensor.p1_meter_current_phase_1",
                              "current_l2": "sensor.p1_meter_current_phase_2", "current_l3": "sensor.p1_meter_current_phase_3"}


def test_plug_in_battery_styrs_via_p1_matarens_val():
    b = discover_house(P1 + BAT)["battery"]
    gs = b["generic_suggestion"]
    assert b["soc_entity"] == "sensor.plug_in_battery_state_of_charge"
    assert gs["preset"] == "homewizard"
    assert gs["entities"]["mode_select"] == "select.p1_meter_battery_group_charging_strategy"
    assert gs["modes"] == {"auto": "zero", "hold": "zero_charge_only", "idle": "standby", "charge": "to_full"}
    text = _builder()({"cars": [], "battery": b})
    drv = build_battery_driver(yaml.safe_load(text))
    assert drv.supported_intents() == {"auto", "hold", "idle", "charge"}
    with patch("homeassistant.set_select", return_value=True) as sel:
        assert drv.apply_intent("idle")
        sel.assert_called_once_with("select.p1_meter_battery_group_charging_strategy", "standby")


def test_p1_utan_batteri_ger_inget_batteri():
    assert discover_house(P1)["battery"] is None
