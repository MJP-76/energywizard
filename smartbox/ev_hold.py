"""ev_hold.py - varför laddar bilen långsammare än vi beställt? (idé från FTW v0.160, Emil godkände 2026-11-07)

EnergyWizard beställer t.ex. 16 A men bilen drar 10 A. Förut syntes bara den lägre siffran, och det såg ut som att
styrningen inte fungerade. Oftast är det något annat som håller emot, och det går att läsa ut vad:
  - laddboxens totala gräns (Easee: "output limit") är lägre: lastbalansering/Equalizer eller kretsens gräns
  - laddboxens egen maxgräns är lägre än beställningen
  - laddboxen anger en anledning ("reason for no current")
  - inget av det: bilen tar inte mer (bilens egen laddare, laddgräns i bilen eller kallt batteri)

Kräver att skillnaden håller i sig HOLD_MIN minuter (bilen rampar upp strömmen efter en ändring). Ren logik,
testas i tests/test_ev_hold.py; motorn (main.py) skriver resultatet som en kontrollvarning (control_alerts.py).
"""
HOLD_MIN = 5            # minuter i rad innan det räknas som att något håller emot
MARGIN_A = 2.0          # så mycket under beställningen innan det räknas (mätbrus, avrundning)
_BENIGN = ("", "unknown", "unavailable", "none", "no_current_request", "ok")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def explain(ordered_a, reading: dict | None):
    """Text om varför laddningen ligger under beställningen, eller None (ingen skillnad / inget att säga).
    Pausad laddning (0 A beställt) eller bil som inte drar alls (stannad laddning sköts av en egen vakt) -> None."""
    if not reading or not ordered_a or ordered_a < 6:
        return None
    got = _num(reading.get("current_a"))
    if got is None or got < 1 or got >= ordered_a - MARGIN_A:
        return None
    o = int(round(ordered_a))
    g = f"{got:.0f}"
    out_lim = _num(reading.get("output_limit_a"))
    max_lim = _num(reading.get("max_limit_a"))
    if out_lim is not None and 0 < out_lim <= ordered_a - 1:
        return (f"Laddboxen håller bilen på {out_lim:.0f} A, vi beställde {o} A. Laddboxens lastbalansering eller kretsens "
                f"gräns tar ner strömmen, troligen för att resten av huset drar mycket just nu.")
    if max_lim is not None and 0 < max_lim <= ordered_a - 1:
        return f"Laddboxens maxgräns är {max_lim:.0f} A, vi beställde {o} A. Gränsen ändras i laddboxens app."
    why = str(reading.get("reason_no_current") or "").strip()
    if out_lim is None and max_lim is None and not why:
        # Laddboxens gränser går inte att läsa (Easee: sensorerna är avstängda som standard i HA)
        return (f"Bilen tar bara {g} A, vi beställde {o} A. Antingen begränsar bilen själv (egen laddare, laddgräns, "
                f"kallt batteri) eller laddboxens lastbalansering. Aktivera laddboxens sensorer för strömgränser i "
                f"Home Assistant så kan EnergyWizard säga vilket.")
    if why.lower() not in _BENIGN:
        return f"Bilen laddar med {g} A, vi beställde {o} A. Laddboxen anger: {why.replace('_', ' ')}."
    return (f"Bilen tar bara {g} A, vi beställde {o} A. Det är bilen som begränsar: dess egen laddare, en laddgräns "
            f"i bilen eller ett kallt batteri.")


class HoldWatch:
    """Per bil: rapporterar en förklaring först när den hållit i sig HOLD_MIN minuter, och slutar när den försvinner."""

    def __init__(self):
        self._since: dict = {}

    def step(self, car_id, ordered_a, reading, now_ts: float):
        txt = explain(ordered_a, reading)
        if txt is None:
            self._since.pop(car_id, None)
            return None
        t0 = self._since.setdefault(car_id, now_ts)
        return txt if now_ts - t0 >= HOLD_MIN * 60 else None
