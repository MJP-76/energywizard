"""logger._coerce_bools: bool-värden får inte fälla hela minutloggen (DatatypeMismatch hos hus med andra drivrutiner)."""
import logger


def test_bool_blir_heltal_utom_i_boolkolumner(monkeypatch):
    monkeypatch.setattr(logger, "_bool_columns", {"flagga"})
    ut = logger._coerce_bools({"compressor_running": True, "alarm_active": False, "flagga": True, "temp": 21.5, "x": None})
    assert ut == {"compressor_running": 1, "alarm_active": 0, "flagga": True, "temp": 21.5, "x": None}
    assert type(ut["compressor_running"]) is int


def test_utan_databas_blir_alla_bool_heltal(monkeypatch):
    monkeypatch.setattr(logger, "_bool_columns", None)
    def boom():
        raise RuntimeError("ingen db")
    monkeypatch.setattr(logger, "get_db", boom)
    assert logger._coerce_bools({"a": True, "b": 2}) == {"a": 1, "b": 2}
