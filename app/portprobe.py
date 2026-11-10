"""De poortcheck van de kwetsbaarheidsscan, als los proces.

Sonar start dit bestand met een leeg milieu en geeft de doelen via stdin. Het importeert niets van Sonar, dus de API-sleutel
zit niet in dit proces. Het maakt alleen een TCP-verbinding en sluit die meteen: geen wachtwoorden, geen exploits en
er wordt niets gestuurd. Adressen buiten RFC 1918 worden hier nogmaals geweigerd.

Invoer: {"targets": ["192.168.1.5"], "ports": [22, 443], "delay": 1.0, "timeout": 1.5}
Uitvoer: regels JSON; {"done": n, "total": t} en als laatste {"result": {ip: {"open": [poort], "closed": aantal}}}.
"""
import asyncio
import ipaddress
import json
import random
import sys

ALLOWED = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
MAX_PROBES = 4000


def allowed(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and any(a in n for n in ALLOWED)


async def probe(ip: str, port: int, timeout: float) -> str:
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
    except ConnectionRefusedError:
        return "closed"
    except (asyncio.TimeoutError, OSError):
        return "silent"
    w.close()
    return "open"


async def run(job: dict) -> dict:
    # Door elkaar, zodat één apparaat maar af en toe een verzoek krijgt en de IPS het niet voor een aanval aanziet.
    pairs = [(ip, int(p)) for ip in job["targets"] if allowed(ip) for p in job["ports"]][:MAX_PROBES]
    random.shuffle(pairs)
    res = {ip: {"open": [], "closed": 0} for ip, _ in pairs}
    for n, (ip, port) in enumerate(pairs, 1):
        state = await probe(ip, port, float(job.get("timeout", 1.5)))
        if state == "open":
            res[ip]["open"].append(port)
        elif state == "closed":
            res[ip]["closed"] += 1
        if n % 5 == 0 or n == len(pairs):
            print(json.dumps({"done": n, "total": len(pairs)}), flush=True)
        await asyncio.sleep(float(job.get("delay", 1.0)))
    return res


if __name__ == "__main__":
    print(json.dumps({"result": asyncio.run(run(json.load(sys.stdin)))}), flush=True)
