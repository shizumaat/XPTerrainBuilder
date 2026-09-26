"""THE JETWAY STRIP'S REGION — recognised without recognition (spec
``docs/specs/jetway-strip-spec.md`` §1; owner RULINGS 2026-09-18t Q3 and
(2), 23a; issues #31/#32).

Owner, verbatim (18t Q3): "UNDER THE JETWAYS THE APRON STRIP IS LEVEL
WITH THE TERMINAL — a NEW AIRSIDE LAW, solved airside-first; nothing
groundside pulls it."  18t (2): units by intersection, NO jetway
recognition.  So nothing here reads a name:

1. THE RIDER.  A placement the plan holds no geometry for
   (``airport/riders.rider_candidates``: an ``.agp``, a dropped
   multi-anchor resource, a ``lib/`` resource, any path the partition
   skipped) RIDES the 23a pad whose outline it stands within its own
   ``rider_reach`` of; host = the nearest outline, ties -> larger area,
   lower face id (F.5).
2. THE STRIP.  Per cluster pad (23a: pad = the unit footprint), the pad
   OUTER-RING edges carrying a rider anchor within its reach are the
   RIDER EDGES; the strip is the APRON within ``[design] jetway_strip_m``
   (D) of a rider edge, measured along the edge's outward normal and
   capped at the edge's ends + D — apron-face vertices only, minus the
   STRIKE SET (:func:`strike_set`, the §30 (4) derivation of "apron a pad
   may move", ONE site since the collar generators were deleted).
3. Riders are NOT bodies: this module mints no row and touches no plan
   body; it returns data (``model.jetway.StripSet``) the post-stage-1
   projection (``solve/project_strip.py``) applies.

This layer may not import ``planar`` or ``airport`` (M0 §1): the rider
candidates arrive from the pipeline as a mapping, like ``Airport.clusters``.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import design as design_law, rolled_on_roles
from ..model.airport import Airport
from ..model.constraints import ConstraintSet
from ..model.jetway import JetwayStrip, RiderAnchor, StripSet
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["strip_m", "strike_set", "jetway_strips", "rider_hosts"]

XY = tuple[float, float]


def strip_m(law: Law) -> float:
    """§1 (2): ``[design] jetway_strip_m`` (D = 40 m).  ONE derivation
    site; 0 disarms the strip."""
    return float(design_law(law).jetway_strip_m)


_BASE_MEMO: list[tuple[int, _t.Any, tuple]] = []


def _base_strike(planar: PlanarMap, law: Law, airport: Airport | None
                 ) -> tuple[set[int], set[int], dict[int, int]]:
    """``(taxi, coupled, pad_face_of)``: the taxi / runway family's own
    vertices; the apron vertices a taxi-family NO-STEP row pairs with a
    taxi vertex (owner RULINGS 2026-09-13cc (i): "one apron cell short",
    ``no_step.no_step_edges`` the one derivation of that coupling); and
    per pad vertex the pad face owning it.  Memoised per planar map."""
    key = id(planar)
    for k, pm, got in _BASE_MEMO:
        if k == key and pm is planar:
            return got
    from .no_step import no_step_edges
    from .pads import _pad_groups
    vw = view(planar, law)
    taxi_roles = tuple(sorted(set(rolled_on_roles(law)) - {"apron"}))
    taxi: set[int] = set()
    for f in vw.faces_of_role(taxi_roles):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            taxi.update(ring)
    coupled: set[int] = set()
    for a, b, _cap, _d in no_step_edges(planar, law, airport):
        if a in taxi and b not in taxi:
            coupled.add(b)
        elif b in taxi and a not in taxi:
            coupled.add(a)
    pad_of: dict[int, int] = {}
    for fid, _ref, grp in _pad_groups(planar, law):
        for v in grp:
            pad_of.setdefault(v, fid)
    got = (taxi, coupled, pad_of)
    _BASE_MEMO.append((key, planar, got))
    del _BASE_MEMO[:-2]
    return got


def strike_set(planar: PlanarMap, law: Law, airport: Airport | None,
               own: _t.AbstractSet[int] = frozenset()) -> dict[int, str]:
    """§30 (4) / spec §1 (2): ``vertex -> why`` for every vertex a pad's
    apron region may NEVER move — THE ONE derivation of "apron a pad may
    move" (13cc (i)), read by the strip.

    ``taxi``    a vertex any face of the taxi / runway family carries —
                identity is the weld (09-01g), so it IS a taxiway vertex
                and the taxi family is never moved by a pad;
    ``coupled`` an apron vertex a taxi-family no-step row pairs with a
                taxi vertex (measured on KCLT: the reach lifted such apron
                and 2,815 taxi vertices moved, worst 1.88 m);
    ``pad``     a vertex some OTHER pad owns (moving it drags a pad the
                strip has nothing to do with — HECA's skirt 7.07 -> 12.11
                m on the first collar arm).  ``own`` (the host pad's own
                vertices) is exempt: the pad takes the strip."""
    taxi, coupled, pad_of = _base_strike(planar, law, airport)
    out: dict[int, str] = {}
    for v in coupled:
        out[v] = "coupled"
    for v in pad_of:
        if v not in own:
            out[v] = "pad"
    for v in taxi:
        out[v] = "taxi"
    return out


def _outer_ring_ccw(pts: list[XY]) -> bool:
    a = 0.0
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a > 0.0


def rider_hosts(planar: PlanarMap, law: Law, airport: Airport | None,
                candidates: _t.Mapping[str, tuple[float, str]]
                ) -> tuple[list[RiderAnchor], dict[int, str]]:
    """§1 (1): ``(riders, face -> cluster id)``.  Every candidate standing
    within its own reach of a CLUSTER pad face's outline rides the
    nearest (ties: larger area, lower face id).  A candidate within no
    reach rides nothing — the marshaller 40 m out never rides."""
    from .cluster_pad import cluster_pad_faces
    from .pads import _pad_polys
    faces = cluster_pad_faces(planar, law, airport)
    face_cid = {f: cid for cid, fids in faces.items() for f in fids}
    polys = [(fid, ref, poly) for fid, ref, _g, poly in _pad_polys(planar, law)
             if fid in face_cid]
    if not polys or not candidates:
        return [], face_cid
    tree = STRtree([p for _f, _r, p in polys])
    riders: list[RiderAnchor] = []
    objs = {o.id: o for o in (getattr(airport, "dsf_objects", ()) or ())}
    for oid, (reach, _kind) in candidates.items():
        o = objs.get(oid)
        if o is None:
            continue
        pt = Point(*o.xy)
        best = None
        for i in tree.query(pt.buffer(reach)):
            fid, ref, poly = polys[int(i)]
            d = float(poly.exterior.distance(pt))
            if d > reach:
                continue
            k = (round(d, 6), -poly.area, fid)
            if best is None or k < best[0]:
                best = (k, fid, ref, d)
        if best is None:
            continue
        _k, fid, ref, d = best
        riders.append(RiderAnchor(oid, o.path, (float(o.xy[0]), float(o.xy[1])),
                                  ref, fid, round(d, 3), float(reach)))
    return riders, face_cid


def jetway_strips(planar: PlanarMap, law: Law, airport: Airport | None,
                  cs: ConstraintSet | None,
                  candidates: _t.Mapping[str, tuple[float, str]]) -> StripSet:
    """§1: the airport's strips, one per CLUSTER pad carrying a rider
    edge (Q1 default (a): one level per pad).  A pad with no rider mints
    no strip; D = 0 disarms the whole law."""
    D = strip_m(law)
    counts: dict[str, _t.Any] = {"candidates": len(candidates)}
    if D <= 0.0 or not candidates:
        counts["status"] = "off" if D <= 0.0 else "no candidates"
        return StripSet(counts=counts)
    riders, face_cid = rider_hosts(planar, law, airport, candidates)
    counts["riders"] = len(riders)
    if not riders:
        counts["status"] = "no riders"
        return StripSet(riders=tuple(riders), counts=counts)
    vw = view(planar, law)
    # the RIDER EDGES, per cluster: outer-ring segments within a rider's
    # own reach of its anchor, with their outward unit normal
    by_face: dict[int, list[RiderAnchor]] = {}
    for r in riders:
        by_face.setdefault(r.host_face, []).append(r)
    edges_of: dict[str, list[tuple[XY, XY, XY]]] = {}
    riders_of: dict[str, list[RiderAnchor]] = {}
    pad_ref_of: dict[str, tuple[float, str, int]] = {}
    own_of: dict[str, set[int]] = {}
    for fid, rs in by_face.items():
        cid = face_cid[fid]
        ring = vw.rings[fid]
        pts = [vw.xy[v] for v in ring]
        n = len(pts)
        if n < 3:
            continue
        ccw = _outer_ring_ccw(pts)
        segs = [LineString([pts[i], pts[(i + 1) % n]]) for i in range(n)]
        hit: set[int] = set()
        for r in rs:
            p = Point(*r.xy)
            for i, s in enumerate(segs):
                if s.length > 0.0 and s.distance(p) <= r.reach_m:
                    hit.add(i)
        for i in sorted(hit):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
            L = math.hypot(x1 - x0, y1 - y0)
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            # outward = right of travel on a CCW ring, left on a CW one
            nx, ny = (uy, -ux) if ccw else (-uy, ux)
            edges_of.setdefault(cid, []).append(((x0, y0), (x1, y1), (nx, ny)))
        riders_of.setdefault(cid, []).extend(rs)
        area = Polygon(pts).area
        cur = pad_ref_of.get(cid)
        if cur is None or area > cur[0]:
            pad_ref_of[cid] = (area, planar.faces[fid].ref, fid)
        own = own_of.setdefault(cid, set())
        for rg in [ring, *vw.holes[fid]]:
            own.update(rg)
    # every face of a cluster is its own pad plate member (§30 (4)): the
    # host's own vertices are ALL its faces', rider-carrying or not
    for f, cid in face_cid.items():
        if cid in own_of:
            for rg in [vw.rings[f], *vw.holes[f]]:
                own_of[cid].update(rg)
    apron_vs: set[int] = set()
    for f in vw.faces_of_role(("apron",)):
        for rg in [vw.rings[f.id], *vw.holes[f.id]]:
            apron_vs.update(rg)
    pins = {p.v for p in (cs.pins if cs is not None else ())}
    all_own = set().union(*own_of.values()) if own_of else set()
    taxi, coupled, pad_of = _base_strike(planar, law, airport)
    # the REGION per cluster: each rider edge's rectangle, D along its
    # outward normal and D past each end
    regions: dict[str, _t.Any] = {}
    for cid, es in edges_of.items():
        rects = []
        for (x0, y0), (x1, y1), (nx, ny) in es:
            L = math.hypot(x1 - x0, y1 - y0)
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            a = (x0 - D * ux, y0 - D * uy)
            b = (x1 + D * ux, y1 + D * uy)
            rects.append(Polygon([a, b, (b[0] + D * nx, b[1] + D * ny),
                                  (a[0] + D * nx, a[1] + D * ny)]))
        regions[cid] = unary_union(rects).buffer(0.01)
    # assign each apron vertex to the nearest region's cluster (by its
    # distance to that cluster's rider edges), strike, and collect
    edge_lines = {cid: unary_union([LineString([a, b]) for a, b, _n in es])
                  for cid, es in edges_of.items()}
    prepared = {cid: prep(g) for cid, g in regions.items()}
    got: dict[str, list[int]] = {cid: [] for cid in regions}
    struck_of: dict[str, list[tuple[int, str]]] = {cid: [] for cid in regions}
    for v in sorted(apron_vs):
        p = Point(*vw.xy[v])
        inside = [cid for cid, g in prepared.items() if g.contains(p)]
        if not inside:
            continue
        cid = min(inside, key=lambda c: (edge_lines[c].distance(p), c))
        own = own_of.get(cid, set())
        why = None
        if v in taxi:
            why = "taxi"
        elif v in pins:
            why = "pin"
        elif v in coupled:
            why = "coupled"
        elif v in pad_of and v not in own:
            why = "pad"
        if why is None:
            got[cid].append(v)
        else:
            struck_of[cid].append((v, why))
    strips: list[JetwayStrip] = []
    for cid in sorted(regions):
        vs = got[cid]
        if not vs:
            continue
        _a, ref, fid = pad_ref_of[cid]
        reg = regions[cid]
        geoms = list(getattr(reg, "geoms", [reg]))
        rings = tuple(tuple((round(x, 3), round(y, 3)) for x, y in g.exterior.coords)
                      for g in geoms if not g.is_empty)
        strips.append(JetwayStrip(
            id=f"strip:{cid}", pad_ref=ref, pad_face=fid,
            riders=tuple(sorted(r.obj_id for r in riders_of.get(cid, ()))),
            rider_edges=tuple((a, b) for a, b, _n in edges_of[cid]),
            region=rings, vertices=tuple(vs), struck=tuple(struck_of[cid])))
    fixed: dict[int, str] = {}
    for v in pad_of:
        if v not in all_own:
            fixed[v] = "pad"
    for v in pins:
        fixed[v] = "pin"
    for v in taxi:
        fixed[v] = "taxi"
    movable = frozenset(v for v in apron_vs if v not in fixed)
    counts.update(status="ok", strips=len(strips),
                  rider_edges=sum(len(e) for e in edges_of.values()),
                  strip_vertices=sum(len(s.vertices) for s in strips),
                  struck=sum(len(s.struck) for s in strips),
                  riders_in_a_strip=sum(len(s.riders) for s in strips))
    return StripSet(strips=tuple(strips), riders=tuple(riders), movable=movable,
                    fixed=fixed, counts=counts)
