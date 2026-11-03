"""HeishaMon-drivrutinen mot en låtsad HeishaMon (samma /json-form som HeishaMon/webfunctions.cpp skriver)."""
import requests

from drivers.heatpump_heishamon import HeishaMonHeatPumpDriver
import house_config


def _json(**values):
    return {"heatpump": [{"Topic": f"TOP{i}", "Name": k, "Value": v, "Description": ""} for i, (k, v) in enumerate(values.items())]}


BASE = dict(Heatpump_State=1, Operating_Mode_State=4, Heating_Mode=0, Z1_Heat_Request_Temp=1, Outside_Temp=-2,
            Z1_Temp=21.5, Main_Inlet_Temp=30, Main_Outlet_Temp=35, DHW_Temp=47, Compressor_Freq=38,
            Heat_Power_Production=4200, Heat_Power_Consumption=1000, DHW_Power_Production=0, DHW_Power_Consumption=200,
            Cool_Power_Production=0, Cool_Power_Consumption=0, Defrosting_State=0, Error="No error")


class FakeHttp:
    def __init__(self, values=None, fail=False):
        self.values = dict(BASE, **(values or {}))
        self.commands = []
        self.fail = fail

    def get(self, url, params=None, timeout=None):
        if self.fail:
            raise requests.ConnectionError("nere")
        http = self

        class R:
            def raise_for_status(self): pass
            def json(self): return _json(**http.values)
        if url.endswith("/command"):
            self.commands.append(params)
        return R()


def test_lasning_och_matter_bild():
    d = HeishaMonHeatPumpDriver("192.168.1.60", session=FakeHttp())
    s = d.read_sensors()
    assert s["outdoor_temp"] == -2 and s["forward_temp"] == 35 and s["return_temp"] == 30 and s["water_temp"] == 47
    assert s["compressor_running"] is True and s["compressor_power_kw"] == 1.2
    assert s["indoor_temp"] is None and s["operating_mode"] is None        # Thermia-koder i main.py: lämnas tomt
    st = d.read_state()
    assert st["mode"] == "heat_dhw" and st["power_w"] == 1200 and st["heat_output_w"] == 4200 and st["cop"] == 3.5
    assert st["fault"] is None and st["defrosting"] is False
    assert d.capabilities() == {"curve_offset", "pause"}


def test_av_fel_avfrostning_och_rumsgivare():
    d = HeishaMonHeatPumpDriver("hm", indoor_from_z1=True,
                                session=FakeHttp(dict(Heatpump_State=0, Error="H15", Defrosting_State=1, Compressor_Freq=0)))
    st = d.read_state()
    assert st["mode"] == "off" and st["fault"] == "H15" and st["defrosting"] is True and st["running"] is False
    assert st["indoor_temp"] == 21.5


def test_minus_ett_ar_okant():
    d = HeishaMonHeatPumpDriver("hm", session=FakeHttp(dict(Outside_Temp=-1)))
    assert d.read_sensors()["outdoor_temp"] is None


def test_kurva_relativt_grundforskjutning_och_bara_i_kurvlage():
    http = FakeHttp()
    d = HeishaMonHeatPumpDriver("hm", base_shift=1, session=http)
    assert d.adjust_curve(2) and http.commands[-1] == {"SetZ1HeatRequestTemperature": 3}
    assert d.adjust_curve(9) and http.commands[-1] == {"SetZ1HeatRequestTemperature": 5}    # taket -5..5
    assert d.reset_curve_offset() and http.commands[-1] == {"SetZ1HeatRequestTemperature": 1}
    direct = FakeHttp(dict(Heating_Mode=1))
    d2 = HeishaMonHeatPumpDriver("hm", session=direct)
    assert not d2.adjust_curve(2) and direct.commands == []                                 # direktläge: absolut temp


def test_paus_och_lagen():
    http = FakeHttp()
    d = HeishaMonHeatPumpDriver("hm", session=http)
    assert d.pause(30, now=0) and http.commands[-1] == {"SetHeatpump": 0}
    d.tick(now=30 * 60)
    assert http.commands[-1] == {"SetHeatpump": 1}
    assert d.set_operating_mode("heat_dhw") and http.commands[-1] == {"SetOperationMode": 4}
    assert d.set_operating_mode("off") and http.commands[-1] == {"SetHeatpump": 0}
    n = len(http.commands)
    assert not d.set_operating_mode(1) and len(http.commands) == n                          # Thermias råa kod avvisas
    assert d.set_water_stop_temp(90) and http.commands[-1] == {"SetDHWTemp": 75}
    assert not d.set_room_temp(21)


def test_nere_ger_tomt_och_false():
    d = HeishaMonHeatPumpDriver("hm", session=FakeHttp(fail=True))
    assert d.read_sensors() == {} and not d.adjust_curve(1) and not d.pause(10)
    assert HeishaMonHeatPumpDriver("").read_sensors() == {}


def test_house_config_bygger_drivrutinen():
    d = house_config.build_heat_pump_driver({"heat_pump": {"enabled": True, "driver": "heishamon", "host": "10.0.0.9",
                                                           "base_shift": -1, "indoor_from_z1": True}})
    assert isinstance(d, HeishaMonHeatPumpDriver) and d._host == "10.0.0.9" and d._base_shift == -1 and d._indoor_from_z1
