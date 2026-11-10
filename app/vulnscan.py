"""Kwetsbaarheidscheck: wat er bekend lek is en, als je dat wilt, wat er open staat. Drie lagen, van voorzichtig naar actief.

1. Passief: de lijst van CISA met lekken die echt misbruikt worden (KEV), naast de adviezen van Ubiquiti en je firmware.
2. Buitenkant (aanzetten): Shodan InternetDB over je publieke adres. Dat adres gaat dan naar Shodan.
3. Poortcheck (start je zelf): ongeveer 30 beheerpoorten, traag, alleen op apparaten uit je eigen controller. Slimme apparaten
   en gasten slaan we over: die kunnen vastlopen en een lijst CVE's erbij helpt je niet.

Er is bewust geen veld om zelf een doel in te vullen. 'Niets gevonden' is pas iets waard als je weet wat er bekeken is,
daarom geeft de pagina altijd de dekking mee.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import sys
import time
from pathlib import Path

import httpx

from . import advisories as adv
from .i18n import L
from .segments import client_segment, smart_reason

log = logging.getLogger("sonar.vulnscan")
KEV_URLS = ("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json")
INTERNETDB = "https://internetdb.shodan.io/"
DAY = 86400
MAX_HOSTS = 64
DELAY, TIMEOUT = 1.0, 1.5
STALE_DAYS = 14   # zo lang mag Shodan een poort tonen van iets wat uitstaat voor het een bevinding wordt
_RFC1918 = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]

# plain = onversleuteld of vaak zonder inlog en telt als bevinding; admin = beheer of delen: normaal, maar goed om te weten.
PORTS: dict[int, tuple[str, str]] = {
    21: ("FTP", "plain"), 22: ("SSH", "admin"), 23: ("Telnet", "plain"), 80: ("HTTP", "admin"), 139: ("NetBIOS", "admin"),
    443: ("HTTPS", "admin"), 445: ("SMB", "admin"), 554: ("RTSP", "plain"), 1883: ("MQTT", "plain"), 2049: ("NFS", "plain"),
    2375: ("Docker API", "plain"), 3306: ("MySQL", "plain"), 3389: ("Remote Desktop", "admin"), 5000: ("Synology / web", "admin"),
    5001: ("Synology / web", "admin"), 5432: ("PostgreSQL", "plain"), 5900: ("VNC", "plain"), 6379: ("Redis", "plain"),
    8006: ("Proxmox", "admin"), 8080: ("Web", "admin"), 8123: ("Home Assistant", "admin"), 8443: ("UniFi / web", "admin"),
    8883: ("MQTT TLS", "admin"), 9000: ("Web", "admin"), 9090: ("Cockpit / web", "admin"), 9443: ("Portainer / web", "admin"),
    10000: ("Webmin", "admin"), 11211: ("Memcached", "plain"), 27017: ("MongoDB", "plain"),
}

DEMO_KEV = {c: {"vendor": v, "product": p, "name": f"{p} (demo)", "added": "2026-06-01", "ransomware": False} for c, v, p in (
    ("CVE-2026-00000", "Ubiquiti", "UniFi Access Points"), ("CVE-2026-00001", "Ubiquiti", "UniFi OS"),
    ("CVE-2026-00002", "Demo", "Demo webserver"))}
_DEMO_OPEN = ([22, 443, 8006], [445, 5000, 5001], [22, 1883, 8123], [23, 80])


# ------------------------------------------------------------------ bronnen
def parse_kev(data: dict) -> dict:
    return {v["cveID"]: {"vendor": v.get("vendorProject") or "", "product": v.get("product") or "", "name": v.get("vulnerabilityName") or "",
                         "added": v.get("dateAdded") or "", "ransomware": v.get("knownRansomwareCampaignUse") == "Known"}
            for v in data.get("vulnerabilities") or [] if v.get("cveID")}


async def fetch_kev(http) -> dict:
    last: Exception | None = None
    for url in KEV_URLS:   # de site van CISA weigert soms verkeer; GitHub is de officiële kopie
        try:
            r = await http.get(url, headers={"User-Agent": "UniFi-Sonar"}, timeout=30)
            r.raise_for_status()
            return parse_kev(r.json())
        except (httpx.HTTPError, ValueError) as e:
            last = e
    raise last or RuntimeError("KEV")


def public_address(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


async def fetch_outside(http, ip: str, ts: int) -> dict:
    if not public_address(ip):
        return {"state": "nat", "ip": ip, "fetched": ts}
    r = await http.get(INTERNETDB + ip, headers={"User-Agent": "UniFi-Sonar"}, timeout=15)
    if r.status_code == 404:    # Shodan kent dit adres niet: dat zegt niets over of het veilig is
        return {"state": "nodata", "ip": ip, "fetched": ts}
    r.raise_for_status()
    d = r.json()
    return {"state": "ok", "ip": ip, "ports": sorted(d.get("ports") or []), "vulns": sorted(d.get("vulns") or []),
            "tags": d.get("tags") or [], "fetched": ts}


def _ranges(spec) -> list[tuple[int, int]]:
    """'443', '80,443' of '1000-1010' zoals de controller ze geeft."""
    out = []
    for part in str(spec or "").replace(" ", "").split(","):
        a, _, b = part.partition("-")
        try:
            lo, hi = int(a), int(b or a)
        except ValueError:
            continue
        if 0 < lo <= hi <= 65535:
            out.append((lo, hi))
    return out


def _covers(spec, port: int) -> bool:
    return any(lo <= port <= hi for lo, hi in _ranges(spec))


def explain_outside(ports: list[int], cfg: dict | None, hosts: list[dict], first_seen: dict, accepted: set[str], now: int) -> list[dict]:
    """Elke poort die Shodan ziet, naast wat je controller zegt dat open hoort te staan.

    expected   = een actieve forward, UPnP-koppeling of VPN-server gebruikt deze poort
    stale      = alleen iets wat uitstaat gebruikt hem: waarschijnlijk zijn de gegevens van Shodan ouder
    lingering  = idem, maar Shodan ziet hem al langer dan STALE_DAYS: nagaan
    unexplained = je controller weet er niets van
    unknown    = Sonar kan je forwards niet lezen, dus ook niets verklaren
    """
    fw = (cfg or {}).get("forwards")
    vpn = (cfg or {}).get("vpn") or []
    open_by_ip = {h["ip"]: h["open"] for h in hosts or []}
    rows = []
    for p in ports:
        on: list[dict] = []
        off: list[dict] = []
        for f in fw or []:
            if _covers(f.get("port"), p):
                fr, er = _ranges(f.get("fwd_port")), _ranges(f.get("port"))
                to_port = fr[0][0] + (p - next(lo for lo, hi in er if lo <= p <= hi)) if fr and er else p   # reeks op reeks: zelfde afstand
                also = [{"port": o, "name": PORTS.get(o, ("?", ""))[0]} for o in open_by_ip.get(f.get("fwd_ip"), []) if o != to_port]
                (on if f.get("enabled") else off).append({"kind": "upnp" if f.get("upnp") else "forward", "name": f.get("name") or "",
                                                          "to": f"{f['fwd_ip']}:{to_port}" if f.get("fwd_ip") else "", "also": also})
        for v in vpn:
            if v.get("port") == p:
                (on if v.get("enabled") else off).append({"kind": "vpn", "name": v.get("name") or v.get("type") or "VPN", "to": "", "also": []})
        since = int(first_seen.get(str(p)) or now)
        state = "expected" if on else "unknown" if fw is None else \
                ("stale" if now - since < STALE_DAYS * DAY else "lingering") if off else "unexplained"
        rows.append({"port": p, "name": PORTS.get(p, ("", ""))[0], "state": state, "via": on or off, "since": since,
                     "accepted": f"wan:{p}" in accepted})
    return rows


# ------------------------------------------------------------------ wat we mogen controleren
def _rfc1918(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and any(a in n for n in _RFC1918)


def targets(clients: list[dict], seg: dict | None, limit: int = MAX_HOSTS) -> tuple[list[dict], dict]:
    """Alleen verbonden apparaten uit de controller, op een netwerk waarvan we weten wat het is."""
    segs = (seg or {}).get("segments") or []
    out: list[dict] = []
    skipped = {"iot": 0, "guest": 0, "unknown": 0, "offline": 0, "limit": 0}
    for c in clients:
        s = client_segment(c, segs)
        why = "offline" if not c.get("connected", True) or not _rfc1918(c.get("ip") or "") else \
              "guest" if c.get("guest") or (s and s["kind"] == "guest") else \
              "iot" if (s and s["kind"] == "iot") or smart_reason(c) else \
              "unknown" if not s else "limit" if len(out) >= limit else None
        if why:
            skipped[why] += 1
        else:
            out.append({"ip": c["ip"], "mac": c["mac"], "name": c.get("name") or c["ip"], "network": s["name"]})
    return out, skipped


def _why(port: int) -> str:
    return {
        21: L("Stuurt wachtwoorden onversleuteld.", "Sends passwords unencrypted."),
        23: L("Stuurt alles onversleuteld, ook het wachtwoord. Vervang door SSH.", "Sends everything unencrypted, including the password. Replace with SSH."),
        554: L("Videostream, vaak zonder of met een standaardwachtwoord.", "Video stream, often without a password or with a default one."),
        1883: L("MQTT zonder versleuteling. Controleer of de broker een wachtwoord eist.", "MQTT without encryption. Check that the broker requires a password."),
        2049: L("Bestandsdeling die vertrouwt op het IP-adres van de ander.", "File sharing that trusts the other side's IP address."),
        2375: L("Wie hierbij kan, heeft in feite root op de machine.", "Anyone who reaches this effectively has root on the machine."),
        5900: L("Schermovername, vaak met een zwak wachtwoord en onversleuteld.", "Screen sharing, often with a weak password and unencrypted."),
    }.get(port) or L("Database of cache: hoort niet voor het hele netwerk open te staan.", "Database or cache: should not be open to the whole network.") \
        if PORTS[port][1] == "plain" else ""


def _used_by(db, ip: str, port: int) -> list[str]:
    """Wie deze dienst de afgelopen tijd via de gateway gebruikte. Verkeer binnen hetzelfde netwerk ziet de gateway niet."""
    rows = db.q("SELECT DISTINCT client_name n FROM flows WHERE dir='local' AND remote_ip=? AND port=? AND action='allowed' LIMIT 5", (ip, port))
    return [r["n"] for r in rows if r["n"]]


def mark_exploited(matches: list[dict], kev: dict) -> list[dict]:
    return [{**m, "exploited": [c for c in m["cves"] if c in kev]} for m in matches]


def os_server_minimum(items: list[dict], kev: dict) -> dict | None:
    """De versie van UniFi OS Server die minstens nodig is tegen lekken die echt misbruikt worden. De API geeft die versie niet."""
    best = None
    for a in items:
        for s in a["summaries"]:
            hit = [c for c in s["cves"] if c in kev]
            for p, v in s["fixed"] if hit else []:
                if "unifi os server" in p.lower() and (not best or adv._ver(v) > adv._ver(best["version"])):
                    best = {"version": v, "advisory": a["id"], "url": a["url"], "cves": hit}
    return best


# ------------------------------------------------------------------ uitvoeren en bewaren
class VulnScan:
    def __init__(self, settings, db, mock) -> None:
        self.s, self.db, self.mock = settings, db, mock
        st = db.get_kv("vulnscan") or {}
        self.outside: dict | None = st.get("outside")
        self.ports: dict | None = st.get("ports")
        self.accepted: set[str] = set(st.get("accepted") or [])
        self.kev: dict = db.get_kv("kev") or {}
        self._kev_checked = self.kev.get("fetched") or 0
        self.running: dict | None = None
        self._task: asyncio.Task | None = None

    @property
    def options(self) -> dict:
        return {"outside": False, "nightly": False, **(self.s.vulnscan or {})}

    def _save(self) -> None:
        self.db.set_kv("vulnscan", {"outside": self.outside, "ports": self.ports, "accepted": sorted(self.accepted)})

    @property
    def kev_items(self) -> dict:
        return self.kev.get("items") or {}

    async def refresh_kev(self, ts: int) -> None:
        self._kev_checked = ts
        if self.mock:
            self.kev = {"items": DEMO_KEV, "fetched": ts, "error": None}
            return
        try:
            async with httpx.AsyncClient(follow_redirects=True) as http:
                self.kev = {"items": await fetch_kev(http), "fetched": ts, "error": None}
        except Exception as e:  # noqa: BLE001 – internet weg of feed veranderd: oude lijst houden
            log.info("KEV-lijst: %s", e)
            self.kev = {**self.kev, "error": str(e)[:200]}
        self.db.set_kv("kev", self.kev)

    async def refresh_outside(self, ip: str, ts: int) -> None:
        prev = (self.outside or {}).get("first_seen") or {}
        if self.mock:
            res = {"state": "ok", "ip": ip, "ports": [443, 8080, 8443], "vulns": ["CVE-2026-00002"], "tags": [], "fetched": ts}
        else:
            try:
                async with httpx.AsyncClient(follow_redirects=True) as http:
                    res = await fetch_outside(http, ip, ts)
            except Exception as e:  # noqa: BLE001 – Shodan niet bereikbaar: laatste antwoord houden en het zeggen
                log.info("InternetDB: %s", e)
                res = {**(self.outside or {"state": "error", "ip": ip}), "error": str(e)[:200], "fetched": ts}
                prev = {}   # niets nieuws gezien: de oude data blijft staan, inclusief wanneer elke poort verscheen
        # Shodan geeft geen datum, dus Sonar onthoudt zelf sinds wanneer een poort in de lijst staat.
        res["first_seen"] = {str(p): prev.get(str(p), ts) for p in res.get("ports") or []} if prev or "first_seen" not in res else res["first_seen"]
        self.outside = res
        self._save()

    async def tick(self, snap: dict, ts: int) -> None:
        if self.s.advisories is not False and (ts - self._kev_checked >= (3600 if self.kev.get("error") else DAY) or not self.kev):
            await self.refresh_kev(ts)
        if ts < time.time() - 120:   # de demo vult zich met metingen uit het verleden
            return
        ip = (snap.get("wan") or {}).get("wan_ip") or ""
        out = self.outside or {}
        if self.options["outside"] and ip and (ts - (out.get("fetched") or 0) >= DAY or out.get("ip") != ip):
            await self.refresh_outside(ip, ts)
        if self.options["nightly"] and 3 <= time.localtime(ts).tm_hour < 5 and ts - ((self.ports or {}).get("ran") or 0) >= 20 * 3600:
            self.start(snap)

    def start(self, snap: dict) -> bool:
        if self.running:
            return False
        self.running = {"done": 0, "total": 0, "started": int(time.time())}
        self._task = asyncio.create_task(self._run(snap.get("clients") or [], (snap.get("config") or {}).get("segments")))
        return True

    async def _run(self, clients: list[dict], seg: dict | None) -> None:
        started = int(time.time())
        tg, skipped = targets(clients, seg)
        error = None
        try:
            res = await (self._demo(tg) if self.mock else self._probe(tg))
        except Exception as e:  # noqa: BLE001 – vorige uitslag bewaren en de fout laten zien
            log.warning("Poortcheck: %s", e)
            res, error = None, str(e)[:200]
        if res is not None:
            hosts = [{**t, "open": sorted(res.get(t["ip"], {}).get("open") or []),
                      "answered": bool(res.get(t["ip"], {}).get("open") or res.get(t["ip"], {}).get("closed"))} for t in tg]
            self.ports = {"ran": started, "took": int(time.time()) - started, "hosts": hosts, "skipped": skipped, "error": None}
        else:
            self.ports = {**(self.ports or {"hosts": [], "skipped": skipped}), "error": error}
        self.running = None
        self._save()

    async def _demo(self, tg: list[dict]) -> dict:
        self.running["total"] = len(tg)
        for i in range(len(tg)):
            self.running["done"] = i + 1
            await asyncio.sleep(0.1)
        return {t["ip"]: {"open": _DEMO_OPEN[i] if i < len(_DEMO_OPEN) else [], "closed": 0 if i == len(_DEMO_OPEN) else 29}
                for i, t in enumerate(tg)}

    async def _probe(self, tg: list[dict]) -> dict:
        """Een eigen proces met een leeg milieu: daar zit geen API-sleutel in, ook niet als er iets misgaat."""
        job = {"targets": [t["ip"] for t in tg], "ports": sorted(PORTS), "delay": DELAY, "timeout": TIMEOUT}
        script = str(Path(__file__).with_name("portprobe.py"))
        proc = await asyncio.create_subprocess_exec(sys.executable, "-I", script, stdin=asyncio.subprocess.PIPE,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env={})
        result = None

        async def read() -> None:
            nonlocal result
            proc.stdin.write(json.dumps(job).encode())
            await proc.stdin.drain()
            proc.stdin.close()
            async for line in proc.stdout:
                msg = json.loads(line)
                if "result" in msg:
                    result = msg["result"]
                else:
                    self.running.update(msg)
            await proc.wait()

        try:
            await asyncio.wait_for(read(), len(tg) * len(PORTS) * (DELAY + TIMEOUT) + 60)
        finally:
            if proc.returncode is None:
                proc.kill()
        if result is None:
            raise RuntimeError(L("De poortcheck stopte zonder uitslag.", "The port check stopped without a result."))
        return result

    def accept(self, mac: str, port: int, accepted: bool) -> None:
        (self.accepted.add if accepted else self.accepted.discard)(f"{mac}:{port}")
        self._save()

    # -------------------------------------------------------------- uitkomst
    def _plain_open(self) -> list[tuple[dict, int]]:
        return [(h, p) for h in (self.ports or {}).get("hosts") or [] for p in h["open"]
                if PORTS.get(p, ("", ""))[1] == "plain" and f"{h['mac']}:{p}" not in self.accepted]

    def outside_ports(self, cfg: dict | None) -> list[dict]:
        out = self.outside or {}
        if not self.options["outside"] or out.get("state") != "ok":
            return []
        return explain_outside(out.get("ports") or [], cfg, (self.ports or {}).get("hosts") or [], out.get("first_seen") or {},
                               self.accepted, int(time.time()))

    def for_rules(self, cfg: dict | None = None) -> dict:
        vulns = (self.outside or {}).get("vulns") or [] if self.options["outside"] else []
        hot = [v for v in vulns if v in self.kev_items]
        rows = [r for r in self.outside_ports(cfg) if not r["accepted"]]
        bad = sum(r["state"] in ("unexplained", "lingering") for r in rows)
        return {"findings": len(self._plain_open()) + len(vulns) + bad, "exploited": len(hot),
                "stale": sum(r["state"] == "stale" for r in rows)}

    def view(self, snap: dict, sysinfo: dict, advisory_items: list[dict], advisories_on: bool) -> dict:
        kev = self.kev_items
        devices, clients = snap.get("devices") or [], snap.get("clients") or []
        inv = adv.inventory(devices, (sysinfo or {}).get("network_version"))
        items = advisory_items if advisories_on else []
        matches = mark_exploited(adv.match(items, inv), kev)
        exploited: dict[str, dict] = {}
        for m in matches:
            if m["exploited"]:
                e = exploited.setdefault(m["id"], {"id": m["id"], "title": m["title"], "url": m["url"], "fixed": m["fixed"], "cves": set(), "devices": {}})
                e["cves"].update(m["exploited"])
                e["devices"].update({d["name"]: d["version"] for d in m["devices"]})
        rows = [{**e, "cves": sorted(e["cves"]), "ransomware": any(kev[c]["ransomware"] for c in e["cves"]),
                 "devices": [{"name": n, "version": v} for n, v in e["devices"].items()]} for e in exploited.values()]

        out = self.outside if self.options["outside"] else None
        out_view = {**out, "vulns": [{"id": v, "exploited": v in kev, "name": (kev.get(v) or {}).get("name")} for v in out.get("vulns") or []],
                    "explained": self.outside_ports(snap.get("config")), "stale_days": STALE_DAYS} if out else None

        p = self.ports or {}
        hosts = [{**h, "open": [{"port": o, "name": PORTS.get(o, ("?", ""))[0], "cls": PORTS.get(o, ("", "admin"))[1], "why": _why(o) if o in PORTS else "",
                                 "accepted": f"{h['mac']}:{o}" in self.accepted, "used_by": _used_by(self.db, h["ip"], o)} for o in h["open"]]}
                 for h in p.get("hosts") or [] if h["open"]]
        hosts.sort(key=lambda h: (-sum(o["cls"] == "plain" and not o["accepted"] for o in h["open"]), h["name"].lower()))
        now_tg, now_skip = targets(clients, (snap.get("config") or {}).get("segments"))
        answered = sum(bool(h.get("answered")) for h in p.get("hosts") or [])
        tried = len(p.get("hosts") or [])
        checked_fw = sum(bool(x["version"]) for x in inv) if advisories_on and items else 0
        cover = self._coverage(inv, checked_fw, advisories_on, items, sysinfo, kev, out, p, answered, tried)
        rules = self.for_rules(snap.get("config"))
        return {"options": self.options, "mock": bool(self.mock), "running": self.running,
                "kev": {"fetched": self.kev.get("fetched"), "count": len(kev), "error": self.kev.get("error")},
                "summary": {"exploited": len(rows) + rules["exploited"], "findings": rules["findings"],
                            "checked": checked_fw + answered, "total": len(inv) + len(clients)},
                "exploited": rows, "outside": out_view, "hosts": hosts, "coverage": cover,
                "ports": {"ran": p.get("ran"), "took": p.get("took"), "error": p.get("error"), "skipped": p.get("skipped"), "answered": answered, "tried": tried},
                "plan": {"targets": len(now_tg), "skipped": now_skip, "ports": len(PORTS), "minutes": max(1, round(len(now_tg) * len(PORTS) * (DELAY + 0.3) / 60))}}

    def _coverage(self, inv, checked_fw, advisories_on, items, sysinfo, kev, out, p, answered, tried) -> list[dict]:
        cov = [{"id": "firmware", "state": "ok" if checked_fw else "off", "title": L("Firmware van UniFi-apparaten", "UniFi device firmware"),
                "text": L(f"{checked_fw} van {len(inv)} vergeleken met de adviezen van Ubiquiti en de KEV-lijst.", f"{checked_fw} of {len(inv)} compared with Ubiquiti's advisories and the KEV list.")
                if checked_fw else L("Niet vergeleken: de beveiligingsadviezen staan uit of zijn nog niet opgehaald.", "Not compared: security advisories are off or not fetched yet.")}]
        if (sysinfo or {}).get("hardware") == "UOSSERVER":
            need = os_server_minimum(items, kev)
            cov.append({"id": "os_server", "state": "manual", "title": "UniFi OS Server",
                        "text": L("UniFi geeft deze versie niet door via de API, dus Sonar kan hem niet vergelijken."
                                  + (f" Controleer zelf of je minstens {need['version']} draait (advies {need['advisory']}, wordt echt misbruikt)." if need else ""),
                                  "UniFi does not expose this version through the API, so Sonar cannot compare it."
                                  + (f" Check yourself that you run at least {need['version']} (advisory {need['advisory']}, exploited in the wild)." if need else "")),
                        "url": need["url"] if need else None})
        st = (out or {}).get("state")
        cov.append({"id": "outside", "state": {"ok": "ok", "nodata": "none", "nat": "none", "error": "none"}.get(st, "off"), "title": L("Je publieke adres", "Your public address"),
                    "text": {"ok": L("Bekeken met Shodan InternetDB. Die gegevens zijn tot een week oud en de CVE's zijn afgeleid uit versienummers, dus mogelijk niet echt van toepassing.",
                                     "Checked with Shodan InternetDB. The data is up to a week old and the CVEs are inferred from version numbers, so they may not really apply."),
                             "nodata": L("Shodan kent dit adres niet. Dat zegt niets over of het veilig is.", "Shodan doesn't know this address. That says nothing about whether it is safe."),
                             "nat": L("Je gateway heeft geen publiek adres (bijvoorbeeld CGNAT), dus er valt niets op te zoeken.", "Your gateway has no public address (CGNAT, for example), so there is nothing to look up."),
                             "error": L("Shodan was niet bereikbaar.", "Shodan could not be reached.")}.get(st, L("Staat uit. Als je dit aanzet, gaat je publieke adres naar Shodan.", "Switched off. If you turn it on, your public address is sent to Shodan."))})
        sk = p.get("skipped") or {}
        n_skip = (sk.get("iot") or 0) + (sk.get("guest") or 0) + (sk.get("unknown") or 0) + (sk.get("limit") or 0)
        cov.append({"id": "ports", "state": "off" if not p.get("ran") else "ok" if answered == tried and not n_skip else "partial", "title": L("Open poorten binnen je netwerk", "Open ports inside your network"),
                    "text": L(f"{answered} van {tried} apparaten gaven antwoord" + (f"; van {tried - answered} kwam niets terug (firewall of uit)" if tried - answered else "") + (f". {n_skip} overgeslagen (slimme apparaten, gasten of onbekend netwerk)." if n_skip else "."),
                              f"{answered} of {tried} devices answered" + (f"; nothing came back from {tried - answered} (firewall or off)" if tried - answered else "") + (f". {n_skip} skipped (smart devices, guests or unknown network)." if n_skip else "."))
                    if p.get("ran") else L("Nog niet gedaan. Je start dit zelf.", "Not done yet. You start this yourself.")})
        cov.append({"id": "software", "state": "none", "title": L("Software op je andere apparaten", "Software on your other devices"),
                    "text": L("Niet beoordeeld. Sonar ziet dat een dienst draait, niet welke versie. Werk je NAS, Proxmox en Home Assistant dus zelf bij.",
                              "Not assessed. Sonar sees that a service runs, not which version. So keep your NAS, Proxmox and Home Assistant up to date yourself.")})
        return cov
