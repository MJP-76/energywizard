"""#184: NIBE 43427 "Status kompressor" ger statuskoder (20/40/60/100) eller text, inte frekvens."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "smartbox"))
from drivers.heatpump_ha_entities import compressor_running  # noqa: E402

E = "sensor.status_kompressor_43427"


def test_nibe_statuskoder():
    assert compressor_running(E, 20.0, lambda: None) is False
    assert compressor_running(E, 40.0, lambda: None) is True
    assert compressor_running(E, 60.0, lambda: None) is True
    assert compressor_running(E, 100.0, lambda: None) is False


def test_text():
    assert compressor_running(E, None, lambda: "Running") is True
    assert compressor_running(E, None, lambda: "Stopped") is False
    assert compressor_running(E, None, lambda: "konstigt") is None


def test_frekvens_som_forut():
    assert compressor_running("sensor.kompressorfrekvens_aktuell", 20.0, lambda: None) is True
    assert compressor_running("sensor.kompressorfrekvens_aktuell", 0.0, lambda: None) is False
    assert compressor_running(None, 5.0, lambda: None) is None
