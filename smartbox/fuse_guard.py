"""
fuse_guard.py - termisk säkringsmodell för effektvakten (elbilsladdning mot huvudsäkringen).

Ersätter den tidigare regeln "ledig ström = säkring - husets minutsnitt (värsta fasen)", som
strypte bilen varje gång en kort topp (vattenkokare, ugn) syntes i minutsnittet - trots att en
riktig säkring tål korta toppar. En säkring löser ut av VÄRME, inte av en enskild avläsning.

Byggd mot FTW:s dokumenterade säkerhetsmodell (github.com/srcfl/ftw, docs/safety.md,
"The EV hard limit treats the main fuse as heat, not as one reading"):

  - Varje fas I² lågpassfiltreras med 60 s tidskonstant ("värmen" i säkringen).
  - Arbetsgräns per fas = säkringens märkvärde - valfri säkerhetsmarginal.
  - STRYPNING: när den filtrerade strömmen går över gränsen, eller OMEDELBART när en
    enskild avläsning går över 1,2 × märkvärdet.
  - ÖKNING för en bil som redan laddar: bara om ökningen ryms under gränsen, räknat på det
    högsta av avläsningen och den filtrerade strömmen - och aldrig inom 20 s efter en strypning.
  - START av en bil som står still: räknar på avläsningen som den är (+ den nya strömmen); den
    filtrerade strömmen spärrar bara medan den själv ligger över gränsen.
  - En fas som EXPORTERAR (negativ ström från Tibber) stryps aldrig för - mindre bil-last
    skulle bara öka exporten. Den räknas utan sin värme vid ökning/start.

Avsteg från FTW, medvetet: FTW ser gammal mätardata som ett skäl att stoppa all laddning.
Här faller `ev_cap_a()` istället tillbaka på None (= gpm.py använder den gamla formeln), så
ett Tibber-avbrott inte stoppar nattens laddning. Det är samma beteende som innan modellen
fanns - inte sämre, men inte heller FTW:s striktare nivå.

Rena funktioner/klass utan I/O - testas i tests/test_fuse_guard.py.
"""

import math
import time

TAU_S = 60.0               # tidskonstant för I²-filtret
TRIP_FACTOR = 1.2          # en enskild avläsning över 1,2 × märkvärdet stryper omedelbart
RECOVERY_S = 20.0          # ingen ökning inom så här lång tid efter en strypning
STALE_S = 60.0             # äldre mätdata än så här = modellen svarar inte (None)
EV_RUNNING_A = 1.0         # bilen räknas som laddande om den drar minst så här på någon fas


class FuseThermalModel:
    def __init__(self, tau_s=TAU_S, trip_factor=TRIP_FACTOR, recovery_s=RECOVERY_S, stale_s=STALE_S):
        self.tau_s = float(tau_s)
        self.trip_factor = float(trip_factor)
        self.recovery_s = float(recovery_s)
        self.stale_s = float(stale_s)
        self._heat = None          # filtrerat I² per fas
        self._last = None          # senaste avläsning per fas (signerad, A)
        self._last_ts = None
        self._last_cut_ts = None

    # ---------- mätning ----------

    def update(self, phase_currents, ts=None):
        """Matar in en avläsning (A per fas, negativ = export). Anropas var 10:e sekund."""
        if not phase_currents or any(c is None for c in phase_currents):
            return
        ts = time.time() if ts is None else float(ts)
        cur = [float(c) for c in phase_currents]
        sq = [c * c for c in cur]
        if self._heat is None or len(self._heat) != len(cur) or self._last_ts is None:
            self._heat = sq   # första avläsningen: utgå från att den har legat så ett tag
        else:
            dt = max(0.0, ts - self._last_ts)
            alpha = 1.0 - math.exp(-dt / self.tau_s) if self.tau_s > 0 else 1.0
            self._heat = [h + (s - h) * alpha for h, s in zip(self._heat, sq)]
        self._last = cur
        self._last_ts = ts

    def is_fresh(self, ts=None):
        ts = time.time() if ts is None else float(ts)
        return self._last_ts is not None and (ts - self._last_ts) <= self.stale_s

    def filtered_a(self):
        """Filtrerad ("termisk") ström per fas, A RMS. Alltid >= 0."""
        return [math.sqrt(max(0.0, h)) for h in self._heat] if self._heat else []

    def last_a(self):
        return list(self._last) if self._last else []

    # ---------- beslut ----------

    def _limit(self, fuse_a, margin_a):
        return float(fuse_a) - max(0.0, float(margin_a or 0.0))

    def check(self, fuse_a, margin_a=0.0):
        """('ok'|'overload'|'trip', överskott i A). Bara IMPORTERANDE faser räknas.
        trip = enskild avläsning över 1,2 × märkvärdet (agera direkt i 10-sekundersloopen).
        overload = filtrerad ström över arbetsgränsen."""
        if not self._last:
            return ("ok", 0.0)
        limit = self._limit(fuse_a, margin_a)
        trip_level = self.trip_factor * float(fuse_a)
        trip_excess = 0.0
        over_excess = 0.0
        for inst, filt in zip(self._last, self.filtered_a()):
            if inst <= 0:
                continue   # exporterande fas - aldrig strypning för den
            if inst > trip_level:
                trip_excess = max(trip_excess, inst - limit)
            if filt > limit:
                over_excess = max(over_excess, filt - limit)
        if trip_excess > 0:
            return ("trip", trip_excess)
        if over_excess > 0:
            return ("overload", over_excess)
        return ("ok", 0.0)

    def mark_cut(self, ts=None):
        self._last_cut_ts = time.time() if ts is None else float(ts)

    def in_recovery(self, ts=None):
        ts = time.time() if ts is None else float(ts)
        return self._last_cut_ts is not None and (ts - self._last_cut_ts) < self.recovery_s

    def ev_cap_a(self, fuse_a, ev_phase_a, margin_a=0.0, ts=None):
        """Högsta tillåtna totala bilström (A per fas, samma enhet som laddargränserna) just nu.

        ev_phase_a = vad bilarna faktiskt drar per fas (summa av alla laddare).
        None = modellen har ingen färsk mätdata - anroparen använder sin gamla formel.
        En strypning registreras automatiskt (startar 20 s-spärren mot ny ökning)."""
        ts = time.time() if ts is None else float(ts)
        if not self.is_fresh(ts) or not self._last:
            return None
        n = len(self._last)
        ev = [float(x or 0.0) for x in (list(ev_phase_a or []) + [0.0] * n)[:n]]
        limit = self._limit(fuse_a, margin_a)
        trip_level = self.trip_factor * float(fuse_a)
        filt = self.filtered_a()
        ev_now = max(ev) if ev else 0.0
        running = ev_now >= EV_RUNNING_A
        recovering = self.in_recovery(ts)

        caps = []
        cut = False
        for inst, f, e in zip(self._last, filt, ev):
            exporting = inst <= 0
            if running:
                if not exporting and inst > trip_level:
                    caps.append(e - (inst - limit)); cut = True          # omedelbar strypning
                elif not exporting and f > limit:
                    caps.append(e - (f - limit)); cut = True             # termisk överlast
                else:
                    reading = inst if exporting else max(inst, f)
                    room = 0.0 if recovering else max(0.0, limit - reading)
                    caps.append(e + room)                                # håll, öka bara det som ryms
            else:
                if not exporting and f > limit:
                    caps.append(0.0)                                     # fasen är redan varm: ingen start
                else:
                    caps.append(limit - (inst - e))                      # start: avläsningen som den är
        if cut:
            self.mark_cut(ts)
        cap = min(caps) if caps else 0.0
        return max(0, int(math.floor(cap)))


def fast_trip_limits(model, fuse_a, sent_limits, margin_a=0.0, min_charge_a=6, ts=None):
    """10-sekundersloopens nödbroms. Returnerar {car_id: ny_gräns} för de bilar som ska strypas
    NU (en avläsning över 1,2 × säkringen), annars {}. Varje laddande bil sänks med hela
    överskottet - försiktigt om flera bilar delar fas, men det är en nödbroms, inte fördelning;
    minutloopen fördelar om när 20 s-spärren släppt."""
    state, excess = model.check(fuse_a, margin_a)
    if state != "trip":
        return {}
    need = int(math.ceil(excess))
    out = {}
    for car_id, sent in (sent_limits or {}).items():
        if sent and sent > 0:
            new = int(sent) - need
            out[car_id] = new if new >= min_charge_a else 0
    if out:
        model.mark_cut(ts)
    return out
