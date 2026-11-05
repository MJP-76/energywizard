"""plan_clock.build: en rad per kvart 24 h framåt med pris, batteri, bilar, värme och sol."""
from datetime import datetime, timedelta
import zoneinfo

import plan_clock

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")


def test_kvartar_med_plan():
    now = datetime(2026, 11, 5, 17, 37, tzinfo=SWE)
    q0 = datetime(2026, 11, 5, 17, 30, tzinfo=SWE)
    prices = [(q0 + timedelta(minutes=15 * k), 1.0 + k / 100) for k in range(96)]
    d = plan_clock.build(now, prices, ev_rows=[("leaf", q0 + timedelta(hours=3), 4.6)],
                         bat_rows=[(q0 + timedelta(hours=1), "discharge", 40, 1.2, -1.7)],
                         heat_modes={q0.replace(minute=0): "EXPENSIVE"}, solar_w={(q0 + timedelta(hours=18)).replace(minute=0): 3000},
                         full_cost=lambda s, t: s + 0.5)
    sl = d["slots"]
    assert len(sl) == 96 and sl[0]["t"].startswith("2026-11-05T17:30")
    assert sl[0]["price"] == 1.5 and sl[0]["heat"] == "EXPENSIVE"
    assert sl[4]["bat"] == "discharge" and sl[4]["bat_kw"] == -1.7 and sl[4]["soc"] == 40
    assert sl[12]["ev"] == {"leaf": 4.6}
    assert sl[72]["sun_w"] == 3000


def test_timpriser_blir_fyra_kvartar_och_klockan_slutar_med_priserna():
    now = datetime(2026, 11, 5, 17, 5, tzinfo=SWE)
    h0 = datetime(2026, 11, 5, 17, 0, tzinfo=SWE)
    d = plan_clock.build(now, [(h0 + timedelta(hours=k), 2.0) for k in range(7)])
    assert len(d["slots"]) == 28 and all(s["spot"] == 2.0 for s in d["slots"])


def test_urladdning_som_saljer_far_egen_farg():
    """Anders på Discord: laddar ur för eget bruk (orange) skiljs från laddar ur och säljer (egen färg)."""
    import plan_brief
    now = datetime(2026, 11, 5, 17, 2, tzinfo=SWE)
    q0 = datetime(2026, 11, 5, 17, 0, tzinfo=SWE)
    rows = [(q0, "discharge", 60, 2.0, -2.0, -0.05), (q0 + timedelta(minutes=15), "discharge", 55, 2.1, -3.0, -1.4),
            (q0 + timedelta(minutes=30), "discharge", 50, 2.2, -3.0, -1.2)]
    items = plan_brief.battery_items(rows, now)
    assert [i["action"] for i in items] == ["discharge", "export"]
    assert items[1]["title"] == "🔋 Batteriet laddar ur och säljer" and items[1]["price_peak"] == 2.2
    d = plan_clock.build(now, [(q0 + timedelta(minutes=15 * k), 1.0) for k in range(8)], bat_rows=rows)
    assert [s["bat"] for s in d["slots"][:3]] == ["discharge", "export", "export"]
