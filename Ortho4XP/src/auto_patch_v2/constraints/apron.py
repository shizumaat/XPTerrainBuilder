"""APRON generator (families ``within_shape`` on aprons and
``apron_lattice_membrane``; RULINGS 2026-08-21b/c/d, 2026-08-24b/c,
2026-08-26).

THE APRON WITHIN-SHAPE POPULATION (2026-08-21c, spec
``apron-within-shape-population``): an apron's strict cap
(``common.roles.apron``) is owed on its MOVEMENT SURFACES — every ring
edge, every chord from a ring vertex to a SPINE vertex (a taxi / road
centreline vertex on the ring) and every FRONTAGE chord from a pad
vertex (a vertex a rigid face shares with the apron: the building seat
the census prices at the strict cap, 2026-08-08 / 09-01g); a
generic interior body chord is law at the interior fan cap
(``common.apron_fan_ramp_max``) out to ``within_shape.apron_body_chord_max_m``
and not a grade path beyond it.  The census gates body chords further by
polygon visibility; v2 prices the superset, which can only be stricter.

Lattice / membrane (``emit.chords.apron_interior_spacing_m``): the M1 map
has no interior vertices (M0 open question 3); the membrane family is
therefore vacuous on v2's own publication — recorded in the M2 report,
nothing minted here.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import is_rigid_role, role_cap
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .geometry import project_to_chain
from .precedence import view

__all__ = ["apron_within_shape"]

GEN = "apron"


def apron_within_shape(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """Ring edges and spine chords at the apron cap; body chords within
    the body gate at the interior fan cap."""
    vw = view(planar, law)
    cap = role_cap(law, "apron")
    if cap is None:
        return []
    fan = law.tables.common.apron_fan_ramp_max
    gate = law.tables.emit.within_shape.apron_body_chord_max_m
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    strict = set(vw.spine)
    for fid, f in planar.faces.items():
        if f.role in rigid:
            strict.update(vw.rings[fid])
            for h in vw.holes[fid]:
                strict.update(h)
    # the census reads spine membership by PROXIMITY to the published axis
    # polylines (the weld tolerance): an apron vertex lying ON a taxi
    # centreline chord between two axis vertices is a spine node there
    # even when the noding left it off the breakline chain
    chains = [[vw.xy[v] for v in ch] for bid, ch in vw.chains.items()
              if planar.breaklines[bid].kind == "taxi_centerline" and len(ch) >= 2]
    for f in vw.faces_of_role(("apron",)):
        for v in vw.rings[f.id]:
            if v in strict:
                continue
            for ch in chains:
                if project_to_chain(vw.xy[v], ch)[0] <= min_d:
                    strict.add(v)
                    break
    rows: list[Row] = []
    for f in vw.faces_of_role(("apron",)):
        src_ring = Source(GEN, "common.roles.apron ring edge (2026-08-21b)",
                          (f"face:{f.id}", f.ref))
        src_spine = Source(GEN, "common.roles.apron frontage chord (2026-08-21c)",
                           (f"face:{f.id}", f.ref))
        src_body = Source(GEN, "common.apron_fan_ramp_max interior (2026-08-21c)",
                          (f"face:{f.id}", f.ref))
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            n = len(ring)
            for i in range(n):
                a = ring[i]
                a_strict = a in strict
                for j in range(i + 1, n):
                    b = ring[j]
                    d = vw.dist(a, b)
                    if d < min_d:
                        continue
                    adjacent = (j == i + 1) or (i == 0 and j == n - 1)
                    if adjacent:
                        rows.append(Diff(a, b, cap.longitudinal, d, src_ring))
                    elif a_strict or b in strict:
                        rows.append(Diff(a, b, cap.longitudinal, d, src_spine))
                    elif d <= gate:
                        rows.append(Diff(a, b, fan, d, src_body))
    return rows
