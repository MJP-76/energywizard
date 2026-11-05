"""#122: översiktens bild visar installationens bilar och spabad - inte Emils Tesla/Nissan/spa."""
import live_flow

ROW = {"net_power": 500, "pv_power_w": 0, "house_consumption_w": 500, "spa_temp": None, "spa_power_w": 0,
       "ev_power_kw": 0, "ev_carport_power_kw": 3.7, "tesla_soc": 40, "nissan_soc": 60, "kia_soc": 55}


def _ids(d):
    return {n["id"] for n in d.get("nodes", d.get("items", []))} if isinstance(d, dict) else set()


def test_bara_installationens_bilar_och_inget_spa():
    d = live_flow.nodes(dict(ROW), cars=[("kia", "Kia EV6", "ev_power_kw")], has_spa=False)
    txt = str(d)
    assert "Kia EV6" in txt and "Tesla" not in txt and "Nissan" not in txt and "Spabad" not in txt


def test_utan_installation_bara_neutrala_laddboxar():
    txt = str(live_flow.nodes(dict(ROW)))
    assert "Laddbox 1" in txt and "Nissan" not in txt and "Tesla" not in txt      # inga fasta bilnamn
