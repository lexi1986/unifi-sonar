"""Naamloze apparaten herkennen: uit wat ze opzoeken (verbindingen en AdGuard), hun fabrikant en hun hostnaam
raadt Sonar wat het is, met het bewijs erbij. Alleen een voorstel: de naam zet je zelf, in UniFi."""
from __future__ import annotations

import math
import re

from .i18n import L
from .segments import client_segment

WEEK = 7 * 86400

# soort → (nl, en)
KINDS = {
    "smart": ("slim apparaat", "smart device"), "media": ("tv of speaker", "TV or speaker"), "camera": ("camera", "camera"),
    "computer": ("computer", "computer"), "phone": ("telefoon of tablet", "phone or tablet"), "server": ("server", "server"),
    "printer": ("printer", "printer"), "console": ("spelcomputer", "game console"), "car": ("auto", "car"),
    "other": ("overig", "other"),
}

# domeinen die veel soorten apparaten opzoeken: zwak bewijs naast een fabrikant met een vast MAC-adres
# (een Nest Hub en een NVIDIA Shield gebruiken ook Google Play, een server ook weleens iets van Apple)
GENERIC = {"Android-telefoon of -tablet", "Telefoon of tablet", "Apple-apparaat", "Tv of mediaspeler", "Windows-pc", "Gaming-pc"}

# (domeinen, merk, naam nl, naam en, soort). Specifiek vóór algemeen: bij gelijke score wint de eerste.
SIGNS: list[tuple[tuple[str, ...], str, str, str, str]] = [
    (("tuya.com", "tuyaeu.com", "tuyaus.com", "tuyacn.com"), "Tuya", "Tuya-stekker of -lamp", "Tuya plug or light", "smart"),
    (("shelly.cloud", "shelly.com"), "Shelly", "Shelly-schakelaar", "Shelly switch", "smart"),
    (("meethue.com",), "Philips Hue", "Hue Bridge", "Hue Bridge", "smart"),
    (("tado.com",), "tado", "tado-bridge", "tado bridge", "smart"),
    (("home-connect.com", "bsh-group.com"), "Bosch/Siemens", "Home Connect-apparaat (Bosch/Siemens)", "Home Connect appliance (Bosch/Siemens)", "smart"),
    (("daikineurope.com", "daikin.com", "daikincloud.net"), "Daikin", "Daikin-warmtepomp of -airco", "Daikin heat pump or AC", "smart"),
    (("eufylife.com", "eufy.com"), "eufy", "eufy-robot of -camera", "eufy robot or camera", "smart"),
    (("roborock.com",), "Roborock", "Roborock-robotstofzuiger", "Roborock robot vacuum", "smart"),
    (("io.mi.com", "xiaomi.com", "mi.com"), "Xiaomi", "Xiaomi-apparaat", "Xiaomi device", "smart"),
    (("ecovacs.com",), "Ecovacs", "Ecovacs-robotstofzuiger", "Ecovacs robot vacuum", "smart"),
    (("tplinkcloud.com", "tplinknbu.com", "tplinkra.com"), "TP-Link", "TP-Link Tapo/Kasa-apparaat", "TP-Link Tapo/Kasa device", "smart"),
    (("wizconnected.com", "wiz.com"), "WiZ", "WiZ-lamp", "WiZ light", "smart"),
    (("coolkit.cc", "ewelink.cc", "sonoff.tech"), "Sonoff", "Sonoff/eWeLink-schakelaar", "Sonoff/eWeLink switch", "smart"),
    (("meross.com",), "Meross", "Meross-stekker", "Meross plug", "smart"),
    (("govee.com",), "Govee", "Govee-lamp", "Govee light", "smart"),
    (("homewizard.com", "homewizard.net"), "HomeWizard", "HomeWizard-meter", "HomeWizard meter", "smart"),
    (("solaredge.com",), "SolarEdge", "SolarEdge-omvormer", "SolarEdge inverter", "smart"),
    (("enphaseenergy.com", "enlighten.enphaseenergy.com"), "Enphase", "Enphase-omvormer", "Enphase inverter", "smart"),
    (("growatt.com", "growatt.cn"), "Growatt", "Growatt-omvormer", "Growatt inverter", "smart"),
    (("samsungcloudsolution.com", "smartthings.com"), "Samsung", "Samsung SmartThings-apparaat", "Samsung SmartThings device", "smart"),
    (("miele.com", "miele.de"), "Miele", "Miele-apparaat", "Miele appliance", "smart"),
    (("nest.com",), "Google Nest", "Google Nest", "Google Nest", "smart"),
    (("avs-alexa-eu.amazon.com", "avs-alexa-na.amazon.com", "alexa.amazon.com", "amazonalexa.com"), "Amazon", "Amazon Echo", "Amazon Echo", "smart"),
    (("ring.com",), "Ring", "Ring-deurbel of -camera", "Ring doorbell or camera", "camera"),
    (("ezvizlife.com", "hik-connect.com"), "Hikvision/EZVIZ", "Hikvision/EZVIZ-camera", "Hikvision/EZVIZ camera", "camera"),
    (("reolink.com",), "Reolink", "Reolink-camera", "Reolink camera", "camera"),
    (("arlo.com", "arlo.net"), "Arlo", "Arlo-camera", "Arlo camera", "camera"),
    (("sonos.com",), "Sonos", "Sonos-speaker", "Sonos speaker", "media"),
    (("lgtvsdp.com", "lgsmartad.com", "lgappstv.com"), "LG", "LG-tv", "LG TV", "media"),
    (("samsungotn.net", "samsungcloud.tv", "samsungacr.com"), "Samsung", "Samsung-tv", "Samsung TV", "media"),
    (("fireoscaptiveportal.com", "amazonvideo.com", "primevideo.com"), "Amazon", "Fire TV", "Fire TV", "media"),
    (("heos.io", "denon.com"), "Denon/Marantz", "HEOS-speaker", "HEOS speaker", "media"),
    (("bose.io", "bose.com"), "Bose", "Bose-speaker", "Bose speaker", "media"),
    (("nflxvideo.net", "netflix.com"), "", "Tv of mediaspeler", "TV or media player", "media"),
    (("playstation.net", "playstation.com"), "Sony", "PlayStation", "PlayStation", "console"),
    (("nintendo.net", "nintendo.com"), "Nintendo", "Nintendo Switch", "Nintendo Switch", "console"),
    (("xboxlive.com",), "Microsoft", "Xbox", "Xbox", "console"),
    (("synology.com", "quickconnect.to"), "Synology", "Synology-NAS", "Synology NAS", "server"),
    (("plex.tv",), "Plex", "Plex-server", "Plex server", "server"),
    (("home-assistant.io", "nabucasa.com"), "Home Assistant", "Home Assistant", "Home Assistant", "server"),
    (("hpeprint.com", "hpsmart.com"), "HP", "HP-printer", "HP printer", "printer"),
    (("epson.net", "epsonconnect.com"), "Epson", "Epson-printer", "Epson printer", "printer"),
    (("brother.com", "brother.co.jp"), "Brother", "Brother-printer", "Brother printer", "printer"),
    (("bambulab.com",), "Bambu Lab", "Bambu Lab-3D-printer", "Bambu Lab 3D printer", "printer"),
    (("teslamotors.com", "tesla.com", "tesla.services"), "Tesla", "Tesla", "Tesla", "car"),
    (("windowsupdate.com", "msftconnecttest.com", "teams.microsoft.com"), "Microsoft", "Windows-pc", "Windows PC", "computer"),
    (("steampowered.com", "steamcontent.com"), "", "Gaming-pc", "Gaming PC", "computer"),
    (("connectivitycheck.gstatic.com", "android.clients.google.com", "play.googleapis.com"), "", "Android-telefoon of -tablet", "Android phone or tablet", "phone"),
    (("whatsapp.net", "instagram.com", "tiktokcdn.com"), "", "Telefoon of tablet", "Phone or tablet", "phone"),
    (("icloud.com", "apple.com", "mzstatic.com"), "Apple", "Apple-apparaat", "Apple device", "phone"),
]

# fabrikant (OUI) → (merk, nl, en, soort). Zwakker bewijs dan een domein: een chip zegt weinig over het apparaat.
VENDORS: list[tuple[re.Pattern, str, str, str, str]] = [(re.compile(p, re.I), *rest) for p, *rest in [
    (r"tuya", "Tuya", "Tuya-stekker of -lamp", "Tuya plug or light", "smart"),
    (r"shelly|allterco", "Shelly", "Shelly-schakelaar", "Shelly switch", "smart"),
    (r"signify|philips light", "Philips Hue", "Hue-lamp of -bridge", "Hue light or bridge", "smart"),
    (r"\btado\b", "tado", "tado-bridge", "tado bridge", "smart"),
    (r"bsh hausger", "Bosch/Siemens", "Bosch/Siemens-apparaat", "Bosch/Siemens appliance", "smart"),
    (r"daikin", "Daikin", "Daikin-warmtepomp of -airco", "Daikin heat pump or AC", "smart"),
    (r"espressif", "", "Apparaat met ESP-chip (slim apparaat of zelfbouw)", "Device with an ESP chip (smart device or DIY)", "smart"),
    (r"altobeam", "", "Robot of camera (AltoBeam-wifi)", "Robot or camera (AltoBeam wifi)", "smart"),
    (r"sonos", "Sonos", "Sonos-speaker", "Sonos speaker", "media"),
    (r"amazon tech", "Amazon", "Amazon-apparaat (Echo, Fire TV, Kindle)", "Amazon device (Echo, Fire TV, Kindle)", "smart"),
    (r"google", "Google", "Google Nest of Chromecast", "Google Nest or Chromecast", "smart"),
    (r"ring\b", "Ring", "Ring-deurbel of -camera", "Ring doorbell or camera", "camera"),
    (r"hikvision|ezviz", "Hikvision/EZVIZ", "Hikvision/EZVIZ-camera", "Hikvision/EZVIZ camera", "camera"),
    (r"reolink", "Reolink", "Reolink-camera", "Reolink camera", "camera"),
    (r"synology", "Synology", "Synology-NAS", "Synology NAS", "server"),
    (r"raspberry", "Raspberry Pi", "Raspberry Pi", "Raspberry Pi", "server"),
    (r"proxmox", "Proxmox", "Virtuele machine of container op Proxmox", "Virtual machine or container on Proxmox", "server"),
    (r"nvidia", "NVIDIA", "NVIDIA Shield", "NVIDIA Shield", "media"),
    (r"sony interactive", "Sony", "PlayStation", "PlayStation", "console"),
    (r"nintendo", "Nintendo", "Nintendo Switch", "Nintendo Switch", "console"),
    (r"\bapple\b", "Apple", "Apple-apparaat", "Apple device", "phone"),
    (r"samsung", "Samsung", "Samsung-apparaat", "Samsung device", "phone"),
    (r"hewlett|\bhp\b", "HP", "HP-printer", "HP printer", "printer"),
    (r"seiko epson", "Epson", "Epson-printer", "Epson printer", "printer"),
    (r"brother", "Brother", "Brother-printer", "Brother printer", "printer"),
    (r"tesla", "Tesla", "Tesla", "Tesla", "car"),
    (r"american power conversion|\bapc\b", "APC", "APC-noodstroomvoeding (UPS)", "APC UPS", "other"),
    (r"^dell\b", "Dell", "Dell-computer of -dock", "Dell computer or dock", "computer"),
]]

HOSTS: list[tuple[re.Pattern, str, str, str, str]] = [(re.compile(p, re.I), *rest) for p, *rest in [
    (r"^shelly", "Shelly", "Shelly-schakelaar", "Shelly switch", "smart"),
    (r"^(tasmota|wled|esphome)|^esp(32|8266)?[-_]", "", "Zelfbouw-apparaat (ESPHome/Tasmota/WLED)", "DIY device (ESPHome/Tasmota/WLED)", "smart"),
    (r"iphone", "Apple", "iPhone", "iPhone", "phone"), (r"ipad", "Apple", "iPad", "iPad", "phone"),
    (r"macbook|imac|mac-?mini", "Apple", "Mac", "Mac", "computer"),
    (r"^android|galaxy|pixel", "", "Android-telefoon of -tablet", "Android phone or tablet", "phone"),
    (r"^(desktop|laptop)-[a-z0-9]{6,}", "Microsoft", "Windows-pc", "Windows PC", "computer"),
    (r"raspberrypi", "Raspberry Pi", "Raspberry Pi", "Raspberry Pi", "server"),
    (r"chromecast", "Google", "Chromecast", "Chromecast", "media"),
    (r"^(hp|npi)[0-9a-f]{6}", "HP", "HP-printer", "HP printer", "printer"),
    (r"^(brw|brn)[0-9a-f]{12}", "Brother", "Brother-printer", "Brother printer", "printer"),
    (r"^epson", "Epson", "Epson-printer", "Epson printer", "printer"),
]]

# hostnamen die niets zeggen: de standaardnaam van een wifi-chip of een Android-ID
NO_NAME = re.compile(r"^(lwip\d*|espressif|esp[-_]?[0-9a-f]{4,}|android-[0-9a-f]{8,}|unknown|localhost|none|wlan\d*|"
                     r"[0-9a-f]{12}|[0-9a-f]{2}(-[0-9a-f]{2}){5})$", re.I)


def unnamed(c: dict) -> bool:
    """Geen eigen naam: UniFi toont dan de hostnaam, de fabrikant of het MAC-adres."""
    n = (c.get("name") or "").strip()
    return not n or n.lower() in {(c.get("mac") or "").lower(), (c.get("vendor") or "").lower()} or bool(NO_NAME.match(n))


def random_mac(mac: str | None) -> bool:
    """Privé-wifiadres (telefoons, tablets, laptops): het 'lokaal beheerd'-bit staat aan."""
    try:
        return bool(int((mac or "")[1], 16) & 2)
    except (ValueError, IndexError):
        return False


def _match(dom: str, suffixes: tuple[str, ...]) -> bool:
    return any(dom == s or dom.endswith("." + s) for s in suffixes)


def guess(c: dict, domains: dict[str, int], segs: list[dict] | None = None) -> dict | None:
    """Beste gok voor één apparaat, of None als er niets bruikbaars is. domains: domein → aantal keer."""
    scores: dict[tuple, dict] = {}

    def add(key: tuple, pts: float, why: str) -> None:
        s = scores.setdefault(key, {"score": 0.0, "why": [], "sources": set()})
        s["score"] += pts
        s["why"].append(why)
        s["sources"].add(why.split(":")[0])

    for doms, brand, nl, en, kind in SIGNS:
        hits = sorted(((d, n) for d, n in domains.items() if _match(d, doms)), key=lambda x: -x[1])
        if hits:
            n = sum(x[1] for x in hits)
            add((brand, nl, en, kind), 3 + min(math.log10(n + 1), 2),
                "dns:" + L(f"zoekt {hits[0][0]} op ({n}×)", f"looks up {hits[0][0]} ({n}×)"))
    v = c.get("vendor") or ""
    for rx, brand, nl, en, kind in VENDORS:
        if v and rx.search(v):
            add((brand, nl, en, kind), 1.5, "vendor:" + L(f"fabrikant {v}", f"vendor {v}"))
            break
    h = c.get("hostname") or ""
    for rx, brand, nl, en, kind in HOSTS:
        if h and rx.search(h):
            add((brand, nl, en, kind), 3, "host:" + L(f"hostnaam {h}", f"hostname {h}"))
            break
    if not scores:
        return None
    # merken die elkaar bevestigen (bijv. domein én fabrikant Tuya) tellen samen
    for key, s in scores.items():
        for other, o in scores.items():
            if other is not key and key[0] and other[0] == key[0] and other[3] == key[3]:
                s["bonus"] = s.get("bonus", 0) + o["score"] / 2
    best_key, best = max(scores.items(), key=lambda kv: kv[1]["score"] + kv[1].get("bonus", 0))
    total = best["score"] + best.get("bonus", 0)
    vendor_key = next((k for k, s in scores.items() if "vendor" in s["sources"] and k[0]), None)
    if best_key[1] in GENERIC and vendor_key and vendor_key[0] != best_key[0] and not random_mac(c.get("mac")):
        # een vast MAC-adres van een bekende fabrikant zegt meer dan een algemeen domein
        scores[vendor_key]["why"] += best["why"]
        scores[vendor_key]["sources"] |= best["sources"]
        best_key, best, total = vendor_key, scores[vendor_key], 3.5
    brand, nl, en, kind = best_key
    why = [w.split(":", 1)[1] for k, s in scores.items() if k == best_key or (k[0] and k[0] == brand) for w in s["why"]]
    multi = len({src for k, s in scores.items() if k == best_key or (k[0] and k[0] == brand) for src in s["sources"]})
    conf = "high" if total >= 5 and multi >= 2 or total >= 6 else "medium" if total >= 3 else "low"
    out = {"label": L(nl, en), "brand": brand, "kind": kind, "kind_label": L(*KINDS[kind]), "confidence": conf,
           "evidence": list(dict.fromkeys(why))[:4], "name": suggest_name(L(nl, en), c)}
    seg = client_segment(c, segs) if segs else None
    if kind in ("smart", "camera") and seg and seg.get("kind") == "main" and any(s.get("kind") == "iot" for s in segs or []):
        out["hint"] = L("Een slim apparaat op je hoofdnetwerk: dat hoort meestal op je IoT-netwerk.",
                        "A smart device on your main network: it usually belongs on your IoT network.")
    return out


def suggest_name(label: str, c: dict) -> str:
    """Kort voorstel uit het label: zonder toelichting tussen haakjes en zonder 'of …'."""
    return re.sub(r"\s*\(.*\)$", "", label).split(" of ")[0].split(" or ")[0].strip()[:54]


def _unique(rows: list[dict], clients: list[dict]) -> None:
    """Twee dezelfde voorstellen, of een naam die al bestaat: dan het staartje van het MAC-adres erachter."""
    taken = [(c.get("name") or "").lower() for c in clients if not unnamed(c)]
    names = [r["guess"]["name"].lower() for r in rows if r.get("guess")]
    for r in rows:
        g = r.get("guess")
        if g and (names.count(g["name"].lower()) > 1 or g["name"].lower() in taken):
            g["name"] = f"{g['name']} {r['mac'][-5:]}"


def domains_by_mac(db, ts: int) -> dict[str, dict[str, int]]:
    """Domeinen per apparaat uit de verbindingen (ook de namen die AdGuard aanvulde) en uit AdGuard zelf."""
    out: dict[str, dict[str, int]] = {}
    for r in db.q("SELECT client_mac, domain, COUNT(*) n FROM flows WHERE ts >= ? AND client_mac IS NOT NULL AND domain IS NOT NULL "
                  "AND domain != '' AND dir IN ('out', 'blocked') GROUP BY client_mac, domain", (ts - WEEK,)):
        d = out.setdefault(r["client_mac"], {})
        d[r["domain"].lower()] = d.get(r["domain"].lower(), 0) + r["n"]
    try:
        rows = db.q("SELECT mac, domain, n FROM dns_domains WHERE last >= ?", (ts - WEEK,))
    except Exception:  # noqa: BLE001 – zonder AdGuard bestaat de tabel misschien niet
        rows = []
    for r in rows:
        d = out.setdefault(r["mac"], {})
        d[r["domain"]] = d.get(r["domain"], 0) + r["n"]
    return out


def identify_all(snap: dict, db, ts: int, only_unnamed: bool = True) -> list[dict]:
    segs = ((snap.get("config") or {}).get("segments") or {}).get("segments")
    doms = domains_by_mac(db, ts)
    out = []
    for c in snap.get("clients") or []:
        if c.get("guest") or (only_unnamed and not unnamed(c)):
            continue
        g = guess(c, doms.get(c["mac"], {}), segs)
        out.append({"mac": c["mac"], "name": c.get("name") or c["mac"], "ip": c.get("ip"), "vendor": c.get("vendor"),
                    "hostname": c.get("hostname"), "wired": c.get("wired"), "guess": g})
    _unique(out, snap.get("clients") or [])
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda x: (order[x["guess"]["confidence"]] if x["guess"] else 3, x["name"].lower()))


def identify_one(snap: dict, db, mac: str, ts: int) -> dict | None:
    segs = ((snap.get("config") or {}).get("segments") or {}).get("segments")
    c = next((x for x in snap.get("clients") or [] if x["mac"] == mac), None)
    if not c:
        return None
    row = {"mac": mac, "guess": guess(c, domains_by_mac(db, ts).get(mac, {}), segs)}
    _unique([row], [x for x in snap.get("clients") or [] if x["mac"] != mac])
    return {"unnamed": unnamed(c), "guess": row["guess"]}
