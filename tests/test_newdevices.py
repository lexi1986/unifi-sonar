import asyncio

import httpx

from app import rules
from app.config import Settings
from app.db import DB
from app.notify import Notifier

T = 1_800_000_000


def cl(mac, name, host=None, **kw):
    return {"mac": mac, "name": name, "hostname": host, "vendor": "Acme", "ip": "192.168.1.50", "wired": False,
            "guest": False, "ap_mac": None, "ssid": "Thuis", **kw}


def test_baseline_new_device_and_rotation(tmp_path):
    db = DB(str(tmp_path / "n.db"))
    assert db.register_clients([cl("aa:00:00:00:00:01", "Laptop"), cl("ba:00:00:00:00:02", "iPad", "ipad-keuken")], T) == []
    assert db.pending_new(0) == []                                    # eerste keer: alles stil goedgekeurd
    new = db.register_clients([cl("aa:00:00:00:00:03", "Onbekend"),
                               cl("be:00:00:00:00:04", "iPad", "iPad-Keuken"),   # zelfde hostnaam, nieuw privé-adres
                               cl("aa:00:00:00:00:05", "Gast", guest=True)], T + 60)
    assert set(new) == {"aa:00:00:00:00:03", "be:00:00:00:00:04", "aa:00:00:00:00:05"}
    assert [r["mac"] for r in db.pending_new(0)] == ["aa:00:00:00:00:03"]
    assert db.rotations(0)[0]["rotated_from"] == "ba:00:00:00:00:02"
    assert db.approve_client("aa:00:00:00:00:03") and db.pending_new(0) == []
    assert DB.private_mac("ba:00:00:00:00:02") and not DB.private_mac("f4:e2:c6:00:00:01")


def test_new_device_issue_is_pushed_without_resolved_message(tmp_path):
    db = DB(str(tmp_path / "p.db"))
    db.register_clients([cl("aa:00:00:00:00:01", "Laptop")], T)
    db.register_clients([cl("aa:00:00:00:00:09", "Tablet")], T + 10)
    snap = {"devices": [], "clients": [cl("aa:00:00:00:00:09", "Tablet")], "wan": {"up": True, "latency_ms": 5, "loss_pct": 0}}
    issues: list = []
    rules._new_devices(issues, snap, db, T + 20, lambda m: m)
    assert issues and issues[0]["severity"] == "info" and issues[0]["approve"] == "aa:00:00:00:00:09"
    rules.attach_scores(snap, issues)
    assert snap["health"]["score"] == 100                               # telt niet mee in de score

    sent = []
    def handler(req):
        import json
        sent.append(json.loads(req.content)["event"])
        return httpx.Response(200)
    s = Settings(mode="mock", notify={"channels": [{"id": "c", "kind": "webhook", "url": "http://h.test/x",
                                                     "min_severity": "warning", "resolved": True, "enabled": True}],
                                       "delay_min": 0})
    n = Notifier(s, db, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    db.sync_issues(issues, T + 20)
    asyncio.run(n.process({"issues": issues, "health": {"score": 100}}, T + 20))
    assert sent == ["opened"]                                           # info, maar toch gemeld
    db.sync_issues([], T + 100)
    asyncio.run(n.process({"issues": [], "health": {"score": 100}}, T + 100))
    asyncio.run(n.process({"issues": [], "health": {"score": 100}}, T + 200))
    assert sent == ["opened"]                                           # geen 'opgelost' na 'Ken ik'
