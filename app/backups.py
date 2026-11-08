"""Kopieën van de UniFi Network-backups, zodat je er nog bij kunt als de controller zelf is gecrasht.

Sonar haalt de automatische backups (.unf) van de controller op en kan desgewenst elke dag zelf een verse laten maken.
Een .unf bevat je hele configuratie, ook wifi-wachtwoorden: de map is alleen leesbaar voor de service en downloaden
via het dashboard kan alleen als de inlog aanstaat.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.unf$")
KEEP = 30
STALE_DAYS, STALE_DAYS_DAILY = 40, 3     # UniFi maakt standaard soms maar één backup per maand


def folder(data_dir: str) -> Path:
    p = Path(data_dir) / "backups"
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)
    return p


def listing(data_dir: str) -> list[dict]:
    """Nieuwste eerst."""
    out = []
    for f in folder(data_dir).glob("*.unf"):
        st = f.stat()
        out.append({"name": f.name, "size": st.st_size, "ts": int(st.st_mtime), "source": "sonar" if f.name.startswith("sonar_") else "auto"})
    return sorted(out, key=lambda x: -x["ts"])


def path_of(data_dir: str, name: str) -> Path | None:
    if not NAME_RE.match(name or ""):
        return None
    p = folder(data_dir) / name
    return p if p.is_file() else None


def has(data_dir: str, name: str) -> bool:
    return path_of(data_dir, name) is not None


def store(data_dir: str, name: str, data: bytes, ts: float | None = None) -> None:
    """Eerst naar een tijdelijk bestand: een halve download mag nooit voor een backup doorgaan."""
    if not NAME_RE.match(name):
        raise ValueError(name)
    if not data:
        raise ValueError("empty backup")
    target = folder(data_dir) / name
    tmp = target.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    if ts:
        os.utime(tmp, (ts, ts))
    os.replace(tmp, target)


def prune(data_dir: str, keep: int = KEEP) -> None:
    for b in listing(data_dir)[keep:]:
        (folder(data_dir) / b["name"]).unlink(missing_ok=True)


def summary(data_dir: str, daily: bool, now: float | None = None) -> dict:
    rows = listing(data_dir)
    now = now if now is not None else time.time()
    newest = rows[0]["ts"] if rows else None
    limit = (STALE_DAYS_DAILY if daily else STALE_DAYS) * 86400
    return {"count": len(rows), "newest": newest, "daily": daily, "stale": newest is None or now - newest > limit}
