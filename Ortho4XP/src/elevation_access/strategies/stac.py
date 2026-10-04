"""The ``stac`` access strategy (:class:`StacCloudOptimizedGeoTiffStrategy`).

Fetch lidar elevation via a STAC API search + Cloud-Optimized GeoTIFF.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime

import O4_UI_Utils as UI

from elevation_access.base import TransientFetchError
from elevation_access.failures import _warn_sign_in_needed_once
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.stac_assets import (
    _select_stac_dtm_assets,
    _stac_asset_href_to_vsicurl,
)
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import warp_vsicurl_sources_to_geotiff

__all__ = [
    "StacCloudOptimizedGeoTiffStrategy",
]


# =====================================================================
# Strategy 2: stac (SpatioTemporal Asset Catalog search -> COG -> warp)
# =====================================================================
# The extensibility proof (spec Phase C2): a whole new provider family --
# a STAC API search endpoint serving Cloud-Optimized GeoTIFF assets --
# plugs into the SAME orchestration (discovery loop, cache, index,
# provenance, composite assembly, bake, and the Phase C1 grid decision)
# with only this one class + one Providers/Elevation/*.elv definition,
# reusing warp_vsicurl_sources_to_geotiff for the fetch core.  Shipped
# with HRDEM.elv (Natural Resources Canada high-resolution lidar).


@register_access_strategy("stac")
class StacCloudOptimizedGeoTiffStrategy:
    """Fetch lidar elevation via a STAC API search + Cloud-Optimized GeoTIFF.

    Discovery POSTs (falling back to GET) a bounding-box + collections
    query to the STAC ``/search`` endpoint named by the definition's
    ``discovery_url_template`` and returns the intersecting items.  Fetch
    selects the highest-resolution Digital Terrain Model asset of each
    item, mosaics their Cloud-Optimized GeoTIFFs through GDAL's virtual
    file system (window reads only) and warps to EPSG:4326 at the target
    resolution -- reusing warp_vsicurl_sources_to_geotiff, exactly like
    tnm_cog, with zero change to the orchestration around it.
    """

    # Windowed /vsicurl reader: eligible for whole-tile overlay fetches.
    supports_wide_area = True

    def _search_url_and_body(self, definition, bounding_box_wgs84):
        (west, south, east, north) = bounding_box_wgs84
        template = definition.get("discovery_url_template", "")
        # The endpoint may be a bare .../search URL or one already carrying
        # ?collections=...; keep any query the definition supplied.
        url = template
        collections = [
            token.strip()
            for token in str(definition.get("collections", "")).split(",")
            if token.strip()
        ]
        body = {
            "bbox": [west, south, east, north],
            "limit": int(float(definition.get("search_limit", 50))),
        }
        if collections:
            body["collections"] = collections
        return (url, body, collections, (west, south, east, north))

    # Hard ceiling on rel=next pages followed per search.  At the default
    # page limit of 50 items this allows 1000 items -- an order of
    # magnitude above the largest airport box (LSGG's ~2 km margin box
    # spans ~40-50 of SWISSALTI3D's 1 km-square items) while still
    # bounding a server whose next links never terminate.
    _SEARCH_MAX_PAGES = 20

    def discover(self, definition, bounding_box_wgs84):
        import requests

        (url, body, collections, bbox) = self._search_url_and_body(
            definition, bounding_box_wgs84
        )
        if not url:
            return None
        payload = None
        try:
            response = requests.post(url, json=body, timeout=30)
            if response.status_code == 200:
                payload = response.json()
        except Exception as error:
            UI.vprint(
                1, "   WARNING: STAC POST search failed:", str(error)
            )
        if payload is None:
            # Fall back to a GET query-string search (some STAC servers).
            (west, south, east, north) = bbox
            get_url = url + (
                ("&" if "?" in url else "?")
                + "bbox="
                + ",".join(repr(value) for value in (west, south, east, north))
            )
            if collections:
                get_url = get_url + "&collections=" + ",".join(collections)
            # A failed SEARCH says nothing about coverage. Recording it
            # as a durable negative poisoned airports permanently when a
            # rate-limited burst hit the API (observed live: swisstopo
            # answered LSGG then throttled LSGL, which cached
            # "no-coverage" beside a neighbour's "ok" from the same
            # collection). Only an EMPTY RESULT is durable; every
            # transport/HTTP failure raises transient so the next run
            # retries.
            try:
                response = requests.get(get_url, timeout=30)
                if response.status_code != 200:
                    UI.vprint(
                        1,
                        "   WARNING: STAC GET search returned status",
                        response.status_code,
                    )
                    raise TransientFetchError(
                        "STAC search returned status %d"
                        % response.status_code)
                payload = response.json()
            except TransientFetchError:
                raise
            except Exception as error:
                UI.vprint(
                    1, "   WARNING: STAC GET search failed:", str(error)
                )
                raise TransientFetchError(
                    "STAC search failed: %s" % error)
        items = self._parse_search_payload(payload)
        if items is None:
            return None
        return self._follow_pagination(
            requests, definition, url, body, payload, items
        )

    def _follow_pagination(
        self, requests, definition, url, body, payload, items
    ):
        """Accumulate every page of a STAC search via its rel=next links.

        One page of SWISSALTI3D covers 50 km-square items; a large airport
        box holds more, and stopping at page one silently truncated the
        COG set (an inset with holes recorded as "ok" -- worse than no
        inset at all).  A next-page request that FAILS raises
        :class:`TransientFetchError` for the same reason the first-page
        failure does: a partial answer must never become a durable record,
        neither "ok" nor no-coverage.
        """
        pages_fetched = 1
        seen_ids = {
            item.get("id") for item in items if item.get("id")
        }
        next_link = self._next_search_link(payload)
        while next_link is not None and pages_fetched < self._SEARCH_MAX_PAGES:
            payload = self._request_next_page(requests, next_link, url, body)
            pages_fetched += 1
            page_items = self._parse_search_payload(payload)
            if not page_items:
                break
            for item in page_items:
                item_id = item.get("id")
                if item_id and item_id in seen_ids:
                    continue
                if item_id:
                    seen_ids.add(item_id)
                items.append(item)
            next_link = self._next_search_link(payload)
        if next_link is not None:
            # No silent caps: say what was left behind.
            UI.vprint(
                1,
                "   WARNING: STAC search for provider",
                definition.get("code"),
                "still had a next page after",
                pages_fetched,
                "pages - coverage of this window may be incomplete.",
            )
        return items or None

    @staticmethod
    def _next_search_link(payload):
        """The rel=next link object of a search response, if any."""
        if not isinstance(payload, dict):
            return None
        for link in payload.get("links") or []:
            if isinstance(link, dict) and link.get("rel") == "next":
                return link
        return None

    @staticmethod
    def _request_next_page(requests, next_link, search_url, body):
        """Fetch one continuation page described by a rel=next link.

        Two conventions in the wild: a plain GET href carrying the token
        in its query string, and the STAC API POST convention (used by
        data.geo.admin.ch) where the link names ``method: POST`` and a
        ``body`` holding the continuation token, merged over the original
        search body (``merge: true``; a link body without ``merge`` still
        starts from the original body so bbox and collections survive
        servers that send only the token).  Any failure raises
        :class:`TransientFetchError` -- a lost page is a transient
        outage, never a smaller coverage answer.
        """
        href = next_link.get("href") or search_url
        method = str(next_link.get("method", "GET")).upper()
        try:
            if method == "POST" or next_link.get("body") is not None:
                next_body = dict(body)
                link_body = next_link.get("body")
                if isinstance(link_body, dict):
                    next_body.update(link_body)
                response = requests.post(href, json=next_body, timeout=30)
            else:
                response = requests.get(href, timeout=30)
            if response.status_code != 200:
                raise TransientFetchError(
                    "STAC search pagination returned status %d"
                    % response.status_code
                )
            return response.json()
        except TransientFetchError:
            raise
        except Exception as error:
            UI.vprint(
                1, "   WARNING: STAC search pagination failed:", str(error)
            )
            raise TransientFetchError(
                "STAC search pagination failed: %s" % error
            )

    @staticmethod
    def _parse_search_payload(payload):
        """Extract the item list from a STAC ItemCollection response."""
        if not isinstance(payload, dict):
            return None
        features = payload.get("features")
        if features is None and "items" in payload:
            features = payload.get("items")
        if not features:
            return None
        return list(features)

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
        # Credential-gated pixels (Sweden's Geotorget: the STAC search
        # is anonymous but every Cloud-Optimized GeoTIFF read needs the
        # account as HTTP Basic authentication, carried to GDAL through
        # a warp-scoped configuration option).
        gdal_configuration_options = None
        if (
            SESSIONS.credential_kind(definition)
            == SESSIONS.CREDENTIAL_KIND_HTTP_BASIC
            and definition.get("session_name")
        ):
            try:
                session = SESSIONS.ensure_session(definition)
            except SESSIONS.LoginError as error:
                _warn_sign_in_needed_once(definition, error)
                return None
            gdal_configuration_options = {
                "GDAL_HTTP_USERPWD": "%s:%s" % tuple(session.auth)
            }
        items = self.discover(definition, bounding_box_wgs84)
        if not items:
            return None
        prefer_asset_keys = [
            token.strip()
            for token in str(
                definition.get("dtm_asset_keys", "dtm")
            ).split(",")
            if token.strip()
        ]
        selected = _select_stac_dtm_assets(
            items, prefer_asset_keys, target_resolution_m)
        if not selected:
            return None
        # Highest resolution first so the finest asset WINS on overlap
        # (gdal.Warp lets later inputs win, so sort coarsest-to-finest).
        selected.sort(
            key=lambda pair: (pair[1] is None, -(pair[1] or 0.0))
        )
        vsicurl_inputs = [
            _stac_asset_href_to_vsicurl(href) for (href, _resolution) in selected
        ]
        if not warp_vsicurl_sources_to_geotiff(
            vsicurl_inputs,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
            gdal_configuration_options=gdal_configuration_options,
        ):
            return None
        native_resolutions = [
            resolution for (_href, resolution) in selected if resolution
        ]
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [href for (href, _resolution) in selected],
            "source_ids": [
                item.get("id") for item in items if item.get("id")
            ],
            "collections": [
                token.strip()
                for token in str(definition.get("collections", "")).split(",")
                if token.strip()
            ],
            "native_resolution_m": (
                min(native_resolutions)
                if native_resolutions
                else definition.get("native_resolution_m")
            ),
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
