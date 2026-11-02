"""
decision_summary.py - "vad görs nu, och varför" per enhet, ur gpm.py:s egen logg.

gpm.py skriver en loggrad per beslut ("🛁 Prio 4 (SPA): Bilen laddas. Pausar badets
uppvärmning ..."). Tidigare visades bara den SISTA raden som beslut - och eftersom effekt-
vakten (Prio 10) loggar nästan sist varje varv blev det "Peak Shaving är inaktiverat av
användaren" överallt, vilket inte säger något om vad huset gör.

Här grupperas raderna per enhet efter taggen i raden. Inom en enhet vinner den SISTA raden:
gpm.py kör högre prioriteter efter lägre och skriver över deras beslut, så den sista raden är
den som faktiskt bestämde. Rena informationsrader (t.ex. "inaktiverat av användaren", larm-
notiser) tas bort.

Ingen ny logik: texten är gpm.py:s egen, bara utan emoji och "Prio X (TAGG):"-prefix.
Testas i tests/test_decision_summary.py, även mot riktiga gpm.py-utvärderingar.
"""

import re

# (nyckel, ikon, etikett, taggar). Ordningen = visningsordningen.
DEVICES = [
    ("effekt", "⚡", "Effekttak", ("PEAK",)),
    ("elbil", "🚗", "Elbil", ("EV", "EV PLAN", "SOLAR EV", "BATTERISKYDD", "FASVÄXLING", "MANUELL EV",
                             "MANUELL PAUS", "AI EV-VANOR", "GPM FAILSAFE")),
    ("varmepump", "🌡️", "Värmepump", ("HUS", "GRUNDLÄGE", "KOMPRESSOR", "WATCHDOG", "FAILSAFE", "BORTA", "FUKT")),
    ("varmvatten", "💧", "Varmvatten", ("VV-FAILSAFE", "TERMISKT BATTERI", "LEGIONELLA", "AI DUSCH")),
    ("spabad", "🛁", "Spabad", ("SPA", "TVÅNGSVÄRME", "MANUELL ECO")),
    ("sol", "☀️", "Solceller", ("SOL-PI", "EKONOMISKT OPTIMUM")),
]
_TAG_TO_KEY = {tag: key for key, _, _, tags in DEVICES for tag in tags}

# Rader som bara är information, inte ett beslut om vad som görs.
_NOISE = ("inaktiverat av användaren", "Skickade notis")

_PREFIX = re.compile(r"^\W*\s*(?:Prio\s+[\d.]+\s*)?\(([^)]+)\)\s*:\s*|^\W*\s*([A-ZÅÄÖ][A-ZÅÄÖ -]+?|Grundläge|Fukt|GPM Failsafe)\s*:\s*")


def _parse(line):
    """'🛁 Prio 4 (SPA): Text' -> ('SPA', 'Text'). Okänd form -> (None, rad)."""
    m = _PREFIX.match(line or "")
    if not m:
        return None, (line or "").strip()
    tag = (m.group(1) or m.group(2) or "").strip().upper()
    text = line[m.end():].strip()
    return tag, text


def _tidy(text):
    text = text.replace(" -> ", " – ").replace("->", "–")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1].upper() + text[1:] if text else text


def summarize(log_lines, actions=None):
    """{'headline': str, 'items': [{'key', 'icon', 'label', 'text'}]} ur gpm.py:s logg."""
    latest = {}
    for line in log_lines or []:
        if any(n in line for n in _NOISE):
            continue
        tag, text = _parse(line)
        key = _TAG_TO_KEY.get(tag)
        if key is None and tag and tag.startswith("EV"):
            key = "elbil"
        if key and text:
            latest[key] = _tidy(text)

    actions = actions or {}
    items = []
    for key, icon, label, _ in DEVICES:
        if key in latest:
            items.append({"key": key, "icon": icon, "label": label, "text": latest[key]})

    def first(*keys):
        return next((i for k in keys for i in items if i["key"] == k), None)

    peak = first("effekt")
    ev_charging = any((v or {}).get("limit_a", 0) > 0 for v in (actions.get("ev") or {}).values())
    lead = (peak if peak and "nådd" in peak["text"] else None) \
        or (first("elbil") if ev_charging else None) \
        or first("varmepump", "elbil", "spabad", "varmvatten", "sol")
    headline = f"{lead['label']}: {lead['text']}" if lead else "Utvärderar…"
    return {"headline": headline, "items": items}
