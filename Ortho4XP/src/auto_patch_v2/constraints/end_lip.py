"""THE PAVEMENT'S OWN LIP INSIDE A RUNWAY END AREA (owner RULINGS
2026-10-15j, option 1).

Inside a runway's end area, the adjacent ground of every non-runway pavement
(a taxiway, a junction, an apron) FOLLOWS THAT PAVEMENT within its zone 1,
the lip of ``zones.adjacent_ground.lip_width_m`` out from the pavement
edge: its shoulder meets the pavement edge
with no step.  The runway-end profile yields there and governs the rest of
the end area.  This is a general rule for every pavement in every end area.

Measured at CYXY (lane rwyzone15c, phase 4).  The vertex v2132 stands 64 m
beyond 02/20's end and 2.9 m from the parallel taxiway pav9's edge.  pav9
climbs 1.21 m within 72 m of that end, while the end profile allows the
ground +0.14 m there.  No surface satisfied both laws, so the solve split
the difference by about 0.37 m each way.

THE ONE DERIVATION SITE.  :func:`end_lip_vertices` names the set.

* The generator (``constraints/strips``) states no end-profile row of any
  form on these vertices.
* The zone law (``constraints/zones``) leaves them out of the end box, so
  the taxiway's own band binds them in full.
* The build publishes the set as sidecar ``end_profile_yields``.
* Both readers skip it through ``verify.strips.end_profile_exempt``.
"""
from __future__ import annotations

import typing as _t

from .precedence import View

__all__ = ["end_lip_vertices", "nonrunway_pavement_roles", "pavement_edge_junction"]


def nonrunway_pavement_roles(law) -> frozenset[str]:
    """THE PAVEMENT THAT OWNS GROUND INSIDE A RUNWAY'S STRIP: every airside
    pavement role (``airside_stage_roles``) outside the runway family —
    taxiways, junctions, aprons.  The ONE role set :func:`end_lip_vertices`
    and :func:`pavement_edge_junction`'s callers (generators and both
    readers) build their vertex sets from."""
    from ..law.tables import airside_stage_roles
    runway = set(law.tables.precedence.runway_family.members)
    return frozenset(r for r in airside_stage_roles(law) if r not in runway)


def pavement_edge_junction(vertices: _t.Iterable, owned: _t.Container) -> bool:
    """A strip pair / station set that touches a NON-RUNWAY PAVEMENT vertex
    (``owned``: the vertices of :func:`nonrunway_pavement_roles` faces) is a
    PAVEMENT-EDGE JUNCTION (the master's call on #763 phase 8, under RULINGS
    2026-10-15l; Annex 14 §3.4.16: the strip is flush with a pavement edge).
    The pavement-edge no-step law judges it, not the strip's longitudinal
    or arc law: the strip generators and both readers skip it through this
    predicate.  Measured CYXY: 5 strip rows were pairs between strip ground
    and a taxiway / apron vertex standing on the strip footprint's edge."""
    return any(v in owned for v in vertices)


def end_lip_vertices(vw: View, groups: _t.Iterable | None = None) -> frozenset[int]:
    """Every strip vertex, pavement excluded, that stands within the lip
    width of a non-runway airside pavement face (``airside_stage_roles``
    less the runway family — a runway's own pavement past its end has the
    transect foot).

    The lip width is read from the law, and the identity spacing is added
    so that a vertex on the lip's outer ring reads inside.

    With ``groups`` (``strips.RunwayGroup``), the result keeps only the
    vertices inside some group's end corridor (rings 1 and 2) — the
    published set.  The result is memoised on the view, because the
    generator, the zone law and the build each ask for it."""
    memo = vw.__dict__.get("_end_lip")
    if memo is None:
        memo = _lip(vw)
        object.__setattr__(vw, "_end_lip", memo)
    if groups is None:
        return memo
    from .geometry import point_in_rect_ring
    rings = [g.rings[k] for g in groups for k in (1, 2) if k < len(g.rings)]
    return frozenset(v for v in memo
                     if any(point_in_rect_ring(*vw.xy[v], r) for r in rings))


def _lip(vw: View) -> frozenset[int]:
    from shapely import prepared
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    law = vw.law
    pavement = tuple(nonrunway_pavement_roles(law))
    polys = []
    for f in vw.faces_of_role(pavement):
        ring = [vw.xy[v] for v in vw.rings[f.id]]
        if len(ring) >= 3:
            p = Polygon(ring)
            polys.append(p if p.is_valid else p.buffer(0))
    if not polys:
        return frozenset()
    reach = (float(law.tables.zones.adjacent_ground.lip_width_m)
             + float(law.tables.emit.identity.min_distinct_spacing_m))
    lip = prepared.prep(unary_union(polys).buffer(reach))
    strip = {v for f in vw.faces_of_role(("graded_strip",))
             for v in vw.face_vertices(f.id)} - vw.pavement_vertices
    return frozenset(v for v in strip if lip.covers(Point(*vw.xy[v])))
