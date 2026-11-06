"""#156: utan spabad i installationen ska motorn varken anropa spadrivrutinen eller logga spabeslut."""
import re
from pathlib import Path

MAIN = (Path(__file__).resolve().parent.parent / "smartbox" / "main.py").read_text(encoding="utf-8").splitlines()


def test_varje_anrop_till_spadrivrutinen_kraver_ett_spabad():
    calls = [i for i, ln in enumerate(MAIN) if re.search(r"spa_driver\.(set_\w+|read_activities)\(", ln)]
    assert len(calls) >= 6
    for i in calls:
        window = "\n".join(MAIN[max(0, i - 20):i + 1])
        assert "HAS_SPA" in window, f"main.py:{i + 1} anropar spadrivrutinen utan HAS_SPA: {MAIN[i].strip()}"


def test_spaloggrader_kraver_ett_spabad():
    for pat in ("SKICKAR NYA VÄRDEN TILL SPABADET", "TVÅNGSVÄRME AKTIV", "Säkerställer att spabadets smartplug"):
        i = next(i for i, ln in enumerate(MAIN) if pat in ln)
        assert "HAS_SPA" in "\n".join(MAIN[max(0, i - 4):i + 1]), pat


def test_gpm_filtret_ar_skiftlagesokansligt():
    src = (Path(__file__).resolve().parent.parent / "smartbox" / "gpm.py").read_text(encoding="utf-8")
    assert '"spabad" not in l.lower()' in src
