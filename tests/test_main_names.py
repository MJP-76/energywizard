"""smartbox/main.py: två MeterFreeze-objekt fick samma namn (2026-11-03) och det senare skrev över det första,
så health-anropet frozen(net, faser, t) gick mot battery_control-varianten och lastnedbrytningen hoppades över."""
import ast
from collections import Counter
from pathlib import Path


def test_inga_dubbla_modulnamn_for_meterfreeze():
    tree = ast.parse(Path(__file__).resolve().parent.parent.joinpath("smartbox", "main.py").read_text(encoding="utf-8"))
    names = Counter()
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func, "attr", "") == "MeterFreeze":
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names[t.id] += 1
    assert names and all(n == 1 for n in names.values()), names
