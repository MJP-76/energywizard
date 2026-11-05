"""#141 effektledd: gränsen för timmen håller månadens snitt av de N högsta timmarna i samma trappsteg."""
import capacity_tariff as ct


def test_tre_hogsta_pa_olika_dygn():
    peaks = [(1, 6.0), (1, 7.5), (2, 4.0), (3, 8.0), (4, 3.0)]
    top = ct.top_hours(peaks, 3, True)
    assert top == [(3, 8.0), (1, 7.5), (2, 4.0)]                     # dygn 1 räknas en gång (7,5)


def test_granssnittet_stannar_i_steget():
    # topp: 8, 7.5, 4 -> snitt 6.5 kW, steg 5-10. Ny timme idag (dygn 9) får vara upp till 10*3 - (8+7.5) = 14.5 kW
    peaks = [(1, 7.5), (2, 4.0), (3, 8.0)]
    lim, info = ct.limit_kw(peaks, today=9, top_n=3)
    assert info["step"] == [5.0, 10.0] and abs(lim - 14.5) < 1e-9


def test_timme_under_lagsta_toppen_ar_alltid_fri():
    # snittet redan nära steget: utrymmet blir mindre än den lägsta toppen -> gränsen är den lägsta toppen (påverkar inte)
    peaks = [(1, 9.9), (2, 9.9), (3, 9.0)]
    lim, info = ct.limit_kw(peaks, today=9, top_n=3)
    assert abs(lim - 10.2) < 1e-9 and info["free_below_kw"] == 9.0
    peaks = [(1, 9.9), (2, 9.9), (3, 9.9)]
    lim, _ = ct.limit_kw(peaks, today=9, top_n=3)
    assert abs(lim - 10.2) < 1e-9                                      # 30 - 19.8


def test_samma_dygn_ersatter_dygnets_egen_topp():
    peaks = [(1, 8.0), (2, 7.0), (9, 6.0)]                             # idag (9) har redan 6 kW
    lim, info = ct.limit_kw(peaks, today=9, top_n=3)
    assert abs(lim - (10 * 3 - 15.0)) < 1e-9 and info["free_below_kw"] == 6.0


def test_tidigt_i_manaden_raknar_mot_malsteget():
    lim, info = ct.limit_kw([(1, 3.0)], today=2, top_n=3, target_kw=10)
    assert info["step"] == [5.0, 10.0] and lim == 27.0                 # 10*3 - (3+0)
    lim, info = ct.limit_kw([(1, 3.0)], today=2, top_n=3)              # utan mål: lägsta steget (2 kW)
    assert lim == 3.0
