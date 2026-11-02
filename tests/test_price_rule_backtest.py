"""Jämförelsen av värmepumpens prisregel (smartbox/price_rule_backtest.py). Använder motorns
riktiga calculate_day_strategy och full_buy_cost; huset är ett enkelt påhittat hus."""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartbox")))

import nordpool
from price_rule_backtest import base_modes, simulate, run_days, format_report, limit_offset


def _q(hourly):
    return [hourly[i // 4] for i in range(96)]


FLAT_NIGHT = _q([0.30] * 8 + [2.0] * 16)          # jämn billig natt
DIPPING_NIGHT = _q([0.05] * 4 + [0.30] * 4 + [2.0] * 16)


def test_nuvarande_regel_missar_jamn_billig_natt_foreslagen_tar_den():
    s = nordpool.calculate_day_strategy(FLAT_NIGHT, 8)
    lim, h = s["dynamic_limit"], s["hysteresis"]
    now = base_modes(FLAT_NIGHT, lambda i: lim, h, "nuvarande")
    new = base_modes(FLAT_NIGHT, lambda i: lim, h, "foreslagen")
    assert now.count("CHEAP") == 0
    assert new.count("CHEAP") == 32                  # exakt de 8 billiga timmarna


def test_bada_reglerna_tar_en_djup_dipp():
    s = nordpool.calculate_day_strategy(DIPPING_NIGHT, 8)
    lim, h = s["dynamic_limit"], s["hysteresis"]
    assert base_modes(DIPPING_NIGHT, lambda i: lim, h, "nuvarande").count("CHEAP") >= 16
    assert base_modes(DIPPING_NIGHT, lambda i: lim, h, "foreslagen").count("CHEAP") == 32


def test_hysteresen_finns_kvar_uppat():
    """Föreslagen regel: ett pris strax över gränsen (inom hysteresen) byter inte till dyrt."""
    prices = [0.30] * 4 + [0.35] * 4 + [2.0] * 4
    modes = base_modes(prices, lambda i: 0.30, 0.20, "foreslagen")
    assert modes == ["CHEAP"] * 8 + ["EXPENSIVE"] * 4


def test_simulering_termostat_och_kostnad():
    r, t = simulate([1.0] * 4, ["CHEAP"] * 4, lambda i, t: 1.0, lambda i: 0.0, 21.0, 22.0, 20.0, 19.0, 2.0, lambda p: p)
    assert r["pump_h"] == 1.0 and abs(t - 22.0) < 1e-9          # 4 kvartar à 0.25 °C
    assert r["kwh"] == 2.0 and r["kr"] == 2.0
    assert r["heat_in_cheap_pct"] == 100.0


def test_komfortgolvet_varmer_oavsett_pris():
    r, t = simulate([5.0] * 4, ["EXPENSIVE"] * 4, lambda i, t: 1.0, lambda i: 0.0, 18.0, 22.0, 20.0, 19.0, 2.0, lambda p: p)
    assert r["pump_h"] > 0 and r["degree_hours_below_min"] > 0


def test_gransen_hojs_vid_snabb_avsvalning():
    assert limit_offset(0.2) == 0.30 and limit_offset(0.1) == 0.10 and limit_offset(0.0) == 0.0


def _week(cool):
    days = [{"day": f"2026-01-0{k}", "prices": FLAT_NIGHT, "outdoor": [2.0] * 24, "solar": [0.0] * 24} for k in range(1, 8)]
    return run_days(days, nordpool.calculate_day_strategy, 8, 22.0, 20.0, 19.0, 2.2, nordpool.full_buy_cost,
                    lambda d, h, t: 1.2, lambda d, h: cool, 21.0)


def test_milt_vader_foreslagen_lagrar_billig_varme_utan_samre_komfort():
    """Avsvalning 0.04 °C/h: ingen avsvalningshöjning av gränsen -> nuvarande regel får 0 billiga kvartar."""
    res = _week(0.04)
    a, b = res["nuvarande"]["total"], res["foreslagen"]["total"]
    assert a["cheap_quarters"] == 0 and b["cheap_quarters"] == 7 * 32
    assert b["heat_in_cheap_pct"] > a["heat_in_cheap_pct"]
    assert b["kr"] <= a["kr"] + 1e-9
    assert b["min_temp"] >= a["min_temp"] - 1e-9
    txt = format_report(res, 7, {"temp_cheap": 22.0, "temp_expensive": 20.0, "indoor_min": 19.0, "cheap_hours": 8, "pump_kw": 2.2})
    assert "nuvarande" in txt and "föreslagen" in txt


def test_kallt_vader_hojd_grans_raddar_nuvarande_regel():
    """Avsvalning 0.3 °C/h: gpm.py höjer gränsen 0.30 kr -> den jämna natten blir billig även nu.
    Svagheten slår alltså främst i milt väder - därför behövs körningen mot riktig historik."""
    res = _week(0.3)
    assert res["nuvarande"]["total"]["cheap_quarters"] == res["foreslagen"]["total"]["cheap_quarters"] == 7 * 32
