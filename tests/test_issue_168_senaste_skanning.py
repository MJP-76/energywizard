"""#168: senaste skanningen sparas på servern och kan visas igen."""
import asyncio
import importlib.util
import json
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


def test_skanningen_sparas_pa_servern(monkeypatch, tmp_path):
    wd = _wd()
    monkeypatch.setattr(wd.ew_settings, "PATH", str(tmp_path / "energywizard.json"))
    monkeypatch.setattr(wd.discovery, "discover_house", lambda: {"cars": [], "heat_pump": {"driver": "ha_entities"}})
    res = asyncio.run(wd.api_discover())
    assert res["ok"] and res["scanned_at"] > 0
    saved = json.loads((tmp_path / "last_discovery.json").read_text())
    assert saved["heat_pump"]["driver"] == "ha_entities" and saved["ok"]
