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
