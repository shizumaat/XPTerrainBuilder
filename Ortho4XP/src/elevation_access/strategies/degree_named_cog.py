"""Cloud-Optimized GeoTIFFs named by their 1-degree cell coordinates.

The ``degree_named_cog`` access strategy (:class:`DegreeNamedCogStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import os

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.definitions import _coverage_bbox_intersects
from elevation_access.discovery import (
    HTTP_OUTCOME_ABSENT,
    HTTP_OUTCOME_OK,
    HTTP_OUTCOME_UNAVAILABLE,
    http_answer_outcome,
)
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "DEGREE_COG_PROBE_TIMEOUT_S",
    "DegreeNamedCogStrategy",
]


# =====================================================================
# Strategy 15: degree_named_cog (deterministic per-degree COG names)
# =====================================================================
#: Seconds one cell-existence HEAD probe may take.  A probe that runs out
#: of time is a TRANSIENT failure (it got no answer), so this bounds how
#: long a dead mirror costs per cell, never what gets recorded.
DEGREE_COG_PROBE_TIMEOUT_S = 30


@register_access_strategy("degree_named_cog")
class DegreeNamedCogStrategy:
    """Cloud-Optimized GeoTIFFs named by their 1-degree cell coordinates.

    The Copernicus GLO-30 mirror on AWS Open Data publishes one COG per
    1-degree cell with the cell's south-west corner encoded in the object
    name as hemisphere tokens (``N25``/``E051`` style) -- no discovery
    API, no index file: every cell's URL is computable.  Discovery
    enumerates the cells touching the requested box and keeps those whose
    object actually exists (ocean-only cells are simply absent from the
    bucket; one cheap HEAD request per cell separates the two, memoised
    for the process so neighbouring airports in the same cell never
    re-ask).  The fetch is the shared windowed ``/vsicurl/`` warp.

    Deliberately NOT eligible for whole-tile overlay fetches
    (``supports_wide_area = False``): the only shipped user is a global
    SURFACE model (buildings and canopy baked into the heights) whose
    building artifacts are corrected by the airport-scoped footprint
    masking pass -- a tile-wide use would spread uncorrected rooftop
    elevations across every city in the tile.
    """

    supports_wide_area = False

    # Process-lifetime memo of DEFINITIVE existence answers only (a 2xx,
    # or the 404/410 of :data:`HTTP_ABSENT_STATUSES`) keyed by URL.
    # Transient failures (timeouts, 5xx, 429) and host refusals (403,
    # 407) are NOT memoised: one network blip must not poison every
    # later airport of the run with a false "absent".
    _cell_exists_by_url = {}

    @staticmethod
    def degree_cell_tokens(cell_latitude, cell_longitude):
        """Hemisphere-coded name tokens of a 1-degree cell's SW corner.

        ``(25, 51) -> ("N25", "E051")``; ``(-14, -29) -> ("S14", "W029")``.
        Latitude is zero-padded to 2 digits, longitude to 3, matching the
        Copernicus DEM object-name grammar.
        """
        latitude_token = "%s%02d" % (
            "N" if cell_latitude >= 0 else "S",
            abs(cell_latitude),
        )
        longitude_token = "%s%03d" % (
            "E" if cell_longitude >= 0 else "W",
            abs(cell_longitude),
        )
        return latitude_token, longitude_token

    @staticmethod
    def degree_cells_of_bounding_box(bounding_box_wgs84):
        """The integer SW corners of every 1-degree cell a box touches.

        A box edge lying exactly on an integer degree does not pull in the
        cell beyond it (``ceil`` on the top/right edges).
        """
        import math

        (west, south, east, north) = bounding_box_wgs84
        return [
            (cell_latitude, cell_longitude)
            for cell_latitude in range(
                int(math.floor(south)), max(int(math.ceil(north)),
                                            int(math.floor(south)) + 1)
            )
            for cell_longitude in range(
                int(math.floor(west)), max(int(math.ceil(east)),
                                           int(math.floor(west)) + 1)
            )
        ]

    def _cell_url(self, definition, cell_latitude, cell_longitude):
        latitude_token, longitude_token = self.degree_cell_tokens(
            cell_latitude, cell_longitude
        )
        return str(definition.get("url_template", "")).format(
            latitude_token=latitude_token, longitude_token=longitude_token
        )

    def _url_exists(self, url):
        """Is this cell's object in the bucket?

        THE OUTCOME LAW (:func:`http_answer_outcome`, RULINGS
        2026-09-13b, issue #124): only a 404/410 -- the server looked and
        the object is not there -- may answer ``False``, the one answer
        the caller is allowed to record as a durable no-coverage.  A
        401/403/407/405/451/501 RAISES :class:`ProviderUnavailable` (the
        host refused to serve this client, which says nothing about the
        cell); a 429, a 5xx, an answer nobody recognises, and a probe
        that got NO answer at all RAISE :class:`TransientFetchError`
        (nothing recorded, asked again next run).
        """
        memo = DegreeNamedCogStrategy._cell_exists_by_url
        if url in memo:
            return memo[url]
        import requests

        try:
            response = requests.head(
                url, timeout=DEGREE_COG_PROBE_TIMEOUT_S
            )
        except Exception as error:
            # A probe that got NO HTTP ANSWER AT ALL says nothing about
            # whether the cell exists -- whatever the exception's WORDING
            # (issue #121 classified the message and fell through to a
            # durable absent for every message not on the fragment list;
            # #124: there is no message that makes "no answer" mean "not
            # there").  Never memoised: one blip must not poison every
            # later airport of the run with a false absent.
            raise TransientFetchError(
                "existence probe for %s died on the transport: %s"
                % (url, error)
            ) from error
        outcome = http_answer_outcome(response.status_code)
        if outcome == HTTP_OUTCOME_OK:
            memo[url] = True
            return True
        if outcome == HTTP_OUTCOME_ABSENT:
            memo[url] = False
            return False
        if outcome == HTTP_OUTCOME_UNAVAILABLE:
            raise ProviderUnavailable(
                "existence probe for %s was refused with status %s - the "
                "host would not serve this client, which says NOTHING "
                "about the cell: recorded unavailable, not no-coverage"
                % (url, response.status_code)
            )
        raise TransientFetchError(
            "existence probe for %s returned status %s - transient, NOT "
            "recorded as no-coverage" % (url, response.status_code)
        )

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        if not str(definition.get("url_template", "")).strip():
            return None
        sources = [
            {"source": "/vsicurl/" + url, "cell": [cell_latitude, cell_longitude]}
            for (cell_latitude, cell_longitude) in (
                self.degree_cells_of_bounding_box(bounding_box_wgs84)
            )
            for url in [
                self._cell_url(definition, cell_latitude, cell_longitude)
            ]
            if self._url_exists(url)
        ]
        return sources or None

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        if not has_gdal:
            return None
        sources = self.discover(definition, bounding_box_wgs84)
        if not sources:
            return None
        vsicurl_inputs = [entry["source"] for entry in sources]
        if not warp_vsicurl_sources_to_geotiff(
            vsicurl_inputs,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
        ):
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
            "source_urls": [
                entry["source"].replace("/vsicurl/", "", 1)
                for entry in sources
            ],
            "native_resolution_m": definition.get("native_resolution_m"),
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "datum_note": (
                "Elevations are in the source vertical datum; the source "
                "is treated as truth and is NOT shifted toward the base "
                "DEM."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "resolution_m": target_resolution_m,
        }
