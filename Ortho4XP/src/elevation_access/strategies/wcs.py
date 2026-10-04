"""The ``wcs`` access strategy (:class:`WcsStrategy`).

National lidar terrain models served over OGC Web Coverage Service.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import os

import O4_Geo_Utils as GEO
import O4_UI_Utils as UI

from elevation_access.base import TransientFetchError
from elevation_access.definitions import (
    _coverage_bbox_intersects,
    _parse_float,
)
from elevation_access.failures import (
    _warn_sign_in_needed_once,
    error_message_indicates_grid_configuration_failure,
    error_message_indicates_transient_network_failure,
)
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "WCS_REQUEST_TIMEOUT_SECONDS",
    "WcsStrategy",
]


# =====================================================================
# Strategy 3: wcs (OGC Web Coverage Service GetCoverage -> warp)
# =====================================================================


# GDAL's WCS driver defaults its curl TOTAL-transfer timeout to 30
# seconds (frmts/wcs/wcsdataset.cpp falls back to Timeout "30"), which a
# windowed GetCoverage for a large airport at meter-class resolution
# cannot honour: Heathrow's 1 m window from the Environment Agency
# service died mid-stream at 20 MB.  The driver-level open option is the
# ONLY override -- the driver always passes its own TIMEOUT to curl, so
# the GDAL_HTTP_TIMEOUT configuration option never applies to WCS reads.
WCS_REQUEST_TIMEOUT_SECONDS = 600


@register_access_strategy("wcs")
class WcsStrategy:
    """National lidar terrain models served over OGC Web Coverage Service.

    The European national programmes (England's Environment Agency
    composite, Norway's Kartverket national height model, Denmark's
    DHM, ...) publish meter-class bare-earth models as WCS endpoints
    rather than catalogs of Cloud-Optimized GeoTIFFs.  GDAL's WCS driver
    does the protocol work -- version negotiation from 1.0.0 through
    2.0.1, DescribeCoverage, and windowed GetCoverage requests -- so the
    fetch core is the same warp every other strategy uses, reading only
    the airport window from the national coverage.

    Unlike the catalog strategies there is no per-item discovery API:
    one definition names ONE national coverage, and the post-warp
    validity check in :func:`_geotiff_has_valid_data` is what turns
    inside-the-box-but-outside-the-data airports into cached
    no-coverage negatives.
    """

    # Windowed GetCoverage reader: eligible for whole-tile overlay fetches.
    supports_wide_area = True

    def dataset_name(self, definition, api_key=None):
        """The GDAL WCS driver dataset name for the definition.

        A ``{api_key}`` placeholder in the service URL (credential-gated
        services like Denmark's Datafordeler) is substituted when a key
        is supplied and left literal otherwise -- discovery results and
        provenance records use the literal form so the secret never
        lands in a log or a sidecar file.
        """
        service_url = definition["wcs_service_url"]
        if api_key is not None:
            service_url = service_url.replace("{api_key}", api_key)
        separator = "&" if "?" in service_url else "?"
        return (
            "WCS:"
            + service_url
            + separator
            + "version="
            + str(definition.get("wcs_version", "2.0.1"))
            + "&coverage="
            + definition["wcs_coverage"]
        )

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        return [{"dataset": self.dataset_name(definition)}]

    def _window_size(
        self, definition, bounding_box_wgs84, target_resolution_m
    ):
        """Cell count to ask the server for, at the effective posting.

        Same arithmetic as :class:`WcsKvpStrategy`: never finer than the
        source publishes and never finer than the inset target, because
        the warp downsamples to the target anyway and a finer request only
        inflates the server render and the transfer.
        """
        (west, south, east, north) = bounding_box_wgs84
        centre_latitude = (south + north) / 2.0
        pixel_m = _parse_float(definition.get("native_resolution_m"), 0.0)
        target = _parse_float(target_resolution_m, 0.0) or 0.0
        if not pixel_m or pixel_m <= 0.0:
            pixel_m = target or 1.0
        if target and target > pixel_m:
            pixel_m = target
        width = int(round(
            (east - west) * GEO.lon_to_m(centre_latitude) / pixel_m
        ))
        height = int(round((north - south) * GEO.lat_to_m / pixel_m))
        return (max(1, width), max(1, height))

    def _materialize_window(
        self,
        definition,
        dataset,
        bounding_box_wgs84,
        target_resolution_m,
        scratch_path,
    ):
        """Read the airport window with an EXPLICIT size into a scratch file.

        Returns True when the scratch GeoTIFF is on disk, False when the
        server or the driver refused it (the caller then falls back to the
        driver's own windowing, today's behaviour).  Raises
        :class:`TransientFetchError` for a network-shaped failure, exactly
        like every other fetch path, so an outage never becomes a durable
        no-coverage negative.
        """
        (west, south, east, north) = bounding_box_wgs84
        (width, height) = self._window_size(
            definition, bounding_box_wgs84, target_resolution_m
        )
        os.makedirs(os.path.dirname(scratch_path) or ".", exist_ok=True)
        # A size that happens to equal the source window is a 1:1 read
        # again -- the one shape the request cannot carry a size in.  One
        # extra cell per axis can never be 1:1 and never asks the server
        # to downsample, so the retry is the whole remedy.
        for extra_cells in (0, 1):
            try:
                result = gdal.Translate(
                    scratch_path,
                    dataset,
                    projWin=[west, north, east, south],
                    projWinSRS="EPSG:4326",
                    width=width + extra_cells,
                    height=height + extra_cells,
                    format="GTiff",
                    outputType=gdal.GDT_Float32,
                    resampleAlg="bilinear",
                    creationOptions=[
                        "COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES",
                    ],
                )
            except Exception as error:
                if UI.red_flag:
                    raise TransientFetchError(
                        "WCS window read stopped with the build"
                    ) from error
                if error_message_indicates_transient_network_failure(error):
                    raise TransientFetchError(
                        "WCS window read died on a network timeout or "
                        "outage: " + str(error)
                    ) from error
                if (
                    extra_cells == 0
                    and error_message_indicates_grid_configuration_failure(
                        error
                    )
                ):
                    continue
                UI.vprint(
                    1,
                    "   WARNING: WCS window read failed:",
                    str(error),
                )
                return False
            if result is None:
                return False
            result = None  # flush to disk
            return os.path.isfile(scratch_path)
        return False

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        import O4_Authenticated_Sessions as SESSIONS

        if not has_gdal:
            return None
        api_key = None
        if "{api_key}" in str(definition.get("wcs_service_url", "")):
            try:
                api_key = SESSIONS.ensure_api_key(definition)
            except SESSIONS.LoginError as error:
                _warn_sign_in_needed_once(definition, error)
                return None
        dataset_name = self.dataset_name(definition, api_key)
        # Open with an explicit request timeout: the driver's own 30 s
        # default (see WCS_REQUEST_TIMEOUT_SECONDS above) kills large
        # windowed GetCoverage responses mid-stream.  The option also
        # covers the GetCapabilities/DescribeCoverage handshake and is
        # folded into the driver's cached service description.
        try:
            wcs_dataset = gdal.OpenEx(
                dataset_name,
                gdal.OF_RASTER,
                open_options=[
                    "TIMEOUT=%d" % WCS_REQUEST_TIMEOUT_SECONDS
                ],
            )
        except Exception as error:
            if error_message_indicates_transient_network_failure(error):
                raise TransientFetchError(
                    "WCS coverage open died on a network timeout or "
                    "outage: " + str(error)
                ) from error
            UI.vprint(
                1,
                "   WARNING: could not open WCS coverage:",
                str(error),
            )
            return None
        if wcs_dataset is None:
            return None
        value_floor_m = float(definition.get("value_floor_m", -600.0))
        # ASK FOR A SIZE, never let the server guess one (2026-08-24).
        # Handing the open WCS dataset straight to the warp makes GDAL
        # read the window 1:1, and a 1:1 read carries no size in the
        # request: the driver states only SUBSET bounds and then refuses
        # the answer if the server's own arithmetic returns a different
        # cell count.  A SCALED read states the size it wants (SCALESIZE
        # in WCS 2.0, WIDTH/HEIGHT in 1.x) and the server honours it
        # exactly -- verified live against servicios.idee.es, where the
        # 1:1 form fails for every airport-sized window (see
        # _GRID_CONFIGURATION_ERROR_FRAGMENTS).  The scratch window is
        # materialised at the fetch's effective posting and the shared
        # warp core then does the reprojection and resampling as before.
        scratch_path = destination_path + ".getcoverage.tif"
        warped = False
        if self._materialize_window(
            definition,
            wcs_dataset,
            bounding_box_wgs84,
            target_resolution_m,
            scratch_path,
        ):
            try:
                warped = warp_vsicurl_sources_to_geotiff(
                    [scratch_path],
                    bounding_box_wgs84,
                    target_resolution_m,
                    destination_path,
                    value_floor_m=value_floor_m,
                    vertical_unit=_raster_vertical_unit(definition),
                    provider_code=definition.get("code"),
                )
            finally:
                try:
                    os.remove(scratch_path)
                except OSError:
                    pass
        else:
            # Last resort: the driver's own windowing, i.e. the behaviour
            # every already-cached inset was fetched with.
            warped = warp_vsicurl_sources_to_geotiff(
                [wcs_dataset],
                bounding_box_wgs84,
                target_resolution_m,
                destination_path,
                value_floor_m=value_floor_m,
                vertical_unit=_raster_vertical_unit(definition),
                provider_code=definition.get("code"),
            )
        if not warped:
            return None
        if not _geotiff_has_valid_data(destination_path):
            try:
                os.remove(destination_path)
            except OSError:
                pass
            return None
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            # The literal form: any {api_key} placeholder stays a
            # placeholder so the secret never reaches the provenance
            # sidecar.
            "source_urls": [self.dataset_name(definition)],
            "wcs_coverage": definition.get("wcs_coverage"),
            "native_resolution_m": definition.get("native_resolution_m"),
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "datum_note": (
                "Elevations are in the source vertical datum; lidar is "
                "treated as truth and is NOT shifted toward the base DEM."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "resolution_m": target_resolution_m,
        }
