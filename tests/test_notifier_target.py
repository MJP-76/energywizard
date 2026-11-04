"""Issue #104: aviseringsmottagaren får inte vara hårdkodad till en viss telefon."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "smartbox"))
import notifier


def test_env_target_wins(monkeypatch):
    monkeypatch.setenv("NOTIFY_TARGET", "notify.mobile_app_pixel")
    assert notifier.target() == "mobile_app_pixel"


def test_auto_detect_first_mobile_app(monkeypatch):
    monkeypatch.delenv("NOTIFY_TARGET", raising=False)
    import ew_settings
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: None)
    notifier._auto_target.update(t=0.0, name=None)
    monkeypatch.setattr(notifier, "_find_mobile_app", lambda: "mobile_app_lars")
    assert notifier.target() == "mobile_app_lars"


def test_no_phone_means_no_send(monkeypatch):
    monkeypatch.delenv("NOTIFY_TARGET", raising=False)
    import ew_settings
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: None)
    notifier._auto_target.update(t=0.0, name=None)
    monkeypatch.setattr(notifier, "_find_mobile_app", lambda: None)
    sent = []
    monkeypatch.setattr(notifier, "_send", lambda *a, **k: sent.append(a))
    assert notifier.send_emil("t", "m") is False and not sent
