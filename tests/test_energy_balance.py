"""#175: solkorrigeringen får inte räkna batteriets försäljning som sol."""
import energy_balance as eb


def test_batteri_som_saljer_blir_inte_sol():
    # 19:06, mörkt: batteriet laddar ur 8,7 kW, säljer 7,7 kW, huset drar 1 kW, solgivaren 0 W
    assert eb.pv_floor_from_export(0, -7700, -8700) == 0


def test_fryst_solgivare_korrigeras_fortfarande_uppat():
    # SolarEdge fast på 5876 W medan huset säljer 7000 W och batteriet står still
    assert eb.pv_floor_from_export(5876, -7000, 0) == 7000
    # batteriet laddar (+): hela exporten är sol
    assert eb.pv_floor_from_export(1000, -3000, 2000) == 3000
    # delvis: batteriet säljer 2 kW av 5 kW export -> minst 3 kW sol
    assert eb.pv_floor_from_export(0, -5000, -2000) == 3000


def test_orimlig_batterieffekt_raknas_som_noll():
    assert eb.plausible_battery_w(-18200, 5000) == 0.0
    assert eb.plausible_battery_w(-8700, 10000) == -8700
    assert eb.plausible_battery_w(None) == 0.0 and eb.plausible_battery_w(float("nan")) == 0.0


def test_uppmatt_pumpeffekt_gar_fore_kurvan():
    """#178: NIBE lokal mätte 437 W (24 Hz), kurvan sa 2192 W."""
    est = lambda fwd: 2192.0
    assert eb.pump_el_w({"compressor_running": 1, "forward_temp": 30, "compressor_power_w": 437}, est) == 437
    assert eb.pump_el_w({"compressor_running": 1, "forward_temp": 30}, est) == 2192        # utan mätning: kurvan
    assert eb.pump_el_w({"compressor_running": 0}, est) == 0
    assert eb.pump_el_w({"compressor_running": 0, "compressor_power_w": 25}, est) == 25     # mätt vila räknas
    assert eb.pump_el_w({"compressor_running": 1, "compressor_power_w": float("nan")}, est) == 2192
    assert eb.pump_el_w(None, est) == 0
