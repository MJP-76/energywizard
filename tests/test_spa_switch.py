"""Spabad på ett relä (Shelly): EnergyWizard är termostaten (drivers/spa_switch.py)."""
from unittest.mock import patch

import yaml

from drivers import spa_switch
from drivers.spa_switch import SwitchSpaDriver
from house_config import build_spa_driver


class FakeHA:
    def __init__(self, temp=30.0, relay="off"):
        self.temp, self.relay, self.calls = temp, relay, []

    def num(self, e):
        return self.temp if e == "sensor.spa" else 2900.0

    def raw(self, e):
        return self.relay

    def switch(self, e, on):
        self.calls.append(on)
        self.relay = "on" if on else "off"
        return True


def _drv(ha, clock, entities=None):
    d = SwitchSpaDriver(entities or {"heater_switch": "switch.shelly_spa", "temperature": "sensor.spa", "power": "sensor.p"})
    patches = [patch("homeassistant._get_numeric_state", side_effect=ha.num), patch("homeassistant._get_raw_state", side_effect=ha.raw),
               patch("homeassistant.set_switch", side_effect=ha.switch), patch.object(spa_switch.time, "time", side_effect=lambda: clock[0])]
    for p in patches:
        p.start()
    return d, patches


def test_termostat_med_hysteres_och_tidsparr():
    ha, clock = FakeHA(temp=30.0), [1000.0]
    d, ps = _drv(ha, clock)
    try:
        d.set_target_temp(37.5)
        assert ha.calls == [True]                                    # kallt -> på
        assert d.read_state()["heater_state"] == "heating"
        ha.temp = 37.6; clock[0] += 60
        d.read_state(); assert ha.calls == [True]                    # målet nått, men för tätt att byta
        clock[0] += 300
        d.read_state(); assert ha.calls == [True, False]             # av efter spärren
        ha.temp = 37.2; clock[0] += 600
        d.read_state(); assert ha.calls == [True, False]             # inom hysteresen: förblir av
        ha.temp = 36.9
        d.read_state(); assert ha.calls == [True, False, True]       # under målet - 0,5: på
        d.set_economy(True); clock[0] += 600
        d.read_state(); assert ha.calls[-1] is False                 # eco: av
        assert d.read_state()["economy_mode"] == 1.0 and d.read_power_w() == 2900.0
    finally:
        for p in ps:
            p.stop()


def test_givare_som_tystnar_stanger_av_och_maxtemp():
    ha, clock = FakeHA(temp=30.0), [1000.0]
    d, ps = _drv(ha, clock)
    try:
        d.set_target_temp(50)                                         # motorn ber om för mycket
        assert d.read_state()["target_temp"] == 40.0
        ha.temp = None; clock[0] += 400
        d.read_state(); assert ha.calls[-1] is False                 # ingen temp: värm inte i blindo
    finally:
        for p in ps:
            p.stop()


def test_utan_givare_foljer_motorns_eco_val():
    ha, clock = FakeHA(), [1000.0]
    d, ps = _drv(ha, clock, {"heater_switch": "switch.shelly_spa"})
    try:
        d.set_target_temp(38)
        assert ha.calls == [True]
        clock[0] += 400
        d.set_economy(True)
        assert ha.calls == [True, False]
    finally:
        for p in ps:
            p.stop()


def test_byggs_fran_config():
    cfg = yaml.safe_load("spa:\n  enabled: true\n  driver: shelly\n  entities:\n    heater_switch: switch.x\n")
    assert isinstance(build_spa_driver(cfg), SwitchSpaDriver)
