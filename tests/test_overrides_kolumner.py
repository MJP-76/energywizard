"""Hus 5 (telemetri 2026-11-06): logger.set_override föll på StringDataRightTruncation. Gästladdningens JSON är längre
än de gamla 64 tecknen, så överstyrningarnas värde lagras som TEXT och enhetsnamnet får vara upp till 200 tecken."""
import json
from pathlib import Path


def test_overrides_rymmer_gastladdningens_json():
    guest = json.dumps({"kwh": 12.5, "until": "2026-11-07T07:00:00+01:00", "set_at": "2026-11-06T22:41:13.123456+01:00"})
    assert len(guest) > 64
    src = (Path(__file__).resolve().parent.parent / "smartbox" / "logger.py").read_text(encoding="utf-8")
    assert "ALTER TABLE overrides ALTER COLUMN mode TYPE TEXT" in src
    assert "ALTER TABLE overrides ALTER COLUMN device TYPE VARCHAR(200)" in src
