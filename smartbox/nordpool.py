import os
import requests
import psycopg
from datetime import datetime, timedelta
from contextlib import contextmanager
import zoneinfo

SWE_TZ = zoneinfo.ZoneInfo("Europe/Stockholm")

DB_HOST = os.environ.get("POSTGRES_HOST", "postgres-smartbox")
DB_USER = os.environ.get("POSTGRES_USER")
DB_PASS = os.environ.get("POSTGRES_PASSWORD")
DB_NAME = os.environ.get("POSTGRES_DB")

# Val av priskälla: "elprisetjustnu" (default, oförändrat) eller "ha_nordpool"
# (läs Home Assistants egen nordpool-integration istället för att hämta själva).
# Opt-in - installationer utan PRICE_SOURCE satt påverkas inte alls.
PRICE_SOURCE = os.environ.get("PRICE_SOURCE", "elprisetjustnu").strip().lower()
NORDPOOL_HA_ENTITY = os.environ.get("NORDPOOL_HA_ENTITY", "sensor.nordpool").strip()

from logger import get_db

# Verklig köp-/säljkostnad kr/kWh - EN plats för formeln som annars var duplicerad i
# gpm.py, mpc.py, pump_runtime.py och smartdashboard/app.py (källoberoende konstanter:
# nätavgift+skatt+elhandlarens avgift är redan momsinklusive, oavsett vilken bas spotpriset
# har). Sälj: ingen moms på sålt solöverskott (svenska skatteregler för mikroproduktion).
BUY_FIXED_KR = 0.62675        # Sverige (standard): nätöverföring + energiskatt + elhandlarens påslag, inkl. moms
SELL_FIXED_KR = 0.02125
VAT_FACTOR = 1.25

# ---- Elpris och avgifter per land (2026-11-03) ----------------------------------------------------------------
# Allt som gör spotpriset till en verklig kostnad går att ställa in: i webben (Inställningar -> Elpris och avgifter,
# sparas i /data/energywizard.json), med miljövariabler (PRICE_COUNTRY, PRICE_AREA, PRICE_VAT_PCT, PRICE_BUY_EXTRA,
# PRICE_SELL_EXTRA, PRICE_SELL_VAT, PRICE_CURRENCY) eller inte alls (= Sverige, exakt som förut).
# Landet ger bara standardmoms, valuta och elområden - nätavgift, energiskatt och påslag står på elräkningen och
# skiljer sig mellan nätbolag, så de skrivs in av användaren (0 om inget anges, utom Sverige).
# Momssatserna är de allmänna för hushållsel; kontrollera mot elräkningen (t.ex. är Nordnorge momsfritt).
COUNTRIES = {
    "SE": {"name": "Sverige", "vat_pct": 25.0, "currency": "SEK", "areas": ["SE1", "SE2", "SE3", "SE4"],
           "buy_extra": BUY_FIXED_KR, "sell_extra": SELL_FIXED_KR},
    "NO": {"name": "Norge", "vat_pct": 25.0, "currency": "NOK", "areas": ["NO1", "NO2", "NO3", "NO4", "NO5"]},
    "DK": {"name": "Danmark", "vat_pct": 25.0, "currency": "DKK", "areas": ["DK1", "DK2"]},
    "FI": {"name": "Finland", "vat_pct": 25.5, "currency": "EUR", "areas": ["FI"]},
    "EE": {"name": "Estland", "vat_pct": 24.0, "currency": "EUR", "areas": ["EE"]},
    "LV": {"name": "Lettland", "vat_pct": 21.0, "currency": "EUR", "areas": ["LV"]},
    "LT": {"name": "Litauen", "vat_pct": 21.0, "currency": "EUR", "areas": ["LT"]},
    "DE": {"name": "Tyskland", "vat_pct": 19.0, "currency": "EUR", "areas": ["DE-LU"]},
    "NL": {"name": "Nederländerna", "vat_pct": 21.0, "currency": "EUR", "areas": ["NL"]},
    "BE": {"name": "Belgien", "vat_pct": 6.0, "currency": "EUR", "areas": ["BE"]},
    "AT": {"name": "Österrike", "vat_pct": 20.0, "currency": "EUR", "areas": ["AT"]},
    "FR": {"name": "Frankrike", "vat_pct": 20.0, "currency": "EUR", "areas": ["FR"]},
    "PL": {"name": "Polen", "vat_pct": 23.0, "currency": "PLN", "areas": ["PL"]},
    "GB": {"name": "Storbritannien", "vat_pct": 5.0, "currency": "GBP", "areas": ["GB"]},
}
CURRENCY_SYMBOL = {"SEK": "kr", "NOK": "kr", "DKK": "kr", "EUR": "€", "PLN": "zł", "GBP": "£"}


def _setting(key, env, default=None):
    try:
        import ew_settings
        v = ew_settings.get(key)
    except Exception:
        v = None
    if v in (None, ""):
        v = os.environ.get(env, "").strip() or None
    return default if v in (None, "") else v


def _num(v, default):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return default


def cost_settings() -> dict:
    """Gällande land, elområde, moms och avgifter. Utan inställningar: Sverige SE3 med dagens värden."""
    country = str(_setting("price_country", "PRICE_COUNTRY", "SE")).upper()
    preset = COUNTRIES.get(country, COUNTRIES["SE"] if country == "SE" else {"vat_pct": 0.0, "currency": "EUR", "areas": []})
    area = str(_setting("price_area", "PRICE_AREA", "SE3" if country == "SE" else (preset.get("areas") or [""])[0])).upper()
    currency = str(_setting("price_currency", "PRICE_CURRENCY", preset.get("currency", "EUR"))).upper()
    return {
        "country": country, "area": area, "currency": currency, "symbol": CURRENCY_SYMBOL.get(currency, currency),
        "vat_pct": _num(_setting("price_vat_pct", "PRICE_VAT_PCT"), preset.get("vat_pct", 0.0)),
        "buy_extra": _num(_setting("price_buy_extra", "PRICE_BUY_EXTRA"), preset.get("buy_extra", 0.0)),
        "sell_extra": _num(_setting("price_sell_extra", "PRICE_SELL_EXTRA"), preset.get("sell_extra", 0.0)),
        "sell_vat": str(_setting("price_sell_vat", "PRICE_SELL_VAT", "false")).lower() in ("1", "true", "ja", "yes"),
    }


def price_source() -> str:
    """elprisetjustnu.se har bara Sverige. Andra länder läser HA:s Nordpool-integration om inget annat är valt."""
    if "PRICE_SOURCE" in os.environ or cost_settings()["country"] == "SE":
        return PRICE_SOURCE
    return "ha_nordpool"


def _vat_factor() -> float:
    return 1.0 + cost_settings()["vat_pct"] / 100.0


def prices_include_vat() -> bool:
    """True om elpriser.sek_per_kwh redan är momsinklusive (Nordpool-integrationen i HA)."""
    return price_source() == "ha_nordpool"


def full_buy_cost(spot: float) -> float:
    """Verklig köpkostnad per kWh inkl moms, nätöverföring och skatt (i landets valuta). Dubbelräknar aldrig
    moms oavsett vilken bas spotpriset har."""
    c = cost_settings()
    if prices_include_vat():
        return spot + c["buy_extra"]
    return spot * _vat_factor() + c["buy_extra"]


def full_sell_income(spot: float) -> float:
    """Verklig försäljningsintäkt per kWh vid export. Sverige: ingen moms på sålt överskott (mikroproduktion)."""
    c = cost_settings()
    f = _vat_factor()
    base = spot / f if prices_include_vat() else spot
    return (base * f if c["sell_vat"] else base) + c["sell_extra"]


def sql_buy_cost_expr(col: str) -> str:
    """Samma formel som SQL-uttryck (Postgres), för ställen som räknar i databasen
    istället för rad-för-rad i Python (pump_runtime.py, smartdashboard)."""
    c = cost_settings()
    if prices_include_vat():
        return f"({col} + {c['buy_extra']})"
    return f"({col} * {_vat_factor()} + {c['buy_extra']})"


def sql_sell_income_expr(col: str) -> str:
    c = cost_settings()
    f = _vat_factor()
    base = f"({col} / {f})" if prices_include_vat() else f"{col}"
    return f"({base}{f' * {f}' if c['sell_vat'] else ''} + {c['sell_extra']})"

def init_db():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS elpriser (
                        time_start TIMESTAMP WITH TIME ZONE PRIMARY KEY,
                        time_end   TIMESTAMP WITH TIME ZONE,
                        sek_per_kwh NUMERIC
                    )
                """)
            conn.commit()
    except Exception as e:
        print(f"❌ Kunde inte initiera databasen: {e}")

def fetch_api_and_save(date_obj):
    date_str = date_obj.strftime("%Y/%m-%d")
    area = cost_settings()["area"] if cost_settings()["area"] in COUNTRIES["SE"]["areas"] else "SE3"
    url = f"https://www.elprisetjustnu.se/api/v1/prices/{date_str}_{area}.json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            records = [
                (item['time_start'], item['time_end'], item['SEK_per_kWh'])
                for item in data
            ]
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.executemany("""
                        INSERT INTO elpriser (time_start, time_end, sek_per_kwh)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (time_start) DO NOTHING
                    """, records)
                conn.commit()
            print(f"📥 Laddade ner {len(records)} rader för {date_str}.")
            return True
    except Exception as e:
        print(f"❌ Fel vid API-hämtning för {date_str}: {e}")
    return False


def fetch_ha_nordpool_and_save(date_obj):
    """Hämtar priser från Home Assistants egen nordpool-integration (sensor.nordpool,
    attributen raw_today/raw_tomorrow) istället för att anropa elprisetjustnu.se.

    Samma kontrakt som fetch_api_and_save: True/False, samma INSERT/ON CONFLICT-mönster
    så nedströms-konsumenter (get_price_info, get_price_at) inte märker varifrån raderna
    kom. Priserna kommer i 15-minutersupplösning från HA - get_price_info hanterar redan
    båda upplösningarna.
    """
    import homeassistant
    date_str = date_obj.strftime("%Y-%m-%d")
    try:
        entity = _setting("price_ha_entity", "NORDPOOL_HA_ENTITY", NORDPOOL_HA_ENTITY)
        r = requests.get(
            f"{homeassistant._BASE}/states/{entity}",
            headers=homeassistant._HEADERS, timeout=10, verify=homeassistant._VERIFY,
        )
        if r.status_code != 200:
            print(f"❌ HA nordpool-sensorn ({entity}) svarade {r.status_code}.")
            return False
        attrs = r.json().get("attributes", {})
        raw_today = attrs.get("raw_today") or []
        raw_tomorrow = attrs.get("raw_tomorrow") or []

        wanted = [
            item for item in (raw_today + raw_tomorrow)
            if datetime.fromisoformat(item["start"]).astimezone(SWE_TZ).date() == date_obj.date()
        ]
        if not wanted:
            print(f"⚠️ HA nordpool-sensorn har inga priser för {date_str} (ännu).")
            return False

        records = [
            (item["start"], item["end"], item["value"])
            for item in wanted
        ]
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO elpriser (time_start, time_end, sek_per_kwh)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (time_start) DO NOTHING
                """, records)
            conn.commit()
        print(f"📥 Laddade ner {len(records)} rader för {date_str} från HA nordpool-integrationen.")
        return True
    except Exception as e:
        print(f"❌ Fel vid HA nordpool-hämtning för {date_str}: {e}")
    return False


def _fetch_and_save(date_obj):
    """Hämtar och sparar ett dygns priser enligt konfigurerad PRICE_SOURCE, med automatisk
    fallback till elprisetjustnu.se samma cykel om den primära källan misslyckas - pris-
    optimeringen får aldrig stå helt utan källa bara för att HA-integrationen är otillgänglig."""
    if price_source() == "ha_nordpool":
        if fetch_ha_nordpool_and_save(date_obj):
            return True
        print("⚠️ HA nordpool-källan misslyckades, faller tillbaka till elprisetjustnu.se.")
        return fetch_api_and_save(date_obj)
    return fetch_api_and_save(date_obj)


def ensure_prices_exist():
    now = datetime.now(SWE_TZ)
    today    = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    day_after = tomorrow + timedelta(days=1)

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Byte av land/elområde/källa: dagens och morgondagens priser hämtas om (annars ligger det gamla
                # områdets priser kvar, ON CONFLICT DO NOTHING).
                c = cost_settings()
                key = f"{price_source()}:{c['country']}:{c['area']}"
                try:
                    import ew_settings
                    if ew_settings.get("price_fetched_for") not in (None, key):
                        cur.execute("DELETE FROM elpriser WHERE time_start >= %s", (today,))
                        conn.commit()
                        print(f"🔁 Elområde/källa ändrad ({ew_settings.get('price_fetched_for')} -> {key}) - hämtar om priserna.")
                    if ew_settings.get("price_fetched_for") != key:
                        ew_settings.update(price_fetched_for=key)
                except Exception as e:
                    print(f"⚠️ Kunde inte kontrollera elområdet: {e}")
                cur.execute("SELECT COUNT(*) FROM elpriser WHERE time_start >= %s AND time_start < %s", (today, tomorrow))
                if cur.fetchone()[0] == 0:
                    print("⚠️ Saknar priser för idag. Hämtar från API...")
                    # FIX: Agera på fetch-status så tyst degradering (tom prislista -> dyra
                    # default-lägen) syns i loggen istället för att ignoreras.
                    if not _fetch_and_save(today):
                        print("❌ KRITISKT: Kunde inte hämta dagens priser – pris-optimering "
                              "(peak shaving/EV/värme/spa) faller tillbaka till default tills priser finns.")

                if (now.hour == 13 and now.minute >= 30) or now.hour >= 14:
                    cur.execute("SELECT COUNT(*) FROM elpriser WHERE time_start >= %s AND time_start < %s", (tomorrow, day_after))
                    if cur.fetchone()[0] == 0:
                        print("📅 Hämtar morgondagens priser...")
                        # FIX: Logga om morgondagens priser inte kunde hämtas (kan ännu inte
                        # vara publicerade) så det inte tystas helt.
                        if not _fetch_and_save(tomorrow):
                            print("⚠️ Morgondagens priser kunde inte hämtas ännu – försöker igen nästa cykel.")
    except Exception as e:
        print(f"❌ Databasfel vid kontroll av priser: {e}")


def get_price_at(dt):
    """Returnerar elpriset för en given tidpunkt."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT sek_per_kwh FROM elpriser
                    WHERE time_start <= %s AND time_end > %s
                """, (dt, dt))
                row = cur.fetchone()
                return float(row[0]) if row else None
    except Exception as e:
        print(f"❌ Fel vid hämtning av pris för tidpunkt: {e}")
    return None

def _recent_actual_price_avg():
    """Senaste 7 dygnens faktiska snittpris (kr/kWh), för nivåjustering av prisprognosen."""
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("SELECT AVG(sek_per_kwh) FROM elpriser WHERE time_start >= NOW() - INTERVAL '7 days' AND sek_per_kwh IS NOT NULL")
            r = cur.fetchone()
            return float(r[0]) if r and r[0] is not None else None
    except Exception:
        return None

def forecast_price_at(dt):
    """Prisprognos BORTOM Nordpools publicerade horisont.

    Returnerar (pris, är_prognos): publicerat pris om det finns (är_prognos=False), annars en
    MODELLERAD uppskattning (inlärd dygnsform × aktuell prisnivå, är_prognos=True), eller
    (None, True) om varken pris eller modell finns. Modellen fångar dygns-/säsongsmönstret –
    inte exakta toppar – och ska därför användas för PLANERING/visning, inte som facit."""
    published = get_price_at(dt)
    if published is not None:
        return published, False
    try:
        import learning
        shape = learning.get_price_shape_profile()
    except Exception:
        shape = None
    if not shape:
        return None, True
    s = shape.get((dt.month, dt.hour))
    if s is None:
        # Fallback: saknas månadens cell (t.ex. ingen historik för nästa månad ännu) → använd
        # timmens snitt över alla månader (dygnsformen är lik; nivåfaktorn korrigerar nivån).
        hour_cells = [v for (m, h), v in shape.items() if h == dt.hour]
        s = (sum(hour_cells) / len(hour_cells)) if hour_cells else None
    if s is None:
        return None, True
    # Nivåjustering: skala formen så dess snitt för innevarande månad matchar senaste 7 dygns faktiska snitt.
    month_cells = [v for (m, h), v in shape.items() if m == dt.month] or list(shape.values())
    shape_month_avg = (sum(month_cells) / len(month_cells)) if month_cells else None
    actual = _recent_actual_price_avg()
    factor = 1.0
    if shape_month_avg and shape_month_avg > 0 and actual is not None:
        factor = max(0.3, min(3.0, actual / shape_month_avg))
    return round(s * factor, 4), True

# FIX: Tog bort get_upcoming_prices() – död kod (verifierat med grep: inga referenser i
# smartbox/ eller smartdashboard/ utanför denna fil).


def calculate_day_strategy(all_prices, cheap_hours_count):
    """
    Räknar ut dagens regleringsstrategi baserat på prisbilden.

    Logik:
    - Billig dag (snitt < 0.50 kr, spread < 0.30 kr): kör komfort, ingen optimering
    - Annars: skala hysteres efter dagens spread så värmepumpen slipper fladdra
      vid små prisrörelser men reagerar på stora.

    Returns dict med:
      mode        : "comfort" | "optimize"
      hysteresis  : float (kr/kWh) – dead zone runt dynamic_limit
      dynamic_limit: float (kr/kWh)
      comfort_temp: int (pumpvärde, t.ex. 210 = 21.0°C) vid comfort-mode
      description : läsbar förklaring
    """
    if not all_prices:
        return {
            "mode": "optimize",
            "hysteresis": 0.10,
            "dynamic_limit": None,
            "comfort_temp": 210,
            "description": "Ingen prisdata – fallback hysteres 10 öre"
        }

    min_p  = min(all_prices)
    max_p  = max(all_prices)
    spread = max_p - min_p
    avg_p  = sum(all_prices) / len(all_prices)

    cheap_quarters = cheap_hours_count * 4
    dynamic_limit = sorted(all_prices)[cheap_quarters - 1] if len(all_prices) >= cheap_quarters else None

    # Billig dag – kör bara ett fast komfortvärde, spara compressorn. Gränserna är kalibrerade
    # mot momsexklusiva spotpriser - skala med VAT_FACTOR om elpriser nu är momsinklusive
    # (PRICE_SOURCE=ha_nordpool), annars klassas dagar fel när prisnivån byter bas.
    vat_scale = VAT_FACTOR if prices_include_vat() else 1.0
    if avg_p < 0.50 * vat_scale and spread < 0.30 * vat_scale:
        return {
            "mode": "comfort",
            "hysteresis": 0.0,
            "dynamic_limit": dynamic_limit,
            "comfort_temp": 210,
            "description": f"Billig dag (snitt {avg_p:.2f} kr, spread {spread:.2f} kr) – kör 21°C komfort"
        }

    # Skala hysteres: 15 % av spreaden, clampat 5–20 öre
    hysteresis = round(min(max(spread * 0.15, 0.05), 0.20), 3)

    return {
        "mode": "optimize",
        "hysteresis": hysteresis,
        "dynamic_limit": dynamic_limit,
        "comfort_temp": 210,
        "description": f"Optimerar (snitt {avg_p:.2f} kr, spread {spread:.2f} kr → hysteres {hysteresis:.2f} kr)"
    }

def get_price_info(cheap_hours_count=8):
    """Huvudfunktion: returnerar (current_price, dynamic_limit, strategy, all_prices)."""
    init_db()
    ensure_prices_exist()

    now = datetime.now(SWE_TZ)
    today_start    = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    cheap_quarters_count = cheap_hours_count * 4

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Aktuellt pris
                cur.execute("""
                    SELECT sek_per_kwh FROM elpriser
                    WHERE time_start <= %s AND time_end > %s
                """, (now, now))
                row = cur.fetchone()
                current_price = float(row[0]) if row else None

                # FIX: Hämta alla kvarterspriser idag i TIDSORDNING (inte prisordning).
                # Konsumenter (gpm.py prediktiv överladdning, notifier morgontips) indexerar
                # all_prices per kvart (t.ex. all_prices[hour*4 + minute//15]), så listan MÅSTE
                # vara tidssorterad. Prisrankning (cheap hours / dynamic_limit) görs separat via
                # sorted(...) i calculate_day_strategy och är därför opåverkad.
                cur.execute("""
                    SELECT sek_per_kwh FROM elpriser
                    WHERE time_start >= %s AND time_start < %s
                    ORDER BY time_start ASC
                """, (today_start, tomorrow_start))
                raw_prices = [float(r[0]) for r in cur.fetchall()]

                # FALLBACK (#2): saknas dagens priser helt → använd GÅRDAGENS prisprofil som
                # approximation (in-memory, skrivs EJ till DB så riktiga priser kan ta över direkt).
                # Mycket bättre än platt default-hysteres när elprisetjustnu.se tillfälligt är nere.
                price_fallback = False
                if not raw_prices:
                    cur.execute("""
                        SELECT sek_per_kwh FROM elpriser
                        WHERE time_start >= %s AND time_start < %s
                        ORDER BY time_start ASC
                    """, (today_start - timedelta(days=1), today_start))
                    y_prices = [float(r[0]) for r in cur.fetchall()]
                    if y_prices:
                        raw_prices = y_prices
                        price_fallback = True
                        print("⚠️ Dagens priser saknas – använder GÅRDAGENS prisprofil som fallback.")

                # Konvertera till 15-minuters array (96 slots) oavsett källa
                all_prices = []
                if 0 < len(raw_prices) <= 24:
                    for p in raw_prices:
                        all_prices.extend([p, p, p, p])
                else:
                    all_prices = raw_prices

                # Härled aktuellt pris ur fallback-profilen om realtidspriset saknas
                if current_price is None and price_fallback and all_prices:
                    idx = now.hour * 4 + now.minute // 15
                    current_price = all_prices[idx] if idx < len(all_prices) else all_prices[-1]

        strategy = calculate_day_strategy(all_prices, cheap_hours_count)
        strategy["price_fallback"] = price_fallback  # main.py notiserar (deduppat) vid fallback
        dynamic_limit = strategy.get("dynamic_limit")
        return current_price, dynamic_limit, strategy, all_prices

    except Exception as e:
        print(f"❌ Fel vid läsning från databas: {e}")
        return None, None, {"mode": "optimize", "hysteresis": 0.10, "comfort_temp": 210, "description": "DB-fel"}, []