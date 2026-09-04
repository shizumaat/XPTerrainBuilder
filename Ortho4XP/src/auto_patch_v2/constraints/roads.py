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

from ..law import Law
from ..law.tables import family, role_cap
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .geometry import long_axis, pair_is_transverse
from .precedence import view

__all__ = ["road_within_shape", "road_family_roles", "road_law_caps"]

GEN = "roads"


def road_family_roles(law: Law) -> tuple[str, ...]:
    """The roles the cross-section law is defined over — read from the
    family table, never typed here."""
    return tuple(family(law, "road_cross_section").roles)


def road_law_caps(planar: PlanarMap, law: Law) -> dict[int, float]:
    """Road-family face -> the STRICTEST longitudinal cap of any governed
    face sharing a ring edge with it, where stricter than its own
    (LATERAL CONTIGUITY, owner FINAL 2026-08-02 clause 2; RULINGS
    2026-08-25b): the value the emitter stamps as ``o4_grade_law_cap``
    and the cap the road's own pairs are bound at.  M2 reads contiguity
    at the shared edge; the core's per-station road clamp is M3."""
    vw = view(planar, law)
    roads = road_family_roles(law)
    out: dict[int, float] = {}
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
    stricter class carries that class's cap (``road_law_caps``)."""
    vw = view(planar, law)
    roads = road_family_roles(law)
    law_caps = road_law_caps(planar, law)
    min_deg = law.tables.common.road_transverse_axis_min_deg
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    roles = tuple(roads) + ("groundside_pavement",)
    for f in vw.faces_of_role(roles):
        cap = role_cap(law, f.role)
        if cap is None:
            continue
        cap_l = min(cap.longitudinal, law_caps.get(f.id, cap.longitudinal))
        cap_t = min(cap.transverse, cap_l)
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
                    (ax_, ay_), (bx_, by_) = vw.xy[a], vw.xy[b]
                    if axis is not None and pair_is_transverse(
                            axis, bx_ - ax_, by_ - ay_, min_deg):
                        rows.append(Diff(a, b, cap_t, d, src_t))
                    else:
                        rows.append(Diff(a, b, cap_l, d, src_l))
    return rows
