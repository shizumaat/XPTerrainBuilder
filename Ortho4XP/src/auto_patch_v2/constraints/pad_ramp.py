"""THE ROAD YIELDS TO THE PAD — the pad road's ramp rows (issue #609; owner
RULINGS 2026-10-13a (1), 13d, 13e; 09j: pads are senior to roads).

A mapped-road ribbon admitted for a building pad (``model.planar.
pad_road_faces``) is solved in the last stage against constants.  This
module rewrites its rows there (:func:`pad_ramp_rewrite`): the absolute
§37 (6) / (9) road rows leave and ONE design row per vertex lays the ramp
from the nearest pad rim along the road.  The §37 rows themselves are
``constraints/road_ramp``'s; whether a ramp FITS between two standing
levels, the pad's shift and the release are ``constraints/pad_road_reach``'s.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..model.constraints import ConstraintSet, Linear, Row, Source
from ..model.planar import PlanarMap
from ..geom.ramp_profile import ramp_delta  # re-exported: the one ramp law
from .road_ramp import GEN, JOIN_RULING, RULING, RULING_CEILING

__all__ = ["PAD_RAMP_RULING", "pad_ramp_rewrite", "ramp_delta", "stand_off_m"]


#: The ruling head of the ROAD-YIELDS-TO-THE-PAD design row (owner RULINGS
#: 2026-10-13a (1); issue #609).
PAD_RAMP_RULING = ("roads.groundside_road ramp from the pad "
                   "(owner 2026-10-13a (1); issue #609)")


def _dist(planar: PlanarMap, a: int, b: int) -> float:
    (ax, ay), (bx, by) = planar.vertices[a].xy, planar.vertices[b].xy
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def stand_off_m(law: Law) -> float:
    """How far a ribbon the arrangement could not weld to a rim NODE stands
    off that rim (``planar/ribbons._ribbons_pass_c``: notched by the
    hot-pixel band, ``max(1.5, 2) x`` the identity spacing, and snapped
    once more) — three identity cells bound it."""
    return 3.0 * float(law.tables.emit.identity.min_distinct_spacing_m)


def _rim_stand_offs(planar: PlanarMap, law: Law, vs: _t.Iterable[int],
                    rim: frozenset[int]) -> dict[int, tuple[float, int]]:
    """``{v: (distance, nearest rim vertex of that edge)}`` for each of
    ``vs`` standing within :func:`stand_off_m` of a pad's rim EDGE without
    being a rim vertex.  MEASURED KCLT (way ``-8198``, welded to the
    terminal's pad by the touch witness): its end stands 0.7 m off the
    rim — a long straight edge with no node to weld to — and, sharing no
    vertex with the pad, it was ramped from a rim 133 m away round the
    block: 6.2 m under the pad it touches, 60 % over 10 m."""
    import shapely
    from shapely.strtree import STRtree
    from ..law.tables import is_rigid_role
    segs, ends = [], []
    for f in planar.faces.values():
        if not is_rigid_role(law, f.role):
            continue
        for cyc in (f.ring, *f.holes):
            ring = list(planar.ring_vertices(cyc))
            for a, b in zip(ring, ring[1:] + ring[:1]):
                segs.append([planar.vertices[a].xy, planar.vertices[b].xy])
                ends.append((a, b))
    vs = sorted(v for v in vs if v not in rim)
    if not segs or not vs:
        return {}
    lines = shapely.linestrings(segs)
    tree = STRtree(lines)
    pts = shapely.points([planar.vertices[v].xy for v in vs])
    out: dict[int, tuple[float, int]] = {}
    for vi, si in zip(*tree.query(pts, predicate="dwithin",
                                  distance=stand_off_m(law)).tolist()):
        v = vs[vi]
        d = float(shapely.distance(pts[vi], lines[si]))
        r = min(ends[si], key=lambda q: (_dist(planar, v, q), q))
        if v not in out or (d, r) < out[v]:
            out[v] = (d, r)
    return out


def _welded_ribbon_vertices(planar: PlanarMap, law: Law
                            ) -> tuple[dict[int, tuple[int, float]], frozenset[int]]:
    """``{ribbon vertex: (its nearest pad-rim vertex, the RUN to it)}`` over
    THE ROADS ADMITTED FOR A PAD (``model.planar.pad_road_faces``: the
    mint's second pass — in the patch only because a pad is): the faces
    sharing a rim with a building pad (or standing off one,
    :func:`_rim_stand_offs`) and every pad-road face reached from one
    through shared vertices, less a face that touches stage-1 airside
    pavement (``airside_stage_roles``: there the road is bordered by
    airside and keeps the airside's rows).  A road the patch itself admits
    is not here: it keeps the rows it has always had.  The run is measured
    ALONG THE ROAD (the shortest path over those faces' own edges), the
    metric the exit walk (``classify/pad_road_exit``) and the reach read
    (``pad_road_reach``) use — never the straight line, which cuts a bend
    short and leaves the ramp above the terrain at its far end.  The
    second value is the pad rims' vertices."""
    import heapq
    from ..law.tables import airside_stage_roles
    from ..model.planar import face_edge_ids, pad_road_faces
    from .pads import pad_welded_vertices
    rim = pad_welded_vertices(planar, law)
    # a ramp foot's run-out carries its own profile (``constraints/
    # ramp_runout``, #669): it leaves the patch's edge, not a pad's rim
    runs = getattr(planar, "ramp_runouts", None) or {}
    roads = [f for f in pad_road_faces(planar) if str(f.ref) not in runs]
    if not roads:
        return {}, rim
    air = airside_stage_roles(law)
    air_vs: set[int] = set()
    for f in planar.faces.values():
        if f.role in air:
            air_vs |= {v for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}
    face = {f.id: f for f in roads}
    ribbon = {f.id: vs for f in roads
              for vs in [{v for cyc in (f.ring, *f.holes)
                          for v in planar.ring_vertices(cyc)}] if not (vs & air_vs)}
    by_vertex: dict[int, list[int]] = {}
    for fid, vs in ribbon.items():
        for v in vs:
            by_vertex.setdefault(v, []).append(fid)
    off = _rim_stand_offs(planar, law, by_vertex, rim)
    seen = {fid for fid, vs in ribbon.items() if vs & rim or not vs.isdisjoint(off)}
    queue = list(seen)
    while queue:
        fid = queue.pop()
        for v in ribbon[fid]:
            for q in by_vertex.get(v, ()):
                if q not in seen:
                    seen.add(q)
                    queue.append(q)
    adj: dict[int, list[tuple[int, float]]] = {}
    for fid in sorted(seen):
        for e in face_edge_ids(face[fid]):
            a, b = planar.edges[e].a, planar.edges[e].b
            d = _dist(planar, a, b)
            adj.setdefault(a, []).append((b, d))
            adj.setdefault(b, []).append((a, d))
    best = {v: (0.0, v) for v in sorted(adj) if v in rim}
    best.update({v: dr for v, dr in off.items() if v in adj})
    heap = [(d, v, r) for v, (d, r) in best.items()]
    heapq.heapify(heap)
    while heap:
        d, v, r = heapq.heappop(heap)
        if (d, r) > best[v]:
            continue
        for w, dw in adj[v]:
            if w not in rim and (d + dw, r) < best.get(w, (float("inf"), -1)):
                best[w] = (d + dw, r)
                heapq.heappush(heap, (d + dw, w, r))
    return {v: (r, d) for v, (d, r) in best.items() if v not in rim}, rim


def _pad_road_unknowns(planar: PlanarMap, law: Law, levels: _t.Mapping[int, float]
                       ) -> frozenset[int]:
    """Every vertex of a pad-road face that is no constant of ``levels`` and
    no vertex of a pad (a pad's own rows are the pad's, never the road's)."""
    from ..law.tables import is_rigid_role
    from ..model.planar import pad_road_faces
    F = planar.faces
    return frozenset(
        v for f in pad_road_faces(planar) for cyc in (f.ring, *f.holes)
        for v in planar.ring_vertices(cyc) if v not in levels
        and not any(q in F and is_rigid_role(law, F[q].role)
                    for q in planar.vertices[v].incident_faces))


def pad_ramp_rewrite(planar: PlanarMap, law: Law, cs: ConstraintSet,
                     levels: _t.Mapping[int, float] | None = None
                     ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """THE ROAD YIELDS TO THE PAD (owner RULINGS 2026-10-13a (1), issue
    #609; 09j: pads are senior to roads).  A mapped-road ribbon WELDED to
    a building pad's rim takes the PAD's level at the weld and climbs to
    it at the least grade that fits — design ``[road_contact] ramp_grade``
    (5 %), the road's own cap (10 %, its hard cross-section rows, which
    stay) where the run is short.  The pad never moves for the road.

    MEASURED before this rewrite (lane roads609, KCLT / HECA / SPJC / CYXY
    replay pairs): the ribbon's §37 (6) target and hard ceiling are ABSOLUTE
    (the DEM-based profile from a contact whose level classify could not
    know — the pad's seat is a stage-2 unknown) and its §37 (9) coverage-
    edge join is a hard PIN at the core road's level metres off the rim;
    against them the pad's own level is a soft datum, so the LP moved the
    pad to the road (KCLT's garages 223 -> 218.3, HECA building128 -4.53 m,
    SPJC building28 -2.11 m, CYXY lot pav4 -3.55 m).

    THE REWRITE, on every vertex of such a ribbon off the rim: (1) its
    §37 (6) design target and hard ceiling are withdrawn; (2) its join pin
    is RELEASED outright (recorded in ``welded_join_release``'s form, stage
    ``"2p"`` — no target at the core's level either: MEASURED KCLT round 2,
    a released-to-target join at 221.0 still drew the garages 2.7 m down
    through the design rows), so the core ribbon YIELDS to the level the
    patch carries at the join (``emit/road_join.with_pin_yield``) and the
    core's own cap-Lipschitz levelling carries the ramp OUTWARD along the
    mapped road — the run the ribbon could not have inside the patch;
    (3) ONE design row RELATIVE to its nearest rim vertex ``r`` along the
    road, ``d`` the run to it, ``z[v] - z[r] = delta`` where ``delta`` is
    the NEARER TO THE GROUND of two profiles leaving the rim at the design
    grade: ``clip(dem[v] - L[r], -g d, +g d)`` — toward the terrain, never
    past it — and ``dem[v] + shrink(off, g d) - L[r]``, closing the pad's
    own offset over its ground ``off = L[r] - dem[r]`` (``shrink`` takes
    ``g d`` off its size, never past zero).  On level ground they agree.
    Where the ground falls away from the pad faster than the design grade
    the first never comes down (MEASURED KASE, round 5: 2,295 m of exit
    ribbon from 3 exits, the walk stopped by its 1,000 m bound alone) and
    the second does; where the ground rises toward the pad's level the
    first meets it sooner (KCLT way ``-13743``: closing the terminal pad's
    5.5 m offset alone left it 2 m over ground that had risen 3 m).
    ``L[r]`` is the rim's STANDING
    level (``levels``: the last stage's constants).  MEASURED round 5
    (KCLT way ``-8190``, 245 m off a garage at 222.68 m on terrain at
    217.5 m): read off the rim's DEM instead, the row said "+0.37 m from
    the rim" all the way out — the road stood at 223 m over ground at
    218 m and fell 53 % at the patch edge.  Priced
    at ``[design] law`` like every §37 (6) target and ONE-WAY (``[design]
    one_way_rulings``: the rim leads, the road vertex follows), so the row
    itself can never pull the pad.  Nothing absolute
    remains on the ribbon but the core-profile fit (``[design] road``).

    SENIORITY, NOT A WEIGHT (13b (5), 13d "road ramps first"): the
    rewrite runs in THE LAST STAGE (``pipeline/late_stage``), where the
    pad roads are the unknowns and every pad, lot and airside level is a
    constant the map WITHOUT them was solved to — so no road row and no
    road bending has a pad column to bargain with.  MEASURED before that
    order: with these rows in one solve the garages fell 0.40-0.50 m
    (round 2: a free road vertex "held by bending alone"); solved after
    the pads but on rows generated from the map WITH the roads (round 3),
    the patch's own ribbons re-read their borders and lifted a lot 2.9 m
    and the pad welded to it 0.8 m (KCLT ``dsf:pol84``, building77)."""
    near, rim = _welded_ribbon_vertices(planar, law)
    rep: dict[str, _t.Any] = {"ribbon_vertices": len(near), "targets": 0,
                              "ceilings": 0, "rows": 0, "joins": []}
    # THE ABSOLUTE CEILING LEAVES EVERY PAD-ROAD UNKNOWN, not only the ones
    # a rim reaches (13a (1): the pad road is junior to every standing level
    # it meets — a gap part, a lot, a pad).  MEASURED (lane crossfall609,
    # HECA round 5): pad roads welded to a gap part standing 8 m over the
    # DEM (``gap:5``, ~101 m) and reached from no rim kept the §37 (6)
    # DEM-ramp ceiling (93.3 m): 45 rows relaxed, worst 16.85 m
    unknown = _pad_road_unknowns(planar, law, levels) if levels else frozenset()
    if not near and not unknown:
        return cs, rep
    g = float(law.tables.emit.road_contact.ramp_grade)

    def _at(r: Row, ruling: str) -> bool:
        if r.source.generator != GEN or r.source.ruling != ruling:
            return False
        tag = r.source.inputs[0] if r.source.inputs else ""
        return tag.startswith("vertex:") and int(tag[7:]) in near
    linears = [r for r in cs.linears if not _at(r, RULING)]

    def _ceiling(r: Row) -> bool:
        if _at(r, RULING_CEILING):
            return True
        if r.source.generator != GEN or r.source.ruling != RULING_CEILING:
            return False
        tag = r.source.inputs[0] if r.source.inputs else ""
        return tag.startswith("vertex:") and int(tag[7:]) in unknown
    # the join re-stated as a BAND by an earlier rewrite (the reach seed's
    # anchor form) is the same hard absolute, and leaves with the pin
    bands = [r for r in cs.bands if not (_ceiling(r) or _at(r, JOIN_RULING))]
    rep["targets"] = len(cs.linears) - len(linears)
    rep["ceilings"] = len(cs.bands) - len(bands)
    pins, released = [], []
    for p in cs.pins:
        if p.v in near and p.source.generator == GEN and p.source.ruling == JOIN_RULING:
            released.append((p.v, float(p.z), p.source))   # no target: the core yields
        else:
            pins.append(p)
    for b in cs.bands:
        if _at(b, JOIN_RULING) and b.hi is not None:
            released.append((b.v, float(b.hi), b.source))
    rep["joins"] = [
        {"v": int(v), "xy": tuple(float(c) for c in planar.vertices[v].xy),
         "pinned_m": round(z, 4), "z_m": round(z, 4),
         "excess_m": 0.0, "stage": "2p"} for v, z, _s in released]
    pref = getattr(planar, "preferred_z", None) or {}
    levels = levels or {}
    for v, (r, d) in sorted(near.items()):
        dv, dr = planar.vertices[v].dem_z, planar.vertices[r].dem_z
        zr = levels.get(r, pref.get(r, dr))
        if dv is None or zr is None:
            continue
        delta = ramp_delta(float(dv), float(zr), float(dv if dr is None else dr), g, d)
        ref = next((planar.faces[f].ref for f in planar.vertices[v].incident_faces
                    if planar.faces[f].ref), "")
        # ONE-WAY (``[design] one_way_rulings``): the rim is the LEADER,
        # the road vertex follows — the row can never move the pad
        linears.append(Linear(((v, 1.0), (r, -1.0)), delta, delta,
                              Source(GEN, PAD_RAMP_RULING,
                                     (f"vertex:{v}", f"rim:{r}", ref)),
                              follows=v))
        rep["rows"] += 1
    return _dc.replace(cs, pins=tuple(pins), linears=tuple(linears),
                       bands=tuple(bands)), rep
