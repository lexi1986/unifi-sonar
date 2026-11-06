"""Home Assistant-koppeling via MQTT: Sonar verschijnt in HA als apparaat met sensoren en een speedtest-knop.

Gebruikt MQTT-discovery (homeassistant/<component>/unifi_sonar/<sleutel>/config), dus in HA hoef je niets in
te stellen behalve de MQTT-integratie zelf (bijvoorbeeld de Mosquitto-add-on). Een kleine eigen MQTT 3.1.1-
client: publiceren (QoS 0), één onderwerp volgen, keep-alive en een 'last will' zodat HA ziet wanneer Sonar weg is.
"""
from __future__ import annotations

import asyncio
import json
import logging
import struct
import time

from . import VERSION

log = logging.getLogger(__name__)
NODE = "unifi_sonar"
BASE = f"sonar/{NODE}"
DEFAULTS = {"enabled": False, "host": "", "port": 1883, "username": "", "password": "", "prefix": "homeassistant"}

# (sleutel, naam, eenheid, device_class, state_class, icoon)
SENSORS = [
    ("score", "Netwerkscore", None, None, "measurement", "mdi:radar"),
    ("issues", "Openstaande meldingen", None, None, "measurement", "mdi:alert-circle-outline"),
    ("critical", "Kritieke meldingen", None, None, "measurement", "mdi:alert-octagon-outline"),
    ("clients", "Clients online", None, None, "measurement", "mdi:devices"),
    ("clients_wifi", "Wifi-clients", None, None, "measurement", "mdi:wifi"),
    ("devices_online", "UniFi-apparaten online", None, None, "measurement", "mdi:access-point-network"),
    ("latency", "Internetlatency", "ms", "duration", "measurement", "mdi:timer-outline"),
    ("down_now", "Download nu", "Mbit/s", "data_rate", "measurement", "mdi:download"),
    ("up_now", "Upload nu", "Mbit/s", "data_rate", "measurement", "mdi:upload"),
    ("speed_down", "Speedtest download", "Mbit/s", "data_rate", "measurement", "mdi:speedometer"),
    ("speed_up", "Speedtest upload", "Mbit/s", "data_rate", "measurement", "mdi:speedometer"),
    ("speed_ping", "Speedtest ping", "ms", "duration", "measurement", "mdi:timer-outline"),
    ("usage_today", "Datagebruik vandaag", "GB", "data_size", "total_increasing", "mdi:chart-bar"),
    ("usage_month", "Datagebruik deze maand", "GB", "data_size", "total_increasing", "mdi:chart-bar"),
    ("new_devices", "Nieuwe apparaten", None, None, "measurement", "mdi:new-box"),
    ("ips_24h", "IPS-blokkades (24 uur)", None, None, "measurement", "mdi:shield-alert-outline"),
]
BINARY = [("internet", "Internet", "connectivity"), ("controller", "UniFi-controller bereikbaar", "connectivity")]


def config(settings) -> dict:
    return {**DEFAULTS, **(getattr(settings, "mqtt", None) or {})}


# ---------------------------------------------------------------------- MQTT 3.1.1-pakketjes
def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b, n = n % 128, n // 128
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _str(s: str) -> bytes:
    b = s.encode()
    return struct.pack("!H", len(b)) + b


def _packet(kind: int, body: bytes) -> bytes:
    return bytes([kind]) + _varint(len(body)) + body


def connect_packet(client_id: str, user: str, password: str, will_topic: str, keepalive: int = 60) -> bytes:
    flags = 0x02 | 0x04 | 0x20   # schone sessie, last will, will vasthouden (retain)
    payload = _str(client_id) + _str(will_topic) + _str("offline")
    if user:
        flags |= 0x80
        payload += _str(user)
        if password:
            flags |= 0x40
            payload += _str(password)
    return _packet(0x10, _str("MQTT") + bytes([4, flags]) + struct.pack("!H", keepalive) + payload)


def publish_packet(topic: str, payload: str, retain: bool = True) -> bytes:
    return _packet(0x30 | (0x01 if retain else 0), _str(topic) + payload.encode())


def subscribe_packet(topic: str, pid: int = 1) -> bytes:
    return _packet(0x82, struct.pack("!H", pid) + _str(topic) + b"\x00")


async def _read_packet(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    head = (await reader.readexactly(1))[0]
    n, mul = 0, 1
    while True:
        b = (await reader.readexactly(1))[0]
        n += (b & 0x7F) * mul
        mul *= 128
        if not b & 0x80:
            break
    return head, await reader.readexactly(n) if n else b""


CONNACK_ERR = {1: "protocolversie niet ondersteund", 2: "client-id geweigerd", 3: "broker niet beschikbaar",
               4: "gebruikersnaam of wachtwoord onjuist", 5: "niet gemachtigd"}


async def try_connect(cfg: dict, timeout: float = 6) -> str | None:
    """Verbinding testen. Geeft None bij succes, anders een foutmelding."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(cfg["host"], int(cfg["port"])), timeout)
    except Exception as e:  # noqa: BLE001
        return f"Kan {cfg['host']}:{cfg['port']} niet bereiken ({type(e).__name__})"
    try:
        writer.write(connect_packet(f"{NODE}_test", cfg["username"], cfg["password"], f"{BASE}/test"))
        await writer.drain()
        head, body = await asyncio.wait_for(_read_packet(reader), timeout)
        if head >> 4 != 2 or len(body) < 2:
            return "Onverwacht antwoord van de broker"
        return None if body[1] == 0 else f"Broker weigert: {CONNACK_ERR.get(body[1], body[1])}"
    except Exception as e:  # noqa: BLE001
        return f"Geen antwoord van de broker ({type(e).__name__})"
    finally:
        writer.close()


# ---------------------------------------------------------------------- de koppeling zelf
class HAMqtt:
    def __init__(self, settings, collector) -> None:
        self.s = settings
        self.col = collector
        self.writer: asyncio.StreamWriter | None = None
        self.status = {"connected": False, "error": None, "since": None, "last_publish": None}
        self._task: asyncio.Task | None = None

    @property
    def cfg(self) -> dict:
        return config(self.s)

    def start(self) -> None:
        if self.cfg["enabled"] and self.cfg["host"] and not self._task:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self.writer:
            try:
                self.writer.write(publish_packet(f"{BASE}/status", "offline"))
                self.writer.write(b"\xe0\x00")   # DISCONNECT
                await self.writer.drain()
            except Exception:  # noqa: BLE001
                pass
            self.writer.close()
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._task, self.writer = None, None
        self.status.update(connected=False)

    async def _loop(self) -> None:
        delay = 5
        while True:
            try:
                await self._session()
                delay = 5
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 – opnieuw proberen
                self.status.update(connected=False, error=str(e) or type(e).__name__)
                log.warning("MQTT: %s", self.status["error"])
            self.writer = None
            await asyncio.sleep(delay)
            delay = min(300, delay * 2)

    async def _session(self) -> None:
        c = self.cfg
        reader, writer = await asyncio.wait_for(asyncio.open_connection(c["host"], int(c["port"])), 10)
        writer.write(connect_packet(NODE, c["username"], c["password"], f"{BASE}/status"))
        await writer.drain()
        head, body = await asyncio.wait_for(_read_packet(reader), 10)
        if head >> 4 != 2 or len(body) < 2 or body[1] != 0:
            writer.close()
            raise RuntimeError("Broker weigert: " + CONNACK_ERR.get(body[1] if len(body) > 1 else 0, "onbekend"))
        self.writer = writer
        self.status.update(connected=True, error=None, since=int(time.time()))
        log.info("MQTT verbonden met %s:%s", c["host"], c["port"])
        writer.write(subscribe_packet(f"{BASE}/speedtest/set"))
        for topic, payload in self.discovery():
            writer.write(publish_packet(topic, payload))
        writer.write(publish_packet(f"{BASE}/status", "online"))
        await writer.drain()
        self.publish_state()
        last_ping = time.time()
        while True:
            try:
                head, body = await asyncio.wait_for(_read_packet(reader), 30)
            except asyncio.TimeoutError:
                head = None
            if head is not None and head >> 4 == 3:   # PUBLISH: de speedtest-knop
                tlen = struct.unpack("!H", body[:2])[0]
                if body[2:2 + tlen].decode(errors="replace") == f"{BASE}/speedtest/set":
                    asyncio.create_task(self._speedtest())
            if time.time() - last_ping > 45:
                writer.write(b"\xc0\x00")   # PINGREQ
                await writer.drain()
                last_ping = time.time()

    async def _speedtest(self) -> None:
        try:
            await self.col.start_speedtest()
        except Exception as e:  # noqa: BLE001
            log.info("Speedtest via Home Assistant: %s", e)

    # ------------------------------------------------------------------ inhoud
    def discovery(self) -> list[tuple[str, str]]:
        p = self.cfg["prefix"].strip("/") or "homeassistant"
        url = (getattr(self.s, "notify", None) or {}).get("base_url") or None
        dev = {"identifiers": [NODE], "name": "UniFi Sonar", "manufacturer": "UniFi Sonar", "model": "Netwerkdashboard",
               "sw_version": VERSION, **({"configuration_url": url} if url else {})}
        avail = {"availability_topic": f"{BASE}/status"}
        out = []
        for key, name, unit, dc, sc, ic in SENSORS:
            cfg = {"name": name, "unique_id": f"{NODE}_{key}", "object_id": f"sonar_{key}", "state_topic": f"{BASE}/state",
                   "value_template": f"{{{{ value_json.{key} }}}}", "icon": ic, "device": dev, **avail}
            if unit:
                cfg["unit_of_measurement"] = unit
            if dc:
                cfg["device_class"] = dc
            if sc:
                cfg["state_class"] = sc
            if key == "issues":
                cfg["json_attributes_topic"] = f"{BASE}/issues"
            out.append((f"{p}/sensor/{NODE}/{key}/config", json.dumps(cfg)))
        for key, name, dc in BINARY:
            cfg = {"name": name, "unique_id": f"{NODE}_{key}", "object_id": f"sonar_{key}", "state_topic": f"{BASE}/state",
                   "value_template": f"{{{{ 'ON' if value_json.{key} else 'OFF' }}}}", "device_class": dc, "device": dev, **avail}
            out.append((f"{p}/binary_sensor/{NODE}/{key}/config", json.dumps(cfg)))
        out.append((f"{p}/button/{NODE}/speedtest/config", json.dumps({
            "name": "Speedtest starten", "unique_id": f"{NODE}_speedtest", "object_id": "sonar_speedtest",
            "command_topic": f"{BASE}/speedtest/set", "icon": "mdi:speedometer", "device": dev, **avail})))
        return out

    def state(self) -> tuple[dict, dict]:
        snap, db = self.col.latest or {}, self.col.db
        now = int(time.time())
        issues = [i for i in snap.get("issues", []) if not i.get("group") and not i.get("muted")]
        clients = [c for c in snap.get("clients", []) if c.get("connected", True)]
        devs = snap.get("devices", [])
        wan = snap.get("wan", {})
        st = (db.speedtests(now - 90 * 86400) or [None])[-1]
        lt = time.localtime(now)
        day0 = int(time.mktime(lt[:3] + (0, 0, 0, 0, 0, -1)))
        month0 = int(time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1)))
        usage = lambda period, t0: next(((r["rx"] + r["tx"]) / 1e9 for r in db.usage(period, t0) if r["ts"] == t0), None)  # noqa: E731
        mb = lambda v: round(v / 1e6, 1) if v is not None else None  # noqa: E731
        state = {
            "score": snap.get("health", {}).get("score"), "issues": len(issues),
            "critical": sum(i["severity"] == "critical" for i in issues),
            "clients": len(clients), "clients_wifi": sum(1 for c in clients if not c.get("wired")),
            "devices_online": sum(d.get("state") == "online" for d in devs),
            "latency": wan.get("latency_ms"), "down_now": mb(wan.get("rx_bps")), "up_now": mb(wan.get("tx_bps")),
            "speed_down": st and round(st["down"]), "speed_up": st and round(st["up"]), "speed_ping": st and st.get("latency"),
            "usage_today": round(u, 2) if (u := usage("day", day0)) is not None else None,
            "usage_month": round(u, 1) if (u := usage("month", month0)) is not None else None,
            "new_devices": len(db.pending_new(now - 7 * 86400)),
            "ips_24h": len(db.ips_events(now - 86400, "external")),
            "internet": wan.get("up") is not False, "controller": self.col.last_error is None,
        }
        attrs = {"meldingen": [f"{i['severity']}: {i['title']}" for i in issues[:15]]}
        return state, attrs

    def publish_state(self) -> None:
        if not self.writer:
            return
        try:
            state, attrs = self.state()
            self.writer.write(publish_packet(f"{BASE}/state", json.dumps(state)))
            self.writer.write(publish_packet(f"{BASE}/issues", json.dumps(attrs)))
            self.status["last_publish"] = int(time.time())
        except Exception as e:  # noqa: BLE001 – bijzaak
            log.warning("MQTT publiceren: %s", e)
