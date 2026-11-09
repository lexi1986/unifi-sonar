"""Passkeys als extra manier om in te loggen; het wachtwoord blijft altijd werken.

Een browser staat passkeys alleen toe op HTTPS (of localhost) en koppelt ze aan een hostnaam, nooit aan een IP-adres.
De controle van de handtekening doet de bibliotheek py_webauthn. Sonar bewaart alleen de publieke sleutel.
"""
from __future__ import annotations

import ipaddress
import json
import secrets
import time

from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor, ResidentKeyRequirement,
                                      UserVerificationRequirement)

RP_NAME = "UniFi Sonar"
USER_ID = b"unifi-sonar-admin"
TTL = 300
MAX_PASSKEYS = 20


def rp_id_for(hostname: str, scheme: str) -> str | None:
    """De naam waaraan een passkey vastzit, of None als passkeys hier niet kunnen."""
    h = (hostname or "").rstrip(".").lower()
    try:
        ipaddress.ip_address(h)
        return None
    except ValueError:
        pass
    if h == "localhost":
        return h
    return h if scheme == "https" and h else None


class Challenges:
    """Eenmalige uitdagingen; ze leven kort en alleen in het geheugen."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def add(self, kind: str, challenge: bytes, rp_id: str, origin: str, **extra) -> str:
        now = time.time()
        self.items = {k: v for k, v in self.items.items() if v["expires"] > now}
        if len(self.items) > 200:   # geen geheugen vullen met verzoeken die nooit afgemaakt worden
            self.items.clear()
        cid = secrets.token_urlsafe(16)
        self.items[cid] = {"kind": kind, "challenge": challenge, "rp_id": rp_id, "origin": origin, "expires": now + TTL, **extra}
        return cid

    def take(self, cid: str, kind: str, rp_id: str, origin: str) -> dict | None:
        c = self.items.pop(cid, None)
        if not c or c["kind"] != kind or c["expires"] < time.time() or c["rp_id"] != rp_id or c["origin"] != origin:
            return None
        return c


def _all(cfg: dict | None) -> list[dict]:
    return (cfg or {}).get("passkeys") or []


def public_list(cfg: dict | None, rp_id: str | None = None) -> list[dict]:
    return [{"id": p["id"], "name": p["name"], "created": p["created"], "last_used": p.get("last_used"),
             "here": rp_id is None or p["rp_id"] == rp_id} for p in _all(cfg)]


def begin_register(cfg: dict, store: Challenges, rp_id: str, origin: str, name: str) -> dict:
    opts = generate_registration_options(
        rp_id=rp_id, rp_name=RP_NAME, user_id=USER_ID, user_name="sonar", user_display_name=RP_NAME,
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.REQUIRED,
                                                               user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(p["id"])) for p in _all(cfg) if p["rp_id"] == rp_id])
    return {"id": store.add("register", opts.challenge, rp_id, origin, name=name), "options": json.loads(options_to_json(opts))}


def finish_register(store: Challenges, cid: str, credential: dict, rp_id: str, origin: str, now: int | None = None) -> dict | None:
    """De nieuwe passkey om op te slaan, of None als de uitdaging verlopen of onbekend is. Foute handtekeningen geven een exception."""
    c = store.take(cid, "register", rp_id, origin)
    if not c:
        return None
    v = verify_registration_response(credential=credential, expected_challenge=c["challenge"], expected_rp_id=rp_id,
                                     expected_origin=origin, require_user_verification=True)
    return {"id": bytes_to_base64url(v.credential_id), "public_key": bytes_to_base64url(v.credential_public_key),
            "sign_count": v.sign_count, "rp_id": rp_id, "name": c["name"], "created": now or int(time.time()), "last_used": None}


def begin_login(store: Challenges, rp_id: str, origin: str) -> dict:
    opts = generate_authentication_options(rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED)
    return {"id": store.add("login", opts.challenge, rp_id, origin), "options": json.loads(options_to_json(opts))}


def finish_login(cfg: dict, store: Challenges, cid: str, credential: dict, rp_id: str, origin: str, now: int | None = None) -> dict | None:
    """De bijgewerkte passkey bij succes, anders None (of een exception bij een foute handtekening)."""
    c = store.take(cid, "login", rp_id, origin)
    p = next((x for x in _all(cfg) if x["id"] == credential.get("id") and x["rp_id"] == rp_id), None)
    if not c or not p:
        return None
    v = verify_authentication_response(credential=credential, expected_challenge=c["challenge"], expected_rp_id=rp_id, expected_origin=origin,
                                       credential_public_key=base64url_to_bytes(p["public_key"]), credential_current_sign_count=p["sign_count"],
                                       require_user_verification=True)
    return {**p, "sign_count": v.new_sign_count, "last_used": now or int(time.time())}
