"""Språk (smartbox/i18n) och sponsring (smartbox/sponsor.py)."""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "smartbox"))
I18N = ROOT / "smartbox" / "i18n"


def test_ordlistorna_ar_giltiga():
    langs = json.loads((I18N / "languages.json").read_text(encoding="utf-8"))
    assert langs["sv"] == "Svenska" and "en" in langs
    for code in langs:
        if code == "sv":
            continue
        d = json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))
        assert d.get("_language"), code
        for k, v in d.items():
            if k.startswith("_") or not v:
                continue
            assert k.count("#") == v.count("#"), f"{code}: olika antal # i {k!r} -> {v!r}"


@pytest.fixture()
def st(tmp_path, monkeypatch):
    import ew_settings
    monkeypatch.setattr(ew_settings, "PATH", str(tmp_path / "s.json"))
    ew_settings._cache.update(mtime=None, data={})
    return ew_settings


def test_sponsorrutan_en_gang_i_manaden_efter_en_vecka(st):
    import sponsor
    t0 = datetime(2026, 11, 3, 12)
    assert sponsor.state("sv", t0)["show"] is False                  # ny installation: vänta en vecka
    t1 = t0 + timedelta(days=8)
    s = sponsor.state("sv", t1)
    assert s["show"] and "fritid" in s["text"] and "Claude" in s["text"] and s["url"].startswith("https://github.com/sponsors/")
    sponsor.dismiss(t1)
    assert sponsor.state("sv", t1 + timedelta(days=5))["show"] is False  # samma månad
    assert sponsor.state("en", datetime(2026, 12, 1))["show"] is True    # ny månad
    assert "spare time" in sponsor.state("en", t1)["text"] and "1,000" in sponsor.state("en", t1)["text"]


def test_sponsornotisen_kan_stangas_av_och_gar_till_ha_en_gang(st):
    import sponsor
    calls = []
    t0 = datetime(2026, 1, 1)
    sponsor.state("sv", t0)                                            # sätter installed_at
    t = t0 + timedelta(days=10)
    assert sponsor.send_ha_notice(lambda *a: calls.append(a) or True, "sv", t)
    assert not sponsor.send_ha_notice(lambda *a: calls.append(a) or True, "sv", t + timedelta(hours=1))
    assert calls[0][0:2] == ("persistent_notification", "create") and "github.com/sponsors" in calls[0][2]["message"]
    sponsor.set_enabled(False)
    assert not sponsor.state("sv", datetime(2026, 3, 1))["show"]
    assert not sponsor.send_ha_notice(lambda *a: True, "sv", datetime(2026, 3, 1))


def test_installationens_sprak(st):
    import i18n_routes
    assert i18n_routes.default_language() == "sv"
    st.update(language="en")
    assert i18n_routes.default_language() == "en"
    st.update(language="xx")                                           # okänt -> svenska
    assert i18n_routes.default_language() == "sv"


def test_web_common_sprak_bara_i_startguiden_eller_agaren(st):
    from fastapi import FastAPI
    import web_common
    app = FastAPI()
    role = {"r": None}
    setup = {"open": True}
    web_common.register(app, lambda req: role["r"], lambda: setup["open"])
    fn = next(r.endpoint for r in app.routes if getattr(r, "path", "") == "/api/setup/language")

    class R:
        def __init__(self, b): self.b = b
        async def json(self): return self.b
    assert asyncio.run(fn(R({"language": "en"})))["language"] == "en"
    setup["open"] = False
    assert asyncio.run(fn(R({"language": "sv"}))).status_code == 403
    role["r"] = "owner"
    assert asyncio.run(fn(R({"language": "sv"})))["ok"]
    assert asyncio.run(fn(R({"language": "klingon"}))).status_code == 400


def test_extra_utskick_visas_igen_aven_om_manadens_redan_setts(st):
    """2026-11-06: meddelandet om utvecklingskostnaden når även den som redan stängt/fått novembers påminnelse."""
    import sponsor
    t0 = datetime(2026, 10, 1)
    sponsor.state("sv", t0)                                               # installed_at
    st.update(sponsor_seen_month="2026-11", sponsor_ha_month="2026-11")  # novembers vanliga redan visad/skickad
    t = datetime(2026, 11, 6, 12)
    assert sponsor.state("sv", t)["show"] is True and "1 000 €" in sponsor.state("sv", t)["text"]
    assert sponsor.send_ha_notice(lambda *a: True, "sv", t)
    sponsor.dismiss(t)
    assert sponsor.state("sv", t)["show"] is False
    assert not sponsor.send_ha_notice(lambda *a: True, "sv", t + timedelta(hours=1))
    assert "/Emil" not in sponsor.state("sv", t)["text"]
