"""The ``arcgis_feature_tiles`` access strategy (:class:`ArcgisFeatureTileStrategy`).

ArcGIS feature layers whose attributes carry -- or resolve to -- archive
URLs.

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
    _parse_float,
)
from elevation_access.discovery import (
    discovery_json_payload,
    discovery_listing_items,
    discovery_status_is_transient,
    raise_transient_discovery_failure,
)
from elevation_access.downloads import archive_raster_members
from elevation_access.failures import (
    cap_exceeded_unavailable,
    error_message_indicates_transient_network_failure,
)
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.las_tiles import (
    LAS_FOOTPRINT_KEY,
    _esri_polygon_geometry,
    _las_airport_label,
    las_core_geometry,
)
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "ArcgisFeatureTileStrategy",
]


# =====================================================================
# Strategy 14: arcgis_feature_tiles (feature catalogs with DATA_URL)
# =====================================================================
@register_access_strategy("arcgis_feature_tiles")
class ArcgisFeatureTileStrategy:
    """ArcGIS feature layers whose attributes carry -- or resolve to --
    archive URLs.

    Ireland's national lidar is published this way: a folder of
    "Coverage" map services whose polygon layers hold a ``DATA_URL``
    field pointing at zip/7z archives of GeoTIFF tiles.  Discovery
    enumerates the folder ONCE (cached: every layer carrying the URL
    field becomes a query endpoint), then each fetch spatially queries
    those layers for the airport box, downloads the referenced
    archives and warps their terrain-model members through GDAL's
    ``/vsizip`` / ``/vsi7z`` handlers.

    THE INDEX-LAYER FORM (spec us-holder-providers §3.2, Texas): one
    statewide tile-index layer (``index_layer_url``, filtered by
    ``index_where``) whose features name a TILE (``tile_id_field``) of a
    COLLECTION (``collection_field``), not a URL.  An
    ``archive_resolver`` turns (collection, tile) into the archive URL
    (``tnris_resources``: the TxGIO resources API, one listing per
    collection, memoised beside the inset cache), and
    ``member_filter_template`` names the ONE member per feature.  With
    ``archive_access=remote_member`` the archive is never downloaded
    whole: each named member is copied out of the remote zip through
    ``/vsizip//vsicurl/`` (HTTP range reads of that member only) into
    scratch beside the destination and removed after the warp.  When
    the definition carries ``footprint_buffer_m`` and the ladder hands
    the aerodrome boundary (:data:`LAS_FOOTPRINT_KEY`), the listing is
    SURGICAL exactly as the LAS strategy's (tile footprint meets the
    buffered boundary polygon) and the provenance carries a ``core``
    block the ladder assembles a two-layer inset around.

    Every listed archive/member either reaches the warp or the fetch
    RAISES (transient for a network-shaped failure, ``unavailable`` for
    a listed archive or member that is not there): a partial mosaic is
    never delivered as the whole (spec §7).
    """

    MAXIMUM_ARCHIVES_PER_FETCH = 8

    #: Raster members a terrain archive may hold (Erdas IMAGINE included:
    #: some Texas collections ship ``.img`` tiles).
    RASTER_MEMBER_EXTENSIONS = (".tif", ".tiff", ".img")

    #: Same-stem companions copied out of a remote archive WITH a member
    #: (georeferencing, overviews and large-IMG spill files).
    MEMBER_COMPANION_EXTENSIONS = (".tfw", ".tifw", ".aux.xml", ".ige",
                                   ".rrd", ".rde", ".prj")

    #: Index-layer paging: records per query page and the page bound (a
    #: listing still exceeding it is a truncated listing -> transient).
    INDEX_PAGE_SIZE = 1000
    INDEX_MAXIMUM_PAGES = 20

    #: Pages of a TxGIO resources listing followed before the listing is
    #: called truncated (transient).
    RESOURCE_MAXIMUM_PAGES = 50

    def index_path(self, definition):
        return os.path.join(
            FNAMES.Elevation_dir,
            definition["code"].lower() + "_feature_layers.json",
        )

    def resources_path(self, definition):
        """The memoised per-collection archive listing of an
        ``archive_resolver`` provider (``texas1m_resources.json``)."""
        return os.path.join(
            FNAMES.Elevation_dir,
            definition["code"].lower() + "_resources.json",
        )

    def _query_endpoints(self, definition):
        import requests

        if definition.get("index_layer_url"):
            return [str(definition["index_layer_url"]).strip().rstrip("/")]
        try:
            with open(self.index_path(definition), "r") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            pass
        folder_url = definition["catalog_folder_url"].rstrip("/")
        url_field = definition.get("url_field", "DATA_URL")
        session = requests.Session()
        try:
            folder = session.get(folder_url + "?f=json", timeout=60).json()
        except Exception as error:
            UI.vprint(
                1, "   WARNING: catalog folder query failed:", str(error)
            )
            return None
        service_names = sorted(
            {
                service.get("name")
                for service in folder.get("services", [])
                if service.get("name")
                and "coverage" in service.get("name", "").lower()
            }
        )
        UI.vprint(
            1,
            "    Indexing",
            len(service_names),
            "lidar coverage catalogs (once per install).",
        )
        root = folder_url.rsplit("/", 1)[0]
        endpoints = []
        for name in service_names:
            service_url = root + "/" + name + "/MapServer"
            try:
                service = session.get(
                    service_url + "?f=json", timeout=60
                ).json()
            except Exception:
                continue
            for layer in service.get("layers", []):
                layer_url = service_url + "/" + str(layer.get("id"))
                try:
                    layer_meta = session.get(
                        layer_url + "?f=json", timeout=60
                    ).json()
                except Exception:
                    continue
                fields = [
                    field.get("name", "")
                    for field in layer_meta.get("fields", []) or []
                ]
                if url_field in fields:
                    endpoints.append(layer_url)
        if not endpoints:
            return None
        os.makedirs(
            os.path.dirname(self.index_path(definition)), exist_ok=True
        )
        with open(self.index_path(definition), "w", newline="\n") as handle:
            json.dump(endpoints, handle)
        return endpoints

    # -----------------------------------------------------------------
    # The index-layer form (spec §3.2)
    # -----------------------------------------------------------------
    @staticmethod
    def _surgical_core(definition):
        """The buffered aerodrome boundary when the definition opts in
        (``footprint_buffer_m``) AND the ladder handed a footprint."""
        if definition.get("footprint_buffer_m") is None:
            return None
        return las_core_geometry(definition)

    def _index_layer_features(self, definition, query_box, with_geometry):
        """Every feature of the index layer over ``query_box`` (all
        pages), or raise transient on an incomplete answer."""
        import requests

        layer_url = self._query_endpoints(definition)[0]
        (west, south, east, north) = query_box
        fields = [definition.get("tile_id_field", "tileid")]
        if definition.get("archive_resolver"):
            fields.append(definition.get("collection_field", "collid"))
        else:
            fields.append(definition.get("url_field", "DATA_URL"))
        description = "%s index layer query" % definition.get("code")
        features = []
        offset = 0
        for _page in range(self.INDEX_MAXIMUM_PAGES):
            parameters = {
                "where": definition.get("index_where")
                or definition.get("where") or "1=1",
                "geometry": "%r,%r,%r,%r" % (west, south, east, north),
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": ",".join(fields),
                "returnGeometry": "true" if with_geometry else "false",
                "outSR": "4326",
                "orderByFields": fields[0],
                "resultOffset": str(offset),
                "resultRecordCount": str(self.INDEX_PAGE_SIZE),
                "f": "json",
            }
            try:
                response = requests.get(layer_url + "/query",
                                        params=parameters, timeout=60)
            except Exception as error:
                raise_transient_discovery_failure(description, error)
            payload = discovery_json_payload(response, description)
            if payload is None:
                return None
            page_features = discovery_listing_items(
                payload, description, items_key="features", total_key=None)
            features.extend(page_features)
            if not payload.get("exceededTransferLimit"):
                return features
            if not page_features:
                raise_transient_discovery_failure(
                    description, "an empty page that claims more records")
            # The server's own page size may be below the one asked for
            # (its maxRecordCount): advance by what ARRIVED.
            offset += len(page_features)
        raise_transient_discovery_failure(
            description, "a truncated listing (more than %d pages)"
            % self.INDEX_MAXIMUM_PAGES)

    def _tnris_resource_archives(self, definition, collection_id,
                                 refresh=False):
        """``{key: archive URL}`` for one collection, from the memo or
        the TxGIO resources API (every page).  The key is the resource
        file's tile token -- ``{prefix}_{key}{suffix}`` -- and the URL is
        ``archive_url_template`` filled with ``collid``, ``prefix`` and
        ``tileid7`` (the S3 origin, never the CloudFront host, which
        refuses non-browser agents -- spec §3.2)."""
        import requests

        memo_path = self.resources_path(definition)
        memo = {}
        try:
            with open(memo_path, "r") as handle:
                memo = json.load(handle) or {}
        except (OSError, ValueError):
            memo = {}
        if not refresh and isinstance(memo.get(collection_id), dict):
            return memo[collection_id]
        template = definition.get(
            "archive_resolver_url",
            "https://api.tnris.org/api/v1/resources/?collection_id="
            "{collid}&resource_type_abbreviation=DEM")
        suffix = definition.get("archive_resource_suffix", "_dem.zip")
        url = template.format(collid=collection_id)
        description = "%s resources listing %s" % (
            definition.get("code"), collection_id)
        archives = {}
        for _page in range(self.RESOURCE_MAXIMUM_PAGES):
            try:
                response = requests.get(url, timeout=60)
            except Exception as error:
                raise_transient_discovery_failure(description, error)
            payload = discovery_json_payload(response, description)
            if payload is None:
                return {}
            for item in discovery_listing_items(
                    payload, description, items_key="results",
                    total_key="count"):
                resource = str((item or {}).get("resource") or "")
                name = resource.rsplit("/", 1)[-1]
                if not name.endswith(suffix) or "_" not in name:
                    continue
                (prefix, key) = name[: -len(suffix)].rsplit("_", 1)
                archives[key] = definition["archive_url_template"].format(
                    collid=collection_id, prefix=prefix, tileid7=key)
            url = payload.get("next")
            if not url:
                break
        else:
            raise_transient_discovery_failure(
                description, "a truncated listing (more than %d pages)"
                % self.RESOURCE_MAXIMUM_PAGES)
        memo[collection_id] = archives
        os.makedirs(os.path.dirname(memo_path), exist_ok=True)
        with open(memo_path, "w", newline="\n") as handle:
            json.dump(memo, handle, indent=0, sort_keys=True)
        return archives

    def _resolve_archive(self, definition, attributes):
        """The archive URL one index feature lives in, or raise
        ``unavailable`` when the resolver's listing does not hold it."""
        resolver = definition.get("archive_resolver")
        if resolver != "tnris_resources":
            raise ProviderUnavailable(
                "%s: archive_resolver=%s is not a known resolver"
                % (definition.get("code"), resolver))
        collection_id = str(attributes.get(
            definition.get("collection_field", "collid")) or "")
        tile_id = str(attributes.get(
            definition.get("tile_id_field", "tileid")) or "")
        key = tile_id[: int(definition.get("archive_key_length", 7))]
        archives = self._tnris_resource_archives(definition, collection_id)
        if key not in archives:
            # A stale memo is refreshed ONCE before the listing is judged.
            archives = self._tnris_resource_archives(
                definition, collection_id, refresh=True)
        if key not in archives:
            raise ProviderUnavailable(
                "%s: index tile %s has no archive in collection %s's "
                "resources listing - refused, never a partial mosaic"
                % (definition.get("code"), tile_id, collection_id))
        return archives[key]

    def _discover_index_layer(self, definition, bounding_box_wgs84,
                              resolve=False):
        """The index tiles over the box (surgical when opted in).

        ``resolve=False`` (discovery: the ladder re-check, the census)
        lists the TILES only -- no resources-API call and no memo write,
        so asking "is there coverage" never writes the data repo; the
        fetch resolves each tile's archive (``resolve=True``)."""
        core = self._surgical_core(definition)
        query_box = core.bounds if core is not None else bounding_box_wgs84
        features = self._index_layer_features(
            definition, query_box, with_geometry=core is not None)
        if not features:
            return None
        tile_field = definition.get("tile_id_field", "tileid")
        member_template = definition.get("member_filter_template")
        entries = []
        seen = set()
        for feature in features:
            attributes = (feature or {}).get("attributes") or {}
            tile_id = attributes.get(tile_field)
            if tile_id is None or str(tile_id) in seen:
                continue
            if core is not None:
                footprint = _esri_polygon_geometry(feature.get("geometry"))
                if footprint is None or not footprint.intersects(core):
                    continue
            seen.add(str(tile_id))
            if not definition.get("archive_resolver"):
                url = attributes.get(definition.get("url_field", "DATA_URL"))
            elif resolve:
                url = self._resolve_archive(definition, attributes)
            else:
                url = "%s/%s" % (attributes.get(definition.get(
                    "collection_field", "collid")), tile_id)
            if not url:
                continue
            entry = {"url": url, "source_id": str(tile_id)}
            if member_template:
                entry["member"] = str(member_template).format(**{
                    str(name): value for (name, value) in attributes.items()})
            entries.append(entry)
        return entries or None

    def discover(self, definition, bounding_box_wgs84, resolve=False):
        import requests

        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        if definition.get("index_layer_url"):
            return self._discover_index_layer(definition, bounding_box_wgs84,
                                              resolve=resolve)
        endpoints = self._query_endpoints(definition)
        if not endpoints:
            return None
        url_field = definition.get("url_field", "DATA_URL")
        (west, south, east, north) = bounding_box_wgs84
        session = requests.Session()
        archives = []
        seen = set()
        for layer_url in endpoints:
            query = (
                layer_url
                + "/query?geometry=%s,%s,%s,%s" % (west, south, east, north)
                + "&geometryType=esriGeometryEnvelope&inSR=4326"
                + "&spatialRel=esriSpatialRelIntersects&outFields="
                + url_field
                + "&returnGeometry=false&f=json"
            )
            # Spec SQ3: a layer query that dies says nothing about
            # coverage.  Skipping it here and returning the OTHER
            # endpoints' answer records a truncated archive list as a
            # durable one, so the failure raises transient instead.
            description = "ArcGIS layer query %s" % layer_url
            try:
                response = session.get(query, timeout=60)
            except Exception as error:
                raise_transient_discovery_failure(description, error)
            payload = discovery_json_payload(response, description)
            if payload is None:
                continue
            for feature in payload.get("features", []) or []:
                archive_url = (feature.get("attributes") or {}).get(
                    url_field
                )
                if archive_url and archive_url not in seen:
                    seen.add(archive_url)
                    archives.append({"url": archive_url})
        # The WHOLE listing (spec §3.2): the cap is judged in fetch, where
        # exceeding it is ``unavailable`` -- the old ``[:8]`` slice
        # delivered a truncated listing as if it were the whole.
        return archives or None

    # -----------------------------------------------------------------
    # Members
    # -----------------------------------------------------------------
    def _raster_members(self, root, depth=0):
        return archive_raster_members(root, self.RASTER_MEMBER_EXTENSIONS,
                                      depth)

    @staticmethod
    def _members_named(members, needle):
        needle = str(needle).lower()
        return [member for member in members
                if needle in os.path.basename(member).lower()]

    @staticmethod
    def _archive_failure(definition, url, error):
        """Raise the class a failed archive/member read belongs to."""
        if error_message_indicates_transient_network_failure(error):
            raise TransientFetchError(
                "%s: archive %s: %s" % (definition.get("code"), url, error))
        raise ProviderUnavailable(
            "%s: listed archive %s could not be read (%s) - refused, never "
            "a partial mosaic" % (definition.get("code"), url, error))

    def _probe_remote_archive(self, definition, url):
        """Classify an archive GDAL could not list: a 5xx/429/network
        failure is transient, anything else ``unavailable``."""
        import requests

        if not url.lower().startswith(("http://", "https://")):
            raise ProviderUnavailable(
                "%s: listed archive %s is not readable - refused, never a "
                "partial mosaic" % (definition.get("code"), url))
        try:
            response = requests.head(url, timeout=60, allow_redirects=True)
        except Exception as error:
            raise TransientFetchError(
                "%s: archive %s: %s" % (definition.get("code"), url, error))
        if discovery_status_is_transient(response.status_code):
            raise TransientFetchError(
                "%s: archive %s: status %d"
                % (definition.get("code"), url, response.status_code))
        raise ProviderUnavailable(
            "%s: listed archive %s is not readable (status %d) - refused, "
            "never a partial mosaic"
            % (definition.get("code"), url, response.status_code))

    def _copy_remote_member(self, definition, url, member, scratch_dir):
        """Copy ONE member (and its same-stem companions) out of a remote
        zip by range reads; returns ``(local path, bytes)``."""
        source_root = member.rsplit("/", 1)[0]
        name = os.path.basename(member)
        stem = os.path.splitext(name)[0]
        names = [name] + [
            companion for companion in (gdal.ReadDir(source_root) or [])
            if companion != name and companion.lower().startswith(
                stem.lower() + ".")
            and companion.lower()[len(stem):] in
            self.MEMBER_COMPANION_EXTENSIONS
        ]
        copied = 0
        for item in names:
            source = source_root + "/" + item
            target = os.path.join(scratch_dir, item)
            try:
                handle_in = gdal.VSIFOpenL(source, "rb")
                if handle_in is None:
                    raise RuntimeError("cannot open %s" % source)
                try:
                    with open(target, "wb") as handle_out:
                        while True:
                            block = gdal.VSIFReadL(1, 1 << 22, handle_in)
                            if not block:
                                break
                            handle_out.write(block)
                            copied += len(block)
                finally:
                    gdal.VSIFCloseL(handle_in)
            except Exception as error:
                self._archive_failure(definition, url, error)
        return (os.path.join(scratch_dir, name), copied)

    def _remote_members(self, definition, sources, destination_path,
                        scratch_paths):
        """Every listed member copied out of its remote archive."""
        import time

        scratch_dir = destination_path + ".members"
        os.makedirs(scratch_dir, exist_ok=True)
        scratch_paths.append(scratch_dir)
        by_archive = {}
        for entry in sources:
            by_archive.setdefault(entry["url"], []).append(entry)
        members_out = []
        total_bytes = 0
        started = time.time()
        label = "%s %s" % (_las_airport_label(destination_path),
                           definition.get("code"))
        done = 0
        for (url, entries) in by_archive.items():
            # An http(s) archive is read by range requests; a local path
            # (a mirror, the suite's fixtures) through /vsizip alone.
            root = "/vsizip/" + (
                "/vsicurl/" + url if url.lower().startswith(
                    ("http://", "https://")) else url)
            with gdal.config_options({
                    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
                    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".zip"}):
                members = list(self._raster_members(root))
                if not members:
                    self._probe_remote_archive(definition, url)
                for entry in entries:
                    named = self._members_named(
                        members, entry.get("member") or definition.get(
                            "member_filter", "dtm"))
                    if not named:
                        raise ProviderUnavailable(
                            "%s: archive %s holds no member %r for index "
                            "tile %s - refused, never a partial mosaic"
                            % (definition.get("code"), url,
                               entry.get("member"), entry.get("source_id")))
                    for member in named:
                        (local, size) = self._copy_remote_member(
                            definition, url, member, scratch_dir)
                        members_out.append(local)
                        total_bytes += size
                    done += 1
                    UI.vprint(1, "   [inset] %s member %d/%d %s (%.0f MB "
                              "so far, %.0f s)" % (
                                  label, done, len(sources),
                                  entry.get("source_id"),
                                  total_bytes / 1e6, time.time() - started))
        return (members_out, total_bytes)

    def _downloaded_members(self, definition, sources, destination_path,
                            scratch_paths):
        """Download each listed archive whole; its raster members."""
        import requests

        members_out = []
        total_bytes = 0
        by_archive = {}
        for entry in sources:
            by_archive.setdefault(entry["url"], []).append(entry)
        for (number, (url, entries)) in enumerate(by_archive.items()):
            suffix = os.path.splitext(url.split("?")[0])[1] or ".zip"
            scratch_path = destination_path + ".arch%d%s" % (number, suffix)
            try:
                response = requests.get(url, timeout=600)
            except Exception as error:
                # A listed archive that did not arrive leaves the mosaic
                # partial: never delivered as the whole (spec §7).
                raise TransientFetchError(
                    "%s: archive %s: %s"
                    % (definition.get("code"), url, error))
            if response.status_code != 200:
                if discovery_status_is_transient(response.status_code):
                    raise TransientFetchError(
                        "%s: archive %s: status %d"
                        % (definition.get("code"), url,
                           response.status_code))
                raise ProviderUnavailable(
                    "%s: listed archive %s answered status %d - refused, "
                    "never a partial mosaic"
                    % (definition.get("code"), url, response.status_code))
            with open(scratch_path, "wb") as handle:
                handle.write(response.content)
            total_bytes += len(response.content)
            scratch_paths.append(scratch_path)
            handler = "/vsi7z/" if suffix.lower() == ".7z" else "/vsizip/"
            members = list(self._raster_members(handler + scratch_path))
            per_feature = [entry.get("member") for entry in entries
                           if entry.get("member")]
            if per_feature:
                for needle in per_feature:
                    named = self._members_named(members, needle)
                    if not named:
                        raise ProviderUnavailable(
                            "%s: archive %s holds no member %r - refused, "
                            "never a partial mosaic"
                            % (definition.get("code"), url, needle))
                    members_out.extend(named)
            else:
                preferred = self._members_named(
                    members, definition.get("member_filter", "dtm"))
                members_out.extend(preferred or members)
        return (members_out, total_bytes)

    def _declared_warp_input(self, definition, member, destination_path,
                             scratch_paths):
        """``member`` itself, or a VRT wrapper declaring what the member
        lacks: an UNDECLARED fill value (sniffed: a minimum below any land
        on Earth, or the definition's ``source_nodata``) and -- when the
        member carries no CRS at all -- the definition's ``source_srs``."""
        fallback_nodata = _parse_float(definition.get("source_nodata"))
        fallback_srs = definition.get("source_srs")
        try:
            member_dataset = gdal.Open(member)
            band = member_dataset.GetRasterBand(1)
            declared = band.GetNoDataValue()
            (minimum, _maximum) = band.ComputeRasterMinMax(True)
            fill = None
            if minimum < -430.0:
                # Below any land on Earth: the minimum IS the fill.
                fill = minimum
            elif (
                fallback_nodata is not None
                and abs(minimum - fallback_nodata) < 0.5
            ):
                # The definition's known fill is present -- even when the
                # band DECLARES something else (one Irish campaign
                # declares 0.0 while filling with -99, which would also
                # void real sea-level pixels).
                fill = fallback_nodata
            options = {}
            if fill is not None and (
                declared is None or abs(declared - fill) > 0.5
            ):
                options["noData"] = fill
            if fallback_srs and not (member_dataset.GetProjection() or ""):
                options["outputSRS"] = str(fallback_srs)
            if options:
                vrt_path = destination_path + ".m%d.vrt" % len(scratch_paths)
                gdal.Translate(vrt_path, member_dataset, format="VRT",
                               **options)
                scratch_paths.append(vrt_path)
                return vrt_path
            member_dataset = None
        except Exception:
            pass
        return member

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        import shutil

        if not has_gdal:
            return None
        sources = (self.discover(definition, bounding_box_wgs84, resolve=True)
                   if definition.get("index_layer_url")
                   else self.discover(definition, bounding_box_wgs84))
        if not sources:
            return None
        maximum_archives = int(float(definition.get(
            "max_archives_per_airport", self.MAXIMUM_ARCHIVES_PER_FETCH)))
        # The per-feature form counts what it reads -- one member per
        # index tile; the URL form counts archives.
        units = (len(sources) if any("member" in s for s in sources)
                 else len({s["url"] for s in sources}))
        unit_name = ("archive members" if any("member" in s for s in sources)
                     else "archives")
        if units > maximum_archives:
            raise cap_exceeded_unavailable(
                definition, "%d %s" % (units, unit_name),
                "%d" % maximum_archives, "max_archives_per_airport",
                destination_path)
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        scratch_paths = []
        try:
            if definition.get("archive_access") == "remote_member":
                (members, fetched_bytes) = self._remote_members(
                    definition, sources, destination_path, scratch_paths)
            else:
                (members, fetched_bytes) = self._downloaded_members(
                    definition, sources, destination_path, scratch_paths)
            warp_inputs = [
                self._declared_warp_input(definition, member,
                                          destination_path, scratch_paths)
                for member in members
            ]
            warped = bool(warp_inputs) and warp_vsicurl_sources_to_geotiff(
                warp_inputs,
                bounding_box_wgs84,
                target_resolution_m,
                destination_path,
                value_floor_m=float(definition.get("value_floor_m", -600.0)),
                vertical_unit=_raster_vertical_unit(definition),
                provider_code=definition.get("code"),
            )
        finally:
            for scratch_path in scratch_paths:
                try:
                    if os.path.isdir(scratch_path):
                        shutil.rmtree(scratch_path, ignore_errors=True)
                    else:
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
        provenance = {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": list(dict.fromkeys(
                entry["url"] for entry in sources)),
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
        if definition.get("index_layer_url"):
            # ADDITIVE keys for the index-layer form only: the URL form's
            # provenance stays byte-identical to before.
            provenance["source_ids"] = [
                entry.get("source_id") for entry in sources]
            provenance["archive_members"] = len(members)
            # DECOMPRESSED member bytes (what the warp read); the network
            # transfer of a deflated member is smaller (KGRK 2026-09-30:
            # 3.6 MB on the wire per 12.8 MB member).
            provenance["archive_member_bytes"] = int(fetched_bytes)
            core = self._surgical_core(definition)
            if core is not None:
                # THE SURGICAL CORE (spec §4): what the ladder assembles
                # the two-layer inset around (the LAS strategy's block).
                provenance["core"] = {
                    "provider": definition.get("code"),
                    "bounding_box_wgs84": [round(v, 9) for v in core.bounds],
                    "boundary_polygon_wgs84": definition.get(
                        LAS_FOOTPRINT_KEY),
                    "footprint_buffer_m": _parse_float(
                        definition.get("footprint_buffer_m"), default=0.0),
                    "tile_names": [
                        entry.get("source_id") for entry in sources],
                    "feather_m": _parse_float(
                        definition.get("core_feather_m"), default=None),
                }
        return provenance
