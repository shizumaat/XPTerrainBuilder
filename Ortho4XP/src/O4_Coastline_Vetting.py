"""Coastline vetting: OSM ``natural=coastline`` seeds sea only where the
ground agrees (issue #1354).

OpenStreetMap's coastline is a single tag anyone can put on any way.  A
few metres of it, mistagged in the Rocky Mountains 900 km from any ocean,
turned a whole inland tile into sea: two closed rings with no coastline
reaching the tile frame make ``O4_Vector_Utils.coastline_to_MultiPolygon``
read "an ocean tile with two islands", and the one sea seed it returns
floods everything but the patch pavement.

Three rules, each general (no tile or airport is named anywhere):

1. :func:`vet_coastline` — a coastline COMPONENT (a closed way, or the
   merged chain of open ways) that is tiny and lies wholly inside the tile
   frame cannot be told from a tagging error by its geometry alone, so it
   is kept only when a non-OSM witness agrees: the base DEM reads at or
   near sea level just outside it.  Components that reach the frame chain
   into the coastline of the neighbouring tiles and are never touched.
2. :func:`withhold_highland_seeds` — a sea polygon whose ground is far
   above sea level everywhere holds no sea surface, whatever drew it;
   its seed is withheld, so no single seed can flood a highland tile.
3. :func:`refuse_mostly_sea_highland` — the guard rail: a tile that would
   still come out mostly sea while its whole DEM stands above sea level
   fails loudly (:class:`ImplausibleSeaTile`) instead of writing a sea
   tile.

Everything dropped or withheld is said out loud with its coordinates, so
the user can fix the OSM data.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy
import O4_UI_Utils as UI
import shapely
from shapely import geometry, ops

__all__ = [
    "FRAGMENT_MAX_LENGTH_M", "SEA_WITNESS_MAX_M", "WITNESS_REACH_M",
    "SEA_FLOOR_MAX_M", "MOSTLY_SEA_FRACTION", "ImplausibleSeaTile",
    "dem_sampler", "tile_sea_witness", "vet_coastline",
    "withhold_highland_seeds", "refuse_mostly_sea_highland",
]

#: A component shorter than this needs a witness.  A real islet this small
#: (under ~300 m across) is a rock the witness keeps, because the water
#: around it reads at sea level; a mistagged way is usually a building, a
#: pond or a field edge of this size.  Larger strays are rule 2's job.
FRAGMENT_MAX_LENGTH_M = 1000.0

#: "At or near 0 m": the base DEMs (SRTM, Copernicus, 3DEP) carry open sea
#: as 0 or as nodata filled to 0, and their vertical noise on flat ground
#: is a few metres.  10 m keeps every genuine shore and is two orders of
#: magnitude below any highland a stray lands in.
SEA_WITNESS_MAX_M = 10.0

#: How far outside a fragment the witness reads: one and a half 3" DEM
#: cells (~90 m each), so the samples fall on the water beside an islet
#: and not on the islet itself.
WITNESS_REACH_M = 150.0

#: A sea polygon whose LOWEST ground sample is above this holds no sea:
#: the lowest genuine seas lie at or below 0 m (the Caspian at -28 m), and
#: a sea polygon always holds open water cells at its surface level even
#: under a cliffed shore.  100 m clears DEM noise, tide and the coarsest
#: base grid with a wide margin; it is also the issue's guard-rail figure.
SEA_FLOOR_MAX_M = 100.0

#: "Mostly sea": more than half the tile frame.
MOSTLY_SEA_FRACTION = 0.5

#: Grid used to read a polygon's interior floor: 256 x 256 over the 1 deg
#: tile, ~430 m spacing — fine enough that any sea polygon wider than a
#: harbour holds samples, coarse enough to cost milliseconds.
_GRID_N = 256

_EDGE_EPS = 1e-7
_LAT_TO_M = 111120.0

Sampler = Callable[[numpy.ndarray], numpy.ndarray]


class ImplausibleSeaTile(RuntimeError):
    """The tile would be mostly sea while its DEM is above sea level
    everywhere: the coastline data is wrong, so nothing is written."""


def dem_sampler(dem) -> Optional[Sampler]:
    """Nearest-post reader of ``dem``'s working raster over ``(n, 2)``
    tile-relative ``(x, y)`` points; ``None`` when ``dem`` has none."""
    alt = getattr(dem, "alt_dem", None)
    if alt is None:
        return None
    x0, x1, y0, y1 = dem.x0, dem.x1, dem.y0, dem.y1
    ny, nx = alt.shape

    def sample(points: numpy.ndarray) -> numpy.ndarray:
        pts = numpy.asarray(points, dtype=float).reshape(-1, 2)
        col = numpy.rint((numpy.clip(pts[:, 0], x0, x1) - x0)
                         / (x1 - x0) * (nx - 1)).astype(numpy.int64)
        row = numpy.rint((y1 - numpy.clip(pts[:, 1], y0, y1))
                         / (y1 - y0) * (ny - 1)).astype(numpy.int64)
        return numpy.asarray(alt[row, col], dtype=float)

    return sample


def tile_sea_witness(tile) -> Optional[Sampler]:
    """The non-OSM sea witness for ``tile``: its loaded DEM when it has
    one, else its base DEM read from disk — never a download
    (``O4_DEM_Utils.is_cached`` admits the read).  ``None`` when neither
    can be had; callers then keep what they cannot judge."""
    sampler = dem_sampler(getattr(tile, "dem", None))
    if sampler is not None:
        return sampler
    memo = getattr(tile, "_coastline_sea_witness", "unset")
    if memo != "unset":
        return memo
    sampler = _base_dem_sampler(tile)
    try:
        tile._coastline_sea_witness = sampler   # one disk read per tile
    except Exception:                                      # pragma: no cover
        pass
    return sampler


def _base_dem_sampler(tile) -> Optional[Sampler]:
    try:
        import O4_DEM_Utils as DEM

        if not DEM.is_cached(tile):
            return None
        source = str(getattr(tile, "custom_dem", "") or "").split(";")[0]
        dem = DEM.DEM(tile.lat, tile.lon, source.strip(), fill_nodata=True,
                      elevation_level=getattr(tile, "elevation_level",
                                              "auto"))
        return dem_sampler(dem)
    except Exception as error:                             # pragma: no cover
        UI.vprint(1, "    * Coastline witness: base DEM unreadable (",
                  type(error).__name__, ").")
        return None


def _length_m(line, lat: float) -> float:
    coords = numpy.asarray(line.coords, dtype=float)
    if len(coords) < 2:
        return 0.0
    d = numpy.diff(coords, axis=0)
    d[:, 0] *= numpy.cos(numpy.radians(lat + 0.5))
    return float(numpy.hypot(d[:, 0], d[:, 1]).sum() * _LAT_TO_M)


def _inside_frame(line) -> bool:
    (xmin, ymin, xmax, ymax) = line.bounds
    return (xmin > _EDGE_EPS and ymin > _EDGE_EPS
            and xmax < 1 - _EDGE_EPS and ymax < 1 - _EDGE_EPS)


def _components(lines: list) -> list:
    """``[(component, [source line indices])]``: each closed way is its
    own component; open ways are merged into chains first, so a short way
    that continues a longer coastline is judged as the chain."""
    out = [(line, [i]) for i, line in enumerate(lines) if line.is_ring]
    open_idx = [i for i, line in enumerate(lines) if not line.is_ring]
    if not open_idx:
        return out
    merged = ops.linemerge([lines[i] for i in open_idx])
    tree = shapely.STRtree([lines[i] for i in open_idx])
    for chain in getattr(merged, "geoms", [merged]):
        hits = tree.query(chain, predicate="covers")
        out.append((chain, [open_idx[int(h)] for h in hits]))
    return out


def _witness_reads_sea(chain, sampler: Sampler) -> bool:
    ring = chain.buffer(WITNESS_REACH_M / _LAT_TO_M, quad_segs=4).exterior
    pts = numpy.vstack([numpy.asarray(ring.coords, dtype=float),
                        numpy.asarray(chain.coords, dtype=float)])
    return bool(numpy.nanmin(sampler(pts)) <= SEA_WITNESS_MAX_M)


def vet_coastline(coastline, lat: int, lon: int,
                  witness: Callable[[], Optional[Sampler]]):
    """Rule 1: ``coastline`` (tile-relative MultiLineString) without the
    tiny in-frame components no sea witness agrees with.

    ``witness`` is a zero-argument callable returning a sampler, so a DEM
    is only read when a candidate exists.  With no witness the coastline
    is returned unchanged: what cannot be judged is not dropped.  Returns
    ``(coastline, dropped)``, ``dropped`` one ``(lat, lon, length_m,
    ways)`` per dropped component.
    """
    lines = list(getattr(coastline, "geoms", []))
    candidates = [(c, idx) for (c, idx) in _components(lines)
                  if _inside_frame(c)
                  and _length_m(c, lat) < FRAGMENT_MAX_LENGTH_M] if lines \
        else []
    if not candidates:
        return coastline, []
    sampler = witness()
    if sampler is None:
        UI.vprint(1, "    * Coastline vetting: ", len(candidates),
                  "tiny in-tile fragment(s) kept, no DEM to witness them.")
        return coastline, []
    drop, dropped = set(), []
    for chain, idx in candidates:
        if _witness_reads_sea(chain, sampler):
            continue
        drop.update(idx)
        p = chain.representative_point()
        dropped.append((p.y + lat, p.x + lon, _length_m(chain, lat),
                        len(idx)))
    for (plat, plon, length, ways) in dropped:
        UI.loud_warning(
            "Coastline vetting: ignored a stray OSM natural=coastline "
            "fragment at {:.5f}, {:.5f} ({} way(s), {:.0f} m long, not "
            "reaching the tile edge): the ground around it is above "
            "{:.0f} m, so it is not a shore. Please fix it in "
            "OpenStreetMap.".format(plat, plon, ways, length,
                                    SEA_WITNESS_MAX_M))
    if not dropped:
        return coastline, []
    kept = [line for i, line in enumerate(lines) if i not in drop]
    return geometry.MultiLineString(kept), dropped


def _grid(sampler: Sampler):
    g = (numpy.arange(_GRID_N) + 0.5) / _GRID_N
    gx, gy = numpy.meshgrid(g, g)
    gx, gy = gx.ravel(), gy.ravel()
    return gx, gy, sampler(numpy.column_stack([gx, gy]))


def _floor_above(polygon, sampler: Sampler, grid_cache: list) -> bool:
    """True when every ground sample of ``polygon`` (its outer boundary,
    then its interior grid) is above :data:`SEA_FLOOR_MAX_M`."""
    boundary = numpy.asarray(polygon.exterior.coords, dtype=float)
    if numpy.nanmin(sampler(boundary)) <= SEA_FLOOR_MAX_M:
        return False
    if not grid_cache:
        grid_cache.append(_grid(sampler))
    gx, gy, gz = grid_cache[0]
    inside = shapely.contains_xy(polygon, gx, gy)
    return not bool(inside.any()) or bool(
        numpy.nanmin(gz[inside]) > SEA_FLOOR_MAX_M)


def withhold_highland_seeds(seed_area, sampler: Optional[Sampler],
                            lat: int, lon: int):
    """Rule 2: ``seed_area`` (MultiPolygon) without the polygons whose
    ground is above :data:`SEA_FLOOR_MAX_M` everywhere.  Returns
    ``(kept_multipolygon, withheld_count)``; unchanged with no sampler."""
    polygons = list(getattr(seed_area, "geoms", []))
    if sampler is None or not polygons:
        return seed_area, 0
    grid_cache: list = []
    kept, withheld = [], []
    for polygon in polygons:
        (withheld if _floor_above(polygon, sampler, grid_cache)
         else kept).append(polygon)
    for polygon in withheld:
        p = polygon.representative_point()
        UI.loud_warning(
            "Coastline vetting: withheld a sea seed at {:.5f}, {:.5f} "
            "({:.0%} of the tile): the ground there is above {:.0f} m "
            "everywhere, so the OSM coastline that drew it is wrong."
            .format(p.y + lat, p.x + lon, polygon.area, SEA_FLOOR_MAX_M))
    if not withheld:
        return seed_area, 0
    return geometry.MultiPolygon(kept), len(withheld)


def refuse_mostly_sea_highland(seed_area, dem, lat: int, lon: int) -> None:
    """Rule 3, the guard rail: raise :class:`ImplausibleSeaTile` when the
    sea seeds cover more than :data:`MOSTLY_SEA_FRACTION` of the tile
    while the DEM minimum is above :data:`SEA_FLOOR_MAX_M`."""
    alt = getattr(dem, "alt_dem", None)
    if alt is None or seed_area is None or seed_area.is_empty:
        return
    fraction = geometry.box(0, 0, 1, 1).intersection(seed_area).area
    floor = float(numpy.nanmin(alt))
    if fraction > MOSTLY_SEA_FRACTION and floor > SEA_FLOOR_MAX_M:
        message = (
            "Tile {:+03d}{:+04d} would be mostly sea ({:.0%}) but its lowest "
            "ground is {:.0f} m: the coastline looks wrong, so the tile is "
            "not written.".format(lat, lon, fraction, floor))
        UI.loud_warning(message)
        raise ImplausibleSeaTile(message)
