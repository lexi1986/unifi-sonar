"""Issue-detectie: zet ruwe metingen + recente historie om in begrijpelijke
problemen met ernst, uitleg en advies.

Regels kijken naar het gemiddelde over een venster (standaard 15 min) in plaats
van naar één meting, zodat een enkele uitschieter geen alarm geeft.
"""
from __future__ import annotations

import time

from .config import Thresholds

WINDOW = 15 * 60
HOUR = 3600
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
PENALTY = {"critical": 40, "warning": 15, "info": 3}
GOOD_SIGNAL = -65
STANDARD_24 = {1, 6, 11}


def signal_limits(th: Thresholds, band: str | None) -> tuple[float, float]:
    if band == "2.4":
        return th.client_signal_warn_24, th.client_signal_crit_24
    return th.client_signal_warn, th.client_signal_crit


def _issue(key, severity, category, entity_type, entity_id, title, detail, advice,
           metric=None, value=None, threshold=None, device_mac=None, client_mac=None) -> dict:
    return {
        "key": key, "severity": severity, "category": category, "entity_type": entity_type,
        "entity_id": entity_id, "title": title, "detail": detail, "advice": advice,
        "metric": metric, "value": None if value is None else round(value, 1),
        "threshold": threshold, "device_mac": device_mac, "client_mac": client_mac,
    }


def _avg(window: dict, key: str, current):
    """Vensterwaarde als er genoeg historie is, anders de actuele meting."""
    if window and window.get("n", 3) >= 3 and window.get(key) is not None:
        return window[key]
    return current


def evaluate(snap: dict, db, th: Thresholds, ts: int) -> list[dict]:
    out: list[dict] = []
    devices = {d["mac"]: d for d in snap["devices"]}
    name = lambda mac: devices.get(mac, {}).get("name", mac or "?")  # noqa: E731

    cwin = db.client_window(ts - WINDOW)
    roams = db.client_roams(ts - HOUR)
    rwin = db.radio_window(ts - WINDOW)
    pwin = db.port_window(ts - HOUR)
    wwin = db.wan_window(ts - WINDOW)
    whour = db.wan_window(ts - HOUR)
    reboots = db.event_counts(ts - 24 * HOUR, "device_reboot")

    # ------------------------------------------------------------ clients
    for c in snap["clients"]:
        if c["wired"]:
            continue
        w = cwin.get(c["mac"], {})
        sig = _avg(w, "sig", c["signal"])
        rt = _avg(w, "rt", c.get("retry_pct"))
        sat = _avg(w, "sat", c["satisfaction"])
        rate = _avg(w, "rate", c["tx_rate_mbps"])
        ap, band = name(c["ap_mac"]), c["band"]
        where = f"{ap} · {band} GHz"
        flagged = False

        sig_warn, sig_crit = signal_limits(th, band)
        if sig is not None and sig <= sig_warn:
            sev = "critical" if sig <= sig_crit else "warning"
            adv = ("Het apparaat zit te ver van het access point of er zit veel muur/metaal tussen. "
                   "Verplaats het apparaat of de AP, of plaats een extra AP dichterbij.")
            if band == "2.4":
                adv += " Bij IoT-apparaten op 2.4 GHz helpt een AP in dezelfde ruimte vaak het meest."
            out.append(_issue(f"client_signal:{c['mac']}", sev, "wifi", "client", c["mac"],
                              f"{c['name']}: zwak signaal",
                              f"Gemiddeld {sig:.0f} dBm op {where} (drempel {sig_warn:.0f} dBm).",
                              adv, "signal", sig, sig_warn, c["ap_mac"], c["mac"]))
            flagged = True

        if rt is not None and rt >= th.client_retry_warn:
            sev = "critical" if rt >= th.client_retry_crit else "warning"
            if sig is not None and sig > sig_warn:
                adv = (f"Het signaal is op zich voldoende ({sig:.0f} dBm), dus de retries komen waarschijnlijk door "
                       f"storing, een vol kanaal op {where} of een energiezuinige wifi-chip. Kijk naar de kanaalbezetting "
                       f"van die radio en of andere clients daar ook last van hebben.")
            else:
                adv = "Retries komen hier vooral door het zwakke signaal: pakketten moeten opnieuw verstuurd worden."
            out.append(_issue(f"client_retry:{c['mac']}", sev, "wifi", "client", c["mac"],
                              f"{c['name']}: veel wifi-retries",
                              f"{rt:.0f}% van de pakketten moest opnieuw verstuurd worden op {where}.",
                              adv, "retry_pct", rt, th.client_retry_warn, c["ap_mac"], c["mac"]))
            flagged = True

        n_roam = roams.get(c["mac"], 0)
        if n_roam >= th.client_roams_per_hour:
            out.append(_issue(f"client_roam:{c['mac']}", "warning", "wifi", "client", c["mac"],
                              f"{c['name']}: wisselt steeds van access point",
                              f"{n_roam}× van AP gewisseld in het afgelopen uur (nu op {ap}).",
                              "Het apparaat ziet twee AP's met ongeveer even sterk signaal. Verlaag het zendvermogen "
                              "van één van beide, of stel een minimum-RSSI in. Statische apparaten (speakers, TV) "
                              "kun je ook aan één AP vastzetten.",
                              "roams", n_roam, th.client_roams_per_hour, c["ap_mac"], c["mac"]))
            flagged = True

        if (rate is not None and sig is not None and band in ("5", "6")
                and sig > GOOD_SIGNAL and rate < th.client_low_rate_mbps):
            out.append(_issue(f"client_rate:{c['mac']}", "info", "wifi", "client", c["mac"],
                              f"{c['name']}: lage snelheid ondanks goed signaal",
                              f"Linksnelheid {rate:.0f} Mbit/s bij {sig:.0f} dBm op {where}.",
                              "Vaak een energiebesparende stand of een oudere wifi-chip. Controleer stuurprogramma's "
                              "of de kanaalbreedte van de AP.",
                              "tx_rate", rate, th.client_low_rate_mbps, c["ap_mac"], c["mac"]))
            flagged = True

        if not flagged and sat is not None and sat < th.client_satisfaction_warn:
            sev = "critical" if sat < th.client_satisfaction_crit else "warning"
            out.append(_issue(f"client_sat:{c['mac']}", sev, "wifi", "client", c["mac"],
                              f"{c['name']}: slechte wifi-ervaring",
                              f"Satisfaction-score {sat:.0f}/100 op {where}, zonder duidelijke oorzaak in signaal of retries.",
                              "Kijk naar de kanaalbezetting van de AP en naar storing in de buurt.",
                              "satisfaction", sat, th.client_satisfaction_warn, c["ap_mac"], c["mac"]))

    # ------------------------------------------------------------ devices
    aps = [d for d in snap["devices"] if d["type"] == "ap" and d["state"] == "online"]
    for d in snap["devices"]:
        mac, dn = d["mac"], d["name"]
        if d["state"] != "online":
            out.append(_issue(f"dev_state:{mac}", "critical", "device", "device", mac, f"{dn} is {d['state']}",
                              f"{d['model']} ({d['ip'] or 'geen IP'}) is niet online.",
                              "Controleer stroom/PoE en de uplinkkabel. Zie ook de events-tijdlijn.",
                              device_mac=mac))
            continue
        if d["upgradable"]:
            out.append(_issue(f"dev_fw:{mac}", "info", "device", "device", mac, f"{dn}: firmware-update beschikbaar",
                              f"Huidig {d['version']}" + (f", beschikbaar {d['upgrade_to']}" if d["upgrade_to"] else "") + ".",
                              "Plan de update op een rustig moment; het apparaat herstart daarbij.", device_mac=mac))
        for metric, val, lim, label in (("cpu", d["cpu"], th.device_cpu_warn, "CPU"),
                                        ("mem", d["mem"], th.device_mem_warn, "geheugen"),
                                        ("temp", d["temp"], th.device_temp_warn, "temperatuur")):
            if val is not None and val >= lim:
                unit = "°C" if metric == "temp" else "%"
                out.append(_issue(f"dev_{metric}:{mac}", "warning", "device", "device", mac, f"{dn}: hoge {label}",
                                  f"{label.capitalize()} {val:.0f}{unit} (drempel {lim:.0f}{unit}).",
                                  "Zorg voor ventilatie." if metric == "temp" else "Blijft dit hoog, dan helpt een herstart of firmware-update vaak.",
                                  metric, val, lim, mac))
        if reboots.get(mac):
            out.append(_issue(f"dev_reboot:{mac}", "warning", "device", "device", mac, f"{dn} is herstart",
                              f"{reboots[mac]}× herstart in de afgelopen 24 uur.",
                              "Gebeurde dit niet door een update? Controleer dan de stroomvoorziening of PoE-budget.",
                              device_mac=mac))
        if d["poe_budget_w"] and d["poe_used_w"] is not None:
            pct = 100 * d["poe_used_w"] / d["poe_budget_w"]
            if pct >= th.poe_budget_warn:
                out.append(_issue(f"dev_poe:{mac}", "warning", "switch", "device", mac, f"{dn}: PoE-budget bijna vol",
                                  f"{d['poe_used_w']:.0f} van {d['poe_budget_w']:.0f} W in gebruik ({pct:.0f}%).",
                                  "Bij een vol budget schakelt de switch poorten uit. Verplaats een PoE-apparaat naar "
                                  "een andere switch of gebruik een injector.",
                                  "poe_pct", pct, th.poe_budget_warn, mac))

        # ---------------------------------------------------------- radios
        for r in d["radios"]:
            rid = f"{mac}@{r['radio']}"
            w = rwin.get((mac, r["radio"]), {})
            cu = _avg(w, "cu", r["cu_total"])
            intf = _avg(w, "intf", r["interference"])
            rrt = _avg(w, "rt", r.get("retry_pct"))
            where = f"{dn} · {r['radio']} GHz (kanaal {r['channel']})"
            if cu is not None and cu >= th.radio_cu_warn:
                sev = "critical" if cu >= th.radio_cu_crit else "warning"
                if intf is not None and intf >= cu / 2:
                    adv = (f"Het grootste deel ({intf:.0f}%) komt van andere netwerken in de buurt. "
                           + ("Probeer een ander kanaal (1, 6 of 11) en houd 20 MHz breedte aan."
                              if r["radio"] == "2.4" else "Kies een rustiger kanaal of verklein de kanaalbreedte."))
                else:
                    adv = "Vooral eigen verkeer: veel of drukke clients. Stuur apparaten naar 5/6 GHz of voeg een AP toe."
                out.append(_issue(f"radio_cu:{rid}", sev, "wifi", "radio", rid, f"{dn}: {r['radio']} GHz-kanaal erg druk",
                                  f"Kanaalbezetting {cu:.0f}% op {where}.", adv, "cu_total", cu, th.radio_cu_warn, mac))
            elif intf is not None and intf >= th.radio_interference_warn:
                out.append(_issue(f"radio_intf:{rid}", "warning", "wifi", "radio", rid, f"{dn}: veel storing op {r['radio']} GHz",
                                  f"{intf:.0f}% van de zendtijd bezet door andere netwerken op {where}.",
                                  "Kies een rustiger kanaal.", "interference", intf, th.radio_interference_warn, mac))
            if rrt is not None and rrt >= th.radio_retry_warn and r["num_clients"] >= th.radio_retry_min_clients:
                out.append(_issue(f"radio_retry:{rid}", "warning", "wifi", "radio", rid, f"{dn}: veel retries op {r['radio']} GHz",
                                  f"{rrt:.0f}% retries over alle clients op {where}.",
                                  "Kijk welke clients op deze radio slecht scoren; vaak is één zwak apparaat de oorzaak.",
                                  "retry_pct", rrt, th.radio_retry_warn, mac))
            if r["radio"] == "2.4" and r["channel"] and r["channel"] not in STANDARD_24:
                out.append(_issue(f"radio_ch:{rid}", "warning", "wifi", "radio", rid, f"{dn}: 2.4 GHz op kanaal {r['channel']}",
                                  "Kanalen buiten 1, 6 en 11 overlappen met twee kanalen tegelijk.",
                                  "Zet deze radio op kanaal 1, 6 of 11.", device_mac=mac))

        # ----------------------------------------------------------- ports
        for p in d["ports"]:
            pid = f"{mac}#{p['idx']}"
            w = pwin.get((mac, p["idx"]), {})
            where = f"{dn} · {p['name']}"
            span = max(60, (w.get("t1") or ts) - (w.get("t0") or ts))
            err_h = (w.get("err") or 0) * HOUR / span
            if err_h >= th.port_errors_per_hour:
                out.append(_issue(f"port_err:{pid}", "warning", "switch", "port", pid, f"{where}: pakketfouten",
                                  f"Ongeveer {err_h:.0f} fouten per uur op deze poort.",
                                  "Meestal een slechte kabel of connector. Vervang de patchkabel of probeer een andere poort.",
                                  "errors_h", err_h, th.port_errors_per_hour, mac))
            flaps = w.get("flaps", 0)
            if flaps >= th.port_flaps_per_hour:
                out.append(_issue(f"port_flap:{pid}", "warning", "switch", "port", pid, f"{where}: link valt steeds weg",
                                  f"{flaps}× link-down in het afgelopen uur.",
                                  "Controleer kabel, connector en of het aangesloten apparaat herstart (stroom/PoE).",
                                  "flaps", flaps, th.port_flaps_per_hour, mac))
            if p["up"] and p["media"] in ("GE", "2P5GE", "2.5GE", "5GE", "10GE") and 0 < p["speed"] < 1000:
                # Stabiele 100 Mbit-link is vaak gewoon een simpel apparaat; met fouten erbij is het een kabelprobleem.
                bad = err_h >= th.port_errors_per_hour or flaps >= th.port_flaps_per_hour
                out.append(_issue(f"port_speed:{pid}", "warning" if bad else "info", "switch", "port", pid,
                                  f"{where}: maar {int(p['speed'])} Mbit/s",
                                  "Deze gigabit-poort onderhandelt een lagere snelheid"
                                  + (" én geeft fouten." if bad else "."),
                                  "Gigabit heeft alle 4 aderparen nodig; vaak is één ader stuk of zit de stekker niet goed. "
                                  "Kan het aangesloten apparaat zelf geen gigabit (P1-meter, deurbel, IoT), dan is dit normaal.",
                                  "speed", p["speed"], 1000, mac))
            if p["up"] and p["full_duplex"] is False:
                out.append(_issue(f"port_duplex:{pid}", "warning", "switch", "port", pid, f"{where}: half-duplex",
                                  "Half-duplex veroorzaakt botsingen en trage verbindingen.",
                                  "Zet beide kanten op auto-negotiation en vervang de kabel.", device_mac=mac))

    # AP-belasting ongelijk verdeeld
    if len(aps) >= 2:
        avg = sum(a["num_clients"] for a in aps) / len(aps)
        for a in aps:
            if a["num_clients"] >= 15 and a["num_clients"] > 2 * avg:
                out.append(_issue(f"ap_load:{a['mac']}", "info", "wifi", "device", a["mac"], f"{a['name']}: draagt de meeste clients",
                                  f"{a['num_clients']} clients tegen gemiddeld {avg:.0f} per AP.",
                                  "Overweeg band steering of iets lager zendvermogen zodat clients beter spreiden.",
                                  "num_clients", a["num_clients"], round(2 * avg), a["mac"]))

    # ----------------------------------------------------------------- WAN
    wan = snap["wan"]
    gw = next((d["mac"] for d in snap["devices"] if d["type"] == "gateway"), None)
    if wan["up"] is False:
        out.append(_issue("wan_down", "critical", "wan", "wan", "wan", "Internetverbinding is weg",
                          "De gateway meldt de WAN-verbinding als niet actief.",
                          "Controleer modem/ONT en de WAN-kabel naar de UXG.", device_mac=gw))
    lat = _avg(wwin, "lat", wan["latency_ms"])
    if lat is not None and lat >= th.wan_latency_warn:
        sev = "critical" if lat >= th.wan_latency_crit else "warning"
        out.append(_issue("wan_latency", sev, "wan", "wan", "wan", "Hoge internetlatency",
                          f"Gemiddeld {lat:.0f} ms over de laatste 15 minuten.",
                          "Kijk of er een grote download/back-up loopt; anders ligt het waarschijnlijk bij de provider.",
                          "latency_ms", lat, th.wan_latency_warn, gw))
    elif whour.get("lat_max") and whour["lat_max"] >= th.wan_latency_crit:
        spikes = db.q("SELECT COUNT(*) n FROM wan_samples WHERE ts>=? AND latency_ms>=?",
                      (ts - HOUR, th.wan_latency_crit))[0]["n"]
        if spikes >= 2:
            out.append(_issue("wan_spikes", "info", "wan", "wan", "wan", "Af en toe latency-pieken",
                              f"{spikes} metingen boven {th.wan_latency_crit:.0f} ms in het afgelopen uur (max {whour['lat_max']:.0f} ms).",
                              "Merkbaar bij videobellen en gamen. Houd het in de gaten; blijft het, meld het bij de provider.",
                              "latency_max", whour["lat_max"], th.wan_latency_crit, gw))
    loss = _avg(wwin, "loss", wan["loss_pct"])
    if loss is not None and loss >= th.wan_drops_warn:
        out.append(_issue("wan_loss", "warning", "wan", "wan", "wan", "Pakketverlies op internet",
                          f"Gemiddeld {loss:.1f}% verlies over de laatste 15 minuten.",
                          "Controleer de kabel tussen modem en UXG; blijft het, neem contact op met de provider.",
                          "loss_pct", loss, th.wan_drops_warn, gw))

    # ------------------------------------------------------------ IPS (eigen apparaten)
    by_src: dict[str, list[dict]] = {}
    for e in db.ips_events(ts - 24 * HOUR, "internal"):
        by_src.setdefault(e["src_ip"], []).append(e)
    cli_by_ip = {c["ip"]: c for c in snap["clients"] if c.get("ip")}
    for ip, evs in by_src.items():
        c = cli_by_ip.get(ip)
        who = c["name"] if c else (evs[0].get("src_name") if evs[0].get("src_name") != ip else None)
        label = f"{who} ({ip})" if who else ip
        sigs: dict[str, int] = {}
        for e in evs:
            sigs[e["signature"]] = sigs.get(e["signature"], 0) + 1
        top = max(sigs, key=sigs.get)
        from .unifi_client import _name
        targets = sorted({f"{_name(e.get('dst_name'), e['dst_ip'])}:{e['dst_port']}" for e in evs})
        via = f" via {evs[0]['src_net']}" if evs[0].get("src_net") else ""
        out.append(_issue(f"ips_internal:{ip}", "warning", "security", "client" if c else "ip", ip,
                          f"{label}: geblokkeerd door IPS",
                          f"{len(evs)}× geblokkeerd in 24 uur{via}, vooral '{top}'"
                          + (f" (+{len(sigs) - 1} andere regels)" if len(sigs) > 1 else "")
                          + f", naar {', '.join(targets[:3])}{'…' if len(targets) > 3 else ''}.",
                          "Een eigen apparaat dat IPS-regels raakt is óf verkeerd geconfigureerd of besmet, óf een vals "
                          "alarm (bijvoorbeeld 'GPL WEB_SERVER DELETE attempt' bij een gewone web-API, of een SSH-scanregel "
                          "door veel verbindingen). Controleer wat het apparaat deed; is het onschuldig, maak in UniFi dan "
                          "een uitzondering voor deze regel en dit adres, of negeer de melding hier.",
                          "ips_blocks", len(evs), 1, None, c["mac"] if c else None))

    _sticky_after_restart(out, snap, db, th, ts, name)
    _group_coverage(out, snap, name)
    out.sort(key=lambda i: (SEVERITY_ORDER[i["severity"]], i["category"], i["title"]))
    return out


STICKY_LOOKBACK = 7 * 24 * HOUR      # herstarts tot een week terug
STICKY_AFTER = 15 * 60               # clients die tot 15 min na de herstart (opnieuw) verbonden
STICKY_GAIN_DB = 8                   # vóór de herstart minstens zoveel dB beter = duidelijk bewijs


def _restart_clusters(snap: dict, ts: int) -> list[dict]:
    """Herstarts van gateway/switches/AP's, samengevoegd als ze binnen 5 minuten vielen
    (een gateway-herstart neemt de AP's erachter mee)."""
    boots = sorted(((ts - d["uptime"], d) for d in snap["devices"]
                    if d["state"] == "online" and 0 < d["uptime"] < STICKY_LOOKBACK), key=lambda x: x[0])
    clusters: list[dict] = []
    for bt, d in boots:
        if clusters and bt - clusters[-1]["end"] <= 300:
            clusters[-1]["end"] = bt
            clusters[-1]["devices"].append(d)
        else:
            clusters.append({"start": bt, "end": bt, "devices": [d]})
    return clusters


def _sticky_after_restart(out: list[dict], snap: dict, db, th: Thresholds, ts: int, name) -> None:
    """Wifi-clients die kort na een herstart op een (verre) AP terechtkwamen en daar blijven hangen:
    zuinige IoT-apparaten zoeken pas opnieuw als hun verbinding helemaal wegvalt."""
    days = ["ma", "di", "wo", "do", "vr", "za", "zo"]

    def when(t: float) -> str:
        lt = time.localtime(t)
        return f"{days[lt.tm_wday]} {time.strftime('%H:%M', lt)}"

    order = {"gateway": 0, "switch": 1, "ap": 2}
    for cl in _restart_clusters(snap, ts):
        restarted = {d["mac"] for d in cl["devices"]}
        who = [d["name"] for d in sorted(cl["devices"], key=lambda d: order.get(d["type"], 3))]
        names = who[0] if len(who) == 1 else ", ".join(who[:-1]) + " en " + who[-1]
        gkey = f"sticky_restart:{cl['devices'][0]['mac']}:{int(cl['start'] // 60)}"
        members = []
        for c in snap["clients"]:
            a = c.get("assoc_ts")
            if c["wired"] or not a or c["signal"] is None or not (cl["start"] - 60 <= a <= cl["end"] + STICKY_AFTER):
                continue
            warn, _ = signal_limits(th, c["band"])
            before = db.client_before(c["mac"], int(cl["start"]) - 6 * HOUR, int(cl["start"]) - 60)
            if before and before["ap_mac"] != c["ap_mac"] and before["sig"] - c["signal"] >= STICKY_GAIN_DB:
                sev, why = "warning", (f"Zat vóór de herstart op {name(before['ap_mac'])} met {before['sig']:.0f} dBm, "
                                        f"nu op {name(c['ap_mac'])} met {c['signal']:.0f} dBm.")
            elif not before and c["signal"] <= warn and c["ap_mac"] not in restarted:
                sev, why = "info", (f"Verbond {when(a)} met {name(c['ap_mac'])} en zit daar op {c['signal']:.0f} dBm; "
                                    f"mogelijk hoort het bij een AP die toen even weg was.")
            else:
                continue
            members.append(_issue(f"sticky:{c['mac']}", sev, "wifi", "client", c["mac"],
                                  f"{c['name']}: blijft hangen op {name(c['ap_mac'])}", why,
                                  "Opnieuw verbinden laat het apparaat zelf de beste AP kiezen.",
                                  "signal", c["signal"], warn, c["ap_mac"], c["mac"]))
        if not members:
            continue
        for m in members:
            m["group"] = gkey
            m["reconnect"] = True
        out.extend(members)
        sev = min((m["severity"] for m in members), key=SEVERITY_ORDER.get)
        n = len(members)
        out.append(_issue(gkey, sev, "wifi", "restart", gkey,
                          f"Na herstart van {names} ({when(cl['start'])}): {n} apparaat{'en' if n > 1 else ''} op een verre AP",
                          f"{', '.join(m['title'].split(':')[0] for m in members[:6])}{'…' if n > 6 else ''}.",
                          "Deze apparaten maakten verbinding terwijl hun eigen AP even weg was, en wisselen niet uit "
                          "zichzelf terug: vooral zuinige IoT-apparaten zoeken pas opnieuw als hun verbinding helemaal "
                          "wegvalt. Gebruik 'Opnieuw verbinden' per apparaat. Gebeurt dit vaker, zet vaste apparaten dan "
                          "vast aan hun AP of stel een minimum-RSSI in op de verre AP.",
                          "clients", n, 1, cl["devices"][0]["mac"]))
        out[-1]["members"] = [m["client_mac"] for m in members]


def _group_coverage(out: list[dict], snap: dict, name) -> None:
    """Hebben ≥3 clients op dezelfde AP + band signaal/retry-problemen, dan is dat
    één dekkingsprobleem van die radio. De losse client-issues krijgen een
    verwijzing naar de groep, zodat het dashboard ze kan inklappen."""
    clients = {c["mac"]: c for c in snap["clients"]}
    groups: dict[tuple, list[dict]] = {}
    for i in out:
        if i["entity_type"] == "client" and i["metric"] in ("signal", "retry_pct", "satisfaction") and not i.get("group"):
            c = clients.get(i["client_mac"], {})
            groups.setdefault((c.get("ap_mac"), c.get("band")), []).append(i)
    for (ap, band), members in groups.items():
        macs = {m["client_mac"] for m in members}
        if not ap or len(macs) < 3:
            continue
        key = f"coverage:{ap}@{band}"
        sev = min((m["severity"] for m in members), key=SEVERITY_ORDER.get)
        weak = sum(1 for m in members if m["metric"] == "signal")
        names = sorted({clients[m]["name"] for m in macs})
        if weak >= len(macs) / 2:
            title = f"{name(ap)}: zwakke dekking op {band} GHz"
            adv = ("Meerdere apparaten op deze AP hebben een zwak signaal: de AP staat te ver weg of de dekking in "
                   "dat gebied is onvoldoende. Een extra AP of een betere plek lost dit voor al deze apparaten tegelijk op.")
        else:
            title = f"{name(ap)}: slechte wifi-kwaliteit op {band} GHz"
            adv = ("Meerdere apparaten hebben tegelijk veel retries terwijl het signaal redelijk is. Dat wijst op "
                   "storing of een vol kanaal op deze radio, niet op de apparaten zelf.")
        for m in members:
            m["group"] = key
        for i in out:   # radio-retries van dezelfde radio horen bij hetzelfde verhaal
            if i["key"] == f"radio_retry:{ap}@{band}":
                i["group"] = key
        out.append(_issue(key, sev, "wifi", "radio", f"{ap}@{band}", title,
                          f"{len(macs)} apparaten met problemen: {', '.join(names[:6])}{'…' if len(names) > 6 else ''}.",
                          adv, "clients", len(macs), 3, ap))
        out[-1]["members"] = sorted(macs)


def score(issues: list[dict]) -> int:
    return max(0, 100 - sum(PENALTY[i["severity"]] for i in issues))


def attach_scores(snap: dict, issues: list[dict]) -> None:
    n_muted = sum(1 for i in issues if i.get("muted") and not i.get("group"))
    issues = [i for i in issues if not i.get("muted")]     # genegeerd telt nergens mee
    by_dev: dict[str, list] = {}
    by_cli: dict[str, list] = {}
    for i in issues:
        if i.get("client_mac"):
            by_cli.setdefault(i["client_mac"], []).append(i)
        elif i.get("device_mac"):
            by_dev.setdefault(i["device_mac"], []).append(i)
    for d in snap["devices"]:
        own = by_dev.get(d["mac"], [])
        d["issue_count"] = len(own)
        d["client_issue_count"] = sum(1 for i in issues if i.get("client_mac") and i.get("device_mac") == d["mac"])
        d["score"] = score(own)
    for c in snap["clients"]:
        own = by_cli.get(c["mac"], [])
        c["issue_count"] = len(own)
        c["score"] = score(own)
    # Netwerkscore: per getroffen ding één keer tellen (ernstigste melding), en
    # gegroepeerde client-issues via hun groep, niet dubbel.
    worst: dict[str, str] = {}
    for i in issues:
        if i.get("group"):
            continue
        k = f"client:{i['client_mac']}" if i.get("client_mac") else i["key"]
        if k not in worst or SEVERITY_ORDER[i["severity"]] < SEVERITY_ORDER[worst[k]]:
            worst[k] = i["severity"]
    crit = sum(v == "critical" for v in worst.values())
    warn = sum(v == "warning" for v in worst.values())
    info = sum(v == "info" for v in worst.values())
    snap["health"] = {"score": max(0, min(100, 100 - 12 * crit - 4 * warn - 1 * info)),
                      "critical": crit, "warning": warn, "info": info, "total": len(issues), "muted": n_muted}
