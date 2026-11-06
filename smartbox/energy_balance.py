"""Små, testbara regler för husets energibalans (sol + nät = hus + batteri)."""


def plausible_battery_w(power_w, max_power_w=None) -> float:
    """Batteriets effekt (+ = laddar), eller 0 om givaren är orimlig: mer än 1,5 × batteriets max (minst 10 kW).
    #139: en givare i kWh eller växelriktarens totala effekt gav 18,2 kW "urladdning"."""
    if not isinstance(power_w, (int, float)) or power_w != power_w:
        return 0.0
    limit = max(float(max_power_w or 0), 10000.0) * 1.5
    return 0.0 if abs(power_w) > limit else float(power_w)


def pv_floor_from_export(raw_pv_w, grid_net_w, battery_w) -> float:
    """Solproduktionen kan aldrig vara mindre än den export solen står för (fryst solgivare, t.ex. SolarEdge).
    grid_net_w: + = köper, - = säljer. battery_w: + = laddar. Ett batteri som laddar ur och säljer står för en del av
    exporten, och den delen är inte sol (#175: 7,7 kW "sol" i mörker när batteriet sålde 7,7 kW)."""
    raw = raw_pv_w or 0.0
    export_from_sun = max(0.0, -(grid_net_w or 0.0) - max(0.0, -(battery_w or 0.0)))
    return max(raw, export_from_sun)


def pump_el_w(pump_data: dict | None, estimate_w) -> float:
    """Värmepumpens eleffekt (W) för lastnedbrytningen och COP: uppmätt (compressor_power_w, t.ex. NIBE lokal
    register 1048 eller HeishaMon) när drivrutinen ger den, annars uppskattad ur framledningen när kompressorn går.
    #178: kurvan gav 2192 W när pumpen mätte 437 W (24 Hz), så "Oförklarat" blev för litet."""
    p = pump_data or {}
    measured = p.get("compressor_power_w")
    if isinstance(measured, (int, float)) and measured == measured and 0 <= measured < 30000:
        return float(measured)
    if p.get("compressor_running") in (1, True):
        return float(estimate_w(p.get("forward_temp")))
    return 0.0
