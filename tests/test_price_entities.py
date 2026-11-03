"""Prissensorer i Home Assistant från olika länders integrationer (nordpool.parse_price_attributes). Formaten är
integrationernas egna enligt deras dokumentation (se kommentaren i nordpool.py)."""
from datetime import datetime, timedelta

import pytest

import nordpool

T0 = "2026-11-03T00:00:00+01:00"
T1 = "2026-11-03T01:00:00+01:00"


def _p(attrs, unit=""):
    return [(s.isoformat(), e.isoformat(), round(v, 5)) for s, e, v in nordpool.parse_price_attributes(attrs, unit)]


def test_nordpool_hacs():
    a = {"raw_today": [{"start": T0, "end": T1, "value": 1.2}], "raw_tomorrow": [], "today": [1.2]}
    assert _p(a) == [(T0, T1, 1.2)]


def test_energi_data_service_hour_price():
    a = {"raw_today": [{"hour": T0, "price": 2.5}, {"hour": T1, "price": 2.0}]}
    assert _p(a) == [(T0, T1, 2.5), (T1, "2026-11-03T02:00:00+01:00", 2.0)]


def test_entsoe_prices_time_price():
    a = {"prices": [{"time": "2026-11-02T23:00:00+00:00", "price": 0.12}, {"time": "2026-11-03T00:00:00+00:00", "price": 0.1}]}
    rows = nordpool.parse_price_attributes(a, "EUR/kWh")
    assert rows[0][2] == 0.12 and rows[0][1] - rows[0][0] == timedelta(hours=1)


def test_epex_spot_mwh_till_kwh():
    a = {"data": [{"start_time": T0, "end_time": T1, "price_eur_per_mwh": 95.0}]}
    assert _p(a, "EUR/MWh") == [(T0, T1, 0.095)]


def test_octopus_rates_inc_vat():
    a = {"rates": [{"start": "2026-11-03T00:00:00+00:00", "end": "2026-11-03T00:30:00+00:00", "value_inc_vat": 0.2345, "is_capped": False}]}
    assert _p(a)[0][2] == 0.2345


def test_amber_forecasts_per_kwh():
    a = {"forecasts": [{"start_time": "2026-11-03T10:00:01+10:00", "end_time": "2026-11-03T10:30:00+10:00", "per_kwh": 0.31}]}
    assert _p(a)[0][2] == 0.31


def test_tibber_rest_startsat_total_och_ore():
    a = {"today": [{"startsAt": T0, "total": 145.0}]}
    assert _p(a, "öre/kWh")[0][2] == 1.45


def test_tidsstampel_till_pris_dict():
    a = {"Hourly prices": {T0: 3.1, T1: 2.9}}
    assert [r[2] for r in nordpool.parse_price_attributes(a)] == [3.1, 2.9]


def test_vanlig_sensor_kanns_inte_igen():
    assert nordpool.parse_price_attributes({"friendly_name": "Temp", "unit_of_measurement": "°C"}) == []
    assert nordpool.recognize_price_entity({"entity_id": "sensor.temp", "attributes": {"unit_of_measurement": "°C"}}) is None


def test_namn_pa_integrationen():
    r = nordpool.recognize_price_entity
    assert r({"entity_id": "sensor.nordpool_kwh_se3", "attributes": {"raw_today": [{"start": T0, "value": 1}]}}) == "Nord Pool"
    assert r({"entity_id": "sensor.energi_data_service", "attributes": {"raw_today": [{"hour": T0, "price": 1}]}}) == "Energi Data Service"
    assert r({"entity_id": "event.octopus_energy_electricity_x_current_day_rates", "attributes": {"rates": [{"start": T0, "value_inc_vat": 1}]}}) == "Octopus Energy"


def test_octopus_hamtar_aven_morgondagen(monkeypatch):
    import ew_settings
    monkeypatch.setattr(nordpool, "_setting", lambda k, e, d=None: "event.octopus_energy_electricity_1_2_current_day_rates" if k == "price_ha_entity" else d)
    assert nordpool._price_entities() == ["event.octopus_energy_electricity_1_2_current_day_rates",
                                          "event.octopus_energy_electricity_1_2_next_day_rates"]
