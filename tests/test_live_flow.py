

def test_okant_kompressorlage_star_inte_som_vilar():
    """#184: NIBE via myUplink utan kompressorgivare visades som 'Vilar' medan huset drog 5 kW."""
    import live_flow
    d = live_flow.nodes({"compressor_power_kw": 0.0, "indoor_temp": 17.7, "net_power": 4800})
    vp = next(n for n in d["nodes"] if n["key"] == "varmepump")
    assert vp["detail"] == "inne 17.7 °C" and not vp["active"]
    d = live_flow.nodes({"compressor_running": 0, "compressor_power_kw": 0.0, "indoor_temp": 17.7})
    assert next(n for n in d["nodes"] if n["key"] == "varmepump")["detail"] == "Vilar · inne 17.7 °C"
