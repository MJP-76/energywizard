"""Sponsring: länken som finns i alla gränssnitt, och en vänlig påminnelse en gång i månaden.

Påminnelsen är på som standard och kan stängas av i inställningarna. Den visas först när
installationen har använts en vecka, och högst en gång per kalendermånad: som en ruta i webben
och appen (tills den stängs) och som en notis i Home Assistant.
"""
from datetime import datetime, timedelta

import ew_settings

URL = "https://github.com/sponsors/murre87"
GRACE_DAYS = 7

TITLE = {"sv": "Gillar du EnergyWizard? ❤️", "en": "Do you like EnergyWizard? ❤️"}
TEXT = {
    "sv": ("Hej! Jag hoppas att EnergyWizard gör nytta hemma hos dig. Jag bygger det på min fritid, "
           "och mycket av koden skrivs tillsammans med Claude, en AI som kostar pengar varje månad. "
           "Om du tycker att projektet är värt det blir jag jätteglad för ett litet bidrag, stort som smått. "
           "Det håller EnergyWizard gratis och öppet för alla. Tack för att du är med! /Emil"),
    "en": ("Hi! I hope EnergyWizard is making a difference in your home. I build it in my spare time, "
           "and much of the code is written together with Claude, an AI that costs money every month. "
           "If you think the project is worth it, I would be really happy for a small contribution, big or small. "
           "It keeps EnergyWizard free and open for everyone. Thank you for being part of it! /Emil"),
}
BUTTON = {"sv": "Sponsra EnergyWizard", "en": "Sponsor EnergyWizard"}


def _month(now):
    return now.strftime("%Y-%m")


def _installed_at(now):
    st = ew_settings.load()
    raw = st.get("installed_at")
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    try:
        ew_settings.update(installed_at=now.isoformat())
    except OSError:
        pass
    return now


def enabled() -> bool:
    return ew_settings.get("sponsor_notice", True) is not False


def set_enabled(on: bool):
    ew_settings.update(sponsor_notice=bool(on))


def _due(now, key):
    if not enabled():
        return False
    if now - _installed_at(now) < timedelta(days=GRACE_DAYS):
        return False
    return ew_settings.get(key) != _month(now)


def state(lang="sv", now=None) -> dict:
    """Vad webben och appen ska visa."""
    now = now or datetime.now()
    lang = lang if lang in TEXT else "en"
    return {"url": URL, "enabled": enabled(), "show": _due(now, "sponsor_seen_month"),
            "title": TITLE[lang], "text": TEXT[lang], "button": BUTTON[lang]}


def dismiss(now=None):
    """Rutan är stängd för den här månaden."""
    ew_settings.update(sponsor_seen_month=_month(now or datetime.now()))


def send_ha_notice(call_service, lang="sv", now=None) -> bool:
    """Skickar månadens notis till Home Assistant (en gång per månad). True om den skickades."""
    now = now or datetime.now()
    if not _due(now, "sponsor_ha_month"):
        return False
    lang = lang if lang in TEXT else "en"
    ok = call_service("persistent_notification", "create", {
        "notification_id": "energywizard_sponsor",
        "title": TITLE[lang],
        "message": f"{TEXT[lang]}\n\n[{BUTTON[lang]}]({URL})",
    })
    if ok:
        ew_settings.update(sponsor_ha_month=_month(now))
    return bool(ok)
