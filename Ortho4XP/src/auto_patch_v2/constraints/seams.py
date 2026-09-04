"""TILE-SEAM generator: a vertex ON a tile graticule line the airport
crosses is pinned to its DEM sample (user 2026-07-04 "treat the seam like
a runway edge"; v1 sidecar ``seam_pins``).  The neighbouring tile drapes
the same DEM there, so the pin is the only value that meets it.

Single-tile airports (CYXY) cross no line and mint nothing.  The
identity key (lat/lon at ``identity.coordinate_dp``) decides "on the
line": a vertex whose latitude or longitude rounds to an integer degree.
"""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["seam_pins"]

GEN = "seams"


def seam_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """DEM pins on every vertex lying on a tile line."""
    dp = law.tables.emit.identity.coordinate_dp
    tol = 10.0 ** (-dp)
    lats = {round(v.key[0]) for v in planar.vertices.values()}
    lons = {round(v.key[1]) for v in planar.vertices.values()}
    rows: list[Row] = []
    for v in planar.vertices.values():
        lat, lon = v.key
        on_line = any(abs(lat - L) <= tol for L in lats) or \
            any(abs(lon - L) <= tol for L in lons)
        if on_line and v.dem_z is not None:
            rows.append(Pin(v.id, float(v.dem_z),
                            Source(GEN, "tile seam DEM pin (user 2026-07-04)",
                                   (f"vertex:{v.id}",))))
    return rows
