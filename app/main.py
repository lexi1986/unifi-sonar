"""FastAPI-server: collector op de achtergrond + JSON-API + statisch dashboard."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
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

from .collector import Collector  # noqa: E402
from .config import Settings  # noqa: E402
from .db import DB  # noqa: E402
from . import setup as setup_mod  # noqa: E402

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


@app.get("/api/ips")
def ips(hours: float = 24, scope: str = Query("all", pattern="^(all|internal|external)$")):
    collector, db = _need()
    now = int(time.time())
    since = now - int(hours * 3600)
    rows = db.ips_events(since, "all")
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
                    "sources": len({e["src_ip"] for e in rows})},
        "by_signature": top(lambda e: e["sid"] or e["signature"],
                            lambda e: {"signature": e["signature"], "sid": e["sid"], "category": e["category"]}),
        "by_source": top(lambda e: e["src_ip"],
                         lambda e: {"ip": e["src_ip"], "name": e["src_name"], "net": e["src_net"], "internal": e["internal"]}),
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
