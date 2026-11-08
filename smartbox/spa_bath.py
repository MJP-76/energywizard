"""spa_bath.py - badtider för spabadet (Emil 2026-11-08).

Spabadet hölls varmt dygnet runt, och nattsänkningen gav lite: ett välisolerat bad svalnar bara någon grad och värms
sedan upp igen på morgonen. Med badtider (vilka dagar och tider man brukar bada) får badet ligga på eco-golvet
(spa_low_temp) utanför dem och värms upp inför nästa badtid, på de billigaste timmarna (samma planerare som det
manuella spabadsschemat, decisions.check_spa_schedule_plan).

Inställningen (ew_settings "spa_bath_windows"): sju poster, en per veckodag (0 = måndag):
    [{"on": false}, ..., {"on": true, "from": "10:00", "to": "18:00"}, ...]
Inga påslagna dagar = ingen badtidsstyrning (som förut). Ren logik här; testas i tests/test_spa_bath.py.
"""
from datetime import datetime, time, timedelta

PLAN_AHEAD_H = 36          # längre bort än så planeras ingen uppvärmning än (badet ligger kvar på eco-golvet)


def _t(s, default):
    try:
        h, m = (int(x) for x in str(s).split(":")[:2])
        return time(h % 24, m % 60)
    except (TypeError, ValueError):
        return default


def windows(raw) -> list:
    """Normaliserar inställningen till [(veckodag, från, till)] för påslagna dagar."""
    out = []
    for day, w in enumerate((raw or [])[:7]):
        if isinstance(w, dict) and w.get("on"):
            a, b = _t(w.get("from"), time(17, 0)), _t(w.get("to"), time(22, 0))
            if b > a:
                out.append((day, a, b))
    return out


def status(now: datetime, raw):
    """(i_badtid, nästa_start, nuvarande_slut). nästa_start = början på nästa badtid inom en vecka (None = inga
    badtider). i_badtid = True mellan från och till en badtidsdag."""
    ws = windows(raw)
    if not ws:
        return False, None, None
    best = None
    for k in range(8):
        d = (now + timedelta(days=k)).date()
        for day, a, b in ws:
            if d.weekday() != day:
                continue
            start = datetime.combine(d, a, tzinfo=now.tzinfo)
            end = datetime.combine(d, b, tzinfo=now.tzinfo)
            if start <= now < end:
                return True, start, end
            if start > now and (best is None or start < best):
                best = start
    return False, best, None


def listing(raw) -> list:
    """Sju poster för gränssnitten (appen och webben): [{"on", "from", "to"}], måndag först."""
    out = []
    for i in range(7):
        w = raw[i] if isinstance(raw, list) and i < len(raw) and isinstance(raw[i], dict) else {}
        out.append({"on": bool(w.get("on")), "from": str(w.get("from") or "17:00")[:5], "to": str(w.get("to") or "21:00")[:5]})
    return out


def clean(rows):
    """Det gränssnitten skickar -> det som sparas (None = inga badtider). Ogiltiga tider eller till <= från: dagen av."""
    import re
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError("Sju dagar behövs")
    ok = lambda s: bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(s or "")))
    out = []
    for w in rows:
        w = w if isinstance(w, dict) else {}
        a, b = str(w.get("from") or ""), str(w.get("to") or "")
        good = ok(a) and ok(b)
        out.append({"on": bool(w.get("on")) and good and b > a, "from": a if good else "17:00", "to": b if good else "21:00"})
    return out if any(x["on"] for x in out) else None


def summary(saved) -> str:
    n = sum(1 for w in (saved or []) if w.get("on"))
    return (f"Sparat - {n} badtider. Utanför dem får badet svalna till eco-golvet och värms i tid före nästa." if n
            else "Sparat - inga badtider, badet hålls varmt som förut.")
