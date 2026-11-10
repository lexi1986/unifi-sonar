"""De kwetsbaarheidscheck: wat er wel en niet gecontroleerd mag worden, en dat de uitkomst eerlijk is over de dekking."""
import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path

from app import advisories as adv, portprobe, vulnscan
from app.config import Settings
from app.db import DB

SEG = {"segments": [{"id": "1", "name": "Default", "kind": "main"}, {"id": "2", "name": "IoT", "kind": "iot"}, {"id": "3", "name": "Gast", "kind": "guest"}]}


def client(ip, net="Default", **kw):
    return {"ip": ip, "mac": f"aa:{ip}", "name": ip, "network": net, "connected": True, **kw}


def scan(tmp_path, mock=True):
    s = Settings(mode="mock", data_dir=str(tmp_path))
    return vulnscan.VulnScan(s, DB(str(tmp_path / "t.db")), mock)


def test_targets_only_known_private_non_iot_devices():
    tg, skipped = vulnscan.targets([client("192.168.1.2"), client("192.168.20.3", "IoT"), client("192.168.30.4", "Gast"), client("8.8.8.8"),
                                    client("192.168.1.5", connected=False), client("192.168.1.6", hostname="shelly-1"), client("10.0.0.7", "Onbekend")], SEG)
    assert [t["ip"] for t in tg] == ["192.168.1.2"]
    assert skipped == {"iot": 2, "guest": 1, "unknown": 1, "offline": 2, "limit": 0}


def test_without_network_info_nothing_is_scanned():
    tg, skipped = vulnscan.targets([client("192.168.1.2")], None)
    assert tg == [] and skipped["unknown"] == 1


def test_probe_refuses_public_addresses():
    assert portprobe.allowed("192.168.1.1") and portprobe.allowed("10.1.1.1") and portprobe.allowed("172.31.0.1")
    for ip in ("8.8.8.8", "127.0.0.1", "169.254.1.1", "::1", "172.32.0.1", "onzin"):
        assert not portprobe.allowed(ip)


def test_probe_process_runs_without_environment_and_refuses_loopback():
    script = Path(portprobe.__file__)
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    # 127.0.0.1 mag niet: dan krijg je een lege uitslag in plaats van een verbinding
    job = {"targets": ["127.0.0.1"], "ports": [srv.getsockname()[1]], "delay": 0, "timeout": 0.5}
    r = subprocess.run([sys.executable, "-I", str(script)], input=json.dumps(job).encode(), capture_output=True, env={}, timeout=20)
    srv.close()
    assert json.loads(r.stdout.splitlines()[-1]) == {"result": {}}


def test_probe_finds_open_and_closed(monkeypatch):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    port = srv.getsockname()[1]
    monkeypatch.setattr(portprobe, "allowed", lambda ip: True)
    res = asyncio.run(portprobe.run({"targets": ["127.0.0.1"], "ports": [port, 1], "delay": 0, "timeout": 0.5}))
    srv.close()
    assert res["127.0.0.1"]["open"] == [port] and res["127.0.0.1"]["closed"] == 1


def test_kev_parsing_and_marking():
    kev = vulnscan.parse_kev({"vulnerabilities": [{"cveID": "CVE-1", "vendorProject": "Ubiquiti", "product": "UniFi OS", "knownRansomwareCampaignUse": "Known"}]})
    assert kev["CVE-1"]["ransomware"] is True
    assert vulnscan.mark_exploited([{"cves": ["CVE-1", "CVE-2"]}], kev)[0]["exploited"] == ["CVE-1"]


def test_os_server_minimum_only_for_exploited_flaws():
    items = adv.demo(1000)
    assert vulnscan.os_server_minimum(items, vulnscan.DEMO_KEV)["version"] == "5.0.8"
    assert vulnscan.os_server_minimum(items, {}) is None


def test_internetdb_404_is_no_data_not_clean():
    class R:
        status_code = 404

    class H:
        async def get(self, *a, **k):
            return R()
    assert asyncio.run(vulnscan.fetch_outside(H(), "8.8.8.8", 5))["state"] == "nodata"
    assert asyncio.run(vulnscan.fetch_outside(H(), "100.64.1.1", 5))["state"] == "nat"


def test_expected_service_stops_counting(tmp_path):
    v = scan(tmp_path)
    v.ports = {"ran": 1, "hosts": [{"mac": "m", "ip": "192.168.1.2", "name": "x", "network": "Default", "open": [1883, 22], "answered": True}], "skipped": {}}
    assert v.for_rules()["findings"] == 1   # SSH is beheer en telt niet
    v.accept("m", 1883, True)
    assert v.for_rules()["findings"] == 0
    assert scan(tmp_path).accepted == {"m:1883"}   # blijft bewaard


def test_coverage_says_what_was_not_looked_at(tmp_path):
    v = scan(tmp_path)
    d = v.view({"devices": [], "clients": []}, {"hardware": "UOSSERVER"}, adv.demo(1000), True)
    states = {c["id"]: c["state"] for c in d["coverage"]}
    assert states["ports"] == "off" and states["outside"] == "off" and states["software"] == "none" and states["os_server"] == "manual"
    assert d["summary"]["checked"] == 0


CFG = {"forwards": [
    {"name": "HA", "enabled": True, "upnp": False, "port": "443", "fwd_ip": "192.168.1.10", "fwd_port": "8123"},
    {"name": "Spel", "enabled": True, "upnp": True, "port": "3000-3010", "fwd_ip": "192.168.1.20", "fwd_port": "3000-3010"},
    {"name": "Oude camera", "enabled": False, "upnp": False, "port": "8080", "fwd_ip": "192.168.1.30", "fwd_port": "80"}],
    "vpn": [{"name": "WG", "type": "wireguard", "enabled": True, "port": 51820}, {"name": "OVPN", "type": "openvpn", "enabled": False, "port": 1024}]}
DAY = vulnscan.DAY


def test_port_spec_parsing():
    assert vulnscan._covers("443", 443) and not vulnscan._covers("443", 444)
    assert vulnscan._covers("80, 443", 443)
    assert vulnscan._covers("3000-3010", 3005) and not vulnscan._covers("3000-3010", 3011)
    assert vulnscan._covers("1-65535", 9999)          # een forward over alles verklaart ook alles
    assert not vulnscan._covers("", 1) and not vulnscan._covers("x-y,0,70000", 0)


def test_outside_ports_are_explained_by_the_controller():
    now = 1_000 * DAY
    hosts = [{"ip": "192.168.1.10", "open": [22, 8123]}]
    rows = {r["port"]: r for r in vulnscan.explain_outside([443, 3005, 51820, 1024, 8080, 9999], CFG, hosts, {"8080": now - 20 * DAY}, {"wan:9999"}, now)}
    assert rows[443]["state"] == "expected" and rows[443]["via"][0]["to"] == "192.168.1.10:8123"
    assert rows[443]["via"][0]["also"] == [{"port": 22, "name": "SSH"}]   # de doorgezette poort zelf telt niet als 'ook open'
    assert rows[3005]["state"] == "expected" and rows[3005]["via"][0]["kind"] == "upnp"
    assert rows[3005]["via"][0]["to"] == "192.168.1.20:3005"            # reeks op reeks wijst naar dezelfde plek in de reeks
    assert rows[51820]["state"] == "expected" and rows[51820]["via"][0]["kind"] == "vpn"
    assert rows[1024]["state"] == "stale" and rows[1024]["via"][0]["name"] == "OVPN"
    assert rows[8080]["state"] == "lingering"                              # al 20 dagen bij Shodan terwijl de forward uitstaat
    assert rows[9999]["state"] == "unexplained" and rows[9999]["accepted"]


def test_without_forwards_nothing_is_called_unexplained():
    rows = vulnscan.explain_outside([443], {"forwards": None}, [], {}, set(), 0)
    assert rows[0]["state"] == "unknown"
    assert vulnscan.explain_outside([443], None, [], {}, set(), 0)[0]["state"] == "unknown"


def test_outside_findings_count_and_accept(tmp_path):
    v = scan(tmp_path, mock=False)
    v.s.vulnscan = {"outside": True}
    v.outside = {"state": "ok", "ip": "203.0.113.5", "ports": [443, 1024, 9999], "vulns": [], "first_seen": {}}
    r = v.for_rules(CFG)
    assert r["findings"] == 1 and r["stale"] == 1      # 9999 is onverklaard, 1024 waarschijnlijk oud, 443 hoort zo
    v.accept("wan", 9999, True)
    v.accept("wan", 1024, True)
    assert v.for_rules(CFG) == {"findings": 0, "exploited": 0, "stale": 0}
    v.s.vulnscan = {"outside": False}
    assert v.for_rules(CFG)["findings"] == 0           # uitgezet: Shodan telt niet meer mee


def test_first_seen_is_remembered_across_lookups(tmp_path):
    v = scan(tmp_path, mock=False)
    v.s.vulnscan = {"outside": True}
    calls = iter([{"state": "ok", "ip": "203.0.113.5", "ports": [443], "vulns": []},
                  {"state": "ok", "ip": "203.0.113.5", "ports": [443, 1024], "vulns": []},
                  {"state": "ok", "ip": "203.0.113.5", "ports": [1024], "vulns": []}])

    async def fake(http, ip, ts):
        return {**next(calls), "fetched": ts}
    vulnscan.fetch_outside, orig = fake, vulnscan.fetch_outside
    try:
        asyncio.run(v.refresh_outside("203.0.113.5", 100))
        asyncio.run(v.refresh_outside("203.0.113.5", 200))
        assert v.outside["first_seen"] == {"443": 100, "1024": 200}
        asyncio.run(v.refresh_outside("203.0.113.5", 300))
        assert v.outside["first_seen"] == {"1024": 200}
    finally:
        vulnscan.fetch_outside = orig


def test_stale_ports_raise_an_info_issue_only():
    from app import rules_extra
    out = []
    rules_extra.vuln_issue(out, {"vuln": {"findings": 0, "exploited": 0, "stale": 1}}, lambda key, sev, *a, **kw: {"key": key, "severity": sev})
    assert [(i["key"], i["severity"]) for i in out] == [("vuln:outside_stale", "info")]
    out = []
    rules_extra.vuln_issue(out, {"vuln": {"findings": 2, "exploited": 0, "stale": 0}}, lambda key, sev, *a, **kw: {"key": key, "severity": sev})
    assert [(i["key"], i["severity"]) for i in out] == [("vuln:findings", "warning")]
