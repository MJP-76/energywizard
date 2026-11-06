"""2026-11-06: när HA är nere ska inte varje avläsning försöka igen (dussintals försök/min), och felraden skrivs bara
vid tredje försöket i rad och sedan var tionde - utan traceback för nätverksfel."""
from unittest.mock import patch

import requests

import homeassistant as ha


def test_paus_efter_misslyckande_och_lugnare_logg(monkeypatch, capsys):
    monkeypatch.setattr(ha, "_states_cache", {})
    monkeypatch.setattr(ha, "_ha_fail", {"n": 0})
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise requests.exceptions.ConnectionError("SSL handshake timed out")
    clock = [1000.0]
    monkeypatch.setattr(ha.time, "time", lambda: clock[0])
    with patch.object(ha.requests, "get", side_effect=boom):
        assert ha._get_raw_state("sensor.a") is None
        for _ in range(20):                                   # samma minut: inga nya försök
            ha._get_raw_state("sensor.b")
        assert len(calls) == 1
        clock[0] += 31
        ha._get_raw_state("sensor.c")
        assert len(calls) == 2
        for _ in range(8):                                    # direkta anrop (huvudloopen)
            ha.update_states()
    out = capsys.readouterr().out
    assert out.count("❌") == 2                               # n=3 och n=10
    assert "Traceback" not in out
