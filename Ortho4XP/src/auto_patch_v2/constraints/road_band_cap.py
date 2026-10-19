"""THE ROAD IN A SAFETY AREA IS CAPPED BY IT (owner 2026-10-19, #951).

Owner, verbatim: "For roads in safety areas, yes, as long as they are at or
below the safety area grade they are not interfering with air traffic, and
typically they are cut below" -- and then "For roads in safety area, wall
is correct."

``planar/zones.zone_regions`` stands every adjacent-ground band off a
mapped-road ribbon inside it (the groundside stand-off), so the road no
longer shares a kerb vertex with the band and a road below the band's grade
terraces against it: the declared step is the retaining wall.  This module
states the other half, "at or below": every ribbon ring vertex standing
off a band across the stand-off (``PlanarMap.band_kerb_vertices`` at
``law.tables.band_standoff_reach_m``) takes ONE one-way row
``z_road - z_band <= 0`` against the nearest band vertex.  The band leads (the row
``follows`` the road vertex); below the band the road is free."""
from __future__ import annotations

from ..law import Law
from ..law.tables import airside_stage_roles, band_standoff_reach_m
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap

__all__ = ["road_band_caps"]

GEN = "zones"
RULING = "zones.adjacent_ground road cap (owner 2026-10-19, #951)"


def road_band_caps(planar: PlanarMap, law: Law) -> list[Row]:
    """One ``z_road <= z_band`` row per ribbon ring vertex standing off a
    band vertex (module docstring)."""
    reach = band_standoff_reach_m(law)
    kerb = planar.band_kerb_vertices(airside_stage_roles(law), reach)
    band = {v for f in planar.faces.values() if f.role == "graded_strip"
            for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}
    loose = sorted(kerb - band)
    if not band or not loose:
        return []
    from scipy.spatial import cKDTree
    ids = sorted(band)
    tree = cKDTree([planar.vertices[v].xy for v in ids])
    _d, js = tree.query([planar.vertices[v].xy for v in loose])
    return [Linear(((v, 1.0), (ids[int(j)], -1.0)), None, 0.0,
                   Source(GEN, RULING, (f"vertex:{v}", f"vertex:{ids[int(j)]}")),
                   follows=v)
            for v, j in zip(loose, js)]
