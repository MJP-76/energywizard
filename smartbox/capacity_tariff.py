"""capacity_tariff.py - effektavgift efter månadens högsta timmar (#141: Norges kapasitetsledd/effektledd, och svenska
nätbolag som tar betalt efter snittet av 3-5 högsta timmar).

Avgiften bestäms av snittet av månadens N högsta timmar (ofta på N olika dygn) och hamnar i ett trappsteg. Den smarta
gränsen för timmen som pågår är så hög som möjligt utan att snittet går upp ett steg:

    om timmen blir en av de N högsta ersätter den den lägsta av dem (eller dygnets egen topp om samma dygn redan finns)
    nytt snitt = (summa topp-N - den som ersätts + x) / N  <=  stegets övre gräns
    =>  x <= stegets övre gräns × N - (summa topp-N - den som ersätts)

En timme som ändå inte kommer in bland de N högsta (x <= den lägsta av dem) påverkar inte avgiften alls, så gränsen
är aldrig lägre än den. Inställningen (ew_settings "capacity_tariff"): {"enabled", "top_n", "distinct_days", "steps"}.
Ren logik i limit_kw() - testas i tests/test_capacity_tariff.py; main.py använder den som effektvaktens gräns.
"""
# Vanlig norsk trappa (kW) - de flesta nätbolag använder dessa steg; går att ändra i inställningen
DEFAULT_STEPS = [2, 5, 10, 15, 20, 25, 50, 75, 100]


def top_hours(hour_peaks, top_n=3, distinct_days=True):
    """hour_peaks = [(dygn, kW)] för månadens timmar -> de N högsta [(dygn, kW)], en per dygn om distinct_days."""
    if distinct_days:
        best = {}
        for day, kw in hour_peaks:
            if kw is not None and kw > best.get(day, -1.0):
                best[day] = kw
        items = list(best.items())
    else:
        items = [(d, k) for d, k in hour_peaks if k is not None]
    return sorted(items, key=lambda x: x[1], reverse=True)[:max(1, int(top_n))]


def step_for(avg_kw, steps):
    """(nedre, övre) gräns för trappsteget som snittet ligger i."""
    lo = 0.0
    for s in sorted(float(x) for x in steps):
        if avg_kw <= s:
            return lo, s
        lo = s
    return lo, float("inf")


def limit_kw(hour_peaks, today, top_n=3, distinct_days=True, steps=None, target_kw=None):
    """-> (gräns i kW för timmen som pågår, info). today = dygnet för timmen som pågår. target_kw = trappsteget man siktar
    på (övre gräns, t.ex. 10): gränsen räknas mot det högsta av målsteget och steget man redan hamnat i - annars blir den
    orimligt låg i början av månaden när bara några timmar finns."""
    steps = steps or DEFAULT_STEPS
    n = max(1, int(top_n))
    pad = lambda v: (v + [0.0] * n)[:n]
    cur = pad([k for _d, k in top_hours(hour_peaks, n, distinct_days)])
    avg_now = sum(cur) / n
    lo, hi = step_for(avg_now, steps)
    if target_kw:
        hi = max(hi, float(target_kw))
        lo = max([float(x) for x in steps if float(x) < hi] + [0.0])
    # Om timmen som pågår blir en av topparna ersätter den dygnets egen topp (olika dygn) eller den lägsta toppen
    others = pad([k for _d, k in top_hours([(d, k) for d, k in hour_peaks if not (distinct_days and d == today)], n, distinct_days)])
    today_best = max([k for d, k in hour_peaks if d == today] + [0.0]) if distinct_days else 0.0
    base = sorted(others, reverse=True)[:n - 1]                 # de N-1 högsta som står kvar
    free = max(min(others), today_best)                          # under detta påverkas inte snittet alls
    room = hi * n - sum(base) if hi != float("inf") else float("inf")
    limit = max(free, room)
    info = {"avg_kw": round(avg_now, 2), "step": [lo, hi], "top": [round(k, 2) for k in cur],
            "free_below_kw": round(free, 2), "limit_kw": round(limit, 2) if limit != float("inf") else None}
    return limit, info
