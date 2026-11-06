"""#167: index.html länkar app.js och style.css med ?v=<innehållets hash>, så att en ny version alltid hämtas."""
import importlib.util
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_index_har_versionsmarkta_filer():
    mod = sys.modules.get("webdashboard_app")
    cwd = os.getcwd()
    os.chdir(ROOT / "webdashboard")
    try:
        if mod is None:
            spec = importlib.util.spec_from_file_location("webdashboard_app", ROOT / "webdashboard" / "app.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["webdashboard_app"] = mod
            spec.loader.exec_module(mod)
        html = mod._index_html()
    finally:
        os.chdir(cwd)
    assert re.search(r'href="static/style\.css\?v=[0-9a-f]{10}"', html)
    assert re.search(r'src="static/app\.js\?v=[0-9a-f]{10}"', html)
