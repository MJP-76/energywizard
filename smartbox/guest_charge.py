"""guest_charge.py - gästbil på en laddbox (#131).

En bil som inte finns i installationen: ingen laddnivå, inget schema. Användaren anger hur mycket (kWh) och ev. när den
ska vara klar (appen: Gästbil). Motorn laddar då:
  - med klar-tid: de billigaste kvartarna mellan nu och klar-tiden som räcker för energin (räknat på laddboxens effekt),
  - utan klar-tid: direkt.
Strömmen är alltid högst laddboxens max och det säkringen tål just nu (fuse_a - husets last utan elbil - marginal).
Gästläget avslutas när energin är levererad, när kabeln dras ur efter att ha suttit i, eller efter MAX_HOURS.

Ren logik (testas i tests/test_guest_charge.py); main.py läser överstyrningen guest_<bil> och sätter strömmen.
"""
import json
import math
from datetime import datetime, timedelta

MARGIN_A = 2
MAX_HOURS = 36
SLOT = timedelta(minutes=15)


def parse(raw):
    """Överstyrningen guest_<bil> -> dict eller None. {"kwh": 20, "until": iso|None, "set_at": iso}."""
    if not raw or raw in ("off", "auto"):
        return None
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) and float(d.get("kwh") or 0) > 0 else None
    except (ValueError, TypeError):
        return None


def charge_kw(max_a, phases, volt=230.0):
    return max_a * volt * (3 if int(phases or 3) == 3 else 1) / 1000.0


def should_charge(now, kwh_left, until, kw, price_at):
    """True om den här kvarten ska laddas. price_at(t) -> pris för kvarten som börjar t (eller None)."""
    if kwh_left <= 0:
        return False
    if until is None:
        return True
    if now >= until:
        return True                                         # för sent - ladda det som går
    q0 = now.replace(minute=now.minute - now.minute % 15, second=0, microsecond=0)
    slots = []
    t = q0
    while t < until:
        p = price_at(t)
        slots.append((p if p is not None else float("inf"), t))
        t += SLOT
    need = max(1, math.ceil(kwh_left / max(0.1, kw * 0.25)))
    if need >= len(slots):
        return True                                         # behöver alla kvartar som finns kvar
    chosen = {t for _p, t in sorted(slots, key=lambda x: (x[0], x[1]))[:need]}
    return q0 in chosen


def amps(now, guest, delivered_kwh, max_a, phases, available_a, price_at):
    """Strömmen (A) för gästbilen just nu, och skälet."""
    kwh_left = float(guest.get("kwh") or 0) - float(delivered_kwh or 0)
    until = datetime.fromisoformat(guest["until"]) if guest.get("until") else None
    if kwh_left <= 0:
        return 0, "Gästbilen har fått sina kWh"
    cap = int(max(0, min(max_a, (available_a or max_a) - MARGIN_A)))
    if cap < 6:
        return 0, "Gästbilen väntar - säkringen har inte utrymme just nu"
    if should_charge(now, kwh_left, until, charge_kw(cap, phases), price_at):
        return cap, f"Gästbil: laddar ({kwh_left:.1f} kWh kvar{', klar ' + until.strftime('%H:%M') if until else ''})"
    return 0, f"Gästbil: väntar på billigare kvartar ({kwh_left:.1f} kWh kvar till {until.strftime('%H:%M')})"


def expired(guest, now):
    try:
        return now - datetime.fromisoformat(guest["set_at"]) > timedelta(hours=MAX_HOURS)
    except (KeyError, ValueError, TypeError):
        return False
