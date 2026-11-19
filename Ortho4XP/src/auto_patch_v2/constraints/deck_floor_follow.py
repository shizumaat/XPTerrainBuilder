"""THE CARVE UNDER A GENERATED DECK TAKES THE NO-BRIDGE AIRSIDE AS GIVEN
(owner RULINGS 2026-11-19s (1)-(2); ``docs/specs/airside-first-bridges-
spec.md`` section 1 row 4; spec 2123 A1 Q6).

Stage 1 solves the airside with no generated bridge (``planar/
deck_airside``: the deck withheld, its ring filled with the carried
pavement).  Between the two stages (``solve_design``'s ``stage2_rewrite``)
each generated deck of the full map reads that answer ONCE:

* ITS TOP is the stage-1 pavement over its ring -- a Coons patch of the
  stage-1 levels along the ring's four edges (``geom/coons_patch``), exact
  on each edge, so both ends are flush by construction at any slope;
* every full-map AIRSIDE vertex on or inside the ring the coordinate join
  left without a stage-1 level is FIXED at that patch (``stage2_fixed``),
  and every vertex the join fixed there that the full map does not carry
  as airside (the deck's ground, the bank's crest under the ring's sides)
  is stage 2's to solve (``stage2_free``): the carve never moves airside;
* its FLOOR pins (``constraints/edge_floor.DECK_FLOOR``) drop to the
  deeper of the planar floor (the lidar road) and the deck's underside
  less the road's clearance: ``patch low - floor_min_m`` (the slab plus
  ``structure_approach.design_clearance_m``), never higher (19s (2)).

The patches go to the object stage (``pipeline/generated_publication``)
through the design report (``reach_seed["generated_tops"]``).  A pack
hard deck's floor is the object's own and stays.  Pure: a new set, the
original untouched; no generated deck, no change.  Nothing here names an
airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..geom.coons_patch import CoonsPatch, edge_profiles
from ..geom.exact import hypot
from ..geom.rotated_rect import rotated_rectangle
from .edge_floor import DECK_FLOOR

__all__ = ["floor_follow_rewrite"]

#: the cut's own floor and ramp roles (``emit/graded.FLOOR_ROLES``'s
#: tunnel members; ``constraints/edge_deck._FLOOR_ROLES`` reads the ramp)
_CUT_ROLES = ("tunnel_ramp", "tunnel_trench")

#: a vertex this near a ring (m) stands on it: the planar build snaps a
#: vertex to its identity lattice (``law.tables.snap_margin_m``, 0.35 m) and
#: welds a boundary to a pavement edge within ``weld_spacing_m``
_ON_RING_M = 0.6


@_dc.dataclass(frozen=True)
class _StageTwo:
    """What the rewrite hands stage 2 (module doc)."""

    report: dict
    fixed: dict = _dc.field(default_factory=dict)
    free: frozenset = frozenset()
    tops: dict = _dc.field(default_factory=dict)

    def stage_two(self, rep: _t.Mapping) -> dict:
        """The keys the caller's rewrite report takes: this report, and the
        ``stage2_fixed`` / ``stage2_free`` / ``generated_tops`` that
        ``solve_design`` and the publication read (``stage2_free`` joined
        with what ``rep`` already frees)."""
        out: dict = {"deck_floor_follow": self.report}
        if self.fixed:
            out["stage2_fixed"] = dict(self.fixed)
        if self.free:
            out["stage2_free"] = frozenset(rep.get("stage2_free") or ()) | self.free
        if self.tops:
            out["generated_tops"] = dict(self.tops)
        return out


def _deck_frame(db) -> "tuple[tuple, tuple, tuple] | None":
    """``(o, u, w)``: the deck ring as the parallelogram ``o + s u + t w``
    -- ``s = 0`` its end A (the edge nearest ``seats_a``), ``u`` along its
    sides to end B, ``w`` along end A.  A ring of other than four corners
    reads its least rotated rectangle; ``None`` for no ring."""
    from shapely.geometry import MultiPoint, Point, Polygon
    if len(getattr(db, "ring", ()) or ()) < 3:
        return None
    poly = Polygon(db.ring).buffer(0.0).simplify(0.05)
    if poly.is_empty or poly.geom_type != "Polygon":
        return None
    pts = list(poly.exterior.coords)[:-1]
    if len(pts) != 4:
        pts = list(rotated_rectangle(poly).exterior.coords)[:-1]
    if len(pts) != 4:
        return None
    sa = getattr(db, "seats_a", ()) or ()
    ca = MultiPoint([tuple(p) for p in sa]).centroid if sa else Point(pts[0])
    from shapely.geometry import LineString
    i = min(range(4), key=lambda k: LineString([pts[k], pts[(k + 1) % 4]]).distance(ca))
    c0, c1, c3 = pts[i], pts[(i + 1) % 4], pts[(i + 3) % 4]
    return (c0, (c3[0] - c0[0], c3[1] - c0[1]), (c1[0] - c0[0], c1[1] - c0[1]))


def _samples(pm, levels: _t.Mapping[int, float], ring) -> list[tuple[float, float, float]]:
    """``(x, y, z)`` of every ``pm`` vertex with a level on or inside ``ring``."""
    from shapely.geometry import Point
    from shapely.prepared import prep
    near = prep(ring.buffer(_ON_RING_M))
    out = []
    for v, z in levels.items():
        vx = pm.vertices.get(v) if isinstance(pm.vertices, dict) else pm.vertices[v]
        if vx is not None and near.contains(Point(vx.xy)):
            out.append((float(vx.xy[0]), float(vx.xy[1]), float(z)))
    return out


def _patch(db, stage1, pm, levels) -> "tuple[CoonsPatch | None, int]":
    """``(the deck's top, the samples read)`` (module doc): stage 1's levels
    along its ring, else the full map's (no stage-1 map: the end lines'
    stations alone)."""
    from ..planar.deck_bridge import deck_polygon
    fr = _deck_frame(db)
    if fr is None:
        return None, 0
    ring = deck_polygon(db)
    solved = getattr(stage1, "solved", None) if stage1 is not None else None
    smp = _samples(stage1.pm, solved, ring) if solved else []
    got = edge_profiles(*fr, smp, tol=_ON_RING_M) if smp else None
    if got is None:
        # stage 1 carried no pavement over the ring (a pack structure kept
        # the fill out): the full map's own airside on it, at stage 1's levels
        smp = _samples(pm, levels, ring)
        got = edge_profiles(*fr, smp, tol=_ON_RING_M)
    if got is None and solved:
        # ... else stage 1's surface round the ring, read across it (a TIN)
        from shapely.prepared import prep
        tin = _tin(stage1, prep(ring.buffer(_ON_RING_M)))
        if tin is not None:
            o, u, w = fr
            smp = [(x, y, z) for x, y in _edge_points(o, u, w, 2.0)
                   if (z := tin((x, y))) is not None]
            got = edge_profiles(*fr, smp, tol=_ON_RING_M)
    return got, len(smp)


def _edge_points(o, u, w, step: float) -> list[tuple[float, float]]:
    """Points every ``step`` metres round the parallelogram ``(o, u, w)``."""
    out = []
    for a, d in ((o, u), (o, w), ((o[0] + u[0], o[1] + u[1]), w),
                 ((o[0] + w[0], o[1] + w[1]), u)):
        n = max(1, int(hypot(*d) / step))
        out += [(a[0] + d[0] * k / n, a[1] + d[1] * k / n) for k in range(n + 1)]
    return out


def floor_follow_rewrite(pm, cs, levels: _t.Mapping[int, float], stage1=None, law=None
                         ) -> tuple[_t.Any, _StageTwo]:
    """``(cs with the generated decks' floor pins moved, _StageTwo)``
    (module doc).  ``levels``: stage 1's levels on the full map's ids;
    ``stage1``: the stage-1 problem (``pipeline/stage_one_map.StageOne``,
    duck-typed: ``.pm`` and ``.solved``), ``law`` for the airside set."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    from ..model.structures import is_generated
    from ..planar.deck_bridge import deck_polygon
    rep: dict = {"decks": 0, "pins": 0, "max_drop_m": 0.0, "fixed": 0, "freed": 0,
                 "floor": {}, "top_low": {}, "ring_off": {}, "samples": {}}
    decks = [d for d in getattr(pm, "decks", ()) or () if is_generated(d)]
    from ..planar.deck_airside import withheld
    held = list(withheld())          # the no-bridge arm's (``deck_airside``)
    if not decks and not held:
        return cs, _StageTwo(rep)
    from ..model.platform import stage_air_vertices
    air = stage_air_vertices(pm, law) if law is not None else set()
    # a road's and the cut's own vertices are never the abutment's crest
    from ..law.tables import family
    low = set(_CUT_ROLES) | (set(family(law, "road_cross_section").roles)
                             if law is not None else set())
    fixed: dict[int, float] = {}
    free: set[int] = set()
    tops: dict[str, dict] = {}
    patches: dict[str, CoonsPatch] = {}
    target: dict[str, float] = {}
    for d in decks:
        patch, n_smp = _patch(d, stage1, pm, levels)
        if patch is None:
            rep.setdefault("no_top", {})[d.object_id] = n_smp
            continue
        tops[d.object_id] = {"o": list(patch.o), "u": list(patch.u), "w": list(patch.w),
                             **patch.as_record()}
        patches[d.object_id] = patch
        target[d.object_id] = patch.low() - float(d.floor_min_m)
        rep["top_low"][d.object_id] = round(patch.low(), 3)
        rep["samples"][d.object_id] = [len(patch.a), len(patch.b), len(patch.s0), len(patch.s1)]
        near = prep(deck_polygon(d).buffer(_ON_RING_M))
        lu = max(1e-9, hypot(patch.u[0], patch.u[1]))
        for v, vx in pm.vertices.items():
            if not near.contains(Point(vx.xy)):
                continue
            roles = {pm.faces[f].role for f in vx.incident_faces}
            if low & roles:
                continue                # a road's or the cut's own vertex: stage 2's
            s_, _t = patch.st(*vx.xy)
            on_end = min(abs(s_), abs(s_ - 1.0)) * lu <= _ON_RING_M
            if v in air and v in levels:
                # the join's own level against the patch: the deck's flushness
                off = abs(float(levels[v]) - patch.z(*vx.xy))
                rep["ring_off"][d.object_id] = round(max(off, rep["ring_off"].get(
                    d.object_id, 0.0)), 3)
            if (v in air and v not in levels) or (on_end and v not in air):
                # the airside the join missed, and the abutment's crest under
                # each end: the deck's level (flush by construction)
                fixed[v] = round(patch.z(*vx.xy), 6)
            elif v in levels and v not in air:
                free.add(v)
    _zone_pins(pm, (*decks, *held), stage1, law, air, levels, low, fixed)
    # owner 2026-11-19T23:07Z: the cut is the deck's -- its floor, banks,
    # abutment embankments and ramps back to the terrain, levelled from the
    # top just read (``constraints/deck_carve``); never an airside vertex
    from .deck_carve import carve_levels
    cut, rep["carve"] = carve_levels(pm, decks, patches, air, levels, fixed, law)
    fixed.update(cut)
    free.difference_update(cut)
    rep["fixed"], rep["freed"] = len(fixed), len(free)
    cs2 = _floor_pins(pm, cs, target, rep)
    return cs2, _StageTwo(rep, fixed, frozenset(free), tops)


def _zone_pins(pm, decks, stage1, law, air, levels, low, fixed: dict) -> None:
    """Every full-map AIRSIDE vertex the coordinate join left without a
    stage-1 level within a deck's ZONE -- its ring and the pavement its
    cut opens (``approach``), grown by the road's ramp at its grade cap
    (``floor_min_m / [tunnel] ramp_max_grade``: as far as the carve can
    reach) -- takes stage 1's surface there (:func:`_tin`), unless the deck
    already fixed it: the carve's rows never move airside (19s (1); the
    no-bridge arm pins the same vertices, ``deck_airside.no_bridge_arm``).
    Never a road's or the cut's own vertex (``low``)."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep

    from ..planar.deck_bridge import deck_polygon
    cap = float(law.tables.structures.tunnel.ramp_max_grade) if law is not None else 0.0
    parts = []
    for d in decks:
        reach = float(d.floor_min_m) / cap if cap > 0.0 else 0.0
        polys = [deck_polygon(d)] + [Polygon(q) for q in getattr(d, "approach", ()) or ()
                                     if len(q) >= 3]
        parts.append(unary_union([p if p.is_valid else p.buffer(0.0) for p in polys])
                     .buffer(reach))
    if not parts:
        return
    zone = prep(unary_union(parts))
    tin = _tin(stage1, zone)
    if tin is None:
        return
    for v, vx in pm.vertices.items():
        if v not in air or v in levels or v in fixed or not zone.contains(Point(vx.xy)):
            continue
        if low & {pm.faces[f].role for f in vx.incident_faces}:
            continue
        z = tin(vx.xy)
        if z is not None:
            fixed[v] = round(z, 6)


def _tin(stage1, opened) -> "_t.Callable | None":
    """``z(xy)``: stage 1's levelled surface (a linear TIN of its solved
    vertices) -- the no-bridge airside a vertex the full map minted where
    the cut opens pavement takes; ``None`` without a stage-1 answer."""
    solved = getattr(stage1, "solved", None) if stage1 is not None else None
    if not solved:
        return None
    import numpy as np
    from scipy.interpolate import LinearNDInterpolator
    x0, y0, x1, y1 = opened.context.bounds
    pts, zs = [], []
    for v, z in solved.items():
        vx = stage1.pm.vertices.get(v) if isinstance(stage1.pm.vertices, dict) \
            else stage1.pm.vertices[v]
        if vx is not None and x0 - 30.0 <= vx.xy[0] <= x1 + 30.0 \
                and y0 - 30.0 <= vx.xy[1] <= y1 + 30.0:
            pts.append(vx.xy)
            zs.append(float(z))
    if len(pts) < 3:
        return None
    f = LinearNDInterpolator(np.asarray(pts, float), np.asarray(zs, float))

    def z_at(xy) -> "float | None":
        got = float(f(xy[0], xy[1]))
        return got if got == got else None
    return z_at


def _floor_pins(pm, cs, target: _t.Mapping[str, float], rep: dict):
    """``cs`` with each generated deck's floor pins at ``min(pin, target)``;
    ``rep`` takes the counts and each deck's floor."""
    deck_of = {tn.id: getattr(tn, "deck_bridge", "") for tn in getattr(pm, "structures", ()) or ()}
    by_tn: dict[str, float] = {}
    for p in cs.pins:
        if p.source.ruling == DECK_FLOOR and p.source.inputs:
            tid = p.source.inputs[0]
            if deck_of.get(tid) in target:
                by_tn[tid] = max(by_tn.get(tid, -float("inf")), float(p.z))
    for tid, z in by_tn.items():
        oid = deck_of[tid]
        floor = min(z, target[oid])
        cur = rep["floor"].get(oid)
        rep["floor"][oid] = round(floor if cur is None else min(cur, floor), 3)
    drop = {tid: target[deck_of[tid]] - z for tid, z in by_tn.items()
            if target[deck_of[tid]] < z - 1e-6}
    if not drop:
        return cs
    pins = []
    for p in cs.pins:
        tid = p.source.inputs[0] if p.source.ruling == DECK_FLOOR and p.source.inputs else None
        if tid in drop:
            p = _dc.replace(p, z=float(p.z) + drop[tid])
            rep["pins"] += 1
        pins.append(p)
    rep["decks"] = len({deck_of[t] for t in drop})
    rep["max_drop_m"] = round(-min(drop.values()), 3)
    return _dc.replace(cs, pins=tuple(pins))
