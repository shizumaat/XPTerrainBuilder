"""The Colorado (CWCB) lidar API: per-tile zips of a ready-gridded DEM.

The ``cwcb_lidar_api`` access strategy (:class:`CwcbLidarApiStrategy`).

The Colorado Water Conservation Board lidar API
(``coloradohazardmapping.com/api/lidar``): per-tile zips of a ready-
gridded DEM (Routt 2016: a 1000 x 1000 Float32 ERDAS IMAGINE ``.img`` at
3 ft, NAD83(2011) Colorado North ftUS, heights in US survey feet
NAVD88). No LAS gridding.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import os

import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable
from elevation_access.definitions import (
    _coverage_bbox_intersects,
    _parse_float,
)
from elevation_access.discovery import (
    _DISCOVERY_ERROR_KEYS,
    discovery_json_payload,
    discovery_listing_items,
    raise_transient_discovery_failure,
)
from elevation_access.downloads import (
    _write_refused_by_armed_guard,
    download_zip_whole,
)
from elevation_access.failures import cap_exceeded_unavailable
from elevation_access.fetch_slots import (
    _held_provider_fetch_slot,
    provider_fetch_slots,
)
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.las_tiles import (
    CWCB_SUMMARIES_DEFAULT_MAX_AGE_DAYS,
    LAS_FOOTPRINT_KEY,
    _CWCB_LAS_MEMBER_SUFFIX,
    _cwcb_dataset_ids,
    _cwcb_request_polygon,
    _las_airport_label,
    cwcb_summaries_cache_path,
    las_core_geometry,
)
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _source_contribution_entry,
    _source_holds_data_over_bbox,
    inset_valid_fraction,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "CwcbLidarApiStrategy",
]


# =====================================================================
# Strategy: cwcb_lidar_api (Colorado CWCB lidar API: tile zips of a
# ready-gridded DEM; spec us-holder-providers §3.5, RULINGS 2026-09-30bm)
# =====================================================================


@register_access_strategy("cwcb_lidar_api")
class CwcbLidarApiStrategy:
    """The Colorado Water Conservation Board lidar API
    (``coloradohazardmapping.com/api/lidar``): per-tile zips of a
    ready-gridded DEM (Routt 2016: a 1000 x 1000 Float32 ERDAS IMAGINE
    ``.img`` at 3 ft, NAD83(2011) Colorado North ftUS, heights in US
    survey feet NAVD88).  No LAS gridding.

    Discovery (spec §3.5): ``POST tiles_url`` with the request polygon's
    WKT as a JSON string -> ``{"datasets": [...], "tiles": [keys]}`` over
    every dataset; the keys are filtered to ``dataset_ids`` through the
    per-dataset ``POST summaries_url ["<dataset>"]`` listing (tile id,
    footprint WKT, per-format bytes), memoised in
    :func:`cwcb_summaries_cache_path` and re-listed when stale; a tile is
    kept only when its footprint meets the polygon.  Classified by the
    module's one discovery law: 5xx/429/non-JSON/an ``{"error": ...}``
    inside a 200/a listing that is not a listing are TRANSIENT; a
    well-formed answer naming none of the datasets is the durable
    no-coverage.

    Fetch: caps checked BEFORE any byte moves (``max_tiles_per_airport``,
    ``max_bytes_per_airport`` against the listing's own per-format bytes
    -- the uncompressed member size, an upper bound on the zip), each
    ``GET file_url_template`` ({tileKey}, {formatKey}) streamed whole to
    scratch beside the destination (the server ignores ``Range``; a died
    transfer is re-GET whole once), the ``member_suffix`` member read
    through ``/vsizip/``, a VRT of the members into the shared warp with
    ``source_srs`` and ``vertical_unit``; scratch removed in ``finally``.
    A SURGICAL fetch (a footprint on the definition) returns a ``core``
    block, so the ladder judges it over the airport and assembles the
    next covering rung around it (the two-layer inset, spec §4).
    """

    supports_wide_area = False

    # ------------------------------------------------------------ checks
    def _refuse_unsupported_member(self, definition):
        suffix = str(definition.get("member_suffix", ".img")).strip().lower()
        if suffix == _CWCB_LAS_MEMBER_SUFFIX:
            raise ProviderUnavailable(
                "%s: member_suffix=.las is a LAS point cloud inside the zip "
                "-- the zip-unwrapped LAS path (las_tile_index "
                "index_format=cwcb archive_member=las, CWCB7V2LAS.elv), "
                "not cwcb_lidar_api, "
                "which reads a ready-gridded raster member"
                % definition.get("code"))
        return suffix

    # --------------------------------------------------------- summaries
    def _post_json(self, url, body, description):
        import requests

        try:
            response = requests.post(
                url, data=json.dumps(body),
                headers={"Content-Type": "application/json"}, timeout=120)
        except Exception as error:
            raise_transient_discovery_failure(description + " request",
                                              error)
        payload = discovery_json_payload(response, description)
        if isinstance(payload, dict):
            for key in _DISCOVERY_ERROR_KEYS + ("exceptionMessage",):
                if payload.get(key):
                    raise_transient_discovery_failure(
                        description,
                        "a 200 body reporting '%s': %s"
                        % (key, str(payload[key])[:200]))
        return payload

    def _list_dataset(self, definition, dataset_id):
        """The dataset's tile listing from the server, reduced to
        ``{tileKey: {"tile_id", "wkt", "bytes": {format: n}}}``."""
        description = "%s tileSummaries (%s)" % (definition.get("code"),
                                                 dataset_id)
        payload = self._post_json(definition.get("summaries_url"),
                                  [dataset_id], description)
        if payload is None:
            return None
        if not isinstance(payload, dict) or not isinstance(
                payload.get(dataset_id), dict):
            raise_transient_discovery_failure(
                description, "a 200 body carrying no listing for the "
                "dataset")
        listing = {}
        for (key, entry) in payload[dataset_id].items():
            try:
                wkt = entry["geography"]["geography"]["wellKnownText"]
                model = entry["model"]
            except (KeyError, TypeError):
                raise_transient_discovery_failure(
                    description, "tile %s carries no footprint" % key)
            listing[str(key)] = {
                "tile_id": str(model.get("tileId") or key),
                "wkt": str(wkt),
                "bytes": {
                    str(item.get("format")): int(item.get("fileSizeTotal")
                                                 or 0)
                    for item in (model.get("fileSummaries") or ())
                    if isinstance(item, dict)},
            }
        return listing

    def _dataset_listing(self, definition, dataset_id, force=False):
        """The cached listing when fresh, else a re-list (written back
        only when it changed, and never under an armed shared-repo
        guard -- the listing is then used from memory)."""
        import time as _time

        path = cwcb_summaries_cache_path(definition.get("code"), dataset_id)
        max_age_days = _parse_float(
            definition.get("summaries_max_age_days"),
            default=CWCB_SUMMARIES_DEFAULT_MAX_AGE_DAYS)
        cached = None
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    cached = json.load(handle)
            except (OSError, ValueError):
                cached = None
        if isinstance(cached, dict) and not force:
            age_days = (_time.time() - os.path.getmtime(path)) / 86400.0
            if age_days <= max_age_days:
                return cached, "cached"
        listing = self._list_dataset(definition, dataset_id)
        if listing is None:
            return None, "listed"
        text = json.dumps(listing, sort_keys=True, separators=(",", ":"))
        if (cached != listing and not _write_refused_by_armed_guard(path)):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                scratch = path + ".part"
                with open(scratch, "w", encoding="utf-8",
                          newline="\n") as handle:
                    handle.write(text)
                os.replace(scratch, path)
            except OSError as error:
                UI.vprint(1, "   [inset] %s: tile listing not cached (%s) "
                          "- used from memory" % (definition.get("code"),
                                                  error))
        return listing, "listed"

    # --------------------------------------------------------- discovery
    def discover(self, definition, bounding_box_wgs84):
        """The tiles of ``dataset_ids`` whose footprint meets the request
        polygon, ``[{source_id, tile_key, title, download_url, bytes,
        dataset}]`` sorted by tile id; ``None`` for a durable no-coverage
        (a well-formed answer naming none of the datasets)."""
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        self._refuse_unsupported_member(definition)
        return self.discover_tiles(definition, bounding_box_wgs84)

    def discover_tiles(self, definition, bounding_box_wgs84):
        """THE CWCB discovery, whatever the tile's member: also the tile
        index of ``las_tile_index index_format=cwcb`` (the zipped point
        clouds, spec us-holder-providers §3.3)."""
        from shapely import from_wkt

        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        datasets = _cwcb_dataset_ids(definition)
        format_key = str(definition.get("format_key", "")).strip()
        if not datasets or not format_key:
            raise ProviderUnavailable(
                "%s: .elv carries no dataset_ids / format_key"
                % definition.get("code"))
        (polygon, _core) = _cwcb_request_polygon(definition,
                                                 bounding_box_wgs84)
        description = "%s tiles" % definition.get("code")
        payload = self._post_json(definition.get("tiles_url"), polygon.wkt,
                                  description)
        if payload is None:
            return None
        keys = discovery_listing_items(payload, description,
                                       items_key="tiles", total_key=None)
        named = payload.get("datasets")
        if not isinstance(named, list):
            raise_transient_discovery_failure(
                description, "a 200 body carrying no 'datasets' list")
        keys = {str(key) for key in keys}
        sources = []
        for dataset_id in datasets:
            if dataset_id not in named:
                continue
            (listing, how) = self._dataset_listing(definition, dataset_id)
            if listing is None:
                continue
            if how == "cached" and not keys.intersection(listing):
                # The server names the dataset here and the cache holds
                # none of its keys: the cache is stale, not the server.
                (listing, how) = self._dataset_listing(
                    definition, dataset_id, force=True)
                if listing is None:
                    continue
            for key in sorted(keys.intersection(listing)):
                entry = listing[key]
                size = entry.get("bytes", {}).get(format_key)
                if size is None:
                    continue           # no such product for this tile
                try:
                    footprint = from_wkt(entry["wkt"])
                except Exception:
                    raise_transient_discovery_failure(
                        description, "tile %s footprint unreadable" % key)
                if not footprint.intersects(polygon):
                    continue
                sources.append({
                    "source_id": entry["tile_id"],
                    "tile_key": key,
                    "title": entry["tile_id"],
                    "dataset": dataset_id,
                    "bytes": int(size),
                    "download_url": str(definition.get(
                        "file_url_template", ""))
                    .replace("{tileKey}", key)
                    .replace("{formatKey}", format_key),
                    "publication_date": definition.get(
                        "publication_date") or "",
                })
        if not sources:
            return None
        return sorted(sources, key=lambda source: source["source_id"])

    # ------------------------------------------------------------- fetch
    def _check_caps(self, definition, sources, destination_path):
        """Refuse an over-cap fetch BEFORE any byte moves (spec §3)."""
        max_tiles = int(float(definition.get("max_tiles_per_airport", 0)
                              or 0))
        max_bytes = int(float(definition.get("max_bytes_per_airport", 0)
                              or 0))
        total_bytes = sum(source["bytes"] for source in sources)
        if (max_tiles and len(sources) > max_tiles) or (
                max_bytes and total_bytes > max_bytes):
            raise cap_exceeded_unavailable(
                definition,
                "%d tiles / %.0f MB" % (len(sources), total_bytes / 1e6),
                "%d / %.0f MB" % (max_tiles, max_bytes / 1e6),
                "max_tiles_per_airport / max_bytes_per_airport",
                destination_path)
        return total_bytes

    def _download_zip(self, definition, source, scratch_path, member,
                      progress_label):
        """One tile zip, WHOLE (the server ignores ``Range``): the module's
        one whole-archive download, :func:`download_zip_whole`."""
        return download_zip_whole(definition, source, scratch_path, member,
                                  progress_label)

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        code = definition.get("code")
        if not has_gdal:
            return None
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        suffix = self._refuse_unsupported_member(definition)
        sources = self.discover(definition, bounding_box_wgs84)
        if not sources:
            return None
        total_bytes = self._check_caps(definition, sources,
                                       destination_path)
        airport = _las_airport_label(destination_path)
        slots = provider_fetch_slots(definition)
        UI.vprint(
            1,
            "    [inset] %s %s: downloading %d tile zip(s) (<= %.0f MB) "
            "over %d connection(s)"
            % (airport, code, len(sources), total_bytes / 1e6, slots),
        )
        scratch_paths = []
        try:
            jobs = []
            for (number, source) in enumerate(sources):
                scratch_path = "%s.cwcb%d.zip" % (destination_path, number)
                scratch_paths.append(scratch_path)
                jobs.append((number, source, scratch_path,
                             source["source_id"] + suffix))

            def _download(job):
                (number, source, scratch_path, member) = job
                # Its OWN semaphore: the per-airport loop already holds
                # one of ``code``'s slots around this whole fetch, and two
                # airports of one tile on the same key would deadlock.
                with _held_provider_fetch_slot(code + ":tiles", slots):
                    return self._download_zip(
                        definition, source, scratch_path, member,
                        "%s %s tile %d/%d %s" % (
                            airport, code, number + 1, len(sources),
                            source["source_id"]))

            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=slots) as pool:
                results = list(pool.map(_download, jobs))
            missing = sorted(job[1]["source_id"]
                             for (job, ok) in zip(jobs, results) if not ok)
            present = [(job[1], "/vsizip/%s/%s" % (job[2], job[3]))
                       for (job, ok) in zip(jobs, results) if ok]
            if not present:
                raise ProviderUnavailable(
                    "%s: listing names %d tiles, server has none"
                    % (code, len(sources)))
            bytes_fetched = sum(os.path.getsize(job[2])
                                for (job, ok) in zip(jobs, results) if ok)
            source_nodata = _parse_float(definition.get("source_nodata"))
            vrt_path = destination_path + ".cwcb.vrt"
            scratch_paths.append(vrt_path)
            gdal.BuildVRT(
                vrt_path, [path for (_source, path) in present],
                options=gdal.BuildVRTOptions(
                    srcNodata=source_nodata, VRTNodata=source_nodata)
                if source_nodata is not None else None)
            if not warp_vsicurl_sources_to_geotiff(
                [vrt_path],
                bounding_box_wgs84,
                target_resolution_m,
                destination_path,
                source_srs=definition.get("source_srs") or None,
                source_nodata=source_nodata,
                value_floor_m=float(definition.get("value_floor_m",
                                                   -600.0)),
                vertical_unit=_raster_vertical_unit(definition),
                provider_code=code,
            ):
                return None
            used = []
            empty = []
            for (source, path) in present:
                if _source_holds_data_over_bbox(
                        path, bounding_box_wgs84,
                        source_nodata=source_nodata):
                    used.append(source)
                else:
                    empty.append(source)
        finally:
            for path in scratch_paths:
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:                      # pragma: no cover
                        pass
        provenance = {
            "provider": code,
            "access_strategy": definition.get("access_strategy"),
            "dataset_ids": _cwcb_dataset_ids(definition),
            "format_key": definition.get("format_key"),
            "source_urls": [source["download_url"] for source in sources],
            "source_ids": [source["source_id"] for source in sources],
            "sources_used": [
                _source_contribution_entry(source) for source in used],
            "sources_empty_over_bbox": [
                _source_contribution_entry(source) for source in empty],
            "tiles_missing": missing,
            "bytes_fetched": bytes_fetched,
            "bytes_listed": total_bytes,
            "publication_date": definition.get("publication_date"),
            "valid_fraction": round(inset_valid_fraction(destination_path),
                                    6),
            "rmse_z_m": _parse_float(definition.get("rmse_z_m")),
            "license": definition.get("license"),
            "license_note": definition.get("license_note"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "source_crs": definition.get("source_srs"),
            "datum_note": (
                "Elevations are in the source vertical datum; lidar is "
                "treated as truth and is NOT shifted toward the base DEM."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "native_resolution_m": definition.get("native_resolution_m"),
            "resolution_m": target_resolution_m,
        }
        core = las_core_geometry(definition)
        if core is not None:
            # THE SURGICAL CORE (spec §4): the tiles meeting the buffered
            # aerodrome boundary; outside them the raster is NoData and
            # the ladder assembles the next covering rung around it.
            provenance["core"] = {
                "provider": code,
                "bounding_box_wgs84": [round(v, 9) for v in core.bounds],
                "boundary_polygon_wgs84": definition.get(
                    LAS_FOOTPRINT_KEY),
                "footprint_buffer_m": _parse_float(
                    definition.get("footprint_buffer_m"), default=0.0),
                "tile_names": [source["source_id"]
                               for (source, _path) in present],
                "feather_m": _parse_float(
                    definition.get("core_feather_m"), default=None),
            }
        return provenance
