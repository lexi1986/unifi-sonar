import asyncio
import json
import struct

from app import ha_mqtt
from app.collector import Collector
from app.config import Settings
from app.db import DB


class FakeBroker:
    """Minimale MQTT-broker: CONNACK met een instelbare code, onthoudt PUBLISH-berichten, kan er een terugsturen."""

    def __init__(self, rc=0):
        self.rc, self.published, self.subs, self.conns = rc, {}, [], []

    async def handle(self, reader, writer):
        self.conns.append(writer)
        try:
            while True:
                head, body = await ha_mqtt._read_packet(reader)
                kind = head >> 4
                if kind == 1:
                    writer.write(b"\x20\x02\x00" + bytes([self.rc]))
                elif kind == 3:
                    n = struct.unpack("!H", body[:2])[0]
                    self.published[body[2:2 + n].decode()] = body[2 + n:].decode()
                elif kind == 8:
                    n = struct.unpack("!H", body[2:4])[0]
                    self.subs.append(body[4:4 + n].decode())
                    writer.write(b"\x90\x03" + body[:2] + b"\x00")
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass

    def press(self, topic):
        for w in self.conns:
            w.write(ha_mqtt.publish_packet(topic, "PRESS", retain=False))


def test_packets_and_wrong_password():
    assert ha_mqtt._varint(321) == b"\xc1\x02"
    async def go():
        b = FakeBroker(rc=4)
        srv = await asyncio.start_server(b.handle, "127.0.0.1", 0)
        port = srv.sockets[0].getsockname()[1]
        err = await ha_mqtt.try_connect({"host": "127.0.0.1", "port": port, "username": "x", "password": "y"})
        b.rc = 0
        ok = await ha_mqtt.try_connect({"host": "127.0.0.1", "port": port, "username": "x", "password": "y"})
        srv.close()
        return err, ok
    err, ok = asyncio.run(go())
    assert "wachtwoord onjuist" in err and ok is None


def test_discovery_state_and_speedtest_button(tmp_path):
    async def go():
        b = FakeBroker()
        srv = await asyncio.start_server(b.handle, "127.0.0.1", 0)
        port = srv.sockets[0].getsockname()[1]
        st = Settings(mode="mock", db_path=str(tmp_path / "m.db"), mock_seed_hours=1,
                      mqtt={"enabled": True, "host": "127.0.0.1", "port": port})
        col = Collector(st, DB(st.db_path))
        await col.seed_history()
        pressed = []
        async def fake_speedtest():
            pressed.append(1)
        col.start_speedtest = fake_speedtest
        col.ha.start()
        for _ in range(50):
            await asyncio.sleep(0.05)
            if "sonar/unifi_sonar/state" in b.published and b.subs:
                break
        b.press("sonar/unifi_sonar/speedtest/set")
        for _ in range(40):
            await asyncio.sleep(0.05)
            if pressed:
                break
        await col.ha.stop()
        srv.close()
        return b, pressed, col
    b, pressed, col = asyncio.run(go())
    cfg = json.loads(b.published["homeassistant/sensor/unifi_sonar/score/config"])
    assert cfg["state_topic"] == "sonar/unifi_sonar/state" and cfg["device"]["name"] == "UniFi Sonar"
    assert "homeassistant/button/unifi_sonar/speedtest/config" in b.published
    state = json.loads(b.published["sonar/unifi_sonar/state"])
    assert state["clients"] > 10 and isinstance(state["score"], int) and state["internet"] is True
    assert b.published["sonar/unifi_sonar/status"] == "offline"        # netjes afgemeld bij stoppen
    assert b.subs == ["sonar/unifi_sonar/speedtest/set"] and pressed == [1]
    assert not col.ha.status["connected"]
