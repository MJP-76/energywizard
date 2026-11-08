"""control_journal.py - "Höll vi planen?" (idé från FTW v0.160, Emil godkände 2026-11-07)

Varje minut jämför motorn det den beställde med det enheten faktiskt gjorde, per enhet:
  - elbil: beställd ström mot uppmätt (bara när bilen är inkopplad)
  - värmepump: beställd rumstemperatur mot det pumpen läser tillbaka
  - husbatteri: följer batteriet beslutet? (battery_follow.py)
Resultatet sparas i tabellen control_journal (30 dygn) och sammanfattas per dygn: hur stor del av minuterna
enheten gjorde som vi sa, och när den inte gjorde det (sammanhängande avvikelser, med en förklaring när den finns).
Visas i appen (Historik) och på webben (Historik) med samma sammanfattning (summarize nedan).

I skuggläge beställs ingenting, och då sparas inget heller.
"""
from datetime import timedelta

KEEP_DAYS = 30
EV_MARGIN_A = 2.0
PUMP_MARGIN_C = 0.6


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def check_ev(name, ordered_a, reading, note=None):
    """(enhet, ok, beställt, faktiskt, förklaring) eller None när det inte går att bedöma."""
    got = _f((reading or {}).get("current_a"))
    if ordered_a is None or got is None:
        return None
    if ordered_a <= 0:
        ok = got < 1.5
        return (name, ok, "paus", f"{got:.0f} A", None if ok else "Laddade trots paus")
    ok = got >= ordered_a - EV_MARGIN_A
    return (name, ok, f"{ordered_a:.0f} A", f"{got:.0f} A", None if ok else (note or ("Laddade inte" if got < 1 else "Lägre ström")))


def check_pump(ordered_c, actual_c):
    a, o = _f(actual_c), _f(ordered_c)
    if a is None or o is None:
        return None
    ok = abs(a - o) <= PUMP_MARGIN_C
    return ("Värmepump", ok, f"{o:.1f} °C", f"{a:.1f} °C", None if ok else "Pumpen har en annan måltemperatur")


def check_battery(status, text, intent):
    if status not in ("following", "not_following"):
        return None                     # "checking" (väntar ut en ändring) eller ingen kontroll
    ok = status == "following"
    return ("Husbatteri", ok, str(intent or ""), "följer" if ok else "följer inte", None if ok else (text or None))


# ---- sammanfattning (ren, testas i tests/test_control_journal.py) ----

def summarize(rows, gap_min=3):
    """rows: [(ts, enhet, ok, beställt, faktiskt, förklaring)] i tidsordning. Returnerar per enhet andel minuter
    som följde planen och sammanhängande avvikelser (avbrott kortare än gap_min minuter slås ihop)."""
    by = {}
    for ts, dev, ok, ordered, actual, note in rows:
        d = by.setdefault(dev, {"device": dev, "minutes": 0, "ok": 0, "deviations": []})
        d["minutes"] += 1
        if ok:
            d["ok"] += 1
            continue
        devs = d["deviations"]
        if devs and ts - devs[-1]["_end"] <= timedelta(minutes=gap_min):
            devs[-1]["_end"] = ts
            devs[-1]["minutes"] += 1
            if note and not devs[-1]["note"]:
                devs[-1]["note"] = note
        else:
            devs.append({"_start": ts, "_end": ts, "minutes": 1, "ordered": ordered, "actual": actual, "note": note})
    out = []
    for d in by.values():
        d["pct"] = round(100.0 * d["ok"] / d["minutes"]) if d["minutes"] else None
        devs = [x for x in d["deviations"] if x["minutes"] >= 2]     # enstaka minuter = mätbrus/eftersläpning
        d["deviations"] = [{"start": x["_start"].isoformat(), "end": x["_end"].isoformat(), "minutes": x["minutes"],
                            "ordered": x["ordered"], "actual": x["actual"], "note": x["note"]} for x in devs[-12:]]
        d["deviation_minutes"] = sum(x["minutes"] for x in devs)
        out.append(d)
    order = {"Husbatteri": 0, "Värmepump": 1}
    out.sort(key=lambda d: (order.get(d["device"], 2), d["device"]))
    return out


# ---- databas ----

_SCHEMA = """CREATE TABLE IF NOT EXISTS control_journal (
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(), device TEXT NOT NULL, ok BOOLEAN NOT NULL,
    ordered TEXT, actual TEXT, note TEXT)"""
_pruned = {"at": 0.0}


def record(get_db, checks, now_ts: float) -> None:
    rows = [c for c in checks if c]
    if not rows:
        return
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute(_SCHEMA)
            cur.execute("CREATE INDEX IF NOT EXISTS control_journal_ts ON control_journal (ts)")
            cur.executemany("INSERT INTO control_journal (device, ok, ordered, actual, note) VALUES (%s,%s,%s,%s,%s)",
                            [(d, bool(ok), o, a, (n or None) and str(n)[:300]) for d, ok, o, a, n in rows])
            if now_ts - _pruned["at"] > 3600:
                cur.execute(f"DELETE FROM control_journal WHERE ts < NOW() - INTERVAL '{KEEP_DAYS} days'")
                _pruned["at"] = now_ts
            conn.commit()
    except Exception as e:
        print(f"❌ control_journal.record: {e}")


SQL_DAY = """SELECT ts, device, ok, ordered, actual, note FROM control_journal
             WHERE ts >= (date_trunc('day', NOW() AT TIME ZONE 'Europe/Stockholm') - make_interval(days => :back))
                          AT TIME ZONE 'Europe/Stockholm'
               AND ts <  (date_trunc('day', NOW() AT TIME ZONE 'Europe/Stockholm') - make_interval(days => :back - 1))
                          AT TIME ZONE 'Europe/Stockholm'
             ORDER BY ts"""


def day_summary(conn, back: int = 0) -> list:
    """Sammanfattning för ett dygn (0 = idag, 1 = igår) via en SQLAlchemy-anslutning (appen och webben)."""
    from sqlalchemy import text
    try:
        rows = conn.execute(text(SQL_DAY), {"back": int(back)}).all()
    except Exception:
        conn.rollback()      # tabellen finns inte än (motorn har inte hunnit skriva); lämna anslutningen användbar
        return []
    return summarize([tuple(r) for r in rows])
