"""OGC/STAC search whose asset downloads need a signed-in session.

The ``authenticated_token_search`` access strategy (:class:`AuthenticatedTokenSearchStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import os

import O4_UI_Utils as UI

from elevation_access.definitions import _coverage_bbox_intersects
from elevation_access.discovery import (
    discovery_json_payload,
    raise_transient_discovery_failure,
)
from elevation_access.failures import _warn_sign_in_needed_once
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.stac_assets import _stac_asset_href_to_vsicurl
from elevation_access.strategies.stac import StacCloudOptimizedGeoTiffStrategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "AuthenticatedTokenSearchStrategy",
]


# =====================================================================
# Strategy: authenticated_token_search (signed-in token redemption)
# =====================================================================


@register_access_strategy("authenticated_token_search")
class AuthenticatedTokenSearchStrategy:
    """OGC/STAC search whose asset downloads need a signed-in session.

    The pattern (first seen at Portugal's Direcao-Geral do Territorio
    download centre, live-verified 2026-07-16): the ``search_url``
    endpoint is PUBLIC and its items' asset hrefs are short-lived
    tokenized download URLs -- but redeeming one requires the account
    session cookie, and answers an HTTP redirect to a presigned object-
    storage URL.  The presigned URL itself is public and range-capable,
    so the fetch ends in the same windowed ``/vsicurl`` warp as every
    other Cloud-Optimized GeoTIFF strategy; whole source tiles are never
    downloaded.

    Sessions, cookies, and stored accounts are owned by
    O4_Authenticated_Sessions (definition keys ``session_name``,
    ``login_flow``, ``login_url``, ``session_probe_url``).  Without a
    working sign-in the provider degrades to no-coverage with ONE loud
    instruction, never a silent skip and never a failed build.

    Tokens are minted fresh by the search and redeemed immediately --
    tokens observed at the pilot service expire quickly and may be
    single-use, so nothing tokenized is ever cached or reused.
    """

    # NOT wide-area eligible: a whole 1-degree tile over the pilot
    # service would mean thousands of token redemptions per fetch (and
    # the search limit would truncate the item list).  Airport insets
    # need a few dozen items at most.
    supports_wide_area = False

    def discover(self, definition, bounding_box_wgs84):
        import requests

        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        search_url = definition.get("search_url", "")
        if not search_url:
            return None
        (west, south, east, north) = bounding_box_wgs84
        body = {
            "bbox": [west, south, east, north],
            "limit": int(float(definition.get("search_limit", 200))),
        }
        collections = [
            token.strip()
            for token in str(definition.get("collections", "")).split(",")
            if token.strip()
        ]
        if collections:
            body["collections"] = collections
        # Same law as every other HTTP discovery (spec SQ3): the search
        # dying tells us nothing about coverage, so it raises transient
        # instead of writing a durable no-coverage negative for this
        # provider/airport pair.
        description = "token search for provider %s" % definition.get("code")
        try:
            response = requests.post(search_url, json=body, timeout=30)
        except Exception as error:
            raise_transient_discovery_failure(description, error)
        payload = discovery_json_payload(response, description)
        if payload is None:
            return None
        items = StacCloudOptimizedGeoTiffStrategy._parse_search_payload(
            payload
        )
        if items is not None and len(items) >= body["limit"]:
            # No silent caps: a full page means the search may have
            # truncated the item list for this window.
            UI.vprint(
                1,
                "   WARNING: token search returned the full page of",
                body["limit"],
                "items for provider",
                definition.get("code"),
                "- coverage of this window may be incomplete.",
            )
        return items

    @staticmethod
    def _item_download_hrefs(items):
        """Tokenized download hrefs of the items' data assets."""
        hrefs = []
        for item in items:
            assets = item.get("assets")
            if not isinstance(assets, dict):
                continue
            for asset in assets.values():
                if not isinstance(asset, dict):
                    continue
                href = asset.get("href")
                roles = asset.get("roles") or []
                # A declared data role wins; the fallback (services that
                # do not declare roles at all) must not grab a lone
                # thumbnail or metadata asset by accident.
                if href and (
                    "data" in roles or (not roles and len(assets) == 1)
                ):
                    hrefs.append(href)
                    break
        return hrefs

    @staticmethod
    def _redeem_download_href(session, href):
        """Turn one tokenized download URL into its presigned target.

        The signed-in GET answers a redirect whose Location is the
        presigned object-storage URL.  Anything else (200 would mean the
        service streamed the file itself; an error status means the
        token aged out) returns None and the item is skipped with a
        warning by the caller.
        """
        try:
            response = session.get(href, timeout=30, allow_redirects=False)
        except Exception:
            return None
        if response.status_code not in (301, 302, 303, 307, 308):
            return None
        location = response.headers.get("Location", "")
        if not location.lower().startswith(("http://", "https://")):
            return None
        return location

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
        items = self.discover(definition, bounding_box_wgs84)
        if not items:
            return None
        try:
            session = SESSIONS.ensure_session(definition)
        except SESSIONS.LoginError as error:
            _warn_sign_in_needed_once(definition, error)
            return None
        hrefs = self._item_download_hrefs(items)
        presigned_urls = []
        for href in hrefs:
            presigned = self._redeem_download_href(session, href)
            if presigned is None:
                UI.vprint(
                    1,
                    "   WARNING: could not redeem a download token for",
                    definition.get("code"),
                    "- skipping one source tile.",
                )
                continue
            presigned_urls.append(presigned)
        if not presigned_urls:
            return None
        vsicurl_inputs = [
            _stac_asset_href_to_vsicurl(url) for url in presigned_urls
        ]
        source_nodata = definition.get("source_nodata")
        if not warp_vsicurl_sources_to_geotiff(
            vsicurl_inputs,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            source_nodata=(
                float(source_nodata) if source_nodata is not None else None
            ),
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
            # Provenance records the item ids, NOT the redeemed URLs:
            # presigned URLs carry signature query parameters and expire.
            "source_ids": [
                item.get("id") for item in items if item.get("id")
            ],
            "collections": [
                token.strip()
                for token in str(definition.get("collections", "")).split(",")
                if token.strip()
            ],
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
