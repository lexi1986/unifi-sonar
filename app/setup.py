"""Verbindingstest voor de setup-wizard: adres opschonen, poorten proberen, inloggen en
een eerste meting doen, met begrijpelijke foutmeldingen."""
from __future__ import annotations

import ssl
from urllib.parse import urlsplit

import httpx

from .config import Settings
from .i18n import L
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
        return L(f"{host} reageert niet (time-out).", f"{host} does not respond (time-out).")
    if isinstance(err, httpx.ConnectError):
        cause = str(err)
        if isinstance(err.__cause__, ssl.SSLError) or "CERTIFICATE" in cause.upper():
            return L(f"Het certificaat van {host} wordt niet vertrouwd. Zet 'Certificaat controleren' uit.",
                     f"The certificate of {host} is not trusted. Turn off 'Verify certificate'.")
        if "Name or service not known" in cause or "nodename nor servname" in cause:
            return L(f"De naam {host} kan niet worden gevonden. Probeer het IP-adres.",
                     f"The name {host} cannot be found. Try the IP address.")
        return L(f"Geen verbinding met {host}.", f"No connection to {host}.")
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
        return {"ok": False, "error": L("Vul het adres van je UniFi-console in.", "Enter the address of your UniFi console.")}
    if not api_key and not (username and password):
        return {"ok": False, "error": L("Vul een API-key in (of een gebruikersnaam en wachtwoord).",
                                        "Enter an API key (or a username and password).")}

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
                "hint": L("Controleer het IP-adres. Draait je controller als UniFi OS Server (zelf gehost), "
                          "dan is de poort meestal 11443; die heb ik ook geprobeerd.",
                          "Check the IP address. If your controller runs as UniFi OS Server (self-hosted), "
                          "the port is usually 11443; that was tried too.") if len(urls) > 1 else None}

    s = Settings(mode="live", controller_url=url, site=site or "default", api_key=api_key,
                 username=username, password=password, verify_tls=verify_tls)
    client = UnifiClient(s)
    try:
        sites = await client.sites()
        if sites and s.site not in {x["name"] for x in sites}:
            avail = ", ".join(f"'{x['name']}'" + (f" ({x['desc']})" if x.get("desc") else "") for x in sites)
            return {"ok": False, "url": url, "error": L(f"De site '{s.site}' bestaat niet op deze controller.",
                                                         f"The site '{s.site}' does not exist on this controller."),
                    "hint": L(f"Beschikbaar: {avail}. Gebruik de interne naam (de eerste).",
                              f"Available: {avail}. Use the internal name (the first one).")}
        data = await client.fetch()
    except Exception:  # noqa: BLE001
        return {"ok": False, "url": url, **_classify(client.errors)}
    finally:
        await client.close()

    gw = next((d for d in data["devices"] if d["type"] == "gateway"), None)
    warnings = []
    if data["source"] == "integration":
        warnings.append(L("Met deze API-key werkt alleen de beperkte officiële API: je ziet apparaten en clients, "
                          "maar geen signaal, retries, kanaalbezetting of IPS-blokkades. Wil je alle details, ga dan terug en "
                          "vul onder 'Geavanceerd' een lokaal account met 'View Only'-rechten in.",
                          "With this API key only the limited official API works: you see devices and clients, but no "
                          "signal, retries, channel utilization or IPS blocks. For all details, go back and enter a local "
                          "account with 'View Only' rights under 'Advanced'."))
    if not data["devices"]:
        warnings.append(L(f"Ingelogd, maar de site '{s.site}' bevat geen apparaten. Klopt de sitenaam?",
                          f"Logged in, but the site '{s.site}' has no devices. Is the site name right?"))
    return {"ok": True, "url": url, "source": data["source"],
            "devices": len(data["devices"]), "clients": len(data["clients"]),
            "gateway": f"{gw['name']} ({gw['model']})" if gw else None, "warnings": warnings}


def _classify(errors: dict[str, Exception]) -> dict:
    codes = {getattr(getattr(e, "response", None), "status_code", None) for e in errors.values()}
    text = " ".join(str(e) for e in errors.values())
    if codes & {401, 403}:
        return {"error": L("De controller weigert de inloggegevens.", "The controller rejects the credentials."),
                "hint": L("Controleer de API-key (UniFi Network → Instellingen → Control Plane → Integrations) "
                          "of de gebruikersnaam en het wachtwoord van het lokale account.",
                          "Check the API key (UniFi Network → Settings → Control Plane → Integrations) "
                          "or the username and password of the local account.")}
    if "NoSiteContext" in text or codes & {400}:
        return {"error": L("De site bestaat niet op deze controller.", "The site does not exist on this controller."),
                "hint": L("De standaardsite heet 'default'. Heb je meerdere sites, vul dan de interne naam in "
                          "(te zien in de URL van UniFi Network: …/manage/<site>/dashboard).",
                          "The default site is called 'default'. If you have several sites, enter the internal name "
                          "(visible in the UniFi Network URL: …/manage/<site>/dashboard).")}
    if codes & {404}:
        return {"error": L("Dit adres lijkt geen UniFi OS-console met de Network-app.",
                           "This address does not look like a UniFi OS console with the Network app."),
                "hint": L("Gebruik het adres van je UDM/UCG/Cloud Gateway of UniFi OS Server, niet van een switch of AP.",
                          "Use the address of your UDM/UCG/Cloud Gateway or UniFi OS Server, not of a switch or AP.")}
    if not errors:
        return {"error": L("Geen API-key of account ingevuld.", "No API key or account entered.")}
    return {"error": L("Verbinden lukte niet: ", "Connecting failed: ") + "; ".join(f"{k}: {v}" for k, v in errors.items())[:300]}
