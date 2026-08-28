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
    venv/bin/python tools/osm_site.py FILE --at LAT,LON --contains
    venv/bin/python tools/osm_site.py FILE --line LAT,LON:LAT,LON
        [--step M] [--role ROLE]

``--contains`` IS THE SECOND QUESTION, and it is not the first one.
``--at`` reports the distance to a way's nearest NODE, so a point deep
inside a large ring reads tens of metres away and NEVER 0.00 m — a
lane read "1.20 m / 11.60 m outside" off exactly that and had to be
corrected by a containment read (spec ``lemd-basin-trench-ramp-
extension`` Amendment 2, the two owner probes that turned out to be
9.87 m and 3.88 m INSIDE the pad).  ``--contains`` asks the question
the confusion was about: WHICH RINGS COVER THIS POINT.  Rings are
grouped by ``(role, ref)`` and decided EVEN-ODD inside each group, so a
point in a hole ring is OUTSIDE its own pad, not inside two ways.

``--line A:B [--step M]`` is that same containment answered along a
SEGMENT, station by station — the reading a "the plate covers the whole
ramp" acceptance is stated in (spec ``lemd-pad-authority-carve`` §
Acceptance samples the deck line at ~2 m).  An EMPTY station list is
itself a finding; so is a run of stations inside nothing.

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
import os
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

#: This tool's own directory — where ``check_grade`` (the harness
#: library) lives, so the containment read imports the library's parser
#: rather than growing a second one.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


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


def _library_rings(path: str, probe: tuple[float, float]) -> list:
    """``[(role, ref, way_id, shapely ring in metres about probe), ...]``.

    Geometry comes from the HARNESS LIBRARY's own parser
    (``check_grade._parse_osm``) — imported, never re-spelled, because a
    containment read and the census must agree about what a ring IS
    (the census-wrapper precedent).  The metre frame is this tool's own
    local equirectangular one about ``probe``, which is what every other
    distance it prints is in.

    Falls back to this module's ``read_osm`` when the engine tree is not
    importable (the CLI-on-a-bare-patch case ``check_grade`` itself
    provides for); a feed carries no roles, so its rings come back with
    an empty role.
    """
    from shapely.geometry import Polygon

    lat_m = 111320.0
    lon_m = 111320.0 * math.cos(math.radians(probe[0]))

    def _xy(lat, lon):
        return ((lon - probe[1]) * lon_m, (lat - probe[0]) * lat_m)

    rows = []
    try:
        sys.path.insert(0, str(_TOOLS_DIR))
        from pathlib import Path as _Path

        import check_grade as _cg
        nodes, ways = _cg._parse_osm(_Path(path))
        source = [(w.wid, w.role, w.ref, w.nids) for w in ways]
        coordinates = nodes
    except Exception:
        raw_nodes, raw_ways = read_osm(path)
        source = [(wid, tags.get("role", ""), tags.get("ref", ""), nds)
                  for wid, nds, tags in raw_ways]
        coordinates = {nid: (value[0], value[1])
                       for nid, value in raw_nodes.items()}
    for way_id, role, ref, nids in source:
        ring = [_xy(*coordinates[nid]) for nid in nids
                if nid in coordinates]
        if len(ring) < 3:
            continue
        try:
            polygon = Polygon(ring)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
        except Exception:
            continue
        if polygon.is_empty:
            continue
        rows.append((role, ref, way_id, polygon))
    return rows


def contains_at(rings: list, point_xy: tuple[float, float],
                role: str | None = None) -> list:
    """``[{group, role, ref, ways, inside}, ...]`` — the EVEN-ODD
    containment verdict per ``(role, ref)`` group at one point.

    EVEN-ODD, not "any ring covers it", because that is what a hole IS:
    the emitter ships an interior ring as its own closed way under the
    same ``ref``, so a point in the hole is covered by two rings of the
    group and belongs to neither.  Counting "any" would report a pad as
    covering ground it deliberately does not.
    """
    from shapely.geometry import Point

    probe_point = Point(*point_xy)
    groups: dict = {}
    for ring_role, ref, way_id, polygon in rings:
        if role is not None and ring_role != role:
            continue
        try:
            if not polygon.covers(probe_point):
                continue
        except Exception:
            continue
        key = (ring_role, ref)
        groups.setdefault(key, []).append(way_id)
    out = []
    for (ring_role, ref), way_ids in sorted(groups.items()):
        out.append({
            "role": ring_role, "ref": ref,
            "ways": sorted(way_ids),
            "covering_rings": len(way_ids),
            "inside": len(way_ids) % 2 == 1,
        })
    return out


def line_stations(start: tuple[float, float], end: tuple[float, float],
                  step_m: float) -> list:
    """``[(lat, lon, station_m), ...]`` every ``step_m`` along the
    segment, BOTH ENDS INCLUDED.

    The end is always a station even when the length is not a whole
    multiple of the step: an acceptance stated as "everywhere along the
    deck line" that silently stopped 1.9 m short of the end would be
    answering a shorter question than it was asked.
    """
    length = metres_between(start, end)
    if not (length > 0.0) or not (step_m > 0.0):
        return [(start[0], start[1], 0.0)]
    count = int(math.floor(length / step_m))
    stations = []
    for index in range(count + 1):
        fraction = (index * step_m) / length
        stations.append((
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction,
            index * step_m,
        ))
    if stations[-1][2] < length - 1e-9:
        stations.append((end[0], end[1], length))
    return stations


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
    parser.add_argument("--contains", action="store_true",
                        help="which RINGS COVER the --at point (even-odd "
                             "per role/ref group) instead of node distance")
    parser.add_argument("--line", default=None,
                        help="LAT,LON:LAT,LON — containment station by "
                             "station along a segment")
    parser.add_argument("--step", type=float, default=2.0,
                        help="--line: station spacing in metres")
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    if args.dump is None and not args.at and not args.line:
        parser.error("--at is required unless --dump or --line is given")
    if args.line and args.step <= 0.0:
        parser.error("--step must be positive")
    line = None
    if args.line:
        try:
            start_text, end_text = args.line.split(":")
        except ValueError:
            parser.error("--line takes LAT,LON:LAT,LON")
        line = (_probe(start_text), _probe(end_text))
    probe = _probe(args.at) if args.at else (line[0] if line else None)
    keys = (args.tag_keys.split(",") if args.tag_keys else None)

    report: dict = {"probe": probe, "radius_m": args.radius, "files": []}
    for path in args.files:
        nodes, ways = read_osm(path)
        entry: dict = {"path": path, "nodes": len(nodes),
                       "ways": len(ways)}
        if args.line is not None or args.contains:
            rings = _library_rings(path, probe)
            lat_m = 111320.0
            lon_m = 111320.0 * math.cos(math.radians(probe[0]))

            def _xy(latitude, longitude):
                return ((longitude - probe[1]) * lon_m,
                        (latitude - probe[0]) * lat_m)

            if args.line is not None:
                stations = line_stations(line[0], line[1], args.step)
                rows = []
                for latitude, longitude, station in stations:
                    groups = contains_at(
                        rings, _xy(latitude, longitude), args.role)
                    rows.append({
                        "station_m": round(station, 2),
                        "lat": round(latitude, 11),
                        "lon": round(longitude, 11),
                        "inside": [
                            {"role": g["role"], "ref": g["ref"]}
                            for g in groups if g["inside"]],
                    })
                entry["line"] = rows
                covered = sum(1 for row in rows if row["inside"])
                print(f"=== {path}: {len(rows)} station(s) every "
                      f"{args.step:.2f} m along the line; {covered} "
                      f"inside something"
                      + (f" (role={args.role})" if args.role else ""))
                for row in rows:
                    names = ", ".join(
                        f"{g['role']}:{g['ref']}" for g in row["inside"])
                    print(f"  s={row['station_m']:8.2f}m  "
                          f"{row['lat']:.9f} {row['lon']:.9f}  "
                          f"{names or 'OUTSIDE EVERYTHING'}")
            else:
                groups = contains_at(rings, (0.0, 0.0), args.role)
                entry["contains"] = groups
                inside = [g for g in groups if g["inside"]]
                print(f"=== {path}: {len(inside)} ring group(s) COVER "
                      f"{probe[0]},{probe[1]}"
                      + (f" (role={args.role})" if args.role else ""))
                for group in groups:
                    verdict = "INSIDE " if group["inside"] else "in-a-hole"
                    print(f"  {verdict} {group['role']}:{group['ref']}  "
                          f"rings={group['covering_rings']}  "
                          f"ways={','.join(group['ways'])}")
        elif args.dump is not None:
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
