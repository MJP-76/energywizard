"""Exportstyrning för fler växelriktarmärken, via redan underhållna HA-integrationer:
- Sungrow (mkaiser Modbus-paket): number i WATT + switch för gränsläget -> GenericNumberSolarDriver
- Huawei (wlcrs/huawei_solar): integrationens egna tjänster -> HuaweiSolarServiceDriver
- Fronius m.fl.: HA:s inbyggda modbus.write_register -> ModbusRegisterSolarDriver
Mockar homeassistant helt (samma mönster som test_generic_drivers.py)."""
from unittest.mock import call, patch

from drivers.solar_generic import GenericNumberSolarDriver
from drivers.solar_huawei import HuaweiSolarServiceDriver
from drivers.solar_modbus_register import ModbusRegisterSolarDriver
from house_config import build_solar_driver


# ---------- Watt-gräns (Sungrow) ----------

SUNGROW = {"pv_power_w": "sensor.total_dc_power", "export_limit_w": "number.export_power_limit",
           "export_limit_switch": "switch.export_power_limit"}


def test_watt_grans_raknas_om_mot_entitetens_max_och_slar_pa_lagesbrytaren():
    with patch("drivers.solar_generic.homeassistant") as ha:
        ha.get_attribute.return_value = 10000
        ha.set_number.return_value = True
        ha.set_switch.return_value = True
        d = GenericNumberSolarDriver(entities=SUNGROW)
        assert d.supports_curtailment()
        assert d.set_export_limit_pct(30) is True
    ha.get_attribute.assert_called_with("number.export_power_limit", "max")
    ha.set_number.assert_called_once_with("number.export_power_limit", 3000)
    ha.set_switch.assert_called_once_with("switch.export_power_limit", True)


def test_watt_grans_100_procent_slar_av_lagesbrytaren():
    with patch("drivers.solar_generic.homeassistant") as ha:
        ha.get_attribute.return_value = 10000
        ha.set_number.return_value = True
        ha.set_switch.return_value = True
        GenericNumberSolarDriver(entities=SUNGROW).set_export_limit_pct(100)
    ha.set_number.assert_called_once_with("number.export_power_limit", 10000)
    ha.set_switch.assert_called_once_with("switch.export_power_limit", False)


def test_watt_grans_max_fran_configen_vinner_over_attributet():
    with patch("drivers.solar_generic.homeassistant") as ha:
        ha.set_number.return_value = True
        GenericNumberSolarDriver(entities={"export_limit_w": "number.x", "export_limit_max_w": 8000}).set_export_limit_pct(50)
    ha.get_attribute.assert_not_called()
    ha.set_number.assert_called_once_with("number.x", 4000)


def test_watt_grans_utan_kant_max_stryper_inte():
    """Hellre ingen strypning än en gissad wattsiffra."""
    with patch("drivers.solar_generic.homeassistant") as ha:
        ha.get_attribute.return_value = None
        assert GenericNumberSolarDriver(entities={"export_limit_w": "number.x"}).set_export_limit_pct(0) is False
    ha.set_number.assert_not_called()


def test_watt_grans_lases_tillbaka_som_procent():
    with patch("drivers.solar_generic.homeassistant") as ha:
        ha.get_attribute.return_value = 10000
        ha._get_numeric_state.side_effect = lambda e: {"switch.export_power_limit": 1.0, "number.export_power_limit": 2500.0}[e]
        assert GenericNumberSolarDriver(entities=SUNGROW).get_export_limit_pct() == 25.0


def test_watt_grans_med_avslaget_lage_ar_100_procent():
    with patch("drivers.solar_generic.homeassistant") as ha:
        ha._get_numeric_state.side_effect = lambda e: {"switch.export_power_limit": 0.0, "number.export_power_limit": 0.0}[e]
        assert GenericNumberSolarDriver(entities=SUNGROW).get_export_limit_pct() == 100.0


# ---------- Huawei (tjänster) ----------

def test_huawei_stryper_via_procenttjansten():
    with patch("drivers.solar_huawei.homeassistant") as ha:
        ha.call_service.return_value = True
        d = HuaweiSolarServiceDriver(entities={"device_id": "abc123"})
        assert d.get_export_limit_pct() == 100.0
        assert d.set_export_limit_pct(0) is True
        assert d.get_export_limit_pct() == 0.0
    ha.call_service.assert_called_once_with("huawei_solar", "set_maximum_feed_grid_power_percent",
                                            {"device_id": "abc123", "power_percentage": 0})


def test_huawei_100_procent_aterstaller_till_obegransat():
    with patch("drivers.solar_huawei.homeassistant") as ha:
        ha.call_service.return_value = True
        HuaweiSolarServiceDriver(entities={"device_id": "abc123"}).set_export_limit_pct(100)
    ha.call_service.assert_called_once_with("huawei_solar", "reset_maximum_feed_grid_power", {"device_id": "abc123"})


def test_huawei_misslyckat_anrop_andrar_inte_senaste_varde():
    with patch("drivers.solar_huawei.homeassistant") as ha:
        ha.call_service.return_value = False
        d = HuaweiSolarServiceDriver(entities={"device_id": "abc123"})
        assert d.set_export_limit_pct(20) is False
        assert d.get_export_limit_pct() == 100.0


def test_huawei_utan_device_id_stodjer_inte_strypning():
    d = HuaweiSolarServiceDriver(entities={"pv_power_w": "sensor.input_power"})
    assert not d.supports_curtailment() and d.get_export_limit_pct() is None and d.set_export_limit_pct(0) is False


# ---------- Modbus-register (Fronius-förval) ----------

def _writes(ha):
    return [c.args[2] for c in ha.call_service.call_args_list]


def test_fronius_forval_av_varde_pa_i_ratt_ordning():
    with patch("drivers.solar_modbus_register.homeassistant") as ha:
        ha.call_service.return_value = True
        d = ModbusRegisterSolarDriver(modbus={"preset": "fronius", "hub": "fronius"})
        assert d.set_export_limit_pct(50) is True
    assert all(c.args[:2] == ("modbus", "write_register") for c in ha.call_service.call_args_list)
    assert _writes(ha) == [
        {"hub": "fronius", "slave": 1, "address": 40236, "value": 0},
        {"hub": "fronius", "slave": 1, "address": 40232, "value": 5000},
        {"hub": "fronius", "slave": 1, "address": 40236, "value": 1},
    ]


def test_fronius_0_procent_blir_lagsta_tillatna_1_procent():
    with patch("drivers.solar_modbus_register.homeassistant") as ha:
        ha.call_service.return_value = True
        ModbusRegisterSolarDriver(modbus={"preset": "fronius", "hub": "fronius"}).set_export_limit_pct(0)
    assert _writes(ha)[1]["value"] == 100


def test_fronius_100_procent_slar_bara_av_gransen():
    with patch("drivers.solar_modbus_register.homeassistant") as ha:
        ha.call_service.return_value = True
        ModbusRegisterSolarDriver(modbus={"preset": "fronius", "hub": "fronius"}).set_export_limit_pct(100)
    assert _writes(ha) == [{"hub": "fronius", "slave": 1, "address": 40236, "value": 0}]


def test_modbus_adresser_kan_skrivas_over_i_configen():
    with patch("drivers.solar_modbus_register.homeassistant") as ha:
        ha.call_service.return_value = True
        ModbusRegisterSolarDriver(modbus={"preset": "fronius", "hub": "h", "slave": 3,
                                          "pct_register": 40233, "enable_register": 40237}).set_export_limit_pct(10)
    assert [w["address"] for w in _writes(ha)] == [40237, 40233, 40237]
    assert all(w["slave"] == 3 for w in _writes(ha))


def test_modbus_fel_mitt_i_sekvensen_ger_false_och_behaller_senaste():
    with patch("drivers.solar_modbus_register.homeassistant") as ha:
        ha.call_service.side_effect = [True, False]
        d = ModbusRegisterSolarDriver(modbus={"preset": "fronius", "hub": "fronius"})
        assert d.set_export_limit_pct(50) is False
        assert d.get_export_limit_pct() == 100.0
    assert ha.call_service.call_count == 2          # slutar efter felet, slår inte på gränsen


def test_modbus_utan_hub_stodjer_inte_strypning():
    assert not ModbusRegisterSolarDriver(modbus={"preset": "fronius"}).supports_curtailment()


# ---------- house_config kopplar ihop configen ----------

def test_build_solar_driver_huawei_och_modbus():
    hw = build_solar_driver({"solar": {"enabled": True, "driver": "huawei_solar", "entities": {"device_id": "abc"}}})
    assert isinstance(hw, HuaweiSolarServiceDriver) and hw.supports_curtailment()
    mb = build_solar_driver({"solar": {"enabled": True, "driver": "modbus_register",
                                       "modbus": {"preset": "fronius", "hub": "fronius"}}})
    assert isinstance(mb, ModbusRegisterSolarDriver) and mb.supports_curtailment()
