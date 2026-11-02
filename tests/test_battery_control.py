"""Husbatteriet som del av hela systemet (smartbox/battery_control.py, drivers/battery_generic.py)."""
from datetime import datetime, timedelta
from unittest.mock import patch

from battery_control import decide, should_apply
from drivers.battery_generic import GenericBatteryDriver
from house_config import battery_settings, build_battery_driver
from decision_summary import summarize

STYR = {"control": "styr", "reserve_soc": 20.0, "priority_soc": 50.0, "max_soc": 100.0, "max_power_w": 5000.0}
ALL = frozenset({"auto", "hold", "idle", "charge", "discharge"})
BASE = {"soc": 60.0, "price": 1.0, "avg_net_w": 800.0, "meter_fresh": True, "fuse_state": "ok", "peak_reached": False,
        "ev_charging_grid": False, "ev_solar_active": False, "prices_rest_of_day": [1.0] * 20}


def d(**kw):
    return decide({**BASE, **kw}, STYR, ALL)


def test_samarbete_skriver_aldrig_men_forklarar():
    r = decide(BASE, {**STYR, "control": "samarbete"}, ALL)
    assert r["intent"] is None and "samarbete" in r["rule"] and "60 %" in r["reason"]
    assert decide(BASE, {**STYR, "control": "av"}, ALL)["intent"] is None


def test_gammal_data_lamnar_till_vaxelriktaren():
    assert d(meter_fresh=False)["intent"] == "auto"
    assert d(soc=None)["intent"] == "auto"


def test_sakring_och_effekttak_laddar_ur_men_inte_under_reserv():
    assert d(fuse_state="overload")["intent"] == "discharge"
    assert d(peak_reached=True)["intent"] == "discharge"
    assert d(peak_reached=True, soc=15)["intent"] == "hold"        # reservnivån går före
    assert d(peak_reached=True, avg_net_w=-200)["intent"] == "auto"   # säljer redan - inget att täcka


def test_minuspris_laddar_fran_natet_upp_till_max():
    assert d(price=-0.2)["intent"] == "charge"
    assert d(price=-0.2, soc=100)["intent"] != "charge"


def test_elbil_fran_natet_tommer_inte_batteriet():
    r = d(ev_charging_grid=True)
    assert r["intent"] == "hold" and "töms inte i bilen" in r["reason"]


def test_solprioritet_mellan_batteri_och_bil():
    assert d(ev_solar_active=True, soc=70)["intent"] == "idle"       # över prioritetsnivån: bilen först
    assert d(ev_solar_active=True, soc=30)["intent"] == "auto"       # under: batteriet laddar först


def test_reservniva_och_billig_timme():
    assert d(soc=18)["intent"] == "hold"
    cheap = d(price=0.4, prices_rest_of_day=[0.4] * 8 + [2.0] * 12)
    assert cheap["intent"] == "hold" and cheap["rule"] == "cheap_hour"
    assert d()["intent"] == "auto" and d()["rule"] == "default"


def test_saknat_lage_faller_tillbaka_saakert():
    r = decide({**BASE, "ev_solar_active": True, "soc": 70}, STYR, frozenset({"auto", "hold"}))
    assert r["intent"] == "hold" and "saknar läget 'idle'" in r["reason"]
    assert decide({**BASE, "price": -1}, STYR, frozenset({"auto"}))["intent"] == "auto"


def test_lagesbyten_sparsamt_men_sakerhet_direkt():
    t = datetime(2026, 11, 2, 12, 0)
    auto = {"intent": "auto", "power_w": None, "rule": "default"}
    hold = {"intent": "hold", "power_w": None, "rule": "ev_grid"}
    peak = {"intent": "discharge", "power_w": 5000.0, "rule": "peak"}
    assert should_apply(auto, None, None, t)
    assert not should_apply(auto, auto, t - timedelta(hours=1), t)
    assert not should_apply(hold, auto, t - timedelta(minutes=2), t)
    assert should_apply(hold, auto, t - timedelta(minutes=5), t)
    assert should_apply(peak, auto, t - timedelta(seconds=10), t)
    assert not should_apply({"intent": None}, auto, None, t)


def test_drivrutinen_mappar_avsikter_till_batteriets_egna_lagen():
    drv = GenericBatteryDriver(entities={"mode_select": "select.bat", "discharge_power": "number.ur"},
                               modes={"auto": "Self-use", "discharge": "Force discharge", "okänd": "x"})
    assert drv.supported_intents() == {"auto", "discharge"}
    with patch("drivers.battery_generic.homeassistant") as ha:
        ha.set_select.return_value = True; ha.set_number.return_value = True
        assert drv.apply_intent("discharge", 3000.0) is True
        assert drv.apply_intent("hold") is False
    ha.set_number.assert_called_once_with("number.ur", 3000)
    ha.set_select.assert_called_once_with("select.bat", "Force discharge")


def test_utan_lagesmappning_bara_lasning():
    assert GenericBatteryDriver(entities={"mode_select": "select.bat"}).supported_intents() == set()


def test_config_standard_ar_samarbete():
    cfg = {"battery": {"enabled": True, "driver": "generic", "entities": {"soc": "sensor.s"}}}
    assert battery_settings(cfg)["control"] == "samarbete"
    assert battery_settings({"battery": {"enabled": False, "control": "styr"}})["control"] == "av"
    assert battery_settings({"battery": {"enabled": True, "control": "STYR"}})["control"] == "styr"
    drv = build_battery_driver({"battery": {"enabled": True, "driver": "generic", "entities": {"mode_select": "select.b"},
                                            "modes": {"auto": "A"}}})
    assert drv.supported_intents() == {"auto"}


def test_batteriet_syns_i_vad_gors_nu():
    s = summarize(["🔋 (BATTERI): Elbilen laddar från nätet - batteriet töms inte i bilen."])
    assert s["items"] == [{"key": "batteri", "icon": "🔋", "label": "Batteri", "text": "Elbilen laddar från nätet - batteriet töms inte i bilen."}]
