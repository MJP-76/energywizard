"""Husbatteriets dygnsplan (smartbox/battery_plan.py): billig laddning, dyr urladdning, gränser."""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartbox")))

from battery_plan import optimize, blocks, simulate


def _slots(prices, load=1.0, solar=None, ev=None):
    solar = solar or [0.0] * len(prices)
    ev = ev or [0.0] * len(prices)
    return [{"t": f"t{i}", "buy": p * 1.25 + 0.6, "sell": p, "load_kw": load, "solar_kw": solar[i], "ev_kw": ev[i]}
            for i, p in enumerate(prices)]


# 4 h billig natt, 4 h dyr kväll (16 + 16 kvartar)
CHEAP_THEN_DEAR = [0.20] * 16 + [2.50] * 16


def test_laddar_billigt_och_laddar_ur_dyrt_och_sparar_pengar():
    r = optimize(_slots(CHEAP_THEN_DEAR), soc0_kwh=2.0, capacity_kwh=10.0, reserve_kwh=2.0, max_kwh=10.0,
                 charge_kw=3.0, discharge_kw=3.0, eff=0.9)
    acts = [x["action"] for x in r["rows"]]
    assert "charge" in acts[:16]                         # laddar på natten
    assert all(a != "charge" for a in acts[16:])         # aldrig i de dyra timmarna
    assert max(x["soc_kwh"] for x in r["rows"][:16]) > 8.0
    assert r["saving_kr"] > 5                            # 8 kWh × ~2.8 kr skillnad, minus förluster
    assert r["cost"] < r["baseline_cost"]


def test_platt_pris_ger_ingen_meningslos_cykling():
    r = optimize(_slots([1.0] * 32), 5.0, 10.0, 2.0, 10.0, 3.0, 3.0, eff=0.9)
    assert "charge" not in [x["action"] for x in r["rows"]]       # förluster gör det olönsamt
    assert abs(r["saving_kr"]) < 0.5


def test_reservniva_och_max_respekteras():
    r = optimize(_slots(CHEAP_THEN_DEAR), 4.0, 10.0, 3.0, 9.0, 3.0, 3.0)
    socs = [x["soc_kwh"] for x in r["rows"]]
    assert min(socs) >= 3.0 - 0.11 and max(socs) <= 9.0 + 0.11


def test_tommer_inte_batteriet_i_elbilen():
    ev = [0.0] * 16 + [11.0] * 16                        # bilen laddar under de dyra timmarna
    r = optimize(_slots(CHEAP_THEN_DEAR, ev=ev), 9.0, 10.0, 2.0, 10.0, 3.0, 3.0)
    assert all(x["battery_kw"] >= -1e-9 for x in r["rows"][16:])


def test_bara_stodda_avsikter_anvands():
    r = optimize(_slots(CHEAP_THEN_DEAR), 2.0, 10.0, 2.0, 10.0, 3.0, 3.0, allowed={"auto", "hold"})
    assert set(x["action"] for x in r["rows"]) <= {"auto", "hold"}


def test_solen_laddar_batteriet_gratis_i_auto():
    solar = [0.0] * 8 + [4.0] * 8 + [0.0] * 16
    cost, rows = simulate(_slots([1.0] * 32, solar=solar), 2.0, ["auto"] * 32, 10.0, 2.0, 10.0, 3.0, 3.0, 0.9)
    assert rows[15]["soc_kwh"] > 6.0


def test_pass_for_planvyn():
    r = optimize(_slots(CHEAP_THEN_DEAR), 2.0, 10.0, 2.0, 10.0, 3.0, 3.0)
    b = blocks(r["rows"])
    assert b and b[0]["action"] == "charge" and b[0]["start"] == r["rows"][0]["t"] or b[0]["action"] in ("charge", "hold")
    assert all(x["action"] != "auto" for x in b)


def test_tomt_eller_utan_kapacitet():
    assert optimize([], 0, 10, 2, 10, 3, 3)["rows"] == []
    assert optimize(_slots([1.0]), 0, None, 2, 10, 3, 3)["rows"] == []


def test_planvyn_och_tidslinjen_visar_batteriet():
    from datetime import datetime, timedelta
    from plan_brief import battery_items, SWE
    from timeline import build
    now = datetime(2026, 11, 2, 14, 10, tzinfo=SWE)
    q = now.replace(minute=0)
    rows = [(q + timedelta(minutes=15 * i), "charge", 20 + 10 * i, 0.3) for i in range(4)] + \
           [(q + timedelta(hours=3, minutes=15 * i), "discharge", 60 - 10 * i, 2.5) for i in range(4)]
    items = battery_items(rows, now)
    assert [i["title"] for i in items] == ["🔋 Batteriet laddar", "🔋 Batteriet laddar ur"]
    assert items[0]["active"] and items[0]["when"] == "till 15:00" and "till 50 %" in items[0]["detail"]
    d = build(now, {q: {"price": 1.0, "battery_kw": 2.0}}, {q + timedelta(hours=k): 1.0 for k in range(1, 5)}, {}, {}, {},
              battery_plan={q + timedelta(hours=3): "discharge"})
    lane = next(l for l in d["lanes"] if l["key"] == "batteri")
    i_now = d["hours"].index(q.isoformat())
    assert lane["text"][i_now] == "Laddade 2.0 kW" and lane["text"][i_now + 3] == "Planerat: laddar ur"
    assert not any(l["key"] == "batteri" for l in build(now, {}, {}, {}, {}, {})["lanes"])
