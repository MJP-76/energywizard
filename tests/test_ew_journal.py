"""ew_journal: installationens logg - nivåer, läsning och supportfil."""
import os

import pytest

import ew_journal


def test_nivaer():
    assert ew_journal.level_of("❌ HA: Fel vid update_states") == "fel"
    assert ew_journal.level_of("⚠️ Batteriplanen hoppade över") == "varning"
    assert ew_journal.level_of("🔔 Notis → mobile_app_x: Bilen laddar") == "notis"
    assert ew_journal.level_of("🔋 Batteri: charge - billigt") == "info"


def test_las_och_ladda_ner():
    sa = pytest.importorskip("sqlalchemy")
    url = (f"postgresql+psycopg://{os.environ.get('POSTGRES_USER', 'postgres')}:{os.environ.get('POSTGRES_PASSWORD', 'test')}"
           f"@{os.environ.get('POSTGRES_HOST', 'localhost')}/{os.environ.get('POSTGRES_DB', 'postgres')}")
    try:
        eng = sa.create_engine(url)
        conn = eng.connect()
    except Exception:
        pytest.skip("ingen testdatabas")
    with conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS ew_journal"))
        conn.execute(sa.text("CREATE TABLE ew_journal (id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ DEFAULT now(), src TEXT, lvl TEXT, mod TEXT, msg TEXT)"))
        conn.execute(sa.text("INSERT INTO ew_journal (src, lvl, mod, msg) VALUES ('motor','fel','main.loop','❌ Easee svarade inte'),"
                             "('app','info','app.car','Nissan: heat_on'), ('motor','info','main.loop','🔋 Batteri: hold')"))
        conn.commit()
        assert len(ew_journal.read(conn)) == 3
        assert [r["msg"] for r in ew_journal.read(conn, lvl="fel")] == ["❌ Easee svarade inte"]
        assert [r["src"] for r in ew_journal.read(conn, q="batteri")] == ["motor"]
        txt = ew_journal.export_text(conn, 1)
        assert txt.count("\n") == 3 and "[motor] fel" in txt
        conn.execute(sa.text("DROP TABLE ew_journal"))
        conn.commit()


def test_kallan_ar_koden_som_skrev_och_forloppet_kommer_en_gang(monkeypatch):
    import builtins
    import traceback
    got = []
    monkeypatch.setattr(ew_journal, "add", lambda msg, lvl=None, mod="": got.append((mod, msg)))
    orig = builtins.print
    monkeypatch.setattr(ew_journal.sys, "excepthook", ew_journal.sys.excepthook)
    monkeypatch.setattr(ew_journal.threading, "excepthook", ew_journal.threading.excepthook)
    monkeypatch.setattr(ew_journal, "_started", False)
    monkeypatch.setattr(ew_journal.sys, "modules", dict(ew_journal.sys.modules))
    ew_journal.sys.modules.pop("pytest", None)
    monkeypatch.setattr(ew_journal.threading, "Thread", lambda *a, **k: type("T", (), {"start": lambda self: None})())
    try:
        ew_journal.install("motor")

        def skriver():
            try:
                raise ValueError("x")
            except ValueError:
                print("❌ något gick fel")
                traceback.print_exc()
        skriver()
    finally:
        builtins.print = orig
    assert len(got) == 1 and got[0][0].endswith(".skriver") and "Traceback" in got[0][1]
