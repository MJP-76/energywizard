"""driver: ftw - Sourcefuls FTW-drivrutiner som batteri och solceller (drivers/ftw_device.py)."""
import json
import time
from unittest.mock import patch

import pytest

pytest.importorskip("lupa")
import house_config  # noqa: E402
from drivers import ftw_device  # noqa: E402


class _FakeLua:
    """Ersätter LuaDriver: rapporterar som en hybridväxelriktare (FTW:s tecken)."""
    def __init__(self, *a, **k):
        self.allow_write = k.get("allow_write", False)
        self.cmds = []
        g = type("G", (), {"driver_default_mode": staticmethod(lambda: True)})()
        self.L = type("L", (), {"globals": lambda s: g})()

    def poll(self):
        return {"battery": {"w": -1500.0, "soc": 62.0}, "pv": {"w": -3200.0}, "meter": {"w": 400.0}}, 5000

    def command(self, action, power_w=0, cmd=None):
        self.cmds.append((action, power_w))
        return True


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    monkeypatch.setattr("lua_host.LuaDriver", _FakeLua)
    ftw_device._instances.clear()
    monkeypatch.setattr(ftw_device.os.path, "exists", lambda p: True)
    yield


def _wait(dev):
    for _ in range(50):
        if dev.fresh():
            return
        time.sleep(0.02)


def test_battery_och_sol_las_och_delar_enhet():
    cfg = {"battery": {"enabled": True, "driver": "ftw", "ftw": {"driver": "sungrow", "host": "192.0.2.5"}, "capacity_kwh": 10},
           "solar": {"enabled": True, "driver": "ftw", "ftw": {"driver": "sungrow", "host": "192.0.2.5"}}}
    bat, sol = house_config.build_battery_driver(cfg), house_config.build_solar_driver(cfg)
    _wait(bat._dev)
    assert bat._dev is sol._dev                                   # samma växelriktare, en drivrutin
    assert bat.read_state()["soc_pct"] == 62.0 and bat.read_state()["power_w"] == -1500.0   # + = laddar
    assert sol.read_production()["pv_power_w"] == 3200.0          # FTW negativt = produktion
    assert not bat.supports_control() and bat.supported_intents() == set()


def test_styrning_bara_nar_den_uttryckligen_slagits_pa():
    cfg = {"battery": {"enabled": True, "driver": "ftw", "control": "styr", "ftw": {"driver": "sungrow", "host": "192.0.2.6"}}}
    bat = house_config.build_battery_driver(cfg)
    assert not bat.supports_control() and bat.apply_intent("charge", 2000) is False     # inte verifierad
    cfg["battery"]["control_unverified"] = True
    cfg["battery"]["ftw"]["host"] = "192.0.2.7"
    bat = house_config.build_battery_driver(cfg)
    assert bat.supports_control()
    assert bat.apply_intent("discharge", 1800) and bat._dev.drv.cmds[-1] == ("battery", -1800.0)
    assert bat.apply_intent("charge", 2500) and bat._dev.drv.cmds[-1] == ("battery", 2500.0)
    assert bat.refresh() and bat._dev.drv.cmds[-1] == ("battery", 2500.0)              # vakthunden: skickas om
    assert bat.apply_intent("auto")


def test_okand_drivrutin_ger_tydligt_fel(monkeypatch):
    monkeypatch.setattr(ftw_device.os.path, "exists", lambda p: False)
    with pytest.raises(ValueError):
        ftw_device.device({"driver": "finnsinte", "host": "192.0.2.8"})


def test_alla_medfoljande_drivrutiner_finns():
    names = ftw_device.available()
    assert len(names) >= 90 and {"sungrow", "huawei", "pixii", "solax", "victron", "sigenergy", "goodwe"} <= set(names)
