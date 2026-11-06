"""#165: inga inbyggda pumpadresser - Husdata läses bara när installationen angett pumpens adress."""
import importlib


def _fresh(monkeypatch, ip="", fb=""):
    monkeypatch.setenv("PUMP_IP", ip)
    monkeypatch.setenv("PUMP_IP_FALLBACK", fb)
    import pump
    return importlib.reload(pump)


def test_utan_adress_forsoks_ingen_anslutning(monkeypatch, capsys):
    pump = _fresh(monkeypatch)
    assert pump.PUMP_IPS == []
    called = []
    monkeypatch.setattr(pump, "ModbusTcpClient", lambda *a, **k: called.append(a))
    assert pump.read_sensors() is None and pump.read_sensors() is None
    assert called == []
    out = capsys.readouterr().out
    assert out.count("ingen adress") == 1 and "❌" not in out           # en varning, inget fel varje minut


def test_adress_ur_miljon_eller_installationen(monkeypatch):
    pump = _fresh(monkeypatch, "10.0.0.5", "10.0.0.6")
    assert pump.PUMP_IPS == ["10.0.0.5", "10.0.0.6"]
    pump.configure("10.9.9.9")                                          # miljön går före
    assert pump.PUMP_IPS == ["10.0.0.5", "10.0.0.6"]
    pump = _fresh(monkeypatch)
    pump.configure("192.168.1.XXX  # FYLL I")                           # guidens platshållare räknas inte
    assert pump.PUMP_IPS == []
    pump.configure(["10.1.1.1", "10.1.1.1"])
    assert pump.PUMP_IPS == ["10.1.1.1"]


def test_husdata_drivrutinen_tar_adressen_ur_installationen(monkeypatch):
    pump = _fresh(monkeypatch)
    import house_config
    house_config.build_heat_pump_driver({"heat_pump": {"enabled": True, "driver": "thermia_husdata",
                                                       "connection": {"modbus_host": "10.2.2.2"}}})
    assert pump.PUMP_IPS == ["10.2.2.2"]
