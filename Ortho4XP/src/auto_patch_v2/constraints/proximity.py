"""CROSS-SHAPE PROXIMITY generator — family ``cross_shape`` (v1
``check_grade._check_cross_shape_proximity``; v2 ``verify/steps.
cross_shape``, the one reader): two DISTINCT vertices of DIFFERENT
governed faces within ``emit.identity.min_distinct_spacing_m`` of each
other hold the STRICTER of the two faces' caps over their distance —
the census's proximity law, read at the identity knob.  By the identity
law two distinct vertices are never closer than that spacing, so the
population is the stand-off class exactly AT it: a pad rim cut back
half a metre from its neighbour (CYXY building6 ↔ building7 across the
0.5 m sliver of apron pav17, measured 2026-09-05: 0.25 m over 0.5 m in
both readers).  A designed separation (a road-family face against a
non-road one; groundside against airside) is no pair, as the reader
skips it; an ungoverned face (no cap) contributes nothing.

WHY A GENERATOR (lane v2relaxfull6, RULINGS 2026-09-05ab): before the
centreline-only route graph (05aa) that pair was a no_step route pair
through the pad FRONTAGE hop the owner withdrew; under 05aa/05ab both
rim vertices are welded contacts whose only route to each other is
83.5 m out to taxilane station 3154 and back (167 m, outside the 150 m
no-step window), so no route family prices the 0.5 m sliver and the
census reads the step.  The law that governs it is this one, the
reader's own; stating it as a row is the exact twin of the reader.
The rows carry no ``face:`` input: their tier is the vertices' (the
stricter face's law is the row's, ``solve/tiers.row_tier``).
"""
from __future__ import annotations

import math

from ..law import Law
from ..law.tables import role_cap, role_side
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .precedence import view
from .roads import road_family_roles

__all__ = ["cross_shape_pairs"]

GEN = "proximity"


def _designed_separation(law: Law, roads: frozenset[str], ra: str, rb: str) -> bool:
    if (ra in roads) != (rb in roads):
        return True
    return (role_side(law, ra) == "groundside") != (role_side(law, rb) == "groundside")


def cross_shape_pairs(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One ``Diff`` per distinct-vertex pair of different governed faces
    within the identity spacing, at the stricter cap (module docstring)."""
    vw = view(planar, law)
    prox = law.tables.emit.identity.min_distinct_spacing_m
    roads = frozenset(road_family_roles(law))
    caps: dict[int, float] = {}
    for fid, f in planar.faces.items():
        rc = role_cap(law, f.role, f.code_number, f.code_letter)
        if rc is not None:
            caps[fid] = rc.longitudinal
    # every governed vertex with the faces it belongs to
    faces_of: dict[int, list[int]] = {}
    for fid in caps:
        for ring in [vw.rings[fid], *vw.holes[fid]]:
            for v in ring:
                faces_of.setdefault(v, []).append(fid)
    cell = prox
    grid: dict[tuple[int, int], list[int]] = {}
    for v in faces_of:
        x, y = vw.xy[v]
        grid.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))), []).append(v)
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    for v, fa in faces_of.items():
        x, y = vw.xy[v]
        cx, cy = int(math.floor(x / cell)), int(math.floor(y / cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for w in grid.get((cx + dx, cy + dy), ()):
                    if w <= v:
                        continue
                    key = (v, w)
                    if key in seen:
                        continue
                    seen.add(key)
                    d = math.hypot(x - vw.xy[w][0], y - vw.xy[w][1])
                    if d > prox or d <= 0.0:
                        continue
                    cap = None
                    pair: tuple[int, int] | None = None
                    for A in fa:
                        for B in faces_of[w]:
                            if A == B or _designed_separation(
                                    law, roads, planar.faces[A].role, planar.faces[B].role):
                                continue
                            c = min(caps[A], caps[B])
                            if cap is None or c < cap:
                                cap, pair = c, (A, B)
                    if cap is None or pair is None:
                        continue
                    A, B = pair
                    rows.append(Diff(v, w, cap, d, Source(
                        GEN, "emit.identity.min_distinct_spacing_m cross_shape proximity "
                        "(v1 _check_cross_shape_proximity; 2026-09-05ab)",
                        (planar.faces[A].ref, planar.faces[B].ref))))
    return rows
