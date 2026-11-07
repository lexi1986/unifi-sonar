"""SQLite-opslag: tijdreeksen per device/radio/poort/client/WAN, events en issues."""
from __future__ import annotations

import json
import sqlite3
import threading
from collections import defaultdict
from pathlib import Path

from . import i18n

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
CREATE TABLE IF NOT EXISTS speedtests (ts INT PRIMARY KEY, down REAL, up REAL, latency REAL, server TEXT);
CREATE TABLE IF NOT EXISTS ips_ignore (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, sid INT, label TEXT, created INT);
CREATE TABLE IF NOT EXISTS notified (channel TEXT, key TEXT, severity TEXT, sent_ts INT, gone_ts INT, announced INT,
    PRIMARY KEY (channel, key));
CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY, ts INT, dir TEXT, action TEXT, cc TEXT, remote_ip TEXT,
    port INT, domain TEXT, service TEXT, proto TEXT, client_mac TEXT, client_name TEXT, client_ip TEXT, net TEXT,
    up INT, down INT, risk TEXT, reason TEXT);
CREATE INDEX IF NOT EXISTS ix_flows ON flows(ts);
CREATE TABLE IF NOT EXISTS usage (period TEXT, ts INT, rx REAL, tx REAL, PRIMARY KEY (period, ts));
CREATE TABLE IF NOT EXISTS pauses (mac TEXT PRIMARY KEY, until INT, created INT, name TEXT);
CREATE TABLE IF NOT EXISTS known_clients (mac TEXT PRIMARY KEY, first_seen INT, name TEXT, hostname TEXT,
    private INT, approved INT, rotated_from TEXT);
CREATE TABLE IF NOT EXISTS wan_outages (id TEXT PRIMARY KEY, ts INT, seconds INT, wan TEXT);
CREATE TABLE IF NOT EXISTS client_usage (period TEXT, ts INT, mac TEXT, down REAL, up REAL, PRIMARY KEY (period, ts, mac));
CREATE TABLE IF NOT EXISTS schedules (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, macs TEXT, days TEXT,
    start TEXT, stop TEXT, enabled INT);
CREATE TABLE IF NOT EXISTS selftests (ts INT, mac TEXT, name TEXT, room TEXT, ap TEXT, band TEXT, signal REAL,
    down REAL, up REAL, ping REAL);
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
        self._migrate()

    def _migrate(self) -> None:
        """Kolommen die later zijn toegevoegd aan bestaande databases."""
        fcols = {r[1] for r in self.conn.execute("PRAGMA table_info(flows)")}
        if "reason" not in fcols:
            self.conn.execute("ALTER TABLE flows ADD COLUMN reason TEXT")
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(wan_samples)")}
        for col in ("rx_bps", "tx_bps"):
            if col not in cols:
                self.conn.execute(f"ALTER TABLE wan_samples ADD COLUMN {col} REAL")
        self.conn.commit()

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
            c.execute("INSERT INTO wan_samples (ts, up, latency_ms, loss_pct, rx_bps, tx_bps) VALUES (?,?,?,?,?,?)",
                      (ts, None if w["up"] is None else int(w["up"]), w["latency_ms"], w["loss_pct"],
                       w.get("rx_bps"), w.get("tx_bps")))
            c.executemany("INSERT INTO events VALUES (?,?,?,?,?)", [
                (e["ts"], e["kind"], e["entity_type"], e["entity_id"], i18n.dump(e["message"])) for e in events])

    def set_kv(self, key: str, value: dict) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(value)))

    def add_events(self, events: list[dict]) -> None:
        if not events:
            return
        with self.lock, self.conn:
            self.conn.executemany("INSERT INTO events VALUES (?,?,?,?,?)", [
                (e["ts"], e["kind"], e["entity_type"], e["entity_id"], i18n.dump(e["message"])) for e in events])

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
            self.conn.execute("DELETE FROM client_usage WHERE period='hour' AND ts < ?", (before_ts,))
            self.conn.execute("DELETE FROM client_usage WHERE period='day' AND ts < ?", (before_ts - 400 * 86400,))

    # ------------------------------------------------------------- negeren
    def mute(self, key: str, until: int | None, created: int, title) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO muted VALUES (?,?,?,?)", (key, until, created, i18n.dump(title)))

    def unmute(self, key: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM muted WHERE key=?", (key,))

    def muted(self, now: int) -> dict[str, dict]:
        """Actieve negeer-regels; verlopen regels worden opgeruimd."""
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM muted WHERE until IS NOT NULL AND until <= ?", (now,))
            rows = self.conn.execute("SELECT * FROM muted ORDER BY created DESC").fetchall()
        return {r["key"]: {**dict(r), "title": i18n.pick(r["title"])} for r in rows}

    # ----------------------------------------------------------------- IPS
    def store_ips(self, events: list[dict]) -> int:
        with self.lock, self.conn:
            before = self.conn.total_changes
            self.conn.executemany("INSERT OR IGNORE INTO ips_events VALUES (?,?,?,?,?,?)", [
                (e["id"], e["ts"], int(e["internal"]), e["src_ip"], e["sid"], json.dumps(e)) for e in events])
            return self.conn.total_changes - before

    # ------------------------------------------------------------- verbindingen (wereldkaart)
    FLOW_COLS = ("id", "ts", "dir", "action", "cc", "remote_ip", "port", "domain", "service", "proto",
                 "client_mac", "client_name", "client_ip", "net", "up", "down", "risk", "reason")

    def store_flows(self, flows: list[dict]) -> int:
        """Nieuwe of bijgewerkte verbindingen (UniFi meldt lange verbindingen opnieuw met meer bytes)."""
        if not flows:
            return 0
        sql = f"INSERT OR REPLACE INTO flows VALUES ({','.join('?' * len(self.FLOW_COLS))})"
        with self.lock, self.conn:
            before = self.conn.total_changes
            self.conn.executemany(sql, [tuple(f.get(c) for c in self.FLOW_COLS) for f in flows])
            return self.conn.total_changes - before

    def last_flow_ts(self) -> int | None:
        return self.q("SELECT MAX(ts) t FROM flows")[0]["t"]

    def purge_flows(self, before_ts: int) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM flows WHERE ts < ?", (before_ts,))

    def world(self, since: int) -> dict:
        """Verkeer per land en richting, met de belangrijkste domeinen en apparaten."""
        countries: dict[str, dict] = {}
        for r in self.q("SELECT cc, dir, COUNT(*) n, SUM(up) up, SUM(down) down FROM flows "
                        "WHERE ts>=? AND cc IS NOT NULL AND dir IN ('out','in','blocked') GROUP BY cc, dir", (since,)):
            c = countries.setdefault(r["cc"], {"cc": r["cc"], "out_n": 0, "in_n": 0, "bytes": 0, "up": 0, "down": 0,
                                               "blocked_n": 0, "domains": [], "clients": []})
            c[f"{r['dir']}_n"] = r["n"]
            if r["dir"] != "blocked":
                c["up"] += r["up"] or 0
                c["down"] += r["down"] or 0
            c["bytes"] = c["up"] + c["down"]
        for r in self.q("SELECT cc, domain, SUM(up+down) b, COUNT(*) n FROM flows WHERE ts>=? AND cc IS NOT NULL "
                        "AND dir IN ('out','in') AND domain IS NOT NULL GROUP BY cc, domain ORDER BY b DESC", (since,)):
            if r["cc"] in countries and len(countries[r["cc"]]["domains"]) < 4:
                countries[r["cc"]]["domains"].append({"name": r["domain"], "bytes": r["b"], "n": r["n"]})
        for r in self.q("SELECT cc, COALESCE(client_name, client_ip) name, SUM(up+down) b, COUNT(*) n FROM flows "
                        "WHERE ts>=? AND cc IS NOT NULL AND dir IN ('out','in') GROUP BY cc, name ORDER BY b DESC", (since,)):
            if r["cc"] in countries and r["name"] and len(countries[r["cc"]]["clients"]) < 4:
                countries[r["cc"]]["clients"].append({"name": r["name"], "bytes": r["b"], "n": r["n"]})
        tot = self.q("SELECT SUM(dir='out') out_n, SUM(dir='in') in_n, SUM(dir='local') local_n, SUM(dir='blocked') blocked_n, "
                     "SUM(dir IN ('out','in') AND cc IS NULL) unknown_n, "
                     "SUM(CASE WHEN dir IN ('out','in') THEN up+down ELSE 0 END) bytes, COUNT(*) n FROM flows WHERE ts>=?", (since,))[0]
        clients = [dict(r) for r in self.q(
            "SELECT client_mac mac, COALESCE(client_name, client_ip) name, SUM(up+down) bytes, COUNT(*) n, "
            "COUNT(DISTINCT cc) countries FROM flows WHERE ts>=? AND dir IN ('out','in') GROUP BY mac, name "
            "ORDER BY bytes DESC LIMIT 8", (since,))]
        domains = [dict(r) for r in self.q(
            "SELECT domain name, cc, SUM(up+down) bytes, COUNT(*) n FROM flows WHERE ts>=? AND dir IN ('out','in') "
            "AND domain IS NOT NULL GROUP BY domain ORDER BY bytes DESC LIMIT 8", (since,))]
        return {"countries": countries, "totals": {k: tot[k] or 0 for k in tot.keys()},
                "clients": clients, "domains": domains}

    # ------------------------------------------------------------- nieuwe apparaten
    @staticmethod
    def private_mac(mac: str) -> bool:
        """Lokaal beheerd adres (tweede bit van het eerste byte): een privé/willekeurig wifi-adres."""
        try:
            return bool(int(mac.split(":")[0], 16) & 2)
        except (ValueError, IndexError):
            return False

    def register_clients(self, clients: list[dict], ts: int) -> list[str]:
        """Onthoud welke apparaten we kennen. De eerste keer worden alle huidige (en eerder gemeten) apparaten
        stil goedgekeurd. Daarna: nieuw adres met dezelfde hostnaam als een bekend privé-adres = hetzelfde
        apparaat met een wisselend adres; anders een nieuw apparaat (gasten tellen niet). Geeft nieuwe MACs terug."""
        with self.lock, self.conn:
            c = self.conn
            baseline = c.execute("SELECT COUNT(*) FROM known_clients").fetchone()[0] == 0
            known = {r["mac"]: dict(r) for r in c.execute("SELECT * FROM known_clients")}
            if baseline:
                hist = [r[0] for r in c.execute("SELECT DISTINCT mac FROM client_samples")]
                c.executemany("INSERT OR IGNORE INTO known_clients VALUES (?,?,?,?,?,1,NULL)",
                              [(m, ts, None, None, int(self.private_mac(m))) for m in hist])
            new = []
            for cl in clients:
                mac, host = cl["mac"], (cl.get("hostname") or "").strip().lower() or None
                if mac in known:
                    continue
                priv = self.private_mac(mac)
                rotated = None
                if priv and host and not baseline:
                    rotated = next((m for m, r in known.items() if r["private"] and r["hostname"] == host and m != mac), None)
                approved = 1 if baseline or rotated or cl.get("guest") else 0
                c.execute("INSERT OR REPLACE INTO known_clients VALUES (?,?,?,?,?,?,?)",
                          (mac, ts, cl.get("name"), host, int(priv), approved, rotated))
                known[mac] = {"mac": mac, "private": int(priv), "hostname": host}
                if not baseline:
                    new.append(mac)
            return new

    # ------------------------------------------------------------- internet pauzeren
    def set_pause(self, mac: str, until: int | None, created: int, name: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO pauses VALUES (?,?,?,?)", (mac, until, created, name))

    def clear_pause(self, mac: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM pauses WHERE mac=?", (mac,))

    def pauses(self) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM pauses ORDER BY created DESC")]

    def pending_new(self, since: int) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM known_clients WHERE approved=0 AND first_seen>=? ORDER BY first_seen DESC", (since,))]

    def rotations(self, since: int) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM known_clients WHERE rotated_from IS NOT NULL AND first_seen>=? "
                                        "ORDER BY first_seen DESC", (since,))]

    def approve_client(self, mac: str) -> bool:
        with self.lock, self.conn:
            return self.conn.execute("UPDATE known_clients SET approved=1 WHERE mac=?", (mac,)).rowcount > 0

    # ------------------------------------------------------------- datagebruik per dag/maand
    def store_usage(self, period: str, rows: list[dict]) -> None:
        """Rapportregels van de controller; de lopende dag/maand wordt telkens overschreven."""
        with self.lock, self.conn:
            self.conn.executemany("INSERT OR REPLACE INTO usage VALUES (?,?,?,?)",
                                  [(period, r["ts"], r["rx"], r["tx"]) for r in rows])

    def usage(self, period: str, since: int) -> list[dict]:
        return [dict(r) for r in self.q("SELECT ts, rx, tx FROM usage WHERE period=? AND ts>=? ORDER BY ts", (period, since))]

    # ------------------------------------------------------------- internetstoringen
    def store_outages(self, rows: list[dict]) -> int:
        """Storingen uit UniFi bewaren (UniFi zelf houdt ze 90 dagen); geeft het aantal nieuwe terug."""
        with self.lock, self.conn:
            before = self.conn.total_changes
            self.conn.executemany("INSERT OR IGNORE INTO wan_outages VALUES (?,?,?,?)",
                                  [(r["id"], r["ts"], r["seconds"], r.get("wan") or "WAN") for r in rows])
            return self.conn.total_changes - before

    def outages(self, since: int) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM wan_outages WHERE ts + seconds >= ? ORDER BY ts DESC", (since,))]

    # ------------------------------------------------------------- verbruik per apparaat
    def store_client_usage(self, period: str, rows: list[dict]) -> None:
        with self.lock, self.conn:
            self.conn.executemany("INSERT OR REPLACE INTO client_usage VALUES (?,?,?,?,?)",
                                  [(period, r["ts"], r["mac"], r["down"], r["up"]) for r in rows])

    def client_usage_totals(self, period: str, since: int, until: int | None = None) -> dict[str, dict]:
        """Per apparaat het totaal over [since, until)."""
        rows = self.q("SELECT mac, SUM(down) down, SUM(up) up FROM client_usage WHERE period=? AND ts>=? AND ts<? GROUP BY mac",
                      (period, since, until or 2 ** 40))
        return {r["mac"]: {"down": r["down"] or 0, "up": r["up"] or 0} for r in rows}

    def client_usage_series(self, mac: str, period: str, since: int) -> list[dict]:
        return [dict(r) for r in self.q("SELECT ts, down, up FROM client_usage WHERE period=? AND mac=? AND ts>=? ORDER BY ts",
                                        (period, mac, since))]

    # ------------------------------------------------------------- vaste pauzetijden
    def schedules(self) -> list[dict]:
        return [{**dict(r), "macs": json.loads(r["macs"] or "[]"), "days": json.loads(r["days"] or "[]"), "enabled": bool(r["enabled"])}
                for r in self.q("SELECT * FROM schedules ORDER BY id")]

    def save_schedule(self, s: dict) -> int:
        vals = (s["name"], json.dumps(s["macs"]), json.dumps(s["days"]), s["start"], s["stop"], int(s["enabled"]))
        with self.lock, self.conn:
            if s.get("id"):
                self.conn.execute("UPDATE schedules SET name=?, macs=?, days=?, start=?, stop=?, enabled=? WHERE id=?", (*vals, s["id"]))
                return s["id"]
            return self.conn.execute("INSERT INTO schedules (name, macs, days, start, stop, enabled) VALUES (?,?,?,?,?,?)", vals).lastrowid

    def delete_schedule(self, sid: int) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM schedules WHERE id=?", (sid,))

    # ------------------------------------------------------------- wifi-metingen vanaf een apparaat
    def add_selftest(self, r: dict) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO selftests VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (r["ts"], r.get("mac"), r.get("name"), r.get("room"), r.get("ap"), r.get("band"), r.get("signal"),
                               r.get("down"), r.get("up"), r.get("ping")))

    def selftests(self, limit: int = 100) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM selftests ORDER BY ts DESC LIMIT ?", (limit,))]

    def client_roams_since(self, mac: str, since: int) -> list[dict]:
        return [{**dict(r), "message": i18n.pick(r["message"])} for r in self.q(
            "SELECT ts, message FROM events WHERE kind='roam' AND entity_id=? AND ts>=? ORDER BY ts DESC LIMIT 50", (mac, since))]

    def blocked_flows(self, since: int) -> list[dict]:
        return [dict(r) for r in self.q(
            "SELECT ts, cc, reason, service, port, client_name, client_ip, remote_ip FROM flows "
            "WHERE ts>=? AND dir='blocked' ORDER BY ts DESC LIMIT 5000", (since,))]

    def connections(self, since: int, dirs: tuple[str, ...], cc: str | None = None, q: str | None = None,
                    sort: str = "last", limit: int = 100) -> tuple[list[dict], int]:
        """Verbindingen samengevoegd per richting, apparaat, bestemming en poort. Geeft (groepen, totaal aantal groepen)."""
        where, args = ["ts>=?", f"dir IN ({','.join('?' * len(dirs))})"], [since, *dirs]
        if cc:
            where.append("cc=?")
            args.append(cc)
        if q:
            like = f"%{q.lower()}%"
            where.append("(LOWER(COALESCE(client_name,'')) LIKE ? OR LOWER(COALESCE(domain,'')) LIKE ? OR "
                         "COALESCE(remote_ip,'') LIKE ? OR LOWER(COALESCE(cc,'')) = ? OR CAST(port AS TEXT) = ? OR "
                         "LOWER(COALESCE(service,'')) LIKE ?)")
            args += [like, like, like, q.lower(), q, like]
        order = "bytes DESC" if sort == "bytes" else "n DESC" if sort == "count" else "last DESC"
        base = (f"SELECT dir, cc, client_mac, COALESCE(client_name, client_ip) client, client_ip, "
                f"COALESCE(domain, CASE WHEN dir='out' THEN remote_ip END) dest, port, service, MAX(reason) reason, "
                f"COUNT(*) n, SUM(up) up, SUM(down) down, SUM(up+down) bytes, MIN(ts) first, MAX(ts) last, "
                f"COUNT(DISTINCT remote_ip) remotes FROM flows WHERE {' AND '.join(where)} "
                f"GROUP BY dir, cc, client, dest, port")
        total = self.q(f"SELECT COUNT(*) n FROM ({base})", tuple(args))[0]["n"]
        rows = [dict(r) for r in self.q(f"{base} ORDER BY {order} LIMIT ?", (*args, limit))]
        return rows, total

    def flows_recent(self, after: int, limit: int = 40, include_local: bool = False) -> list[dict]:
        cond = "" if include_local else "AND dir!='local'"
        return [dict(r) for r in self.q(f"SELECT * FROM flows WHERE ts>? {cond} ORDER BY ts DESC LIMIT ?", (after, limit))]

    def last_ips_ts(self) -> int | None:
        return self.q("SELECT MAX(ts) t FROM ips_events")[0]["t"]

    def ips_events(self, since: int, scope: str = "all", limit: int = 5000) -> list[dict]:
        cond = {"internal": "AND internal=1", "external": "AND internal=0"}.get(scope, "")
        return [json.loads(r["data"]) for r in
                self.q(f"SELECT data FROM ips_events WHERE ts>=? {cond} ORDER BY ts DESC LIMIT ?", (since, limit))]

    # ------------------------------------------------------------ speedtests
    def store_speedtests(self, rows: list[dict]) -> int:
        """Eén rij per test: een voorlopig resultaat (zonder server) wordt vervangen door dat uit het
        UniFi-archief, ook als de tijdstempels een paar seconden verschillen."""
        added = 0
        with self.lock, self.conn:
            c = self.conn
            for r in rows:
                near = c.execute("SELECT ts, server FROM speedtests WHERE ts BETWEEN ? AND ?",
                                 (r["ts"] - 300, r["ts"] + 300)).fetchall()
                if any(n["server"] or not r.get("server") for n in near):
                    continue
                c.execute("DELETE FROM speedtests WHERE ts BETWEEN ? AND ?", (r["ts"] - 300, r["ts"] + 300))
                c.execute("INSERT INTO speedtests VALUES (?,?,?,?,?)",
                          (r["ts"], r["down"], r["up"], r["latency"], r.get("server") or ""))
                added += 1
        return added

    def speedtests(self, since: int) -> list[dict]:
        return [dict(r) for r in self.q("SELECT * FROM speedtests WHERE ts>=? ORDER BY ts", (since,))]

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

    def client_roams(self, since: int) -> dict[str, dict]:
        """Per client: aantal AP-wissels (n) en het tijdstip van de laatste (last)."""
        rows = self.q("SELECT mac, ts, ap_mac FROM client_samples WHERE ts>=? AND ap_mac IS NOT NULL ORDER BY mac, ts", (since,))
        roams: dict[str, dict] = {}
        prev: dict[str, str] = {}
        for r in rows:
            if r["mac"] in prev and prev[r["mac"]] != r["ap_mac"]:
                d = roams.setdefault(r["mac"], {"n": 0, "last": None})
                d["n"] += 1
                d["last"] = r["ts"]
            prev[r["mac"]] = r["ap_mac"]
        return roams

    def radio_window(self, since: int) -> dict[tuple, dict]:
        rows = self.q("SELECT mac, radio, AVG(cu_total) cu, AVG(interference) intf, AVG(retry_pct) rt, "
                      "AVG(satisfaction) sat FROM radio_samples WHERE ts>=? GROUP BY mac, radio", (since,))
        return {(r["mac"], r["radio"]): dict(r) for r in rows}

    def port_window(self, since: int) -> dict[tuple, dict]:
        rows = self.q("SELECT mac, idx, SUM(errors) err, SUM(drops) drp, MIN(ts) t0, MAX(ts) t1 "
                      "FROM port_samples WHERE ts>=? GROUP BY mac, idx", (since,))
        out = {(r["mac"], r["idx"]): dict(r) for r in rows}
        flaps = self.q("SELECT entity_id, COUNT(*) n, MAX(ts) t FROM events WHERE ts>=? AND kind='port_down' "
                       "GROUP BY entity_id", (since,))
        for f in flaps:
            mac, _, idx = f["entity_id"].rpartition("#")
            out.setdefault((mac, int(idx)), {}).update(flaps=f["n"], flap_ts=f["t"])
        return out

    def wan_window(self, since: int) -> dict:
        r = self.q("SELECT AVG(latency_ms) lat, MAX(latency_ms) lat_max, AVG(loss_pct) loss, "
                   "SUM(CASE WHEN up=0 THEN 1 ELSE 0 END) down, COUNT(*) n FROM wan_samples WHERE ts>=?", (since,))
        return dict(r[0]) if r else {}

    def event_last(self, since: int, kind: str) -> dict[str, int]:
        rows = self.q("SELECT entity_id, MAX(ts) t FROM events WHERE ts>=? AND kind=? GROUP BY entity_id", (since, kind))
        return {r["entity_id"]: r["t"] for r in rows}

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
        return [{**dict(r), "message": i18n.pick(r["message"])}
                for r in self.q("SELECT * FROM events WHERE ts>=? ORDER BY ts DESC LIMIT ?", (since, limit))]
