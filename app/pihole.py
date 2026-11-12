"""Pi-hole (versie 6): dezelfde gegevens als bij AdGuard Home, via de API van Pi-hole.

Alleen lezen, op het in- en uitloggen na. Sonar logt in met het wachtwoord of een app-wachtwoord, krijgt een sessie
en houdt die warm, zodat er niet elke minuut opnieuw ingelogd wordt (Pi-hole kent maar een beperkt aantal sessies).

Eén verschil met AdGuard Home: Pi-hole bewaart in het querylog niet welk adres bij een domein hoort. Namen bij
verbindingen die UniFi niet kan benoemen kan Sonar met alleen een Pi-hole dus niet aanvullen.
"""
from __future__ import annotations

import hashlib
import logging
import time

import httpx

from .i18n import L

log = logging.getLogger("sonar.pihole")

KIND, LABEL = "pihole", "Pi-hole"
# statussen waarbij Pi-hole de vraag zelf tegenhield (lijst, eigen regel) of een geblokkeerd antwoord doorgaf
BLOCKED = {"GRAVITY", "REGEX", "DENYLIST", "GRAVITY_CNAME", "REGEX_CNAME", "DENYLIST_CNAME", "EXTERNAL_BLOCKED_IP",
           "EXTERNAL_BLOCKED_NULL", "EXTERNAL_BLOCKED_NXRA", "EXTERNAL_BLOCKED_EDE15", "SPECIAL_DOMAIN"}
BY_LIST = {"GRAVITY", "GRAVITY_CNAME"}          # alleen dan wijst list_id naar een abonnementslijst
_SESSIONS: dict[tuple, dict] = {}               # per adres én wachtwoord: {"sid", "until"}


class AuthError(Exception):
    pass


def base_url(url: str) -> str:
    """Het adres van de beheerpagina, met of zonder /admin erachter."""
    u = (url or "").strip().rstrip("/")
    if u and "://" not in u:
        u = "http://" + u
    for tail in ("/admin/login", "/admin", "/api"):
        if u.lower().endswith(tail):
            u = u[: -len(tail)]
    return u.rstrip("/")


def to_item(q: dict) -> dict:
    """Eén regel uit het querylog van Pi-hole, in de vorm die Sonar van AdGuard kent."""
    status = (q.get("status") or "").upper()
    client = q.get("client") or {}
    reply = q.get("reply") or {}
    item = {
        "time": float(q.get("time") or 0), "client": client.get("ip") or "",
        "client_info": {"name": client.get("name") or ""},
        "question": {"name": q.get("domain") or "", "type": q.get("type")},
        "reason": "FilteredBlackList" if status in BLOCKED else "NotFilteredNotFound",
        "status": "SERVFAIL" if (reply.get("type") or "").upper() == "SERVFAIL" else "NOERROR",
        "answer": [],          # Pi-hole bewaart het antwoord niet
    }
    if status in BY_LIST and q.get("list_id") is not None:
        item["rules"] = [{"filter_list_id": q["list_id"]}]
    return item


class API:
    """Eén Pi-hole. De enige verzoeken die iets veranderen zijn in- en uitloggen."""

    kind, label = KIND, LABEL

    def __init__(self, inst: dict) -> None:
        self.url = base_url(inst.get("url", ""))
        self.name = inst.get("name") or self.url.split("://")[-1]
        self.password = inst.get("password") or ""
        self.verify = bool(inst.get("verify_tls"))
        # een sessie hoort bij dit adres met dit wachtwoord: een ander wachtwoord mag er nooit op meeliften
        self._key = (self.url, hashlib.sha256(self.password.encode()).hexdigest()[:16])

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(verify=self.verify, timeout=8, follow_redirects=False)

    # ---- sessie
    async def _login(self, http) -> str | None:
        if not self.password:
            return None                      # zonder wachtwoord laat Pi-hole iedereen toe, of het verzoek geeft straks 401
        try:
            r = await http.post(self.url + "/api/auth", json={"password": self.password})
        except httpx.HTTPError as e:
            raise RuntimeError(L(f"geen verbinding: {type(e).__name__}", f"no connection: {type(e).__name__}")) from None
        try:
            s = (r.json() or {}).get("session") or {}
        except ValueError:
            raise RuntimeError(L("geen Pi-hole versie 6 op dit adres", "no Pi-hole version 6 at this address")) from None
        if r.status_code == 429:
            raise AuthError(L("Pi-hole weigert nu nieuwe aanmeldingen (te veel pogingen of geen vrije sessie); probeer het over een paar minuten opnieuw",
                              "Pi-hole refuses new logins right now (too many attempts or no free session); try again in a few minutes"))
        if not s.get("valid"):
            if s.get("totp"):
                raise AuthError(L("deze Pi-hole vraagt een extra code (2FA): maak in Pi-hole een app-wachtwoord en vul dat hier in",
                                  "this Pi-hole asks for an extra code (2FA): create an app password in Pi-hole and enter that here"))
            raise AuthError(L("inloggen geweigerd: controleer het wachtwoord", "login refused: check the password"))
        sid = s.get("sid")
        _SESSIONS[self._key] = {"sid": sid, "until": time.time() + max(30, int(s.get("validity") or 300)) - 20}
        return sid

    async def _sid(self, http) -> str | None:
        s = _SESSIONS.get(self._key)
        if s and s["until"] > time.time():
            return s["sid"]
        return await self._login(http)

    async def logout(self) -> None:
        """Bij het weghalen of wijzigen van deze Pi-hole: de sessie teruggeven."""
        s = _SESSIONS.pop(self._key, None)
        if not s or not s.get("sid"):
            return
        try:
            async with self.client() as http:
                await http.delete(self.url + "/api/auth", headers={"X-FTL-SID": s["sid"]})
        except httpx.HTTPError:
            pass

    async def get(self, http, path: str, **params):
        for attempt in (0, 1):
            sid = await self._sid(http)
            r = await http.get(self.url + path, params=params or None, headers={"X-FTL-SID": sid} if sid else None)
            if r.status_code == 401 and attempt == 0 and self.password:
                _SESSIONS.pop(self._key, None)        # sessie verlopen: één keer opnieuw inloggen
                continue
            break
        if r.status_code in (401, 403):
            raise AuthError(L("inloggen geweigerd: controleer het wachtwoord", "login refused: check the password")
                            if self.password else L("deze Pi-hole vraagt een wachtwoord", "this Pi-hole asks for a password"))
        if r.status_code == 404:
            raise RuntimeError(L("geen Pi-hole versie 6 op dit adres (versie 5 heeft deze API niet)",
                                 "no Pi-hole version 6 at this address (version 5 doesn't have this API)"))
        r.raise_for_status()
        s = _SESSIONS.get(self._key)
        if s:
            s["until"] = time.time() + 280            # elk verzoek verlengt de sessie
        try:
            return r.json()
        except ValueError:
            raise RuntimeError(L("geen Pi-hole versie 6 op dit adres", "no Pi-hole version 6 at this address")) from None

    # ---- wat Sonar nodig heeft, in dezelfde vorm als bij AdGuard
    async def status(self, http) -> dict:
        v = await self.get(http, "/api/info/version")
        b = await self.get(http, "/api/dns/blocking")
        ver = ((v.get("version") or {}).get("core") or {}).get("local") or {}
        ftl = ((v.get("version") or {}).get("ftl") or {}).get("local") or {}
        state = b.get("blocking")
        return {"version": ver.get("version") or ftl.get("version"), "running": True,
                "protection": None if state in (None, "unknown") else state == "enabled" or state is True}

    async def settings(self, http) -> tuple[dict[int, str], dict]:
        ls = (await self.get(http, "/api/lists")).get("lists") or []
        dns = ((await self.get(http, "/api/config/dns")).get("config") or {}).get("dns") or {}
        try:
            doms = (await self.get(http, "/api/domains")).get("domains") or []
        except (RuntimeError, httpx.HTTPError):
            doms = []
        block = [x for x in ls if (x.get("type") or "block") == "block"]
        names = {x["id"]: " ".join(filter(None, [x.get("comment"), x.get("address")])) for x in block if "id" in x}
        rewrites = []
        for h in dns.get("hosts") or []:
            ip, _, host = str(h).strip().partition(" ")
            if host:
                rewrites.append(f"{host.strip()} → {ip}")
        for c in dns.get("cnameRecords") or []:
            src, _, rest = str(c).partition(",")
            if rest:
                rewrites.append(f"{src.strip()} → {rest.split(',')[0].strip()}")
        return names, {
            "rewrites": sorted(rewrites), "lists": sorted(x.get("address") or "" for x in block if x.get("enabled", True)),
            "upstreams": sorted(str(u) for u in dns.get("upstreams") or [] if u),
            "rules": len([d for d in doms if d.get("enabled", True)])}

    async def stats(self, http) -> dict:
        d = (await self.get(http, "/api/stats/summary")).get("queries") or {}
        ups = (await self.get(http, "/api/stats/upstreams")).get("upstreams") or []
        real = [u for u in ups if (u.get("port") or 0) > 0 and (u.get("statistics") or {}).get("response")]
        real.sort(key=lambda u: -(u.get("count") or 0))
        return {"queries": d.get("total") or 0, "blocked": d.get("blocked") or 0, "avg_ms": None,
                "upstreams": [{"name": f"{u.get('name') or u.get('ip')}#{u.get('port')}", "avg_ms": round(u["statistics"]["response"] * 1000, 1)}
                              for u in real[:5]]}

    async def log(self, http, since: float, page: int, max_pages: int) -> tuple[list[dict], str | None]:
        """Nieuwe regels na 'since', nieuwste eerst. Tweede waarde: een opmerking als Pi-hole gegevens verbergt."""
        out: list[dict] = []
        cursor = None
        hidden = False
        for n in range(max_pages):
            params = {"from": since, "length": page, "start": n * page}
            if cursor is not None:
                params["cursor"] = cursor
            d = await self.get(http, "/api/queries", **params)
            rows = d.get("queries") or []
            if cursor is None:
                cursor = d.get("cursor")
            for q in rows:
                if float(q.get("time") or 0) <= since:
                    continue
                if (q.get("domain") or "") == "hidden" or ((q.get("client") or {}).get("ip") or "") in ("0.0.0.0", "::"):
                    hidden = True
                out.append(to_item(q))
            if len(rows) < page or cursor is None:
                break
        note = L("Pi-hole verbergt domeinen of apparaten (privacy-niveau hoger dan 0), dus Sonar kan ze niet aan apparaten koppelen",
                 "Pi-hole hides domains or clients (privacy level above 0), so Sonar can't link them to devices") if hidden else None
        return out, note

    async def test(self) -> dict:
        async with self.client() as http:
            st = await self.status(http)
            items, note = await self.log(http, time.time() - 3600, 1, 1)
        return {"ok": True, "version": st.get("version"), "protection": st.get("protection"), "log": bool(items), "note": note}
