"""Kopieën van de UniFi Network-backups, zodat je er nog bij kunt als de controller zelf is gecrasht.

Sonar haalt de automatische backups (.unf) van de controller op en kan desgewenst elke dag zelf een verse laten maken.
Een .unf bevat je hele configuratie, ook wifi-wachtwoorden: de map is alleen leesbaar voor de service en downloaden
via het dashboard kan alleen als de inlog aanstaat.

Sonar versleutelt de kopieën met een openbare sleutel. De bijbehorende privésleutel staat alleen versleuteld op de
machine, met je wachtwoord en met een herstelcode. Sonar kan dus backups wegschrijven, maar pas weer openen als jij je
wachtwoord of herstelcode invult. Ben je allebei kwijt, dan zijn de bestaande backups niet meer te lezen.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .auth import normalize_code, random_code

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.unf$")
ENC = ".enc"
MAGIC = b"SONARBK1"
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}
KEEP = 30
STALE_DAYS, STALE_DAYS_DAILY = 40, 3     # UniFi maakt standaard soms maar één backup per maand


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _wrap(raw: bytes, secret: str) -> dict:
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    key = hashlib.scrypt(secret.encode(), salt=salt, **_SCRYPT)
    return {"salt": _b64(salt), "nonce": _b64(nonce), "data": _b64(AESGCM(key).encrypt(nonce, raw, None))}


def _unwrap(box: dict, secret: str) -> bytes | None:
    try:
        key = hashlib.scrypt(secret.encode(), salt=base64.b64decode(box["salt"]), **_SCRYPT)
        return AESGCM(key).decrypt(base64.b64decode(box["nonce"]), base64.b64decode(box["data"]), None)
    except (InvalidTag, KeyError, ValueError, TypeError):
        return None


def new_keys(password: str) -> tuple[dict, str]:
    """Een nieuw sleutelpaar en de herstelcode, die de gebruiker één keer te zien krijgt."""
    private = X25519PrivateKey.generate()
    raw, recovery = private.private_bytes_raw(), random_code(6)
    return {"public": _b64(private.public_key().public_bytes_raw()), "password": _wrap(raw, password),
            "recovery": _wrap(raw, normalize_code(recovery))}, recovery


def unlock(keys: dict | None, secret: str) -> bytes | None:
    """De privésleutel met wachtwoord of herstelcode; None als het niet klopt."""
    if not keys or not secret:
        return None
    return _unwrap(keys["password"], secret) or _unwrap(keys["recovery"], normalize_code(secret))


def rewrap(keys: dict, old: str, new: str) -> dict | None:
    """Het wachtwoord is gewijzigd: de privésleutel opnieuw inpakken. None als het oude wachtwoord hem niet opende."""
    raw = _unwrap(keys["password"], old)
    return {**keys, "password": _wrap(raw, new)} if raw else None


def _derive(shared: bytes, ephemeral: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=MAGIC + ephemeral).derive(shared)


def seal(public: str, data: bytes) -> bytes:
    eph = X25519PrivateKey.generate()
    eph_pub, nonce = eph.public_key().public_bytes_raw(), secrets.token_bytes(12)
    key = _derive(eph.exchange(X25519PublicKey.from_public_bytes(base64.b64decode(public))), eph_pub)
    return MAGIC + eph_pub + nonce + AESGCM(key).encrypt(nonce, data, MAGIC)


def unseal(raw_private: bytes, blob: bytes) -> bytes:
    if not blob.startswith(MAGIC):
        raise ValueError("not an encrypted backup")
    eph_pub, nonce, body = blob[8:40], blob[40:52], blob[52:]
    shared = X25519PrivateKey.from_private_bytes(raw_private).exchange(X25519PublicKey.from_public_bytes(eph_pub))
    return AESGCM(_derive(shared, eph_pub)).decrypt(nonce, body, MAGIC)


def folder(data_dir: str) -> Path:
    p = Path(data_dir) / "backups"
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)
    return p


def listing(data_dir: str) -> list[dict]:
    """Nieuwste eerst."""
    out = []
    for f in [*folder(data_dir).glob("*.unf"), *folder(data_dir).glob("*.unf" + ENC)]:
        st = f.stat()
        name = f.name.removesuffix(ENC)
        out.append({"name": name, "size": st.st_size, "ts": int(st.st_mtime), "encrypted": f.name.endswith(ENC),
                    "source": "sonar" if name.startswith("sonar_") else "auto"})
    return sorted(out, key=lambda x: -x["ts"])


def path_of(data_dir: str, name: str) -> Path | None:
    if not NAME_RE.match(name or ""):
        return None
    for p in (folder(data_dir) / (name + ENC), folder(data_dir) / name):
        if p.is_file():
            return p
    return None


def has(data_dir: str, name: str) -> bool:
    return path_of(data_dir, name) is not None


def store(data_dir: str, name: str, data: bytes, ts: float | None = None, public: str | None = None) -> None:
    """Eerst naar een tijdelijk bestand: een halve download mag nooit voor een backup doorgaan."""
    if not NAME_RE.match(name):
        raise ValueError(name)
    if not data:
        raise ValueError("empty backup")
    target = folder(data_dir) / (name + ENC if public else name)
    if public:
        data = seal(public, data)
    tmp = folder(data_dir) / (name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    if ts:
        os.utime(tmp, (ts, ts))
    os.replace(tmp, target)


def encrypt_existing(data_dir: str, public: str) -> int:
    """Bestaande onversleutelde kopieën alsnog versleutelen, met behoud van hun datum."""
    done = 0
    for b in [x for x in listing(data_dir) if not x["encrypted"]]:
        plain = folder(data_dir) / b["name"]
        store(data_dir, b["name"], plain.read_bytes(), b["ts"], public)
        plain.unlink()
        done += 1
    return done


def read(data_dir: str, name: str, raw_private: bytes | None) -> bytes | None:
    """De inhoud van een backup; None als hij versleuteld is en de sleutel ontbreekt."""
    path = path_of(data_dir, name)
    if path is None:
        raise FileNotFoundError(name)
    blob = path.read_bytes()
    if not path.name.endswith(ENC):
        return blob
    return unseal(raw_private, blob) if raw_private else None


def prune(data_dir: str, keep: int = KEEP) -> None:
    for b in listing(data_dir)[keep:]:
        if (p := path_of(data_dir, b["name"])):
            p.unlink(missing_ok=True)


def summary(data_dir: str, daily: bool, now: float | None = None) -> dict:
    rows = listing(data_dir)
    now = now if now is not None else time.time()
    newest = rows[0]["ts"] if rows else None
    limit = (STALE_DAYS_DAILY if daily else STALE_DAYS) * 86400
    return {"count": len(rows), "newest": newest, "daily": daily, "stale": newest is None or now - newest > limit}
