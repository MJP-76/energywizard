"""Issue #98: tidstariff - dyrare nätavgift under höglasttid (t.ex. vardagar 06-22 nov-mars)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import nordpool

SWE = ZoneInfo("Europe/Stockholm")


def _settings(monkeypatch, **kw):
    base = {"price_country": "SE", "price_tou_extra": 0.5, "price_tou_hours": "6-22", "price_tou_months": "11-3"}
    base.update(kw)
    import ew_settings
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: base.get(k, d))
    monkeypatch.delenv("PRICE_SOURCE", raising=False)


def test_tillagg_bara_vardagar_dagtid_vinter(monkeypatch):
    _settings(monkeypatch)
    onsdag_morgon = datetime(2026, 11, 4, 7, 0, tzinfo=SWE)
    assert nordpool.tou_extra_at(onsdag_morgon) == 0.5
    assert nordpool.tou_extra_at(datetime(2026, 11, 4, 22, 0, tzinfo=SWE)) == 0.0     # 22 = slut, ej med
    assert nordpool.tou_extra_at(datetime(2026, 11, 4, 5, 0, tzinfo=SWE)) == 0.0
    assert nordpool.tou_extra_at(datetime(2026, 11, 7, 12, 0, tzinfo=SWE)) == 0.0     # lördag
    assert nordpool.tou_extra_at(datetime(2026, 3, 31, 12, 0, tzinfo=SWE)) == 0.5     # mars med
    assert nordpool.tou_extra_at(datetime(2026, 4, 1, 12, 0, tzinfo=SWE)) == 0.0      # april inte
    # UTC-tid räknas om till svensk tid: 05:30 UTC = 06:30 i november
    assert nordpool.tou_extra_at(datetime(2026, 11, 4, 5, 30, tzinfo=ZoneInfo("UTC"))) == 0.5
    assert nordpool.full_buy_cost(1.0, onsdag_morgon) - nordpool.full_buy_cost(1.0) == 0.5


def test_utan_tidstariff_som_forut(monkeypatch):
    _settings(monkeypatch, price_tou_extra=None)
    t = datetime(2026, 11, 4, 7, 0, tzinfo=SWE)
    assert nordpool.full_buy_cost(1.0, t) == nordpool.full_buy_cost(1.0)
    assert "CASE" not in nordpool.sql_buy_cost_expr("price", "timestamp")


def test_sql_har_samma_villkor(monkeypatch):
    _settings(monkeypatch)
    sql = nordpool.sql_buy_cost_expr("price", "timestamp")
    assert "CASE WHEN" in sql and ">= 6" in sql and "< 22" in sql and ">= 11 OR" in sql and "ISODOW" in sql
    assert "CASE" not in nordpool.sql_buy_cost_expr("price")                           # utan tidskolumn: som förut
