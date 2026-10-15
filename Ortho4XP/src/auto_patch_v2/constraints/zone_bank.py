"""THE ZONE BANK's rows (owner RULINGS 2026-10-15c (3) "1:3 bank";
``planar/zone_bank`` mints the faces).

The bank is the band between the graded zone's outer ring and the raw
DEM, minted wide enough for a 1:3 slope over the estimated step.  Its one
row is the TOE: every bank vertex on the coverage edge (the patch edge,
where the mesh's raw DEM begins) stands at its DEM sample, at the law's
weight.  Between the zone ring (its own law) and the toe the bank's ground
is the bending term's and the §23 ground datum's — a smooth fall over a
run sized for 1:3.  A bank too narrow for its solved step keeps the
excess, which the cross-shape seam reader reads (``strip_seam_tear``).

MEASURED, and why there is no cone row (CYXY replay, 2026-10-15): a 1:3
cone from the zone ring, one-way with the zone leading, did not let the
lag settle (4,557 of 11,580 one-way rows still moving after its 3 rounds,
worst leader move 8.5 m: the bending term couples the bank to its
leaders); two-way it dragged zone rings off their law line and, through a
lip vertex, lifted an apron 1.88 m.  Toe only: the lag settles (23 rows,
the base's own) and the census reads the same.  Vertices any other face
touches (pavement, a pad, a road) carry no bank row: airside is king."""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Band, Row, Source
from ..model.planar import PlanarMap, is_zone_bank_ref

__all__ = ["zone_bank_rows", "TOE_RULING"]

GEN = "zone_bank"
#: The TOE row's head: the bank's outer ring (the patch edge) on the DEM.
TOE_RULING = "zones.adjacent_ground zone bank toe"


def zone_bank_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The bank's toe rows (module docstring).  A generator."""
    bank_v: set[int] = set()
    other_v: set[int] = set()
    for f in planar.faces.values():
        vs = {v for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)}
        if is_zone_bank_ref(f.ref):
            bank_v |= vs
        else:
            other_v |= vs
    edge_v = {v for e in planar.edges.values()
              if e.left_face is None or e.right_face is None for v in (e.a, e.b)}
    rows: list[Row] = []
    for o in sorted((bank_v - other_v) & edge_v):
        dz = planar.vertices[o].dem_z
        if dz is not None:
            rows.append(Band(o, float(dz), float(dz),
                             Source(GEN, TOE_RULING + " (owner RULINGS 2026-10-15c (3))",
                                    (f"vertex:{o}",))))
    return rows
