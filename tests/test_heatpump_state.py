"""Matter-lagret i drivers/heatpump.py: read_state, kurvförskjutning ±n med tak, paus med tidsgräns, nollställning vid start.
Befintliga drivrutiner utan krokarna ska svara False och inte skicka något."""
import drivers.heatpump as hp
from drivers.heatpump import HeatPumpDriver, NullHeatPumpDriver
from drivers.heatpump_generic import GenericClimateHeatPumpDriver
from drivers.heatpump_thermia import ThermiaHusdataHeatPumpDriver


class FakePump(HeatPumpDriver):
    def __init__(self):
        self.writes = []
        self.fail = False

    def read_sensors(self):
        return {"indoor_temp": 21.0, "outdoor_temp": -3.0, "compressor_running": True, "compressor_power_kw": 1.234,
                "water_temp": 48.0, "forward_temp": 35.0, "return_temp": 30.0}

    def set_room_temp(self, t): return False
    def set_water_stop_temp(self, t): return False
    def set_water_start_temp(self, t): return False
    def set_heating_start_temp(self, t): return False
    def set_operating_mode(self, m): return False

    def _write_curve_offset(self, offset):
        self.writes.append(("curve", offset))
        return not self.fail

    def _write_paused(self, paused):
        self.writes.append(("paused", paused))
        return not self.fail


def test_read_state_harleds_ur_sensorerna():
    st = FakePump().read_state()
    assert st["indoor_temp"] == 21.0 and st["outdoor_temp"] == -3.0 and st["running"] is True
    assert st["power_w"] == 1234 and st["dhw_temp"] == 48.0 and st["forward_temp"] == 35.0
    assert st["curve_offset"] == 0.0 and st["paused_until"] is None and st["mode"] is None


def test_kurvan_summeras_och_begransas():
    p = FakePump()
    assert p.capabilities() == {"curve_offset", "pause"}
    assert p.adjust_curve(2) and p.adjust_curve(2) and p.adjust_curve(3)
    assert p.read_state()["curve_offset"] == hp.CURVE_OFFSET_MAX
    assert p.writes[-1] == ("curve", 5.0)
    assert p.adjust_curve(-7) and p.read_state()["curve_offset"] == -2.0


def test_misslyckad_skrivning_andrar_inte_lagret():
    p = FakePump()
    p.fail = True
    assert not p.adjust_curve(2)
    assert p.read_state()["curve_offset"] == 0.0


def test_nollstallning_vid_start():
    p = FakePump()
    p.adjust_curve(3)
    assert p.reset_curve_offset() and p.writes[-1] == ("curve", 0.0) and p.read_state()["curve_offset"] == 0.0


def test_paus_slapps_av_tick_och_har_tak():
    p = FakePump()
    assert p.pause(600, now=1000)                                   # 10 h begärt -> högst 4 h
    assert p.read_state()["paused_until"] == 1000 + hp.PAUSE_MAX_MIN * 60
    p.tick(now=1000 + 60)
    assert p.writes == [("paused", True)]
    p.tick(now=1000 + hp.PAUSE_MAX_MIN * 60)
    assert p.writes[-1] == ("paused", False) and p.read_state()["paused_until"] is None
    assert not p.pause(0)


def test_befintliga_drivrutiner_skickar_inget(monkeypatch):
    import pump
    sent = []
    for name in ("set_room_temp", "set_operating_mode", "set_water_stop_temp"):
        monkeypatch.setattr(pump, name, lambda *a, **k: sent.append(a) or True)
    monkeypatch.setattr(pump, "read_sensors", lambda: {"indoor_temp": 20.5, "operating_mode": 1})
    for d in (NullHeatPumpDriver(), ThermiaHusdataHeatPumpDriver(), GenericClimateHeatPumpDriver(None)):
        assert d.capabilities() == frozenset()
        assert not d.adjust_curve(2) and not d.reset_curve_offset() and not d.pause(30) and not d.resume()
        d.tick()
    assert sent == []
    assert ThermiaHusdataHeatPumpDriver().read_state()["indoor_temp"] == 20.5


def test_generic_climate_lage(monkeypatch):
    import homeassistant
    monkeypatch.setattr(homeassistant, "_get_numeric_attribute", lambda e, a: 21.5)
    for ha, mode in (("heat", "heat"), ("heat_cool", "auto"), ("off", "off"), ("fan_only", None)):
        monkeypatch.setattr(homeassistant, "_get_raw_state", lambda e, ha=ha: ha)
        assert GenericClimateHeatPumpDriver("climate.vp").read_state()["mode"] == mode
