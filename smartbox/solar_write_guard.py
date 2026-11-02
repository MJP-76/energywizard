"""
solar_write_guard.py - hur ofta exportgränsen får skrivas till växelriktaren.

Växelriktare sparar sådana inställningar i flashminne, som tål ett begränsat antal
skrivningar. Home Assistants officiella SolarEdge Modbus-dokumentation säger det rakt ut:
"These settings live in the inverter's flash memory ... An automation that writes one every
few minutes will wear it out." Samma sak gäller Fronius/Growatt-register.

Solregulatorn i gpm.py (Prio 2, PI mot 0 W export vid minuspris) räknar fram ett nytt värde
varje minut. Utan spärr blir det upp till 60 skrivningar i timmen. Regeln här:

  - Börja strypa (från 100 %) och sluta strypa (till 100 %) skrivs DIREKT - det är det som
    spelar roll för plånboken och för att inte lämna växelriktaren strypt.
  - Gå till 0 % skrivs direkt (djupt minuspris).
  - Finjustering däremellan: högst var MIN_INTERVAL och bara vid minst DEADBAND_PCT ändring.

Kostnaden är att regulatorn landar långsammare på exakt 0 W - lite export eller import
under några minuter - mot en växelriktare som inte slits ut.
"""

from datetime import timedelta

MIN_INTERVAL = timedelta(minutes=5)
DEADBAND_PCT = 5


def should_write(new_pct, last_sent_pct, last_write_at, now):
    if new_pct is None:
        return False
    if last_sent_pct is None or last_write_at is None:
        return True
    new_pct, last = round(float(new_pct)), round(float(last_sent_pct))
    if new_pct == last:
        return False
    if new_pct in (0, 100) or last == 100:
        return True                                     # start, stopp och helt stängt: direkt
    if abs(new_pct - last) < DEADBAND_PCT:
        return False
    return (now - last_write_at) >= MIN_INTERVAL
