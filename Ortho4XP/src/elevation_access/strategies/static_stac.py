"""Static STAC catalog trees on object storage (no /search API).

The ``static_stac`` access strategy (:class:`StaticStacCatalogStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import numpy
import os

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable
from elevation_access.capabilities import (
    lerc_decode_available,
    lerc_worker_argv,
)
from elevation_access.definitions import (
    _bounding_boxes_intersect,
    _coverage_bbox_intersects,
    _parse_bounding_box,
    _parse_float,
)
from elevation_access.discovery import (
    discovery_json_payload,
    raise_transient_discovery_failure,
)
from elevation_access.gdal_support import gdal, has_gdal, osr
from elevation_access.registry import register_access_strategy
from elevation_access.stac_assets import (
    _select_stac_dtm_assets,
    _stac_asset_href_to_vsicurl,
)
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "StaticStacCatalogStrategy",
]


# =====================================================================
# Strategy 4: static_stac (catalog.json trees on object storage)
# =====================================================================


@register_access_strategy("static_stac")
class StaticStacCatalogStrategy:
    """Static STAC catalog trees on object storage (no /search API).

    New Zealand's national lidar (the ``nz-elevation`` bucket) publishes
    STAC 1.0 as plain JSON files: a root catalog linking ~200 survey
    collections, each linking hundreds of items, each carrying a
    bounding box and one Cloud-Optimized GeoTIFF asset.  There is no
    search endpoint, so discovery WALKS the tree -- and because that
    walk is thousands of small requests for a whole country, every
    fetched bounding box is memoised in ONE per-provider index file
    under ``Elevation_data/``: the first airport in a region pays the
    walk, every later airport (and every rebuild) reads the index.
    """

    def index_path(self, definition):
        return os.path.join(
            FNAMES.Elevation_dir,
            definition["code"].lower() + "_static_stac_index.json",
        )

    def _load_index(self, definition):
        try:
            with open(self.index_path(definition), "r") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    def _save_index(self, definition, index):
        index_file = self.index_path(definition)
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, "w", newline="\n") as handle:
            json.dump(index, handle)

    def _fetch_json(self, session, url):
        """One catalog/collection/item document, or ``None``.

        Spec SQ3: the catalog being unreachable is not the catalog saying
        "no data here" -- a transport failure, a 5xx/429 and an error page
        served as 200 all raise transient, so an outage during indexing is
        never written into the coverage index as a durable negative.
        """
        try:
            response = session.get(url, timeout=60)
        except Exception as error:
            raise_transient_discovery_failure(
                "static catalog request %s" % url, error
            )
        return discovery_json_payload(
            response, "static catalog request %s" % url
        )

    def _prefer_asset_keys(self, definition):
        return [
            token.strip()
            for token in str(
                definition.get("dtm_asset_keys", "dtm")
            ).split(",")
            if token.strip()
        ]

    def _ensure_collections(self, definition, index, session):
        """Fill index["collections"] = {url: {bbox, items}} once.

        Two catalog shapes are handled.  The New Zealand shape is a tree:
        the root links ~200 survey COLLECTIONS (``rel="child"``), each of
        which carries its own spatial extent and a list of item links.
        The NOAA NCEI CUDEM shape (spec section 2.3) has NO child links --
        its tiles hang directly off the root as ``rel="item"`` links -- so
        when the catalog has zero child links but at least one item link we
        synthesize a single pseudo-collection keyed by the catalog URL,
        whose bounding box is the provider's ``coverage_bbox`` (there is no
        per-collection extent to read) and whose items are the root item
        hrefs.  The tree path below is left byte-identical.
        """
        import urllib.parse

        if index.get("collections") is not None:
            return
        catalog_url = definition["catalog_url"]
        catalog = self._fetch_json(session, catalog_url)
        if catalog is None:
            return
        children = [
            link
            for link in catalog.get("links", [])
            if link.get("rel") == "child" and link.get("href")
        ]
        if not children:
            root_item_hrefs = [
                link["href"]
                for link in catalog.get("links", [])
                if link.get("rel") == "item" and link.get("href")
            ]
            if root_item_hrefs:
                # Reuse the coverage_bbox parser -- a definition parsed from
                # a .elv file already holds a (west, south, east, north)
                # tuple, but one assembled by hand in a test may still be a
                # raw "W,S,E,N" string.
                coverage = definition.get("coverage_bbox")
                if not isinstance(coverage, (list, tuple)):
                    coverage = _parse_bounding_box(coverage)
                if coverage:
                    UI.vprint(
                        1,
                        "    Indexing the",
                        definition["code"],
                        "elevation catalog (root-item catalog,",
                        len(root_item_hrefs),
                        "tiles, once per install).",
                    )
                    index["collections"] = {
                        catalog_url: {
                            "bbox": list(coverage),
                            "items": root_item_hrefs,
                        }
                    }
                    return
        must_contain = str(definition.get("collection_filter", ""))
        if must_contain:
            children = [
                link for link in children if must_contain in link["href"]
            ]
        UI.vprint(
            1,
            "    Indexing the",
            definition["code"],
            "elevation catalog (",
            len(children),
            "collections, once per install).",
        )
        collections = {}
        for link in children:
            collection_url = urllib.parse.urljoin(catalog_url, link["href"])
            collection = self._fetch_json(session, collection_url)
            if not collection:
                continue
            boxes = (
                (collection.get("extent") or {})
                .get("spatial", {})
                .get("bbox")
            ) or []
            if not boxes:
                continue
            collections[collection_url] = {
                "bbox": boxes[0],
                "items": [
                    item_link["href"]
                    for item_link in collection.get("links", [])
                    if item_link.get("rel") == "item"
                    and item_link.get("href")
                ],
            }
        index["collections"] = collections

    def _ensure_items(self, definition, index, session, collection_url):
        """Fill and return the item entries of one collection."""
        import urllib.parse

        items_by_collection = index.setdefault("items", {})
        if collection_url in items_by_collection:
            return items_by_collection[collection_url]
        item_hrefs = index["collections"][collection_url]["items"]
        UI.vprint(
            1,
            "    Indexing",
            len(item_hrefs),
            "elevation tiles of one survey (once).",
        )
        prefer = self._prefer_asset_keys(definition)
        entries = []
        for href in item_hrefs:
            item_url = urllib.parse.urljoin(collection_url, href)
            item = self._fetch_json(session, item_url)
            if not item or not item.get("bbox"):
                continue
            selected = _select_stac_dtm_assets([item], prefer)
            if not selected:
                continue
            (asset_href, resolution) = selected[0]
            entries.append(
                {
                    "bbox": item["bbox"],
                    "href": urllib.parse.urljoin(item_url, asset_href),
                    "resolution": resolution,
                }
            )
        items_by_collection[collection_url] = entries
        return entries

    def discover(self, definition, bounding_box_wgs84):
        import requests

        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        index = self._load_index(definition)
        session = requests.Session()
        self._ensure_collections(definition, index, session)
        if not index.get("collections"):
            return None
        sources = []
        for (collection_url, record) in index["collections"].items():
            if not _bounding_boxes_intersect(
                record["bbox"], bounding_box_wgs84
            ):
                continue
            for entry in self._ensure_items(
                definition, index, session, collection_url
            ):
                if _bounding_boxes_intersect(
                    entry["bbox"], bounding_box_wgs84
                ):
                    sources.append(entry)
        self._save_index(definition, index)
        return sources or None

    # THE DECODE RUNS OUT OF PROCESS, in ``src/O4_LERC_Decode.py``:
    # imagecodecs' LERC decoder and the osgeo shared libraries abort the
    # process when both are loaded (a native symbol clash, reproduced on
    # macOS with the Homebrew GDAL and the imagecodecs wheels), so the
    # decode must never share a process with GDAL.  ONE implementation
    # for both the source and the frozen path (2026-09-12as (3)):
    # ``lerc_worker_argv`` below spells the argv for each.

    def _decode_lerc_sources(self, definition, sources, destination_path):
        """Download + decode LERC-compressed assets to local GeoTIFFs.

        Some catalogs (New Zealand's) compress their Cloud-Optimized
        GeoTIFFs with LERC, a codec most GDAL builds (Homebrew, the
        official wheels) ship WITHOUT -- a ``/vsicurl`` warp then fails
        with "missing codec LERC".  When the definition declares
        ``asset_compression=lerc`` the whole tile is downloaded instead
        and decoded (in a subprocess, :func:`lerc_worker_argv`) into
        a temporary plain GeoTIFF beside ``destination_path``,
        georeferenced from the embedded ModelPixelScale/ModelTiepoint
        tags and the definition's ``source_epsg``.  Returns the
        temporary paths (caller deletes).
        """
        import subprocess

        import requests

        import O4_Console_Encoding

        if not lerc_decode_available():
            # THE 1.0.324 CONDITION, honestly named (owner RULINGS
            # 2026-09-13b).  The packaged engine of that build returned
            # an EMPTY list here instead, the warp had nothing to warp,
            # the strategy answered ``None`` -- and ``None`` is recorded
            # as a durable no-coverage.  NZQN's 1 m lidar was lost that
            # way.  A missing decoder is never a coverage answer.
            raise ProviderUnavailable(
                "the LERC decoder is not available (tifffile/imagecodecs)"
            )
        source_epsg = int(float(definition.get("source_epsg", 4326)))
        temporary_paths = []
        # Why nothing decoded, when nothing decodes: a 404 is the server
        # ANSWERING about the asset (durable), anything else -- a timeout,
        # a 5xx, a decode crash -- is us, and must never become a
        # no-coverage negative.
        non_durable_failure = None
        for (number, entry) in enumerate(sources):
            tiff_path = destination_path + ".lerc%d.download" % number
            npy_path = destination_path + ".lerc%d.npy" % number
            try:
                response = requests.get(entry["href"], timeout=300)
                if response.status_code != 200:
                    if int(response.status_code) != 404:
                        non_durable_failure = (
                            "asset download returned status %s"
                            % response.status_code
                        )
                    continue
                with open(tiff_path, "wb") as handle:
                    handle.write(response.content)
                completed = subprocess.run(
                    lerc_worker_argv(tiff_path, npy_path),
                    capture_output=True,
                    **O4_Console_Encoding.child_console_pipe(),
                    timeout=600,
                )
                if completed.returncode != 0:
                    raise RuntimeError(
                        completed.stderr.strip()[-200:] or "decode failed"
                    )
                payload = (completed.stdout or "").strip()
                if not payload:
                    # A console-less frozen binary (the Windows/Linux Qt
                    # app, which is also the engine) can run with no
                    # stdout at all: the worker writes the same JSON
                    # beside the array (RULINGS 2026-09-13a (1)).
                    with open(npy_path + ".tags.json") as handle:
                        payload = handle.read()
                tags = json.loads(payload)
                scale = tags["scale"]
                tiepoint = tags["tiepoint"]
                values = numpy.load(npy_path)
            except Exception as error:
                non_durable_failure = "could not decode an asset: %s" % error
                UI.vprint(
                    1,
                    "   WARNING: could not decode elevation tile",
                    entry["href"],
                    ":",
                    str(error),
                )
                continue
            finally:
                for scratch in (tiff_path, npy_path,
                                npy_path + ".tags.json"):
                    try:
                        os.remove(scratch)
                    except OSError:
                        pass
            temporary_path = destination_path + ".lerc%d.tif" % number
            driver = gdal.GetDriverByName("GTiff")
            dataset = driver.Create(
                temporary_path,
                values.shape[1],
                values.shape[0],
                1,
                gdal.GDT_Float32,
            )
            dataset.SetGeoTransform(
                (tiepoint[3], scale[0], 0.0, tiepoint[4], 0.0, -scale[1])
            )
            spatial_reference = osr.SpatialReference()
            spatial_reference.ImportFromEPSG(source_epsg)
            dataset.SetProjection(spatial_reference.ExportToWkt())
            band = dataset.GetRasterBand(1)
            nodata = _parse_float(definition.get("source_nodata"), -9999.0)
            band.SetNoDataValue(nodata)
            band.WriteArray(values)
            band.FlushCache()
            dataset = None
            temporary_paths.append(temporary_path)
        if sources and not temporary_paths and non_durable_failure:
            # Discovery FOUND assets over this box -- the provider has
            # data here -- and none of them reached us for a reason that
            # is ours or the transport's.  That is not coverage news.
            raise ProviderUnavailable(non_durable_failure)
        return temporary_paths

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
        temporary_paths = []
        if str(definition.get("asset_compression", "")).lower() == "lerc":
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            temporary_paths = self._decode_lerc_sources(
                definition, sources, destination_path
            )
            warp_inputs = temporary_paths
        else:
            warp_inputs = [
                _stac_asset_href_to_vsicurl(entry["href"])
                for entry in sources
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
        for temporary_path in temporary_paths:
            try:
                os.remove(temporary_path)
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
        resolutions = [
            entry["resolution"]
            for entry in sources
            if entry.get("resolution")
        ]
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [entry["href"] for entry in sources],
            "native_resolution_m": (
                min(resolutions)
                if resolutions
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
