"""Pi-hole (versie 6) als DNS-filter: een nagebootste Pi-hole die zich gedraagt volgens de officiële API-beschrijving."""
import asyncio
import json
import time

import httpx
import pytest

from app import adguard as ag, pihole
from app.config import Settings
from app.db import DB

DAY = 86400
SEG = {"segments": [{"id": "1", "name": "Default", "kind": "main"}, {"id": "2", "name": "IoT", "kind": "iot"}]}
PHONE = {"mac": "aa:00:00:00:00:01", "ip": "192.168.1.50", "name": "Telefoon", "vendor": "Apple", "network": "Default", "connected": True}
PLUG = {"mac": "aa:00:00:00:00:02", "ip": "192.168.20.7", "name": "Stekker", "vendor": "Espressif Inc.", "network": "IoT", "connected": True}
SNAP = {"clients": [PHONE, PLUG], "devices": [], "config": {"segments": SEG, "dns_servers": ["192.168.1.10"]}}


class FakePihole:
    """Net genoeg Pi-hole om tegen te testen: sessies, de eindpunten die Sonar leest en het bladeren door het querylog."""

    def __init__(self, password="geheim", totp=False, lists=None, hosts=None):
        self.password, self.totp = password, totp
        self.sid, self.logins, self.calls = None, 0, []
        self.queries: list[dict] = []          # nieuwste eerst, zoals Pi-hole ze geeft
        self.blocking = "enabled"
        self.lists = lists or [{"id": 1, "address": "https://example.org/ads.txt", "comment": "Advertenties", "type": "block", "enabled": True},
                               {"id": 2, "address": "https://example.org/tif.txt", "comment": "Threat Intelligence Feeds", "type": "block", "enabled": True},
                               {"id": 3, "address": "https://example.org/allow.txt", "comment": None, "type": "allow", "enabled": True}]
        self.hosts = hosts if hosts is not None else ["192.168.1.13 nas.thuis.lan"]

    def add(self, t, ip, domain, status="FORWARDED", list_id=None, reply="IP", name=None):
        self.queries.insert(0, {"id": len(self.queries) + 1, "time": float(t), "type": "A", "domain": domain, "cname": None, "status": status,
                                "client": {"ip": ip, "name": name}, "dnssec": "INSECURE", "reply": {"type": reply, "time": 0.012},
                                "list_id": list_id, "upstream": "9.9.9.9#53", "ede": {"code": 0, "text": None}})
        self.queries.sort(key=lambda q: -q["time"])

    def handle(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        self.calls.append(f"{req.method} {path}")
        if path == "/api/auth" and req.method == "POST":
            ok = json.loads(req.content or b"{}").get("password") == self.password and not self.totp
            if not ok:
                return httpx.Response(401, json={"session": {"valid": False, "totp": self.totp, "sid": None, "csrf": None, "validity": -1,
                                                             "message": "password incorrect"}})
            self.logins += 1
            self.sid = f"sid-{self.logins}"
            return httpx.Response(200, json={"session": {"valid": True, "totp": False, "sid": self.sid, "csrf": "c", "validity": 300,
                                                         "message": "correct password"}})
        if path == "/api/auth" and req.method == "DELETE":
            self.sid = None
            return httpx.Response(204)
        if self.password and (self.sid is None or req.headers.get("X-FTL-SID") != self.sid):
            return httpx.Response(401, json={"error": {"key": "unauthorized", "message": "Unauthorized", "hint": None}})
        q = dict(req.url.params)
        if path == "/api/info/version":
            return httpx.Response(200, json={"version": {"core": {"local": {"branch": "master", "version": "v6.2", "hash": "x"}},
                                                         "ftl": {"local": {"version": "v6.3"}}}})
        if path == "/api/dns/blocking":
            return httpx.Response(200, json={"blocking": self.blocking, "timer": None})
        if path == "/api/lists":
            return httpx.Response(200, json={"lists": self.lists})
        if path == "/api/config/dns":
            return httpx.Response(200, json={"config": {"dns": {"upstreams": ["9.9.9.9", "1.1.1.1#53"], "hosts": self.hosts,
                                                                "cnameRecords": ["foto.thuis.lan,nas.thuis.lan"]}}})
        if path == "/api/domains":
            return httpx.Response(200, json={"domains": [{"domain": "ads.example", "type": "deny", "kind": "exact", "enabled": True}]})
        if path == "/api/stats/summary":
            return httpx.Response(200, json={"queries": {"total": 7497, "blocked": 3465, "percent_blocked": 46.2}})
        if path == "/api/stats/upstreams":
            return httpx.Response(200, json={"upstreams": [
                {"ip": "blocklist", "name": "blocklist", "port": -1, "count": 900, "statistics": {"response": 0, "variance": 0}},
                {"ip": "9.9.9.9", "name": "dns.quad9.net", "port": 53, "count": 400, "statistics": {"response": 0.0254, "variance": 0.01}}]})
        if path == "/api/queries":
            rows = [x for x in self.queries if x["time"] >= float(q.get("from", 0))]
            if "cursor" in q:
                rows = [x for x in rows if x["id"] <= int(q["cursor"])]
            start, length = int(q.get("start", 0)), int(q.get("length", 100))
            return httpx.Response(200, json={"queries": rows[start:start + length], "cursor": rows[0]["id"] if rows else None,
                                             "recordsTotal": len(self.queries), "recordsFiltered": len(rows)})
        return httpx.Response(404, json={"error": {"key": "not_found"}})


@pytest.fixture
def fake(monkeypatch):
    f = FakePihole()
    monkeypatch.setattr(pihole.API, "client", lambda self: httpx.AsyncClient(transport=httpx.MockTransport(f.handle)))
    pihole._SESSIONS.clear()
    yield f
    pihole._SESSIONS.clear()


INST = {"kind": "pihole", "name": "Pi", "url": "http://192.168.1.10/admin", "password": "geheim"}


def run(coro):
    return asyncio.run(coro)


async def call(api, method, *a):
    async with api.client() as http:
        return await getattr(api, method)(http, *a)


def test_address_and_query_mapping():
    assert pihole.base_url("192.168.1.10/admin/") == "http://192.168.1.10"
    assert pihole.base_url("https://pi.hole:8443/admin/login") == "https://pi.hole:8443"
    q = {"time": 1700000000.5, "domain": "evil.example", "status": "GRAVITY", "list_id": 2, "client": {"ip": "192.168.1.50", "name": "tel"},
         "reply": {"type": "NXDOMAIN", "time": 0.001}}
    it = pihole.to_item(q)
    assert ag.blocked(it) and it["rules"] == [{"filter_list_id": 2}] and it["client"] == "192.168.1.50"
    assert ag.parse_time(it["time"]) == 1700000000.5 and it["answer"] == []
    assert ag.threat_list(it, {2: "Threat Intelligence Feeds https://x"}) and not ag.threat_list(it, {2: "Advertenties"})
    regex = pihole.to_item({**q, "status": "REGEX", "list_id": 7})        # list_id wijst dan naar een eigen regel, geen lijst
    assert ag.blocked(regex) and "rules" not in regex
    ok = pihole.to_item({**q, "status": "FORWARDED", "list_id": None, "reply": {"type": "SERVFAIL"}})
    assert not ag.blocked(ok) and ok["status"] == "SERVFAIL"
    assert not ag.blocked(pihole.to_item({**q, "status": "CACHE"}))


def test_session_is_reused_and_renewed(fake):
    api = pihole.API(INST)
    assert api.url == "http://192.168.1.10"
    st = run(call(api, "status"))
    assert st == {"version": "v6.2", "running": True, "protection": True} and fake.logins == 1
    run(call(api, "stats"))
    assert fake.logins == 1                                   # dezelfde sessie, niet elke ronde opnieuw inloggen
    fake.sid = "weg"                                          # Pi-hole herstartte: de sessie bestaat niet meer
    assert run(call(api, "status"))["version"] == "v6.2" and fake.logins == 2
    fake.blocking = "disabled"
    assert run(call(api, "status"))["protection"] is False
    run(api.logout())
    assert fake.sid is None and "DELETE /api/auth" in fake.calls


def test_wrong_password_two_factor_and_old_version(fake):
    with pytest.raises(pihole.AuthError):
        run(call(pihole.API({**INST, "password": "fout"}), "status"))
    fake.totp = True
    pihole._SESSIONS.clear()
    with pytest.raises(pihole.AuthError, match="app"):
        run(call(pihole.API(INST), "status"))
    fake.totp = False
    with pytest.raises(pihole.AuthError):                     # zonder wachtwoord bij een Pi-hole die er wel een heeft
        run(call(pihole.API({**INST, "password": ""}), "status"))
    fake.password = ""                                        # een Pi-hole zonder wachtwoord laat iedereen toe
    assert run(call(pihole.API({**INST, "password": ""}), "status"))["version"] == "v6.2"
    r = run(ag.test_instance({**INST, "password": "fout"}))
    assert r["ok"] is False and r["kind"] == "pihole"


def test_settings_stats_and_paging(fake):
    api = pihole.API(INST)
    names, cfg = run(call(api, "settings"))
    assert names == {1: "Advertenties https://example.org/ads.txt", 2: "Threat Intelligence Feeds https://example.org/tif.txt"}   # geen allow-lijst
    assert cfg["rewrites"] == ["foto.thuis.lan → nas.thuis.lan", "nas.thuis.lan → 192.168.1.13"]
    assert cfg["upstreams"] == ["1.1.1.1#53", "9.9.9.9"] and cfg["rules"] == 1 and len(cfg["lists"]) == 2
    st = run(call(api, "stats"))
    assert st["queries"] == 7497 and st["blocked"] == 3465 and st["upstreams"] == [{"name": "dns.quad9.net#53", "avg_ms": 25.4}]
    now = time.time()
    for i in range(25):
        fake.add(now - 100 + i, "192.168.1.50", f"d{i}.example")
    fake.add(now - 500, "192.168.1.50", "oud.example")
    items, note = run(call(api, "log", now - 200, 10, 5))
    assert len(items) == 25 and note is None                  # drie pagina's van 10, niets dubbel, niets van voor 'since'
    assert items[0]["question"]["name"] == "d24.example"
    assert sum(c == "GET /api/queries" for c in fake.calls) == 3
    fake.add(now, "0.0.0.0", "hidden")
    items, note = run(call(api, "log", now - 1, 10, 5))
    assert len(items) == 1 and note and "privacy" in note.lower()


def collector(tmp_path, instances):
    s = Settings(mode="live", data_dir=str(tmp_path))
    s.adguard = {"instances": instances}
    return ag.AdGuard(s, DB(str(tmp_path / "t.db")), None)


def test_a_full_round_with_pihole(fake, tmp_path):
    w = collector(tmp_path, [INST])
    now = int(time.time())
    fake.add(now - 60, PLUG["ip"], "a1.eu.tuya.com")
    fake.add(now - 50, PLUG["ip"], "a1.eu.tuya.com")
    fake.add(now - 40, PHONE["ip"], "nu.nl")
    fake.add(now - 30, PHONE["ip"], "secure-login-check.example", status="GRAVITY", list_id=2)
    fake.add(now - 20, PHONE["ip"], "ads.example", status="GRAVITY", list_id=1)
    api = w.apis()[0]
    assert api.kind == "pihole"
    run(w._one(api, SNAP, now, True, True))
    st = w.status[api.url]
    assert st["ok"] and st["kind"] == "pihole" and st["version"] == "v6.2" and st["stats"]["queries"] == 7497
    rules = w.for_rules()
    assert rules["product"] == "Pi-hole" and rules["kinds"] == ["pihole"]
    cov = ag.coverage(w.db, now)
    assert cov["queries"] == 5 and cov["blocked"] == 2
    assert [r["domain"] for r in w.db.q("SELECT domain FROM dns_domains WHERE mac=?", (PLUG["mac"],))] == ["tuya.com"]
    assert w.db.q("SELECT COUNT(*) n FROM dns_domains WHERE mac=?", (PHONE["mac"],))[0]["n"] == 0     # telefoon: alleen tellen
    th = w.db.q("SELECT name, list FROM dns_threats")
    assert len(th) == 1 and th[0]["name"] == "secure-login-check.example" and "Threat" in th[0]["list"]
    assert w.db.q("SELECT COUNT(*) n FROM dns_names")[0]["n"] == 0        # Pi-hole bewaart geen antwoorden
    run(w._one(api, SNAP, now + 60, False, False))                        # tweede ronde: niets dubbel
    assert ag.coverage(w.db, now + 60)["queries"] == 5 and fake.logins == 1
    view = ag.view(w, SNAP, w.db, now)
    assert view["product"] == "Pi-hole" and view["names"] is False and view["instances"][0]["kind"] == "pihole"


def test_issues_name_the_right_product(fake, tmp_path):
    w = collector(tmp_path, [INST])
    now = int(time.time())
    fake.blocking = "disabled"
    api = w.apis()[0]
    run(w._one(api, SNAP, now, True, True))
    out = []
    ag.issues(out, {**SNAP, "adguard": w.for_rules()}, w.db, now,
              lambda key, sev, *a, **kw: {"key": key, "title": a[3], "detail": a[4], "advice": a[5]})
    hit = [i for i in out if i["key"].startswith("adguard:protection")]
    assert hit and "Pi-hole" in hit[0]["detail"] and "Enable Blocking" in hit[0]["advice"] and "AdGuard" not in hit[0]["advice"]


def test_mixed_kinds_and_drift(fake, tmp_path, monkeypatch):
    w = collector(tmp_path, [INST, {"kind": "pihole", "name": "Pi 2", "url": "http://192.168.1.11", "password": "geheim"},
                             {"name": "AG", "url": "http://192.168.1.12", "username": "u", "password": "p"}])
    assert [a.kind for a in w.apis()] == ["pihole", "pihole", "adguard"]
    assert w.for_rules()["product"] in ("je DNS-filter", "your DNS filter")
    now = int(time.time())
    a, b, _ = w.apis()
    run(w._one(a, SNAP, now, True, True))
    fake.hosts = []                                            # de tweede Pi-hole mist het lokale DNS-record
    run(w._one(b, SNAP, now, True, True))
    w.config["http://192.168.1.12"] = {"kind": "adguard", "rewrites": [], "lists": ["heel-anders"], "upstreams": [], "rules": 9}
    w.status["http://192.168.1.12"] = {"name": "AG", "url": "http://192.168.1.12", "kind": "adguard"}
    d = w.drift()
    assert d and d["names"] == ["Pi", "Pi 2"]                  # de AdGuard doet niet mee: ander soort, niet te vergelijken
    assert [(x["what"], x["missing_on"], x["kind"]) for x in d["items"]] == [("rewrites", "Pi 2", "pihole")]


def test_settings_keep_kind_and_never_move_a_password(monkeypatch):
    from app import main
    monkeypatch.setattr(main.rt, "settings", Settings(mode="live"))
    main.rt.settings.adguard = {"instances": [{"kind": "adguard", "name": "x", "url": "http://192.168.1.10", "username": "u", "password": "oud"}]}
    same = main._ag_instances([main.AdGuardInstance(kind="adguard", url="http://192.168.1.10", username="u")])
    assert same[0]["password"] == "oud" and same[0]["kind"] == "adguard"
    other = main._ag_instances([main.AdGuardInstance(kind="pihole", url="http://192.168.1.10", username="u")])
    assert other[0] == {"kind": "pihole", "name": "192.168.1.10", "url": "http://192.168.1.10", "username": "", "password": "", "verify_tls": False}


def test_over_a_real_socket(tmp_path):
    """Dezelfde nagebootste Pi-hole, maar nu achter een echte HTTP-server: zo gaat de hele weg via het netwerk mee."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    f = FakePihole()
    now = time.time()
    f.add(now - 30, PLUG["ip"], "shelly.cloud")

    class H(BaseHTTPRequestHandler):
        def _do(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            r = f.handle(httpx.Request(self.command, f"http://x{self.path}", headers=dict(self.headers), content=body))
            self.send_response(r.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(r.content)))
            self.end_headers()
            self.wfile.write(r.content)
        do_GET = do_POST = do_DELETE = _do

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pihole._SESSIONS.clear()
    try:
        inst = {"kind": "pihole", "name": "Pi", "url": f"http://127.0.0.1:{srv.server_port}/admin", "password": "geheim"}
        assert run(ag.test_instance(inst)) == {"ok": True, "version": "v6.2", "protection": True, "log": True, "note": None, "kind": "pihole"}
        bad = run(ag.test_instance({**inst, "password": "fout"}))
        assert bad["ok"] is False and ("wachtwoord" in bad["error"] or "password" in bad["error"])
        w = collector(tmp_path, [inst])
        run(w._one(w.apis()[0], SNAP, int(now), True, True))
        assert w.status[w.apis()[0].url]["ok"] and ag.coverage(w.db, int(now))["queries"] == 1
    finally:
        srv.shutdown()
        pihole._SESSIONS.clear()
    gone = run(ag.test_instance({"kind": "pihole", "url": "http://127.0.0.1:9", "password": "x"}))
    assert gone["ok"] is False and gone["error"]
