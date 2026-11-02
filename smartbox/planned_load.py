"""
planned_load.py - EnergyWizards planerade laster som en lastprognos Predbat kan läsa in.

Steg 2 i samplaneringen med Predbat (se ROADMAP.md): Predbat planerar husbatteriet mot en
prognos av husets last. Om EnergyWizard redan vet att elbilen ska ladda 11 kW kl 02-05 är det
precis den sortens kommande last Predbat annars inte ser i förväg.

Formatet är bekräftat mot Predbats egen källkod (springfall2008/batpred, apps/predbat/fetch.py,
fetch_extra_load_forecast + get_from_incrementing), inte gissat: `load_forecast` i apps.yaml pekar
på `sensor$attribut`, attributet är en dict {tidsstämpel med tidszon: kWh} där kWh är en
STIGANDE (kumulativ) serie - Predbat räknar lasten per minut som skillnaden mellan två minuter.
Därför skrivs varje slott med en punkt vid start OCH slut, så att Predbats utjämning inte smetar
ut energin över luckorna mellan slottarna.

Bara elbilens laddplan ingår: det är den enda last EnergyWizard planerar framåt i tiden.
Värmepump och spabad bestäms minut för minut utifrån nuläget (gpm.py) och har ingen plan att
publicera - att hitta på en sådan vore en gissning, inte en plan.

Rena funktioner utan I/O - testas i tests/test_planned_load.py.
"""

from datetime import datetime, timedelta
import zoneinfo

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")
SLOT = timedelta(minutes=15)   # samma upplösning som decisions.py:s laddplan (freq='15min')


def _local(ts):
    """ev_plan_slots.t_slot sparas som naiv svensk lokaltid (se main.py:_persist_ev_plan)."""
    return ts.replace(tzinfo=SWE) if ts.tzinfo is None else ts.astimezone(SWE)


def build_forecast(rows, now):
    """rows = [(car_id, t_slot, kw), ...] från ev_plan_slots. now = tz-medveten datetime.

    Returnerar (kw_nu, attribut) för sensorn:
      - kw_nu: planerad elbilseffekt i den pågående slotten (kW)
      - attribut['predbat']: {iso: kumulativ kWh} - peka Predbats load_forecast hit
      - attribut['slottar']: [{start, slut, kw, bilar}] - läsbar form för dashboards
      - attribut['totalt_kwh']: summa planerad energi framåt
    Slottar som redan är helt passerade tas bort; flera bilar i samma slott summeras."""
    now = _local(now)
    per_slot = {}
    for car_id, t_slot, kw in rows or []:
        if t_slot is None or kw is None or float(kw) <= 0:
            continue
        start = _local(t_slot)
        if start + SLOT <= now:
            continue
        s = per_slot.setdefault(start, {"kw": 0.0, "bilar": set()})
        s["kw"] += float(kw)
        s["bilar"].add(str(car_id))

    predbat = {}
    slottar = []
    cum = 0.0
    kw_now = 0.0
    for start in sorted(per_slot):
        kw = per_slot[start]["kw"]
        end = start + SLOT
        eff_start = max(start, now)          # bara den återstående delen av pågående slott räknas
        if start <= now < end:
            kw_now = kw
        predbat[eff_start.isoformat(timespec="seconds")] = round(cum, 4)
        cum += kw * (end - eff_start).total_seconds() / 3600.0
        predbat[end.isoformat(timespec="seconds")] = round(cum, 4)
        slottar.append({"start": start.isoformat(timespec="minutes"), "slut": end.isoformat(timespec="minutes"),
                        "kw": round(kw, 2), "bilar": sorted(per_slot[start]["bilar"])})

    attrs = {
        "predbat": predbat,
        "slottar": slottar,
        "totalt_kwh": round(cum, 2),
        "uppdaterad": now.isoformat(timespec="seconds"),
    }
    return round(kw_now, 2), attrs
