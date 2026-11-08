"""ev_in_meter.py - ser mätaren elbilen? (idé från Energy Pilot/evsplit, Emil 2026-11-08)

EnergyWizard räknar husets förbrukning från mätaren (sol + nät - batteri) och drar sedan av elbilens laddning för
husets grundlast, säkringsmarginalen och prognoserna. Det stämmer bara om mätaren faktiskt mäter laddboxen. Sitter
laddboxen bakom en egen mätare (eller är "mätaren" en undermätare för huset), dras bilen av fast den aldrig fanns med:
grundlasten blir för låg och säkringsmarginalen fel.

Avgörs ur historiken: timmar då bilen laddade jämförs med samma timme på dygnet utan laddning. Steg husets förbrukning
med ungefär lika mycket som bilen tog (kvot nära 1) ser mätaren bilen; steg den nästan inte alls (kvot nära 0) gör den
det inte. För få laddtimmar eller en kvot däremellan = okänt (inget ändras). Ren logik + en databasfråga; motorn kör
det en gång per dygn och sparar svaret i ew_settings ("ev_in_meter").
"""
from statistics import median

MIN_HOURS = 6           # så många laddtimmar (med jämförelsetimmar) innan vi säger något
MIN_EV_KW = 1.0         # timmen räknas som laddtimme om bilen tog minst så här mycket i snitt


def detect(hours):
    """hours: [(timme_på_dygnet, hus_kw, bil_kw)] per klocktimme. Returnerar (svar, kvot, antal):
    svar True = mätaren ser bilen, False = inte, None = vet inte än."""
    quiet = {}
    for h, house, ev in hours:
        if ev < 0.1:
            quiet.setdefault(h, []).append(house)
    ratios = []
    for h, house, ev in hours:
        base = quiet.get(h)
        if ev >= MIN_EV_KW and base and len(base) >= 3:
            ratios.append((house - median(base)) / ev)
    if len(ratios) < MIN_HOURS:
        return None, None, len(ratios)
    r = median(ratios)
    if r >= 0.6:
        return True, round(r, 2), len(ratios)
    if r <= 0.25:
        return False, round(r, 2), len(ratios)
    return None, round(r, 2), len(ratios)


SQL = """SELECT extract(hour FROM h AT TIME ZONE 'Europe/Stockholm')::int, hus, bil FROM (
           SELECT date_trunc('hour', timestamp) h, avg(house_consumption_w) / 1000.0 hus,
                  avg(COALESCE(ev_power_kw, 0) + COALESCE(ev_carport_power_kw, 0)) bil, count(*) n
           FROM sensor_log WHERE timestamp > NOW() - INTERVAL '60 days' AND house_consumption_w IS NOT NULL
           GROUP BY 1) x WHERE n >= 30"""


def from_db(get_db):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        return detect([(int(h), float(a or 0), float(b or 0)) for h, a, b in cur.fetchall()])


def text(answer, ratio) -> str | None:
    if answer is False:
        return (f"Mätaren verkar inte se elbilens laddning (husets förbrukning steg bara {ratio:.0%} av det bilen tog). "
                f"EnergyWizard drar därför inte längre av bilen från husets förbrukning. Sitter laddboxen bakom en egen "
                f"mätare stämmer det; annars: kontrollera husets mätare i installationen.")
    return None
