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


# --- Hållfas (2026-11-06): kolla 10 min efter att värmen gått av, värm igen om temperaturen inte hölls ---
from car_climate_watch import HOLD_MAX_S, HOLD_RECHECK_S, MAX_REHEATS  # noqa: E402


def _started():
    w = ClimateWatch()
    w.step("21.0", "off", 0)
    assert w.step("21.0", "heat_cool", 60, 15.0) == "ok"
    return w


def test_varmer_igen_om_kupen_svalnat_10_min_efter_att_varmen_gick_av():
    w = _started()
    assert w.step("21.0", "off", 600, 21.5) is None                       # bilen stängde av vid temperaturen
    assert w.step("21.0", "off", 600 + HOLD_RECHECK_S - 60, 18.0) is None  # inte 10 min än
    assert w.step("21.0", "off", 600 + HOLD_RECHECK_S, 18.0) == "reheat"
    assert w.step("21.0", "heat_cool", 700 + HOLD_RECHECK_S, 18.5) == "ok"  # startade igen -> hållfas igen


def test_haller_temperaturen_ingen_atgard():
    w = _started()
    w.step("21.0", "off", 600, 21.5)
    assert w.step("21.0", "off", 600 + HOLD_RECHECK_S, 20.5) is None       # inom 1 °C
    assert w.step("21.0", "off", 600 + 2 * HOLD_RECHECK_S, 19.5) == "reheat"  # nästa koll 10 min senare


def test_hallfasen_slutar_efter_en_timme_och_nar_man_stanger_av():
    w = _started()
    assert w.step("21.0", "heat_cool", HOLD_MAX_S, 21.0) == "done"
    w = _started()
    assert w.step("off", None, 300) is None and w.hold_since is None


def test_okand_kupetemp_varmer_igen_hogst_max_reheats():
    w = _started()
    t, n = 100, 0
    for _ in range(20):
        r = w.step("21.0", "off", t, None)
        if r == "reheat":
            n += 1
            t += 60
            assert w.step("21.0", "heat_cool", t, None) == "ok"
        t += 60
        if t >= HOLD_MAX_S - 120:
            break
    assert 1 <= n <= MAX_REHEATS
