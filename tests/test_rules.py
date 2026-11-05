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
    def event_counts(self, since, kind): return getattr(self, "events", {}).get(kind, {})
    def ips_events(self, since, scope="all", limit=5000):
        return [e for e in getattr(self, "ips", []) if scope == "all" or e["internal"] == (scope == "internal")]
    def client_before(self, mac, t0, t1): return None
    def last_state_ts(self, mac, state="online"): return getattr(self, "online_ts", None)
    def client_ap_stats(self, mac, since): return getattr(self, "ap_stats", {}).get(mac, {"aps": [], "switches": 0})
    def ips_ignores(self): return getattr(self, "ignores", [])
    def speedtests(self, since): return getattr(self, "tests", [])
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
    assert {"coverage", "client_roam", "port_err", "port_speed", "dev_poe", "port_flap", "dev_fw", "ips_internal",
            "cfg_cochannel5", "cfg_ch24", "cfg_bandsteer", "cfg_ft", "upnp_on", "upnp_priv", "pf_risky"} <= keys
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


# ---------------------------------------------------------------- tijdelijke toestand, stille controller
def test_upgrading_is_info_then_warning():
    db = EmptyDB(); db.online_ts = TS - 120
    out = {i["key"]: i for i in rules.evaluate(snap([ap(state="upgrading")], []), db, Thresholds(), TS)}
    assert out["dev_state:ap1"]["severity"] == "info"
    db.online_ts = TS - 3600
    out = {i["key"]: i for i in rules.evaluate(snap([ap(state="upgrading")], []), db, Thresholds(), TS)}
    assert out["dev_state:ap1"]["severity"] == "warning" and "blijft hangen" in out["dev_state:ap1"]["title"]


def test_controller_quiet_groups_offline_devices():
    devs = [ap("a", state="offline"), ap("b", state="offline"), ap("c", state="heartbeat_missed"), ap("d")]
    out = run(snap(devs, []))
    assert out["controller_quiet"]["severity"] == "critical"
    assert all(out[f"dev_state:{m}"]["group"] == "controller_quiet" for m in "abc")
    assert "controller_quiet" not in run(snap([ap("a", state="offline"), ap("b"), ap("c"), ap("d")], []))


def test_reboot_by_firmware_update_is_not_flagged():
    db = EmptyDB(); db.events = {"device_reboot": {"ap1": 1}, "device_upgrade": {"ap1": 1}}
    assert "dev_reboot:ap1" not in {i["key"] for i in rules.evaluate(snap([ap()], []), db, Thresholds(), TS)}
    db.events["device_reboot"]["ap1"] = 2
    assert "dev_reboot:ap1" in {i["key"] for i in rules.evaluate(snap([ap()], []), db, Thresholds(), TS)}


# ---------------------------------------------------------------- blijft hangen (algemeen)
def _sticky_db(switches=1):
    db = EmptyDB()
    db.ap_stats = {"lamp": {"switches": switches, "aps": [
        {"ap_mac": "near", "seconds": 6 * 86400, "n": 8000, "signal": -58.0},
        {"ap_mac": "far", "seconds": 7200, "n": 120, "signal": -79.0}]}}
    return db


def test_sticky_general_static_device():
    devs = [ap("near", uptime=30 * 86400), ap("far", uptime=30 * 86400)]
    lamp = client("lamp", ap_mac="far", signal=-79, assoc_ts=TS - 2 * 3600)
    out = {i["key"]: i for i in rules.evaluate(snap(devs, [lamp]), _sticky_db(), Thresholds(), TS)}
    i = out["sticky:lamp"]
    assert i["severity"] == "warning" and i["reconnect"] and "AP near" in i["detail"]
    assert out["client_signal:lamp"]["group"] == "sticky:lamp"


def test_sticky_general_skips_mobile_locked_and_fresh():
    devs = [ap("near", uptime=30 * 86400), ap("far", uptime=30 * 86400)]
    lamp = client("lamp", ap_mac="far", signal=-79, assoc_ts=TS - 2 * 3600)
    keys = lambda c, db: {i["key"] for i in rules.evaluate(snap(devs, [c]), db, Thresholds(), TS)}  # noqa: E731
    assert "sticky:lamp" not in keys(lamp, _sticky_db(switches=40))                    # telefoon die rondloopt
    assert "sticky:lamp" not in keys(dict(lamp, fixed_ap="far"), _sticky_db())          # bewust vastgezet
    assert "sticky:lamp" not in keys(dict(lamp, assoc_ts=TS - 600), _sticky_db())       # net verbonden


# ---------------------------------------------------------------- instellingen
def radio(band, ch, width=20, **kw):
    r = dict(radio=band, channel=ch, channel_auto=False, width=width, tx_power=20, tx_power_mode="auto", min_rssi=None,
             cu_total=10, cu_self=5, interference=5, num_clients=2, satisfaction=95, tx_packets=1, tx_retries=0, retry_pct=2)
    r.update(kw)
    return r


def test_blocks5():
    assert rules._blocks5(44, 80) == {36, 40, 44, 48}
    assert rules._blocks5(104, 40) == {100, 104}
    assert rules._blocks5(157, 80) == {149, 153, 157, 161}
    assert rules._blocks5("auto", 80) == set()


def test_config_checks():
    a = ap("a", bandsteering="prefer_5g", radios=[radio("2.4", 6), radio("5", 36, 80)])
    b = ap("b", bandsteering="off", radios=[radio("2.4", 6, 40), radio("5", 44, 80)])
    c = ap("c", bandsteering="prefer_5g", radios=[radio("2.4", 1), radio("5", 149, 80, min_rssi=-65)])
    s = snap([a, b, c], [])
    s["config"] = {"wlans": [
        {"name": "Thuis", "enabled": True, "bands": ["2.4", "5"], "guest": False, "iot": False,
         "fast_roaming": False, "bss_transition": True, "minrate_24": 1000},
        {"name": "IoT", "enabled": True, "bands": ["2.4"], "guest": False, "iot": True,
         "fast_roaming": False, "bss_transition": False, "minrate_24": 1000}], "upnp_enabled": None, "forwards": None}
    out = run(s)
    assert out["cfg_cochannel5:a,b"]["severity"] == "info"
    assert "kanaal 11" in out["cfg_ch24"]["title"]
    assert "niet overal" in out["cfg_bandsteer"]["title"]
    assert "cfg_ft:Thuis" in out and "cfg_minrate:Thuis" in out
    assert "cfg_ft:IoT" not in out and "cfg_minrate:IoT" not in out      # IoT-netwerk met rust laten
    assert out["cfg_width24:b@2.4"]["severity"] == "warning"
    assert out["cfg_minrssi:c@5"]["severity"] == "warning"


def test_normalize_config_drops_secrets():
    from app.unifi_client import normalize_config
    cfg = normalize_config([{"name": "x", "x_passphrase": "geheim", "x_iapp_key": "k", "wlan_band": "both"}],
                           [{"key": "usg", "upnp_enabled": True}],
                           [{"name": "pf", "dst_port": "22", "fwd": "10.0.0.2", "fwd_port": "22", "enabled": True}])
    assert "geheim" not in str(cfg) and "x_iapp" not in str(cfg)
    assert cfg["wlans"][0]["bands"] == ["2.4", "5"] and cfg["upnp_enabled"] is True and not cfg["forwards"][0]["upnp"]


# ---------------------------------------------------------------- open naar internet + IPS negeren
def _ext(port, n, ip="198.51.100.7"):
    return [{"ts": TS - 60, "src_ip": ip, "dst_ip": "203.0.113.1", "dst_port": port, "sid": 1, "internal": False}] * n


def test_exposure_checks():
    s = snap([ap()], [client("nas", wired=True, ip="10.0.0.2", name="NAS")])
    fw = [{"name": "NAS SSH", "enabled": True, "upnp": False, "proto": "tcp", "port": "22", "fwd_ip": "10.0.0.2",
           "fwd_port": "22", "src": "any", "rx_bytes": 0},
          {"name": "Web", "enabled": True, "upnp": False, "proto": "tcp", "port": "443", "fwd_ip": "10.0.0.3",
           "fwd_port": "8443", "src": "any", "rx_bytes": 0},
          {"name": "UPnP", "enabled": True, "upnp": True, "proto": "tcp", "port": "80", "fwd_ip": "10.0.0.9",
           "fwd_port": "80", "src": "any", "rx_bytes": 0}]
    s["config"] = {"wlans": None, "upnp_enabled": True, "forwards": fw}
    db = EmptyDB()
    db.ips = _ext(443, 12)
    out = {i["key"]: i for i in rules.evaluate(s, db, Thresholds(), TS)}
    assert "SSH" in out["pf_risky:22"]["title"] and "NAS" in out["pf_risky:22"]["detail"]
    assert out["pf_attacked:443"]["value"] == 12
    assert "upnp_on" in out and out["upnp_priv:10.0.0.9:80"]["severity"] == "warning"
    db.ignores = [{"ip": "198.51.100.7", "sid": None}]
    assert "pf_attacked:443" not in {i["key"] for i in rules.evaluate(s, db, Thresholds(), TS)}


def test_ips_ignore_rules():
    e = {"src_ip": "10.0.0.5", "sid": 7}
    assert rules.ips_ignored(e, [{"ip": "10.0.0.5", "sid": None}])
    assert rules.ips_ignored(e, [{"ip": None, "sid": 7}])
    assert rules.ips_ignored(e, [{"ip": "10.0.0.5", "sid": 7}])
    assert not rules.ips_ignored(e, [{"ip": "10.0.0.5", "sid": 8}, {"ip": "10.0.0.6", "sid": None}])
