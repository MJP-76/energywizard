"""'Vad görs nu och varför' per enhet (smartbox/decision_summary.py)."""
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartbox")))

from decision_summary import summarize

LOG = [
    "🔴 Grundläge: Dyr el (1.20 kr >= 0.90 kr). Värmepump styrs ner till sparläge.",
    "🚗 Prio 3 (EV Plan): Laddar enligt schema. Husets säkring tillåter 14A. Sätter Nissan: 0A, Tesla: 14A.",
    "🛁 Prio 4 (SPA): Bilen laddas. Pausar badets uppvärmning under laddfönstret så att mer ström finns kvar till bilen.",
    "🛑 Prio 5 (HUS): För varmt inne (22.6°C >= 22.5°C). Mjukt kompressor-stopp aktiverat (-3.5°C).",
    "💡 Prio 10 (PEAK): Peak Shaving är inaktiverat av användaren. Skyddar ej effekttak.",
]


def test_en_rad_per_enhet_och_brus_bort():
    s = summarize(LOG)
    keys = [i["key"] for i in s["items"]]
    assert keys == ["elbil", "varmepump", "spabad"]           # ingen 'effekt' - bara brus
    assert not any("inaktiverat" in i["text"] for i in s["items"])


def test_sista_raden_per_enhet_vinner():
    """Grundläget sa 'dyr el', men Prio 5 (som körs senare) bestämde - det är den som visas."""
    pump = next(i for i in summarize(LOG)["items"] if i["key"] == "varmepump")
    assert pump["text"].startswith("För varmt inne")


def test_text_utan_emoji_och_prio_prefix():
    spa = next(i for i in summarize(LOG)["items"] if i["key"] == "spabad")
    assert spa["text"] == "Bilen laddas. Pausar badets uppvärmning under laddfönstret så att mer ström finns kvar till bilen."
    assert spa["label"] == "Spabad" and spa["icon"] == "🛁"


def test_rubriken_ar_inte_peak_shaving_brus():
    s = summarize(LOG, {"ev": {"tesla": {"limit_a": 14}}})
    assert s["headline"].startswith("Elbil: Laddar enligt schema")
    s2 = summarize(LOG, {"ev": {"tesla": {"limit_a": 0}}})
    assert s2["headline"].startswith("Värmepump: För varmt inne")


def test_effekttaket_leder_nar_det_faktiskt_stryper():
    log = LOG[:-1] + ["🚨 Prio 10 (PEAK): Energibudget nådd! (4.10/4.00 kWh). STRYPER VÄRMEPUMP, Varmvatten och EV & Spa!"]
    s = summarize(log, {"ev": {"tesla": {"limit_a": 0}}})
    assert s["headline"].startswith("Effekttak: Energibudget nådd")


def test_pilar_blir_tankstreck():
    s = summarize(["🛁 Prio 4 (SPA): Minuspris -> Värmer bad till max för termisk lagring."])
    assert s["items"][0]["text"] == "Minuspris – Värmer bad till max för termisk lagring."


def test_tom_logg():
    assert summarize([]) == {"headline": "Utvärderar…", "items": []}


def test_riktig_gpm_utvardering_ger_inte_peak_shaving_som_rubrik():
    """Kör motorn på riktigt (peak shaving avstängd) - rubriken ska handla om huset, inte om brus."""
    from gpm import GlobalPriorityManager
    g = GlobalPriorityManager()
    actions = g.evaluate({"now": datetime(2026, 11, 2, 18, 0), "current_price": 2.0, "all_prices": [0.3] * 32 + [2.0] * 64,
                          "dynamic_limit": 0.3, "hysteresis": 0.2, "car_ids": [], "peak_shaving_enabled": False,
                          "indoor_temp": 21.0, "indoor_min": 19.0, "indoor_max": 22.5, "outdoor_avg_5d": 0.0})
    assert any("inaktiverat" in l for l in actions["log"])     # motorn loggar fortfarande bruset...
    s = summarize(actions["log"], actions)
    assert "inaktiverat" not in s["headline"]                   # ...men det visas inte som beslut
    assert any(i["key"] == "varmepump" for i in s["items"])
