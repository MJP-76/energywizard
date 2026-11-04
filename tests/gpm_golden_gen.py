"""Facit för gpm:s beslut (2026-11-04): körs mot koden FÖRE generaliseringen till N bilar och sparar
alla beslut och loggrader. tests/test_gpm_golden.py kräver att den nya koden ger exakt samma sak med
Emils två bilar (nissan 1-fas, tesla fasväxling). Kör: python tests/gpm_golden_gen.py > tests/fixtures/gpm_golden.json"""
import json, os, random, sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "smartbox"))
sys.path.insert(0, os.path.dirname(__file__))


def scenarios(seed=42, n=260, steps=10):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        t = datetime(2026, rnd.choice([1, 4, 7, 11]), rnd.randint(1, 27), rnd.randint(0, 23), rnd.choice([0, 15, 30, 45]),
                     tzinfo=timezone.utc)
        base_price = rnd.choice([-0.2, 0.05, 0.3, 0.8, 1.5, 3.0])
        prices = [round(max(-0.5, base_price + rnd.uniform(-0.6, 0.9)), 3) for _ in range(24)]
        seq = []
        nsoc, tsoc = rnd.choice([None, 20, 55, 80, 97, 100]), rnd.choice([None, 15, 50, 79, 96, 100])
        ncon, tcon = rnd.random() < 0.6, rnd.random() < 0.6
        for k in range(steps):
            t = t + timedelta(minutes=rnd.choice([1, 1, 5, 6]))
            pv = max(0.0, rnd.choice([0, 0, 1500, 4000, 7500]) + rnd.uniform(-800, 800))
            house = rnd.uniform(400, 3500)
            avg_net = house - pv + rnd.uniform(-300, 300)
            st = {
                "now": t, "current_price": round(base_price + rnd.uniform(-0.2, 0.2), 3), "all_prices": prices,
                "dynamic_limit": rnd.choice([0.6, 1.0, 1.4]), "hysteresis": 0.05,
                "avg_net_w": avg_net, "pv_power_w": pv, "house_load_a": rnd.uniform(3, 20), "max_fuse_a": 25,
                "ev_fuse_cap_a": rnd.choice([None, 10, 16]), "ev_actual_a": rnd.choice([0, 6, 10, 16]),
                "current_target_limit": rnd.choice([5.0, 8.0, 10.0]), "peak_shaving_enabled": rnd.random() < 0.7,
                "consumed_kwh_this_hour": rnd.uniform(0, 4), "predicted_base_load_kw": rnd.uniform(0.5, 3),
                "indoor_temp": rnd.uniform(19.0, 23.5), "indoor_min": 19.0, "indoor_max": 22.0, "indoor_humidity": rnd.choice([None, 40, 70]),
                "outdoor_temp": rnd.uniform(-15, 20), "outdoor_avg_5d": rnd.uniform(-10, 15), "water_temp": rnd.uniform(40, 62),
                "water_target_normal": 50.0, "temp_cheap": 22.0, "temp_expensive": 20.0, "heat_stop_outdoor": 17.0,
                "spa_temp": rnd.uniform(30, 39), "spa_low_temp": 15.0, "spa_normal_temp": 37.0, "spa_max_temp": 39.0,
                "solar_is_shaky": rnd.random() < 0.3, "current_solar_limit_pct": 100, "solar_auto_export": rnd.random() < 0.3,
                "days_since_legionella": rnd.randint(0, 14), "legionella_max_days": 7, "last_heartbeat": t,
                "car_ids": ["nissan", "tesla"],
                # Emils bilar som installationen beskriver dem (gamla koden ignorerar nyckeln)
                "car_specs": {"nissan": {"name": "Nissan", "max_a": 20, "phases": "1"},
                              "tesla": {"name": "Tesla", "max_a": 16, "phases": "auto"}},
                "nissan_soc": nsoc, "tesla_soc": tsoc, "nissan_connected": ncon, "tesla_connected": tcon,
                "nissan_charge_completed": nsoc == 100, "tesla_charge_completed": tsoc == 100,
                "nissan_prio": 2, "tesla_prio": 1, "nissan_phases": rnd.choice([None, "SinglePhase", "ThreePhase"]), "tesla_phases": rnd.choice([None, "SinglePhase", "ThreePhase"]),
                "nissan_force_amps": rnd.choice([0, 0, 0, 10]), "tesla_force_amps": rnd.choice([0, 0, 0, 16]),
                "sun_soon": {"sunny": rnd.random() < 0.4}, "sun_day": {"sunny": rnd.random() < 0.4},
            }
            r = rnd.random()
            if r < 0.5:                       # en laddplan (pandas) som ibland täcker nuvarande kvart
                import pandas as pd
                slot = t.replace(minute=(t.minute // 15) * 15, second=0, microsecond=0, tzinfo=None)
                if r < 0.15:
                    slot = slot + timedelta(hours=2)
                st["ev_plan"] = pd.DataFrame([{"t_slot": slot, "nissan_kw": rnd.choice([0.0, 1.5, 3.7]),
                                               "tesla_kw": rnd.choice([0.0, 3.0, 7.4, 11.0]),
                                               "nissan_panic": rnd.random() < 0.2, "tesla_panic": rnd.random() < 0.2}])
            elif r < 0.6:
                import pandas as pd
                st["ev_plan"] = pd.DataFrame()
            seq.append(st)
        out.append(seq)
    return out


def _clean(v):
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def run():
    import gpm
    res = []
    with patch.object(gpm.GlobalPriorityManager, "_restore_compressor_lock", lambda self: None), \
            patch("gpm.notifier") as _n, patch("gpm.logger") as _l, \
            patch("gpm.learning.get_optimal_pi_params", return_value=(0.5, 0.05)):
        for seq in scenarios():
            eng = gpm.GlobalPriorityManager()
            out = []
            for st in seq:
                a = eng.evaluate(dict(st))
                out.append(_clean({k: v for k, v in a.items()}))
            res.append(out)
    return res


if __name__ == "__main__":
    json.dump(run(), sys.stdout, ensure_ascii=False)
