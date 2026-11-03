"""Skuggläge (shadow.py): ingenting skickas till prylarna, allt loggas, läsning och egna sensorer fungerar."""
from unittest.mock import patch

import pytest

import ew_settings
import homeassistant
import shadow


@pytest.fixture(autouse=True)
def _ren(monkeypatch, tmp_path):
    monkeypatch.setattr(ew_settings, "PATH", str(tmp_path / "ew.json"))
    ew_settings._cache.update(mtime=None, data={})
    monkeypatch.delenv("SHADOW_MODE", raising=False)
    shadow._last.clear()
    monkeypatch.setattr(shadow, "record", lambda what, detail="": logged.append((what, detail)))
    logged.clear()


logged = []


def test_av_som_standard_skickar_som_vanligt():
    assert not shadow.active()
    with patch.object(homeassistant, "_requests_real") as real:
        homeassistant.requests.post("http://ha/api/services/climate/set_temperature", json={"entity_id": "climate.x"})
    real.post.assert_called_once()
    assert logged == []


def test_pa_stoppar_tjanster_men_inte_last_eller_egna_sensorer():
    ew_settings.update(shadow_mode=True)
    assert shadow.active()
    with patch.object(homeassistant, "_requests_real") as real:
        r = homeassistant.requests.post("http://ha/api/services/select/select_option",
                                        json={"entity_id": "select.batteri", "option": "Force Charge"})
        assert r.status_code == 200 and r.json() == []
        real.post.assert_not_called()
        homeassistant.requests.post("http://ha/api/states/sensor.smartbox_plan", json={"state": 1})
        homeassistant.requests.post("http://ha/api/template", json={"template": "{{ 1 }}"})
        assert real.post.call_count == 2
    assert logged == [("select/select_option", "entity_id=select.batteri, option=Force Charge")]


def test_miljovariabel_slar_pa(monkeypatch):
    monkeypatch.setenv("SHADOW_MODE", "true")
    assert shadow.active()


def test_thermia_och_heishamon_skriver_inte():
    ew_settings.update(shadow_mode=True)
    import pump
    with patch.object(pump, "_get_client") as gc:
        assert pump._write_holding(13, 215) is True
    gc.assert_not_called()
    from drivers.heatpump_heishamon import HeishaMonHeatPumpDriver
    class Http:
        def get(self, *a, **k):
            raise AssertionError("inget anrop i skuggläget")
    assert HeishaMonHeatPumpDriver("hm", session=Http())._command("SetHeatpump", 0)
    assert ("Thermia (Husdata) register", "13 = 215") in logged and ("HeishaMon", "SetHeatpump=0") in logged
