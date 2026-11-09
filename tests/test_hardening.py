"""Verplichte inlog, intrekbare sessies, versleutelde backups, vastgelegd certificaat en geheimen per adres."""
import asyncio
import datetime as dt
import http.server
import json
import ssl
import threading

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth, backups, main
from app.config import Settings
from app import unifi_client as uc

PW = "een-lang-wachtwoord"


@pytest.fixture
def live(tmp_path, monkeypatch):
    s = Settings(mode="live", controller_url="https://unifi.invalid", api_key="k", verify_tls=True, data_dir=str(tmp_path))
    s.save()
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.rt, "settings", s)
    monkeypatch.setattr(main.rt, "collector", None)
    monkeypatch.setattr(main.rt, "db", None)
    monkeypatch.setattr(main, "login_limiter", auth.Limiter())
    return s


def first_login(s):
    c = TestClient(main.app)
    code = auth.ensure_setup_code(s.data_dir)
    r = c.post("/api/auth/setup", json={"code": code, "password": PW})
    assert r.status_code == 200
    return c, r.json()["recovery_code"]


def test_live_needs_login_and_setup_code(live):
    c = TestClient(main.app)
    state = c.get("/api/auth/state").json()
    assert state["setup_needed"] and not state["authenticated"]
    for path in ("/api/status", "/api/setup", "/api/backups"):
        assert c.get(path).status_code == 401, path
    assert c.post("/api/auth/password", json={"new": PW}).status_code == 401   # niet de eerste de beste
    assert c.post("/api/auth/setup", json={"code": "FOUT", "password": PW}).status_code == 403
    code = auth.ensure_setup_code(live.data_dir)
    assert oct((__import__("pathlib").Path(live.data_dir) / auth.SETUP_FILE).stat().st_mode)[-3:] == "600"
    assert c.post("/api/auth/setup", json={"code": code.lower().replace("-", " "), "password": "kort"}).status_code == 400
    r = c.post("/api/auth/setup", json={"code": code, "password": PW})
    assert r.status_code == 200 and r.json()["recovery_code"] and c.get("/api/status").status_code == 200
    assert not (__import__("pathlib").Path(live.data_dir) / auth.SETUP_FILE).exists()
    assert c.post("/api/auth/setup", json={"code": code, "password": PW}).status_code == 409
    assert c.post("/api/auth/disable", json={"password": PW}).status_code == 403


def test_sessions_can_be_revoked(live):
    a, _ = first_login(live)
    b = TestClient(main.app)
    assert b.post("/api/auth/login", json={"password": PW}, headers={"user-agent": "Mozilla (iPhone) Version/18 Safari/605"}).status_code == 200
    stolen = b.cookies.get(auth.COOKIE)
    rows = a.get("/api/auth/sessions").json()["rows"]
    assert len(rows) == 2 and rows[0]["current"] and rows[1]["agent"] == "iPhone · Safari" and stolen.split(".")[0] not in json.dumps(rows)
    assert a.post("/api/auth/sessions/revoke", json={"id": rows[1]["id"]}).json()["revoked"] == 1
    assert b.get("/api/status").status_code == 401 and a.get("/api/status").status_code == 200
    # uitloggen maakt de cookie echt ongeldig, ook als iemand hem had gekopieerd
    keep = a.cookies.get(auth.COOKIE)
    assert a.post("/api/auth/logout", json={}).status_code == 200
    replay = TestClient(main.app, cookies={auth.COOKIE: keep})
    assert replay.get("/api/status").status_code == 401


def test_backup_encryption(tmp_path):
    keys, recovery = backups.new_keys(PW)
    assert PW not in json.dumps(keys) and recovery not in json.dumps(keys)
    backups.store(str(tmp_path), "a.unf", b"oud", 1000)
    assert backups.encrypt_existing(str(tmp_path), keys["public"]) == 1
    backups.store(str(tmp_path), "b.unf", b"wifi-wachtwoord", 2000, keys["public"])
    files = {f["name"]: f for f in backups.listing(str(tmp_path))}
    assert set(files) == {"a.unf", "b.unf"} and all(f["encrypted"] for f in files.values()) and files["a.unf"]["ts"] == 1000
    assert b"wifi-wachtwoord" not in (tmp_path / "backups" / "b.unf.enc").read_bytes() and backups.has(str(tmp_path), "b.unf")
    for secret in (PW, recovery, recovery.lower().replace("-", "")):
        assert backups.read(str(tmp_path), "b.unf", backups.unlock(keys, secret)) == b"wifi-wachtwoord"
    assert backups.unlock(keys, "fout") is None and backups.read(str(tmp_path), "b.unf", None) is None
    moved = backups.rewrap(keys, PW, "nieuw-wachtwoord")
    assert backups.unlock(moved, "nieuw-wachtwoord") and backups.unlock(moved, PW) is None and backups.unlock(moved, recovery)
    assert backups.rewrap(keys, "fout", "x") is None
    backups.prune(str(tmp_path), keep=1)
    assert [f["name"] for f in backups.listing(str(tmp_path))] == ["b.unf"]


def test_backup_download_with_secret(live):
    c, recovery = first_login(live)
    backups.store(live.data_dir, "a.unf", b"inhoud", 1000, live.backup_keys["public"])
    dl = lambda secret: c.post("/api/backups/download", json={"name": "a.unf", "secret": secret})   # noqa: E731
    assert dl("fout").status_code == 403 and dl(recovery).content == b"inhoud" and dl(PW).content == b"inhoud"
    # een nieuw wachtwoord opent de bestaande backups ook
    assert c.post("/api/auth/password", json={"current": PW, "new": "nieuw-wachtwoord"}).status_code == 200
    assert dl("nieuw-wachtwoord").content == b"inhoud" and dl(PW).status_code == 403


def test_existing_install_can_encrypt(live):
    live.auth = auth.new_config(PW)
    live.save()
    backups.store(live.data_dir, "a.unf", b"inhoud", 1000)
    c = TestClient(main.app)
    assert c.post("/api/auth/login", json={"password": PW}).status_code == 200
    assert c.post("/api/backups/encrypt", json={"password": "fout"}).status_code == 403
    r = c.post("/api/backups/encrypt", json={"password": PW}).json()
    assert r["encrypted"] == 1 and r["recovery_code"] and c.post("/api/backups/encrypt", json={"password": PW}).status_code == 409
    assert not (backups.folder(live.data_dir) / "a.unf").exists()
    assert c.post("/api/backups/download", json={"name": "a.unf", "secret": r["recovery_code"]}).content == b"inhoud"


def test_stored_secrets_do_not_follow_a_new_address(live):
    live.mqtt = {"host": "broker.lan", "port": 1883, "password": "geheim"}
    same = main._mqtt_cfg(main.MqttSave(enabled=True, host="broker.lan", port=1883))
    other = main._mqtt_cfg(main.MqttSave(enabled=True, host="evil.example", port=1883))
    typed = main._mqtt_cfg(main.MqttSave(enabled=True, host="evil.example", port=1883, password="nieuw"))
    assert same["password"] == "geheim" and other["password"] == "" and typed["password"] == "nieuw"
    stored = {"c": {"id": "c", "url": "https://ntfy.example/x", "token": "tok"}}
    make = lambda url, token=None: main._channel(main.ChannelIn(id="c", kind="ntfy", name="n", url=url, token=token), stored)   # noqa: E731
    assert make("")["token"] == "tok" and make("https://ntfy.example/x")["token"] == "tok"
    assert make("https://evil.example/x")["token"] == "" and make("https://evil.example/x", "eigen")["token"] == "eigen"


# ---------------------------------------------------------------- certificaat
def make_cert(tmp_path, name, issuer=None):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, name)])
    now = dt.datetime.now(dt.timezone.utc)
    signer_key, signer_name = (issuer[1], issuer[0].subject) if issuer else (key, subject)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(signer_name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=30)).sign(signer_key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM)
    path = tmp_path / f"{name}.pem"
    path.write_bytes(pem + key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert, key, pem.decode(), str(path)


@pytest.fixture
def tls_server():
    seen, servers = [], []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.headers.get("X-API-KEY"))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):
            pass

    def start(certfile):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"https://127.0.0.1:{srv.server_address[1]}"
    yield start, seen
    for s in servers:
        s.shutdown()


async def get_with_key(settings):
    client = uc.UnifiClient(settings)
    try:
        await client.prepare()
        return await client.http.get("/", headers={"X-API-KEY": "geheim"})
    finally:
        await client.close()


def test_pin_on_first_use_then_refuse_other_certificate(tmp_path, tls_server):
    start, seen = tls_server
    *_, pem_a, file_a = make_cert(tmp_path, "a")
    *_, file_b = make_cert(tmp_path, "b")
    url_a, url_b = start(file_a), start(file_b)
    s = Settings(mode="live", controller_url=url_a, api_key="k")
    assert asyncio.run(get_with_key(s)).status_code == 200 and s.tls_pin.strip() == pem_a.strip() and seen == ["geheim"]
    seen.clear()
    s.controller_url = url_b         # iemand anders doet zich voor als de controller
    with pytest.raises(httpx.ConnectError) as e:
        asyncio.run(get_with_key(s))
    assert uc.certificate_changed(e.value) and seen == []      # de sleutel is niet verstuurd


def test_pin_works_for_a_certificate_from_a_ca(tmp_path, tls_server):
    start, seen = tls_server
    ca, ca_key, *_ = make_cert(tmp_path, "ca")
    *_, pem, file_leaf = make_cert(tmp_path, "leaf", issuer=(ca, ca_key))
    s = Settings(mode="live", controller_url=start(file_leaf), api_key="k", tls_pin=pem)
    assert asyncio.run(get_with_key(s)).status_code == 200 and seen == ["geheim"]


def test_expired_pin_is_not_enforced(tmp_path):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "oud")])
    old = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1)
            .not_valid_before(old).not_valid_after(old + dt.timedelta(days=1)).sign(key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    assert uc.cert_expired(pem) and uc.controller_verify(Settings(tls_pin=pem)) is False
    assert uc.controller_verify(Settings(verify_tls=True, tls_pin=pem)) is True
