"""#134 lampbevakning/solgräns bara med val, #136 tidslinjen bara med husets bilar/spa, #139 effekt i kW,
#140 generiska laddboxen ger laddeffekt."""
from datetime import datetime, timedelta
from unittest.mock import patch
import zoneinfo

import homeassistant as H
import timeline

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")


def _states(d):
    return {e: {"entity_id": e, "state": str(v[0]), "attributes": {"unit_of_measurement": v[1]}} for e, v in d.items()}


def test_get_power_w_raknar_om_kw():
    with patch.object(H, "_states_cache", _states({"sensor.bat": (1.5, "kW"), "sensor.w": (700, "W"), "sensor.x": (3, "")})):
        assert H.get_power_w("sensor.bat") == 1500
        assert H.get_power_w("sensor.w") == 700
        assert H.get_power_w("sensor.x") == 3


def test_generiska_laddboxen_ger_power_kw():
    from drivers.charger_generic import GenericChargerDriver
    st = _states({"sensor.garo_power": (7.2, "kW"), "sensor.garo_status": ("charging", ""), "sensor.garo_w": (3600, "W")})
    with patch.object(H, "_states_cache", st):
        d = GenericChargerDriver(id="garo", entities={"power_kw": "sensor.garo_power", "status": "sensor.garo_status"}).read_state()
        assert d["power_kw"] == 7.2
        d = GenericChargerDriver(id="garo", entities={"power": "sensor.garo_w"}).read_state()
        assert d["power_kw"] == 3.6
        assert GenericChargerDriver(id="garo", entities={}).read_state()["power_kw"] is None


def test_tidslinjen_visar_bara_husets_bilar_och_spa():
    now = datetime(2026, 11, 5, 12, 0, tzinfo=SWE)
    h = now.replace(minute=0) - timedelta(hours=1)
    past = {h: {"price": 1.0, "solar_kw": 0.2, "compressor": 0.5, "spa": None, "ev": {"tesla": 7.0}}}
    d = timeline.build(now, past, {now.replace(minute=0): 1.0}, {}, {}, {}, car_ids=["tesla"], car_names={"tesla": "Tesla Model Y"},
                       has_spa=False, has_heat=True)
    labels = [ln["label"] for ln in d["lanes"]]
    assert labels == ["Värmepump", "Tesla Model Y"]


def test_tidslinjen_kopplar_laddbox_till_ratt_bil():
    class _Res:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

        def scalar(self):
            return None

    class _Conn:
        def execute(self, q, params=None):
            s = str(q)
            if "FROM sensor_log WHERE timestamp >= :start" in s:
                h = datetime(2026, 11, 5, 11, 0)
                return _Res([(h, 1.0, 200.0, 0.5, 0, 7.0, None, None)])     # laddbox 1 laddar 7 kW
            return _Res([])

        def rollback(self):
            pass
    now = datetime(2026, 11, 5, 12, 0, tzinfo=SWE)
    d = timeline.load(_Conn(), now=now, cars=[("tesla", "Tesla", "ev_power_kw")], has_spa=False, has_heat=False)
    labels = [ln["label"] for ln in d["lanes"]]
    assert labels == ["Tesla"]
    assert any(v for v in d["lanes"][0]["values"] if v)


def test_vaxelriktare_utan_batteri_foreslas_inte_som_batteri():
    """srcfl/ftw#1669: en hybridväxelriktare med bara solceller har batterisensorer på 0 % / 0 W."""
    from discovery import discover_house

    def ent(e, n, dc, u, st, d="d1"):
        return {"e": e, "n": n, "d": d, "dn": "Growatt", "m": "Growatt", "mo": "MIN 6000TL-X", "dc": dc, "u": u, "st": st}
    utan = [ent("sensor.growatt_battery_soc", "Battery SOC", "battery", "%", "0"),
            ent("sensor.growatt_battery_power", "Battery Power", "power", "W", "0")]
    assert not discover_house(utan).get("battery")
    med = [ent("sensor.growatt_battery_soc", "Battery SOC", "battery", "%", "54"),
           ent("sensor.growatt_battery_power", "Battery Power", "power", "W", "-800")]
    assert discover_house(med).get("battery")
