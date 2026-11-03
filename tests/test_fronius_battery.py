"""Fronius Gen24 via redpomodoro/fronius_modbus (Storage Control Mode + effekt i W), och att entitetsväljaren
väljer växelriktaren som kan styra före en BYD-integration som bara läser (bbr111/byd_hvs, redpomodoro/byd_battery_box)."""
import yaml

from discovery import discover_house
from house_config import build_battery_driver
from test_solax_modbus_battery import _builder
from test_solis_battery import SOLIS


def _e(eid, name, dev, maker, dc=None, u=None, st="1"):
    return {"e": eid, "n": name, "a": None, "d": dev, "dn": f"{maker} enhet", "m": maker, "mo": "", "dc": dc, "u": u, "st": st}


FRONIUS = [
    _e("sensor.fronius_storage_soc", "Fronius Storage SOC", "dev_fro", "Fronius", "battery", "%", "70"),
    _e("sensor.fronius_storage_power", "Fronius Storage Power", "dev_fro", "Fronius", "power", "W", "-500"),
    _e("select.fronius_storage_control_mode", "Fronius Storage Control Mode", "dev_fro", "Fronius", st="Auto"),
    _e("number.fronius_grid_charge_power", "Fronius Grid charge power", "dev_fro", "Fronius", "power", "W", "0"),
    _e("number.fronius_grid_discharge_power", "Fronius Grid discharge power", "dev_fro", "Fronius", "power", "W", "0"),
]
# BYD-integrationen kommer FÖRST i listan - den ska ändå inte väljas, den kan inte styra.
BYD = [
    {**_e("sensor.byd_state_of_charge", "BYD State of Charge", "dev_byd", "BYD", "battery", "%", "71"), "dn": "BYD HVS", "mo": "Battery-Box Premium HVS"},
    {**_e("sensor.byd_power", "BYD Power", "dev_byd", "BYD", "power", "W", "-480"), "dn": "BYD HVS", "mo": "Battery-Box Premium HVS"},
    {**_e("sensor.byd_bms_1_cell_voltage_max", "BMS 1 Cell voltage max", "dev_byd", "BYD", "voltage", "V", "3.34"), "dn": "BYD HVS"},
]
BYD_CAR = [
    _e("sensor.atto3_battery", "Atto 3 Battery", "dev_car", "BYD", "battery", "%", "64"),
    _e("device_tracker.atto3", "Atto 3", "dev_car", "BYD"),
]


def test_fronius_kanns_igen_med_hall_lage():
    gs = discover_house(FRONIUS)["battery"]["generic_suggestion"]
    assert gs["preset"] == "fronius_modbus"
    assert gs["modes"] == {"auto": "Auto", "hold": "Block Discharging", "charge": "Charge from Grid",
                           "discharge": "Discharge to Grid"}
    assert gs["entities"]["charge_power"] == "number.fronius_grid_charge_power"
    text = _builder()({"cars": [], "battery": discover_house(FRONIUS)["battery"]})
    assert build_battery_driver(yaml.safe_load(text)).supported_intents() == {"auto", "hold", "charge", "discharge"}


def test_styrbar_vaxelriktare_fore_byd_som_bara_laser():
    for inverter, preset in ((FRONIUS, "fronius_modbus"), (SOLIS, "solis_modbus")):
        b = discover_house(BYD + inverter)["battery"]
        assert b["control_preset"] == preset, preset


def test_bara_byd_ger_lasning_och_ar_ingen_bil():
    d = discover_house(BYD)
    assert d["cars"] == []
    assert d["battery"]["soc_entity"] == "sensor.byd_state_of_charge" and not d["battery"].get("control_preset")


def test_byd_bil_ar_fortfarande_bil():
    d = discover_house(BYD_CAR)
    assert len(d["cars"]) == 1 and d["battery"] is None
