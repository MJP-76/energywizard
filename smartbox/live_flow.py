"""
live_flow.py - "just nu"-bilden: vilka delar av huset som drar eller ger el, och hur mycket.

Ur senaste raden i sensor_log. Bara det som faktiskt finns visas: en enhet utan mätvärden
(ingen värmepump, inget spabad, ingen bil på en laddbox) tas inte med, så bilden aldrig
visar tomma rutor för saker huset inte har. Sol, nät och hus är alltid med.

Riktning: net_power + = köper, - = säljer. battery_power_w + = laddar, - = laddar ur.
Laddboxarna kopplas till bilnamn som i resten av gränssnittet (timeline.CHARGER_CAR).
Ren funktion, testas i tests/test_live_flow.py.
"""

WATER_ON = 2          # decisions.WATER_ON - varmvattenproduktion begärd


def _f(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def nodes(row, decision_items=None):
    """row = senaste sensor_log-raden som dict. Returnerar {'nodes': [...], 'why': {nyckel: text}}."""
    r = row or {}
    out = []

    def add(key, label, icon, w, active, detail, page, role="load"):
        out.append({"key": key, "label": label, "icon": icon, "w": None if w is None else round(w),
                    "active": bool(active), "detail": detail, "page": page, "role": role})

    pv = _f(r.get("pv_power_w"))
    add("sol", "Sol", "☀️", pv or 0.0, (pv or 0) > 50, f"{(pv or 0) / 1000:.1f} kW", "solceller", "source")

    net = _f(r.get("net_power"))
    if net is None:
        add("nat", "Elnät", "🔌", 0.0, False, "–", "elforbrukning", "grid")
    else:
        add("nat", "Elnät", "🔌", net, abs(net) > 50,
            (f"Säljer {-net / 1000:.1f} kW" if net < -50 else f"Köper {net / 1000:.1f} kW"), "elforbrukning", "grid")

    house = _f(r.get("house_consumption_w"))
    if house is None and net is not None:
        house = net + (pv or 0.0) - (_f(r.get("battery_power_w")) or 0.0)
    add("hus", "Hemmet", "🏠", house, True, f"{(house or 0) / 1000:.1f} kW", "oversikt", "hub")

    bat = _f(r.get("battery_power_w"))
    if bat is not None:
        soc = _f(r.get("battery_soc"))
        add("batteri", "Batteri", "🔋", bat, abs(bat) > 30,
            ("Laddar" if bat > 30 else "Laddar ur" if bat < -30 else "Vilar") + (f" · {soc:.0f} %" if soc is not None else ""),
            "elforbrukning", "battery")

    comp = _f(r.get("compressor_running"))
    if comp is not None or r.get("compressor_power_kw") is not None:
        kw = _f(r.get("compressor_power_kw")) or 0.0
        indoor = _f(r.get("indoor_temp"))
        add("varmepump", "Värmepump", "🌡️", kw * 1000.0, (comp or 0) > 0 or kw > 0.1,
            ("Går" if (comp or 0) > 0 else "Vilar") + (f" · inne {indoor:.1f} °C" if indoor is not None else ""),
            "varmepump")
        wt = _f(r.get("water_temp"))
        if wt is not None:
            heating_water = (comp or 0) > 0 and _f(r.get("water_mode")) == WATER_ON
            add("varmvatten", "Varmvatten", "💧", None, heating_water,
                f"{wt:.0f} °C" + (" · värms" if heating_water else ""), "varmepump")

    spa_t = _f(r.get("spa_temp"))
    if spa_t is not None or r.get("spa_power_w") is not None:
        spa_w = _f(r.get("spa_power_w")) or 0.0
        on = bool(r.get("spa_heater_running")) or spa_w > 500
        add("spabad", "Spabad", "🛁", spa_w, on, (f"{spa_t:.1f} °C" if spa_t is not None else "–") + (" · värms" if on else ""), "spabad")

    for col, car, soc_col in (("ev_power_kw", "nissan", "nissan_soc"), ("ev_carport_power_kw", "tesla", "tesla_soc")):
        kw = _f(r.get(col))
        soc = _f(r.get(soc_col))
        if kw is None and soc is None:
            continue
        kw = (kw or 0.0) / 1000.0 if (kw or 0) > 100 else (kw or 0.0)       # vissa rader loggade W
        add(f"ev_{car}", car.capitalize(), "🚗", kw * 1000.0, kw > 0.05,
            (f"Laddar {kw:.1f} kW" if kw > 0.05 else "Laddar inte") + (f" · {soc:.0f} %" if soc is not None else ""), "elbil")

    why = {}
    for it in decision_items or []:
        k = {"elbil": None, "varmepump": "varmepump", "varmvatten": "varmvatten", "spabad": "spabad", "sol": "sol"}.get(it.get("key"))
        if k:
            why[k] = it.get("text")
        elif it.get("key") == "elbil":
            for n in out:
                if n["key"].startswith("ev_"):
                    why[n["key"]] = it.get("text")
    return {"nodes": out, "why": why}
