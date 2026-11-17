"""Kanaalplan: voor al je AP's samen een kanaal per band, zodat ze elkaar en de buren zo min mogelijk storen.

Het plan rekent met dezelfde kanaaltabel als de meldingen (buren gewogen naar sterkte, eerder gemeten storing) en
weegt daarbovenop: twee eigen AP's op hetzelfde kanaal, een wissel die weinig oplevert (elke wissel is een korte
wifi-onderbreking op die AP), DFS-kanalen en een smallere kanaalbreedte.

Toepassen gebeurt alleen op jouw verzoek, AP voor AP: UniFi start de radio's van een AP opnieuw als je een kanaal
wijzigt. Weigert een AP een kanaal (sommige modellen of landinstellingen), dan onthoudt Sonar dat en kiest het een
ander kanaal."""
from __future__ import annotations

import itertools
import time

from .i18n import L
from .rules_extra import BAD_INTERFERENCE, DAY, DFS_5, _occupies, channel_history, channel_table

OWN_PENALTY = 3000     # twee eigen AP's in hetzelfde blok ≈ een buur op −55 dBm, voor beide
MOVE_COST = 30         # een wissel moet meer opleveren dan ongeveer één buur op −75 dBm
DFS_PENALTY = 60       # DFS werkt, maar bij radar wijkt de AP even uit
NARROW_PENALTY = 150   # per halvering van de kanaalbreedte: minder snelheid
EXACT_LIMIT = 60000    # tot zoveel combinaties alles doorrekenen, daarboven stap voor stap verbeteren

KV_REFUSED = "channels_refused"   # {"mac@band": [kanaal, ...]}: kanalen die die AP niet aannam
KV_LOCKED = "channels_locked"     # {"mac@band": true}: niet aanpassen (bijvoorbeeld vanwege Zigbee)
KV_ALLOWED = "channels_allowed"   # wat UniFi in dit land toestaat (stat/current-channel)
KV_UNDO = "channels_undo"         # {"ts": .., "aps": {mac: {"name": .., "radios": {band: {"channel": raw, "ht": raw}}}}}

WEATHER_5 = {120, 124, 128}   # weerradar: in Europa luistert een AP hier 10 minuten voordat hij mag zenden

VALID = {"2.4": set(range(1, 14)), "5": {36, 40, 44, 48, 149, 153, 157, 161, 165, *DFS_5}}
WIDTHS = {"2.4": {20, 40}, "5": {20, 40, 80, 160}}


def _kv(db, key: str) -> dict:
    try:
        return (db.get_kv(key) or {}) if db is not None else {}
    except Exception:  # noqa: BLE001
        return {}


def load_allowed(db) -> dict | None:
    """Bewaard als JSON: de breedtes komen terug als tekst."""
    a = _kv(db, KV_ALLOWED)
    if not a:
        return None
    return {"country": a.get("country"), **{b: {int(w): v for w, v in (a.get(b) or {}).items()} for b in ("2.4", "5")}}


def allowed_ok(allowed: dict | None, band: str, ch: int, width: int) -> bool:
    """Mag dit kanaal met deze breedte volgens UniFi? Zonder lijst (oude controller, beperkte API) is alles goed."""
    if not allowed or not (allowed.get(band) or {}).get(width if band == "5" else 20):
        return True
    return int(ch) in allowed[band][width if band == "5" else 20]


def _radio(ap: dict, band: str) -> dict | None:
    return next((r for r in ap.get("radios") or [] if r["radio"] == band and r.get("channel")), None)


def _options(ap: dict, band: str, ins: dict, devices: list[dict], hist: dict, refused: set[int],
             allowed: dict | None = None) -> list[dict]:
    """Alle kanalen die deze radio zou kunnen krijgen, met wat ze kosten. De huidige stand zit er altijd bij."""
    r = _radio(ap, band)
    cur_ch, w0 = int(r["channel"]), int(r.get("width") or (20 if band == "2.4" else 80))
    on_dfs = cur_ch in DFS_5
    tiers = [(w0, None)]
    if band == "5":
        tiers += ([(w0, True)] if not on_dfs else []) + ([(40, None)] + ([(40, True)] if not on_dfs else []) if w0 > 40 else [])
    opts: dict[tuple[int, int], dict] = {}
    for w, dfs in tiers:
        rows = channel_table(ap, band, ins, devices, hist, w if band == "5" else None, dfs)
        for row in rows:
            ch = row["channel"]
            if (ch, w) in opts or ch in refused or (row["interference"] or 0) >= BAD_INTERFERENCE \
                    or not allowed_ok(allowed, band, ch, w):
                continue
            extra = 0
            if band == "5" and ch in DFS_5 and not on_dfs:
                extra += DFS_PENALTY
            if w < w0:
                extra += NARROW_PENALTY * {2: 1, 4: 2, 8: 3}.get(w0 // w, 1)
            opts[(ch, w)] = {"channel": ch, "width": w, "row": row, "extra": extra}
    # de huidige stand, ook als die geen 'net' kanaal is (2.4 GHz op 3) of storing heeft: blijven moet altijd kunnen
    if (cur_ch, w0) not in opts:
        rows = channel_table(ap, band, ins, devices, hist)
        row = next((x for x in rows if x["current"]), None) or {"channel": cur_ch, "neighbors": 0, "strongest": None, "own": [],
                                                                 "load": 0, "interference": None, "current": True}
        opts[(cur_ch, w0)] = {"channel": cur_ch, "width": w0, "row": {**row, "channel": cur_ch}, "extra": 0}
    for o in opts.values():
        o["stay"] = (o["channel"], o["width"]) == (cur_ch, w0)
        o["occ"] = _occupies(band, o["channel"], o["width"])
        o["cost"] = o["row"]["load"] + o["extra"] + (0 if o["stay"] else MOVE_COST)
    return sorted(opts.values(), key=lambda o: (not o["stay"], o["cost"], o["channel"]))


def _total(choice: list[dict]) -> float:
    cost = sum(o["cost"] for o in choice)
    for a, b in itertools.combinations(choice, 2):
        if a["occ"] & b["occ"]:
            cost += OWN_PENALTY
    return cost


def _pairs(choice: list[dict]) -> int:
    """Hoeveel paren eigen AP's elkaars kanaal delen."""
    return sum(1 for a, b in itertools.combinations(choice, 2) if a["occ"] & b["occ"])


def _solve(options: list[list[dict]]) -> list[dict]:
    """Goedkoopste combinatie: bij weinig AP's alles doorrekenen, anders vanaf de huidige stand per AP verbeteren
    tot niets meer helpt. Gelijke kosten: de huidige stand wint (opties staan met 'blijven' voorop)."""
    if not options:
        return []
    n = 1
    for o in options:
        n *= len(o)
    if n <= EXACT_LIMIT:
        return list(min(itertools.product(*options), key=_total))
    choice = [o[0] for o in options]
    for _ in range(12):
        changed = False
        for i, opts in enumerate(options):
            best = min(opts, key=lambda o: _total(choice[:i] + [o] + choice[i + 1:]))
            if best is not choice[i] and _total(choice[:i] + [best] + choice[i + 1:]) < _total(choice):
                choice[i], changed = best, True
        if not changed:
            break
    return choice


def _nb(row: dict) -> dict:
    return {k: row.get(k) for k in ("neighbors", "strongest", "interference", "load")}


def plan(snap: dict, ins: dict, db, ts: int | None = None, allowed: dict | None = None) -> dict:
    """Het kanaalplan voor alle AP's die nu online zijn, per band."""
    ts = int(ts or time.time())
    devices = snap.get("devices") or []
    aps = sorted((d for d in devices if d["type"] == "ap" and d.get("state") == "online"), key=lambda d: d["name"].lower())
    refused, locked = _kv(db, KV_REFUSED), _kv(db, KV_LOCKED)
    out: dict = {"available": "neighbors" in ins, "bands": {}, "aps": [{"mac": a["mac"], "name": a["name"]} for a in aps],
                 "skipped": sorted(d["name"] for d in devices if d["type"] == "ap" and d.get("state") != "online"),
                 # AP's online, maar geen enkel kanaal bekend: de beperkte officiële API geeft die niet door
                 "no_channels": bool(aps) and not any(_radio(a, b) for a in aps for b in ("2.4", "5")),
                 "allowed": {"country": allowed.get("country"), "5": {str(w): v for w, v in (allowed.get("5") or {}).items()}} if allowed else None}
    for band in ("2.4", "5"):
        radios = [(ap, _radio(ap, band)) for ap in aps if _radio(ap, band)]
        options = []
        for ap, r in radios:
            key = f"{ap['mac']}@{band}"
            hist = channel_history(db, ap["mac"], band, ts - 30 * DAY) if db is not None else {}
            opts = _options(ap, band, ins, devices, hist, {int(c) for c in refused.get(key, [])}, allowed)
            if locked.get(key):
                opts = [o for o in opts if o["stay"]]
            options.append(opts)
        choice = _solve(options)
        now = [next(o for o in opts if o["stay"]) for opts in options]   # de huidige stand zit altijd in de opties
        rows = []
        for (ap, r), cur, pick in zip(radios, now, choice):
            key = f"{ap['mac']}@{band}"
            shares_now = [a["name"] for (a, _), o in zip(radios, now) if a["mac"] != ap["mac"] and o["occ"] & cur["occ"]]
            shares = [a["name"] for (a, _), o in zip(radios, choice) if a["mac"] != ap["mac"] and o["occ"] & pick["occ"]]
            notes = []
            if not pick["stay"] and band == "5" and pick["channel"] in DFS_5 and cur["channel"] not in DFS_5:
                notes.append("dfs")
            if pick["width"] < cur["width"]:
                notes.append("narrower")
            rows.append({
                "mac": ap["mac"], "name": ap["name"], "band": band, "auto": bool(r.get("channel_auto")),
                "locked": bool(locked.get(key)), "refused": sorted(int(c) for c in refused.get(key, [])),
                "clients": r.get("num_clients") or 0,
                "current": {"channel": cur["channel"], "width": cur["width"], **_nb(cur["row"]), "shares": shares_now},
                "target": {"channel": pick["channel"], "width": pick["width"], **_nb(pick["row"]), "shares": shares},
                "change": not pick["stay"], "notes": notes,
            })
        changes = sum(x["change"] for x in rows)
        out["bands"][band] = {"radios": rows, "changes": changes,
                              "own_now": _pairs(now), "own_plan": _pairs(choice),
                              "load_now": round(sum(o["row"]["load"] for o in now)), "load_plan": round(sum(o["row"]["load"] for o in choice))}
    out["changes"] = sum(b["changes"] for b in out["bands"].values())
    undo = _kv(db, KV_UNDO)
    out["undo"] = {"ts": undo.get("ts"), "aps": [v["name"] for v in (undo.get("aps") or {}).values()]} if undo.get("aps") else None
    return out


def validate(items: list[dict], snap: dict, allowed: dict | None = None) -> dict[str, dict[str, tuple[int, int]]]:
    """Wat er toegepast mag worden, gegroepeerd per AP: {mac: {band: (kanaal, breedte)}}. Alleen AP's die online zijn,
    alleen geldige kanalen en breedtes."""
    aps = {d["mac"]: d for d in snap.get("devices") or [] if d["type"] == "ap" and d.get("state") == "online"}
    out: dict[str, dict[str, tuple[int, int]]] = {}
    for it in items:
        mac, band = str(it.get("mac", "")).lower(), str(it.get("band", ""))
        ch, w = int(it.get("channel") or 0), int(it.get("width") or 0)
        if mac not in aps:
            raise ValueError(L(f"{mac}: geen access point dat nu online is", f"{mac}: not an access point that is online now"))
        if band not in VALID or ch not in VALID[band] or w not in WIDTHS[band]:
            raise ValueError(L(f"{aps[mac]['name']}: kanaal {ch} ({w} MHz) kan niet op {band} GHz",
                               f"{aps[mac]['name']}: channel {ch} ({w} MHz) isn't valid on {band} GHz"))
        if not allowed_ok(allowed, band, ch, w):
            raise ValueError(L(f"{aps[mac]['name']}: UniFi staat kanaal {ch} ({w} MHz) niet toe in dit land",
                               f"{aps[mac]['name']}: UniFi doesn't allow channel {ch} ({w} MHz) in this country"))
        if not _radio(aps[mac], band):
            raise ValueError(L(f"{aps[mac]['name']} heeft geen {band} GHz-radio", f"{aps[mac]['name']} has no {band} GHz radio"))
        out.setdefault(mac, {})[band] = (ch, w)
    if not out:
        raise ValueError(L("Niets om toe te passen", "Nothing to apply"))
    return out


def radar_wait(band: str, channel, width) -> str | None:
    """Moet de AP eerst naar radar luisteren (DFS)? 'weather' voor de weerradarkanalen (10 minuten), 'dfs' voor de
    rest (1 minuut), None als hij meteen mag zenden."""
    if band != "5" or channel == "auto":
        return None
    occ = _occupies("5", int(channel), int(float(width or 20)))
    return "weather" if occ & WEATHER_5 else "dfs" if occ & set(DFS_5) else None


def heal_refused(db, snap: dict) -> list[str]:
    """Staat een AP inmiddels toch op een kanaal dat Sonar als geweigerd onthield (de wissel kwam later dan Sonar
    wachtte), dan telt dat kanaal weer mee. Geeft de 'mac@band'-sleutels terug die bijgewerkt zijn."""
    data = _kv(db, KV_REFUSED)
    if not data:
        return []
    changed = []
    for d in snap.get("devices") or []:
        if d.get("state") not in (None, "online"):
            continue
        for r in d.get("radios") or []:
            key = f"{d.get('mac')}@{r.get('radio')}"
            if key in data and r.get("channel") is not None and int(r["channel"]) in data[key]:
                data[key] = [c for c in data[key] if c != int(r["channel"])]
                if not data[key]:
                    del data[key]
                changed.append(key)
    if changed:
        db.set_kv(KV_REFUSED, data)
    return changed


def remember_refused(db, mac: str, band: str, channel: int) -> None:
    data = _kv(db, KV_REFUSED)
    key = f"{mac}@{band}"
    data[key] = sorted(set(data.get(key, [])) | {int(channel)})
    db.set_kv(KV_REFUSED, data)


def forget_refused(db, mac: str, band: str) -> None:
    data = _kv(db, KV_REFUSED)
    data.pop(f"{mac}@{band}", None)
    db.set_kv(KV_REFUSED, data)


def set_locked(db, mac: str, band: str, locked: bool) -> None:
    data = _kv(db, KV_LOCKED)
    if locked:
        data[f"{mac}@{band}"] = True
    else:
        data.pop(f"{mac}@{band}", None)
    db.set_kv(KV_LOCKED, data)
