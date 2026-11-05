"""battery_follow.py - följer husbatteriet det EnergyWizard säger åt det?

Önskemål (Discord, efter att någon undrat varför batteriet laddade när det skulle ladda ur och appen inte sa
något): jämför det senast skickade kommandot med batteriets uppmätta effekt. Avviker det i mer än FOLLOW_MIN
minuter i rad blir läget "följer inte" - det visas i appen och på webben och ger en notis (kategorin "batteri",
går att stänga av). Kommer batteriet i fas igen återgår läget till "följer".

Ingen varning när avvikelsen har en naturlig förklaring: fullt batteri som inte kan ladda mer, batteriet vid
reservnivån som inte får ladda ur mer, eller "auto"/självförbrukning (då bestämmer batteriet själv).
Ren logik i step() - testas i tests/test_battery_follow.py.
"""
FOLLOW_MIN = 5
TOL_W = 150            # under så här mycket effekt räknas batteriet som stilla
FULL_SOC = 98


def _kw(w):
    return f"{abs(w) / 1000:.1f} kW" if abs(w) >= 1000 else f"{abs(w):.0f} W"


def mismatch(intent, wanted_w, actual_w, soc, reserve_soc):
    """Text som beskriver avvikelsen, eller None om batteriet gör det det ska (eller har en naturlig förklaring)."""
    if actual_w is None or intent in (None, "auto"):
        return None
    want = f" {_kw(wanted_w)}" if wanted_w else ""
    doing = ("laddar " + _kw(actual_w)) if actual_w > TOL_W else ("laddar ur " + _kw(actual_w)) if actual_w < -TOL_W else "står still"
    if intent == "charge":
        if actual_w > TOL_W or (soc is not None and soc >= FULL_SOC):
            return None
        return f"Bad om laddning{want}, men batteriet {doing}."
    if intent == "discharge":
        if actual_w < -TOL_W or (soc is not None and reserve_soc is not None and soc <= reserve_soc + 1):
            return None
        return f"Bad om urladdning{want}, men batteriet {doing}."
    if intent in ("hold", "idle"):
        # "sparas" får ta emot sol (laddning) men ska inte ladda ur; "vila" ska stå still
        if intent == "hold" and actual_w >= -TOL_W * 2:
            return None
        if intent == "idle" and abs(actual_w) <= TOL_W * 2:
            return None
        return f"Bad batteriet att {'spara laddningen' if intent == 'hold' else 'vila'}, men det {doing}."
    return None


class FollowWatch:
    def __init__(self):
        self.since = None
        self.text = None
        self.alerted = False

    def step(self, intent, wanted_w, actual_w, soc, reserve_soc, now_s):
        """Returnerar (läge, text, ny_varning): läge = "following" | "checking" | "not_following" | None (inget att
        kontrollera). ny_varning = True första gången ett avvikande läge blir "not_following" (skicka notis då)."""
        if intent in (None, "auto") or actual_w is None:
            self.since, self.text, self.alerted = None, None, False
            return None, None, False
        txt = mismatch(intent, wanted_w, actual_w, soc, reserve_soc)
        if txt is None:
            self.since, self.text, self.alerted = None, None, False
            return "following", None, False
        if self.since is None:
            self.since = now_s
        self.text = txt
        if now_s - self.since < FOLLOW_MIN * 60:
            return "checking", txt, False
        new = not self.alerted
        self.alerted = True
        return "not_following", txt, new
