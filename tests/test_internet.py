import asyncio
import time as _time_mod

from app import rules
from app.collector import Collector
from app.config import Settings, Thresholds
from app.db import DB
from app.unifi_client import normalize_speedtest_state, normalize_speedtests, wan_rates
from tests.test_rules import TS, EmptyDB, ap, snap


def test_wan_rates_use_active_wan_port():
    gw = {"wan1": {"is_uplink": False, "rx_bytes-r": 1, "speed": 1000},
          "wan2": {"is_uplink": True, "rx_bytes-r": 125_000, "tx_bytes-r": 12_500, "rx_bytes": 9, "tx_bytes": 3, "speed": 10000}}
    r = wan_rates(gw)
    assert r["rx_bps"] == 1_000_000 and r["tx_bps"] == 100_000 and r["link_mbps"] == 10000
    assert wan_rates({}, {"rx_bytes-r": 10, "tx_bytes-r": 5})["rx_bps"] == 80


def test_speedtest_state_and_archive():
    st = normalize_speedtest_state({"status_ping": 2, "status_download": 1, "status_upload": 0, "status_summary": 1})
    assert st["running"] and st["phase"] == "download"
    done = normalize_speedtest_state({"status_ping": 2, "status_download": 2, "status_upload": 2, "status_summary": 2,
                                      "rundate": TS, "xput_download": 940.5, "xput_upload": 480, "latency": 5})
    assert not done["running"] and done["down"] == 940.5 and done["rundate"] == TS
    rows = normalize_speedtests([{"time": TS * 1000, "xput_download": 900, "xput_upload": 400, "latency": 6,
                                  "server": {"city": "Amsterdam", "provider": "Ubiquiti"}},
                                 {"time": (TS - 10) * 1000, "xput_download": 0}])   # mislukte test overslaan
    assert rows == [{"ts": TS, "down": 900, "up": 400, "latency": 6, "server": "Amsterdam, Ubiquiti"}]


def test_speedtest_rows_are_merged(tmp_path):
    db = DB(str(tmp_path / "s.db"))
    db.store_speedtests([{"ts": TS, "down": 900, "up": 400, "latency": 6, "server": ""}])          # van de gateway
    db.store_speedtests([{"ts": TS + 4, "down": 901, "up": 401, "latency": 6, "server": "Amsterdam"}])  # uit het archief
    db.store_speedtests([{"ts": TS + 2, "down": 900, "up": 400, "latency": 6, "server": ""}])      # nogmaals voorlopig
    rows = db.speedtests(0)
    assert len(rows) == 1 and rows[0]["server"] == "Amsterdam"


def test_slow_internet_rule():
    db = EmptyDB()
    db.tests = [{"ts": TS - d * 86400, "down": 950, "up": 480} for d in range(6, 0, -1)]
    assert not any(i["key"].startswith("speed_low") for i in rules.evaluate(snap([ap()], []), db, Thresholds(), TS))
    db.tests.append({"ts": TS - 3600, "down": 410, "up": 470})
    out = {i["key"]: i for i in rules.evaluate(snap([ap()], []), db, Thresholds(), TS)}
    assert out["speed_low:down"]["severity"] == "warning" and "950" in out["speed_low:down"]["detail"]
    db.tests[-1]["ts"] = TS - 5 * 86400 - 1   # oude meting: niet meer melden
    db.tests.sort(key=lambda r: r["ts"])
    assert "speed_low:down" not in {i["key"] for i in rules.evaluate(snap([ap()], []), db, Thresholds(), TS)}


def test_demo_speedtest_end_to_end(tmp_path, monkeypatch):
    st = Settings(mode="mock", db_path=str(tmp_path / "t.db"), mock_seed_hours=1)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    clock = [col.latest["ts"] + 10]
    monkeypatch.setattr("app.collector.time.time", lambda: clock[0])

    async def flow():
        live = await col.live_wan()
        assert live["rx_bps"] and live["link_mbps"] == 1000
        await col.sync_speedtests(force=True)
        before = len(col.db.speedtests(0))
        assert before == 30
        await col.start_speedtest()
        clock[0] += 8
        col._live = None
        mid = await col.live_wan()
        assert col.speedtest["running"] and mid["speedtest"]["phase"] == "download"
        clock[0] += 30
        col._live = None
        await col.live_wan()
        assert not col.speedtest["running"]
        assert len(col.db.speedtests(0)) == before + 1
        try:
            await col.start_speedtest()          # te snel weer
            raise AssertionError("tweede test had geweigerd moeten worden")
        except RuntimeError as e:
            assert "minuut" in str(e)

    asyncio.run(flow())


def test_usage_and_me_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_DOTENV", "1")
    from fastapi.testclient import TestClient
    from app import main
    from app.unifi_client import normalize_usage
    assert normalize_usage([{"time": TS * 1000, "wan-rx_bytes": 10, "wan2-rx_bytes": 5, "wan-tx_bytes": 2}]) == \
        [{"ts": TS, "rx": 15, "tx": 2}]
    st = Settings(mode="mock", db_path=str(tmp_path / "u.db"), mock_seed_hours=1)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    asyncio.run(col.sync_usage(force=True))
    today = col.db.usage("day", 0)[-1]["ts"]
    col.db.store_usage("day", [{"ts": today, "rx": 1e15, "tx": 1e15}])   # de lopende dag groeit mee
    monkeypatch.setattr(main.rt, "collector", col)
    monkeypatch.setattr(main.rt, "db", col.db)
    c = TestClient(main.app)
    u = c.get("/api/usage").json()
    assert len(u["days"]) == 90 and u["months"] and u["today"] == {"rx": 1e15, "tx": 1e15} and u["avg_day"]["rx"] > 1e9
    me = c.get("/api/me").json()                       # demo: doet alsof je op de iPhone kijkt
    assert me["found"] and me["client"]["name"] == "iPhone" and me["uplink"]["name"]
    wired = c.get("/api/me?ip=192.168.1.10").json()
    assert wired["client"]["wired"] and wired["client"]["name"] == "Home Assistant"
    assert c.get("/api/me?ip=10.9.9.9").json() == {"found": False, "ip": "10.9.9.9"}


def test_pause_and_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_DOTENV", "1")
    import time as _t
    from fastapi.testclient import TestClient
    from app import main
    st = Settings(mode="mock", db_path=str(tmp_path / "p.db"), mock_seed_hours=1)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    monkeypatch.setattr(main.rt, "collector", col)
    monkeypatch.setattr(main.rt, "db", col.db)
    c = TestClient(main.app)
    mac = next(x["mac"] for x in col.latest["clients"] if x["name"] == "iPad Keuken")
    assert c.post(f"/api/clients/{mac}/pause", json={"until": int(_t.time()) + 60}).json()["ok"]
    assert mac in col.mock.blocked and c.get("/api/pauses").json()["pauses"][0]["name"] == "iPad Keuken"
    asyncio.run(col._expire_pauses(int(_t.time()) + 61))             # tijd om: vanzelf weer toegelaten
    assert mac not in col.mock.blocked and col.db.pauses() == []
    c.post(f"/api/clients/{mac}/pause", json={"until": None})
    assert c.post(f"/api/clients/{mac}/resume").json()["ok"] and mac not in col.mock.blocked
    assert c.post(f"/api/clients/{mac}/pause", json={"until": 5}).status_code == 400


def test_usage_never_drops_when_controller_restarts_counting(tmp_path):
    """Network 11 zette zijn statistieken over naar PostgreSQL en begon opnieuw te tellen: een lager totaal voor
    dezelfde dag of maand mag wat Sonar al had niet overschrijven, en een maand is minstens de som van zijn dagen."""
    db = DB(str(tmp_path / "u.db"))
    m0, m1, d = 1_000_000, 1_000_000 + 30 * 86400, 86400
    db.store_usage("month", [{"ts": m0, "rx": 500.0, "tx": 50.0}])
    db.store_usage("day", [{"ts": m0 + i * d, "rx": 40.0, "tx": 4.0} for i in range(15)])   # 600 / 60 in dagen
    assert db.usage("month", 0) == [{"ts": m0, "rx": 600.0, "tx": 60.0}]
    db.store_usage("day", [{"ts": m0 + 14 * d, "rx": 2.0, "tx": 1.0}])                      # opnieuw begonnen
    db.store_usage("month", [{"ts": m0, "rx": 3.0, "tx": 1.0}, {"ts": m1, "rx": 7.0, "tx": 2.0}])
    assert db.usage("day", 0)[14] == {"ts": m0 + 14 * d, "rx": 40.0, "tx": 4.0}
    assert db.usage("month", 0) == [{"ts": m0, "rx": 600.0, "tx": 60.0}, {"ts": m1, "rx": 7.0, "tx": 2.0}]
    db.store_client_usage("day", [{"ts": m0, "mac": "aa", "down": 9.0, "up": 1.0}])
    db.store_client_usage("day", [{"ts": m0, "mac": "aa", "down": 0.5, "up": 0.1}])
    assert db.client_usage_totals("day", 0) == {"aa": {"down": 9.0, "up": 1.0}}


def test_network11_usage_falls_back_to_v2(monkeypatch):
    """Network 11 geeft stat/report leeg terug: dan het WAN-totaal uit v2 aggregated-dashboard en het verbruik per
    apparaat uit v2 traffic, voor de lopende en de vorige periode."""
    import httpx
    from app import unifi_client as uc
    now = int(_time_mod.mktime((2026, 11, 20, 0, 40, 0, 0, 0, -1)))
    monkeypatch.setattr(uc.time, "time", lambda: now)
    midnight = int(_time_mod.mktime((2026, 11, 20, 0, 0, 0, 0, 0, -1)))
    assert uc.usage_windows("day", now) == [(midnight, now), (midnight - 86400, midnight)]
    assert uc.usage_windows("month", now)[0][0] == int(_time_mod.mktime((2026, 11, 1, 0, 0, 0, 0, 0, -1)))
    assert [a for a, _ in uc.usage_windows("hour", now)] == [midnight, midnight - 3600, midnight - 7200]
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        if "/stat/report/" in req.url.path:
            return httpx.Response(200, json={"meta": {"rc": "ok"}, "data": []})       # Network 11: leeg
        a = int(req.url.params["start"]) // 1000
        if req.url.path.endswith("/aggregated-dashboard"):
            assert req.url.params["widgets"] == "wan_activity"
            if a < midnight:
                return httpx.Response(200, json={"wan_activity": {"no_stats_reason": "no_data"}})
            return httpx.Response(200, json={"wan_activity": {"total_activity": {"summary": {"rx_bytes": 5e9, "tx_bytes": 1e9}}}})
        if req.url.path.endswith("/traffic"):
            return httpx.Response(200, json={"client_usage_by_app": [
                {"client": {"mac": "AA:BB:CC:00:00:01"}, "usage_by_app": [{"bytes_received": 700, "bytes_transmitted": 70},
                                                                         {"bytes_received": 300, "bytes_transmitted": 30}]},
                {"client": {"mac": "aa:bb:cc:00:00:02"}, "usage_by_app": [{"bytes_received": 0, "bytes_transmitted": 0}]}]})
        return httpx.Response(404)

    s = Settings(mode="live", controller_url="https://ctrl.example", api_key="k")
    c = uc.UnifiClient(s)
    c.http = httpx.AsyncClient(base_url="https://ctrl.example", transport=httpx.MockTransport(handler))
    c.source = "legacy-key"
    days = asyncio.run(c.usage("day", now - 400 * 86400, now))
    assert days == [{"ts": midnight, "rx": 5_000_000_000, "tx": 1_000_000_000}]      # gisteren: geen data in Network 11
    hours = asyncio.run(c.client_usage("hour", now - 48 * 3600, now))
    assert {(h["ts"], h["mac"], h["down"], h["up"]) for h in hours} == {(t, "aa:bb:cc:00:00:01", 1000.0, 100.0) for t in (midnight, midnight - 3600, midnight - 7200)}
    assert any("/stat/report/daily.site" in p for p in seen) and any(p.endswith("/traffic") for p in seen)


def test_network11_speedtests_and_categories():
    from app import unifi_client as uc
    rows = uc.normalize_speedtests_v2([
        {"download_mbps": 0, "upload_mbps": 0, "interface_name": "eth6", "wan_networkgroup": "WAN2"},       # geen test
        {"download_mbps": 1069, "upload_mbps": 1097, "latency_ms": 5, "time": 1793955162997, "wan_networkgroup": "WAN"}])
    assert rows == [{"ts": 1793955162, "down": 1069, "up": 1097, "latency": 5, "server": "WAN"}]
    d = {"client_usage_by_app": [{"client": {"mac": "AA:00:00:00:00:01"}, "usage_by_app": [
        {"application": 1, "category": 20, "bytes_received": 10, "bytes_transmitted": 1},
        {"application": 2, "category": 20, "bytes_received": 5, "bytes_transmitted": 1},
        {"application": 3, "category": 4, "bytes_received": 0, "bytes_transmitted": 0}]}]}
    assert uc.dpi_from_traffic(d) == [{"mac": "aa:00:00:00:00:01", "cat": 20, "down": 15.0, "up": 2.0}]
