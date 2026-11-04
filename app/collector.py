"""Pollt de bron, berekent delta's (retries, poortfouten, throughput), detecteert
events, slaat alles op en draait de issue-regels."""
from __future__ import annotations

import asyncio
import logging
import time

from . import rules
from .config import Settings
from .db import DB
from .mock import MockNetwork
from .unifi_client import UnifiClient, normalize_ips, normalize_legacy

log = logging.getLogger(__name__)


def _delta(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None:
        return None
    return cur - prev if cur >= prev else None   # teller-reset → onbekend


def _retry_pct(pk: float | None, rt: float | None, ppk: float | None, prt: float | None) -> float | None:
    dpk, drt = _delta(pk, ppk), _delta(rt, prt)
    if dpk is None or drt is None:   # eerste meting: cumulatieve verhouding
        dpk, drt = pk, rt
    if not dpk or drt is None:
        return None
    return round(min(100.0, 100.0 * drt / dpk), 1)


class Collector:
    def __init__(self, settings: Settings, db: DB):
        self.s = settings
        self.db = db
        self.mock = MockNetwork() if settings.mode == "mock" else None
        self.client = None if self.mock else UnifiClient(settings)
        self.prev: dict | None = None
        self.latest: dict | None = db.get_kv("latest")
        self.last_error: str | None = None
        self.last_ok: int | None = None
        self.ips_available: bool | None = True if self.mock else None
        self._ips_checked = 0

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

        def ev(kind: str, etype: str, eid: str, msg: str) -> None:
            events.append({"ts": ts, "kind": kind, "entity_type": etype, "entity_id": eid, "message": msg})

        for d in snap["devices"]:
            p = pdev.get(d["mac"])
            if p:
                if p["state"] == "online" and d["state"] != "online":
                    ev("device_offline", "device", d["mac"], f"{d['name']} is {d['state']}")
                elif p["state"] != "online" and d["state"] == "online":
                    ev("device_online", "device", d["mac"], f"{d['name']} is weer online")
                if d["uptime"] and p["uptime"] and d["uptime"] + 120 < p["uptime"]:
                    ev("device_reboot", "device", d["mac"], f"{d['name']} is herstart")
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
                        ev("port_down", "port", f"{d['mac']}#{port['idx']}", f"{d['name']} · {port['name']}: link weg")
                    elif not pp["up"] and port["up"]:
                        ev("port_up", "port", f"{d['mac']}#{port['idx']}",
                           f"{d['name']} · {port['name']}: link op {int(port['speed'])} Mbit")
        # Generieke poortnamen ("Port 7") aanvullen met wat erop aangesloten zit.
        attached = {(c["sw_mac"], c["sw_port"]): c["name"] for c in snap["clients"] if c["wired"]}
        attached.update({(d["uplink_mac"], d["uplink_port"]): d["name"] for d in snap["devices"] if d["uplink_mac"]})
        for d in snap["devices"]:
            for port in d["ports"]:
                who = attached.get((d["mac"], port["idx"]))
                if who and port["name"].lower().startswith("port"):
                    port["name"] = f"poort {port['idx']} ({who})"
        devnames = {d["mac"]: d["name"] for d in snap["devices"]}
        for c in snap["clients"]:
            p = pcli.get(c["mac"], {})
            if not c["wired"]:
                if c.get("retry_pct") is None:
                    c["retry_pct"] = _retry_pct(c["tx_packets"], c["tx_retries"],
                                                p.get("tx_packets"), p.get("tx_retries"))
                if p and p.get("ap_mac") and c["ap_mac"] and c["ap_mac"] != p["ap_mac"]:
                    ev("roam", "client", c["mac"],
                       f"{c['name']}: {devnames.get(p['ap_mac'], '?')} → {devnames.get(c['ap_mac'], '?')}")
            else:
                c["retry_pct"] = None
            if prev and not p:
                ev("client_join", "client", c["mac"], f"{c['name']} verbonden")
        if prev:
            cur = {c["mac"] for c in snap["clients"]}
            for mac, c in pcli.items():
                if mac not in cur:
                    ev("client_leave", "client", mac, f"{c['name']} niet meer verbonden")
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
            return
        self.ips_available = rows is not None
        if rows:
            n = self.db.store_ips(rows)
            if n:
                log.info("IPS: %s nieuwe blokkades", n)

    # ---------------------------------------------------------------- tick
    async def tick(self, ts: int | None = None, dt: float | None = None) -> dict:
        ts = int(ts or time.time())
        if self.mock:
            self.mock.now = ts
        snap = await self._fetch(dt or self.s.poll_seconds)
        snap["ts"] = ts
        events = self._enrich(snap)
        self.db.store(snap, events)
        await self._collect_ips(ts, dt or self.s.poll_seconds)
        issues = rules.evaluate(snap, self.db, self.s.thresholds, ts)
        self.db.sync_issues(issues, ts)
        snap["issues"] = issues
        self.apply_mutes(snap, ts)
        self.prev = snap
        self.latest = snap
        self.last_ok = ts
        self.last_error = None
        return snap

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
        log.info("Demohistorie aanmaken: %s uur", self.s.mock_seed_hours)
        for ts in range(start, now - step, step):
            await self.tick(ts=ts, dt=step)
        # De laatste tick schrijft 'latest' weg zodat het dashboard direct data heeft.
        self.db.set_kv("latest", self.latest)

    async def run(self) -> None:
        last_purge = 0
        while True:
            try:
                await self.tick()
                self.db.set_kv("latest", self.latest)
                if time.time() - last_purge > 3600:
                    self.db.purge(int(time.time()) - self.s.retention_days * 86400)
                    last_purge = time.time()
            except Exception as e:  # noqa: BLE001 – collector mag niet stoppen
                self.last_error = str(e)
                log.exception("Poll mislukt")
            await asyncio.sleep(self.s.poll_seconds)
