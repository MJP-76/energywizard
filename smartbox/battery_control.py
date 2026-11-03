"""
battery_control.py - husbatteriet som en del av HELA systemet, inte en egen ö.

Batteriet konkurrerar med elbil, värmepump, spabad och export om samma watt. Därför fattas
besluten här med hela husets läge som indata (elbilens laddning, effekttaket, säkringen,
elpriset, solöverskottet) - samma idé som evcc:s samspel mellan batteri och elbil och FTW:s
säkerhetsmodell, men egen implementation.

Tre lägen (battery.control i house_config.yaml):
  samarbete  (standard) Ett annat system styr batteriet (växelriktarens egen BESS, Predbat).
             EnergyWizard skriver ALDRIG till batteriet - läser bara, och resten av motorn
             räknar redan rätt eftersom allt mäts vid huvudsäkringen (efter batteriet).
  styr       EnergyWizard väljer läge enligt reglerna nedan.
  av         Batteriet ignoreras.

Reglerna, i prioritetsordning (första som gäller vinner):
  1. Gammal data (batteriet eller elmätaren svarar inte)  -> auto  (växelriktaren tar över)
  2. Säkringen överbelastad / över 1,2 x                   -> ladda ur (om över reservnivån)
  3. Effekttaket nått och huset köper el                   -> ladda ur (om över reservnivån)
  4. Minuspris                                             -> ladda (även från nätet), upp till max
  5. Elbilen laddar från nätet                             -> håll (töm inte batteriet i bilen)
  6. Elbilen solladdar och batteriet är över prioritetsnivån -> vila (överskottet till bilen)
  7. Batteriet vid/under reservnivån                       -> håll (sparas till strömavbrott)
  8. Dygnsplanen (battery_plan.py) för pågående kvart     -> ladda / ladda ur / håll / auto
  9. (utan plan) Billig timme och dyrare timmar kvar       -> håll (spara till de dyra timmarna)
 10. Annars                                                -> auto (självförbrukning)

En avsikt som drivrutinen inte stöder ersätts av närmaste säkra (vila -> håll -> auto).
Ren funktion; testas i tests/test_battery_control.py.
"""

from datetime import timedelta

MIN_CHANGE_INTERVAL = timedelta(minutes=5)     # lägesbyten sparsamt (flashminne), säkerhetsregler undantagna
SAFETY_RULES = {"stale", "fuse", "peak"}
FUSE_MIN_W = 500
FROZEN_AFTER_S = 600          # elmätaren visar exakt samma värde så här länge -> räknas som död


class MeterFreeze:
    """Känner igen en elmätare som fastnat (FTW-lärdom). HA kan fortsätta svara med senaste
    värdet när mätaren tystnat, så en lyckad läsning betyder inte att värdet är färskt.
    En riktig mätare ändras hela tiden, även lite."""

    def __init__(self, after_s=FROZEN_AFTER_S):
        self.after_s = after_s
        self._value = None
        self._since = None

    def update(self, value, now):
        if value != self._value:
            self._value, self._since = value, now
        return self.frozen(now)

    def frozen(self, now):
        return self._since is not None and (now - self._since) >= self.after_s
_FALLBACK = {"idle": ["idle", "hold", "auto"], "hold": ["hold", "auto"], "charge": ["charge", "auto"],
             "discharge": ["discharge", "auto"], "auto": ["auto"]}


def _percentile(values, pct):
    s = sorted(v for v in values if v is not None)
    if not s:
        return None
    return s[max(0, min(len(s) - 1, int(round(pct / 100.0 * (len(s) - 1)))))]


def decide(s, cfg, supported=frozenset({"auto"})):
    """s = husets läge (se nycklar nedan), cfg = house_config.battery_settings().
    Returnerar {'intent': str|None, 'power_w': float|None, 'rule': str, 'reason': str}.
    intent None = skriv ingenting (samarbete/av eller inget batteri)."""
    control = cfg.get("control", "samarbete")
    soc = s.get("soc")
    if control == "av":
        return {"intent": None, "power_w": None, "rule": "av", "reason": "Batteristyrningen är avstängd."}
    if control == "samarbete":
        txt = "Samarbete: batteriet styrs av ett annat system (t.ex. växelriktarens BESS eller Predbat)."
        if soc is not None:
            txt += f" EnergyWizard läser det ({soc:.0f} %) och räknar med det, men skriver aldrig."
        return {"intent": None, "power_w": None, "rule": "samarbete", "reason": txt}

    reserve, prio, max_soc = cfg.get("reserve_soc", 20.0), cfg.get("priority_soc", 50.0), cfg.get("max_soc", 100.0)
    pmax = cfg.get("max_power_w", 5000.0)
    above_reserve = soc is not None and soc > reserve

    def out(intent, rule, reason, power=None):
        for cand in _FALLBACK[intent]:
            if cand == "auto" or cand in supported:
                if cand != intent:
                    reason += f" (batteriet saknar läget '{intent}' - kör '{cand}')"
                return {"intent": cand, "power_w": power if cand == intent else None, "rule": rule, "reason": reason}

    if soc is None or not s.get("meter_fresh", True):
        return out("auto", "stale", "Säkerhet: batteriet eller elmätaren svarar inte - växelriktaren styr själv.")
    if s.get("fuse_state") in ("trip", "overload") and above_reserve:
        # Bara överskottet (FTW-lärdom): full urladdning trycker ner nätet långt under gränsen
        # och slösar batteri. Överskottet i A på värsta fasen räknas om till effekt för en
        # trefasig växelriktare, med 20 % marginal. Okänt överskott -> full effekt.
        excess_a = s.get("fuse_excess_a") or 0
        p = pmax
        if excess_a > 0:
            p = max(FUSE_MIN_W, excess_a * 230.0 * 3 * 1.2)
            p = min(pmax, p) if pmax else p
        return out("discharge", "fuse", f"Säkringen är överbelastad - batteriet laddar ur för att avlasta ({soc:.0f} %).", p)
    if s.get("peak_reached") and (s.get("avg_net_w") or 0) > 100 and above_reserve:
        return out("discharge", "peak", f"Effekttaket är nått - batteriet täcker toppen ({soc:.0f} %).", pmax)
    price = s.get("price")
    if price is not None and price < 0 and soc < max_soc:
        return out("charge", "negative", f"Minuspris ({price:.2f} kr/kWh) - laddar batteriet från nätet.", pmax)
    if s.get("ev_charging_grid"):
        return out("hold", "ev_grid", "Elbilen laddar från nätet - batteriet töms inte i bilen.")
    if s.get("ev_solar_active") and soc >= prio:
        return out("idle", "ev_solar", f"Elbilen solladdar och batteriet har {soc:.0f} % (över {prio:.0f} %) - solöverskottet går till bilen.")
    if soc <= reserve:
        return out("hold", "reserve", f"Batteriet är på reservnivån ({soc:.0f} % ≤ {reserve:.0f} %) - sparas till strömavbrott.")
    planned = s.get("planned_action")
    if planned:
        from battery_plan import REASON
        pmax_plan = pmax if planned in ("charge", "discharge") else None
        if pmax_plan and s.get("planned_power_w"):            # planens egen effekt, aldrig över taket
            pmax_plan = min(pmax_plan, max(500.0, float(s["planned_power_w"])))
        detail = f" ({price:.2f} kr/kWh)" if price is not None else ""
        saving = s.get("plan_saving_kr")
        extra = f" Planen sparar ≈ {saving:.0f} kr mot ren självförbrukning." if saving and saving >= 1 else ""
        note = f" {s['learned_note']}" if s.get("learned_note") else ""
        return out(planned, "plan", f"{REASON.get(planned, 'Planen')}{detail}.{extra}{note}", pmax_plan)
    remaining = s.get("prices_rest_of_day") or []
    p33, p67 = _percentile(remaining, 33), _percentile(remaining, 67)
    if price is not None and p33 is not None and p67 is not None and price <= p33 and p67 > price * 1.2 + 0.05:
        return out("hold", "cheap_hour", f"Billig timme ({price:.2f} kr) och dyrare timmar kvar idag - batteriet sparas till dem.")
    return out("auto", "default", f"Självförbrukning - batteriet täcker husets behov ({soc:.0f} %).")


def should_apply(new, last, last_change_at, now):
    """Byt läge bara när det behövs: direkt vid säkerhetsregler, annars högst var 5:e minut."""
    if new is None or new.get("intent") is None:
        return False
    if last is None or last_change_at is None:
        return True
    if new["intent"] == last.get("intent") and new.get("power_w") == last.get("power_w"):
        return False
    if new.get("rule") in SAFETY_RULES or last.get("rule") in SAFETY_RULES:
        return True
    return (now - last_change_at) >= MIN_CHANGE_INTERVAL
