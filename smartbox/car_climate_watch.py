"""car_climate_watch.py - följer upp "värme på" för bilen tills bilen faktiskt värmer, eller säger till att den inte gjorde det.

2026-11-04: värmen i Leafen startades från appen två gånger en kall morgon. Home Assistant tog emot kommandot, men
Nissans moln startade aldrig klimatet i bilen - och ingen märkte det. Appen sparade överstyrningen
"<bil>_climate" (t.ex. "21.0") med en kommentar om att motorn följer upp den, men ingen kod läste den.

Nu: så länge överstyrningen säger värme och bilens climate-entitet fortfarande är av skickas kommandot om efter
RESEND_AFTER (Nissan missar ofta första försöket), högst MAX_TRIES gånger. Startar värmen: klart (överstyrningen
nollställs). Har den inte startat efter GIVE_UP: en avisering och överstyrningen nollställs, så att den inte
ligger kvar och skickar på nytt senare. Ren logik i step() - testas i tests/test_car_climate_watch.py.
"""

RESEND_AFTER_S = 180
MAX_TRIES = 3
GIVE_UP_S = 12 * 60


class ClimateWatch:
    def __init__(self):
        self.since = None
        self.tries = 0
        self.last_send = None

    def step(self, wanted_temp, climate_state, now_s):
        """wanted_temp = överstyrningens värde (None/"off" = ingen värme begärd), climate_state = entitetens läge.
        Returnerar en av: None (inget att göra), "resend", "ok", "give_up"."""
        on_requested = wanted_temp not in (None, "", "off")
        if not on_requested:
            self.since, self.tries, self.last_send = None, 0, None
            return None
        if self.since is None:                       # nyss begärd (appen skickade själv första kommandot)
            self.since, self.tries, self.last_send = now_s, 0, now_s
        if climate_state not in (None, "", "off", "unavailable", "unknown"):
            self.since, self.tries, self.last_send = None, 0, None
            return "ok"
        if now_s - self.since >= GIVE_UP_S:
            self.since, self.tries, self.last_send = None, 0, None
            return "give_up"
        if self.tries < MAX_TRIES and now_s - self.last_send >= RESEND_AFTER_S:
            self.tries += 1
            self.last_send = now_s
            return "resend"
        return None
