"""#180: höglasttiden var hårdkodad till Jönköping Energi (vardagar 07-20 nov-mars) och följde inte inställningarna."""
import zoneinfo
from datetime import datetime

import pytest

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")
FRE_2052 = datetime(2026, 11, 6, 20, 52, tzinfo=SWE)       # fredag kväll i november (Lars exempel)


@pytest.fixture
def ns(monkeypatch, tmp_path):
    import ew_settings, nordpool
    monkeypatch.setattr(ew_settings, "PATH", str(tmp_path / "s.json"))
    ew_settings._cache.update(mtime=None, data={})
    for k in ("POWER_HIGH_ENABLED", "PRICE_TOU_EXTRA", "PRICE_TOU_HOURS"):
        monkeypatch.delenv(k, raising=False)
    return ew_settings, nordpool


def test_standard_utan_installning_ar_som_forut(ns):
    s, n = ns
    assert n.high_load_window()["source"] == "standard"
    assert n.is_high_load_time(datetime(2026, 11, 6, 10, tzinfo=SWE)) and not n.is_high_load_time(FRE_2052)


def test_tidstariffens_tider_galler_utan_eget_val(ns):
    s, n = ns
    s.update(price_tou_extra=0.46, price_tou_hours="6-22", price_tou_months="11-3", price_tou_weekdays=True)
    assert n.high_load_window()["source"] == "tidstariff"
    assert n.is_high_load_time(FRE_2052)                                     # höglast till 22 enligt tariffen
    assert not n.is_high_load_time(datetime(2026, 11, 7, 12, tzinfo=SWE))    # lördag


def test_egna_tider_och_av(ns):
    s, n = ns
    s.update(power_high_enabled=True, power_high_hours="8-18", power_high_months="1-12", power_high_weekdays=False)
    assert n.is_high_load_time(datetime(2026, 7, 4, 9, tzinfo=SWE)) and not n.is_high_load_time(datetime(2026, 7, 4, 18, tzinfo=SWE))
    s.update(power_high_enabled=False)
    assert n.high_load_window()["source"] == "av" and not n.is_high_load_time(datetime(2026, 11, 6, 10, tzinfo=SWE))


def test_settings_och_webben_anvander_samma_regel(ns):
    import settings
    s, n = ns
    s.update(power_high_enabled=False)
    assert settings.is_high_load_time(datetime(2026, 11, 6, 10, tzinfo=SWE)) is False
