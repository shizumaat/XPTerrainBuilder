"""THE FLAT-SITE PLATEAU IS A FILL, NOT A CUT — the stamp's one after-pass.

Owner RULINGS 2026-10-26r (Q173, option a; #1208), refining 2026-10-20af
and 2026-10-20ag: "flattening only raises ground; where the real ground
stands more than 0.5 m above the flat level, keep the real ground, except
where pavement grading itself needs a cut".  It replaces the #1137 rule
("a hill is not the site": off the airport's whole gate, ground more than
5 m above Z0 came back), which left the boundary's own grass — and every
metre of ground up to 5 m above Z0 around it — cut down to Z0.  Seen as a
coastal-flat airport's edge cut down (the CYVR report; at CYVR itself the
stamp turned out not to fire, ``docs/findings/1208-l1208.md``).

THE RULE.  The stamp (``O4_Airport_Elevation_Insets``: the core, each
claimed-object cluster, the R21 isthmus) bakes a constant Z0.  After an
airport's bakes, against a snapshot of the honest surface taken before
them, a post the stamp LOWERED whose honest surface stands above Z0 by
more than :data:`KEEP_ABOVE_M` gets that surface back — in full from
:data:`REAL_FROM_M`, linearly in between, so the result is continuous in
the honest surface and no post ends more than ``KEEP_ABOVE_M`` below it.

ONLY A CUT IS UNDONE.  A post the stamp raised (honest surface below Z0 —
the reclamation class R8-1 and 20af exist for: VHHH's 2.00 m sea fill)
keeps Z0.

PAVEMENT AND THE RUNWAY STRIPS KEEP THEIR CUT (RULINGS 2026-10-27d:
inside the boundary only runways and pavement stay flat; 2026-10-27v (2):
the runway strips stay graded as the strip law requires).  The decision
record's ``held_ll`` — apt.dat pavements ∪ runways ∪ the pack's draped
pavement pages (``auto_patch_v2/airport/pack_pavement.py``) ∪ each
runway's graded strip (``auto_patch_v2/law/runway_strip.py``), margin 0 —
stays at Z0 whatever the DEM says.  The rest of the boundary's grass, the
margin, the cluster hulls and the isthmus keep their real ground; the
groundside roads and pads on it grade by their own rules (2026-10-27v
(1)), and grading the pavement's edge to the real ground beside it is the
patch's own work (its adjacent-ground zones).

It reads no file and writes nothing but the working raster.
"""
from __future__ import annotations

import math

__all__ = [
    "KEEP_ABOVE_M",
    "REAL_FROM_M",
    "site_geometry_tile_degrees",
    "snapshot_window",
    "restore_ground_above_flat_level",
]

#: RULINGS 2026-10-26r: honest ground standing more than this above Z0 is
#: real ground the plateau must not cut.  Up to it the plateau stands.
KEEP_ABOVE_M = 0.5
#: From this height above Z0 the honest surface comes back in full;
#: between :data:`KEEP_ABOVE_M` and it the restore weight ramps 0 -> 1
#: (a mechanism choice: no 0.5 m cliff along the contour, and the deepest
#: remaining cut is ``KEEP_ABOVE_M``, at the contour itself).
REAL_FROM_M = 2.0 * KEEP_ABOVE_M


def site_geometry_tile_degrees(record, tile_lat: int, tile_lon: int,
                               key: str = "held_ll"):
    """The record's ``held_ll`` rings (or another ring list named by
    ``key`` — ``footprint_ll``, the plateau's footprint, #1144) as ONE
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


def restore_ground_above_flat_level(base_dem, snapshot, held, z0_m: float,
                                    metres_per_degree=None) -> dict:
    """Undo the plateau's cut on ground standing above Z0 (module doc).

    ``snapshot`` is :func:`snapshot_window`'s answer taken before the
    airport's bakes; ``held`` the ground held at Z0
    (:func:`site_geometry_tile_degrees`), which is never touched (``None``:
    no post is exempt).  ``metres_per_degree`` — ``(lon_m, lat_m)`` —
    only sizes the report.

    Returns ``{"restored_posts", "restored_km2", "max_offset_m"}``: the
    posts the stamp had lowered that now carry some of the honest surface
    back, and the largest ``before - Z0`` among them.
    """
    import numpy

    report = {"restored_posts": 0, "restored_km2": 0.0, "max_offset_m": 0.0}
    if snapshot is None:
        return report
    row_min, row_max, col_min, col_max, before = snapshot
    window = base_dem.alt_dem[row_min:row_max + 1, col_min:col_max + 1]
    after = numpy.asarray(window, dtype=numpy.float64)
    offset = before - float(z0_m)
    weight = numpy.clip((offset - KEEP_ABOVE_M) / (REAL_FROM_M - KEEP_ABOVE_M),
                        0.0, 1.0)
    nodata = getattr(base_dem, "nodata", None)
    if nodata is not None:
        weight[before == nodata] = 0.0
    weight[~(after < before)] = 0.0          # ONLY A CUT IS UNDONE
    rows, cols = numpy.nonzero(weight > 0.0)
    if not len(rows):
        return report
    x_step = (base_dem.x1 - base_dem.x0) / (base_dem.nxdem - 1)
    y_step = (base_dem.y1 - base_dem.y0) / (base_dem.nydem - 1)
    if held is not None:
        from shapely import contains_xy

        xs = base_dem.x0 + (cols + col_min) * x_step
        ys = base_dem.y1 - (rows + row_min) * y_step
        on_held = contains_xy(held, xs, ys)
        weight[rows[on_held], cols[on_held]] = 0.0
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
