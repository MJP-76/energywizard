"""Batteriplanen lär sig (smartbox/battery_learning.py) - mot ett simulerat batteri med känd
verkningsgrad och kapacitet."""
import math
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartbox")))

from battery_learning import learn, apply, realized_saving, describe, segments

CFG = {"capacity_kwh": 10.0, "max_power_w": 5000.0, "efficiency": 0.9}


def _battery(cycles=4, eff=0.9, cap=11.0, kw=3.0):
    """Minutvisa mätningar: ladda 20->90 %, vila, ladda ur 90->20 %, vila - upprepat."""
    ec = ed = math.sqrt(eff)
    t, soc, out = 0.0, 20.0, []
    def run(p_kw, until):
        nonlocal t, soc
        while (p_kw > 0 and soc < until) or (p_kw < 0 and soc > until):
            out.append((t, round(soc, 2), p_kw * 1000))
            de = p_kw / 60.0 * (ec if p_kw > 0 else 1 / ed)
            soc += de / cap * 100.0
            t += 60
    for _ in range(cycles):
        run(kw, 90.0)
        for _ in range(30):
            out.append((t, round(soc, 2), 0.0)); t += 60
        run(-kw, 20.0)
        for _ in range(30):
            out.append((t, round(soc, 2), 0.0)); t += 60
    return out


def test_hittar_verkningsgrad_och_kapacitet():
    m = learn(_battery(eff=0.88, cap=11.0), [], CFG)
    assert abs(m["learned"]["efficiency"] - 0.88) < 0.02
    assert abs(m["learned"]["capacity_kwh"] - 11.0) < 0.3
    assert m["use"]["efficiency"] == m["learned"]["efficiency"]
    assert m["use"]["capacity_kwh"] == m["learned"]["capacity_kwh"]
    assert abs(m["use"]["charge_kw"] - 3.0) < 0.01 and abs(m["use"]["discharge_kw"] - 3.0) < 0.01


def test_for_lite_data_anvands_inte():
    m = learn(_battery(cycles=2), [], CFG)
    assert "efficiency" not in m["use"] and "capacity_kwh" not in m["use"]
    assert "behöver 1" in describe(m)


def test_orimliga_varden_anvands_inte():
    m = learn(_battery(eff=0.9, cap=30.0), [], CFG)          # 300 % av konfigurerat
    assert "capacity_kwh" not in m["use"] and "capacity_kwh" in m["learned"]


def test_solprognosens_fel_per_timme():
    pairs = [(9, 2000, 1000)] * 6 + [(13, 4000, 4400)] * 6 + [(16, 1500, 1500)] * 2   # 16: för få timmar
    m = learn([], pairs, CFG)
    assert m["use"]["solar_factor"] == {9: 0.5, 13: 1.1}


def test_apply_lagger_inlart_over_config():
    s = apply({**CFG, "control": "styr"}, {"use": {"efficiency": 0.86, "charge_kw": 2.5, "solar_factor": {9: 0.5}}})
    assert s["efficiency"] == 0.86 and s["capacity_kwh"] == 10.0 and s["charge_kw"] == 2.5 and s["solar_factor"] == {9: 0.5}
    assert apply(CFG, None)["solar_factor"] == {}


def test_uppmatt_besparing():
    # 1 h: huset drar 3 kW, batteriet laddar ur 3 kW -> nätet 0. Utan batteri hade 3 kWh köpts.
    rows = [(60.0, 0.0, -3000.0, 2.0)] * 60
    saved = realized_saving(rows, lambda s: s * 1.25 + 0.6, lambda s: s)
    assert abs(saved - 3.0 * (2.0 * 1.25 + 0.6)) < 0.01
    # laddning från nätet kostar: 1 h à 3 kW vid 0,2 kr
    cost = realized_saving([(60.0, 3000.0, 3000.0, 0.2)] * 60, lambda s: s * 1.25 + 0.6, lambda s: s)
    assert cost < 0


def test_pass_delas_vid_riktningsbyte_och_luckor():
    samples = [(i * 60.0, 20 + i, 3000.0) for i in range(10)] + [(3600.0 + i * 60, 30 - i, -3000.0) for i in range(10)]
    segs = segments(samples)
    assert [s[0] for s in segs] == ["in", "out"]
