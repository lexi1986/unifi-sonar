import asyncio

from app.collector import Collector
from app.config import Settings
from app.db import DB
from app.unifi_client import normalize_flow

T = 1_800_000_000


def flow(direction, src, dst, tx=100, rx=900, **kw):
    f = {"id": kw.pop("id", f"f-{direction}"), "action": "allowed", "direction": direction, "protocol": "TCP",
         "flow_end_time": T * 1000, "service": "HTTPS", "source": src, "destination": dst,
         "in": {"network_name": "Default"}, "out": {"network_name": "WAN"},
         "traffic_data": {"bytes_tx": tx, "bytes_rx": rx}}
    f.update(kw)
    return f


def test_normalize_flow_directions():
    out = normalize_flow(flow("outgoing", {"ip": "192.168.1.5", "mac": "AA:BB:CC:00:00:01", "client_name": "Laptop"},
                              {"ip": "203.0.113.9", "port": 443, "domains": ["example.org"], "region": "de"}))
    assert out["dir"] == "out" and out["cc"] == "DE" and out["domain"] == "example.org"
    assert out["client_mac"] == "aa:bb:cc:00:00:01" and out["up"] == 100 and out["down"] == 900 and out["port"] == 443

    inc = normalize_flow(flow("incoming", {"ip": "198.51.100.4", "port": 50000, "region": "US"},
                              {"ip": "192.168.1.13", "client_name": "NAS", "port": 22}))
    assert inc["dir"] == "in" and inc["client_name"] == "NAS" and inc["port"] == 22
    assert inc["up"] == 900 and inc["down"] == 100            # de NAS verstuurt wat de bron ontvangt

    reg = normalize_flow(flow("incoming", {"ip": "198.51.100.9", "region": "RU"}, {"ip": "192.168.1.13", "port": 445},
                              action="blocked"))
    assert reg["dir"] == "blocked" and reg["cc"] == "RU"    # regioblokkade: niet als 'inkomend' tellen
    reg2 = normalize_flow(flow("incoming", {"ip": "198.51.100.9", "region": "RU"}, {"ip": "203.0.113.2", "port": 23},
                               action="blocked", policies=[{"type": "PROTECTION", "internal_type": "REGION_BLOCKING"}]))
    assert reg2["reason"] == "Regioblokkade"

    vpn = normalize_flow(flow("incoming", {"ip": "192.168.2.4"}, {"ip": "192.168.1.22", "port": 53}))
    assert vpn["dir"] == "local" and vpn["cc"] is None        # VPN-client: geen internetverkeer


def test_world_aggregates_and_updates(tmp_path):
    db = DB(str(tmp_path / "w.db"))
    a = normalize_flow(flow("outgoing", {"ip": "192.168.1.5", "client_name": "Laptop"},
                            {"ip": "203.0.113.9", "port": 443, "domains": ["example.org"], "region": "DE"}, id="a"))
    db.store_flows([a, normalize_flow(flow("incoming", {"ip": "198.51.100.4", "region": "US"},
                                           {"ip": "192.168.1.13", "client_name": "NAS", "port": 22}, id="b"))])
    db.store_flows([dict(a, down=5000)])                       # lange verbinding: later opnieuw gemeld, niet dubbel tellen
    w = db.world(T - 60)
    assert w["countries"]["DE"]["out_n"] == 1 and w["countries"]["DE"]["bytes"] == 5100
    assert w["countries"]["US"]["in_n"] == 1 and w["totals"]["n"] == 2
    assert w["domains"][0]["name"] == "example.org" and w["clients"][0]["name"] == "Laptop"
    db.purge_flows(T + 1)
    assert db.world(0)["totals"]["n"] == 0


def test_demo_world_api(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_DOTENV", "1")
    from fastapi.testclient import TestClient
    from app import main
    st = Settings(mode="mock", db_path=str(tmp_path / "t.db"), mock_seed_hours=1)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    monkeypatch.setattr(main.rt, "collector", col)
    monkeypatch.setattr(main.rt, "db", col.db)
    c = TestClient(main.app)
    w = c.get("/api/world?hours=24").json()
    ccs = {x["cc"] for x in w["countries"]}
    assert w["home"] == "NL" and {"US", "SE", "CN"} <= ccs and w["totals"]["blocked_n"] > 0
    blk = [x for x in w["countries"] if x.get("blocked")]
    assert blk and all({"what", "target", "n", "sources", "by"} <= set(b) for x in blk for b in x["blocked"])
    assert any(b["by"] == "Regioblokkade" and b["target"] == "je gateway (WAN)" for x in blk for b in x["blocked"])
    out = c.get("/api/world/connections?hours=24&dir=out&sort=bytes&limit=10").json()
    assert out["total"] >= len(out["rows"]) > 0 and all(r["dir"] == "out" for r in out["rows"])
    assert out["rows"][0]["bytes"] >= out["rows"][-1]["bytes"]
    blk = c.get("/api/world/connections?hours=24&dir=blocked").json()["rows"]
    assert {r["by"] for r in blk} >= {"IPS", "Regioblokkade"}
    se = c.get("/api/world/connections?hours=24&q=spotify").json()["rows"]
    assert se and all("spotify" in (r["dest"] or "") for r in se)
    assert all(r["cc"] == "US" for r in c.get("/api/world/connections?hours=24&cc=us").json()["rows"])
    live = c.get("/api/world/live?limit=20").json()["flows"]
    assert live and all("remote_ip" not in f for f in live)
