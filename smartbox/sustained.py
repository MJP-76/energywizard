"""sustained.py - ett villkor räknas först när det hållit i sig en viss tid.

2026-11-06: innetemperaturen föll från 21,8 till 14,6 °C på sju minuter (vädring/öppen dörr nära givarna) och var
tillbaka över 20 °C en kvart senare. Motorn skickade "Kallt inomhus!" och tvingade värmen på oavsett elpris direkt.
Nu agerar den på kallt inne först när det varit kallt i COLD_CONFIRM_MIN minuter i följd.
"""
from datetime import timedelta

COLD_CONFIRM_MIN = 30


class Sustained:
    def __init__(self, minutes: float = COLD_CONFIRM_MIN):
        self.span = timedelta(minutes=minutes)
        self.since = None

    def update(self, condition: bool, now) -> bool:
        """condition = villkoret just nu (None räknas som falskt). Returnerar True när det varit sant minst `minutes`
        minuter i följd. Ett enda varv utan villkoret nollställer."""
        if not condition:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        return now - self.since >= self.span
