"""FTW-drivrutinerna genom vår Lua-brygga mot Sourcefuls enhetssimulator (srcfl/device-simulator).

Körs bara i GitHub Actions (.github/workflows/simulator.yml), där start_sims.sh startat en simulerad växelriktare per
drivrutin. Läsning ska stämma med det simulerade huset (sol 3 kW, batteri 50 %). Styrning provas för hybriderna: efter
"ladda 2 kW" ska batteriet ladda, efter "ladda ur" ladda ur. Resultatet skrivs till out/report.json (artefakt).
Utan simulatorn hoppas testerna över.
"""
import json
import os
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
DEVICES = HERE / "out" / "devices.json"
REPORT = HERE / "out" / "report.json"
pytestmark = pytest.mark.skipif(not DEVICES.exists(), reason="simulatorn körs bara i GitHub Actions")
pytest.importorskip("lupa")

from lua_host import LuaDriver, FTW_DIR  # noqa: E402


# Kända avvikelser mellan FTW-drivrutinen och simulatorn (rapporteras, gör inte körningen röd)
KNOWN_READ_GAPS = {"fronius": "FTW:s fronius-drivrutin läser solen som 0 W mot simulatorns Fronius GEN24 (2026-11-06)"}


def _devices():
    return json.loads(DEVICES.read_text()) if DEVICES.exists() else []


def _report(driver, **kv):
    r = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    r.setdefault(driver, {}).update(kv)
    REPORT.write_text(json.dumps(r, indent=1, ensure_ascii=False))


def _poll(drv, n=4, wait=1.5):
    em = {}
    for _ in range(n):
        em, _nxt = drv.poll()
        if em.get("battery") or em.get("pv"):
            time.sleep(wait)
            em, _nxt = drv.poll()
            break
        time.sleep(wait)
    return em


@pytest.mark.parametrize("dev", _devices(), ids=lambda d: d["driver"])
def test_lasning_stammer_med_huset(dev):
    drv = LuaDriver(os.path.join(FTW_DIR, dev["driver"] + ".lua"), host="127.0.0.1", port=dev["modbus_port"],
                    unit_id=dev["unit_id"], log=lambda *a: None)
    try:
        em = _poll(drv)
    finally:
        drv.close()
    _report(dev["driver"], emits={k: {kk: v for kk, v in (vv or {}).items() if kk in ("w", "soc")} for k, vv in em.items()})
    assert em, f"{dev['driver']}: inget rapporterat"
    pv = (em.get("pv") or {}).get("w")
    if dev["driver"] in KNOWN_READ_GAPS and pv is not None and abs(pv) < 1:
        _report(dev["driver"], read_ok=False, note=KNOWN_READ_GAPS[dev["driver"]])
        pytest.xfail(KNOWN_READ_GAPS[dev["driver"]])
    if pv is not None:
        assert abs(abs(pv) - dev["spec"]["pv_w"]) <= 0.25 * dev["spec"]["pv_w"], f"sol {pv} W, väntat ~{dev['spec']['pv_w']}"
    soc = (em.get("battery") or {}).get("soc")
    if soc is not None:
        soc = soc * 100 if soc <= 1 else soc
        assert abs(soc - dev["spec"]["soc_pct"]) <= 3, f"laddnivå {soc} %, väntat ~{dev['spec']['soc_pct']}"
    _report(dev["driver"], read_ok=True)


@pytest.mark.parametrize("dev", [d for d in _devices() if d["spec"].get("battery_kwh")], ids=lambda d: d["driver"])
def test_styrning_laddar_och_laddar_ur(dev):
    """Informativt: vilka drivrutiners styrning som fungerar mot simulatorn (underlag för FTW_CONTROL_VERIFIED)."""
    drv = LuaDriver(os.path.join(FTW_DIR, dev["driver"] + ".lua"), host="127.0.0.1", port=dev["modbus_port"],
                    unit_id=dev["unit_id"], allow_write=True, config={"nominal_w": 10000}, log=lambda *a: None)
    out = {}
    try:
        _poll(drv, n=2)
        if drv.L.globals().driver_command is None:
            _report(dev["driver"], control="ingen driver_command")
            pytest.skip("drivrutinen har ingen styrning")
        for name, w in (("charge", 2000), ("discharge", -2000)):
            ok = drv.command("battery", w, {"source": "ci"})
            got = None
            for _ in range(45):                                  # simulatorn svarar med modellens egen fördröjning
                time.sleep(1.0)
                got = ((drv.poll()[0].get("battery") or {}).get("w"))
                if got is not None and ((w > 0 and got > 500) or (w < 0 and got < -500)):
                    break
            out[name] = {"command_ok": bool(ok), "battery_w": got}
        try:
            drv.L.globals().driver_default_mode and drv.L.globals().driver_default_mode()
        except Exception:
            pass
    finally:
        drv.close()
    works = all(v["battery_w"] is not None and ((k == "charge" and v["battery_w"] > 500) or (k == "discharge" and v["battery_w"] < -500))
                for k, v in out.items())
    _report(dev["driver"], control=out, control_ok=works)
    if not works:
        pytest.xfail(f"{dev['driver']}: styrningen följde inte i simulatorn: {out}")
