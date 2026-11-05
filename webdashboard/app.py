"""EnergyWizard Webdashboard: ny dator-/surfplatte-dashboard, ersätter smartdashboard
(Streamlit) stegvis (EnergyWizard Open, Fas A-F - se /home/emil/.claude/plans/
glowing-moseying-octopus.md). Byggd på samma mönster som ewapp (FastAPI, inget
byggsteg, delad databas) men med en desktop-layout (sidomeny, flera sidor samtidigt
synliga, vanlig scroll) istället för ewapp:s enda-skärm-mobillayout.

Fas A: bara inloggning (delad med ewapp via smartbox/webauth.py), sidomeny-skal med
alla 13 planerade sidor, och en testgraf som bevisar att ECharts-pipen fungerar.
Ingen sida har riktigt innehåll än - det är Fas B och framåt.
"""
import asyncio
import hashlib
import hmac
import math
import os
import sys
import time
import zoneinfo

import re
import requests

sys.path.insert(0, "/smartbox")
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text

import webauth
import discovery
import house_config
import pump

WATCHTOWER_URL = os.environ.get("WATCHTOWER_URL", "http://host.docker.internal:8090")
WATCHTOWER_TOKEN = os.environ.get("WATCHTOWER_API_TOKEN", "")
# Bara på utvecklarens egen installation: telemetrisamlarens sammanställning (antal aktiva + utrustning).
TELEMETRY_STATS_URL = os.environ.get("TELEMETRY_STATS_URL", "").strip()
TELEMETRY_STATS_TOKEN = os.environ.get("TELEMETRY_STATS_TOKEN", "").strip()       # samma som samlarens STATS_TOKEN
INSTALLS_PAGE = {"id": "installationer", "name": "Installationer", "icon": "👥", "built": True}
# /v1/check gör en riktig registry-koll (tar ~5s) - cachas här så "System"-sidan
# inte startar om den varje gång sidan öppnas.
_wt_cache = {"ts": 0, "data": None}
WT_CACHE_TTL = 600

ENGINE = create_engine(
    f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@{os.environ.get('POSTGRES_HOST', 'postgres-smartbox')}/{os.environ['POSTGRES_DB']}",
    pool_pre_ping=True, pool_size=3,
)

# Eget salt ("webdash") -> egen cookie-scope, skild session från ewapp även om PASSWORD
# är detsamma. family-rollen har inga skriv-vägar än (Fas A har inga formulär alls).
AUTH = webauth.Auth(salt="webdash", family_write_prefixes=(), cookie="ew_web")      # egen kaka, se webauth.Auth

# -- styrkommandon: samma knappar som ewapp, inte dubblerad logik ------------------------
# webdashboard har ingen egen Tesla/Nissan/SolarEdge/spa-styrningskod - den enda riktiga
# hårdvarulogiken (handskakningar, HA-anrop) finns i ewapp/app.py, redan testad i skarp
# drift. Istället för att skriva om den (gissad kod = exakt det det här projektet undviker,
# se ROADMAP) PROXAR webdashboard de skrivande anropen till ewapp-containern internt
# (samma docker-nät, container_name "ewapp", port 8502) med ett eget serversignerat
# "ew"-cookie - exakt samma HMAC-formel ewapp/app.py:s _sign() använder (salt "ewapp"),
# bara byggd server-till-server här istället för att komma från webbläsaren.
# OBS: /api/secure + /api/tesla/access (lås/upplåsning/luckor) är MEDVETET INTE proxade -
# det är ett separat omverifieringsflöde (eget "ew2"-cookie, lösenord igen, 10 minuters
# fönster) som förtjänar sin egen, noga testade implementation - inte en hastig kopia.
EWAPP_URL = os.environ.get("EWAPP_URL", "http://ewapp:8502")
_EWAPP_SECRET = hashlib.sha256(("ewapp|" + webauth.owner_password()).encode()).digest()


def _ewapp_cookie() -> str:
    exp = int(time.time()) + 60
    payload = f"{exp}.owner.owner"
    return f"{payload}.{hmac.new(_EWAPP_SECRET, payload.encode(), hashlib.sha256).hexdigest()}"


async def _ewapp_proxy(path: str, body: dict, extra_cookies: dict | None = None) -> JSONResponse:
    try:
        cookies = {"ew": _ewapp_cookie()}
        cookies.update(extra_cookies or {})
        r = requests.post(f"{EWAPP_URL}{path}", cookies=cookies, json=body, timeout=25)
    except requests.RequestException as e:
        return JSONResponse({"detail": f"Nådde inte ewapp: {e}"}, status_code=502)
    try:
        data = r.json()
    except ValueError:
        data = {"detail": r.text}
    return JSONResponse(data, status_code=r.status_code)


# -- Bil-lås/luckor: eget, separat omverifieringsflöde (ew2), inte bara proxat rakt av ----
# Lås upp/luckor kräver lösenordet igen (10 min) precis som i ewapp - webdashboard har sin
# EGEN ew2-kaka (samma hemlighet/formel som ewapp:s _secure_ok(), eftersom bägge delar
# PASSWORD) så den kan vidareskickas till ewapp:s /api/tesla/access och godkännas där utan
# att webdashboard behöver duplicera Tesla-hanteringen eller spärrlogiken - ewapp:s egen
# _secure_ok()/_unlock_fails kör fortfarande på riktigt, bara anropad härifrån också.
_secure_fails: dict = {}


def _secure_ok(request: Request) -> bool:
    v = request.cookies.get("ew2", "")
    try:
        exp, sig = v.split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(sig, hmac.new(_EWAPP_SECRET, ("sec" + exp).encode(), hashlib.sha256).hexdigest())
    except Exception:
        return False


# De 13 sidorna enligt inventeringen av smartdashboard (se planfilen) - tomma till Fas B+.
# "built": False döljs i menyn (se /api/me) tills sidan faktiskt har eget innehåll i
# app.js - en platshållarflik ("byggs i en senare fas") är precis det en betatestare
# tolkar som att allt är trasigt, så den ska aldrig synas i en skarp installation.
PAGES = [
    {"id": "oversikt", "name": "Översikt", "icon": "📊", "built": True},
    {"id": "ekonomi", "name": "Ekonomi", "icon": "💰", "built": True},
    {"id": "elforbrukning", "name": "Elförbrukning", "icon": "🔌", "built": True},
    {"id": "elbil", "name": "Elbil", "icon": "⚡", "built": True},
    {"id": "varmepump", "name": "Värmepump", "icon": "♨️", "built": True},
    {"id": "solceller", "name": "Solceller", "icon": "☀️", "built": True},
    {"id": "spabad", "name": "Spabad", "icon": "🛁", "built": True},
    {"id": "temperaturer", "name": "Temperaturer", "icon": "🌡️", "built": True},
    {"id": "prognos", "name": "Prognos", "icon": "📅", "built": True},
    {"id": "historik", "name": "Historik", "icon": "📈", "built": True},
    {"id": "installningar", "name": "Inställningar", "icon": "⚙️", "built": True},
    {"id": "aviseringar", "name": "Aviseringar", "icon": "🔔", "built": True},
    {"id": "system", "name": "System", "icon": "🛠️", "built": True},
]

app = FastAPI(title="EnergyWizard Webdashboard")


@app.on_event("startup")
async def _print_welcome():
    """Skriver ut adressen i docker-loggarna direkt vid start, samma mönster som
    ha-gateway/print-url.sh - annars är README den ENDA platsen en ny användare kan
    hitta adressen, och det kräver att man redan vet att man ska leta där. Kan inte
    räkna ut värdens egen LAN-IP pålitligt inifrån en bridge-nätverkad container
    (containerns egen IP är inte samma sak, skulle bli missvisande) - ärligt
    generiskt istället för en gissning som ser exakt ut men kan vara fel."""
    print("")
    print("=" * 66)
    print("🔆  EnergyWizard webdashboard är igång!")
    print("    Besök http://<din-servers-lokala-IP>:8503 i webbläsaren")
    print("    (hittar du inte IP:n? \"ip addr\" på servern, eller din routers DHCP-lista)")
    print("=" * 66)
    print("")


@app.middleware("http")
async def guard(request: Request, call_next):
    err = AUTH.guard_response(request)
    if err is not None:
        return err
    resp = await call_next(request)
    resp.headers.update(webauth.SECURITY_HEADERS)
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/static/") or request.url.path == "/":
        # Statiska filer (JS/CSS/HTML) ska alltid hämtas om - annars ser man kvarbliven
        # gammal kod efter en uppdatering tills man själv tömmer webbläsarens cache
        # (upptäckt 2026-10-31 - samma fix som ewapp redan hade för sina statiska filer).
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.post("/api/login")
async def login(request: Request):
    return await AUTH.login(request)


@app.post("/api/logout")
async def logout():
    return AUTH.logout()


# ---------- Startguiden: lösenord, Home Assistant, prylar (allt i webben) ----------
import ew_settings  # noqa: E402
import homeassistant  # noqa: E402


def _devices_chosen() -> bool:
    # Filen som den står (inte med standardvärden ifyllda): något mer än house_id?
    try:
        import yaml
        with open(HOUSE_CONFIG_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return False
    return isinstance(cfg, dict) and any(k != "house_id" and v for k, v in cfg.items())


@app.get("/api/setup/status")
async def api_setup_status(request: Request):
    """Vad som saknas. Öppen före inloggning, men avslöjar inget utöver ja/nej."""
    role, _ = AUTH.session(request)
    has_pw = bool(webauth.owner_password())
    out = {"needs_password": not has_pw, "supervisor": bool(homeassistant.SUPERVISOR_TOKEN),
           "ha_ok": homeassistant.configured(), "devices_chosen": _devices_chosen()}
    if role == "owner":
        out.update(ha_url=homeassistant.HA_URL or "", ha_from_env=bool(homeassistant._ENV_URL or homeassistant.HA_IP),
                   can_save_config=_config_writable())
    return out


@app.post("/api/setup/password")
async def api_setup_password(request: Request):
    """Första lösenordet. Går bara när inget lösenord finns; loggar in direkt."""
    if webauth.owner_password():
        return JSONResponse({"detail": "Lösenordet är redan valt. Logga in."}, status_code=409)
    body = await request.json()
    pw = str(body.get("password", ""))
    if len(pw) < 8:
        return JSONResponse({"detail": "Välj minst 8 tecken."}, status_code=400)
    ew_settings.update(dashboard_password=pw)
    return await AUTH.login(request)


@app.post("/api/setup/ha")
async def api_setup_ha(request: Request):
    """Testar och sparar adress + token till Home Assistant (bara ägaren)."""
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"detail": "Bara ägaren kan ändra anslutningen"}, status_code=403)
    if homeassistant.SUPERVISOR_TOKEN:
        return {"ok": True, "message": "Körs som Home Assistant-tillägg: anslutningen sköts av Home Assistant."}
    if homeassistant._ENV_URL or homeassistant.HA_IP:
        return JSONResponse({"detail": "Anslutningen styrs av HA_URL/HA_IP i .env och ändras där."}, status_code=409)
    body = await request.json()
    url, token = str(body.get("url", "")).strip(), str(body.get("token", "")).strip()
    if not url or not token:
        return JSONResponse({"detail": "Fyll i både adress och token."}, status_code=400)
    ok, msg = homeassistant.test_connection(url, token)
    if not ok:
        return JSONResponse({"detail": msg}, status_code=400)
    ew_settings.update(ha_url=homeassistant.normalize_ha_url(url), ha_token=token)
    homeassistant.reconfigure()
    return {"ok": True, "message": msg}


# ---------- Batteriets planering: stil och försäljning (valt i webben) ----------
@app.get("/api/battery-plan-settings")
async def api_battery_plan_settings():
    import battery_plan
    st = ew_settings.load()
    try:
        bs = house_config.battery_settings(house_config.load_house_config(HOUSE_CONFIG_FILE))
    except Exception:
        bs = {}
    return {"style": st.get("battery_plan_style") or bs.get("plan_style") or battery_plan.DEFAULT_STYLE,
            "allow_export": st.get("battery_allow_export", bs.get("allow_export", True)) is not False,
            "styles": list(battery_plan.PLAN_STYLES), "has_battery": bs.get("control", "av") != "av"}


@app.post("/api/battery-plan-settings")
async def api_battery_plan_settings_save(request: Request):
    import battery_plan
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"detail": "Bara ägaren kan ändra batteriets planering"}, status_code=403)
    body = await request.json()
    upd = {}
    if "style" in body:
        if body["style"] not in battery_plan.PLAN_STYLES:
            return JSONResponse({"detail": "Okänd stil"}, status_code=400)
        upd["battery_plan_style"] = body["style"]
    if "allow_export" in body:
        upd["battery_allow_export"] = bool(body["allow_export"])
    ew_settings.update(**upd)
    return {"ok": True, **upd}


@app.get("/api/mqtt-settings")
async def mqtt_get(request: Request):
    """Inställningar -> Home Assistant via MQTT (smartbox/mqtt_bridge.py). Lösenordet skickas aldrig tillbaka."""
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren"}, status_code=403)
    st = ew_settings.load()
    from urllib.parse import urlparse
    guess = urlparse(homeassistant._BASE).hostname or ""
    return {"ok": True, "host": st.get("mqtt_host") or "", "port": st.get("mqtt_port") or 1883, "user": st.get("mqtt_user") or "",
            "has_password": bool(st.get("mqtt_password")), "status": st.get("mqtt_status"), "suggested_host": guess}


@app.post("/api/mqtt-settings")
async def mqtt_set(request: Request):
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren kan ändra MQTT"}, status_code=403)
    b = await request.json()
    host = str(b.get("host") or "").strip()
    if host and not re.fullmatch(r"[A-Za-z0-9.\-:\[\]]{1,253}", host):
        return JSONResponse({"error": "Ogiltig adress"}, status_code=400)
    try:
        port = int(b.get("port") or 1883)
    except ValueError:
        return JSONResponse({"error": "Ogiltig port"}, status_code=400)
    upd = {"mqtt_host": host or None, "mqtt_port": port if host else None, "mqtt_user": (str(b.get("user") or "").strip() or None) if host else None,
           "mqtt_status": None}
    if not host:
        upd["mqtt_password"] = None
    elif b.get("password"):                        # tomt fält = behåll det sparade lösenordet
        upd["mqtt_password"] = str(b["password"])
    ew_settings.update(**upd)
    return {"ok": True}


@app.get("/api/shadow")
async def shadow_get():
    """Skuggläget (smartbox/shadow.py): på/av och vad EnergyWizard hade gjort de senaste dygnen."""
    import shadow
    try:
        with ENGINE.connect() as c:
            rows = c.execute(text("SELECT ts AT TIME ZONE 'Europe/Stockholm', what, detail FROM shadow_actions "
                                  "ORDER BY ts DESC LIMIT 60")).fetchall()
    except Exception:          # tabellen finns först när något loggats
        rows = []
    return {"ok": True, "active": shadow.active(), "forced_by_env": os.environ.get("SHADOW_MODE", "").lower() in ("1", "true", "ja", "yes"),
            "actions": [{"ts": str(r[0])[:16], "what": r[1], "detail": r[2]} for r in rows]}


@app.post("/api/shadow")
async def shadow_set(request: Request):
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren kan slå på eller av skuggläget"}, status_code=403)
    ew_settings.update(shadow_mode=bool((await request.json()).get("active")) or None)
    return {"ok": True}


_PRICE_KEYS = ("price_country", "price_area", "price_vat_pct", "price_buy_extra", "price_sell_extra", "price_sell_vat",
               "price_currency", "price_ha_entity", "price_tou_extra", "price_tou_hours", "price_tou_months", "price_tou_weekdays")


@app.get("/api/price-settings")
async def price_settings_get():
    """Inställningar -> Elpris och avgifter: gällande värden, länderna och ett räkneexempel."""
    import nordpool
    c = nordpool.cost_settings()
    c = {**c, "tou_hours": f"{c['tou_hours'][0]}-{c['tou_hours'][1]}", "tou_months": f"{c['tou_months'][0]}-{c['tou_months'][1]}"}
    return {"ok": True, **c, "source": nordpool.price_source(), "ha_entity": ew_settings.get("price_ha_entity") or "sensor.nordpool",
            "countries": {k: {"name": v["name"], "vat_pct": v["vat_pct"], "currency": v["currency"], "areas": v["areas"]}
                          for k, v in nordpool.COUNTRIES.items()},
            # Räkneexempel för spotpris 1,00 exkl. moms: samma formel som nordpool.full_buy_cost/full_sell_income
            "example": {"spot": 1.0, "buy": round(1.0 * (1 + c["vat_pct"] / 100) + c["buy_extra"], 4),
                        "sell": round((1 + c["vat_pct"] / 100 if c["sell_vat"] else 1.0) + c["sell_extra"], 4)}}


@app.get("/api/price-entities")
async def price_entities():
    """Prissensorer i Home Assistant med dygnets priser (Nord Pool, ENTSO-e, EPEX Spot, Energi Data Service, Octopus,
    Amber ...), för valet av priskälla i installationen och under Inställningar."""
    import nordpool
    try:
        r = requests.get(f"{homeassistant._BASE}/states", headers=homeassistant._HEADERS, timeout=20, verify=homeassistant._VERIFY)
        r.raise_for_status()
        states = r.json()
    except Exception as e:
        return {"ok": False, "error": f"Kunde inte läsa Home Assistant: {e}", "entities": []}
    out = []
    for st in states:
        e = st.get("entity_id", "")
        if not (e.startswith("sensor.") or e.startswith("event.")) or e.endswith("_next_day_rates"):
            continue
        kind = nordpool.recognize_price_entity(st)
        if kind:
            a = st.get("attributes") or {}
            n = len(nordpool.parse_price_attributes(a, a.get("unit_of_measurement", "")))
            out.append({"entity_id": e, "name": a.get("friendly_name") or e, "integration": kind,
                        "unit": a.get("unit_of_measurement") or "", "points": n})
    selected = ew_settings.get("price_ha_entity") or ""
    if not selected and nordpool.price_source() == "ha_nordpool":       # vald via miljön (PRICE_SOURCE/NORDPOOL_HA_ENTITY)
        selected = os.environ.get("NORDPOOL_HA_ENTITY", "sensor.nordpool")
    return {"ok": True, "entities": out, "selected": selected,
            "includes_vat": nordpool.prices_include_vat() if ew_settings.get("price_ha_entity") else
            str(ew_settings.get("price_includes_vat", True)).lower() not in ("0", "false")}


# ---- Aviseringar till vilken telefon (issue #123: förut den första mobile_app_* i HA - kunde vara fel persons) ----
@app.get("/api/notify-target")
async def notify_target_get(request: Request):
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren"}, status_code=403)
    try:
        r = requests.get(f"{homeassistant._BASE}/services", headers=homeassistant._HEADERS, timeout=15, verify=homeassistant._VERIFY)
        r.raise_for_status()
        svcs = next((d.get("services") or {} for d in r.json() if d.get("domain") == "notify"), {})
    except Exception as e:
        return {"ok": False, "error": f"Kunde inte läsa Home Assistant: {e}"}
    phones = sorted(n for n in svcs if n.startswith("mobile_app_"))
    return {"ok": True, "phones": phones, "selected": ew_settings.get("notify_target") or "",
            "env": os.environ.get("NOTIFY_TARGET", "")}


@app.post("/api/notify-target")
async def notify_target_set(request: Request):
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren kan välja telefon"}, status_code=403)
    t = str((await request.json()).get("target") or "").strip()
    if t and not re.fullmatch(r"mobile_app_[a-z0-9_]+", t):
        return JSONResponse({"error": "Ogiltig telefon"}, status_code=400)
    ew_settings.update(notify_target=t or None)
    return {"ok": True, "message": "Sparat - aviseringarna går till " + (t or "den första telefonen i Home Assistant")}


# ---- Givare (2026-11-04): innegivare, utegivare och fukt väljs av användaren - inget är hårdkodat --------------------
_INDOOR_HINT = re.compile(r"inne|inomhus|vardagsrum|sovrum|kök|kok|hall|kontor|living|bedroom|kitchen|room|rum|indoor|matter|zigbee|aqara|timmerflotte", re.I)
_OUTDOOR_HINT = re.compile(r"\bute\b|utomhus|outdoor|outside|ute_|_ute", re.I)
_NOT_ROOM = re.compile(r"cpu|processor|battery|batteri|tesla|leaf|car|bil|inverter|växelriktare|framledning|retur|forward|return|"
                       r"brine|köldbärare|varmvatten|hot ?water|dhw|spa|pool|bad|tank|frys|kyl|freezer|fridge|motor|chip|disk|nas|router|"
                       r"compressor|kompressor|wled|esp32 internal|board", re.I)


@app.get("/api/sensors")
async def sensors_get(request: Request):
    """Temperatur- och fuktgivare i Home Assistant med förslag (innegivare, utegivare), plus nuvarande val."""
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren"}, status_code=403)
    try:
        r = requests.get(f"{homeassistant._BASE}/states", headers=homeassistant._HEADERS, timeout=20, verify=homeassistant._VERIFY)
        r.raise_for_status()
        states = r.json()
    except Exception as e:
        return {"ok": False, "error": f"Kunde inte läsa Home Assistant: {e}"}
    temps, hums = [], []
    for st in states:
        e, a = st.get("entity_id", ""), st.get("attributes") or {}
        if not e.startswith("sensor."):
            continue
        name = a.get("friendly_name") or e
        try:
            val = float(st.get("state"))
        except (TypeError, ValueError):
            val = None
        dc, unit = a.get("device_class"), a.get("unit_of_measurement")
        text_ = f"{e} {name}"
        if dc == "temperature" or unit in ("°C", "°F"):
            room = bool(_INDOOR_HINT.search(text_)) and not _NOT_ROOM.search(text_) and not _OUTDOOR_HINT.search(text_)
            temps.append({"entity": e, "name": name, "value": val, "suggest_indoor": room and val is not None and 10 <= val <= 30,
                          "suggest_outdoor": bool(_OUTDOOR_HINT.search(text_)) and not _NOT_ROOM.search(text_)})
        elif dc == "humidity" or (unit == "%" and re.search(r"humid|fukt", text_, re.I)):
            hums.append({"entity": e, "name": name, "value": val})
    temps.sort(key=lambda x: (not x["suggest_indoor"], not x["suggest_outdoor"], x["name"].lower()))
    hums.sort(key=lambda x: x["name"].lower())
    return {"ok": True, "temperatures": temps, "humidities": hums, "selected": homeassistant.sensor_config()}


@app.post("/api/sensors")
async def sensors_set(request: Request):
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren kan ändra givare"}, status_code=403)
    body = await request.json()
    ent_ok = lambda x: isinstance(x, str) and re.fullmatch(r"sensor\.[a-z0-9_]+", x)
    old = {s.get("entity"): s for s in (homeassistant.sensor_config().get("indoor") or []) if isinstance(s, dict)}
    used, indoor = set(), []
    for item in (body.get("indoor") or [])[:12]:
        e = item.get("entity")
        if not ent_ok(e):
            return JSONResponse({"error": f"Ogiltig givare: {e}"}, status_code=400)
        prev = old.get(e, {})
        key = prev.get("key")
        if not key or key in used:                       # behåll nyckeln (loggkolumnen) för givare som redan var valda
            n = 1
            while f"in_{n}" in used or any(s.get("key") == f"in_{n}" for s in old.values() if s.get("entity") != e):
                n += 1
            key = f"in_{n}"
        used.add(key)
        s = {"key": key, "entity": e, "label": str(item.get("label") or prev.get("label") or e)[:60]}
        if ent_ok(item.get("humidity")):
            s["humidity"] = item["humidity"]
        try:
            off = float(str(item.get("offset") or 0).replace(",", "."))
        except ValueError:
            return JSONResponse({"error": "Ogiltig korrigering"}, status_code=400)
        if not -5 <= off <= 5:
            return JSONResponse({"error": "Korrigeringen ska vara mellan -5 och 5 °C"}, status_code=400)
        if off:
            s["offset"] = off
        if prev.get("esphome_ip"):
            s["esphome_ip"] = prev["esphome_ip"]
        indoor.append(s)
    outdoor = body.get("outdoor")
    if outdoor and not ent_ok(outdoor):
        return JSONResponse({"error": "Ogiltig utegivare"}, status_code=400)
    ew_settings.update(sensors={"indoor": indoor, **({"outdoor": outdoor} if outdoor else {})})
    return {"ok": True, "message": "Sparat - motorn använder givarna från nästa varv."}


@app.post("/api/price-source")
async def price_source_set(request: Request):
    """Väljer prissensor i HA (tom = standard: elprisetjustnu.se i Sverige) och om priset i den är inklusive moms."""
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren kan ändra priskällan"}, status_code=403)
    body = await request.json()
    ent = str(body.get("ha_entity") or "").strip()
    if ent and not re.fullmatch(r"(sensor|event)\.[a-z0-9_]+", ent):
        return JSONResponse({"error": "Ogiltig entitet"}, status_code=400)
    ew_settings.update(price_ha_entity=ent or None, price_includes_vat=bool(body.get("includes_vat", True)))
    return {"ok": True}


@app.post("/api/price-settings")
async def price_settings_set(request: Request):
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"error": "Bara ägaren kan ändra elpris och avgifter"}, status_code=403)
    import nordpool
    body = await request.json()
    upd = {}
    country = str(body.get("country") or "SE").upper()
    if country not in nordpool.COUNTRIES:
        return JSONResponse({"error": "Okänt land"}, status_code=400)
    upd["price_country"] = country
    area = str(body.get("area") or "").upper()
    upd["price_area"] = area if area in nordpool.COUNTRIES[country]["areas"] else nordpool.COUNTRIES[country]["areas"][0]
    for key, field, lo, hi in (("price_vat_pct", "vat_pct", 0, 50), ("price_buy_extra", "buy_extra", -5, 50), ("price_sell_extra", "sell_extra", -5, 50)):
        v = body.get(field)
        if v in (None, ""):
            upd[key] = None                     # tomt = landets standard
            continue
        try:
            v = float(str(v).replace(",", "."))
        except ValueError:
            return JSONResponse({"error": f"Ogiltigt värde: {field}"}, status_code=400)
        if not lo <= v <= hi:
            return JSONResponse({"error": f"{field} utanför rimligt intervall"}, status_code=400)
        upd[key] = v
    upd["price_sell_vat"] = bool(body.get("sell_vat"))
    # Tidstariff (issue #98): tillägg under höglasttid. Tomt/0 = ingen.
    if "tou_extra" in body:
        v = body.get("tou_extra")
        try:
            v = 0.0 if v in (None, "") else float(str(v).replace(",", "."))
        except ValueError:
            return JSONResponse({"error": "Ogiltigt värde: tou_extra"}, status_code=400)
        if not 0 <= v <= 20:
            return JSONResponse({"error": "tou_extra utanför rimligt intervall"}, status_code=400)
        upd["price_tou_extra"] = v or None
        for key, field, lo, hi in (("price_tou_hours", "tou_hours", 0, 24), ("price_tou_months", "tou_months", 1, 12)):
            raw = str(body.get(field) or "").replace("–", "-").replace(" ", "")
            m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", raw)
            if not m or not all(lo <= int(x) <= hi for x in m.groups()):
                return JSONResponse({"error": f"Ogiltigt intervall: {field} (t.ex. {'6-22' if field == 'tou_hours' else '11-3'})"}, status_code=400)
            upd[key] = f"{int(m.group(1))}-{int(m.group(2))}"
        upd["price_tou_weekdays"] = bool(body.get("tou_weekdays", True))
    if "ha_entity" in body:
        ent = str(body.get("ha_entity") or "").strip()
        upd["price_ha_entity"] = ent if re.fullmatch(r"(sensor|event)\.[a-z0-9_]+", ent) else None
    ew_settings.update(**upd)
    return {"ok": True}


@app.get("/api/me")
async def me(request: Request):
    role, user = AUTH.session(request)
    pages = [p for p in PAGES if p["built"]]
    if TELEMETRY_STATS_URL and role == "owner":       # bara utvecklarens egen server, bara ägaren
        pages.insert(len(pages) - 1, INSTALLS_PAGE)
    return {"role": role, "user": user, "pages": pages}


@app.get("/api/ping")
async def ping():
    """Bevisar att databaskopplingen fungerar - samma ENGINE-mönster som ewapp/smartbox."""
    with ENGINE.connect() as c:
        c.exec_driver_sql("SELECT 1")
    return {"ok": True, "ts": int(time.time())}


def _n(v, default=None):
    """None/NaN-säker talkonvertering - sensor_log har gott om NULL/NaN."""
    try:
        f = float(v)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _is_high_load_time(dt):
    """Samma regel som smartbox/settings.py:is_high_load_time - inlinad här hellre än att
    dra in hela settings.py:s tunga importkedja (pandas/psycopg_pool/...) för en rad logik."""
    return dt.month in (11, 12, 1, 2, 3) and dt.weekday() <= 4 and 7 <= dt.hour < 20


def _temp_target(conn, mode: str) -> float:
    row = conn.execute(text("SELECT temp_cheap, temp_expensive FROM system_settings WHERE id = 1")).fetchone()
    cheap, expensive = (row[0], row[1]) if row else (None, None)
    return float(cheap if cheap is not None else 22.0) if mode == "CHEAP" else float(expensive if expensive is not None else 20.0)


def _heat_battery(row) -> dict | None:
    """Varmvattenberedaren som ett termiskt batteri: laddnivå = var water_temp ligger
    mellan husets EGNA aktuella golv (water_start_temp) och tak (water_setpoint) -
    samma gränser gpm.py Prio 4.5 redan styr mot, inte hårdkodade konstanter."""
    water_temp = _n(row.get("water_temp"))
    floor = _n(row.get("water_start_temp"))
    ceiling = _n(row.get("water_setpoint"))
    if water_temp is None or floor is None or ceiling is None or ceiling <= floor:
        return None
    charge_pct = max(0.0, min(100.0, (water_temp - floor) / (ceiling - floor) * 100.0))
    compressor_running = bool(row.get("compressor_running"))
    if compressor_running:
        status = "Laddar"
    elif charge_pct >= 95:
        status = "Vilar"
    else:
        status = "Tömmer"
    return {"charge_pct": round(charge_pct, 0), "status": status, "water_temp": water_temp, "floor": floor, "ceiling": ceiling}


@app.get("/api/overview")
async def overview(request: Request):
    """Fas B, sida 1 (Översikt): beslutsbanner + de åtta nyckeltalen, portade från
    smartdashboard/app.py:s page_overview() (samma SQL, samma fält - bara flyttat
    bakom ett JSON-API istället för Streamlit-rendering)."""
    with ENGINE.connect() as c:
        row = c.execute(text(
            "SELECT *, timestamp AT TIME ZONE 'Europe/Stockholm' AS sthlm_time FROM sensor_log ORDER BY timestamp DESC LIMIT 1"
        )).mappings().first()
        price_hist = c.execute(text(
            "SELECT time_start, sek_per_kwh FROM elpriser WHERE time_start >= now() - interval '24 hours' ORDER BY time_start"
        )).fetchall()
        if row is None:
            return {"ok": False, "error": "Ingen data i sensor_log än"}
        mode = str(row.get("active_mode") or "").upper()
        target_room = _temp_target(c, mode)
        ov = _overrides(c, ("heat", "hotwater"))
        cfg = _settings_row(c, ("temp_cheap", "temp_expensive"))
    is_high_load = _is_high_load_time(row["sthlm_time"])

    return {
        "ok": True,
        "mode": mode,
        "heat_mode": ov.get("heat", "auto"), "hotwater_mode": ov.get("hotwater", "auto"),
        "temp_cheap": _n(cfg.get("temp_cheap")), "temp_expensive": _n(cfg.get("temp_expensive")),
        "decision": row.get("active_decision") or "Utvärderar…",
        "decision_items": _json_list(row.get("decision_summary")),     # vad görs nu och varför, per enhet
        "price": _n(row.get("price")),
        "indoor_temp": _n(row.get("indoor_temp")),
        "indoor_target": target_room,
        "indoor_humidity": _n(row.get("indoor_humidity")),
        "outdoor_temp": _n(row.get("outdoor_temp")),
        "net_power_w": _n(row.get("net_power")),
        "pv_power_w": _n(row.get("pv_power_w")),
        "water_temp": _n(row.get("water_temp")),
        # Båda laddboxarna (ev_* = Nissans, ev_carport_* = Teslas) - förut bara den ena, så rutan visade
        # 0 kW medan Teslan laddade.
        "ev_power_kw": (None if row.get("ev_power_kw") is None and row.get("ev_carport_power_kw") is None
                        else round((_n(row.get("ev_power_kw")) or 0) + (_n(row.get("ev_carport_power_kw")) or 0), 2)),
        "is_high_load": is_high_load,
        "sthlm_time": str(row["sthlm_time"]),
        "price_24h": [{"t": r[0].isoformat(), "p": float(r[1])} for r in price_hist],
        "heat_battery": _heat_battery(row),
    }


@app.get("/api/updates")
async def updates(request: Request, force: bool = False):
    """System-sidan: vilka containrar på hela NUC:en (inte bara EnergyWizard) har en
    nyare image enligt Watchtower. Cachas 10 min - force=1 kollar om direkt."""
    if not WATCHTOWER_TOKEN:          # ingen Watchtower här (HA-tillägget, de flesta installationer) - inget fel (#121)
        return {"ok": True, "configured": False, "addon": bool(homeassistant.SUPERVISOR_TOKEN)}
    now = time.time()
    if force or _wt_cache["data"] is None or now - _wt_cache["ts"] > WT_CACHE_TTL:
        try:
            r = requests.post(
                f"{WATCHTOWER_URL}/v1/check",
                headers={"Authorization": f"Bearer {WATCHTOWER_TOKEN}"},
                timeout=30,
            )
            r.raise_for_status()
            _wt_cache["data"] = r.json()
            _wt_cache["ts"] = now
        except requests.RequestException as e:
            if _wt_cache["data"] is None:
                return {"ok": False, "error": f"Kunde inte nå Watchtower: {e}"}
    containers = _wt_cache["data"].get("containers", [])
    pending = [c["name"] for c in containers if c.get("update_available")]
    return {
        "ok": True,
        "checked_at": _wt_cache["ts"],
        "total": len(containers),
        "pending": sorted(pending),
    }


@app.get("/api/installs")
async def installs(request: Request):
    """System-sidan: hur många som kör EnergyWizard och med vilken utrustning (från telemetrisamlaren)."""
    role, _ = AUTH.session(request)
    if not TELEMETRY_STATS_URL or role != "owner":
        return {"ok": False, "configured": False}
    try:
        import telemetry
        try:
            cfg = house_config.load_house_config(HOUSE_CONFIG_FILE)
        except Exception:
            cfg = {}
        me = telemetry.house_hash(cfg, create=False)      # samma som motorn skickar (installationens slumpade ID)
        r = requests.get(TELEMETRY_STATS_URL, timeout=10, headers={"X-Stats-Token": TELEMETRY_STATS_TOKEN}, params={"me": me})
        r.raise_for_status()
        return {"ok": True, "configured": True, **r.json()}
    except (requests.RequestException, ValueError) as e:
        return {"ok": False, "configured": True, "error": f"Kunde inte nå telemetrisamlaren: {e}"}


def _latest_row(c):
    """Senaste raden i sensor_log som dict - delad av alla de nya datasidorna nedan
    istället för att varje endpoint skriver om samma SELECT * ... LIMIT 1."""
    row = c.execute(text(
        "SELECT *, timestamp AT TIME ZONE 'Europe/Stockholm' AS sthlm_time FROM sensor_log ORDER BY timestamp DESC LIMIT 1"
    )).mappings().first()
    return dict(row) if row else None


def _json_list(raw):
    import json
    try:
        v = json.loads(raw) if raw else []
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def _overrides(c, keys):
    rows = c.execute(text("SELECT device, mode FROM overrides WHERE device = ANY(:k)"), {"k": list(keys)}).fetchall()
    return {r[0]: r[1] for r in rows}


def _settings_row(c, cols):
    row = c.execute(text(f"SELECT {', '.join(cols)} FROM system_settings WHERE id = 1")).mappings().first()
    return dict(row) if row else {}


def _price_24h(c):
    rows = c.execute(text(
        "SELECT time_start, sek_per_kwh FROM elpriser WHERE time_start >= now() - interval '24 hours' ORDER BY time_start"
    )).fetchall()
    return [{"t": r[0].isoformat(), "p": float(r[1])} for r in rows]


def _ewapp_cars() -> list:
    """Bilarna som mobilappen räknar fram ur installationen (house_config.yaml) och Home Assistant."""
    try:
        r = requests.get(f"{EWAPP_URL}/api/state", cookies={"ew": _ewapp_cookie()}, timeout=25)
        r.raise_for_status()
        return r.json().get("cars", []) or []
    except Exception as e:
        print(f"⚠️ Bilarna från mobilappen: {e}", flush=True)
        return []


@app.get("/api/car")
async def api_car():
    """Elbil-sidan: SoC/laddstatus för båda bilarna + dagens schema (ev_charging_schedule)
    och planerade laddningspass (ev_plan_slots, summeras bara - full passplan hör hemma
    i ewapp:s egen editor, inte duplicerad här)."""
    with ENGINE.connect() as c:
        row = _latest_row(c)
        if row is None:
            return {"ok": False, "error": "Ingen data i sensor_log än"}
        today_dow = time.localtime().tm_wday
        sched = c.execute(text(
            "SELECT car_id, target_time, target_soc, enabled FROM ev_charging_schedule WHERE day_of_week = :d"
        ), {"d": today_dow}).mappings().all()
        planned = c.execute(text(
            "SELECT car_id, SUM(kw) / 4.0 AS kwh FROM ev_plan_slots WHERE t_slot::date = CURRENT_DATE GROUP BY car_id"   # 15-min-slottar: kW × 0,25 h
        )).mappings().all()
        try:
            slots = c.execute(text("SELECT car_id, t_slot, kw, start_soc, end_soc FROM ev_plan_slots "
                                   "WHERE t_slot >= (now() AT TIME ZONE 'Europe/Stockholm') - interval '15 minutes' ORDER BY t_slot")).fetchall()
            plan_prices = c.execute(text("SELECT time_start, sek_per_kwh FROM elpriser WHERE time_start >= now() - interval '1 hour' "
                                         "AND time_start < now() + interval '36 hours' ORDER BY time_start")).fetchall()
        except Exception:
            c.rollback()
            slots, plan_prices = [], []
    planned_by_car = {p["car_id"]: _n(p["kwh"]) for p in planned}
    # Bilarna ur installationen, live från mobilappens /api/state (samma bilar och entiteter som där) - inga
    # inbyggda bilnamn eller loggkolumner per bil (issue #113: andra såg Emils Tesla/Nissan utan värden).
    cars = []
    for c in _ewapp_cars():
        cars.append({"id": c.get("key"), "name": c.get("name"), "soc": _n(c.get("soc")), "stale": bool(c.get("soc_stale")),
                     "power_kw": _n(c.get("power_kw")), "status": c.get("status"),
                     "climate_temp": _n(c.get("inside")), "climate_state": "heat_cool" if c.get("climate_on") else "off"})
    for car in cars:
        car["planned_kwh_today"] = planned_by_car.get(car["id"])
    schedule = [{"car_id": s["car_id"], "target_time": str(s["target_time"]) if s["target_time"] else None,
                 "target_soc": s["target_soc"], "enabled": s["enabled"]} for s in sched]
    return {"ok": True, "cars": cars, "session_kwh": _n(row.get("ev_session_kwh")),
            "current_a": _n(row.get("ev_current_a")), "dynamic_limit_a": _n(row.get("ev_dynamic_limit_a")),
            "current_target_limit": _n(row.get("current_target_limit")), "schedule_today": schedule,
            # Laddplanen per kvart (naiv svensk lokaltid i ev_plan_slots) + elpriset, för grafen
            "plan": [{"car": r[0], "t": r[1].isoformat(), "kw": _n(r[2]), "soc0": _n(r[3]), "soc1": _n(r[4])} for r in slots],
            "plan_prices": [{"t": t.astimezone(zoneinfo.ZoneInfo("Europe/Stockholm")).replace(tzinfo=None).isoformat(), "p": float(p)} for t, p in plan_prices if p is not None]}


@app.get("/api/solar")
async def api_solar():
    """Solceller-sidan: produktion, dagens energi, exportgräns och husbatteriet - allt
    redan loggat av smartbox i sensor_log varje cykel, ingen live HA-fråga behövs."""
    with ENGINE.connect() as c:
        row = _latest_row(c)
        if row is None:
            return {"ok": False, "error": "Ingen data i sensor_log än"}
        price_24h = _price_24h(c)
        ov = _overrides(c, ("solar_auto_export", "notify_solar_limit"))
        # Dagens produktion: växelriktarens egen räknare om den finns, annars uppmätt effekt minut för minut.
        pv_today = c.execute(text("SELECT sum(pv_power_w) / 60000.0 FROM sensor_log WHERE pv_power_w > 0 AND "
                                  "timestamp >= date_trunc('day', now() AT TIME ZONE 'Europe/Stockholm') AT TIME ZONE 'Europe/Stockholm'")).scalar()
    auto = str(ov.get("solar_auto_export", "true")).lower() != "false"
    price_now = _n(row.get("price"))
    return {"ok": True, "pv_power_w": _n(row.get("pv_power_w")),
            "solar_today_kwh": _n(row.get("solar_today_kwh")) if row.get("solar_today_kwh") is not None else _n(pv_today),
            "solar_forecast_w": _n(row.get("solar_forecast_w")), "solar_limit_pct": _n(row.get("solar_limit_pct")),
            "inverter_status": row.get("inverter_status"), "battery_soc": _n(row.get("battery_soc")),
            "battery_power_w": _n(row.get("battery_power_w")), "net_power_w": _n(row.get("net_power")),
            "price": _n(row.get("price")), "price_24h": price_24h,
            "auto_export": auto, "ai_limit": auto and price_now is not None and price_now < 0,
            "notify": ov.get("notify_solar_limit", "true") == "true"}


@app.get("/api/economy")
async def api_economy():
    """Ekonomi-sidan: dagens pris (min/medel/max) och en uppskattad kostnad hittills
    idag (ackumulerad förbrukning × dagens snittpris) - en grov uppskattning, inte en
    exakt timme-för-timme-kostnad, och tydligt märkt som sådan i gränssnittet."""
    with ENGINE.connect() as c:
        row = _latest_row(c)
        if row is None:
            return {"ok": False, "error": "Ingen data i sensor_log än"}
        today_prices = c.execute(text(
            "SELECT sek_per_kwh FROM elpriser WHERE time_start::date = CURRENT_DATE"
        )).fetchall()
        price_24h = _price_24h(c)
        import savings
        import nordpool
        from datetime import datetime
        import zoneinfo
        today = datetime.now(zoneinfo.ZoneInfo("Europe/Stockholm")).date().isoformat()
        money = savings.money_rows(c, days=40)
        timing = savings.daily_rows(c, days=40)
    prices = [float(r[0]) for r in today_prices if r[0] is not None]
    avg_price = sum(prices) / len(prices) if prices else None
    # Förut: accumulated_consumption_kwh × snittpris - fältet är alltid 0, så kortet visade 0,00 kr.
    return {"ok": True, "price": _n(row.get("price")), "price_min": min(prices) if prices else None,
            "price_avg": avg_price, "price_max": max(prices) if prices else None, "price_24h": price_24h,
            "symbol": nordpool.cost_settings()["symbol"], "money_days": money[-31:],
            "money": savings.money_periods(money, today), "timing": savings.summarize_periods(timing, today)}


@app.get("/api/savings")
async def api_savings():
    """Besparingskortet: per dag de senaste ~40 dygnen + Idag / 7 dagar / Månad. Samma formel
    som den publika sidan och HA-sensorn - se smartbox/savings.py."""
    import savings
    from datetime import datetime
    import zoneinfo
    today = datetime.now(zoneinfo.ZoneInfo("Europe/Stockholm")).date().isoformat()
    with ENGINE.connect() as c:
        rows = savings.daily_rows(c, days=40)
    return {"ok": True, "today": today, "days": rows[-31:], "periods": savings.summarize_periods(rows, today)}


@app.get("/api/plan")
async def api_plan():
    """Planen framåt i klartext: elbilens laddpass + värmepumpens grundläge enligt elpriset.
    Bygger ingen ny plan, beskriver bara motorns - se smartbox/plan_brief.py."""
    import nordpool
    import plan_brief
    from datetime import datetime
    import zoneinfo
    now = datetime.now(zoneinfo.ZoneInfo("Europe/Stockholm"))
    with ENGINE.connect() as c:
        prices = c.execute(text(
            "SELECT time_start, sek_per_kwh FROM elpriser "
            "WHERE time_start >= date_trunc('day', now() AT TIME ZONE 'Europe/Stockholm') AT TIME ZONE 'Europe/Stockholm' "
            "ORDER BY time_start")).fetchall()
        try:
            ev_rows = c.execute(text("SELECT car_id, t_slot, kw FROM ev_plan_slots")).fetchall()
        except Exception:
            c.rollback()
            ev_rows = []
        try:
            bat_rows = c.execute(text("SELECT t_slot, action, soc_pct, spot, battery_kw FROM battery_plan_slots "
                                      "WHERE t_slot >= now() - interval '15 minutes' ORDER BY t_slot")).fetchall()
        except Exception:      # tabellen skapas först när en batteriplan sparats
            c.rollback()
            bat_rows = []
        cheap_hours = _settings_row(c, ["cheap_hours_count"]).get("cheap_hours_count") or 8
        try:                       # bilarnas mål till planklockan: närmaste påslagna schema idag eller imorgon
            sched = c.execute(text("SELECT car_id, day_of_week, target_time, target_soc FROM ev_charging_schedule "
                                   "WHERE enabled")).fetchall()
        except Exception:
            c.rollback()
            sched = []
        mode_row = c.execute(text("SELECT active_mode FROM sensor_log WHERE active_mode IS NOT NULL "
                                  "ORDER BY timestamp DESC LIMIT 1")).fetchone()
        try:
            import solar_days
            sun = solar_days.load(c, now)
        except Exception:
            sun = None
    brief = plan_brief.build_brief(now, [(r[0], float(r[1])) for r in prices if r[1] is not None],
                                   [tuple(r) for r in ev_rows], nordpool.calculate_day_strategy,
                                   int(cheap_hours), mode_row[0] if mode_row else None, battery_rows=[tuple(r) for r in bat_rows])
    from datetime import timedelta
    clock_prices = [{"t": r[0].isoformat(), "spot": round(float(r[1]), 4), "total": round(nordpool.full_buy_cost(float(r[1]), r[0]), 4)}
                    for r in prices if r[1] is not None and now - timedelta(minutes=15) <= r[0] < now + timedelta(hours=24)]
    return {"ok": True, **brief, "solar_days": sun, "now": now.isoformat(), "prices": clock_prices,
            "car_goals": _with_plugged(_car_goals(sched, now))}


def _with_plugged(goals):
    """Lägger till om bilen är ansluten (evs[].entities.plugged_in i house_config): ett mål är bara en plan om
    kabeln sitter i. None = okänt (ingen sådan entitet)."""
    try:
        evs = {e.get("id"): e for e in (house_config.load_house_config(HOUSE_CONFIG_FILE).get("evs") or [])}
    except Exception:
        evs = {}
    for g in goals:
        ent = ((evs.get(g["car"]) or {}).get("entities") or {}).get("plugged_in")
        st = homeassistant._get_raw_state(ent) if ent else None
        g["plugged"] = None if st in (None, "unknown", "unavailable") else str(st).lower() in ("on", "true", "home", "1")
    return goals


def _car_goals(sched, now):
    """Nästa mål per bil ur laddschemat: {'car', 'at' (iso), 'soc'} - idag om tiden inte passerat, annars imorgon."""
    from datetime import datetime, timedelta
    goals = {}
    for car, dow, tt, soc in sched or []:
        for add in (0, 1):
            day = (now + timedelta(days=add)).date()
            if day.weekday() != dow or tt is None:
                continue
            at = datetime.combine(day, tt if not isinstance(tt, str) else datetime.strptime(tt[:5], "%H:%M").time(),
                                  tzinfo=now.tzinfo)
            if at > now and (car not in goals or at < datetime.fromisoformat(goals[car]["at"])):
                goals[car] = {"car": car, "at": at.isoformat(), "soc": None if soc is None else int(soc)}
    return sorted(goals.values(), key=lambda g: g["at"])


@app.get("/api/flow")
async def api_flow():
    """Översiktens levande bild: vad som drar/ger el just nu, bara det huset har (live_flow.py)."""
    import live_flow
    with ENGINE.connect() as c:
        row = _latest_row(c)
    if row is None:
        return {"ok": False, "error": "Ingen data i sensor_log än"}
    # Bilarna och spabadet ur installationen (bara det huset har). Laddboxarna loggas i installationens ordning:
    # första -> ev_power_kw, andra -> ev_carport_power_kw (smartbox/main.py).
    cars, has_spa = None, None
    try:
        hc = house_config.load_house_config(HOUSE_CONFIG_FILE)
        has_spa = bool((hc.get("spa") or {}).get("enabled"))
        order = list(house_config.build_physical_charger_drivers(hc))
        home = {c: p for p, c in house_config.build_default_car_per_charger(hc).items()}
        cols = ["ev_power_kw", "ev_carport_power_kw"]
        cars = []
        for ev in hc.get("evs") or []:
            cid = ev.get("id")
            if not cid:
                continue
            idx = order.index(home[cid]) if home.get(cid) in order else -1
            cars.append((cid, ev.get("name") or cid.capitalize(), cols[idx] if 0 <= idx < len(cols) else None))
    except Exception as e:
        print(f"⚠️ Översiktens bilar/spa ur installationen: {e}", flush=True)
    d = live_flow.nodes(row, _json_list(row.get("decision_summary")), cars=cars, has_spa=has_spa)
    return {"ok": True, "ts": str(row.get("sthlm_time"))[:16], **d}


@app.get("/api/timeline")
async def api_timeline():
    """Dygnet timme för timme: uppmätt 24 h bakåt + planerat framåt (timeline.py)."""
    import timeline
    with ENGINE.connect() as c:
        return timeline.load(c)


@app.get("/api/energyhistory")
async def api_energyhistory(range: str = "24h"):
    """Historik-sidan: energisummor Idag/7 dagar/30 dagar + effekt över tid + senaste värden
    (smartbox/energy_history.py, delad med mobilappen)."""
    import energy_history
    with ENGINE.connect() as c:
        return energy_history.history_payload(c, range)


@app.get("/api/consumption")
async def api_consumption():
    """Elförbrukning-sidan: fasströmmar/effekt just nu + senaste förklarade uppdelningen
    (load_breakdown - EV/pump/spa/oförklarat) och effektvaktens status."""
    with ENGINE.connect() as c:
        row = _latest_row(c)
        if row is None:
            return {"ok": False, "error": "Ingen data i sensor_log än"}
        lb = c.execute(text(
            "SELECT total_w, ev_w, pump_w, spa_w, unexplained_w FROM load_breakdown ORDER BY timestamp DESC LIMIT 1"
        )).mappings().first()
        cfg = _settings_row(c, ("peak_shaving_enabled", "power_limit_kw", "fuse_size_a"))
    # avg_w_l1..3 är (trots namnet) fasströmmar i ampere ur elmätaren - visas i A mot huvudsäkringen (#130)
    return {"ok": True, "fuse_size_a": _n(cfg.get("fuse_size_a")),
            "avg_w_l1": _n(row.get("avg_w_l1")), "avg_w_l2": _n(row.get("avg_w_l2")),
            "avg_w_l3": _n(row.get("avg_w_l3")), "avg_w_tot": _n(row.get("avg_w_tot")),
            "house_consumption_w": _n(row.get("house_consumption_w")), "power_oven_w": _n(row.get("power_oven_w")),
            "power_computer_w": _n(row.get("power_computer_w")), "peak_shaving_active": bool(row.get("peak_shaving_active")),
            "predicted_base_load_kw": _n(row.get("predicted_base_load_kw")),
            "peak_shaving_enabled": bool(cfg.get("peak_shaving_enabled")), "power_limit_kw": _n(cfg.get("power_limit_kw")),
            "breakdown": {k: _n(lb[k]) for k in ("total_w", "ev_w", "pump_w", "spa_w", "unexplained_w")} if lb else None}


@app.get("/api/spa")
async def api_spa():
    """Spabad-sidan: temperatur, mål, värmarstatus och signalstyrka (RF-kanal till
    styrenheten) - direkt ur sensor_log, samma fält gpm.py redan styr mot."""
    with ENGINE.connect() as c:
        row = _latest_row(c)
        if row is None:
            return {"ok": False, "error": "Ingen data i sensor_log än"}
        cfg = _settings_row(c, ("spa_force_heat", "spa_normal_temp", "spa_max_temp", "spa_low_temp",
                                "spa_schedule_enabled", "spa_target_datetime", "spa_target_temp"))
        ov = _overrides(c, ("spa_force_eco",))
        hist = c.execute(text("""SELECT date_trunc('hour', timestamp AT TIME ZONE 'Europe/Stockholm') h, avg(spa_temp), avg(spa_target),
                                        avg(spa_heater_running::int) FROM sensor_log WHERE timestamp > now() - interval '24 hours'
                                 GROUP BY 1 ORDER BY 1""")).fetchall()
    return {"ok": True, "temp": _n(row.get("spa_temp")), "target": _n(row.get("spa_target")),
            "heater_running": bool(row.get("spa_heater_running")), "power_w": _n(row.get("spa_power_w")),
            "signal_pct": _n(row.get("spa_signal_pct")), "rf_channel": _n(row.get("spa_rf_channel")),
            "force_heat": bool(cfg.get("spa_force_heat")), "eco": ov.get("spa_force_eco") == "on",
            "normal_temp": _n(cfg.get("spa_normal_temp")), "max_temp": _n(cfg.get("spa_max_temp")), "low_temp": _n(cfg.get("spa_low_temp")),
            "ready_enabled": bool(cfg.get("spa_schedule_enabled")),
            "ready_at": cfg["spa_target_datetime"].astimezone(zoneinfo.ZoneInfo("Europe/Stockholm")).strftime("%Y-%m-%dT%H:%M") if cfg.get("spa_target_datetime") else None,
            "ready_temp": _n(cfg.get("spa_target_temp")),
            "history": [{"t": h.isoformat(), "temp": _n(a), "target": _n(b), "heating": _n(hr)} for h, a, b, hr in hist]}


ROOMS = [("temp_vardagsrum", "Vardagsrum"), ("temp_masterbedroom", "Sovrum"), ("temp_barnrum_nere", "Barnrum nere"),
         ("temp_cesars_rum", "Cesars rum"), ("temp_isacs_rum", "Isacs rum"), ("temp_utbyggnad", "Utbyggnad"),
         ("temp_tvattstuga", "Tvättstuga"), ("temp_friggebod", "Friggebod"), ("temp_garage", "Garage"),
         ("temp_matter_1", "Sensor Matter 1"), ("temp_matter_2", "Sensor Matter 2"), ("temp_matter_3", "Sensor Matter 3"),
         ("temp_esp", "ESP-sensor")]


@app.get("/api/temperatures")
async def api_temperatures():
    """Temperaturer-sidan: samma rumslista som ewapp:s /api/rooms (ROOMS ovan är en
    medveten kopia, inte en delad import - webdashboard har ingen HA-koppling att
    dela, bara sensor_log)."""
    with ENGINE.connect() as c:
        row = _latest_row(c)
    if row is None:
        return {"ok": False, "error": "Ingen data i sensor_log än"}
    rooms = [{"name": n, "temp": _n(row.get(col))} for col, n in ROOMS]
    # De valda innegivarna (Inställningar -> Givare), live ur Home Assistant (issue #128: utan Emils rumskolumner syntes
    # inga rum alls)
    try:
        chosen = homeassistant.indoor_sensors()
        if chosen:
            homeassistant.update_states()
            seen = {r["name"] for r in rooms if r["temp"] is not None}
            for sn in chosen:
                if sn.get("entity") and sn["label"] not in seen:
                    rooms.append({"name": sn["label"], "temp": _n(homeassistant._get_numeric_state(sn["entity"]))})
    except Exception as e:
        print(f"⚠️ Givarna till Temperaturer-sidan: {e}", flush=True)
    return {"ok": True, "indoor_temp": _n(row.get("indoor_temp")), "outdoor_temp": _n(row.get("outdoor_temp")),
            "indoor_humidity": _n(row.get("indoor_humidity")), "rooms": [r for r in rooms if r["temp"] is not None],
            "vent_supply_temp": _n(row.get("vent_supply_temp")), "vent_exhaust_temp": _n(row.get("vent_exhaust_temp")),
            "vent_setpoint_c": _n(row.get("vent_setpoint_c"))}


@app.get("/api/forecast")
async def api_forecast():
    """Prognos-sidan: kommande väder (weather_forecast) och kommande elpriser (elpriser) -
    samma tabeller gpm.py redan planerar mot, bara en vy på dem."""
    with ENGINE.connect() as c:
        weather = c.execute(text(
            "SELECT timestamp, temp, cloud_cover, wind_speed, rain_probability, thunder_probability "
            "FROM weather_forecast WHERE timestamp >= now() ORDER BY timestamp LIMIT 48"
        )).mappings().all()
        prices = c.execute(text(
            "SELECT time_start, sek_per_kwh FROM elpriser WHERE time_start >= now() ORDER BY time_start LIMIT 48"
        )).fetchall()
    return {"ok": True,
            "weather": [{"t": w["timestamp"].isoformat(), "temp": _n(w["temp"]), "cloud_cover": _n(w["cloud_cover"]),
                         "wind_speed": _n(w["wind_speed"]), "rain_probability": _n(w["rain_probability"]),
                         "thunder_probability": _n(w["thunder_probability"])} for w in weather],
            "prices": [{"t": r[0].isoformat(), "p": float(r[1])} for r in prices]}


@app.get("/api/historylog")
async def api_historylog():
    """Historik-sidan: ew_log (familjelogg + systemhändelser) - de senaste 80 posterna,
    nyast först."""
    with ENGINE.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS ew_log (id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ DEFAULT NOW(), usr TEXT, txt TEXT)"))
        rows = c.execute(text("SELECT ts, usr, txt FROM ew_log ORDER BY ts DESC LIMIT 80")).fetchall()
    return {"ok": True, "entries": [{"ts": r[0].isoformat(), "user": r[1], "text": r[2]} for r in rows]}


NOTIFY_LABELS = {
    "notify_spa_boost": "Spabadet värmer extra (boost)", "notify_spa_reconnect": "Spabadet tappade kontakten och är tillbaka",
    "notify_ev_full": "Elbilen är fulladdad", "notify_price_tip": "Pristips (ovanligt billig/dyr timme)",
    "notify_high_low": "Höglast/baslast byter", "notify_peak_shaving": "Effektvakten griper in",
    "notify_pump_alarm": "Värmepumpen larmar", "notify_pump_mode": "Värmepumpen byter läge",
    "notify_solar_error": "Solcellsväxelriktaren svarar inte", "notify_solar_limit": "Solexporten begränsas/släpps",
}


@app.get("/api/notifications")
async def api_notifications():
    """Aviseringar-sidan: nuvarande på/av-läge för varje aviseringstyp (overrides-
    tabellen, delad med ewapp - samma device/mode-par ewapp:s /api/energy-action:notify
    redan skriver till, bara en läsvy här)."""
    with ENGINE.connect() as c:
        rows = c.execute(text("SELECT device, mode FROM overrides WHERE device LIKE 'notify_%'")).fetchall()
    items = [{"key": r[0], "label": NOTIFY_LABELS.get(r[0], r[0]), "on": str(r[1]).lower() == "true"} for r in rows]
    items.sort(key=lambda i: i["label"])
    return {"ok": True, "items": items}


@app.post("/api/notifications/{key}")
async def set_notification(key: str, request: Request):
    """Växlar en aviseringstyp - samma overrides-tabell/semantik som ewapp:s notify-
    inställningar, så en ändring här syns direkt i ewapp också (och tvärtom)."""
    if key not in NOTIFY_LABELS:
        return JSONResponse({"ok": False, "error": "Okänd aviseringstyp"}, status_code=404)
    v = (await request.json()).get("value")
    with ENGINE.begin() as c:
        c.execute(text(
            "INSERT INTO overrides (device, mode) VALUES (:d, :m) ON CONFLICT (device) DO UPDATE SET mode = :m, updated_at = now()"
        ), {"d": key, "m": "true" if v else "false"})
    return {"ok": True}


@app.post("/api/car/{car}/action")
async def proxy_car_action(car: str, request: Request):
    """Elbil-sidan: start/max/stop/auto-laddning + värm/stoppa klimatet - ewapp:s egen
    car_command()/heat_on/heat_off, bara anropad härifrån också."""
    if not re.fullmatch(r"[a-z0-9_]{1,40}", car or ""):
        return JSONResponse({"detail": "Okänd bil"}, status_code=404)
    body = await request.json()
    if body.get("kind") not in ("start", "max", "set", "stop", "auto", "heat_on", "heat_off"):
        return JSONResponse({"detail": "Okänd åtgärd"}, status_code=400)
    return await _ewapp_proxy(f"/api/car/{car}/action", body)


@app.post("/api/home-action/{what}")
async def proxy_home_action(what: str, request: Request):
    """Spabad-sidan: spa_heat/spa_auto/spa_eco, Värmepump-sidan: heat/hotwater - ewapp:s
    /api/home/{what}. Eget pathnamn (inte /api/home/{what}) så det inte krockar med en
    egen framtida webdashboard-endpoint under /api/home."""
    if what not in ("heat", "hotwater", "spa_heat", "spa_auto", "spa_eco", "spa_ready"):
        return JSONResponse({"detail": "Okänd åtgärd"}, status_code=404)
    body = await request.json()
    return await _ewapp_proxy(f"/api/home/{what}", body)


@app.post("/api/energy-action/{what}")
async def proxy_energy_action(what: str, request: Request):
    """Solceller-sidan: manuell exportgräns, prisgolv, avisering på/av - ewapp:s
    /api/energy/{what}."""
    if what not in ("limit", "auto", "notify"):
        return JSONResponse({"detail": "Okänd åtgärd"}, status_code=404)
    body = await request.json()
    return await _ewapp_proxy(f"/api/energy/{what}", body)


@app.post("/api/schedule")
async def proxy_schedule(request: Request):
    """Elbil-sidan: redigera laddschemat (klar kl/nivå per veckodag) - ewapp:s
    /api/schedule, samma ev_charging_schedule-tabell vi redan läser i /api/car."""
    return await _ewapp_proxy("/api/schedule", await request.json())


@app.post("/api/settings-action")
async def proxy_setting(request: Request):
    """Elförbrukning-sidan (effektvakt på/av + effektgräns) och Värmepump-sidan
    (billig/dyr måltemperatur) - ewapp:s /api/settings, begränsat till de nycklar
    webdashboards sidor faktiskt visar kontroller för."""
    body = await request.json()
    if body.get("key") not in ("peak_shaving_enabled", "power_limit_kw", "temp_cheap", "temp_expensive",
                               "spa_normal_temp", "spa_max_temp", "spa_low_temp"):
        return JSONResponse({"detail": "Okänd inställning"}, status_code=400)
    return await _ewapp_proxy("/api/settings", body)


@app.post("/api/secure")
async def secure(request: Request):
    """Lösenordet igen innan ett lås-/luckokommando går igenom - samma 10-minutersfönster
    som ewapp:s /api/secure, men verifierat lokalt (delad PASSWORD) istället för proxat,
    så webdashboard kan sätta sin egen ew2-kaka utan en extra nätverksrunda."""
    ip = AUTH.client_ip(request)
    if _secure_fails.get(ip, (0, 0))[0] >= 5 and time.time() - _secure_fails[ip][1] < 900:
        return JSONResponse({"detail": "För många försök – vänta en stund"}, status_code=429)
    body = await request.json()
    role, user = AUTH.session(request)
    expected = AUTH.user_password(user or "")
    if not expected or not hmac.compare_digest(str(body.get("password", "")), expected):
        _secure_fails[ip] = (_secure_fails.get(ip, (0, 0))[0] + 1, time.time())
        return JSONResponse({"detail": "Fel lösenord"}, status_code=401)
    _secure_fails.pop(ip, None)
    exp = int(time.time()) + 600
    r = JSONResponse({"ok": True, "until": exp})
    r.set_cookie("ew2", f"{exp}." + hmac.new(_EWAPP_SECRET, ("sec" + str(exp)).encode(), hashlib.sha256).hexdigest(), max_age=600, httponly=True, secure=True, samesite="lax", path="/")
    return r


@app.post("/api/tesla/access")
async def proxy_tesla_access(request: Request):
    """Lås/lås upp bilen, öppna/stäng luckor - ewapp:s /api/tesla/access. Allt utom 'lock'
    kräver en färsk /api/secure härifrån (INTE bara ewapp:s egen, se ovan) innan vi ens
    försöker proxa - annars kunde vem som helst med ett inloggat webdashboard-fönster
    låsa upp bilen utan att ange lösenordet igen."""
    body = await request.json()
    what = body.get("what")
    if what not in ("lock", "unlock", "trunk", "frunk"):
        return JSONResponse({"detail": "Okänd åtgärd"}, status_code=400)
    if what != "lock" and not _secure_ok(request):
        return JSONResponse({"detail": "secure"}, status_code=403)
    car = next((c.get("key") for c in _ewapp_cars() if c.get("access")), None)   # bilen som har lås valda i installationen
    if not car:
        return JSONResponse({"detail": "Ingen bil har lås valda i installationen"}, status_code=404)
    return await _ewapp_proxy(f"/api/car/{car}/access", body, extra_cookies={"ew2": request.cookies.get("ew2", "")})


@app.get("/api/tesla/access-state")
async def tesla_access_state():
    """Lås-/luckostatus (låst/upplåst, bak-/frontlucka öppen) för Elbil-sidan - ewapp:s
    egen /api/state beräknar redan det här (live HA-läsning), vi plockar bara ut biten för
    Tesla istället för att läsa HA-entiteterna en gång till här."""
    try:
        r = requests.get(f"{EWAPP_URL}/api/state", cookies={"ew": _ewapp_cookie()}, timeout=25)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return JSONResponse({"detail": f"Nådde inte ewapp: {e}"}, status_code=502)
    car = next((c for c in data.get("cars", []) if c.get("access")), None)
    return {"ok": True, "access": car.get("access") if car else None, "car": car.get("name") if car else None}


@app.post("/api/discover")
async def api_discover():
    """Entitetsväljare (Inställningar-sidan): skannar husets riktiga Home Assistant
    efter kandidat-entiteter per kategori. Live-anrop mot HA, bara på knapptryck -
    inte cachat/automatiskt som /api/overview."""
    try:
        return {"ok": True, **discovery.discover_house()}
    except Exception as e:
        return {"ok": False, "error": f"Kunde inte skanna Home Assistant: {e}"}


@app.post("/api/discover-modbus")
async def api_discover_modbus():
    """Eget, valfritt steg - söker efter en Husdata-värmepump på det lokala nätverket
    (för installationer utan PUMP_IP satt alls). EN RIKTIG nätverksoperation (probear
    andra enheter på användarens LAN), därför en separat knapp i gränssnittet, aldrig
    en del av /api/discover. Körs i tråd så den inte blockerar servern i upp till en
    minut (pump.scan_for_husdata gör ett blockerande nätverksanrop per kandidat-IP)."""
    try:
        found = await asyncio.to_thread(pump.scan_for_husdata)
        return {"ok": True, "found": found}
    except Exception as e:
        return {"ok": False, "error": f"Kunde inte söka på nätverket: {e}"}


def _yaml_str(v) -> str:
    return "null" if v is None else f'"{v}"'


def _build_house_config_yaml(sel: dict) -> str:
    """Bygger en riktig house_config.yaml-text från de BEKRÄFTADE valen frontend
    skickar in (samma form som discovery.discover_house() ger, men bara det
    användaren lämnat ikryssat). Fält discovery inte kan avgöra (Modbus-adress,
    fysisk laddarplats) lämnas som tydliga FYLL I-platshållare, inte gissade."""
    lines = ['house_id: "mitt-hus"   # byt gärna till något eget', ""]

    lines.append("evs:")
    cars = sel.get("cars") or []
    if not cars:
        lines[-1] = "evs: []"
    for i, c in enumerate(cars):
        car_id = c.get("id") or f"bil{i + 1}"
        lines.append(f"  - id: {car_id}")
        lines.append(f"    driver: {c.get('driver') or 'generic_ev'}")
        lines.append(f"    battery_kwh: {c.get('battery_kwh') or 60}  # FYLL I - din bils batteristorlek i kWh")
        lines.append("    entities:")
        if c.get("soc_entity"):
            lines.append(f"      soc: {c['soc_entity']}")
        if c.get("plugged_in_entity"):
            lines.append(f"      plugged_in: {c['plugged_in_entity']}")
        if c.get("climate_entity"):
            lines.append(f"      climate: {c['climate_entity']}")
        charger = c.get("charger")
        if charger:
            charger_driver = charger.get("driver") or "generic"
            lines.append("    charger:")
            lines.append(f"      id: {charger.get('device_name') or car_id + '_laddare'}")
            lines.append(f"      driver: {charger_driver}  # ihopparningen bil<->laddare är en gissning (ordning på vad du kryssade i) - dubbelkolla den")
            if charger_driver == "easee":
                dn = (charger.get("device_name") or "").lower()
                guessed_physical = "carport" if "carport" in dn else "lite" if "lite" in dn else None
                if guessed_physical:
                    lines.append(f"      physical: {guessed_physical}  # gissat från enhetsnamnet '{charger.get('device_name')}' - dubbelkolla")
                else:
                    lines.append("      physical: lite  # FYLL I - vilken av dina Easee-boxar (lite/carport, bara namn - byt om du vill)")
            lines.append("      entities:")
            charger_entities = (charger.get("entities") or {}).copy()
            if charger.get("status_entity"):
                charger_entities.setdefault("status", charger["status_entity"])
            for key, val in charger_entities.items():
                lines.append(f"        {key}: {val}")
    lines.append("")

    hp = sel.get("heat_pump")
    if hp:
        hp_driver = hp.get("driver") or "generic_climate"
        lines += ["heat_pump:", "  enabled: true", f"  driver: {hp_driver}"]
        if hp_driver == "generic_climate":
            lines += ["  entities:"]
            for key, val in (hp.get("entities") or {}).items():
                lines.append(f"    {key}: {val}")
        elif hp_driver == "heishamon":
            lines += ["  host: 192.168.1.XXX  # FYLL I - HeishaMon-kortets IP (dess webbsida visar /json)",
                      "  base_shift: 0       # din vanliga kurvförskjutning (-5..5); EnergyWizard flyttar relativt den",
                      "  indoor_from_z1: false  # true bara om zon 1 har en rumsgivare"]
        else:
            lines += ["  connection:", "    modbus_host: 192.168.1.XXX  # FYLL I - värmepumpens IP/gateway, kan inte upptäckas automatiskt",
                       "    modbus_port: 502", "    unit_id: 1"]
    else:
        lines += ["heat_pump:", "  enabled: false"]
    lines.append("")

    solar = sel.get("solar")
    if solar:
        lines += ["solar:", "  enabled: true", f"  driver: {solar.get('driver') or 'generic_number'}", "  entities:"]
        solar_entities = (solar.get("entities") or {}).copy()
        if solar.get("pv_power_entity"):
            solar_entities.setdefault("pv_power_w", solar["pv_power_entity"])
        if solar.get("today_kwh_entity"):
            solar_entities.setdefault("today_kwh", solar["today_kwh_entity"])
        for key, val in solar_entities.items():
            lines.append(f"    {key}: {val}")
    else:
        lines += ["solar:", "  enabled: false"]
    lines.append("")

    spa = sel.get("spa")
    if spa:
        lines += ["spa:", "  enabled: true", f"  driver: {spa.get('driver') or 'generic_spa'}", "  entities:"]
        if spa.get("current_temp_entity"):
            lines.append(f"    current_temp: {spa['current_temp_entity']}")
        if spa.get("power_entity"):
            lines.append(f"    power_w: {spa['power_entity']}")
    else:
        lines += ["spa:", "  enabled: false"]
    lines.append("")

    battery = sel.get("battery")
    if battery:
        gs = battery.get("generic_suggestion") or {}
        modes = battery.get("modes") or gs.get("modes")
        lines += ["battery:", "  enabled: true", f"  driver: {battery.get('driver') or 'generic'}",
                   "  capacity_kwh: 10  # FYLL I - batteriets kapacitet i kWh",
                   "  control: samarbete   # samarbete = läs bara (ett annat system styr) | styr = EnergyWizard styr | av",
                   "  reserve_soc: 20      # sparas alltid till strömavbrott (%)",
                   "  priority_soc: 50     # över detta får elbilen solöverskottet före batteriet (%)",
                   "  max_power_w: 5000    # FYLL I - batteriets max ladd-/urladdningseffekt (W)"]
        if gs.get("preset") and re.fullmatch(r"[a-z0-9_]{1,40}", str(gs["preset"])):
            lines.append(f"  preset: {gs['preset']}   # vilken förinställning lägena kommer från (för telemetrin)")
        if gs.get("keepalive_s"):
            lines.append(f"  keepalive_s: {int(gs['keepalive_s'])}     # skriv om laddkommandot så här ofta (växelriktarens fjärrstyrning släpper annars)")
        if modes:
            lines.append(f"  modes:               # förifyllt för {gs.get('preset') or 'din integration'} - kontrollera mot HA")
            for intent, opt in modes.items():
                if isinstance(opt, dict):
                    pairs = ", ".join(f'{k}: "{v}"' for k, v in opt.items())
                    lines.append(f"    {intent}: {{{pairs}}}")
                else:
                    lines.append(f'    {intent}: "{opt}"')
        else:
            lines += ["  # modes:              # krävs för 'styr' - exakt de alternativ batteriets select visar i HA",
                      "  #   auto: \"Maximize self-consumption\"",
                      "  #   hold: \"...\"", "  #   idle: \"...\"", "  #   charge: \"...\"", "  #   discharge: \"...\""]
        lines.append("  entities:")
        battery_entities = (battery.get("entities") or gs.get("entities") or {}).copy()
        if battery.get("soc_entity"):
            battery_entities.setdefault("soc", battery["soc_entity"])
        if battery.get("power_entity") and "power_charge" not in battery_entities:
            battery_entities.setdefault("power", battery["power_entity"])
        for key, val in battery_entities.items():
            if isinstance(val, list):                     # flera batteribankar (#86)
                lines.append(f"    {key}: [{', '.join(str(v) for v in val)}]")
            else:
                lines.append(f"    {key}: {val}")
        if isinstance(battery_entities.get("soc"), list):
            lines.append(f"    bank_kwh: [{', '.join('10' for _ in battery_entities['soc'])}]   # FYLL I - varje banks storlek i kWh, samma ordning")
    else:
        lines += ["battery:", "  enabled: false"]
    pm = sel.get("power_meter")
    if pm and pm.get("entities"):
        lines += ["", "power_meter:   # nätimport/-export och fasströmmar (effektvakt, säkringsskydd, solladdning)",
                  f"  driver: {pm.get('driver') or 'power_w'}", "  entities:"]
        for key, val in pm["entities"].items():
            lines.append(f"    {key}: {val}")
        if pm.get("driver") == "power_w":
            lines.append("    # power_w_invert: true   # om mätaren visar EXPORT som positivt")
        if pm.get("secondary_power_w") and re.fullmatch(r"sensor\.[a-z0-9_]+", str(pm["secondary_power_w"])):
            lines.append(f"  secondary_power_w: {pm['secondary_power_w']}   # annan byggnad - visas, styr inte säkringsskyddet")
    lines += ["", "fuse:", "  main_fuse_a: 25  # FYLL I - din huvudsäkring i Ampere"]

    # Ett "entities:" utan rader under blir None i YAML - skriv en tom lista över givare i stället (#127)
    def _indent(t):
        return len(t) - len(t.lstrip())
    for i, ln in enumerate(lines):
        if ln.rstrip().endswith("entities:"):
            nxt = next((x for x in lines[i + 1:] if x.strip() and not x.strip().startswith("#")), "")
            if _indent(nxt) <= _indent(ln):
                lines[i] = ln.rstrip() + " {}"
    return "\n".join(lines) + "\n"


@app.post("/api/generate-house-config")
async def api_generate_house_config(request: Request):
    sel = await request.json()
    yaml_text = _build_house_config_yaml(sel)
    # Egenkontroll innan den lämnas ut: ska gå att läsa in och bygga drivrutiner
    # från, inte bara vara syntaktiskt rätt YAML - samma verktyg som redan finns.
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=True) as f:
            f.write(yaml_text)
            f.flush()
            cfg = house_config.load_house_config(f.name)
            house_config.build_car_drivers(cfg)
            house_config.build_heat_pump_driver(cfg)
            house_config.build_solar_driver(cfg)
            house_config.build_spa_driver(cfg)
            house_config.build_battery_driver(cfg)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Den genererade filen gick inte att läsa in: {e}"}, status_code=500)
    return Response(content=yaml_text, media_type="text/yaml",
                     headers={"Content-Disposition": "attachment; filename=house_config.yaml"})


HOUSE_CONFIG_FILE = os.environ.get("HOUSE_CONFIG_PATH", "/house_config.yaml")


def _config_writable() -> bool:
    """Bara installationer som install.sh skapat sparar härifrån (HOUSE_CONFIG_WRITABLE=1
    och filen monterad skrivbar). En handskriven config skrivs aldrig över från webben."""
    return os.environ.get("HOUSE_CONFIG_WRITABLE") == "1" and os.access(HOUSE_CONFIG_FILE, os.W_OK)


@app.get("/api/house-config-status")
async def api_house_config_status(request: Request):
    role, _ = AUTH.session(request)
    return {"writable": role == "owner" and _config_writable()}


@app.post("/api/save-house-config")
async def api_save_house_config(request: Request):
    role, _ = AUTH.session(request)
    if role != "owner":
        return JSONResponse({"ok": False, "error": "Bara ägaren kan spara"}, status_code=403)
    if not _config_writable():
        return JSONResponse({"ok": False, "error": "Den här installationen sparar inte från webben. Ladda ner filen i stället."},
                            status_code=409)
    resp = await api_generate_house_config(request)
    if not isinstance(resp, Response):
        return resp
    if getattr(resp, "status_code", 200) != 200:
        return resp
    # Skrivs på plats (samma fil, inte en ny): Docker monterar filen, och en ny fil syns inte i motorn.
    with open(HOUSE_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(resp.body.decode("utf-8"))
    return {"ok": True, "message": "Sparat. Motorn startar om och läser in den nya inställningen inom en minut."}


import i18n_routes  # noqa: E402
i18n_routes.register(app)
import web_common  # noqa: E402
web_common.register(app, lambda r: AUTH.session(r)[0], lambda: not webauth.owner_password())
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/{full_path:path}")
async def spa(full_path: str):
    return FileResponse("static/index.html")
