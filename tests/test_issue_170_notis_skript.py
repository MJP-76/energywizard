"""#170: aviseringar kan gå till ett eget skript i Home Assistant (variablerna title och message)."""
from unittest.mock import patch

import notifier


class _R:
    def raise_for_status(self):
        pass


def test_skript_anropas_med_rubrik_och_text(monkeypatch):
    monkeypatch.setattr(notifier, "_ha_base", "http://ha/api")
    monkeypatch.setattr(notifier, "_ha_headers", {})
    with patch.object(notifier.requests, "post", return_value=_R()) as post:
        assert notifier._send("script.ew_notis", "Kallt inomhus", "Det är 17 °C inne")
    url, kw = post.call_args[0][0], post.call_args[1]
    assert url == "http://ha/api/services/script/ew_notis"
    assert kw["json"] == {"title": "Kallt inomhus", "message": "Det är 17 °C inne"}


def test_telefon_som_forut(monkeypatch):
    monkeypatch.setattr(notifier, "_ha_base", "http://ha/api")
    monkeypatch.setattr(notifier, "_ha_headers", {})
    with patch.object(notifier.requests, "post", return_value=_R()) as post:
        notifier._send("mobile_app_pixel", "T", "M")
    assert post.call_args[0][0] == "http://ha/api/services/notify/mobile_app_pixel"


def test_vald_mottagare_behaller_script_prefixet(monkeypatch):
    monkeypatch.delenv("NOTIFY_TARGET", raising=False)
    import ew_settings
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: "script.ew_notis" if k == "notify_target" else d)
    assert notifier.target() == "script.ew_notis"
    monkeypatch.setattr(ew_settings, "get", lambda k, d=None: "notify.mobile_app_x" if k == "notify_target" else d)
    assert notifier.target() == "mobile_app_x"
