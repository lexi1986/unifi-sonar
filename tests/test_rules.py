import asyncio

from app import rules
from app.collector import Collector, _retry_pct
from app.config import Settings, Thresholds
from app.db import DB

TS = 1_800_000_000


class EmptyDB:
    """Geen historie: regels vallen terug op de actuele meting."""
    def client_window(self, since): return {}
    def client_roams(self, since): return {}
    def radio_window(self, since): return {}
    def port_window(self, since): return {}
    def wan_window(self, since): return {}
    def event_counts(self, since, kind): return {}
    def ips_events(self, since, scope="all", limit=5000): return getattr(self, "ips", [])
    def client_before(self, mac, t0, t1): return None
    def q(self, *a): return [{"n": 0}]


def ap(mac="ap1", **kw):
    d = dict(mac=mac, name=f"AP {mac}", model="U6", type="ap", state="online", version="6", upgradable=False,
             upgrade_to="", uptime=1000, ip="", cpu=5, mem=40, temp=None, num_clients=3, satisfaction=90,
             uplink_mac=None, uplink_port=None, uplink_type=None, poe_budget_w=None, poe_used_w=None,
             radios=[], ports=[])
    d.update(kw)
    return d


def client(mac, **kw):
    d = dict(mac=mac, name=mac, ip="", vendor="", wired=False, network="", guest=False, ssid="x", ap_mac="ap1",
             sw_mac=None, sw_port=None, band="2.4", channel=6, proto="n", signal=-55, noise=-95, satisfaction=95,
             tx_rate_mbps=72, rx_rate_mbps=72, tx_packets=1, tx_retries=0, uptime=1, retry_pct=2)
    d.update(kw)
    return d


def snap(devices, clients):
    return {"ts": TS, "devices": devices, "clients": clients,
            "wan": {"up": True, "latency_ms": 10, "loss_pct": 0, "wan_ip": "", "isp": "", "xput_down": None, "xput_up": None}}


def run(s):
    return {i["key"]: i for i in rules.evaluate(s, EmptyDB(), Thresholds(), TS)}


def test_weak_signal_is_critical():
    out = run(snap([ap()], [client("c1", signal=-84)]))
    assert out["client_signal:c1"]["severity"] == "critical"


def test_retries_with_good_signal_point_to_interference():
    out = run(snap([ap()], [client("c1", signal=-50, retry_pct=45)]))
    i = out["client_retry:c1"]
    assert i["severity"] == "critical"
    assert "storing" in i["advice"]


def test_coverage_group_collapses_clients():
    cl = [client(f"c{i}", signal=-78) for i in range(3)] + [client("ok")]
    out = run(snap([ap()], cl))
    g = out["coverage:ap1@2.4"]
    assert g["value"] == 3 and "dekking" in g["title"]
    assert all(out[f"client_signal:c{i}"]["group"] == g["key"] for i in range(3))
    assert "client_signal:ok" not in out


def test_100mbit_on_gigabit_port():
    port = dict(idx=3, name="Port 3", up=True, speed=100, media="GE", full_duplex=True, poe_w=0, rx_errors=0,
                tx_errors=0, rx_dropped=0, tx_dropped=0, is_uplink=False, rx_bytes=0, tx_bytes=0)
    sw = ap("sw1", type="switch", ports=[port])
    assert run(snap([sw], []))["port_speed:sw1#3"]["severity"] == "info"


def test_offline_device():
    assert run(snap([ap(state="offline")], []))["dev_state:ap1"]["severity"] == "critical"


def test_retry_pct_handles_counter_reset():
    assert _retry_pct(1000, 100, 500, 50) == 10.0     # delta 50/500
    assert _retry_pct(100, 10, 5000, 900) == 10.0     # reset → cumulatief


def test_health_score_does_not_double_count_groups():
    s = snap([ap()], [client(f"c{i}", signal=-78) for i in range(3)])
    issues = rules.evaluate(s, EmptyDB(), Thresholds(), TS)
    rules.attach_scores(s, issues)
    assert s["health"]["warning"] == 1 and s["health"]["total"] == 4


def test_mock_end_to_end(tmp_path):
    st = Settings(mode="mock", db_path=str(tmp_path / "t.db"), mock_seed_hours=2)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    seen = col.db.issues(open_only=False, limit=1000)   # ook issues die tussendoor opgelost zijn
    keys = {i["key"].split(":")[0] for i in seen}
    titles = " ".join(i["title"] for i in seen)
    assert {"coverage", "client_roam", "port_err", "port_speed", "dev_poe", "port_flap", "dev_fw", "ips_internal"} <= keys
    assert "Ring Deurbel" in titles and "Sonos Keuken" in titles


def test_signal_limits_depend_on_band():
    out = run(snap([ap()], [client("iot", band="2.4", signal=-74), client("iot2", band="2.4", signal=-77),
                            client("tv", band="5", signal=-76)]))
    assert "client_signal:iot" not in out                      # -74 op 2.4 GHz is prima
    assert out["client_signal:iot2"]["severity"] == "warning"
    assert out["client_signal:tv"]["severity"] == "warning"    # 5 GHz is strenger


def test_radio_retries_ignored_on_quiet_radio():
    radio = dict(radio="5", channel=44, width=80, tx_power=20, cu_total=3, cu_self=1, interference=2,
                 num_clients=2, satisfaction=None, tx_packets=1, tx_retries=1, retry_pct=28)
    assert "radio_retry:ap1@5" not in run(snap([ap(radios=[radio])], []))
    radio["num_clients"] = 6
    assert "radio_retry:ap1@5" in run(snap([ap(radios=[radio])], []))


def test_satisfaction_minus_one_is_unknown():
    from app.unifi_client import _sat
    assert _sat(-1) is None and _sat("97") == 97.0 and _sat(None) is None


def test_health_counts_each_client_once():
    s = snap([ap()], [client("c1", signal=-79, retry_pct=30)])
    issues = rules.evaluate(s, EmptyDB(), Thresholds(), TS)
    rules.attach_scores(s, issues)
    assert len(issues) == 2 and s["health"]["warning"] == 1


def test_muted_issues_do_not_count(tmp_path):
    st = Settings(mode="mock", db_path=str(tmp_path / "t.db"), mock_seed_hours=1)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    before = dict(col.latest["health"])
    target = next(i for i in col.latest["issues"] if not i.get("group") and i["severity"] == "warning")
    col.db.mute(target["key"], None, TS, target["title"])
    col.apply_mutes()
    after = col.latest["health"]
    assert after["muted"] == 1 and after["score"] >= before["score"]
    assert next(i for i in col.latest["issues"] if i["key"] == target["key"])["muted"]
    assert any(i["muted"] for i in col.db.issues(True, now=TS))
    # verlopen negeer-regel verdwijnt vanzelf
    col.db.mute(target["key"], TS + 10, TS, target["title"])
    assert target["key"] not in col.db.muted(TS + 11)


def test_internal_ips_block_becomes_issue():
    from app.unifi_client import normalize_ips
    flow = {"id": "f1", "action": "blocked", "flow_start_time": TS * 1000, "protocol": "TCP",
            "in": {"network_name": "VPN-Thuis"}, "source": {"ip": "192.168.20.5"},
            "destination": {"ip": "192.168.1.40", "port": 80},
            "ips": {"signature": "GPL WEB_SERVER DELETE attempt", "signature_id": 2101603, "category_name": "emerging-webserver"}}
    ext = dict(flow, id="f2", source={"ip": "198.51.100.7"})
    db = EmptyDB()
    db.ips = [e for e in (normalize_ips(flow), normalize_ips(ext)) if e["internal"]]
    out = {i["key"]: i for i in rules.evaluate(snap([ap()], []), db, Thresholds(), TS)}
    i = out["ips_internal:192.168.20.5"]
    assert i["category"] == "security" and "DELETE" in i["detail"] and "VPN-Thuis" in i["detail"]
    assert not any(k.startswith("ips_internal:198.") for k in out)


def test_sticky_after_restart_with_history(tmp_path):
    st = Settings(mode="mock", db_path=str(tmp_path / "t.db"), mock_seed_hours=4)
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    issues = {i["key"]: i for i in col.latest["issues"]}
    group = next(i for k, i in issues.items() if k.startswith("sticky_restart:"))
    kindle = next(c for c in col.latest["clients"] if c["name"] == "Kindle")
    member = issues[f"sticky:{kindle['mac']}"]
    assert "AP Boven" in group["title"] and group["members"] == [kindle["mac"]]
    assert member["group"] == group["key"] and member["reconnect"] and member["severity"] == "warning"
    assert "vóór de herstart op AP Boven" in member["detail"]
    # andere clients van AP Boven zijn na de herstart gewoon teruggekomen: geen melding
    assert sum(k.startswith("sticky:") for k in issues) == 1


def test_sticky_without_history_needs_weak_signal_on_ap_that_stayed_up():
    a1, a2 = ap("far", uptime=10 * 86400), ap("near", uptime=3600)
    weak = client("lamp", ap_mac="far", signal=-84, assoc_ts=TS - 3600 + 120)
    ok = client("bulb", ap_mac="far", signal=-60, assoc_ts=TS - 3600 + 120)
    back = client("tv", ap_mac="near", signal=-80, assoc_ts=TS - 3600 + 200)
    old = client("old", ap_mac="far", signal=-84, assoc_ts=TS - 5 * 86400)
    db = EmptyDB(); db.client_before = lambda *a: None
    out = {i["key"]: i for i in rules.evaluate(snap([a1, a2], [weak, ok, back, old]), db, Thresholds(), TS)}
    assert out["sticky:lamp"]["severity"] == "info"
    assert not any(k in out for k in ("sticky:bulb", "sticky:tv", "sticky:old"))
