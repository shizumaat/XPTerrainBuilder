"""ROAD generator (families ``within_shape`` on the road family and
groundside pavement, ``road_cross_section``; RULINGS 2026-08-25g "roads
are laterally flat", owner 2026-08-03 VDOT GS-9 8 %, owner 2026-08-12
groundside = the road limit).

A road ring's pairs split by geometry against THE RING'S OWN LONG AXIS
(the minimum-area rectangle, ``geometry.long_axis``): a pair at or
beyond ``common.road_transverse_axis_min_deg`` off it is the
CROSS-SECTION and prices at ``transverse``; every other pair prices at
``longitudinal``.  ``service_road`` / ``service_junction`` are the road
family (``families.road_cross_section.roles``); ``groundside_pavement``
carries the same caps but no cross-section family — its pairs are all
longitudinal.  M2 binds the contacts only; the core's road clamp (M3)
owns the general road profile.
"""
from __future__ import annotations

import math

from ..law import Law
from ..law.tables import family, role_cap
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .geometry import long_axis, pair_is_transverse
from .precedence import view

__all__ = ["road_within_shape", "road_family_roles", "road_law_caps",
           "road_pair_reading", "NOT_A_PAIR", "NO_FRAME"]

#: :func:`road_pair_reading` verdicts (§37 (7)).
NOT_A_PAIR = "not_a_pair"     # two routes: a switchback's branches
NO_FRAME = "no_frame"         # no route answers one of them: the chord law

GEN = "roads"

#: per-generator statistics (``constraints.generate`` publishes them
#: beside the row count as ``road_within_shape.<key>``)
STATS: dict[str, dict[str, int]] = {}


def road_family_roles(law: Law) -> tuple[str, ...]:
    """The roles the cross-section law is defined over — read from the
    family table, never typed here."""
    return tuple(family(law, "road_cross_section").roles)


def road_pair_reading(cap_l: float, cap_t: float, min_deg: float,
                      fa: tuple[int, float, float] | None,
                      fb: tuple[int, float, float] | None,
                      chord: float | None = None
                      ) -> tuple[float, bool] | str:
    """§37 (7) A ROAD PAIR IS PRICED ALONG THE ROUTE (owner RULINGS
    2026-09-13av) — THE ONE READING, imported by the generator, the v2
    verify and the v1 census so all three pair the same way.

    ``fa`` / ``fb`` are the two vertices' route frames
    (``PlanarMap.road_route_frame``: ``(route id, station s, signed
    lateral t)``).  Returns ``(bound_m, transverse)``:

    * ``bound = cap_l·|Δs| + cap_t·|Δt|`` — the BOX (the taxi family's own
      reading of a diagonal, RULINGS 2026-09-06q/06s), with ``Δs`` the
      ROUTE distance along the road's centreline and ``Δt`` the offset
      across it.  A pure cross-section pair reads ``cap_t × width``, a
      pure longitudinal pair ``cap_l × route``, and neither is the plan
      chord the law used to read.
    * ``transverse`` — the pair is the CROSS-SECTION when its direction in
      ROUTE COORDINATES is at least ``min_deg`` off the centreline
      (``common.road_transverse_axis_min_deg``, the same number the ring's
      long-axis test used); ``road_cross_section`` prices only those.

    ``NOT_A_PAIR`` when the two vertices sit on DIFFERENT routes: two
    branches of one page (KCLT ``dsf:pol51``'s switchback — 45.6 m apart
    in plan, 279.9 m apart along the road) are not a pair, and the ground
    between them is adjacent ground (§19 / §31).  ``NO_FRAME`` when either
    vertex has no route: the caller keeps the chord law and counts it.
    """
    if fa is None or fb is None:
        return NO_FRAME
    if fa[0] != fb[0]:
        return NOT_A_PAIR
    ds, dt = abs(fa[1] - fb[1]), abs(fa[2] - fb[2])
    transverse = math.degrees(math.atan2(dt, ds)) >= min_deg
    bound = cap_l * ds + cap_t * dt
    # NEVER TIGHTER THAN THE CROSS-SECTION'S OWN CHORD READING.  A
    # projection COLLAPSES: two vertices a metre apart on a bend can share
    # a station and an offset, and the box would then price them at ~0 —
    # tighter than the law was before §37 (7), which prices no pair over
    # ``cap_t x its plan distance``.  The route reading is a RELAXATION of
    # the pair law (that is the whole of the ruling); this floor keeps it
    # one (the census's own ``max(baked, cap*dist)`` convention).
    if chord is not None:
        bound = max(bound, cap_t * float(chord))
    return bound, transverse


def road_law_caps(planar: PlanarMap, law: Law, airport: Airport | None = None
                  ) -> dict[int, float]:
    """Road-family face -> the STRICTEST longitudinal cap of any governed
    face sharing a ring edge with it OR present in any of its stations'
    laterally-contiguous cross-sections (``contiguity.station_caps``,
    the census's own walk), where stricter than its own (LATERAL
    CONTIGUITY, owner FINAL 2026-08-02 clause 2; RULINGS 2026-08-25b,
    2026-08-28 Amendment 2).  Without ``airport`` the strip keep-out
    (clause 5) is not applied — stricter, never looser.

    §37 (1) (RULINGS 2026-09-13q KCLT item 5): THIS IS THE TRANSVERSE
    CAP AND ONLY THE TRANSVERSE CAP.  Lateral contiguity exists so a
    road does not TEAR against the surface beside it — a lateral
    relation, priced across the road's section.  Binding the road's
    LONGITUDINAL law to it as well made KCLT's east access road
    (``dsf:pol51``, shapeIDs 945/946) descend at 1.4 % where its DEM
    falls 9 %, ending +14.22 m in the air at 35.2074982, -80.9296586 —
    0.015 on 42 of KCLT's 121 groundside faces, the 1:3 bank then
    walking 34 m to daylight the fill.  A road's longitudinal cap stays
    its own (``service_road`` 8 %); the value here is stamped as
    ``o4_grade_law_cap_t`` and bounds the CROSS-SECTION pairs only."""
    vw = view(planar, law)
    roads = road_family_roles(law)
    out: dict[int, float] = {}
    from .contiguity import face_station_cap, road_station_caps
    for fid, sts in road_station_caps(planar, law, airport, vw).items():
        c = face_station_cap(sts)
        mc = vw.caps.get(fid)
        if c is not None and mc is not None and c < mc[0]:
            out[fid] = c
    for e in planar.edges.values():
        if e.left_face is None or e.right_face is None:
            continue
        for me, other in ((e.left_face, e.right_face), (e.right_face, e.left_face)):
            fm = planar.faces[me]
            if fm.role not in roads:
                continue
            oc = vw.caps[other]
            mc = vw.caps[me]
            if oc is None or mc is None or oc[0] >= mc[0]:
                continue
            out[me] = min(out.get(me, mc[0]), oc[0])
    return out


def road_within_shape(planar: PlanarMap, law: Law, airport: Airport
                      ) -> list[Row]:
    """All pairs of every road-family / groundside ring, cross-section
    pairs at the transverse cap; a road laterally contiguous with a
    stricter class carries that class's cap as its TRANSVERSE cap and
    keeps its own longitudinal one (``road_law_caps``, §37 (1))."""
    vw = view(planar, law)
    roads = road_family_roles(law)
    law_caps = road_law_caps(planar, law, airport)   # §37 (1): TRANSVERSE only
    # §37 (7) (owner RULINGS 2026-09-13av): the road's own route frame,
    # published by ``airport/road_ramp.road_route_frame``.  Absent (a v1
    # map, a probe that skipped the publisher) the chord law stands.
    frame = getattr(planar, "road_route_frame", None) or {}
    stats = STATS.setdefault("road_within_shape",
                             {"routed": 0, "chord": 0, "not_a_pair": 0,
                              "ring_edge": 0})
    for k in stats:
        stats[k] = 0
    min_deg = law.tables.common.road_transverse_axis_min_deg
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    # groundside classes without a cross-section axis: all pairs at the
    # role's longitudinal cap (parking_lot: owner 2026-09-04j, 5 %)
    roles = tuple(roads) + ("groundside_pavement", "parking_lot")
    for f in vw.faces_of_role(roles):
        cap = role_cap(law, f.role)
        if cap is None:
            continue
        # §37 (1): the longitudinal cap is the ROLE'S OWN; lateral
        # contiguity binds the transverse cap only
        cap_l = cap.longitudinal
        cap_t = min(cap.transverse, cap_l,
                    law_caps.get(f.id, cap.transverse))
        ring = vw.rings[f.id]
        axis = None
        if f.role in roads:
            ax = long_axis([vw.xy[v] for v in ring])
            axis = ax[0] if ax else None
        src_l = Source(GEN, "common.roles longitudinal (2026-08-03)",
                       (f"face:{f.id}", f.ref))
        src_t = Source(GEN, "road_cross_section (2026-08-25g)",
                       (f"face:{f.id}", f.ref))
        for cyc in [ring, *vw.holes[f.id]]:
            n = len(cyc)
            for i in range(n):
                a = cyc[i]
                for j in range(i + 1, n):
                    b = cyc[j]
                    d = vw.dist(a, b)
                    if d < min_d:
                        continue
                    # §37 (7): the ROUTE reading where the map carries the
                    # road's own frame; the chord law where it does not
                    read = road_pair_reading(cap_l, cap_t, min_deg,
                                             frame.get(a), frame.get(b), d) \
                        if frame else NO_FRAME
                    if read == NOT_A_PAIR:
                        # A RING EDGE IS ALWAYS PRICED (the census's own
                        # R19-5 floor): two ADJACENT ring vertices are
                        # neighbours whatever route answers them — a way
                        # BOUNDARY mid-road must not leave a step
                        # unpriced.  Only a non-adjacent cross-route pair
                        # is the switchback the ruling frees.
                        if j != i + 1 and not (i == 0 and j == n - 1):
                            stats["not_a_pair"] += 1
                            continue
                        read = NO_FRAME
                        stats["ring_edge"] += 1
                    if read != NO_FRAME:
                        bound, transverse = read
                        stats["routed"] += 1
                        rows.append(Diff(a, b, bound / d, d,
                                         src_t if transverse else src_l))
                        continue
                    stats["chord"] += 1
                    (ax_, ay_), (bx_, by_) = vw.xy[a], vw.xy[b]
                    if axis is not None and pair_is_transverse(
                            axis, bx_ - ax_, by_ - ay_, min_deg):
                        rows.append(Diff(a, b, cap_t, d, src_t))
                    else:
                        rows.append(Diff(a, b, cap_l, d, src_l))
    return rows
