"""notify_log.py - aviseringshistorik med leveransstatus (idé från FTW v0.160, Emil godkände 2026-11-07).

"Fick jag ingen notis, eller skickades den aldrig?" Varje avisering från motorn (notifier.py) och mobilappen (ewapp
push) sparas här med hur det gick:
  sent    Home Assistant tog emot den (HA bekräftar inte att telefonen fått den, bara att den skickades vidare)
  failed  Home Assistant svarade med fel eller svarade inte (orsaken sparas)
  muted   kategorin är avstängd under Inställningar -> Notiser
  none    ingen mottagare (ingen telefon vald eller hittad, eller ingen hemma med "bara den som är hemma")
Tabellen notify_log hålls i 60 dygn. Egen kort anslutning (används både i motorn och i appen). Fel här får aldrig
stoppa själva aviseringen.
"""
import os

KEEP_DAYS = 60
STATUS_TEXT = {"sent": "Skickad", "failed": "Misslyckades", "muted": "Avstängd kategori", "none": "Ingen mottagare"}

_SCHEMA = """CREATE TABLE IF NOT EXISTS notify_log (
    id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT NOW(), src TEXT, category TEXT, title TEXT,
    message TEXT, recipient TEXT, status TEXT NOT NULL, detail TEXT)"""
_n = {"writes": 0}


def _category(key, title):
    if key:
        return key
    try:
        import notify_prefs
        return notify_prefs.category_for(title or "")
    except Exception:
        return None


def add(title, message, status, recipient=None, key=None, detail=None, src="motorn"):
    try:
        import psycopg
        with psycopg.connect(host=os.environ.get("POSTGRES_HOST", "postgres-smartbox"), user=os.environ["POSTGRES_USER"],
                             password=os.environ["POSTGRES_PASSWORD"], dbname=os.environ["POSTGRES_DB"], connect_timeout=5) as c:
            c.execute(_SCHEMA)
            c.execute("INSERT INTO notify_log (src, category, title, message, recipient, status, detail) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                      (src, _category(key, title), str(title or "")[:200], str(message or "")[:1000],
                       (recipient or "").removeprefix("notify.") or None, status, (str(detail)[:300] if detail else None)))
            _n["writes"] += 1
            if _n["writes"] % 50 == 1:
                c.execute(f"DELETE FROM notify_log WHERE ts < NOW() - INTERVAL '{KEEP_DAYS} days'")
    except Exception as e:
        print(f"⚠️ Aviseringshistoriken: {type(e).__name__}: {e}")


def short_error(e) -> str:
    """En begriplig orsak ur ett requests-fel (utan adresser eller nycklar)."""
    s = getattr(getattr(e, "response", None), "status_code", None)
    if s == 401:
        return "Home Assistant nekade (fel eller utgången token)"
    if s == 400:
        return "Home Assistant avvisade aviseringen (finns mottagaren kvar?)"
    if s:
        return f"Home Assistant svarade {s}"
    n = type(e).__name__
    if "Timeout" in n:
        return "Home Assistant svarade inte i tid"
    if "Connection" in n:
        return "Kunde inte nå Home Assistant"
    return n


def recent(conn, days: int = 7, limit: int = 200) -> list:
    """Senaste aviseringarna via en SQLAlchemy-anslutning (appen och webben)."""
    from sqlalchemy import text
    try:
        rows = conn.execute(text("SELECT ts, src, category, title, message, recipient, status, detail FROM notify_log "
                                 "WHERE ts >= NOW() - make_interval(days => :d) ORDER BY ts DESC LIMIT :n"),
                            {"d": int(days), "n": int(limit)}).mappings().all()
    except Exception:
        conn.rollback()           # tabellen finns inte än
        return []
    labels = {}
    try:
        import notify_prefs
        labels = {k: label for k, label, _ in notify_prefs.CATEGORIES}
    except Exception:
        pass
    return [{"ts": r["ts"].isoformat(), "src": r["src"], "category": labels.get(r["category"], r["category"]),
             "title": r["title"], "message": r["message"], "recipient": r["recipient"], "status": r["status"],
             "status_text": STATUS_TEXT.get(r["status"], r["status"]), "detail": r["detail"]} for r in rows]
