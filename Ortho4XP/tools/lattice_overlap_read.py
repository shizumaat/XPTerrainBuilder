"""LATTICE / SPINE-STATION OVERLAP READ — does an emitted apron-membrane
SEGMENT leave the apron it belongs to?

THE QUESTION, AND WHY NO EXISTING TOOL ANSWERS IT.  ``harness/census.py``
prices PAIRS OF VALUES; a breakline that runs straight through a carved
building breaks no grade law, so a census reports it at zero rows however
wrong it looks in the sim.  ``osm_site.py`` says what is at a coordinate
and ``arm_site_read.py`` answers one named place; neither sweeps a whole
patch asking a CONTAINMENT question.  This is that sweep, and it is a
MEASUREMENT: it prices nothing, it registers no law family, and defect
counts come from the census and nowhere else.

MEASURED BASIS (owner sim read of 1.0.260, RULINGS 2026-08-26b item 1).
At HECA, 7 of 940 emitted ``apron_lattice`` segments left the apron
footprint — 89.6 m: 28.1 m through building way -10158, 23.5 m through
junctions -12775/-12776, the rest through graded strips.  Mechanism:
``apron_lattice._rows_and_columns`` joined consecutive grid POINTS into
straight polylines with only per-POINT containment, so a segment between
two lawful points bridged holes and concavities.  Round 3 §2 clips per
segment; this tool is how that is verified, and how a regression in the
same class would be caught.

TWO PARSE CONVENTIONS, DELIBERATELY.  Geometry, the metre frame and the
role-carrying rings come from the harness library itself
(``check_grade._parse_osm`` / ``_ll_to_m_factory`` about the sidecar's
own anchor) — imported, never re-spelled, which is the census-wrapper
precedent.  But ``_parse_osm`` DROPS ANY WAY WITH FEWER THAN THREE
NODES before its open-feature route, and a two-node membrane breakline
is exactly what a short apron crossing emits: read through that parser
alone, 13 of 18 HECA station crossings were invisible and the tool
reported an apron as stationless while the patch carried stations on it.
So the FEATURE ways are parsed here directly, and only the feature ways
— the footprint they are judged against is still the library's.

A segment is reported when more than ``--tolerance`` metres of it lie
outside the union of the emitted ``apron`` rings; the default is the
emit rounding, not a law threshold.  For each one the tool names what it
passes through (role and way id, by intersection length), which is the
attribution the fix is written against.

    venv/bin/python tools/lattice_overlap_read.py PATCH.osm [PATCH.osm ...]
        [--features apron_lattice,apron_spine_station] [--tolerance M]
        [--top N] [--json OUT.json]

Run from ``Ortho4XP/``.  Several patches are reported separately — that
is the arm-to-arm read; quote it on identical options, never as a
verdict.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The emitted ``o4_feature`` classes that ARE apron membrane: open
#: constrained breaklines living inside an apron face.  Both are
#: role-less (``check_grade.ROLE_LESS_FEATURE_CLASSES``) and both are
#: priced by the one ``apron_lattice_membrane`` family.
DEFAULT_FEATURES = ("apron_lattice", "apron_spine_station")

#: Below this many metres outside, a segment is emit rounding on the ring
#: it runs beside, not an excursion.  NOT a law threshold — this tool
#: prices nothing.
DEFAULT_TOLERANCE_M = 0.05

#: The role whose emitted rings ARE the footprint a membrane segment must
#: stay inside.  A literal, and flagged as one: renaming ``ROLE_APRON``'s
#: VALUE in ``auto_patch/layout.py`` breaks this file silently.
APRON_ROLE = "apron"


def _feature_ways(path):
    """``{o4_feature: [[node_id, ...], ...]}`` straight out of the patch.

    Parsed HERE rather than through ``check_grade._parse_osm`` for one
    measured reason, stated in the module docstring: that parser drops a
    way with fewer than three nodes before its open-feature route, and a
    two-node membrane breakline is precisely what a short apron crossing
    emits.  Nothing else is read here — roles, geometry and the metre
    frame all come from the library.
    """
    import xml.etree.ElementTree as ET
    out: dict = {}
    root = ET.parse(str(path)).getroot()
    for w in root.findall("way"):
        cls = None
        for tg in w.findall("tag"):
            if tg.get("k") == "o4_feature":
                cls = tg.get("v")
                break
        if cls is None:
            continue
        nids = [nd.get("ref") for nd in w.findall("nd")]
        if len(nids) >= 2:
            out.setdefault(cls, []).append(nids)
    return out


def _ll_of(anchor, xy):
    """The INVERSE of the harness library's own metre frame, so a
    reported coordinate is in the frame the sidecar declares.  The
    forward map is ``check_grade._ll_to_m_factory``; this is only for
    REPORTING a position, never for measuring one."""
    import math
    lat = float(anchor[0]) + xy[1] / 111320.0
    lon = float(anchor[1]) + xy[0] / (
        111320.0 * max(1e-9, math.cos(math.radians(float(anchor[0])))))
    return [round(lat, 7), round(lon, 7)]


def read(path, *, features=DEFAULT_FEATURES,
         tolerance_m=DEFAULT_TOLERANCE_M):
    """``{feature_class: {...}}`` for one emitted patch.

    Per class: ``ways``, ``segments``, ``outside_total_m`` and the
    ``outside`` list — one entry per offending segment with the metres
    outside, the (role, way id, metres) it passes through, and the
    segment midpoint in metres and lat/lon.
    """
    import math
    import check_grade as CG
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union

    path = Path(path)
    nodes, ways = CG._parse_osm(path)
    side = json.loads(Path(str(path) + ".axes.json").read_text())
    anchor = tuple(side["anchor"])
    to_m = CG._ll_to_m_factory(nodes, anchor)

    aprons: list = []
    others: list = []
    for w in ways:
        pts = [to_m(*nodes[n]) for n in w.nids if n in nodes]
        if len(pts) < 4:
            continue
        try:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
        except Exception:                                 # pragma: no cover
            continue
        if w.role == APRON_ROLE:
            aprons.append(poly)
        else:
            others.append((w.role or "?", w.wid, poly))
    footprint = unary_union(aprons) if aprons else None

    feats = _feature_ways(path)
    out: dict = {}
    for cls in features:
        n_ways = 0
        n_segs = 0
        bad: list = []
        for nids in feats.get(cls, ()):
            pts = [to_m(*nodes[n]) for n in nids if n in nodes]
            if len(pts) < 2:
                continue
            n_ways += 1
            for a, b in zip(pts, pts[1:]):
                n_segs += 1
                ls = LineString([a, b])
                if footprint is not None and footprint.contains(ls):
                    continue
                outside = (ls.difference(footprint).length
                           if footprint is not None else ls.length)
                if outside <= float(tolerance_m):
                    continue
                through: list = []
                for (role, wid, poly) in others:
                    if not poly.intersects(ls):
                        continue
                    seg = poly.intersection(ls)
                    length = float(getattr(seg, "length", 0.0) or 0.0)
                    if length > float(tolerance_m):
                        through.append((role, wid, round(length, 1)))
                through.sort(key=lambda t: -t[2])
                mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))
                bad.append({
                    "outside_m": round(float(outside), 2),
                    "through": through,
                    "mid_m": [round(mid[0], 1), round(mid[1], 1)],
                    "mid_ll": _ll_of(anchor, mid)})
        bad.sort(key=lambda d: -d["outside_m"])
        out[cls] = {"ways": n_ways, "segments": n_segs, "outside": bad,
                    "outside_total_m": round(
                        sum(d["outside_m"] for d in bad), 1)}
    return out


def format_report(path, result, *, top=12):
    lines = [f"== {path}"]
    for cls, d in result.items():
        lines.append(
            f"  {cls}: {d['ways']} way(s) / {d['segments']} segment(s); "
            f"{len(d['outside'])} leaving the apron footprint, "
            f"{d['outside_total_m']} m")
        for b in d["outside"][:top]:
            lines.append(f"     {b['outside_m']} m out at "
                         f"{tuple(b['mid_m'])} through {b['through']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Emitted apron-membrane segments that leave their "
                    "apron footprint.  A MEASUREMENT: it prices no law "
                    "and counts no defects.")
    ap.add_argument("patches", nargs="+", help="emitted patch .osm")
    ap.add_argument("--features", default=",".join(DEFAULT_FEATURES),
                    help="comma list of o4_feature classes to sweep")
    ap.add_argument("--tolerance", type=float,
                    default=DEFAULT_TOLERANCE_M,
                    help="metres outside below which a segment is emit "
                         "rounding, not an excursion")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args(argv)
    features = tuple(f for f in args.features.split(",") if f)
    payload: dict = {}
    for p in args.patches:
        if not Path(str(p) + ".axes.json").exists():
            raise SystemExit(
                f"REFUSING: {p} has no .axes.json sidecar — without the "
                f"anchor there is no metre frame to measure in, and a "
                f"guessed one is a different projection.")
        res = read(p, features=features, tolerance_m=args.tolerance)
        payload[str(p)] = res
        print(format_report(p, res, top=args.top))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=1))
    return 0


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
