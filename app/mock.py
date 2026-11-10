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
import time

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

# Deze slimme apparaten staan in de demo al op het aparte IoT-netwerk; de rest van de slimme apparaten
# (ESP Weerstation, Camera Tuin, P1 Meter) nog niet, zodat de segmentatie-check iets te melden heeft.
IOT_CLIENTS = {"Ring Deurbel", "Nest Thermostaat", "Robotstofzuiger", "Shelly Plug Schuur", "Shelly 1PM Tuin",
               "Hue Bridge Gast", "Echo Dot Keuken", "Echo Show Slaapkamer", "Wasmachine", "Droger", "Tado Bridge",
               "Bosch Vaatwasser", "Zonnepanelen Omvormer", "Hue Bridge", "Warmtepomp", "Laadpaal", "Doorbell Hub"}


def _cip(name: str, i: int, wired: bool) -> str:
    return f"192.168.{20 if name in IOT_CLIENTS else 1}.{(10 if wired else 100) + i}"


# Wie praat met welk land: (apparaat, domein, land, poort, dienst, typische grootte in bytes)
FLOW_DEST = [
    ("TV Woonkamer", "nflxvideo.net", "NL", 443, "HTTPS", 180_000_000), ("Apple TV Boven", "youtube.com", "NL", 443, "HTTPS", 90_000_000),
    ("Mediaspeler", "nflxvideo.net", "NL", 443, "HTTPS", 120_000_000), ("Fire TV", "primevideo.com", "IE", 443, "HTTPS", 60_000_000),
    ("iPhone", "icloud.com", "US", 443, "HTTPS", 2_000_000), ("iPhone", "whatsapp.net", "DE", 443, "HTTPS", 400_000),
    ("iPhone", "spotify.com", "SE", 443, "HTTPS", 6_000_000), ("MacBook Pro", "github.com", "US", 443, "HTTPS", 1_500_000),
    ("MacBook Pro", "apple.com", "NL", 443, "HTTPS", 3_000_000), ("Galaxy S24", "googleapis.com", "NL", 443, "HTTPS", 900_000),
    ("Galaxy S24", "instagram.com", "IE", 443, "HTTPS", 8_000_000), ("Laptop Werk", "teams.microsoft.com", "IE", 443, "HTTPS", 12_000_000),
    ("Laptop Werk", "outlook.office365.com", "NL", 443, "HTTPS", 900_000), ("Kantoor-PC", "zoom.us", "US", 8801, "OTHER", 15_000_000),
    ("Kantoor-PC", "nu.nl", "NL", 443, "HTTPS", 1_200_000), ("iPad Keuken", "bol.com", "NL", 443, "HTTPS", 800_000),
    ("PS5", "playstation.net", "US", 443, "HTTPS", 40_000_000), ("Switch Nintendo", "nintendo.net", "JP", 443, "HTTPS", 2_000_000),
    ("Sonos Keuken", "sonos.com", "US", 443, "HTTPS", 120_000), ("Sonos Woonkamer", "spotify.com", "SE", 443, "HTTPS", 5_000_000),
    ("Ring Deurbel", "ring.com", "US", 443, "HTTPS", 4_000_000), ("Nest Thermostaat", "nest.com", "US", 443, "HTTPS", 30_000),
    ("Echo Dot Keuken", "avs-alexa-eu.amazon.com", "IE", 443, "HTTPS", 200_000), ("Kindle", "amazon.com", "US", 443, "HTTPS", 60_000),
    ("Robotstofzuiger", "api.io.mi.com", "CN", 443, "HTTPS", 25_000), ("Shelly Plug Schuur", "shelly.cloud", "DE", 6022, "OTHER", 8_000),
    ("Tado Bridge", "tado.com", "DE", 443, "HTTPS", 15_000), ("Zonnepanelen Omvormer", "solaredge.com", "IL", 443, "HTTPS", 40_000),
    ("Garmin Edge", "garmin.com", "US", 443, "HTTPS", 300_000), ("Tesla", "tesla.com", "US", 443, "HTTPS", 1_000_000),
    ("Bosch Vaatwasser", "home-connect.com", "DE", 443, "HTTPS", 20_000), ("NAS Synology", "backblazeb2.com", "US", 443, "HTTPS", 300_000_000),
    ("Docker Host", "docker.io", "US", 443, "HTTPS", 50_000_000), ("Proxmox Host", "download.proxmox.com", "AT", 443, "HTTPS", 20_000_000),
    ("Home Assistant", "nabucasa.com", "DE", 443, "HTTPS", 200_000), ("Pi-hole", "cloudflare-dns.com", "NL", 853, "DNS", 40_000),
    ("ESP Weerstation", "openweathermap.org", "GB", 443, "HTTPS", 5_000),
    ("Galaxy S24", "tiktokcdn.com", "SG", 443, "HTTPS", 20_000_000), ("Kantoor-PC", "alicdn.com", "HK", 443, "HTTPS", 900_000), ("Warmtepomp", "daikineurope.com", "BE", 443, "HTTPS", 30_000),
]
NAMELESS = {"Robotstofzuiger", "Shelly Plug Schuur", "Tado Bridge", "Zonnepanelen Omvormer", "ESP Weerstation", "Warmtepomp", "Docker Host"}
# zonder naam in UniFi (hostnaam, fabrikant): de apparaatherkenning laat zien wat het zijn
UNNAMED = {"Tado Bridge": (None, "Tado GmbH"), "Bosch Vaatwasser": ("lwip0", "BSH Hausgeräte GmbH"),
           "Warmtepomp": ("espressif", "Espressif Inc.")}
FLOW_IN = [  # (apparaat, poort, dienst, land, grootte)
    ("Home Assistant", 8123, "HTTPS", "NL", 900_000), ("Home Assistant", 8123, "HTTPS", "ES", 600_000),
    ("NAS Synology", 22, "SSH", "CN", 4_000), ("NAS Synology", 22, "SSH", "US", 4_000), ("NAS Synology", 22, "SSH", "BR", 3_000),
    ("NAS Synology", 22, "SSH", "VN", 3_000),
]
ATTACKER_CC = {"198.51.100.7": "RU", "198.51.100.23": "CN", "198.51.100.61": "US", "198.51.100.88": "BR",
               "198.51.100.140": "NL", "203.0.113.9": "IN", "203.0.113.45": "KR", "203.0.113.200": "DE"}

NEWDEV_T = 5 * 3600   # simulatietijd waarop een onbekende tablet opduikt
CHANGE_T = 5.5 * 3600  # simulatietijd waarop er instellingen veranderen (voor het wijzigingslog)
ROTATE_T = 4.5 * 3600  # simulatietijd waarop de iPad Keuken een nieuw privé-adres krijgt
REBOOT_T = 3 * 3600   # simulatietijd waarop AP Boven herstart
PRINTER_T = 3.5 * 3600  # simulatietijd waarop de printer naar AP Schuur zakt
CH5 = {AP_WK: 36, AP_BV: 100, AP_KT: 149, AP_SC: 44}   # AP Woonkamer en AP Schuur delen 36–48
CH24 = {AP_WK: 6, AP_BV: 1, AP_KT: 6, AP_SC: 6}       # kanaal 11 blijft vrij
DNS_LEAKS = [   # (apparaat, adres, poort, dienst, domein): DNS buiten je eigen DNS-server om
    ("Fire TV", "8.8.8.8", 53, "DNS", None), ("Tesla", "1.1.1.1", 853, "DNS_OVER_TLS", "one.one.one.one"),
    ("Nest Thermostaat", "8.8.4.4", 443, "HTTPS", "dns.google"),
]
BLOCK_DEMO_RULE = "Geen eigen DNS (IoT)"
DEMO_AUDIT_RULES = [
    {"_id": "p-audit-1", "name": "Blokkeer IoT-camera", "action": "BLOCK", "enabled": True, "index": 10010, "predefined": False,
     "protocol": "all", "connection_state_type": "ALL", "source": {"zone_id": "z-int", "matching_target": "ANY"},
     "destination": {"zone_id": "z-iot", "matching_target": "IP", "ips": ["192.168.20.50"], "port_matching_type": "ANY"}},
    {"_id": "p-audit-2", "name": "Tablet IoT tijdelijk", "action": "ALLOW", "enabled": True, "index": 10050, "predefined": False,
     "protocol": "all", "connection_state_type": "ALL", "source": {"zone_id": "z-iot", "matching_target": "IP", "ips": ["192.168.20.50"]},
     "destination": {"zone_id": "z-int", "matching_target": "ANY", "port_matching_type": "ANY"}},
    {"_id": "p-audit-3", "name": BLOCK_DEMO_RULE, "description": "Slimme apparaten gebruiken alleen de DNS-server van het eigen netwerk.",
     "action": "BLOCK", "enabled": True, "index": 10060, "predefined": False, "protocol": "tcp", "connection_state_type": "ALL",
     "source": {"zone_id": "z-iot", "matching_target": "ANY"},
     "destination": {"zone_id": "z-ext", "matching_target": "ANY", "port_matching_type": "SPECIFIC", "port": "853"}},
]
NEIGHBOR_SSIDS = ["Ziggo-5G", "KPN-WiFi-2E4A", "H369A1B2C", "FRITZ!Box 7590 XL", "Odido-Thuis", "Buren", "TV-Kast", "Ziggo1234567"]
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
        self.blocked: set[str] = set()   # gepauzeerde apparaten: verschijnen niet meer als client
        self.names: dict[str, str] = {}   # namen die je in Sonar gaf (in het echt: in UniFi)

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
        wireless = list(WIRELESS)
        if self.t >= NEWDEV_T:
            wireless.append(("Galaxy-Tab-S9", "Samsung Electronics", AP_WK, "na", -58, 4))
        for i, (name, vendor, ap, radio, sig, retry) in enumerate(wireless):
            mac = _mac(0x100 + i) if i < len(WIRELESS) else "a4:6c:f1:3e:90:2b"
            if name == "iPad Keuken":   # privé-wifiadres dat wisselt
                mac = "ba:5e:c0:00:01:0a" if self.t < ROTATE_T else "be:12:7a:00:02:0a"
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
                "ip": _cip(name, i, False), "is_wired": False, "network": "IoT" if name in IOT_CLIENTS else "Default",
                "essid": "Thuis-IoT" if name in IOT_CLIENTS and radio == "ng" else "Thuis",
                "ap_mac": ap, "radio": radio, "channel": CH24[ap] if radio == "ng" else CH5[ap],
                "radio_proto": "ax" if radio == "na" else "n", "signal": round(s), "noise": -95,
                "satisfaction": round(sat), "tx_rate": round(rate), "rx_rate": round(rate * 0.8),
                "tx_packets": self._cnt(mac, "pk", pkts), "tx_retries": self._cnt(mac, "rt", pkts * rpct / 100),
                "uptime": int(self.t + 3600 * (i % 7 + 1)), "latest_assoc_time": assoc,
            })
        for i, (name, vendor, sw, port) in enumerate(WIRED):
            out.append({
                "mac": _mac(0x200 + i), "name": name, "hostname": name.lower().replace(" ", "-"), "oui": vendor,
                "ip": _cip(name, i, True), "is_wired": True, "network": "IoT" if name in IOT_CLIENTS else "Default",
                "sw_mac": sw, "sw_port": port,
                "satisfaction": 100, "uptime": int(self.t + 86400 * (i % 5 + 1)),
            })
        for c in out:
            raw = UNNAMED.get(c["name"])
            if raw:   # UniFi kent geen naam: alleen een nietszeggende hostnaam en de fabrikant
                c["hostname"], c["oui"] = raw
                del c["name"]
            if c["mac"] in self.names:
                c["name"] = self.names[c["mac"]]
        return [c for c in out if c["mac"] not in self.blocked]

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
                "uplink": {"uplink_mac": GW if mac == SW_MK else SW_MK, "uplink_remote_port": 2 if mac == SW_MK else {SW_KT: 23, SW_SC: 24}[mac], "type": "wire", "speed": 1000},
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
                "uplink": {"uplink_mac": info["uplink"][0], "uplink_remote_port": info["uplink"][1], "type": "wire", "speed": 1000},
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

    def flows(self, ts: int, dt: float, rnd: random.Random | None = None) -> list[dict]:
        """Verbindingen in het formaat van /v2/api/site/<site>/traffic-flows (zonder IPS)."""
        rnd = rnd or R
        hour = time.localtime(ts).tm_hour
        busy = 1.0 if 18 <= hour < 23 else 0.6 if 7 <= hour < 18 else 0.25
        names = {n: (_mac(0x100 + i), _cip(n, i, False)) for i, (n, *_r) in enumerate(WIRELESS)}
        names.update({n: (_mac(0x200 + i), _cip(n, i, True)) for i, (n, *_r) in enumerate(WIRED)})
        out = []
        for k in range(max(1, int(dt / 60 * 22 * busy))):
            who, domain, cc, port, svc, size = rnd.choice(FLOW_DEST)
            if who not in names:
                continue
            mac, ip = names[who]
            b = int(size * 0.12 * rnd.lognormvariate(0, 1.1))
            t_end = ts - rnd.randint(0, int(dt))
            ext = f"203.0.113.{rnd.randint(1, 250)}"   # documentatie-adressen
            nameless = who in NAMELESS     # UniFi weet niet altijd de naam; AdGuard vult die dan aan
            if nameless:
                from .mock_adguard import demo_ip
                ext = demo_ip(domain)
            out.append({"id": f"mockf-{t_end}-{k}-{mac}", "action": "allowed", "direction": "outgoing", "protocol": "TCP",
                        "flow_start_time": (t_end - rnd.randint(1, 300)) * 1000, "flow_end_time": t_end * 1000,
                        "in": {"network_name": "Default"}, "out": {"network_name": "WAN"}, "service": svc, "risk": "low",
                        "source": {"ip": ip, "mac": mac, "client_name": who, "port": rnd.randint(30000, 60000)},
                        "destination": {"ip": ext, "port": port, "domains": [] if nameless else [domain], "region": cc},
                        "traffic_data": {"bytes_tx": int(b * 0.08), "bytes_rx": int(b * 0.92)}})
        for who, ip_, port, svc, dom in DNS_LEAKS:   # apparaten die om je eigen DNS-server heen gaan
            if rnd.random() < dt / 600 and who in names:
                mac, ip = names[who]
                t_end = ts - rnd.randint(0, int(dt))
                out.append({"id": f"mockdns-{t_end}-{mac}", "action": "allowed", "direction": "outgoing",
                            "protocol": "UDP" if port == 53 else "TCP", "flow_start_time": (t_end - 2) * 1000,
                            "flow_end_time": t_end * 1000, "in": {"network_name": "Default"}, "out": {"network_name": "WAN"},
                            "service": svc, "risk": "low", "source": {"ip": ip, "mac": mac, "client_name": who, "port": 41000},
                            "destination": {"ip": ip_, "port": port, "domains": [dom] if dom else [], "region": "US"},
                            "traffic_data": {"bytes_tx": 120, "bytes_rx": 260}})
            if rnd.random() < dt / 300 and who in names:   # dezelfde poging, maar nu tegengehouden door een firewallregel
                mac, ip = names[who]
                out.append({"id": f"mockdnsb-{ts}-{mac}", "action": "blocked", "direction": "outgoing", "protocol": "TCP",
                            "flow_end_time": ts * 1000, "in": {"network_name": "IoT"}, "out": {"network_name": "WAN"},
                            "service": "DNS_OVER_TLS", "risk": "low",
                            "policies": [{"id": "p-audit-3", "type": "FIREWALL", "internal_type": "FIREWALL_POLICY", "name": BLOCK_DEMO_RULE}],
                            "source": {"ip": ip, "mac": mac, "client_name": who, "port": 41001},
                            "destination": {"ip": "203.0.113.53", "port": 853, "region": "US"},
                            "traffic_data": {"bytes_tx": 60, "bytes_rx": 0}})
        for k in range(int(dt / 60 * 2)):   # van buiten naar binnen: VPN, Home Assistant en de open SSH-poort
            host, port, svc, cc, size = rnd.choice(FLOW_IN)
            mac, ip = names[host]
            t_end = ts - rnd.randint(0, int(dt))
            src = f"198.51.100.{rnd.randint(1, 250)}"
            out.append({"id": f"mockfi-{t_end}-{k}-{port}", "action": "allowed", "direction": "incoming", "protocol": "TCP",
                        "flow_start_time": (t_end - 30) * 1000, "flow_end_time": t_end * 1000,
                        "in": {"network_name": "WAN"}, "out": {"network_name": "Default"}, "service": svc, "risk": "low",
                        "source": {"ip": src, "port": rnd.randint(30000, 60000), "region": cc},
                        "destination": {"ip": ip, "mac": mac, "client_name": host, "port": port},
                        "traffic_data": {"bytes_tx": int(size * rnd.random()), "bytes_rx": int(size * rnd.random() * 3)}})
        if rnd.random() < 0.15:   # door de regioblokkade tegengehouden
            cc, port, svc = rnd.choice((("RU", 23, "TELNET"), ("RU", 445, "MICROSOFT_DS"), ("CN", 3389, "RDP"), ("KP", 22, "SSH")))
            out.append({"id": f"mockfb-{ts}-{port}", "action": "blocked", "direction": "incoming", "protocol": "TCP",
                        "flow_end_time": ts * 1000, "service": svc, "risk": "high",
                        "policies": [{"type": "PROTECTION", "internal_type": "REGION_BLOCKING", "name": "Region Blocking"}],
                        "in": {"network_name": "WAN"}, "source": {"ip": f"198.51.100.{rnd.randint(1, 250)}", "region": cc},
                        "destination": {"ip": "203.0.113.24", "port": port},
                        "traffic_data": {"bytes_tx": 60, "bytes_rx": 0}})
        if rnd.random() < 0.5:   # tussen eigen netwerken
            out.append({"id": f"mockfl-{ts}", "action": "allowed", "direction": "local", "protocol": "UDP", "service": "DNS",
                        "flow_end_time": ts * 1000, "source": {"ip": "192.168.1.105", "client_name": "Kindle"},
                        "destination": {"ip": "192.168.1.22", "client_name": "Pi-hole", "port": 53},
                        "traffic_data": {"bytes_tx": 90, "bytes_rx": 180}})
        return out

    @staticmethod
    def _flow(ts, src, sname, snet, dst, dname, port, sig, sid, cat, risk, proto="TCP") -> dict:
        return {
            "id": f"mock-{ts}-{src}-{port}-{sid}", "action": "blocked", "risk": risk, "protocol": proto,
            "flow_start_time": ts * 1000, "in": {"network_name": snet}, "out": {"network_name": "Default"},
            "source": {"ip": src, "client_name": sname, "region": None if sname else ATTACKER_CC.get(src, "CN")},
            "destination": {"ip": dst, "port": port, "client_name": dname},
            "ips": {"signature": sig, "signature_id": sid, "category_name": cat,
                    "alarm_category_potential_risk": "Demodata"},
        }

    # ------------------------------------------------------------ instellingen
    def config_raw(self) -> dict:
        """Zoals UnifiClient.fetch_config_raw. Halverwege de demo zet iemand Fast Roaming aan en verdwijnt een oude forward."""
        wlans, settings, forwards, networks = self.config()
        if self.t >= CHANGE_T:
            wlans[0].update(fast_roaming_enabled=True, minrate_ng_data_rate_kbps=6000)
        if self.t >= CHANGE_T + 600:
            forwards = [f for f in forwards if f["name"] != "Oude camera"]
        settings = settings + [{"key": "global_switch", "stp_version": "rstp", "auto_stp_edge_detection_enabled": False}]
        zones, policies = self.firewall()
        policies = policies + DEMO_AUDIT_RULES   # voor de firewall-audit: een regel die nooit raakt en één die IoT openzet
        return {"wlans": wlans, "settings": settings, "forwards": forwards, "networks": networks,
                "zones": zones, "firewall": policies}

    @staticmethod
    def firewall() -> tuple[list, list]:
        """Zone-gebaseerde firewall zoals UniFi Network 9+ die geeft (v2 firewall/zone en firewall-policies)."""
        zones = [{"_id": "z-int", "name": "Internal", "zone_key": "internal", "network_ids": ["net-default"]},
                 {"_id": "z-ext", "name": "External", "zone_key": "external", "network_ids": ["net-wan"]},
                 {"_id": "z-gw", "name": "Gateway", "zone_key": "gateway", "network_ids": []},
                 {"_id": "z-vpn", "name": "Vpn", "zone_key": "vpn", "network_ids": ["net-wg", "net-ovpn"]},
                 {"_id": "z-hs", "name": "Hotspot", "zone_key": "hotspot", "network_ids": []},
                 {"_id": "z-dmz", "name": "Dmz", "zone_key": "dmz", "network_ids": []},
                 {"_id": "z-iot", "name": "IoT", "zone_key": None, "network_ids": ["net-iot"]}]
        allow = {"internal": lambda d: d != "z-iot", "external": lambda d: False, "gateway": lambda d: True,
                 "vpn": lambda d: d != "z-iot", "hotspot": lambda d: d == "z-ext", "dmz": lambda d: d == "z-ext",
                 None: lambda d: d in ("z-ext", "z-gw")}

        def pol(name, src, dst, action, index, predefined=False, ips=None, port=None, proto="all"):
            return {"_id": f"p-{src}-{dst}-{index}", "name": name, "action": action, "enabled": True, "index": index,
                    "predefined": predefined, "protocol": proto, "connection_state_type": "ALL",
                    "source": {"zone_id": src, "matching_target": "ANY"},
                    "destination": {"zone_id": dst, "matching_target": "IP" if ips else "ANY", "ips": ips or [],
                                    "port_matching_type": "SPECIFIC" if port else "ANY", "port": port}}
        policies = []
        for z in zones:
            for d in zones:
                if z["zone_key"] == d["zone_key"] == "gateway":
                    continue
                ok = allow[z["zone_key"]](d["_id"])
                policies.append(pol("Allow All Traffic" if ok else "Block All Traffic", z["_id"], d["_id"],
                                    "ALLOW" if ok else "BLOCK", 2147483647, predefined=True))
        policies += [pol("Internal naar IoT", "z-int", "z-iot", "ALLOW", 10000),
                     pol("IoT naar Home Assistant", "z-iot", "z-int", "ALLOW", 10000, ips=["192.168.1.10"]),
                     pol("IoT naar Pi-hole", "z-iot", "z-int", "ALLOW", 10001, ips=["192.168.1.22"], port="53", proto="tcp_udp")]
        return zones, policies

    @staticmethod
    def config() -> tuple[list, list, list, list]:
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
        networks = [
            {"_id": "net-default", "name": "Default", "purpose": "corporate", "ip_subnet": "192.168.1.1/24",
             "firewall_zone_id": "z-int", "dhcpd_dns_enabled": True, "dhcpd_dns_1": "192.168.1.22"},
            {"_id": "net-iot", "name": "IoT", "purpose": "corporate", "vlan": 20, "vlan_enabled": True,
             "ip_subnet": "192.168.20.1/24", "firewall_zone_id": "z-iot", "dhcpd_dns_enabled": True, "dhcpd_dns_1": "192.168.1.22"},
            {"_id": "net-wg", "name": "WireGuard", "purpose": "remote-user-vpn", "vpn_type": "wireguard-server", "enabled": True, "local_port": 51820},
            {"_id": "net-ovpn", "name": "OpenVPN", "purpose": "remote-user-vpn", "vpn_type": "openvpn-server", "enabled": True,
             "local_port": 1194, "vpn_protocol": "TCP"},
        ]
        return wlans, settings, forwards, networks

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

    def backups(self, now: int) -> list[dict]:
        """Nep-backups voor de demomodus (geen echte configuratie)."""
        month0 = int(time.mktime(time.localtime(now)[:2] + (1, 0, 30, 0, 0, 0, -1)))
        return [{"filename": f"autobackup_10.6.109_{time.strftime('%Y%m%d', time.localtime(month0 - i * 31 * 86400))}.unf", "time": month0 - i * 31 * 86400} for i in range(3)]

    def probe_ms(self, now: float) -> float:
        """Vertraging tijdens de test: de demolijn loopt vooral bij uploaden vol (cijfer C)."""
        phase, t0 = None, 0
        if self.speedtest_started is not None:
            el = now - self.speedtest_started
            for name, length in self.TEST_PHASES:
                if el < t0 + length:
                    phase = name
                    break
                t0 += length
        return 9 + random.uniform(0, 2) + {"download": 24, "upload": 110}.get(phase, 0) * random.uniform(0.8, 1.2)

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

    def usage_report(self, period: str, now: int) -> list[dict]:
        """Zoals stat/report/daily.site en monthly.site: ~25–45 GB per dag, in het weekend meer."""
        rnd, out = random.Random(5), []
        day0 = int(time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1)))
        days = []
        for d in range(120, -1, -1):
            ts = day0 - d * 86400
            wd = time.localtime(ts).tm_wday
            rx = rnd.uniform(18e9, 34e9) * (1.35 if wd >= 5 else 1) + (rnd.uniform(25e9, 60e9) if rnd.random() < 0.05 else 0)
            if d == 0:
                rx *= (now - day0) / 86400   # vandaag is nog bezig
            days.append((ts, rx, rx * rnd.uniform(0.08, 0.16)))
        if period == "day":
            return [{"time": ts * 1000, "wan-rx_bytes": rx, "wan-tx_bytes": tx} for ts, rx, tx in days]
        months: dict[int, list] = {}
        for ts, rx, tx in days:
            lt = time.localtime(ts)
            key = int(time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1)))
            m = months.setdefault(key, [0, 0])
            m[0] += rx
            m[1] += tx
        return [{"time": k * 1000, "wan-rx_bytes": v[0], "wan-tx_bytes": v[1]} for k, v in sorted(months.items())]

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

    # ------------------------------------------------------------ inzichten
    def insights(self, now: int) -> dict:
        """Zoals UnifiClient.insights: storingen, verbindingspogingen, anomalieën en wifi in de buurt."""
        day = 86400
        midnight = int(time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1)))
        outages = [(midnight - 20 * 60, 12 * 60), (midnight - 6 * day + 9 * 3600, 300), (midnight - 19 * day, 2 * 3600 + 300),
                   (midnight - 47 * day, 40)]   # vaste tijdstippen: dezelfde storing houdt dezelfde id
        health = []
        for d in range(90, 0, -1):
            t = now - d * day
            health.append({"ts": t, "down": any(t <= o < t + day for o, _ in outages), "loss": d in (8, 33), "lat": d in (8, 21)})
        total = sum(s for _, s in outages)
        wan = [{"wan": "WAN", "isp": "Glasvezel NL", "uptime": round(100 * (1 - total / (90 * day)), 3),
                "outages": [{"id": f"mock-out-{o}", "ts": o, "seconds": s} for o, s in outages], "health": health}]
        conn = {"2.4": {"attempts": 64, "failed": 7, "success": 89.0, "assoc": 100.0, "auth": 91.0, "dhcp": 89.0, "dns": 89.0},
                "5": {"attempts": 118, "failed": 1, "success": 99.0, "assoc": 100.0, "auth": 99.0, "dhcp": 99.0, "dns": 99.0},
                "all": {"attempts": 182, "failed": 8, "success": 95.6, "assoc": 100.0, "auth": 96.0, "dhcp": 95.6, "dns": 95.6}}
        mac = {n: _mac(0x100 + i) for i, (n, *_r) in enumerate(WIRELESS)}
        anomalies = []
        for name, kind, times in (("iPhone", "USER_HIGH_TCP_LATENCY", 3), ("Fire TV", "USER_HIGH_DNS_LATENCY", 4),
                                  ("Tesla", "USER_HIGH_TCP_PACKET_LOSS", 2), ("Ring Deurbel", "USER_SLEEPY_CLIENT", 5),
                                  ("Sonos Keuken", "USER_POOR_STREAM_EFF", 1)):
            anomalies += [{"type": kind, "mac": mac[name], "ts": now - 3600 * (k * 3 + 1)} for k in range(times)]
        rnd = random.Random(3)
        neighbors = []
        # (kanaal, aantal, sterk): alleen bij AP Woonkamer staan de buren luid op kanaal 6
        heard = {AP_WK: [(6, 6, True), (11, 1, False), (1, 2, False), (36, 2, False), (149, 1, False)],
                 AP_BV: [(1, 3, False), (6, 2, False), (100, 2, False), (36, 1, False)],
                 AP_KT: [(6, 3, False), (1, 1, False), (149, 1, False)], AP_SC: [(6, 1, False), (44, 1, False)]}
        for ap, chans in heard.items():
            for ch, n, strong in chans:
                for k in range(n):
                    band = "2.4" if ch <= 14 else "5"
                    neighbors.append({"bssid": f"02:00:{ch:02x}:{k:02x}:{list(APS).index(ap):02x}:01", "ssid": rnd.choice(NEIGHBOR_SSIDS),
                                      "ap_mac": ap, "band": band, "channel": ch, "width": 20 if band == "2.4" else 80,
                                      "signal": rnd.randint(-70, -58) if strong else rnd.randint(-90, -78), "ubnt": False,
                                      "age": 30, "security": "wpapsk"})
        return {"wan_history": wan, "wifi_connectivity": conn, "anomalies": anomalies, "neighbors": neighbors}

    def client_usage(self, period: str, now: int) -> list[dict]:
        """Zoals stat/report/hourly.user en daily.user: verkeer per apparaat (tx = download, rx = upload)."""
        rnd = random.Random(17 if period == "day" else 18)
        heavy = {"TV Woonkamer": (9e9, 0.02), "Apple TV Boven": (4e9, 0.02), "PS5": (6e9, 0.05), "MacBook Pro": (3e9, 0.3),
                 "NAS Synology": (1.5e9, 2.5), "Camera Voordeur": (0.2e9, 12), "Camera Oprit": (0.2e9, 10),
                 "Kantoor-PC": (2e9, 0.2), "iPhone": (1.2e9, 0.15), "Galaxy S24": (0.9e9, 0.15), "Laptop Werk": (1.5e9, 0.4)}
        rows = []
        step, n = (86400, 35) if period == "day" else (3600, 48)
        t0 = now - now % step
        allc = [(n_, _mac(0x100 + i)) for i, (n_, *_r) in enumerate(WIRELESS)] + [(n_, _mac(0x200 + i)) for i, (n_, *_r) in enumerate(WIRED)]
        for k in range(n, -1, -1):
            ts = t0 - k * step
            for name, mac in allc:
                base, ratio = heavy.get(name, (0.05e9, 0.2))
                down = base * rnd.lognormvariate(0, 0.5) * (step / 86400) * (1.4 if period == "hour" and 18 <= time.localtime(ts).tm_hour < 23 else 1)
                rows.append({"time": ts * 1000, "user": mac, "tx_bytes": down, "rx_bytes": down * ratio * rnd.uniform(0.6, 1.4)})
        return rows

    def dpi(self) -> list[dict]:
        """Zoals stat/stadpi by_cat (alleen met 'Traffic Identification' aan)."""
        idx = {n: _mac(0x200 + i) for i, (n, *_r) in enumerate(WIRED)} | {n: _mac(0x100 + i) for i, (n, *_r) in enumerate(WIRELESS)}
        cats = {"TV Woonkamer": {4: 8.1e9, 13: 0.4e9}, "PS5": {8: 5.2e9, 4: 0.9e9, 14: 0.3e9}, "MacBook Pro": {13: 1.1e9, 5: 0.8e9, 4: 0.6e9, 14: 0.4e9},
                "iPhone": {24: 0.5e9, 4: 0.4e9, 0: 0.1e9, 13: 0.2e9}, "Apple TV Boven": {4: 3.6e9}}
        return [{"mac": idx[n], "by_cat": [{"cat": c, "rx_bytes": b, "tx_bytes": b * 0.04} for c, b in v.items()]} for n, v in cats.items()]

    def snapshot(self, dt: float) -> tuple[list, list, list]:
        self.advance(dt)
        sta = self.stat_sta(dt)
        devs = self.stat_device(dt, sta)
        return devs, sta, self.stat_health(devs)
