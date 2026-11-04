"""2026-11-04: givarna väljs av användaren - inget hårdkodat. Utan val: inga givare."""
import homeassistant as ha
import ew_settings


def _use(monkeypatch, tmp_path, sensors):
    monkeypatch.setattr(ew_settings, "PATH", str(tmp_path / "s.json"))
    ew_settings._cache.update(mtime=None, data={})
    if sensors is not None:
        ew_settings.update(sensors=sensors)


def test_utan_val_inga_givare(monkeypatch, tmp_path):
    _use(monkeypatch, tmp_path, None)
    monkeypatch.setattr(ha, "_get_numeric_state", lambda e: 21.0)
    assert ha.indoor_sensors() == [] and ha.read_temperatures() == {"ute": None} and ha.read_humidities() == {}


def test_valda_givare_esphome_reserv_och_fukt(monkeypatch, tmp_path):
    _use(monkeypatch, tmp_path, {"outdoor": "sensor.ute", "indoor": [
        {"key": "indoor_1", "entity": "sensor.a", "humidity": "sensor.a_hum", "label": "Vardagsrum"},
        {"entity": "sensor.b", "esphome_ip": "10.0.0.5", "offset": -0.6}]})
    vals = {"sensor.a": 21.5, "sensor.b": None, "sensor.ute": -2.0, "sensor.a_hum": 41.0}
    monkeypatch.setattr(ha, "_get_numeric_state", lambda e: vals.get(e))
    monkeypatch.setattr(ha, "read_esphome_temp", lambda ip: 22.4 if ip == "10.0.0.5" else None)
    assert ha.read_temperatures() == {"indoor_1": 21.5, "in_2": 22.4, "ute": -2.0}     # rått värde, korrigeringen i main.py
    assert ha.read_humidities() == {"indoor_1": 41.0}
    assert ha.indoor_sensor_labels() == {"indoor_1": "Vardagsrum", "in_2": "sensor.b"}
