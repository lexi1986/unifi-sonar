"""De uitbreidingen: DNS om je DNS-server heen, storingen, verbruik per apparaat, firewall-audit, mislukte verbindingen,
UniFi-anomalieën, kanaaladvies, vaste pauzetijden, wifi-meting, beveiligingsadviezen en een nieuw publiek IP."""
import asyncio
import time

import pytest

from app import advisories, i18n, rules_extra, schedules, segments
from app.collector import Collector
from app.config import Settings
from app.db import DB
from app.mock import MockNetwork
from app.unifi_client import (config_from_raw, normalize_anomalies, normalize_client_usage, normalize_wan_history,
                              normalize_wifi_connectivity)

RSS = """<?xml version="1.0"?><rss><channel><item><title><![CDATA[Security Advisory Bulletin 080]]></title>
<link>https://community.ui.com/releases/x</link><pubDate>Sat, 07 Nov 2026 10:00:00 GMT</pubDate>
<description><![CDATA[<p><strong>Summary 1 of 1</strong></p><p>A malicious actor with access to the network could exploit a flaw in UniFi Access Points to do bad things.</p>
<p><strong>Affected Products:<br></strong>UniFi Access Points (Version 6.7.20 and earlier)<br>UniFi Network Application (Version 10.1.85 and earlier)<br>UniFi Network Application (Version 10.2.93 and earlier)</p>
<p><strong>Mitigation:<br></strong>Update UniFi Access Points to Version 6.7.21 or later.<br>Update UniFi Network Application to Version 10.2.97 or later.</p>
<p><strong>Base Score: </strong>9.1 Critical</p><p>CVE: CVE-2026-1234</p>]]></description></item></channel></rss>"""


def test_advisory_parse_and_match():
    items = advisories.parse(RSS)
    s = items[0]["summaries"][0]
    assert items[0]["id"] == "080" and s["score"] == 9.1 and s["cves"] == ["CVE-2026-1234"]
    assert ("UniFi Access Points", "6.7.20") in s["affected"] and ("UniFi Access Points", "6.7.21") in s["fixed"]
    inv = [{"kind": "ap", "name": "AP Zolder", "version": "6.7.20.15000"}, {"kind": "ap", "name": "AP Nieuw", "version": "6.8.2"},
           {"kind": "network", "name": "UniFi Network", "version": "10.1.90"}]
    m = advisories.match(items, inv)
    assert {d["name"] for x in m for d in x["devices"]} == {"AP Zolder"}   # 10.1.90 zit in de 10.1-lijn, die tot 10.1.85 getroffen was
    assert advisories.match(items, [{"kind": "network", "name": "N", "version": "10.1.80"}])
    assert next(x for x in m if x["product"].startswith("UniFi Access"))["fixed"] == "6.7.21"
    # versielijnen: 10.1.86 valt onder 10.1.85? nee; maar 10.1.80 wel
    assert advisories.affected_any("10.1.80", ["10.1.85", "10.2.93"]) and not advisories.affected_any("10.2.97", ["10.1.85", "10.2.93"])
    # een UXG is geen Dream Machine
    assert advisories._kind("Dream Machines, Cloud Gateways and Dream Wall") == "gw-console"
    assert advisories._kind("UniFi Gateways") == "gw-uxg" and advisories._gw_kind("UXGA6AA") == "gw-uxg"


def test_schedule_window_over_midnight():
    s = {"id": 1, "name": "Kinderen", "macs": ["aa:bb:cc:dd:ee:ff"], "days": [0, 1, 2, 3, 4], "start": "21:00", "stop": "07:00",
         "enabled": True}
    t = lambda d, h, m=0: time.mktime((2026, 11, d, h, m, 0, 0, 0, -1))  # noqa: E731 – 9 november 2026 is een maandag
    assert schedules.window(s, t(9, 20, 59)) is None and schedules.window(s, t(9, 21))
    assert schedules.window(s, t(14, 6)) and not schedules.window(s, t(14, 21, 30))   # vrijdagnacht wel, zaterdagavond niet
    assert schedules.wanted([s], t(10, 3))["aa:bb:cc:dd:ee:ff"]["until"] == t(10, 7)
    with pytest.raises(ValueError):
        schedules.clean({**s, "start": "25:00"})
    assert schedules.clean({**s, "macs": ["AA:BB:CC:DD:EE:FF", "rommel"]})["macs"] == ["aa:bb:cc:dd:ee:ff"]


def test_normalizers():
    agg = {"wan_history": {"wan_history_details": [{"network_group": "WAN", "isp_name": "X", "uptime": 99.9,
           "downtime_history": [{"id": 7, "timestamp": 1_800_000_000_000, "downtime_in_seconds": 120}],
           "health_history": [{"timestamp": 1_800_000_000_000, "wan_downtime": True}, {"timestamp": 1, "not_reported": True}]}]},
           "wifi_connectivity": {"radio_connectivity": [{"radio_filter": "ng", "attempts": {"total_attempts": 10,
                                 "failed_client_connections": 3, "success_ratio": 70.0, "association_ratio": 100.0,
                                 "authentication_ratio": 75.0, "dhcp_ratio": 70.0, "dns_ratio": 70.0}}]}}
    w = normalize_wan_history(agg)[0]
    assert w["outages"] == [{"id": "7", "ts": 1_800_000_000, "seconds": 120}] and len(w["health"]) == 1
    assert normalize_wifi_connectivity(agg)["2.4"]["failed"] == 3
    # vanuit het netwerk gezien: tx is wat naar het apparaat gaat (download)
    u = normalize_client_usage([{"time": 1_800_000_000_000, "user": "AA:BB", "tx_bytes": 900, "rx_bytes": 100}])[0]
    assert u == {"ts": 1_800_000_000, "mac": "aa:bb", "down": 900.0, "up": 100.0}
    assert len(normalize_anomalies([{"anomaly": "USER_SLEEPY_CLIENT", "mac": "AA", "timestamps": [1_800_000_000_000, 1_800_000_060_000]}])) == 2


def test_firewall_audit_and_dns_servers():
    m = MockNetwork()
    cfg = config_from_raw(m.config_raw())
    kinds = {(f["type"], f["rule"]) for f in cfg["segments"]["audit"]}
    assert ("shadowed", "Blokkeer IoT-camera") in kinds and ("opens", "Tablet IoT tijdelijk") in kinds
    assert cfg["dns_servers"] == ["192.168.1.22"]
    # internet → binnen zonder beperking is 'exposed'
    zones, pols = MockNetwork.firewall()
    pols = pols + [{"name": "Alles open", "action": "ALLOW", "enabled": True, "index": 9000, "predefined": False, "protocol": "all",
                    "connection_state_type": "ALL", "source": {"zone_id": "z-ext", "matching_target": "ANY"},
                    "destination": {"zone_id": "z-int", "matching_target": "ANY"}}]
    nets = m.config()[3]
    assert any(f["type"] == "exposed" for f in segments.build(nets, zones, pols)["audit"])


def test_dns_kind_and_channel_candidates():
    assert rules_extra.dns_kind({"port": 53}) == "dns" and rules_extra.dns_kind({"port": 853}) == "dot"
    assert rules_extra.dns_kind({"port": 443, "domain": "dns.google"}) == "doh" and rules_extra.dns_kind({"port": 443, "domain": "x.nl"}) is None
    cand = lambda ch, w: [r["channel"] for r in rules_extra.channel_table(  # noqa: E731
        {"mac": "a", "radios": [{"radio": "5", "channel": ch, "width": w}]}, "5", {"neighbors": []}, [])]
    assert cand(36, 80) == [36, 149] and 52 in cand(100, 80) and 165 not in cand(36, 80)


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    import os
    os.environ["NO_DOTENV"] = "1"
    tmp = tmp_path_factory.mktemp("x")
    st = Settings(mode="mock", db_path=str(tmp / "s.db"), mock_seed_hours=1, data_dir=str(tmp))
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    return col


def test_demo_issues(demo):
    keys = {i["key"].split(":")[0] for i in demo.latest["issues"]}
    assert {"dns_leak", "fw_shadow", "fw_opens", "conn_fail", "ufi_anom", "cfg_quieter", "advisory", "wan_outage"} <= keys
    leak = {i18n.issue(i, "en")["title"] for i in demo.latest["issues"] if i["key"].startswith("dns_leak")}
    assert "Fire TV bypasses your DNS server" in leak
    adv = next(i for i in demo.latest["issues"] if i["key"].startswith("advisory"))
    assert adv["notify"] and adv["severity"] == "warning" and "AP Kantoor (6.5.62)" in adv["detail"]
    # de DNS-server zelf (upstream) telt niet als lek
    assert not any("Pi-hole" in i["title"] for i in demo.latest["issues"] if i["key"].startswith("dns_leak"))


def test_endpoints(demo, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main.rt, "collector", demo)
    monkeypatch.setattr(main.rt, "db", demo.db)
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    c = TestClient(main.app)
    o = c.get("/api/outages").json()
    assert o["available"] and 99 < o["uptime"]["day"] < 100 and len(o["months"]) == 6 and o["outages"][0]["seconds"] == 720
    u = c.get("/api/usage/clients?period=week").json()
    assert u["rows"][0]["name"] == "TV Woonkamer" and u["dpi"] and u["rows"][0]["cats"]
    assert c.get(f"/api/usage/client/{u['rows'][0]['mac']}").json()["days"]
    ap = next(d for d in demo.latest["devices"] if d["name"] == "AP Woonkamer")
    nb = c.get(f"/api/neighbors/{ap['mac']}").json()
    assert nb["available"] and any(r["current"] for r in nb["channels"]["2.4"])
    assert c.get("/api/wifi/connectivity").json()["bands"]["all"]["attempts"] == 182
    assert len(c.get("/api/selftest/down?mb=2").content) == 2 << 20
    assert c.post("/api/selftest/up", content=b"x" * 5000).json()["bytes"] == 5000
    r = c.post("/api/selftest/result", json={"down": 400, "up": 300, "ping": 2.5, "room": "Zolder"}).json()["result"]
    assert r["room"] == "Zolder" and r["name"] == "iPhone" and c.get("/api/selftests").json()["rows"][0]["down"] == 400
    a = c.get("/api/advisories").json()
    assert a["enabled"] and a["items"][0]["affects"]


def test_schedule_endpoint_pauses_and_releases(demo, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main.rt, "collector", demo)
    monkeypatch.setattr(main.rt, "db", demo.db)
    c = TestClient(main.app)
    mac = next(x["mac"] for x in demo.latest["clients"] if x["name"] == "PS5")
    assert c.post("/api/schedules/save", json={"name": "", "macs": [mac], "days": [0], "start": "21:00", "stop": "07:00"}).status_code == 400
    sid = c.post("/api/schedules/save", json={"name": "Altijd", "macs": [mac], "days": list(range(7)), "start": "00:00",
                                              "stop": "23:59"}).json()["id"]
    assert mac in demo.mock.blocked and mac in c.get("/api/schedules").json()["paused"]
    c.post("/api/schedules/delete", json={"id": sid})
    assert mac not in demo.mock.blocked
    with i18n.use("en"):
        msgs = [e["message"] for e in demo.db.events(0, 50)]
    assert any("paused by 'Altijd'" in m for m in msgs) and any("pause time 'Altijd' over" in m for m in msgs)


def test_public_ip_change(demo):
    snap = {"wan": {"wan_ip": "203.0.113.24"}, "devices": [], "clients": []}
    demo.db.set_kv("wan_ip", {"ip": "203.0.113.1"})
    demo._track_wan_ip(snap, int(time.time()))
    assert snap["wan_ip_change"]["old"] == "203.0.113.1"
    out = []
    rules_extra.public_ip(out, snap, __import__("app.rules", fromlist=["_issue"])._issue, None)
    assert out[0]["notify"] and "203.0.113.24" in out[0]["detail"]


def test_source_recovers_after_a_hiccup(monkeypatch, tmp_path):
    """Eén DNS-hapering mag Sonar niet blijvend op de beperkte officiële API laten staan."""
    from app import unifi_client as uc
    monkeypatch.setenv("NO_DOTENV", "1")
    clock = [1000.0]
    monkeypatch.setattr(uc.time, "monotonic", lambda: clock[0])
    c = uc.UnifiClient(Settings(mode="live", controller_url="https://unifi.invalid", api_key="k", data_dir=str(tmp_path)))
    legacy_ok, calls = [True], []

    async def legacy(use_key):
        calls.append("legacy")
        if not legacy_ok[0]:
            raise OSError("Temporary failure in name resolution")
        return {}

    async def integration():
        calls.append("integration")
        return {}

    monkeypatch.setattr(c, "_fetch_legacy", legacy)
    monkeypatch.setattr(c, "_fetch_integration", integration)
    poll = lambda: asyncio.run(c.fetch())  # noqa: E731
    assert poll()["source"] == "legacy-key"
    legacy_ok[0] = False
    assert poll()["source"] == "integration"          # de hapering: terugvallen mag
    legacy_ok[0] = True
    calls.clear()
    clock[0] += 299
    assert poll()["source"] == "integration" and calls == ["integration"]   # nog niet opnieuw proberen
    clock[0] += 1
    assert poll()["source"] == "legacy-key"           # na 5 minuten weer terug op de rijke bron
    # werkt de rijke bron echt niet, dan blijft het bij één poging per 5 minuten
    legacy_ok[0] = False
    assert poll()["source"] == "integration"
    clock[0] += 300
    calls.clear()
    assert poll()["source"] == "integration" and calls == ["legacy", "integration"]
    calls.clear()
    assert poll()["source"] == "integration" and calls == ["integration"]


# ------------------------------------------------------------------ inlog
def test_auth_tokens_and_limiter():
    from app import auth
    cfg = auth.new_config("een-lang-wachtwoord")
    assert auth.enabled(cfg) and auth.verify_password("een-lang-wachtwoord", cfg["hash"]) and not auth.verify_password("fout", cfg["hash"])
    tok = auth.make_token(cfg, now=1000)
    assert auth.token_valid(cfg, tok, now=2000) and not auth.token_valid(cfg, tok, now=1000 + auth.SESSION_SECONDS + 1)
    assert not auth.token_valid(cfg, tok.replace(".", ".0"), now=2000) and not auth.token_valid(cfg, None) and not auth.token_valid({}, tok)
    assert not auth.token_valid(auth.new_config("een-lang-wachtwoord"), tok, now=2000)   # nieuw geheim: oude sessies vervallen
    assert not auth.should_renew(tok, now=1000) and auth.should_renew(tok, now=1000 + auth.RENEW_AFTER + 1)
    lim = auth.Limiter()
    for _ in range(auth.MAX_FAILS):
        assert lim.wait("a", now=10) == 0
        lim.failed("a", now=10)
    assert lim.wait("a", now=10) > 0 and lim.wait("b", now=10) == 0 and lim.wait("a", now=10 + auth.FAIL_WINDOW + 1) == 0


def test_login_locks_the_api(demo, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main.rt, "collector", demo)
    monkeypatch.setattr(main.rt, "db", demo.db)
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.rt.settings, "auth", {})
    monkeypatch.setattr(main, "login_limiter", main.auth_mod.Limiter())
    c = TestClient(main.app)
    assert c.get("/api/snapshot").status_code == 200 and c.get("/api/auth/state").json()["enabled"] is False
    assert c.post("/api/auth/password", json={"new": "kort"}).status_code == 400
    assert c.post("/api/auth/password", json={"new": "een-lang-wachtwoord"}).status_code == 200
    assert '"auth"' in (tmp_path / "config.json").read_text() and "een-lang-wachtwoord" not in (tmp_path / "config.json").read_text()
    assert c.get("/api/snapshot").status_code == 200   # deze browser blijft ingelogd
    anon = TestClient(main.app)
    for path in ("/api/snapshot", "/api/status", "/api/setup", "/api/mqtt"):
        assert anon.get(path).status_code == 401, path
    assert anon.post("/api/speedtest", json={}).status_code == 401
    assert anon.get("/").status_code == 200 and anon.get("/api/auth/state").json() == {"enabled": True, "authenticated": False, "min_length": 8, "passkeys": 0}
    assert anon.post("/api/auth/login", json={"password": "fout"}).status_code == 403
    assert anon.post("/api/auth/login", json={"password": "een-lang-wachtwoord"}).status_code == 200
    cookie = anon.cookies.get(main.auth_mod.COOKIE)
    assert cookie and anon.get("/api/snapshot").status_code == 200
    assert anon.post("/api/auth/password", json={"current": "fout", "new": "nog-een-wachtwoord"}).status_code == 403
    assert anon.post("/api/auth/disable", json={"password": "een-lang-wachtwoord"}).status_code == 200
    assert TestClient(main.app).get("/api/snapshot").status_code == 200
    # te vaak raden
    main.rt.settings.auth = main.auth_mod.new_config("een-lang-wachtwoord")
    guess = TestClient(main.app)
    codes = [guess.post("/api/auth/login", json={"password": "fout"}).status_code for _ in range(main.auth_mod.MAX_FAILS + 1)]
    assert codes[-1] == 429 and codes[0] == 403
    assert guess.post("/api/auth/login", json={"password": "een-lang-wachtwoord"}).status_code == 429


def test_auth_reset_keeps_the_rest(tmp_path):
    import json
    from app import auth
    f = tmp_path / "config.json"
    f.write_text(json.dumps({"mode": "mock", "auth": {"hash": "x", "secret": "y"}}))
    assert auth.reset_file(str(tmp_path)) and json.loads(f.read_text()) == {"mode": "mock"} and not auth.reset_file(str(tmp_path))


# ------------------------------------------------------------------ vertraging onder belasting
def test_bufferbloat_grades():
    from app import bufferbloat as bb
    assert [bb.grade(x) for x in (1, 5, 29, 59, 199, 399, 400)] == ["A+", "A", "A", "B", "C", "D", "F"]
    r = bb.summarize({"idle": [9, 10, 11], "download": [30, 40, 50], "upload": [510, 520, 1500]}, "h", 5)
    assert r["idle"] == 10 and r["added_down"] == 30 and r["added_up"] == 510 and r["grade"] == "F"
    assert bb.summarize({"idle": [9, 10], "download": [30, 40, 50]}, "h", 5) is None           # te weinig rustmetingen
    assert bb.summarize({"idle": [9, 10, 11], "download": [30]}, "h", 5) is None                # te weinig onder belasting
    # de gateway zei niet in welke fase hij zat
    assert bb.summarize({"idle": [9, 10, 11], "load": [40, 40, 40]}, "h", 5)["added_up"] == 30


def test_bufferbloat_issue_and_result(demo):
    demo._bloat = {"host": "h", "idle": [9, 10, 11], "download": [500, 510, 520], "upload": [30, 30, 30], "load": []}
    before = list(demo.bloat_history)
    demo._bloat_done()
    assert demo.bloat_history[-1]["grade"] == "F" and demo.db.get_kv("bufferbloat")["items"][-1]["grade"] == "F" and demo._bloat is None
    out = []
    rules_extra.bufferbloat(out, {"bufferbloat": demo.bloat_history[-1]}, __import__("app.rules", fromlist=["_issue"])._issue, None)
    assert out and "Smart Queues" in out[0]["advice"]
    out.clear()
    rules_extra.bufferbloat(out, {"bufferbloat": {**demo.bloat_history[-1], "grade": "B"}}, __import__("app.rules", fromlist=["_issue"])._issue, None)
    assert not out
    demo.bloat_history = before


# ------------------------------------------------------------------ aanwezigheid in Home Assistant
def test_presence_trackers(demo):
    import json
    from app.ha_mqtt import HAMqtt
    c0 = next(c for c in demo.latest["clients"] if c.get("connected", True))
    gone = "aa:bb:cc:00:00:01"
    s = Settings(mode="mock", data_dir="x", mqtt={"presence": [{"mac": c0["mac"], "name": "Telefoon"}, {"mac": gone, "name": "Weg"}], "presence_grace": 300})
    ha = HAMqtt(s, demo)
    conf = {t: json.loads(p) for t, p in ha.discovery() if "/device_tracker/" in t}
    tid = c0["mac"].replace(":", "")
    cfg = conf[f"homeassistant/device_tracker/unifi_sonar/{tid}/config"]
    assert len(conf) == 2 and cfg["name"] == "Telefoon" and cfg["source_type"] == "router" and cfg["payload_home"] == "home"
    p = ha.presence()
    assert p[c0["mac"]]["home"] and not p[gone]["home"]
    # even van de wifi: binnen de wachttijd nog thuis, daarna weg
    keep = demo.latest["clients"]
    last_ok = demo.last_ok
    demo.latest["clients"] = [c for c in keep if c["mac"] != c0["mac"]]
    ref = int(last_ok or time.time())
    demo.last_ok = ref + 299
    assert ha.presence()[c0["mac"]]["home"]
    demo.last_ok = ref + 301
    assert not ha.presence()[c0["mac"]]["home"]
    demo.latest["clients"], demo.last_ok = keep, last_ok
    # niet meer gevolgd: de oude entiteit gaat uit Home Assistant
    demo.db.set_kv("mqtt_presence", {"ids": [tid, "oud000000000"]})
    retired = dict(ha.retired())
    assert retired == {"homeassistant/device_tracker/unifi_sonar/oud000000000/config": "", "sonar/unifi_sonar/presence/oud000000000": "",
                       "sonar/unifi_sonar/presence/oud000000000/attrs": ""}


# ------------------------------------------------------------------ UniFi-backups
def test_backup_store_and_prune(tmp_path):
    import os
    from app import backups as b
    d = str(tmp_path)
    for i in range(b.KEEP + 3):
        b.store(d, f"autobackup_{i}.unf", b"x" * 10, 1000 + i)
    b.prune(d)
    rows = b.listing(d)
    assert len(rows) == b.KEEP and rows[0]["name"] == f"autobackup_{b.KEEP + 2}.unf" and not b.has(d, "autobackup_0.unf")
    assert os.stat(tmp_path / "backups" / rows[0]["name"]).st_mode & 0o077 == 0 and os.stat(tmp_path / "backups").st_mode & 0o077 == 0
    assert b.path_of(d, "../config.json") is None and b.path_of(d, "..%2fx.unf") is None
    with pytest.raises(ValueError):
        b.store(d, "../x.unf", b"x")
    with pytest.raises(ValueError):
        b.store(d, "leeg.unf", b"")
    assert b.summary(d, False, now=1000 + 41 * 86400)["stale"] and not b.summary(d, False, now=2000)["stale"]
    assert b.summary(d, True, now=1100 + 4 * 86400)["stale"]


def test_backups_copied_from_controller(tmp_path, monkeypatch):
    """Alleen wat nieuw is wordt opgehaald, en een halve download wordt niet bewaard."""
    from app import backups as b
    monkeypatch.setenv("NO_DOTENV", "1")
    st = Settings(mode="live", controller_url="https://unifi.invalid", api_key="k", db_path=str(tmp_path / "s.db"), data_dir=str(tmp_path))
    col = Collector(st, DB(st.db_path))
    rows = [{"filename": "autobackup_1.unf", "size": 4, "time": 1_800_000_000_000}]
    asked, made = [], []

    async def lst():
        return rows

    async def dl(path):
        asked.append(path)
        return b"data"

    async def create():
        made.append(1)
        return b"vers"

    monkeypatch.setattr(col.client, "backups_list", lst)
    monkeypatch.setattr(col.client, "backup_download", dl)
    monkeypatch.setattr(col.client, "backup_create", create)
    asyncio.run(col.collect_backups())
    assert asked == ["/dl/autobackup/autobackup_1.unf"] and not made and b.listing(st.data_dir)[0]["ts"] == 1_800_000_000
    asyncio.run(col.collect_backups())                       # binnen 6 uur: niets
    asyncio.run(col.collect_backups(force=True))             # bestaat al: niet opnieuw
    assert len(asked) == 1
    rows.append({"filename": "autobackup_2.unf", "size": 999, "time": 1_800_000_100_000})
    asyncio.run(col.collect_backups(force=True))
    assert not b.has(st.data_dir, "autobackup_2.unf") and "autobackup_2.unf" in col.backup_status["error"]
    rows.pop()
    st.backup_daily = True
    asyncio.run(col.collect_backups(force=True))
    asyncio.run(col.collect_backups(force=True))             # dagelijks: maar één keer per dag
    assert len(made) == 1 and any(x["source"] == "sonar" for x in b.listing(st.data_dir)) and col.backup_status["error"] is None
    asyncio.run(col.client.close())


def test_backup_download_needs_login(demo, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main.rt, "collector", demo)
    monkeypatch.setattr(main.rt, "db", demo.db)
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.rt.settings, "data_dir", demo.s.data_dir)
    monkeypatch.setattr(main.rt.settings, "auth", {})
    asyncio.run(demo.collect_backups(force=True))
    c = TestClient(main.app)
    info = c.get("/api/backups").json()
    name = info["files"][0]["name"]
    assert info["files"] and not info["can_download"] and c.get(f"/api/backups/download/{name}").status_code == 403
    monkeypatch.setattr(main.rt.settings, "auth", main.auth_mod.new_config("een-lang-wachtwoord"))
    assert c.get(f"/api/backups/download/{name}").status_code == 401   # niet ingelogd
    assert c.post("/api/auth/login", json={"password": "een-lang-wachtwoord"}).status_code == 200
    r = c.get(f"/api/backups/download/{name}")
    assert r.status_code == 200 and r.content.startswith(b"demo") and "attachment" in r.headers["content-disposition"]
    assert c.get("/api/backups/download/geheim.unf").status_code == 404
    out = []
    rules_extra.backup_stale(out, {"backups": {"count": 0, "newest": None, "daily": False, "stale": True}}, __import__("app.rules", fromlist=["_issue"])._issue, None)
    assert out and out[0]["key"] == "backup_stale"


# ------------------------------------------------------------------ passkeys
def test_passkey_site_rules_and_challenges():
    from app import passkeys as pk
    assert pk.rp_id_for("192.168.1.5", "https") is None and pk.rp_id_for("sonar.example.com", "http") is None
    assert pk.rp_id_for("Sonar.Example.com.", "https") == "sonar.example.com" and pk.rp_id_for("localhost", "http") == "localhost"
    store = pk.Challenges()
    cid = store.add("login", b"x", "a.example", "https://a.example")
    assert store.take(cid, "register", "a.example", "https://a.example") is None   # verkeerd soort: meteen weg
    cid = store.add("login", b"x", "a.example", "https://a.example")
    assert store.take(cid, "login", "b.example", "https://b.example") is None
    cid = store.add("login", b"x", "a.example", "https://a.example")
    assert store.take(cid, "login", "a.example", "https://a.example")["challenge"] == b"x"
    assert store.take(cid, "login", "a.example", "https://a.example") is None      # maar één keer te gebruiken


def test_passkey_endpoints(demo, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main.rt, "collector", demo)
    monkeypatch.setattr(main.rt, "db", demo.db)
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.rt.settings, "auth", main.auth_mod.new_config("een-lang-wachtwoord"))
    monkeypatch.setattr(main.rt.settings, "allowed_hosts", ["sonar.example.com"])
    monkeypatch.setattr(main, "login_limiter", main.auth_mod.Limiter())
    (tmp_path / "config.json").write_text("{}")
    https = {"host": "sonar.example.com", "x-forwarded-proto": "https"}
    c = TestClient(main.app)
    assert c.post("/api/auth/passkey/register/options", json={"password": "een-lang-wachtwoord"}, headers=https).status_code == 401   # niet ingelogd
    assert c.post("/api/auth/passkey/login/options", headers=https).status_code == 400                                                # nog geen passkeys
    assert c.post("/api/auth/login", json={"password": "een-lang-wachtwoord"}).status_code == 200
    assert c.post("/api/auth/passkey/register/options", json={"password": "fout"}, headers=https).status_code == 403                  # wachtwoord nodig
    assert c.post("/api/auth/passkey/register/options", json={"password": "een-lang-wachtwoord"}).status_code == 400                  # geen https
    r = c.post("/api/auth/passkey/register/options", json={"name": "Telefoon", "password": "een-lang-wachtwoord"}, headers=https).json()
    o = r["options"]
    assert o["rp"]["id"] == "sonar.example.com" and o["authenticatorSelection"]["residentKey"] == "required" and o["authenticatorSelection"]["userVerification"] == "required"
    assert c.post("/api/auth/passkey/register", json={"id": r["id"], "credential": {"id": "x"}}, headers=https).status_code == 400
    assert not main.rt.settings.auth.get("passkeys")
    # een bestaande passkey blijft staan als je het wachtwoord wijzigt
    key = {"id": "AAAA", "public_key": "AAAA", "sign_count": 0, "rp_id": "sonar.example.com", "name": "Telefoon", "created": 1, "last_used": None}
    main.rt.settings.auth = {**main.rt.settings.auth, "passkeys": [key]}
    assert c.post("/api/auth/password", json={"current": "een-lang-wachtwoord", "new": "nieuw-lang-wachtwoord"}).status_code == 200
    assert main.rt.settings.auth["passkeys"] == [key]
    assert c.get("/api/auth/passkeys").json()["rows"][0]["here"] is False and "public_key" not in c.get("/api/auth/passkeys").json()["rows"][0]
    # een verzonnen handtekening komt er niet in
    anon = TestClient(main.app)
    assert anon.get("/api/auth/state").json()["passkeys"] == 1
    r = anon.post("/api/auth/passkey/login/options", headers=https).json()
    bad = {"id": "AAAA", "rawId": "AAAA", "type": "public-key", "response": {"clientDataJSON": "AAAA", "authenticatorData": "AAAA", "signature": "AAAA"}}
    assert anon.post("/api/auth/passkey/login", json={"id": r["id"], "credential": bad}, headers=https).status_code == 403
    assert anon.get("/api/snapshot").status_code == 401
    assert c.post("/api/auth/passkey/delete", json={"id": "AAAA"}).status_code == 200 and main.rt.settings.auth["passkeys"] == []
