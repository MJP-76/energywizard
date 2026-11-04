"""Issue #118: som HA-tillägg öppnas webben via Ingress - då har HA redan loggat in användaren."""
from starlette.requests import Request

import webauth


def _req(peer, headers=None):
    h = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "client": (peer, 1234), "headers": h, "method": "GET", "path": "/"})


def test_ingress_ger_agaren_bara_som_tillagg_och_bara_fran_supervisorn(monkeypatch):
    cls = webauth.Auth
    ok = {"X-Ingress-Path": "/api/hassio_ingress/abc", "X-Remote-User-Name": "lars"}
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    assert cls.ingress_user(_req("172.30.32.2", ok)) is None                 # inte tillägg: aldrig
    monkeypatch.setenv("SUPERVISOR_TOKEN", "x")
    assert cls.ingress_user(_req("172.30.32.2", ok)) == "lars"
    assert cls.ingress_user(_req("192.168.1.50", ok)) is None                # headern från nätet räcker inte
    assert cls.ingress_user(_req("172.30.32.2", {})) is None                 # utan Ingress-header
