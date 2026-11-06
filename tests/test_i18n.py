"""Taalkeuze: teksten in beide talen, wisselen via de API, en wat er bewaard wordt gaat mee."""
import asyncio
import json

import pytest

from app import i18n
from app.collector import Collector
from app.config import Settings
from app.db import DB
from app.ha_mqtt import HAMqtt
from app.notify import Notifier


@pytest.fixture(autouse=True)
def _reset_language():
    yield
    i18n.set_server("nl")


def test_basics():
    i18n.set_server("nl")
    assert i18n.L("ja", "yes") == "ja"
    with i18n.use("en"):
        assert i18n.L("ja", "yes") == "yes"
    assert i18n.both(lambda: i18n.L("ja", "yes")) == {"nl": "ja", "en": "yes"}
    stored = i18n.dump(i18n.bi("weg", "gone"))
    assert i18n.pick(stored) == "weg" and i18n.pick(stored, "en") == "gone"
    assert i18n.pick("gewone tekst", "en") == "gewone tekst"          # oude regels zonder vertaling
    assert i18n.normalize("EN-gb") == "en" and i18n.normalize("fr") is None
    merged = i18n.merge_issues([{"key": "a", "title": "Zwak", "detail": "d", "advice": "a"}],
                               [{"key": "a", "title": "Weak", "detail": "d-en", "advice": "a-en"}])
    assert i18n.issue(merged[0], "en")["title"] == "Weak" and "en" not in i18n.issue(merged[0], "en")
    assert i18n.issue(merged[0], "nl")["title"] == "Zwak"


def _app(tmp_path, monkeypatch, language=""):
    monkeypatch.setenv("NO_DOTENV", "1")
    from fastapi.testclient import TestClient
    from app import main
    st = Settings(mode="mock", db_path=str(tmp_path / "s.db"), mock_seed_hours=1, data_dir=str(tmp_path), language=language)
    st.save()
    col = Collector(st, DB(st.db_path))
    asyncio.run(col.seed_history())
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.rt, "settings", st)
    monkeypatch.setattr(main.rt, "collector", col)
    monkeypatch.setattr(main.rt, "db", col.db)
    i18n.set_server(language)
    return TestClient(main.app), col


def test_switch_language_via_api(tmp_path, monkeypatch):
    c, col = _app(tmp_path, monkeypatch, "nl")
    nl = {i["key"]: i["title"] for i in c.get("/api/snapshot").json()["issues"]}
    assert c.get("/api/status").json()["language"] == "nl"

    assert c.post("/api/language", json={"language": "en"}).json()["ok"]
    assert Settings.load(str(tmp_path)).language == "en"                       # bewaard in config.json
    en = {i["key"]: i["title"] for i in c.get("/api/snapshot").json()["issues"]}
    assert en.keys() == nl.keys() and en != nl
    assert en["segment:" + next(k.split(":", 1)[1] for k in en if k.startswith("segment:"))].endswith("is on your main network")
    # ook de historie (opgeslagen meldingen en de tijdlijn) wisselt mee
    stored = c.get("/api/issues?state=all").json()
    assert any(i["title"].startswith("New device") or "weak" in i["title"] for i in stored)
    msgs = [e["message"] for e in c.get("/api/events?hours=2").json()]
    assert any(m.endswith(": link lost") for m in msgs) and not any(m.endswith(": link weg") for m in msgs)
    # foutmeldingen van de API volgen de taal ook
    assert c.post("/api/mute", json={"key": "bestaat-niet"}).json()["detail"] == "Unknown issue"
    assert c.post("/api/language", json={"language": "de"}).status_code == 422


def test_index_follows_setting_or_browser(tmp_path, monkeypatch):
    c, _ = _app(tmp_path, monkeypatch, "")
    assert '<html lang="en" data-lang-set="0">' in c.get("/", headers={"accept-language": "en-US,en;q=0.9"}).text
    assert '<html lang="nl" data-lang-set="0">' in c.get("/", headers={"accept-language": "nl-NL,nl;q=0.9"}).text
    c.post("/api/language", json={"language": "en"})
    assert '<html lang="en" data-lang-set="1">' in c.get("/", headers={"accept-language": "nl-NL"}).text


def test_notifications_and_home_assistant_use_the_language(tmp_path):
    i18n.set_server("en")
    db = DB(str(tmp_path / "n.db"))
    issue = {"key": "k", "severity": "warning", "category": "wifi", "title": "Zwak", "detail": "d", "advice": "doe iets",
             "en": {"title": "Weak", "detail": "d", "advice": "do something"}}
    n = Notifier(Settings(mode="mock"), db)
    msg = n._issue_msg(issue, "escalated")
    assert msg["title"] == "Escalated: Weak" and "Advice: do something" in msg["text"]
    assert n.test_msg()["title"] == "Test message from UniFi Sonar"

    class Col:
        latest, db, last_error = {}, None, None
    names = {t.split("/")[3]: json.loads(p)["name"] for t, p in HAMqtt(Settings(mode="mock"), Col).discovery()}
    assert names["score"] == "Network score" and names["speedtest"] == "Start speed test"
    i18n.set_server("nl")
    names = {t.split("/")[3]: json.loads(p)["name"] for t, p in HAMqtt(Settings(mode="mock"), Col).discovery()}
    assert names["score"] == "Netwerkscore"
