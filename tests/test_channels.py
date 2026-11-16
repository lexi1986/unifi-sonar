"""Kanaalplan voor alle AP's samen, en het toepassen ervan (in de demo)."""
import asyncio
import os

import pytest

from app import channels
from app.collector import Collector
from app.config import Settings
from app.db import DB
from app.mock import AP_SC, AP_WK


def _ap(mac, *radios, clients=0):
    return {"mac": mac, "name": f"AP {mac.upper()}", "type": "ap", "state": "online",
            "radios": [{"radio": b, "channel": ch, "width": w, "num_clients": clients} for b, ch, w in radios]}


def _nbr(ap, band, ch, sig, width=20):
    return {"ap_mac": ap, "band": band, "channel": ch, "width": width, "signal": sig, "ssid": "buren"}


class KV:
    """Genoeg van de database voor het plan: kv-opslag, en geen gemeten storing."""
    def __init__(self):
        self.kv = {}

    def get_kv(self, k):
        return self.kv.get(k)

    def set_kv(self, k, v):
        self.kv[k] = v

    def q(self, *_a):
        return []


def _radio(p, band, mac):
    return next(r for r in p["bands"][band]["radios"] if r["mac"] == mac)


def test_plan_spreads_24ghz_and_counts_pairs():
    devs = [_ap("a", ("2.4", 6, 20)), _ap("b", ("2.4", 6, 20)), _ap("c", ("2.4", 1, 20))]
    nbrs = [_nbr(m, "2.4", 6, -70) for m in "abc"] + [_nbr(m, "2.4", 1, -72) for m in "abc"]
    p = channels.plan({"devices": devs}, {"neighbors": nbrs}, KV())
    b = p["bands"]["2.4"]
    assert b["changes"] == 1 and b["own_now"] == 1 and b["own_plan"] == 0
    moved = [r for r in b["radios"] if r["change"]]
    assert moved[0]["mac"] in ("a", "b") and moved[0]["target"]["channel"] == 11
    assert moved[0]["current"]["shares"] and not moved[0]["target"]["shares"]


def test_plan_keeps_channel_when_gain_is_small():
    devs = [_ap("a", ("2.4", 1, 20)), _ap("b", ("2.4", 6, 20)), _ap("c", ("2.4", 11, 20))]
    nbrs = [_nbr("a", "2.4", 1, -85)]   # één zwakke buur: wisselen levert minder op dan de onderbreking kost
    p = channels.plan({"devices": devs}, {"neighbors": nbrs}, KV())
    assert p["changes"] == 0


def test_plan_skips_locked_and_refused_channels():
    devs = [_ap("a", ("2.4", 6, 20)), _ap("b", ("2.4", 6, 20)), _ap("c", ("2.4", 1, 20))]
    db = KV()
    channels.remember_refused(db, "a", "2.4", 11)
    channels.set_locked(db, "b", "2.4", True)
    p = channels.plan({"devices": devs}, {"neighbors": []}, db)
    a, b = _radio(p, "2.4", "a"), _radio(p, "2.4", "b")
    assert b["locked"] and not b["change"]
    assert a["refused"] == [11] and a["target"]["channel"] != 11
    channels.set_locked(db, "b", "2.4", False)
    channels.forget_refused(db, "a", "2.4")
    p = channels.plan({"devices": devs}, {"neighbors": []}, db)
    assert {r["target"]["channel"] for r in p["bands"]["2.4"]["radios"]} == {1, 6, 11}


def test_plan_5ghz_own_block_then_dfs():
    devs = [_ap("a", ("5", 36, 80)), _ap("b", ("5", 36, 80)), _ap("c", ("5", 149, 80))]
    p = channels.plan({"devices": devs}, {"neighbors": []}, KV())
    b = p["bands"]["5"]
    assert b["own_now"] == 1 and b["own_plan"] == 0 and b["changes"] == 1
    moved = next(r for r in b["radios"] if r["change"])
    assert moved["target"]["channel"] in channels.DFS_5 and moved["target"]["width"] == 80 and "dfs" in moved["notes"]


def test_validate():
    snap = {"devices": [_ap("aa:bb:cc:dd:ee:01", ("2.4", 6, 20), ("5", 36, 80)), {**_ap("aa:bb:cc:dd:ee:02", ("2.4", 1, 20)), "state": "offline"}]}
    ok = channels.validate([{"mac": "AA:BB:CC:DD:EE:01", "band": "2.4", "channel": 11, "width": 20},
                            {"mac": "aa:bb:cc:dd:ee:01", "band": "5", "channel": 100, "width": 80}], snap)
    assert ok == {"aa:bb:cc:dd:ee:01": {"2.4": (11, 20), "5": (100, 80)}}
    for bad in ({"mac": "aa:bb:cc:dd:ee:01", "band": "2.4", "channel": 14, "width": 20},
                {"mac": "aa:bb:cc:dd:ee:01", "band": "5", "channel": 37, "width": 80},
                {"mac": "aa:bb:cc:dd:ee:02", "band": "2.4", "channel": 6, "width": 20}):
        with pytest.raises(ValueError):
            channels.validate([bad], snap)


def test_apply_refuse_and_undo_in_demo(tmp_path):
    os.environ["NO_DOTENV"] = "1"
    st = Settings(mode="mock", db_path=str(tmp_path / "s.db"), mock_seed_hours=0, data_dir=str(tmp_path))
    col = Collector(st, DB(st.db_path))
    col.chan_timing = (0.05, 5, 0.2)
    col.mock.prov_s = 0.2

    async def run():
        await col.tick()
        job = col.apply_channels({AP_WK: {"2.4": (11, 20)}, AP_SC: {"2.4": (11, 20)}})
        with pytest.raises(RuntimeError):   # één tegelijk
            col.apply_channels({AP_WK: {"2.4": (1, 20)}})
        await col._chan_task
        return job

    job = asyncio.run(run())
    st_ = {s["mac"]: s["status"] for s in job["steps"]}
    assert st_ == {AP_WK: "ok", AP_SC: "refused"} and not job["running"]
    assert col.mock.ch[(AP_WK, "ng")] == 11 and col.mock.ch[(AP_SC, "ng")] == 6
    assert channels._kv(col.db, channels.KV_REFUSED) == {f"{AP_SC}@2.4": [11]}
    wk = next(d for d in col.latest["devices"] if d["mac"] == AP_WK)
    assert next(r for r in wk["radios"] if r["radio"] == "2.4")["channel"] == 11   # meteen bijgewerkt
    undo = col.db.get_kv(channels.KV_UNDO)
    assert undo["aps"][AP_WK]["radios"]["2.4"]["channel"] == 6

    async def back():
        col.apply_channels({m: {b: (v["channel"], v["ht"]) for b, v in ap["radios"].items()} for m, ap in undo["aps"].items()}, undo=True)
        await col._chan_task
    asyncio.run(back())
    assert col.mock.ch[(AP_WK, "ng")] == 6 and col.db.get_kv(channels.KV_UNDO) == {}


def test_api_plan_apply_lock(tmp_path, monkeypatch):
    """Via de echte API: toepassen moet een taak in de event-loop starten (een gewone functie kan dat niet)."""
    from fastapi.testclient import TestClient
    from app import main
    os.environ["NO_DOTENV"] = "1"
    st = Settings(mode="mock", db_path=str(tmp_path / "s.db"), mock_seed_hours=0, data_dir=str(tmp_path))
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.tick())
    monkeypatch.setattr(main.rt, "collector", col)
    monkeypatch.setattr(main.rt, "db", col.db)
    client = TestClient(main.app)
    p = client.get("/api/channels").json()
    assert p["can_write"] and p["demo"] and p["job"] is None and p["changes"] >= 1
    assert client.post("/api/channels/apply", json={"items": [{"mac": AP_WK, "band": "2.4", "channel": 14, "width": 20}]}).status_code == 400
    assert client.post("/api/channels/undo", json={}).status_code == 400            # nog niets om terug te zetten
    assert client.post("/api/channels/lock", json={"mac": AP_WK.upper(), "band": "2.4", "locked": True}).json()["ok"]
    assert _radio(client.get("/api/channels").json(), "2.4", AP_WK)["locked"]
    r = client.post("/api/channels/apply", json={"items": [{"mac": AP_WK, "band": "5", "channel": 100, "width": 80}]})
    assert r.status_code == 200 and r.json()["job"]["running"]


def test_plan_without_channels_says_so():
    """Beperkte officiële API: AP's online, maar geen kanalen. Dan geen 'alles goed' en geen 'geen AP's'."""
    devs = [_ap("a", ("2.4", None, None), ("5", None, None)), _ap("b", ("2.4", None, None))]
    p = channels.plan({"devices": devs}, {"neighbors": []}, KV())
    assert p["no_channels"] and p["changes"] == 0
    devs[0]["radios"][0]["channel"] = 6
    assert not channels.plan({"devices": devs}, {"neighbors": []}, KV())["no_channels"]
