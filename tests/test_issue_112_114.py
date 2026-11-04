"""#114: Tibber Pulse med köp- och säljeffekt räknas på dem (fasströmmen saknar tecken). #112: text i operating_mode."""
import homeassistant as ha

P = "sensor.tibber_pulse_irsta_prastgard_9"
LARS = [f"{P}_voltage_phase{n}" for n in (1, 2, 3)] + [f"{P}_current_l{n}" for n in (1, 2, 3)] + \
       [f"{P}_power", f"{P}_power_production", f"{P}_max_power", f"{P}_accumulated_consumption_current_hour"]


def test_pulse_med_kop_och_salj_hittas():
    e = ha.detect_tibber_pulse(LARS)
    assert e["import_w"] == f"{P}_power" and e["export_w"] == f"{P}_power_production"


def test_pulse_utan_saljeffekt_raknar_som_forut():
    e = ha.detect_tibber_pulse([x for x in LARS if not x.endswith("_production")])
    assert "import_w" not in e and "voltage_l1" in e


def test_export_syns_med_kop_och_salj(monkeypatch):
    vals = {f"{P}_power": 0.0, f"{P}_power_production": 2400.0, f"{P}_current_l1": 3.5, f"{P}_current_l2": 3.4,
            f"{P}_current_l3": 3.6, f"{P}_voltage_phase1": 230.0, f"{P}_voltage_phase2": 230.0, f"{P}_voltage_phase3": 230.0}
    monkeypatch.setattr(ha, "_get_numeric_state", lambda e: vals.get(e))
    monkeypatch.setattr(ha, "POWER_METER", ha.detect_tibber_pulse(LARS))
    r = ha.read_power_meter()
    assert r["net_power_w"] == -2400.0 and r["l1_a"] == 3.5          # U x I hade gett +2400 (köper)


def test_operating_mode_text_loggas_inte_i_sifferkolumnen():
    src = open("smartbox/logger.py", encoding="utf-8").read()
    assert 'isinstance(pump_operating_mode, int)' in src
