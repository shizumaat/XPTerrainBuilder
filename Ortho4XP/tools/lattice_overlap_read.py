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

``--on-edge`` IS THE SECOND QUESTION, SAME POPULATION, SAME PARSER
(promoted from the lane/lemd123 scratch sweep per RULINGS ``7e90032``;
spec ``docs/specs/lemd-rim-and-stations-spec.md`` §D).  A membrane node
can be perfectly INSIDE its apron and still be a defect: if it lands ON
a ring EDGE without being a vertex of that ring it is an unwelded
T-vertex, two constrained segments ~2 cm apart, which is the documented
mm-jitter segment-recovery killer and what the owner saw as texture
tearing at LEMD 40.4968469,-3.5645062 (RULINGS 2026-08-28 item 1) and at
HECA 30.109477,31.4036224 (RULINGS 2026-08-28b item 4).  Measured basis
at 1.0.263: 144 such nodes across four patches — LEMD 76, HECA 29,
SPJC 33, CYXY 6 — every one on a boundary SHARED by two rings, hosts 121
apron / 23 junction, worst value tear 0.907 m.  §A closes it; this
subcommand is how that is verified and how the class is caught again.

    venv/bin/python tools/lattice_overlap_read.py PATCH.osm [PATCH.osm ...]
        [--features apron_lattice,apron_spine_station] [--tolerance M]
        [--top N] [--json OUT.json]
        [--on-edge [--near M] [--vertex-tol M]]

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
    """``{o4_feature: [(way_id, [node_id, ...]), ...]}`` straight out of
    the patch.

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
            out.setdefault(cls, []).append((w.get("id"), nids))
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
        for (_wid, nids) in feats.get(cls, ()):
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


#: ``--on-edge``: how far off a ring EDGE a feature node may sit and
#: still count as ON it.  Emit rounding, not a law threshold.
DEFAULT_NEAR_M = 1.0

#: ``--on-edge``: within this of an edge ENDPOINT the node is that
#: endpoint, not a T-vertex.  The registry's own bucket size
#: (``layout.SHARED_VERTEX_TOL_M``), quoted here as a literal because a
#: measurement tool must not import solver state.
DEFAULT_VERTEX_TOL_M = 0.5


def read_on_edge(path, *, features=DEFAULT_FEATURES,
                 near_m=DEFAULT_NEAR_M,
                 vertex_tol_m=DEFAULT_VERTEX_TOL_M):
    """``--on-edge``: which emitted feature NODES sit ON a ring edge of
    an existing shape without being a vertex of it — UNWELDED T-VERTICES,
    which is what the owner saw as texture tearing at LEMD
    40.4968469,-3.5645062 (RULINGS 2026-08-28 item 1) and again at HECA
    30.109477,31.4036224 (RULINGS 2026-08-28b item 4).

    THE SAME PARSE CONTRACT as ``read`` above, for the same measured
    reason: geometry, roles and the metre frame come from the harness
    library; the FEATURE ways come from ``_feature_ways`` because
    ``check_grade._parse_osm`` drops any way with fewer than three nodes
    before its open-feature route — and the LEMD station way the owner
    named has exactly three.

    A node is reported when it is not already a ring node id, its foot on
    some ring edge is within ``near_m`` perpendicular, and that foot is
    strictly interior and at least ``vertex_tol_m`` from either endpoint.
    Every host of the shared boundary is listed, with the VALUE TEAR
    against each host's own lerp at the foot.

    Prices no law, counts no defects.  Per class: ``nodes``,
    ``shared_with_a_ring``, ``on_edge_unwelded`` and the ``rows``.
    """
    import math
    import check_grade as CG
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree

    path = Path(path)
    fout: dict = {}
    nodes, ways = CG._parse_osm(path, feature_out=fout)
    fways = {}
    for _cls, _lst in fout.items():
        for _w in _lst:
            fways[str(_w.wid)] = _w
    side = json.loads(Path(str(path) + ".axes.json").read_text())
    anchor = tuple(side["anchor"])
    to_m = CG._ll_to_m_factory(nodes, anchor)

    edges: list = []    # (ax, ay, bx, by, role, wid, za, zb, na, nb)
    verts: list = []
    ring_nids: set = set()
    for w in ways:
        pts, nids, zs = [], [], []
        for k, n in enumerate(w.nids):
            if n in nodes:
                pts.append(to_m(*nodes[n]))
                nids.append(n)
                zs.append(w.elevs[k] if k < len(w.elevs) else None)
        if len(pts) < 3:
            continue
        ring_nids.update(nids)
        for i in range(len(pts)):
            a = pts[i]
            b = pts[(i + 1) % len(pts)]
            j = (i + 1) % len(pts)
            edges.append((a[0], a[1], b[0], b[1], w.role or "?", w.wid,
                          zs[i], zs[j], nids[i], nids[j]))
        verts.extend(pts)

    etree = STRtree([LineString([(e[0], e[1]), (e[2], e[3])])
                     for e in edges]) if edges else None
    vtree = STRtree([Point(x, y) for (x, y) in verts]) if verts else None

    feats = _feature_ways(path)
    out: dict = {}
    for cls in features:
        seen: dict = {}
        salt: dict = {}
        for (wid, nids) in feats.get(cls, ()):
            fw = fways.get(str(wid))
            for k, n in enumerate(nids):
                if n in nodes:
                    seen.setdefault(n, wid)
                    if fw is not None and k < len(fw.elevs):
                        salt.setdefault(n, fw.elevs[k])
        rows: list = []
        n_shared = 0
        for n, wid in seen.items():
            if n in ring_nids:
                n_shared += 1
                continue
            x, y = to_m(*nodes[n])
            dv = None
            if vtree is not None:
                p = Point(x, y)
                for j in vtree.query(
                        p.buffer(max(near_m, vertex_tol_m) * 4)):
                    vx, vy = verts[int(j)]
                    d = math.hypot(vx - x, vy - y)
                    if dv is None or d < dv:
                        dv = d
            best = None
            hosts: list = []
            if etree is not None:
                p = Point(x, y)
                for j in etree.query(p.buffer(near_m * 4)):
                    (ax, ay, bx, by, role, ewid, za, zb,
                     _na, _nb) = edges[int(j)]
                    dx, dy = bx - ax, by - ay
                    L2 = dx * dx + dy * dy
                    if L2 < 1e-12:
                        continue
                    L = math.sqrt(L2)
                    t = ((x - ax) * dx + (y - ay) * dy) / L2
                    if t <= 0.0 or t >= 1.0:
                        continue
                    if t * L < vertex_tol_m or (1.0 - t) * L < vertex_tol_m:
                        continue                # coincident with an endpoint
                    perp = abs((x - ax) * dy - (y - ay) * dx) / L
                    if perp > near_m:
                        continue
                    lerp = (None if (za is None or zb is None)
                            else float(za) + t * (float(zb) - float(za)))
                    hosts.append((perp, role, ewid, t * L, (1.0 - t) * L,
                                  lerp))
                    if best is None or perp < best[0]:
                        best = hosts[-1]
            if best is None or best[0] > near_m:
                continue
            sa = salt.get(n)
            tears = [] if sa is None else [
                (h[2], h[1], round(float(sa) - h[5], 3))
                for h in hosts if h[5] is not None]
            rows.append({
                "node": n,
                "feature_way": wid,
                "perp_m": round(best[0], 4),
                "host_role": best[1],
                "host_way": best[2],
                "along_a_m": round(best[3], 2),
                "along_b_m": round(best[4], 2),
                "nearest_vertex_m": (round(dv, 3) if dv is not None
                                     else None),
                "ll": _ll_of(anchor, (x, y)),
                "station_alt": (None if sa is None else round(float(sa), 3)),
                "hosts": len(hosts),
                "tears": tears,
                "worst_tear_m": max((abs(t[2]) for t in tears),
                                    default=None)})
        rows.sort(key=lambda d: d["perp_m"])
        out[cls] = {"nodes": len(seen), "shared_with_a_ring": n_shared,
                    "on_edge_unwelded": len(rows), "rows": rows}

    # ── THE NEEDLE READ (owner sim load-time regression, attributed
    # 2026-08-28b) ───────────────────────────────────────────────────
    # A welded T-vertex closes the VALUE tear; the geometric cost of the
    # unwelded one is a needle fan, because two constrained segments
    # ~2 cm apart and parallel force the mesher to thread triangles
    # between them along the whole collinear run.  Same instrument, same
    # parse, because it is the same defect seen from the mesh side.
    out["near_parallel_pairs"] = _near_parallel_pairs(
        edges, feats, nodes, to_m, anchor, features)
    return out


def _near_parallel_pairs(edges, feats, nodes, to_m, anchor, features):
    """Side-by-side constrained-segment pairs: FEATURE segment x ring
    edge (the §A class), and apron ring x apron ring (a SECOND, older
    source — two rings tracing one boundary with non-identical
    spellings; reported, never conflated with the first)."""
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree

    if not edges:
        return {"feature_x_ring": [], "apron_x_apron": [],
                "by_class_and_role": {}, "feature_x_ring_coincident": 0,
                "apron_x_apron_coincident_welded": 0,
                "apron_x_apron_coincident_unwelded": 0}
    etree = STRtree([LineString([(e[0], e[1]), (e[2], e[3])])
                     for e in edges])

    def _query(seg):
        (ax, ay), (bx, by) = seg
        mid = Point(0.5 * (ax + bx), 0.5 * (ay + by))
        half = 0.5 * ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        return etree.query(mid.buffer(half + NEAR_PARALLEL_GAP_M * 2.0))

    fx: list = []
    n_coincident = [0]
    by_class_role: dict = {}
    for cls in features:
        for (wid, nids) in feats.get(cls, ()):
            pts = [to_m(*nodes[n]) for n in nids if n in nodes]
            for a, b in zip(pts, pts[1:]):
                seg = (a, b)
                for j in _query(seg):
                    e = edges[int(j)]
                    hit = _near_parallel(seg, ((e[0], e[1]), (e[2], e[3])))
                    if hit is None:
                        continue
                    if hit[0] <= COINCIDENT_GAP_M:
                        # ONE line, welded: the mesher sees a single
                        # constraint and no fan follows.
                        n_coincident[0] += 1
                        continue
                    key = f"{cls} x {e[4]}"
                    by_class_role[key] = by_class_role.get(key, 0) + 1
                    fx.append({
                        "feature": cls, "feature_way": wid,
                        "host_role": e[4], "host_way": e[5],
                        "gap_m": round(hit[0], 4),
                        "overlap_m": round(hit[1], 2),
                        "ll": _ll_of(anchor,
                                     (0.5 * (a[0] + b[0]),
                                      0.5 * (a[1] + b[1])))})

    # apron x apron: two rings tracing one boundary.  Reported with
    # whether the two ways share any node id — if they do not, the
    # boundary has two spellings and that is its own needle source.
    ring_nids_by_way: dict = {}
    for e in edges:
        ring_nids_by_way.setdefault(e[5], set())
    ax_pairs: list = []
    sharing = 0
    unshared = [0]
    seen_pair: set = set()
    apron_edges = [(k, e) for k, e in enumerate(edges) if e[4] == APRON_ROLE]
    for (k, e) in apron_edges:
        seg = ((e[0], e[1]), (e[2], e[3]))
        for j in _query(seg):
            f = edges[int(j)]
            if f[4] != APRON_ROLE or f[5] == e[5]:
                continue
            key = (min(k, int(j)), max(k, int(j)))
            if key in seen_pair:
                continue
            seen_pair.add(key)
            hit = _near_parallel(seg, ((f[0], f[1]), (f[2], f[3])))
            if hit is None:
                continue
            shares = bool({e[8], e[9]} & {f[8], f[9]})
            ax_pairs.append({
                "way_a": e[5], "way_b": f[5],
                "shares_node_ids": shares,
                "gap_m": round(hit[0], 4),
                "overlap_m": round(hit[1], 2),
                "ll": _ll_of(anchor, (0.5 * (e[0] + e[2]),
                                      0.5 * (e[1] + e[3])))})
            if hit[0] <= COINCIDENT_GAP_M and shares:
                sharing += 1
            elif hit[0] <= COINCIDENT_GAP_M:
                unshared[0] += 1
    fx.sort(key=lambda d: d["gap_m"])
    ax_pairs.sort(key=lambda d: d["gap_m"])
    return {"feature_x_ring": fx, "apron_x_apron": ax_pairs,
            "by_class_and_role": by_class_role,
            "feature_x_ring_coincident": n_coincident[0],
            "apron_x_apron_coincident_welded": sharing,
            "apron_x_apron_coincident_unwelded": unshared[0]}


#: ``--on-edge``: two constrained segments this close and this parallel
#: force a needle fan through the mesher.  Measured on the owner's fresh
#: +30+031 tile: in-bbox aspect p99 43,275 against a ~23 baseline class,
#: 61,901 needles >= 20 (20.3 % of in-bbox), 78,801 sub-0.1 m2 slivers;
#: the worst cell (30.130, 31.412) had 8 of its 12 near-parallel pairs
#: apron-ring x apron_spine_station.  NOT a law threshold.
NEAR_PARALLEL_GAP_M = 0.5
NEAR_PARALLEL_COS = 0.999
#: below this much shared projection the two segments run end-to-end,
#: not side-by-side, and no needle fan follows
NEAR_PARALLEL_OVERLAP_M = 0.5
#: at or under this gap the two segments ARE one line — a duplicated
#: constraint, which the mesher sees once and cannot thread a triangle
#: between.  This is what a WELD produces, and it is the difference
#: between the defect and its fix: counted, never reported as a needle.
COINCIDENT_GAP_M = 1e-6


def _near_parallel(a, b, *, gap_m=NEAR_PARALLEL_GAP_M,
                   cos_min=NEAR_PARALLEL_COS,
                   overlap_min_m=NEAR_PARALLEL_OVERLAP_M):
    """Do segments ``a`` and ``b`` (each ``((x0,y0),(x1,y1))``) run
    SIDE BY SIDE within ``gap_m``?  ``(gap, overlap)`` if so, else None.

    Three conditions, and all three are needed: close, parallel, AND
    overlapping along the shared direction — two collinear segments laid
    end to end are a weld, not a needle."""
    import math
    (ax, ay), (bx, by) = a
    (cx, cy), (dx_, dy_) = b
    ux, uy = bx - ax, by - ay
    vx, vy = dx_ - cx, dy_ - cy
    lu = math.hypot(ux, uy)
    lv = math.hypot(vx, vy)
    if lu < 1e-9 or lv < 1e-9:
        return None
    cos = abs((ux * vx + uy * vy) / (lu * lv))
    if cos < cos_min:
        return None
    ux, uy = ux / lu, uy / lu
    t0 = (cx - ax) * ux + (cy - ay) * uy
    t1 = (dx_ - ax) * ux + (dy_ - ay) * uy
    lo, hi = (t0, t1) if t0 <= t1 else (t1, t0)
    overlap = min(hi, lu) - max(lo, 0.0)
    if overlap < overlap_min_m:
        return None
    from shapely.geometry import LineString
    gap = float(LineString(a).distance(LineString(b)))
    if gap > gap_m:
        return None
    return (gap, overlap)


def format_on_edge_report(path, result, *, top=12, near_m=DEFAULT_NEAR_M):
    lines = [f"== {path}"]
    for cls, d in result.items():
        if cls == "near_parallel_pairs":
            continue
        lines.append(
            f"  {cls}: {d['nodes']} feature node(s), "
            f"{d['shared_with_a_ring']} share a ring node id, "
            f"{d['on_edge_unwelded']} sit ON a ring edge "
            f"(<= {near_m} m perp, foot interior) unwelded")
        for row in d["rows"][:top]:
            lines.append(
                f"     node {row['node']} way {row['feature_way']} perp "
                f"{row['perp_m']} m on {row['host_role']} "
                f"{row['host_way']} (a {row['along_a_m']} / b "
                f"{row['along_b_m']}) nearest-vertex "
                f"{row['nearest_vertex_m']} m  alt={row['station_alt']} "
                f"hosts={row['hosts']} tear={row['worst_tear_m']}  "
                f"{row['ll']}")
    np_ = result.get("near_parallel_pairs")
    if np_ is not None:
        lines.append(
            f"  NEAR-PARALLEL constrained pairs "
            f"(<= {NEAR_PARALLEL_GAP_M} m apart, |cos| >= "
            f"{NEAR_PARALLEL_COS}, >= {NEAR_PARALLEL_OVERLAP_M} m shared "
            f"run) — the mesh-needle source:")
        lines.append(
            f"     feature x ring: {len(np_['feature_x_ring'])} "
            f"({np_['feature_x_ring_coincident']} coincident, i.e. WELDED "
            f"— one line, no fan)"
            + ("" if not np_["by_class_and_role"] else "  ["
               + ", ".join(f"{k}: {v}" for k, v in
                           sorted(np_["by_class_and_role"].items()))
               + "]"))
        for row in np_["feature_x_ring"][:top]:
            lines.append(
                f"       {row['feature']} way {row['feature_way']} vs "
                f"{row['host_role']} {row['host_way']}: gap "
                f"{row['gap_m']} m over {row['overlap_m']} m  {row['ll']}")
        lines.append(
            f"     apron x apron: {len(np_['apron_x_apron'])} "
            f"({np_['apron_x_apron_coincident_welded']} coincident AND "
            f"sharing node ids — one constraint, no fan; "
            f"{np_['apron_x_apron_coincident_unwelded']} coincident but "
            f"NOT sharing node ids) — a SECOND, pre-existing source: two "
            f"rings tracing one boundary with non-identical spellings")
        for row in np_["apron_x_apron"][:top]:
            lines.append(
                f"       apron {row['way_a']} vs apron {row['way_b']}: gap "
                f"{row['gap_m']} m over {row['overlap_m']} m  {row['ll']}")
    return "\n".join(lines)


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
    ap.add_argument("--on-edge", action="store_true",
                    help="sweep feature NODES that sit on a ring EDGE "
                         "without being a vertex of it (unwelded "
                         "T-vertices) instead of segments leaving the "
                         "apron footprint")
    ap.add_argument("--near", type=float, default=DEFAULT_NEAR_M,
                    help="--on-edge: metres of perpendicular offset "
                         "within which a node counts as ON the edge")
    ap.add_argument("--vertex-tol", type=float,
                    default=DEFAULT_VERTEX_TOL_M,
                    help="--on-edge: metres from an edge ENDPOINT within "
                         "which the node IS that endpoint")
    args = ap.parse_args(argv)
    features = tuple(f for f in args.features.split(",") if f)
    payload: dict = {}
    for p in args.patches:
        if not Path(str(p) + ".axes.json").exists():
            raise SystemExit(
                f"REFUSING: {p} has no .axes.json sidecar — without the "
                f"anchor there is no metre frame to measure in, and a "
                f"guessed one is a different projection.")
        if args.on_edge:
            res = read_on_edge(p, features=features, near_m=args.near,
                               vertex_tol_m=args.vertex_tol)
            payload[str(p)] = res
            print(format_on_edge_report(p, res, top=args.top,
                                        near_m=args.near))
            continue
        res = read(p, features=features, tolerance_m=args.tolerance)
        payload[str(p)] = res
        print(format_report(p, res, top=args.top))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=1))
    return 0


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
