"""notify_log.py + notifier: aviseringshistorik med leveransstatus (FTW-idé, Emil 2026-11-07)."""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "smartbox"))
import notifier  # noqa: E402
import notify_log  # noqa: E402


class R:
    def __init__(self, code):
        self.status_code = code


def test_begripliga_orsaker():
    assert "token" in notify_log.short_error(requests.HTTPError(response=R(401)))
    assert "mottagaren" in notify_log.short_error(requests.HTTPError(response=R(400)))
    assert "i tid" in notify_log.short_error(requests.Timeout())
    assert "nå" in notify_log.short_error(requests.ConnectionError())


def _capture(monkeypatch):
    got = []
    monkeypatch.setattr(notify_log, "add", lambda *a, **k: got.append(a))
    monkeypatch.setattr(notifier, "_init", lambda: None)
    notifier._ha_base, notifier._ha_headers = "http://ha/api", {}
    return got


def test_skickad_och_misslyckad_sparas(monkeypatch):
    got = _capture(monkeypatch)

    class Ok:
        def raise_for_status(self):
            pass
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: Ok())
    assert notifier._send("mobile_app_x", "Tesla laddar", "16 A", key="elbil")
    assert got[-1][2] == "sent" and got[-1][3] == "mobile_app_x" and got[-1][4] == "elbil"

    def boom(*a, **k):
        raise requests.Timeout()
    monkeypatch.setattr(notifier.requests, "post", boom)
    assert not notifier._send("mobile_app_x", "Tesla laddar", "16 A")
    assert got[-1][2] == "failed" and "i tid" in got[-1][5]


def test_avstangd_och_ingen_mottagare_sparas(monkeypatch):
    got = _capture(monkeypatch)
    import notify_prefs
    monkeypatch.setattr(notify_prefs, "enabled", lambda k=None, t=None: False)
    notifier.send_emil("Spabadet klart", "38 °C", key="spa")
    assert got[-1][2] == "muted"
    monkeypatch.setattr(notify_prefs, "enabled", lambda k=None, t=None: True)
    monkeypatch.setattr(notifier, "recipients", lambda: [])
    notifier.send_emil("Spabadet klart", "38 °C", key="spa")
    assert got[-1][2] == "none"
