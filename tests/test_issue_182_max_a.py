"""#182: Max/Ladda nu i appen var låsta till 16 A. Nu: installationens charger.max_a, annars inlärd (bara lägre), annars 16."""
from pathlib import Path


def _fn():
    src = (Path(__file__).resolve().parent.parent / "ewapp" / "app.py").read_text(encoding="utf-8")
    i = src.index("def car_max_a"); j = src.index("\n\n\n", i)
    return src[i:j]


def test_installationens_maxstrom_galler(monkeypatch, tmp_path):
    import ew_settings
    monkeypatch.setattr(ew_settings, "PATH", str(tmp_path / "s.json"))
    ew_settings._cache.update(mtime=None, data={})
    ns = {"CARS": {"tesla": {"max_a": 25}, "leaf": {}, "id3": {}}, "ew_settings": ew_settings}
    exec(_fn(), ns)
    f = ns["car_max_a"]
    assert f("tesla") == 25 and f("leaf") == 16
    ew_settings.update(learned_ev={"id3": {"one": 0, "multi": 12, "max_a": 10}, "leaf": {"one": 0, "multi": 0, "max_a": 20}})
    assert f("id3") == 10 and f("leaf") == 16               # inlärt bara om lägre än 16


def test_appen_anvander_maxstrommen():
    src = (Path(__file__).resolve().parent.parent / "ewapp" / "app.py").read_text(encoding="utf-8")
    assert "amps = 16 if kind" not in src and "top = car_max_a(car)" in src
