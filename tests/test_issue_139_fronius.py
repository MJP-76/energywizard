"""#139: Fronius GEN24 med separata givare för batteriets laddning och urladdning - guiden ska använda dem."""
from discovery import discover_house

P = "sensor.fronius_symo_gen24_8_0_plus"


def ent(e, n, dc=None, u=None, st="0", d="dev_fr", dom=None):
    return {"e": e, "n": n, "a": None, "d": d, "dn": "Fronius Symo GEN24 8.0 Plus", "m": "Fronius", "mo": "Symo GEN24", "dc": dc, "u": u, "st": st}


ENTS = [ent(f"{P}_storage_state_of_charge", "Storage state of charge", "battery", "%", "88"),
        ent(f"{P}_storage_charging_power", "Storage charging power", "power", "W", "0"),
        ent(f"{P}_storage_discharging_power", "Storage discharging power", "power", "W", "6000"),
        ent(f"{P}_storage_charge_rate", "Storage charge rate", "power", "W", "18200"),
        ent(f"{P}_load", "Load", "power", "W", "1200"),
        ent(f"{P}_mppt_module_0_dc_power", "MPPT module 0 DC power", "power", "W", "0"),
        ent("select.fronius_symo_gen24_8_0_plus_storage_control_mode", "Storage Control Mode", st="Auto")]


def test_fronius_far_laddnings_och_urladdningseffekt():
    b = discover_house(ENTS)["battery"]
    e = b["generic_suggestion"]["entities"]
    assert e.get("power_charge") == f"{P}_storage_charging_power"
    assert e.get("power_discharge") == f"{P}_storage_discharging_power"
    assert "power" not in e                                    # ingen ensam (fel) effektgivare
