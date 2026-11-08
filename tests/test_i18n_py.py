"""i18n_py.py: motorns texter på installationens språk, samma ordlista och regler som i18n.js."""
import builtins
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "smartbox"))
import i18n_py  # noqa: E402


def test_samma_som_webblasaren():
    assert i18n_py.tr("📱 Aviseringar till", "en") == "📱 Notifications to"
    assert i18n_py.tr("Höll vi planen?", "en") == "Did we keep to the plan?"
    assert i18n_py.tr("Standard för Sverige: 25 %", "en") == "Default for Sweden: 25 %"
    assert i18n_py.tr("Laddat och vad det kostade", "en") == "Charged and what it cost"


def test_svenska_och_okant_oforandrat():
    assert i18n_py.tr("Höll vi planen?", "sv") == "Höll vi planen?"
    assert i18n_py.tr("Detta finns inte i ordlistan alls här", "en") == "Detta finns inte i ordlistan alls här"
    assert "Detta finns inte i ordlistan alls här" in i18n_py.missing


def test_sprak_ordning(monkeypatch):
    import ew_settings
    i18n_py._state.update(lang=None, at=0, ha=None, ha_at=0)
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: None)
    monkeypatch.setattr(i18n_py, "_ha_language", lambda: "nl")         # HA på nederländska, ingen nl-ordlista
    assert i18n_py.language() == "en"
    i18n_py._state.update(lang=None, at=0, ha=None, ha_at=0)
    monkeypatch.setattr(i18n_py, "_ha_language", lambda: "sv")
    assert i18n_py.language() == "sv"
    i18n_py._state.update(lang=None, at=0, ha=None, ha_at=0)
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: "en" if k == "language" else None)
    assert i18n_py.language() == "en"
    i18n_py._state.update(lang=None, at=0, ha=None, ha_at=0)


def test_utskrifter_oversatts(monkeypatch, capsys):
    orig = builtins.print
    try:
        monkeypatch.setattr(i18n_py, "language", lambda refresh_s=3600: "en")
        i18n_py.install_print()
        print("📱 Aviseringar till", 5)
        assert capsys.readouterr().out.strip() == "📱 Notifications to 5"
    finally:
        builtins.print = orig


def test_motorns_rader_med_namn():
    t = i18n_py.tr
    assert t("📍 GPS: Volvo EX30 närmar sig hemmet! (Avstånd: 2.4 km). Förallokerar.", "en") == \
        "📍 GPS: Volvo EX30 is approaching home! (Distance: 2.4 km). Pre-allocating."
    assert t("  🚗 Prio 3 (EV Plan): Laddar enligt schema. Husets säkring tillåter 16A. Sätter Zeekr: 16A.", "en") == \
        "  🚗 Prio 3 (EV plan): Charging by the schedule. The house fuse allows 16A. Setting Zeekr: 16A."
    assert t("⚡ Easee: Dynamisk gräns satt till 0 A", "en") == "⚡ Easee: dynamic limit set to 0 A"
    assert t("🔧 Sätter pumpens måltemp till 20.0°C...", "en") == "🔧 Setting the pump's target to 20.0°C..."
