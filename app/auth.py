"""De inlog van het dashboard: één wachtwoord, verplicht zodra Sonar een echt netwerk bewaakt.

Het eerste wachtwoord kan alleen met een eenmalige code die op de machine zelf staat, zodat niet de eerste de beste
op het netwerk het dashboard kan overnemen. Het wachtwoord wordt alleen als scrypt-hash bewaard. Een sessie is een
ondertekende cookie (HMAC) met een vervaldatum en een id dat ook op de server staat; daardoor kun je sessies intrekken.
Wie het wachtwoord wijzigt, krijgt een nieuw geheim, waardoor alle bestaande sessies vervallen.

Wachtwoord kwijt? Op de machine zelf:  cd /opt/unifi-sonar && .venv/bin/python -m app.auth --reset
en daarna de service herstarten; de journal en `unifi-sonar-update` tonen dan een nieuwe eenmalige code.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

COOKIE = "sonar_session"
SESSION_SECONDS = 90 * 86400
RENEW_AFTER = 86400          # een dag na uitgifte krijgt de browser een verse cookie (blijft dus ingelogd zolang hij komt)
MIN_LENGTH = 8
MAX_FAILS, FAIL_WINDOW = 5, 300
MAX_SESSIONS = 30
SETUP_FILE = "setup-code"
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # zonder tekens die op elkaar lijken
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    return f"scrypt${_b64(salt)}${_b64(hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT))}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, salt, want = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), **_SCRYPT)
        return kind == "scrypt" and hmac.compare_digest(got, base64.b64decode(want))
    except (ValueError, TypeError):
        return False


def new_config(password: str) -> dict:
    return {"hash": hash_password(password), "secret": secrets.token_hex(32)}


def enabled(cfg: dict | None) -> bool:
    return bool(cfg and cfg.get("hash") and cfg.get("secret"))


def random_code(groups: int = 3) -> str:
    return "-".join("".join(secrets.choice(CODE_LETTERS) for _ in range(4)) for _ in range(groups))


def normalize_code(code: str) -> str:
    return re.sub(r"[\s-]", "", code or "").upper()


def _setup_path(data_dir: str) -> Path:
    return Path(data_dir) / SETUP_FILE


def ensure_setup_code(data_dir: str) -> str:
    """De eenmalige code voor het eerste wachtwoord; alleen leesbaar op de machine zelf."""
    path = _setup_path(data_dir)
    if path.is_file():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    code = random_code()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(code + "\n")
    return code


def check_setup_code(data_dir: str, code: str) -> bool:
    path = _setup_path(data_dir)
    want = normalize_code(path.read_text()) if path.is_file() else ""
    return bool(want) and hmac.compare_digest(want, normalize_code(code))


def clear_setup_code(data_dir: str) -> None:
    _setup_path(data_dir).unlink(missing_ok=True)


def _sign(cfg: dict, sid: str, expires: int) -> str:
    body = f"{sid}.{expires}"
    return f"{body}.{hmac.new(cfg['secret'].encode(), body.encode(), hashlib.sha256).hexdigest()}"


def _parts(cfg: dict, token: str | None) -> tuple[str, int] | None:
    """(sessie-id, vervaltijd) als de handtekening klopt."""
    bits = (token or "").split(".")
    if len(bits) != 3 or not bits[1].isdigit() or not hmac.compare_digest(_sign(cfg, bits[0], int(bits[1])), token):
        return None
    return bits[0], int(bits[1])


def new_session(cfg: dict, agent: str = "", now: float | None = None) -> str:
    """Maakt een sessie aan in cfg; de aanroeper slaat cfg op."""
    now = int(now if now is not None else time.time())
    rows = {k: v for k, v in (cfg.get("sessions") or {}).items() if v["expires"] > now}
    sid = secrets.token_urlsafe(16)
    rows[sid] = {"created": now, "last_seen": now, "expires": now + SESSION_SECONDS, "agent": agent}
    for old in sorted(rows, key=lambda k: rows[k]["last_seen"])[:max(0, len(rows) - MAX_SESSIONS)]:
        del rows[old]
    cfg["sessions"] = rows
    return _sign(cfg, sid, now + SESSION_SECONDS)


def token_valid(cfg: dict | None, token: str | None, now: float | None = None) -> bool:
    if not enabled(cfg):
        return False
    parts = _parts(cfg, token)
    return bool(parts) and parts[0] in (cfg.get("sessions") or {}) and parts[1] > (now if now is not None else time.time())


def should_renew(token: str, now: float | None = None) -> bool:
    now = now if now is not None else time.time()
    return int(token.split(".")[1]) - now < SESSION_SECONDS - RENEW_AFTER


def renew(cfg: dict, token: str, now: float | None = None) -> str:
    """Zelfde sessie, nieuwe vervaltijd. De aanroeper slaat cfg op."""
    now = int(now if now is not None else time.time())
    sid = token.split(".")[0]
    cfg["sessions"][sid].update(last_seen=now, expires=now + SESSION_SECONDS)
    return _sign(cfg, sid, now + SESSION_SECONDS)


def end_session(cfg: dict | None, token: str | None) -> bool:
    if not enabled(cfg) or not (parts := _parts(cfg, token)):
        return False
    return (cfg.get("sessions") or {}).pop(parts[0], None) is not None


def public_id(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()[:12]   # het echte id is een geheim en gaat niet naar de browser


def session_rows(cfg: dict | None, token: str | None, now: float | None = None) -> list[dict]:
    now = now if now is not None else time.time()
    mine = token.split(".")[0] if token else None
    rows = [{"id": public_id(k), "agent": v.get("agent") or "", "created": v["created"], "last_seen": v["last_seen"], "current": k == mine}
            for k, v in ((cfg or {}).get("sessions") or {}).items() if v["expires"] > now]
    return sorted(rows, key=lambda r: (not r["current"], -r["last_seen"]))


def revoke(cfg: dict, ident: str | None, token: str | None) -> int:
    """Eén sessie (ident) of, zonder ident, alle andere sessies dan die van deze browser."""
    mine = token.split(".")[0] if token else None
    rows = cfg.get("sessions") or {}
    gone = [k for k in rows if k != mine and (ident is None or public_id(k) == ident)]
    for k in gone:
        del rows[k]
    return len(gone)


def agent_label(ua: str) -> str:
    """Alleen het soort apparaat en de browser bewaren, niet de hele User-Agent."""
    ua = ua or ""
    device = next((n for p, n in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Macintosh", "Mac"),
                                  ("Windows", "Windows"), ("Linux", "Linux")) if p in ua), "")
    browser = next((n for p, n in (("Edg/", "Edge"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari")) if p in ua), "")
    return " · ".join(x for x in (device, browser) if x)


class Limiter:
    """Raden ontmoedigen: na MAX_FAILS foute pogingen per adres even niets meer proberen."""

    def __init__(self) -> None:
        self.fails: dict[str, list[float]] = {}

    def wait(self, ip: str, now: float | None = None) -> int:
        """Seconden die dit adres nog moet wachten (0 = mag)."""
        now = now if now is not None else time.time()
        recent = [t for t in self.fails.get(ip, []) if now - t < FAIL_WINDOW]
        if recent:
            self.fails[ip] = recent
        else:
            self.fails.pop(ip, None)
        return int(recent[0] + FAIL_WINDOW - now) + 1 if len(recent) >= MAX_FAILS else 0

    def failed(self, ip: str, now: float | None = None) -> None:
        if len(self.fails) > 1000:   # geen geheugen vullen met verzonnen adressen
            self.fails.clear()
        self.fails.setdefault(ip, []).append(now if now is not None else time.time())

    def reset(self, ip: str) -> None:
        self.fails.pop(ip, None)


def reset_file(data_dir: str) -> bool:
    """Haalt de inlog uit config.json. Schrijft in hetzelfde bestand, zodat eigenaar en rechten blijven staan."""
    path = Path(data_dir) / "config.json"
    cfg = json.loads(path.read_text())
    if not cfg.pop("auth", None):
        return False
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    return True


if __name__ == "__main__":
    if "--reset" not in sys.argv:
        sys.exit("Gebruik / usage: python -m app.auth --reset [data_dir]")
    args = [a for a in sys.argv[1:] if a != "--reset"]
    done = reset_file(args[0] if args else "/var/lib/unifi-sonar")
    print("Inlog verwijderd; herstart de service en haal de eenmalige code op met: journalctl -u unifi-sonar -n 20\n"
          "Login removed; restart the service and get the one-time code with: journalctl -u unifi-sonar -n 20" if done
          else "Er was geen inlog ingesteld. / No login was set.")
