"""#161: flikar för utrustning som installationen inte har döljs."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _wd():
    mod = sys.modules.get("webdashboard_app")
    if mod is None:
        cwd = os.getcwd()
        os.chdir(ROOT / "webdashboard")
        try:
            spec = importlib.util.spec_from_file_location("webdashboard_app", ROOT / "webdashboard" / "app.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["webdashboard_app"] = mod
            spec.loader.exec_module(mod)
        finally:
            os.chdir(cwd)
    return mod


def test_utan_spa_bil_varmepump_sol_doljs_flikarna():
    assert _wd()._hidden_pages({}) == {"spabad", "elbil", "varmepump", "solceller"}


def test_med_allt_visas_allt_och_batteri_haller_solceller_kvar():
    cfg = {"spa": {"enabled": True}, "evs": [{"id": "tesla"}], "heat_pump": {"enabled": True}, "solar": {"enabled": True}}
    assert _wd()._hidden_pages(cfg) == set()
    assert "solceller" not in _wd()._hidden_pages({"battery": {"enabled": True}})


def test_egna_dolda_flikar_men_aldrig_oversikt_eller_installningar():
    cfg = {"spa": {"enabled": True}, "evs": [{"id": "x"}], "heat_pump": {"enabled": True}, "solar": {"enabled": True},
           "ui": {"hidden_tabs": ["prognos", "temperaturer", "oversikt", "installningar"]}}
    assert _wd()._hidden_pages(cfg) == {"prognos", "temperaturer"}
