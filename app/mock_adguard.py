"""Demodata voor de AdGuard-koppeling: twee AdGuard-servers die een beetje uiteenlopen, een querylog dat past bij de
verbindingen uit mock.py, een robotstofzuiger met een nieuw domein, een kantoor-pc die tegen phishing werd beschermd
en een Fire TV die AdGuard overslaat."""
from __future__ import annotations

import random
import time
import zlib
from datetime import datetime, timezone

from .mock import FLOW_DEST, IOT_CLIENTS, WIRED, WIRELESS, _cip, _mac


def reg_domain(name: str) -> str:
    from .adguard import reg_domain as r
    return r(name)

DAY = 86400
SERVERS = {"NAS Synology", "Docker Host", "Proxmox Host", "Home Assistant", "Pi-hole", "ESP Weerstation"}
BYPASS = "Fire TV"                       # gebruikt eigen DNS: AdGuard ziet hem nooit
THREAT = ("Kantoor-PC", "secure-login-check.example")
NEW = ("Robotstofzuiger", "ota.unknown-cloud.example")
R = random.Random(7)


def demo_ip(domain: str) -> str:
    """Vast adres per domein, zodat de verbindingen in mock.py en de DNS-antwoorden hier bij elkaar passen."""
    return f"203.0.113.{zlib.crc32(domain.encode()) % 200 + 20}"


def _clients() -> dict[str, tuple[str, str]]:
    out = {n: (_mac(0x100 + i), _cip(n, i, False)) for i, (n, *_r) in enumerate(WIRELESS)}
    out.update({n: (_mac(0x200 + i), _cip(n, i, True)) for i, (n, *_r) in enumerate(WIRED)})
    return out


def _domains(who: str) -> list[str]:
    return [d for w, d, *_r in FLOW_DEST if w == who]


def seed(db) -> None:
    """Een week aan geleerde domeinen en een etmaal aan tellingen, zodat de demo meteen iets laat zien."""
    now = int(time.time())
    cl = _clients()
    with db.lock, db.conn:
        c = db.conn
        if c.execute("SELECT COUNT(*) FROM dns_domains").fetchone()[0]:
            return
        for who, (mac, _ip) in cl.items():
            if who in IOT_CLIENTS or who in SERVERS:
                for d in {reg_domain(x) for x in _domains(who)} or {"gstatic.com"}:
                    c.execute("INSERT OR IGNORE INTO dns_domains VALUES (?,?,?,?,?,?)", (mac, d, now - 12 * DAY, now - 600, R.randint(200, 4000), 0))
        mac = cl[NEW[0]][0]
        c.execute("INSERT OR IGNORE INTO dns_domains VALUES (?,?,?,?,?,?)", (mac, "unknown-cloud.example", now - 3 * 3600, now - 900, 14, 0))
        for h in range(30):
            hour = now - now % 3600 - h * 3600
            for who, (mac, _ip) in cl.items():
                if who != BYPASS:
                    q = R.randint(20, 400)
                    c.execute("INSERT OR IGNORE INTO dns_hourly VALUES (?,?,?,?)", (hour, mac, q, q // R.randint(6, 20)))
            c.execute("INSERT OR IGNORE INTO dns_hourly VALUES (?,?,?,?)", (hour, "redirected", R.randint(5, 40), 0))
        pc_mac, pc_ip = cl[THREAT[0]]
        for k in range(3):
            c.execute("INSERT INTO dns_threats VALUES (?,?,?,?,?)", (now - 7200 - k * 400, pc_mac, pc_ip, THREAT[1], "HaGeZi's Threat Intelligence Feeds"))
        c.execute("INSERT OR REPLACE INTO kv VALUES ('adguard', ?)", ('{"cursor": {}, "since": %d}' % (now - 3 * DAY),))


def probe(host: str) -> dict:
    return {"ok": True, "ms": round(R.uniform(2, 6) if host.endswith(".22") else R.uniform(8, 18), 1), "rcode": 0}


class _Http:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).isoformat().replace("+00:00", "Z")


class MockAPI:
    snap: dict = {}

    def __init__(self, inst: dict, n: int) -> None:
        self.name, self.url, self.n = inst["name"], inst["url"], n
        self.verify = False

    def client(self):
        return _Http()

    async def get(self, http, path: str, **params):
        if path == "/control/status":
            return {"version": "v0.107.63", "running": True, "protection_enabled": True}
        if path == "/control/filtering/status":
            f = [{"id": 1, "name": "AdGuard DNS filter", "url": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt", "enabled": True},
                 {"id": 2, "name": "HaGeZi's Threat Intelligence Feeds", "url": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_44.txt", "enabled": True}]
            if self.n == 0:
                f.append({"id": 3, "name": "OISD Big", "url": "https://big.oisd.nl", "enabled": True})
            return {"filters": f, "user_rules": ["||ads.example^"]}
        if path == "/control/rewrite/list":
            return [{"domain": "nas.thuis.lan", "answer": "192.168.1.13", "enabled": True}] if self.n == 0 else []
        if path == "/control/dns_info":
            return {"upstream_dns": ["https://dns.quad9.net/dns-query", "tls://1.1.1.1"]}
        if path == "/control/stats":
            return {"num_dns_queries": 48210 // (self.n + 1), "num_blocked_filtering": 6110 // (self.n + 1), "avg_processing_time": 0.004 + self.n * 0.006,
                    "top_upstreams_avg_time": [{"https://dns.quad9.net/dns-query": 0.012}, {"tls://1.1.1.1": 0.018}]}
        if path == "/control/querylog":
            return {"data": self._log() if self.n == 0 and not params.get("older_than") else [], "oldest": ""}
        raise RuntimeError(path)

    def _log(self) -> list[dict]:
        now = time.time()
        out = []
        for c in self.snap.get("clients") or []:
            who = c.get("name")
            if who == BYPASS or not c.get("ip"):
                continue
            for d in _domains(who)[:3] or ["connectivitycheck.gstatic.com"]:
                t = now - R.uniform(0, 50)
                out.append({"time": _iso(t), "client": c["ip"], "question": {"name": d, "type": "A"}, "reason": "NotFilteredNotFound",
                            "status": "NOERROR", "answer": [{"type": "A", "value": demo_ip(d)}]})
            if who == THREAT[0] and R.random() < 0.2:
                out.append({"time": _iso(now - 5), "client": c["ip"], "question": {"name": THREAT[1], "type": "A"},
                            "reason": "FilteredBlackList", "rules": [{"filter_list_id": 2, "text": f"||{THREAT[1]}^"}], "status": "NOERROR", "answer": []})
            if who == NEW[0]:
                out.append({"time": _iso(now - 8), "client": c["ip"], "question": {"name": NEW[1], "type": "A"}, "reason": "NotFilteredNotFound",
                            "status": "NOERROR", "answer": [{"type": "A", "value": demo_ip(NEW[1])}]})
        return sorted(out, key=lambda x: x["time"], reverse=True)
