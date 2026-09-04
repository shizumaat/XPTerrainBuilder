"""TILE-SEAM generator (M3a).

THE LAW.  The graticule line an airport crosses is cut out of the map as
a band ``law.emit.seam.half_width_m`` each side (user 2026-05-10); the
mesh drapes the DEM in the band, and every vertex bounding it — every
role, the runway included (owner 2026-07-26, v1 ``repin_airside_seam_
cutbacks``: "every AIRSIDE cut-back edge … DEM-anchored HARD") — takes
the DEM (user 2026-07-04 "treat the seam like a runway edge"; owner
2026-07-24 "the tile seam at ALL points must be anchored at DEM").  The
production sampler serves each vertex from ITS tile's baked raster, so
that value is the one the neighbouring tile's mesh meets.  A grade row
between two seam pins prices terrain against terrain and is exempt
(``constraints.seam_exempt``; the census's own reading with sidecar
``seam_pins``: pin↔pin skips, pin↔free checks at the body cap).

WHERE THE TERRAIN AT THE SEAM IS STEEPER THAN THE LAW (owner 2026-07-24:
"not every sampled contact point can be honoured … anchoring all of it
would emit a law-violating surface"; v1 chose a deterministic sweep for
the runway and pinned everything else, its inexact solve absorbing the
rest), the seam value is a PREFERENCE row (``Linear.soft``): the LP
honours every seam vertex exactly wherever the law graph allows and
deviates by the MINIMUM (weighted L1) only where two seam values cannot
both be reached lawfully — the SPLP class measured 2026-09-04: a runway
edge at 55.51 m and a strip vertex at 57.00 m on the same seam line, the
zone band + strip chain between them reaching 1.46 m.  A seam vertex
whose solved value leaves its DEM sample by more than the materiality
floor is REPORTED (``pipeline`` "seam residuals") and is NOT published
as a pin, so the census prices its pairs at the body cap — never
midpointed, never silently dropped.

Single-tile airports (CYXY) have no seam vertices and mint nothing.
"""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap

__all__ = ["seam_pins", "seam_vertices_pinned"]

GEN = "seams"
RULING = "tile seam DEM pin (user 2026-07-04; owner 2026-07-24/26), a preference where the law forbids"


def seam_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """A soft DEM pin on every seam-band vertex."""
    rows: list[Row] = []
    for vid in sorted(planar.seam_vertices):
        v = planar.vertices[vid]
        if v.dem_z is None:
            continue
        z = float(v.dem_z)
        rows.append(Linear(((vid, 1.0),), z, z,
                           Source(GEN, RULING, (f"vertex:{vid}",)),
                           f"seam:{vid}", None))
    return rows


def seam_vertices_pinned(rows) -> set[int]:
    """The vertices the seam generator pinned (for the pair exemption)."""
    return {r.terms[0][0] for r in rows
            if isinstance(r, Linear) and r.source.generator == GEN}
