"""The global depth source wherever the sea is shallow and no fine source is.

RULINGS 2026-11-24a as widened by the owner (2026-11-24T02:08Z and 02:10Z,
"Bahamas is exactly where we would want it"): in
``masks_use_DEM_too="auto"`` a fine source keeps its airport-gated band;
all other sea takes its alpha from the coarse source (GEBCO, ~450 m).
Coverage follows DEPTH, not distance from a shore: one raster per tile at
the source's native resolution (the tile plus :data:`OVERHANG_DEGREES`,
about 0.2 MB) reaches banks with no coastline nearby, and the alpha is
zero from ``reef_visibility_depth`` down, so open deep water stays masked.

Coarse depth only ever ADDS a soft alpha over the water: the sea, and
inland water the source measures at sea level (a tidal lagoon, an
estuary, :func:`_measured_inland`; owner 2026-11-24T13:52Z, the Ria
Formosa):

* it never refines the land pre-mask: a 450 m "land" pixel is not a coast;
* its alpha is zero on and next to fine data, rising over
  :data:`FINE_JOIN_FEATHER_M`, so a fine pixel keeps its exact value and
  the join shows no step;
* its top is the tile's ``shallow_water_opacity`` (0.85 by default, as
  for every depth ramp: :func:`O4_Bathymetry_Band.shallow_water_opacity`).
"""
from __future__ import annotations

import hashlib
import os
from typing import NamedTuple, Optional

import numpy
from PIL import Image

import O4_Bathymetry_Band as BAND
import O4_Bathymetry_Source_Revision as SOURCE_REVISION
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_UI_Utils as UI
from elevation_access.failures import warp_failure_is_transient

__all__ = ["CoarseFill", "ensure_coarse_fill", "fill_is_settled",
           "fill_state", "square_alpha"]

#: The raster's reach past the tile: a mask square's padded window.
OVERHANG_DEGREES = 0.1
#: Coarse alpha rises from zero over this distance from fine data.
FINE_JOIN_FEATHER_M = 900.0
#: ... and falls to zero over this distance inside a source's own data edge
#: (a regional coarse source such as EMODnet ends at sea).
COVERAGE_FADE_M = 900.0
#: Gaussian sigma that removes the source grid's stair-steps (half a pixel
#: of the 450 m grid).
SMOOTHING_SIGMA_M = 225.0
#: The alpha is computed on the 6144 px window divided by this.
_DECIMATION = 8
#: Fine data within this many decimated pixels forces the alpha to zero,
#: so the bilinear upsample cannot reach a fine pixel.
_FINE_GUARD_PIXELS = 2
_NO_DATA_SUFFIX = ".none"
#: A fetch that failed: the masks step is not reused until it is asked again.
_RETRY_SUFFIX = ".retry"


class CoarseFill(NamedTuple):
    """The coarse raster, and the fine mosaic it must stay off."""

    coarse_path: str
    fine_vrt: Optional[str]


def _coarse_definition(tile) -> Optional[dict]:
    """The best coarse provider covering the tile, or ``None``."""
    import O4_Airport_Elevation_Insets as INSETS

    coarse = BAND._admitted_definitions(
        INSETS.select_bathymetry_definitions(tile.lat, tile.lon),
        True, False)[2]
    return coarse[0] if coarse else None


def _raster_path(tile, definition: dict) -> str:
    """One file per provider and source revision: a revised source is a
    new file, so nothing recorded under the old one is trusted."""
    return os.path.join(
        FNAMES.bathymetry_band_directory(tile.lat, tile.lon),
        "coarse_%s_r%s.tif" % (
            definition["code"].lower(),
            SOURCE_REVISION.declared_revision(definition) or 0),
    )


def ensure_coarse_fill(tile, fine_vrt) -> Optional[CoarseFill]:
    """The tile's coarse raster, fetched once.  ``None`` when the source
    has nothing here or the fetch failed (asked again next build).  Never
    raises."""
    definition = _coarse_definition(tile) if BAND.has_gdal else None
    if definition is None:
        return None
    path = _raster_path(tile, definition)
    if os.path.isfile(path + _NO_DATA_SUFFIX):
        return None
    if os.path.isfile(path):
        return CoarseFill(path, fine_vrt)
    try:
        return (CoarseFill(path, fine_vrt)
                if _fetch_raster(tile, definition, path) else None)
    except Exception as error:
        UI.vprint(1, "   WARNING: coarse bathymetry skipped:", str(error))
        with open(path + _RETRY_SUFFIX, "wb"):
            pass
        return None


def _fetch_raster(tile, definition: dict, path: str) -> bool:
    """Fetch the native-resolution raster; ``False`` for a durable "no
    data here".  A failure raises."""
    import O4_Airport_Elevation_Insets as INSETS

    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = "%s.part%d.tif" % (path, os.getpid())
    box = (tile.lon - OVERHANG_DEGREES, tile.lat - OVERHANG_DEGREES,
           tile.lon + 1 + OVERHANG_DEGREES, tile.lat + 1 + OVERHANG_DEGREES)
    try:
        with warp_failure_is_transient():
            answer = INSETS.fetch_inset(
                definition, box, float(definition["native_resolution_m"]),
                temporary)
        if answer is None:
            with open(path + _NO_DATA_SUFFIX, "wb"):
                pass
            outcome = False
        else:
            os.replace(temporary, path)
            outcome = True
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    if os.path.exists(path + _RETRY_SUFFIX):
        os.remove(path + _RETRY_SUFFIX)
    return outcome


def fill_state(tile) -> Optional[str]:
    """The masks key's view: a digest of the raster once fetched, PENDING
    after a failed fetch, else ``None`` (nothing the step used, so a tile
    the fill never reached keeps its key).  Disk only."""
    if str(getattr(tile, "masks_use_DEM_too", "False")) != "auto":
        return None
    definition = _coarse_definition(tile) if BAND.has_gdal else None
    if definition is None:
        return None
    path = _raster_path(tile, definition)
    if os.path.isfile(path):
        text = "%s:%d" % (os.path.basename(path), os.path.getsize(path))
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    if os.path.isfile(path + _RETRY_SUFFIX):
        return SOURCE_REVISION.PENDING
    return None


def fill_is_settled(tile) -> bool:
    """Whether the masks step would fetch nothing for the fill
    (``is_cached``'s question).  Disk only."""
    definition = _coarse_definition(tile) if BAND.has_gdal else None
    if definition is None:
        return True
    path = _raster_path(tile, definition)
    if os.path.isfile(path) or os.path.isfile(path + _NO_DATA_SUFFIX):
        return True
    if os.path.isfile(path + _RETRY_SUFFIX):
        return False
    # No cached coastline: the OSM admission answers for that download, and
    # nothing says this tile has a sea to fill.
    cached = FNAMES.osm_cached(tile.lat, tile.lon, "coastline")
    return not os.path.isfile(cached) or BAND._cached_coastline_is_empty(tile)


def _ramp(distance_m, width_m):
    r = numpy.clip(distance_m / width_m, 0.0, 1.0)
    return r * r * (3.0 - 2.0 * r)


def _measured_inland(inland_full, values):
    """The 6144 px inland-water pixels whose water body the source measures
    at or below sea level somewhere in the window (``values``: the source on
    the decimated grid).

    A lake or river above sea level reads as land (its surface elevation)
    and stays out: the source carries no depth for it.  A tidal lagoon is
    at sea level, so its channels read at or below zero; its whole body
    then takes the sea's depth alpha (intertidal flats read just above
    zero and stay shallow).  Bodies are connected on the decimated grid.
    """
    from scipy.ndimage import label

    size = values.shape[0]
    blocks = inland_full.reshape(size, _DECIMATION, size, _DECIMATION)
    inland = blocks.any(axis=(1, 3))
    (bodies, count) = label(inland, structure=numpy.ones((3, 3)))
    if not count:
        return None
    wet = numpy.unique(bodies[inland & (values > -32000.0) & (values <= 0.0)])
    wet = wet[wet > 0]
    if not wet.size:
        return None
    chosen = numpy.isin(bodies, wet)
    return inland_full & numpy.repeat(
        numpy.repeat(chosen, _DECIMATION, axis=0), _DECIMATION, axis=1)


def square_alpha(til_x, til_y, tile, fill: CoarseFill, sea_full,
                 inland_full=None):
    """The fill's 4096 px alpha for one mask square, zero off the water
    (``sea_full``: the 6144 px pre-mask's sea pixels; ``inland_full``: its
    inland-water pixels, of which only :func:`_measured_inland` ones count),
    or ``None`` when it adds nothing."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter

    size = 6144 // _DECIMATION
    values = BAND.read_band_window(
        til_x, til_y, tile.mask_zl, fill.coarse_path, size)
    if values is None:
        return None
    valid = values > -32000.0
    if not valid.any():
        return None
    (latitude, _) = GEO.gtile_to_wgs84(til_x, til_y, tile.mask_zl)
    pixel_m = GEO.webmercator_pixel_size(latitude, tile.mask_zl) * _DECIMATION
    sigma = max(SMOOTHING_SIGMA_M / pixel_m, 0.5)
    weight = gaussian_filter(valid.astype(numpy.float32), sigma)
    depth = gaussian_filter(
        numpy.where(valid, numpy.minimum(values, 0.0), 0.0), sigma
    ) / numpy.maximum(weight, 1e-3)
    water_full = sea_full
    if inland_full is not None and inland_full.any():
        measured = _measured_inland(inland_full, values)
        if measured is not None:
            water_full = sea_full | measured
    if not water_full[1024:5120, 1024:5120].any():
        return None
    alpha = 255.0 * BAND.shallow_water_opacity(tile) * BAND.depth_spline(
        depth, getattr(tile, "reef_visibility_depth", 25.0))
    if not valid.all():
        alpha *= _ramp(distance_transform_edt(valid) * pixel_m,
                       COVERAGE_FADE_M)
    if fill.fine_vrt:
        fine = BAND.read_band_window(
            til_x, til_y, tile.mask_zl, fill.fine_vrt, size, resample="max")
        if fine is not None and (fine > -32000.0).any():
            away = distance_transform_edt(fine <= -32000.0)
            alpha *= _ramp((away - _FINE_GUARD_PIXELS) * pixel_m,
                           FINE_JOIN_FEATHER_M)
    margin = 1024 // _DECIMATION
    cropped = numpy.clip(numpy.round(alpha[margin:-margin, margin:-margin]),
                         0, 255).astype(numpy.uint8)
    if not cropped.any():
        return None
    final = numpy.asarray(Image.fromarray(cropped).resize(
        (4096, 4096), Image.BILINEAR)).copy()
    final[~water_full[1024:5120, 1024:5120]] = 0
    return final if final.any() else None
