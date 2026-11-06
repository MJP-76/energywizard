"""#171: Tibber Pulse med nyare namn (hemmets namn i stället för tibber_pulse_) - köp/sälj ska hittas, annars blir
försäljning köp (U x I saknar tecken). Laddnivå "inf" är inget värde. Nätets tecken kan vändas i webben."""
from unittest.mock import patch

import homeassistant as ha

P = "sensor.hemmet"
IDS = [f"{P}_voltage_phase{n}" for n in (1, 2, 3)] + [f"{P}_current_phase{n}" for n in (1, 2, 3)] + [f"{P}_power", f"{P}_power_production"]


def test_pulse_med_hemmets_namn_far_kop_och_salj():
    e = ha.detect_tibber_pulse(IDS)
    assert e["import_w"] == f"{P}_power" and e["export_w"] == f"{P}_power_production"


def test_inf_ar_inget_matvarde(monkeypatch):
    monkeypatch.setattr(ha, "_states_cache", {"sensor.soc": {"state": "inf"}, "sensor.x": {"state": "nan"}, "sensor.ok": {"state": "44"}})
    monkeypatch.setattr(ha, "_ha_fail", {"n": 0, "at": 0})
    assert ha._get_numeric_state("sensor.soc") is None and ha._get_numeric_state("sensor.x") is None
    assert ha._get_numeric_state("sensor.ok") == 44.0


def test_natets_tecken_kan_vandas_i_webben(monkeypatch):
    monkeypatch.setattr(ha, "POWER_METER", {"power_w": "sensor.net"})
    monkeypatch.setattr(ha, "_states_cache", {"sensor.net": {"state": "6200", "attributes": {"unit_of_measurement": "W"}}})
    monkeypatch.setattr(ha, "_setting", lambda k: k == "grid_power_invert")
    assert ha.read_power_meter()["net_power_w"] == -6200.0
    monkeypatch.setattr(ha, "POWER_METER", {"power_w": "sensor.net", "power_w_invert": False})   # låst i YAML
    assert ha.read_power_meter()["net_power_w"] == 6200.0


def test_live_flow_visar_inte_inf():
    import live_flow
    d = live_flow.nodes({"battery_power_w": 0, "battery_soc": float("inf"), "net_power": 100, "pv_power_w": 0})
    bat = next(n for n in d["nodes"] if n["key"] == "batteri")
    assert "inf" not in bat["detail"]
