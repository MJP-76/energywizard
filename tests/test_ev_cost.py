"""ev_cost.py: laddat idag/veckan/månaden och vad det kostade (FTW 0.162-idé)."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "smartbox"))
import ev_cost  # noqa: E402


def test_perioder_i_svensk_tid():
    now = datetime(2026, 11, 8, 0, 30, tzinfo=ev_cost.SWE)        # söndag strax efter midnatt
    b = ev_cost.bounds(now)
    assert b["today"].isoformat().startswith("2026-11-08T00:00")
    assert b["week"].isoformat().startswith("2026-11-02T00:00")   # måndag
    assert b["month"].isoformat().startswith("2026-11-01T00:00")


class Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *a, **k):
        rows = self.rows

        class R:
            def all(self_inner):
                return rows
        return R()

    def rollback(self):
        pass


def test_luckor_ger_delvis():
    now = datetime(2026, 11, 8, 12, 0, tzinfo=ev_cost.SWE)
    # idag: 12 h förflutet men bara 6 h loggat -> delvis; veckan: helt loggad
    rows = [("today", 6.0, 10.0, 0.0, 25.0), ("week", 6 * 24 + 12, 100.0, 20.0, 200.0), ("month", 7 * 24 + 12, 120.0, 20.0, 240.0)]
    s = ev_cost.summary(Conn(rows), now)
    assert s["today"]["partial"] is True and s["today"]["kr"] == 25
    assert s["week"]["partial"] is False and s["week"]["solar_kwh"] == 20.0
