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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
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
from . import auth as auth_mod  # noqa: E402
from . import backups as backups_mod  # noqa: E402
from . import i18n  # noqa: E402
from . import notify as notify_mod  # noqa: E402
from . import ha_mqtt  # noqa: E402
from . import setup as setup_mod  # noqa: E402
from .collector import Collector  # noqa: E402
from .config import Settings, Thresholds  # noqa: E402
from .db import DB  # noqa: E402
from .i18n import L  # noqa: E402
from .rules import ips_ignored  # noqa: E402

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("unifi_sonar")
DATA_DIR = os.environ.get("DATA_DIR") or str(ROOT / "data")


class Runtime:
    """Houdt instellingen, database en collector bij; kan na de wizard opnieuw starten."""

    def __init__(self) -> None:
        self.settings = Settings.load(DATA_DIR)
        i18n.set_server(self.settings.language)
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


AUTH_OPEN = {"/api/auth/state", "/api/auth/login"}
login_limiter = auth_mod.Limiter()


def _set_session(resp, request: Request) -> None:
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(auth_mod.COOKIE, auth_mod.make_token(rt.settings.auth), max_age=auth_mod.SESSION_SECONDS,
                    httponly=True, samesite="strict", secure=secure, path="/")


@app.middleware("http")
async def guard(request: Request, call_next):
    host = request.headers.get("host", "")
    if not host_allowed(host):
        return PlainTextResponse(L(
            f"UniFi Sonar: onbekende hostnaam '{_hostname(host)}'.\n\nOpen het dashboard via het IP-adres en voeg deze "
            "naam toe onder Instellingen → Toegang, of zet ALLOWED_HOSTS in de service (systemctl edit unifi-sonar).",
            f"UniFi Sonar: unknown host name '{_hostname(host)}'.\n\nOpen the dashboard via its IP address and add this "
            "name under Settings → Access, or set ALLOWED_HOSTS in the service (systemctl edit unifi-sonar)."), 421)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        # Acties alleen vanaf het dashboard zelf, niet vanaf een andere website in dezelfde browser.
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin and origin != "null" and urlsplit(origin).netloc.lower() != host.lower()):
            return JSONResponse({"detail": L("Verzoek van een andere website geweigerd.",
                                             "Request from another website refused.")}, 403)
    path, token = request.url.path, request.cookies.get(auth_mod.COOKIE)
    locked = auth_mod.enabled(rt.settings.auth)
    if locked and path.startswith("/api/") and path not in AUTH_OPEN and not auth_mod.token_valid(rt.settings.auth, token):
        return JSONResponse({"detail": "auth_required"}, 401)
    resp = await call_next(request)
    if locked and token and path.startswith("/api/") and path not in AUTH_OPEN and auth_mod.should_renew(token):
        _set_session(resp, request)   # wie blijft komen, blijft ingelogd (bijvoorbeeld een tablet aan de muur)
    return resp


def _need() -> tuple[Collector, DB]:
    if not rt.collector or not rt.db:
        raise HTTPException(409, "setup_required")
    return rt.collector, rt.db


def _bucket(hours: float) -> int:
    return max(rt.settings.poll_seconds, int(hours * 3600 / 240) // 60 * 60 or 60)


@app.get("/api/status")
def status():
    s = rt.settings
    lang = {"language": i18n.current(), "language_set": bool(s.language)}
    if not s.configured or not rt.collector:
        return {"setup_required": True, "mode": s.mode, "now": int(time.time()), **lang}
    c = rt.collector
    return {"setup_required": False, "mode": s.mode, "source": (c.latest or {}).get("source"), **lang,
            "last_ok": c.last_ok, "last_error": c.last_error,
            "poll_seconds": s.poll_seconds, "now": int(time.time()),
            "thresholds": vars(s.thresholds)}


# ----------------------------------------------------------------------- taal
class LanguageRequest(BaseModel):
    language: Literal["nl", "en"]


@app.post("/api/language")
async def language_save(req: LanguageRequest):
    """Taal van de app, ook voor meldingen naar buiten en de namen in Home Assistant."""
    s = Settings.load(DATA_DIR)
    s.language = rt.settings.language = req.language
    s.save()
    i18n.set_server(req.language)
    if rt.collector:
        await rt.collector.language_changed()
    return {"ok": True, "language": req.language}


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
    raise HTTPException(403, L("Vul ter bevestiging de huidige API-key (of het huidige wachtwoord) in.",
                               "To confirm, enter the current API key (or the current password)."))


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
        raise HTTPException(400, result.get("error") or L("Verbindingstest mislukt", "Connection test failed"))
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


# ----------------------------------------------------------------------- inlog
class LoginRequest(BaseModel):
    password: str = Field(default="", max_length=200)


class PasswordRequest(BaseModel):
    current: str = Field(default="", max_length=200)
    new: str = Field(default="", max_length=200)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _store_auth(cfg: dict) -> None:
    s = Settings.load(DATA_DIR)
    s.auth = rt.settings.auth = cfg
    s.save()


def _check_current(req_password: str, request: Request) -> None:
    ip = _client_ip(request)
    if (w := login_limiter.wait(ip)):
        raise HTTPException(429, L(f"Te veel pogingen. Probeer het over {w} seconden opnieuw.", f"Too many attempts. Try again in {w} seconds."))
    if not auth_mod.verify_password(req_password, rt.settings.auth["hash"]):
        login_limiter.failed(ip)
        raise HTTPException(403, L("Wachtwoord klopt niet.", "Wrong password."))
    login_limiter.reset(ip)


@app.get("/api/auth/state")
def auth_state(request: Request):
    on = auth_mod.enabled(rt.settings.auth)
    return {"enabled": on, "authenticated": not on or auth_mod.token_valid(rt.settings.auth, request.cookies.get(auth_mod.COOKIE)),
            "min_length": auth_mod.MIN_LENGTH}


@app.post("/api/auth/login")
def auth_login(req: LoginRequest, request: Request):
    if not auth_mod.enabled(rt.settings.auth):
        return {"ok": True}
    _check_current(req.password, request)
    resp = JSONResponse({"ok": True})
    _set_session(resp, request)
    return resp


@app.post("/api/auth/logout")
def auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth_mod.COOKIE, path="/")
    return resp


@app.post("/api/auth/password")
def auth_password(req: PasswordRequest, request: Request):
    """Inlog aanzetten of het wachtwoord wijzigen. Staat de inlog al aan, dan is het huidige wachtwoord nodig."""
    if auth_mod.enabled(rt.settings.auth):
        _check_current(req.current, request)
    if len(req.new) < auth_mod.MIN_LENGTH:
        raise HTTPException(400, L(f"Kies een wachtwoord van minstens {auth_mod.MIN_LENGTH} tekens.",
                                   f"Choose a password of at least {auth_mod.MIN_LENGTH} characters."))
    _store_auth(auth_mod.new_config(req.new))
    resp = JSONResponse({"ok": True})
    _set_session(resp, request)   # deze browser blijft ingelogd; andere sessies vervallen
    return resp


@app.post("/api/auth/disable")
def auth_disable(req: LoginRequest, request: Request):
    if auth_mod.enabled(rt.settings.auth):
        _check_current(req.password, request)
        _store_auth({})
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth_mod.COOKIE, path="/")
    return resp


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
            raise HTTPException(400, L(f"Geen geldige hostnaam: {h}", f"Not a valid host name: {h}"))
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
        raise HTTPException(400, L("Vul het adres van de MQTT-broker in.", "Enter the address of the MQTT broker."))
    if re.search(r"[\s/:]", host):
        raise HTTPException(400, L("Alleen de naam of het IP-adres van de broker, zonder http:// of poort.",
                                   "Only the name or IP address of the broker, without http:// or a port."))
    return {"enabled": req.enabled, "host": host, "port": req.port, "username": req.username.strip(),
            "password": req.password if req.password else old.get("password", ""),
            "prefix": req.prefix.strip().strip("/") or "homeassistant",
            "presence": old.get("presence", []), "presence_grace": old.get("presence_grace", ha_mqtt.DEFAULTS["presence_grace"])}


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


class PresenceDevice(BaseModel):
    mac: str = Field(pattern=r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")
    name: str = Field(default="", max_length=80)


class PresenceSave(BaseModel):
    devices: list[PresenceDevice] = Field(default_factory=list, max_length=30)
    grace: int = Field(default=300, ge=60, le=3600)


@app.post("/api/mqtt/presence")
async def mqtt_presence(req: PresenceSave):
    """Welke apparaten als device_tracker in Home Assistant komen, en hoe lang iemand weg moet zijn voor 'afwezig'."""
    seen, devices = set(), []
    for d in req.devices:
        mac = d.mac.lower()
        if mac not in seen:
            seen.add(mac)
            devices.append({"mac": mac, "name": d.name.strip() or mac})
    s = Settings.load(DATA_DIR)
    s.mqtt = {**ha_mqtt.config(s), "presence": devices, "presence_grace": req.grace}
    s.save()
    rt.settings.mqtt = s.mqtt
    if rt.collector:
        await rt.collector.ha.stop()
        rt.collector.ha.start()
    return {"ok": True, "devices": devices}


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
        raise HTTPException(400, L("Een webhook-adres begint met http:// of https://",
                                   "A webhook address starts with http:// or https://"))
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
        raise HTTPException(400, L("Vul bij elk kanaal een webhook-adres in.", "Enter a webhook address for each channel."))
    base = req.base_url.strip().rstrip("/")
    if base and not re.match(r"^https?://", base):
        raise HTTPException(400, L("Het dashboard-adres begint met http:// of https://",
                                   "The dashboard address starts with http:// or https://"))
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
        raise HTTPException(400, L("Vul een webhook-adres in.", "Enter a webhook address."))
    msg = collector.notifier.test_msg()
    if req.base_url:
        msg["url"] = req.base_url.rstrip("/") + "/#/issues"
    try:
        await collector.notifier.send(ch, msg)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, L(f"Versturen mislukt: {e}", f"Sending failed: {e}")) from e
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
        lines.append(L("Modus: ", "Mode: ") + (s.mode or L("nog niet ingesteld", "not set up yet")))
        return {"text": "\n".join(lines)}
    snap = c.latest or {}
    port = urlsplit(s.controller_url).port if s.controller_url else None
    lines.append(L(f"Modus: {s.mode} · bron: {snap.get('source') or '?'} · elke {s.poll_seconds} s · bewaren {s.retention_days} d",
                   f"Mode: {s.mode} · source: {snap.get('source') or '?'} · every {s.poll_seconds} s · keep {s.retention_days} d"))
    if s.mode == "live":
        host = urlsplit(s.controller_url).hostname or ""
        kind = L("IP-adres", "IP address") if re.match(r"^[\d.]+$|:", host) else L("hostnaam", "host name")
        yes = L("ja", "yes") if s.verify_tls else L("nee", "no")
        lines.append(L(f"Controller: {kind}, poort {port or 443}, certificaat controleren: {yes}",
                       f"Controller: {kind}, port {port or 443}, verify certificate: {yes}"))
    si = c.sysinfo or {}
    if si.get("network_version"):
        lines.append(f"UniFi Network: {si['network_version']}" + (f" (build {si['build']})" if si.get("build") else ""))
    devs = snap.get("devices", [])
    by_type: dict[str, list[str]] = {}
    for d in devs:
        by_type.setdefault(d["type"], []).append(d["model"] or "?")
    lines.append(L("Apparaten: ", "Devices: ") + (" · ".join(f"{len(v)} {k} ({', '.join(sorted(set(v)))})"
                                                       for k, v in sorted(by_type.items())) or L("geen", "none")))
    states = {d["state"] for d in devs if d["state"] != "online"}
    if states:
        lines.append(L("Niet online: ", "Not online: ") + ", ".join(sorted(states)))
    cl = snap.get("clients", [])
    lines.append(f"Clients: {sum(not x['wired'] for x in cl)} wifi · {sum(x['wired'] for x in cl)} " + L("bedraad", "wired"))
    untried = L("nog niet geprobeerd", "not tried yet")
    opt = {"IPS": c.optional.get("ips", untried if c.ips_available is None else None),
           L("instellingen", "settings"): c.optional.get("config", None if c.config else untried)}
    lines.append(L("Extra gegevens: ", "Extra data: ") + " · ".join(f"{k} {'ok' if v is None else scrub(v)[:80]}" for k, v in opt.items()))
    errs = {k: scrub(v)[:160] for k, v in (getattr(c.client, "errors", {}) or {}).items()} if c.client else {}
    if c.last_error:
        lines.append(L("Laatste fout: ", "Last error: ") + scrub(c.last_error)[:200])
    for k, v in errs.items():
        lines.append(L(f"Fout bron {k}: {v}", f"Error source {k}: {v}"))
    if c.last_ok:
        lines.append(L(f"Laatste meting: {int(time.time() - c.last_ok)} s geleden", f"Last poll: {int(time.time() - c.last_ok)} s ago"))
    iss = [i for i in snap.get("issues", []) if not i.get("group")]
    kinds: dict[str, int] = {}
    for i in iss:
        kinds[i["key"].split(":")[0]] = kinds.get(i["key"].split(":")[0], 0) + 1
    h = snap.get("health") or {}
    lines.append(L("Meldingen: ", "Issues: ") + f"{len(iss)} (score {h.get('score', '?')}) · "
                 + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))
    default = vars(Thresholds())
    changed = [f"{k}={v:g}" for k, v in vars(s.thresholds).items() if v != default[k]]
    lines.append(L("Aangepaste drempels: ", "Changed thresholds: ") + (", ".join(changed) if changed else L("geen", "none")))
    ncfg = notify_mod.config(s)
    if ncfg["channels"]:
        st = c.notifier.status
        lines.append(L("Meldingen versturen: ", "Sending notifications: ") + ", ".join(
            f"{ch['kind']} ({L('fout: ', 'error: ') + scrub(st[ch['id']]['error'])[:60] if st.get(ch['id'], {}).get('error') else 'ok'})"
            for ch in ncfg["channels"]))
    try:
        size = Path(s.database).stat().st_size / 1e6
        oldest = rt.db.q("SELECT MIN(ts) t FROM wan_samples")[0]["t"]
        days = round((time.time() - oldest) / 86400, 1) if oldest else 0
        lines.append(L(f"Database: {size:.0f} MB, historie van {days} dagen", f"Database: {size:.0f} MB, {days} days of history"))
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


def _viewer(request: Request, collector, ip: str | None = None) -> tuple[str, dict | None]:
    """Het IP-adres van de browser en de client die daarbij hoort (demo: de iPhone)."""
    addr = request.client.host if request.client else ""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd and addr in ("127.0.0.1", "::1"):   # achter een reverse proxy op dezelfde machine
        addr = fwd.split(",")[0].strip()
    if ip and collector.mock:   # alleen in de demo: een apparaat nadoen
        addr = ip
    clients = (collector.latest or {}).get("clients", [])
    c = next((x for x in clients if x.get("ip") == addr), None)
    if c is None and collector.mock and not ip:
        c = next((x for x in clients if x["name"] == "iPhone"), None)   # demo: doe alsof je op de iPhone kijkt
    return addr, c


@app.get("/api/me")
def me(request: Request, ip: str | None = Query(None, max_length=45)):
    """Het apparaat waarmee je dit dashboard bekijkt, herkend aan het IP-adres van de browser."""
    collector, db = _need()
    addr, c = _viewer(request, collector, ip)
    snap = collector.latest or {}
    if c is None:
        return {"found": False, "ip": addr}
    devs = {d["mac"]: d for d in snap.get("devices", [])}
    up = devs.get(c.get("ap_mac") or c.get("sw_mac") or "", {})
    lt = time.localtime()
    day0 = int(time.mktime(lt[:3] + (0, 0, 0, 0, 0, -1)))
    issues = [{"title": i18n.issue(i)["title"], "severity": i["severity"]} for i in snap.get("issues", [])
              if i.get("client_mac") == c["mac"] and not i.get("muted")]
    return {"found": True, "ip": addr, "demo": collector.mock is not None and addr != c.get("ip"),
            "client": {k: c.get(k) for k in ("mac", "name", "ip", "vendor", "wired", "ssid", "band", "channel", "proto",
                                              "signal", "satisfaction", "tx_rate_mbps", "rx_rate_mbps", "retry_pct",
                                              "assoc_ts", "uptime", "sw_port", "network")},
            "uplink": {"mac": up.get("mac"), "name": up.get("name"), "type": up.get("type")},
            "roams_today": db.client_roams_since(c["mac"], day0), "issues": issues}


# ----------------------------------------------------------------------- internetstoringen
@app.get("/api/outages")
def outages():
    """Storingen van de afgelopen 90 dagen (Sonar bewaart ze zelf ook langer) en de beschikbaarheid per periode."""
    collector, db = _need()
    now = int(time.time())
    rows = db.outages(now - 400 * 86400)

    def uptime(since: int) -> float:
        down = sum(max(0, min(o["ts"] + o["seconds"], now) - max(o["ts"], since)) for o in rows)
        return round(100 * (1 - down / (now - since)), 3)
    lt = time.localtime(now)
    months = []
    for k in range(5, -1, -1):
        y, m = lt.tm_year, lt.tm_mon - k
        while m < 1:
            y, m = y - 1, m + 12
        start = int(time.mktime((y, m, 1, 0, 0, 0, 0, 0, -1)))
        end = min(now, int(time.mktime((y + (m == 12), m % 12 + 1, 1, 0, 0, 0, 0, 0, -1))))
        inside = [o for o in rows if o["ts"] < end and o["ts"] + o["seconds"] > start]
        down = sum(max(0, min(o["ts"] + o["seconds"], end) - max(o["ts"], start)) for o in inside)
        months.append({"ts": start, "uptime": round(100 * (1 - down / max(1, end - start)), 3), "n": len(inside), "seconds": down})
    hist = ((collector.insights or {}).get("wan_history") or [])
    return {"available": bool(hist) or bool(rows), "isp": hist[0]["isp"] if hist else None,
            "uptime": {"day": uptime(now - 86400), "week": uptime(now - 7 * 86400), "month": uptime(now - 30 * 86400),
                       "quarter": uptime(now - 90 * 86400)},
            "outages": rows[:100], "months": months, "error": collector.optional.get("insights")}


# ----------------------------------------------------------------------- verbruik per apparaat
DPI_CAT = {0: ("Berichten", "Messaging"), 1: ("P2P", "P2P"), 3: ("Bestanden", "File transfer"), 4: ("Video en muziek", "Streaming"),
           5: ("Mail en samenwerken", "Mail and collaboration"), 6: ("Bellen", "VoIP"), 8: ("Games", "Games"),
           9: ("Netwerkbeheer", "Network management"), 10: ("Op afstand", "Remote access"), 13: ("Web", "Web"),
           14: ("Updates", "Updates"), 15: ("Web-chat", "Web chat"), 17: ("Zakelijk", "Business"), 18: ("Netwerkprotocollen", "Network protocols"),
           24: ("Sociale media", "Social media"), 255: ("Onbekend", "Unknown")}


def _cat(c) -> str:
    return L(*DPI_CAT[c]) if c in DPI_CAT else (str(c) if c is not None else L("Onbekend", "Unknown"))


def _client_names(collector, db) -> dict[str, str]:
    names = {r["mac"]: r["name"] or r["hostname"] for r in db.q("SELECT mac, name, hostname FROM known_clients")}
    names.update({c["mac"]: c["name"] for c in (collector.latest or {}).get("clients", [])})
    return names


@app.get("/api/usage/clients")
def usage_clients(period: str = Query("day", pattern="^(day|week|month)$")):
    """Grootverbruikers: verkeer per apparaat vandaag, de afgelopen 7 of 30 dagen (ook verkeer binnen je netwerk)."""
    collector, db = _need()
    now = int(time.time())
    day0 = int(time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1)))
    since = {"day": day0, "week": day0 - 6 * 86400, "month": day0 - 29 * 86400}[period]
    tot = db.client_usage_totals("day", since) if period != "day" else db.client_usage_totals("hour", day0)
    if period == "day" and not tot:
        tot = db.client_usage_totals("day", day0)
    names = _client_names(collector, db)
    cats: dict[str, list] = {}
    for d in collector.dpi:
        cats.setdefault(d["mac"], []).append({"cat": _cat(d["cat"]), "bytes": d["down"] + d["up"]})
    rows = [{"mac": m, "name": names.get(m, m), "down": v["down"], "up": v["up"], "total": v["down"] + v["up"],
             "cats": sorted(cats.get(m, []), key=lambda x: -x["bytes"])[:4]} for m, v in tot.items() if v["down"] + v["up"] > 0]
    rows.sort(key=lambda r: -r["total"])
    return {"period": period, "since": since, "rows": rows[:40], "devices": len(rows), "dpi": bool(collector.dpi),
            "error": collector.optional.get("client_usage")}


@app.get("/api/usage/client/{mac}")
def usage_client(mac: str):
    collector, db = _need()
    mac, now = mac.lower(), int(time.time())
    cats = sorted(({"cat": _cat(d["cat"]), "down": d["down"], "up": d["up"]} for d in collector.dpi if d["mac"] == mac),
                  key=lambda x: -(x["down"] + x["up"]))
    return {"days": db.client_usage_series(mac, "day", now - 31 * 86400),
            "hours": db.client_usage_series(mac, "hour", now - 48 * 3600), "cats": cats, "dpi": bool(collector.dpi)}


# ----------------------------------------------------------------------- wifi in de buurt
@app.get("/api/neighbors/{mac}")
def neighbors(mac: str):
    """Wat een access point van de buren hoort, en hoe druk elk kanaal is."""
    from .rules_extra import channel_history, channel_table
    collector, db = _need()
    snap, mac = collector.latest or {}, mac.lower()
    ap = next((d for d in snap.get("devices", []) if d["mac"] == mac), None)
    ins = collector.insights or {}
    if not ap or ap["type"] != "ap":
        raise HTTPException(404, L("Geen access point", "Not an access point"))
    heard = sorted((n for n in ins.get("neighbors") or [] if n["ap_mac"] == mac), key=lambda n: -(n["signal"] or -100))
    since = int(time.time()) - 30 * 86400
    return {"available": "neighbors" in ins,
            "channels": {b: channel_table(ap, b, ins, snap.get("devices", []), channel_history(db, mac, b, since)) for b in ("2.4", "5")},
            "current": {r["radio"]: r.get("channel") for r in ap.get("radios") or []},
            "neighbors": [{k: n[k] for k in ("ssid", "band", "channel", "width", "signal")} for n in heard[:40]], "total": len(heard)}


@app.get("/api/wifi/connectivity")
def wifi_connectivity():
    collector, _ = _need()
    return {"bands": (collector.insights or {}).get("wifi_connectivity") or {}}


# ----------------------------------------------------------------------- vaste pauzetijden
class ScheduleIn(BaseModel):
    id: int | None = None
    name: str = Field(default="", max_length=60)
    macs: list[str] = Field(default_factory=list, max_length=100)
    days: list[int] = Field(default_factory=list, max_length=7)
    start: str = Field(default="21:00", max_length=5)
    stop: str = Field(default="07:00", max_length=5)
    enabled: bool = True


@app.get("/api/schedules")
def schedules_list():
    from . import schedules as sched
    collector, db = _need()
    now = int(time.time())
    names = _client_names(collector, db)
    active = sched.wanted(db.schedules(), now)
    return {"schedules": [{**s, "devices": [{"mac": m, "name": names.get(m, m)} for m in s["macs"]],
                           "until": max((a["until"] for a in active.values() if a["id"] == s["id"]), default=None)}
                          for s in db.schedules()],
            "paused": {m: {**a, "name": names.get(m, m)} for m, a in active.items()}, "now": now}


@app.post("/api/schedules/save")
async def schedules_save(req: ScheduleIn):
    from . import schedules as sched
    collector, db = _need()
    try:
        s = sched.clean(req.model_dump())
    except ValueError as e:
        raise HTTPException(400, {"name": L("Geef het schema een naam.", "Give the schedule a name."),
                                  "same": L("Begin- en eindtijd zijn gelijk.", "Start and end time are the same.")}.get(
                                      str(e), L("Ongeldige tijd (gebruik uu:mm).", "Invalid time (use hh:mm)."))) from e
    sid = db.save_schedule(s)
    await collector.release_schedule()
    return {"ok": True, "id": sid}


class ScheduleDel(BaseModel):
    id: int


@app.post("/api/schedules/delete")   # POST i.p.v. DELETE, zie /api/unmute
async def schedules_delete(req: ScheduleDel):
    collector, db = _need()
    db.delete_schedule(req.id)
    await collector.release_schedule()
    return {"ok": True}


# ----------------------------------------------------------------------- wifi-snelheid meten vanaf je apparaat
_BLOCK = os.urandom(1 << 20)   # 1 MB willekeurige bytes (niet te comprimeren), herhaald voor de download


@app.get("/api/selftest/ping")
def selftest_ping():
    return {"t": time.time()}


@app.get("/api/selftest/down")
def selftest_down(mb: int = Query(25, ge=1, le=500)):
    from fastapi.responses import StreamingResponse

    def chunks():
        for _ in range(mb):
            yield _BLOCK
    return StreamingResponse(chunks(), media_type="application/octet-stream",
                             headers={"Cache-Control": "no-store", "Content-Length": str(mb << 20)})


@app.post("/api/selftest/up")
async def selftest_up(request: Request):
    n = 0
    async for chunk in request.stream():
        n += len(chunk)
        if n > 600 << 20:
            break
    return {"bytes": n}


class SelftestResult(BaseModel):
    down: float = Field(ge=0, le=100000)
    up: float = Field(ge=0, le=100000)
    ping: float | None = Field(default=None, ge=0, le=10000)
    room: str = Field(default="", max_length=40)


@app.post("/api/selftest/result")
def selftest_result(req: SelftestResult, request: Request):
    """Een meting bewaren met wie en waar: het apparaat (aan het IP-adres), de AP, de band en het signaal op dat moment."""
    collector, db = _need()
    addr, c = _viewer(request, collector)
    devs = {d["mac"]: d["name"] for d in (collector.latest or {}).get("devices", [])}
    row = {"ts": int(time.time()), "mac": (c or {}).get("mac"), "name": (c or {}).get("name") or addr, "room": req.room.strip(),
           "ap": devs.get((c or {}).get("ap_mac") or (c or {}).get("sw_mac") or ""), "band": None if (c or {}).get("wired") else (c or {}).get("band"),
           "signal": (c or {}).get("signal"), "down": round(req.down, 1), "up": round(req.up, 1),
           "ping": round(req.ping, 1) if req.ping is not None else None}
    db.add_selftest(row)
    return {"ok": True, "result": row}


@app.get("/api/selftests")
def selftests():
    _, db = _need()
    return {"rows": db.selftests(100)}


# ----------------------------------------------------------------------- beveiligingsadviezen
@app.get("/api/advisories")
def advisories_list():
    from . import advisories as adv
    collector, _ = _need()
    a = collector.advisories or {}
    inv = adv.inventory((collector.latest or {}).get("devices", []), (collector.sysinfo or {}).get("network_version"))
    return {"enabled": rt.settings.advisories is not False, "fetched": a.get("fetched"), "error": a.get("error"),
            "items": adv.summary_list(a.get("items") or [], inv), "feed": adv.FEED}


class AdvisorySettings(BaseModel):
    enabled: bool


@app.post("/api/advisories/settings")
async def advisories_settings(req: AdvisorySettings):
    s = Settings.load(DATA_DIR)
    s.advisories = rt.settings.advisories = req.enabled
    s.save()
    if rt.collector:
        rt.collector._adv_checked = 0
        if req.enabled:
            await rt.collector._collect_advisories(int(time.time()))
        else:
            rt.collector.advisories = {}
    return {"ok": True}


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
            "bufferbloat": collector.bloat_history[-1] if collector.bloat_history else None,
            "available": collector.mock is not None or (collector.client and collector.client.source in ("legacy-key", "legacy-login"))}


@app.get("/api/live/wan")
async def live_wan():
    collector, db = _need()
    try:
        live = await collector.live_wan()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, L(f"Live-meting niet beschikbaar: {e}", f"Live reading not available: {e}")) from e
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
# ----------------------------------------------------------------------- UniFi-backups
class BackupSettings(BaseModel):
    daily: bool = False


@app.get("/api/backups")
def backups_info():
    collector, _ = _need()
    s = rt.settings
    return {"files": backups_mod.listing(s.data_dir), "daily": s.backup_daily, "keep": backups_mod.KEEP,
            "can_download": auth_mod.enabled(s.auth), **collector.backup_status}


@app.post("/api/backups/settings")
def backups_settings(req: BackupSettings):
    s = Settings.load(DATA_DIR)
    s.backup_daily = rt.settings.backup_daily = req.daily
    s.save()
    return {"ok": True, "daily": req.daily}


@app.post("/api/backups/run")
async def backups_run():
    """Knop 'Nu een backup maken'."""
    collector, _ = _need()
    await collector.collect_backups(force=True, create=True)
    if collector.backup_status["error"]:
        raise HTTPException(502, collector.backup_status["error"])
    return {"ok": True}


@app.get("/api/backups/download/{name}")
def backups_download(name: str):
    if not auth_mod.enabled(rt.settings.auth):   # een backup bevat ook je wifi-wachtwoorden
        raise HTTPException(403, L("Zet eerst de inlog aan onder Instellingen → Toegang.", "First turn on the login under Settings → Access."))
    path = backups_mod.path_of(rt.settings.data_dir, name)
    if not path:
        raise HTTPException(404, L("Backup niet gevonden.", "Backup not found."))
    return FileResponse(path, media_type="application/octet-stream", filename=name)


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
        raise HTTPException(503, collector.last_error or L("Nog geen data opgehaald", "No data fetched yet"))
    return {**collector.latest, "issues": i18n.issues(collector.latest.get("issues", []))}


@app.get("/api/issues")
def issues(state: str = Query("open", pattern="^(open|all)$")):
    collector, db = _need()
    return i18n.issues(db.issues(open_only=state == "open", now=int(time.time())))


class MuteRequest(BaseModel):
    key: str = Field(min_length=1, max_length=300)
    days: float | None = Field(default=None, gt=0, le=3650)   # None = altijd


@app.post("/api/mute")
def mute(req: MuteRequest):
    collector, db = _need()
    now = int(time.time())
    known = {i["key"]: i for i in (collector.latest or {}).get("issues", [])}
    found = known.get(req.key) or next((i for i in db.issues(False, 1000) if i["key"] == req.key), None)
    if found is None:
        raise HTTPException(404, L("Onbekende melding", "Unknown issue"))
    title = i18n.bi(found["title"], (found.get("en") or {}).get("title") or found["title"])
    db.mute(req.key, now + int(req.days * 86400) if req.days else None, now, title)
    collector.apply_mutes()
    return {"ok": True}


@app.post("/api/clients/{mac}/approve")
def approve(mac: str):
    """'Ken ik': een nieuw apparaat goedkeuren. De melding verdwijnt meteen."""
    collector, db = _need()
    mac = mac.lower()
    if not db.approve_client(mac):
        raise HTTPException(404, L("Onbekend apparaat", "Unknown device"))
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
        raise HTTPException(404, L("Geen verbonden wifi-client met dit MAC-adres", "No connected wifi client with this MAC address"))
    if collector.mock:
        return {"ok": True, "demo": True}
    try:
        await collector.client.reconnect(c["mac"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, L(f"UniFi weigerde: {e}", f"UniFi refused: {e}")) from e
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
        raise HTTPException(400, L("Het eindtijdstip ligt in het verleden", "The end time is in the past"))
    c = next((x for x in (collector.latest or {}).get("clients", []) if x["mac"] == mac), None)
    name = c["name"] if c else next((p["name"] for p in db.pauses() if p["mac"] == mac), mac)
    try:
        await collector.set_blocked(mac, True)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, L(f"UniFi weigerde: {e}", f"UniFi refused: {e}")) from e
    db.set_pause(mac, req.until, now, name)
    until = time.strftime("%d-%m %H:%M", time.localtime(req.until)) if req.until else None
    db.add_events([{"ts": now, "kind": "client_leave", "entity_type": "client", "entity_id": mac,
                    "message": i18n.bi(f"{name}: internet gepauzeerd tot {until or 'je hervat'}",
                                       f"{name}: internet paused until {until or 'you resume'}")}])
    return {"ok": True, "demo": bool(collector.mock)}


@app.post("/api/clients/{mac}/resume")
async def resume(mac: str):
    collector, db = _need()
    mac = mac.lower()
    p = next((x for x in db.pauses() if x["mac"] == mac), None)
    try:
        await collector.set_blocked(mac, False)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, L(f"UniFi weigerde: {e}", f"UniFi refused: {e}")) from e
    db.clear_pause(mac)
    if p:
        db.add_events([{"ts": int(time.time()), "kind": "client_join", "entity_type": "client", "entity_id": mac,
                        "message": i18n.bi(f"{p['name']}: pauze opgeheven", f"{p['name']}: pause lifted")}])
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
        raise HTTPException(400, L("Kies een adres, een regel of allebei.", "Choose an address, a rule or both."))
    if req.ip:
        try:
            ipaddress.ip_address(req.ip)
        except ValueError as e:
            raise HTTPException(400, L("Geen geldig IP-adres", "Not a valid IP address")) from e
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
STORED_EN = {"Geblokkeerd": "Blocked", "Regioblokkade": "Region block", "Firewallregel": "Firewall rule",
             "Onbekende regel": "Unknown rule", "Onbekend": "Unknown", "IPS-regel": "IPS rule"}


def _st(v: str | None, default: str | None = None) -> str | None:
    """Vaste teksten die zo in de database staan (blokkeerreden, onbekende IPS-regel) in de actieve taal."""
    v = v or default
    return STORED_EN.get(v, v) if v and i18n.current() == "en" else v


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
        return ip if ip and _is_local_ip(ip) else L("je gateway (WAN)", "your gateway (WAN)")
    return target


def _blocked_details(collector, db, since: int) -> dict[str, list[dict]]:
    """Per land: wat er tegengehouden werd, gericht op welk apparaat en welke poort, vanaf hoeveel adressen."""
    target = _namer(collector)

    rows = [{"cc": f["cc"], "by": _st(f["reason"], "Geblokkeerd"), "what": _st(f["service"], "Onbekend"), "port": f["port"],
             "target": target(f["client_name"], f["client_ip"]), "src": f["remote_ip"], "ts": f["ts"]}
            for f in db.blocked_flows(since) if f["cc"]]
    rows += [{"cc": e["src_country"], "by": "IPS", "what": _st(e.get("signature"), "IPS-regel"), "port": e.get("dst_port"),
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


@app.get("/api/segments")
def segments_api():
    """Netwerken, firewallzones en wat er tussen de zones mag (alleen lezen)."""
    from . import segments
    collector, _ = _need()
    seg = (collector.config or {}).get("segments")
    if not seg:
        return {"available": False}
    snap = collector.latest or {}
    clients = snap.get("clients", [])
    cnt = segments.counts(clients, seg)
    names = {d["ip"]: d["name"] for d in snap.get("devices", []) if d.get("ip")}
    for c in clients:   # zonder eigen naam valt UniFi terug op de fabrikant; dan liever hostnaam of IP-adres
        if c.get("ip"):
            real = c["name"] not in (c.get("vendor"), c.get("mac"), None, "")
            names[c["ip"]] = c["name"] if real else (c.get("hostname") or c["ip"])
    cells = {}
    for k, c in ((seg.get("matrix") or {}).get("cells") or {}).items():
        cells[k] = {**c, "rules": [{**r, "targets": [names.get(ip, ip) for ip in r["ips"]]} for r in c["rules"]]}
    fl = segments.flows(seg, (collector.config or {}).get("forwards"))
    if fl:
        cnt_all = {**cnt}
        for n in fl["nodes"]:
            n.update(cnt_all.get(n["id"], {}))
        for e in fl["edges"]:
            e["rules"] = [{**r, "targets": [names.get(ip, ip) for ip in r["ips"]],
                           "sources": [names.get(ip, ip) for ip in r.get("src_ips", [])]} for r in e["rules"]]
    return {"available": True,
            "segments": [{**s, **cnt.get(s["id"], {})} for s in seg["segments"]],
            "matrix": {**seg["matrix"], "cells": cells} if seg.get("matrix") else None,
            "flows": fl}


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
        r["by"] = _st(r.pop("reason"), "Geblokkeerd") if r["dir"] == "blocked" else None
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
                "service": _st(e.get("signature")), "by": "IPS", "n": 0, "up": 0, "down": 0, "bytes": 0,
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
                     "port": e.get("dst_port"), "domain": None, "service": _st(e.get("signature")),
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
        e["signature"] = _st(e["signature"])
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
def index(request: Request):
    """De pagina met de taal erin: de instelling, of (nog niet gekozen) die van de browser."""
    lang = i18n.normalize(rt.settings.language)
    if not lang:
        accept = request.headers.get("accept-language", "").lower()
        lang = "nl" if not accept or accept.startswith("nl") else "en"
    html = (ROOT / "web" / "index.html").read_text()
    html = html.replace('<html lang="nl">', f'<html lang="{lang}" data-lang-set="{1 if rt.settings.language else 0}">', 1)
    return HTMLResponse(html)


app.mount("/", StaticFiles(directory=ROOT / "web"), name="web")
