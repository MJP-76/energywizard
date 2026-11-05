"""#127: en vald enhet utan givare (t.ex. värmepump via generic_climate där upptäckten inte hittade någon climate-entitet)
gav "entities:" utan innehåll -> None -> 'NoneType' object has no attribute 'get' när guiden sparade."""
import tempfile

import yaml

import house_config


def _load(text):
    with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
        f.write(text)
        f.flush()
        return house_config.load_house_config(f.name)


def test_tomma_entities_kraschar_inte():
    cfg = _load("evs:\n  - id: bil1\n    entities:\n    charger:\n      id: x\n      driver: generic\n      entities:\n"
                "heat_pump:\n  enabled: true\n  driver: generic_climate\n  entities:\n"
                "solar:\n  enabled: true\n  driver: generic_number\n  entities:\n"
                "spa:\n  enabled: true\n  driver: generic_spa\n  entities:\n"
                "battery:\n  enabled: true\n  driver: generic\n  entities:\n  modes:\n")
    house_config.build_car_drivers(cfg)
    house_config.build_charger_drivers(cfg)
    house_config.build_heat_pump_driver(cfg)
    house_config.build_solar_driver(cfg)
    house_config.build_spa_driver(cfg)
    house_config.build_battery_driver(cfg)


def test_guiden_skriver_tomma_givare_som_tom_lista(monkeypatch):
    import importlib.util, os, sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    monkeypatch.chdir(root / "webdashboard")       # app.py monterar static relativt cwd
    mod = sys.modules.get("webdashboard_app")
    if mod is None:
        spec = importlib.util.spec_from_file_location("webdashboard_app", root / "webdashboard" / "app.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["webdashboard_app"] = mod
        spec.loader.exec_module(mod)
    text = mod._build_house_config_yaml({"heat_pump": {"driver": "generic_climate"}, "cars": [{"id": "bil1"}]})
    d = yaml.safe_load(text)
    assert d["heat_pump"]["entities"] == {}
    assert d["evs"][0]["entities"] == {}
