"""Badtider för spabadet (Emil 2026-11-08): eco-golv utanför badtiderna, uppvärmning inför nästa."""
import zoneinfo
from datetime import datetime

import spa_bath

SWE = zoneinfo.ZoneInfo("Europe/Stockholm")
# helger dagtid, aldrig vardagar
W = [{"on": False}] * 5 + [{"on": True, "from": "10:00", "to": "18:00"}, {"on": True, "from": "10:00", "to": "18:00"}]


def test_vardag_nasta_badtid_ar_lordag():
    tis = datetime(2026, 11, 10, 20, 0, tzinfo=SWE)
    inside, nxt, end = spa_bath.status(tis, W)
    assert not inside and nxt == datetime(2026, 11, 14, 10, 0, tzinfo=SWE) and end is None


def test_inne_i_badtiden_och_efter():
    lor = datetime(2026, 11, 14, 12, 0, tzinfo=SWE)
    assert spa_bath.status(lor, W) == (True, datetime(2026, 11, 14, 10, 0, tzinfo=SWE), datetime(2026, 11, 14, 18, 0, tzinfo=SWE))
    sond_kvall = datetime(2026, 11, 15, 19, 0, tzinfo=SWE)
    assert spa_bath.status(sond_kvall, W)[1] == datetime(2026, 11, 21, 10, 0, tzinfo=SWE)


def test_inga_badtider_som_forut():
    assert spa_bath.status(datetime(2026, 11, 10, 20, 0, tzinfo=SWE), None) == (False, None, None)
    assert spa_bath.status(datetime(2026, 11, 10, 20, 0, tzinfo=SWE), [{"on": True, "from": "18:00", "to": "10:00"}]) == (False, None, None)


def test_gpm_vilar_pa_ecogolvet_och_varmer_i_tid():
    from test_marginal_spapaus import _state
    from gpm import GlobalPriorityManager
    t = datetime(2026, 11, 10, 20, 0, tzinfo=SWE)
    base = dict(spa_target_scheduled_active=True, spa_target_scheduled=38.0, spa_low_temp=30.0, spa_bath_note="Nästa badtid lör 10:00",
                nissan_connected=False, tesla_connected=False, avg_net_w=500.0, ev_actual_a=0)
    out = GlobalPriorityManager().evaluate(_state(t, spa_should_heat_now=False, **base))
    assert out["spa_target"] == 30.0 and out["spa_eco"] is True and any("eco-golvet" in l for l in out["log"])
    out = GlobalPriorityManager().evaluate(_state(t, spa_should_heat_now=True, **base))
    assert out["spa_target"] == 38.0 and out["spa_eco"] is False
