"""#142: planen räknar på första påslagna dagen de kommande sju dygnen - webben ska visa samma mål (inte bara
idag/imorgon) och kunna spara hela veckan."""
import importlib.util
import sys
from datetime import datetime, time as dtime
from pathlib import Path
import zoneinfo

import pytest

ROOT = Path(__file__).resolve().parent.parent
SWE = zoneinfo.ZoneInfo("Europe/Stockholm")


@pytest.fixture(scope="module")
def wd():
    import os
    cwd = Path.cwd()
    os.chdir(ROOT / "webdashboard")
    try:
        mod = sys.modules.get("webdashboard_app")
        if mod is None:
            spec = importlib.util.spec_from_file_location("webdashboard_app", ROOT / "webdashboard" / "app.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["webdashboard_app"] = mod
            spec.loader.exec_module(mod)
        yield mod
    finally:
        os.chdir(cwd)


def test_malet_ar_forsta_paslagna_dagen_inom_sju_dygn(wd):
    now = datetime(2026, 11, 5, 20, 0, tzinfo=SWE)            # torsdag kväll
    # bara måndag påslagen 06:00 80 % -> nästa mål måndag, inte "inget"
    g = wd._car_goals([("tesla", 0, dtime(6, 0), 80)], now)
    assert g and g[0]["at"].startswith("2026-11-09T06:00") and g[0]["soc"] == 80
    # torsdag 06:00 har passerat -> nästa torsdag om sju dygn är nästa förekomst
    g = wd._car_goals([("tesla", 3, dtime(6, 0), 80)], now)
    assert g[0]["at"].startswith("2026-11-12T06:00")
    # fredag morgon går före måndag
    g = wd._car_goals([("tesla", 0, dtime(6, 0), 80), ("tesla", 4, dtime(7, 0), 100)], now)
    assert g[0]["at"].startswith("2026-11-06T07:00") and g[0]["soc"] == 100
