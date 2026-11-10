"""Extra controles: DNS om je eigen DNS-server heen, internetstoringen, firewall-audit, mislukte wifi-verbindingen,
wat UniFi zelf opviel, rustigere kanalen, beveiligingsadviezen van Ubiquiti en een gewijzigd publiek IP-adres.

Alle teksten staan in beide talen (L); rules.evaluate draait ze twee keer, zie i18n.
"""
from __future__ import annotations

import ipaddress
import time

from .i18n import L

DAY = 86400

# ------------------------------------------------------------------ DNS om je eigen server heen
DOH_DOMAINS = {"dns.google", "dns.google.com", "cloudflare-dns.com", "one.one.one.one", "mozilla.cloudflare-dns.com",
               "chrome.cloudflare-dns.com", "dns.quad9.net", "dns9.quad9.net", "doh.opendns.com", "dns.nextdns.io",
               "dns.adguard-dns.com", "dns.adguard.com", "doh.cleanbrowsing.org", "doh.mullvad.net", "dns.controld.com"}
DOH_IPS = {"8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220",
           "94.140.14.14", "94.140.15.15", "2001:4860:4860::8888", "2001:4860:4860::8844", "2606:4700:4700::1111"}


def dns_kind(f: dict) -> str | None:
    """'dns' (gewone DNS, poort 53), 'dot' (DNS-over-TLS, 853) of 'doh' (DNS-over-HTTPS naar een bekende resolver)."""
    port, svc = f.get("port"), (f.get("service") or "").upper()
    if port == 53 or svc == "DNS":
        return "dns"
    if port == 853 or "OVER_TLS" in svc:
        return "dot"
    if port == 443 and ((f.get("domain") or "").lower() in DOH_DOMAINS or f.get("remote_ip") in DOH_IPS):
        return "doh"
    return None


def _public(ip: str | None) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except (TypeError, ValueError):
        return False


def dns_leaks(out: list[dict], snap: dict, db, ts: int, issue) -> None:
    cfg = snap.get("config") or {}
    servers = cfg.get("dns_servers")
    if servers is None:
        return
    gw = {d.get("ip") for d in snap["devices"] if d["type"] == "gateway"}
    resolvers = set(servers) | gw   # je DNS-server zelf mag wel naar buiten (upstream)
    rows = db.q("SELECT client_mac, client_name, client_ip, remote_ip, port, service, domain, ts FROM flows "
                "WHERE ts>=? AND dir='out' AND (port IN (53, 853) OR service IN ('DNS', 'DNS_OVER_TLS') OR port=443)",
                (ts - DAY,))
    clients = {c["mac"]: c for c in snap["clients"]}
    per: dict[str, dict] = {}
    for r in rows:
        f = dict(r)
        kind = dns_kind(f)
        if not kind or not f["client_mac"] or f["client_ip"] in resolvers or (f["remote_ip"] and not _public(f["remote_ip"]) and kind != "doh"):
            continue
        p = per.setdefault(f["client_mac"], {"n": 0, "kinds": set(), "servers": set(), "last": 0, "name": f["client_name"]})
        p["n"] += 1
        p["kinds"].add(kind)
        # bij gewone DNS en DoT is het domein in UniFi's verkeerslog onbetrouwbaar (vaak 'ping.ui.com'): dan het adres
        dom = (f["domain"] or "").lower()
        p["servers"].add((dom if kind == "doh" and dom in DOH_DOMAINS else None) or f["remote_ip"] or "?")
        p["last"] = max(p["last"], f["ts"])
    own = ", ".join(servers) if servers else L("je gateway", "your gateway")
    for mac, p in per.items():
        c = clients.get(mac) or {}
        real = c.get("name") and c["name"] not in (c.get("vendor"), mac)   # zonder eigen naam toont UniFi de fabrikant
        flow_name = p["name"] if p["name"] and not p["name"][0].isdigit() else None   # UniFi geeft soms alleen het IP
        who = (c["name"] if real else None) or c.get("hostname") or flow_name or c.get("name") or mac
        kinds = sorted(p["kinds"])
        label = {"dns": L("gewone DNS", "plain DNS"), "dot": "DNS-over-TLS", "doh": "DNS-over-HTTPS"}
        srv = ", ".join(sorted(p["servers"])[:3])
        adv = []
        if "dns" in kinds:
            adv.append(L("Gewone DNS (poort 53) kun je afvangen: maak in UniFi een firewallregel die poort 53 naar internet "
                         "blokkeert voor alles behalve je eigen DNS-server, of stuur het met een NAT-regel om naar je DNS-server.",
                         "Plain DNS (port 53) can be caught: create a firewall rule in UniFi that blocks port 53 to the internet "
                         "for everything except your own DNS server, or redirect it to your DNS server with a NAT rule."))
        if "dot" in kinds:
            adv.append(L("DNS-over-TLS blokkeer je met een regel op poort 853 naar internet; het apparaat valt dan meestal "
                         "terug op je eigen DNS-server.", "Block DNS-over-TLS with a rule on port 853 to the internet; the device "
                         "then usually falls back to your own DNS server."))
        if "doh" in kinds:
            adv.append(L("DNS-over-HTTPS lijkt op gewoon webverkeer en is lastig te blokkeren. Blokkeer de bekende adressen "
                         "(bijvoorbeeld 8.8.8.8, 8.8.4.4 en 1.1.1.1 op poort 443) of accepteer het voor dit apparaat.",
                         "DNS-over-HTTPS looks like ordinary web traffic and is hard to block. Block the well-known addresses "
                         "(for example 8.8.8.8, 8.8.4.4 and 1.1.1.1 on port 443) or accept it for this device."))
        adv.append(L("Veel apparaten (Chromecast, Android, sommige auto's en IoT) hebben een vaste DNS-server ingebouwd. "
                     "Is dat hier zo en vind je het goed, kies dan Negeren → Altijd.",
                     "Many devices (Chromecast, Android, some cars and IoT) have a fixed DNS server built in. If that is the "
                     "case here and you are fine with it, choose Ignore → Always."))
        out.append(issue(f"dns_leak:{mac}", "info", "security", "client", mac,
                         L(f"{who} gaat om je DNS-server heen", f"{who} bypasses your DNS server"),
                         L(f"In 24 uur {p['n']}× {', '.join(label[k] for k in kinds)} naar {srv}, in plaats van via {own}. "
                           "Daardoor werken je advertentie- en trackerfilters niet voor dit apparaat.",
                           f"{p['n']}× {', '.join(label[k] for k in kinds)} to {srv} in 24 hours, instead of via {own}. "
                           "Your ad and tracker filters therefore don't work for this device."),
                         " ".join(adv), "dns_queries", p["n"], 1, c.get("ap_mac") or c.get("sw_mac"),
                         mac if c else None, p["last"]))


# ------------------------------------------------------------------ internetstoringen
def _dur(sec: float) -> str:
    sec = int(sec)
    if sec < 90:
        return L(f"{sec} seconden", f"{sec} seconds")
    if sec < 5400:
        return L(f"{round(sec / 60)} minuten", f"{round(sec / 60)} minutes")
    return L(f"{sec / 3600:.1f}".replace(".", ",") + " uur", f"{sec / 3600:.1f} hours")


def wan_outages(out: list[dict], db, ts: int, issue, gw) -> None:
    week = db.outages(ts - 7 * DAY)
    for o in week:
        end = o["ts"] + o["seconds"]
        if end < ts - DAY or o["seconds"] < 60:
            continue
        when = time.strftime("%d-%m %H:%M", time.localtime(o["ts"]))
        i = issue(f"wan_outage:{o['id']}", "info", "wan", "wan", "wan",
                  L(f"Internet was {_dur(o['seconds'])} weg", f"Internet was down for {_dur(o['seconds'])}"),
                  L(f"Je internetverbinding ({o['wan']}) viel weg op {when} en was na {_dur(o['seconds'])} terug.",
                    f"Your internet connection ({o['wan']}) dropped at {when} and came back after {_dur(o['seconds'])}."),
                  L("Eén keer kan gebeuren (onderhoud bij de provider). Op de pagina Internet zie je alle storingen van de "
                    "afgelopen 90 dagen; handig als je de provider wilt bellen.",
                    "Once can happen (maintenance at the provider). The Internet page shows all outages of the past 90 days; "
                    "handy if you want to call your provider."), device_mac=gw, last_ts=end)
        i.update(quiet_resolve=True)
        out.append(i)
    long = [o for o in week if o["seconds"] >= 60]
    if len(long) >= 3:
        total = sum(o["seconds"] for o in long)
        out.append(issue("wan_outages_week", "warning", "wan", "wan", "wan",
                         L(f"Internet viel deze week {len(long)}× weg", f"Internet dropped {len(long)}× this week"),
                         L(f"Samen {_dur(total)} zonder internet in de afgelopen 7 dagen.",
                           f"{_dur(total)} without internet in total over the past 7 days."),
                         L("Kijk of de storingen op vaste tijden vallen (dan vaak de modem of stroom), en meld het anders bij je "
                           "provider met de lijst van de pagina Internet.",
                           "Check whether the outages happen at fixed times (then often the modem or power); otherwise report "
                           "it to your provider with the list from the Internet page."), "outages", len(long), 3, gw,
                         last_ts=max(o["ts"] + o["seconds"] for o in long)))


# ------------------------------------------------------------------ firewall-audit
def firewall_audit(out: list[dict], seg: dict, issue) -> None:
    for f in seg.get("audit") or []:
        if f["type"] == "shadowed":
            out.append(issue(f"fw_shadow:{f['rule']}", "info", "security", "site", "firewall",
                             L(f"Firewallregel '{f['rule']}' doet niets", f"Firewall rule '{f['rule']}' has no effect"),
                             L(f"Voor verkeer van {f['src']} naar {f['dst']} vangt de eerdere regel '{f['by']}' al alles af "
                               f"({'toestaan' if f['by_action'] == 'allow' else 'blokkeren'}), dus '{f['rule']}' komt nooit aan de beurt.",
                               f"For traffic from {f['src']} to {f['dst']} the earlier rule '{f['by']}' already catches everything "
                               f"({f['by_action']}), so '{f['rule']}' is never reached."),
                             L("Zet de regel boven de algemene regel (UniFi: Instellingen → Beleid → Zone-Based Firewall, volgorde "
                               "aanpassen), of verwijder hem als hij niet meer nodig is.",
                               "Move the rule above the general rule (UniFi: Settings → Policy → Zone-Based Firewall, change the "
                               "order), or remove it if it is no longer needed.")))
        elif f["type"] in ("opens", "exposed"):
            who = L(f" (alleen vanaf {', '.join(f['src_ips'])})", f" (only from {', '.join(f['src_ips'])})") if f["src_ips"] else ""
            exposed = f["type"] == "exposed"
            out.append(issue(f"fw_{f['type']}:{f['rule']}", "critical" if exposed and not f["src_ips"] else "warning",
                             "security", "site", "firewall",
                             L(f"Regel '{f['rule']}' zet {f['dst']} open voor {f['src']}", f"Rule '{f['rule']}' opens {f['dst']} to {f['src']}"),
                             L(f"Deze regel staat al het verkeer van {f['src']} naar {f['dst']} toe{who}, op alle poorten. "
                               + ("Daarmee kan iedereen op internet bij je netwerk." if exposed else
                                  "Daarmee is de scheiding tussen die netwerken voor dit verkeer weg."),
                               f"This rule allows all traffic from {f['src']} to {f['dst']}{who}, on every port. "
                               + ("That lets anyone on the internet reach your network." if exposed else
                                  "That removes the separation between those networks for this traffic.")),
                             L("Beperk de regel tot het apparaat en de poort die echt nodig zijn (bijvoorbeeld alleen Home Assistant "
                               "op 8123), of zet hem uit als hij maar tijdelijk was.",
                               "Restrict the rule to the device and port that are really needed (for example only Home Assistant "
                               "on 8123), or disable it if it was only temporary.")))


# ------------------------------------------------------------------ mislukte wifi-verbindingen
def connect_failures(out: list[dict], ins: dict, issue) -> None:
    for band, c in (ins.get("wifi_connectivity") or {}).items():
        if band == "all" or c.get("failed", 0) < 3 or (c.get("success") or 100) >= 95:
            continue
        stages = [("auth", (c.get("assoc") or 100) - (c.get("auth") or 100)),
                  ("dhcp", (c.get("auth") or 100) - (c.get("dhcp") or 100)),
                  ("dns", (c.get("dhcp") or 100) - (c.get("dns") or 100))]
        stage = max(stages, key=lambda s: s[1])[0]
        why = {"auth": (L("bij het inloggen (wachtwoord of beveiligingstype)", "at login (password or security type)"),
                        L("Meestal een apparaat met een oud wachtwoord, of een ouder apparaat dat WPA3 of beveiligde "
                          "beheerframes (PMF) niet aankan. Zet bij twijfel het wifi-netwerk op 'WPA2/WPA3' en PMF op 'optioneel'.",
                          "Usually a device with an old password, or an older device that can't handle WPA3 or protected "
                          "management frames (PMF). If in doubt, set the wifi network to 'WPA2/WPA3' and PMF to 'optional'.")),
               "dhcp": (L("bij het krijgen van een IP-adres (DHCP)", "when getting an IP address (DHCP)"),
                        L("Controleer of de DHCP-pool van dat netwerk niet vol is en of DHCP op het juiste VLAN draait "
                          "(bijvoorbeeld na het verhuizen van apparaten naar een IoT-netwerk).",
                          "Check that the DHCP pool of that network isn't full and that DHCP runs on the right VLAN "
                          "(for example after moving devices to an IoT network).")),
               "dns": (L("bij de eerste DNS-vraag", "at the first DNS query"),
                       L("De DNS-server die je uitdeelt (bijvoorbeeld AdGuard of Pi-hole) reageerde niet. Kijk of die bereikbaar "
                         "is vanaf dat netwerk; een tweede DNS-server in DHCP voorkomt dit.",
                         "The DNS server you hand out (for example AdGuard or Pi-hole) did not respond. Check that it is "
                         "reachable from that network; a second DNS server in DHCP prevents this."))}[stage]
        out.append(issue(f"conn_fail:{band}", "warning" if (c.get("success") or 100) < 85 else "info", "wifi", "site", f"wifi{band}",
                         L(f"Mislukte wifi-verbindingen op {band} GHz", f"Failed wifi connections on {band} GHz"),
                         L(f"In het afgelopen etmaal lukten {c['success']:.0f}% van de {c['attempts']} pogingen om te verbinden; "
                           f"het ging vooral mis {why[0]}.",
                           f"In the past day {c['success']:.0f}% of the {c['attempts']} connection attempts succeeded; "
                           f"it mostly failed {why[0]}."),
                         why[1], "success_pct", c["success"], 95))


# ------------------------------------------------------------------ wat UniFi zelf opviel
ANOMALY = {
    "USER_HIGH_TCP_LATENCY": ("hoge vertraging", "high latency"),
    "USER_HIGH_DNS_LATENCY": ("trage DNS", "slow DNS"),
    "USER_HIGH_WIFI_LATENCY": ("hoge wifi-vertraging", "high wifi latency"),
    "USER_HIGH_TCP_PACKET_LOSS": ("pakketverlies", "packet loss"),
    "USER_POOR_STREAM_EFF": ("haperende verbinding", "poor stream efficiency"),
    "USER_SLEEPY_CLIENT": ("slaapt vaak", "sleeps often"),
    "USER_HIGH_WIFI_RETRIES": ("veel herhalingen", "many retries"),
    "USER_LOW_PHY_RATE": ("lage linksnelheid", "low link rate"),
    "USER_SIGNAL_STRENGTH_FAILURES": ("verbinding mislukt door zwak signaal", "connection failed due to weak signal"),
}
OWN_METRIC = {"USER_HIGH_WIFI_RETRIES", "USER_LOW_PHY_RATE", "USER_SIGNAL_STRENGTH_FAILURES"}   # meet Sonar zelf al


def anomalies(out: list[dict], snap: dict, ins: dict, ts: int, issue) -> None:
    clients = {c["mac"]: c for c in snap["clients"]}
    covered = {i.get("client_mac") for i in out if i.get("client_mac") and i["category"] == "wifi"}
    per: dict[str, dict[str, list[int]]] = {}
    for a in ins.get("anomalies") or []:
        if a["ts"] < ts - DAY or a["mac"] not in clients or a["type"] not in ANOMALY:
            continue
        if a["type"] in OWN_METRIC and a["mac"] in covered:
            continue
        per.setdefault(a["mac"], {}).setdefault(a["type"], []).append(a["ts"])
    for mac, kinds in per.items():
        total = sum(len(v) for v in kinds.values())
        if total < 3 and "USER_HIGH_DNS_LATENCY" not in kinds:
            continue
        c = clients[mac]
        names = ", ".join(f"{L(*ANOMALY[k])} ({len(v)}×)" for k, v in sorted(kinds.items(), key=lambda kv: -len(kv[1])))
        adv = []
        if "USER_HIGH_DNS_LATENCY" in kinds:
            adv.append(L("Trage DNS ligt meestal aan je DNS-server (AdGuard, Pi-hole) of zijn upstream: kijk daar naar de "
                         "reactietijden.", "Slow DNS is usually your DNS server (AdGuard, Pi-hole) or its upstream: check its "
                         "response times there."))
        if kinds.keys() & {"USER_HIGH_TCP_LATENCY", "USER_HIGH_TCP_PACKET_LOSS", "USER_HIGH_WIFI_LATENCY", "USER_POOR_STREAM_EFF"}:
            adv.append(L("Vertraging en pakketverlies komen vaak door een druk kanaal of een zwakke wifi-verbinding; kijk naar "
                         "het signaal en de kanaalbezetting van de AP.", "Latency and packet loss often come from a busy channel "
                         "or a weak wifi link; check the signal and the channel utilization of the AP."))
        if "USER_SLEEPY_CLIENT" in kinds:
            adv.append(L("Vaak slapen is normaal voor zuinige apparaten; alleen een probleem als het apparaat dan onbereikbaar is.",
                         "Sleeping often is normal for low-power devices; only a problem if the device then can't be reached."))
        out.append(issue(f"ufi_anom:{mac}", "info", "wifi", "client", mac,
                         L(f"{c['name']}: UniFi meldt {L(*ANOMALY[max(kinds, key=lambda k: len(kinds[k]))])}",
                           f"{c['name']}: UniFi reports {L(*ANOMALY[max(kinds, key=lambda k: len(kinds[k]))])}"),
                         L(f"In het afgelopen etmaal zag UniFi bij dit apparaat: {names}.",
                           f"In the past day UniFi saw this for the device: {names}."),
                         " ".join(adv) or L("Houd het in de gaten.", "Keep an eye on it."),
                         "anomalies", total, 3, c.get("ap_mac") or c.get("sw_mac"), mac,
                         max(t for v in kinds.values() for t in v)))


# ------------------------------------------------------------------ rustiger kanaal (wifi in de buurt)
BAD_INTERFERENCE = 40   # % zendtijd bezet door anderen, eerder gemeten op (of naast) dat kanaal: niet aanraden
NON_DFS_5 = [36, 40, 44, 48, 149, 153, 157, 161, 165]
DFS_5 = [52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144]


def _weight(sig) -> float:
    return 10 ** ((max(-95, min(-40, sig or -90)) + 90) / 10)   # −90 dBm ≈ 1, −70 ≈ 100, −60 ≈ 1000


def _occupies(band: str, ch: int, width: int) -> set[int]:
    if band == "2.4":
        return set(range(ch - 2, ch + 3))   # 20 MHz ≈ ±2 kanalen
    n = max(1, int((width or 20) // 20))
    base = 149 if ch >= 149 else 100 if ch >= 100 else 36
    size = 4 * n
    start = base + (ch - base) // size * size
    return set(range(start, start + size, 4))


def channel_history(db, mac: str, band: str, since: int) -> dict[int, float]:
    """Gemeten storing per kanaal uit Sonars eigen historie: zat de AP ooit op dat kanaal, hoeveel van de zendtijd
    was dan bezet door anderen? Zo komt ook storing die niet van wifi komt (en dus niet in de burenlijst staat) mee."""
    try:
        rows = db.q("SELECT channel, AVG(interference) intf, COUNT(*) n FROM radio_samples WHERE mac=? AND radio=? AND ts>=? "
                    "AND channel IS NOT NULL GROUP BY channel", (mac, band, since))
        return {int(r["channel"]): r["intf"] for r in rows if r["n"] >= 6 and r["intf"] is not None}
    except (KeyError, IndexError, TypeError):
        return {}


def channel_table(ap: dict, band: str, ins: dict, devices: list[dict], hist: dict[int, float] | None = None) -> list[dict]:
    """Per kandidaat-kanaal hoe druk het is voor deze AP: buren (gewogen naar sterkte), je eigen AP's en eerder
    gemeten storing op dat kanaal."""
    radio = next((r for r in ap.get("radios") or [] if r["radio"] == band), None)
    if not radio or not radio.get("channel"):
        return []
    width = int(radio.get("width") or (20 if band == "2.4" else 80))
    nb = [n for n in ins.get("neighbors") or [] if n["ap_mac"] == ap["mac"] and n["band"] == band]
    own = [(d["name"], r) for d in devices if d["type"] == "ap" and d["mac"] != ap["mac"] and d.get("state") == "online"
           for r in d.get("radios") or [] if r["radio"] == band and r.get("channel")]
    if band == "2.4":
        cands = [1, 6, 11]
    elif band == "5":
        dfs = radio["channel"] in DFS_5
        step = max(1, width // 20)
        pool = NON_DFS_5 + (DFS_5 if dfs else [])
        cands = sorted({c for c in pool if (c - (149 if c >= 149 else 100 if c >= 100 else 36)) % (4 * step) == 0
                        and _occupies(band, c, width) <= set(pool)})   # alleen volledige blokken (165 past niet in 80 MHz)
    else:
        return []
    rows = []
    for cand in cands:
        occ = _occupies(band, cand, width)
        hits = [n for n in nb if occ & _occupies(band, n["channel"], n["width"])]
        mine = [name for name, r in own if occ & _occupies(band, r["channel"], r.get("width") or width)]
        load = sum(_weight(n["signal"]) for n in hits)   # alleen buren; je eigen AP's staan apart (die regel je zelf)
        # 5 GHz: storing (bijv. een zender of babyfoon) is meestal breder dan één kanaal, dus ook het blok ernaast telt
        # mee. Op 2.4 GHz overlappen de kanalen al; daar alleen wat echt in het blok valt.
        edge = 8 if band == "5" else 0
        measured = [v for ch, v in (hist or {}).items() if min(occ) - edge <= ch <= max(occ) + edge and (ch in occ or v >= BAD_INTERFERENCE)]
        rows.append({"channel": cand, "neighbors": len(hits), "strongest": max((n["signal"] for n in hits if n["signal"] is not None), default=None),
                     "own": mine, "load": round(load), "interference": round(max(measured)) if measured else None,
                     "current": radio["channel"] in occ and cand == min(
                         (c for c in cands if radio["channel"] in _occupies(band, c, width)), default=None)})
    return rows


def quieter_channel(out: list[dict], snap: dict, ins: dict, issue, db=None, ts: int = 0) -> None:
    if not ins.get("neighbors"):
        return
    for ap in snap["devices"]:
        if ap["type"] != "ap" or ap.get("state") != "online":
            continue
        for band in ("2.4", "5"):
            hist = channel_history(db, ap["mac"], band, ts - 30 * DAY) if db is not None else {}
            rows = channel_table(ap, band, ins, snap["devices"], hist)
            cur = next((r for r in rows if r["current"]), None)
            if not cur or cur["load"] < 100:   # minder dan één buur op −70 dBm: niets aan de hand
                continue
            ok = [r for r in rows if (r["interference"] or 0) < BAD_INTERFERENCE or r["current"]]
            free = [r for r in ok if not r["own"]] or ok   # liefst geen kanaal waar al een eigen AP zit
            best = min(free, key=lambda r: r["load"])
            if best["channel"] == cur["channel"] or best["load"] * 4 > cur["load"]:
                continue
            strong = f", {L('sterkste', 'strongest')} {cur['strongest']} dBm" if cur["strongest"] is not None else ""
            out.append(issue(f"cfg_quieter:{ap['mac']}@{band}", "info", "config", "radio", f"{ap['mac']}@{band}",
                             L(f"{ap['name']}: rustiger {band} GHz-kanaal beschikbaar", f"{ap['name']}: quieter {band} GHz channel available"),
                             L(f"Op kanaal {cur['channel']} hoort {ap['name']} {cur['neighbors']} netwerken van buren{strong}"
                               + (f" en je eigen {', '.join(cur['own'])}" if cur["own"] else "")
                               + f". Op kanaal {best['channel']}: {best['neighbors']}" + (f" (plus {', '.join(best['own'])})" if best["own"] else "") + ".",
                               f"On channel {cur['channel']} {ap['name']} hears {cur['neighbors']} neighbouring networks{strong}"
                               + (f" and your own {', '.join(cur['own'])}" if cur["own"] else "")
                               + f". On channel {best['channel']}: {best['neighbors']}" + (f" (plus {', '.join(best['own'])})" if best["own"] else "") + "."),
                             L(f"Overweeg kanaal {best['channel']} (UniFi: Apparaten → {ap['name']} → Radio's). Heb je bewust een "
                               "kanaalplan, bijvoorbeeld omdat een apparaat een kanaal niet ondersteunt of vanwege storing die niet "
                               "van wifi komt, kies dan Negeren. In de AP-details zie je alle kanalen naast elkaar.",
                               f"Consider channel {best['channel']} (UniFi: Devices → {ap['name']} → Radios). If you have a deliberate "
                               "channel plan, for example because a device doesn't support a channel or because of non-wifi "
                               "interference, choose Ignore. The AP details show all channels side by side."),
                             "neighbor_load", cur["load"], best["load"], ap["mac"]))


# ------------------------------------------------------------------ beveiligingsadviezen
def advisory_issues(out: list[dict], ins: dict, issue) -> None:
    by: dict[str, list[dict]] = {}
    for m in ins.get("advisories") or []:
        by.setdefault(m["id"], []).append(m)
    for aid, ms in by.items():
        score = max((m["score"] or 0) for m in ms)
        devs = {d["name"]: d["version"] for m in ms for d in m["devices"]}
        fixed = next((m["fixed"] for m in ms if m["fixed"]), None)
        product = ms[0]["product"]
        cves = sorted({c for m in ms for c in m["cves"]})
        which = ", ".join(f"{n} ({v})" for n, v in list(devs.items())[:5])
        hot = sorted({c for m in ms for c in m.get("exploited") or []})
        i = issue(f"advisory:{aid}", "critical" if score >= 9 or hot else "warning", "security", "site", "advisory",
                  L(f"Beveiligingsadvies {aid} van Ubiquiti geldt voor je {product}",
                    f"Ubiquiti security advisory {aid} applies to your {product}"),
                  L(("Wordt volgens CISA echt misbruikt. " if hot else "") + f"{len(cves) or len(ms)} kwetsbaarhe{'den' if (len(cves) or len(ms)) > 1 else 'id'}, hoogste score "
                    f"{score:.1f}".replace(".", ",") + " van 10." + f" Getroffen: {which}" + (f"; opgelost in versie {fixed}." if fixed else ".")
                    + f" Ubiquiti: \"{ms[0]['summary'][:200]}\"",
                    ("Exploited in the wild according to CISA. " if hot else "") + f"{len(cves) or len(ms)} vulnerabilit{'ies' if (len(cves) or len(ms)) > 1 else 'y'}, highest score "
                    f"{score:.1f} out of 10. Affected: {which}" + (f"; fixed in version {fixed}." if fixed else ".")
                    + f" Ubiquiti: \"{ms[0]['summary'][:200]}\""),
                  L("Werk bij via UniFi (Apparaten → Bijwerken, of Instellingen → Systeem voor de Network-app). "
                    f"Het volledige advies: {ms[0]['url']}",
                    "Update via UniFi (Devices → Update, or Settings → System for the Network app). "
                    f"The full advisory: {ms[0]['url']}"), last_ts=ms[0]["ts"])
        i.update(notify=True)
        out.append(i)


# ------------------------------------------------------------------ kwetsbaarheidscheck
def vuln_issue(out: list[dict], ins: dict, issue) -> None:
    """Bewust alleen een aantal: een melding kan bij een dienst van derden terechtkomen, de details blijven in Sonar."""
    v = ins.get("vuln") or {}
    n = v.get("findings") or 0
    if n:
        out.append(issue("vuln:findings", "critical" if v.get("exploited") else "warning", "security", "site", "vuln",
                         L(f"Kwetsbaarheidscheck: {n} bevinding{'en' if n != 1 else ''}", f"Vulnerability check: {n} finding{'s' if n != 1 else ''}"),
                         L("De details staan alleen in Sonar, onder Beveiliging → Kwetsbaarheden.", "The details are only in Sonar, under Security → Vulnerabilities."),
                         L("Bekijk per bevinding of die dienst open moet staan. Hoort het zo, kies dan 'Hoort zo'.", "For each finding, check whether that service should be open. If it should, choose 'Expected'.")))
    s = v.get("stale") or 0
    if s:
        out.append(issue("vuln:outside_stale", "info", "security", "site", "vuln",
                         L(f"Shodan ziet {s} poort{'en' if s != 1 else ''} van iets wat uitstaat", f"Shodan sees {s} port{'s' if s != 1 else ''} of something that is switched off"),
                         L("Waarschijnlijk zijn de gegevens van Shodan ouder dan je instellingen. De details staan in Sonar, onder Beveiliging → Kwetsbaarheden.",
                           "Shodan's data is probably older than your settings. The details are in Sonar, under Security → Vulnerabilities."),
                         L("Niets doen. Staat de poort er na twee weken nog, dan wordt het een bevinding en loont het om na te gaan of hij echt dicht is.",
                           "Nothing to do. If the port is still listed after two weeks, it becomes a finding and it is worth checking that it is really closed.")))


# ------------------------------------------------------------------ publiek IP-adres
def public_ip(out: list[dict], snap: dict, issue, gw) -> None:
    ch = snap.get("wan_ip_change")
    if not ch:
        return
    when = time.strftime("%d-%m %H:%M", time.localtime(ch["changed"]))
    i = issue(f"wan_ip:{ch['changed']}", "info", "wan", "wan", "wan",
              L("Publiek IP-adres gewijzigd", "Public IP address changed"),
              L(f"Op {when} kreeg je internetverbinding een nieuw adres: {ch['old']} → {ch['ip']}.",
                f"At {when} your internet connection got a new address: {ch['old']} → {ch['ip']}."),
              L("Gebruik je dynamische DNS, een VPN (WireGuard) of diensten die op je IP-adres vertrouwen, controleer dan "
                "of die het nieuwe adres al hebben. Port forwards blijven gewoon werken.",
                "If you use dynamic DNS, a VPN (WireGuard) or services that trust your IP address, check that they already "
                "have the new address. Port forwards keep working."), device_mac=gw, last_ts=ch["changed"])
    i.update(notify=True, quiet_resolve=True)
    out.append(i)


def bufferbloat(out: list[dict], snap: dict, issue, gw) -> None:
    b = snap.get("bufferbloat")
    if not b or b["grade"] not in ("D", "F"):
        return
    i = issue("bufferbloat", "info", "wan", "wan", "wan",
              L(f"Internet wordt traag als de lijn vol zit (cijfer {b['grade']})", f"Internet gets slow when the line is full (grade {b['grade']})"),
              L(f"Tijdens de laatste speedtest liep de vertraging op van {b['idle']:.0f} ms naar {b['idle'] + b['worst']:.0f} ms.",
                f"During the last speed test the delay rose from {b['idle']:.0f} ms to {b['idle'] + b['worst']:.0f} ms."),
              L("Zet Smart Queues aan bij je internetverbinding in UniFi en stel ze in op ongeveer 90% van je lijnsnelheid. Dat kost "
                "iets topsnelheid, maar videobellen en games blijven soepel als iemand iets groots downloadt. Doe daarna opnieuw een speedtest.",
                "Turn on Smart Queues for your internet connection in UniFi and set them to about 90% of your line speed. That costs a "
                "little top speed, but video calls and games stay smooth while someone downloads something big. Then run another speed test."),
              device_mac=gw, last_ts=b["ts"])
    out.append(i)


def backup_stale(out: list[dict], snap: dict, issue, gw) -> None:
    b = snap.get("backups")
    if not b or not b["stale"]:
        return
    when = time.strftime("%d-%m-%Y", time.localtime(b["newest"])) if b["newest"] else None
    out.append(issue("backup_stale", "warning", "config", "wan", "wan",
                     L("Geen recente UniFi-backup", "No recent UniFi backup"),
                     L(f"De nieuwste backup die Sonar heeft, is van {when}." if when else "Sonar heeft nog geen enkele backup van je controller.",
                       f"The newest backup Sonar has is from {when}." if when else "Sonar does not have any backup of your controller yet."),
                     L("Kijk onder Instellingen → UniFi-backups wat er misgaat, of zet daar een dagelijkse backup aan. Staan de automatische "
                       "backups in UniFi wel aan? Dat zie je in UniFi onder Instellingen → Systeem → Backups.",
                       "Check Settings → UniFi backups to see what is going wrong, or turn on a daily backup there. Are automatic backups on in "
                       "UniFi? You can see that in UniFi under Settings → System → Backups."), device_mac=gw))


def run_all(out: list[dict], snap: dict, db, ts: int, issue) -> None:
    gw = next((d["mac"] for d in snap["devices"] if d["type"] == "gateway"), None)
    ins = snap.get("insights") or {}
    dns_leaks(out, snap, db, ts, issue)
    wan_outages(out, db, ts, issue, gw)
    seg = (snap.get("config") or {}).get("segments")
    if seg:
        firewall_audit(out, seg, issue)
    connect_failures(out, ins, issue)
    anomalies(out, snap, ins, ts, issue)
    quieter_channel(out, snap, ins, issue, db, ts)
    advisory_issues(out, ins, issue)
    vuln_issue(out, ins, issue)
    public_ip(out, snap, issue, gw)
    bufferbloat(out, snap, issue, gw)
    backup_stale(out, snap, issue, gw)
