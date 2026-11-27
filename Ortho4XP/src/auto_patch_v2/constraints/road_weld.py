"""A ROAD MEETING AIRSIDE WELDS TO IT (owner RULINGS 2026-11-27a, #2281):
"a road meeting airside is supposed to weld to it (unless it's going into
a tunnel)".

A groundside road vertex within ``emit.identity.weld_spacing_m`` of an
EDGE of an airside pavement face it is not a vertex of, across a strip of
non-pavement (the planar weld leaves one where the gap read over the
tolerance before the snap), holds the pavement edge's level at its
perpendicular foot: ``|z_v - z_foot| <= cap * max(d, min_distinct)`` at
the stricter of the road's and the pavement's caps -- the airside sliver's
reading (``proximity.airside_sliver_pairs``, 2026-10-19an) with a ROAD on
one side, and ONE-WAY (``follows=(v,)``, registered in ``[design]
one_way_rulings``): the road (and a strip vertex its ribbon shares) meets
the pavement, the pavement never moves for a road -- AIRSIDE IS KING.

MEASURED EKVG (62.065792, -7.27727): service way ``-21``'s ribbon ends at
band-kerb vertices 0.57 / 0.79 m from junction ``pav0``'s 54 m edge,
across taxiway D's zone-1 strip; no row priced a vertex against that edge
(``road_ramp.reach_contacts`` reads road-owned vertices only, #2152; the
sliver pairs are pavement-only; the zone band pairs vertex to vertex), so
the road stood 0.9-1.3 m under the junction and drew a 0.63 m step.

A vertex on a STRUCTURE face (a tunnel ramp, wall or deck) takes no weld:
the road is going into the tunnel.  NOT HARD, for the reason
``road_ramp.road_contact_rows`` measured: a row in both the hard and the
one-way registers loses its leaders.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import is_structure_role, role_side
from ..model.airport import Airport
from ..model.constraints import Row, Source
from ..model.planar import PlanarMap
from .proximity import PavementEdges, foot_row, nearest_foot, pavement_edges
from .roads import road_family_roles

__all__ = ["GEN", "RULING", "road_airside_weld"]

GEN = "road_weld"
RULING = ("roads.groundside_road airside weld "
          "(owner 2026-11-27a; issue #2281)")


def _road_caps(planar: PlanarMap, law: Law, ix: PavementEdges
               ) -> tuple[frozenset[str], dict[int, float]]:
    """The groundside road roles, and each of their ring vertices' strictest cap."""
    roads = frozenset(r for r in road_family_roles(law) if role_side(law, r) == "groundside")
    out: dict[int, float] = {}
    for fid, f in planar.faces.items():
        c = ix.caps.get(fid)
        if f.role not in roads or c is None:
            continue
        for ring in (ix.vw.rings[fid], *ix.vw.holes[fid]):
            for v in ring:
                out[v] = min(out.get(v, c), c)
    return roads, out


def road_airside_weld(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One one-way row per groundside road vertex within the weld spacing
    of an airside pavement edge (module docstring)."""
    weld = float(law.tables.emit.identity.weld_spacing_m)
    min_d = float(law.tables.emit.identity.min_distinct_spacing_m)
    ix = pavement_edges(planar, law) if weld > 0.0 else None
    if ix is None:
        return []
    roads, road_cap = _road_caps(planar, law, ix)
    rows: list[Row] = []
    for v in sorted(road_cap):
        if v in ix.faces_of:
            continue                     # a vertex of the pavement: welded already
        fids = planar.vertices[v].incident_faces
        if any(is_structure_role(law, planar.faces[f].role) for f in fids):
            continue                     # into a tunnel: no weld
        foot = nearest_foot(ix, v, (), weld)
        if foot is None:
            continue
        fb = foot[2]
        ref = next((planar.faces[f].ref for f in fids
                    if planar.faces[f].role in roads and planar.faces[f].ref), "")
        rows.append(foot_row(v, foot, min(road_cap[v], ix.caps[fb]), min_d,
                             Source(GEN, RULING, (ref, planar.faces[fb].ref)),
                             follows=(v,)))
    return rows
