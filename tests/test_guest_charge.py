"""#131 gästbil: billigaste kvartarna före klar-tiden, direkt utan klar-tid, alltid under säkringen."""
from datetime import datetime, timedelta
import json
import zoneinfo

import guest_charge as g

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")
NOW = datetime(2026, 11, 5, 22, 0, tzinfo=SWE)


def price_at(t):                       # billigt 02-05, annars dyrt
    return 0.5 if 2 <= t.hour < 5 else 2.0


def test_utan_klartid_laddar_direkt_under_sakringen():
    guest = {"kwh": 10, "until": None, "set_at": NOW.isoformat()}
    a, why = g.amps(NOW, guest, 0, max_a=16, phases=3, available_a=12, price_at=price_at)
    assert a == 10 and "laddar" in why                     # 12 A ledigt - 2 A marginal


def test_med_klartid_vantar_pa_billiga_kvartar():
    guest = {"kwh": 10, "until": (NOW + timedelta(hours=9)).isoformat(), "set_at": NOW.isoformat()}
    a, why = g.amps(NOW, guest, 0, 16, 3, 25, price_at)
    assert a == 0 and "billigare" in why
    a, _ = g.amps(NOW.replace(hour=2) + timedelta(days=1), guest, 0, 16, 3, 25, price_at)
    assert a == 16


def test_for_lite_tid_laddar_direkt_och_klar_nar_kwh_levererats():
    guest = {"kwh": 40, "until": (NOW + timedelta(hours=1)).isoformat(), "set_at": NOW.isoformat()}
    assert g.amps(NOW, guest, 0, 16, 3, 25, price_at)[0] == 16
    assert g.amps(NOW, guest, 40, 16, 3, 25, price_at) == (0, "Gästbilen har fått sina kWh")


def test_ingen_plats_pa_sakringen():
    guest = {"kwh": 10, "until": None, "set_at": NOW.isoformat()}
    assert g.amps(NOW, guest, 0, 16, 3, 7, price_at)[0] == 0


def test_parse_och_utgang():
    assert g.parse(json.dumps({"kwh": 15, "until": None, "set_at": NOW.isoformat()}))["kwh"] == 15
    assert g.parse("off") is None and g.parse("{bad") is None and g.parse(json.dumps({"kwh": 0})) is None
    assert g.expired({"set_at": (NOW - timedelta(hours=40)).isoformat()}, NOW)
