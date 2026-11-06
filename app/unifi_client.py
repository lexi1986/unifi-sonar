"""Uitlezen van een UniFi OS-controller en omzetten naar één intern datamodel.

Twee bronnen:
  * legacy  – /proxy/network/api/s/<site>/stat/* (alle detaildata: signaal, retries,
              kanaalbezetting, poortfouten). Werkt met API-key (nieuwere UniFi OS)
              of met een lokaal read-only account.
  * integration – officiële /proxy/network/integration/v1 API (alleen API-key).
              Minder detail; gebruikt als terugvaloptie.
"""
from __future__ import annotations

import ipaddress
import logging
import re
from typing import Any

import httpx

from . import segments
from .config import Settings
from .i18n import L

log = logging.getLogger(__name__)

BAND = {"ng": "2.4", "na": "5", "6e": "6"}
DEVICE_TYPE = {"ugw": "gateway", "uxg": "gateway", "udm": "gateway", "usw": "switch", "uap": "ap"}
DEVICE_STATE = {0: "offline", 1: "online", 2: "pending", 4: "upgrading", 5: "provisioning",
                6: "heartbeat_missed", 9: "offline", 10: "adopting", 11: "isolated"}


def _num(v: Any, default: float | None = None) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _sat(v: Any) -> float | None:
    """UniFi gebruikt -1 voor 'geen score' (bv. radio zonder clients)."""
    n = _num(v)
    return n if n is not None and n >= 0 else None


# --------------------------------------------------------------------------- legacy

def normalize_legacy(devices: list[dict], clients: list[dict], health: list[dict]) -> dict:
    hmap = {h.get("subsystem"): h for h in health}
    www, wan_h = hmap.get("www", {}), hmap.get("wan", {})

    out_devices = []
    gateway_wan: dict = {}
    gateway_raw: dict = {}
    for d in devices:
        dtype = DEVICE_TYPE.get(d.get("type", ""), d.get("type", "other"))
        stats = d.get("system-stats") or {}
        temps = [t.get("value") for t in d.get("temperatures") or [] if _num(t.get("value")) is not None]
        temp = _num(d.get("general_temperature")) or (max(temps) if temps else None)

        radios = []
        rt = {r.get("name"): r for r in d.get("radio_table") or []}
        for rs in d.get("radio_table_stats") or []:
            base = rt.get(rs.get("name"), {})
            cu_total = _num(rs.get("cu_total"), 0)
            cu_self = (_num(rs.get("cu_self_rx"), 0) or 0) + (_num(rs.get("cu_self_tx"), 0) or 0)
            ch_cfg = base.get("channel")
            radios.append({
                "radio": BAND.get(rs.get("radio") or base.get("radio"), "?"),
                "channel": rs.get("channel") or base.get("channel"),
                "channel_auto": ch_cfg in (None, "auto", 0, "0"),
                "width": _num(base.get("ht")),
                "tx_power_mode": base.get("tx_power_mode"),
                "min_rssi": _num(base.get("min_rssi")) if base.get("min_rssi_enabled") else None,
                "tx_power": _num(rs.get("tx_power")),
                "cu_total": cu_total,
                "cu_self": cu_self,
                "interference": max(0.0, (cu_total or 0) - cu_self),
                "num_clients": int(_num(rs.get("num_sta"), 0)),
                "satisfaction": _sat(rs.get("satisfaction")),
                "tx_packets": _num(rs.get("tx_packets"), 0),
                "tx_retries": _num(rs.get("tx_retries"), 0),
                "retry_pct": _num(rs.get("tx_retries_pct")),   # door UniFi zelf berekend (actueel)
            })

        ports = []
        for p in d.get("port_table") or []:
            ports.append({
                "idx": p.get("port_idx"),
                "name": p.get("name") or f"Port {p.get('port_idx')}",
                "up": bool(p.get("up")),
                "speed": _num(p.get("speed"), 0),
                "media": p.get("media", ""),
                "full_duplex": p.get("full_duplex", True),
                "poe_w": _num(p.get("poe_power"), 0),
                "rx_errors": _num(p.get("rx_errors"), 0),
                "tx_errors": _num(p.get("tx_errors"), 0),
                "rx_dropped": _num(p.get("rx_dropped"), 0),
                "tx_dropped": _num(p.get("tx_dropped"), 0),
                "is_uplink": bool(p.get("is_uplink")),
                "rx_bytes": _num(p.get("rx_bytes"), 0),
                "tx_bytes": _num(p.get("tx_bytes"), 0),
            })

        uplink = d.get("uplink") or {}
        poe_budget = _num(d.get("total_max_power")) or _num(d.get("poe_budget"))
        dev = {
            "mac": d.get("mac"),
            "name": d.get("name") or d.get("model") or d.get("mac"),
            "model": d.get("model_name") or d.get("model", ""),
            "type": dtype,
            "state": DEVICE_STATE.get(d.get("state"), "unknown"),
            "version": d.get("version", ""),
            "upgradable": bool(d.get("upgradable")),
            "upgrade_to": d.get("upgrade_to_firmware", ""),
            "uptime": _num(d.get("uptime"), 0),
            "ip": d.get("ip", ""),
            "cpu": _num(stats.get("cpu")),
            "mem": _num(stats.get("mem")),
            "temp": temp,
            "num_clients": int(_num(d.get("num_sta"), 0)),
            "satisfaction": _sat(d.get("satisfaction")),
            "uplink_mac": uplink.get("uplink_mac"),
            "uplink_port": uplink.get("uplink_remote_port"),
            "uplink_type": uplink.get("type"),
            "uplink_speed": _num(uplink.get("speed")),
            "poe_budget_w": poe_budget,
            "poe_used_w": sum(p["poe_w"] or 0 for p in ports) if poe_budget else None,
            "radios": radios,
            "ports": ports,
            "bandsteering": d.get("bandsteering_mode") if radios else None,
        }
        out_devices.append(dev)
        if dtype == "gateway":
            gateway_wan = (d.get("uptime_stats") or {}).get("WAN") or {}
            gateway_raw = d

    avail = _num(gateway_wan.get("availability"))
    wan = {
        "up": (www.get("status") or wan_h.get("status")) == "ok",
        "latency_ms": _num(www.get("latency")) or _num(gateway_wan.get("latency_average")),
        "loss_pct": round(100 - avail, 2) if avail is not None else None,
        "wan_ip": wan_h.get("wan_ip", ""),
        "isp": wan_h.get("isp_name", ""),
        # 0 betekent "nog nooit een snelheidstest gedraaid"
        "xput_down": _num(www.get("xput_down")) or None,
        "xput_up": _num(www.get("xput_up")) or None,
        **wan_rates(gateway_raw, wan_h),
    }

    out_clients = []
    for c in clients:
        wired = bool(c.get("is_wired"))
        out_clients.append({
            "mac": c.get("mac"),
            "name": c.get("name") or c.get("hostname") or c.get("oui") or c.get("mac"),
            "hostname": c.get("hostname"),
            "ip": c.get("ip", ""),
            "vendor": c.get("oui", ""),
            "wired": wired,
            "network": c.get("network", ""),
            "network_id": c.get("network_id"),
            "guest": bool(c.get("is_guest")),
            "ssid": None if wired else c.get("essid"),
            "ap_mac": None if wired else c.get("ap_mac"),
            "sw_mac": c.get("sw_mac") if wired else None,
            "sw_port": c.get("sw_port") if wired else None,
            "band": None if wired else BAND.get(c.get("radio"), "?"),
            "channel": None if wired else c.get("channel"),
            "proto": None if wired else c.get("radio_proto"),
            "signal": None if wired else _num(c.get("signal")),
            "noise": None if wired else _num(c.get("noise")),
            "satisfaction": _sat(c.get("satisfaction")),
            "tx_rate_mbps": None if wired else round((_num(c.get("tx_rate"), 0) or 0) / 1000, 1),
            "rx_rate_mbps": None if wired else round((_num(c.get("rx_rate"), 0) or 0) / 1000, 1),
            "tx_packets": None if wired else _num(c.get("tx_packets"), 0),
            "tx_retries": None if wired else _num(c.get("tx_retries"), 0),
            "retry_pct": None if wired else _num(c.get("wifi_tx_retries_percentage")),
            "uptime": _num(c.get("uptime"), 0),
            # moment van de laatste (her)verbinding met de huidige AP
            "assoc_ts": int(_num(c.get("latest_assoc_time")) or _num(c.get("assoc_time")) or 0) or None,
            # UniFi houdt net-weggevallen wifi-clients nog even in de lijst, zonder AP
            "connected": wired or bool(c.get("ap_mac")),
            "last_ap_mac": None if wired else c.get("ap_mac") or c.get("last_uplink_mac"),
            "last_seen": int(_num(c.get("last_seen"), 0) or 0) or None,
            # door de gebruiker vastgezet aan één AP (UniFi "Lock to AP")
            "fixed_ap": c.get("fixed_ap_mac") if not wired and c.get("fixed_ap_enabled") else None,
        })
    return {"wan": wan, "devices": out_devices, "clients": out_clients}


def wan_rates(gw: dict, wan_h: dict | None = None) -> dict:
    """Actueel internetverkeer (bit/s) en linksnelheid van de actieve WAN-poort van de gateway."""
    up = gw.get("uplink") or {}
    port = next((gw[k] for k in ("wan1", "wan2", "wan3") if (gw.get(k) or {}).get("is_uplink")), None) or gw.get("wan1") or {}
    src = port or up or wan_h or {}
    rx, tx = _num(src.get("rx_bytes-r")), _num(src.get("tx_bytes-r"))
    if rx is None and wan_h:
        rx, tx = _num(wan_h.get("rx_bytes-r")), _num(wan_h.get("tx_bytes-r"))
    return {"rx_bps": rx * 8 if rx is not None else None, "tx_bps": tx * 8 if tx is not None else None,
            "rx_bytes": _num(src.get("rx_bytes")), "tx_bytes": _num(src.get("tx_bytes")),
            "link_mbps": _num(port.get("speed")) or _num(up.get("speed")) or None}


def normalize_speedtest_state(st: dict) -> dict:
    """'speedtest-status' van de gateway: fases 0 = niet gestart, 1 = bezig, 2 = klaar."""
    phases = {k: int(_num(st.get(f"status_{k}"), 0) or 0) for k in ("ping", "download", "upload")}
    running = any(v == 1 for v in phases.values()) or int(_num(st.get("status_summary"), 0) or 0) == 1
    return {"running": running, "phase": next((k for k, v in phases.items() if v == 1), None),
            "rundate": int(_num(st.get("rundate"), 0) or 0) or None,
            "down": _num(st.get("xput_download")) or None, "up": _num(st.get("xput_upload")) or None,
            "latency": _num(st.get("latency")) or None}


def normalize_speedtests(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        ts = int((_num(r.get("time")) or 0) / 1000) or int(_num(r.get("rundate"), 0) or 0)
        if not ts or not r.get("xput_download"):
            continue
        srv = r.get("server") or {}
        out.append({"ts": ts, "down": _num(r.get("xput_download")), "up": _num(r.get("xput_upload")),
                    "latency": _num(r.get("latency")), "server": ", ".join(x for x in (srv.get("city"), srv.get("provider")) if x)})
    return sorted(out, key=lambda x: x["ts"])


# ------------------------------------------------------------------ configuratie

def config_from_raw(raw: dict) -> dict:
    cfg = normalize_config(raw["wlans"], raw["settings"], raw["forwards"], raw.get("networks"))
    fw = raw.get("firewall")
    cfg["segments"] = segments.build(raw.get("networks"), raw.get("zones"),
                                     fw if raw.get("zones") is not None else None)
    return cfg


def normalize_vpn(networks: list[dict]) -> list[dict]:
    """VPN-servers op de gateway (rest/networkconf), zonder sleutels of wachtwoorden."""
    out = []
    for n in networks:
        t = (n.get("vpn_type") or "").lower()
        if not t.endswith("-server"):
            continue
        kind = t.removesuffix("-server")
        port = n.get("local_port") or n.get(f"{kind}_local_port") or (51820 if kind == "wireguard" else None)
        proto = "udp" if kind in ("wireguard", "l2tp") else (n.get("vpn_protocol") or "udp").lower()
        out.append({"name": n.get("name") or kind, "type": kind, "enabled": bool(n.get("enabled", True)),
                    "port": int(port) if port else None, "proto": proto})
    return out


def normalize_config(wlans: list[dict], settings: list[dict], forwards: list[dict], networks: list[dict] | None = None) -> dict:
    """Wifi-netwerken, UPnP en port forwards. Wachtwoorden en sleutels worden bewust overgeslagen."""
    out_wlans = []
    for w in wlans:
        bands = w.get("wlan_bands") or {"both": ["2g", "5g"], "2g": ["2g"], "5g": ["5g"]}.get(w.get("wlan_band"), ["2g", "5g"])
        out_wlans.append({
            "name": w.get("name", "?"),
            "enabled": bool(w.get("enabled", True)),
            "bands": [{"2g": "2.4", "5g": "5", "6g": "6", "6e": "6"}.get(b, b) for b in bands],   # UniFi zegt 6g
            "guest": bool(w.get("is_guest")),
            "iot": bool(w.get("enhanced_iot")) or bands == ["2g"],
            "fast_roaming": bool(w.get("fast_roaming_enabled")),
            "bss_transition": bool(w.get("bss_transition")),
            "minrate_24": int(_num(w.get("minrate_ng_data_rate_kbps"), 0)) if w.get("minrate_ng_enabled") else 0,
        })
    usg = next((x for x in settings if x.get("key") == "usg"), {})
    out_fw = []
    for f in forwards:
        upnp = bool(f.get("is_upnp")) or f.get("rule_type") == "upnp"
        out_fw.append({
            "name": f.get("name") or f.get("description") or ("UPnP" if upnp else "Port forward"),
            "enabled": bool(f.get("enabled", True)),
            "upnp": upnp,
            "proto": f.get("proto") or f.get("protocol") or "",
            "port": str(f.get("dst_port") or f.get("external_port") or ""),
            "fwd_ip": f.get("fwd") or f.get("internal_ip") or "",
            "fwd_port": str(f.get("fwd_port") or f.get("internal_port") or ""),
            "src": f.get("src") or "any",
            "rx_bytes": _num(f.get("rx_bytes"), 0),
        })
    return {"wlans": out_wlans, "upnp_enabled": usg.get("upnp_enabled"), "forwards": out_fw,
            "vpn": normalize_vpn(networks) if networks is not None else None}


# ----------------------------------------------------------------------------- IPS

_LAN_NETS = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10")]


def is_internal(ip: str | None) -> bool:
    """Eigen netwerk = RFC1918 of CGNAT (VPN-clients vallen hier ook onder)."""
    try:
        a = ipaddress.ip_address(ip or "")
    except ValueError:
        return False
    return any(a in n for n in _LAN_NETS)


_MAC = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", re.I)


def _name(n: str | None, ip: str | None) -> str | None:
    """UniFi gebruikt het MAC-adres als naam voor onbenoemde apparaten; dan liever het IP."""
    return ip if not n or _MAC.match(n) else n


_LAN_NETS = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10",
                                                  "169.254.0.0/16", "127.0.0.0/8", "fc00::/7", "fe80::/10", "::1/128")]


def _is_local_ip(ip: str | None) -> bool:
    """Adres in een thuis-/bedrijfsnetwerk (RFC 1918, CGNAT, link-local). Documentatie-adressen tellen niet mee."""
    try:
        a = ipaddress.ip_address(ip or "")
    except ValueError:
        return False
    return any(a in n for n in _LAN_NETS if n.version == a.version)


def normalize_flow(f: dict) -> dict:
    """Eén verbinding uit /v2/api/site/<site>/traffic-flows, vanuit je eigen netwerk bekeken.

    dir: 'out' (eigen apparaat → internet), 'in' (internet → eigen apparaat), 'blocked' (door de gateway
    tegengehouden) of 'local' (tussen eigen netwerken/VPN). up/down: bytes verstuurd/ontvangen door de eigen kant.
    """
    src, dst, td = f.get("source") or {}, f.get("destination") or {}, f.get("traffic_data") or {}
    incoming = f.get("direction") == "incoming"
    local_side, remote = (dst, src) if incoming else (src, dst)
    cc = remote.get("region") or remote.get("country")
    external = bool(cc) or not _is_local_ip(remote.get("ip"))
    blocked = (f.get("action") or "allowed") != "allowed"
    if not external or f.get("direction") == "local":
        direction = "local"
    else:
        direction = "blocked" if blocked else "in" if incoming else "out"   # bijv. regioblokkade of firewallregel
    tx, rx = int(td.get("bytes_tx") or 0), int(td.get("bytes_rx") or 0)
    return {
        "id": f.get("id") or f"{f.get('flow_start_time')}-{src.get('ip')}-{dst.get('ip')}-{dst.get('port')}",
        "ts": int((f.get("flow_end_time") or f.get("time") or f.get("flow_start_time") or 0) / 1000),
        "dir": direction,
        "action": f.get("action") or "allowed",
        "cc": (cc or "").upper()[:2] or None,
        "remote_ip": remote.get("ip"),
        "port": dst.get("port"),          # de dienst: poort aan de ontvangende kant
        "domain": (remote.get("domains") or [None])[0] or _name(remote.get("client_name"), None),
        "service": f.get("service"),
        "proto": f.get("protocol"),
        "client_mac": (local_side.get("mac") or "").lower() or None,
        "client_name": _name(local_side.get("client_name") or local_side.get("device_name"), local_side.get("ip")),
        "client_ip": local_side.get("ip"),
        "net": (f.get("in") or {}).get("network_name") if not incoming else (f.get("out") or {}).get("network_name"),
        "up": rx if incoming else tx,
        "down": tx if incoming else rx,
        "risk": f.get("risk"),
        "reason": _block_reason(f) if blocked else None,
    }


def normalize_usage(rows: list[dict]) -> list[dict]:
    """Rapportregels → [{ts, rx, tx}] in bytes; rx = gedownload, tx = geüpload (WAN1 + WAN2)."""
    out = []
    for r in rows:
        if not r.get("time"):
            continue
        rx = (_num(r.get("wan-rx_bytes"), 0) or 0) + (_num(r.get("wan2-rx_bytes"), 0) or 0)
        tx = (_num(r.get("wan-tx_bytes"), 0) or 0) + (_num(r.get("wan2-tx_bytes"), 0) or 0)
        out.append({"ts": int(r["time"] / 1000), "rx": round(rx), "tx": round(tx)})
    return out


def _block_reason(f: dict) -> str:
    """Waardoor een verbinding tegengehouden werd, in gewone woorden."""
    for p in f.get("policies") or []:
        t, it = (p.get("type") or "").upper(), (p.get("internal_type") or "").upper()
        if "REGION" in it:
            return "Regioblokkade"
        if t == "INTRUSION_PREVENTION" or "IPS" in it:
            return "IPS"
        if t == "FIREWALL":
            return "Firewallregel"
        if t:
            return t.replace("_", " ").capitalize()
    return "Geblokkeerd"


def normalize_ips(f: dict) -> dict:
    """Eén geblokkeerde flow uit /v2/api/site/<site>/traffic-flows (policy_type INTRUSION_PREVENTION)."""
    ips, src, dst = f.get("ips") or {}, f.get("source") or {}, f.get("destination") or {}
    src_ip = src.get("ip")
    return {
        "id": f.get("id") or f"{f.get('flow_start_time')}-{src_ip}-{dst.get('ip')}-{dst.get('port')}",
        "ts": int((f.get("flow_start_time") or f.get("time") or 0) / 1000),
        "action": f.get("action", "blocked"),
        "risk": f.get("risk"),
        "src_ip": src_ip,
        "src_name": _name(src.get("client_name") or (src.get("domains") or [None])[0], src_ip),
        "src_mac": src.get("mac"),
        "src_net": (f.get("in") or {}).get("network_name") or src.get("network_name"),
        "src_country": src.get("country") or src.get("region"),
        "dst_ip": dst.get("ip"),
        "dst_port": dst.get("port"),
        "dst_name": _name(dst.get("client_name"), dst.get("ip")),
        "dst_net": (f.get("out") or {}).get("network_name") or dst.get("network_name"),
        "proto": f.get("protocol"),
        "service": f.get("service"),
        "signature": ips.get("signature") or "Onbekende regel",
        "sid": ips.get("signature_id"),
        "category": ips.get("category_name") or "",
        "info": ips.get("alarm_category_potential_risk") or "",
        "internal": is_internal(src_ip),
    }


# ---------------------------------------------------------------------- integration

def normalize_integration(devices: list[dict], stats: dict[str, dict], clients: list[dict]) -> dict:
    by_id = {d["id"]: d for d in devices}
    out_devices = []
    for d in devices:
        s = stats.get(d["id"], {})
        feats = [f.lower() for f in d.get("features", [])]
        model = d.get("model", "")
        dtype = "ap" if "accesspoint" in feats else "switch" if "switching" in feats else (
            "gateway" if model.upper().startswith(("UXG", "UDM", "UCG", "UDR", "USG")) else "other")
        radios = []
        for r in (s.get("interfaces") or {}).get("radios") or []:
            ghz = _num(r.get("frequencyGHz"))
            radios.append({
                "radio": "2.4" if ghz and ghz < 3 else "6" if ghz and ghz > 5.9 else "5",
                "channel": None, "channel_auto": None, "width": None, "tx_power": None, "tx_power_mode": None, "min_rssi": None,
                "cu_total": None, "cu_self": None, "interference": None,
                "num_clients": 0, "satisfaction": None,
                "tx_packets": None, "tx_retries": None,
                "retry_pct": _num(r.get("txRetriesPct")),
            })
        out_devices.append({
            "mac": (d.get("macAddress") or "").lower(),
            "name": d.get("name") or model,
            "model": model, "type": dtype,
            "state": "online" if d.get("state") == "ONLINE" else d.get("state", "unknown").lower(),
            "version": d.get("firmwareVersion", ""),
            "upgradable": bool(d.get("firmwareUpdatable")), "upgrade_to": "",
            "uptime": _num(s.get("uptimeSec"), 0), "ip": d.get("ipAddress", ""),
            "cpu": _num(s.get("cpuUtilizationPct")), "mem": _num(s.get("memoryUtilizationPct")),
            "temp": None, "num_clients": 0, "satisfaction": None,
            "uplink_mac": None, "uplink_port": None, "uplink_type": None, "uplink_speed": None,
            "poe_budget_w": None, "poe_used_w": None,
            "radios": radios, "ports": [], "bandsteering": None,
        })
    out_clients = []
    for c in clients:
        wired = c.get("type") == "WIRED"
        up = by_id.get(c.get("uplinkDeviceId"), {})
        up_mac = (up.get("macAddress") or "").lower() or None
        out_clients.append({
            "mac": (c.get("macAddress") or "").lower(), "name": c.get("name") or c.get("macAddress"),
            "ip": c.get("ipAddress", ""), "vendor": "", "wired": wired, "network": "", "guest": False,
            "ssid": None, "ap_mac": None if wired else up_mac,
            "sw_mac": up_mac if wired else None, "sw_port": None,
            "band": None, "channel": None, "proto": None, "signal": None, "noise": None,
            "satisfaction": None, "tx_rate_mbps": None, "rx_rate_mbps": None,
            "tx_packets": None, "tx_retries": None, "uptime": 0, "assoc_ts": None,
            "connected": True, "last_ap_mac": None if wired else up_mac, "last_seen": None, "fixed_ap": None,
        })
    for dev in out_devices:
        dev["num_clients"] = sum(1 for c in out_clients if dev["mac"] in (c["ap_mac"], c["sw_mac"]))
    return {"wan": {"up": None, "latency_ms": None, "loss_pct": None, "wan_ip": "", "isp": "",
                    "xput_down": None, "xput_up": None, "rx_bps": None, "tx_bps": None, "rx_bytes": None,
                    "tx_bytes": None, "link_mbps": None},
            "devices": out_devices, "clients": out_clients}


# --------------------------------------------------------------------------- client

class UnifiClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.http = httpx.AsyncClient(base_url=settings.controller_url, verify=settings.verify_tls,
                                      timeout=20, follow_redirects=True)
        self.source: str | None = None   # "legacy-key", "legacy-login" of "integration"
        self._logged_in = False
        self._csrf: str | None = None
        self._site_id: str | None = None
        self.errors: dict[str, Exception] = {}   # laatste fout per bron (voor de setup-wizard)

    async def close(self) -> None:
        await self.http.aclose()

    def _headers(self) -> dict:
        return {"X-API-KEY": self.s.api_key, "Accept": "application/json"} if self.s.api_key else {}

    async def _login(self) -> None:
        r = await self.http.post("/api/auth/login", json={
            "username": self.s.username, "password": self.s.password, "rememberMe": True})
        r.raise_for_status()
        self._logged_in = True
        self._csrf = r.headers.get("x-csrf-token")

    async def _legacy(self, path: str, use_key: bool) -> list[dict]:
        url = f"/proxy/network/api/s/{self.s.site}/{path}"
        r = await self.http.get(url, headers=self._headers() if use_key else {})
        if r.status_code == 401 and not use_key and self.s.username:
            await self._login()
            r = await self.http.get(url)
        r.raise_for_status()
        return r.json().get("data", [])

    async def _fetch_legacy(self, use_key: bool) -> dict:
        devices = await self._legacy("stat/device", use_key)
        clients = await self._legacy("stat/sta", use_key)
        health = await self._legacy("stat/health", use_key)
        return normalize_legacy(devices, clients, health)

    async def _fetch_integration(self) -> dict:
        h = self._headers()
        base = "/proxy/network/integration/v1"
        if not self._site_id:
            sites = (await self.http.get(f"{base}/sites", headers=h)).raise_for_status().json()["data"]
            site = next((x for x in sites if x.get("internalReference") == self.s.site), None)
            if site is None:
                raise RuntimeError(L(f"NoSiteContext: site '{self.s.site}' niet gevonden", f"NoSiteContext: site '{self.s.site}' not found"))
            self._site_id = site["id"]
        sb = f"{base}/sites/{self._site_id}"
        devices = (await self.http.get(f"{sb}/devices?limit=200", headers=h)).raise_for_status().json()["data"]
        stats = {}
        for d in devices:
            r = await self.http.get(f"{sb}/devices/{d['id']}/statistics/latest", headers=h)
            if r.status_code == 200:
                stats[d["id"]] = r.json()
        clients = (await self.http.get(f"{sb}/clients?limit=500", headers=h)).raise_for_status().json()["data"]
        return normalize_integration(devices, stats, clients)

    async def sites(self) -> list[dict] | None:
        """Beschikbare sites [{name, desc}] of None als dat niet op te vragen is."""
        try:
            if self.s.api_key:
                r = await self.http.get("/proxy/network/api/self/sites", headers=self._headers())
            else:
                await self._login()
                r = await self.http.get("/proxy/network/api/self/sites")
            if r.status_code == 200:
                return [{"name": x.get("name"), "desc": x.get("desc")} for x in r.json().get("data", [])]
        except Exception:  # noqa: BLE001
            pass
        return None

    def _write_headers(self) -> dict:
        return self._headers() if self.source == "legacy-key" else ({"x-csrf-token": self._csrf} if self._csrf else {})

    async def fetch_config_raw(self) -> dict | None:
        """Ruwe instellingen (alleen lezen): wifi, algemene instellingen, port forwards, netwerken, firewall.
        None = niet beschikbaar. Wachtwoorden zitten erin; die gaan alleen gehasht het wijzigingslog in."""
        if self.source not in ("legacy-key", "legacy-login"):
            return None
        use_key = self.source == "legacy-key"
        raw = {"wlans": await self._legacy("rest/wlanconf", use_key),
               "settings": await self._legacy("rest/setting", use_key),
               "forwards": await self._legacy("stat/portforward", use_key)}   # statisch én actieve UPnP-mappings
        try:
            raw["networks"] = await self._legacy("rest/networkconf", use_key)
        except Exception:  # noqa: BLE001 – optioneel
            raw["networks"] = None
        raw["firewall"] = raw["zones"] = None
        try:   # zone-gebaseerde firewall (Network 9+), anders de oude regels
            v2h = self._headers() if use_key else {}
            r = await self.http.get(f"/proxy/network/v2/api/site/{self.s.site}/firewall-policies", headers=v2h)
            if r.status_code == 200 and isinstance(r.json(), list):
                raw["firewall"] = r.json()
                z = await self.http.get(f"/proxy/network/v2/api/site/{self.s.site}/firewall/zone", headers=v2h)
                if z.status_code == 200 and isinstance(z.json(), list):
                    raw["zones"] = z.json()
            else:
                raw["firewall"] = await self._legacy("rest/firewallrule", use_key)
        except Exception:  # noqa: BLE001 – optioneel
            pass
        return raw

    async def fetch_config(self) -> dict | None:
        """Wifi-instellingen, UPnP, port forwards en VPN-servers (alleen lezen). None = niet beschikbaar."""
        raw = await self.fetch_config_raw()
        return config_from_raw(raw) if raw is not None else None

    async def sysinfo(self) -> dict:
        if self.source not in ("legacy-key", "legacy-login"):
            return {}
        rows = await self._legacy("stat/sysinfo", self.source == "legacy-key")
        si = rows[0] if rows else {}
        return {"network_version": si.get("version"), "build": si.get("build"), "timezone": si.get("timezone")}

    # ----------------------------------------------------------- internet
    def _legacy_only(self) -> bool:
        if self.source not in ("legacy-key", "legacy-login"):
            raise RuntimeError(L("Alleen beschikbaar via de uitgebreide API (API-key of lokaal account)",
                                 "Only available via the extended API (API key or local account)"))
        return self.source == "legacy-key"

    async def gateway(self, mac: str) -> dict:
        """Ruwe gegevens van alleen de gateway: snel genoeg om elke paar seconden op te vragen."""
        rows = await self._legacy(f"stat/device/{mac}", self._legacy_only())
        return rows[0] if rows else {}

    async def speedtest_start(self, mac: str) -> None:
        self._legacy_only()
        r = await self.http.post(f"/proxy/network/api/s/{self.s.site}/cmd/devmgr", headers=self._write_headers(),
                                 json={"cmd": "speedtest", "mac": mac.lower()})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200 or (body.get("meta") or {}).get("rc") not in (None, "ok"):
            raise RuntimeError((body.get("meta") or {}).get("msg") or f"HTTP {r.status_code}")

    async def speedtests(self, since_s: int, until_s: int) -> list[dict]:
        self._legacy_only()
        r = await self.http.post(f"/proxy/network/api/s/{self.s.site}/stat/report/archive.speedtest",
                                 headers=self._write_headers(),
                                 json={"attrs": ["xput_download", "xput_upload", "latency", "time", "rundate", "server"],
                                       "start": since_s * 1000, "end": until_s * 1000})
        r.raise_for_status()
        return normalize_speedtests(r.json().get("data", []))

    async def usage(self, period: str, since_s: int, until_s: int) -> list[dict]:
        """Internetverbruik per dag of maand (stat/report/daily.site, monthly.site), alle WAN-poorten samen."""
        self._legacy_only()
        report = {"day": "daily", "month": "monthly"}[period]
        r = await self.http.post(f"/proxy/network/api/s/{self.s.site}/stat/report/{report}.site",
                                 headers=self._write_headers(),
                                 json={"attrs": ["wan-rx_bytes", "wan-tx_bytes", "wan2-rx_bytes", "wan2-tx_bytes", "time"],
                                       "start": since_s * 1000, "end": until_s * 1000})
        r.raise_for_status()
        return normalize_usage(r.json().get("data", []))

    async def fetch_ips(self, since_ms: int, until_ms: int) -> list[dict] | None:
        """Door de IPS geblokkeerde flows. None = niet beschikbaar met deze bron."""
        if self.source not in ("legacy-key", "legacy-login"):
            return None
        headers = self._write_headers()
        out: list[dict] = []
        for page in range(20):
            r = await self.http.post(
                f"/proxy/network/v2/api/site/{self.s.site}/traffic-flows", headers=headers,
                json={"timestampFrom": since_ms, "timestampTo": until_ms, "pageNumber": page,
                      "pageSize": 200, "policy_type": ["INTRUSION_PREVENTION"]})
            if r.status_code != 200:
                log.warning("IPS-flows ophalen mislukt: %s %s", r.status_code, r.text[:200])
                return out or None
            body = r.json()
            out += [normalize_ips(f) for f in body.get("data", [])]
            if page + 1 >= body.get("total_page_count", 1):
                break
        return out

    async def fetch_flows(self, since_ms: int, until_ms: int, max_pages: int = 40) -> list[dict] | None:
        """Alle verbindingen (toegestaan en geblokkeerd) uit het verkeerslogboek. None = niet beschikbaar."""
        if self.source not in ("legacy-key", "legacy-login"):
            return None
        headers = self._write_headers()
        out: list[dict] = []
        for page in range(max_pages):
            r = await self.http.post(
                f"/proxy/network/v2/api/site/{self.s.site}/traffic-flows", headers=headers,
                json={"timestampFrom": since_ms, "timestampTo": until_ms, "pageNumber": page, "pageSize": 200})
            if r.status_code != 200:
                log.warning("Verbindingen ophalen mislukt: %s %s", r.status_code, r.text[:200])
                return out or None
            body = r.json()
            out += [normalize_flow(f) for f in body.get("data", []) if not f.get("ips")]
            if page + 1 >= body.get("total_page_count", 1):
                break
        return out

    async def reconnect(self, mac: str) -> None:
        """Laat een wifi-client opnieuw verbinden (UniFi 'kick-sta'); hij kiest dan zelf opnieuw een AP."""
        if self.source not in ("legacy-key", "legacy-login"):
            raise RuntimeError(L("Opnieuw verbinden kan alleen via de uitgebreide API", "Reconnecting only works via the extended API"))
        headers = self._write_headers()
        r = await self.http.post(f"/proxy/network/api/s/{self.s.site}/cmd/stamgr", headers=headers,
                                 json={"cmd": "kick-sta", "mac": mac.lower()})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200 or (body.get("meta") or {}).get("rc") not in (None, "ok"):
            raise RuntimeError((body.get("meta") or {}).get("msg") or f"HTTP {r.status_code}")

    async def block(self, mac: str, blocked: bool) -> None:
        """Apparaat blokkeren of weer toelaten (UniFi 'block-sta'/'unblock-sta'): geblokkeerd kan het niet
        verbinden met wifi of het netwerk. Sonar gebruikt dit voor 'internet pauzeren'."""
        if self.source not in ("legacy-key", "legacy-login"):
            raise RuntimeError(L("Pauzeren kan alleen via de uitgebreide API", "Pausing only works via the extended API"))
        r = await self.http.post(f"/proxy/network/api/s/{self.s.site}/cmd/stamgr", headers=self._write_headers(),
                                 json={"cmd": "block-sta" if blocked else "unblock-sta", "mac": mac.lower()})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200 or (body.get("meta") or {}).get("rc") not in (None, "ok"):
            raise RuntimeError((body.get("meta") or {}).get("msg") or f"HTTP {r.status_code}")

    async def fetch(self) -> dict:
        """Kies automatisch de rijkste bron die werkt en onthoud die."""
        order = [self.source] if self.source else []
        order += [s for s in ("legacy-key", "legacy-login", "integration") if s not in order]
        last_err: Exception | None = None
        for src in order:
            if src == "legacy-key" and not self.s.api_key:
                continue
            if src == "legacy-login" and not self.s.username:
                continue
            if src == "integration" and not self.s.api_key:
                continue
            try:
                data = await (self._fetch_integration() if src == "integration"
                              else self._fetch_legacy(use_key=src == "legacy-key"))
                if src != self.source:
                    log.info("UniFi-bron: %s", src)
                self.source = src
                data["source"] = src
                return data
            except Exception as e:  # noqa: BLE001 – volgende bron proberen
                log.warning("Bron %s mislukt: %s", src, e)
                self.errors[src] = e
                last_err = e
        raise RuntimeError(L(f"Geen enkele UniFi-bron werkt: {last_err}", f"No UniFi source works: {last_err}"))
