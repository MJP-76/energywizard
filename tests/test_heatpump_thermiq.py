"""Thermia via ThermIQ (thermiq/thermiq_mqtt-ha): drivrutinen läser och skriver integrationens egna entiteter,
guiden känner igen den och skriver en house_config som bygger rätt drivrutin. Ingen riktig HA eller pump."""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

import homeassistant
import house_config
from discovery import discover_house
from drivers.heatpump_thermiq import ThermIQHeatPumpDriver

P = "thermiq_mqtt_vp1"
STATES = {
    f"sensor.{P}_outdoor_t": "-3", f"sensor.{P}_indoor_t": "21", f"sensor.{P}_indoor_dec_t": "4",
    f"sensor.{P}_supplyline_t": "35", f"sensor.{P}_returnline_t": "29", f"sensor.{P}_boiler_t": "51",
    f"sensor.{P}_integral1": "-120", f"binary_sensor.{P}_compressor_on": "on",
    f"binary_sensor.{P}_alarm_indication_on": "off",
}


def _fake_state(e):
    v = STATES.get(e)
    if v is None:
        return None
    return {"on": 1.0, "off": 0.0}.get(v, float(v) if v.lstrip("-").replace(".", "").isdigit() else v)


def test_laser_thermiq_entiteterna():
    with patch.object(homeassistant, "_get_numeric_state", side_effect=_fake_state):
        s = ThermIQHeatPumpDriver(prefix="vp1").read_sensors()
    assert s["indoor_temp"] == 21.4 and s["outdoor_temp"] == -3 and s["forward_temp"] == 35
    assert s["return_temp"] == 29 and s["water_temp"] == 51 and s["degree_minutes"] == -120
    assert s["compressor_running"] is True and s["alarm_active"] == 0


def test_skriver_rumsborvarde_och_varmvatten_begransat(monkeypatch):
    import shadow
    monkeypatch.setattr(shadow, "active", lambda: False)
    calls = []
    with patch.object(homeassistant, "set_number", side_effect=lambda e, v: calls.append((e, v)) or True):
        d = ThermIQHeatPumpDriver(prefix=P)
        assert d.set_room_temp(21.5) and d.set_water_stop_temp(80) and d.set_water_start_temp(45)
        assert d.set_heating_start_temp(10) is False and d.set_operating_mode("heat") is False
    assert calls == [(f"number.{P}_indoor_requested_t", 21.5), (f"number.{P}_hotwater_stop_t", 65.0),
                     (f"number.{P}_hotwater_start_t", 45.0)]


def test_skugglage_skickar_inget(monkeypatch):
    import shadow
    monkeypatch.setattr(shadow, "active", lambda: True)
    monkeypatch.setattr(shadow, "record", lambda *a: None)
    with patch.object(homeassistant, "set_number") as sn:
        assert ThermIQHeatPumpDriver(prefix=P).set_room_temp(20)
    sn.assert_not_called()


def test_guiden_kanner_igen_thermiq_och_bygger_drivrutinen():
    ents = [{"e": e, "n": e.split(".")[1], "d": "dev_tiq", "dn": "ThermIQ", "m": "ThermIQ", "mo": None, "dc": None,
             "u": None, "st": v, "a": None} for e, v in STATES.items()]
    hp = discover_house(ents)["heat_pump"]
    assert hp["driver"] == "thermiq" and hp["prefix"] == P and hp["driver_known"]

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
        cfg = yaml.safe_load(mod._build_house_config_yaml({"heat_pump": hp}))
    finally:
        os.chdir(cwd)
    assert cfg["heat_pump"] == {"enabled": True, "driver": "thermiq", "prefix": P}
    drv = house_config.build_heat_pump_driver(cfg)
    assert isinstance(drv, ThermIQHeatPumpDriver) and drv._prefix == P
