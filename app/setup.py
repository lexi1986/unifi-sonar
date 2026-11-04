"""Verbindingstest voor de setup-wizard: adres opschonen, poorten proberen, inloggen en
een eerste meting doen, met begrijpelijke foutmeldingen."""
from __future__ import annotations

import ssl
from urllib.parse import urlsplit

import httpx

from .config import Settings
from .unifi_client import UnifiClient

UNIFI_OS_SERVER_PORT = 11443


def candidate_urls(address: str) -> list[str]:
    """'192.168.1.1' → ['https://192.168.1.1', 'https://192.168.1.1:11443'].
    Met een expliciete poort of schema wordt alleen dat adres geprobeerd."""
    a = address.strip().rstrip("/")
    if not a:
        return []
    explicit_scheme = "://" in a
    if not explicit_scheme:
        a = "https://" + a
    parts = urlsplit(a)
    base = f"{parts.scheme}://{parts.netloc}"
    if parts.port or explicit_scheme:
        return [base]
    return [base, f"{base}:{UNIFI_OS_SERVER_PORT}"]


def _explain(err: Exception, url: str) -> str:
    host = urlsplit(url).netloc
    if isinstance(err, httpx.ConnectTimeout) or isinstance(err, httpx.ReadTimeout):
        return f"{host} reageert niet (time-out)."
    if isinstance(err, httpx.ConnectError):
        cause = str(err)
        if isinstance(err.__cause__, ssl.SSLError) or "CERTIFICATE" in cause.upper():
            return f"Het certificaat van {host} wordt niet vertrouwd. Zet 'Certificaat controleren' uit."
        if "Name or service not known" in cause or "nodename nor servname" in cause:
            return f"De naam {host} kan niet worden gevonden. Probeer het IP-adres."
        return f"Geen verbinding met {host}."
    return f"{host}: {err}"


async def _reachable(url: str, verify: bool) -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(verify=verify, timeout=6, follow_redirects=False) as c:
            r = await c.get(url + "/")
        return r.status_code < 500, None
    except Exception as e:  # noqa: BLE001
        return False, _explain(e, url)


async def test_connection(address: str, api_key: str, username: str, password: str,
                          site: str, verify_tls: bool) -> dict:
    urls = candidate_urls(address)
    if not urls:
        return {"ok": False, "error": "Vul het adres van je UniFi-console in."}
    if not api_key and not (username and password):
        return {"ok": False, "error": "Vul een API-key in (of een gebruikersnaam en wachtwoord)."}

    errors = []
    url = None
    for u in urls:
        ok, why = await _reachable(u, verify_tls)
        if ok:
            url = u
            break
        errors.append(why)
    if not url:
        return {"ok": False, "error": errors[0],
                "hint": "Controleer het IP-adres. Draait je controller als UniFi OS Server (zelf gehost), "
                        "dan is de poort meestal 11443; die heb ik ook geprobeerd." if len(urls) > 1 else None}

    s = Settings(mode="live", controller_url=url, site=site or "default", api_key=api_key,
                 username=username, password=password, verify_tls=verify_tls)
    client = UnifiClient(s)
    try:
        sites = await client.sites()
        if sites and s.site not in {x["name"] for x in sites}:
            avail = ", ".join(f"'{x['name']}'" + (f" ({x['desc']})" if x.get("desc") else "") for x in sites)
            return {"ok": False, "url": url, "error": f"De site '{s.site}' bestaat niet op deze controller.",
                    "hint": f"Beschikbaar: {avail}. Gebruik de interne naam (de eerste)."}
        data = await client.fetch()
    except Exception:  # noqa: BLE001
        return {"ok": False, "url": url, **_classify(client.errors)}
    finally:
        await client.close()

    gw = next((d for d in data["devices"] if d["type"] == "gateway"), None)
    warnings = []
    if data["source"] == "integration":
        warnings.append("Met deze API-key werkt alleen de beperkte officiële API: je ziet apparaten en clients, "
                        "maar geen signaal, retries, kanaalbezetting of IPS-blokkades. Wil je alle details, ga dan terug en "
                        "vul onder 'Geavanceerd' een lokaal account met 'View Only'-rechten in.")
    if not data["devices"]:
        warnings.append(f"Ingelogd, maar de site '{s.site}' bevat geen apparaten. Klopt de sitenaam?")
    return {"ok": True, "url": url, "source": data["source"],
            "devices": len(data["devices"]), "clients": len(data["clients"]),
            "gateway": f"{gw['name']} ({gw['model']})" if gw else None, "warnings": warnings}


def _classify(errors: dict[str, Exception]) -> dict:
    codes = {getattr(getattr(e, "response", None), "status_code", None) for e in errors.values()}
    text = " ".join(str(e) for e in errors.values())
    if codes & {401, 403}:
        return {"error": "De controller weigert de inloggegevens.",
                "hint": "Controleer de API-key (UniFi Network → Instellingen → Control Plane → Integrations) "
                        "of de gebruikersnaam en het wachtwoord van het lokale account."}
    if "NoSiteContext" in text or codes & {400}:
        return {"error": "De site bestaat niet op deze controller.",
                "hint": "De standaardsite heet 'default'. Heb je meerdere sites, vul dan de interne naam in "
                        "(te zien in de URL van UniFi Network: …/manage/<site>/dashboard)."}
    if codes & {404}:
        return {"error": "Dit adres lijkt geen UniFi OS-console met de Network-app.",
                "hint": "Gebruik het adres van je UDM/UCG/Cloud Gateway of UniFi OS Server, niet van een switch of AP."}
    if not errors:
        return {"error": "Geen API-key of account ingevuld."}
    return {"error": "Verbinden lukte niet: " + "; ".join(f"{k}: {v}" for k, v in errors.items())[:300]}
