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
