"""Martins jämförelse 2026-11-07: aviseringar till den som är hemma (som Familjetavlans hemlarm), samma i motor och app."""
import notifier


def test_bara_de_som_ar_hemma(monkeypatch):
    where = {"mobile_app_a": True, "mobile_app_b": False, "mobile_app_c": None}
    monkeypatch.setattr(notifier, "_persons", lambda: {})
    monkeypatch.setattr(notifier, "phone_home", lambda s, p=None: where[s])
    assert notifier.pick_home(["mobile_app_a", "mobile_app_b", "mobile_app_c"]) == ["mobile_app_a"]


def test_ingen_hemma_alla_far(monkeypatch):
    monkeypatch.setattr(notifier, "_persons", lambda: {})
    where = {"mobile_app_a": False, "mobile_app_b": False, "mobile_app_ipad": None}
    monkeypatch.setattr(notifier, "phone_home", lambda s, p=None: where[s])
    assert notifier.pick_home(list(where)) == ["mobile_app_a", "mobile_app_b"]     # inte väggplattan


def test_okand_plats_som_forut(monkeypatch):
    monkeypatch.setattr(notifier, "_persons", lambda: {})
    monkeypatch.setattr(notifier, "phone_home", lambda s, p=None: None)
    assert notifier.pick_home(["mobile_app_a"]) == ["mobile_app_a"]


def test_utan_installningen_den_valda_mottagaren(monkeypatch):
    monkeypatch.setattr(notifier, "target", lambda: "mobile_app_a")
    monkeypatch.setattr(notifier, "home_only", lambda: False)
    assert notifier.recipients() == ["mobile_app_a"]
    monkeypatch.setattr(notifier, "home_only", lambda: True)
    monkeypatch.setattr(notifier, "_all_phones", lambda: ["mobile_app_a", "mobile_app_b"])
    monkeypatch.setattr(notifier, "_persons", lambda: {})
    monkeypatch.setattr(notifier, "phone_home", lambda s, p=None: s == "mobile_app_b")
    assert notifier.recipients() == ["mobile_app_b"]


def test_person_avgor_inte_surfplattan():
    persons = {"device_tracker.emil_s24": "home", "device_tracker.elin": "not_home"}
    assert notifier.phone_home("mobile_app_emil_s24", persons) is True
    assert notifier.phone_home("mobile_app_elin", persons) is False
    assert notifier.phone_home("mobile_app_ipad", persons) is None
