"""Maakt web/world.js: landsgrenzen (Natural Earth 1:110m) en labelpunten (1:50m) in de Equal Earth-projectie.

Natural Earth is publiek domein (https://www.naturalearthdata.com). Eenmalig draaien:

    curl -fsSLO https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_110m_admin_0_countries.geojson
    curl -fsSLO https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_50m_admin_0_countries.geojson
    python tools/make_world.py ne_110m_admin_0_countries.geojson ne_50m_admin_0_countries.geojson > web/world.js
    python tools/make_world.py --geo ne_110m_admin_0_countries.geojson ne_50m_admin_0_countries.geojson > web/world-geo.js

Met --geo komen de grenzen in lengte-/breedtegraden (voor de 3D-globe, getekend met d3-geo).
"""
import json
import math
import sys

W = 1000                       # breedte in kaartpunten
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2
X_MAX = 2 * math.sqrt(3) * math.pi / (3 * A1)
SCALE = W / (2 * X_MAX)
NORTH, SOUTH = 84, -57         # Antarctica laten we weg
# Natural Earth tekent overzeese gebieden als deel van het moederland. UniFi geeft ze een eigen
# landcode, dus we knippen ze los: (land, nieuwe code, test op lengtegraad, labelpunt).
OVERSEAS = [("FR", "GF", lambda lon: lon < -20, (-53.1, 4.0))]


def raw(lon: float, lat: float) -> tuple[float, float]:
    t = math.asin(M * math.sin(math.radians(lat)))
    t2 = t * t
    t6 = t2 * t2 * t2
    x = 2 * math.sqrt(3) * math.radians(lon) * math.cos(t) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1))
    y = t * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1)
    return x, y


Y_TOP = raw(0, NORTH)[1]
H = round((Y_TOP - raw(0, SOUTH)[1]) * SCALE)


def proj(lon: float, lat: float) -> tuple[float, float]:
    x, y = raw(lon, max(SOUTH, min(NORTH, lat)))
    return round((x + X_MAX) * SCALE, 1), round((Y_TOP - y) * SCALE, 1)


def code(p: dict) -> str | None:
    c = p.get("ISO_A2_EH") or p.get("ISO_A2")
    return c if c and c != "-99" else None


def ring_path(ring: list) -> str:
    pts, last = [], None
    for lon, lat in ring:
        x, y = proj(lon, lat)
        if last and abs(x - last[0]) + abs(y - last[1]) < 0.8:
            continue
        pts.append((x, y))
        last = (x, y)
    if len(pts) < 3:
        return ""
    return "M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z"


def _signed_area(ring: list) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) / 2


def geo_ring(ring: list, exterior: bool) -> list:
    """Vereenvoudigde ring in graden. d3-geo wil buitenringen met de klok mee en gaten andersom."""
    pts, last = [], None
    for lon, lat in ring:
        p = (round(lon, 2), round(lat, 2))
        if last and abs(p[0] - last[0]) + abs(p[1] - last[1]) < 0.25:
            continue
        pts.append(p)
        last = p
    if len(pts) < 4:
        return []
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    clockwise = _signed_area(pts[:-1]) < 0
    if clockwise != exterior:
        pts.reverse()
    return [list(p) for p in pts]


def main_geo(shapes_file: str, labels_file: str) -> None:
    feats: dict[str, list] = {}
    for f in json.load(open(shapes_file))["features"]:
        c = code(f["properties"])
        if not c or c == "AQ":
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            target = c
            for parent, sub, test, _label in OVERSEAS:
                if c == parent and test(poly[0][0][0]):
                    target = sub
            rings = [geo_ring(r, i == 0) for i, r in enumerate(poly)]
            if rings and rings[0]:
                feats.setdefault(target, []).append([r for r in rings if r])
    labels: dict[str, list] = {}
    for f in json.load(open(labels_file))["features"]:
        p = f["properties"]
        c = code(p)
        if c and c != "AQ" and p.get("LABEL_X") is not None:
            labels[c] = [round(p["LABEL_X"], 2), round(p["LABEL_Y"], 2)]
    for _parent, sub, _test, (lon, lat) in OVERSEAS:
        labels[sub] = [lon, lat]
    out = {"type": "FeatureCollection", "labels": labels, "features": [
        {"type": "Feature", "id": c, "geometry": {"type": "MultiPolygon", "coordinates": polys}}
        for c, polys in sorted(feats.items())]}
    print("// Gegenereerd door tools/make_world.py --geo uit Natural Earth (publiek domein). Niet met de hand bewerken.")
    print("window.WORLD_GEO = " + json.dumps(out, separators=(",", ":")) + ";")


def main(shapes_file: str, labels_file: str) -> None:
    countries: dict[str, dict] = {}
    for f in json.load(open(shapes_file))["features"]:
        c = code(f["properties"])
        if not c or c == "AQ":
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            target = c
            for parent, sub, test, _label in OVERSEAS:
                if c == parent and test(poly[0][0][0]):
                    target = sub
            d = "".join(ring_path(r) for r in poly)
            if d:
                countries.setdefault(target, {})["d"] = countries.get(target, {}).get("d", "") + d
    for f in json.load(open(labels_file))["features"]:
        p = f["properties"]
        c = code(p)
        if c and c != "AQ" and p.get("LABEL_X") is not None:
            countries.setdefault(c, {})["c"] = list(proj(p["LABEL_X"], p["LABEL_Y"]))
    for _parent, sub, _test, (lon, lat) in OVERSEAS:
        countries.setdefault(sub, {})["c"] = list(proj(lon, lat))
    countries = {k: v for k, v in countries.items() if "c" in v}
    out = {"w": W, "h": H, "countries": countries}
    print("// Gegenereerd door tools/make_world.py uit Natural Earth (publiek domein). Niet met de hand bewerken.")
    print("window.WORLD = " + json.dumps(out, separators=(",", ":")) + ";")


if __name__ == "__main__":
    if sys.argv[1] == "--geo":
        main_geo(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1], sys.argv[2])
