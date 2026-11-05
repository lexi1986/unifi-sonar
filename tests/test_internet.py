import asyncio

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
    col.db.store_usage("day", [{"ts": col.db.usage("day", 0)[-1]["ts"], "rx": 1, "tx": 1}])   # lopende dag overschrijven
    monkeypatch.setattr(main.rt, "collector", col)
    monkeypatch.setattr(main.rt, "db", col.db)
    c = TestClient(main.app)
    u = c.get("/api/usage").json()
    assert len(u["days"]) == 90 and u["months"] and u["today"] == {"rx": 1, "tx": 1} and u["avg_day"]["rx"] > 1e9
    me = c.get("/api/me").json()                       # demo: doet alsof je op de iPhone kijkt
    assert me["found"] and me["client"]["name"] == "iPhone" and me["uplink"]["name"]
    wired = c.get("/api/me?ip=192.168.1.10").json()
    assert wired["client"]["wired"] and wired["client"]["name"] == "Home Assistant"
    assert c.get("/api/me?ip=10.9.9.9").json() == {"found": False, "ip": "10.9.9.9"}
