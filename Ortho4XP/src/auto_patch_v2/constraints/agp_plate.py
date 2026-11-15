"""THE GROUND AT AN AGP FOLLOWER'S GROUND FLOOR (#2090 C3; spec
``2090-agp-group-groundside-spec.md`` C3 and amendment C; owner 21:42Z
"Lots 5 %").  Every row carries its group's id ``agp:<gid>`` in its inputs,
so the stage-2 datum rewrite moves it by the group's delta
(``constraints/agp_level``); its head is the hard-deck bridge's one ruling
(``edge_deck.RIGID``).  For every BUILT plate (``geom/agp_plate``) at level
``L``:

* P1 every vertex inside it that is no airside, structure, rigid or road
  vertex stands in ``[L - visual_m / 2, L]``;
* P2 every at-grade road vertex inside it is held at ``L`` as R1 holds an
  end-line vertex (``[L - deck_flush_m, L]``) — the road ramp is seeded
  there (``airport/deck_ends.deck_end_seeds``); a way at another layer is
  listed, never held;
* P3 a ``parking_lot`` vertex ``d`` metres outside it, ``d <= max |L - DEM|
  / 0.05``, stands in ``[L - visual_m / 2 - 0.05 d, L + 0.05 d]``.

C3c: no row on a road vertex under a joined or riding deck's ring (the road
under the bridge keeps its floor, owner Q1 (a)).  Seniority: a deck stack's
R1 / R3 vertex (its end roads, its ground) takes no P1; P1 over P3 (P3 is
outside every plate).  Nothing here names an airport.
"""
from __future__ import annotations

from ..geom.agp_plate import built_plates, inside_plates, near_plates, under_rings
from ..law import Law
from ..law.tables import airside_stage_roles, is_rigid_role, is_structure_role
from ..model.agp_plate import plate_groups, plate_road_levels, riding_rings
from ..model.airport import Airport
from ..model.constraints import Band, Row, Source
from ..model.planar import ROAD_ROLES, PlanarMap, is_agp_ground_ref, is_stack_ground_ref
from .edge_deck import RIGID

__all__ = ["GEN", "LOT_GRADE", "agp_plate_rows", "STATS"]

GEN = "agp_plate"
#: owner 2026-11-14T21:42Z "Lots 5 %": a lot leaves a plate at this grade
LOT_GRADE = 0.05
STATS: dict[str, dict[str, int]] = {}


def agp_plate_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """P1-P3 (module doc)."""
    plates = built_plates(plate_groups(planar, airport))
    STATS["agp_plate_rows"] = st = {"p1": 0, "p2": 0, "p3": 0, "p2_other_layer": 0,
                                    "under_deck": 0}
    if not plates:
        return []
    vis = float(law.tables.emit.cockpit.visual_m)
    flush = float(law.tables.structures.bridge.deck_flush_m)
    air = airside_stage_roles(law)
    rows: list[Row] = []
    listed: list[int] = []
    p2 = plate_road_levels(planar, law, airport, listed)
    st["p2_other_layer"] = len(listed)
    for v, (L, gid) in sorted(p2.items()):
        rows.append(Band(v, L - flush, L, Source(GEN, RIGID, (gid, f"vertex:{v}", "P2"))))
    st["p2"] = len(p2)
    free, lots = [], []
    for v, vx in planar.vertices.items():
        faces = [planar.faces[f] for f in vx.incident_faces if f in planar.faces]
        roles = {f.role for f in faces}
        if roles & air or roles & set(ROAD_ROLES) or any(
                is_structure_role(law, r) or is_rigid_role(law, r) for r in roles):
            continue
        if any(is_stack_ground_ref(f.ref) for f in faces):
            continue                            # a deck stack's R1 / R3 ground
        free.append((v, vx.xy))
        if "parking_lot" in roles:
            lots.append((v, vx.xy))
    inside = inside_plates(free, plates)
    under = under_rings([(v, planar.vertices[v].xy) for v in inside],
                        riding_rings(planar, airport))
    st["under_deck"] = len(under)
    for v, (gid, p) in sorted(inside.items()):
        if v in under:
            continue
        L = float(p.level)
        rows.append(Band(v, L - 0.5 * vis, L, Source(GEN, RIGID, (gid, f"vertex:{v}", "P1"))))
        st["p1"] += 1
    reach = {id(p): max(float(p.dem_off_m), _rise(planar, p, poly)) / LOT_GRADE
             for _g, p, poly in plates}
    for v, (gid, p, d) in sorted(near_plates(lots, plates, lambda p: reach[id(p)]).items()):
        L = float(p.level)
        rows.append(Band(v, L - 0.5 * vis - LOT_GRADE * d, L + LOT_GRADE * d,
                         Source(GEN, RIGID, (gid, f"vertex:{v}", "P3"))))
        st["p3"] += 1
    return rows


def _rise(planar, p, poly) -> float:
    """max |L - DEM| over the plate's own ground pieces' vertices (0 with none)."""
    best = 0.0
    tag = f":{p.member}:"
    for f in planar.faces.values():
        if not (is_agp_ground_ref(f.ref) and tag in str(f.ref)):
            continue
        for v in planar.ring_vertices(f.ring):
            dz = planar.vertices[v].dem_z
            if dz is not None:
                best = max(best, abs(float(p.level) - float(dz)))
    return best
