"""THE ZONE BANK's rows (owner RULINGS 2026-10-15c (3) "1:3 bank";
``planar/zone_bank`` mints the faces).

Every bank vertex that is not the zone's own — the bank's interior and its
outer ring, the patch edge — stands within the 1:3 cone of the zone ring
beside it: ``|z_o − z_i| ≤ bank_slope · d`` against its ``_NEAREST``
nearest zone vertices (any zone's: a bank trimmed against a neighbour zone
stands beside that zone too).  ONE-WAY (``[design] one_way_rulings``): the
zone's ground LEADS and never moves for its bank, as the zone never moves
the pavement.  Inside the cone the bank's ground is the §23 ground datum's
(the objective's pull to the DEM), so the solve puts the toe where the DEM
meets the cone — the collar precedent (``constraints/platform._bank_rows``,
RULINGS 2026-10-02v (5)): a bank minted at the estimated width, the toe
placed by the solve inside it.  A bank too narrow for its solved step
keeps the residual at the patch edge, reported by the census, never
hidden."""
from __future__ import annotations

import math

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Band, Diff, Row, Source
from ..model.planar import PlanarMap
from ..model.planar import is_zone_bank_ref

__all__ = ["zone_bank_rows", "BANK_RULING", "TOE_RULING"]

GEN = "zone_bank"
#: The ruling HEAD (``[design] one_way_rulings`` names it).
BANK_RULING = "zones.adjacent_ground zone bank"
#: The TOE row's head: the bank's outer ring (the patch edge) on the DEM.
TOE_RULING = "zones.adjacent_ground zone bank toe"
#: How many zone-ring vertices each bank vertex is coned against.
_NEAREST = 3


def zone_bank_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The bank rows (module docstring).  A generator."""
    from scipy.spatial import cKDTree
    cap = float(law.tables.emit.design.bank_slope)
    if cap <= 0.0:
        return []
    bank_v: set[int] = set()
    zone_v: set[int] = set()
    for f in planar.faces.values():
        vs = {v for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)}
        if is_zone_bank_ref(f.ref):
            bank_v |= vs
        elif f.role == "graded_strip":
            zone_v |= vs
    # the LEADERS: every zone vertex, not only the ring a bank shares — a bank
    # trimmed against a NEIGHBOUR zone stands beside that zone's ring too
    # (measured KBJC replay: 29 seam tears bank | other zone at 4-5 m)
    inner = sorted(zone_v)
    outer = sorted(bank_v - zone_v)
    if not inner or not outer:
        return []
    xy = {v: planar.vertices[v].xy for v in inner + outer}
    tree = cKDTree([xy[v] for v in inner])
    rows: list[Row] = []
    src = Source(GEN, BANK_RULING + " (owner RULINGS 2026-10-15c (3))", ())
    k = min(_NEAREST, len(inner))
    for o in outer:
        _d, idx = tree.query(xy[o], k=k)
        for j in ([idx] if k == 1 else list(idx)):
            i = inner[int(j)]
            d = math.hypot(xy[o][0] - xy[i][0], xy[o][1] - xy[i][1])
            if d <= 0.0:
                continue
            rows.append(Diff(o, i, cap, d, Source(src.generator, src.ruling,
                                                  (f"vertex:{o}",)), follows=(o,)))
    # THE TOE IS THE DEM (the patch edge meets the mesh's raw DEM): every
    # bank vertex on the coverage edge is held at its DEM sample, as the
    # law's own row — the weak §23 datum alone let the bending term float
    # it (measured KBJC replay: 177 patch-edge vertices over 1 m)
    edge_v = {v for e in planar.edges.values()
              if e.left_face is None or e.right_face is None for v in (e.a, e.b)}
    tsrc = Source(GEN, TOE_RULING + " (owner RULINGS 2026-10-15c (3))", ())
    for o in outer:
        dz = planar.vertices[o].dem_z
        if o in edge_v and dz is not None:
            rows.append(Band(o, float(dz), float(dz),
                             Source(tsrc.generator, tsrc.ruling, (f"vertex:{o}",))))
    return rows
