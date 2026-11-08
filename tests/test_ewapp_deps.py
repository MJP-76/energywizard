"""ewapp importerar smartbox-moduler (monterade från värden) i /api/plan. Allt de i sin tur importerar på modulnivå
måste finnas i ewapp-bilden, annars kraschar Plan-fliken (pandas och psycopg_pool saknades 2026-11-03)."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SB = ROOT / "smartbox"
PIP_NAMES = {"yaml": "pyyaml", "sklearn": "scikit-learn", "psycopg": "psycopg"}


def _module_imports(path):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:                # bara modulnivå: importer inne i funktioner är valfria
        if isinstance(node, ast.Import):
            yield from (a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            yield node.module.split(".")[0]


def _third_party(start):
    seen, todo, ext = set(), list(start), set()
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        for name in _module_imports(SB / f"{m}.py"):
            if (SB / f"{name}.py").exists():
                todo.append(name)
            elif name not in sys.stdlib_module_names:
                ext.add(name)
    return ext


def test_ewapp_bilden_har_allt_som_plan_importerar():
    dockerfile = (ROOT / "ewapp" / "Dockerfile").read_text(encoding="utf-8").lower().replace("-", "_")
    ewapp_own = {"fastapi", "uvicorn", "requests", "sqlalchemy", "PIL"}
    missing = sorted(n for n in _third_party(["nordpool", "plan_brief"]) - ewapp_own
                     if PIP_NAMES.get(n, n).lower().replace("-", "_") not in dockerfile)
    assert not missing, f"saknas i ewapp/Dockerfile: {missing}"


def test_numpy_last_for_aldre_processorer():
    """#202: NumPy 2.4 kräver x86-64-v2 och kraschar vid start på äldre x86-processorer. Alla images låser <2.4."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert "numpy<2.4" in (root / "smartbox/requirements.txt").read_text()
    for f in ("ewapp/Dockerfile", "webdashboard/Dockerfile", "ha-addon/smartbox/Dockerfile"):
        assert '"numpy<2.4"' in (root / f).read_text(), f


def test_sprak_foljer_webblasaren_utan_val(monkeypatch):
    """#202: utan valt språk i installationen säger /i18n/config chosen=false, och i18n.js tar webbläsarens språk."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "smartbox"))
    import ew_settings
    import i18n_routes
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: None)
    assert i18n_routes._chosen() is False
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: "en" if k == "language" else None)
    assert i18n_routes._chosen() is True
    assert "c.chosen === false" in (root / "smartbox/i18n/i18n.js").read_text()
