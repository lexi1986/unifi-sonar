"""SQLite-opslag: tijdreeksen per device/radio/poort/client/WAN, events en issues."""
from __future__ import annotations

import json
import sqlite3
import threading
from collections import defaultdict
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS device_samples (ts INT, mac TEXT, state TEXT, cpu REAL, mem REAL, temp REAL,
    num_clients INT, satisfaction REAL, uptime REAL);
CREATE TABLE IF NOT EXISTS radio_samples (ts INT, mac TEXT, radio TEXT, channel INT, cu_total REAL,
    interference REAL, num_clients INT, satisfaction REAL, retry_pct REAL);
CREATE TABLE IF NOT EXISTS port_samples (ts INT, mac TEXT, idx INT, up INT, speed REAL, errors REAL,
    drops REAL, rx_bps REAL, tx_bps REAL);
CREATE TABLE IF NOT EXISTS client_samples (ts INT, mac TEXT, ap_mac TEXT, band TEXT, signal REAL,
    satisfaction REAL, retry_pct REAL, tx_rate REAL);
CREATE TABLE IF NOT EXISTS wan_samples (ts INT, up INT, latency_ms REAL, loss_pct REAL);
CREATE TABLE IF NOT EXISTS events (ts INT, kind TEXT, entity_type TEXT, entity_id TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS issues (key TEXT PRIMARY KEY, severity TEXT, category TEXT, title TEXT,
    entity_type TEXT, entity_id TEXT, first_seen INT, last_seen INT, resolved_at INT, data TEXT);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS muted (key TEXT PRIMARY KEY, until INT, created INT, title TEXT);
CREATE TABLE IF NOT EXISTS ips_events (id TEXT PRIMARY KEY, ts INT, internal INT, src_ip TEXT, sid INT, data TEXT);
CREATE INDEX IF NOT EXISTS ix_ips ON ips_events(ts);
CREATE INDEX IF NOT EXISTS ix_dev ON device_samples(mac, ts);
CREATE INDEX IF NOT EXISTS ix_radio ON radio_samples(mac, ts);
CREATE INDEX IF NOT EXISTS ix_port ON port_samples(mac, idx, ts);
CREATE INDEX IF NOT EXISTS ix_client ON client_samples(mac, ts);
CREATE INDEX IF NOT EXISTS ix_client_ts ON client_samples(ts);
CREATE INDEX IF NOT EXISTS ix_wan ON wan_samples(ts);
CREATE INDEX IF NOT EXISTS ix_events ON events(ts);
"""

TS_TABLES = ("device_samples", "radio_samples", "port_samples", "client_samples", "wan_samples", "events", "ips_events")


class DB:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.lock = threading.Lock()

    def q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    # ------------------------------------------------------------------ writes
    def store(self, snap: dict, events: list[dict]) -> None:
        ts = snap["ts"]
        with self.lock, self.conn:
            c = self.conn
            c.executemany("INSERT INTO device_samples VALUES (?,?,?,?,?,?,?,?,?)", [
                (ts, d["mac"], d["state"], d["cpu"], d["mem"], d["temp"], d["num_clients"], d["satisfaction"], d["uptime"])
                for d in snap["devices"]])
            c.executemany("INSERT INTO radio_samples VALUES (?,?,?,?,?,?,?,?,?)", [
                (ts, d["mac"], r["radio"], r["channel"], r["cu_total"], r["interference"], r["num_clients"],
                 r["satisfaction"], r.get("retry_pct"))
                for d in snap["devices"] for r in d["radios"]])
            c.executemany("INSERT INTO port_samples VALUES (?,?,?,?,?,?,?,?,?)", [
                (ts, d["mac"], p["idx"], int(p["up"]), p["speed"], p.get("errors_delta"), p.get("drops_delta"),
                 p.get("rx_bps"), p.get("tx_bps"))
                for d in snap["devices"] for p in d["ports"]])
            c.executemany("INSERT INTO client_samples VALUES (?,?,?,?,?,?,?,?)", [
                (ts, x["mac"], x["ap_mac"], x["band"], x["signal"], x["satisfaction"], x.get("retry_pct"), x["tx_rate_mbps"])
                for x in snap["clients"]])
            w = snap["wan"]
            c.execute("INSERT INTO wan_samples VALUES (?,?,?,?)",
                      (ts, None if w["up"] is None else int(w["up"]), w["latency_ms"], w["loss_pct"]))
            c.executemany("INSERT INTO events VALUES (?,?,?,?,?)", [
                (e["ts"], e["kind"], e["entity_type"], e["entity_id"], e["message"]) for e in events])

    def set_kv(self, key: str, value: dict) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(value)))

    def get_kv(self, key: str) -> dict | None:
        rows = self.q("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else None

    def sync_issues(self, issues: list[dict], ts: int) -> None:
        """Open issues bijwerken, verdwenen issues als opgelost markeren."""
        keys = {i["key"] for i in issues}
        with self.lock, self.conn:
            c = self.conn
            for i in issues:
                row = c.execute("SELECT first_seen, resolved_at FROM issues WHERE key=?", (i["key"],)).fetchone()
                first = ts if row is None or row["resolved_at"] is not None else row["first_seen"]
                c.execute("INSERT OR REPLACE INTO issues VALUES (?,?,?,?,?,?,?,?,NULL,?)",
                          (i["key"], i["severity"], i["category"], i["title"], i["entity_type"], i["entity_id"],
                           first, ts, json.dumps(i)))
            open_rows = c.execute("SELECT key FROM issues WHERE resolved_at IS NULL").fetchall()
            for r in open_rows:
                if r["key"] not in keys:
                    c.execute("UPDATE issues SET resolved_at=? WHERE key=?", (ts, r["key"]))

    def purge(self, before_ts: int) -> None:
        with self.lock, self.conn:
            for t in TS_TABLES:
                self.conn.execute(f"DELETE FROM {t} WHERE ts < ?", (before_ts,))
            self.conn.execute("DELETE FROM issues WHERE resolved_at IS NOT NULL AND resolved_at < ?", (before_ts,))

    # ------------------------------------------------------------- negeren
    def mute(self, key: str, until: int | None, created: int, title: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO muted VALUES (?,?,?,?)", (key, until, created, title))

    def unmute(self, key: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM muted WHERE key=?", (key,))

    def muted(self, now: int) -> dict[str, dict]:
        """Actieve negeer-regels; verlopen regels worden opgeruimd."""
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM muted WHERE until IS NOT NULL AND until <= ?", (now,))
            rows = self.conn.execute("SELECT * FROM muted ORDER BY created DESC").fetchall()
        return {r["key"]: dict(r) for r in rows}

    # ----------------------------------------------------------------- IPS
    def store_ips(self, events: list[dict]) -> int:
        with self.lock, self.conn:
            before = self.conn.total_changes
            self.conn.executemany("INSERT OR IGNORE INTO ips_events VALUES (?,?,?,?,?,?)", [
                (e["id"], e["ts"], int(e["internal"]), e["src_ip"], e["sid"], json.dumps(e)) for e in events])
            return self.conn.total_changes - before

    def last_ips_ts(self) -> int | None:
        return self.q("SELECT MAX(ts) t FROM ips_events")[0]["t"]

    def ips_events(self, since: int, scope: str = "all", limit: int = 5000) -> list[dict]:
        cond = {"internal": "AND internal=1", "external": "AND internal=0"}.get(scope, "")
        return [json.loads(r["data"]) for r in
                self.q(f"SELECT data FROM ips_events WHERE ts>=? {cond} ORDER BY ts DESC LIMIT ?", (since, limit))]

    def is_empty(self) -> bool:
        return not self.q("SELECT 1 FROM wan_samples LIMIT 1")

    # ---------------------------------------------------------- window stats
    def client_window(self, since: int) -> dict[str, dict]:
        rows = self.q("SELECT mac, AVG(signal) sig, AVG(retry_pct) rt, AVG(satisfaction) sat, AVG(tx_rate) rate, "
                      "COUNT(*) n FROM client_samples WHERE ts>=? GROUP BY mac", (since,))
        return {r["mac"]: dict(r) for r in rows}

    def client_before(self, mac: str, t0: int, t1: int) -> dict | None:
        """Waar zat deze client tussen t0 en t1 (meest gebruikte AP + gemiddeld signaal daar)?"""
        rows = self.q("SELECT ap_mac, COUNT(*) n, AVG(signal) sig FROM client_samples "
                      "WHERE mac=? AND ts>=? AND ts<? AND ap_mac IS NOT NULL GROUP BY ap_mac ORDER BY n DESC LIMIT 1",
                      (mac, t0, t1))
        return dict(rows[0]) if rows and rows[0]["n"] >= 3 else None

    def client_roams(self, since: int) -> dict[str, int]:
        rows = self.q("SELECT mac, ap_mac FROM client_samples WHERE ts>=? AND ap_mac IS NOT NULL ORDER BY mac, ts", (since,))
        roams: dict[str, int] = defaultdict(int)
        prev: dict[str, str] = {}
        for r in rows:
            if r["mac"] in prev and prev[r["mac"]] != r["ap_mac"]:
                roams[r["mac"]] += 1
            prev[r["mac"]] = r["ap_mac"]
        return dict(roams)

    def radio_window(self, since: int) -> dict[tuple, dict]:
        rows = self.q("SELECT mac, radio, AVG(cu_total) cu, AVG(interference) intf, AVG(retry_pct) rt, "
                      "AVG(satisfaction) sat FROM radio_samples WHERE ts>=? GROUP BY mac, radio", (since,))
        return {(r["mac"], r["radio"]): dict(r) for r in rows}

    def port_window(self, since: int) -> dict[tuple, dict]:
        rows = self.q("SELECT mac, idx, SUM(errors) err, SUM(drops) drp, MIN(ts) t0, MAX(ts) t1 "
                      "FROM port_samples WHERE ts>=? GROUP BY mac, idx", (since,))
        out = {(r["mac"], r["idx"]): dict(r) for r in rows}
        flaps = self.q("SELECT entity_id, COUNT(*) n FROM events WHERE ts>=? AND kind='port_down' GROUP BY entity_id", (since,))
        for f in flaps:
            mac, _, idx = f["entity_id"].rpartition("#")
            out.setdefault((mac, int(idx)), {})["flaps"] = f["n"]
        return out

    def wan_window(self, since: int) -> dict:
        r = self.q("SELECT AVG(latency_ms) lat, MAX(latency_ms) lat_max, AVG(loss_pct) loss, "
                   "SUM(CASE WHEN up=0 THEN 1 ELSE 0 END) down, COUNT(*) n FROM wan_samples WHERE ts>=?", (since,))
        return dict(r[0]) if r else {}

    def event_counts(self, since: int, kind: str) -> dict[str, int]:
        rows = self.q("SELECT entity_id, COUNT(*) n FROM events WHERE ts>=? AND kind=? GROUP BY entity_id", (since, kind))
        return {r["entity_id"]: r["n"] for r in rows}

    # ------------------------------------------------------------ dashboard
    def series(self, table: str, cols: list[str], where: str, args: tuple, since: int, bucket: int) -> list[dict]:
        sel = ", ".join(f"AVG({c}) AS {c}" for c in cols)
        sql = (f"SELECT (ts/{bucket})*{bucket} AS t, {sel} FROM {table} "
               f"WHERE ts>=? {('AND ' + where) if where else ''} GROUP BY t ORDER BY t")
        return [dict(r) for r in self.q(sql, (since, *args))]

    def issues(self, open_only: bool, limit: int = 200, now: int | None = None) -> list[dict]:
        sql = "SELECT * FROM issues " + ("WHERE resolved_at IS NULL " if open_only else "") + \
              "ORDER BY resolved_at IS NOT NULL, last_seen DESC LIMIT ?"
        muted = self.muted(now) if now else {}
        out = []
        for r in self.q(sql, (limit,)):
            d = json.loads(r["data"])
            d.update(first_seen=r["first_seen"], last_seen=r["last_seen"], resolved_at=r["resolved_at"])
            m = muted.get(d["key"]) or muted.get(d.get("group") or "")
            d["muted"] = bool(m)
            d["muted_until"] = m["until"] if m else None
            out.append(d)
        return out

    def events(self, since: int, limit: int = 200) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM events WHERE ts>=? ORDER BY ts DESC LIMIT ?", (since, limit))]
