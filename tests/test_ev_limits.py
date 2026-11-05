"""Faser och maxström per bil lärs in av laddningarna - bara där installationen inte anger dem."""
from ev_limits import LimitLearner, MIN_SAMPLES


def test_enfasbil_och_egen_maxstrom():
    l = LimitLearner()
    for _ in range(MIN_SAMPLES):
        l.observe("leaf", [15.6, 0.1, 0.2], commanded_a=32)
    assert l.phases("leaf") == "1" and l.max_a("leaf") == 15


def test_trefasbil_som_tar_allt_far_ingen_maxgrans():
    l = LimitLearner()
    for _ in range(MIN_SAMPLES):
        l.observe("tesla", [15.9, 16.0, 15.8], commanded_a=16)
    assert l.phases("tesla") == "3" and l.max_a("tesla") is None


def test_bara_utan_installationens_egna_varden():
    l = LimitLearner({"leaf": {"one": 20, "multi": 0, "max_a": 15}, "kona": {"one": 0, "multi": 30, "max_a": 11}})
    specs = {"leaf": {"phases": "3", "max_a": 16}, "kona": {"phases": "auto", "max_a": 16}}
    changed = l.apply(specs, {"leaf": {"phases": True, "max_a": True}, "kona": {}})
    assert specs["leaf"] == {"phases": "3", "max_a": 16}                 # installationen bestämmer
    assert specs["kona"] == {"phases": "3", "max_a": 11} and changed == {"kona": {"phases": "3", "max_a": 11}}


def test_brus_ger_inget():
    l = LimitLearner()
    l.observe("x", [0.3, 0.2, 0.1], 16)
    assert l.phases("x") is None and l.max_a("x") is None
