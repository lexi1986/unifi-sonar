"""Beveiligingsadviezen van Ubiquiti, vergeleken met de firmware van je eigen apparaten.

Ubiquiti publiceert genummerde 'Security Advisory Bulletins' met per kwetsbaarheid de getroffen producten
("UniFi Access Points (Version 6.6.55 and earlier)") en de versie met de oplossing ("Update … to Version 6.6.65
or later"). Sonar haalt de openbare RSS-feed op (er gaat niets van jouw netwerk mee) en kijkt of een van jouw
apparaten nog een getroffen versie draait.
"""
from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEED = "https://community.ui.com/rss/releases/Security/f3f45fa2-1784-4594-b48d-28baf317b208"
_AFFECTED = re.compile(r"([A-Za-z0-9][^\n():]*?)\s*\((?:[Vv]ersions?)\s+([\d][\d.]*)\s+and\s+(?:earlier|older|below)\)")
_FIXED = re.compile(r"(?:Update|Upgrade)\s+(?:your\s+|the\s+)?(.+?)\s+to\s+(?:[Vv]ersion\s+)?([\d][\d.]*)\s+or\s+later")
_SCORE = re.compile(r"Base Score:\s*([\d.]+)")
_CVE = re.compile(r"CVE-\d{4}-\d+")


def _text(desc: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", desc or "", flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", t)


def parse(xml_text: str) -> list[dict]:
    """De RSS-feed → [{id, title, url, ts, summaries: [{summary, affected: [(product, max)], fixed: [(product, versie)],
    score, cves}]}]."""
    out = []
    root = ET.fromstring(xml_text)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        num = re.search(r"(\d{2,4})\s*$", title)
        try:
            ts = int(parsedate_to_datetime(it.findtext("pubDate") or "").timestamp())
        except (TypeError, ValueError):
            ts = 0
        text = _text(it.findtext("description") or "")
        parts = re.split(r"Summary \d+ of \d+", text)
        parts = parts[1:] if len(parts) > 1 else parts
        summaries = []
        for p in parts:
            aff = p.split("Affected Products:", 1)[-1].split("Mitigation:", 1)[0] if "Affected Products:" in p else ""
            mit = p.split("Mitigation:", 1)[-1].split("Impact:", 1)[0] if "Mitigation:" in p else ""
            first = next((s.strip() for s in p.split("\n") if len(s.strip()) > 40), "")
            sc = _SCORE.search(p)
            summaries.append({"summary": first[:400],
                              "affected": [(a.strip(), m.rstrip(".")) for a, m in _AFFECTED.findall(aff)],
                              "fixed": [(a.strip(), v.rstrip(".")) for a, v in _FIXED.findall(mit)],
                              "score": float(sc.group(1)) if sc else None, "cves": sorted(set(_CVE.findall(p)))})
        out.append({"id": num.group(1) if num else title, "title": title, "url": (it.findtext("link") or "").strip(),
                    "ts": ts, "summaries": summaries})
    return out


async def fetch(http) -> list[dict]:
    r = await http.get(FEED, headers={"User-Agent": "UniFi-Sonar", "Accept": "application/rss+xml"}, timeout=20)
    r.raise_for_status()
    return parse(r.text)


# ------------------------------------------------------------------ vergelijken
def _kind(product: str) -> str | None:
    """Soort product in een advies. Gateways splitsen we: een UniFi Gateway (UXG) is een andere productlijn
    dan een console (Dream Machine, Dream Router, Cloud Gateway)."""
    p = product.lower()
    if "network application" in p or "network server" in p or re.search(r"\bunifi network\b", p):
        return "network"
    if "access point" in p or re.search(r"\buap\b", p):
        return "ap"
    if ("switch" in p or re.search(r"\busw\b", p)) and "edge" not in p and "solar" not in p:
        return "switch"
    if "unifi gateway" in p or re.search(r"\buxg\b", p):
        return "gw-uxg"
    if any(k in p for k in ("dream machine", "dream router", "cloud gateway", "udm", "ucg", "udr")):
        return "gw-console"
    return None


def _ver(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def affected(ours: str, max_version: str) -> bool:
    a, b = _ver(ours), _ver(max_version)
    return bool(a and b) and a[:len(b)] <= b


def affected_any(ours: str, maxima: list[str]) -> bool:
    """Meerdere versielijnen (bijv. 9.0.114, 10.1.85 en 10.2.93): vergelijk met de lijn van jouw versie."""
    a = _ver(ours)
    if not a:
        return False
    same = [m for m in maxima if _ver(m)[:2] == a[:2]] or [m for m in maxima if _ver(m)[:1] == a[:1]] or maxima
    return any(affected(ours, m) for m in same)


def _gw_kind(model: str) -> str:
    return "gw-uxg" if (model or "").upper().startswith("UXG") else "gw-console"


def inventory(devices: list[dict], network_version: str | None) -> list[dict]:
    inv = [{"kind": _gw_kind(d.get("model_code") or d.get("model") or "") if d["type"] == "gateway" else d["type"],
            "name": d["name"], "version": d.get("version") or ""} for d in devices
           if d.get("type") in ("ap", "switch", "gateway")]
    if network_version and network_version != "demo":
        inv.append({"kind": "network", "name": "UniFi Network", "version": network_version})
    return inv


def match(items: list[dict], inv: list[dict]) -> list[dict]:
    """Welke adviezen gaan over een product dat jij hebt, met een versie die nog getroffen is."""
    out = []
    for a in items:
        for s in a["summaries"]:
            maxima: dict[str, list[tuple[str, str]]] = {}
            for product, maxv in s["affected"]:
                if _kind(product):
                    maxima.setdefault(_kind(product), []).append((product, maxv))
            for kind, entries in maxima.items():
                hit = [x for x in inv if x["kind"] == kind and affected_any(x["version"], [m for _, m in entries])]
                if not hit:
                    continue
                product, maxv = entries[0]
                fixed = next((v for p, v in s["fixed"] if _kind(p) == kind), None)
                out.append({"id": a["id"], "title": a["title"], "url": a["url"], "ts": a["ts"], "product": product,
                            "max": maxv, "fixed": fixed, "score": s["score"], "cves": s["cves"], "summary": s["summary"],
                            "devices": [{"name": x["name"], "version": x["version"]} for x in hit]})
    return out


def summary_list(items: list[dict], inv: list[dict], limit: int = 8) -> list[dict]:
    """Voor de pagina Beveiliging: de nieuwste adviezen, met of ze jou raken."""
    hits = {m["id"] for m in match(items, inv)}
    out = []
    for a in sorted(items, key=lambda x: -x["ts"])[:limit]:
        products = sorted({p for s in a["summaries"] for p, _ in s["affected"]})
        scores = [s["score"] for s in a["summaries"] if s["score"] is not None]
        out.append({"id": a["id"], "title": a["title"], "url": a["url"], "ts": a["ts"], "products": products,
                    "score": max(scores) if scores else None, "affects": a["id"] in hits})
    return out


def demo(now: int | None = None) -> list[dict]:
    """Voor de demomodus: drie verzonnen adviezen, waarvan één de demo-AP's raakt."""
    now = now or int(time.time())
    return [
        {"id": "073", "title": "Security Advisory Bulletin 073 (demo)", "url": "https://community.ui.com/releases", "ts": now - 3 * 86400,
         "summaries": [{"summary": "A malicious actor with access to the network could exploit an improper input validation "
                                   "vulnerability in UniFi Access Points to execute commands.",
                        "affected": [("UniFi Access Points", "6.6.77")], "fixed": [("UniFi Access Points", "6.7.10")],
                        "score": 8.8, "cves": ["CVE-2026-00000"]}]},
        {"id": "072", "title": "Security Advisory Bulletin 072 (demo)", "url": "https://community.ui.com/releases", "ts": now - 9 * 86400,
         "summaries": [{"summary": "WiFiman Desktop could expose information about the host device.",
                        "affected": [("WiFiman Desktop", "1.1.3")], "fixed": [("WiFiman Desktop", "1.3.0")], "score": 7.5, "cves": []}]},
        {"id": "071", "title": "Security Advisory Bulletin 071 (demo)", "url": "https://community.ui.com/releases", "ts": now - 30 * 86400,
         "summaries": [{"summary": "UniFi Switches could allow a denial of service.",
                        "affected": [("UniFi Switches", "6.9.0")], "fixed": [("UniFi Switches", "7.0.1")], "score": 5.3, "cves": []}]},
    ]
