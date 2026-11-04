"""Bilens värme från appen följs upp: skickas om om bilen inte startat, avisering efter 12 min (2026-11-04)."""
from car_climate_watch import ClimateWatch, GIVE_UP_S, MAX_TRIES, RESEND_AFTER_S


def test_startar_direkt_ingen_atgard_och_ok():
    w = ClimateWatch()
    assert w.step("21.0", "off", 0) is None
    assert w.step("21.0", "heat_cool", 60) == "ok"
    assert w.step("off", "heat_cool", 120) is None


def test_skickar_om_och_ger_upp():
    w = ClimateWatch()
    out = [w.step("21.0", "off", t) for t in range(0, GIVE_UP_S + 1, 30)]
    assert out.count("resend") == MAX_TRIES
    assert out[RESEND_AFTER_S // 30] == "resend"
    assert out[-1] == "give_up"
    assert w.step("21.0", "off", GIVE_UP_S + 30) is None          # nytt försök börjar om (anroparen nollställer överstyrningen)


def test_ingen_varme_begard():
    w = ClimateWatch()
    assert w.step(None, "off", 0) is None and w.step("off", None, 0) is None
