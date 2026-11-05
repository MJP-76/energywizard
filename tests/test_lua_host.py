"""lua_host: FTW:s Lua-drivrutiner körs genom vår host-brygga. Verifierat live 2026-11-05 mot en Shelly 3EM Gen3
(samma värden som Shellyns eget API och Home Assistant). Här: samma drivrutin mot ett inspelat svar."""
import json
import os
from unittest.mock import patch

import pytest

pytest.importorskip("lupa")
from lua_host import LuaDriver, FTW_DIR  # noqa: E402

# Inspelat från Shelly 3EM Gen3 (S3EMG3) 2026-11-05
DEVINFO = {"name": None, "id": "shelly3em63g3-x", "model": "S3EM-003CXCEU63", "gen": 3, "app": "S3EMG3", "ver": "2.1.1"}
EM = {"id": 0, "a_current": 0.018, "a_voltage": 228.3, "a_act_power": 1.1, "a_freq": 50.0, "b_current": 0.049, "b_voltage": 230.0,
      "b_act_power": -7.3, "c_current": 0.018, "c_voltage": 227.7, "c_act_power": -2.1, "total_act_power": -8.3}


class _R:
    def __init__(self, body):
        self.text, self.status_code, self.ok = json.dumps(body), 200, True


def _fake_get(self_or_url, url=None, timeout=None, **kw):
    url = url if isinstance(self_or_url, object) and url is not None else self_or_url
    if "GetDeviceInfo" in url:
        return _R(DEVINFO)
    if "EM.GetStatus" in url:
        return _R(EM)
    return _R({})


def test_shelly_3em_genom_bryggan():
    with patch("requests.Session.get", _fake_get):
        d = LuaDriver(os.path.join(FTW_DIR, "shelly.lua"), host="192.0.2.1", port=80, log=lambda *_: None)
        em, nxt = d.poll()
    m = em["meter"]
    assert round(m["w"], 1) == -8.3 and m["l1_v"] == 228.3 and m["l2_w"] == -7.3 and m["hz"] == 50.0
    assert d.info.get("make") == "Shelly" and nxt > 0


def test_skrivning_stoppad_i_lasläge():
    with patch("requests.Session.get", _fake_get):
        d = LuaDriver(os.path.join(FTW_DIR, "shelly.lua"), host="192.0.2.1", port=80, log=lambda *_: None)
    assert d._modbus_write(40000, [1]) == "skrivning avstängd (läsläge)"


def test_sandlada_utan_filer_och_processer():
    with patch("requests.Session.get", _fake_get):
        d = LuaDriver(os.path.join(FTW_DIR, "shelly.lua"), host="192.0.2.1", port=80, log=lambda *_: None)
    assert d.L.eval("os") is None and d.L.eval("io") is None and d.L.eval("require") is None


def test_avkodning():
    with patch("requests.Session.get", _fake_get):
        d = LuaDriver(os.path.join(FTW_DIR, "shelly.lua"), host="192.0.2.1", port=80, log=lambda *_: None)
    h = d.L.globals().host
    assert h.decode_i16(0xFFFF) == -1 and h.decode_u32_be(1, 2) == 65538 and h.decode_i32_be(0xFFFF, 0xFFFE) == -2
    assert abs(h.scale(1234, -2) - 12.34) < 1e-9
