"""From remote sources to one GeoTIFF: the warp every raster strategy ends in.

:func:`warp_vsicurl_sources_to_geotiff` mosaics a list of sources over
the requested box at the target resolution; the helpers beside it say
which sources contributed and whether the result holds any data.
"""

import numpy
import os

import O4_Geo_Utils as GEO
import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.failures import (
    error_message_indicates_grid_configuration_failure,
    error_message_indicates_transient_network_failure,
)
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.vertical_units import (
    VERTICAL_UNIT_STAMP_APPLIED,
    VERTICAL_UNIT_STAMP_DECLARED,
    VERTICAL_UNIT_STAMP_SOURCE,
    VERTICAL_UNIT_TO_M,
    resolve_warp_vertical_unit,
)

__all__ = [
    "_SOURCE_CONTRIBUTION_PROBE_SAMPLES",
    "_geotiff_has_valid_data",
    "_source_contribution_entry",
    "_source_holds_data_over_bbox",
    "inset_valid_fraction",
    "warp_vsicurl_sources_to_geotiff",
]


# =====================================================================
# Shared fetch helpers (strategy-agnostic; reused by tnm_cog and stac)
# =====================================================================
#: GDAL archive handlers whose member paths read a LOCAL archive unless a
#: curl handler is chained inside them.
_LOCAL_ARCHIVE_HANDLERS = ("/vsizip/", "/vsi7z/")


def _vsicurl_allowed_extensions(warp_inputs):
    """Extension allowlist for the warp's remote reads, or ``None``.

    ``CPL_VSIL_CURL_ALLOWED_EXTENSIONS`` makes any curl-backed open whose
    URL does not end in a listed extension fail instantly WITHOUT a
    network request — a second fence (behind ``GDAL_DISABLE_READDIR_ON_
    OPEN``) against per-open sidecar-metadata probing.  It is scoped to
    the warp call rather than set globally because the template strategy
    legitimately opens remote zips (``/vsizip//vsicurl/…zip``) outside
    the warp, which a global ``.tif`` list would break.

    The list is DERIVED from the inputs (plus ``.vrt``'s referenced
    ``.tif``/``.tiff``) instead of hard-coded, so a provider with an
    unusual raster extension can never be locked out by its own guard.
    GDAL strips the query string before matching, so presigned URLs
    (``….tif?X-Amz-…``) pass.  Returns ``None`` — option omitted — when
    no input is curl-backed, when a curl input has no usable extension,
    or when a chained virtual path (``/vsizip//vsicurl/…``) makes the
    underlying URL's extension differ from the path's.
    """
    extensions = {".tif", ".tiff", ".vrt"}
    saw_curl_input = False
    for source in warp_inputs:
        if not isinstance(source, str) or not source.startswith("/vsi"):
            # Local scratch files and already-open datasets (the wcs
            # strategy hands the warp a Dataset) never go through curl.
            continue
        if source.startswith(_LOCAL_ARCHIVE_HANDLERS) and not any(
                remote in source for remote in ("/vsicurl/", "/vsis3/")):
            # A member of a LOCAL scratch archive (tnm_cog's downloaded
            # 1/9 arc-second zips, #157) never goes through curl either.
            continue
        if not source.startswith(("/vsicurl/", "/vsis3/")):
            return None
        saw_curl_input = True
        basename = source.split("?", 1)[0].rsplit("/", 1)[-1]
        if "." not in basename:
            return None
        extensions.add("." + basename.rsplit(".", 1)[-1].lower())
    if not saw_curl_input:
        return None
    return ",".join(sorted(extensions))


def warp_vsicurl_sources_to_geotiff(
    vsicurl_inputs,
    bounding_box_wgs84,
    target_resolution_m,
    destination_path,
    source_srs=None,
    source_nodata=None,
    value_floor_m=-600.0,
    gdal_configuration_options=None,
    vertical_unit=None,
    provider_code=None,
    failure_reasons=None,
):
    """Mosaic + warp remote rasters to an EPSG:4326 float32 GeoTIFF window.

    The genuinely shared core of every Cloud-Optimized GeoTIFF strategy:
    ``gdal.Warp`` reads only the requested window from each ``/vsicurl/``
    source (the full source tiles, hundreds of megabytes each, are never
    downloaded), mosaics them (later inputs win on overlap), reprojects to
    EPSG:4326 and resamples to ``target_resolution_m`` at the bounding
    box's centre latitude.  Returns ``True`` on success, ``False`` on a
    durable GDAL failure (the caller records no-coverage), and raises
    :class:`TransientFetchError` when the failure is network-shaped (a
    curl timeout, a connection failure, a 5xx) so callers can skip the
    provider WITHOUT caching a no-coverage negative.  A no-op returning
    ``False`` when GDAL is unavailable.

    ``value_floor_m`` is the lowest value the post-warp sanitizer treats as
    genuine data (spec section 2.3): terrestrial elevation providers keep
    the default -600 m, while a bathymetry provider passes its own
    ``value_floor_m`` (CUDEM Hawaii uses -11100 m) so measured seabed
    depths are not mistaken for leaked fill values and discarded.

    ``gdal_configuration_options`` are applied around the warp only (via
    ``gdal.config_options``): credential-gated sources use it to pass
    e.g. ``GDAL_HTTP_USERPWD`` without leaking it into global state.

    ``vertical_unit`` (the provider's ``.elv`` key, ``m|ft|ftUS``; spec
    us-holder-providers §2 -- THE ONE SITE the key is applied): ``None``
    (no key) leaves this function a strict no-op on the cells and the
    file.  With a key, every input's CRS is checked first
    (:func:`resolve_warp_vertical_unit` -- a contradiction raises
    :class:`ProviderUnavailable` before any byte is warped), then the
    post-warp array pass multiplies the VALID cells by the unit's metres
    factor BEFORE the garbage test, so the ``value_floor_m`` / ceiling
    is judged in metres and the -32768 nodata is untouched (bilinear
    resampling is linear, so scaling after the warp equals scaling
    before).  The raster is stamped (``O4_VERTICAL_UNIT_*`` metadata,
    :func:`raster_vertical_unit_stamp`) and :func:`fetch_inset` lifts the
    stamp into the provenance as ``vertical_unit_source`` /
    ``vertical_unit_applied``.

    ``failure_reasons`` (a list, optional): on a ``False`` return the
    reason is appended to it, so a caller that knows its inputs were
    LISTED products can record the warp failure as ``unavailable`` with
    its reason instead of a no-coverage answer (#157).
    """
    if not has_gdal:
        return False
    (west, south, east, north) = bounding_box_wgs84
    centre_latitude = (south + north) / 2.0
    metres_per_degree_latitude = GEO.lat_to_m
    metres_per_degree_longitude = GEO.lon_to_m(centre_latitude)
    x_resolution_deg = target_resolution_m / metres_per_degree_longitude
    y_resolution_deg = target_resolution_m / metres_per_degree_latitude
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)

    def _abort_when_red_flagged(_fraction, _message, _data):
        # gdal.Warp polls this between work chunks; returning 0 aborts.
        # A Stop must not wait out a many-minute remote warp (and the
        # abort is raised as TRANSIENT below, so no durable no-coverage
        # negative is recorded for a user-cancelled fetch).
        return 0 if UI.red_flag else 1

    warp_options = gdal.WarpOptions(
        callback=_abort_when_red_flagged,
        format="GTiff",
        outputType=gdal.GDT_Float32,
        # Some sources (plain XYZ grids) carry no CRS of their own.
        srcSRS=source_srs,
        # ... and some carry an UNDECLARED fill value (Ireland's -99).
        srcNodata=source_nodata,
        dstSRS="EPSG:4326",
        # Heights must pass through UNCHANGED in the source vertical
        # datum (the provenance datum_note promises exactly that).
        # Without -novshift, GDAL applies a geoid shift whenever a
        # source declares a compound CRS -- Lantmateriet's COGs
        # (EPSG:5845, SWEREF99 TM + RH2000 height) came out 23-36 m
        # too high that way, ellipsoidal instead of orthometric.
        options=["-novshift"],
        outputBounds=(west, south, east, north),
        xRes=x_resolution_deg,
        yRes=y_resolution_deg,
        resampleAlg="bilinear",
        dstNodata=-32768.0,
        # TILED so the grid decision's windowed probe reads decode a few
        # 256x256 blocks instead of whole DEFLATE strips of a
        # native-resolution inset.
        creationOptions=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"],
    )
    configuration_options = dict(gdal_configuration_options or {})
    allowed_extensions = _vsicurl_allowed_extensions(vsicurl_inputs)
    if (
        allowed_extensions
        and "CPL_VSIL_CURL_ALLOWED_EXTENSIONS" not in configuration_options
        and os.environ.get("CPL_VSIL_CURL_ALLOWED_EXTENSIONS") is None
        and gdal.GetConfigOption("CPL_VSIL_CURL_ALLOWED_EXTENSIONS") is None
    ):
        configuration_options["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = (
            allowed_extensions
        )
    vertical_factor = None
    vertical_unit_source = None
    if vertical_unit is not None:
        if vertical_unit not in VERTICAL_UNIT_TO_M:
            raise ProviderUnavailable(
                "%s: .elv vertical_unit=%s is not one of %s"
                % (provider_code or "elevation provider", vertical_unit,
                   "|".join(sorted(VERTICAL_UNIT_TO_M))))
        # The refusal is judged BEFORE the warp: a contradicted unit must
        # never reach a raster, not even a scratch one.
        if configuration_options:
            with gdal.config_options(configuration_options):
                (vertical_factor, vertical_unit_source) = (
                    resolve_warp_vertical_unit(
                        vsicurl_inputs, vertical_unit, source_srs,
                        provider_code))
        else:
            (vertical_factor, vertical_unit_source) = (
                resolve_warp_vertical_unit(
                    vsicurl_inputs, vertical_unit, source_srs,
                    provider_code))
    try:
        if configuration_options:
            with gdal.config_options(configuration_options):
                dataset = gdal.Warp(
                    destination_path,
                    list(vsicurl_inputs),
                    options=warp_options,
                )
        else:
            dataset = gdal.Warp(
                destination_path, list(vsicurl_inputs), options=warp_options
            )
    except Exception as error:
        if UI.red_flag:
            raise TransientFetchError(
                "elevation warp stopped with the build"
            ) from error
        if error_message_indicates_transient_network_failure(error):
            raise TransientFetchError(
                "elevation warp died on a network timeout or outage: "
                + str(error)
            ) from error
        if error_message_indicates_grid_configuration_failure(error):
            # The server's grid disagreed with its own DescribeCoverage;
            # that is a protocol answer, not a coverage answer, so it must
            # never become a durable no-coverage negative.
            raise TransientFetchError(
                "elevation warp refused the server's returned grid: "
                + str(error)
            ) from error
        UI.vprint(1, "   WARNING: elevation warp failed:", str(error))
        if failure_reasons is not None:
            failure_reasons.append(str(error))
        return False
    if dataset is None:
        if UI.red_flag:
            raise TransientFetchError("elevation warp stopped with the build")
        if failure_reasons is not None:
            failure_reasons.append("the warp returned no dataset")
        return False
    dataset = None  # flush to disk before reopening
    # Sentinel sanitization: sources with UNDECLARED nodata leak their
    # fill values straight through the warp as "valid elevation" (the
    # Dutch national service fills with float-max, some Irish campaign
    # tiles with -9999).  Terrestrial elevations live within
    # -430..+8850 m; anything above +12000 or below ``value_floor_m``, or
    # not finite, is garbage and becomes nodata here so it can never reach
    # a bake.  The floor is per-call: terrestrial providers keep the -600 m
    # default (small negative fills like Ireland's -99 are PLAUSIBLE land
    # heights and need the per-provider source_nodata key instead), while
    # bathymetry providers lower it (CUDEM Hawaii to -11100 m) so real
    # seabed depths survive.  Done on a fresh update handle after the warp
    # result is flushed.
    try:
        dataset = gdal.Open(destination_path, gdal.GA_Update)
        band = dataset.GetRasterBand(1)
        values = band.ReadAsArray()
        if values is not None:
            rewrite = False
            if vertical_factor is not None and vertical_factor != 1.0:
                # THE VERTICAL-UNIT SITE (spec §2): valid cells to metres
                # BEFORE the garbage test, so the ceiling below is judged
                # in metres (a feet raster used to lose every cell above
                # 12,000 ft-as-m) and the nodata cells stay -32768.
                valid = numpy.isfinite(values) & (values != -32768.0)
                values[valid] = (
                    values[valid].astype(numpy.float64) * vertical_factor
                ).astype(values.dtype)
                rewrite = True
            garbage = (
                ~numpy.isfinite(values)
                | (values > 12000.0)
                | (values < value_floor_m)
            )
            if garbage.any():
                values[garbage] = -32768.0
                rewrite = True
            if rewrite:
                band.WriteArray(values)
                band.FlushCache()
        if vertical_factor is not None:
            dataset.SetMetadataItem(VERTICAL_UNIT_STAMP_DECLARED,
                                    vertical_unit)
            dataset.SetMetadataItem(VERTICAL_UNIT_STAMP_SOURCE,
                                    vertical_unit_source)
            dataset.SetMetadataItem(VERTICAL_UNIT_STAMP_APPLIED, "m")
        dataset = None
    except Exception as error:
        if vertical_factor is not None:
            # A raster whose unit was NOT applied must never survive as a
            # metres inset (spec §7 STOP): it goes, and the provider is
            # unavailable this run -- the ladder climbs.
            dataset = None
            try:
                os.remove(destination_path)
            except OSError:
                pass
            raise ProviderUnavailable(
                "%s: the vertical_unit=%s pass failed (%s) - the raster "
                "was removed, never baked in source units"
                % (provider_code or "elevation provider", vertical_unit,
                   error)) from error
        UI.vprint(
            1, "   WARNING: sentinel sanitization skipped:", str(error)
        )
    return True


# ---------------------------------------------------------------------
# Border-aware assembly (round 13, docs/specs/round13-border-aware-inset-
# fetch-spec.md) -- the pieces a multi-project mosaic needs
# ---------------------------------------------------------------------
#: A source's contribution is judged on a decimated grid over the box
#: (~65 k samples): the question is only "did this project hold ANY data
#: HERE", and a Cloud-Optimized GeoTIFF answers it from an overview
#: instead of a second full-window read.
_SOURCE_CONTRIBUTION_PROBE_SAMPLES = 256


def _source_holds_data_over_bbox(
    warp_input, bounding_box_wgs84, source_nodata=None,
    samples=_SOURCE_CONTRIBUTION_PROBE_SAMPLES,
):
    """True when one source holds ANY valid pixel over the bounding box.

    The honest instrument behind the record's ``sources_used`` /
    ``sources_empty_over_bbox`` split (R13-3): a source's EXTENT covers
    KMCI from both states, its DATA does not, and extents are the metric
    that produced a 100 % nodata inset in the first place.  Undecidable
    answers (no GDAL, a read that raises) read as ``True`` -- a probe may
    never INVENT an empty source and write a contributor out of the
    record.
    """
    if not has_gdal:
        return True
    (west, south, east, north) = bounding_box_wgs84
    try:
        probe = gdal.Warp(
            "",
            [warp_input],
            options=gdal.WarpOptions(
                format="MEM",
                outputType=gdal.GDT_Float32,
                dstSRS="EPSG:4326",
                options=["-novshift"],
                srcNodata=source_nodata,
                outputBounds=(west, south, east, north),
                width=samples,
                height=samples,
                resampleAlg="near",
                dstNodata=-32768.0,
            ),
        )
        if probe is None:
            return True
        values = probe.GetRasterBand(1).ReadAsArray()
        probe = None
    except Exception as error:
        UI.vprint(2, "   inset source probe skipped:", str(error))
        return True
    if values is None:
        return True
    return bool(numpy.any((values != -32768.0) & numpy.isfinite(values)))


def _source_contribution_entry(source):
    """One source's line in the record (R13-3): who it was, when it was
    published, and the id that finds it again at the provider."""
    return {
        "title": source.get("title"),
        "publication_date": source.get("publication_date"),
        "source_id": source.get("source_id"),
    }


def _geotiff_has_valid_data(geotiff_path):
    """Does the raster contain at least one non-nodata sample?

    A Web Coverage Service window requested inside the definition's
    coverage_bbox but outside the national data extent (a Welsh airport
    against the England-only composite, say) warps successfully to an
    all-nodata raster; treating that as a fetched inset would bake a
    nodata hole into the airport.  Callers delete the file and record
    no-coverage instead.
    """
    if not has_gdal:
        return False
    try:
        dataset = gdal.Open(geotiff_path)
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        values = band.ReadAsArray()
    except Exception:
        return False
    if values is None:
        return False
    if nodata is None:
        return True
    return bool((values != nodata).any())


# The fraction is estimated from a DECIMATED read (GDAL nearest sampling
# on to at most this many samples per axis, ~262 k samples): reading
# KMCI's raster whole is 336 MB for a single ratio, and the sampling
# error at the 5 % gate is far below the gate.
_INSET_VALID_SAMPLES_PER_AXIS = 512


#: ``{(path, mtime, size): fraction}`` -- the measurement is stable for
#: the life of a file and is asked for once per consumer per build.
_inset_valid_fraction_cache = {}


def inset_valid_fraction(inset_path):
    """Fraction of an inset raster's pixels that are NOT nodata.

    ``1.0`` when the file declares no nodata value (every pixel is data
    by definition) and when the raster cannot be read at all -- an
    unreadable file is a different failure with its own handling, and
    this metric must never invent a reason to drop an inset.
    """
    try:
        stat = os.stat(inset_path)
        key = (inset_path, stat.st_mtime, stat.st_size)
    except OSError:                                      # pragma: no cover
        return 1.0
    if key in _inset_valid_fraction_cache:
        return _inset_valid_fraction_cache[key]
    fraction = 1.0
    if has_gdal:
        try:
            dataset = gdal.Open(inset_path)
            band = dataset.GetRasterBand(1)
            nodata = band.GetNoDataValue()
            if nodata is not None:
                values = band.ReadAsArray(
                    buf_xsize=min(_INSET_VALID_SAMPLES_PER_AXIS,
                                  dataset.RasterXSize),
                    buf_ysize=min(_INSET_VALID_SAMPLES_PER_AXIS,
                                  dataset.RasterYSize),
                )
                if values is not None and values.size:
                    valid = (values != nodata) & numpy.isfinite(values)
                    fraction = float(valid.mean())
        except Exception:                                # pragma: no cover
            fraction = 1.0
    _inset_valid_fraction_cache[key] = fraction
    return fraction
