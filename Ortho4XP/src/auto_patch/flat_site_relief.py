"""A HILL IS NOT THE SITE — the flat-site plateau's off-site relief rule.

Issue #1137 (owner, app 1.0.409 in-sim): at VMMC and VHHH the terrain
BEYOND the airport boundary sat at apron level.  VMMC 22.158794,
113.571673 — the Taipa hillside west of the terminal — read 6.096 m in the
tile's ``.alt`` and mesh against 86.4 m in the same raster composed with
FLAT-SITE mode off; VHHH's Lantau hillside behind Tung Chung (22.2913,
113.9630, 294 m) read 7.62 m.  The flat-site synthetic inset is a
RECTANGLE (the bbox of the detector's region, and one box per claimed
object cluster) minus water, so every patch of land inside the box took
Z0 — the airport's own surfaces, and the hill beside them alike.

THE RULE (the R21 isthmus band, "a hill is not a causeway", applied to
every flat-site footprint): the plateau keeps the airport's OWN surfaces
(the decision record's ``gate`` — pavement ∪ runways ∪ boundary, water
cut) at Z0 whatever the DEM says there, because that is what the detector
measured flat.  Everywhere else the box reaches — its margin, its corners,
a cluster box — ground the honest surface holds ABOVE Z0 keeps it: up to
``band_m / 2`` above it is Z0, beyond ``band_m`` the pre-substitution
surface comes back untouched, and in between the two blend linearly, so
the plateau meets the hillside without a manufactured cliff.

ONLY ABOVE.  Land the honest surface holds BELOW Z0 is still lifted: that
is the reclamation class R8-1 exists for (VHHH's HZMB port island and the
ground east of Chek Lap Kok read the hongkong5m raster's 2.00 m sea fill,
VMMC's reclaimed fringe 0.00 m — 2.7 and 0.46 km2 of land the 1.0.409
plateau lifted, measured 2026-10-20), where the DEM predates the land and
the CIFP datum is the truth.  A hill standing out of the plateau is the
opposite case: real relief the source has no reason to invent.

It runs AFTER an airport's core and cluster insets are baked, over the
window they cover, against a snapshot taken BEFORE them — so every gate
the bake already applies (the R11-2 cluster datum ring, the water cut,
the feather) measures exactly what it measured before, and the honest
surface it restores is the one the detector classified.  It reads no
file and writes nothing but the working raster.
"""
from __future__ import annotations

import math

__all__ = [
    "BAND_FULL_FRACTION",
    "site_geometry_tile_degrees",
    "snapshot_window",
    "restore_off_site_relief",
]

#: The inner part of the band, as a fraction of ``band_m``, over which the
#: substitution stands in full.  Between it and ``band_m`` the restore
#: weight ramps 0 -> 1, so the value is continuous in the honest surface.
BAND_FULL_FRACTION = 0.5


def site_geometry_tile_degrees(record, tile_lat: int, tile_lon: int,
                               key: str = "gate_ll"):
    """The record's ``gate_ll`` rings (or another ring list named by
    ``key`` — ``region_ll``, the plateau's footprint, #1144) as ONE
    tile-relative geometry, or ``None`` when the record carries none."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    def _ring(points):
        return [(float(lo) - tile_lon, float(la) - tile_lat)
                for lo, la in points]

    polys = []
    for outer, holes in (record.get(key) or ()):
        if len(outer) < 3:
            continue
        poly = Polygon(_ring(outer), [_ring(h) for h in holes if len(h) >= 3])
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty:
            polys.append(poly)
    if not polys:
        return None
    union = unary_union(polys)
    return None if union.is_empty else union


def snapshot_window(base_dem, rects):
    """``(row_min, row_max, col_min, col_max, before)`` — the working-grid
    window covering every rectangle in ``rects`` (tile-relative degrees)
    and a COPY of its values, or ``None`` when nothing overlaps."""
    import numpy

    if not rects:
        return None
    x_step = (base_dem.x1 - base_dem.x0) / (base_dem.nxdem - 1)
    y_step = (base_dem.y1 - base_dem.y0) / (base_dem.nydem - 1)
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    col_min = max(int(math.floor((x0 - base_dem.x0) / x_step)), 0)
    col_max = min(int(math.ceil((x1 - base_dem.x0) / x_step)),
                  base_dem.nxdem - 1)
    row_min = max(int(math.floor((base_dem.y1 - y1) / y_step)), 0)
    row_max = min(int(math.ceil((base_dem.y1 - y0) / y_step)),
                  base_dem.nydem - 1)
    if col_min > col_max or row_min > row_max:
        return None
    before = numpy.array(
        base_dem.alt_dem[row_min:row_max + 1, col_min:col_max + 1],
        dtype=numpy.float64)
    return (row_min, row_max, col_min, col_max, before)


def restore_off_site_relief(base_dem, snapshot, site, z0_m: float,
                            band_m: float, metres_per_degree=None) -> dict:
    """Put the honest surface back on off-site ground standing above Z0.

    ``snapshot`` is :func:`snapshot_window`'s answer taken before the
    airport's insets baked; ``site`` the airport's own surfaces
    (:func:`site_geometry_tile_degrees`), which are never touched.
    ``metres_per_degree`` — ``(lon_m, lat_m)`` — only sizes the report.

    Returns ``{"restored_posts", "restored_km2", "max_offset_m"}``: the
    posts the substitution had moved that now carry some of the honest
    surface back, and the largest ``before - Z0`` among them.
    """
    import numpy
    from shapely import contains_xy

    report = {"restored_posts": 0, "restored_km2": 0.0, "max_offset_m": 0.0}
    if snapshot is None or site is None or not band_m or band_m <= 0:
        return report
    row_min, row_max, col_min, col_max, before = snapshot
    window = base_dem.alt_dem[row_min:row_max + 1, col_min:col_max + 1]
    after = numpy.asarray(window, dtype=numpy.float64)
    moved = after != before
    if not numpy.any(moved):
        return report
    full_m = float(band_m) * BAND_FULL_FRACTION
    # Signed: only ground ABOVE Z0 comes back (module doc, ONLY ABOVE).
    offset = before - float(z0_m)
    weight = numpy.clip((offset - full_m) / (float(band_m) - full_m),
                        0.0, 1.0)
    nodata = getattr(base_dem, "nodata", None)
    if nodata is not None:
        weight[before == nodata] = 0.0
    weight[~moved] = 0.0
    rows, cols = numpy.nonzero(weight > 0.0)
    if not len(rows):
        return report
    x_step = (base_dem.x1 - base_dem.x0) / (base_dem.nxdem - 1)
    y_step = (base_dem.y1 - base_dem.y0) / (base_dem.nydem - 1)
    xs = base_dem.x0 + (cols + col_min) * x_step
    ys = base_dem.y1 - (rows + row_min) * y_step
    on_site = contains_xy(site, xs, ys)
    weight[rows[on_site], cols[on_site]] = 0.0
    restored = weight > 0.0
    if not numpy.any(restored):
        return report
    blended = after + weight * (before - after)
    window[...] = blended.astype(base_dem.alt_dem.dtype)
    count = int(restored.sum())
    lon_m, lat_m = metres_per_degree or (0.0, 0.0)
    report["restored_posts"] = count
    report["restored_km2"] = round(
        count * abs(x_step * lon_m) * abs(y_step * lat_m) / 1e6, 4)
    report["max_offset_m"] = round(float(offset[restored].max()), 2)
    return report
