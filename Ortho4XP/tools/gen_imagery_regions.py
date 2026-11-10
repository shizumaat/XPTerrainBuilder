"""Generate ``src/O4_Imagery_Regions_Table.py``: every 1° tile's imagery
region (RULINGS 2026-11-10e (3): "Use the same regions that simheaven
uses").

THE SOURCE.  simHeaven publishes six X-World continental packages (the
"XP12 Sceneries" page, https://simheaven.com/xp12-sceneries/: X-WORLD
Europe, America, Asia, Australia-Oceania, Africa, Antarctica) and, on the
same page, ONE map of their split, https://simheaven.com/wp/wp-content/uploads/Map.png
(402 x 302 px, read 2026-11-10).  No tile list is published, so the
boundaries below were digitized from that map: a Mercator view with
lon = -139 + 0.694 * x and lat = gd((150.4 - y) / 82.56) (calibrated on
Florida, Madagascar, the Cape and the 60° S line), about 0.7° per pixel
with lines 3-4 px thick — a boundary tile may sit one or two tiles from
where simHeaven's packages put it.  Where the map's line crosses a sea
strait between two coasts (the Mediterranean, the Turkey-Syria border)
it is snapped to a whole-degree row between the coasts, recorded below.
Outside the map (west of 139° W, east of 140° E, north of 71° N) the
lines are extended as noted.

Regions are decided by each tile's CENTRE (lat + 0.5, lon + 0.5).  The
table holds every tile on Earth, land and sea, in exactly one region.

    cd Ortho4XP && venv/bin/python tools/gen_imagery_regions.py [--check]

``--check`` exits 1 when the committed table differs from a fresh run.
"""

from __future__ import annotations

import os
import sys

TABLE = os.path.join(os.path.dirname(__file__), "..", "src",
                     "O4_Imagery_Regions_Table.py")

#: America's EAST edge, (lat, lon) north to south: Greenland America,
#: Iceland/Svalbard/Jan Mayen Europe; the mid-Atlantic wedge the map
#: leaves uncoloured goes to Europe north of 29.4° N and Africa south of
#: it; Brazil America, Ascension/St Helena Africa.  North of 71.6° the
#: map's line is extended toward (90, -5).
AMERICA_EAST = ((90.0, -5.0), (71.6, -14.1), (62.2, -34.9), (25.1, -60.6),
                (9.9, -43.9), (0.3, -26.6), (-60.0, -23.8))
#: America's WEST edge south of 14° N (Oceania beyond it), (lat, lon);
#: west of the map it runs along 14° N, so Hawaii is America.
AMERICA_WEST = ((14.0, -180.0), (14.0, -139.0), (9.3, -114.7),
                (-0.4, -114.7), (-60.0, -121.7))
#: Chukotka (west of 169° W, north of 64° N) is Asia; the Aleutians west
#: of 180° (172° E .. 180°, 50-55° N) are America.
CHUKOTKA = (-169.0, 64.0)
ALEUTIANS_WEST = (172.0, 50.0, 55.0)
#: Europe's SOUTH edge as (lon_from, lat) steps, west to east, up to
#: Asia's edge (44.9° E).  Map 29.4° N west of 15.3° W (Madeira Europe,
#: Canaries Africa), rising to ~35° at 9.4° W; snapped across the
#: Mediterranean (Spain / Morocco, Algeria, Tunisia / Sardinia-Sicily,
#: Libya-Egypt / Malta-Crete) and the Turkey-Syria border (Antakya
#: Europe, Aleppo Asia).
EUROPE_SOUTH = ((-180.0, 29.4), (-15.3, 31.0), (-12.0, 33.0), (-9.4, 36.0),
                (-2.0, 37.0), (8.0, 38.0), (12.0, 35.0), (15.0, 34.0),
                (34.5, 36.0), (37.0, 37.0))
#: Europe's EAST edge: the map's line at 44.9° E from the pole, with its
#: notch into the Caspian's west shore (to 50.5° E, Baku) between 38.5 and 42° N (Armenia, Azerbaijan).
EUROPE_EAST = 44.9
EUROPE_NOTCH = (50.5, 38.5, 42.0)
#: Africa's EAST edge, (lat, lon) north to south: Sinai Africa / Israel
#: Asia, the Red Sea, the Gulf of Aden (Djibouti Africa / Yemen,
#: Socotra Asia), Seychelles and Mauritius Africa, then the Africa /
#: Oceania line to 60° S (Heard and Kerguelen Oceania).
AFRICA_EAST = ((33.6, 34.0), (29.5, 34.0), (12.7, 42.1), (12.0, 53.2),
               (-0.4, 59.5), (-12.8, 66.4), (-60.0, 43.5))
#: Asia's SOUTH edge east of 66.4° E, (lon, lat): Indonesia and Timor
#: Asia, New Guinea Oceania (128.9° E), then north-east past the
#: Marianas (Oceania) to 23° N east of 155° E (Wake Oceania, the Bonin
#: islands Asia).
ASIA_SOUTH = ((66.4, -12.8), (90.0, -9.7), (102.5, -8.0), (117.8, -13.1),
              (126.8, -10.8), (128.9, -8.7), (128.9, -0.4),
              (137.2, 16.0), (155.0, 23.0), (180.0, 23.0))
#: Antarctica: south of 60° S.
ANTARCTICA_NORTH = -60.0

REGION_CODES = ("europe", "america", "asia", "africa",
                "australia_oceania", "antarctica")


def _along(points, key):
    """Linear interpolation on a polyline of (k, v) pairs sorted on k
    either way; clamps at both ends."""
    pts = sorted(points)
    if key <= pts[0][0]:
        return pts[0][1]
    for (k0, v0), (k1, v1) in zip(pts, pts[1:]):
        if key <= k1:
            if k1 == k0:
                return v1
            return v0 + (v1 - v0) * (key - k0) / (k1 - k0)
    return pts[-1][1]


def _europe_south(lon):
    lat = EUROPE_SOUTH[0][1]
    for start, value in EUROPE_SOUTH:
        if lon >= start:
            lat = value
    return lat


def region_at(lat, lon):
    """The region of the point (``lat``, ``lon``) in degrees."""
    if lat < ANTARCTICA_NORTH:
        return "antarctica"
    if lon >= ALEUTIANS_WEST[0] and ALEUTIANS_WEST[1] <= lat < ALEUTIANS_WEST[2]:
        return "america"
    if lon < 0:
        if lon < CHUKOTKA[0] and lat >= CHUKOTKA[1]:
            return "asia"
        if lon < _along(AMERICA_EAST, lat):
            if lat >= AMERICA_WEST[0][0] or lon > _along(AMERICA_WEST, lat):
                return "america"
            return "australia_oceania"
    in_notch = (EUROPE_EAST <= lon < EUROPE_NOTCH[0]
                and EUROPE_NOTCH[1] <= lat < EUROPE_NOTCH[2])
    if (lon < EUROPE_EAST or in_notch) and lat >= _europe_south(lon):
        return "europe"
    if lon < _along(AFRICA_EAST, lat):
        return "africa"
    if lat < _along(ASIA_SOUTH, lon):
        return "australia_oceania"
    return "asia"


def rows():
    """``{lat: ((lon_from, code), ...)}`` runs for every 1° tile row."""
    out = {}
    for lat in range(-90, 90):
        runs = []
        for lon in range(-180, 180):
            code = region_at(lat + 0.5, lon + 0.5)
            if not runs or runs[-1][1] != code:
                runs.append((lon, code))
        out[lat] = tuple(runs)
    return out


def render():
    lines = [
        '"""Every 1° tile\'s imagery region — GENERATED by',
        "``tools/gen_imagery_regions.py`` (do not edit; its docstring names",
        "the source: simHeaven's X-World region map, read 2026-11-10).",
        "",
        "``ROWS[lat]`` holds ``(lon_from, region)`` runs west to east: a tile",
        "``(lat, lon)`` is in the region of the last run starting at or west",
        'of ``lon``."""',
        "",
        "ROWS = {",
    ]
    for lat, runs in rows().items():
        body = ", ".join("(%d, %r)" % run for run in runs)
        lines.append("    %d: (%s%s)," % (lat, body, "," if len(runs) == 1 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv):
    text = render()
    if "--check" in argv:
        with open(TABLE, encoding="utf-8") as f:
            same = f.read() == text
        print("table is current" if same else "table is STALE: regenerate")
        return 0 if same else 1
    with open(TABLE, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", os.path.normpath(TABLE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
