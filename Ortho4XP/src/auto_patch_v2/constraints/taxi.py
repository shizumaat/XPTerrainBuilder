"""TAXI-FAMILY generator (family ``within_shape`` on the taxi family,
``plane_gradient`` on triangles; ICAO Annex 14 §3.9.10 / FAA AC
150/5300-13B §4 through ``rulesets.<authority>.taxi``).

* every taxi-family face (``precedence.taxi_family.members``) is a PLANE
  shape in the census (all vertex pairs at the role's longitudinal cap by
  code letter) — the same population here, as ``Diff`` rows;
* every ``taxi_centerline`` breakline chord at the cap of the face(s) it
  bounds (RULINGS "reach follows centrelines": the profile an aircraft
  actually travels);
* a THREE-vertex face is a rendered triangle whose PLANE gradient the
  census reads (user 2026-07-05): its gradient vector is linear in z, so
  ``|∇z| ≤ cap`` is bound by 16 half-planes at ``cap · cos(π/16)`` — a
  linearisation of the disc (1.9 % inside the law's own bound; the
  tightening is a linearisation artefact, not a law value).
"""
from __future__ import annotations

import math

from ..law import Law
from ..law.tables import role_cap
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import View, view

__all__ = ["taxi_within_shape", "taxi_centerlines", "triangle_planes",
           "all_pairs"]

GEN = "taxi"
_GRADIENT_DIRECTIONS = 16


def all_pairs(vw: View, ring: list[int], cap_l: float, src: Source,
              min_d: float) -> list[Row]:
    """Every distinct vertex pair of ``ring`` at ``cap_l``."""
    rows: list[Row] = []
    n = len(ring)
    for i in range(n):
        a = ring[i]
        for j in range(i + 1, n):
            b = ring[j]
            d = vw.dist(a, b)
            if d < min_d:
                continue
            rows.append(Diff(a, b, cap_l, d, src))
    return rows


def taxi_within_shape(planar: PlanarMap, law: Law, airport: Airport
                      ) -> list[Row]:
    """All pairs of every taxi-family ring at its letter cap."""
    vw = view(planar, law)
    members = law.tables.precedence.taxi_family.members
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    for f in vw.faces_of_role(members):
        cap = role_cap(law, f.role, f.code_number, f.code_letter)
        if cap is None:
            continue
        src = Source(GEN, "rulesets.taxi.longitudinal within_shape",
                     (f"face:{f.id}", f.ref))
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            rows.extend(all_pairs(vw, ring, cap.longitudinal, src, min_d))
    return rows


def taxi_centerlines(planar: PlanarMap, law: Law, airport: Airport
                     ) -> list[Row]:
    """Longitudinal cap along every taxi centreline chord: the strictest
    governed cap of the faces the chord bounds (an apron lane is apron,
    RULINGS 2026-09-03j)."""
    vw = view(planar, law)
    rows: list[Row] = []
    for bid, b in planar.breaklines.items():
        if b.kind != "taxi_centerline":
            continue
        src = Source(GEN, "rulesets.taxi.longitudinal centreline",
                     (f"breakline:{bid}", b.ref))
        for eid in b.edges:
            e = planar.edges[eid]
            caps = [vw.caps[f][0] for f in (e.left_face, e.right_face)
                    if f is not None and vw.caps[f] is not None]
            if not caps:
                continue
            d = vw.dist(e.a, e.b)
            if d <= 0.0:
                continue
            rows.append(Diff(e.a, e.b, min(caps), d, src))
    return rows


def triangle_planes(planar: PlanarMap, law: Law, airport: Airport
                    ) -> list[Row]:
    """``|∇z| ≤ cap`` on every governed three-vertex face (the census's
    ``plane_gradient`` family reads triangles only)."""
    vw = view(planar, law)
    from .roads import road_law_caps
    law_caps = road_law_caps(planar, law)
    rows: list[Row] = []
    for fid, ring in vw.rings.items():
        if len(ring) != 3 or vw.holes[fid]:
            continue
        cap = vw.caps[fid]
        if cap is None:
            continue
        cap = (min(cap[0], law_caps.get(fid, cap[0])), cap[1])
        f = planar.faces[fid]
        (x1, y1), (x2, y2), (x3, y3) = (vw.xy[v] for v in ring)
        det = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
        if abs(det) < 1e-9:
            continue
        # ∇z = M · (z1, z2, z3): gx = Σ gi·zi, gy = Σ hi·zi (barycentric)
        gx = ((y2 - y3) / det, (y3 - y1) / det, (y1 - y2) / det)
        gy = ((x3 - x2) / det, (x1 - x3) / det, (x2 - x1) / det)
        src = Source(GEN, "plane_gradient (user 2026-07-05)",
                     (f"face:{fid}", f.ref))
        bound = cap[0] * math.cos(math.pi / _GRADIENT_DIRECTIONS)
        for k in range(_GRADIENT_DIRECTIONS):
            th = 2.0 * math.pi * k / _GRADIENT_DIRECTIONS
            c, s = math.cos(th), math.sin(th)
            terms = tuple((ring[i], c * gx[i] + s * gy[i]) for i in range(3))
            rows.append(Linear(terms, None, bound, src))
    return rows
