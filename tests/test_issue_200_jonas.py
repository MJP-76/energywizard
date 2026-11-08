"""#200 (Jonas): "klar senast" ur en HA-entitet, och NIBE via kurvförskjutningen när rumsbörvärde saknas."""
import zoneinfo
from datetime import datetime
from unittest.mock import patch

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")
NOW = datetime(2026, 11, 8, 10, 0, tzinfo=SWE)


def test_klar_senast_lases_i_flera_former():
    import homeassistant as h
    for raw, want in (("2026-11-08 15:30:00", datetime(2026, 11, 8, 15, 30, tzinfo=SWE)),
                      ("15:30:00", datetime(2026, 11, 8, 15, 30, tzinfo=SWE)),
                      ("07:00", datetime(2026, 11, 9, 7, 0, tzinfo=SWE)),         # passerat idag -> imorgon
                      ("2026-11-08T14:30:00+00:00", datetime(2026, 11, 8, 15, 30, tzinfo=SWE)),
                      ("2026-11-07 15:30:00", None), ("unavailable", None)):
        with patch.object(h, "_get_raw_state", return_value=raw):
            assert h.read_ready_by("input_datetime.bil_klar", NOW) == want, raw
    assert h.read_ready_by(None, NOW) is None


def test_klar_senast_gar_fore_veckoschemat():
    import decisions
    sched = {"bil": {6: {"enabled": True, "target_time": "07:00", "target_soc": 80}}}     # söndag 07:00 (redan passerat)
    ready = datetime(2026, 11, 8, 15, 30, tzinfo=SWE)
    t, soc, kwh, _ = decisions.get_car_plan_details(NOW, "bil", sched, 40, 60, ready_by=ready, ready_soc=90)
    assert t == ready and soc == 90 and round(kwh, 1) == round(0.5 * 60 * 1.12, 1)
    t2, *_ = decisions.get_car_plan_details(NOW, "bil", sched, 40, 60)                     # utan: schemat/morgongolvet
    assert t2 != ready


def test_nibe_kurvforskjutning_nar_rumsborvarde_saknas():
    from drivers.heatpump_ha_entities import HaEntitiesHeatPumpDriver
    d = HaEntitiesHeatPumpDriver({"curve_offset": "number.f730_heating_offset_climate_system_1"}, cfg={})
    with patch("homeassistant.set_number", return_value=True) as sn, patch("shadow.active", return_value=False):
        assert d.set_room_temp(21.5) and sn.call_args.args == ("number.f730_heating_offset_climate_system_1", 2)
        assert d.set_room_temp(20.0) and sn.call_args.args[1] == -1
        assert d.set_room_temp(30.0) and sn.call_args.args[1] == 5                              # inom -5..+5


def test_guiden_kopplar_nibe_47011():
    from discovery import _nibe_bt_entities
    base = dict(dc="temperature", u="°C", d="dev", m="NIBE")
    ents = [{"e": "sensor.f730_bt1", "n": "Outdoor temperature (BT1)", **base},
            {"e": "sensor.f730_bt2", "n": "Supply line (BT2)", **base},
            {"e": "number.f730_heating_offset_climate_system_1_47011", "n": "Heating offset climate system 1", "dc": None, "u": None, "d": "dev", "m": "NIBE"}]
    assert _nibe_bt_entities(ents)["curve_offset"] == "number.f730_heating_offset_climate_system_1_47011"
