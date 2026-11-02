"""Termisk säkringsmodell (smartbox/fuse_guard.py) - både när den ska strypa och när den INTE ska.
Säkring 25 A i alla tester, prov var 10:e sekund som i main.py:s snabbloop."""
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartbox")))

import fuse_guard
from fuse_guard import FuseThermalModel, fast_trip_limits

FUSE = 25


def _feed(model, phases, seconds, t0=0.0, step=10.0):
    t = t0
    end = t0 + seconds
    while t < end:
        model.update(phases, ts=t)
        t += step
    return t - step   # tidpunkt för senaste provet


def test_filtret_konvergerar_mot_konstant_strom():
    m = FuseThermalModel()
    t = _feed(m, [10, 10, 10], 600)
    assert all(abs(x - 10) < 0.01 for x in m.filtered_a())
    assert m.check(FUSE) == ("ok", 0.0)


def test_kort_topp_stryper_inte_laddande_bil():
    """Bil drar 16 A, huset 6 A (totalt 22 A). En 20 s topp på +8 A (30 A totalt, över 25 A men
    under 1,2 × 25 = 30 A ... precis på, så 29 A) ska bilen få HÅLLA - säkringen tål det."""
    m = FuseThermalModel()
    t = _feed(m, [22, 22, 22], 300)
    t = _feed(m, [29, 29, 29], 20, t0=t + 10)
    assert max(m.filtered_a()) < FUSE                       # värmen har inte hunnit över
    cap = m.ev_cap_a(FUSE, [16, 16, 16], ts=t)
    assert cap == 16                                        # håll, ingen ökning (avläsningen är redan över)
    assert not m.in_recovery(ts=t)                          # ingen strypning registrerad


def test_gamla_formeln_hade_strupit_vid_samma_topp():
    """Dokumenterar skillnaden: säkring - husets last på toppen (29 - 16 = 13 A hus) = 12 A."""
    gammal = FUSE - (29 - 16)
    assert gammal < 16


def test_ihallande_overlast_stryper_nar_varmen_gar_over():
    m = FuseThermalModel()
    t = _feed(m, [22, 22, 22], 300)
    t = _feed(m, [28, 28, 28], 300, t0=t + 10)              # 5 min över märkvärdet
    assert m.check(FUSE)[0] == "overload"
    cap = m.ev_cap_a(FUSE, [16, 16, 16], ts=t)
    assert cap <= 16 - (28 - FUSE) + 1                      # sänkt med överskottet
    assert m.in_recovery(ts=t)                              # 20 s-spärren startad


def test_omedelbar_strypning_over_1_2_ganger_sakringen():
    m = FuseThermalModel()
    t = _feed(m, [20, 20, 20], 300)
    m.update([31, 20, 20], ts=t + 10)                       # 31 A > 30 A på L1
    state, excess = m.check(FUSE)
    assert state == "trip" and excess == 6
    cap = m.ev_cap_a(FUSE, [16, 16, 16], ts=t + 10)
    assert cap == 10


def test_ingen_okning_inom_20_s_efter_strypning():
    m = FuseThermalModel()
    t = _feed(m, [10, 10, 10], 300)
    m.mark_cut(ts=t)
    assert m.ev_cap_a(FUSE, [8, 8, 8], ts=t + 5) == 8       # håller, ökar inte
    assert m.ev_cap_a(FUSE, [8, 8, 8], ts=t + 25) == 8 + (FUSE - 10)


def test_okning_raknar_pa_det_hogsta_av_avlasning_och_varme():
    """Strömmen har just sjunkit (avläsning 15 A) men säkringen är fortfarande varm (~24 A):
    ökningen räknas mot värmen, inte mot den låga avläsningen."""
    m = FuseThermalModel()
    t = _feed(m, [24, 24, 24], 600)
    m.update([15, 15, 15], ts=t + 10)
    filt = max(m.filtered_a())
    assert filt > 20
    cap = m.ev_cap_a(FUSE, [10, 10, 10], ts=t + 10)
    assert cap == int(10 + (FUSE - filt))


def test_start_av_stillastaende_bil_raknar_pa_avlasningen():
    m = FuseThermalModel()
    t = _feed(m, [7, 7, 7], 300)
    assert m.ev_cap_a(FUSE, [0, 0, 0], ts=t) == FUSE - 7


def test_start_spärras_medan_fasen_ar_for_varm():
    m = FuseThermalModel()
    t = _feed(m, [27, 27, 27], 600)
    assert m.ev_cap_a(FUSE, [0, 0, 0], ts=t) == 0


def test_exporterande_fas_stryps_aldrig():
    """Negativ ström = export (Tibber). -35 A på L1 är över 1,2 × säkringen i belopp, men mindre
    bil-last skulle bara öka exporten - ingen strypning."""
    m = FuseThermalModel()
    t = _feed(m, [-35, 5, 5], 300)
    assert m.check(FUSE) == ("ok", 0.0)
    assert m.ev_cap_a(FUSE, [6, 6, 6], ts=t) == 6 + (FUSE - 5)


def test_obalans_varsta_fasen_styr():
    m = FuseThermalModel()
    t = _feed(m, [5, 20, 5], 300)
    assert m.ev_cap_a(FUSE, [0, 0, 0], ts=t) == FUSE - 20


def test_sakerhetsmarginal_dras_av():
    m = FuseThermalModel()
    t = _feed(m, [5, 5, 5], 300)
    assert m.ev_cap_a(FUSE, [0, 0, 0], margin_a=2, ts=t) == FUSE - 2 - 5


def test_gammal_matdata_ger_none_sa_gpm_faller_tillbaka():
    m = FuseThermalModel()
    t = _feed(m, [5, 5, 5], 60)
    assert m.ev_cap_a(FUSE, [0, 0, 0], ts=t + 120) is None
    assert FuseThermalModel().ev_cap_a(FUSE, [0, 0, 0], ts=0) is None


def test_saknad_fas_ignoreras():
    m = FuseThermalModel()
    m.update([5, None, 5], ts=0)
    assert m.filtered_a() == []


def test_nodbroms_stryper_bara_vid_trip():
    m = FuseThermalModel()
    t = _feed(m, [26, 26, 26], 30)                          # över märkvärdet, under 1,2 ×
    assert fast_trip_limits(m, FUSE, {"tesla": 16}, ts=t) == {}
    m.update([33, 26, 26], ts=t + 10)                       # 33 A > 30 A
    out = fast_trip_limits(m, FUSE, {"tesla": 16, "nissan": 0, "leaf": 10}, ts=t + 10)
    assert out == {"tesla": 8, "leaf": 0}                   # 16-8 = 8, 10-8 = 2 < 6 -> 0; 0 A rörs inte
    assert m.in_recovery(ts=t + 15)


# ---------- integration mot gpm.py ----------

def test_gpm_anvander_modellens_tak_istallet_for_gamla_formeln():
    from gpm import _ev_fuse_room
    assert _ev_fuse_room({"max_fuse_a": 25}, 13) == 12                 # utan modell: gamla formeln
    assert _ev_fuse_room({"max_fuse_a": 25, "ev_fuse_cap_a": 16}, 13) == 16
    assert _ev_fuse_room({"max_fuse_a": 25, "ev_fuse_cap_a": None}, 13) == 12


def test_gpm_betalt_for_att_importera_respekterar_modellens_tak():
    from gpm import GlobalPriorityManager
    engine = GlobalPriorityManager()
    actions = engine.evaluate({
        "now": datetime(2026, 10, 30, 3, 0, 0),
        "current_price": -0.50, "all_prices": [-0.5] * 24,
        "tesla_connected": True, "tesla_soc": 50, "tesla_charge_completed": True,
        "car_ids": ["tesla"],
        "max_fuse_a": 25, "house_load_a": 2, "ev_fuse_cap_a": 7,
        "peak_shaving_enabled": False,
    })
    assert actions["tesla_limit_a"] <= 7
