"""AdGuard Home: wie wat opzoekt, of je DNS-servers het doen en wat AdGuard tegenhield.

Alleen lezen. Sonar haalt het querylog, de statistieken en de instellingen op via de API van AdGuard Home
(gebruikersnaam en wachtwoord) en stelt elke DNS-server zelf af en toe een gewone DNS-vraag.

Privacy: het querylog is in feite de browsegeschiedenis van iedereen in huis. Daarom bewaart Sonar domeinen per
apparaat alleen voor apparaten die het volgt: slimme apparaten en servers, of wat je zelf aanzet. Van alle andere
apparaten telt het alleen hoeveel ze opzoeken en hoeveel er tegengehouden werd. Blokkades van malware en phishing
worden wel voor elk apparaat bewaard, want daar wil je juist van weten.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import random
import re
import struct
import time
from collections import deque
from datetime import datetime
from urllib.parse import urlparse

import httpx

from . import pihole
from .i18n import L
from .segments import client_segment, smart_reason

log = logging.getLogger("sonar.adguard")

DAY = 86400
PAGE = 500                 # querylog-regels per verzoek
MAX_PAGES = 20             # per ronde; daarna verder in de volgende
LOG_EVERY = 60
STATS_EVERY = 600
CONFIG_EVERY = 900
PROBE_EVERY = 120          # elke 2 minuten één DNS-vraag per server: genoeg om uitval snel te zien
PROBE_NAME = "example.com"
LEARN_DAYS = 7             # zo lang leert Sonar wat normaal is voor een apparaat
SLOW_MS = 150
BYPASS_MIN_FLOWS = 20
MAX_INSTANCES = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS dns_hourly (hour INT, mac TEXT, q INT, blocked INT, PRIMARY KEY (hour, mac));
CREATE TABLE IF NOT EXISTS dns_names (mac TEXT, ip TEXT, domain TEXT, ts INT, PRIMARY KEY (mac, ip));
CREATE TABLE IF NOT EXISTS dns_domains (mac TEXT, domain TEXT, first INT, last INT, n INT, blocked INT, PRIMARY KEY (mac, domain));
CREATE TABLE IF NOT EXISTS dns_threats (ts INT, mac TEXT, ip TEXT, name TEXT, list TEXT);
CREATE INDEX IF NOT EXISTS ix_dns_threats ON dns_threats(ts);
CREATE INDEX IF NOT EXISTS ix_dns_names_ts ON dns_names(ts);
"""

# Filterlijsten tegen malware, phishing en oplichting, herkend aan hun naam.
THREAT_LIST = re.compile(r"malware|phish|threat|scam|fraud|ransom|crypto.?jack|botnet|stalkerware|urlhaus|badware|"
                         r"spam404|dandelion|security|abuse", re.I)
# Fabrikanten en namen van servers en NAS'en: die volgt Sonar standaard, net als slimme apparaten.
SERVER_VENDORS = ("synology", "qnap", "asustor", "terramaster", "raspberry", "supermicro", "nabu casa", "proxmox")
SERVER_HOST = re.compile(r"(^|[-_.\s])(nas|server|srv|pve|proxmox|home[-\s]?assistant|hassio|hass|docker|plex|jellyfin|unraid|"
                         r"truenas|diskstation|adguard|pihole|pi-hole|nextcloud|frigate|n8n|lxc)([-_.\s\d]|$)", re.I)
LOCAL = (".local", ".lan", ".home", ".internal", ".arpa", ".localdomain", ".localhost")
# Tweede niveaus waar het 'echte' domein één label dieper zit.
_SLD = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.nz", "co.jp", "ne.jp", "or.jp", "com.br",
        "com.cn", "com.tw", "co.kr", "co.za", "com.mx", "com.tr", "co.in", "github.io", "herokuapp.com", "cloudfront.net",
        "amazonaws.com", "azurewebsites.net", "appspot.com", "blogspot.com", "netlify.app", "vercel.app", "workers.dev",
        "pages.dev", "duckdns.org", "ddns.net", "no-ip.org", "synology.me", "myqnapcloud.com", "azureedge.net", "akamaiedge.net"}


# ------------------------------------------------------------------ hulpfuncties
def reg_domain(name: str) -> str:
    """Het domein zonder subdomeinen: a1.eu.tuya.com → tuya.com. Benadering zonder de volledige suffixlijst."""
    labels = name.lower().rstrip(".").split(".")
    if len(labels) <= 2:
        return ".".join(labels)
    return ".".join(labels[-3:] if ".".join(labels[-2:]) in _SLD else labels[-2:])


def interesting(name: str) -> bool:
    n = name.lower().rstrip(".")
    return "." in n and not n.endswith(LOCAL) and n != PROBE_NAME


_FRAC = re.compile(r"(\.\d{6})\d+")


def parse_time(s) -> float:
    """AdGuard geeft een tijdstip met nanoseconden (Python kan er zes aan); Pi-hole geeft seconden als getal."""
    if isinstance(s, (int, float)):
        return float(s)
    try:
        return datetime.fromisoformat(_FRAC.sub(r"\1", s.replace("Z", "+00:00"))).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def device_class(c: dict, segs: list[dict] | None) -> str:
    """'smart', 'server' of 'personal'. Persoonlijke apparaten volgt Sonar niet, tenzij je dat zelf aanzet."""
    s = client_segment(c, segs) if segs else None
    if smart_reason(c) or (s and s.get("kind") == "iot"):
        return "smart"
    v = (c.get("vendor") or "").lower()
    if any(x in v for x in SERVER_VENDORS) or any(SERVER_HOST.search(x or "") for x in (c.get("hostname"), c.get("name"))):
        return "server"
    return "personal"


def gateway_ips(snap: dict, segs) -> set[str]:
    """Alle adressen van de gateway. UniFi geeft bij de gateway zelf het WAN-adres; de LAN-kant staat als
    gateway-adres in het subnet van elk netwerk ("192.168.1.1/24"). Omgeleide DNS komt met die afzender binnen."""
    out = {d.get("ip") for d in snap.get("devices") or [] if d.get("type") == "gateway" and d.get("ip")}
    for s in segs or []:
        sub = s.get("subnet") or ""
        if "/" in sub:
            out.add(sub.split("/")[0])
    return out


def subnets(segs) -> list:
    out = []
    for s in segs or []:
        try:
            out.append(ipaddress.ip_network(s.get("subnet") or "", strict=False))
        except ValueError:
            pass
    return out


def outside(ip: str, nets: list) -> bool:
    """Een IPv4-adres buiten al je UniFi-netwerken (een ander netwerk achter een router, een VPN): dat kan nooit
    een UniFi-apparaat zijn, dus het telt niet mee als 'onbekend'. IPv6 of zonder netwerken weet Sonar het niet zeker."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return bool(nets) and a.version == 4 and not any(a in n for n in nets if n.version == 4)


def host_of(url: str) -> str:
    return (urlparse(url if "://" in url else "http://" + url).hostname or "").lower()


def threat_list(item: dict, lists: dict[int, str]) -> str | None:
    """De naam van de beveiligingslijst die dit tegenhield, of None als het geen malware of phishing was."""
    r = item.get("reason")
    if r == "FilteredSafeBrowsing":
        return "AdGuard Browsing Security"
    if r == "FilteredBlackList":
        for rule in item.get("rules") or []:
            name = lists.get(rule.get("filter_list_id"))
            if name and THREAT_LIST.search(name):
                return name
    return None


def blocked(item: dict) -> bool:
    r = item.get("reason") or ""
    return r.startswith("Filtered") and r != "FilteredSafeSearch"


async def dns_probe(server: str, name: str = PROBE_NAME, timeout: float = 2.0, port: int = 53) -> dict:
    """Eén gewone DNS-vraag (A-record) via UDP. ok = er kwam een geldig antwoord, ook als het domein niet bestaat."""
    qid = random.randrange(1, 65535)
    packet = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + b"".join(
        bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0" + struct.pack(">HH", 1, 1)
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()

    class Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            if len(data) >= 12 and data[:2] == packet[:2] and not fut.done():
                fut.set_result(data)

        def error_received(self, exc):
            if not fut.done():
                fut.set_exception(exc)

    t0 = time.monotonic()
    tr = None
    try:
        tr, _ = await loop.create_datagram_endpoint(Proto, remote_addr=(server, port))
        tr.sendto(packet)
        data = await asyncio.wait_for(fut, timeout)
        rcode = data[3] & 0x0F
        return {"ok": rcode in (0, 3), "ms": round((time.monotonic() - t0) * 1000, 1), "rcode": rcode}
    except asyncio.TimeoutError:
        return {"ok": False, "ms": None, "error": "timeout"}
    except OSError as e:
        return {"ok": False, "ms": None, "error": str(e)[:80]}
    finally:
        if tr:
            tr.close()


class AuthError(Exception):
    pass


class API:
    """Eén AdGuard Home. Alleen GET-verzoeken."""

    kind, label = "adguard", "AdGuard Home"

    def __init__(self, inst: dict) -> None:
        self.name = inst.get("name") or host_of(inst.get("url", ""))
        self.url = (inst.get("url") or "").rstrip("/")
        if self.url and "://" not in self.url:
            self.url = "http://" + self.url
        self.auth = (inst.get("username") or "", inst.get("password") or "")
        self.verify = bool(inst.get("verify_tls"))

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(verify=self.verify, timeout=8, follow_redirects=False)

    async def get(self, http, path: str, **params):
        r = await http.get(self.url + path, params=params or None, auth=self.auth if self.auth[0] else None)
        if r.status_code in (401, 403):
            raise AuthError(L("inloggen geweigerd: controleer gebruikersnaam en wachtwoord", "login refused: check username and password"))
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            raise RuntimeError(L("geen AdGuard Home op dit adres", "no AdGuard Home at this address")) from None


    # ---- wat Sonar nodig heeft; pihole.API heeft dezelfde methodes
    async def status(self, http) -> dict:
        s = await self.get(http, "/control/status")
        return {"version": s.get("version"), "running": s.get("running"), "protection": s.get("protection_enabled")}

    async def settings(self, http) -> tuple[dict[int, str], dict]:
        f = await self.get(http, "/control/filtering/status")
        rw = await self.get(http, "/control/rewrite/list")
        info = await self.get(http, "/control/dns_info")
        names = {x["id"]: x.get("name") or x.get("url") or "" for x in f.get("filters") or [] if "id" in x}
        return names, {
            "rewrites": sorted(f"{r.get('domain')} → {r.get('answer')}" for r in rw or [] if r.get("enabled", True)),
            "lists": sorted(x.get("url") or x.get("name") for x in f.get("filters") or [] if x.get("enabled")),
            "upstreams": sorted(u for u in info.get("upstream_dns") or [] if u and not u.startswith("#")),
            "rules": len([r for r in f.get("user_rules") or [] if r.strip() and not r.startswith("!")])}

    async def stats(self, http) -> dict:
        d = await self.get(http, "/control/stats")
        return {"queries": d.get("num_dns_queries") or 0, "blocked": d.get("num_blocked_filtering") or 0,
                "avg_ms": round((d.get("avg_processing_time") or 0) * 1000, 1),
                "upstreams": [{"name": k, "avg_ms": round(v * 1000, 1)} for e in d.get("top_upstreams_avg_time") or []
                              for k, v in e.items()][:5]}

    async def log(self, http, since: float, page: int, max_pages: int) -> tuple[list[dict], str | None]:
        return await fetch_log(self, http, since), None

    async def test(self) -> dict:
        async with self.client() as http:
            st = await self.status(http)
            q = await self.get(http, "/control/querylog", limit=1)
        return {"ok": True, "version": st.get("version"), "protection": st.get("protection"), "log": bool(q.get("data"))}


KINDS = {"adguard": API, "pihole": pihole.API}


def kind_of(inst: dict) -> str:
    return inst.get("kind") if inst.get("kind") in KINDS else "adguard"


def make_api(inst: dict):
    return KINDS[kind_of(inst)](inst)


def product(kinds) -> str:
    """Hoe Sonar je DNS-filter noemt in teksten: de naam van het product, of iets algemeens als je er twee soorten hebt."""
    ks = set(kinds)
    if ks == {"adguard"}:
        return "AdGuard"
    if ks == {"pihole"}:
        return "Pi-hole"
    return L("je DNS-filter", "your DNS filter")


async def fetch_log(api, http, since: float) -> list[dict]:
    """Nieuwe querylog-regels na 'since', nieuwste eerst, in pagina's terug in de tijd."""
    out: list[dict] = []
    older = None
    for _ in range(MAX_PAGES):
        d = await api.get(http, "/control/querylog", limit=PAGE, **({"older_than": older} if older else {}))
        page = d.get("data") or []
        for it in page:
            if parse_time(it.get("time")) <= since:
                return out
            out.append(it)
        if len(page) < PAGE or not d.get("oldest"):
            break
        older = d["oldest"]
    return out


async def test_instance(inst: dict) -> dict:
    """Voor de knop 'Verbinding testen'."""
    try:
        return {**await make_api(inst).test(), "kind": kind_of(inst)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "kind": kind_of(inst), "error": str(e)[:200] or type(e).__name__}


# ------------------------------------------------------------------ verzamelen
class AdGuard:
    def __init__(self, settings, db, mock) -> None:
        self.s, self.db, self.mock = settings, db, mock
        with db.lock, db.conn:
            db.conn.executescript(SCHEMA)
        if mock:
            self._seed_demo()
        st = db.get_kv("adguard") or {}
        self.cursor: dict[str, float] = st.get("cursor") or {}
        self.since: int | None = st.get("since")            # vanaf wanneer Sonar het querylog bijhoudt
        self.status: dict[str, dict] = {}                     # per AdGuard: bereikbaar, versie, bescherming, statistiek
        self.config: dict[str, dict] = {}                     # per AdGuard: rewrites, lijsten, upstreams
        self.lists: dict[str, dict[int, str]] = {}
        self.probes: dict[str, deque] = {}
        self.servfail: dict[str, deque] = {}                  # per AdGuard: (ts, vragen, SERVFAIL) per ronde
        self._last = {"log": 0, "stats": 0, "config": 0, "probe": 0}

    # instellingen
    @property
    def cfg(self) -> dict:
        return {"instances": [], "personal": False, "watch": {}, **(self.s.adguard or {})}

    def instances(self) -> list[dict]:
        inst = [i for i in self.cfg["instances"] if i.get("url")][:MAX_INSTANCES]
        if not inst and self.mock:
            return [{"name": "AdGuard 1", "url": "http://192.168.1.22"}, {"name": "AdGuard 2", "url": "http://192.168.1.23"}]
        return inst

    def apis(self) -> list:
        if self.mock:
            from .mock_adguard import MockAPI
            return [MockAPI(i, n) for n, i in enumerate(self.instances())]
        return [make_api(i) for i in self.instances()]

    @property
    def active(self) -> bool:
        return bool(self.instances())

    def watched(self, c: dict, segs) -> bool:
        o = self.cfg["watch"].get(c.get("mac"))
        if o is not None:
            return bool(o)
        return self.cfg["personal"] or device_class(c, segs) != "personal"

    def _save(self) -> None:
        self.db.set_kv("adguard", {"cursor": self.cursor, "since": self.since})

    # de ronde
    async def tick(self, snap: dict, ts: int) -> None:
        apis = self.apis()
        urls = {a.url for a in apis}
        for d in (self.status, self.config, self.lists, self.servfail):     # een server die je weghaalde telt niet meer mee
            for u in [u for u in d if u not in urls]:
                del d[u]
        if not self.active or ts < time.time() - 120:     # demo: niet tijdens het vullen met historie
            return
        if self.mock:
            from .mock_adguard import MockAPI
            MockAPI.snap = snap
        if ts - self._last["probe"] >= PROBE_EVERY:
            self._last["probe"] = ts
            await self._probe(snap, apis, ts)
        if ts - self._last["log"] < LOG_EVERY:
            return
        self._last["log"] = ts
        due_stats, due_cfg = ts - self._last["stats"] >= STATS_EVERY, ts - self._last["config"] >= CONFIG_EVERY
        await asyncio.gather(*(self._one(a, snap, ts, due_stats, due_cfg) for a in apis))
        if due_stats:
            self._last["stats"] = ts
        if due_cfg:
            self._last["config"] = ts
        self.name_flows(ts)
        self._save()

    async def _one(self, api, snap: dict, ts: int, due_stats: bool, due_cfg: bool) -> None:
        st = self.status.setdefault(api.url, {"name": api.name, "url": api.url})
        st.update(name=api.name, kind=api.kind)
        try:
            async with api.client() as http:
                t0 = time.monotonic()
                s = await api.status(http)
                st.update(ok=True, error=None, checked=ts, http_ms=round((time.monotonic() - t0) * 1000), version=s.get("version"),
                          running=s.get("running"), protection=s.get("protection"))
                if due_cfg or api.url not in self.lists:
                    self.lists[api.url], cfg = await api.settings(http)
                    self.config[api.url] = {**cfg, "kind": api.kind}
                if due_stats or "stats" not in st:
                    st["stats"] = await api.stats(http)
                first = api.url not in self.cursor
                since = self.cursor.get(api.url) or ts - 3600     # de eerste keer alleen het laatste uur
                items, st["note"] = await api.log(http, since, PAGE, MAX_PAGES)
            if items:
                self.cursor[api.url] = max(parse_time(i.get("time")) for i in items)
            elif first:
                self.cursor[api.url] = since
            if self.since is None:
                self.since = ts
            self.ingest(items, snap, api.url, ts)
        except Exception as e:  # noqa: BLE001 – een AdGuard die niet antwoordt mag de rest niet ophouden
            log.info("%s %s: %s", api.label, api.name, e)
            st.update(ok=False, error=str(e)[:200] or type(e).__name__, checked=ts)

    async def _probe(self, snap: dict, apis, ts: int) -> None:
        servers = {}
        for a in apis:
            h = host_of(a.url)
            if h:
                servers[h] = a.name
        for ip in ((snap.get("config") or {}).get("dns_servers") or []):
            servers.setdefault(ip, ip)
        if self.mock:
            from .mock_adguard import probe as mprobe
            results = [mprobe(h) for h in servers]
        else:
            results = await asyncio.gather(*(dns_probe(h) for h in servers))
        for (h, name), r in zip(servers.items(), results):
            q = self.probes.setdefault(h, deque(maxlen=30))
            q.append({"ts": ts, "name": name, **r})
        for h in list(self.probes):
            if h not in servers:
                del self.probes[h]

    def ingest(self, items: list[dict], snap: dict, url: str, ts: int) -> None:
        """Het querylog omzetten naar tellingen per apparaat, namen bij IP-adressen en domeinen van gevolgde apparaten."""
        clients = snap.get("clients") or []
        segs = ((snap.get("config") or {}).get("segments") or {}).get("segments")
        by_ip = {c["ip"]: c for c in clients if c.get("ip")}
        by_name = {(c.get("hostname") or "").lower(): c for c in clients if c.get("hostname")}
        gw = gateway_ips(snap, segs)
        nets = subnets(segs)
        lists = self.lists.get(url) or {}
        watch: dict[str, bool] = {}
        hourly: dict[tuple, list] = {}
        names: dict[tuple, tuple] = {}
        doms: dict[tuple, list] = {}
        threats = []
        sf = 0
        for it in items:
            t = int(parse_time(it.get("time")))
            q = it.get("question") or {}
            name = (q.get("unicode_name") or q.get("name") or "").lower().rstrip(".")
            ip = it.get("client") or ""
            c = by_ip.get(ip) or by_name.get(((it.get("client_info") or {}).get("name") or "").lower())
            mac = c["mac"] if c else "redirected" if ip in gw else "elsewhere" if outside(ip, nets) else "unknown"
            blk = blocked(it)
            sf += it.get("status") == "SERVFAIL"
            h = hourly.setdefault((t - t % 3600, mac), [0, 0])
            h[0] += 1
            h[1] += blk
            tl = threat_list(it, lists) if blk else None
            if tl:
                threats.append((t, mac if c else None, ip, name, tl))
            if not c or not interesting(name):
                continue
            if mac not in watch:
                watch[mac] = self.watched(c, segs)
            if not watch[mac]:
                continue
            for a in it.get("answer") or []:
                if a.get("type") in ("A", "AAAA") and a.get("value"):
                    names[(mac, a["value"])] = (name, t)
            d = doms.setdefault((mac, reg_domain(name)), [t, t, 0, 0])
            d[0], d[1] = min(d[0], t), max(d[1], t)
            d[2] += 1
            d[3] += blk
        self.servfail.setdefault(url, deque(maxlen=60)).append((ts, len(items), sf))
        with self.db.lock, self.db.conn:
            c = self.db.conn
            c.executemany("INSERT INTO dns_hourly VALUES (?,?,?,?) ON CONFLICT(hour, mac) DO UPDATE SET q=q+excluded.q, "
                          "blocked=blocked+excluded.blocked", [(h, m, v[0], v[1]) for (h, m), v in hourly.items()])
            c.executemany("INSERT OR REPLACE INTO dns_names VALUES (?,?,?,?)", [(m, i, n, t) for (m, i), (n, t) in names.items()])
            c.executemany("INSERT INTO dns_domains VALUES (?,?,?,?,?,?) ON CONFLICT(mac, domain) DO UPDATE SET "
                          "first=MIN(first, excluded.first), last=MAX(last, excluded.last), n=n+excluded.n, blocked=blocked+excluded.blocked",
                          [(m, d, v[0], v[1], v[2], v[3]) for (m, d), v in doms.items()])
            c.executemany("INSERT INTO dns_threats VALUES (?,?,?,?,?)", threats)

    def name_flows(self, ts: int) -> None:
        """Verbindingen zonder naam krijgen de naam die het apparaat net daarvoor bij AdGuard opzocht."""
        with self.db.lock, self.db.conn:
            self.db.conn.execute(
                "UPDATE flows SET domain=(SELECT n.domain FROM dns_names n WHERE n.mac=flows.client_mac AND n.ip=flows.remote_ip) "
                "WHERE ts>=? AND dir='out' AND domain IS NULL AND remote_ip IS NOT NULL AND client_mac IS NOT NULL AND EXISTS "
                "(SELECT 1 FROM dns_names n WHERE n.mac=flows.client_mac AND n.ip=flows.remote_ip)", (ts - 7200,))

    def forget(self, mac: str) -> None:
        """Niet meer volgen = ook de domeinen van dat apparaat weggooien."""
        with self.db.lock, self.db.conn:
            self.db.conn.execute("DELETE FROM dns_domains WHERE mac=?", (mac,))
            self.db.conn.execute("DELETE FROM dns_names WHERE mac=?", (mac,))

    def purge(self, ts: int, retention_days: int) -> None:
        with self.db.lock, self.db.conn:
            c = self.db.conn
            c.execute("DELETE FROM dns_hourly WHERE hour < ?", (ts - retention_days * DAY,))
            c.execute("DELETE FROM dns_threats WHERE ts < ?", (ts - retention_days * DAY,))
            c.execute("DELETE FROM dns_names WHERE ts < ?", (ts - 2 * DAY,))
            c.execute("DELETE FROM dns_domains WHERE last < ?", (ts - 90 * DAY,))

    def _seed_demo(self) -> None:
        from .mock_adguard import seed
        seed(self.db)

    # ------------------------------------------------------------- uitkomst
    def servers(self) -> list[dict]:
        out = []
        kinds = {host_of(u): st.get("kind") for u, st in self.status.items()}
        for h, q in self.probes.items():
            last = list(q)
            ok = [p["ms"] for p in last[-10:] if p["ok"] and p["ms"] is not None]
            down = len(last) >= 3 and not any(p["ok"] for p in last[-3:])
            out.append({"host": h, "name": last[-1]["name"], "kind": kinds.get(h), "ok": last[-1]["ok"], "down": down, "ms": last[-1].get("ms"),
                        "median_ms": sorted(ok)[len(ok) // 2] if ok else None, "error": last[-1].get("error"),
                        "history": [p["ms"] if p["ok"] else None for p in last], "checked": last[-1]["ts"]})
        return out

    def drift(self) -> dict | None:
        """Verschillen tussen servers van hetzelfde soort: een AdGuard en een Pi-hole stel je anders in, die vergelijkt Sonar niet."""
        out, names = [], []
        for kind in KINDS:
            cfgs = [(self.status.get(u, {}).get("name") or u, c) for u, c in self.config.items() if c.get("kind", "adguard") == kind]
            if len(cfgs) < 2:
                continue
            names += [n for n, _ in cfgs]
            for key, label in (("rewrites", "rewrites"), ("lists", "lists"), ("upstreams", "upstreams")):
                sets = [(n, set(c[key])) for n, c in cfgs]
                union = set().union(*(s for _, s in sets))
                for n, s in sets:
                    missing = sorted(union - s)
                    if missing:
                        out.append({"what": label, "missing_on": n, "items": missing[:10], "n": len(missing), "kind": kind})
            rules = {n: c["rules"] for n, c in cfgs}
            if len(set(rules.values())) > 1:
                out.append({"what": "rules", "missing_on": None, "items": [f"{n}: {v}" for n, v in rules.items()], "n": 0, "kind": kind})
        return {"items": out, "names": names} if names else None

    def for_rules(self) -> dict:
        servfail = {}
        for url, q in self.servfail.items():
            recent = [x for x in q if x[0] >= time.time() - 3600]
            n, f = sum(x[1] for x in recent), sum(x[2] for x in recent)
            servfail[self.status.get(url, {}).get("name") or url] = (n, f)
        kinds = sorted({kind_of(i) for i in self.instances()})
        return {"active": self.active, "since": self.since, "servers": self.servers(), "drift": self.drift(),
                "kinds": kinds, "product": product(kinds),
                "apis": [{k: v for k, v in s.items() if k != "stats"} for s in self.status.values()], "servfail": servfail,
                "watch": self.cfg["watch"], "personal": self.cfg["personal"]}


# ------------------------------------------------------------------ controles
def _who(clients: dict, db, mac: str) -> str:
    c = clients.get(mac)
    if c:
        return c.get("name") or mac
    r = db.q("SELECT name FROM known_clients WHERE mac=?", (mac,))
    return (r[0]["name"] if r and r[0]["name"] else None) or mac


def new_domains(db, ts: int) -> dict[str, list[dict]]:
    """Domeinen die een gevolgd apparaat het afgelopen etmaal voor het eerst opzocht, na een week leren."""
    learned = {r["mac"] for r in db.q("SELECT mac FROM dns_domains GROUP BY mac HAVING MIN(first) <= ?", (ts - LEARN_DAYS * DAY,))}
    out: dict[str, list[dict]] = {}
    for r in db.q("SELECT mac, domain, first, n, blocked FROM dns_domains WHERE first >= ? ORDER BY first DESC", (ts - DAY,)):
        if r["mac"] in learned:
            out.setdefault(r["mac"], []).append(dict(r))
    return out


def threats(db, ts: int) -> list[dict]:
    rows = db.q("SELECT mac, ip, name, list, ts FROM dns_threats WHERE ts >= ? ORDER BY ts DESC", (ts - DAY,))
    per: dict[str, dict] = {}
    for r in rows:
        k = r["mac"] or r["ip"]
        p = per.setdefault(k, {"mac": r["mac"], "ip": r["ip"], "n": 0, "domains": [], "lists": set(), "last": r["ts"]})
        p["n"] += 1
        p["lists"].add(r["list"])
        if r["name"] not in p["domains"]:
            p["domains"].append(r["name"])
    for p in per.values():
        p["lists"] = sorted(p["lists"])
        ips = db.q("SELECT COUNT(*) n FROM ips_events WHERE ts >= ? AND internal=1 AND src_ip=?", (ts - DAY, p["ip"]))
        p["ips"] = ips[0]["n"] if ips else 0
    return sorted(per.values(), key=lambda p: -p["n"])


def coverage(db, ts: int) -> dict:
    rows = {r["mac"]: (r["q"], r["b"]) for r in db.q("SELECT mac, SUM(q) q, SUM(blocked) b FROM dns_hourly WHERE hour >= ? GROUP BY mac",
                                                       (ts - DAY - ts % 3600,))}
    total = sum(q for q, _ in rows.values())
    return {"queries": total, "blocked": sum(b for _, b in rows.values()), "redirected": rows.get("redirected", (0, 0))[0],
            "unknown": rows.get("unknown", (0, 0))[0], "elsewhere": rows.get("elsewhere", (0, 0))[0],
            "devices": sum(1 for m in rows if ":" in m), "per": rows}


def bypass(snap: dict, db, ts: int, ag: dict) -> tuple[list[dict], str | None]:
    """Apparaten met verkeer naar internet die AdGuard nooit iets vragen. Tweede waarde: waarom er niet gekeken is."""
    if not ag.get("since") or ag["since"] > ts - DAY:
        return [], L(f"Sonar volgt {ag.get('product') or 'AdGuard'} nog geen etmaal.", f"Sonar hasn't followed {ag.get('product') or 'AdGuard'} for a full day yet.")
    cov = coverage(db, ts)
    if cov["queries"] and cov["unknown"] / cov["queries"] > 0.1:
        return [], L("Meer dan 10% van de vragen komt van adressen die Sonar niet aan een apparaat kan koppelen (bijvoorbeeld IPv6), "
                     f"dus het kan niet zeggen wie {ag.get('product') or 'AdGuard'} overslaat.",
                     "More than 10% of queries come from addresses Sonar can't link to a device (IPv6, for example), "
                     f"so it can't tell who skips {ag.get('product') or 'AdGuard'}.")
    resolvers = _resolvers(snap, ag)
    own = {m for m, o in own_dns(snap, db, ts, ag).items() if not o["dot"]}   # doorgelaten DoT gaat echt om AdGuard heen
    flows = {r["client_mac"]: (r["n"], r["last"]) for r in db.q(
        "SELECT client_mac, COUNT(*) n, MAX(ts) last FROM flows WHERE ts >= ? AND dir='out' AND client_mac IS NOT NULL GROUP BY client_mac",
        (ts - DAY,))}
    out = []
    for c in snap.get("clients") or []:
        n, last = flows.get(c["mac"], (0, 0))
        if n < BYPASS_MIN_FLOWS or c.get("guest") or not c.get("connected", True) or c.get("ip") in resolvers or c["mac"] in own:
            continue
        if cov["per"].get(c["mac"], (0, 0))[0] == 0:
            out.append({"mac": c["mac"], "name": c.get("name") or c["mac"], "ip": c.get("ip"), "flows": n, "last": last})
    return out, None


def _public(ip) -> bool:
    try:
        return ipaddress.ip_address(ip or "").is_global
    except ValueError:
        return False


def _resolvers(snap: dict, ag: dict) -> set[str]:
    return {s["host"] for s in ag.get("servers") or []} | set((snap.get("config") or {}).get("dns_servers") or [])


def own_dns(snap: dict, db, ts: int, ag: dict) -> dict[str, dict]:
    """Apparaten die zelf een andere DNS-server aanspreken (poort 53 of 853, niet je AdGuard). Doorgelaten poort 53
    is met een NAT-regel omgeleid: UniFi logt het oorspronkelijke doel, AdGuard ziet alleen de gateway als afzender.
    Geblokkeerd is tegengehouden door je firewall. De DNS-lekcontrole meldt ze al; hier staan ze zodat 'AdGuard
    overslaan' ze niet ten onrechte meldt."""
    resolvers = _resolvers(snap, ag)
    out: dict[str, dict] = {}
    # UniFi zet omgeleide DNS op 'local' (het nieuwe doel ligt in je netwerk), maar logt wel het oorspronkelijke adres
    for r in db.q("SELECT client_mac, client_ip, remote_ip, port, dir, action, MAX(client_name) cname, COUNT(*) n, MAX(ts) last FROM flows WHERE ts >= ? "
                  "AND dir IN ('out', 'local', 'blocked') AND client_mac IS NOT NULL AND port IN (53, 853) "
                  "GROUP BY client_mac, client_ip, remote_ip, port, dir, action", (ts - DAY,)):
        if r["remote_ip"] in resolvers or r["client_ip"] in resolvers or not _public(r["remote_ip"]):
            continue      # gewoon AdGuard, of AdGuard zelf die zijn upstream vraagt
        o = out.setdefault(r["client_mac"], {"redirected": 0, "blocked": 0, "dot": 0, "servers": set(), "last": 0, "flow_name": None})
        if r["cname"] and not r["cname"][0].isdigit():    # UniFi geeft soms alleen het IP
            o["flow_name"] = re.sub(r"\s[0-9a-f]{2}:[0-9a-f]{2}$", "", r["cname"])   # zonder het MAC-staartje
        if r["dir"] == "blocked" or r["action"] != "allowed":
            o["blocked"] += r["n"]
        elif r["port"] == 53:
            o["redirected"] += r["n"]
        else:
            o["dot"] += r["n"]       # doorgelaten DoT: echt om AdGuard heen
        o["servers"].add(r["remote_ip"])
        o["last"] = max(o["last"], r["last"])
    return out


def issues(out: list[dict], snap: dict, db, ts: int, issue) -> None:
    ag = snap.get("adguard") or {}
    if not ag.get("active"):
        return
    clients = {c["mac"]: c for c in snap.get("clients") or []}
    dhcp = (snap.get("config") or {}).get("dns_servers") or []
    servers = ag.get("servers") or []
    first_api = host_of((ag.get("apis") or [{}])[0].get("url") or "") if ag.get("apis") else None
    P = ag.get("product") or "AdGuard"
    label = lambda kind: "Pi-hole" if kind == "pihole" else "AdGuard" if kind == "adguard" else L("de DNS-server", "the DNS server")

    # 3. bewaking: antwoorden je DNS-servers nog, en snel genoeg?
    for s in servers:
        primary = s["host"] in dhcp[:1] or s["host"] == first_api
        if s["down"]:
            out.append(issue(f"adguard:down:{s['host']}", "critical" if primary else "warning", "wan", "site", "dns",
                             L(f"DNS-server {s['name']} antwoordt niet", f"DNS server {s['name']} is not answering"),
                             L(f"Sonar stelde {s['host']} drie keer achter elkaar een DNS-vraag en kreeg geen antwoord"
                               f"{' (' + s['error'] + ')' if s.get('error') and s['error'] != 'timeout' else ''}.",
                               f"Sonar asked {s['host']} a DNS question three times in a row and got no answer"
                               f"{' (' + s['error'] + ')' if s.get('error') and s['error'] != 'timeout' else ''}."),
                             L("Gaat al je DNS via deze server, bijvoorbeeld door een NAT-regel die DNS omleidt, dan kan nu niemand in huis "
                               f"nog namen opzoeken. Herstart {label(s.get('kind'))}, of zet de omleiding tijdelijk uit tot hij weer draait.",
                               "If all your DNS goes through this server, for example because of a NAT rule that redirects DNS, nobody at "
                               f"home can look up names right now. Restart {label(s.get('kind'))}, or switch off the redirect until it runs again."),
                             last_ts=s["checked"]))
        elif s["median_ms"] is not None and s["median_ms"] > SLOW_MS:
            out.append(issue(f"adguard:slow:{s['host']}", "warning", "wan", "site", "dns",
                             L(f"DNS van {s['name']} is traag", f"DNS from {s['name']} is slow"),
                             L(f"Een DNS-antwoord duurt de laatste tijd ongeveer {s['median_ms']:.0f} ms; normaal is onder de 50 ms.",
                               f"A DNS answer takes about {s['median_ms']:.0f} ms lately; normal is under 50 ms."),
                             (L("Kijk in Pi-hole bij Settings → DNS welke upstream je gebruikt en probeer een andere. Controleer ook of de "
                                "machine waar Pi-hole op draait niet overbelast is.",
                                "In Pi-hole, check under Settings → DNS which upstream you use and try another one. Also check that the "
                                "machine Pi-hole runs on isn't overloaded.") if s.get("kind") == "pihole" else
                              L("Kijk in AdGuard bij Instellingen → DNS-instellingen welke upstream traag is, en zet 'Parallelle verzoeken' "
                                "of 'Snelste IP-adres' aan. Controleer ook of de machine waar AdGuard op draait niet overbelast is.",
                                "In AdGuard, check under Settings → DNS settings which upstream is slow, and turn on 'Parallel requests' or "
                                "'Fastest IP address'. Also check that the machine AdGuard runs on isn't overloaded.")), metric="ms",
                             value=s["median_ms"], threshold=SLOW_MS))
    for a in ag.get("apis") or []:
        A, pi = label(a.get("kind")), a.get("kind") == "pihole"
        if a.get("ok") is False:
            out.append(issue(f"adguard:api:{host_of(a['url'])}", "warning", "config", "site", "dns",
                             L(f"Sonar kan {a['name']} niet uitlezen", f"Sonar can't read {a['name']}"),
                             L(f"De API van {A} gaf: {a.get('error')}. Zolang dat zo is, ziet Sonar geen nieuwe DNS-vragen van dit adres.",
                               f"The API of {A} returned: {a.get('error')}. Until that is fixed, Sonar sees no new DNS queries from this address."),
                             L(f"Controleer het adres en het wachtwoord{'' if pi else ' en de gebruikersnaam'} onder Instellingen → DNS-filter.",
                               f"Check the address and password{'' if pi else ' and the username'} under Settings → DNS filter.")))
        elif a.get("protection") is False:
            out.append(issue(f"adguard:protection:{host_of(a['url'])}", "warning", "security", "site", "dns",
                             L(f"Bescherming van {a['name']} staat uit", f"Protection on {a['name']} is off"),
                             L(f"{A} beantwoordt DNS-vragen, maar blokkeert niets: geen advertenties, geen trackers en geen malware.",
                               f"{A} answers DNS queries but blocks nothing: no ads, no trackers and no malware."),
                             (L("Zet in Pi-hole het blokkeren weer aan (Enable Blocking in het menu). Stond het tijdelijk uit, dan gaat het vanzelf weer aan.",
                                "Turn blocking back on in Pi-hole (Enable Blocking in the menu). If it was paused, it comes back on by itself.") if pi else
                              L("Zet in AdGuard bovenaan de bescherming weer aan. Stond hij tijdelijk uit, dan gaat hij vanzelf weer aan.",
                                "Turn protection back on at the top of AdGuard. If it was paused, it comes back on by itself."))))
        elif a.get("note"):
            out.append(issue(f"adguard:hidden:{host_of(a['url'])}", "info", "config", "site", "dns",
                             L(f"{a['name']} verbergt gegevens voor Sonar", f"{a['name']} hides data from Sonar"),
                             str(a["note"]) + ".",
                             L("Wil je dat Sonar per apparaat ziet wat het opzoekt, zet dan in Pi-hole bij Settings → Privacy het niveau op "
                               "'Show everything'. Wil je dat niet, negeer deze melding dan.",
                               "If you want Sonar to see what each device looks up, set the level to 'Show everything' in Pi-hole under "
                               "Settings → Privacy. If you don't, ignore this issue.")))
    for name, (n, f) in (ag.get("servfail") or {}).items():
        if n >= 50 and f / n > 0.05:
            out.append(issue(f"adguard:servfail:{name}", "warning", "wan", "site", "dns",
                             L(f"{name} krijgt geen antwoord van zijn upstream", f"{name} gets no answer from its upstream"),
                             L(f"{f} van de {n} DNS-vragen van het afgelopen uur eindigden in een fout (SERVFAIL).",
                               f"{f} of the {n} DNS queries in the past hour ended in an error (SERVFAIL)."),
                             L(f"Controleer in {P} bij de DNS-instellingen de upstreams en voeg een tweede upstream toe.",
                               f"In {P}, check the upstreams under the DNS settings and add a second upstream."),
                             metric="%", value=100 * f / n, threshold=5))
    d = ag.get("drift")
    if d and d["items"]:
        word = {"rewrites": ("rewrite", "rewrites"), "lists": (L("filterlijst", "filter list"), L("filterlijsten", "filter lists")),
                "upstreams": ("upstream", "upstreams")}
        parts = [f"{x['n']} {word[x['what']][x['n'] != 1]} {L('ontbreekt op' if x['n'] == 1 else 'ontbreken op', 'missing on')} {x['missing_on']}"
                 for x in d["items"] if x["missing_on"]]
        if any(x["what"] == "rules" for x in d["items"]):
            parts.append(L("het aantal eigen regels verschilt", "the number of custom rules differs"))
        out.append(issue("adguard:drift", "info", "config", "site", "dns",
                         L(f"Je {P}-servers lopen uiteen" if P in ("AdGuard", "Pi-hole") else "Je DNS-filters lopen uiteen",
                           f"Your {P} servers have drifted apart" if P in ("AdGuard", "Pi-hole") else "Your DNS filters have drifted apart"),
                         "; ".join(parts) + ".",
                         L("Valt de ene uit, dan gedraagt de andere zich anders: een naam die alleen op de ene een rewrite heeft, werkt dan niet "
                           "meer. Zet ze gelijk, of laat ze bijhouden met " + ("nebula-sync." if all(x.get("kind") == "pihole" for x in d["items"]) else "adguardhome-sync." if all(x.get("kind") == "adguard" for x in d["items"]) else "adguardhome-sync of nebula-sync."),
                           "If one fails, the other behaves differently: a name with a rewrite on only one of them stops working. "
                           "Make them the same, or keep them in sync with " + ("nebula-sync." if all(x.get("kind") == "pihole" for x in d["items"]) else "adguardhome-sync." if all(x.get("kind") == "adguard" for x in d["items"]) else "adguardhome-sync or nebula-sync."))))

    # 2. wat belt je IoT naar huis?
    for mac, doms in new_domains(db, ts).items():
        who = _who(clients, db, mac)
        names = ", ".join(d["domain"] for d in doms[:3]) + ("…" if len(doms) > 3 else "")
        out.append(issue(f"dns_new:{mac}", "info", "security", "client", mac,
                         L(f"{who} zoekt nieuwe domeinen op", f"{who} looks up new domains"),
                         L(f"Na een week leren zocht dit apparaat het afgelopen etmaal {len(doms)} domein{'en' if len(doms) != 1 else ''} op "
                           f"dat het nog nooit gebruikte: {names}.",
                           f"After a week of learning, this device looked up {len(doms)} domain{'s' if len(doms) != 1 else ''} it never used "
                           f"before in the past day: {names}."),
                         L("Vaak is dit een firmware-update of een nieuwe dienst van de fabrikant. Ken je het domein niet en past het niet "
                           f"bij het merk, zoek het dan op of blokkeer het in {P}.",
                           "Often this is a firmware update or a new service from the vendor. If you don't know the domain and it doesn't "
                           f"match the brand, look it up or block it in {P}."), client_mac=mac, last_ts=doms[0]["first"]))

    # 4. malware en phishing tegengehouden
    for t in threats(db, ts):
        mac = t["mac"]
        who = _who(clients, db, mac) if mac else t["ip"]
        both = t["ips"] > 0
        out.append(issue(f"dns_threat:{mac or t['ip']}", "critical" if both else "warning", "security", "client" if mac else "site",
                         mac or t["ip"],
                         L(f"{P[0].upper() + P[1:]} hield malware of phishing tegen voor {who}", f"{P[0].upper() + P[1:]} blocked malware or phishing for {who}"),
                         L(f"{who}{' (' + t['ip'] + ')' if mac and t.get('ip') else ''}: {t['n']} keer in het afgelopen etmaal, via {', '.join(t['lists'])}: {', '.join(t['domains'][:3])}"
                           f"{'…' if len(t['domains']) > 3 else ''}." + (f" Ook de IPS greep {t['ips']} keer in bij dit apparaat." if both else ""),
                           f"{who}{' (' + t['ip'] + ')' if mac and t.get('ip') else ''}: {t['n']} times in the past day, via {', '.join(t['lists'])}: {', '.join(t['domains'][:3])}"
                           f"{'…' if len(t['domains']) > 3 else ''}." + (f" The IPS also stepped in {t['ips']} times for this device." if both else "")),
                         L("Eén keer is meestal een foute link of advertentie. Komt het vaker terug, of grijpt ook de IPS in, controleer het apparaat "
                           "dan op malware en kijk welke app of extensie dit opvraagt.",
                           "Once is usually a bad link or ad. If it keeps coming back, or the IPS steps in too, check the device for malware "
                           "and see which app or extension makes these requests."), client_mac=mac, last_ts=t["last"]))

    # 5. apparaten die AdGuard overslaan
    rows, _ = bypass(snap, db, ts, ag)
    for b in rows:
        out.append(issue(f"dns_bypass:{b['mac']}", "info", "security", "client", b["mac"],
                         L(f"{b['name']} vraagt {P} nooit iets", f"{b['name']} never asks {P} anything"),
                         L(f"Dit apparaat maakte het afgelopen etmaal {b['flows']} verbindingen met internet, maar zocht niets op bij {P}.",
                           f"This device made {b['flows']} internet connections in the past day, but looked up nothing at {P}."),
                         L("Waarschijnlijk heeft het een eigen DNS-server ingesteld (een NAT-regel die DNS omleidt vangt dat op, maar dan ziet "
                           f"{P} alleen je gateway als afzender) of gebruikt het DNS-over-HTTPS. Zet in het apparaat of de browser "
                           "'Beveiligde DNS' uit, of blokkeer de bekende DoH-servers in je firewall.",
                           f"It probably has its own DNS server set (a NAT rule that redirects DNS catches that, but then {P} only sees "
                           "your gateway as the sender) or it uses DNS-over-HTTPS. Turn off 'Secure DNS' in the device or browser, or block "
                           "the known DoH servers in your firewall."), client_mac=b["mac"], last_ts=b["last"]))


# ------------------------------------------------------------------ voor de pagina's
def view(ag_obj: AdGuard, snap: dict, db, ts: int) -> dict:
    ag = ag_obj.for_rules()
    clients = {c["mac"]: c for c in snap.get("clients") or []}
    segs = ((snap.get("config") or {}).get("segments") or {}).get("segments")
    rows, why = bypass(snap, db, ts, ag)
    nd = new_domains(db, ts)
    cfg = ag_obj.cfg
    stats = {s["url"]: s.get("stats") for s in ag_obj.status.values()}
    watched = sum(1 for c in clients.values() if ag_obj.watched(c, segs))
    return {
        "active": ag["active"], "mock": bool(ag_obj.mock), "since": ag["since"], "personal": cfg["personal"],
        "product": ag["product"], "kinds": ag["kinds"],
        # Pi-hole bewaart geen antwoorden: namen bij verbindingen kan alleen met een AdGuard erbij
        "names": "adguard" in ag["kinds"] or bool(ag_obj.mock),
        "instances": [{"name": a.name, "url": a.url, "kind": a.kind, **{k: v for k, v in ag_obj.status.get(a.url, {}).items() if k not in ("name", "url", "kind")},
                       "stats": stats.get(a.url)} for a in ag_obj.apis()],
        "servers": ag["servers"], "drift": ag["drift"], "totals": {k: v for k, v in coverage(db, ts).items() if k != "per"},
        "threats": [{**t, "name": _who(clients, db, t["mac"]) if t["mac"] else t["ip"]} for t in threats(db, ts)],
        "bypass": rows, "bypass_why": why,
        "own_dns": sorted(({"mac": m, **{k: v for k, v in o.items() if k not in ("servers", "flow_name")},
                            "name": (lambda n: o["flow_name"] if n == m and o["flow_name"] else n)(_who(clients, db, m)),
                            "servers": sorted(o["servers"])[:3]} for m, o in own_dns(snap, db, ts, ag).items()),
                          key=lambda x: -(x["redirected"] + x["blocked"] + x["dot"])),
        "new_domains": [{"mac": m, "name": _who(clients, db, m), "domains": d} for m, d in nd.items()],
        "watched": watched, "not_watched": len(clients) - watched,
    }


def client_view(ag_obj: AdGuard, snap: dict, db, mac: str, ts: int) -> dict:
    c = next((x for x in snap.get("clients") or [] if x["mac"] == mac), {"mac": mac})
    segs = ((snap.get("config") or {}).get("segments") or {}).get("segments")
    hourly = {r["hour"]: (r["q"], r["blocked"]) for r in db.q("SELECT hour, q, blocked FROM dns_hourly WHERE mac=? AND hour >= ?",
                                                               (mac, ts - DAY - ts % 3600))}
    watched = ag_obj.watched(c, segs)
    learned = db.q("SELECT MIN(first) f FROM dns_domains WHERE mac=?", (mac,))
    start = learned[0]["f"] if learned and learned[0]["f"] else None
    doms = [dict(r) for r in db.q("SELECT domain, first, last, n, blocked FROM dns_domains WHERE mac=? ORDER BY n DESC LIMIT 40", (mac,))] if watched else []
    for d in doms:
        d["new"] = bool(start and start <= ts - LEARN_DAYS * DAY and d["first"] >= ts - DAY)
    return {"active": ag_obj.active, "product": product(kind_of(i) for i in ag_obj.instances()) if ag_obj.active else None,
            "watched": watched, "auto": device_class(c, segs), "override": ag_obj.cfg["watch"].get(mac),
            "queries": sum(q for q, _ in hourly.values()), "blocked": sum(b for _, b in hourly.values()),
            "learning_until": start + LEARN_DAYS * DAY if start and start > ts - LEARN_DAYS * DAY else None, "domains": doms}
