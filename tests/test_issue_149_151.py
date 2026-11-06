"""#149: en utegivare vald bland innegivarna räknas inte in i innetemperaturen.
#151: rumsbörvärdet skickas i °C till drivrutinerna (main.py räknar i tiondelar)."""
import re
from pathlib import Path
from unittest.mock import patch

import homeassistant


def test_utegivare_bland_innegivarna_raknas_inte():
    cfg = {"indoor": [{"key": "in_1", "entity": "sensor.f750_cu_rumstemperatur_bt50_40033", "label": "F750 Cu Rumstemperatur (BT50) (40033)"},
                      {"key": "in_2", "entity": "sensor.f750_cu_utomhustemperatur_40004", "label": "F750 Cu Utomhustemperatur (40004)"},
                      {"key": "in_3", "entity": "sensor.uterum_temp", "label": "Uterum"},
                      {"key": "in_4", "entity": "sensor.vald_som_ute", "label": "Garage"}],
           "outdoor": "sensor.vald_som_ute"}
    with patch.object(homeassistant, "sensor_config", return_value=cfg):
        keys = [s["key"] for s in homeassistant.indoor_sensors()]
    assert keys == ["in_1", "in_3"]          # uterummet är inne; utomhusgivaren och den valda utegivaren räknas inte


def test_utegivare_kanns_igen():
    assert homeassistant.is_outdoor_sensor("sensor.temp_ute")
    assert homeassistant.is_outdoor_sensor("sensor.x", "Outdoor temperature")
    assert not homeassistant.is_outdoor_sensor("sensor.vardagsrum_temperature", "Vardagsrum")
    assert not homeassistant.is_outdoor_sensor("sensor.uterum_temperature", "Uterum")


def test_rumsborvardet_skickas_i_grader():
    src = (Path(__file__).resolve().parent.parent / "smartbox" / "main.py").read_text(encoding="utf-8")
    calls = re.findall(r"heat_pump_driver\.set_room_temp\(([^)]*)\)", src)
    assert calls == ["current_chosen_temp / 10.0"]
