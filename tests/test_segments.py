import asyncio

from app import rules, segments
from app.collector import Collector
from app.config import Settings
from app.db import DB
from app.mock import MockNetwork

ZONES, POLICIES = MockNetwork.firewall()
NETS = [{"_id": "net-default", "name": "Default", "purpose": "corporate", "firewall_zone_id": "z-int"},
        {"_id": "net-iot", "name": "IoT", "purpose": "corporate", "vlan": 20, "firewall_zone_id": "z-iot"},
        {"_id": "net-gast", "name": "Gasten", "purpose": "guest", "vlan": 30}]


def cl(name, vendor="", host=None, net="Default", wired=False):
    return {"mac": f"aa:{abs(hash(name)) % 256:02x}:00:00:00:01", "name": name, "vendor": vendor, "hostname": host,
            "network": net, "wired": wired, "connected": True, "ap_mac": None if wired else "ap", "sw_mac": "sw" if wired else None}


def test_smart_reason():
    assert segments.smart_reason(cl("x", "Espressif Inc.")) == "fabrikant Espressif"
    assert segments.smart_reason(cl("x", host="tasmota-1234")) == "naam tasmota-1234"
    assert segments.smart_reason(cl("x", host="Samsung-Washer")) == "naam Samsung-Washer"
    for c in (cl("iPhone", "Apple, Inc."), cl("Pixel", "Google, Inc."), cl("TV", "Samsung Electronics"),
              cl("Speaker", "Sonos, Inc."), cl("Laptop", "Dell Inc.", "desk-pc")):
        assert segments.smart_reason(c) is None, c["name"]


def test_build_classifies_and_reads_zone_matrix():
    seg = segments.build(NETS, ZONES, POLICIES)
    kinds = {s["name"]: (s["kind"], s["isolated"]) for s in seg["segments"]}
    assert kinds == {"Default": ("main", None), "IoT": ("iot", True), "Gasten": ("guest", None)}
    cells = seg["matrix"]["cells"]
    assert cells["z-iot>z-int"]["default"] == "block" and cells["z-iot>z-int"]["effective"] == "block"
    assert [r["name"] for r in cells["z-iot>z-int"]["rules"]] == ["IoT naar Home Assistant", "IoT naar Pi-hole"]
    assert cells["z-iot>z-int"]["rules"][1]["port"] == "53" and cells["z-iot>z-int"]["rules"][1]["proto"] == "tcp/udp"
    # een eigen 'alles toestaan'-regel maakt Internal → IoT effectief open, ook al is de standaard dicht
    assert cells["z-int>z-iot"]["default"] == "block" and cells["z-int>z-iot"]["effective"] == "allow"
    assert [z["name"] for z in seg["matrix"]["zones"]][:2] == ["Internal", "IoT"]
    # zonder zones (oude firewall) geen tabel en geen oordeel over afscherming
    old = segments.build(NETS, None, None)
    assert old["matrix"] is None and {s["name"]: s["kind"] for s in old["segments"]}["IoT"] == "iot"
    assert all(s["isolated"] is None for s in old["segments"])


def _issues(seg, clients):
    out = []
    rules._segment_checks(out, {"clients": clients, "devices": []}, seg, lambda m: m or "?")
    return out


def test_rules_misplaced_open_and_suggestion():
    seg = segments.build(NETS, ZONES, POLICIES)
    out = _issues(seg, [cl("ESP", "Espressif Inc."), cl("Shelly", "Shelly", net="IoT"), cl("iPhone", "Apple, Inc."),
                        cl("Cam", "Reolink Innovation Limited", wired=True)])
    assert sorted(i["title"] for i in out) == ["Cam staat op je hoofdnetwerk", "ESP staat op je hoofdnetwerk"]
    assert all(i["severity"] == "info" and i["category"] == "security" for i in out)
    assert "Virtual Network Override → IoT" in next(i for i in out if i["title"].startswith("ESP"))["advice"]
    assert "switchpoort" in next(i for i in out if i["title"].startswith("Cam"))["advice"]

    # IoT-netwerk in de Internal-zone: wel een VLAN, maar niet afgeschermd
    zones = [dict(z, network_ids=["net-default", "net-iot"]) if z["_id"] == "z-int"
             else dict(z, network_ids=[]) if z["_id"] == "z-iot" else z for z in ZONES]
    nets = [dict(n, firewall_zone_id="z-int") if n["_id"] == "net-iot" else n for n in NETS]
    open_seg = segments.build(nets, zones, POLICIES)
    assert {s["name"]: s["kind"] for s in open_seg["segments"]}["IoT"] == "iot"
    keys = {i["key"]: i for i in _issues(open_seg, [])}
    assert keys["segment_open:net-iot"]["severity"] == "warning"

    # geen apart netwerk: één tip bij ≥3 slimme apparaten, geen losse meldingen
    flat = segments.build(NETS[:1], ZONES, POLICIES)
    few = _issues(flat, [cl("A", "Espressif Inc."), cl("B", "Tuya Smart Inc.")])
    many = _issues(flat, [cl("A", "Espressif Inc."), cl("B", "Tuya Smart Inc."), cl("C", host="shelly-plug")])
    assert few == [] and [i["key"] for i in many] == ["segment:none"]


def test_demo_and_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_DOTENV", "1")
    from fastapi.testclient import TestClient
    from app import main
    st = Settings(mode="mock", db_path=str(tmp_path / "s.db"), mock_seed_hours=1)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    titles = {i["title"] for i in col.latest["issues"] if i["key"].startswith("segment")}
    assert titles == {"ESP Weerstation staat op je hoofdnetwerk", "Camera Tuin staat op je hoofdnetwerk",
                      "P1 Meter staat op je hoofdnetwerk"}
    monkeypatch.setattr(main.rt, "collector", col)
    monkeypatch.setattr(main.rt, "db", col.db)
    d = TestClient(main.app).get("/api/segments").json()
    assert d["available"]
    by = {s["name"]: s for s in d["segments"]}
    assert by["IoT"]["isolated"] and by["IoT"]["clients"] >= 10 and by["Default"]["smart"] == 3
    ha = d["matrix"]["cells"]["z-iot>z-int"]["rules"][0]
    assert ha["targets"] == ["Home Assistant"]      # IP-adres vertaald naar de naam van het apparaat


def test_flows_between_networks():
    nets = NETS[:2] + [{"_id": "net-wg", "name": "WireGuard", "purpose": "remote-user-vpn", "vpn_type": "wireguard-server",
                        "enabled": True, "firewall_zone_id": "z-vpn"}]
    nets = [dict(n, ip_subnet=sn) for n, sn in zip(nets, ("192.168.1.1/24", "192.168.20.1/24", "10.8.0.1/24"))]
    seg = segments.build(nets, ZONES, POLICIES)
    fwd = [{"name": "NAS SSH", "enabled": True, "fwd_ip": "192.168.1.13", "port": "22", "proto": "tcp"}]
    fl = segments.flows(seg, fwd)
    assert {n["id"] for n in fl["nodes"]} == {"net-default", "net-iot", "net-wg", "gateway", "internet"}
    e = {(x["from"], x["to"]): x for x in fl["edges"]}
    assert e[("net-iot", "net-default")]["status"] == "partial"           # dicht, behalve HA en DNS
    assert [r["name"] for r in e[("net-iot", "net-default")]["rules"]] == ["IoT naar Home Assistant", "IoT naar Pi-hole"]
    assert e[("net-default", "net-iot")]["status"] == "allow"             # eigen regel 'alles toestaan'
    assert e[("net-iot", "internet")]["status"] == "allow" and e[("net-iot", "gateway")]["status"] == "allow"
    assert e[("net-iot", "net-wg")]["status"] == "block" and e[("net-wg", "net-iot")]["status"] == "block"
    assert e[("internet", "net-default")]["status"] == "partial"          # port forward
    assert e[("internet", "net-default")]["rules"][0]["forward"]
    assert e[("internet", "net-iot")]["status"] == "block"
    assert ("internet", "gateway") not in e and ("gateway", "net-iot") not in e

    # een regel naar een adres in een ánder netwerk van dezelfde zone telt niet mee voor dit netwerk
    nets2 = nets + [{"_id": "net-lab", "name": "Lab", "purpose": "corporate", "ip_subnet": "192.168.50.1/24",
                     "firewall_zone_id": "z-int"}]
    zones2 = [dict(z, network_ids=z["network_ids"] + ["net-lab"]) if z["_id"] == "z-int" else z for z in ZONES]
    fl2 = segments.flows(segments.build(nets2, zones2, POLICIES))
    e2 = {(x["from"], x["to"]): x for x in fl2["edges"]}
    assert e2[("net-iot", "net-lab")]["status"] == "block" and e2[("net-iot", "net-default")]["status"] == "partial"
    assert e2[("net-default", "net-lab")]["status"] == "allow"            # Internal → Internal

    # alles-afvangende blokkade vóór een uitzondering: de uitzondering komt nooit aan de beurt
    pols = POLICIES + [{"_id": "x", "name": "Alles dicht", "action": "BLOCK", "enabled": True, "index": 5000,
                        "predefined": False, "protocol": "all", "connection_state_type": "ALL",
                        "source": {"zone_id": "z-int", "matching_target": "ANY"},
                        "destination": {"zone_id": "z-iot", "matching_target": "ANY"}}]
    e3 = {(x["from"], x["to"]): x for x in segments.flows(segments.build(nets, ZONES, pols))["edges"]}
    assert e3[("net-default", "net-iot")]["status"] == "block"
    assert [r["name"] for r in e3[("net-default", "net-iot")]["rules"]] == ["Alles dicht"]


def test_rule_targets_skip_vendor_names(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_DOTENV", "1")
    from fastapi.testclient import TestClient
    from app import main
    st = Settings(mode="mock", db_path=str(tmp_path / "t.db"), mock_seed_hours=1)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    for c in col.latest["clients"]:
        if c["ip"] == "192.168.1.22":   # Pi-hole zonder eigen naam: UniFi toont dan de fabrikant
            c.update(name=c["vendor"], hostname=None)
    monkeypatch.setattr(main.rt, "collector", col)
    monkeypatch.setattr(main.rt, "db", col.db)
    d = TestClient(main.app).get("/api/segments").json()
    dns = d["matrix"]["cells"]["z-iot>z-int"]["rules"][1]
    assert dns["targets"] == ["192.168.1.22"]
