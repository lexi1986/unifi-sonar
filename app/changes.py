"""Wijzigingslog: wat er aan de instellingen van het netwerk veranderd is.

Van de instellingen (wifi, netwerken, port forwards, firewall, algemene instellingen) en van de apparaten
(naam, kanalen, breedte, zendvermogen, band steering) maken we een 'vingerafdruk': een plat woordenboek
met per instelling een leesbare waarde. Door de vorige en de nieuwe vingerafdruk te vergelijken ontstaan
gebeurtenissen voor de tijdlijn, zoals "Wifi 'Thuis': Fast Roaming uit → aan".

Wachtwoorden worden nooit opgeslagen: alleen een gezouten hash, zodat "Wachtwoord gewijzigd" kan.

De vingerafdruk zelf is altijd Nederlands (anders zou wisselen van taal als wijziging tellen); de berichten
op de tijdlijn worden in beide talen gemaakt.
"""
from __future__ import annotations

import hashlib
import re

from . import i18n

SEP = "\t"
SECRET = "#"   # waarden die met # beginnen zijn hashes: alleen 'gewijzigd' tonen
BANDS = {"2g": "2.4", "5g": "5", "6g": "6", "6e": "6"}


def _onoff(v) -> str:
    return "aan" if v else "uit"


def _secret(salt: str, value) -> str | None:
    if not value:
        return None
    return SECRET + hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16]


def _security(w: dict) -> str:
    sec = (w.get("security") or "").lower()
    if sec in ("open", ""):
        return "open"
    if sec == "wpapsk":
        if w.get("wpa3_support") and not w.get("wpa3_transition"):
            return "WPA3"
        return "WPA2/WPA3" if w.get("wpa3_transition") else "WPA2"
    return sec.upper()


def _rate(enabled, kbps) -> str:
    return f"{(kbps or 0) / 1000:g} Mbit/s" if enabled else "uit"


def config_fingerprint(raw: dict, salt: str) -> dict[str, str]:
    """raw: {'wlans', 'settings', 'forwards', 'networks', 'firewall'} zoals de controller ze geeft."""
    fp: dict[str, str] = {}
    nets = {n.get("_id"): n.get("name") for n in raw.get("networks") or []}

    def put(section: str, name: str, label: str, value) -> None:
        if value is None:
            return
        fp[SEP.join((section, name or "?", label))] = value if isinstance(value, str) else str(value)

    for w in raw.get("wlans") or []:
        n = w.get("name")
        put("Wifi", n, "", "bestaat")
        put("Wifi", n, "ingeschakeld", _onoff(w.get("enabled", True)))
        put("Wifi", n, "beveiliging", _security(w))
        put("Wifi", n, "wachtwoord", _secret(salt, w.get("x_passphrase")))
        put("Wifi", n, "banden", ", ".join(BANDS.get(b, b) for b in w.get("wlan_bands") or []) + " GHz")
        put("Wifi", n, "verborgen", _onoff(w.get("hide_ssid")))
        put("Wifi", n, "gastnetwerk", _onoff(w.get("is_guest")))
        put("Wifi", n, "netwerk", nets.get(w.get("networkconf_id")))
        put("Wifi", n, "Fast Roaming", _onoff(w.get("fast_roaming_enabled")))
        put("Wifi", n, "Fast Roaming (WPA3)", _onoff(w.get("wpa3_fast_roaming")))
        put("Wifi", n, "handoff-suggesties (802.11v)", _onoff(w.get("bss_transition")))
        put("Wifi", n, "minimale snelheid 2.4 GHz", _rate(w.get("minrate_ng_enabled"), w.get("minrate_ng_data_rate_kbps")))
        put("Wifi", n, "minimale snelheid 5 GHz", _rate(w.get("minrate_na_enabled"), w.get("minrate_na_data_rate_kbps")))
        for band, key in (("5 GHz", "na"), ("6 GHz", "6e")):
            if f"roaming_assistant_{key}_enabled" in w:
                on = w.get(f"roaming_assistant_{key}_enabled")
                put("Wifi", n, f"roaming-assistent {band}", f"{w.get(f'roaming_assistant_{key}_rssi')} dBm" if on else "uit")
        put("Wifi", n, "beveiligde beheerframes (PMF)", w.get("pmf_mode"))
        put("Wifi", n, "client-isolatie", _onoff(w.get("l2_isolation")))
        put("Wifi", n, "multicast-verbetering", _onoff(w.get("mcastenhance_enabled")))
        put("Wifi", n, "MLO", _onoff(w.get("mlo_enabled")) if "mlo_enabled" in w else None)

    for nw in raw.get("networks") or []:
        n = nw.get("name")
        vpn = (nw.get("vpn_type") or "").endswith("-server")
        sec = "VPN-server" if vpn else "WAN" if nw.get("purpose") == "wan" else "Netwerk"
        put(sec, n, "", "bestaat")
        put(sec, n, "ingeschakeld", _onoff(nw.get("enabled", True)))
        if vpn:
            put(sec, n, "poort", f"{nw.get('local_port')}/{(nw.get('vpn_protocol') or 'udp').lower()}")
        elif nw.get("purpose") == "wan":
            put(sec, n, "Smart Queues", _onoff(nw.get("wan_smartq_enabled")))
        else:
            put(sec, n, "subnet", nw.get("ip_subnet"))
            put(sec, n, "VLAN", str(nw.get("vlan")) if nw.get("vlan_enabled") else "geen")
            put(sec, n, "DHCP", f"{nw.get('dhcpd_start')} – {nw.get('dhcpd_stop')}" if nw.get("dhcpd_enabled") else "uit")
            put(sec, n, "IGMP-snooping", _onoff(nw.get("igmp_snooping")))
            put(sec, n, "internettoegang", _onoff(nw.get("internet_access_enabled", True)))

    for f in raw.get("forwards") or []:
        if f.get("is_upnp"):
            continue   # UPnP-mappings komen en gaan vanzelf
        n = f.get("name")
        put("Port forward", n, "", "bestaat")
        put("Port forward", n, "ingeschakeld", _onoff(f.get("enabled", True)))
        put("Port forward", n, "regel", f"{f.get('proto') or 'tcp_udp'} {f.get('dst_port')} → {f.get('fwd')}:{f.get('fwd_port')}")
        put("Port forward", n, "bron", f.get("src") or "iedereen")

    for r in raw.get("firewall") or []:
        if r.get("predefined"):
            continue
        n = r.get("name")
        put("Firewallregel", n, "", "bestaat")
        put("Firewallregel", n, "ingeschakeld", _onoff(r.get("enabled", True)))
        put("Firewallregel", n, "actie", (r.get("action") or "").lower() or None)

    s = {x.get("key"): x for x in raw.get("settings") or []}
    put("Instelling", "UPnP", "", _onoff((s.get("usg") or {}).get("upnp_enabled")) if "usg" in s else None)
    gs = s.get("global_switch") or {}
    put("Instelling", "Spanning tree", "", gs.get("stp_version"))
    put("Instelling", "automatische edge-detectie", "", _onoff(gs.get("auto_stp_edge_detection_enabled")) if gs else None)
    ips = s.get("ips") or {}
    put("Instelling", "IPS-modus", "", ips.get("ips_mode"))
    mgmt = s.get("mgmt") or {}
    put("Instelling", "SSH op apparaten", "", _onoff(mgmt.get("x_ssh_enabled")) if mgmt else None)
    put("Instelling", "status-ledjes", "", _onoff(mgmt.get("led_enabled")) if "led_enabled" in mgmt else None)
    return fp


def device_fingerprint(devices: list[dict]) -> dict[str, str]:
    """Per apparaat (op MAC): naam, radio-instellingen en band steering. Werkelijk zendvermogen bij 'auto'
    schommelt vanzelf en telt daarom niet mee."""
    fp: dict[str, str] = {}
    for d in devices:
        m = d["mac"]
        fp[SEP.join(("dev", m, "naam"))] = d.get("name") or m
        if d.get("bandsteering") is not None:
            fp[SEP.join(("dev", m, "band steering"))] = {"prefer_5g": "voorkeur 5 GHz", "equal": "gelijk verdelen",
                                                         "off": "uit"}.get(d["bandsteering"], str(d["bandsteering"]))
        for r in d.get("radios") or []:
            b = r.get("radio")
            if r.get("channel") is not None:
                fp[SEP.join(("dev", m, f"{b} GHz kanaal"))] = f"{r['channel']}" + (" (auto)" if r.get("channel_auto") else "")
            if r.get("width"):
                fp[SEP.join(("dev", m, f"{b} GHz breedte"))] = f"{int(r['width'])} MHz"
            if r.get("tx_power_mode"):
                mode = r["tx_power_mode"]
                fp[SEP.join(("dev", m, f"{b} GHz zendvermogen"))] = (f"{mode} ({r['tx_power']:g} dBm)"
                                                                      if mode == "custom" and r.get("tx_power") else mode)
            fp[SEP.join(("dev", m, f"{b} GHz minimum-RSSI"))] = f"{r['min_rssi']:g} dBm" if r.get("min_rssi") else "uit"
    return fp


SECTION_EN = {"VPN-server": "VPN server", "Netwerk": "Network", "Firewallregel": "Firewall rule", "Instelling": "Setting"}
WORD_EN = {
    "ingeschakeld": "enabled", "beveiliging": "security", "wachtwoord": "password", "banden": "bands",
    "verborgen": "hidden", "gastnetwerk": "guest network", "netwerk": "network",
    "handoff-suggesties (802.11v)": "handoff suggestions (802.11v)", "beveiligde beheerframes (PMF)":
    "protected management frames (PMF)", "client-isolatie": "client isolation", "multicast-verbetering":
    "multicast enhancement", "poort": "port", "IGMP-snooping": "IGMP snooping", "internettoegang": "internet access",
    "regel": "rule", "bron": "source", "actie": "action", "automatische edge-detectie": "automatic edge detection",
    "IPS-modus": "IPS mode", "SSH op apparaten": "SSH on devices", "status-ledjes": "status LEDs", "naam": "name",
    "aan": "on", "uit": "off", "bestaat": "exists", "geen": "none", "iedereen": "anyone",
    "voorkeur 5 GHz": "prefer 5 GHz", "gelijk verdelen": "balance equally",
}
_PARTS_EN = [("minimale snelheid", "minimum rate"), ("roaming-assistent", "roaming assistant"), ("kanaal", "channel"),
             ("breedte", "width"), ("zendvermogen", "transmit power"), ("minimum-RSSI", "minimum RSSI")]


def _en(text: str | None) -> str | None:
    """Een label of waarde uit de (Nederlandse) vingerafdruk in het Engels."""
    if not text:
        return text
    if text in WORD_EN:
        return WORD_EN[text]
    if text in SECTION_EN:
        return SECTION_EN[text]
    for nl, en in _PARTS_EN:
        text = re.sub(rf"\b{re.escape(nl)}\b", en, text)
    return text


def diff(old: dict[str, str], new: dict[str, str], devnames: dict[str, str] | None = None) -> list[dict]:
    """Verschillen als gebeurtenissen: [{entity_type, entity_id, message}], met message in beide talen."""
    devnames = devnames or {}
    out: list[dict] = []
    gone_entities = {k.rsplit(SEP, 1)[0] for k in old if k.endswith(SEP) and k not in new}
    new_entities = {k.rsplit(SEP, 1)[0] for k in new if k.endswith(SEP) and k not in old}
    for k in sorted(set(old) | set(new)):
        a, b = old.get(k), new.get(k)
        if a == b:
            continue
        section, name, label = k.split(SEP)
        if section == "dev":
            if b is None or a is None:   # apparaat erbij of weg: dat melden de andere gebeurtenissen al
                continue
            who = devnames.get(name, name)
            if label == "naam":
                msg = i18n.bi(f"Apparaat hernoemd: {a} → {b}", f"Device renamed: {a} → {b}")
            else:
                msg = i18n.bi(f"{who} · {label}: {a} → {b}", f"{who} · {_en(label)}: {_en(a)} → {_en(b)}")
            out.append({"entity_type": "device", "entity_id": name, "message": msg})
            continue
        ent = f"{section}{SEP}{name}"
        sec_en, name_en = _en(section), (_en(name) if section == "Instelling" else name)

        def title(sec: str, nm: str) -> str:
            return f"{sec} '{nm}'" if nm not in ("", "?") and label else f"{sec}: {nm}" if not label else sec
        if not label:   # het ding zelf
            if section == "Instelling":
                if ent in new_entities or (a is None and b):
                    msg = i18n.bi(f"{section} {name}: {b}", f"{sec_en} {name_en}: {_en(b)}")
                elif ent in gone_entities or (b is None and a):
                    msg = i18n.bi(f"{section} {name}: {a} → –", f"{sec_en} {name_en}: {_en(a)} → –")
                else:
                    msg = i18n.bi(f"{section} {name}: {a} → {b}", f"{sec_en} {name_en}: {_en(a)} → {_en(b)}")
            elif ent in new_entities or (a is None and b):
                msg = i18n.bi(f"{section} '{name}' toegevoegd", f"{sec_en} '{name}' added")
            elif ent in gone_entities or (b is None and a):
                msg = i18n.bi(f"{section} '{name}' verwijderd", f"{sec_en} '{name}' removed")
            else:
                msg = i18n.bi(f"{section} {name}: {a} → {b}", f"{sec_en} {name}: {_en(a)} → {_en(b)}")
            out.append({"entity_type": "site", "entity_id": ent, "message": msg})
            continue
        if ent in new_entities or ent in gone_entities:
            continue   # nieuwe/verwijderde dingen: één regel is genoeg
        if (a or "").startswith(SECRET) or (b or "").startswith(SECRET):
            msg = i18n.bi(f"{title(section, name)}: {label} gewijzigd", f"{title(sec_en, name_en)}: {_en(label)} changed")
        else:
            msg = i18n.bi(f"{title(section, name)}: {label} {a or '–'} → {b or '–'}",
                          f"{title(sec_en, name_en)}: {_en(label)} {_en(a) or '–'} → {_en(b) or '–'}")
        out.append({"entity_type": "site", "entity_id": ent, "message": msg})
    return out
