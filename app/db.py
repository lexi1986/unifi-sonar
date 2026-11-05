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
CREATE TABLE IF NOT EXISTS ips_ignore (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, sid INT, label TEXT, created INT);
CREATE TABLE IF NOT EXISTS notified (channel TEXT, key TEXT, severity TEXT, sent_ts INT, gone_ts INT, announced INT,
    PRIMARY KEY (channel, key));
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

    # ------------------------------------------------------ IPS negeerregels
    def ips_ignores(self) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM ips_ignore ORDER BY created DESC")]

    def add_ips_ignore(self, ip: str | None, sid: int | None, label: str, created: int) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM ips_ignore WHERE ip IS ? AND sid IS ?", (ip, sid))
            self.conn.execute("INSERT INTO ips_ignore (ip, sid, label, created) VALUES (?,?,?,?)", (ip, sid, label, created))

    def remove_ips_ignore(self, rule_id: int) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM ips_ignore WHERE id=?", (rule_id,))

    # ------------------------------------------------------------ meldingen
    def notified(self, channel: str) -> dict[str, dict]:
        return {r["key"]: dict(r) for r in self.q("SELECT * FROM notified WHERE channel=?", (channel,))}

    def set_notified(self, channel: str, key: str, severity: str, ts: int, announced: bool = True) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO notified VALUES (?,?,?,?,NULL,?)",
                              (channel, key, severity, ts, int(announced)))

    def set_notified_gone(self, channel: str, key: str, ts: int | None) -> None:
        with self.lock, self.conn:
            self.conn.execute("UPDATE notified SET gone_ts=? WHERE channel=? AND key=?", (ts, channel, key))

    def drop_notified(self, channel: str, key: str | None = None) -> None:
        with self.lock, self.conn:
            if key is None:
                self.conn.execute("DELETE FROM notified WHERE channel=?", (channel,))
            else:
                self.conn.execute("DELETE FROM notified WHERE channel=? AND key=?", (channel, key))

    def issue(self, key: str) -> dict | None:
        rows = self.q("SELECT data FROM issues WHERE key=?", (key,))
        return json.loads(rows[0]["data"]) if rows else None

    def first_seen(self) -> dict[str, int]:
        return {r["key"]: r["first_seen"] for r in self.q("SELECT key, first_seen FROM issues WHERE resolved_at IS NULL")}

    # ------------------------------------------------------------- patronen
    def last_state_ts(self, mac: str, state: str = "online") -> int | None:
        return self.q("SELECT MAX(ts) t FROM device_samples WHERE mac=? AND state=?", (mac, state))[0]["t"]

    def client_ap_stats(self, mac: str, since: int, gap: int = 300) -> dict:
        """Per AP: tijd (s) en gemiddeld signaal, plus hoe vaak de client van AP wisselde."""
        rows = self.q("SELECT ts, ap_mac, signal FROM client_samples WHERE mac=? AND ts>=? AND ap_mac IS NOT NULL "
                      "ORDER BY ts", (mac, since))
        per: dict[str, dict] = {}
        switches, prev = 0, None
        for i, r in enumerate(rows):
            nxt = rows[i + 1]["ts"] if i + 1 < len(rows) else r["ts"] + 60
            dt = max(0, min(gap, nxt - r["ts"]))
            a = per.setdefault(r["ap_mac"], {"ap_mac": r["ap_mac"], "seconds": 0, "n": 0, "_sig": 0.0, "_ns": 0})
            a["seconds"] += dt
            a["n"] += 1
            if r["signal"] is not None:
                a["_sig"] += r["signal"]
                a["_ns"] += 1
            if prev and prev != r["ap_mac"]:
                switches += 1
            prev = r["ap_mac"]
        for a in per.values():
            a["signal"] = round(a.pop("_sig") / a["_ns"], 1) if a["_ns"] else None
            a.pop("_ns")
        return {"aps": sorted(per.values(), key=lambda a: -a["seconds"]), "switches": switches}

    def _slot_seconds(self, sql: str, args: tuple, gap: int = 300) -> dict[tuple, float]:
        """Tijd per (weekdag ma=0, uur) uit een gesorteerde reeks tijdstippen (lokale tijd)."""
        import time as _t
        rows = [r[0] for r in self.q(sql, args)]
        out: dict[tuple, float] = defaultdict(float)
        for i, t in enumerate(rows):
            nxt = rows[i + 1] if i + 1 < len(rows) else t + 60
            lt = _t.localtime(t)
            out[(lt.tm_wday, lt.tm_hour)] += max(0, min(gap, nxt - t))
        return out

    def presence(self, mac: str, since: int) -> list[list[float | None]]:
        """7×24 raster: deel van de gemeten tijd dat de client verbonden was (None = geen metingen)."""
        seen = self._slot_seconds("SELECT ts FROM client_samples WHERE mac=? AND ts>=? ORDER BY ts", (mac, since))
        base = self._slot_seconds("SELECT ts FROM wan_samples WHERE ts>=? ORDER BY ts", (since,))
        return [[round(min(1.0, seen.get((d, h), 0) / base[(d, h)]), 3) if base.get((d, h)) else None
                 for h in range(24)] for d in range(7)]

    def radio_heatmap(self, mac: str, since: int) -> dict[str, dict]:
        import time as _t
        acc: dict[str, dict] = {}
        for r in self.q("SELECT ts, radio, cu_total, interference, num_clients FROM radio_samples WHERE mac=? AND ts>=?",
                        (mac, since)):
            lt = _t.localtime(r["ts"])
            cell = acc.setdefault(r["radio"], {}).setdefault((lt.tm_wday, lt.tm_hour), [0.0, 0.0, 0.0, 0])
            cell[0] += r["cu_total"] or 0
            cell[1] += r["interference"] or 0
            cell[2] += r["num_clients"] or 0
            cell[3] += 1
        out = {}
        for radio, cells in acc.items():
            grid = {k: [[None] * 24 for _ in range(7)] for k in ("cu", "interference", "clients")}
            for (d, h), (cu, intf, ncl, n) in cells.items():
                grid["cu"][d][h] = round(cu / n, 1)
                grid["interference"][d][h] = round(intf / n, 1)
                grid["clients"][d][h] = round(ncl / n, 1)
            out[radio] = grid
        return out

    def store_rows(self, table: str, rows: list[tuple]) -> None:
        """Ruwe rijen (demodata-historie)."""
        if not rows:
            return
        with self.lock, self.conn:
            self.conn.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(rows[0]))})", rows)

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
