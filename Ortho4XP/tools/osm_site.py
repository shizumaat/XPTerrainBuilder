#!/usr/bin/env python
"""WHAT IS AT THIS COORDINATE — ways near a point, in a patch or a feed.

Promoted 2026-08-12 from the round-20 lane's scratchpad readers
``kclt_site.py`` (emitted patches) and ``osmfeed.py`` (bz2 road feeds) on
their SECOND use (RULINGS ``7e90032``, promote-on-reuse).  They were two
copies of one question asked of two file formats, which is exactly the
shape the census-wrapper precedent warns about — one grew an ``alt_abs``
reader and the other grew bz2, and neither could read the other's file.
One reader now handles both.

It MEASURES NOTHING and DERIVES NO LAW.  Every value printed is read
verbatim out of the file: way ids, tags, node ids, coordinates, the
``alt_abs`` a node carries.  Defect counts come from
``tools/harness/census.py`` and from nowhere else; this answers "which
ways are here, what are they tagged, and what altitudes do their nodes
carry", which is the question an attribution starts from.

    venv/bin/python tools/osm_site.py FILE [FILE...] --at LAT,LON
        [--radius M] [--role ROLE] [--tag-keys k,k] [--json OUT]
    venv/bin/python tools/osm_site.py FILE --dump WAY_ID [--at LAT,LON]

Both OSM dialects this repo produces are read: the emitted patch's
single-quoted attributes (``layout.to_osm``) and the Ortho4XP road
feeds' double-quoted ones, plain or ``.bz2``.  Several FILEs are read
independently and reported one after another — that is the arm-vs-arm
comparison the round-20 lane needed (an owner artifact against a lane
build), and reading them in one process is what keeps the probe point,
the radius and the projection identical between the two.

Distances are metres in a local equirectangular frame about the probe
point — the same frame ``bridges._local_meter_projections`` uses for a
site this small, and never a substitute for the layout's own metres.
"""
from __future__ import annotations

import argparse
import bz2
import json
import math
import re
import sys

# The two dialects, one pattern each.  ``[^>]*?`` before the coordinate
# pair lets ``version``/``action``/``visible`` sit in any order.
_NODE_BLOCK = re.compile(
    r"<node id=(['\"])(-?\d+)\1.*?(?:/>|</node>)", re.S)
_WAY_BLOCK = re.compile(
    r"<way id=(['\"])(-?\d+)\1[^>]*>(.*?)</way>", re.S)
_ND_REF = re.compile(r"<nd ref=['\"](-?\d+)['\"]")
_TAG = re.compile(r"<tag k=['\"]([^'\"]*)['\"] v=['\"]([^'\"]*)['\"]")
_LAT = re.compile(r"lat=['\"](-?[\d.]+)['\"]")
_LON = re.compile(r"lon=['\"](-?[\d.]+)['\"]")
_ALT = re.compile(r"<tag k=['\"]alt_abs['\"] v=['\"](-?[\d.eE+]+)['\"]")


def read_osm(path: str) -> tuple[dict, list]:
    """``({node_id: (lat, lon, alt_or_None, tags)}, [(way_id, nds, tags)])``.

    ``.bz2`` is decompressed transparently.  A node's altitude is its
    ``alt_abs`` tag when it carries one — the per-node form the emitter
    ships — and ``None`` otherwise; a vertex without one is a real state
    (no authority claimed it), never a zero.
    """
    opener = bz2.open if path.endswith(".bz2") else open
    with opener(path, "rt", errors="replace") as handle:
        text = handle.read()
    nodes: dict = {}
    for match in _NODE_BLOCK.finditer(text):
        block, nid = match.group(0), match.group(2)
        lat, lon = _LAT.search(block), _LON.search(block)
        if not lat or not lon:
            continue
        alt = _ALT.search(block)
        nodes[nid] = (float(lat.group(1)), float(lon.group(1)),
                      float(alt.group(1)) if alt else None,
                      dict(_TAG.findall(block)))
    ways = [(m.group(2), _ND_REF.findall(m.group(3)),
             dict(_TAG.findall(m.group(3))))
            for m in _WAY_BLOCK.finditer(text)]
    return nodes, ways


def metres_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Local equirectangular metres between two ``(lat, lon)`` pairs."""
    lat_m = 111320.0
    lon_m = 111320.0 * math.cos(math.radians((a[0] + b[0]) / 2.0))
    return math.hypot((a[0] - b[0]) * lat_m, (a[1] - b[1]) * lon_m)


def ways_near(nodes: dict, ways: list, probe: tuple[float, float],
              radius_m: float, role: str | None = None) -> list:
    """Ways with a node within ``radius_m`` of ``probe``, nearest first.

    ``role`` filters on the emitted ``role`` tag (the patch's own role
    literal), which is how a site question is usually scoped: "what
    tunnel_ramp is here", not "what is here".
    """
    out = []
    for way_id, nds, tags in ways:
        if role is not None and tags.get("role") != role:
            continue
        best = None
        for nid in nds:
            value = nodes.get(nid)
            if value is None:
                continue
            distance = metres_between((value[0], value[1]), probe)
            if best is None or distance < best:
                best = distance
        if best is None or best > radius_m:
            continue
        alts = [nodes[n][2] for n in nds
                if n in nodes and nodes[n][2] is not None]
        out.append({
            "way": way_id,
            "distance_m": round(best, 2),
            "nodes": len(nds),
            "alt_min": round(min(alts), 3) if alts else None,
            "alt_max": round(max(alts), 3) if alts else None,
            "tags": tags,
        })
    out.sort(key=lambda row: row["distance_m"])
    return out


def dump_way(nodes: dict, ways: list, way_id: str,
             probe: tuple[float, float] | None = None) -> list:
    """One way's node chain in order: index, id, lat/lon, alt, distance."""
    for wid, nds, _tags in ways:
        if wid != way_id:
            continue
        rows = []
        for index, nid in enumerate(nds):
            value = nodes.get(nid)
            if value is None:
                rows.append({"i": index, "node": nid, "missing": True})
                continue
            row = {"i": index, "node": nid, "lat": value[0],
                   "lon": value[1], "alt_abs": value[2]}
            if probe is not None:
                row["distance_m"] = round(
                    metres_between((value[0], value[1]), probe), 2)
            rows.append(row)
        return rows
    return []


def _probe(text: str) -> tuple[float, float]:
    lat, lon = (float(part) for part in text.split(","))
    return (lat, lon)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+",
                        help=".osm patch or .osm/.osm.bz2 feed")
    parser.add_argument("--at", help="lat,lon probe point")
    parser.add_argument("--radius", type=float, default=60.0)
    parser.add_argument("--role", default=None,
                        help="only ways carrying this role tag")
    parser.add_argument("--dump", default=None,
                        help="way id — print its node chain instead")
    parser.add_argument("--tag-keys", default=None,
                        help="comma list of tag keys to show (default all)")
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    if args.dump is None and not args.at:
        parser.error("--at is required unless --dump is given")
    probe = _probe(args.at) if args.at else None
    keys = (args.tag_keys.split(",") if args.tag_keys else None)

    report: dict = {"probe": probe, "radius_m": args.radius, "files": []}
    for path in args.files:
        nodes, ways = read_osm(path)
        entry: dict = {"path": path, "nodes": len(nodes),
                       "ways": len(ways)}
        if args.dump is not None:
            entry["dump"] = dump_way(nodes, ways, args.dump, probe)
            print(f"=== {path}: way {args.dump}")
            for row in entry["dump"]:
                if row.get("missing"):
                    print(f"  {row['i']:4d} {row['node']:>12} MISSING")
                    continue
                distance = (f" d={row['distance_m']:8.2f}"
                            if "distance_m" in row else "")
                print(f"  {row['i']:4d} {row['node']:>12} "
                      f"{row['lat']:.9f} {row['lon']:.9f} "
                      f"alt={row['alt_abs']}{distance}")
        else:
            rows = ways_near(nodes, ways, probe, args.radius, args.role)
            if keys is not None:
                for row in rows:
                    row["tags"] = {k: v for k, v in row["tags"].items()
                                   if k in keys}
            entry["near"] = rows
            print(f"=== {path}: {len(rows)} way(s) within "
                  f"{args.radius:.1f} m of {probe[0]},{probe[1]}")
            for row in rows:
                print(f"  {row['distance_m']:8.2f}m  way {row['way']:>10}  "
                      f"n={row['nodes']:<4} "
                      f"alt=[{row['alt_min']},{row['alt_max']}]  "
                      f"{json.dumps(row['tags'], sort_keys=True)}")
        report["files"].append(entry)

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(report, handle, indent=2)
        print(f"JSON -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
