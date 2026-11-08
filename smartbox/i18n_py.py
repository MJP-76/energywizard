"""i18n_py.py - motorns texter på installationens språk (Energy Pilot-idé + Emil 2026-11-08: "Bör inte felloggar vara i
det språk som användaren har valt?").

Samma ordlista och samma regler som gränssnitten (smartbox/i18n/<språk>.json, i18n.js): svensk text -> översättning,
# står för ett tal. Används för motorns utskrifter i tilläggsloggen (det användare klistrar in i issues). Husets egen
logg i databasen (ew_journal) sparas på svenska och översätts när den visas, så felsökningen fungerar likadant överallt.

Språket: valt i EnergyWizard (ew_settings "language") går först, annars Home Assistants språk (/api/config), annars
svenska. Ett språk utan ordlista ger engelska om den finns, annars svenska.
"""
import builtins
import json
import os
import re
import time
import unicodedata

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n")
NUM = re.compile(r"\d+(?:[.,]\d+)?")
TRAIL = re.compile(r"[\s:.…!?,;)\]]+$")
SPLITS = [re.compile(r"(?<=[.!?]) (?=[A-ZÅÄÖ])"), re.compile(r" · "), re.compile(r" – "), re.compile(r" - ")]
LOOKS_SV = re.compile(r"[åäöÅÄÖ]|\b(och|inte|för|att|är|på|till|med|eller|när|kvar|idag|imorgon)\b", re.I)

_state = {"lang": None, "at": 0.0, "dict": {}, "dict_lang": None}

# Meningar med namn i (bilar, entiteter) - samma regler som RULES i i18n.js (engelska)
RULES_EN = [
    (re.compile(r"^GPS: (.+) närmar sig hemmet! \(Avstånd: (.+?) km(\)?)$"), lambda m: f"GPS: {m[1]} is approaching home! (Distance: {m[2]} km{m[3]}"),
    (re.compile(r"^Hittade befintligt framtida schema för (.+)$"), lambda m: f"Found an existing future schedule for {m[1]}"),
    (re.compile(r"^(\S+(?: \S+){0,2}) frånkopplad$"), lambda m: f"{m[1]} disconnected"),
    (re.compile(r"^Senast kända batterinivåer inlästa: (.+)$"), lambda m: f"Last known battery levels loaded: {m[1]}"),
    (re.compile(r"^Sätter (.+)$"), lambda m: f"Setting {m[1]}"),
    (re.compile(r"^Prio (\d+) \(BATTERISKYDD\): (.+) måste ladda (\d+) min i sträck för att skydda kontaktorerna$"),
     lambda m: f"Prio {m[1]} (BATTERY PROTECTION): {m[2]} must charge {m[3]} min in a row to protect the contactors"),
    (re.compile(r"^Tvingar fram (\d+)A$"), lambda m: f"Forcing {m[1]}A"),
    (re.compile(r"^\(Kört (.+) min\)$"), lambda m: f"(Run {m[1]} min)"),
    (re.compile(r"^Klimat: (\S+) satt till (\S+) \((.+?)°C(\)?)$"), lambda m: f"Climate: {m[1]} set to {m[2]} ({m[3]}°C{m[4]}"),
    (re.compile(r"^Notis → ([^:]+): (.+)$"), lambda m: f"Notification → {m[1]}: {m[2]}"),
    (re.compile(r"^(.+) har varit onåbar i över (\d+) minuter$"), lambda m: f"{m[1]} has been unreachable for over {m[2]} minutes"),
    (re.compile(r"^(\S+(?: \S+){0,2}) laddar$"), lambda m: f"{m[1]} charging"),
    (re.compile(r"^(\S+): värmen är igång i bilen - håller temperaturen en timme från knapptrycket$"),
     lambda m: f"{m[1]}: the heating is on in the car - holding the temperature for an hour from the button press"),
]
missing: dict = {}


def _lead_len(s: str) -> int:
    """Ledande blanksteg, symboler, skiljetecken och emoji (som \\p{S}\\p{P}\\p{Extended_Pictographic} i i18n.js)."""
    i = 0
    while i < len(s):
        c = s[i]
        cat = unicodedata.category(c)
        if c.isspace() or cat[0] in ("S", "P") or c in ("️", "‍") or ord(c) >= 0x1F000:
            i += 1
        else:
            break
    return i


def _ha_language():
    try:
        import homeassistant
        import requests
        r = requests.get(f"{homeassistant._BASE}/config", headers=homeassistant._HEADERS, timeout=5,
                         verify=homeassistant._VERIFY)
        return str((r.json() or {}).get("language") or "").split("-")[0].lower() or None
    except Exception:
        return None


def available() -> set:
    try:
        return {f[:-5] for f in os.listdir(DIR) if f.endswith(".json") and f != "languages.json"} | {"sv"}
    except OSError:
        return {"sv"}


def language(refresh_s: float = 30) -> str:
    """Installationens språk. Cachat refresh_s sekunder (utskrifterna); Home Assistants språk cachas en timme."""
    if _state["lang"] and time.time() - _state["at"] < refresh_s:
        return _state["lang"]
    if _state.get("busy"):                 # en utskrift medan språket slås upp: svenska tills vidare
        return _state["lang"] or "sv"
    _state["busy"] = True
    try:
        return _resolve()
    finally:
        _state["busy"] = False


def ha_language():
    """Home Assistants språk (kod som "en", "nl"), cachat en timme. None = okänt."""
    if time.time() - _state.get("ha_at", 0) > 3600:
        _state.update(ha=_ha_language(), ha_at=time.time())
    return _state.get("ha")


def _resolve() -> str:
    lang = None
    try:
        import ew_settings
        lang = ew_settings.get("language")
    except Exception:
        pass
    av = available()
    if lang:                               # valt i EnergyWizard: okänt språk -> svenska (som förut)
        lang = lang if lang in av else "sv"
    else:                                  # Home Assistants språk: utan ordlista -> engelska om den finns
        ha = ha_language()
        lang = (ha if ha in av else ("en" if "en" in av else "sv")) if ha else "sv"
    _state.update(lang=lang, at=time.time())
    return lang


def _dict(lang):
    if _state["dict_lang"] != lang:
        try:
            with open(os.path.join(DIR, f"{lang}.json"), encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        _state.update(dict={k: v for k, v in d.items() if not k.startswith("_") and v}, dict_lang=lang)
    return _state["dict"]


def _fill(text, nums):
    it = iter(nums)
    return re.sub("#", lambda m: next(it, "#").replace(",", "."), text)


def _lookup(core, d):
    if core in d:
        return d[core]
    nums = NUM.findall(core)
    key = NUM.sub("#", core)
    if key in d:
        return _fill(d[key], nums)
    return None


def tr(s: str, lang: str | None = None) -> str:
    lang = lang or language()
    if not s or lang == "sv":
        return s
    d = _dict(lang)
    n = _lead_len(s)
    lead, rest = s[:n], s[n:]
    m = TRAIL.search(rest)
    trail = m.group(0) if m else ""
    core = rest[:len(rest) - len(trail)]
    if not core:
        return s
    r = _lookup(rest.strip(), d)
    if r is not None:
        return lead + r + rest[len(rest.rstrip()):]
    r = _lookup(core, d)
    if r is not None:
        return lead + r + trail
    if lang == "en":
        for rx, fn in RULES_EN:
            m = rx.match(core)
            if m:
                return lead + fn(m) + trail
    for sep in SPLITS:
        parts = sep.split(core)
        if len(parts) > 1:
            j = sep.search(core).group(0) or " "
            out = [tr(p, lang) for p in parts]
            if out != parts:
                return lead + j.join(out) + trail
    if LOOKS_SV.search(core) and len(core) < 400 and len(missing) < 2000:
        k = NUM.sub("#", core)
        missing[k] = missing.get(k, 0) + 1
    return s


def install_print() -> None:
    """Motorns utskrifter på installationens språk. Installeras före loggens och telemetrins krokar, så att de ser
    originaltexten (svenska) medan tilläggsloggen får översättningen."""
    if getattr(builtins.print, "_ew_tr", False):
        return
    orig = builtins.print

    def translated(*args, **kwargs):
        try:
            if language() != "sv":
                args = tuple(tr(a) if isinstance(a, str) else a for a in args)
        except Exception:
            pass
        orig(*args, **kwargs)

    translated._ew_tr = True
    builtins.print = translated
