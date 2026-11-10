"""Pollt de bron, berekent delta's (retries, poortfouten, throughput), detecteert
events, slaat alles op en draait de issue-regels."""
from __future__ import annotations

import asyncio
import httpx
import random
import logging
import re
import time

from . import rules
from .config import Settings
from .db import DB
from .mock import MockNetwork
from .notify import Notifier
from . import changes, i18n
from .i18n import L
from .ha_mqtt import HAMqtt
from .unifi_client import (UnifiClient, config_from_raw, normalize_config, normalize_flow, normalize_ips, normalize_legacy, normalize_usage, normalize_speedtest_state,
                           normalize_speedtests, wan_rates, normalize_client_usage, normalize_dpi)
from . import advisories, backups, bufferbloat, schedules, vulnscan

log = logging.getLogger(__name__)


def _delta(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None:
        return None
    return cur - prev if cur >= prev else None   # teller-reset → onbekend


def _num_or(*vals):
    return next((float(v) for v in vals if isinstance(v, (int, float))), None)


def _retry_pct(pk: float | None, rt: float | None, ppk: float | None, prt: float | None) -> float | None:
    dpk, drt = _delta(pk, ppk), _delta(rt, prt)
    if dpk is None or drt is None:   # eerste meting: cumulatieve verhouding
        dpk, drt = pk, rt
    if not dpk or drt is None:
        return None
    return round(min(100.0, 100.0 * drt / dpk), 1)


FLOW_HOURS = 48   # verbindingen zijn talrijk (duizenden per uur): kort bewaren


class Collector:
    def __init__(self, settings: Settings, db: DB):
        self.s = settings
        self.db = db
        self.mock = MockNetwork() if settings.mode == "mock" else None
        self.client = None if self.mock else UnifiClient(settings, persist_pin=True)
        self.prev: dict | None = None
        self.latest: dict | None = db.get_kv("latest")
        self.last_error: str | None = None
        self.last_ok: int | None = None
        self.ips_available: bool | None = True if self.mock else None
        self._ips_checked = 0
        self.config: dict | None = None          # wifi-instellingen, UPnP, port forwards
        self._cfg_checked = 0
        self.sysinfo: dict = {"network_version": "demo", "hardware": "UOSSERVER"} if self.mock else {}
        self._sys_checked = 0
        self.optional: dict[str, str | None] = {}   # optionele bronnen → None (ok) of foutmelding
        self.notifier = Notifier(settings, db)
        self._live: dict | None = None            # laatste live-meting van de gateway
        self._live_lock = asyncio.Lock()
        self._st_checked = 0
        self.speedtest = {"running": False, "started": None, "error": None}
        self.flows_available: bool | None = True if self.mock else None
        self._usage_checked = 0
        self.ha = HAMqtt(settings, self)
        self._flows_checked = 0
        self.insights: dict = db.get_kv("insights") or {}   # storingen, verbindingspogingen, anomalieën, buren-wifi
        self._ins_checked = 0
        self._cu_checked = 0
        self.dpi: list[dict] = []
        self.advisories: dict = db.get_kv("advisories") or {}
        self.vuln = vulnscan.VulnScan(settings, db, self.mock)
        self._adv_checked = 0
        self.bloat_history: list[dict] = (self.db.get_kv("bufferbloat") or {}).get("items", [])
        self._bloat: dict | None = None
        self._bk_checked = 0
        self.backup_status: dict = {"checked": None, "error": None}
        if self.mock and not self.bloat_history:
            self.bloat_history = [{"ts": int(time.time()) - 86400, "host": "demo", "idle": 9.0, "down": 33.0, "up": 121.0,
                                   "added_down": 24.0, "added_up": 112.0, "worst": 112.0, "grade": "C"}]

    async def _fetch(self, dt: float) -> dict:
        if self.mock:
            data = normalize_legacy(*self.mock.snapshot(dt))
            data["source"] = "mock"
            return data
        return await self.client.fetch()

    # --------------------------------------------------------------- enrich
    def _enrich(self, snap: dict) -> list[dict]:
        prev = self.prev
        ts = snap["ts"]
        dt = max(1, ts - prev["ts"]) if prev else None
        events: list[dict] = []
        pdev = {d["mac"]: d for d in prev["devices"]} if prev else {}
        pcli = {c["mac"]: c for c in prev["clients"]} if prev else {}

        def ev(kind: str, etype: str, eid: str, nl: str, en: str) -> None:
            events.append({"ts": ts, "kind": kind, "entity_type": etype, "entity_id": eid, "message": i18n.bi(nl, en)})

        for d in snap["devices"]:
            p = pdev.get(d["mac"])
            if p:
                if p["state"] == "online" and d["state"] != "online":
                    ev("device_offline", "device", d["mac"], f"{d['name']} is {d['state']}", f"{d['name']} is {d['state']}")
                elif p["state"] != "online" and d["state"] == "online":
                    ev("device_online", "device", d["mac"], f"{d['name']} is weer online", f"{d['name']} is back online")
                if d["uptime"] and p["uptime"] and d["uptime"] + 120 < p["uptime"]:
                    ev("device_reboot", "device", d["mac"], f"{d['name']} is herstart", f"{d['name']} restarted")
                if p.get("version") and d.get("version") and p["version"] != d["version"]:
                    ev("device_upgrade", "device", d["mac"], f"{d['name']} bijgewerkt naar {d['version']}",
                       f"{d['name']} updated to {d['version']}")
            prad = {r["radio"]: r for r in (p or {}).get("radios", [])}
            for r in d["radios"]:
                if r.get("retry_pct") is None:
                    pr = prad.get(r["radio"], {})
                    r["retry_pct"] = _retry_pct(r["tx_packets"], r["tx_retries"], pr.get("tx_packets"), pr.get("tx_retries"))
            pports = {x["idx"]: x for x in (p or {}).get("ports", [])}
            for port in d["ports"]:
                pp = pports.get(port["idx"])
                if pp and dt:
                    e = [_delta(port[k], pp[k]) for k in ("rx_errors", "tx_errors")]
                    dr = [_delta(port[k], pp[k]) for k in ("rx_dropped", "tx_dropped")]
                    port["errors_delta"] = sum(x for x in e if x is not None)
                    port["drops_delta"] = sum(x for x in dr if x is not None)
                    rx, tx = _delta(port["rx_bytes"], pp["rx_bytes"]), _delta(port["tx_bytes"], pp["tx_bytes"])
                    port["rx_bps"] = rx * 8 / dt if rx is not None else None
                    port["tx_bps"] = tx * 8 / dt if tx is not None else None
                    if pp["up"] and not port["up"]:
                        ev("port_down", "port", f"{d['mac']}#{port['idx']}", f"{d['name']} · {port['name']}: link weg",
                           f"{d['name']} · {port['name']}: link lost")
                    elif not pp["up"] and port["up"]:
                        ev("port_up", "port", f"{d['mac']}#{port['idx']}",
                           f"{d['name']} · {port['name']}: link op {int(port['speed'])} Mbit",
                           f"{d['name']} · {port['name']}: link up at {int(port['speed'])} Mbit")
        # Generieke poortnamen ("Port 7") aanvullen met wat erop aangesloten zit.
        attached = {(c["sw_mac"], c["sw_port"]): c["name"] for c in snap["clients"] if c["wired"]}
        attached.update({(d["uplink_mac"], d["uplink_port"]): d["name"] for d in snap["devices"] if d["uplink_mac"]})
        for d in snap["devices"]:
            for port in d["ports"]:
                who = attached.get((d["mac"], port["idx"]))
                if who and port["name"].lower().startswith("port"):
                    port["name"] = L(f"poort {port['idx']} ({who})", f"port {port['idx']} ({who})")
        devnames = {d["mac"]: d["name"] for d in snap["devices"]}
        for c in snap["clients"]:
            p = pcli.get(c["mac"], {})
            if not c["wired"]:
                if c.get("retry_pct") is None:
                    c["retry_pct"] = _retry_pct(c["tx_packets"], c["tx_retries"],
                                                p.get("tx_packets"), p.get("tx_retries"))
                if p and p.get("ap_mac") and c["ap_mac"] and c["ap_mac"] != p["ap_mac"]:
                    msg = f"{c['name']}: {devnames.get(p['ap_mac'], '?')} → {devnames.get(c['ap_mac'], '?')}"
                    ev("roam", "client", c["mac"], msg, msg)
            else:
                c["retry_pct"] = None
            if prev and not p:
                ev("client_join", "client", c["mac"], f"{c['name']} verbonden", f"{c['name']} connected")
        if prev:
            cur = {c["mac"] for c in snap["clients"]}
            for mac, c in pcli.items():
                if mac not in cur:
                    ev("client_leave", "client", mac, f"{c['name']} niet meer verbonden", f"{c['name']} disconnected")
        return events

    async def _collect_ips(self, ts: int, dt: float) -> None:
        """IPS-blokkades bijhouden: in demo elke tick, live hooguit elke 5 minuten."""
        if self.mock:
            self.db.store_ips([normalize_ips(f) for f in self.mock.ips_flows(ts, dt)])
            return
        if ts - self._ips_checked < 300:
            return
        self._ips_checked = ts
        since = max(self.db.last_ips_ts() or 0, ts - self.s.retention_days * 86400) - 120
        try:
            rows = await self.client.fetch_ips(since * 1000, ts * 1000)
        except Exception as e:  # noqa: BLE001 – IPS is bijzaak, poll mag doorgaan
            log.warning("IPS-flows: %s", e)
            self.optional["ips"] = str(e)
            return
        self.ips_available = rows is not None
        self.optional["ips"] = None if rows is not None else L("alleen via de uitgebreide API", "only via the extended API")
        if rows:
            n = self.db.store_ips(rows)
            if n:
                log.info("IPS: %s nieuwe blokkades", n)

    async def _collect_flows(self, ts: int, dt: float) -> None:
        """Verbindingen voor de wereldkaart: in demo elke tick, live elke minuut (UniFi levert ze per minuut)."""
        if self.mock:
            self.db.store_flows([normalize_flow(f) for f in self.mock.flows(ts, dt)])
            return
        if ts - self._flows_checked < 60:
            return
        self._flows_checked = ts
        since = max(self.db.last_flow_ts() or 0, ts - 3600) - 300   # overlap: lange verbindingen worden bijgewerkt
        try:
            rows = await self.client.fetch_flows(since * 1000, ts * 1000)
        except Exception as e:  # noqa: BLE001 – bijzaak, poll mag doorgaan
            log.warning("Verbindingen: %s", e)
            self.optional["flows"] = str(e)
            return
        self.flows_available = rows is not None
        self.optional["flows"] = None if rows is not None else L("alleen via de uitgebreide API", "only via the extended API")
        if rows:
            self.db.store_flows(rows)

    async def _collect_config(self, ts: int) -> None:
        """Instellingen veranderen zelden: live elke 15 minuten, demo altijd."""
        if self.mock:
            raw = self.mock.config_raw()
            self.config = config_from_raw(raw)
            self._track("fp_config", changes.config_fingerprint(raw, self._salt()), ts)
            return
        if ts - self._cfg_checked < 900:
            return
        self._cfg_checked = ts
        try:
            raw = await self.client.fetch_config_raw()
            if raw is not None:
                self.config = config_from_raw(raw)
                self._track("fp_config", changes.config_fingerprint(raw, self._salt()), ts)
            self.optional["config"] = None if raw is not None else L("alleen via de uitgebreide API", "only via the extended API")
        except Exception as e:  # noqa: BLE001 – optioneel
            log.warning("Instellingen ophalen: %s", e)
            self.optional["config"] = str(e)
        if ts - self._sys_checked >= 3600:
            self._sys_checked = ts
            try:
                self.sysinfo = await self.client.sysinfo() or self.sysinfo
            except Exception as e:  # noqa: BLE001
                self.optional["sysinfo"] = str(e)

    # ------------------------------------------------------------ inzichten
    async def _collect_insights(self, ts: int) -> None:
        """Elk kwartier: internetstoringen (90 dagen), verbindingspogingen, anomalieën en wifi in de buurt."""
        if ts - self._ins_checked < 900:
            return
        self._ins_checked = ts
        try:
            data = self.mock.insights(ts) if self.mock else await self.client.insights(ts)
        except Exception as e:  # noqa: BLE001 – optioneel
            log.warning("Inzichten ophalen: %s", e)
            self.optional["insights"] = str(e)
            return
        self.optional["insights"] = None if data is not None else L("alleen via de uitgebreide API", "only via the extended API")
        if not data:
            return
        for w in data.get("wan_history") or []:
            self.db.store_outages([{**o, "wan": w["wan"]} for o in w["outages"]])
        self.insights = {**self.insights, **data, "ts": ts}
        self.db.set_kv("insights", self.insights)

    async def sync_client_usage(self, force: bool = False) -> None:
        """Verkeer per apparaat (per uur en per dag) en, als UniFi dat meet, per categorie. Elk uur."""
        now = int(time.time())
        if not force and now - self._cu_checked < 3600:
            return
        self._cu_checked = now
        try:
            for period, back in (("hour", 48 * 3600), ("day", 35 * 86400)):
                if self.mock:
                    rows = normalize_client_usage(self.mock.client_usage(period, now))
                else:
                    if self.client.source not in ("legacy-key", "legacy-login"):
                        return
                    rows = await self.client.client_usage(period, now - back, now)
                self.db.store_client_usage(period, rows)
            self.dpi = normalize_dpi(self.mock.dpi()) if self.mock else await self.client.client_dpi()
            self.optional["client_usage"] = None
        except Exception as e:  # noqa: BLE001 – optioneel
            log.warning("Verbruik per apparaat: %s", e)
            self.optional["client_usage"] = str(e)

    async def _collect_advisories(self, ts: int) -> None:
        """Beveiligingsadviezen van Ubiquiti: elke 6 uur de openbare feed (demo: ingebouwde voorbeelden)."""
        if (self.s.advisories is False) or ts - self._adv_checked < 6 * 3600:
            return
        self._adv_checked = ts
        if self.mock:
            self.advisories = {"items": advisories.demo(ts), "fetched": ts, "error": None}
            return
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as http:
                items = await advisories.fetch(http)
            self.advisories = {"items": items, "fetched": ts, "error": None}
        except Exception as e:  # noqa: BLE001 – internet weg of feed veranderd: oude lijst houden
            log.info("Beveiligingsadviezen: %s", e)
            self.advisories = {**self.advisories, "error": str(e)[:200]}
        self.db.set_kv("advisories", self.advisories)

    def _track_wan_ip(self, snap: dict, ts: int) -> None:
        """Publiek IP-adres gewijzigd? Op de tijdlijn, en een melding die een dag blijft staan."""
        ip = (snap.get("wan") or {}).get("wan_ip") or ""
        if not ip:
            return
        kv = self.db.get_kv("wan_ip") or {}
        if kv.get("ip") and kv["ip"] != ip:
            kv = {"ip": ip, "old": kv["ip"], "changed": ts}
            self.db.add_events([{"ts": ts, "kind": "wan_ip", "entity_type": "wan", "entity_id": "wan",
                                 "message": i18n.bi(f"Publiek IP-adres gewijzigd: {kv['old']} → {ip}",
                                                    f"Public IP address changed: {kv['old']} → {ip}")}])
            self.db.set_kv("wan_ip", kv)
        elif not kv.get("ip"):
            self.db.set_kv("wan_ip", {"ip": ip})
        snap["wan_ip_change"] = kv if kv.get("changed") and ts - kv["changed"] < 86400 else None

    async def _apply_schedules(self, ts: int) -> None:
        """Vaste pauzetijden afdwingen. Wat een schema blokkeerde, laat het ook weer toe (een handmatige pauze niet)."""
        sch = self.db.schedules()
        want = schedules.wanted(sch, ts)
        state = self.db.get_kv("sched_blocked") or {}
        manual = {p["mac"] for p in self.db.pauses()}
        names = {c["mac"]: c["name"] for c in (self.latest or {}).get("clients", [])}
        changed = False
        for mac, w in want.items():
            if mac in state or mac in manual:
                if mac in state and state[mac].get("until") != w["until"]:
                    state[mac] = {**state[mac], "until": w["until"]}
                    changed = True
                continue
            try:
                await self.set_blocked(mac, True)
            except Exception as e:  # noqa: BLE001 – volgende ronde opnieuw
                log.warning("Schema '%s' voor %s: %s", w["name"], mac, e)
                continue
            state[mac] = {"schedule": w["name"], "until": w["until"], "name": names.get(mac, mac)}
            until = time.strftime("%H:%M", time.localtime(w["until"]))
            nm = state[mac]["name"]
            self.db.add_events([{"ts": ts, "kind": "client_leave", "entity_type": "client", "entity_id": mac,
                                 "message": i18n.bi(f"{nm}: gepauzeerd volgens '{w['name']}' tot {until}",
                                                    f"{nm}: paused by '{w['name']}' until {until}")}])
            changed = True
        for mac in [m for m in state if m not in want]:
            if mac not in manual:
                try:
                    await self.set_blocked(mac, False)
                except Exception as e:  # noqa: BLE001
                    log.warning("Schema opheffen voor %s: %s", mac, e)
                    continue
                nm = state[mac].get("name", mac)
                self.db.add_events([{"ts": ts, "kind": "client_join", "entity_type": "client", "entity_id": mac,
                                     "message": i18n.bi(f"{nm}: pauzetijd '{state[mac].get('schedule')}' voorbij",
                                                        f"{nm}: pause time '{state[mac].get('schedule')}' over")}])
            del state[mac]
            changed = True
        if changed:
            self.db.set_kv("sched_blocked", state)

    async def release_schedule(self, sid: int | None = None) -> None:
        """Na wijzigen of verwijderen van een schema: meteen opnieuw toepassen."""
        await self._apply_schedules(int(time.time()))

    # ------------------------------------------------------------ internet pauzeren
    async def set_blocked(self, mac: str, blocked: bool) -> None:
        if self.mock:
            (self.mock.blocked.add if blocked else self.mock.blocked.discard)(mac)
            return
        await self.client.block(mac, blocked)

    async def _expire_pauses(self, ts: int) -> None:
        """Pauzes waarvan de tijd om is: apparaat weer toelaten."""
        for p in self.db.pauses():
            if p["until"] and p["until"] <= ts:
                try:
                    await self.set_blocked(p["mac"], False)
                except Exception as e:  # noqa: BLE001 – volgende ronde opnieuw
                    log.warning("Pauze opheffen voor %s: %s", p["mac"], e)
                    continue
                self.db.clear_pause(p["mac"])
                self.db.add_events([{"ts": ts, "kind": "client_join", "entity_type": "client", "entity_id": p["mac"],
                                     "message": i18n.bi(f"{p['name']}: pauze voorbij, mag weer online",
                                                        f"{p['name']}: pause over, back online")}])

    # ------------------------------------------------------------ wijzigingslog
    def _salt(self) -> str:
        """Willekeurig zout per installatie, zodat wachtwoord-hashes in de database niets zeggen."""
        kv = self.db.get_kv("fp_salt")
        if not kv:
            import secrets
            kv = {"salt": secrets.token_hex(16)}
            self.db.set_kv("fp_salt", kv)
        return kv["salt"]

    def _track(self, key: str, fp: dict, ts: int) -> None:
        """Vergelijk een vingerafdruk met de vorige en zet verschillen als 'config'-gebeurtenis op de tijdlijn.
        De eerste keer wordt alleen de beginstand bewaard."""
        old = self.db.get_kv(key)
        if old is not None and old != fp:
            names = {d["mac"]: d["name"] for d in (self.latest or {}).get("devices", [])}
            evs = changes.diff(old, fp, names)
            self.db.add_events([{"ts": ts, "kind": "config", **e} for e in evs])
            if evs:
                log.info("Wijzigingslog: %s", "; ".join(i18n.pick(e["message"], "nl") for e in evs[:5]))
        if old != fp:
            self.db.set_kv(key, fp)

    # ------------------------------------------------------------ internet
    def _gateway_mac(self) -> str | None:
        return next((d["mac"] for d in (self.latest or {}).get("devices", []) if d["type"] == "gateway"), None)

    async def _gateway_raw(self) -> dict:
        if self.mock:
            self.mock.now = int(time.time())
            return self.mock.stat_device(0, [])[0]
        mac = self._gateway_mac()
        if not mac:
            raise RuntimeError(L("Geen gateway gevonden", "No gateway found"))
        return await self.client.gateway(mac)

    async def live_wan(self) -> dict:
        """Actueel internetverkeer. Hooguit elke 2 s naar de controller; 'updated' = wanneer de gateway
        voor het laatst nieuwe tellers doorgaf (UniFi doet dat om de 10–45 s)."""
        async with self._live_lock:
            now = time.time()
            if self._live and now - self._live["ts"] < 2:
                return self._live
            gw = await self._gateway_raw()
            r = wan_rates(gw)
            prev = self._live or {}
            changed = bool(self.mock) or (r["rx_bytes"], r["tx_bytes"]) != (prev.get("rx_bytes"), prev.get("tx_bytes"))
            st = normalize_speedtest_state(gw.get("speedtest-status") or {})
            self._live = {**r, "ts": now, "updated": now if changed or not prev else prev["updated"],
                          "latency_ms": _num_or((gw.get("uplink") or {}).get("latency"), (self.latest or {}).get("wan", {}).get("latency_ms")),
                          "speedtest": st}
            await self._speedtest_progress(st)
            return self._live

    async def _speedtest_progress(self, st: dict) -> None:
        s = self.speedtest
        if s["running"] and not st["running"] and st["rundate"] and st["rundate"] >= (s["started"] or 0) - 5:
            s["running"] = False   # klaar: eerst het archief van UniFi, anders het resultaat van de gateway zelf
            self._bloat_done()
            await self.sync_speedtests(force=True)
            if st["down"]:
                self.db.store_speedtests([{"ts": st["rundate"], "down": st["down"], "up": st["up"],
                                           "latency": st["latency"], "server": ""}])
        elif s["running"] and s["started"] and time.time() - s["started"] > 180:
            s.update(running=False, error=L("De test duurde te lang en is afgebroken.", "The test took too long and was stopped."))
            self._bloat = None

    async def start_speedtest(self) -> None:
        s = self.speedtest
        if s["running"]:
            raise RuntimeError(L("Er loopt al een speedtest.", "A speed test is already running."))
        if s["started"] and time.time() - s["started"] < 60:
            raise RuntimeError(L("Wacht een minuut tussen twee tests.", "Wait a minute between two tests."))
        prev = s["started"]
        s.update(running=True, started=time.time(), error=None)   # meteen, zodat een tweede klik geen tweede test start
        try:
            probed = await self._bloat_prepare()
            if self.mock:
                self.mock.start_speedtest(time.time())
            else:
                mac = self._gateway_mac()
                if not mac:
                    raise RuntimeError(L("Geen gateway gevonden", "No gateway found"))
                await self.client.speedtest_start(mac)
        except Exception:
            s.update(running=False, started=prev)
            raise
        s["started"] = time.time()
        self._live = None
        if probed:
            asyncio.create_task(self._bloat_measure(*probed))

    # ---------------------------------------------------------------- backups
    async def collect_backups(self, force: bool = False, create: bool = False) -> None:
        """Elke 6 uur de automatische backups kopiëren; desgewenst eens per dag een verse laten maken."""
        now, d = int(time.time()), self.s.data_dir
        public = (self.s.backup_keys or {}).get("public")
        if not force and now - self._bk_checked < 6 * 3600:
            return
        self._bk_checked = now
        try:
            if self.mock:
                for b in self.mock.backups(now):
                    if not backups.has(d, b["filename"]):
                        backups.store(d, b["filename"], b"demo: geen echte backup / not a real backup\n", b["time"], public)
            else:
                rows = await self.client.backups_list()
                if rows is None:
                    self.backup_status.update(error=L("Alleen via de uitgebreide UniFi-API.", "Only via the extended UniFi API."))
                    return
                for row in rows:
                    name = row.get("filename") or ""
                    if not backups.NAME_RE.match(name) or backups.has(d, name):
                        continue
                    data = await self.client.backup_download(f"/dl/autobackup/{name}")
                    if row.get("size") and len(data) != row["size"]:
                        raise RuntimeError(L(f"Backup {name} kwam niet volledig binnen.", f"Backup {name} did not arrive completely."))
                    backups.store(d, name, data, (row.get("time") or 0) / 1000 or None, public)
            made = (self.db.get_kv("backup_made") or {}).get("ts", 0)
            if create or (self.s.backup_daily and now - made >= 86400 - 600):
                data = b"demo: geen echte backup / not a real backup\n" if self.mock else await self.client.backup_create()
                ver = re.sub(r"[^0-9.]", "", str(self.sysinfo.get("network_version") or "")) or "x"
                backups.store(d, f"sonar_{ver}_{time.strftime('%Y%m%d_%H%M', time.localtime(now))}.unf", data, now, public)
                self.db.set_kv("backup_made", {"ts": now})
            backups.prune(d)
            self.backup_status.update(checked=now, error=None)
        except Exception as e:  # noqa: BLE001 – bijzaak
            log.warning("UniFi-backups: %s", e)
            self.backup_status.update(checked=now, error=str(e) or type(e).__name__)

    # ---------------------------------------------------------------- vertraging onder belasting
    async def _bloat_prepare(self):
        """Eerst meten hoe snel het antwoord is op een rustige lijn. Mislukt dit, dan gaat de speedtest gewoon door."""
        try:
            if self.mock:
                host, probe = "demo", self._mock_probe
            else:
                found = await bufferbloat.make_probe()
                if not found:
                    return None
                host, probe = found
            idle = []
            for _ in range(5):
                idle.append(await probe())
                await asyncio.sleep(0.15)
            self._bloat = {"host": host, "idle": idle, "download": [], "upload": [], "load": []}
            return (probe,)
        except Exception as e:  # noqa: BLE001 – bijzaak
            log.info("Vertraging onder belasting: %s", e)
            return None

    async def _mock_probe(self) -> float:
        return self.mock.probe_ms(time.time())

    async def _bloat_measure(self, probe) -> None:
        """Meet tijdens de test. Vraagt zelf de voortgang op, zodat het ook werkt als de pagina Internet niet openstaat
        (bijvoorbeeld bij de knop in Home Assistant)."""
        phase, asked, started = None, 0.0, time.monotonic()
        while self._bloat is not None and time.monotonic() - started < 190:
            try:
                if time.monotonic() - asked >= 2:
                    asked = time.monotonic()
                    phase = (await self.live_wan())["speedtest"].get("phase")
                    if self._bloat is None:
                        return
                if self.speedtest["running"] and phase != "ping" and time.monotonic() - started > 3:
                    ms = await probe()
                    if self._bloat is not None:
                        self._bloat["load" if phase is None else phase].append(ms)
            except Exception as e:  # noqa: BLE001 – bijzaak, de speedtest loopt door
                log.info("Vertraging onder belasting: %s", e)
            await asyncio.sleep(bufferbloat.INTERVAL)
        self._bloat = None

    def _bloat_done(self) -> None:
        b, self._bloat = self._bloat, None
        r = bufferbloat.summarize(b, b["host"], int(time.time())) if b else None
        if r:
            self.bloat_history = (self.bloat_history + [r])[-20:]
            self.db.set_kv("bufferbloat", {"items": self.bloat_history})

    async def sync_speedtests(self, force: bool = False) -> None:
        """Speedtest-historie van de controller overnemen (elk uur), zodat hij langer bewaard blijft."""
        now = int(time.time())
        if not force and now - self._st_checked < 3600:
            return
        self._st_checked = now
        try:
            if self.mock:
                rows = normalize_speedtests(self.mock.speedtest_history(now))
            else:
                if self.client.source not in ("legacy-key", "legacy-login"):
                    return
                rows = await self.client.speedtests(now - 90 * 86400, now)
            self.db.store_speedtests(rows)
            self.optional["speedtest"] = None
        except Exception as e:  # noqa: BLE001 – optioneel
            log.warning("Speedtest-historie: %s", e)
            self.optional["speedtest"] = str(e)

    async def sync_usage(self, force: bool = False) -> None:
        """Datagebruik per dag en maand van de controller overnemen (elk uur), zodat het langer bewaard blijft."""
        now = int(time.time())
        if not force and now - self._usage_checked < 3600:
            return
        self._usage_checked = now
        try:
            for period, days in (("day", 400), ("month", 3 * 366)):
                if self.mock:
                    rows = normalize_usage(self.mock.usage_report(period, now))
                else:
                    if self.client.source not in ("legacy-key", "legacy-login"):
                        return
                    rows = await self.client.usage(period, now - days * 86400, now)
                self.db.store_usage(period, rows)
            self.optional["usage"] = None
        except Exception as e:  # noqa: BLE001 – optioneel
            log.warning("Datagebruik: %s", e)
            self.optional["usage"] = str(e)

    # ---------------------------------------------------------------- tick
    async def tick(self, ts: int | None = None, dt: float | None = None) -> dict:
        ts = int(ts or time.time())
        if self.mock:
            self.mock.now = ts
        snap = await self._fetch(dt or self.s.poll_seconds)
        snap["ts"] = ts
        events = self._enrich(snap)
        self.db.store(snap, events)
        self.db.register_clients(snap["clients"], ts)
        self._track("fp_devices", changes.device_fingerprint(snap["devices"]), ts)
        await self._expire_pauses(ts)
        await self._collect_ips(ts, dt or self.s.poll_seconds)
        await self._collect_flows(ts, dt or self.s.poll_seconds)
        await self._collect_config(ts)
        await self._collect_insights(ts)
        await self._apply_schedules(ts)
        self._track_wan_ip(snap, ts)
        snap["config"] = self.config
        snap["insights"] = self.insights_for_rules(snap)
        snap["bufferbloat"] = next((b for b in self.bloat_history[-1:] if ts - b["ts"] < 14 * 86400), None)
        if not self.mock or ts >= time.time() - 120:   # demo: alleen bij echte metingen, niet tijdens het vullen
            await self.sync_speedtests()
            await self.sync_usage()
        await self.sync_client_usage()       # zelf elk uur (wandklok), dus ook tijdens het vullen van de demo maar één keer
        await self._collect_advisories(ts)
        await self.vuln.tick(snap, ts)
        await self.collect_backups()
        snap["backups"] = backups.summary(self.s.data_dir, self.s.backup_daily) if self.backup_status["checked"] else None
        # In beide talen, zodat wisselen van taal direct werkt en ook opgeloste meldingen meegaan.
        tr = i18n.both(lambda: rules.evaluate(snap, self.db, self.s.thresholds, ts))
        issues = i18n.merge_issues(tr["nl"], tr["en"])
        self.db.sync_issues(issues, ts)
        snap["issues"] = issues
        self.apply_mutes(snap, ts)
        self.prev = snap
        self.latest = snap
        self.last_ok = ts
        self.last_error = None
        return snap

    def insights_for_rules(self, snap: dict) -> dict:
        si = self.sysinfo or {}
        inv = advisories.inventory(snap.get("devices", []), si.get("network_version"))
        items = (self.advisories or {}).get("items") or [] if self.s.advisories is not False else []
        return {**self.insights, "advisories": vulnscan.mark_exploited(advisories.match(items, inv), self.vuln.kev_items),
                "vuln": self.vuln.for_rules(snap.get("config"))}

    async def language_changed(self) -> None:
        """Andere taal gekozen: Home Assistant krijgt de sensornamen opnieuw in die taal."""
        if self.ha.cfg.get("enabled"):
            await self.ha.stop()
            self.ha.start()

    def apply_mutes(self, snap: dict | None = None, now: int | None = None) -> None:
        """Markeer genegeerde issues en herbereken scores (ook direct na (de)negeren)."""
        snap = snap or self.latest
        if not snap:
            return
        muted = self.db.muted(int(now or time.time()))
        for i in snap["issues"]:
            m = muted.get(i["key"]) or muted.get(i.get("group") or "")
            i["muted"] = bool(m)
            i["muted_until"] = m["until"] if m else None
        rules.attach_scores(snap, snap["issues"])

    async def seed_history(self) -> None:
        """Mockmodus: vul de database met een paar uur gesimuleerde historie."""
        if not self.mock or not self.db.is_empty() or self.s.mock_seed_hours <= 0:
            return
        step = self.s.poll_seconds
        now = int(time.time())
        start = now - self.s.mock_seed_hours * 3600
        log.info("Demohistorie aanmaken: %s uur (en een week grove historie)", self.s.mock_seed_hours)
        self.mock.backfill(self.db, start - 7 * 86400, start)
        rnd = random.Random(11)
        for ts in range(start - 42 * 3600, start, 300):   # verbindingen: 48 uur voor de wereldkaart
            self.db.store_flows([normalize_flow(f) for f in self.mock.flows(ts, 300, rnd)])
        for ts in range(start, now - step, step):
            await self.tick(ts=ts, dt=step)
        # De laatste tick schrijft 'latest' weg zodat het dashboard direct data heeft.
        self.db.set_kv("latest", self.latest)

    async def run(self) -> None:
        last_purge = 0
        self.ha.start()
        while True:
            try:
                snap = await self.tick()
                self.db.set_kv("latest", self.latest)
                self.ha.publish_state()
                if time.time() - last_purge > 3600:
                    self.db.purge(int(time.time()) - self.s.retention_days * 86400)
                    self.db.purge_flows(int(time.time()) - FLOW_HOURS * 3600)
                    last_purge = time.time()
            except Exception as e:  # noqa: BLE001 – collector mag niet stoppen
                self.last_error = str(e)
                log.exception("Poll mislukt")
                await self.notifier.collector_error(str(e), time.time())
            else:
                try:
                    await self.notifier.process(snap, snap["ts"])
                except Exception:  # noqa: BLE001 – meldingen zijn bijzaak
                    log.exception("Meldingen versturen mislukt")
            await asyncio.sleep(self.s.poll_seconds)
