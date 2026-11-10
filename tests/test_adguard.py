"""AdGuard Home: wat Sonar bewaart (en vooral wat niet), namen bij verbindingen en de vijf controles."""
import asyncio
import time

import pytest

from app import adguard as ag, main
from app.config import Settings
from app.db import DB

DAY = ag.DAY
SEG = {"segments": [{"id": "1", "name": "Default", "kind": "main"}, {"id": "2", "name": "IoT", "kind": "iot"}]}
PHONE = {"mac": "aa:00:00:00:00:01", "ip": "192.168.1.50", "name": "Telefoon", "vendor": "Apple", "network": "Default", "connected": True}
PLUG = {"mac": "aa:00:00:00:00:02", "ip": "192.168.20.7", "name": "Stekker", "vendor": "Espressif Inc.", "network": "IoT", "connected": True}
NAS = {"mac": "aa:00:00:00:00:03", "ip": "192.168.1.13", "name": "NAS", "hostname": "diskstation", "vendor": "Synology", "network": "Default", "connected": True}
GW = {"mac": "aa:00:00:00:00:fe", "ip": "192.168.1.254", "type": "gateway"}


def snap(**kw):
    return {"clients": [PHONE, PLUG, NAS], "devices": [GW], "config": {"segments": SEG, "dns_servers": ["192.168.1.10"]}, **kw}


def watcher(tmp_path, **cfg):
    s = Settings(mode="live", data_dir=str(tmp_path))
    s.adguard = {"instances": [{"name": "AG", "url": "http://192.168.1.10", "username": "u", "password": "p"}], **cfg}
    return ag.AdGuard(s, DB(str(tmp_path / "t.db")), None)


def item(client, name, t, reason="NotFilteredNotFound", answer=("203.0.113.9",), **kw):
    return {"time": time.strftime("%Y-%m-%dT%H:%M:%S.123456789+00:00", time.gmtime(t)), "client": client,
            "question": {"name": name, "type": "A"}, "reason": reason, "status": "NOERROR",
            "answer": [{"type": "A", "value": a} for a in answer], **kw}


def test_registrable_domain_and_time_parsing():
    assert ag.reg_domain("a1.eu.tuya.com") == "tuya.com"
    assert ag.reg_domain("www.bbc.co.uk") == "bbc.co.uk"
    assert ag.reg_domain("x.y.amazonaws.com") == "y.amazonaws.com"
    assert ag.reg_domain("localhost") == "localhost"
    assert not ag.interesting("nas.local") and not ag.interesting("1.1.168.192.in-addr.arpa") and not ag.interesting(ag.PROBE_NAME)
    from datetime import datetime, timezone
    want = datetime(2026, 11, 10, 8, 0, 0, 123456, tzinfo=timezone.utc).timestamp()
    assert abs(ag.parse_time("2026-11-10T09:00:00.123456789+01:00") - want) < 0.001
    assert ag.parse_time("onzin") == 0


def test_device_classes():
    assert ag.device_class(PLUG, SEG["segments"]) == "smart"
    assert ag.device_class(NAS, SEG["segments"]) == "server"
    assert ag.device_class({**PHONE, "name": "Home Assistant"}, None) == "server"
    assert ag.device_class(PHONE, SEG["segments"]) == "personal"


def test_threat_lists_are_recognized_by_name():
    lists = {1: "AdGuard DNS filter", 2: "HaGeZi's Threat Intelligence Feeds"}
    assert ag.threat_list({"reason": "FilteredSafeBrowsing"}, lists) == "AdGuard Browsing Security"
    assert ag.threat_list({"reason": "FilteredBlackList", "rules": [{"filter_list_id": 2}]}, lists) == lists[2]
    assert ag.threat_list({"reason": "FilteredBlackList", "rules": [{"filter_list_id": 1}]}, lists) is None   # gewone advertentie
    assert not ag.blocked({"reason": "FilteredSafeSearch"}) and ag.blocked({"reason": "FilteredBlackList"})


def test_personal_devices_only_get_counted(tmp_path):
    w = watcher(tmp_path)
    w.lists[w.instances()[0]["url"]] = {2: "Phishing URL Blocklist"}
    now = int(time.time())
    w.ingest([item(PHONE["ip"], "www.bank.example", now - 30), item(PLUG["ip"], "a1.eu.tuya.com", now - 20),
              item(GW["ip"], "dns.google", now - 10),
              item(PHONE["ip"], "evil.example", now - 5, "FilteredBlackList", (), rules=[{"filter_list_id": 2}])],
             snap(), w.instances()[0]["url"], now)
    q = w.db.q
    assert [r["mac"] for r in q("SELECT DISTINCT mac FROM dns_domains")] == [PLUG["mac"]]
    assert {r["mac"] for r in q("SELECT mac FROM dns_names")} == {PLUG["mac"]}
    counts = {r["mac"]: (r["q"], r["blocked"]) for r in q("SELECT mac, SUM(q) q, SUM(blocked) blocked FROM dns_hourly GROUP BY mac")}
    assert counts[PHONE["mac"]] == (2, 1) and counts["redirected"] == (1, 0)
    t = q("SELECT * FROM dns_threats")
    assert len(t) == 1 and t[0]["mac"] == PHONE["mac"] and t[0]["name"] == "evil.example"   # malware wel, ook bij een telefoon


def test_personal_switch_and_per_device_override(tmp_path):
    w = watcher(tmp_path, personal=True)
    assert w.watched(PHONE, SEG["segments"])
    w = watcher(tmp_path, watch={PLUG["mac"]: False, PHONE["mac"]: True})
    assert not w.watched(PLUG, SEG["segments"]) and w.watched(PHONE, SEG["segments"])
    now = int(time.time())
    w.ingest([item(PHONE["ip"], "a.example", now)], snap(), "u", now)
    w.forget(PHONE["mac"])
    assert not w.db.q("SELECT * FROM dns_domains") and not w.db.q("SELECT * FROM dns_names")


def test_flows_get_the_name_the_device_looked_up(tmp_path):
    w = watcher(tmp_path)
    now = int(time.time())
    w.db.store_flows([{"id": "f1", "ts": now, "dir": "out", "action": "allowed", "cc": "DE", "remote_ip": "203.0.113.9", "port": 443,
                       "domain": None, "service": "HTTPS", "proto": "TCP", "client_mac": PLUG["mac"], "client_name": "Stekker",
                       "client_ip": PLUG["ip"], "net": "IoT", "up": 1, "down": 1, "risk": "low"},
                      {"id": "f2", "ts": now, "dir": "out", "action": "allowed", "cc": "DE", "remote_ip": "203.0.113.9", "port": 443,
                       "domain": None, "service": "HTTPS", "proto": "TCP", "client_mac": PHONE["mac"], "client_name": "Telefoon",
                       "client_ip": PHONE["ip"], "net": "Default", "up": 1, "down": 1, "risk": "low"}])
    w.ingest([item(PLUG["ip"], "api.tuya.com", now - 5), item(PHONE["ip"], "news.example", now - 5)], snap(), "u", now)
    w.name_flows(now)
    names = {r["id"]: r["domain"] for r in w.db.q("SELECT id, domain FROM flows")}
    assert names == {"f1": "api.tuya.com", "f2": None}     # de telefoon wordt niet gevolgd, dus ook niet benoemd


def test_new_domains_only_after_learning(tmp_path):
    w = watcher(tmp_path)
    now = int(time.time())
    ins = "INSERT INTO dns_domains VALUES (?,?,?,?,?,?)"
    with w.db.lock, w.db.conn:
        w.db.conn.execute(ins, (PLUG["mac"], "tuya.com", now - 10 * DAY, now, 900, 0))
        w.db.conn.execute(ins, (PLUG["mac"], "strange.example", now - 3600, now, 3, 0))
        w.db.conn.execute(ins, (NAS["mac"], "synology.com", now - 2 * DAY, now, 50, 0))
        w.db.conn.execute(ins, (NAS["mac"], "new.example", now - 600, now, 1, 0))
    nd = ag.new_domains(w.db, now)
    assert list(nd) == [PLUG["mac"]] and nd[PLUG["mac"]][0]["domain"] == "strange.example"   # de NAS leert nog


def test_bypass_needs_a_full_day_and_mappable_clients(tmp_path):
    w = watcher(tmp_path)
    now = int(time.time())
    w.db.store_flows([{"id": f"{mac}-{i}", "ts": now - i * 60, "dir": "out", "action": "allowed", "cc": "US", "remote_ip": "203.0.113.5", "port": 443,
                       "domain": None, "service": "HTTPS", "proto": "TCP", "client_mac": mac, "client_name": "x", "client_ip": "x",
                       "net": "Default", "up": 1, "down": 1, "risk": "low"} for i in range(25) for mac in (PHONE["mac"], NAS["mac"])])
    w.ingest([item(NAS["ip"], "synology.com", now - 60)], snap(), "u", now)
    rows, why = ag.bypass(snap(), w.db, now, {"since": now - 3600})
    assert rows == [] and why
    rows, why = ag.bypass(snap(), w.db, now, {"since": now - 2 * DAY})
    assert [r["mac"] for r in rows] == [PHONE["mac"]] and why is None
    w.ingest([item("fe80::1", "x.example", now - 30) for _ in range(5)], snap(), "u", now)   # veel onbekende afzenders
    rows, why = ag.bypass(snap(), w.db, now, {"since": now - 2 * DAY})
    assert rows == [] and "IPv6" in why


def run_issues(sn, db):
    out = []
    ag.issues(out, sn, db, int(time.time()), lambda key, sev, *a, **kw: {"key": key, "severity": sev, "client_mac": kw.get("client_mac")})
    return {i["key"]: i["severity"] for i in out}


def test_health_issues(tmp_path):
    db = DB(str(tmp_path / "t.db"))
    ag.AdGuard(Settings(mode="live", data_dir=str(tmp_path)), db, None)   # tabellen
    down = {"host": "192.168.1.10", "name": "AG", "down": True, "median_ms": None, "checked": 1, "error": "timeout"}
    slow = {"host": "192.168.1.11", "name": "AG2", "down": False, "median_ms": 400, "checked": 1}
    sn = snap(adguard={"active": True, "servers": [down, slow], "since": None,
                       "apis": [{"name": "AG", "url": "http://192.168.1.10", "ok": False, "error": "x"},
                                {"name": "AG2", "url": "http://192.168.1.11", "ok": True, "protection": False}],
                       "servfail": {"AG2": (200, 30)},
                       "drift": {"items": [{"what": "rewrites", "missing_on": "AG2", "items": ["a → b"], "n": 1}], "names": ["AG", "AG2"]}})
    got = run_issues(sn, db)
    assert got["adguard:down:192.168.1.10"] == "critical"          # de eerste DNS-server: daar gaat alles heen
    assert got["adguard:slow:192.168.1.11"] == "warning"
    assert got["adguard:api:192.168.1.10"] == "warning" and got["adguard:protection:192.168.1.11"] == "warning"
    assert got["adguard:servfail:AG2"] == "warning" and got["adguard:drift"] == "info"
    assert run_issues(snap(adguard={"active": False}), db) == {}


def test_threat_with_ips_is_critical(tmp_path):
    w = watcher(tmp_path)
    now = int(time.time())
    with w.db.lock, w.db.conn:
        w.db.conn.execute("INSERT INTO dns_threats VALUES (?,?,?,?,?)", (now - 60, PHONE["mac"], PHONE["ip"], "evil.example", "Phishing"))
    assert run_issues(snap(adguard={"active": True}), w.db)[f"dns_threat:{PHONE['mac']}"] == "warning"
    with w.db.lock, w.db.conn:
        w.db.conn.execute("INSERT INTO ips_events VALUES (?,?,?,?,?,?)", ("i1", now - 30, 1, PHONE["ip"], 1, "{}"))
    assert run_issues(snap(adguard={"active": True}), w.db)[f"dns_threat:{PHONE['mac']}"] == "critical"


def test_querylog_paging_stops_at_cursor():
    now = int(time.time())

    class Fake:
        calls = 0

        async def get(self, http, path, **p):
            Fake.calls += 1
            start = now - (Fake.calls - 1) * ag.PAGE
            return {"data": [item("1.2.3.4", "a.example", start - i) for i in range(ag.PAGE)], "oldest": "x"}
    got = asyncio.run(ag.fetch_log(Fake(), None, now - ag.PAGE - 10))
    assert Fake.calls == 2 and len(got) == ag.PAGE + 11     # tot en met de regel net na de cursor (tijden hebben .123)


def test_dns_probe_against_local_server():
    async def go():
        loop = asyncio.get_running_loop()

        class Srv(asyncio.DatagramProtocol):
            def connection_made(self, tr):
                self.tr = tr

            def datagram_received(self, data, addr):
                self.tr.sendto(data[:2] + b"\x81\x80" + data[4:], addr)   # zelfde ID, antwoord zonder fout
        tr, _ = await loop.create_datagram_endpoint(Srv, local_addr=("127.0.0.1", 0))
        port = tr.get_extra_info("sockname")[1]
        ok = await ag.dns_probe("127.0.0.1", port=port)
        tr.close()
        bad = await ag.dns_probe("127.0.0.1", port=port, timeout=0.3)
        return ok, bad
    ok, bad = asyncio.run(go())
    assert ok["ok"] and ok["ms"] is not None and not bad["ok"]


def test_password_stays_with_its_address(tmp_path, monkeypatch):
    s = Settings(mode="live", data_dir=str(tmp_path))
    s.adguard = {"instances": [{"name": "AG", "url": "http://192.168.1.10", "username": "u", "password": "geheim"}]}
    monkeypatch.setattr(main.rt, "settings", s)
    same = main._ag_instances([main.AdGuardInstance(url="http://192.168.1.10/", username="u")])
    other = main._ag_instances([main.AdGuardInstance(url="192.168.1.99", username="u")])
    assert same[0]["password"] == "geheim" and other[0]["password"] == "" and other[0]["url"] == "http://192.168.1.99"
    with pytest.raises(main.HTTPException):
        main._ag_instances([main.AdGuardInstance(url="http://x/ $(rm)")])


def test_gateway_lan_address_other_networks_and_own_dns(tmp_path):
    """Echte UniFi geeft bij de gateway het WAN-adres; de LAN-kant staat als gateway-adres in het subnet."""
    w = watcher(tmp_path)
    now = int(time.time())
    segs = {"segments": [{**SEG["segments"][0], "subnet": "192.168.1.1/24"}, {**SEG["segments"][1], "subnet": "192.168.20.1/24"}]}
    sn = snap(devices=[{**GW, "ip": "198.51.100.7"}], config={"segments": segs, "dns_servers": ["192.168.1.10"]})
    w.ingest([item("192.168.1.1", "a.example", now - 60), item("192.168.20.1", "b.example", now - 60),
              item("10.9.0.4", "c.example", now - 60), item("192.168.1.77", "d.example", now - 60),
              item("fe80::5", "e.example", now - 60)], sn, "u", now)
    cov = ag.coverage(w.db, now)
    assert (cov["redirected"], cov["elsewhere"], cov["unknown"]) == (2, 1, 2)

    flow = lambda mac, i, ip, port, action: {"id": f"{mac}-{port}-{i}", "ts": now - i * 60, "dir": "out", "action": action, "cc": "US",
                                             "remote_ip": ip, "port": port, "domain": None, "service": "DNS", "proto": "UDP",
                                             "client_mac": mac, "client_name": "x", "client_ip": "x", "net": "Default", "up": 1, "down": 1, "risk": "low"}
    w.db.store_flows([flow(m, i, "203.0.113.5", 443, "allowed") for i in range(25) for m in (PHONE["mac"], NAS["mac"], PLUG["mac"])]
                     + [{**flow(NAS["mac"], i, "8.8.8.8", 53, "allowed"), "dir": "local"} for i in range(3)]   # omgeleid door de NAT-regel
                     + [{**flow(PLUG["mac"], i, "1.1.1.1", 853, "blocked"), "dir": "blocked"} for i in range(4)]  # tegengehouden
                     + [{**flow("aa:00:00:00:00:10", i, "9.9.9.9", 53, "allowed"), "client_ip": "192.168.1.10"} for i in range(5)]  # AdGuard zelf
                     + [flow(PHONE["mac"], i, "192.168.1.10", 53, "allowed") for i in range(2)])  # gewoon AdGuard
    own = ag.own_dns(sn, w.db, now, {})
    assert set(own) == {NAS["mac"], PLUG["mac"]}
    assert own[NAS["mac"]]["redirected"] == 3 and own[PLUG["mac"]]["blocked"] == 4
    with w.db.lock, w.db.conn:
        w.db.conn.execute("DELETE FROM dns_hourly WHERE mac='unknown'")   # anders houdt de 10%-drempel de controle tegen
    rows, why = ag.bypass(sn, w.db, now, {"since": now - 2 * DAY})
    assert why is None and [r["mac"] for r in rows] == [PHONE["mac"]]   # NAS en stekker vangt je netwerk al op
