"""Cloud-Optimized GeoTIFFs indexed by a plain-text list of URLs.

The ``coordinate_named_url_list`` access strategy (:class:`CoordinateNamedUrlListStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import os
import re as _re

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.definitions import (
    _bounding_boxes_intersect,
    _coverage_bbox_intersects,
)
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import warp_vsicurl_sources_to_geotiff

__all__ = [
    "CoordinateNamedUrlListStrategy",
]


# =====================================================================
# Strategy: coordinate_named_url_list (plain URL list, filename = location)
# =====================================================================


# The NOAA NCEI CUDEM filename tile-locator token.  Grammar (spec / this
# file's docstring): a filename contains one pair
# ``_<lat><sep><lon>_`` where the LATITUDE token is
# ``[ns]DDxQQ`` and the LONGITUDE token is ``[ew]DDDxQQ`` -- two-digit
# whole degrees of latitude, three-digit whole degrees of longitude, a
# decimal separator, and a two-digit hundredths part in {00,25,50,75}.
# The separator is written both lowercase ``x`` (n39x00) AND uppercase
# ``X`` (n25X75, the 2018 Florida campaign): the live CONUS list mixes
# both, so the pattern accepts either (a spec-reality note recorded in the
# strategy docstring).
_CUDEM_TILE_TOKEN = _re.compile(
    r"_([ns])(\d{2})[xX](\d{2})_([ew])(\d{3})[xX](\d{2})_"
)


@register_access_strategy("coordinate_named_url_list")
class CoordinateNamedUrlListStrategy:
    """Cloud-Optimized GeoTIFFs indexed by a plain-text list of URLs.

    NOAA NCEI publishes several CUDEM regions (CONUS coasts, Guam) NOT as a
    STAC catalog but as a single ``urllist<id>.txt`` file: one Cloud-
    Optimized GeoTIFF URL per line, the tile's location encoded in the
    filename.  There is no per-tile JSON to walk (unlike ``static_stac``),
    so discovery fetches that ONE text file once, parses every filename's
    coordinate token into a bounding box, and memoises the result in a
    per-provider index under ``Elevation_data/`` -- the first airport in a
    region pays the single small download, every later airport and every
    rebuild reads the index.  Fetch is the shared windowed ``/vsicurl``
    warp core (only the requested window of each remote tile is read).

    Filename grammar and its coordinate semantics (validated 2026-07-16
    against the NCEI STAC oracles -- do NOT change without re-validating):

      * The token pair is ``_[ns]DDxQQ_[ew]DDDxQQ_`` where ``x`` (or its
        uppercase ``X`` variant, both live in the CONUS list) is the
        decimal separator and ``QQ`` is hundredths of a degree in
        {00,25,50,75}.
      * The LATITUDE token gives the tile's NORTH edge: ``n`` = positive
        latitude, ``s`` = negative.  Verified against Hawaii item
        ``ncei19_n22x00_w159x50`` (bbox north 22.0002) and, for the
        southern hemisphere, American Samoa items
        ``ncei19_s14x25_w169x75`` (bbox north -14.2498) and
        ``ncei19_s14x00_w169x50`` (bbox north -13.9998): ``s14x25`` is the
        NORTH edge at -14.25, not the south edge.
      * The LONGITUDE token gives the tile's WEST edge: ``w`` = negative
        longitude, ``e`` = positive (Guam ``ncei19_n13x25_e144x50`` ->
        west 144.50).
      * Every tile is 0.25 deg x 0.25 deg, so ``east = west + 0.25`` and
        ``south = north - 0.25``.

    Lines whose filename carries no such token (the list also holds
    shapefile sidecars, metadata ``.xml``/``.json``, ``.zip`` archives and
    the list file itself) are skipped, reported once as a summary count --
    never one warning per line.
    """

    # Windowed /vsicurl reader: eligible for whole-tile overlay fetches.
    supports_wide_area = True

    # 0.25 deg tile edge, and the padding applied to every stored bbox so a
    # query that grazes a tile boundary still matches (mirrors the oracle
    # bboxes' own ~0.0002 deg overlap).
    TILE_DEGREES = 0.25
    BBOX_PADDING_DEGREES = 0.001

    @staticmethod
    def parse_filename_bbox(filename):
        """Parse a CUDEM tile filename into ``[west, south, east, north]``.

        Returns the UNPADDED tile bounding box, or ``None`` when the
        filename carries no ``_[ns]DDxQQ_[ew]DDDxQQ_`` locator token.  See
        the class docstring for the validated north-edge / west-edge
        coordinate convention.
        """
        match = _CUDEM_TILE_TOKEN.search(filename)
        if match is None:
            return None
        (
            latitude_hemisphere,
            latitude_degrees,
            latitude_hundredths,
            longitude_hemisphere,
            longitude_degrees,
            longitude_hundredths,
        ) = match.groups()
        latitude = int(latitude_degrees) + int(latitude_hundredths) / 100.0
        longitude = int(longitude_degrees) + int(longitude_hundredths) / 100.0
        north = latitude if latitude_hemisphere == "n" else -latitude
        west = longitude if longitude_hemisphere == "e" else -longitude
        tile = CoordinateNamedUrlListStrategy.TILE_DEGREES
        return [west, north - tile, west + tile, north]

    def index_path(self, definition):
        return os.path.join(
            FNAMES.Elevation_dir,
            definition["code"].lower() + "_url_list_index.json",
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

    def _ensure_entries(self, definition, index):
        """Fill ``index["entries"]`` from the URL list once (memoised).

        ``entries`` is a list of ``{"href": url, "bbox": padded box}``.
        The single text-file download happens only when the index has no
        ``entries`` key yet; a later call (this run or a rebuild) reads the
        saved index and performs ZERO HTTP.
        """
        import requests

        if index.get("entries") is not None:
            return
        url_list_url = definition.get("url_list_url")
        if not url_list_url:
            return
        try:
            response = requests.get(url_list_url, timeout=60)
        except Exception as error:
            UI.vprint(
                1, "   WARNING: URL-list request failed:", str(error)
            )
            return
        if response.status_code != 200:
            UI.vprint(
                1,
                "   WARNING: URL-list request returned status",
                response.status_code,
            )
            return
        entries = []
        skipped = 0
        padding = self.BBOX_PADDING_DEGREES
        for line in response.text.splitlines():
            url = line.strip()
            if not url:
                continue
            filename = url.rsplit("/", 1)[-1]
            box = self.parse_filename_bbox(filename)
            if box is None:
                skipped += 1
                continue
            entries.append(
                {
                    "href": url,
                    "bbox": [
                        box[0] - padding,
                        box[1] - padding,
                        box[2] + padding,
                        box[3] + padding,
                    ],
                }
            )
        UI.vprint(
            1,
            "    Indexing the",
            definition.get("code"),
            "elevation URL list (",
            len(entries),
            "coordinate-named tiles,",
            skipped,
            "non-tile lines skipped, once per install).",
        )
        index["entries"] = entries

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        index = self._load_index(definition)
        self._ensure_entries(definition, index)
        entries = index.get("entries")
        if not entries:
            return None
        self._save_index(definition, index)
        matched = [
            entry
            for entry in entries
            if _bounding_boxes_intersect(entry["bbox"], bounding_box_wgs84)
        ]
        return matched or None

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
        vsicurl_inputs = ["/vsicurl/" + entry["href"] for entry in sources]
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
        tile_stems = [
            entry["href"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
            for entry in sources
        ]
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [entry["href"] for entry in sources],
            "source_ids": tile_stems,
            "project_titles": tile_stems,
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "datum_note": (
                "Depths are in the source local tidal datum; a bathymetry "
                "source is used only for water rendering, never for terrain "
                "grading."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            # Every other strategy stamps what the SOURCE publishes
            # beside what the warp targeted; without it a manifest
            # reader has only the target and calls a 1 m lidar cut
            # coarse (the 2026-08-15 N32W098 class), and a
            # manifest-side pixel tolerance cannot be computed at
            # all (measured 2026-09-17: 229 usgs3dep manifests).
            "native_resolution_m": definition.get(
                "native_resolution_m"),
            "resolution_m": target_resolution_m,
        }
