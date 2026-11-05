import asyncio
import json

import httpx

from app.config import Settings
from app.db import DB
from app.notify import Notifier, mask

T0 = 1_800_000_000


def issue(key, sev="warning", **kw):
    i = {"key": key, "severity": sev, "category": "wifi", "entity_type": "client", "entity_id": key,
         "title": f"Titel {key}", "detail": "Detail", "advice": "Advies", "device_mac": None, "client_mac": None}
    i.update(kw)
    return i


class Harness:
    """Notifier met een echte (tijdelijke) database en een nep-webhook die alles opvangt."""

    def __init__(self, tmp_path, delay=5, **ch):
        self.sent: list[dict] = []
        self.fail = False

        def handler(req: httpx.Request) -> httpx.Response:
            if self.fail:
                return httpx.Response(500)
            self.sent.append(json.loads(req.content))
            return httpx.Response(200)

        self.db = DB(str(tmp_path / "n.db"))
        channel = {"id": "c1", "kind": "webhook", "url": "http://hook.test/x", "min_severity": "warning",
                   "resolved": True, "enabled": True, **ch}
        self.s = Settings(mode="mock", notify={"channels": [channel], "delay_min": delay, "base_url": "http://sonar.lan"})
        self.n = Notifier(self.s, self.db, httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    def tick(self, ts, issues):
        self.db.sync_issues(issues, ts)
        asyncio.run(self.n.process({"issues": issues, "health": {"score": 80}}, ts))
        return [m["event"] for m in self.sent]


def test_opened_after_delay_then_resolved(tmp_path):
    h = Harness(tmp_path)
    a = issue("a")
    assert h.tick(T0, [a]) == []                     # nog geen 5 minuten
    assert h.tick(T0 + 301, [a]) == ["opened"]
    assert h.sent[0]["title"] == "Titel a" and h.sent[0]["url"] == "http://sonar.lan/#/issues"
    assert h.tick(T0 + 360, [a]) == ["opened"]       # niet nog een keer
    h.tick(T0 + 400, [])                             # weg, maar nog niet lang genoeg
    assert h.tick(T0 + 420, [a]) == ["opened"]       # terug binnen de wachttijd: geen berichten
    h.tick(T0 + 500, [])
    assert h.tick(T0 + 820, []) == ["opened", "resolved"]
    assert h.sent[-1]["title"].startswith("Opgelost")


def test_escalation_mute_and_min_severity(tmp_path):
    h = Harness(tmp_path, delay=0)
    assert h.tick(T0, [issue("a"), issue("i", "info")]) == ["opened"]       # info valt onder de grens
    assert h.tick(T0 + 60, [issue("a", "critical")]) == ["opened", "escalated"]
    h.tick(T0 + 120, [issue("a", "critical", muted=True)])                   # genegeerd: stil vergeten
    assert h.tick(T0 + 999, []) == ["opened", "escalated"]


def test_many_new_issues_are_bundled_and_groups_skipped(tmp_path):
    h = Harness(tmp_path, delay=0)
    items = [issue(f"k{n}") for n in range(6)] + [issue("member", group="k0")]
    assert h.tick(T0, items) == ["bundle"]
    assert "6 nieuwe meldingen" in h.sent[0]["title"]


def test_failed_send_is_retried_later(tmp_path, monkeypatch):
    h = Harness(tmp_path, delay=0)
    real_sleep = asyncio.sleep
    monkeypatch.setattr("app.notify.asyncio.sleep", lambda *_: real_sleep(0))
    h.fail = True
    h.tick(T0, [issue("a")])
    assert h.n.status["c1"]["error"]
    h.fail = False
    assert h.tick(T0 + 60, [issue("a")]) == []        # kanaal faalde net: even met rust laten
    h.n.status["c1"]["error_ts"] = 0
    assert h.tick(T0 + 400, [issue("a")]) == ["opened"]


def test_baseline_skips_existing_issues(tmp_path):
    h = Harness(tmp_path, delay=0)
    h.n.baseline("c1", [issue("old")])
    assert h.tick(T0, [issue("old"), issue("new")]) == ["opened"]
    assert h.tick(T0 + 60, [issue("new")]) == ["opened"]   # 'old' was nooit gemeld: ook geen 'opgelost'


def test_controller_down_and_up(tmp_path):
    h = Harness(tmp_path)
    asyncio.run(h.n.collector_error("timeout", T0))
    asyncio.run(h.n.collector_error("timeout", T0 + 200))
    assert h.sent == []
    asyncio.run(h.n.collector_error("timeout naar https://192.168.1.1", T0 + 400))
    assert [m["event"] for m in h.sent] == ["controller_down"]
    h.tick(T0 + 460, [])
    assert [m["event"] for m in h.sent] == ["controller_down", "controller_up"]


def test_channel_formats():
    n = Notifier(Settings(), None, httpx.AsyncClient())
    msg = {"event": "opened", "severity": "critical", "title": "T", "text": "x", "url": "http://s/#/issues"}
    url, body, headers = n._payload({"kind": "ntfy", "url": "https://ntfy.sh/geheim", "token": "tk"}, msg)
    assert url == "https://ntfy.sh" and body["topic"] == "geheim" and body["priority"] == 5
    assert headers["Authorization"] == "Bearer tk"
    url, body, _ = n._payload({"kind": "discord", "url": "https://discord.com/api/webhooks/1/a"}, msg)
    assert body["embeds"][0]["color"] == 0xFB7185
    assert mask("https://discord.com/api/webhooks/123/abcdef") == "https://discord.com/…cdef"


# ---------------------------------------------------------------- toegang (DNS-rebinding, andere websites)
def test_host_and_origin_guard(monkeypatch):
    monkeypatch.setenv("NO_DOTENV", "1")
    from fastapi.testclient import TestClient
    from app import main
    c = TestClient(main.app)
    assert c.get("/api/status", headers={"host": "192.168.1.20"}).status_code == 200
    assert c.get("/api/status", headers={"host": "sonar.local:8080"}).status_code == 200
    assert c.get("/api/status", headers={"host": "evil.example.com"}).status_code == 421
    monkeypatch.setattr(main.rt.settings, "allowed_hosts", ["sonar.example.com"])
    assert c.get("/api/status", headers={"host": "sonar.example.com"}).status_code == 200
    r = c.post("/api/unmute", json={"key": "x"}, headers={"host": "192.168.1.20", "origin": "https://evil.example.com"})
    assert r.status_code == 403
    r = c.post("/api/unmute", json={"key": "x"}, headers={"host": "192.168.1.20", "sec-fetch-site": "cross-site"})
    assert r.status_code == 403


def test_debug_text_is_scrubbed():
    from app.main import scrub
    out = scrub("fout bij https://unifi.thuis.nl:11443/api via 192.168.1.2 voor aa:bb:cc:dd:ee:ff")
    assert "192.168" not in out and "aa:bb" not in out and "thuis.nl" not in out
