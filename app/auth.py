"""Optionele inlog voor het dashboard: één wachtwoord, ingesteld onder Instellingen → Toegang.

Het wachtwoord wordt alleen als scrypt-hash bewaard. Een sessie is een ondertekende cookie (HMAC) met een vervaldatum;
wie het wachtwoord wijzigt, krijgt een nieuw geheim, waardoor alle bestaande sessies vervallen.

Wachtwoord kwijt? Op de machine zelf:  cd /opt/unifi-sonar && .venv/bin/python -m app.auth --reset
en daarna de service herstarten.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sys
import time
from pathlib import Path

COOKIE = "sonar_session"
SESSION_SECONDS = 90 * 86400
RENEW_AFTER = 86400          # een dag na uitgifte krijgt de browser een verse cookie (blijft dus ingelogd zolang hij komt)
MIN_LENGTH = 8
MAX_FAILS, FAIL_WINDOW = 5, 300
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


def _mac(cfg: dict, expires: str) -> str:
    return hmac.new(cfg["secret"].encode(), expires.encode(), hashlib.sha256).hexdigest()


def make_token(cfg: dict, now: float | None = None) -> str:
    expires = str(int((now if now is not None else time.time()) + SESSION_SECONDS))
    return f"{expires}.{_mac(cfg, expires)}"


def token_valid(cfg: dict | None, token: str | None, now: float | None = None) -> bool:
    if not enabled(cfg) or not token or "." not in token:
        return False
    expires, mac = token.split(".", 1)
    if not expires.isdigit() or not hmac.compare_digest(_mac(cfg, expires), mac):
        return False
    return int(expires) > (now if now is not None else time.time())


def should_renew(token: str, now: float | None = None) -> bool:
    now = now if now is not None else time.time()
    return int(token.split(".", 1)[0]) - now < SESSION_SECONDS - RENEW_AFTER


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
    print("Inlog verwijderd; herstart de service. / Login removed; restart the service." if done
          else "Er was geen inlog ingesteld. / No login was set.")
