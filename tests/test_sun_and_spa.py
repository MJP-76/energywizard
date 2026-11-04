"""2026-11-04: huset blev 23 °C en solig förmiddag och spabadet slog av och på. Solutsikten ska dämpa
värmelagringen, och spabadets solvärme ska inte stänga av sig själv när värmaren börjar dra."""
from datetime import datetime, timedelta

import weather
from gpm import GlobalPriorityManager


def test_soligt_ar_andel_av_klarvader():
    assert weather.sunny_verdict(4.0, 6.0)
    assert not weather.sunny_verdict(2.0, 6.0)
    assert not weather.sunny_verdict(1.0, 1.2)          # skymning: för lite sol att tala om


def test_spabadet_haller_solvarmen_trots_egen_forbrukning():
    g = GlobalPriorityManager()
    now = datetime(2026, 11, 4, 10, 0)
    assert not g._spa_solar_hold(-2000, {}, now, -1100)            # inget pågående -> vanlig tröskel gäller
    g.spa_solar_since = now
    assert g._spa_solar_hold(+1000, {"spa_measured_w": 3000}, now + timedelta(minutes=3), -1100)   # minsta gångtid
    assert g._spa_solar_hold(+900, {"spa_measured_w": 3000}, now + timedelta(minutes=12), -1100)   # -2100 utan badet
    assert not g._spa_solar_hold(+2500, {"spa_measured_w": 3000}, now + timedelta(minutes=12), -1100)  # solen borta
    assert g.spa_solar_since is None
