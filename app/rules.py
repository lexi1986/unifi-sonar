"""Issue-detectie: zet ruwe metingen + recente historie om in begrijpelijke
problemen met ernst, uitleg en advies.

Regels kijken naar het gemiddelde over een venster (standaard 15 min) in plaats
van naar één meting, zodat een enkele uitschieter geen alarm geeft.
"""
from __future__ import annotations

import time

from . import segments
from .config import Thresholds
from .i18n import L

WINDOW = 15 * 60
HOUR = 3600
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
PENALTY = {"critical": 40, "warning": 15, "info": 3}
GOOD_SIGNAL = -65
STANDARD_24 = {1, 6, 11}


# Tijdelijke toestanden: geen alarm, behalve als het te lang duurt.
TRANSIENT = {"upgrading": ("wordt bijgewerkt", "is updating"), "provisioning": ("wordt ingesteld", "is provisioning"),
             "adopting": ("wordt geadopteerd", "is being adopted")}
TRANSIENT_MAX = 20 * 60
QUIET_MIN_DEVICES = 3       # "controller hoort niets": minstens zoveel apparaten
QUIET_FRACTION = 0.6        # ... en dit deel van alle apparaten tegelijk weg


def ips_ignored(e: dict, ignores: list[dict]) -> bool:
    """Valt een IPS-blokkade onder een negeerregel (adres, regel of de combinatie)?"""
    for r in ignores:
        if (r["ip"] is None or r["ip"] == e.get("src_ip")) and (r["sid"] is None or r["sid"] == e.get("sid")):
            return True
    return False


def signal_limits(th: Thresholds, band: str | None) -> tuple[float, float]:
    if band == "2.4":
        return th.client_signal_warn_24, th.client_signal_crit_24
    return th.client_signal_warn, th.client_signal_crit


def _issue(key, severity, category, entity_type, entity_id, title, detail, advice,
           metric=None, value=None, threshold=None, device_mac=None, client_mac=None, last_ts=None) -> dict:
    """last_ts: wanneer het onderliggende voorval (herstart, blokkade, linkverlies…) het laatst gebeurde."""
    return {
        "key": key, "severity": severity, "category": category, "entity_type": entity_type,
        "entity_id": entity_id, "title": title, "detail": detail, "advice": advice,
        "metric": metric, "value": None if value is None else round(value, 1),
        "threshold": threshold, "device_mac": device_mac, "client_mac": client_mac, "last_ts": last_ts,
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
    reboot_ts = db.event_last(ts - 24 * HOUR, "device_reboot")

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
            adv = L("Het apparaat zit te ver van het access point of er zit veel muur/metaal tussen. "
                    "Verplaats het apparaat of de AP, of plaats een extra AP dichterbij.",
                    "The device is too far from the access point or there is a lot of wall/metal in between. "
                    "Move the device or the AP, or add an extra AP closer by.")
            if band == "2.4":
                adv += L(" Bij IoT-apparaten op 2.4 GHz helpt een AP in dezelfde ruimte vaak het meest.",
                         " For IoT devices on 2.4 GHz, an AP in the same room usually helps most.")
            if c.get("fixed_ap") and c["fixed_ap"] == c["ap_mac"]:
                adv = L(f"Dit apparaat staat in UniFi vastgezet aan {ap}. Controleer of dat de dichtstbijzijnde AP is; "
                        "zo niet, zet het vast aan de goede AP of haal de vergrendeling weg.",
                        f"This device is locked to {ap} in UniFi. Check whether that is the nearest AP; "
                        "if not, lock it to the right AP or remove the lock.")
            out.append(_issue(f"client_signal:{c['mac']}", sev, "wifi", "client", c["mac"],
                              L(f"{c['name']}: zwak signaal", f"{c['name']}: weak signal"),
                              L(f"Gemiddeld {sig:.0f} dBm op {where} (drempel {sig_warn:.0f} dBm).",
                                f"Average {sig:.0f} dBm on {where} (threshold {sig_warn:.0f} dBm)."),
                              adv, "signal", sig, sig_warn, c["ap_mac"], c["mac"]))
            flagged = True

        if rt is not None and rt >= th.client_retry_warn:
            sev = "critical" if rt >= th.client_retry_crit else "warning"
            if sig is not None and sig > sig_warn:
                adv = L(f"Het signaal is op zich voldoende ({sig:.0f} dBm), dus de retries komen waarschijnlijk door "
                        f"storing, een vol kanaal op {where} of een energiezuinige wifi-chip. Kijk naar de kanaalbezetting "
                        f"van die radio en of andere clients daar ook last van hebben.",
                        f"The signal itself is fine ({sig:.0f} dBm), so the retries probably come from interference, "
                        f"a busy channel on {where} or a power-saving wifi chip. Look at the channel utilization of that "
                        f"radio and whether other clients there are affected too.")
            else:
                adv = L("Retries komen hier vooral door het zwakke signaal: pakketten moeten opnieuw verstuurd worden.",
                        "Here the retries mainly come from the weak signal: packets have to be sent again.")
            out.append(_issue(f"client_retry:{c['mac']}", sev, "wifi", "client", c["mac"],
                              L(f"{c['name']}: veel wifi-retries", f"{c['name']}: many wifi retries"),
                              L(f"{rt:.0f}% van de pakketten moest opnieuw verstuurd worden op {where}.",
                                f"{rt:.0f}% of the packets had to be resent on {where}."),
                              adv, "retry_pct", rt, th.client_retry_warn, c["ap_mac"], c["mac"]))
            flagged = True

        roam = roams.get(c["mac"]) or {}
        n_roam = roam.get("n", 0)
        if n_roam >= th.client_roams_per_hour:
            out.append(_issue(f"client_roam:{c['mac']}", "warning", "wifi", "client", c["mac"],
                              L(f"{c['name']}: wisselt steeds van access point", f"{c['name']}: keeps switching access points"),
                              L(f"{n_roam}× van AP gewisseld in het afgelopen uur (nu op {ap}).",
                                f"Switched AP {n_roam}× in the past hour (now on {ap})."),
                              L("Het apparaat ziet twee AP's met ongeveer even sterk signaal. Verlaag het zendvermogen "
                                "van één van beide, of stel een minimum-RSSI in. Statische apparaten (speakers, TV) "
                                "kun je ook aan één AP vastzetten.",
                                "The device sees two APs with about equally strong signal. Lower the transmit power of "
                                "one of them, or set a minimum RSSI. Stationary devices (speakers, TV) can also be "
                                "locked to one AP."),
                              "roams", n_roam, th.client_roams_per_hour, c["ap_mac"], c["mac"], roam.get("last")))
            flagged = True

        if (rate is not None and sig is not None and band in ("5", "6")
                and sig > GOOD_SIGNAL and rate < th.client_low_rate_mbps):
            out.append(_issue(f"client_rate:{c['mac']}", "info", "wifi", "client", c["mac"],
                              L(f"{c['name']}: lage snelheid ondanks goed signaal", f"{c['name']}: low speed despite good signal"),
                              L(f"Linksnelheid {rate:.0f} Mbit/s bij {sig:.0f} dBm op {where}.",
                                f"Link rate {rate:.0f} Mbit/s at {sig:.0f} dBm on {where}."),
                              L("Vaak een energiebesparende stand of een oudere wifi-chip. Controleer stuurprogramma's "
                                "of de kanaalbreedte van de AP.",
                                "Often a power-saving mode or an older wifi chip. Check the drivers or the channel "
                                "width of the AP."),
                              "tx_rate", rate, th.client_low_rate_mbps, c["ap_mac"], c["mac"]))
            flagged = True

        if not flagged and sat is not None and sat < th.client_satisfaction_warn:
            sev = "critical" if sat < th.client_satisfaction_crit else "warning"
            out.append(_issue(f"client_sat:{c['mac']}", sev, "wifi", "client", c["mac"],
                              L(f"{c['name']}: slechte wifi-ervaring", f"{c['name']}: poor wifi experience"),
                              L(f"Satisfaction-score {sat:.0f}/100 op {where}, zonder duidelijke oorzaak in signaal of retries.",
                                f"Satisfaction score {sat:.0f}/100 on {where}, with no clear cause in signal or retries."),
                              L("Kijk naar de kanaalbezetting van de AP en naar storing in de buurt.",
                                "Look at the channel utilization of the AP and at interference nearby."),
                              "satisfaction", sat, th.client_satisfaction_warn, c["ap_mac"], c["mac"]))

    # ------------------------------------------------------------ devices
    aps = [d for d in snap["devices"] if d["type"] == "ap" and d["state"] == "online"]
    upgrades = db.event_counts(ts - 24 * HOUR, "device_upgrade")
    for d in snap["devices"]:
        mac, dn = d["mac"], d["name"]
        if d["state"] in TRANSIENT:
            since = db.last_state_ts(mac) or ts
            long = ts - since > TRANSIENT_MAX
            out.append(_issue(f"dev_state:{mac}", "warning" if long else "info", "device", "device", mac,
                              f"{dn} {L(*TRANSIENT[d['state']])}" + (L(" en blijft hangen", " and is stuck") if long else ""),
                              L(f"{d['model']} is al {round((ts - since) / 60)} minuten bezig.",
                                f"{d['model']} has been busy for {round((ts - since) / 60)} minutes.") if long
                              else L(f"{d['model']} is tijdelijk niet beschikbaar; dit duurt meestal een paar minuten.",
                                     f"{d['model']} is temporarily unavailable; this usually takes a few minutes."),
                              L("Duurt het langer dan een half uur, herstart het apparaat dan via UniFi of door de stroom/PoE "
                                "even los te halen.", "If it takes longer than half an hour, restart the device via UniFi "
                                "or by briefly disconnecting power/PoE.") if long
                              else L("Niets doen: het apparaat komt vanzelf terug.", "Nothing to do: the device comes back by itself."),
                              device_mac=mac))
            continue
        if d["state"] != "online":
            out.append(_issue(f"dev_state:{mac}", "critical", "device", "device", mac, f"{dn} is {d['state']}",
                              L(f"{d['model']} ({d['ip'] or 'geen IP'}) is niet online.",
                                f"{d['model']} ({d['ip'] or 'no IP'}) is not online."),
                              L("Controleer stroom/PoE en de uplinkkabel. Zie ook de events-tijdlijn.",
                                "Check power/PoE and the uplink cable. See also the event timeline."),
                              device_mac=mac))
            continue
        if d["upgradable"]:
            out.append(_issue(f"dev_fw:{mac}", "info", "device", "device", mac,
                              L(f"{dn}: firmware-update beschikbaar", f"{dn}: firmware update available"),
                              L(f"Huidig {d['version']}", f"Current {d['version']}")
                              + (L(f", beschikbaar {d['upgrade_to']}", f", available {d['upgrade_to']}") if d["upgrade_to"] else "") + ".",
                              L("Plan de update op een rustig moment; het apparaat herstart daarbij.",
                                "Schedule the update at a quiet moment; the device restarts during it."), device_mac=mac))
        for metric, val, lim, label in (("cpu", d["cpu"], th.device_cpu_warn, "CPU"),
                                        ("mem", d["mem"], th.device_mem_warn, L("geheugen", "memory")),
                                        ("temp", d["temp"], th.device_temp_warn, L("temperatuur", "temperature"))):
            if val is not None and val >= lim:
                unit = "°C" if metric == "temp" else "%"
                out.append(_issue(f"dev_{metric}:{mac}", "warning", "device", "device", mac,
                                  L(f"{dn}: hoge {label}", f"{dn}: high {label}"),
                                  L(f"{label.capitalize()} {val:.0f}{unit} (drempel {lim:.0f}{unit}).",
                                    f"{label.capitalize()} {val:.0f}{unit} (threshold {lim:.0f}{unit})."),
                                  L("Zorg voor ventilatie.", "Make sure it is ventilated.") if metric == "temp"
                                  else L("Blijft dit hoog, dan helpt een herstart of firmware-update vaak.",
                                         "If it stays high, a restart or firmware update often helps."),
                                  metric, val, lim, mac))
        if reboots.get(mac, 0) > upgrades.get(mac, 0):   # herstarts door een firmware-update tellen niet
            out.append(_issue(f"dev_reboot:{mac}", "warning", "device", "device", mac,
                              L(f"{dn} is herstart", f"{dn} restarted"),
                              L(f"{reboots[mac]}× herstart in de afgelopen 24 uur.", f"Restarted {reboots[mac]}× in the past 24 hours."),
                              L("Gebeurde dit niet door een update? Controleer dan de stroomvoorziening of PoE-budget.",
                                "Not caused by an update? Then check the power supply or PoE budget."),
                              device_mac=mac, last_ts=reboot_ts.get(mac)))
        if d["poe_budget_w"] and d["poe_used_w"] is not None:
            pct = 100 * d["poe_used_w"] / d["poe_budget_w"]
            if pct >= th.poe_budget_warn:
                out.append(_issue(f"dev_poe:{mac}", "warning", "switch", "device", mac,
                                  L(f"{dn}: PoE-budget bijna vol", f"{dn}: PoE budget almost full"),
                                  L(f"{d['poe_used_w']:.0f} van {d['poe_budget_w']:.0f} W in gebruik ({pct:.0f}%).",
                                    f"{d['poe_used_w']:.0f} of {d['poe_budget_w']:.0f} W in use ({pct:.0f}%)."),
                                  L("Bij een vol budget schakelt de switch poorten uit. Verplaats een PoE-apparaat naar "
                                    "een andere switch of gebruik een injector.",
                                    "When the budget is full the switch turns ports off. Move a PoE device to another "
                                    "switch or use an injector."),
                                  "poe_pct", pct, th.poe_budget_warn, mac))

        # ---------------------------------------------------------- radios
        for r in d["radios"]:
            rid = f"{mac}@{r['radio']}"
            w = rwin.get((mac, r["radio"]), {})
            cu = _avg(w, "cu", r["cu_total"])
            intf = _avg(w, "intf", r["interference"])
            rrt = _avg(w, "rt", r.get("retry_pct"))
            where = L(f"{dn} · {r['radio']} GHz (kanaal {r['channel']})", f"{dn} · {r['radio']} GHz (channel {r['channel']})")
            if cu is not None and cu >= th.radio_cu_warn:
                sev = "critical" if cu >= th.radio_cu_crit else "warning"
                if intf is not None and intf >= cu / 2:
                    adv = (L(f"Het grootste deel ({intf:.0f}%) komt van andere netwerken in de buurt. ",
                             f"Most of it ({intf:.0f}%) comes from other networks nearby. ")
                           + (L("Probeer een ander kanaal (1, 6 of 11) en houd 20 MHz breedte aan.",
                                "Try another channel (1, 6 or 11) and keep 20 MHz width.")
                              if r["radio"] == "2.4" else L("Kies een rustiger kanaal of verklein de kanaalbreedte.",
                                                            "Pick a quieter channel or reduce the channel width.")))
                else:
                    adv = L("Vooral eigen verkeer: veel of drukke clients. Stuur apparaten naar 5/6 GHz of voeg een AP toe.",
                            "Mostly your own traffic: many or busy clients. Steer devices to 5/6 GHz or add an AP.")
                out.append(_issue(f"radio_cu:{rid}", sev, "wifi", "radio", rid,
                                  L(f"{dn}: {r['radio']} GHz-kanaal erg druk", f"{dn}: {r['radio']} GHz channel very busy"),
                                  L(f"Kanaalbezetting {cu:.0f}% op {where}.", f"Channel utilization {cu:.0f}% on {where}."),
                                  adv, "cu_total", cu, th.radio_cu_warn, mac))
            elif intf is not None and intf >= th.radio_interference_warn:
                out.append(_issue(f"radio_intf:{rid}", "warning", "wifi", "radio", rid,
                                  L(f"{dn}: veel storing op {r['radio']} GHz", f"{dn}: heavy interference on {r['radio']} GHz"),
                                  L(f"{intf:.0f}% van de zendtijd bezet door andere netwerken op {where}.",
                                    f"{intf:.0f}% of airtime taken by other networks on {where}."),
                                  L("Kies een rustiger kanaal.", "Pick a quieter channel."),
                                  "interference", intf, th.radio_interference_warn, mac))
            # Op een radio die bijna niets doet (bezetting < RETRY_MIN_CU) kosten retries geen zendtijd: dan is het
            # ruis van een paar apparaten die snelheden uitproberen (zoals iPhones op 6 GHz), geen probleem.
            busy = cu is None or cu >= RETRY_MIN_CU
            if rrt is not None and rrt >= th.radio_retry_warn and r["num_clients"] >= th.radio_retry_min_clients and busy:
                out.append(_issue(f"radio_retry:{rid}", "warning", "wifi", "radio", rid,
                                  L(f"{dn}: veel retries op {r['radio']} GHz", f"{dn}: many retries on {r['radio']} GHz"),
                                  L(f"{rrt:.0f}% retries over alle clients op {where}.", f"{rrt:.0f}% retries across all clients on {where}."),
                                  L("Kijk welke clients op deze radio slecht scoren; vaak is één zwak apparaat de oorzaak.",
                                    "Check which clients on this radio score poorly; often one weak device is the cause."),
                                  "retry_pct", rrt, th.radio_retry_warn, mac))
            if r["radio"] == "2.4" and r["channel"] and r["channel"] not in STANDARD_24:
                out.append(_issue(f"radio_ch:{rid}", "warning", "wifi", "radio", rid,
                                  L(f"{dn}: 2.4 GHz op kanaal {r['channel']}", f"{dn}: 2.4 GHz on channel {r['channel']}"),
                                  L("Kanalen buiten 1, 6 en 11 overlappen met twee kanalen tegelijk.",
                                    "Channels other than 1, 6 and 11 overlap with two channels at once."),
                                  L("Zet deze radio op kanaal 1, 6 of 11.", "Set this radio to channel 1, 6 or 11."), device_mac=mac))

        # ----------------------------------------------------------- ports
        for p in d["ports"]:
            pid = f"{mac}#{p['idx']}"
            w = pwin.get((mac, p["idx"]), {})
            where = f"{dn} · {p['name']}"
            span = max(60, (w.get("t1") or ts) - (w.get("t0") or ts))
            err_h = (w.get("err") or 0) * HOUR / span
            if err_h >= th.port_errors_per_hour:
                out.append(_issue(f"port_err:{pid}", "warning", "switch", "port", pid, L(f"{where}: pakketfouten", f"{where}: packet errors"),
                                  L(f"Ongeveer {err_h:.0f} fouten per uur op deze poort.", f"About {err_h:.0f} errors per hour on this port."),
                                  L("Meestal een slechte kabel of connector. Vervang de patchkabel of probeer een andere poort.",
                                    "Usually a bad cable or connector. Replace the patch cable or try another port."),
                                  "errors_h", err_h, th.port_errors_per_hour, mac))
            flaps = w.get("flaps", 0)
            if flaps >= th.port_flaps_per_hour:
                out.append(_issue(f"port_flap:{pid}", "warning", "switch", "port", pid,
                                  L(f"{where}: link valt steeds weg", f"{where}: link keeps dropping"),
                                  L(f"{flaps}× link-down in het afgelopen uur.", f"{flaps}× link down in the past hour."),
                                  L("Controleer kabel, connector en of het aangesloten apparaat herstart (stroom/PoE).",
                                    "Check the cable, connector and whether the connected device restarts (power/PoE)."),
                                  "flaps", flaps, th.port_flaps_per_hour, mac, last_ts=w.get("flap_ts")))
            if p["up"] and p["media"] in ("GE", "2P5GE", "2.5GE", "5GE", "10GE") and 0 < p["speed"] < 1000:
                # Stabiele 100 Mbit-link is vaak gewoon een simpel apparaat; met fouten erbij is het een kabelprobleem.
                bad = err_h >= th.port_errors_per_hour or flaps >= th.port_flaps_per_hour
                out.append(_issue(f"port_speed:{pid}", "warning" if bad else "info", "switch", "port", pid,
                                  L(f"{where}: maar {int(p['speed'])} Mbit/s", f"{where}: only {int(p['speed'])} Mbit/s"),
                                  L("Deze gigabit-poort onderhandelt een lagere snelheid", "This gigabit port negotiates a lower speed")
                                  + (L(" én geeft fouten.", " and has errors.") if bad else "."),
                                  L("Gigabit heeft alle 4 aderparen nodig; vaak is één ader stuk of zit de stekker niet goed. "
                                    "Kan het aangesloten apparaat zelf geen gigabit (P1-meter, deurbel, IoT), dan is dit normaal.",
                                    "Gigabit needs all 4 wire pairs; often one wire is broken or the plug is not seated well. "
                                    "If the connected device cannot do gigabit itself (smart meter, doorbell, IoT), this is normal."),
                                  "speed", p["speed"], 1000, mac))
            if p["up"] and p["full_duplex"] is False:
                out.append(_issue(f"port_duplex:{pid}", "warning", "switch", "port", pid, f"{where}: half-duplex",
                                  L("Half-duplex veroorzaakt botsingen en trage verbindingen.",
                                    "Half duplex causes collisions and slow connections."),
                                  L("Zet beide kanten op auto-negotiation en vervang de kabel.",
                                    "Set both sides to auto-negotiation and replace the cable."), device_mac=mac))

    # AP-belasting ongelijk verdeeld
    if len(aps) >= 2:
        avg = sum(a["num_clients"] for a in aps) / len(aps)
        for a in aps:
            if a["num_clients"] >= 15 and a["num_clients"] > 2 * avg:
                out.append(_issue(f"ap_load:{a['mac']}", "info", "wifi", "device", a["mac"],
                                  L(f"{a['name']}: draagt de meeste clients", f"{a['name']}: carries most clients"),
                                  L(f"{a['num_clients']} clients tegen gemiddeld {avg:.0f} per AP.",
                                    f"{a['num_clients']} clients against an average of {avg:.0f} per AP."),
                                  L("Overweeg band steering of iets lager zendvermogen zodat clients beter spreiden.",
                                    "Consider band steering or slightly lower transmit power so clients spread better."),
                                  "num_clients", a["num_clients"], round(2 * avg), a["mac"]))

    # ----------------------------------------------------------------- WAN
    wan = snap["wan"]
    gw = next((d["mac"] for d in snap["devices"] if d["type"] == "gateway"), None)
    if wan["up"] is False:
        out.append(_issue("wan_down", "critical", "wan", "wan", "wan", L("Internetverbinding is weg", "Internet connection is down"),
                          L("De gateway meldt de WAN-verbinding als niet actief.", "The gateway reports the WAN connection as inactive."),
                          L("Controleer modem/ONT en de WAN-kabel naar de UXG.", "Check the modem/ONT and the WAN cable to the gateway."),
                          device_mac=gw))
    lat = _avg(wwin, "lat", wan["latency_ms"])
    if lat is not None and lat >= th.wan_latency_warn:
        sev = "critical" if lat >= th.wan_latency_crit else "warning"
        out.append(_issue("wan_latency", sev, "wan", "wan", "wan", L("Hoge internetlatency", "High internet latency"),
                          L(f"Gemiddeld {lat:.0f} ms over de laatste 15 minuten.", f"Average {lat:.0f} ms over the last 15 minutes."),
                          L("Kijk of er een grote download/back-up loopt; anders ligt het waarschijnlijk bij de provider.",
                            "Check whether a large download/backup is running; otherwise it is probably the provider."),
                          "latency_ms", lat, th.wan_latency_warn, gw))
    elif whour.get("lat_max") and whour["lat_max"] >= th.wan_latency_crit:
        sp = dict(db.q("SELECT COUNT(*) n, MAX(ts) t FROM wan_samples WHERE ts>=? AND latency_ms>=?",
                       (ts - HOUR, th.wan_latency_crit))[0])
        spikes = sp["n"]
        if spikes >= 2:
            out.append(_issue("wan_spikes", "info", "wan", "wan", "wan", L("Af en toe latency-pieken", "Occasional latency spikes"),
                              L(f"{spikes} metingen boven {th.wan_latency_crit:.0f} ms in het afgelopen uur (max {whour['lat_max']:.0f} ms).",
                                f"{spikes} readings above {th.wan_latency_crit:.0f} ms in the past hour (max {whour['lat_max']:.0f} ms)."),
                              L("Merkbaar bij videobellen en gamen. Houd het in de gaten; blijft het, meld het bij de provider.",
                                "Noticeable in video calls and gaming. Keep an eye on it; if it persists, report it to the provider."),
                              "latency_max", whour["lat_max"], th.wan_latency_crit, gw, last_ts=sp.get("t")))
    loss = _avg(wwin, "loss", wan["loss_pct"])
    if loss is not None and loss >= th.wan_drops_warn:
        out.append(_issue("wan_loss", "warning", "wan", "wan", "wan", L("Pakketverlies op internet", "Packet loss on the internet"),
                          L(f"Gemiddeld {loss:.1f}% verlies over de laatste 15 minuten.", f"Average {loss:.1f}% loss over the last 15 minutes."),
                          L("Controleer de kabel tussen modem en UXG; blijft het, neem contact op met de provider.",
                            "Check the cable between the modem and the gateway; if it persists, contact the provider."),
                          "loss_pct", loss, th.wan_drops_warn, gw))

    # ------------------------------------------------------------ IPS (eigen apparaten)
    by_src: dict[str, list[dict]] = {}
    ignores = db.ips_ignores()
    for e in db.ips_events(ts - 24 * HOUR, "internal"):
        if not ips_ignored(e, ignores):
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
        to = f"{', '.join(targets[:3])}{'…' if len(targets) > 3 else ''}"
        out.append(_issue(f"ips_internal:{ip}", "warning", "security", "client" if c else "ip", ip,
                          L(f"{label}: geblokkeerd door IPS", f"{label}: blocked by IPS"),
                          L(f"{len(evs)}× geblokkeerd in 24 uur{via}, vooral '{top}'", f"Blocked {len(evs)}× in 24 hours{via}, mostly '{top}'")
                          + ((L(f" (+{len(sigs) - 1} andere regels)", f" (+{len(sigs) - 1} other rules)")) if len(sigs) > 1 else "")
                          + L(f", naar {to}.", f", to {to}."),
                          L("Een eigen apparaat dat IPS-regels raakt is óf verkeerd geconfigureerd of besmet, óf een vals "
                            "alarm (bijvoorbeeld 'GPL WEB_SERVER DELETE attempt' bij een gewone web-API, of een SSH-scanregel "
                            "door veel verbindingen). Controleer wat het apparaat deed; is het onschuldig, maak in UniFi dan "
                            "een uitzondering voor deze regel en dit adres, of negeer de melding hier.",
                            "One of your own devices hitting IPS rules is either misconfigured or infected, or a false alarm "
                            "(for example 'GPL WEB_SERVER DELETE attempt' on an ordinary web API, or an SSH scan rule caused by "
                            "many connections). Check what the device did; if it is harmless, add an exception in UniFi for "
                            "this rule and this address, or ignore the issue here."),
                          "ips_blocks", len(evs), 1, None, c["mac"] if c else None,
                          max(e["ts"] for e in evs)))

    _new_devices(out, snap, db, ts, name)
    _speedtest_check(out, db, ts, gw)
    cfg = snap.get("config") or {}
    _sticky_after_restart(out, snap, db, th, ts, name)
    _sticky_general(out, snap, db, th, ts, name)
    _group_coverage(out, snap, name)
    _controller_quiet(out, snap)
    if cfg.get("wlans") is not None:
        _config_checks(out, snap, cfg, name)
    if cfg.get("forwards") is not None:
        _exposure_checks(out, snap, cfg, db, ts, ignores)
    if cfg.get("vpn") is not None:
        _vpn_checks(out, cfg, db, ts)
    if cfg.get("segments"):
        _segment_checks(out, snap, cfg["segments"], name)
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
    days = L("ma di wo do vr za zo", "Mon Tue Wed Thu Fri Sat Sun").split()

    def when(t: float) -> str:
        lt = time.localtime(t)
        return f"{days[lt.tm_wday]} {time.strftime('%H:%M', lt)}"

    order = {"gateway": 0, "switch": 1, "ap": 2}
    for cl in _restart_clusters(snap, ts):
        restarted = {d["mac"] for d in cl["devices"]}
        who = [d["name"] for d in sorted(cl["devices"], key=lambda d: order.get(d["type"], 3))]
        names = _join(who)
        gkey = f"sticky_restart:{cl['devices'][0]['mac']}:{int(cl['start'] // 60)}"
        members = []
        for c in snap["clients"]:
            a = c.get("assoc_ts")
            if c["wired"] or not a or c["signal"] is None or not (cl["start"] - 60 <= a <= cl["end"] + STICKY_AFTER):
                continue
            warn, _ = signal_limits(th, c["band"])
            before = db.client_before(c["mac"], int(cl["start"]) - 6 * HOUR, int(cl["start"]) - 60)
            if before and before["ap_mac"] != c["ap_mac"] and before["sig"] - c["signal"] >= STICKY_GAIN_DB:
                sev, why = "warning", L(f"Zat vóór de herstart op {name(before['ap_mac'])} met {before['sig']:.0f} dBm, "
                                        f"nu op {name(c['ap_mac'])} met {c['signal']:.0f} dBm.",
                                        f"Was on {name(before['ap_mac'])} with {before['sig']:.0f} dBm before the restart, "
                                        f"now on {name(c['ap_mac'])} with {c['signal']:.0f} dBm.")
            elif not before and c["signal"] <= warn and c["ap_mac"] not in restarted:
                sev, why = "info", L(f"Verbond {when(a)} met {name(c['ap_mac'])} en zit daar op {c['signal']:.0f} dBm; "
                                     f"mogelijk hoort het bij een AP die toen even weg was.",
                                     f"Connected to {name(c['ap_mac'])} on {when(a)} and sits there at {c['signal']:.0f} dBm; "
                                     f"it may belong to an AP that was briefly gone then.")
            else:
                continue
            members.append(_issue(f"sticky:{c['mac']}", sev, "wifi", "client", c["mac"],
                                  L(f"{c['name']}: blijft hangen op {name(c['ap_mac'])}", f"{c['name']}: stuck on {name(c['ap_mac'])}"), why,
                                  L("Opnieuw verbinden laat het apparaat zelf de beste AP kiezen.",
                                    "Reconnecting lets the device pick the best AP itself."),
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
                          L(f"Na herstart van {names} ({when(cl['start'])}): {n} apparaat{'en' if n > 1 else ''} op een verre AP",
                            f"After restart of {names} ({when(cl['start'])}): {n} device{'s' if n > 1 else ''} on a distant AP"),
                          f"{', '.join(m['title'].split(':')[0] for m in members[:6])}{'…' if n > 6 else ''}.",
                          L("Deze apparaten maakten verbinding terwijl hun eigen AP even weg was, en wisselen niet uit "
                            "zichzelf terug: vooral zuinige IoT-apparaten zoeken pas opnieuw als hun verbinding helemaal "
                            "wegvalt. Gebruik 'Opnieuw verbinden' per apparaat. Gebeurt dit vaker, zet vaste apparaten dan "
                            "vast aan hun AP of stel een minimum-RSSI in op de verre AP.",
                            "These devices connected while their own AP was briefly gone, and do not switch back by "
                            "themselves: low-power IoT devices in particular only search again when their connection drops "
                            "completely. Use 'Reconnect' per device. If this happens more often, lock stationary devices to "
                            "their AP or set a minimum RSSI on the distant AP."),
                          "clients", n, 1, cl["devices"][0]["mac"]))
        out[-1]["members"] = [m["client_mac"] for m in members]


def _group_coverage(out: list[dict], snap: dict, name) -> None:
    """Hebben ≥3 clients op dezelfde AP + band signaal/retry-problemen, dan is dat
    één dekkingsprobleem van die radio. De losse client-issues krijgen een
    verwijzing naar de groep, zodat het dashboard ze kan inklappen."""
    clients = {c["mac"]: c for c in snap["clients"]}
    groups: dict[tuple, list[dict]] = {}
    for i in out:
        if (i["entity_type"] == "client" and i["metric"] in ("signal", "retry_pct", "satisfaction") and not i.get("group")
                and not i["key"].startswith("sticky:")):   # "blijft hangen" is een eigen oorzaak
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
            title = L(f"{name(ap)}: zwakke dekking op {band} GHz", f"{name(ap)}: weak coverage on {band} GHz")
            adv = L("Meerdere apparaten op deze AP hebben een zwak signaal: de AP staat te ver weg of de dekking in "
                    "dat gebied is onvoldoende. Een extra AP of een betere plek lost dit voor al deze apparaten tegelijk op.",
                    "Several devices on this AP have a weak signal: the AP is too far away or coverage in that area is "
                    "insufficient. An extra AP or a better spot fixes this for all of these devices at once.")
        else:
            title = L(f"{name(ap)}: slechte wifi-kwaliteit op {band} GHz", f"{name(ap)}: poor wifi quality on {band} GHz")
            adv = L("Meerdere apparaten hebben tegelijk veel retries terwijl het signaal redelijk is. Dat wijst op "
                    "storing of een vol kanaal op deze radio, niet op de apparaten zelf.",
                    "Several devices have many retries at the same time while the signal is reasonable. That points to "
                    "interference or a busy channel on this radio, not to the devices themselves.")
        for m in members:
            m["group"] = key
        for i in out:   # radio-retries van dezelfde radio horen bij hetzelfde verhaal
            if i["key"] == f"radio_retry:{ap}@{band}":
                i["group"] = key
        out.append(_issue(key, sev, "wifi", "radio", f"{ap}@{band}", title,
                          L(f"{len(macs)} apparaten met problemen: ", f"{len(macs)} devices with problems: ")
                          + f"{', '.join(names[:6])}{'…' if len(names) > 6 else ''}.",
                          adv, "clients", len(macs), 3, ap))
        out[-1]["members"] = sorted(macs)


SPEED_DROP = 0.6        # laatste test onder 60% van wat normaal is
SPEED_RECENT = 3 * 24 * HOUR


NEW_DEVICE_DAYS = 7
RETRY_MIN_CU = 5.0          # % kanaalbezetting waaronder retries van een radio niet gemeld worden
VPN_LABEL = {"openvpn": "OpenVPN", "l2tp": "L2TP/IPsec", "pptp": "PPTP", "wireguard": "WireGuard"}


def _vpn_checks(out: list[dict], cfg: dict, db, ts: int) -> None:
    """VPN-servers op de gateway die naar internet openstaan. WireGuard antwoordt alleen op verkeer met een
    geldige sleutel en is daardoor onzichtbaar voor scanners; OpenVPN en zeker L2TP/PPTP niet."""
    for v in cfg.get("vpn") or []:
        if not v["enabled"] or v["type"] == "wireguard" or not v["port"]:
            continue
        row = db.q("SELECT COUNT(*) n, COUNT(DISTINCT remote_ip) s FROM flows WHERE ts>=? AND dir IN ('in','blocked') "
                   "AND port=?", (ts - 24 * 3600, v["port"]))[0]
        n, srcs = row["n"] or 0, (dict(row).get("s") or 0)
        label = VPN_LABEL.get(v["type"], v["type"])
        old = v["type"] in ("l2tp", "pptp")
        seen = (L(f" In de afgelopen 24 uur kwamen er {n} verbindingspogingen van buiten op die poort",
                  f" In the past 24 hours there were {n} connection attempts from outside on that port")
                + (L(f" (van {srcs} adressen).", f" (from {srcs} addresses).") if srcs > 1 else ".")) if n else ""
        out.append(_issue(f"vpn_open:{v['type']}:{v['port']}", "warning" if old else "info", "security", "site", "vpn",
                          L(f"{label}-server open naar internet (poort {v['port']}/{v['proto']})",
                            f"{label} server open to the internet (port {v['port']}/{v['proto']})"),
                          L(f"VPN-server '{v['name']}' antwoordt op poort {v['port']}: iedereen op internet kan zien dat hier een "
                            f"VPN-server draait.{seen}", f"VPN server '{v['name']}' answers on port {v['port']}: anyone on the "
                            f"internet can see that a VPN server runs here.{seen}")
                          + (L(" Dit protocol is verouderd en niet meer veilig genoeg.",
                               " This protocol is outdated and no longer secure enough.") if old else ""),
                          L("Gebruik je hem niet (meer), zet hem dan uit (UniFi: Instellingen → VPN → VPN Server). Gebruik je "
                            "hem wel, stap dan bij voorkeur over op WireGuard: dat antwoordt alleen op verkeer met een geldige "
                            "sleutel en is daardoor onzichtbaar voor scanners. Houd de firmware van je gateway actueel.",
                            "Not using it (anymore)? Turn it off (UniFi: Settings → VPN → VPN Server). If you do use it, "
                            "preferably switch to WireGuard: it only answers traffic with a valid key and is therefore "
                            "invisible to scanners. Keep your gateway firmware up to date.")))


def _new_devices(out: list[dict], snap: dict, db, ts: int, name) -> None:
    """Apparaten die voor het eerst in het netwerk verschijnen, en apparaten met een wisselend privé-adres."""
    clients = {c["mac"]: c for c in snap["clients"]}
    since = ts - NEW_DEVICE_DAYS * 86400
    for r in db.pending_new(since):
        c = clients.get(r["mac"]) or {}
        label = c.get("name") or r["name"] or r["hostname"] or r["mac"]
        up = c.get("ap_mac") or c.get("sw_mac")
        where = ((f"via {name(up)}" + (L(f" poort {c['sw_port']}", f" port {c['sw_port']}") if c.get("sw_port") else ""))
                 if up else L("nu niet verbonden", "not connected now"))
        parts = [c.get("vendor") or None, c.get("ssid") or c.get("network") or None, where, c.get("ip") or None,
                 L("privé-wifiadres", "private wifi address") if r["private"] else None]
        when = time.strftime("%d-%m %H:%M", time.localtime(r["first_seen"]))
        i = _issue(f"new_device:{r['mac']}", "info", "new", "client", r["mac"], L(f"Nieuw apparaat: {label}", f"New device: {label}"),
                   L(f"Voor het eerst gezien op {when}: ", f"First seen on {when}: ") + " · ".join(p for p in parts if p) + ".",
                   L("Herken je het? Klik dan op 'Ken ik'. Herken je het niet, blokkeer het dan in UniFi (Clients → het "
                     "apparaat → Blokkeren) en verander voor de zekerheid je wifi-wachtwoord.",
                     "Do you recognize it? Then click 'I know this'. If you don't, block it in UniFi (Clients → the "
                     "device → Block) and change your wifi password to be safe."),
                   device_mac=up, client_mac=r["mac"] if c else None)
        i.update(notify=True, quiet_resolve=True, approve=r["mac"])
        out.append(i)
    for r in db.rotations(since):
        c = clients.get(r["mac"]) or {}
        label = c.get("name") or r["name"] or r["hostname"]
        out.append(_issue(f"mac_rotate:{r['hostname']}", "info", "wifi", "client", r["mac"],
                          L(f"{label} wisselt van wifi-adres", f"{label} keeps changing its wifi address"),
                          L(f"Dit apparaat kwam terug met een ander privé-wifiadres (eerst …{r['rotated_from'][-8:]}, nu "
                            f"…{r['mac'][-8:]}). Sonar en UniFi zien het daardoor als nieuw apparaat: de historie begint opnieuw "
                            "en instellingen zoals een vaste AP of IP-adres werken niet meer.",
                            f"This device came back with a different private wifi address (first …{r['rotated_from'][-8:]}, now "
                            f"…{r['mac'][-8:]}). Sonar and UniFi therefore see it as a new device: the history starts over "
                            "and settings such as a fixed AP or IP address no longer work."),
                          L("Zet het privé-adres voor je eigen netwerk op 'vast'. iPhone/iPad: Instellingen → Wifi → (i) bij je "
                            "netwerk → Privé-wifiadres → Vast. Mac: Systeeminstellingen → Wifi → Details → Privé-wifiadres → Vast. "
                            "Android: Wifi → je netwerk → Privacy → 'Willekeurig MAC-adres per netwerk' (niet 'per verbinding').",
                            "Set the private address for your own network to 'fixed'. iPhone/iPad: Settings → Wi-Fi → (i) next "
                            "to your network → Private Wi-Fi Address → Fixed. Mac: System Settings → Wi-Fi → Details → Private "
                            "Wi-Fi Address → Fixed. Android: Wi-Fi → your network → Privacy → 'Randomized MAC per network' "
                            "(not 'per connection')."),
                          client_mac=r["mac"] if c else None))


SEGMENT_SUGGEST_MIN = 3   # zoveel slimme apparaten zonder apart netwerk = tip om er een te maken


def _segment_checks(out: list[dict], snap: dict, seg: dict, name) -> None:
    """Slimme apparaten op het hoofdnetwerk, en een IoT-netwerk dat niet is afgeschermd."""
    segs = seg["segments"]
    apart = [s for s in segs if s["kind"] in ("iot", "other")]
    if not apart:
        smart = [c for c in snap["clients"] if segments.smart_reason(c)
                 and (s := segments.client_segment(c, segs)) and s["kind"] == "main"]
        if len(smart) >= SEGMENT_SUGGEST_MIN:
            names = sorted(c["name"] for c in smart)
            out.append(_issue("segment:none", "info", "security", "site", "segments",
                              L(f"{len(smart)} slimme apparaten delen het netwerk met je computers",
                                f"{len(smart)} smart devices share the network with your computers"),
                              L(f"Onder andere {_join(names[:5])}{' en meer' if len(names) > 5 else ''}. Slimme apparaten krijgen "
                                "zelden updates; wordt er één overgenomen, dan kan het van daaruit bij je computers, NAS en "
                                "telefoons.", f"Including {_join(names[:5])}{' and more' if len(names) > 5 else ''}. Smart "
                                "devices rarely get updates; if one is taken over, it can reach your computers, NAS and "
                                "phones from there."),
                              L("Maak in UniFi een apart netwerk (VLAN) voor slimme apparaten en zet het in een eigen firewallzone "
                                "(Instellingen → Netwerken, daarna Zone-Based Firewall → Create Zone). Sta daarna alleen toe wat nodig "
                                "is, bijvoorbeeld verkeer naar Home Assistant. Wifi-apparaten verhuis je zonder nieuwe SSID met "
                                "'Virtual Network Override' per apparaat.",
                                "Create a separate network (VLAN) for smart devices in UniFi and put it in its own firewall zone "
                                "(Settings → Networks, then Zone-Based Firewall → Create Zone). Then allow only what is needed, "
                                "for example traffic to Home Assistant. Wifi devices can be moved without a new SSID using "
                                "'Virtual Network Override' per device."), "clients", len(smart), SEGMENT_SUGGEST_MIN))
        return
    target = next((s for s in apart if s["kind"] == "iot"), apart[0])
    for s in apart:
        if s["isolated"] is False:
            out.append(_issue(f"segment_open:{s['id']}", "warning", "security", "site", f"segment:{s['id']}",
                              L(f"Netwerk {s['name']} is niet afgeschermd", f"Network {s['name']} is not isolated"),
                              L(f"{s['name']} zit in de firewallzone '{s['zone'] or 'Internal'}'",
                                f"{s['name']} is in the firewall zone '{s['zone'] or 'Internal'}'")
                              + (L(" samen met je hoofdnetwerk", " together with your main network") if (s["zone"] or "Internal") == next(
                                  (m["zone"] for m in segs if m["kind"] == "main"), None) else "")
                              + L(": apparaten op dit netwerk kunnen gewoon bij je computers, NAS en telefoons. Een apart "
                                  "VLAN alleen scheidt niets.", ": devices on this network can simply reach your computers, "
                                  "NAS and phones. A separate VLAN alone separates nothing."),
                              L("Maak in UniFi een eigen zone voor dit netwerk (Instellingen → Zone-Based Firewall → Create Zone). "
                                "Verkeer van die zone naar Internal is dan standaard geblokkeerd; sta daarna alleen toe wat nodig "
                                "is, zoals Home Assistant of je DNS-server.",
                                "Create a zone of its own for this network in UniFi (Settings → Zone-Based Firewall → Create Zone). "
                                "Traffic from that zone to Internal is then blocked by default; then allow only what is needed, "
                                "such as Home Assistant or your DNS server.")))
    for c, why in segments.misplaced(snap["clients"], seg):
        up = c.get("ap_mac") or c.get("sw_mac")
        main = segments.client_segment(c, segs)
        port = L(f" poort {c['sw_port']}", f" port {c['sw_port']}") if c.get("sw_port") else ""
        how = (L("Wifi: in UniFi bij het apparaat → Settings → Virtual Network Override → " + target["name"] + ". Dat kan op "
                 "dezelfde SSID. Let op: na zo'n wijziging stellen alle access points zich opnieuw in en valt de wifi ongeveer "
                 "een minuut weg, dus verhuis meerdere apparaten in één keer.",
                 "Wifi: in UniFi at the device → Settings → Virtual Network Override → " + target["name"] + ". This works on "
                 "the same SSID. Note: after such a change all access points re-provision and wifi drops for about a "
                 "minute, so move several devices at once.") if not c.get("wired") else
               L(f"Bekabeld: zet de switchpoort ({name(up)}{port}) op het netwerk {target['name']} (Port Manager → Native VLAN/Network).",
                 f"Wired: set the switch port ({name(up)}{port}) to the network {target['name']} (Port Manager → Native VLAN/Network)."))
        i = _issue(f"segment:{c['mac']}", "info", "security", "client", c["mac"],
                   L(f"{c['name']} staat op je hoofdnetwerk", f"{c['name']} is on your main network"),
                   L(f"Sonar herkent dit als slim apparaat ({why}). Het staat op {main['name']}, terwijl je daar het netwerk "
                     f"{target['name']} voor hebt.", f"Sonar recognizes this as a smart device ({why}). It is on {main['name']}, "
                     f"while you have the network {target['name']} for that."),
                   how + L(" Krijgt het daar een nieuw IP-adres, pas dat dan ook aan in Home Assistant of de app die het "
                           "aanstuurt. Hoort het bewust hier (bijvoorbeeld omdat het met je telefoon moet praten)? Kies dan "
                           "Negeren → Altijd.", " If it gets a new IP address there, update it in Home Assistant or the app "
                           "that controls it too. Does it belong here on purpose (for example because it has to talk to your "
                           "phone)? Then choose Ignore → Always."), device_mac=up, client_mac=c["mac"])
        out.append(i)


def _speedtest_check(out: list[dict], db, ts: int, gw) -> None:
    """Vergelijk de laatste speedtest met wat normaal is voor deze verbinding (mediaan van eerdere tests)."""
    rows = db.speedtests(ts - 30 * 24 * HOUR)
    if len(rows) < 4 or ts - rows[-1]["ts"] > SPEED_RECENT:
        return
    last, prev = rows[-1], rows[-21:-1]
    for key, label in (("down", "download"), ("up", "upload")):   # zelfde woord in beide talen
        vals = sorted(r[key] for r in prev if r[key])
        if not vals or not last[key]:
            continue
        med = vals[len(vals) // 2]
        if last[key] < SPEED_DROP * med:
            when = time.strftime("%d-%m %H:%M", time.localtime(last["ts"]))
            out.append(_issue(f"speed_low:{key}", "warning", "wan", "wan", "wan",
                              L(f"Internet trager dan normaal ({label})", f"Internet slower than normal ({label})"),
                              L(f"Laatste speedtest ({when}): {last[key]:.0f} Mbit/s {label}, normaal rond {med:.0f} Mbit/s.",
                                f"Last speed test ({when}): {last[key]:.0f} Mbit/s {label}, normally around {med:.0f} Mbit/s."),
                              L("Draai de test nog eens op een rustig moment (op de pagina Internet). Blijft het laag, kijk dan of "
                                "het modem/de ONT goed is aangesloten en meld het bij je provider; de historie laat zien sinds wanneer.",
                                "Run the test again at a quiet moment (on the Internet page). If it stays low, check that the "
                                "modem/ONT is connected properly and report it to your provider; the history shows since when."),
                              f"speed_{key}", last[key], round(SPEED_DROP * med), gw, last_ts=last["ts"]))
            return   # één melding is genoeg


def _dur(sec: float) -> str:
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    if h >= 48:
        return L(f"{h // 24} dagen", f"{h // 24} days")
    return L(f"{h} u {m} m", f"{h} h {m} m") if h else L(f"{m} minuten", f"{m} minutes")


def _join(names: list[str]) -> str:
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + L(" en ", " and ") + names[-1]


STICKY_MIN_STAY = HOUR          # pas na een uur op de verre AP spreken we van "blijft hangen"
STICKY_MAX_SWITCHES = 6         # meer AP-wissels per week = mobiel apparaat dat gewoon rondloopt
STICKY_MIN_OTHER = 30 * 60      # minstens een half uur bewijs op de betere AP


def _sticky_general(out: list[dict], snap: dict, db, th: Thresholds, ts: int, name) -> None:
    """Vaste wifi-apparaten die al lang met zwak signaal op een AP zitten, terwijl ze de afgelopen week
    op een andere AP duidelijk beter zaten (ook zonder herstart)."""
    flagged = {i["client_mac"] for i in out if i["key"].startswith("sticky:")}
    online_aps = {d["mac"] for d in snap["devices"] if d["type"] == "ap" and d["state"] == "online"}
    cwin = db.client_window(ts - WINDOW)
    for c in snap["clients"]:
        mac = c["mac"]
        if c["wired"] or not c.get("ap_mac") or mac in flagged or c.get("fixed_ap"):
            continue
        sig = _avg(cwin.get(mac, {}), "sig", c["signal"])
        warn, _ = signal_limits(th, c["band"])
        a = c.get("assoc_ts")
        if sig is None or sig > warn or not a or ts - a < STICKY_MIN_STAY:
            continue
        st = db.client_ap_stats(mac, ts - 7 * 24 * HOUR)
        if st["switches"] > STICKY_MAX_SWITCHES:
            continue
        better = [x for x in st["aps"] if x["ap_mac"] != c["ap_mac"] and x["ap_mac"] in online_aps
                  and x["seconds"] >= STICKY_MIN_OTHER and x["signal"] is not None and x["signal"] - sig >= STICKY_GAIN_DB]
        if not better:
            continue
        best = max(better, key=lambda x: x["signal"])
        usual = st["aps"][0]["ap_mac"] == best["ap_mac"]
        key = f"sticky:{mac}"
        here, there = name(c["ap_mac"]), name(best["ap_mac"])
        out.append(_issue(key, "warning" if usual else "info", "wifi", "client", mac,
                          L(f"{c['name']}: zit op een verre AP ({here})", f"{c['name']}: on a distant AP ({here})"),
                          L(f"Al {_dur(ts - a)} op {here} met {sig:.0f} dBm. Op {there} had het de afgelopen week gemiddeld "
                            f"{best['signal']:.0f} dBm", f"On {here} for {_dur(ts - a)} with {sig:.0f} dBm. On {there} it averaged "
                            f"{best['signal']:.0f} dBm over the past week")
                          + (L(", en daar zit het normaal ook.", ", and that is where it normally is.") if usual else "."),
                          L("Vaste apparaten wisselen vaak niet uit zichzelf terug naar een betere AP als ze eenmaal (bijvoorbeeld "
                            "na een storing) op een verdere AP zitten. 'Opnieuw verbinden' laat het apparaat opnieuw kiezen. "
                            f"Gebeurt dit vaker, zet het dan in UniFi vast aan {there} of stel op {here} een minimum-RSSI in.",
                            "Stationary devices often do not switch back to a better AP by themselves once they are on a more "
                            "distant AP (for example after an outage). 'Reconnect' lets the device choose again. If this happens "
                            f"more often, lock it to {there} in UniFi or set a minimum RSSI on {here}."),
                          "signal", sig, warn, c["ap_mac"], mac))
        out[-1]["reconnect"] = True
        for i in out:   # het zwakke signaal en de retries zijn hetzelfde verhaal
            if i["key"] in (f"client_signal:{mac}", f"client_retry:{mac}"):
                i["group"] = key


def _controller_quiet(out: list[dict], snap: dict) -> None:
    """Valt (bijna) alles tegelijk weg, dan ligt het aan de controller of het netwerk ernaartoe."""
    devs = snap["devices"]
    gone = [d for d in devs if d["state"] != "online" and d["state"] not in TRANSIENT]
    if len(gone) < QUIET_MIN_DEVICES or len(gone) < QUIET_FRACTION * len(devs):
        return
    key = "controller_quiet"
    macs = {d["mac"] for d in gone}
    for i in out:
        if i["key"].startswith("dev_state:") and i["device_mac"] in macs:
            i["group"] = key
    out.append(_issue(key, "critical", "device", "controller", key,
                      L(f"UniFi hoort {len(gone)} van de {len(devs)} apparaten niet meer",
                        f"UniFi no longer hears {len(gone)} of the {len(devs)} devices"),
                      f"{_join([d['name'] for d in gone[:6]])}{'…' if len(gone) > 6 else ''}"
                      + L(" zijn tegelijk weggevallen.", " dropped out at the same time."),
                      L("Als bijna alles tegelijk wegvalt, ligt het meestal niet aan de apparaten zelf. Controleer of de "
                        "UniFi-controller (UniFi OS) draait en of de gateway en de centrale switch stroom hebben. Na een "
                        "herstart van de controller duurt het een paar minuten voordat alle apparaten zich weer melden.",
                        "When almost everything drops at once, it is usually not the devices themselves. Check that the UniFi "
                        "controller (UniFi OS) is running and that the gateway and the core switch have power. After a "
                        "controller restart it takes a few minutes before all devices report in again."),
                      "devices", len(gone), QUIET_MIN_DEVICES))
    out[-1]["members"] = sorted(macs)


def _blocks5(ch, width) -> set[int]:
    """Welke 20 MHz-kanalen bezet een 5 GHz-radio op dit kanaal en deze breedte?"""
    try:
        ch = int(ch)
    except (TypeError, ValueError):
        return set()
    n = max(1, int((width or 20) // 20))
    base = 149 if ch >= 149 else 100 if ch >= 100 else 36
    size = 4 * n
    start = base + (ch - base) // size * size
    return set(range(start, start + size, 4))


def _config_checks(out: list[dict], snap: dict, cfg: dict, name) -> None:
    """Wifi-instellingen die vaak tot problemen leiden. Alleen advies: Sonar verandert zelf niets."""
    aps = [d for d in snap["devices"] if d["type"] == "ap" and d["state"] == "online" and d["radios"]]
    wlans = [w for w in cfg["wlans"] if w["enabled"]]
    main = [w for w in wlans if not w["guest"] and not w["iot"] and "2.4" in w["bands"] and "5" in w["bands"]]
    dev_of = lambda d: d["mac"]  # noqa: E731

    for d in aps:
        for r in d["radios"]:
            rid = f"{d['mac']}@{r['radio']}"
            if r["radio"] == "2.4" and (r.get("width") or 20) > 20:
                out.append(_issue(f"cfg_width24:{rid}", "warning", "config", "radio", rid,
                                  L(f"{d['name']}: 2.4 GHz op {int(r['width'])} MHz", f"{d['name']}: 2.4 GHz at {int(r['width'])} MHz"),
                                  L("Op 2.4 GHz past maar één niet-overlappend kanaal van 40 MHz; je stoort buren en je eigen AP's.",
                                    "Only one non-overlapping 40 MHz channel fits in 2.4 GHz; you interfere with neighbours and your own APs."),
                                  L("Zet de kanaalbreedte op 2.4 GHz op 20 MHz (UniFi: Apparaat → Radio's).",
                                    "Set the 2.4 GHz channel width to 20 MHz (UniFi: Device → Radios)."), device_mac=dev_of(d)))
            if r.get("min_rssi") is not None and r["min_rssi"] > -70:
                out.append(_issue(f"cfg_minrssi:{rid}", "warning", "config", "radio", rid,
                                  L(f"{d['name']}: minimum-RSSI erg streng ({r['min_rssi']:.0f} dBm)",
                                    f"{d['name']}: minimum RSSI very strict ({r['min_rssi']:.0f} dBm)"),
                                  L(f"Apparaten met een zwakker signaal dan {r['min_rssi']:.0f} dBm worden op {r['radio']} GHz losgekoppeld.",
                                    f"Devices with a weaker signal than {r['min_rssi']:.0f} dBm are disconnected on {r['radio']} GHz."),
                                  L("Een minimum-RSSI strenger dan −70 dBm kan apparaten laten blijven loskoppelen als er geen betere "
                                    "AP is. Begin bij −75 tot −80 dBm.", "A minimum RSSI stricter than −70 dBm can keep disconnecting "
                                    "devices when there is no better AP. Start at −75 to −80 dBm."), device_mac=dev_of(d)))

    # 5 GHz: eigen AP's in hetzelfde kanaalblok
    r5 = [(d, r, _blocks5(r["channel"], r.get("width"))) for d in aps for r in d["radios"] if r["radio"] == "5"]
    groups: list[list] = []
    for item in r5:
        hit = [g for g in groups if any(item[2] & o[2] for o in g)]
        merged = [item] + [x for g in hit for x in g]
        groups = [g for g in groups if g not in hit] + [merged]
    for g in groups:
        if len(g) < 2:
            continue
        g.sort(key=lambda x: x[0]["name"])
        key = "cfg_cochannel5:" + ",".join(x[0]["mac"] for x in g)
        chans = sorted(set().union(*(x[2] for x in g)))
        auto = all(x[1].get("channel_auto") for x in g)
        out.append(_issue(key, "info", "config", "radio", key,
                          L(f"{_join([x[0]['name'] for x in g])} delen hetzelfde 5 GHz-kanaal",
                            f"{_join([x[0]['name'] for x in g])} share the same 5 GHz channel"),
                          "; ".join(L(f"{x[0]['name']} op {x[1]['channel']}", f"{x[0]['name']} on {x[1]['channel']}")
                                    + f" ({int(x[1].get('width') or 20)} MHz)" for x in g)
                          + L(f". Samen bezetten ze kanaal {chans[0]}–{chans[-1]}, dus ze moeten op elkaar wachten.",
                              f". Together they occupy channels {chans[0]}–{chans[-1]}, so they have to wait for each other."),
                          L("Geef elke AP een eigen kanaalblok (bijvoorbeeld 36, 52, 100 en 149), of kies 40 MHz breedte zodat "
                            "er meer blokken zijn. Staan de AP's ver uit elkaar of in een ander gebouw, dan merk je hier weinig van.",
                            "Give each AP its own channel block (for example 36, 52, 100 and 149), or choose 40 MHz width so "
                            "there are more blocks. If the APs are far apart or in another building, you will notice little of this.")
                          + (L(" De kanalen staan nu op automatisch; zet ze handmatig of draai de kanaaloptimalisatie opnieuw.",
                               " The channels are set to automatic now; set them manually or run channel optimization again.") if auto else ""),
                          "aps", len(g), 1, g[0][0]["mac"]))

    # 2.4 GHz: een vrij standaardkanaal terwijl een ander dubbel gebruikt wordt
    use: dict[int, list[str]] = {1: [], 6: [], 11: []}
    for d in aps:
        for r in d["radios"]:
            if r["radio"] == "2.4" and r["channel"] in use:
                use[r["channel"]].append(d["name"])
    free = [c for c, n in use.items() if not n]
    busy = [c for c, n in use.items() if len(n) >= 2]
    if free and busy:
        out.append(_issue("cfg_ch24", "info", "config", "site", "wifi24",
                          L(f"2.4 GHz: kanaal {_join([str(c) for c in free])} wordt niet gebruikt",
                            f"2.4 GHz: channel {_join([str(c) for c in free])} is not used"),
                          " · ".join(L(f"kanaal {c}: {_join(n)}", f"channel {c}: {_join(n)}") for c, n in use.items() if n) + ".",
                          L(f"Verdeel de AP's over de kanalen 1, 6 en 11: zet een van de AP's op kanaal {busy[0]} over naar "
                            f"kanaal {free[0]}, bij voorkeur de AP die het dichtst bij een andere AP op kanaal {busy[0]} staat.",
                            f"Spread the APs over channels 1, 6 and 11: move one of the APs on channel {busy[0]} to channel "
                            f"{free[0]}, preferably the AP closest to another AP on channel {busy[0]}.")))

    if main and len(aps) >= 2:
        # band steering
        known = [d for d in aps if d.get("bandsteering") is not None and any(r["radio"] == "5" for r in d["radios"])]
        off = [d for d in known if d["bandsteering"] == "off"]
        if off:
            on = [d for d in known if d["bandsteering"] != "off"]
            out.append(_issue("cfg_bandsteer", "info", "config", "site", "bandsteer",
                              L("Band steering staat " + ("niet overal aan" if on else "uit"),
                                "Band steering is " + ("not on everywhere" if on else "off")),
                              L(f"Uit op {_join([d['name'] for d in off])}", f"Off on {_join([d['name'] for d in off])}")
                              + (L(f"; aan op {_join([d['name'] for d in on])}.", f"; on for {_join([d['name'] for d in on])}.") if on else "."),
                              L("Met band steering worden apparaten die 5 GHz kunnen daarheen gestuurd, waar meer ruimte is. "
                                "Zet het op 'Prefer 5G' (UniFi: Apparaat → Radio's → Band Steering). Zuinige IoT-apparaten op "
                                "2.4 GHz hebben er geen last van.", "With band steering, devices that can do 5 GHz are steered "
                                "there, where there is more room. Set it to 'Prefer 5G' (UniFi: Device → Radios → Band Steering). "
                                "Low-power IoT devices on 2.4 GHz are not affected."), device_mac=off[0]["mac"]))
        for w in main:
            if not w["fast_roaming"]:
                out.append(_issue(f"cfg_ft:{w['name']}", "info", "config", "wlan", w["name"],
                                  L(f"Wifi '{w['name']}': Fast Roaming staat uit", f"Wifi '{w['name']}': Fast Roaming is off"),
                                  L("Zonder 802.11r duurt overstappen naar een andere AP langer",
                                    "Without 802.11r, moving to another AP takes longer")
                                  + (L("; BSS Transition (802.11v) staat wel aan.", "; BSS Transition (802.11v) is on.") if w["bss_transition"]
                                     else L(", en ook BSS Transition (802.11v) staat uit.", ", and BSS Transition (802.11v) is off too.")),
                                  L("Zet Fast Roaming aan bij dit wifi-netwerk (UniFi: WiFi → netwerk → Advanced) zodat telefoons "
                                    "en laptops soepel van AP wisselen. Werkt een ouder apparaat daarna niet meer, zet het dan op "
                                    "een apart IoT-netwerk zonder Fast Roaming.", "Turn on Fast Roaming for this wifi network "
                                    "(UniFi: WiFi → network → Advanced) so phones and laptops switch APs smoothly. If an older "
                                    "device stops working afterwards, put it on a separate IoT network without Fast Roaming.")))
    for w in main:
        if w["minrate_24"] < 5500 and any(r["radio"] == "2.4" for d in aps for r in d["radios"]):
            rate = f"{w['minrate_24'] / 1000:g} Mbit/s" if w["minrate_24"] else L("niet ingesteld", "not set")
            out.append(_issue(f"cfg_minrate:{w['name']}", "info", "config", "wlan", w["name"],
                              L(f"Wifi '{w['name']}': trage 2.4 GHz-snelheden toegestaan", f"Wifi '{w['name']}': slow 2.4 GHz rates allowed"),
                              L(f"De minimale datasnelheid op 2.4 GHz is {rate}. Apparaten die op 1 of 2 Mbit/s praten, "
                                "houden het kanaal lang bezet en blijven langer aan een verre AP hangen.",
                                f"The minimum data rate on 2.4 GHz is {rate}. Devices talking at 1 or 2 Mbit/s occupy the "
                                "channel for a long time and stay connected to a distant AP longer."),
                              L("Zet de minimale datasnelheid op 2.4 GHz op 6 Mbit/s (UniFi: WiFi → netwerk → Advanced → "
                                "Minimum Data Rate). Laat een apart IoT-netwerk met verre apparaten zoals het is.",
                                "Set the minimum data rate on 2.4 GHz to 6 Mbit/s (UniFi: WiFi → network → Advanced → "
                                "Minimum Data Rate). Leave a separate IoT network with distant devices as it is.")))
    high = [d["name"] for d in aps for r in d["radios"] if r["radio"] == "2.4" and r.get("tx_power_mode") == "high"]
    if len(high) >= 2:
        out.append(_issue("cfg_txpow24", "info", "config", "site", "txpow24",
                          L("Hoog zendvermogen op 2.4 GHz", "High transmit power on 2.4 GHz"),
                          L(f"{_join(high)} zenden op 2.4 GHz op 'High'.", f"{_join(high)} transmit on 2.4 GHz at 'High'."),
                          L("Bij meerdere AP's zorgt hoog 2.4 GHz-vermogen dat apparaten aan een verre AP blijven hangen en "
                            "dat AP's elkaar storen. Zet 2.4 GHz op 'Medium' of 'Low' en laat 5 GHz op 'Auto'.",
                            "With several APs, high 2.4 GHz power makes devices stick to a distant AP and makes APs interfere "
                            "with each other. Set 2.4 GHz to 'Medium' or 'Low' and leave 5 GHz on 'Auto'.")))


RISKY_PORTS = {21: "FTP", 22: "SSH", 23: "Telnet", 139: "NetBIOS", 445: "SMB", 1433: "SQL Server", 3306: "MySQL",
               3389: "Remote Desktop", 5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 9200: "Elasticsearch",
               27017: "MongoDB"}
ATTACKED_MIN = 10   # zoveel IPS-blokkades per dag op een doorgezette poort = gericht doelwit


def _ports(spec: str) -> set[int]:
    out: set[int] = set()
    for part in str(spec or "").split(","):
        a, _, b = part.strip().partition("-")
        try:
            lo, hi = int(a), int(b or a)
        except ValueError:
            continue
        out.update(range(lo, min(hi, lo + 2000) + 1))
    return out


def _exposure_checks(out: list[dict], snap: dict, cfg: dict, db, ts: int, ignores: list[dict]) -> None:
    """Wat staat er open naar internet: UPnP en port forwards, gekoppeld aan wat de IPS ziet."""
    who = {c["ip"]: c["name"] for c in snap["clients"] if c.get("ip")}
    fw = cfg["forwards"]
    upnp = [f for f in fw if f["upnp"]]
    target = lambda f: f"{who.get(f['fwd_ip'], f['fwd_ip'])}:{f['fwd_port'] or f['port']}"  # noqa: E731
    if cfg.get("upnp_enabled"):
        out.append(_issue("upnp_on", "info", "security", "site", "upnp", L("UPnP staat aan", "UPnP is on"),
                          L(f"Apparaten in je netwerk kunnen zelf poorten openzetten naar internet. Nu actief: {len(upnp)}",
                            f"Devices in your network can open ports to the internet themselves. Active now: {len(upnp)}")
                          + (f" ({', '.join(f['port'] + ' → ' + target(f) for f in upnp[:4])}{'…' if len(upnp) > 4 else ''})." if upnp else "."),
                          L("Gebruik je het alleen voor een spelcomputer, laat het dan aan met 'Secure mode'. Heb je het niet "
                            "nodig, zet het uit (UniFi: Instellingen → Internet → UPnP).", "If you only use it for a game "
                            "console, leave it on with 'Secure mode'. If you don't need it, turn it off (UniFi: Settings → "
                            "Internet → UPnP).")))
    for f in upnp:
        ports = _ports(f["port"])
        if ports and min(ports) < 1024:
            out.append(_issue(f"upnp_priv:{f['fwd_ip']}:{f['port']}", "warning", "security", "ip", f["fwd_ip"],
                              L(f"UPnP opent poort {f['port']} naar {who.get(f['fwd_ip'], f['fwd_ip'])}",
                                f"UPnP opens port {f['port']} to {who.get(f['fwd_ip'], f['fwd_ip'])}"),
                              L(f"Een apparaat heeft via UPnP poort {f['port']} ({f['proto'] or 'tcp/udp'}) op internet naar "
                                f"{target(f)} gezet. Poorten onder 1024 zijn standaarddiensten zoals web, mail of bestandsdeling.",
                                f"A device used UPnP to forward port {f['port']} ({f['proto'] or 'tcp/udp'}) from the internet to "
                                f"{target(f)}. Ports below 1024 are standard services such as web, mail or file sharing."),
                              L("Controleer of dit apparaat bereikbaar moet zijn vanaf internet. Zo niet, zet UPnP uit of blokkeer "
                                "het apparaat voor UPnP; werk de firmware van het apparaat bij.",
                                "Check whether this device needs to be reachable from the internet. If not, turn UPnP off or "
                                "block the device for UPnP; update the device's firmware.")))
    statics = [f for f in fw if not f["upnp"] and f["enabled"]]
    if not statics:
        return
    ext = [e for e in db.ips_events(ts - 24 * HOUR, "external") if not ips_ignored(e, ignores)]
    for f in statics:
        ports, fports = _ports(f["port"]), _ports(f["fwd_port"]) or _ports(f["port"])
        risky = sorted(p for p in ports | fports if p in RISKY_PORTS)
        if risky and f["src"] in ("any", "", None):
            p = risky[0]
            out.append(_issue(f"pf_risky:{f['port']}", "warning", "security", "ip", f["fwd_ip"],
                              L(f"{RISKY_PORTS[p]} open naar internet ({f['name']})", f"{RISKY_PORTS[p]} open to the internet ({f['name']})"),
                              L(f"Port forward '{f['name']}' zet poort {f['port']} voor iedereen door naar {target(f)}.",
                                f"Port forward '{f['name']}' forwards port {f['port']} for anyone to {target(f)}."),
                              L(f"{RISKY_PORTS[p]} hoort niet open op internet te staan: dit wordt continu gescand en aangevallen. "
                                "Gebruik een VPN (WireGuard, Teleport) om er van buitenaf bij te komen, of beperk de forward tot "
                                "vaste bron-adressen.", f"{RISKY_PORTS[p]} should not be open to the internet: it is scanned and "
                                "attacked constantly. Use a VPN (WireGuard, Teleport) to reach it from outside, or restrict the "
                                "forward to fixed source addresses.")))
        hit_ts = [e["ts"] for e in ext if e.get("dst_port") in ports
                  or (e.get("dst_ip") == f["fwd_ip"] and e.get("dst_port") in fports)]
        hits = len(hit_ts)
        if hits >= ATTACKED_MIN:
            out.append(_issue(f"pf_attacked:{f['port']}", "info", "security", "ip", f["fwd_ip"],
                              L(f"Port forward '{f['name']}' wordt aangevallen", f"Port forward '{f['name']}' is under attack"),
                              L(f"De IPS hield in 24 uur {hits} pogingen tegen op poort {f['port']} (→ {target(f)}).",
                                f"The IPS stopped {hits} attempts on port {f['port']} in 24 hours (→ {target(f)})."),
                              L("De IPS houdt bekende aanvallen tegen, maar dit is je meest bekeken deur. Houd de software achter "
                                "deze poort bijgewerkt, gebruik sterke wachtwoorden en overweeg de forward te beperken tot "
                                "bekende bron-adressen of een VPN.", "The IPS stops known attacks, but this is your most watched "
                                "door. Keep the software behind this port up to date, use strong passwords and consider "
                                "restricting the forward to known source addresses or a VPN."),
                              "ips_blocks", hits, ATTACKED_MIN, last_ts=max(hit_ts)))


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
        if i.get("group") or i.get("category") == "new":   # een nieuw apparaat is geen gezondheidsprobleem
            continue
        k = f"client:{i['client_mac']}" if i.get("client_mac") else i["key"]
        if k not in worst or SEVERITY_ORDER[i["severity"]] < SEVERITY_ORDER[worst[k]]:
            worst[k] = i["severity"]
    crit = sum(v == "critical" for v in worst.values())
    warn = sum(v == "warning" for v in worst.values())
    info = sum(v == "info" for v in worst.values())
    snap["health"] = {"score": max(0, min(100, 100 - 12 * crit - 4 * warn - 1 * info)),
                      "critical": crit, "warning": warn, "info": info, "total": len(issues), "muted": n_muted}
