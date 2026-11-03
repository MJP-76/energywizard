"""Telemetri: PÅ som standard, mot en publik samlare Emil driftsätter
(https://energywizzard.profitalgos.com/telemetry) - stäng av med
TELEMETRY_OPT_IN=false i .env om du inte vill skicka något alls, eller peka
om med TELEMETRY_ENDPOINT. Avstängt skickas absolut ingenting - ingen
nätverksanrop görs ens.

Vad som skickas när den är PÅ (och bara det):
  - en anonymiserad husidentifierare (sha256(house_id), inte house_id i klartext)
  - vilka drivrutinklasser som är aktiva (klassnamn, t.ex. "GenericSolarDriver" -
    inga entity-id:n, inga sensorvärden, inga adresser/IP:n), och för varje
    kategori tillverkarens namn enligt Home Assistants enhetsregister (t.ex.
    "FoxESS"), så att generiska drivrutiner också säger vilket märke de styr
  - en gång per dygn, så att samlaren kan räkna aktiva installationer
  - fel: modul + feltyp (exceptionens klassnamn, ALDRIG str(exception) - kan
    innehålla sensorvärden eller sökvägar)
  - tidsstämpel och git-commit-hash (grov versionsindikator)
Inget annat skickas - ingen elprisdata, ingen sensorhistorik, ingen plats.

Fail-safe med flit: ett nätverksfel eller en trasig collector får ALDRIG
störa huvudloopen i main.py - varje publik funktion fångar allt och loggar
bara lokalt, med kort timeout.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# På som standard - TELEMETRY_OPT_IN=false (eller "0"/"no") stänger av helt.
OPT_IN = os.environ.get("TELEMETRY_OPT_IN", "true").strip().lower() not in ("false", "0", "no")
# Tom sträng = standard: docker-compose skickar TELEMETRY_ENDPOINT= (tom) när .env saknar raden, och då
# skickades ingenting alls (upptäckt 2026-11-03 - Emils eget hus syntes aldrig i samlaren).
ENDPOINT = (os.environ.get("TELEMETRY_ENDPOINT", "").strip() or "https://energywizzard.profitalgos.com/telemetry").rstrip("/")
SNAPSHOT_EVERY = timedelta(hours=24)        # daglig signal: samlaren räknar "aktiva" som hörda de senaste 3 dygnen
_last_snapshot: datetime | None = None

_ERROR_SEEN: dict[str, datetime] = {}  # (modul, feltyp) -> senast skickad, i minnet räcker - processen kör kontinuerligt


def _hashed_house_id(house_id: str) -> str:
    return hashlib.sha256((house_id or "unknown").encode()).hexdigest()[:16]


def _software_version() -> str:
    v = os.environ.get("APP_VERSION", "").strip()          # satt av bildbygget; git finns inte i bilden
    if v and v != "dev":
        return v[:40]
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=3, cwd=Path(__file__).parent)
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _first_entity(section: dict) -> str | None:
    for v in (section.get("entities") or {}).values():
        if isinstance(v, str) and "." in v:
            return v
    return None


def _brand(section: dict, maker_fn) -> str:
    """Tillverkaren (HA:s enhetsregister) för sektionens första entitet - bara märkesnamnet, aldrig entiteten."""
    e = _first_entity(section)
    if not e or maker_fn is None:
        return ""
    try:
        m = (maker_fn(e) or "").strip()
    except Exception:
        return ""
    m = "".join(ch for ch in m if ch.isalnum() or ch in " -_.")[:40].strip()
    return f"@{m}" if m else ""


def _ha_maker(entity_id: str) -> str:
    import re
    import homeassistant
    if not homeassistant.configured() or not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity_id or ""):
        return ""
    template = "{{ device_attr(device_id('%s'), 'manufacturer') or '' }}" % entity_id
    r = requests.post(f"{homeassistant._BASE}/template", headers=homeassistant._HEADERS, timeout=5,
                      verify=homeassistant._VERIFY, json={"template": template})
    r.raise_for_status()
    return r.text.strip()


def _driver_summary(cfg: dict, maker_fn=None) -> list[str]:
    """Kategoriska drivrutinsnamn, t.ex. ["heatpump:husdata", "car:tesla", "battery:generic@FoxESS"] -
    bara klassnamn/kategorier ur configen och märkesnamn ur HA:s enhetsregister, inga entity-id:n."""
    out = []
    for key, cat in (("heat_pump", "heatpump"), ("solar", "solar"), ("spa", "spa"), ("battery", "battery")):
        sec = cfg.get(key, {}) or {}
        if sec.get("enabled"):
            out.append(f"{cat}:{sec.get('driver', '?')}{_brand(sec, maker_fn)}")
    for ev in cfg.get("evs", []) or []:
        out.append(f"car:{ev.get('driver', '?')}{_brand(ev, maker_fn)}")
    for ch in cfg.get("chargers", []) or []:
        out.append(f"charger:{ch.get('driver', '?')}{_brand(ch, maker_fn)}")
    return out


def maybe_send_daily(cfg: dict, now: datetime | None = None) -> None:
    """Anropas varje varv i huvudloopen: skickar översikten igen när ett dygn gått (signalen "aktiv")."""
    global _last_snapshot
    now = now or datetime.now(timezone.utc)
    if not (OPT_IN and ENDPOINT) or (_last_snapshot is not None and now - _last_snapshot < SNAPSHOT_EVERY):
        return
    _last_snapshot = now                              # sätts direkt: en långsam HA ska inte ge flera trådar
    import threading
    threading.Thread(target=send_driver_snapshot, args=(cfg,), daemon=True, name="telemetry-daily").start()


def send_driver_snapshot(cfg: dict) -> None:
    """Skickas vid uppstart och sedan en gång per dygn - vilka drivrutinkategorier som är aktiva."""
    global _last_snapshot
    if not (OPT_IN and ENDPOINT):
        return
    _last_snapshot = datetime.now(timezone.utc)
    try:
        payload = {
            "house": _hashed_house_id(cfg.get("house_id", "")),
            "version": _software_version(),
            "drivers": _driver_summary(cfg, _ha_maker),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        requests.post(f"{ENDPOINT}/ingest/drivers", json=payload, timeout=5)
    except Exception as e:
        print(f"ℹ️ Telemetri (drivrutinsöversikt) kunde inte skickas, fortsätter ändå: {e}")


def report_error(cfg: dict, module: str, error_type: str) -> None:
    """module/error_type ska alltid vara korta konstanter (t.ex. modulnamn och
    exceptionens klassnamn via type(e).__name__) - aldrig str(exception) rakt
    av. Avdubblar en gång/dygn per (modul, feltyp) så en upprepad bugg inte
    spammar samlaren."""
    if not (OPT_IN and ENDPOINT):
        return
    try:
        key = f"{module}:{error_type}"
        now = datetime.now(timezone.utc)
        last = _ERROR_SEEN.get(key)
        if last is not None and (now - last) < timedelta(hours=24):
            return
        _ERROR_SEEN[key] = now
        payload = {
            "house": _hashed_house_id(cfg.get("house_id", "")),
            "version": _software_version(),
            "module": module,
            "error_type": error_type,
            "ts": now.isoformat(),
        }
        requests.post(f"{ENDPOINT}/ingest/error", json=payload, timeout=5)
    except Exception as e:
        print(f"ℹ️ Telemetri (felrapport) kunde inte skickas, fortsätter ändå: {e}")
