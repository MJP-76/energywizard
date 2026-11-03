"""Husvärme utan innegivare: prisstyrning med skydd (gpm.no_sensor_heat)."""
from datetime import datetime, timedelta, timezone

from gpm import no_sensor_heat, NO_SENSOR_MAX_LOWERED_S

T0 = datetime(2026, 1, 10, 17, 0, tzinfo=timezone.utc)


def test_dyr_el_sanker_men_hogst_tre_timmar_i_strack():
    m, t, since, rec, why = no_sensor_heat("EXPENSIVE", 2.0, 22.0, 20.0, None, None, T0)
    assert (m, t) == ("EXPENSIVE", 20.0) and since == T0 and "sänker värmen 2" in why
    later = T0 + timedelta(seconds=NO_SENSOR_MAX_LOWERED_S)
    m, t, since, rec, why = no_sensor_heat("EXPENSIVE", 2.0, 22.0, 20.0, T0, None, later)
    assert (m, t) == ("CHEAP", 22.0) and rec == later + timedelta(hours=1)
    # under återhämtningen: normal värme även om elen fortfarande är dyr
    m, t, *_ = no_sensor_heat("EXPENSIVE", 2.0, 22.0, 20.0, None, rec, later + timedelta(minutes=30))
    assert (m, t) == ("CHEAP", 22.0)
    # efter återhämtningen får den sänka igen
    m, t, *_ = no_sensor_heat("EXPENSIVE", 2.0, 22.0, 20.0, None, rec, rec + timedelta(minutes=1))
    assert m == "EXPENSIVE"


def test_kyla_begransar_sankningen():
    assert no_sensor_heat("EXPENSIVE", -8.0, 22.0, 20.0, None, None, T0)[1] == 21.0      # högst 1 °C
    m, t, _, _, why = no_sensor_heat("EXPENSIVE", -20.0, 22.0, 20.0, None, None, T0)
    assert (m, t) == ("CHEAP", 22.0) and "för kallt" in why


def test_billig_el_nollstaller():
    m, t, since, rec, why = no_sensor_heat("CHEAP", 2.0, 22.0, 20.0, T0, None, T0 + timedelta(hours=1))
    assert (m, t, since, why) == ("CHEAP", 22.0, None, None)
