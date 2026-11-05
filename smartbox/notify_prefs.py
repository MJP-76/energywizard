"""notify_prefs.py - vilka notiser som skickas. Varje notis hör till en kategori och varje kategori går att stänga av
(Inställningar -> Notiser på webben och i appen). Sparas som "notify_off": [kategori, ...] i /data/energywizard.json,
som motorn, appen och webben delar.

Kategorin anges när notisen skickas (notifier.send_emil(..., key="batteri")). Utan angiven kategori härleds den ur
rubriken, så att även äldre anrop går att stänga av - och det som inte känns igen hamnar under "Övrigt", som också
går att stänga av.
"""
import re

CATEGORIES = [
    ("elbil", "🚗 Elbil", "Laddning startar/klar, kabeln lossnade, laddar inte trots order, bilvärmen startade inte"),
    ("batteri", "🔋 Husbatteri", "Batteriet gör inte som det blir tillsagt"),
    ("sol", "☀️ Solceller", "Exportgränsen sätts/släpps, växelriktarfel, gränsen går inte att läsa"),
    ("varmepump", "♨️ Värmepump", "Larm, avstängd pump, sommarläge, kallt inne, innegivare tystnat"),
    ("spabad", "🛁 Spabad", "Spabadet redo, skyddssensorer, tappad kontakt, locket"),
    ("pris", "💰 Elpris", "Morgonens eltips, extremt högt/lågt pris, reservpriser"),
    ("effekt", "⚡ Effekt", "Effektvakten, hög nätimport, ovanlig baslast"),
    ("lampor", "💡 Lampor", "Valda lampor som slutat svara, välkommen hem"),
    ("system", "🛠️ System", "Home Assistant/sensorer borta och tillbaka, väderprognosen, disk"),
    ("ovrigt", "🔔 Övrigt", "Allt annat"),
]
KEYS = [k for k, _, _ in CATEGORIES]

_RULES = [
    ("batteri", r"husbatteri|batteriet (gör|följer|laddar trots)|not following"),
    ("elbil", r"bil|laddar inte|laddning|kabel|fulladdad|färdigladdad|gps|leaf|tesla|värmen startade inte"),
    ("sol", r"sol(cell|el|ar)|exportgräns|växelriktar|solaredge"),
    ("spabad", r"spa"),
    ("varmepump", r"värmepump|husdata|sommarläge|kallt|innetemp|innegivare|pump"),
    ("pris", r"elpris|eltips|pris"),
    ("effekt", r"effekt|baslast|nätimport|säkring|oförklarad"),
    ("lampor", r"lampa|lampor|välkommen hem"),
    ("system", r"home assistant|sensor|väderprognos|offline|online|disk|databas"),
]


def category_for(title: str) -> str:
    t = (title or "").lower()
    for key, pat in _RULES:
        if re.search(pat, t):
            return key
    return "ovrigt"


def disabled() -> set:
    try:
        import ew_settings
        v = ew_settings.get("notify_off") or []
        return {x for x in v if x in KEYS}
    except Exception:
        return set()


def enabled(key: str | None = None, title: str | None = None) -> bool:
    return (key if key in KEYS else category_for(title)) not in disabled()


def set_disabled(keys) -> list:
    import ew_settings
    keys = sorted({k for k in keys or [] if k in KEYS})
    ew_settings.update(notify_off=keys)
    return keys


def listing() -> list:
    off = disabled()
    return [{"key": k, "label": label, "desc": desc, "on": k not in off} for k, label, desc in CATEGORIES]
