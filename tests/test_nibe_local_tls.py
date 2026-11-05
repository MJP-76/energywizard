"""#145: en riktig NIBE S1255 svarar med Connection: close. Förut gav läsningen "Bad file descriptor" (settimeout på en
stängd socket). Här: en riktig lokal TLS-server som stänger efter svaret, och en som håller öppet."""
import datetime as dt
import hashlib
import http.server
import json
import ssl
import tempfile
import threading

import pytest

pytest.importorskip("cryptography")
from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402

import drivers.heatpump_nibe_local as nl  # noqa: E402

BODY = json.dumps({"devices": [{"deviceIndex": 0, "product": {"name": "", "serialNumber": "123"}}]}).encode()


def _cert():
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "nibe-test")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    d = tempfile.mkdtemp()
    open(f"{d}/c.pem", "wb").write(cert.public_bytes(serialization.Encoding.PEM))
    open(f"{d}/k.pem", "wb").write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                     serialization.NoEncryption()))
    return f"{d}/c.pem", f"{d}/k.pem", hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def _server(close):
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0" if close else "HTTP/1.1"

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(BODY)))
            if close:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(BODY)

        def log_message(self, *a):
            pass
    certf, keyf, pin = _cert()
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certf, keyf)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, pin


@pytest.mark.parametrize("close", [True, False])
def test_svaret_las_oavsett_om_pumpen_stanger(close, monkeypatch):
    srv, pin = _server(close)
    monkeypatch.setattr(nl, "_USERNAME", "u")
    monkeypatch.setattr(nl, "_PASSWORD", "p")
    try:
        r = nl._request("127.0.0.1", srv.server_address[1], pin, "GET", "/api/v1/devices", 5)
        assert r["devices"][0]["deviceIndex"] == 0
    finally:
        srv.shutdown()


def test_tomt_produktnamn_godtas_och_forvald_modell_anvands(monkeypatch):
    drv = nl.NibeLocalHeatPumpDriver(connection={"host": "127.0.0.1", "expected_product": "NIBE S1255"})
    calls = []

    def fake_call(method, path, payload=None):
        calls.append(path)
        return json.loads(BODY) if path.endswith("/devices") else {}
    monkeypatch.setattr(drv, "_call", fake_call)
    drv._read_points()
    assert drv._product == "NIBE S1255"                      # registren för S1155/S1255 väljs efter modellen
