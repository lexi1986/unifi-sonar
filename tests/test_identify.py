"""Naamloze apparaten herkennen, een naam geven en quarantaine."""
import asyncio
import os
import time

import pytest

from app import identify
from app.collector import Collector
from app.config import Settings
from app.db import DB

SEGS = [{"id": "1", "name": "Default", "kind": "main"}, {"id": "2", "name": "IoT", "kind": "iot"}]


def test_unnamed():
    assert identify.unnamed({"mac": "aa:bb:cc:dd:ee:ff", "name": "aa:bb:cc:dd:ee:ff"})
    assert identify.unnamed({"mac": "x", "name": "Tuya Smart Inc.", "vendor": "Tuya Smart Inc."})
    assert identify.unnamed({"mac": "x", "name": "lwip0"}) and identify.unnamed({"mac": "x", "name": "ESP_4F2A1C"})
    assert identify.unnamed({"mac": "x", "name": "android-1a2b3c4d5e6f7a8b"})
    assert not identify.unnamed({"mac": "x", "name": "Wasmachine", "vendor": "Miele"})


def test_guess_combines_domains_vendor_and_hostname():
    plug = {"mac": "aa:00:00:00:46:30", "name": "lwip0", "hostname": "lwip0", "vendor": "Tuya Smart Inc.", "network": "Default"}
    g = identify.guess(plug, {"a1.tuyaeu.com": 412, "pool.ntp.org": 30}, SEGS)
    assert g["brand"] == "Tuya" and g["kind"] == "smart" and g["confidence"] == "high"
    assert any("tuyaeu.com" in e for e in g["evidence"]) and any("Tuya Smart" in e for e in g["evidence"])
    assert g["name"] == "Tuya-stekker" and "hint" in g                        # slim apparaat op het hoofdnetwerk
    rows = [{"mac": "aa:00:00:00:46:30", "guess": dict(g)}, {"mac": "aa:00:00:00:99:01", "guess": dict(g)}]
    identify._unique(rows, [])
    assert [r["guess"]["name"] for r in rows] == ["Tuya-stekker 46:30", "Tuya-stekker 99:01"]   # twee gelijke: met staartje

    only_vendor = identify.guess({"mac": "aa:00:00:00:00:01", "name": "Espressif Inc.", "vendor": "Espressif Inc."}, {})
    assert only_vendor["confidence"] == "low" and "ESP" in only_vendor["label"]

    # het specifieke domein wint van de algemene fabrikant: een Echo, geen 'Amazon-apparaat'
    echo = identify.guess({"mac": "aa:00:00:00:00:02", "name": "Amazon Technologies Inc.", "vendor": "Amazon Technologies Inc."},
                          {"avs-alexa-eu.amazon.com": 90})
    assert echo["label"] == "Amazon Echo" and echo["confidence"] == "high"

    phone = identify.guess({"mac": "be:12:00:00:00:03", "name": "iPhone-van-Sam", "hostname": "iPhone-van-Sam", "vendor": ""}, {})
    assert phone["label"] == "iPhone" and phone["kind"] == "phone"
    assert identify.guess({"mac": "aa:00:00:00:00:04", "name": "x", "vendor": "Acme"}, {"example.com": 4}) is None

    # een algemeen domein overstemt geen fabrikant met een vast MAC-adres
    hub = identify.guess({"mac": "f4:f5:d8:00:00:05", "name": "Google, Inc.", "vendor": "Google, Inc."}, {"play.googleapis.com": 200})
    assert hub["label"] == "Google Nest of Chromecast" and hub["confidence"] == "medium"
    vm = identify.guess({"mac": "bc:24:11:00:00:06", "name": "x", "vendor": "Proxmox Server Solutions GmbH"}, {"web.push.apple.com": 14})
    assert vm["kind"] == "server"
    # met een privé-adres is het wél gewoon een telefoon
    tel = identify.guess({"mac": "e2:00:00:00:00:07", "name": "x", "vendor": "Google, Inc."}, {"play.googleapis.com": 200})
    assert tel["kind"] == "phone" and identify.random_mac("e2:00:00:00:00:07") and not identify.random_mac("f4:f5:d8:00:00:05")


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    os.environ["NO_DOTENV"] = "1"
    tmp = tmp_path_factory.mktemp("id")
    st = Settings(mode="mock", db_path=str(tmp / "s.db"), mock_seed_hours=1, data_dir=str(tmp))
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    return col


@pytest.fixture
def client(demo, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main.rt, "collector", demo)
    monkeypatch.setattr(main.rt, "db", demo.db)
    return TestClient(main.app)


def test_demo_has_recognisable_unnamed_devices_and_naming_works(demo, client):
    devs = client.get("/api/identify").json()["devices"]
    by_label = {d["guess"]["label"]: d for d in devs if d["guess"]}
    assert "Daikin-warmtepomp of -airco" in by_label and "tado-bridge" in by_label
    assert any(d["guess"] and d["guess"]["brand"] == "Bosch/Siemens" for d in devs)
    assert all(identify.unnamed({"mac": d["mac"], "name": d["name"], "vendor": d["vendor"]}) for d in devs)
    mac = by_label["tado-bridge"]["mac"]
    assert client.get(f"/api/identify/{mac}").json()["unnamed"]
    r = client.post(f"/api/clients/{mac}/name", json={"name": "  Tado   Bridge "}).json()
    assert r["ok"] and r["name"] == "Tado Bridge"
    assert next(c for c in demo.latest["clients"] if c["mac"] == mac)["name"] == "Tado Bridge"
    assert demo.mock.names[mac] == "Tado Bridge"                        # blijft staan na de volgende ronde
    assert not client.get(f"/api/identify/{mac}").json()["unnamed"]
    assert client.post(f"/api/clients/{mac}/name", json={"name": "   "}).status_code == 400
    assert client.post("/api/clients/00:00:00:00:00:00/name", json={"name": "x"}).status_code == 404


def test_quarantine_blocks_until_released_and_survives_schedules(demo, client):
    from app import rules_extra
    from app.rules import _issue
    mac = next(x["mac"] for x in demo.latest["clients"] if x["name"] == "Kantoor-PC")
    assert client.post(f"/api/clients/{mac}/quarantine", json={"reason": ""}).status_code == 422
    assert client.post(f"/api/clients/{mac}/quarantine", json={"reason": "Malware volgens AdGuard en IPS"}).json()["ok"]
    assert mac in demo.mock.blocked
    p = next(x for x in client.get("/api/pauses").json()["pauses"] if x["mac"] == mac)
    ip = next(x["ip"] for x in demo.latest["clients"] if x["mac"] == mac)
    assert p["reason"].startswith("Malware") and p["until"] is None and p["ip"] == ip   # adres bewaard: geblokkeerd is hij uit de lijst
    assert client.post(f"/api/clients/{mac}/pause", json={"until": None}).status_code == 409   # een pauze mag het niet overschrijven

    out = []
    rules_extra.quarantined(out, demo.db, _issue)
    assert [i["key"] for i in out] == [f"quarantine:{mac}"] and "Malware" in out[0]["detail"] and ip in out[0]["detail"]

    # een schema dat afloopt laat een apparaat in quarantaine niet vrij
    demo.db.set_kv("sched_blocked", {mac: {"schedule": "x", "until": 1, "name": "Kantoor-PC"}})
    asyncio.run(demo._apply_schedules(int(time.time())))
    assert mac in demo.mock.blocked

    assert client.post(f"/api/clients/{mac}/resume").json()["ok"] and mac not in demo.mock.blocked
    assert not any(x["mac"] == mac for x in demo.db.pauses())
    assert any("vrijgegeven" in e["message"] or "released" in e["message"] for e in demo.db.events(0, 20))
