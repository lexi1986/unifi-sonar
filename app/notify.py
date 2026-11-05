"""Meldingen naar buiten: Home Assistant, ntfy, Discord, Slack of een eigen webhook.

Werking per kanaal:
  * een melding gaat pas weg als hij `delay_min` minuten openstaat (geen alarm bij één uitschieter);
  * daarna één bericht, plus een nieuw bericht als hij ernstiger wordt;
  * 'opgelost' pas als hij `delay_min` minuten weg is (geen heen-en-weer bij flapperen);
  * genegeerde meldingen en meldingen onder de minimale ernst worden overgeslagen;
  * komen er veel tegelijk binnen, dan wordt het één bundelbericht.
De verzendstatus staat in de database, zodat een herstart niet alles opnieuw verstuurt.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

KINDS = ("homeassistant", "ntfy", "discord", "slack", "webhook")
RANK = {"critical": 0, "warning": 1, "info": 2}
LABEL = {"critical": "Kritiek", "warning": "Waarschuwing", "info": "Info"}
COLOR = {"critical": 0xFB7185, "warning": 0xFFBE5C, "info": 0x39D8F4, "ok": 0x48E0B4}
BUNDLE_AT = 4               # vanaf zoveel nieuwe meldingen in één keer: bundelen
CONTROLLER_DOWN_AFTER = 300  # seconden zonder verbinding voordat we waarschuwen
DEFAULTS = {"channels": [], "delay_min": 5, "digest_hour": None, "base_url": ""}


def config(settings) -> dict:
    cfg = {**DEFAULTS, **(settings.notify or {})}
    cfg["channels"] = [c for c in cfg.get("channels") or [] if isinstance(c, dict)]
    return cfg


def mask(url: str) -> str:
    """Toon genoeg van een webhook-adres om hem te herkennen, niet genoeg om hem te gebruiken."""
    if not url:
        return ""
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}/…{url[-4:]}" if p.netloc else "…" + url[-4:]


def new_id() -> str:
    return secrets.token_hex(4)


def _ntfy_target(url: str) -> tuple[str, str]:
    p = urlsplit(url)
    topic = p.path.strip("/").split("/")[-1]
    return f"{p.scheme}://{p.netloc}", topic


class Notifier:
    def __init__(self, settings, db, http: httpx.AsyncClient | None = None):
        self.s = settings
        self.db = db
        self.http = http or httpx.AsyncClient(timeout=10, follow_redirects=True)
        self.status: dict[str, dict] = {}        # per kanaal: laatste succes/fout (voor de instellingenpagina)
        self._down_since: float | None = None
        self._down_sent = False

    async def close(self) -> None:
        await self.http.aclose()

    # ------------------------------------------------------------------ verzenden
    def _payload(self, ch: dict, msg: dict) -> tuple[str, dict, dict]:
        """(url, json, headers) voor één bericht in het formaat van het kanaal."""
        kind, url = ch.get("kind", "webhook"), ch["url"]
        sev = msg.get("severity", "info")
        text = msg["text"]
        link = msg.get("url") or ""
        if kind == "ntfy":
            base, topic = _ntfy_target(url)
            prio = {"critical": 5, "warning": 4, "info": 3, "ok": 2}.get(sev, 3)
            tags = {"critical": ["rotating_light"], "warning": ["warning"], "ok": ["white_check_mark"]}.get(sev, ["information_source"])
            body = {"topic": topic, "title": msg["title"], "message": text, "priority": prio, "tags": tags}
            if link:
                body["click"] = link
            headers = {"Authorization": f"Bearer {ch['token']}"} if ch.get("token") else {}
            return base, body, headers
        if kind == "discord":
            embed = {"title": msg["title"][:256], "description": text[:4000], "color": COLOR.get(sev, COLOR["info"])}
            if link:
                embed["url"] = link
            return url, {"username": "UniFi Sonar", "embeds": [embed]}, {}
        if kind == "slack":
            return url, {"text": f"*{msg['title']}*\n{text}" + (f"\n<{link}|Open UniFi Sonar>" if link else "")}, {}
        # Home Assistant (webhook-trigger) en algemene webhooks: gestructureerde JSON
        body = {"source": "unifi-sonar", "event": msg["event"], "severity": sev, "title": msg["title"],
                "message": text, "url": link, "ts": int(time.time())}
        body.update(msg.get("data") or {})
        return url, body, {}

    async def send(self, ch: dict, msg: dict) -> None:
        url, body, headers = self._payload(ch, msg)
        last: Exception | None = None
        for attempt in range(3):
            try:
                r = await self.http.post(url, json=body, headers=headers)
                if r.status_code < 300:
                    self.status[ch["id"]] = {"ok": int(time.time()), "error": None}
                    return
                last = RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
                if r.status_code < 500 and r.status_code != 429:
                    break   # verkeerde URL/token: opnieuw proberen helpt niet
            except httpx.HTTPError as e:
                last = e
            await asyncio.sleep(1 + attempt * 2)
        self.status[ch["id"]] = {**self.status.get(ch["id"], {}), "error": str(last), "error_ts": int(time.time())}
        raise RuntimeError(str(last))

    async def _safe_send(self, ch: dict, msg: dict) -> bool:
        try:
            await self.send(ch, msg)
            return True
        except Exception as e:  # noqa: BLE001 – een kapot kanaal mag de meting niet stoppen
            log.warning("Melding via %s mislukt: %s", ch.get("kind"), e)
            return False

    # ------------------------------------------------------------------ berichten
    def _link(self, path: str = "") -> str:
        base = (config(self.s).get("base_url") or "").rstrip("/")
        return f"{base}/#/{path}" if base else ""

    def _issue_msg(self, i: dict, event: str) -> dict:
        prefix = {"opened": "", "escalated": "Ernstiger: ", "resolved": "Opgelost: "}[event]
        text = i["detail"] if event == "resolved" else f"{i['detail']}\n\nAdvies: {i['advice']}"
        target = f"clients/{i['client_mac']}" if i.get("client_mac") else "issues"
        return {"event": event, "severity": "ok" if event == "resolved" else i["severity"],
                "title": prefix + i["title"], "text": text, "url": self._link(target),
                "data": {"key": i["key"], "category": i["category"], "issue_severity": i["severity"],
                         "device_mac": i.get("device_mac"), "client_mac": i.get("client_mac")}}

    def _bundle_msg(self, items: list[dict]) -> dict:
        worst = min((i["severity"] for i in items), key=RANK.get)
        lines = [f"• {LABEL[i['severity']]}: {i['title']}" for i in items[:12]]
        if len(items) > 12:
            lines.append(f"… en nog {len(items) - 12}")
        return {"event": "bundle", "severity": worst, "title": f"{len(items)} nieuwe meldingen in je netwerk",
                "text": "\n".join(lines), "url": self._link("issues"),
                "data": {"keys": [i["key"] for i in items]}}

    def test_msg(self) -> dict:
        return {"event": "test", "severity": "info", "title": "Testbericht van UniFi Sonar",
                "text": "Als je dit leest, komen meldingen goed aan.", "url": self._link("issues")}

    # ------------------------------------------------------------------ elke meting
    def baseline(self, ch_id: str, issues: list[dict]) -> None:
        """Nieuw kanaal: wat nu al openstaat niet alsnog versturen."""
        self.db.drop_notified(ch_id)
        now = int(time.time())
        for i in issues:
            if not i.get("group") and not i.get("muted"):
                self.db.set_notified(ch_id, i["key"], i["severity"], now, announced=False)

    async def process(self, snap: dict, ts: int) -> None:
        cfg = config(self.s)
        if self._down_sent:
            self._down_sent = False
            await self._broadcast(cfg, {"event": "controller_up", "severity": "ok", "title": "UniFi-controller weer bereikbaar",
                                        "text": "UniFi Sonar meet weer.", "url": self._link()})
        self._down_since = None
        chans = [c for c in cfg["channels"] if c.get("enabled", True) and c.get("url")]
        if not chans:
            return
        delay = max(0, int(cfg.get("delay_min") or 0)) * 60
        first = self.db.first_seen()
        top = {i["key"]: i for i in snap["issues"] if not i.get("group") and not i.get("muted")}
        for ch in chans:
            st = self.status.get(ch["id"]) or {}
            if st.get("error") and time.time() - st.get("error_ts", 0) < 300:
                continue   # kanaal faalde net: even met rust laten
            sent = self.db.notified(ch["id"])
            limit = RANK.get(ch.get("min_severity", "warning"), 1)
            fresh, escalated = [], []
            for k, i in top.items():
                if RANK[i["severity"]] > limit or ts - first.get(k, ts) < delay:
                    continue
                prev = sent.get(k)
                if prev is None:
                    fresh.append(i)
                elif prev["gone_ts"]:
                    self.db.set_notified_gone(ch["id"], k, None)   # was even weg, nu terug: stil doorgaan
                elif RANK[i["severity"]] < RANK.get(prev["severity"], 2):
                    escalated.append(i)
            msgs = ([self._bundle_msg(fresh)] if len(fresh) >= BUNDLE_AT else [self._issue_msg(i, "opened") for i in fresh])
            msgs += [self._issue_msg(i, "escalated") for i in escalated]
            ok = True
            for m in msgs:
                ok = await self._safe_send(ch, m) and ok
            if ok:
                for i in fresh + escalated:
                    self.db.set_notified(ch["id"], i["key"], i["severity"], ts)
            # verdwenen of genegeerd
            stored = {i["key"]: i for i in snap["issues"]}
            for k, prev in sent.items():
                if k in top:
                    continue
                if stored.get(k, {}).get("muted") or not prev["announced"]:
                    self.db.drop_notified(ch["id"], k)
                elif not prev["gone_ts"]:
                    self.db.set_notified_gone(ch["id"], k, ts)
                elif ts - prev["gone_ts"] >= delay:
                    if ch.get("resolved", True):
                        old = self.db.issue(k) or {"key": k, "title": k, "detail": "", "advice": "", "category": "",
                                                   "severity": prev["severity"]}
                        if not await self._safe_send(ch, self._issue_msg(old, "resolved")):
                            continue
                    self.db.drop_notified(ch["id"], k)
        await self._digest(cfg, snap, ts)

    async def _broadcast(self, cfg: dict, msg: dict) -> None:
        for ch in cfg["channels"]:
            if ch.get("enabled", True) and ch.get("url"):
                await self._safe_send(ch, msg)

    async def _digest(self, cfg: dict, snap: dict, ts: int) -> None:
        hour = cfg.get("digest_hour")
        if hour is None or hour == "":
            return
        lt = time.localtime(ts)
        today = time.strftime("%Y-%m-%d", lt)
        if lt.tm_hour != int(hour) or (self.db.get_kv("digest") or {}).get("day") == today:
            return
        self.db.set_kv("digest", {"day": today})
        h = snap.get("health") or {}
        top = [i for i in snap["issues"] if not i.get("group") and not i.get("muted")]
        top.sort(key=lambda i: RANK[i["severity"]])
        lines = [f"Netwerkscore {h.get('score', '?')}/100 · {h.get('critical', 0)} kritiek · "
                 f"{h.get('warning', 0)} waarschuwing · {h.get('info', 0)} info"]
        lines += [f"• {LABEL[i['severity']]}: {i['title']}" for i in top[:15]]
        if not top:
            lines.append("Geen open meldingen.")
        await self._broadcast(cfg, {"event": "digest", "severity": "info", "title": "Dagoverzicht van je netwerk",
                                    "text": "\n".join(lines), "url": self._link("issues"),
                                    "data": {"health": h, "keys": [i["key"] for i in top]}})

    async def collector_error(self, error: str, ts: float) -> None:
        """Lukt meten niet meer (controller weg), dan na een paar minuten één melding."""
        if self._down_since is None:
            self._down_since = ts
        if self._down_sent or ts - self._down_since < CONTROLLER_DOWN_AFTER:
            return
        self._down_sent = True
        await self._broadcast(config(self.s), {
            "event": "controller_down", "severity": "critical", "title": "UniFi Sonar kan de controller niet bereiken",
            "text": f"Al {round((ts - self._down_since) / 60)} minuten geen meting. Laatste fout: {error[:300]}",
            "url": self._link()})
