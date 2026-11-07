"""2026-11-07: guiden kopplade bara Easee-boxens status och skrev in utvecklarens boxnamn (physical: lite/carport) åt alla,
och fasströmmarna lästes aldrig (attributen heter state_inCurrentT3 osv. i nyare integration)."""
import importlib.util, os, sys
from pathlib import Path
from unittest.mock import patch

import yaml

from discovery import discover_house


def _easee(dev, name, lang="en"):
    words = {"en": ("Status", "Power", "Current", "Session energy", "Lifetime energy", "Online", "Charger enabled", "Touch button enabled"),
             "sv": ("Status", "Effekt", "Ström", "Energi laddningssession", "Livstidsförbrukning", "Online", "Laddboxen aktiverad", "Touch-knapp aktiverad")}[lang]
    slug = name.lower().replace(" ", "_")
    base = dict(a=None, d=dev, dn=name, m="Easee", mo="Home")
    ids = ["status", "power", "current", "session_energy", "lifetime_energy", "online", "charger_enabled", "touch_button_enabled"]
    if lang == "sv":
        ids = ["status", "effekt", "strom", "energi_laddningssession", "livstidsforbrukning", "online", "laddboxen_aktiverad", "touch_knapp_aktiverad"]
    dom = ["sensor", "sensor", "sensor", "sensor", "sensor", "binary_sensor", "switch", "switch"]
    dc = [None, "power", "current", "energy", "energy", "connectivity", None, None]
    unit = [None, "kW", "A", "kWh", "kWh", None, None, None]
    out = []
    for i in range(8):
        out.append({"e": f"{dom[i]}.{slug}_{ids[i]}", "n": f"{name} {words[i]}", "dc": dc[i], "u": unit[i], "st": "0",
                    "ci": "EH123456" if ids[i] in ("current", "strom") else None, **base})
    return out


def test_easee_kopplas_helt_pa_engelska_och_svenska():
    for lang in ("en", "sv"):
        c = discover_house(_easee("dev1", "Garage box", lang))["chargers"][0]
        assert c["charger_id"] == "EH123456"
        assert c["enable_switch"].endswith("charger_enabled" if lang == "en" else "laddboxen_aktiverad")
        m = c["easee_entities"]
        assert set(m) >= {"status", "power_kw", "current_a", "session_kwh", "lifetime_kwh", "online"}
        assert m["current_a"].endswith("_current" if lang == "en" else "_strom")


def test_guidens_yaml_har_serienummer_och_inga_hardkodade_boxnamn():
    root = Path(__file__).resolve().parent.parent
    cwd = os.getcwd()
    os.chdir(root / "webdashboard")
    try:
        mod = sys.modules.get("webdashboard_app")
        if mod is None:
            spec = importlib.util.spec_from_file_location("webdashboard_app", root / "webdashboard" / "app.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["webdashboard_app"] = mod
            spec.loader.exec_module(mod)
        c = discover_house(_easee("dev1", "Garage box", "sv"))["chargers"][0]
        text = mod._build_house_config_yaml({"cars": [{"id": "bil", "name": "Bil", "charger": c}]})
    finally:
        os.chdir(cwd)
    assert "physical" not in text and "lite" not in text and "carport" not in text
    ev = yaml.safe_load(text)["evs"][0]["charger"]
    assert ev["id"] == "EH123456" and ev["enable_switch"] == "switch.garage_box_laddboxen_aktiverad"
    assert ev["entities"]["power_kw"] == "sensor.garage_box_effekt"


def test_fasstrommar_las_med_nya_attributnamnen():
    import homeassistant as h
    attrs = {"state_inCurrentT3": 6.1, "state_inCurrentT4": 0.0, "state_inCurrentT5": 0.0}
    with patch.object(h, "_get_numeric_state", return_value=0.0), patch.object(h, "_get_raw_state", return_value="charging"), \
         patch.object(h, "_get_numeric_attribute", side_effect=lambda e, a: attrs.get(a)):
        r = h._read_easee_charger({"current_a": "sensor.x_strom", "status": "sensor.x_status"})
    assert (r["current_l1"], r["current_l2"], r["current_l3"]) == (6.1, 0.0, 0.0)
