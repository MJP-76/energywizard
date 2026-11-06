"""car_climate_watch.py - följer upp "värme på" för bilen tills bilen faktiskt värmer, eller säger till att den inte gjorde det.

2026-11-04: värmen i Leafen startades från appen två gånger en kall morgon. Home Assistant tog emot kommandot, men
Nissans moln startade aldrig klimatet i bilen - och ingen märkte det. Appen sparade överstyrningen
"<bil>_climate" (t.ex. "21.0") med en kommentar om att motorn följer upp den, men ingen kod läste den.

Nu: så länge överstyrningen säger värme och bilens climate-entitet fortfarande är av skickas kommandot om efter
RESEND_AFTER (Nissan missar ofta första försöket), högst MAX_TRIES gånger. Startar värmen: klart (överstyrningen
nollställs). Har den inte startat efter GIVE_UP: en avisering och överstyrningen nollställs, så att den inte
ligger kvar och skickar på nytt senare. Ren logik i step() - testas i tests/test_car_climate_watch.py.

2026-11-06 (hållfas): när värmen väl startat hålls temperaturen. Bilar stänger själva av klimatet när kupén nått
temperaturen eller efter en stund (Leafen efter ~15 min). Har klimatet varit av HOLD_RECHECK_S (10 min) kollas
kupétemperaturen; ligger den mer än HOLD_TOL_C under önskad (eller rapporterar bilen ingen) startas värmen igen, högst
MAX_REHEATS gånger. Hållfasen slutar HOLD_MAX_S efter knapptrycket eller när användaren stänger av värmen ("done" ->
anroparen nollställer överstyrningen).
"""

RESEND_AFTER_S = 180
MAX_TRIES = 3
GIVE_UP_S = 12 * 60
HOLD_RECHECK_S = 10 * 60
HOLD_MAX_S = 60 * 60
HOLD_TOL_C = 1.0
MAX_REHEATS = 3
_OFF = (None, "", "off", "unavailable", "unknown")


class ClimateWatch:
    def __init__(self):
        self._reset()

    def _reset(self):
        self.since = None          # startfas: när kommandot skickades (None = ingen startfas pågår)
        self.tries = 0
        self.last_send = None
        self.requested_at = None   # när värmen begärdes (hållfasens tidsgräns räknas härifrån)
        self.hold_since = None     # hållfas: värmen har startat
        self.off_at = None         # hållfas: när klimatet senast sågs gå av
        self.reheats = 0

    def step(self, wanted_temp, climate_state, now_s, cabin_temp=None):
        """wanted_temp = överstyrningens värde (None/"off" = ingen värme begärd), climate_state = entitetens läge,
        cabin_temp = kupétemperaturen (None = okänd). Returnerar en av: None (inget att göra), "resend", "ok",
        "give_up", "reheat" (värm igen - temperaturen hölls inte), "done" (hållfasen slut)."""
        if wanted_temp in (None, "", "off"):
            self._reset()
            return None
        if self.requested_at is None:
            self.requested_at = now_s
        on = climate_state not in _OFF
        if self.hold_since is not None:
            if now_s - self.requested_at >= HOLD_MAX_S:
                self._reset()
                return "done"
            if on:
                self.off_at = None
                return None
            if self.off_at is None:
                self.off_at = now_s
                return None
            if now_s - self.off_at < HOLD_RECHECK_S:
                return None
            self.off_at = now_s                                   # nästa koll om 10 min
            try:
                target = float(wanted_temp)
            except (TypeError, ValueError):
                target = 21.0
            if (cabin_temp is not None and cabin_temp >= target - HOLD_TOL_C) or self.reheats >= MAX_REHEATS:
                return None
            self.reheats += 1
            self.hold_since, self.since, self.tries, self.last_send = None, now_s, 0, now_s
            return "reheat"
        if self.since is None:                       # nyss begärd (appen skickade själv första kommandot)
            self.since, self.tries, self.last_send = now_s, 0, now_s
        if on:
            self.since, self.tries, self.last_send = None, 0, None
            self.hold_since, self.off_at = now_s, None
            return "ok"
        if now_s - self.since >= GIVE_UP_S:
            self._reset()
            return "give_up"
        if self.tries < MAX_TRIES and now_s - self.last_send >= RESEND_AFTER_S:
            self.tries += 1
            self.last_send = now_s
            return "resend"
        return None
