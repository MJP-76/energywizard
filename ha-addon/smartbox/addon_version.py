"""Tilläggets version (används av CI-jobbet tillagg i .github/workflows/docker.yml och av testerna).

  addon_version.py changelog          -> versionen överst i CHANGELOG.md ("## 1.2.17 (2026-11-06)")
  addon_version.py config             -> versionen i config.yaml
  addon_version.py set <ver> <image>  -> skriver version och image i config.yaml; exit 0 om något ändrades, 1 annars

Versionen i config.yaml höjs bara av CI, efter att den färdiga bilden <image>:<ver> finns (annars skulle Home
Assistant erbjuda en uppdatering vars bild inte går att hämta). För en ny version: lägg en ny rubrik överst i
CHANGELOG.md - rör inte config.yaml.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANGELOG = HERE / "CHANGELOG.md"
CONFIG = HERE / "config.yaml"
_VER = r"(\d+\.\d+\.\d+)"


def changelog_version(text: str | None = None) -> str:
    text = CHANGELOG.read_text(encoding="utf-8") if text is None else text
    m = re.search(rf"^## {_VER}\b", text, re.M)
    if not m:
        raise SystemExit("ingen versionsrubrik (## x.y.z) i CHANGELOG.md")
    return m.group(1)


def config_version(text: str | None = None) -> str:
    text = CONFIG.read_text(encoding="utf-8") if text is None else text
    m = re.search(rf'^version: "{_VER}"', text, re.M)
    if not m:
        raise SystemExit('ingen rad version: "x.y.z" i config.yaml')
    return m.group(1)


def _key(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


def set_version(text: str, version: str, image: str) -> str:
    if _key(version) < _key(config_version(text)):
        raise SystemExit(f"{version} är äldre än config.yaml:s {config_version(text)}")
    text = re.sub(r'^version: ".*"$', f'version: "{version}"', text, count=1, flags=re.M)
    line = f'image: "{image}"'
    if re.search(r"^image:.*$", text, re.M):
        text = re.sub(r"^image:.*$", line, text, count=1, flags=re.M)
    else:
        text = re.sub(r'^(version: ".*")$', lambda m: m.group(1) + "\n" + line, text, count=1, flags=re.M)
    return text


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "changelog":
        print(changelog_version())
    elif cmd == "config":
        print(config_version())
    elif cmd == "set" and len(sys.argv) == 4:
        old = CONFIG.read_text(encoding="utf-8")
        new = set_version(old, sys.argv[2], sys.argv[3])
        if new == old:
            sys.exit(1)
        CONFIG.write_text(new, encoding="utf-8")
    else:
        raise SystemExit(__doc__)
