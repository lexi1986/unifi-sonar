"""FastAPI-server: collector op de achtergrond + JSON-API + statisch dashboard."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import platform
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


if not os.environ.get("NO_DOTENV"):   # tests/verse installaties: .env overslaan
    load_dotenv(ROOT / ".env")

from . import VERSION  # noqa: E402
from . import notify as notify_mod  # noqa: E402
from . import ha_mqtt  # noqa: E402
from . import setup as setup_mod  # noqa: E402
from .collector import Collector  # noqa: E402
from .config import Settings, Thresholds  # noqa: E402
from .db import DB  # noqa: E402
from .rules import ips_ignored  # noqa: E402

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("unifi_sonar")
DATA_DIR = os.environ.get("DATA_DIR") or str(ROOT / "data")


class Runtime:
    """Houdt instellingen, database en collector bij; kan na de wizard opnieuw starten."""

    def __init__(self) -> None:
        self.settings = Settings.load(DATA_DIR)
        self.db: DB | None = None
        self.collector: Collector | None = None
        self.task: asyncio.Task | None = None

    async def start(self) -> None:
        s = self.settings
        if not s.configured:
            log.info("Nog niet ingesteld: open het dashboard om de setup-wizard te doorlopen")
            return
        self.db = DB(s.database)
        self.collector = Collector(s, self.db)
        await self.collector.seed_history()
        self.task = asyncio.create_task(self.collector.run())
        log.info("Gestart in modus %s", s.mode)

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.collector and self.collector.client:
            await self.collector.client.close()
        if self.collector:
            await self.collector.notifier.close()
            await self.collector.ha.stop()
        self.task = self.collector = None

    async def apply(self, settings: Settings) -> None:
        await self.stop()
        self.settings = settings
        await self.start()


rt = Runtime()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await rt.start()
    yield
    await rt.stop()


app = FastAPI(title="UniFi Sonar", lifespan=lifespan)


@app.middleware("http")
async def no_cache(request, call_next):
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-cache"   # na een update altijd de nieuwe frontend
    return resp


# ----------------------------------------------------------------------- toegang
LOCAL_SUFFIXES = (".local", ".lan", ".home", ".internal", ".home.arpa", ".localdomain", ".localhost")
HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")


def _hostname(host: str) -> str:
    host = (host or "").strip().lower()
    if host.startswith("["):
        return host[1:host.find("]")] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def env_hosts() -> set[str]:
    return {h.strip().lower() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()}


def host_allowed(host: str) -> bool:
    """Bescherming tegen DNS-rebinding: alleen IP-adressen, lokale namen en zelf opgegeven hostnamen."""
    h = _hostname(host).rstrip(".")
    if not h:
        return False
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        pass
    if h == "localhost" or "." not in h or h.endswith(LOCAL_SUFFIXES):
        return True
    return h in {x.lower() for x in rt.settings.allowed_hosts or []} | env_hosts()


@app.middleware("http")
async def guard(request: Request, call_next):
    host = request.headers.get("host", "")
    if not host_allowed(host):
        return PlainTextResponse(
            f"UniFi Sonar: onbekende hostnaam '{_hostname(host)}'.\n\nOpen het dashboard via het IP-adres en voeg deze "
            "naam toe onder Instellingen → Toegang, of zet ALLOWED_HOSTS in de service (systemctl edit unifi-sonar).", 421)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        # Acties alleen vanaf het dashboard zelf, niet vanaf een andere website in dezelfde browser.
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin and origin != "null" and urlsplit(origin).netloc.lower() != host.lower()):
            return JSONResponse({"detail": "Verzoek van een andere website geweigerd."}, 403)
    return await call_next(request)


def _need() -> tuple[Collector, DB]:
    if not rt.collector or not rt.db:
        raise HTTPException(409, "setup_required")
    return rt.collector, rt.db


def _bucket(hours: float) -> int:
    return max(rt.settings.poll_seconds, int(hours * 3600 / 240) // 60 * 60 or 60)


@app.get("/api/status")
def status():
    s = rt.settings
    if not s.configured or not rt.collector:
        return {"setup_required": True, "mode": s.mode, "now": int(time.time())}
    c = rt.collector
    return {"setup_required": False, "mode": s.mode, "source": (c.latest or {}).get("source"),
            "last_ok": c.last_ok, "last_error": c.last_error,
            "poll_seconds": s.poll_seconds, "now": int(time.time()),
            "thresholds": vars(s.thresholds)}


# ----------------------------------------------------------------------- setup-wizard
class SetupRequest(BaseModel):
    address: str = Field(default="", max_length=300)
    api_key: str = Field(default="", max_length=200)
    username: str = Field(default="", max_length=200)
    password: str = Field(default="", max_length=200)
    site: str = Field(default="default", max_length=100)
    verify_tls: bool = False
    current_api_key: str = Field(default="", max_length=200)   # bevestiging bij opnieuw instellen


async def _authorized(req: SetupRequest) -> None:
    """Is er al een live koppeling, dan mag alleen wie de huidige sleutel kent die wijzigen."""
    s = rt.settings
    if not s.configured or s.mode != "live":
        return
    secrets = {x for x in (s.api_key, s.password) if x}
    if {req.api_key, req.current_api_key, req.password} & secrets:
        return
    await asyncio.sleep(1.5)   # raden ontmoedigen
    raise HTTPException(403, "Vul ter bevestiging de huidige API-key (of het huidige wachtwoord) in.")


@app.get("/api/setup")
def setup_info():
    s = rt.settings
    return {"configured": s.configured, "mode": s.mode, "controller_url": s.controller_url, "site": s.site,
            "verify_tls": s.verify_tls, "has_api_key": bool(s.api_key), "username": s.username,
            "needs_confirmation": s.configured and s.mode == "live"}


@app.post("/api/setup/test")
async def setup_test(req: SetupRequest):
    await _authorized(req)
    return await setup_mod.test_connection(req.address, req.api_key, req.username, req.password,
                                           req.site, req.verify_tls)


@app.post("/api/setup/save")
async def setup_save(req: SetupRequest):
    await _authorized(req)
    result = await setup_mod.test_connection(req.address, req.api_key, req.username, req.password,
                                             req.site, req.verify_tls)
    if not result["ok"]:
        raise HTTPException(400, result.get("error") or "Verbindingstest mislukt")
    s = Settings.load(DATA_DIR)
    s.mode, s.controller_url, s.site, s.verify_tls = "live", result["url"], req.site or "default", req.verify_tls
    s.api_key, s.username, s.password = req.api_key, req.username, req.password
    s.save()
    await rt.apply(s)
    return {"ok": True}


@app.post("/api/setup/demo")
async def setup_demo(req: SetupRequest):
    await _authorized(req)
    s = Settings.load(DATA_DIR)
    s.mode = "mock"
    s.save()
    await rt.apply(s)
    return {"ok": True}


# ----------------------------------------------------------------------- toegang (instellingen)
class AccessRequest(BaseModel):
    allowed_hosts: list[str] = Field(default_factory=list, max_length=20)


@app.get("/api/access")
def access_info(request: Request):
    return {"allowed_hosts": rt.settings.allowed_hosts or [], "env_hosts": sorted(env_hosts()),
            "current_host": _hostname(request.headers.get("host", ""))}


@app.post("/api/access")
def access_save(req: AccessRequest):
    hosts = []
    for h in req.allowed_hosts:
        h = _hostname(h.strip()).rstrip(".")
        if not h:
            continue
        if not HOSTNAME_RE.match(h):
            raise HTTPException(400, f"Geen geldige hostnaam: {h}")
        if h not in hosts:
            hosts.append(h)
    s = Settings.load(DATA_DIR)
    s.allowed_hosts = rt.settings.allowed_hosts = hosts
    s.save()
    return {"ok": True, "allowed_hosts": hosts}


# ----------------------------------------------------------------------- meldingen
class ChannelIn(BaseModel):
    id: str = Field(default="", max_length=20)
    kind: Literal["homeassistant", "ntfy", "discord", "slack", "webhook"] = "webhook"
    name: str = Field(default="", max_length=60)
    url: str = Field(default="", max_length=600)       # leeg = bestaande behouden
    token: str | None = Field(default=None, max_length=300)   # None = bestaande behouden
    min_severity: Literal["critical", "warning", "info"] = "warning"
    resolved: bool = True
    enabled: bool = True


class MqttSave(BaseModel):
    enabled: bool = False
    host: str = Field(default="", max_length=200)
    port: int = Field(default=1883, ge=1, le=65535)
    username: str = Field(default="", max_length=120)
    password: str | None = Field(default=None, max_length=200)   # None of leeg = bewaarde wachtwoord houden
    prefix: str = Field(default="homeassistant", max_length=60)


def _mqtt_cfg(req: MqttSave) -> dict:
    old = ha_mqtt.config(rt.settings)
    host = req.host.strip()
    if req.enabled and not host:
        raise HTTPException(400, "Vul het adres van de MQTT-broker in.")
    if re.search(r"[\s/:]", host):
        raise HTTPException(400, "Alleen de naam of het IP-adres van de broker, zonder http:// of poort.")
    return {"enabled": req.enabled, "host": host, "port": req.port, "username": req.username.strip(),
            "password": req.password if req.password else old.get("password", ""),
            "prefix": req.prefix.strip().strip("/") or "homeassistant"}


@app.get("/api/mqtt")
def mqtt_info():
    cfg = ha_mqtt.config(rt.settings)
    status = rt.collector.ha.status if rt.collector else {}
    return {**{k: v for k, v in cfg.items() if k != "password"}, "has_password": bool(cfg.get("password")), "status": status}


@app.post("/api/mqtt/test")
async def mqtt_test(req: MqttSave):
    cfg = _mqtt_cfg(MqttSave(**{**req.model_dump(), "enabled": True}))
    err = await ha_mqtt.try_connect(cfg)
    return {"ok": err is None, "error": err}


@app.post("/api/mqtt/save")
async def mqtt_save(req: MqttSave):
    cfg = _mqtt_cfg(req)
    s = Settings.load(DATA_DIR)
    s.mqtt = cfg
    s.save()
    rt.settings.mqtt = cfg
    if rt.collector:
        await rt.collector.ha.stop()
        rt.collector.ha.start()
    return {"ok": True}


class NotifySave(BaseModel):
    channels: list[ChannelIn] = Field(default_factory=list, max_length=5)
    delay_min: int = Field(default=5, ge=0, le=120)
    digest_hour: int | None = Field(default=None, ge=0, le=23)
    base_url: str = Field(default="", max_length=300)


def _channel(c: ChannelIn, stored: dict[str, dict]) -> dict:
    old = stored.get(c.id, {})
    url = c.url.strip() or old.get("url", "")
    if url and not re.match(r"^https?://[^\s/]+", url):
        raise HTTPException(400, "Een webhook-adres begint met http:// of https://")
    token = old.get("token", "") if c.token is None else c.token.strip()
    return {"id": c.id if c.id in stored else notify_mod.new_id(), "kind": c.kind, "name": c.name.strip(), "url": url,
            "token": token, "min_severity": c.min_severity, "resolved": c.resolved, "enabled": c.enabled}


@app.get("/api/notify")
def notify_info():
    cfg = notify_mod.config(rt.settings)
    status = rt.collector.notifier.status if rt.collector else {}
    return {**{k: cfg[k] for k in ("delay_min", "digest_hour", "base_url")},
            "channels": [{**{k: v for k, v in c.items() if k not in ("url", "token")},
                          "url_masked": notify_mod.mask(c.get("url", "")), "has_token": bool(c.get("token")),
                          "status": status.get(c["id"])} for c in cfg["channels"]]}


@app.post("/api/notify/save")
def notify_save(req: NotifySave):
    stored = {c["id"]: c for c in notify_mod.config(rt.settings)["channels"]}
    channels = [_channel(c, stored) for c in req.channels]
    if any(not c["url"] for c in channels):
        raise HTTPException(400, "Vul bij elk kanaal een webhook-adres in.")
    base = req.base_url.strip().rstrip("/")
    if base and not re.match(r"^https?://", base):
        raise HTTPException(400, "Het dashboard-adres begint met http:// of https://")
    s = Settings.load(DATA_DIR)
    s.notify = {"channels": channels, "delay_min": req.delay_min, "digest_hour": req.digest_hour, "base_url": base}
    s.save()
    rt.settings.notify = s.notify
    if rt.collector and rt.db:
        issues = (rt.collector.latest or {}).get("issues", [])
        for c in channels:
            if c["id"] not in stored:
                rt.collector.notifier.baseline(c["id"], issues)   # wat nu al openstaat niet alsnog sturen
        for cid in set(stored) - {c["id"] for c in channels}:
            rt.db.drop_notified(cid)
    return {"ok": True}


class NotifyTest(BaseModel):
    channel: ChannelIn
    base_url: str = Field(default="", max_length=300)


@app.post("/api/notify/test")
async def notify_test(req: NotifyTest):
    collector, db = _need()
    stored = {c["id"]: c for c in notify_mod.config(rt.settings)["channels"]}
    ch = _channel(req.channel, stored)
    if not ch["url"]:
        raise HTTPException(400, "Vul een webhook-adres in.")
    msg = collector.notifier.test_msg()
    if req.base_url:
        msg["url"] = req.base_url.rstrip("/") + "/#/issues"
    try:
        await collector.notifier.send(ch, msg)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Versturen mislukt: {e}") from e
    return {"ok": True}


# ----------------------------------------------------------------------- probleemoplossing
def _git_version() -> str:
    head = ROOT / ".git" / "HEAD"
    try:
        ref = head.read_text().strip()
        if ref.startswith("ref:"):
            p = ROOT / ".git" / ref[5:]
            sha = p.read_text().strip() if p.exists() else next(
                (ln.split()[0] for ln in (ROOT / ".git" / "packed-refs").read_text().splitlines() if ln.endswith(ref[5:])), "")
        else:
            sha = ref
        return sha[:7] or "?"
    except OSError:
        return "lokaal"


def scrub(text: str) -> str:
    """Haal adressen, namen en MAC's uit een tekst, zodat hij veilig te delen is."""
    text = re.sub(r"https?://[^\s'\"<>]+", "<url>", str(text))
    text = re.sub(r"\b([0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", "<mac>", text, flags=re.I)
    text = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}\b", "<ip>", text)
    host = urlsplit(rt.settings.controller_url).hostname if rt.settings.controller_url else None
    if host:
        text = text.replace(host, "<controller>")
    return text


@app.get("/api/debug")
def debug_info():
    s, c = rt.settings, rt.collector
    lines = [f"UniFi Sonar {VERSION} ({_git_version()}) · Python {platform.python_version()} · {platform.system()} {platform.machine()}"]
    if not c:
        lines.append(f"Modus: {s.mode or 'nog niet ingesteld'}")
        return {"text": "\n".join(lines)}
    snap = c.latest or {}
    port = urlsplit(s.controller_url).port if s.controller_url else None
    lines.append(f"Modus: {s.mode} · bron: {snap.get('source') or '?'} · elke {s.poll_seconds} s · bewaren {s.retention_days} d")
    if s.mode == "live":
        host = urlsplit(s.controller_url).hostname or ""
        kind = "IP-adres" if re.match(r"^[\d.]+$|:", host) else "hostnaam"
        lines.append(f"Controller: {kind}, poort {port or 443}, certificaat controleren: {'ja' if s.verify_tls else 'nee'}")
    si = c.sysinfo or {}
    if si.get("network_version"):
        lines.append(f"UniFi Network: {si['network_version']}" + (f" (build {si['build']})" if si.get("build") else ""))
    devs = snap.get("devices", [])
    by_type: dict[str, list[str]] = {}
    for d in devs:
        by_type.setdefault(d["type"], []).append(d["model"] or "?")
    lines.append("Apparaten: " + (" · ".join(f"{len(v)} {k} ({', '.join(sorted(set(v)))})" for k, v in sorted(by_type.items())) or "geen"))
    states = {d["state"] for d in devs if d["state"] != "online"}
    if states:
        lines.append("Niet online: " + ", ".join(sorted(states)))
    cl = snap.get("clients", [])
    lines.append(f"Clients: {sum(not x['wired'] for x in cl)} wifi · {sum(x['wired'] for x in cl)} bedraad")
    opt = {"IPS": c.optional.get("ips", "nog niet geprobeerd" if c.ips_available is None else None),
           "instellingen": c.optional.get("config", None if c.config else "nog niet geprobeerd")}
    lines.append("Extra gegevens: " + " · ".join(f"{k} {'ok' if v is None else scrub(v)[:80]}" for k, v in opt.items()))
    errs = {k: scrub(v)[:160] for k, v in (getattr(c.client, "errors", {}) or {}).items()} if c.client else {}
    if c.last_error:
        lines.append(f"Laatste fout: {scrub(c.last_error)[:200]}")
    for k, v in errs.items():
        lines.append(f"Fout bron {k}: {v}")
    if c.last_ok:
        lines.append(f"Laatste meting: {int(time.time() - c.last_ok)} s geleden")
    iss = [i for i in snap.get("issues", []) if not i.get("group")]
    kinds: dict[str, int] = {}
    for i in iss:
        kinds[i["key"].split(":")[0]] = kinds.get(i["key"].split(":")[0], 0) + 1
    h = snap.get("health") or {}
    lines.append(f"Meldingen: {len(iss)} (score {h.get('score', '?')}) · " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))
    default = vars(Thresholds())
    changed = [f"{k}={v:g}" for k, v in vars(s.thresholds).items() if v != default[k]]
    lines.append("Aangepaste drempels: " + (", ".join(changed) if changed else "geen"))
    ncfg = notify_mod.config(s)
    if ncfg["channels"]:
        st = c.notifier.status
        lines.append("Meldingen versturen: " + ", ".join(
            f"{ch['kind']} ({'fout: ' + scrub(st[ch['id']]['error'])[:60] if st.get(ch['id'], {}).get('error') else 'ok'})"
            for ch in ncfg["channels"]))
    try:
        size = Path(s.database).stat().st_size / 1e6
        oldest = rt.db.q("SELECT MIN(ts) t FROM wan_samples")[0]["t"]
        lines.append(f"Database: {size:.0f} MB, historie van {round((time.time() - oldest) / 86400, 1) if oldest else 0} dagen")
    except (OSError, TypeError):
        pass
    return {"text": "\n".join(lines)}


# ----------------------------------------------------------------------- internet
@app.get("/api/usage")
def usage():
    """Datagebruik per dag (laatste 90 dagen) en per maand (laatste 24 maanden), met de lopende periodes apart."""
    collector, db = _need()
    now = time.localtime()
    day0 = int(time.mktime(now[:3] + (0, 0, 0, 0, 0, -1)))
    month0 = int(time.mktime((now.tm_year, now.tm_mon, 1, 0, 0, 0, 0, 0, -1)))
    prev0 = int(time.mktime((now.tm_year - (now.tm_mon == 1), (now.tm_mon - 2) % 12 + 1, 1, 0, 0, 0, 0, 0, -1)))
    days = db.usage("day", day0 - 89 * 86400)
    months = db.usage("month", month0 - 730 * 86400)
    pick = lambda rows, ts: next(({"rx": r["rx"], "tx": r["tx"]} for r in rows if r["ts"] == ts), None)  # noqa: E731
    full = [r for r in days if r["ts"] < day0][-30:]
    avg = {"rx": sum(r["rx"] for r in full) / len(full), "tx": sum(r["tx"] for r in full) / len(full)} if full else None
    return {"days": days, "months": months, "today": pick(days, day0), "this_month": pick(months, month0),
            "last_month": pick(months, prev0), "avg_day": avg, "day0": day0, "month0": month0,
            "since": db.q("SELECT MIN(ts) t FROM usage WHERE period='day'")[0]["t"],
            "error": collector.optional.get("usage")}


@app.get("/api/me")
def me(request: Request, ip: str | None = Query(None, max_length=45)):
    """Het apparaat waarmee je dit dashboard bekijkt, herkend aan het IP-adres van de browser."""
    collector, db = _need()
    addr = request.client.host if request.client else ""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd and addr in ("127.0.0.1", "::1"):   # achter een reverse proxy op dezelfde machine
        addr = fwd.split(",")[0].strip()
    if ip and collector.mock:   # alleen in de demo: een apparaat nadoen
        addr = ip
    snap = collector.latest or {}
    clients = snap.get("clients", [])
    c = next((x for x in clients if x.get("ip") == addr), None)
    if c is None and collector.mock and not ip:
        c = next((x for x in clients if x["name"] == "iPhone"), None)   # demo: doe alsof je op de iPhone kijkt
    if c is None:
        return {"found": False, "ip": addr}
    devs = {d["mac"]: d for d in snap.get("devices", [])}
    up = devs.get(c.get("ap_mac") or c.get("sw_mac") or "", {})
    lt = time.localtime()
    day0 = int(time.mktime(lt[:3] + (0, 0, 0, 0, 0, -1)))
    issues = [{"title": i["title"], "severity": i["severity"]} for i in snap.get("issues", [])
              if i.get("client_mac") == c["mac"] and not i.get("muted")]
    return {"found": True, "ip": addr, "demo": collector.mock is not None and addr != c.get("ip"),
            "client": {k: c.get(k) for k in ("mac", "name", "ip", "vendor", "wired", "ssid", "band", "channel", "proto",
                                              "signal", "satisfaction", "tx_rate_mbps", "rx_rate_mbps", "retry_pct",
                                              "assoc_ts", "uptime", "sw_port", "network")},
            "uplink": {"mac": up.get("mac"), "name": up.get("name"), "type": up.get("type")},
            "roams_today": db.client_roams_since(c["mac"], day0), "issues": issues}


@app.get("/api/internet")
async def internet(hours: float = Query(24, gt=0, le=24 * 31)):
    collector, db = _need()
    now = int(time.time())
    since, b = now - int(hours * 3600), _bucket(hours)
    await collector.sync_speedtests()
    series = [dict(r) for r in db.q(
        f"SELECT (ts/{b})*{b} t, AVG(rx_bps) rx, MAX(rx_bps) rx_max, AVG(tx_bps) tx, MAX(tx_bps) tx_max, AVG(latency_ms) lat "
        f"FROM wan_samples WHERE ts>=? GROUP BY t ORDER BY t", (since,))]
    return {"bucket": b, "series": series, "wan": (collector.latest or {}).get("wan"),
            "speedtests": db.speedtests(now - 90 * 86400), "speedtest": collector.speedtest,
            "available": collector.mock is not None or (collector.client and collector.client.source in ("legacy-key", "legacy-login"))}


@app.get("/api/live/wan")
async def live_wan():
    collector, db = _need()
    try:
        live = await collector.live_wan()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Live-meting niet beschikbaar: {e}") from e
    return {**live, "now": time.time(), "test": collector.speedtest}


@app.post("/api/speedtest")
async def speedtest_start():
    collector, db = _need()
    try:
        await collector.start_speedtest()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(409, str(e)) from e
    return {"ok": True}


# ----------------------------------------------------------------------- patronen
@app.get("/api/patterns/client/{mac}")
def patterns_client(mac: str, days: int = Query(7, ge=1, le=31)):
    collector, db = _need()
    since = int(time.time()) - days * 86400
    st = db.client_ap_stats(mac.lower(), since)
    total = sum(a["seconds"] for a in st["aps"]) or 1
    names = {d["mac"]: d["name"] for d in (collector.latest or {}).get("devices", [])}
    first = db.q("SELECT MIN(ts) t FROM wan_samples WHERE ts>=?", (since,))[0]["t"]   # sinds wanneer Sonar meet
    return {"days": days, "since": first, "switches": st["switches"], "presence": db.presence(mac.lower(), since),
            "aps": [{"ap_mac": a["ap_mac"], "name": names.get(a["ap_mac"], a["ap_mac"]), "seconds": a["seconds"],
                     "share": round(a["seconds"] / total, 3), "signal": a["signal"]} for a in st["aps"]]}


@app.get("/api/patterns/device/{mac}")
def patterns_device(mac: str, days: int = Query(7, ge=1, le=31)):
    collector, db = _need()
    since = int(time.time()) - days * 86400
    return {"days": days, "radios": db.radio_heatmap(mac.lower(), since)}


@app.get("/api/snapshot")
def snapshot():
    collector, db = _need()
    if not collector.latest:
        raise HTTPException(503, collector.last_error or "Nog geen data opgehaald")
    return collector.latest


@app.get("/api/issues")
def issues(state: str = Query("open", pattern="^(open|all)$")):
    collector, db = _need()
    return db.issues(open_only=state == "open", now=int(time.time()))


class MuteRequest(BaseModel):
    key: str = Field(min_length=1, max_length=300)
    days: float | None = Field(default=None, gt=0, le=3650)   # None = altijd


@app.post("/api/mute")
def mute(req: MuteRequest):
    collector, db = _need()
    now = int(time.time())
    known = {i["key"]: i for i in (collector.latest or {}).get("issues", [])}
    title = known.get(req.key, {}).get("title") or next((i["title"] for i in db.issues(False, 1000) if i["key"] == req.key), None)
    if title is None:
        raise HTTPException(404, "Onbekende melding")
    db.mute(req.key, now + int(req.days * 86400) if req.days else None, now, title)
    collector.apply_mutes()
    return {"ok": True}


@app.post("/api/clients/{mac}/approve")
def approve(mac: str):
    """'Ken ik': een nieuw apparaat goedkeuren. De melding verdwijnt meteen."""
    collector, db = _need()
    mac = mac.lower()
    if not db.approve_client(mac):
        raise HTTPException(404, "Onbekend apparaat")
    snap = collector.latest
    if snap:
        snap["issues"] = [i for i in snap["issues"] if i["key"] != f"new_device:{mac}"]
        db.sync_issues(snap["issues"], int(time.time()))
        collector.apply_mutes(snap)
    return {"ok": True}


@app.post("/api/clients/{mac}/reconnect")
async def reconnect(mac: str):
    """Laat een wifi-client opnieuw verbinden zodat hij zelf de beste AP kiest (UniFi kick-sta)."""
    collector, db = _need()
    c = next((x for x in (collector.latest or {}).get("clients", []) if x["mac"] == mac.lower()), None)
    if not c or c["wired"]:
        raise HTTPException(404, "Geen verbonden wifi-client met dit MAC-adres")
    if collector.mock:
        return {"ok": True, "demo": True}
    try:
        await collector.client.reconnect(c["mac"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"UniFi weigerde: {e}") from e
    return {"ok": True}


class PauseRequest(BaseModel):
    until: int | None = Field(default=None, gt=0)   # Unix-tijd; None = tot je zelf hervat


@app.get("/api/pauses")
def pauses():
    _, db = _need()
    return {"pauses": db.pauses(), "now": int(time.time())}


@app.post("/api/clients/{mac}/pause")
async def pause(mac: str, req: PauseRequest):
    """Internet pauzeren: het apparaat wordt in UniFi geblokkeerd (geen wifi/netwerk) tot 'until' of tot hervatten."""
    collector, db = _need()
    mac = mac.lower()
    now = int(time.time())
    if req.until is not None and req.until <= now:
        raise HTTPException(400, "Het eindtijdstip ligt in het verleden")
    c = next((x for x in (collector.latest or {}).get("clients", []) if x["mac"] == mac), None)
    name = c["name"] if c else next((p["name"] for p in db.pauses() if p["mac"] == mac), mac)
    try:
        await collector.set_blocked(mac, True)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"UniFi weigerde: {e}") from e
    db.set_pause(mac, req.until, now, name)
    until = time.strftime("%d-%m %H:%M", time.localtime(req.until)) if req.until else "je hervat"
    db.add_events([{"ts": now, "kind": "client_leave", "entity_type": "client", "entity_id": mac,
                    "message": f"{name}: internet gepauzeerd tot {until}"}])
    return {"ok": True, "demo": bool(collector.mock)}


@app.post("/api/clients/{mac}/resume")
async def resume(mac: str):
    collector, db = _need()
    mac = mac.lower()
    p = next((x for x in db.pauses() if x["mac"] == mac), None)
    try:
        await collector.set_blocked(mac, False)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"UniFi weigerde: {e}") from e
    db.clear_pause(mac)
    if p:
        db.add_events([{"ts": int(time.time()), "kind": "client_join", "entity_type": "client", "entity_id": mac,
                        "message": f"{p['name']}: pauze opgeheven"}])
    return {"ok": True}


class UnmuteRequest(BaseModel):
    key: str = Field(min_length=1, max_length=300)


# Bewust POST en geen DELETE: de UXG-IPS (regel 2101603 "GPL WEB_SERVER DELETE attempt")
# blokkeert elk HTTP DELETE-verzoek vanuit een ander netwerk (bv. de WireGuard-VPN).
@app.post("/api/unmute")
def unmute(req: UnmuteRequest):
    collector, db = _need()
    db.unmute(req.key)
    collector.apply_mutes()
    return {"ok": True}


@app.get("/api/muted")
def muted():
    collector, db = _need()
    return list(db.muted(int(time.time())).values())


@app.get("/api/events")
def events(hours: float = 24, limit: int = 300):
    collector, db = _need()
    return db.events(int(time.time() - hours * 3600), limit)


class IpsIgnore(BaseModel):
    ip: str | None = Field(default=None, max_length=64)
    sid: int | None = None
    label: str = Field(default="", max_length=200)


@app.post("/api/ips/ignore")
def ips_ignore(req: IpsIgnore):
    collector, db = _need()
    if req.ip is None and req.sid is None:
        raise HTTPException(400, "Kies een adres, een regel of allebei.")
    if req.ip:
        try:
            ipaddress.ip_address(req.ip)
        except ValueError as e:
            raise HTTPException(400, "Geen geldig IP-adres") from e
    db.add_ips_ignore(req.ip or None, req.sid, req.label, int(time.time()))
    return {"ok": True}


class IpsUnignore(BaseModel):
    id: int


@app.post("/api/ips/unignore")   # POST i.p.v. DELETE, zie /api/unmute
def ips_unignore(req: IpsUnignore):
    collector, db = _need()
    db.remove_ips_ignore(req.id)
    return {"ok": True}


def _exposure(collector, rows: list[dict]) -> dict | None:
    """Port forwards en UPnP-mappings, met hoe vaak de IPS er aanvallen op tegenhield."""
    from .rules import _ports
    cfg = collector.config
    if not cfg or cfg.get("forwards") is None:
        return None
    who = {c["ip"]: c["name"] for c in (collector.latest or {}).get("clients", []) if c.get("ip")}
    ext = [e for e in rows if not e["internal"]]
    out = []
    for f in cfg["forwards"]:
        ports, fports = _ports(f["port"]), _ports(f["fwd_port"]) or _ports(f["port"])
        hits = sum(1 for e in ext if e.get("dst_port") in ports or (e.get("dst_ip") == f["fwd_ip"] and e.get("dst_port") in fports))
        out.append({**f, "target_name": who.get(f["fwd_ip"]), "attacks": hits})
    out.sort(key=lambda f: (not f["enabled"], f["upnp"], -f["attacks"]))
    return {"upnp_enabled": cfg.get("upnp_enabled"), "forwards": out}


# ---------------------------------------------------------------- wereldkaart
def _flow_names(collector) -> dict:
    snap = collector.latest or {}
    return {c["mac"]: c["name"] for c in snap.get("clients", []) if c.get("name") and c["name"] != c["mac"]}


def _namer(collector):
    """Naam voor een eigen adres: apparaatnaam, anders het IP, en een publiek adres is je gateway (WAN)."""
    from .unifi_client import _is_local_ip, _name
    snap = collector.latest or {}
    by_ip = {c["ip"]: c["name"] for c in snap.get("clients", []) if c.get("ip") and c["name"] != c["mac"]}
    by_ip.update({d["ip"]: d["name"] for d in snap.get("devices", []) if d.get("ip")})

    def target(name, ip):
        name = _name(name, ip)
        if name and name != ip:
            return name
        if ip and ip in by_ip:
            return by_ip[ip]
        return ip if ip and _is_local_ip(ip) else "je gateway (WAN)"
    return target


def _blocked_details(collector, db, since: int) -> dict[str, list[dict]]:
    """Per land: wat er tegengehouden werd, gericht op welk apparaat en welke poort, vanaf hoeveel adressen."""
    target = _namer(collector)

    rows = [{"cc": f["cc"], "by": f["reason"] or "Geblokkeerd", "what": f["service"] or "Onbekend", "port": f["port"],
             "target": target(f["client_name"], f["client_ip"]), "src": f["remote_ip"], "ts": f["ts"]}
            for f in db.blocked_flows(since) if f["cc"]]
    rows += [{"cc": e["src_country"], "by": "IPS", "what": e.get("signature") or "IPS-regel", "port": e.get("dst_port"),
              "target": target(e.get("dst_name"), e.get("dst_ip")), "src": e.get("src_ip"), "ts": e["ts"]}
             for e in db.ips_events(since, "external") if e.get("src_country")]
    out: dict[str, dict[tuple, dict]] = {}
    for r in rows:
        k = (r["by"], r["what"], r["port"], r["target"])
        g = out.setdefault(r["cc"], {}).setdefault(k, {"by": r["by"], "what": r["what"], "port": r["port"],
                                                        "target": r["target"], "n": 0, "last": 0, "_src": set()})
        g["n"] += 1
        g["last"] = max(g["last"], r["ts"])
        if r["src"]:
            g["_src"].add(r["src"])
    result = {}
    for cc, groups in out.items():
        items = sorted(groups.values(), key=lambda g: (-g["n"], -g["last"]))[:5]
        for g in items:
            g["sources"] = len(g.pop("_src"))
        result[cc] = items
    return result


@app.get("/api/world")
def world(hours: float = Query(1, gt=0, le=48)):
    collector, db = _need()
    since = int(time.time() - hours * 3600)
    w = db.world(since)
    blocked: dict[str, int] = {}
    for e in db.ips_events(since, "external"):
        if e.get("src_country"):
            blocked[e["src_country"]] = blocked.get(e["src_country"], 0) + 1
    for cc, n in blocked.items():   # IPS-blokkades komen uit een eigen tabel; regioblokkades zitten al in de flows
        c = w["countries"].setdefault(cc, {"cc": cc, "out_n": 0, "in_n": 0, "blocked_n": 0, "bytes": 0, "up": 0,
                                           "down": 0, "domains": [], "clients": []})
        c["blocked_n"] = c.get("blocked_n", 0) + n
    names = _flow_names(collector)
    for c in w["clients"]:
        c["name"] = names.get(c["mac"], c["name"])
    w["totals"]["blocked_n"] += sum(blocked.values())
    for cc, items in _blocked_details(collector, db, since).items():
        if cc in w["countries"]:
            w["countries"][cc]["blocked"] = items
    w["totals"]["countries"] = sum(1 for c in w["countries"].values() if c["out_n"] or c["in_n"])
    return {"hours": hours, "home": (rt.settings.home_country or "NL").upper(), "available": collector.flows_available,
            "error": collector.optional.get("flows"), "countries": list(w["countries"].values()),
            "totals": w["totals"], "clients": w["clients"], "domains": w["domains"]}


@app.get("/api/world/connections")
def world_connections(hours: float = Query(1, gt=0, le=48), dir: str = Query("all", pattern="^(all|out|in|blocked)$"),
                      cc: str | None = Query(None, pattern="^[A-Za-z]{2}$"), q: str | None = Query(None, max_length=60),
                      sort: str = Query("last", pattern="^(last|bytes|count)$"), limit: int = Query(50, ge=1, le=500)):
    """Verbindingen samengevoegd per apparaat en bestemming; geblokkeerd bevat ook de IPS."""
    collector, db = _need()
    since = int(time.time() - hours * 3600)
    dirs = ("out", "in", "blocked") if dir == "all" else (dir,)
    cc = cc.upper() if cc else None
    q = (q or "").strip() or None
    rows, total = db.connections(since, dirs, cc, q, sort, limit)
    target, names = _namer(collector), _flow_names(collector)
    for r in rows:
        r["by"] = (r.pop("reason") or "Geblokkeerd") if r["dir"] == "blocked" else None
        r["client"] = names.get(r["client_mac"], r["client"]) if r["client_mac"] else r["client"]
        if r["dir"] in ("in", "blocked"):
            r["client"] = target(r["client"], r["client_ip"])
        r.pop("client_ip", None)
    if "blocked" in dirs:   # IPS-blokkades staan in een eigen tabel: op dezelfde manier samenvoegen
        groups: dict[tuple, dict] = {}
        for e in db.ips_events(since, "external"):
            if cc and e.get("src_country") != cc:
                continue
            g = groups.setdefault((e.get("src_country"), e.get("signature"), e.get("dst_port"), e.get("dst_ip")), {
                "dir": "blocked", "cc": e.get("src_country"), "client_mac": None,
                "client": target(e.get("dst_name"), e.get("dst_ip")), "dest": None, "port": e.get("dst_port"),
                "service": e.get("signature"), "by": "IPS", "n": 0, "up": 0, "down": 0, "bytes": 0,
                "first": e["ts"], "last": e["ts"], "remotes": set()})
            g["n"] += 1
            g["first"], g["last"] = min(g["first"], e["ts"]), max(g["last"], e["ts"])
            g["remotes"].add(e.get("src_ip"))
        ips = []
        for g in groups.values():
            g["remotes"] = len(g["remotes"])
            hay = " ".join(str(x) for x in (g["client"], g["service"], g["cc"], g["port"])).lower()
            if not q or q.lower() in hay:
                ips.append(g)
        total += len(ips)
        key = {"bytes": lambda r: -(r["bytes"] or 0), "count": lambda r: -r["n"]}.get(sort, lambda r: -r["last"])
        rows = sorted(rows + ips, key=key)[:limit]
    return {"hours": hours, "rows": rows, "total": total}


@app.get("/api/world/live")
def world_live(after: int = 0, limit: int = Query(40, ge=1, le=200)):
    collector, db = _need()
    after = max(after, int(time.time()) - 3600)
    names = _flow_names(collector)
    rows = db.flows_recent(after, limit)
    for r in rows:
        r["client_name"] = names.get(r["client_mac"], r["client_name"])
        r.pop("remote_ip", None)
        r.pop("client_ip", None)
    for e in db.ips_events(after, "external")[:limit]:
        rows.append({"id": e["id"], "ts": e["ts"], "dir": "blocked", "action": "blocked", "cc": e.get("src_country"),
                     "port": e.get("dst_port"), "domain": None, "service": e.get("signature"),
                     "client_name": e.get("dst_name"), "up": 0, "down": 0})
    rows.sort(key=lambda r: -r["ts"])
    return {"flows": rows[:limit], "now": int(time.time())}


@app.get("/api/ips")
def ips(hours: float = 24, scope: str = Query("all", pattern="^(all|internal|external)$"), ignored: bool = False):
    collector, db = _need()
    now = int(time.time())
    since = now - int(hours * 3600)
    rows = db.ips_events(since, "all")
    ignores = db.ips_ignores()
    for e in rows:
        e["ignored"] = ips_ignored(e, ignores)
    n_ignored = sum(e["ignored"] for e in rows)
    exposure = _exposure(collector, [e for e in rows if not e["ignored"]])
    if not ignored:
        rows = [e for e in rows if not e["ignored"]]
    names = {c["ip"]: c["name"] for c in (collector.latest or {}).get("clients", [])
             if c.get("ip") and c["name"] != c["mac"]}
    names.update({d["ip"]: d["name"] for d in (collector.latest or {}).get("devices", []) if d.get("ip")})
    from .unifi_client import _name
    for e in rows:   # namen opschonen en aanvullen uit de actuele snapshot
        e["src_name"], e["dst_name"] = _name(e["src_name"], e["src_ip"]), _name(e["dst_name"], e["dst_ip"])
        if e["internal"] and e["src_name"] in (None, e["src_ip"]):
            e["src_name"] = names.get(e["src_ip"], e["src_ip"])
        if e["dst_name"] in (None, e["dst_ip"]):
            e["dst_name"] = names.get(e["dst_ip"], e["dst_ip"])

    def top(keyf, extra):
        acc: dict = {}
        for e in rows:
            k = keyf(e)
            a = acc.setdefault(k, {"count": 0, **extra(e)})
            a["count"] += 1
        return sorted(acc.values(), key=lambda x: -x["count"])[:10]

    bucket = 3600 if hours <= 48 else 6 * 3600
    series: dict[int, dict] = {}
    for t in range((since // bucket) * bucket, now + 1, bucket):
        series[t] = {"t": t, "external": 0, "internal": 0}
    for e in rows:
        b = series.get((e["ts"] // bucket) * bucket)
        if b:
            b["internal" if e["internal"] else "external"] += 1
    shown = [e for e in rows if scope == "all" or (scope == "internal") == e["internal"]]
    return {
        "available": collector.ips_available,
        "summary": {"total": len(rows), "internal": sum(e["internal"] for e in rows),
                    "external": sum(not e["internal"] for e in rows),
                    "sources": len({e["src_ip"] for e in rows}), "ignored": n_ignored},
        "ignores": ignores, "exposure": exposure,
        "by_signature": top(lambda e: e["sid"] or e["signature"],
                            lambda e: {"signature": e["signature"], "sid": e["sid"], "category": e["category"]}),
        "by_source": top(lambda e: e["src_ip"],
                         lambda e: {"ip": e["src_ip"], "name": e["src_name"], "net": e["src_net"], "internal": e["internal"],
                                    "country": e.get("src_country")}),
        "series": list(series.values()), "bucket": bucket,
        "events": shown[:300],
    }


@app.get("/api/history/overview")
def history_overview(hours: float = 6):
    collector, db = _need()
    since, b = int(time.time() - hours * 3600), _bucket(hours)
    wan = db.series("wan_samples", ["latency_ms", "loss_pct"], "", (), since, b)
    clients = [dict(r) for r in db.q(
        f"SELECT t, AVG(n) total, AVG(w) wireless, AVG(sat) sat FROM ("
        f" SELECT (ts/{b})*{b} t, ts, COUNT(*) n, SUM(ap_mac IS NOT NULL) w, AVG(satisfaction) sat"
        f" FROM client_samples WHERE ts>=? GROUP BY ts) GROUP BY t ORDER BY t", (since,))]
    return {"bucket": b, "wan": wan, "clients": clients}


@app.get("/api/history/device/{mac}")
def history_device(mac: str, hours: float = 6):
    collector, db = _need()
    since, b = int(time.time() - hours * 3600), _bucket(hours)
    radios = {}
    for r in db.q("SELECT DISTINCT radio FROM radio_samples WHERE mac=? AND ts>=?", (mac, since)):
        radios[r["radio"]] = db.series("radio_samples", ["cu_total", "interference", "retry_pct", "num_clients"],
                                       "mac=? AND radio=?", (mac, r["radio"]), since, b)
    ports = [dict(r) for r in db.q(
        f"SELECT (ts/{b})*{b} t, SUM(rx_bps)/COUNT(DISTINCT ts) rx, SUM(tx_bps)/COUNT(DISTINCT ts) tx"
        f" FROM port_samples WHERE mac=? AND ts>=? GROUP BY t ORDER BY t", (mac, since))]
    return {"bucket": b,
            "device": db.series("device_samples", ["cpu", "mem", "temp", "num_clients", "satisfaction"], "mac=?", (mac,), since, b),
            "radios": radios, "traffic": ports,
            "events": [e for e in db.events(since, 500) if e["entity_id"] == mac or e["entity_id"].startswith(mac + "#")]}


@app.get("/api/history/client/{mac}")
def history_client(mac: str, hours: float = 6):
    collector, db = _need()
    since, b = int(time.time() - hours * 3600), _bucket(hours)
    return {"bucket": b,
            "series": db.series("client_samples", ["signal", "retry_pct", "satisfaction", "tx_rate"], "mac=?", (mac,), since, b),
            "events": [e for e in db.events(since, 1000) if e["entity_id"] == mac][:100]}


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/", StaticFiles(directory=ROOT / "web"), name="web")
