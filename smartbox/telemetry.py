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
# Anonymt livstecken (2026-11-06, Emils beslut): även installationer utan telemetri skickar en gång per dygn bara
# installations-ID (slumpat, hashat) och version - inget om utrustning, mätvärden eller fel. Syns som en installation
# utan utrustning på Installationer. Redovisas i README/DOCS och kan stängas av (TELEMETRY_PING=false / tilläggets
# alternativ "anonymous_ping"). Med den vanliga telemetrin på skickas det inte (översikten räcker).
PING = os.environ.get("TELEMETRY_PING", "true").strip().lower() not in ("false", "0", "no")
SNAPSHOT_EVERY = timedelta(hours=24)        # daglig signal: samlaren räknar "aktiva" som hörda de senaste 3 dygnen
_last_snapshot: datetime | None = None

_ERROR_SEEN: dict[str, datetime] = {}  # (modul, feltyp) -> senast skickad, i minnet räcker - processen kör kontinuerligt


def _hashed_house_id(house_id: str) -> str:
    return hashlib.sha256((house_id or "unknown").encode()).hexdigest()[:16]


def install_id(create: bool = True) -> str | None:
    """Slumpat ID för just den här installationen, sparat i /data/energywizard.json (telemetry_id).
    2026-11-04: house_id dög inte - startguiden skriver "mitt-hus" åt alla, och utan house_id blev det
    "unknown", så många hus räknades som ett och skrev över varandras utrustning. create=False (webben)
    skapar aldrig ett eget, så att motorn och webben inte kan få olika."""
    try:
        import ew_settings
        tid = ew_settings.get("telemetry_id")
        if not tid and create:
            import uuid
            tid = uuid.uuid4().hex
            ew_settings.update(telemetry_id=tid)
            if ew_settings.get("telemetry_id") != tid:     # gick inte att spara: hellre inget än ett nytt varje start
                return None
        return tid or None
    except Exception:
        return None


def house_hash(cfg: dict | None = None, create: bool = True) -> str:
    tid = install_id(create)
    return _hashed_house_id(tid) if tid else _hashed_house_id((cfg or {}).get("house_id", ""))


def _software_version() -> str:
    v = os.environ.get("APP_VERSION", "").strip()          # satt av bildbygget; git finns inte i bilden
    if v and v != "dev":
        return v[:7] if len(v) == 40 and all(c in "0123456789abcdef" for c in v) else v[:40]
    try:                                                    # HA-tillägget: commit skriven vid bygget (ha-addon/smartbox/Dockerfile)
        f = Path(__file__).parent / "VERSION"
        if f.exists() and f.read_text().strip():
            return f.read_text().strip()[:40]
    except OSError:
        pass
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
    m, _, model = m.partition("|")                     # _ha_maker: "tillverkare|modell"
    clean = lambda x, n: "".join(ch for ch in x if ch.isalnum() or ch in " -_.")[:n].strip()
    m, model = clean(m, 40), clean(model, 40)
    if model and m and model.lower().startswith(m.lower()):
        model = model[len(m):].strip()
    return (f"@{m}" + (f"#{model}" if model else "")) if m else ""


def _ha_maker(entity_id: str) -> str:
    import re
    import homeassistant
    if not homeassistant.configured() or not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity_id or ""):
        return ""
    template = ("{%% set d = device_id('%s') %%}{{ device_attr(d, 'manufacturer') or '' }}|{{ device_attr(d, 'model') or '' }}"
                % entity_id)
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
            drv = sec.get("driver", "?")
            if drv == "ftw":                                 # vilken FTW-drivrutin (bara dess namn, t.ex. ftw-pixii)
                name = str((sec.get("ftw") or {}).get("driver") or "?")
                drv = "ftw-" + "".join(ch for ch in name if ch.isalnum() or ch in "_-")[:30]
            out.append(f"{cat}:{drv}{_brand(sec, maker_fn)}")
    for ev in cfg.get("evs", []) or []:
        out.append(f"car:{ev.get('driver', '?')}{_brand(ev, maker_fn)}")
        if isinstance(ev.get("charger"), dict) and ev["charger"].get("driver"):      # laddboxen ligger under bilen
            out.append(f"charger:{ev['charger']['driver']}{_brand(ev['charger'], maker_fn)}")
    for ch in cfg.get("chargers", []) or []:
        out.append(f"charger:{ch.get('driver', '?')}{_brand(ch, maker_fn)}")
    # Elmätaren (märket ur HA, t.ex. Tibber/Shelly/IAMMETER), priskällan och landet, och hur EnergyWizard körs.
    pm = (cfg.get("power_meter") or {})
    if pm.get("entities"):
        out.append(f"meter:ha{_brand(pm, maker_fn)}")
    out.extend(_setup_summary(cfg))
    return out


def _bucket(v, edges, unit):
    """Avrundat intervall, t.ex. 12.8 kWh -> "10-15kWh" - aldrig exakta värden."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    lo = 0
    for e in edges:
        if v < e:
            return f"{lo}-{e}{unit}"
        lo = e
    return f"{lo}+{unit}"


# Senaste läget ur huvudloopen (note_state), avrundat när det skickas. Bara med i den dagliga rapporten.
_state: dict = {}
_state_sent = {"with_temps": False}


def note_state(indoor=None, outdoor=None, indoor_source=None, indoor_sensors=0, indoor_entities=None):
    """Anropas varje varv: innetemperatur, ute, varifrån innetemperaturen kommer (ha_sensors/heatpump/none)
    och vilka givare (bara för att slå upp märket - entiteterna skickas aldrig)."""
    _state.update(indoor=indoor, outdoor=outdoor, indoor_source=indoor_source, indoor_sensors=indoor_sensors,
                  indoor_entities=list(indoor_entities or [])[:6])


def _state_summary(maker_fn=None) -> list[str]:
    out = []
    src = _state.get("indoor_source")
    if src:
        brands = sorted({b for b in (_brand({"entities": {"e": e}}, maker_fn) for e in _state.get("indoor_entities") or []) if b})
        n = _state.get("indoor_sensors") or 0
        out.append(f"indoor:{src}" + (f"_{n}" if src == "ha_sensors" else "") + (brands[0] if len(brands) == 1 else ""))
        if len(brands) > 1:
            out.append(f"indoor:mixed@{'+'.join(x.lstrip('@').split('#')[0] for x in brands)[:60]}")
    for key, name in (("indoor", "temp:inne"), ("outdoor", "temp:ute")):
        v = _state.get(key)
        if isinstance(v, (int, float)) and -60 < v < 60:
            out.append(f"{name}_{int(round(v))}C")
    return out


def _setup_summary(cfg: dict) -> list[str]:
    out = []
    # Storlekar, avrundade till intervall (2026-11-04)
    bat = cfg.get("battery") or {}
    if bat.get("enabled"):
        b = _bucket(bat.get("capacity_kwh"), (5, 10, 15, 20, 30, 50), "kWh")
        if b:
            out.append(f"size:battery_{b}")
    for ev in cfg.get("evs", []) or []:
        b = _bucket(ev.get("battery_kwh"), (30, 50, 70, 90), "kWh")
        if b:
            out.append(f"size:car_{b}")
    fuse = (cfg.get("fuse") or {}).get("main_fuse_a")
    if fuse:
        try:
            out.append(f"size:fuse_{int(float(fuse))}A")
        except (TypeError, ValueError):
            pass
    try:
        import nordpool
        out.append(f"price:{nordpool.price_source()}")
        cs = nordpool.cost_settings()
        out.append(f"country:{cs['country']}")
        if cs.get("tou_extra"):
            out.append("mode:tou_tariff")
    except Exception:
        pass
    bat = cfg.get("battery") or {}
    if bat.get("enabled"):
        ctl = str(bat.get("control", "samarbete")).lower()
        out.append(f"mode:battery_{ctl if ctl in ('styr', 'samarbete', 'av') else 'samarbete'}")
        if bat.get("modes"):
            out.append(f"mode:preset_{str(bat.get('preset') or 'egen')[:30]}")
    try:
        import ew_settings
        if ew_settings.get("shadow_mode"):
            out.append("mode:shadow")
    except Exception:
        pass
    return out


def maybe_send_daily(cfg: dict, now: datetime | None = None) -> None:
    """Anropas varje varv i huvudloopen: skickar översikten igen när ett dygn gått (signalen "aktiv")."""
    global _last_snapshot
    now = now or datetime.now(timezone.utc)
    if not OPT_IN and PING and ENDPOINT:                  # bara livstecken, en gång per dygn
        if _last_snapshot is None or now - _last_snapshot >= SNAPSHOT_EVERY:
            _last_snapshot = now
            import threading
            threading.Thread(target=send_ping, args=(cfg,), daemon=True, name="telemetry-ping").start()
        return
    if not (OPT_IN and ENDPOINT):
        return
    # Startrapporten skickas innan något är uppmätt: skicka en gång till när temperaturerna finns (sedan dygnsvis).
    first_temps = not _state_sent["with_temps"] and _state.get("indoor_source") is not None
    if not first_temps and _last_snapshot is not None and now - _last_snapshot < SNAPSHOT_EVERY:
        return
    _state_sent["with_temps"] = _state_sent["with_temps"] or first_temps
    _last_snapshot = now                              # sätts direkt: en långsam HA ska inte ge flera trådar
    import threading
    threading.Thread(target=send_driver_snapshot, args=(cfg,), daemon=True, name="telemetry-daily").start()


def send_ping(cfg: dict) -> None:
    """Anonymt livstecken: installations-ID (hashat) och version, inget annat. Se PING ovan."""
    global _last_snapshot
    if OPT_IN or not (PING and ENDPOINT):
        return
    _last_snapshot = datetime.now(timezone.utc)
    try:
        requests.post(f"{ENDPOINT}/ingest/drivers", json={"house": house_hash(cfg), "version": _software_version(),
                                                           "drivers": [], "ping": True}, timeout=5)
    except Exception as e:
        print(f"ℹ️ Livstecken kunde inte skickas, fortsätter ändå: {e}")


def send_driver_snapshot(cfg: dict) -> None:
    """Skickas vid uppstart och sedan en gång per dygn - vilka drivrutinkategorier som är aktiva."""
    global _last_snapshot
    if not (OPT_IN and ENDPOINT):
        return
    _last_snapshot = datetime.now(timezone.utc)
    try:
        payload = {
            "house": house_hash(cfg),
            "version": _software_version(),
            "drivers": _driver_summary(cfg, _ha_maker) + _state_summary(_ha_maker),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        requests.post(f"{ENDPOINT}/ingest/drivers", json=payload, timeout=5)
    except Exception as e:
        print(f"ℹ️ Telemetri (drivrutinsöversikt) kunde inte skickas, fortsätter ändå: {e}")


ERROR_REPEAT = timedelta(hours=1)


def report_error(cfg: dict, module: str, error_type: str) -> None:
    """module/error_type ska alltid vara korta konstanter (t.ex. modulnamn och
    exceptionens klassnamn via type(e).__name__) - aldrig str(exception) rakt
    av. Avdubblar en gång/timme per (modul, feltyp): en upprepad bugg spammar inte samlaren, men ett fel som
    kvarstår rapporteras igen varje timme, så Installationer kan visa bara fel som fortfarande uppstår."""
    if not (OPT_IN and ENDPOINT):
        return
    try:
        key = f"{module}:{error_type}"
        now = datetime.now(timezone.utc)
        last = _ERROR_SEEN.get(key)
        if last is not None and (now - last) < ERROR_REPEAT:
            return
        _ERROR_SEEN[key] = now
        payload = {
            "house": house_hash(cfg),
            "version": _software_version(),
            "module": module,
            "error_type": error_type,
            "ts": now.isoformat(),
        }
        requests.post(f"{ENDPOINT}/ingest/error", json=payload, timeout=5)
    except Exception as e:
        print(f"ℹ️ Telemetri (felrapport) kunde inte skickas, fortsätter ändå: {e}")


# ---- Felkrok (2026-11-04) -----------------------------------------------------------------------------------------
# Motorn skriver fel som "❌ ..." på ett 60-tal ställen (fångade undantag som annars bara syns i loggen, t.ex.
# databasfel, HA som inte svarar, drivrutiner som inte når pumpen/laddboxen). Kroken rapporterar varje sådan rad
# som modul.funktion + undantagets typ - kodens egna namn, ALDRIG radens text (den kan innehålla adresser och
# entitetsnamn). report_error avdubblar en gång per timme och feltyp. Samlaren gör sedan GitHub-issues av dem.
_hook_cfg: dict = {}


def install_error_hook(cfg: dict) -> None:
    import builtins
    import sys
    import threading
    _hook_cfg.clear()
    _hook_cfg.update(cfg or {})
    if getattr(builtins.print, "_ew_hook", False) or not (OPT_IN and ENDPOINT):
        return
    orig = builtins.print

    def hooked(*args, **kwargs):
        orig(*args, **kwargs)
        try:
            if not args or not isinstance(args[0], str) or not args[0].lstrip().startswith("❌"):
                return
            f = sys._getframe(1)
            mod = os.path.splitext(os.path.basename(f.f_code.co_filename))[0]
            if mod == "telemetry":
                return
            exc = sys.exc_info()[0]
            where = f"{mod}.{f.f_code.co_name}"[:60]
            kind = exc.__name__ if exc else "Error"
            threading.Thread(target=report_error, args=(_hook_cfg, where, kind), daemon=True).start()
        except Exception:
            pass

    hooked._ew_hook = True
    builtins.print = hooked
