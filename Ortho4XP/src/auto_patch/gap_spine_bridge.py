"""THE GAP-BRIDGING SPINE — §1 of docs/specs/heca-apron-round2-spec.md
(Fable spec, 2026-08-25; HECA apron round 2).

THE DEFECT THIS EXISTS FOR.  HECA's apt.dat taxi-route graph has a FEED
GAP: taxiway J ends at node 462 (30.1290178, 31.4055840) and the next
route starts at node 470 (30.1311876, 31.4048028), 254 m north, with no
1202 edge between them and no OSM way there either.  The two ends sit on
ONE continuous piece of apron pavement, so the pavement is real and
taxiable — but the global slice cuts along CENTERLINES, and there is no
centerline across that stretch.  The result is a 215 x 430 m region of
emitted apron with ZERO interior vertices: its membrane is uncontrolled
for 233 m, the visible break is the anchor-influence boundary, and the
census is STRUCTURALLY BLIND there (no nodes -> no rows), which is how
the same cliff survived three rounds of censuses reading 1,679.

The engine's own ramp-lead-in trim (``apt_dat_reader.taxi_centerlines``)
fires ZERO times at HECA and is not the mechanism to extend: it DELETES
a stand lead-in, it does not synthesize a missing one.

WHAT THIS DOES.  Where two taxi-route ENDS lie unconnected across
continuous apron pavement, synthesize ONE bridging centerline between
them — for each dead end, the nearest VISIBLE route end across
apron-only pavement, within ``config.GAP_SPINE_MAX_M``.  The bridge is a
FIRST-CLASS centerline: it is appended to ``layout.apt_taxi_centerlines``
BEFORE the global slice, so it cuts interior vertices exactly as any
route does, ``grade_graph.centerline_specs`` gives it its own profile,
and ``spine_nodes_m`` puts its vertices in the nearest-anchor chord
population.

ONE VISIBILITY NOTION, NEVER A THIRD.  The reachability test is
``grade_graph._visibility_predicate`` — the SAME predicate the §1
chord-anchor enumeration consumes, called the same way (a polygon's own
exterior ring, grown by ``_VIS_BUF``).  The POPULATION at this point in
the pipeline is the pavement region itself rather than a classified
apron face, for the structural reason that face classification has not
run yet (it consumes the slice this feature feeds).  The region is the
slice's own pavement input MINUS the runway union — i.e. the pavement
that is not a runway and not a terminal — so a chord may not leave
pavement, may not cross a gap, and may not cross a runway.

DETERMINISM.  Candidate pairs are ordered by (distance, node id, node
id) and consumed greedily, one bridge per end.  Node ids are the real
apt.dat 1201 ids, recovered by joining each end's coordinates back to
``airport.taxi_nodes`` — so the tie rule the spec states ("lower node
id") is the rule that runs, and the log can name node 462 and node 470.
An end that joins to no apt.dat node (a route-arc-minted terminus) sorts
after every identified end under a synthetic id.
"""
from __future__ import annotations

import math

import O4_UI_Utils as UI

#: Coordinate tolerance (m) at which two route vertices are the SAME
#: network node.  ``grade_graph.SPINE_PERP_TOL_M`` is the project's
#: existing "this ring vertex IS on that centerline" tolerance and this
#: is the same question asked of two centerline vertices — one notion.
from .grade_graph import SPINE_PERP_TOL_M as _JOIN_TOL_M

#: How close an end must be to an apt.dat 1201 node to be NAMED by it.
#: Route-arc welding moves an endpoint by at most a weld tolerance, so
#: this is deliberately loose: a wrong name is caught by the log, a
#: missing name only costs the deterministic tie its real id.
_NODE_ID_JOIN_M = 5.0


class _DSU:
    """Union-find over route-vertex cells — the connectivity the spec's
    word "unconnected" names."""

    def __init__(self):
        self._parent: dict = {}

    def find(self, a):
        p = self._parent.setdefault(a, a)
        while p != a:
            a, p = p, self._parent.setdefault(p, p)
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def _cell(x: float, y: float) -> tuple:
    """The join cell for ``_JOIN_TOL_M`` coincidence."""
    return (int(math.floor(x / _JOIN_TOL_M)),
            int(math.floor(y / _JOIN_TOL_M)))


def _neighbour_cells(c):
    cx, cy = c
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            yield (cx + dx, cy + dy)


def route_ends(centerlines, *, join_tol_m: float = _JOIN_TOL_M):
    """``(ends, components)`` for the non-service taxi routes.

    ``ends`` — ``[{"xy", "cl", "at_start"}]``, one per polyline terminus
    that no OTHER route touches: a DEAD END, the "1201/1202 leaf end or
    emitted axis endpoint" the spec names.  ``components`` — the
    union-find over every route vertex, so two ends can be asked whether
    they are already connected through the network.
    """
    dsu = _DSU()
    occupancy: dict = {}
    polylines: list = []
    for k, tcl in enumerate(centerlines):
        if getattr(tcl, "is_service", False):
            continue
        ln = getattr(tcl, "line", None)
        if ln is None or getattr(ln, "is_empty", True):
            continue
        try:
            pts = [(float(x), float(y)) for x, y in ln.coords]
        except Exception:                                 # pragma: no cover
            continue
        if len(pts) < 2:
            continue
        polylines.append((k, tcl, pts))
        prev = None
        for (x, y) in pts:
            c = _cell(x, y)
            occupancy.setdefault(c, []).append((x, y, k))
            if prev is not None:
                dsu.union(prev, c)
            prev = c
    # Weld coincident vertices of DIFFERENT routes into one component.
    for c, members in occupancy.items():
        for nc in _neighbour_cells(c):
            others = occupancy.get(nc)
            if not others:
                continue
            for (x, y, k) in members:
                for (ox, oy, ok) in others:
                    if ok == k:
                        continue
                    if math.hypot(ox - x, oy - y) <= join_tol_m:
                        dsu.union(c, nc)
    ends: list = []
    for (k, tcl, pts) in polylines:
        for at_start, (x, y) in ((True, pts[0]), (False, pts[-1])):
            touched = False
            for nc in _neighbour_cells(_cell(x, y)):
                for (ox, oy, ok) in occupancy.get(nc, ()):
                    if ok == k:
                        continue
                    if math.hypot(ox - x, oy - y) <= join_tol_m:
                        touched = True
                        break
                if touched:
                    break
            if not touched:
                ends.append({"xy": (x, y), "cl": k, "at_start": at_start,
                             "tcl": tcl})
    return ends, dsu


def _apt_node_ids(airport, to_m):
    """``[(x, y, node_id)]`` for every apt.dat 1201 node, in local
    metres — the join that gives the tie rule its real ids."""
    out: list = []
    nodes = getattr(airport, "taxi_nodes", None) or {}
    for nid, n in nodes.items():
        try:
            x, y = to_m(float(n.lon), float(n.lat))
        except Exception:                                 # pragma: no cover
            continue
        out.append((float(x), float(y), int(nid)))
    return out


def _name_ends(ends, apt_nodes):
    """Stamp each end with the nearest apt.dat node id within
    ``_NODE_ID_JOIN_M`` (``None`` when the end is route-arc minted)."""
    for e in ends:
        x, y = e["xy"]
        best = None
        for (nx, ny, nid) in apt_nodes:
            d = math.hypot(nx - x, ny - y)
            if d <= _NODE_ID_JOIN_M and (best is None or d < best[0]
                                         or (d == best[0]
                                             and nid < best[1])):
                best = (d, nid)
        e["node_id"] = None if best is None else best[1]


def _visibility_regions(apron_pavement):
    """``[(prepared_polygon_predicate, polygon)]`` — one entry per
    connected piece of apron-only pavement, each carrying the SAME
    ``grade_graph._visibility_predicate`` the chord enumeration uses."""
    from .grade_graph import _visibility_predicate
    if apron_pavement is None or getattr(apron_pavement, "is_empty", True):
        return []
    geoms = list(getattr(apron_pavement, "geoms", ())) or [apron_pavement]
    out: list = []
    for poly in geoms:
        try:
            if poly.is_empty or poly.geom_type != "Polygon":
                continue
            ring = [(float(x), float(y))
                    for x, y in poly.exterior.coords]
        except Exception:                                 # pragma: no cover
            continue
        vis = _visibility_predicate(ring)
        if vis is None:
            continue
        out.append((vis, poly))
    return out


def _visible(regions, a, b) -> bool:
    """True iff the chord ``a``→``b`` is walkable across ONE piece of
    apron-only pavement, under the §1 chord-anchor visibility
    predicate."""
    for (vis, _poly) in regions:
        try:
            if vis(a[0], a[1], b[0], b[1]):
                return True
        except Exception:                                 # pragma: no cover
            continue
    return False


def plan_gap_spine_bridges(centerlines, apron_pavement, *, max_m: float,
                           apt_nodes=None):
    """The PLAN: ``[{"a", "b", "node_a", "node_b", "dist_m", "cl_a",
    "cl_b"}]``, one record per bridge to synthesize.

    Pure geometry + the visibility predicate; no layout mutation, so the
    twins can drive it directly.  ``apt_nodes`` — ``_apt_node_ids``
    output, or ``None`` (every end sorts under a synthetic id)."""
    ends, dsu = route_ends(centerlines)
    _name_ends(ends, apt_nodes or ())
    regions = _visibility_regions(apron_pavement)
    if not regions or len(ends) < 2:
        return []
    # A stable sort key for an end with no apt.dat id: after every
    # identified end, then by rounded coordinate.
    def _key(e):
        nid = e.get("node_id")
        return ((0, nid) if nid is not None
                else (1, (round(e["xy"][0], 3), round(e["xy"][1], 3))))

    cands: list = []
    for i in range(len(ends)):
        for j in range(i + 1, len(ends)):
            ea, eb = ends[i], ends[j]
            if ea["cl"] == eb["cl"]:
                continue                  # the same route's own two ends
            (ax, ay), (bx, by) = ea["xy"], eb["xy"]
            d = math.hypot(bx - ax, by - ay)
            if d > max_m or d <= 0.0:
                continue
            if dsu.find(_cell(ax, ay)) == dsu.find(_cell(bx, by)):
                continue                  # already CONNECTED: no feed gap
            if not _visible(regions, ea["xy"], eb["xy"]):
                continue
            ka, kb = _key(ea), _key(eb)
            lo, hi = (ea, eb) if ka <= kb else (eb, ea)
            cands.append((d, _key(lo), _key(hi), lo, hi))
    cands.sort(key=lambda c: (c[0], c[1], c[2]))
    used: set = set()
    plan: list = []
    for (d, _ka, _kb, ea, eb) in cands:
        ia, ib = id(ea), id(eb)
        if ia in used or ib in used:
            continue
        used.add(ia)
        used.add(ib)
        plan.append({"a": ea["xy"], "b": eb["xy"],
                     "node_a": ea.get("node_id"),
                     "node_b": eb.get("node_id"),
                     "dist_m": d, "cl_a": ea["cl"], "cl_b": eb["cl"],
                     "tcl_a": ea.get("tcl")})
    return plan


def synthesize_gap_spine_bridges(layout, apron_pavement, *,
                                 airport=None, to_m=None, max_m=None):
    """Append one ``TaxiCenterline`` per planned bridge to
    ``layout.apt_taxi_centerlines`` and publish the provenance on
    ``layout.gap_spine_bridges``.

    Returns the list of published records.  Flag OFF (or no plan):
    returns ``[]`` and touches nothing — byte-identical."""
    from .apt_dat_reader import TaxiCenterline
    from . import config as _cfg
    if not getattr(_cfg, "GAP_SPINE_BRIDGE_ENABLED", False):
        return []
    if max_m is None:
        max_m = float(getattr(_cfg, "GAP_SPINE_MAX_M", 300.0))
    centerlines = list(getattr(layout, "apt_taxi_centerlines", []) or [])
    if not centerlines:
        return []
    apt_nodes = (_apt_node_ids(airport, to_m)
                 if (airport is not None and to_m is not None) else None)
    plan = plan_gap_spine_bridges(centerlines, apron_pavement,
                                  max_m=max_m, apt_nodes=apt_nodes)
    if not plan:
        return []
    from shapely.geometry import LineString
    records: list = []
    for p in plan:
        try:
            line = LineString([p["a"], p["b"]])
        except Exception:                                 # pragma: no cover
            continue
        # THE SIZE LETTER IS INHERITED, never invented: the bridge is the
        # continuation of the route it leaves, so it grades at that
        # route's own per-segment ICAO cap.
        src = p.get("tcl_a")
        sizes = list(getattr(src, "seg_sizes", []) or []) if src else []
        letter = sizes[-1] if sizes else ""
        centerlines.append(TaxiCenterline(
            line=line, seg_sizes=[letter], is_service=False,
            name="gap_spine_bridge", route_line=None))
        rec = {"a": [round(p["a"][0], 3), round(p["a"][1], 3)],
               "b": [round(p["b"][0], 3), round(p["b"][1], 3)],
               "node_a": p["node_a"], "node_b": p["node_b"],
               "dist_m": round(float(p["dist_m"]), 2),
               "size": letter}
        if hasattr(layout, "m_to_ll"):
            try:
                rec["a_ll"] = [round(v, 7)
                               for v in layout.m_to_ll(*p["a"])]
                rec["b_ll"] = [round(v, 7)
                               for v in layout.m_to_ll(*p["b"])]
            except Exception:                             # pragma: no cover
                pass
        records.append(rec)
    if not records:
        return []
    layout.apt_taxi_centerlines = centerlines
    layout.gap_spine_bridges = records
    for rec in records:
        UI.vprint(1, f"  [gap-spine-bridge] synthesized centerline "
                     f"node {rec['node_a']} -> node {rec['node_b']}, "
                     f"{rec['dist_m']} m across apron pavement "
                     f"(size {rec['size'] or '?'}) — the feed gap the "
                     f"slice had no centerline for")
    return records
