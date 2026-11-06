"""Netwerkscheiding: welke netwerken (VLAN's) er zijn, in welke firewallzone ze zitten, wat er tussen de zones
mag, en welke slimme apparaten nog op het hoofdnetwerk staan. Alleen lezen; Sonar verandert hier niets aan."""
from __future__ import annotations

import ipaddress
import re

# Fabrikanten (OUI) die vrijwel alleen slimme apparaten maken. Bewust zonder Apple, Samsung, Google, Amazon,
# Xiaomi en TP-Link: die maken ook telefoons, laptops of routers.
SMART_VENDORS = (
    "espressif", "tuya", "shelly", "allterco", "itead", "sonoff", "signify", "philips lighting", "ring llc",
    "roborock", "tado", "miele", "bsh hausger", "bosch", "homewizard", "solaredge", "enphase", "growatt",
    "fronius", "sma solar", "reolink", "hikvision", "dahua", "ezviz", "eufy", "altobeam", "lg innotek",
    "nest labs", "ecobee", "daikin", "meross", "lumi united", "wyze", "arlo", "yeelink", "beken",
    "bouffalo", "gaoshengda", "midea", "gree electric", "alfen", "wallbox", "easee", "netatmo", "somfy",
)
# Hostnamen van bekende IoT-firmware en -merken.
SMART_HOST = re.compile(
    r"^(esp[-_]|esp32|esp8266|espressif|tasmota|shelly|sonoff|nspanel|wled|lwip|tuya|hw-|homewizard|lge_|eufy|"
    r"ring-|reolink|envoy$|tado|roborock|rockrobo|wiz_|philips-hue|yeelink|openbeken|obk|slzb|ewelink|meross|"
    r"tapo|kasa|netatmo)|(-washer|-dryer|dishwasher|esphome)", re.I)
IOT_NAME = re.compile(r"iot|smart|domotica|thing|apparat|device|sensor|camera", re.I)
BUILTIN_ZONES = {"internal", "external", "gateway", "vpn", "hotspot", "dmz"}


_SUFFIX = re.compile(r"[,.]?\s+(inc|ltd|limited|llc|corp|corporation|co|company|gmbh|b\.?v|ag|sa|s\.?a\.?s|technology|"
                     r"technologies|innovation|electronics|energy|smart|international|holdings?)\b.*$", re.I)


def vendor_short(v: str) -> str:
    return _SUFFIX.sub("", v).strip(" ,.") or v


def smart_reason(c: dict) -> str | None:
    """Waarom Sonar dit voor een slim apparaat houdt, of None."""
    v = (c.get("vendor") or "").lower()
    for s in SMART_VENDORS:
        if s in v:
            return f"fabrikant {vendor_short(c['vendor'])}"
    h = c.get("hostname") or ""
    if h and SMART_HOST.search(h):
        return f"naam {h}"
    return None


def _policy_summary(p: dict) -> dict:
    d = p.get("destination") or {}
    s = p.get("source") or {}
    port = d.get("port") if d.get("port_matching_type") not in (None, "ANY") else None
    proto = (p.get("protocol") or "all").lower()
    full = (s.get("matching_target") in (None, "ANY") and d.get("matching_target") in (None, "ANY")
            and not port and proto == "all")
    return {"name": p.get("name") or "?", "action": "allow" if p.get("action") == "ALLOW" else "block",
            "enabled": bool(p.get("enabled", True)), "proto": None if proto == "all" else proto.replace("_", "/"),
            "port": str(port) if port else None, "ips": list(d.get("ips") or []),
            "to": (d.get("matching_target") or "ANY").lower(), "full": full, "index": p.get("index") or 0,
            "src_ips": list(s.get("ips") or []), "src_nets": list(s.get("network_ids") or []),
            "dst_nets": list(d.get("network_ids") or [])}


def build(networks: list[dict] | None, zones: list[dict] | None, policies: list[dict] | None) -> dict | None:
    """Uit rest/networkconf, v2 firewall/zone en v2 firewall-policies. None = geen netwerkgegevens."""
    if networks is None:
        return None
    zone_by_id = {z.get("_id"): z for z in zones or []}
    net_zone = {nid: z for z in zones or [] for nid in z.get("network_ids") or []}
    segs = []
    for n in networks:
        purpose = n.get("purpose")
        if purpose not in ("corporate", "guest"):
            continue
        z = zone_by_id.get(n.get("firewall_zone_id")) or net_zone.get(n.get("_id"))
        zkey = (z or {}).get("zone_key")
        if purpose == "guest" or zkey == "hotspot":
            kind = "guest"
        elif z and zkey not in ("internal", None):
            kind = "other" if zkey != "dmz" else "iot"
        elif z and zkey is None:
            kind = "iot" if IOT_NAME.search(f"{n.get('name')} {z.get('name')}") else "other"
        elif IOT_NAME.search(n.get("name") or ""):   # ook in de Internal-zone: dan is het wel apart, maar niet afgeschermd
            kind = "iot"
        else:
            kind = "main"
        if kind == "main" and n.get("network_isolation_enabled"):
            kind = "iot" if IOT_NAME.search(n.get("name") or "") else "other"
        segs.append({"id": n.get("_id"), "name": n.get("name") or "?", "vlan": n.get("vlan") if n.get("vlan_enabled", True) else None,
                     "subnet": n.get("ip_subnet"), "kind": kind, "zone_id": (z or {}).get("_id"),
                     "zone": (z or {}).get("name"), "isolated_flag": bool(n.get("network_isolation_enabled"))})

    matrix = None
    if zones and policies is not None and any("zone_id" in (p.get("source") or {}) for p in policies):
        shown = [z for z in zones if z.get("network_ids") or z.get("zone_key") in ("external", "gateway")]
        order = {"internal": 0, None: 1, "dmz": 2, "hotspot": 3, "vpn": 4, "gateway": 5, "external": 6}
        shown.sort(key=lambda z: (order.get(z.get("zone_key"), 1), z.get("name") or ""))
        cells: dict[str, dict] = {}
        for p in sorted(policies, key=lambda p: p.get("index") or 0):
            src, dst = (p.get("source") or {}).get("zone_id"), (p.get("destination") or {}).get("zone_id")
            cell = cells.setdefault(f"{src}>{dst}", {"default": None, "rules": []})
            if p.get("predefined"):
                if (p.get("source") or {}).get("matching_target") in (None, "ANY") and p.get("connection_state_type") == "ALL" \
                        and (p.get("protocol") or "all") == "all" and (p.get("destination") or {}).get("matching_target") in (None, "ANY"):
                    cell["default"] = "allow" if p.get("action") == "ALLOW" else "block"   # laatste (hoogste index) wint
            elif p.get("connection_state_type") != "RESPOND_ONLY":
                cell["rules"].append(_policy_summary(p))
        for c in cells.values():
            full = next((r for r in c["rules"] if r["enabled"] and r["full"]), None)
            c["effective"] = full["action"] if full else c["default"]
            c["rules"] = [{k: v for k, v in r.items() if k not in ("full", "index")} for r in c["rules"]]
        matrix = {"zones": [{"id": z.get("_id"), "name": z.get("name"), "key": z.get("zone_key"),
                             "networks": len(z.get("network_ids") or [])} for z in shown],
                  "cells": {k: v for k, v in cells.items()
                            if any(k.startswith(f"{z.get('_id')}>") for z in shown)}}

    internal_id = next((z.get("_id") for z in zones or [] if z.get("zone_key") == "internal"), None)
    for s in segs:
        if s["kind"] in ("iot", "other"):
            if s["isolated_flag"]:
                s["isolated"] = True
            elif matrix and s["zone_id"]:
                s["isolated"] = s["zone_id"] != internal_id and \
                    (matrix["cells"].get(f"{s['zone_id']}>{internal_id}") or {}).get("effective") == "block"
            else:
                s["isolated"] = None   # oude firewallregels: niet betrouwbaar af te leiden
        else:
            s["isolated"] = None
        del s["isolated_flag"]
    vpn = []
    for n in networks:
        if n.get("purpose") == "remote-user-vpn" or (n.get("vpn_type") or "").endswith("-server"):
            z = zone_by_id.get(n.get("firewall_zone_id")) or net_zone.get(n.get("_id"))
            vpn.append({"id": n.get("_id"), "name": n.get("name") or "VPN", "subnet": n.get("ip_subnet"), "kind": "vpn",
                        "zone_id": (z or {}).get("_id"), "zone": (z or {}).get("name"), "enabled": bool(n.get("enabled", True))})
    return {"segments": segs, "vpn": vpn, "matrix": matrix, "zones_available": matrix is not None}


# ------------------------------------------------------------------ verkeersstromen tussen netwerken

def _net(subnet: str | None):
    try:
        return ipaddress.ip_network(subnet, strict=False) if subnet else None
    except ValueError:
        return None


def _ip_in(ips: list[str], net) -> bool:
    for ip in ips:
        try:
            if net is not None and (ipaddress.ip_network(ip, strict=False).subnet_of(net)
                                    or net.subnet_of(ipaddress.ip_network(ip, strict=False))):
                return True
        except (ValueError, TypeError):
            continue
    return False


def _public(ips: list[str]) -> bool:
    for ip in ips:
        try:
            if not ipaddress.ip_network(ip, strict=False).is_private:
                return True
        except ValueError:
            continue
    return False


def flows(seg: dict, forwards: list[dict] | None = None) -> dict | None:
    """Per paar netwerken (plus gateway en internet): mag een nieuwe verbinding van A naar B?
    'allow', 'partial' (alleen sommige apparaten/poorten, of met uitzonderingen) of 'block', met de regels die dat
    bepalen. Nagerekend uit de zone-standaard en de eigen regels op volgorde, per netwerk verfijnd waar een regel
    op een adres of netwerk mikt."""
    m = seg.get("matrix")
    if not m:
        return None
    key_zone = {z["key"]: z["id"] for z in m["zones"] if z["key"] in ("external", "gateway")}
    nets = [{**x, "net": _net(x.get("subnet"))} for x in seg["segments"] + [v for v in seg.get("vpn", []) if v["enabled"]]
            if x.get("zone_id")]
    nodes = [{"id": n["id"], "name": n["name"], "kind": n["kind"], "zone": n.get("zone"), "subnet": n.get("subnet"),
              "isolated": n.get("isolated")} for n in nets]
    special = []
    if "gateway" in key_zone:
        special.append({"id": "gateway", "name": "Gateway", "kind": "gateway", "zone_id": key_zone["gateway"], "net": None})
    if "external" in key_zone:
        special.append({"id": "internet", "name": "Internet", "kind": "internet", "zone_id": key_zone["external"], "net": None})
    nodes += [{"id": x["id"], "name": x["name"], "kind": x["kind"]} for x in special]
    sources = nets + [x for x in special if x["id"] == "internet"]
    edges = []
    for a in sources:
        for b in nets + special:
            if a["id"] == b["id"] or (a["id"] == "internet" and b["id"] == "gateway"):
                continue
            cell = m["cells"].get(f"{a['zone_id']}>{b['zone_id']}")
            if not cell or not cell.get("default"):
                continue
            base, why, partial = cell["default"], [], False
            whole_set = False
            for r in cell["rules"]:
                if not r["enabled"]:
                    continue
                if r["src_nets"] and a["id"] not in r["src_nets"]:
                    continue
                if r["dst_nets"] and b["id"] not in r["dst_nets"]:
                    continue
                if r["src_ips"] and a["net"] is not None and not _ip_in(r["src_ips"], a["net"]):
                    continue
                if r["ips"]:
                    if b["id"] == "internet" and not _public(r["ips"]):
                        continue
                    if b["net"] is not None and not _ip_in(r["ips"], b["net"]):
                        continue
                if whole_set:   # na een regel die alles afvangt, komt de rest nooit meer aan de beurt
                    continue
                whole = not r["ips"] and not r["src_ips"] and not r["port"] and not r["proto"]
                if whole:
                    base, whole_set = r["action"], True
                why.append(r)
            if any(r["action"] != base for r in why):
                partial = True
            fw = []
            if a["id"] == "internet" and b["net"] is not None:
                for f in forwards or []:
                    if f.get("enabled") and _ip_in([f.get("fwd_ip") or ""], b["net"]):
                        fw.append({"name": f["name"], "action": "allow", "enabled": True, "proto": f.get("proto") or None,
                                   "port": f.get("port") or None, "ips": [f["fwd_ip"]], "to": "ip", "forward": True,
                                   "upnp": f.get("upnp", False)})
                if fw and base == "block":
                    partial = True
            edges.append({"from": a["id"], "to": b["id"], "status": "partial" if partial else base,
                          "default": cell["default"], "rules": [{k: v for k, v in r.items() if k not in ("src_nets", "dst_nets")}
                                                                for r in why] + fw})
    return {"nodes": nodes, "edges": edges}


def client_segment(c: dict, segs: list[dict]) -> dict | None:
    by_id = {s["id"]: s for s in segs}
    if c.get("network_id") in by_id:
        return by_id[c["network_id"]]
    return next((s for s in segs if s["name"] == c.get("network")), None)


def misplaced(clients: list[dict], seg: dict) -> list[tuple[dict, str]]:
    """Slimme apparaten op een hoofdnetwerk, terwijl er een apart netwerk voor is."""
    segs = seg["segments"]
    if not any(s["kind"] in ("iot", "other") for s in segs):
        return []
    out = []
    for c in clients:
        s = client_segment(c, segs)
        why = smart_reason(c)
        if s and s["kind"] == "main" and why and c.get("connected", True):
            out.append((c, why))
    return out


def counts(clients: list[dict], seg: dict) -> dict[str, dict]:
    out = {s["id"]: {"clients": 0, "wifi": 0, "wired": 0, "smart": 0} for s in seg["segments"]}
    for c in clients:
        s = client_segment(c, seg["segments"])
        if not s:
            continue
        o = out[s["id"]]
        o["clients"] += 1
        o["wired" if c.get("wired") else "wifi"] += 1
        o["smart"] += 1 if smart_reason(c) else 0
    return out
