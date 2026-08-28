#!/usr/bin/env python
"""WHAT IS AT THIS COORDINATE — ways near a point, in a patch or a feed.

Promoted 2026-08-12 from the round-20 lane's scratchpad readers
``kclt_site.py`` (emitted patches) and ``osmfeed.py`` (bz2 road feeds) on
their SECOND use (RULINGS ``7e90032``, promote-on-reuse).  They were two
copies of one question asked of two file formats, which is exactly the
shape the census-wrapper precedent warns about — one grew an ``alt_abs``
reader and the other grew bz2, and neither could read the other's file.
One reader now handles both.

THE THIRD ROAD SOURCE (2026-08-28, the LEMD ramp/road fidelity round).
At LEMD the tile carries NO small-roads extract and ``big_roads`` is
empty at the tunnel sites, so the road corridors derive from the X-Plane
DSF VECTOR ROAD NETWORK sidecar
(``Airport_mod_cache/<pack>/o4_dsf_road_network_<tile>.cache``) — the
source neither dialect above can read, and the one an attribution of a
corridor's WIDTH and CENTRE has to start from.  A ``.cache`` FILE is
unpickled and its segments are presented as ways in exactly the shape
above, so ``--at`` / ``--dump`` / ``--json`` work unchanged.  The record
types come from the engine's own ``auto_patch.dsf_road_network``: this
reader never re-parses a DSF and never grows a second road parser.

It MEASURES NOTHING and DERIVES NO LAW.  Every value printed is read
verbatim out of the file: way ids, tags, node ids, coordinates, the
``alt_abs`` a node carries.  Defect counts come from
``tools/harness/census.py`` and from nowhere else; this answers "which
ways are here, what are they tagged, and what altitudes do their nodes
carry", which is the question an attribution starts from.

    venv/bin/python tools/osm_site.py FILE [FILE...] --at LAT,LON
        [--radius M] [--role ROLE] [--tag-keys k,k] [--json OUT]
    venv/bin/python tools/osm_site.py FILE --dump WAY_ID [--at LAT,LON]
    venv/bin/python tools/osm_site.py o4_dsf_road_network_+40-004.cache
        --at LAT,LON [--by-line]

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

TWO SELECTION FRAMES, and the one in force is printed on every report.
By default a way is selected and ranked by its nearest NODE, which is the
frame every existing caller reads in.  ``--by-line`` selects and ranks by
the closest approach to the POLYLINE between consecutive nodes instead —
the frame a DSF road segment needs, because its shape points can stand
tens of metres apart while the road itself passes right over the probe.
It is ON by default for a ``.cache`` file and OFF for OSM; ``--by-line``
/ ``--by-node`` force it either way.  Both distances are always reported,
so the two frames are never silently mixed.
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


#: A ``.cache`` FILE is the DSF vector road-network sidecar, and it is the
#: only container this reader unpickles.  Named here so the dispatch and
#: the ``--by-line`` default read one rule.
DSF_ROAD_CACHE_SUFFIX = ".cache"


def read_dsf_road_network(path: str) -> tuple[dict, list]:
    """The DSF vector road-network sidecar, in ``read_osm``'s own shape.

    ``Airport_mod_cache/<pack>/o4_dsf_road_network_<tile>.cache`` is the
    pickle ``object_terrain_assembly._discover_sibling_road_networks``
    writes: ``{"fingerprint": str, "result": RoadNetwork}``.  Each
    :class:`auto_patch.dsf_road_network.RoadSegment` becomes one "way"
    whose nodes are its shape points in order, so every selection, dump
    and JSON path above works on it unchanged.

    The record types are the ENGINE's (``auto_patch.dsf_road_network``,
    imported so the unpickle resolves them) — this tool re-parses no DSF
    and states no second grammar.  A node carries no ``alt_abs``: the
    network's third column is a draping LEVEL FLAG, not an elevation
    (module docstring, ``LEVEL_DRAPED_MAX_ABS``), so it is reported as
    the ``level`` / ``draped`` tags it is and never as an altitude.
    """
    import os
    import pickle

    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
    try:
        from auto_patch import dsf_road_network  # noqa: F401
    except ImportError as error:                       # pragma: no cover
        raise SystemExit(
            f"REFUSED: cannot import auto_patch.dsf_road_network "
            f"({error}) — the sidecar holds its record types and "
            f"unpickling without them would be a second parser")
    with open(path, "rb") as handle:
        payload = pickle.load(handle)
    network = (payload or {}).get("result") if isinstance(payload, dict) \
        else None
    if network is None or not hasattr(network, "segments"):
        raise SystemExit(
            f"REFUSED: {path} is not a DSF road-network sidecar "
            f"(no RoadNetwork under 'result')")
    nodes: dict = {}
    ways: list = []
    for index, segment in enumerate(network.segments):
        way_id = f"seg{index}"
        refs: list[str] = []
        for position, point in enumerate(segment.shape_points):
            node_id = f"{way_id}:{position}"
            nodes[node_id] = (
                float(point.latitude), float(point.longitude), None,
                {"level": f"{point.level:.6f}",
                 "draped": "yes" if point.draped else "no"})
            refs.append(node_id)
        draped = [point.draped for point in segment.shape_points]
        ways.append((way_id, refs, {
            "source": "dsf-road-network",
            "road_subtype": str(segment.road_subtype),
            "net_def": segment.network_definition_path,
            "draped": ("all" if all(draped)
                       else "none" if not any(draped) else "partial"),
            "junctions": (f"{segment.start_junction_id}-"
                          f"{segment.end_junction_id}"),
        }))
    return nodes, ways


def read_site_file(path: str) -> tuple[dict, list]:
    """Dispatch on the container: the DSF road-network sidecar, else OSM."""
    if path.endswith(DSF_ROAD_CACHE_SUFFIX):
        return read_dsf_road_network(path)
    return read_osm(path)


def metres_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Local equirectangular metres between two ``(lat, lon)`` pairs."""
    lat_m = 111320.0
    lon_m = 111320.0 * math.cos(math.radians((a[0] + b[0]) / 2.0))
    return math.hypot((a[0] - b[0]) * lat_m, (a[1] - b[1]) * lon_m)


def _metres_to_segment(probe: tuple[float, float],
                       a: tuple[float, float],
                       b: tuple[float, float]) -> float:
    """Closest approach from ``probe`` to the segment ``a``–``b``, in the
    same local equirectangular metres."""
    lat_m = 111320.0
    lon_m = 111320.0 * math.cos(math.radians(probe[0]))
    px, py = 0.0, 0.0
    ax = (a[1] - probe[1]) * lon_m
    ay = (a[0] - probe[0]) * lat_m
    bx = (b[1] - probe[1]) * lon_m
    by = (b[0] - probe[0]) * lat_m
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared < 1e-12:
        return math.hypot(ax - px, ay - py)
    t = ((px - ax) * dx + (py - ay) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    return math.hypot(ax + dx * t - px, ay + dy * t - py)


def ways_near(nodes: dict, ways: list, probe: tuple[float, float],
              radius_m: float, role: str | None = None,
              by_line: bool = False) -> list:
    """Ways within ``radius_m`` of ``probe``, nearest first.

    ``role`` filters on the emitted ``role`` tag (the patch's own role
    literal), which is how a site question is usually scoped: "what
    tunnel_ramp is here", not "what is here".

    ``by_line`` picks WHICH DISTANCE selects and ranks: the nearest NODE
    (default — the frame every pre-2026-08-28 caller reads in) or the
    closest approach to the POLYLINE.  Both are always reported, as
    ``distance_m`` and ``line_distance_m``, so the two frames can never
    be mixed unnoticed; ``line_distance_m`` is ``None`` for a way with
    fewer than two placed nodes.
    """
    out = []
    for way_id, nds, tags in ways:
        if role is not None and tags.get("role") != role:
            continue
        placed = [(nodes[n][0], nodes[n][1]) for n in nds if n in nodes]
        best = None
        for point in placed:
            distance = metres_between(point, probe)
            if best is None or distance < best:
                best = distance
        line_best = None
        for index in range(len(placed) - 1):
            distance = _metres_to_segment(
                probe, placed[index], placed[index + 1])
            if line_best is None or distance < line_best:
                line_best = distance
        if best is None:
            continue
        selector = (line_best if by_line and line_best is not None else best)
        if selector > radius_m:
            continue
        alts = [nodes[n][2] for n in nds
                if n in nodes and nodes[n][2] is not None]
        out.append({
            "way": way_id,
            "distance_m": round(best, 2),
            "line_distance_m": (None if line_best is None
                                else round(line_best, 2)),
            "selected_by": "line" if by_line else "node",
            "nodes": len(nds),
            "alt_min": round(min(alts), 3) if alts else None,
            "alt_max": round(max(alts), 3) if alts else None,
            "tags": tags,
        })
    out.sort(key=lambda row: (
        row["line_distance_m"] if (by_line
                                   and row["line_distance_m"] is not None)
        else row["distance_m"]))
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
                        help=".osm patch, .osm/.osm.bz2 feed, or a "
                             "DSF road-network .cache sidecar")
    parser.add_argument("--at", help="lat,lon probe point")
    parser.add_argument("--radius", type=float, default=60.0)
    parser.add_argument("--role", default=None,
                        help="only ways carrying this role tag")
    parser.add_argument("--dump", default=None,
                        help="way id — print its node chain instead")
    parser.add_argument("--tag-keys", default=None,
                        help="comma list of tag keys to show (default all)")
    parser.add_argument("--json", default=None)
    frame = parser.add_mutually_exclusive_group()
    frame.add_argument(
        "--by-line", dest="by_line", action="store_true", default=None,
        help="select and rank by closest approach to the POLYLINE "
             "(default for a DSF road-network .cache)")
    frame.add_argument(
        "--by-node", dest="by_line", action="store_false",
        help="select and rank by the nearest NODE (default for OSM)")
    args = parser.parse_args(argv)

    if args.dump is None and not args.at:
        parser.error("--at is required unless --dump is given")
    probe = _probe(args.at) if args.at else None
    keys = (args.tag_keys.split(",") if args.tag_keys else None)

    report: dict = {"probe": probe, "radius_m": args.radius, "files": []}
    for path in args.files:
        nodes, ways = read_site_file(path)
        by_line = (args.by_line if args.by_line is not None
                   else path.endswith(DSF_ROAD_CACHE_SUFFIX))
        entry: dict = {"path": path, "nodes": len(nodes),
                       "ways": len(ways),
                       "selection_frame": "line" if by_line else "node"}
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
            rows = ways_near(nodes, ways, probe, args.radius, args.role,
                             by_line=by_line)
            if keys is not None:
                for row in rows:
                    row["tags"] = {k: v for k, v in row["tags"].items()
                                   if k in keys}
            entry["near"] = rows
            print(f"=== {path}: {len(rows)} way(s) within "
                  f"{args.radius:.1f} m of {probe[0]},{probe[1]} "
                  f"[selected by {'polyline' if by_line else 'nearest node'}]")
            for row in rows:
                line = ("     -" if row["line_distance_m"] is None
                        else f"{row['line_distance_m']:8.2f}")
                print(f"  node={row['distance_m']:8.2f}m "
                      f"line={line}m  way {row['way']:>10}  "
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
