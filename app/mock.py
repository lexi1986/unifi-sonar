"""Gesimuleerd UniFi-netwerk dat ruwe data levert in hetzelfde formaat als de
legacy controller-API. Zo test je de hele keten (normaliseren → opslaan →
issue-detectie → dashboard) zonder controller.

Bewust ingebouwde problemen:
  * Ring Deurbel: zwak signaal op AP Schuur (2.4 GHz), veel retries
  * Sonos Keuken: blijft wisselen tussen AP Woonkamer en AP Boven
  * AP Woonkamer 2.4 GHz: hoge kanaalbezetting door buren
  * Switch Meterkast poort 7: oplopende CRC/rx-fouten (kabel)
  * Switch Kantoor poort 3: draait op 100 Mbit i.p.v. 1 Gbit
  * Switch Kantoor: PoE-budget bijna vol
  * Switch Schuur poort 4: link gaat regelmatig op en neer
  * AP Kantoor: firmware-update beschikbaar
  * WAN: af en toe een latency-piek
  * AP Boven herstart na 3 uur; de Kindle blijft daarna hangen op AP Schuur
  * Printer HP zakt na 3,5 uur weg naar AP Schuur en blijft daar (zonder herstart)
  * Instellingen: AP Woonkamer en AP Schuur in hetzelfde 5 GHz-blok, 2.4 GHz-kanaal 11 vrij,
    band steering uit op AP Schuur, Fast Roaming uit, UPnP aan, SSH doorgezet naar de NAS
  * Een week grove historie voor de patronen (aanwezigheid, drukte per uur)
"""
from __future__ import annotations

import math
import random

R = random.Random(42)


def _mac(i: int) -> str:
    return "f4:e2:c6:%02x:%02x:%02x" % ((i >> 16) & 255, (i >> 8) & 255, i & 255)


GW, SW_MK, SW_KT, SW_SC = _mac(1), _mac(2), _mac(3), _mac(4)
AP_WK, AP_BV, AP_KT, AP_SC = _mac(11), _mac(12), _mac(13), _mac(14)

APS = {
    AP_WK: dict(name="AP Woonkamer", model="U7PRO", model_name="U7 Pro", uplink=(SW_MK, 2)),
    AP_BV: dict(name="AP Boven", model="U6PRO", model_name="U6 Pro", uplink=(SW_MK, 3)),
    AP_KT: dict(name="AP Kantoor", model="U6LITE", model_name="U6 Lite", uplink=(SW_KT, 2)),
    AP_SC: dict(name="AP Schuur", model="U6MESH", model_name="U6 Mesh", uplink=(SW_SC, 2)),
}

WIRELESS = [  # naam, vendor, ap, band, basis-signaal, basis-retry%
    ("iPhone", "Apple", AP_WK, "na", -54, 4), ("MacBook Pro", "Apple", AP_KT, "na", -49, 3),
    ("iPad Keuken", "Apple", AP_WK, "na", -63, 6), ("Sonos Keuken", "Sonos", AP_WK, "na", -67, 9),
    ("Sonos Woonkamer", "Sonos", AP_WK, "na", -52, 4), ("Ring Deurbel", "Ring", AP_SC, "ng", -82, 34),
    ("Nest Thermostaat", "Google", AP_WK, "ng", -61, 7), ("Robotstofzuiger", "Roborock", AP_WK, "ng", -66, 9),
    ("Galaxy S24", "Samsung", AP_BV, "na", -58, 5), ("Kindle", "Amazon", AP_BV, "ng", -66, 8),
    ("Apple TV Boven", "Apple", AP_BV, "na", -55, 3), ("Shelly Plug Schuur", "Shelly", AP_SC, "ng", -69, 11),
    ("Shelly 1PM Tuin", "Shelly", AP_SC, "ng", -75, 17), ("Hue Bridge Gast", "Signify", AP_BV, "ng", -60, 5),
    ("Laptop Werk", "Dell", AP_KT, "na", -57, 4), ("Printer HP", "HP", AP_KT, "ng", -64, 9),
    ("Echo Dot Keuken", "Amazon", AP_WK, "ng", -62, 10), ("Echo Show Slaapkamer", "Amazon", AP_BV, "ng", -59, 6),
    ("Apple Watch", "Apple", AP_WK, "na", -60, 7), ("PS5", "Sony", AP_BV, "na", -56, 5),
    ("Tesla", "Tesla", AP_SC, "na", -68, 7), ("Wasmachine", "Miele", AP_BV, "ng", -66, 8),
    ("Droger", "Miele", AP_BV, "ng", -67, 8), ("Camera Tuin", "Reolink", AP_SC, "na", -68, 9),
    ("ESP Weerstation", "Espressif", AP_SC, "ng", -76, 18), ("Tado Bridge", "Tado", AP_WK, "ng", -58, 5),
    ("Pixel 8", "Google", AP_KT, "na", -61, 6), ("Switch Nintendo", "Nintendo", AP_BV, "na", -64, 8),
    ("Fire TV", "Amazon", AP_WK, "na", -57, 5), ("Garmin Edge", "Garmin", AP_SC, "ng", -67, 9),
    ("iPhone Gast", "Apple", AP_WK, "na", -59, 5), ("Bosch Vaatwasser", "Bosch", AP_WK, "ng", -64, 11),
    ("Zonnepanelen Omvormer", "SolarEdge", AP_SC, "ng", -77, 19),
]

WIRED = [  # naam, vendor, switch, poort
    ("Home Assistant", "Proxmox", SW_MK, 5), ("Proxmox Host", "Intel", SW_MK, 6), ("Kantoor-PC", "ASUS", SW_MK, 7),
    ("NAS Synology", "Synology", SW_MK, 8), ("P1 Meter", "HomeWizard", SW_MK, 9), ("Zigbee Coordinator", "SMLight", SW_MK, 10),
    ("Hue Bridge", "Signify", SW_MK, 11), ("Camera Voordeur", "UniFi", SW_MK, 12), ("Camera Oprit", "UniFi", SW_MK, 13),
    ("Sonos Port", "Sonos", SW_MK, 14), ("TV Woonkamer", "LG", SW_MK, 15), ("Apple TV Woonkamer", "Apple", SW_MK, 16),
    ("Pi-hole", "Raspberry Pi", SW_MK, 17), ("Werklaptop Dock", "Dell", SW_KT, 3), ("Monitor Kantoor", "Dell", SW_KT, 4),
    ("VoIP Telefoon", "Yealink", SW_KT, 5), ("Printer Kantoor", "Brother", SW_KT, 6), ("Laadpaal", "Alfen", SW_SC, 3),
    ("Camera Schuur", "UniFi", SW_SC, 4), ("Warmtepomp", "Daikin", SW_MK, 18), ("Doorbell Hub", "Ring", SW_MK, 19),
    ("UPS", "APC", SW_MK, 20), ("Docker Host", "Intel", SW_MK, 21), ("Mediaspeler", "Nvidia", SW_MK, 22),
]


REBOOT_T = 3 * 3600   # simulatietijd waarop AP Boven herstart
PRINTER_T = 3.5 * 3600  # simulatietijd waarop de printer naar AP Schuur zakt
CH5 = {AP_WK: 36, AP_BV: 100, AP_KT: 149, AP_SC: 44}   # AP Woonkamer en AP Schuur delen 36–48
CH24 = {AP_WK: 6, AP_BV: 1, AP_KT: 6, AP_SC: 6}       # kanaal 11 blijft vrij
AWAY = {"iPhone", "MacBook Pro", "Galaxy S24", "Laptop Werk", "Pixel 8", "Apple Watch", "Tesla"}   # overdag weg


LINK_DOWN, LINK_UP = 1000.0, 500.0   # demo-abonnement in Mbit/s


def traffic(ts: float, rnd: random.Random = R) -> tuple[float, float]:
    """Internetverkeer (bit/s) op een tijdstip: rustig 's nachts, druk 's avonds, af en toe een download."""
    import time as _t
    lt = _t.localtime(ts)
    hour = lt.tm_hour + lt.tm_min / 60
    base = 6 + 50 * max(0.0, math.sin((hour - 7) / 16 * math.pi)) + (90 if 19 <= hour < 23 else 0)
    rx = base * rnd.uniform(0.6, 1.5) + (rnd.uniform(200, 650) if rnd.random() < 0.06 else 0)
    tx = rx * rnd.uniform(0.05, 0.15) + (rnd.uniform(40, 120) if rnd.random() < 0.03 else 0)
    return rx * 1e6, tx * 1e6


class MockNetwork:
    def __init__(self) -> None:
        self.t = 0.0
        self.now = 0           # wandkloktijd, gezet door de collector
        self.speedtest_started: float | None = None
        self.speedtest_last: dict | None = None
        self.counters: dict[str, dict[str, float]] = {}
        self.flap_state = True
        self.sonos_ap = AP_WK

    # ----------------------------------------------------------------- helpers
    def _cnt(self, key: str, field: str, inc: float) -> float:
        c = self.counters.setdefault(key, {})
        c[field] = c.get(field, 0.0) + max(0.0, inc)
        return round(c[field])

    def advance(self, dt: float) -> None:
        self.t += dt
        if R.random() < dt / 180:  # ~elke 3 minuten roamt de Sonos
            self.sonos_ap = AP_BV if self.sonos_ap == AP_WK else AP_WK
        if R.random() < dt / 900:  # ~4x per uur flapt de poort
            self.flap_state = not self.flap_state
        elif not self.flap_state and R.random() < 0.6:
            self.flap_state = True

    # ----------------------------------------------------------------- devices
    def _port(self, dev: str, idx: int, dt: float, *, up=True, speed=1000, media="GE",
              poe=0.0, name=None, uplink=False, err_rate=0.0) -> dict:
        key = f"{dev}:{idx}"
        traffic = R.uniform(2e5, 8e6) * dt if up else 0
        return {
            "port_idx": idx, "name": name or f"Port {idx}", "up": up, "speed": speed if up else 0,
            "full_duplex": True, "media": media, "poe_power": f"{poe:.2f}", "is_uplink": uplink,
            "rx_errors": self._cnt(key, "rxe", err_rate * dt * R.uniform(0.6, 1.4)),
            "tx_errors": 0,
            "rx_dropped": self._cnt(key, "rxd", R.uniform(0, 0.002) * dt),
            "tx_dropped": 0,
            "rx_bytes": self._cnt(key, "rxb", traffic), "tx_bytes": self._cnt(key, "txb", traffic * 0.6),
        }

    def _switch_ports(self, dev: str, count: int, dt: float) -> list[dict]:
        wired = {p: n for n, _v, s, p in WIRED if s == dev}
        aps = {APS[a]["uplink"][1]: APS[a]["name"] for a in APS if APS[a]["uplink"][0] == dev}
        ports = []
        for i in range(1, count + 1):
            name = wired.get(i) or aps.get(i)
            up = name is not None or i == 1
            kw: dict = {"name": name or ("Uplink" if i == 1 else None), "up": up, "uplink": i == 1}
            if i in aps:
                kw["poe"] = R.uniform(9, 14)
            if dev == SW_MK and i == 7:
                kw["err_rate"] = 0.07                     # ~250 fouten per uur
            if dev == SW_MK and i in (12, 13):
                kw["poe"] = R.uniform(4, 6)
            if dev == SW_KT:
                kw["poe"] = (R.uniform(9, 12) if i in aps else R.uniform(7.5, 9.5)) if up and i != 1 else 0
            if dev == SW_KT and i == 3:
                kw["speed"] = 100                          # zou 1 Gbit moeten zijn
            if dev == SW_SC and i == 4:
                kw["up"] = self.flap_state
            if dev == SW_MK and i > count - 2:
                kw.update(media="SFP+", speed=10000 if i == count else 0, up=i == count,
                          name="Uplink UXG" if i == count else None, uplink=i == count)
            ports.append(self._port(dev, i, dt, **kw))
        return ports

    def _radio_stats(self, ap: str, dt: float, clients: list[dict]) -> tuple[list, list]:
        table, stats = [], []
        for name, radio, ch, ht in (("wifi0", "ng", CH24[ap], 20), ("wifi1", "na", CH5[ap], 80)):
            on = [c for c in clients if c.get("ap_mac") == ap and c.get("radio") == radio]
            cu_self = 5 + 1.5 * len(on) + R.uniform(-2, 2)
            other = R.uniform(8, 18)
            if ap == AP_WK and radio == "ng":
                other = 52 + 10 * math.sin(self.t / 2400) + R.uniform(-4, 4)
            cu_total = min(100, cu_self + other)
            sat = sum(c["satisfaction"] for c in on) / len(on) if on else 100
            retry = 0.04 + (0.10 if (ap == AP_WK and radio == "ng") else 0) + (0.12 if ap == AP_SC and radio == "ng" else 0)
            pkts = R.uniform(300, 900) * dt * max(1, len(on))
            key = f"{ap}:{radio}"
            table.append({"name": name, "radio": radio, "channel": ch if radio == "ng" else "auto", "ht": ht,
                          "tx_power_mode": "auto", "min_rssi_enabled": False})
            stats.append({
                "name": name, "radio": radio, "channel": ch, "num_sta": len(on), "satisfaction": round(sat),
                "cu_total": round(cu_total), "cu_self_rx": round(cu_self * 0.6), "cu_self_tx": round(cu_self * 0.4),
                "tx_power": 20 if radio == "ng" else 23,
                "tx_packets": self._cnt(key, "pk", pkts), "tx_retries": self._cnt(key, "rt", pkts * retry * R.uniform(0.8, 1.2)),
            })
        return table, stats

    # --------------------------------------------------------------------- api
    def stat_sta(self, dt: float) -> list[dict]:
        out = []
        for i, (name, vendor, ap, radio, sig, retry) in enumerate(WIRELESS):
            mac = _mac(0x100 + i)
            if name == "Sonos Keuken":
                ap = self.sonos_ap
            assoc = self.now - int(self.t + 3600 * (i % 7 + 1))
            if name == "Kindle" and self.t >= REBOOT_T + 30:   # blijft hangen na herstart AP Boven
                ap, sig, retry = AP_SC, -80, 14
                assoc = int(self.now - (self.t - REBOOT_T) + 40)
            if name == "Printer HP" and self.t >= PRINTER_T:     # zakt weg naar een verre AP, zonder herstart
                ap, sig, retry = AP_SC, -78, 15
                assoc = int(self.now - (self.t - PRINTER_T))
            s = sig + R.uniform(-3, 3)
            if name == "Ring Deurbel":
                s += 2 * math.sin(self.t / 1800)
            rpct = max(0.5, retry + R.uniform(-2, 2))
            pkts = R.uniform(20, 400) * dt
            sat = max(5, min(100, 100 - (max(0, -s - 60) * 2.0) - rpct * 0.7 + R.uniform(-3, 3)))
            rate = max(6.5, min(1200, 2.2 ** ((s + 95) / 5)) if radio == "na" else min(144, 2.2 ** ((s + 95) / 6.5))) * 1000
            out.append({
                "mac": mac, "name": name, "hostname": name.lower().replace(" ", "-"), "oui": vendor,
                "ip": f"192.168.1.{100 + i}", "is_wired": False, "network": "Default", "essid": "Thuis",
                "ap_mac": ap, "radio": radio, "channel": CH24[ap] if radio == "ng" else CH5[ap],
                "radio_proto": "ax" if radio == "na" else "n", "signal": round(s), "noise": -95,
                "satisfaction": round(sat), "tx_rate": round(rate), "rx_rate": round(rate * 0.8),
                "tx_packets": self._cnt(mac, "pk", pkts), "tx_retries": self._cnt(mac, "rt", pkts * rpct / 100),
                "uptime": int(self.t + 3600 * (i % 7 + 1)), "latest_assoc_time": assoc,
            })
        for i, (name, vendor, sw, port) in enumerate(WIRED):
            out.append({
                "mac": _mac(0x200 + i), "name": name, "hostname": name.lower().replace(" ", "-"), "oui": vendor,
                "ip": f"192.168.1.{10 + i}", "is_wired": True, "network": "Default", "sw_mac": sw, "sw_port": port,
                "satisfaction": 100, "uptime": int(self.t + 86400 * (i % 5 + 1)),
            })
        return out

    def stat_device(self, dt: float, sta: list[dict]) -> list[dict]:
        uptime_base = 86400 * 12 + self.t
        devs = []
        lat = 9 + R.uniform(-2, 3) + (R.uniform(90, 160) if R.random() < 0.04 else 0)
        rx, tx = traffic(self.now or 0)
        wan1 = {"is_uplink": True, "up": True, "speed": 1000, "rx_bytes-r": rx / 8, "tx_bytes-r": tx / 8,
                "rx_bytes": self._cnt("wan", "rx", rx / 8 * dt), "tx_bytes": self._cnt("wan", "tx", tx / 8 * dt)}
        devs.append({
            "wan1": wan1, "speedtest-status": self.speedtest_status(self.now or 0),
            "mac": GW, "name": "UXG", "model": "UXGMAX", "model_name": "UXG Max", "type": "uxg", "state": 1,
            "version": "4.1.13", "upgradable": False, "uptime": uptime_base, "ip": "192.168.1.1",
            "system-stats": {"cpu": f"{R.uniform(8, 22):.1f}", "mem": f"{R.uniform(48, 55):.1f}"},
            "general_temperature": round(R.uniform(52, 58), 1), "num_sta": len(sta),
            "uptime_stats": {"WAN": {"availability": 100 - (R.uniform(0.5, 3) if lat > 60 else 0), "latency_average": round(lat)}},
            "port_table": [self._port(GW, 1, dt, name="WAN", uplink=True), self._port(GW, 2, dt, media="SFP+", speed=10000, name="LAN")],
        })
        for mac, name, model, mname, nports, budget in (
            (SW_MK, "Switch Meterkast", "USL24PB", "USW Pro 24 PoE", 26, 400),
            (SW_KT, "Switch Kantoor", "USL8LP", "USW Lite 8 PoE", 8, 52),
            (SW_SC, "Switch Schuur", "USMINI", "USW Flex Mini", 5, None),
        ):
            ports = self._switch_ports(mac, nports, dt)
            num = sum(1 for c in sta if c.get("sw_mac") == mac)
            d = {
                "mac": mac, "name": name, "model": model, "model_name": mname, "type": "usw", "state": 1,
                "version": "7.1.26", "upgradable": False, "uptime": uptime_base - 3600 * (2 if mac == SW_SC else 40),
                "ip": f"192.168.1.{2 + [SW_MK, SW_KT, SW_SC].index(mac)}",
                "system-stats": {"cpu": f"{R.uniform(3, 15):.1f}", "mem": f"{R.uniform(30, 45):.1f}"},
                "general_temperature": round(R.uniform(40, 48), 1) if mac == SW_MK else None,
                "num_sta": num, "port_table": ports,
                "uplink": {"uplink_mac": GW if mac == SW_MK else SW_MK, "uplink_remote_port": 2 if mac == SW_MK else {SW_KT: 23, SW_SC: 24}[mac], "type": "wire"},
            }
            if budget:
                d["total_max_power"] = budget
            devs.append(d)
        for mac, info in APS.items():
            table, stats = self._radio_stats(mac, dt, sta)
            on = [c for c in sta if c.get("ap_mac") == mac]
            devs.append({
                "mac": mac, "name": info["name"], "model": info["model"], "model_name": info["model_name"], "type": "uap",
                "state": 1, "version": "6.6.77" if mac != AP_KT else "6.5.62",
                "upgradable": mac == AP_KT, "upgrade_to_firmware": "6.6.77" if mac == AP_KT else "",
                "uptime": (self.t - REBOOT_T + 5) if (mac == AP_BV and self.t >= REBOOT_T) else uptime_base - 7200 * list(APS).index(mac),
                "ip": f"192.168.1.{20 + list(APS).index(mac)}",
                "system-stats": {"cpu": f"{R.uniform(4, 18):.1f}", "mem": f"{R.uniform(40, 60):.1f}"},
                "num_sta": len(on), "satisfaction": round(sum(c["satisfaction"] for c in on) / len(on)) if on else 100,
                "radio_table": table, "radio_table_stats": stats,
                "bandsteering_mode": "off" if mac == AP_SC else "prefer_5g",
                "uplink": {"uplink_mac": info["uplink"][0], "uplink_remote_port": info["uplink"][1], "type": "wire"},
                "port_table": [self._port(mac, 1, dt, name="Uplink", uplink=True)],
            })
        return devs

    def stat_health(self, devs: list[dict]) -> list[dict]:
        gw = devs[0]["uptime_stats"]["WAN"]
        return [
            {"subsystem": "www", "status": "ok", "latency": gw["latency_average"], "xput_down": 921.4, "xput_up": 462.3},
            {"subsystem": "wan", "status": "ok", "wan_ip": "203.0.113.24", "isp_name": "Glasvezel NL"},
        ]

    # ------------------------------------------------------------------ IPS
    EXT_SIGS = [
        ("ET SCAN Suspicious inbound to mySQL port 3306", 2010937, "emerging-scan", 3306),
        ("ET WEB_SERVER Possible CVE-2021-41773 Path Traversal Attempt", 2034125, "emerging-web_server", 443),
        ("ET SCAN Nikto Web App Scan in Progress", 2002677, "emerging-scan", 443),
        ("ET SCAN Potential VNC Scan 5900-5920", 2002911, "emerging-scan", 5901),
        ("ET CINS Active Threat Intelligence Poor Reputation IP group 42", 2403341, "ciarmy", 443),
        ("ET DROP Dshield Block Listed Source group 1", 2402000, "dshield", 22),
        ("ET SCAN MS Terminal Server Traffic on Non-standard Port", 2023753, "emerging-scan", 3390),
    ]

    ATTACKERS = [f"198.51.100.{i}" for i in (7, 23, 61, 88, 140)] + [f"203.0.113.{i}" for i in (9, 45, 200)]

    def ips_flows(self, ts: int, dt: float) -> list[dict]:
        """Flows in hetzelfde formaat als /v2/api/site/<site>/traffic-flows."""
        out = []
        n_ext = sum(1 for _ in range(int(max(1, dt // 60))) if R.random() < 0.12)   # ~7 per uur
        for k in range(n_ext):
            sig, sid, cat, port = R.choice(self.EXT_SIGS)
            src = R.choice(self.ATTACKERS)
            out.append(self._flow(ts - k, src, None, "WAN", "203.0.113.24", None, port, sig, sid, cat, "high"))
        if int(self.t) % 5400 < dt:   # eigen apparaat, elke 90 minuten
            out.append(self._flow(ts, "192.168.1.115", "Printer HP", "Default", "192.168.1.1", "UXG", 161,
                                  "GPL SNMP public access udp", 2101411, "emerging-snmp", "medium", proto="UDP"))
        return out

    @staticmethod
    def _flow(ts, src, sname, snet, dst, dname, port, sig, sid, cat, risk, proto="TCP") -> dict:
        return {
            "id": f"mock-{ts}-{src}-{port}-{sid}", "action": "blocked", "risk": risk, "protocol": proto,
            "flow_start_time": ts * 1000, "in": {"network_name": snet}, "out": {"network_name": "Default"},
            "source": {"ip": src, "client_name": sname, "country": None if sname else "ZZ"},
            "destination": {"ip": dst, "port": port, "client_name": dname},
            "ips": {"signature": sig, "signature_id": sid, "category_name": cat,
                    "alarm_category_potential_risk": "Demodata"},
        }

    # ------------------------------------------------------------ instellingen
    @staticmethod
    def config() -> tuple[list, list, list]:
        """Ruwe rest/wlanconf, rest/setting en stat/portforward."""
        wlans = [
            {"name": "Thuis", "enabled": True, "wlan_bands": ["2g", "5g"], "fast_roaming_enabled": False,
             "bss_transition": True, "minrate_ng_enabled": True, "minrate_ng_data_rate_kbps": 1000},
            {"name": "Thuis-IoT", "enabled": True, "wlan_bands": ["2g"], "enhanced_iot": True, "fast_roaming_enabled": False,
             "minrate_ng_enabled": True, "minrate_ng_data_rate_kbps": 1000},
            {"name": "Thuis-Gast", "enabled": True, "wlan_bands": ["2g", "5g"], "is_guest": True, "fast_roaming_enabled": False},
        ]
        settings = [{"key": "usg", "upnp_enabled": True, "upnp_secure_mode": True}]
        forwards = [
            {"name": "Home Assistant", "enabled": True, "proto": "tcp", "dst_port": "443", "fwd": "192.168.1.10",
             "fwd_port": "8123", "src": "any", "rx_bytes": 48_211_904},
            {"name": "NAS SSH", "enabled": True, "proto": "tcp", "dst_port": "22", "fwd": "192.168.1.13",
             "fwd_port": "22", "src": "any", "rx_bytes": 1_204_332},
            {"name": "Oude camera", "enabled": False, "proto": "tcp", "dst_port": "8080", "fwd": "192.168.1.30",
             "fwd_port": "80", "src": "any", "rx_bytes": 0},
            {"name": "PS5", "enabled": True, "is_upnp": 1, "proto": "udp", "dst_port": "3074", "fwd": "192.168.1.119",
             "fwd_port": "3074", "rx_bytes": 3_400_112},
            {"name": "Camera Tuin", "enabled": True, "is_upnp": 1, "proto": "tcp", "dst_port": "80", "fwd": "192.168.1.123",
             "fwd_port": "80", "rx_bytes": 92_118},
        ]
        return wlans, settings, forwards

    # ------------------------------------------------------------ historie
    def backfill(self, db, start: int, end: int, step: int = 300) -> None:
        """Grove historie (elke 5 min) voor de patronen: wie is wanneer thuis en wanneer is het druk."""
        import time as _t
        rnd = random.Random(7)
        cli, rad, wan = [], [], []
        band = {"ng": "2.4", "na": "5"}
        for ts in range(start, end, step):
            lt = _t.localtime(ts)
            weekday, hour = lt.tm_wday < 5, lt.tm_hour + lt.tm_min / 60
            evening = 1.0 if 18 <= hour < 23 else 0.4 if 7 <= hour < 18 else 0.1
            wan.append((ts, 1, 9 + rnd.uniform(-2, 3) + (30 * evening if rnd.random() < 0.03 else 0), 0, *traffic(ts, rnd)))
            per_ap: dict[tuple, int] = {}
            for i, (name, _v, ap, radio, sig, retry) in enumerate(WIRELESS):
                if name in AWAY and weekday and 8.5 <= hour < 17.5:
                    continue
                if name == "iPhone Gast" and weekday:
                    continue
                if name == "Sonos Keuken" and rnd.random() < 0.3:
                    ap = AP_BV
                per_ap[(ap, radio)] = per_ap.get((ap, radio), 0) + 1
                cli.append((ts, _mac(0x100 + i), ap, band[radio], round(sig + rnd.uniform(-3, 3)),
                            round(max(5, 100 - max(0, -sig - 60) * 2 - retry * 0.7)), max(0.5, retry + rnd.uniform(-2, 2)), None))
            for i, (_n, _v, _s, _p) in enumerate(WIRED):
                cli.append((ts, _mac(0x200 + i), None, None, None, 100, None, None))
            for ap in APS:
                for radio in ("ng", "na"):
                    n = per_ap.get((ap, radio), 0)
                    own = 4 + 1.5 * n * (0.5 + evening)
                    other = (48 + 14 * evening if ap == AP_WK and radio == "ng" else 8 + 8 * evening) + rnd.uniform(-3, 3)
                    rad.append((ts, ap, band[radio], CH24[ap] if radio == "ng" else CH5[ap], min(100, own + other),
                                other, n, 95, 4 + rnd.uniform(0, 3)))
        db.store_rows("client_samples", cli)
        db.store_rows("radio_samples", rad)
        db.store_rows("wan_samples", wan)

    # ----------------------------------------------------------- speedtest
    TEST_PHASES = (("ping", 3), ("download", 12), ("upload", 12))

    def start_speedtest(self, now: float) -> None:
        self.speedtest_started = now

    def speedtest_status(self, now: float) -> dict:
        """Zelfde velden als 'speedtest-status' op een echte gateway."""
        st = {"status_ping": 0, "status_download": 0, "status_upload": 0, "status_summary": 0}
        if self.speedtest_started is not None:
            el, t0 = now - self.speedtest_started, 0
            for name, length in self.TEST_PHASES:
                if el < t0 + length:
                    st[f"status_{name}"] = 1
                    st["status_summary"] = 1
                    break
                st[f"status_{name}"] = 2
                t0 += length
            else:
                rnd = random.Random(int(self.speedtest_started))
                self.speedtest_last = {"rundate": int(self.speedtest_started + t0),
                                       "xput_download": round(LINK_DOWN * rnd.uniform(0.88, 0.95), 1),
                                       "xput_upload": round(LINK_UP * rnd.uniform(0.9, 0.97), 1), "latency": rnd.randint(4, 8)}
                self.speedtest_started = None
                st["status_summary"] = 2
        return {**st, **(self.speedtest_last or {"rundate": 0, "xput_download": 0, "xput_upload": 0, "latency": 0})}

    def speedtest_history(self, now: int, days: int = 30) -> list[dict]:
        """Archief zoals stat/report/archive.speedtest: elke nacht een test, één keer een slechte."""
        rnd, out = random.Random(11), []
        for d in range(days, 0, -1):
            ts = now - d * 86400 - (now % 86400) + 3 * 3600 + rnd.randint(0, 1800)
            bad = d == 9
            out.append({"time": ts * 1000, "xput_download": round(LINK_DOWN * (rnd.uniform(0.35, 0.45) if bad else rnd.uniform(0.86, 0.96)), 1),
                        "xput_upload": round(LINK_UP * rnd.uniform(0.88, 0.97), 1), "latency": rnd.randint(4, 9) + (25 if bad else 0),
                        "server": {"city": "Amsterdam", "provider": "Demo"}})
        if self.speedtest_last:
            out.append({"time": self.speedtest_last["rundate"] * 1000, **{k: self.speedtest_last[k] for k in ("xput_download", "xput_upload", "latency")},
                        "server": {"city": "Amsterdam", "provider": "Demo"}})
        return out

    def snapshot(self, dt: float) -> tuple[list, list, list]:
        self.advance(dt)
        sta = self.stat_sta(dt)
        devs = self.stat_device(dt, sta)
        return devs, sta, self.stat_health(devs)
