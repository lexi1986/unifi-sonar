"""Vaste pauzetijden: een groep apparaten (bijvoorbeeld 'Kinderen') heeft op gekozen dagen tussen twee tijden geen
internet. Sonar blokkeert ze dan in UniFi, net als bij 'Internet pauzeren', en laat ze daarna weer toe.

Een schema over middernacht heen (21:00–07:00) hoort bij de dag waarop het begint: 'ma–vr 21:00–07:00' loopt
dus van maandagavond tot zaterdagochtend.
"""
from __future__ import annotations

import re
import time

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def minutes(hhmm: str) -> int:
    m = TIME_RE.match(hhmm or "")
    if not m:
        raise ValueError(hhmm)
    return int(m.group(1)) * 60 + int(m.group(2))


def window(s: dict, ts: float) -> tuple[int, int] | None:
    """Het venster [begin, eind) waarin het schema nu loopt, of None."""
    if not s.get("enabled") or not s.get("days") or not s.get("macs"):
        return None
    start, stop = minutes(s["start"]), minutes(s["stop"])
    if start == stop:
        return None
    y, mo, d = time.localtime(ts)[:3]
    at = lambda day, mins: int(time.mktime((y, mo, day, mins // 60, mins % 60, 0, 0, 0, -1)))  # noqa: E731 – mktime rekent dag 0/32 zelf om
    for back in (0, 1):   # vandaag begonnen, of gisteren begonnen en loopt over middernacht door
        if time.localtime(at(d - back, 12 * 60)).tm_wday not in s["days"]:
            continue
        b, e = at(d - back, start), at(d - back + (1 if stop < start else 0), stop)
        if b <= ts < e:
            return b, e
    return None


def wanted(schedules: list[dict], ts: float) -> dict[str, dict]:
    """Welke apparaten nu volgens een schema gepauzeerd horen te zijn: mac → {schedule, until}."""
    out: dict[str, dict] = {}
    for s in schedules:
        w = window(s, ts)
        if not w:
            continue
        for mac in s["macs"]:
            if mac not in out or w[1] > out[mac]["until"]:
                out[mac] = {"id": s["id"], "name": s["name"], "until": w[1]}
    return out


def clean(s: dict) -> dict:
    """Controle bij opslaan; gooit ValueError met een leesbare reden."""
    name = (s.get("name") or "").strip()[:60]
    macs = sorted({m.strip().lower() for m in s.get("macs") or [] if re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", m.strip().lower())})
    days = sorted({int(d) for d in s.get("days") or [] if str(d).isdigit() and 0 <= int(d) <= 6})
    minutes(s.get("start", "")), minutes(s.get("stop", ""))
    if not name:
        raise ValueError("name")
    if s.get("start") == s.get("stop"):
        raise ValueError("same")
    return {"id": s.get("id"), "name": name, "macs": macs, "days": days, "start": s["start"], "stop": s["stop"],
            "enabled": bool(s.get("enabled", True))}
