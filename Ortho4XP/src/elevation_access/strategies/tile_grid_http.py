"""The ``tile_grid_http`` access strategy (:class:`TileGridHttpStrategy`).

Deterministic per-kilometre tile downloads on a projected grid.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import os

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.definitions import (
    _coverage_bbox_intersects,
    transform_bounding_box_to_epsg,
)
from elevation_access.discovery import (
    HTTP_OUTCOME_ABSENT,
    HTTP_OUTCOME_OK,
    HTTP_OUTCOME_UNAVAILABLE,
    http_answer_outcome,
)
from elevation_access.failures import cap_exceeded_unavailable
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "TILE_GRID_PROBE_TIMEOUT_S",
    "TileGridHttpStrategy",
]


# =====================================================================
# Strategy 9: tile_grid_http (deterministic projected kilometre tiles)
# =====================================================================
#: Seconds one tile-grid existence probe (HEAD or ranged GET) may
#: wait for an answer.  A probe that times out is TRANSIENT: it got
#: no answer, so it says nothing about whether the tile is there
#: (:meth:`TileGridHttpStrategy._tile_exists`, issue #180).
TILE_GRID_PROBE_TIMEOUT_S = 30


@register_access_strategy("tile_grid_http")
class TileGridHttpStrategy:
    """Deterministic per-kilometre tile downloads on a projected grid.

    The German Länder pattern: bare-earth GeoTIFF tiles named by their
    lower-left kilometre coordinate in the UTM CRS (Bavaria's
    ``{easting_km}_{northing_km}.tif``, Thuringia's zipped epochs, the
    NRW year-stamped files).  Discovery is pure arithmetic --
    transform the airport box to ``source_epsg``, floor to the
    ``tile_size_km`` grid -- refined by either a HEAD probe per
    candidate (missing water/border tiles must not fail the mosaic) or
    a one-time cached directory index (``index_url``) where filenames
    carry unpredictable tokens like NRW's per-tile acquisition year.
    Fetch reads the tiles remotely through ``/vsicurl/`` (wrapped in
    ``/vsizip/`` when ``zip_inner_suffix`` says the GeoTIFF sits
    inside a per-tile zip) and warps through the shared core.
    """

    MAXIMUM_TILES_PER_FETCH = 120

    def index_path(self, definition):
        return os.path.join(
            FNAMES.Elevation_dir,
            definition["code"].lower() + "_tile_grid_index.json",
        )

    def _tile_names_from_index(self, definition):
        """The cached filename list of the provider's directory index."""
        import requests

        index_url = definition.get("index_url")
        if not index_url:
            return None
        try:
            with open(self.index_path(definition), "r") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            pass
        try:
            response = requests.get(index_url, timeout=120)
        except Exception as error:
            UI.vprint(
                1, "   WARNING: tile index request failed:", str(error)
            )
            return None
        if response.status_code != 200:
            return None
        names = []

        def _collect(node):
            if isinstance(node, dict):
                for value in node.values():
                    _collect(value)
            elif isinstance(node, list):
                for value in node:
                    _collect(value)
            elif isinstance(node, str) and any(
                token in node.lower() for token in (".tif", ".zip", ".xyz")
            ):
                names.append(node)

        try:
            _collect(response.json())
        except ValueError:
            # Not JSON: scrape filename-looking tokens out of an HTML
            # or plain-text directory listing (the Apache index case).
            import re

            names.extend(
                re.findall(
                    r"[\w\-\.]+\.(?:tif|zip|xyz)", response.text
                )
            )
            names = sorted(set(names))
        if not names:
            return None
        os.makedirs(
            os.path.dirname(self.index_path(definition)), exist_ok=True
        )
        with open(self.index_path(definition), "w", newline="\n") as handle:
            json.dump(names, handle)
        return names

    def discover(self, definition, bounding_box_wgs84):
        import requests

        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        source_epsg = int(float(definition.get("source_epsg", 25832)))
        tile_size_km = int(float(definition.get("tile_size_km", 1)))
        (x_min, y_min, x_max, y_max) = transform_bounding_box_to_epsg(
            bounding_box_wgs84, source_epsg
        )
        # Grid anchor offsets, in km: Baden-Wuerttemberg's 2 km tiles
        # are anchored at ODD easting kilometres.
        offset_e = int(float(definition.get("grid_easting_offset_km", 0)))
        offset_n = int(float(definition.get("grid_northing_offset_km", 0)))

        def _grid_range(minimum_m, maximum_m, offset_km):
            first = (
                int((minimum_m / 1000.0 - offset_km) // tile_size_km)
                * tile_size_km
                + offset_km
            )
            last = (
                int((maximum_m / 1000.0 - offset_km) // tile_size_km)
                * tile_size_km
                + offset_km
            )
            return range(first, last + tile_size_km, tile_size_km)

        eastings = _grid_range(x_min, x_max, offset_e)
        northings = _grid_range(y_min, y_max, offset_n)
        candidates = [
            (easting, northing)
            for easting in eastings
            for northing in northings
        ]
        maximum_tiles = int(float(definition.get(
            "max_tiles_per_airport", self.MAXIMUM_TILES_PER_FETCH)))
        if len(candidates) > maximum_tiles:
            raise cap_exceeded_unavailable(
                definition, "%d grid tiles" % len(candidates),
                "%d tiles" % maximum_tiles, "max_tiles_per_airport")
        index_names = self._tile_names_from_index(definition)
        template = definition["tile_url_template"]
        headers = self._http_headers(definition)
        sources = []
        session = requests.Session()
        for (easting, northing) in candidates:
            if index_names is not None:
                token = definition.get(
                    "index_token_template", "_{easting_km}_{northing_km}_"
                ).replace("{easting_km}", str(easting)).replace(
                    "{northing_km}", str(northing)
                )
                matches = [
                    name for name in index_names if token in name
                ]
                if not matches:
                    continue
                best_match = sorted(matches)[-1]
                # Index entries that are already full URLs (the
                # Schleswig-Holstein GeoJSON) need no template at all.
                if best_match.startswith("http"):
                    url = best_match
                else:
                    url = template.replace("{file_name}", best_match)
            else:
                northing_index_offset = int(
                    float(definition.get("grid_northing_index_offset", 0))
                )
                url = (
                    template.replace("{easting_km}", str(easting))
                    .replace("{northing_km}", str(northing))
                    # Austria's tiles are named in full metres.
                    .replace("{easting_m}", str(easting * 1000))
                    .replace("{northing_m}", str(northing * 1000))
                    # Espirito Santo's blocks are named by grid INDEX
                    # (coordinate // tile size), northing from the top.
                    .replace(
                        "{easting_index}",
                        str(easting // tile_size_km),
                    )
                    .replace(
                        "{northing_index}",
                        str(
                            northing // tile_size_km
                            + northing_index_offset
                        ),
                    )
                )
                if not self._tile_exists(
                    definition, session, headers, url
                ):
                    continue
            sources.append({"url": url})
        return sources or None

    def _http_headers(self, definition):
        """Optional per-provider request headers, ``Name: value;;...``.

        Saxony's geocloud is a PUBLIC Nextcloud share whose WebDAV path
        expects the (public) share token as a Basic-authorization user
        -- not a personal credential, just the same token that is in
        the public URL, so it may live in the definition file.
        """
        headers = {}
        for pair in str(definition.get("http_headers", "")).split(";;"):
            if ":" in pair:
                (name, value) = pair.split(":", 1)
                headers[name.strip()] = value.strip()
        return headers or None

    def _tile_exists(self, definition, session, headers, url):
        """Does a candidate tile URL exist?  Water/border tiles do not.

        ``probe_mode``: ``head`` (default), ``ranged_get`` (hosts that
        reject HEAD -- Saxony's answers 401 to it), ``gdal_open``
        (templates that are GDAL virtual paths rather than plain URLs,
        e.g. members inside one big remote zip), or ``none``.

        THE OUTCOME LAW (:func:`http_answer_outcome`, RULINGS
        2026-09-13b, issue #180 -- the #124 family at this second site):
        only a 404/410 -- the server looked and the tile is not there --
        may answer ``False``.  That answer SKIPS the tile, and a box
        whose every candidate is skipped leaves ``discover`` with no
        sources, which the caller records as a durable no-coverage; so a
        CDN 403, a proxy 407, a 429, a 503 or a dead transport must never
        reach it.  A 401/403/405/407/451 RAISES
        :class:`ProviderUnavailable` (the host refused to serve this
        client, which says nothing about the tile); a 429, a 5xx, an
        answer nobody recognises, and a probe that got NO answer at all
        RAISE :class:`TransientFetchError` (nothing recorded, asked again
        next run).  Both raises climb out through :meth:`fetch` into the
        ladder, which rules them per rung.

        REPORTED, NOT DECIDED (#180's open measurement): for a host whose
        answer for a genuinely absent tile is NOT a 404/410 -- no shipped
        definition is known to be one, and the one-request-per-provider
        live sweep the issue asks for is still untaken -- this turns a
        working provider into a refusal instead of a quiet skip.  The
        escape is the definition's own ``probe_mode=none``, which probes
        nothing and lets the warp decide; it needs no new knob.
        """
        probe_mode = str(definition.get("probe_mode", "head")).lower()
        if url.startswith("/vsi") or probe_mode == "gdal_open":
            # ``gdal.Open`` has ONE answer for "not there" and "refused"
            # alike (``None``), so this branch cannot tell the two apart
            # and keeps reading ``None`` as absent.  An EXCEPTION is not
            # an answer at all, and is classified as what it is.
            try:
                dataset = gdal.Open(url)
            except Exception as error:
                raise TransientFetchError(
                    "tile existence probe for %s died inside GDAL: %s - "
                    "transient, NOT recorded as no-coverage"
                    % (url, error)
                ) from error
            return dataset is not None
        if probe_mode == "none":
            return True
        try:
            if probe_mode == "ranged_get":
                request_headers = dict(headers or {})
                request_headers["Range"] = "bytes=0-0"
                probe = session.get(
                    url,
                    timeout=TILE_GRID_PROBE_TIMEOUT_S,
                    headers=request_headers,
                    stream=True,
                )
                probe.close()
            else:
                probe = session.head(
                    url,
                    timeout=TILE_GRID_PROBE_TIMEOUT_S,
                    headers=headers,
                    allow_redirects=True,
                )
        except Exception as error:
            # No HTTP answer at all says NOTHING about the tile, whatever
            # the exception's wording (#121: the wording was classified
            # and fell through to a durable absent for every message not
            # on a fragment list).
            raise TransientFetchError(
                "tile existence probe for %s died on the transport: %s - "
                "transient, NOT recorded as no-coverage" % (url, error)
            ) from error
        outcome = http_answer_outcome(probe.status_code)
        if outcome == HTTP_OUTCOME_OK:
            return True
        if outcome == HTTP_OUTCOME_ABSENT:
            return False
        if outcome == HTTP_OUTCOME_UNAVAILABLE:
            raise ProviderUnavailable(
                "tile existence probe for %s was refused with status %s - "
                "the host would not serve this client, which says NOTHING "
                "about the tile: recorded unavailable, not no-coverage"
                % (url, probe.status_code)
            )
        raise TransientFetchError(
            "tile existence probe for %s returned status %s - transient, "
            "NOT recorded as no-coverage" % (url, probe.status_code)
        )

    def _zip_inner_name(self, definition, url):
        """The GeoTIFF member name inside a per-tile zip.

        Zip stem + ``zip_inner_suffix``, minus an optional trailing
        ``zip_inner_strip`` token (Saxony's ``..._sn_tiff.zip`` holds
        ``..._sn.tif``).
        """
        stem = os.path.basename(url.split("?")[0])[: -len(".zip")]
        strip = definition.get("zip_inner_strip")
        if strip and stem.endswith(strip):
            stem = stem[: -len(strip)]
        return stem + definition.get("zip_inner_suffix", ".tif")

    def _warp_input_for(self, definition, url):
        if url.startswith("/vsi"):
            return url
        if definition.get("zip_inner_suffix") and url.lower().endswith(
            ".zip"
        ):
            return (
                "/vsizip//vsicurl/"
                + url
                + "/"
                + self._zip_inner_name(definition, url)
            )
        return "/vsicurl/" + url

    def _download_inputs(
        self, definition, sources, destination_path
    ):
        """``fetch_mode=download``: whole-tile pulls to local scratch.

        For hosts that ignore ranged requests or gate reads behind
        headers GDAL cannot easily carry (Saxony's share, the
        Schleswig-Holstein download script): each tile is downloaded
        with the definition's headers, and the warp input is the local
        file (or the GeoTIFF member inside the local zip).  Returns
        ``(warp_inputs, scratch_paths)``.
        """
        import requests

        headers = self._http_headers(definition)
        zip_inner_suffix = definition.get("zip_inner_suffix")
        warp_inputs = []
        scratch_paths = []
        for (number, entry) in enumerate(sources):
            suffix = definition.get("download_suffix") or (
                ".zip"
                if ".zip" in entry["url"].lower()
                else os.path.splitext(entry["url"].split("?")[0])[1]
                or ".dat"
            )
            scratch_path = destination_path + ".tile%d%s" % (number, suffix)
            try:
                response = requests.get(
                    entry["url"], timeout=300, headers=headers
                )
                if response.status_code != 200:
                    continue
                with open(scratch_path, "wb") as handle:
                    handle.write(response.content)
            except Exception as error:
                UI.vprint(
                    1,
                    "   WARNING: could not download elevation tile",
                    entry["url"][:90],
                    ":",
                    str(error),
                )
                continue
            scratch_paths.append(scratch_path)
            member_glob = definition.get("zip_member_glob")
            if member_glob and suffix == ".zip":
                # Members may sit under an inner folder (the
                # Baden-Wuerttemberg zips do) -- walk two levels.
                def _matching_members(root, depth=0):
                    for member in gdal.ReadDir(root) or []:
                        entry = root + "/" + member
                        if member.lower().endswith(member_glob):
                            yield entry
                        elif depth < 2 and "." not in member:
                            yield from _matching_members(entry, depth + 1)

                warp_inputs.extend(
                    _matching_members("/vsizip/" + scratch_path)
                )
            elif zip_inner_suffix and suffix == ".zip":
                warp_inputs.append(
                    "/vsizip/"
                    + scratch_path
                    + "/"
                    + self._zip_inner_name(definition, entry["url"])
                )
            else:
                warp_inputs.append(scratch_path)
        return (warp_inputs, scratch_paths)

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
        scratch_paths = []
        if str(definition.get("fetch_mode", "")).lower() == "download":
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            (warp_inputs, scratch_paths) = self._download_inputs(
                definition, sources, destination_path
            )
        else:
            warp_inputs = [
                self._warp_input_for(definition, entry["url"])
                for entry in sources
            ]
        source_srs = definition.get("warp_source_epsg")
        warped = bool(warp_inputs) and warp_vsicurl_sources_to_geotiff(
            warp_inputs,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
            source_srs=(
                "EPSG:" + str(int(float(source_srs))) if source_srs else None
            ),
        )
        for scratch_path in scratch_paths:
            try:
                os.remove(scratch_path)
            except OSError:
                pass
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
            "source_urls": [entry["url"] for entry in sources],
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
