"""Felicity Solar via partach/ha_felicity: känns igen, men bara för avläsning (integrationens egen EMS styr, och dess
Operating Mode-val skriver Economic även när Backup väljs på T-REX 5/10K). Effektens tecken kan vändas med power_invert."""
from unittest.mock import patch

from discovery import discover_house
from house_config import build_battery_driver


def _e(eid, name, dc=None, u=None, st="1"):
    return {"e": eid, "n": name, "a": None, "d": "dev_fel", "dn": "Felicity T-REX-10K", "m": "Felicity Solar",
            "mo": "T-REX-10K-P3G01", "dc": dc, "u": u, "st": st}


FELICITY = [
    _e("sensor.felicity_battery_capacity", "Felicity Battery Capacity", "battery", "%", "64"),
    _e("sensor.felicity_battery_power", "Felicity Battery Power", "power", "W", "-850"),
    _e("select.felicity_operating_mode", "Felicity Operating Mode", st="General mode (self-use, load priority)"),
    _e("select.felicity_grid_mode", "Felicity Grid Mode", st="from_grid"),
]


def test_felicity_kanns_igen_men_styrs_inte():
    b = discover_house(FELICITY)["battery"]
    gs = b["generic_suggestion"]
    assert b["control_preset"] == "felicity_monitor" and "ha_felicity" in b["note"]
    assert gs["entities"] == {"soc": "sensor.felicity_battery_capacity", "power": "sensor.felicity_battery_power"}
    assert gs["modes"] == {}
    d = build_battery_driver({"battery": {"enabled": True, "driver": "generic", **gs}})
    assert not d.supports_control() and d.supported_intents() == set()
    assert not d.apply_intent("charge", 2000)


def test_power_invert():
    cfg = {"battery": {"enabled": True, "driver": "generic", "entities": {"power": "sensor.felicity_battery_power"}}}
    with patch("homeassistant._get_numeric_state", return_value=-850.0):
        assert build_battery_driver(cfg).read_state()["power_w"] == -850.0
        cfg["battery"]["power_invert"] = True
        assert build_battery_driver(cfg).read_state()["power_w"] == 850.0


def test_yaml_fran_webben_ger_lasande_drivrutin():
    import yaml
    from test_solax_modbus_battery import _builder
    text = _builder()({"cars": [], "battery": discover_house(FELICITY)["battery"]})
    drv = build_battery_driver(yaml.safe_load(text))
    assert drv.supported_intents() == set()
    assert "sensor.felicity_battery_capacity" in text
