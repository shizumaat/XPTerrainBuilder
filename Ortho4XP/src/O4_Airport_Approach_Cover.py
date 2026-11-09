"""Where an airport's sharper imagery (``cover_zl``) goes (#1990).

Owner 2026-11-09 (approved spec, issue #1990): ZL18 at airports follows
the approaches.  The sharper squares are the ``cover_zl`` texture squares
that meet the airport's COVER REGION:

* the airport boundary (the tile's ``.apt`` pickle, tile-local degrees),
  widened by ``cover_extent`` km around the polygon itself (0 = the
  boundary only, Light on disk);
* one APPROACH CORRIDOR per runway end, read from apt.dat row 100: from
  the landing threshold (displaced thresholds respected) outward along the
  extended centreline for as far as a 3 degree glide path takes to climb
  ``cover_approach_ft`` above the threshold (1,000 ft ~ 5.8 km, 500 ft ~
  2.9 km, 0 = no corridor), widening from the runway width at the
  threshold to :data:`CORRIDOR_FAR_WIDTH_M` at its far end.

Every number comes from the cfg and apt.dat: nothing here knows which
airport it is reading.  Coordinates leave this module tile-local
(``x = lon - tile.lon``, ``y = lat - tile.lat``) like the boundary.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from shapely import affinity, ops
from shapely.geometry import Polygon, box
from shapely.prepared import prep

from auto_patch_v2.airport import apt_dat as APT_DAT

import O4_Airport_Elevation_Insets as INSETS
import O4_Geo_Utils as GEO

__all__ = [
    "GLIDE_PATH_DEG", "CORRIDOR_FAR_WIDTH_M", "corridor_length_m",
    "threshold_corridors", "cover_region", "cover_squares", "square_bounds",
    "airport_runways", "tile_cover_squares",
]

#: The glide path the corridor length is read on (owner: "3° glide path").
GLIDE_PATH_DEG = 3.0
#: The corridor's width at its far end (owner: "to ~1 km").
CORRIDOR_FAR_WIDTH_M = 1000.0
_FT_TO_M = 0.3048


def corridor_length_m(height_ft: float) -> float:
    """How far from the threshold a 3 degree glide path is ``height_ft``
    above it: 1,000 ft is about 5.8 km, 500 ft about 2.9 km."""
    height_m = max(float(height_ft), 0.0) * _FT_TO_M
    return height_m / math.tan(math.radians(GLIDE_PATH_DEG))


def _end_corridor(near, far, displaced_m, width_m, length_m):
    """The corridor off runway end ``near`` (``(lat, lon)``), the runway
    running toward ``far``, as a ring of ``(lon, lat)`` degrees."""
    lat0 = (near[0] + far[0]) / 2.0
    kx, ky = GEO.lon_to_m(lat0), GEO.lat_to_m
    dx, dy = (far[1] - near[1]) * kx, (far[0] - near[0]) * ky
    n = math.hypot(dx, dy)
    if n < 1e-6:
        return None
    ux, uy = dx / n, dy / n               # along the runway, near -> far
    nx, ny = -uy, ux                       # its left normal
    tx = near[1] * kx + min(max(displaced_m, 0.0), n) * ux
    ty = near[0] * ky + min(max(displaced_m, 0.0), n) * uy
    fx, fy = tx - length_m * ux, ty - length_m * uy   # outward
    h0 = max(width_m, 0.0) / 2.0
    h1 = max(CORRIDOR_FAR_WIDTH_M, width_m) / 2.0
    ring = ((tx - h0 * nx, ty - h0 * ny), (fx - h1 * nx, fy - h1 * ny),
            (fx + h1 * nx, fy + h1 * ny), (tx + h0 * nx, ty + h0 * ny))
    return [(x / kx, y / ky) for (x, y) in ring]


def threshold_corridors(runways: Iterable, length_m: float) -> list:
    """One corridor polygon (absolute ``(lon, lat)`` degrees) per runway
    end of ``runways`` (``auto_patch_v2.airport.apt_dat.AptRunway``);
    ``[]`` when ``length_m`` is 0."""
    if length_m <= 0:
        return []
    out = []
    for rw in runways:
        (_, lat_a, lon_a, disp_a, _), (_, lat_b, lon_b, disp_b, _) = rw.ends
        for near, far, disp in (((lat_a, lon_a), (lat_b, lon_b), disp_a),
                                ((lat_b, lon_b), (lat_a, lon_a), disp_b)):
            ring = _end_corridor(near, far, disp, rw.width_m, length_m)
            if ring is not None:
                out.append(Polygon(ring))
    return out


def cover_region(boundary, runways: Sequence, tile_lat: int, tile_lon: int,
                 extent_km: float, approach_ft: float):
    """The airport's cover region, tile-local degrees: ``boundary``
    widened by ``extent_km`` (in metres, around the polygon, not its
    bounding box) united with the approach corridors of ``runways``."""
    parts = []
    if boundary is not None and not boundary.is_empty:
        if extent_km > 0:
            c = boundary.centroid
            kx, ky = GEO.lon_to_m(tile_lat + c.y), GEO.lat_to_m
            metric = affinity.scale(boundary, kx, ky, origin=(0, 0))
            boundary = affinity.scale(metric.buffer(1000.0 * extent_km),
                                      1 / kx, 1 / ky, origin=(0, 0))
        parts.append(boundary)
    for poly in threshold_corridors(runways, corridor_length_m(approach_ft)):
        parts.append(affinity.translate(poly, -tile_lon, -tile_lat))
    return ops.unary_union(parts) if parts else Polygon()


def square_bounds(til_x: int, til_y: int, zl: int, tile_lat: int,
                  tile_lon: int) -> tuple:
    """``(xmin, ymin, xmax, ymax)`` tile-local degrees of the ``zl``
    texture square whose top-left gtile is ``(til_x, til_y)``."""
    lat_top, lon_left = GEO.gtile_to_wgs84(til_x, til_y, zl)
    lat_bot, lon_right = GEO.gtile_to_wgs84(til_x + 16, til_y + 16, zl)
    return (lon_left - tile_lon, lat_bot - tile_lat,
            lon_right - tile_lon, lat_top - tile_lat)


def cover_squares(region, tile_lat: int, tile_lon: int, zl: int) -> set:
    """The ``zl`` texture squares (top-left gtile ``(til_x, til_y)``) of
    the tile that meet ``region`` (tile-local degrees)."""
    if region is None or region.is_empty:
        return set()
    xmin, ymin, xmax, ymax = region.bounds
    xmin, ymin = max(xmin, 0.0), max(ymin, 0.0)
    xmax, ymax = min(xmax, 1.0), min(ymax, 1.0)
    if xmin > xmax or ymin > ymax:
        return set()
    x0, y0 = GEO.wgs84_to_orthogrid(tile_lat + ymax, tile_lon + xmin, zl)
    x1, y1 = GEO.wgs84_to_orthogrid(tile_lat + ymin, tile_lon + xmax, zl)
    tile_box = box(0.0, 0.0, 1.0, 1.0)
    hit = prep(region.intersection(tile_box))
    out = set()
    for til_x in range(x0, x1 + 1, 16):
        for til_y in range(y0, y1 + 1, 16):
            if hit.intersects(box(*square_bounds(til_x, til_y, zl,
                                                 tile_lat, tile_lon))):
                out.add((til_x, til_y))
    return out


def airport_runways(code, xplane_root: Optional[str]) -> tuple:
    """apt.dat row-100 runways of airport ``code``, from the apt.dat
    auto_patch's own selector picks for it (the pack X-Plane draws, else
    Global Airports); ``()`` for a code apt.dat does not know or an
    install that cannot be found."""
    if not isinstance(code, str) or not xplane_root:
        return ()
    try:
        path = APT_DAT.select_apt_dat(xplane_root, code)
        block = APT_DAT.read_airport_block(path, code) if path else None
        return APT_DAT.parse_airport_block(block).runways if block else ()
    except (OSError, ValueError):
        return ()


def tile_cover_squares(tile, dico_airports: dict, airports: Iterable,
                       xplane_root: Optional[str] = None) -> set:
    """Every ``tile.cover_zl`` texture square the ``airports`` of
    ``dico_airports`` cover: boundary (+ ``tile.cover_extent`` km) and,
    with ``tile.cover_approach_ft`` above 0, their approach corridors."""
    approach_ft = float(getattr(tile, "cover_approach_ft", 0) or 0)
    extent_km = float(getattr(tile, "cover_extent", 0) or 0)
    if approach_ft > 0 and xplane_root is None:
        xplane_root = INSETS._xplane_root_for_package_footprints()
    squares = set()
    for airport in airports:
        runways = (airport_runways(airport, xplane_root)
                   if approach_ft > 0 else ())
        region = cover_region(dico_airports[airport].get("boundary"),
                              runways, tile.lat, tile.lon, extent_km,
                              approach_ft)
        squares |= cover_squares(region, tile.lat, tile.lon, tile.cover_zl)
    return squares
