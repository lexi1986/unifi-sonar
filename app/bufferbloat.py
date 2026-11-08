"""Vertraging onder belasting (bufferbloat): hoeveel trager wordt je internet als de lijn vol zit?

Tijdens de speedtest op de gateway meet Sonar steeds hoe lang het opzetten van een TCP-verbinding met een grote
website duurt. Dat is één heen-en-terug over dezelfde internetlijn; er gaan geen gegevens mee. Het verschil tussen een
rustige lijn en een volle lijn wordt een cijfer van A+ tot F.
"""
from __future__ import annotations

import asyncio
import socket
import statistics
import time
from typing import Awaitable, Callable

HOSTS = ("www.cloudflare.com", "www.google.com")
TIMEOUT = 1.5                # s; wie niet op tijd antwoordt, telt als zo traag (een volle lijn is juist wat we meten)
INTERVAL = 0.4               # s tussen twee metingen
MIN_SAMPLES = 3
GRADES = ((5, "A+"), (30, "A"), (60, "B"), (200, "C"), (400, "D"))
Probe = Callable[[], Awaitable[float]]


def grade(added_ms: float) -> str:
    return next((g for limit, g in GRADES if added_ms < limit), "F")


def summarize(samples: dict[str, list[float]], host: str, ts: int) -> dict | None:
    """Van losse metingen per fase naar één resultaat; None als er te weinig gemeten is."""
    idle = samples.get("idle") or []
    if len(idle) < MIN_SAMPLES:
        return None
    base = statistics.median(idle)

    def loaded(key: str) -> float | None:
        # 'load' = de gateway zei niet in welke fase hij zat
        rows = next((samples[k] for k in (key, "load") if len(samples.get(k) or []) >= MIN_SAMPLES), None)
        return statistics.median(rows) if rows else None

    down, up = loaded("download"), loaded("upload")
    if down is None and up is None:
        return None
    added = lambda v: None if v is None else round(max(0.0, v - base), 1)  # noqa: E731
    worst = max(x for x in (added(down), added(up)) if x is not None)
    return {"ts": ts, "host": host, "idle": round(base, 1), "down": None if down is None else round(down, 1),
            "up": None if up is None else round(up, 1), "added_down": added(down), "added_up": added(up),
            "worst": worst, "grade": grade(worst)}


async def rtt(ip: str, timeout: float = TIMEOUT) -> float:
    t0 = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, 443), timeout)
    except (asyncio.TimeoutError, OSError):
        return timeout * 1000
    ms = (time.perf_counter() - t0) * 1000
    writer.close()
    return ms


async def make_probe() -> tuple[str, Probe] | None:
    """De eerste website die antwoordt; eenmalig opgezocht, zodat DNS niet meetelt in de meting."""
    loop = asyncio.get_running_loop()
    for host in HOSTS:
        try:
            infos = await asyncio.wait_for(loop.getaddrinfo(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM), 3)
        except (asyncio.TimeoutError, OSError):
            continue
        ip = infos[0][4][0]
        if await rtt(ip) < TIMEOUT * 1000:
            return host, lambda: rtt(ip)
    return None
