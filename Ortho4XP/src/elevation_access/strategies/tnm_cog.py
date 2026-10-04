"""The ``tnm_cog`` access strategy (:class:`TnmCloudOptimizedGeoTiffStrategy`).

Fetch United States Geological Survey 3DEP lidar via the National Map.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import os

import O4_Geo_Utils as GEO
import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.definitions import _parse_boolean, _parse_float
from elevation_access.discovery import (
    raise_transient_discovery_failure,
    tnm_listing_items,
)
from elevation_access.downloads import (
    archive_raster_members,
    download_whole,
    download_zip_whole,
)
from elevation_access.fetch_slots import (
    _held_provider_fetch_slot,
    provider_fetch_slots,
)
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.las_tiles import _las_airport_label, _las_size_text
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _SOURCE_CONTRIBUTION_PROBE_SAMPLES,
    _source_contribution_entry,
    _source_holds_data_over_bbox,
    inset_valid_fraction,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "PREFETCH_WHOLE_MAX_BYTES",
    "RASTER_HEIGHT_UNITS_TO_M",
    "TnmCloudOptimizedGeoTiffStrategy",
    "raster_height_unit",
    "raster_native_resolution_m",
]


def _refuse_mixed_vertical_datums(definition, sources):
    """Raise unless every discovered source shares one vertical datum.

    R13-2 mosaics ACROSS projects, and heights may only be mixed inside a
    single datum.  3DEP is NAVD88 throughout today, so this never fires --
    which is exactly why it is asserted rather than assumed: a provider
    that one day discovers sources in two datums must stop loudly, not
    average an ellipsoidal tile into an orthometric one.  A source carries
    its own ``vertical_datum`` only where a strategy records one;
    everything else inherits the provider definition's.
    """
    declared = definition.get("vertical_datum")
    datums = sorted(
        {str(source.get("vertical_datum") or declared) for source in sources}
    )
    if len(datums) > 1:
        raise ValueError(
            "elevation provider %s discovered sources in %d vertical datums "
            "(%s) for one inset - REFUSING to mix heights in a mosaic"
            % (definition.get("code"), len(datums), ", ".join(datums))
        )


def _tnm_project_of(title, download_url=None):
    """The 3DEP project name inside a TNM product title.

    Titles read ``USGS 1 Meter 15 x34y435 KS_Statewide_2018_A18`` -- the
    project is the last token, and the project is what a reader needs
    when a border airport mosaics two states.  ``"?"`` for a title-less
    item.  An Original Product Resolution title ends in the TILE id
    (``USGS Original Product Resolution Anchorage_Lidar 63376784``), so
    when the download URL names its project (``.../Projects/<name>/``)
    that wins (#153).
    """
    url = str(download_url or "")
    if "/Projects/" in url:
        name = url.split("/Projects/", 1)[1].split("/", 1)[0]
        if name:
            return name
    tokens = str(title or "").split()
    return tokens[-1] if tokens else "?"


# ---------------------------------------------------------------------
# Products read at their ORIGINAL resolution (#153, the USGS OPR rung):
# the grid, the CRS and the HEIGHT UNIT come from each file, not from
# the definition.
# ---------------------------------------------------------------------
#: Height units a raster may name (band unit type / CRS unit name), in
#: metres per unit.
RASTER_HEIGHT_UNITS_TO_M = {
    "m": 1.0, "metre": 1.0, "meter": 1.0, "metres": 1.0, "meters": 1.0,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "international foot": 0.3048,
    "us survey foot": 1200.0 / 3937.0, "ftus": 1200.0 / 3937.0,
    "us-ft": 1200.0 / 3937.0, "foot_us": 1200.0 / 3937.0,
    "us survey feet": 1200.0 / 3937.0,
}


#: A source's own contribution probe samples its FOOTPRINT (one ~1 km
#: OPR tile) rather than the whole box, so a coarse grid answers it.
_SOURCE_FOOTPRINT_PROBE_SAMPLES = 32


#: Parallel header reads when a listing's sources are inspected.
_SOURCE_INSPECTION_WORKERS = 8


#: Whole-tile prefetch (#158) stops asking above this many bytes for one
#: airport; beyond it the windowed ``/vsicurl`` read -- slower, but
#: bounded by the window and needing no scratch -- carries the fetch.  A
#: provider raises or lowers it with ``prefetch_whole_max_bytes`` in its
#: ``.elv``.  2 GB holds KGEG's 64 x ~16 MB OPR campaign twice over.
PREFETCH_WHOLE_MAX_BYTES = 2.0e9


def _definition_reads_source_units(definition):
    """``source_units=from_source``: the provider's products each carry
    their own grid and height unit, read from the file (#153)."""
    return str((definition or {}).get("source_units", "")).strip().lower() \
        == "from_source"


def raster_height_unit(dataset):
    """``(metres_per_unit, unit_name, rule)`` for a GDAL raster's HEIGHTS.

    The order of evidence: a compound CRS's VERTICAL unit (Montana DNRC:
    NAVD88 height in feet); else the band's declared unit type; else the
    HORIZONTAL unit of a projected CRS (USGS OPR products posted in a
    State Plane foot CRS with no vertical CRS carry heights in that same
    foot -- measured 2026-10-01: Fairbanks FB17 reads 434.9 where the
    seamless 1/3 arc-second reads 132.7 m; 434.9 ftUS = 132.6 m); else
    metres."""
    srs = dataset.GetSpatialRef()
    if srs is not None and srs.IsCompound():
        try:
            factor = float(srs.GetTargetLinearUnits("VERT_CS"))
            name = srs.GetAttrValue("VERT_CS|UNIT") or "vertical CRS unit"
            if factor > 0:
                return (factor, str(name), "vertical-crs")
        except Exception:
            pass
    unit_type = str(dataset.GetRasterBand(1).GetUnitType() or "").strip()
    if unit_type.lower() in RASTER_HEIGHT_UNITS_TO_M:
        return (RASTER_HEIGHT_UNITS_TO_M[unit_type.lower()], unit_type,
                "band-unit")
    if srs is not None and srs.IsProjected():
        factor = float(srs.GetLinearUnits() or 1.0)
        return (factor, str(srs.GetLinearUnitsName() or ""),
                "horizontal-crs")
    return (1.0, "metre", "default")


def raster_native_resolution_m(dataset):
    """The raster's posting in metres (its pixel width in its own CRS)."""
    transform = dataset.GetGeoTransform()
    pixel = abs(float(transform[1]))
    srs = dataset.GetSpatialRef()
    if srs is not None and srs.IsProjected():
        return pixel * float(srs.GetLinearUnits() or 1.0)
    if srs is not None and srs.IsGeographic():
        return pixel * GEO.lat_to_m
    return pixel


def _raster_source_byte_size(warp_input):
    """The source file's size in bytes, or ``None``.  ``gdal.VSIStatL``
    answers for a local path and from the ``/vsicurl`` HEAD the open has
    already made and cached, so this costs no extra request."""
    try:
        stat = gdal.VSIStatL(warp_input)
    except Exception:                                    # pragma: no cover
        return None
    if stat is None:
        return None
    try:
        size = int(stat.size)
    except (AttributeError, TypeError, ValueError):       # pragma: no cover
        return None
    return size if size > 0 else None


def _inspect_raster_source(warp_input):
    """One source's header facts, or ``None`` when it cannot be opened.

    The BLOCK LAYOUT comes out with the rest (#158): the headers are read
    once for every listed product anyway, so whether a product is
    stripped or tiled is known before a single byte of raster is asked
    for."""
    dataset = gdal.Open(warp_input)
    if dataset is None:
        return None
    (factor, unit, rule) = raster_height_unit(dataset)
    srs = dataset.GetSpatialRef()
    band = dataset.GetRasterBand(1)
    (block_x_size, block_y_size) = band.GetBlockSize()
    record = {
        "native_resolution_m": round(raster_native_resolution_m(dataset), 4),
        "z_to_m": factor,
        "height_unit": unit,
        "height_unit_rule": rule,
        "crs": (srs.GetName() if srs is not None else None),
        "raster_x_size": int(dataset.RasterXSize),
        "raster_y_size": int(dataset.RasterYSize),
        "block_x_size": int(block_x_size),
        "block_y_size": int(block_y_size),
        "overview_count": int(band.GetOverviewCount()),
        "file_bytes": _raster_source_byte_size(warp_input),
    }
    band = None
    dataset = None
    return record


def _raster_source_is_stripped(source):
    """A STRIPPED raster: its block is as wide as the raster itself
    (#158 -- WA_NorthEast_B22's 2000 x 1 DEFLATE strips), so decoding
    ANY pixel decodes the whole row and a windowed read is never
    cheaper than the file.  A 256 x 256 tiled Cloud-Optimized GeoTIFF is
    not: the window read is what it was built for."""
    width = source.get("raster_x_size")
    block_x_size = source.get("block_x_size")
    if not width or not block_x_size:
        return False
    return int(block_x_size) >= int(width) > 1


def _inspect_and_screen_raster_sources(definition, sources, warp_input_for):
    """Read every source's header (grid, CRS, height unit) and keep the
    lidar-class ones: ``(kept, excluded)``.  A header that cannot be read
    is network-shaped (the listing named it) -> TRANSIENT."""
    from concurrent.futures import ThreadPoolExecutor

    limit = _parse_float(definition.get("max_source_resolution_m"),
                         default=None)

    def _read(source):
        try:
            with gdal.config_options({
                    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff"}):
                return _inspect_raster_source(warp_input_for(source))
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=_SOURCE_INSPECTION_WORKERS) as pool:
        answers = list(pool.map(_read, sources))
    kept = []
    excluded = []
    for (source, answer) in zip(sources, answers):
        if answer is None or isinstance(answer, Exception):
            raise TransientFetchError(
                "%s: header of %s could not be read: %s"
                % (definition.get("code"), source.get("source_id"), answer))
        source = dict(source, **answer)
        if limit is not None and answer["native_resolution_m"] > limit:
            excluded.append(source)
        else:
            kept.append(source)
    return kept, excluded


def _metre_scaled_vrt(warp_input, z_to_m, vrt_path):
    """A local VRT over ``warp_input`` whose heights read in METRES
    (``ScaleRatio`` = metres per unit; NoData passes unscaled)."""
    os.makedirs(os.path.dirname(vrt_path) or ".", exist_ok=True)
    dataset = gdal.Translate(
        vrt_path, warp_input,
        options=gdal.TranslateOptions(
            format="VRT", outputType=gdal.GDT_Float32,
            scaleParams=[[0.0, 1.0, 0.0, float(z_to_m)]]))
    if dataset is None:
        raise TransientFetchError("could not open %s to scale its heights"
                                  % warp_input)
    dataset = None
    return vrt_path


def _source_probe_box(source, bounding_box_wgs84):
    """The part of the request box a source's listed footprint covers
    (the whole box when the listing gave no footprint)."""
    box = source.get("bounding_box")
    if not isinstance(box, dict):
        return bounding_box_wgs84
    try:
        (west, south, east, north) = bounding_box_wgs84
        west = max(west, float(box["minX"]))
        south = max(south, float(box["minY"]))
        east = min(east, float(box["maxX"]))
        north = min(north, float(box["maxY"]))
    except (KeyError, TypeError, ValueError):
        return bounding_box_wgs84
    if east <= west or north <= south:
        return bounding_box_wgs84
    return (west, south, east, north)


def _source_units_provenance(used, excluded, definition):
    """The record keys of a ``source_units=from_source`` fetch: the
    native resolution READ FROM THE FILES (the coarsest contributing
    product -- the inset is at least that fine everywhere it has data),
    the height units met and how each was decided, and the products
    screened out as coarser than ``max_source_resolution_m``."""
    resolutions = [source["native_resolution_m"] for source in used
                   if source.get("native_resolution_m")]
    units = sorted({"%s (%s)" % (source.get("height_unit"),
                                 source.get("height_unit_rule"))
                    for source in used if source.get("height_unit")})
    record = {
        "native_resolution_m": (max(resolutions) if resolutions
                                else definition.get("native_resolution_m")),
        "native_resolution_range_m": (
            [min(resolutions), max(resolutions)] if resolutions else None),
        "native_resolution_from": "source files",
        "vertical_unit_source": units,
        "heights_converted_to_m": sorted(
            {source.get("height_unit") for source in used
             if source.get("z_to_m") not in (None, 1.0)}),
        "source_crs": sorted({str(source.get("crs")) for source in used}),
    }
    if excluded:
        record["sources_excluded_too_coarse"] = [
            dict(_source_contribution_entry(source),
                 native_resolution_m=source.get("native_resolution_m"))
            for source in excluded
        ]
        record["max_source_resolution_m"] = _parse_float(
            definition.get("max_source_resolution_m"))
    return record


# =====================================================================
# Strategy 1: tnm_cog (TNM Access API -> /vsicurl COG window -> warp)
# =====================================================================
@register_access_strategy("tnm_cog")
class TnmCloudOptimizedGeoTiffStrategy:
    """Fetch United States Geological Survey 3DEP lidar via the National Map.

    Discovery hits the TNM Access API (no authentication) for products
    intersecting the bounding box.  Fetch performs a ranged window read from
    the Cloud-Optimized GeoTIFF on the ``prd-tnm`` S3 bucket through GDAL's
    ``/vsicurl/`` virtual file system and warps the window to EPSG:4326 at
    the requested resolution -- the full source tile (hundreds of megabytes)
    is never downloaded.
    """

    # Windowed /vsicurl reader: gates whole-tile elevation-level overlay use
    # (a whole tile costs only a decimated overview read, not a full campaign).
    supports_wide_area = True

    def discover(self, definition, bounding_box_wgs84):
        import requests

        (west, south, east, north) = bounding_box_wgs84
        template = definition.get("discovery_url_template", "")
        url = (
            template.replace("{west}", repr(west))
            .replace("{south}", repr(south))
            .replace("{east}", repr(east))
            .replace("{north}", repr(north))
        )
        # A DISCOVERY OUTAGE IS NOT A NO-COVERAGE ANSWER (spec SQ3): the
        # transport failure, the 5xx/429 and the non-JSON body all raise
        # transient through the one classifier; only a real answer (a 4xx
        # about this request, or a catalog with no usable items) returns
        # None and is recorded durably.
        items = tnm_listing_items(url, "TNM discovery")
        if items is None:
            return None
        sources = []
        for item in items:
            download_url = item.get("downloadURL") or (
                item.get("urls", {}) or {}
            ).get("TIFF")
            if not download_url:
                continue
            sources.append(
                {
                    "download_url": download_url,
                    "source_id": item.get("sourceId"),
                    "title": item.get("title"),
                    "publication_date": item.get("publicationDate") or "",
                    "bounding_box": item.get("boundingBox"),
                }
            )
        # What this discovery LISTED, kept for the ladder: a rung whose
        # listing yields no usable raster still records it, so the
        # build-time re-check compares like with like (#153).
        self.last_listing = list(sources)
        if not sources:
            if items:
                # The listing named products and none of them carried a
                # download URL: a listing that lost half its fields, not
                # a "no data here" answer.
                raise_transient_discovery_failure(
                    "TNM discovery",
                    "a listing of %d product(s) with no download URL"
                    % len(items),
                )
            return None
        # Newest project first (spec: prefer the newest publicationDate).
        sources.sort(
            key=lambda source: source["publication_date"], reverse=True
        )
        return sources

    #: A listed product whose URL ends in this suffix is an ARCHIVE, not a
    #: raster (#157: TNM serves the NED 1/9 arc-second products as ERDAS
    #: IMAGINE inside a zip).
    ARCHIVE_SUFFIX = ".zip"

    #: The raster member read out of a zipped product, in preference
    #: order: the ``.img`` the NED zips carry, else a GeoTIFF.
    ARCHIVE_MEMBER_PREFERENCE = (".img", ".tif", ".tiff")

    def _warp_input_for(self, source):
        """The GDAL path a discovered source is read through."""
        return "/vsicurl/" + source["download_url"]

    def _is_archive(self, source):
        return str(source.get("download_url") or "").split("?", 1)[
            0].lower().endswith(self.ARCHIVE_SUFFIX)

    def _stage_archives(self, definition, sources, destination_path,
                        scratch_paths):
        """Every ZIPPED listed product (#157), downloaded whole to scratch
        beside the destination; ``{download_url: /vsizip/ member path}``.

        A deflated member cannot be range-read (measured 2026-09-30,
        KGRK's 1/9 arc-second zip: the central directory lists in one
        range read, 0.8 s, but merely OPENING the 200 MB ``.img`` through
        ``/vsizip//vsicurl/`` streamed for 57 s), so the archive comes
        whole through :func:`download_zip_whole` -- the module's one
        whole-archive download -- and its raster member is chosen by
        :func:`archive_raster_members` in :attr:`ARCHIVE_MEMBER_PREFERENCE`
        order.  A listed archive that is not on the server (404) or holds
        no raster member is ``unavailable`` -- never a no-coverage answer;
        the scratch paths are appended to ``scratch_paths`` BEFORE the
        download so the caller's ``finally`` removes a partial one.
        """
        staged = {}
        archives = [source for source in sources if self._is_archive(source)]
        if not archives:
            return staged
        code = definition.get("code")
        airport = _las_airport_label(destination_path)
        os.makedirs(os.path.dirname(destination_path) or ".", exist_ok=True)
        for (number, source) in enumerate(archives):
            scratch_path = "%s.tnm%d%s" % (destination_path, number,
                                            self.ARCHIVE_SUFFIX)
            scratch_paths.append(scratch_path)
            UI.vprint(1, "    [inset] %s %s: zipped product %d/%d %s - "
                      "downloading whole (a zipped raster cannot be "
                      "window-read)" % (airport, code, number + 1,
                                        len(archives), source.get(
                                            "source_id")))
            if not download_zip_whole(
                    definition, source, scratch_path, None,
                    "%s %s archive %d/%d %s" % (
                        airport, code, number + 1, len(archives),
                        source.get("source_id"))):
                raise ProviderUnavailable(
                    "%s: listed product %s is not on the server (HTTP 404) "
                    "- %s" % (code, source.get("source_id"),
                              source["download_url"]))
            members = list(archive_raster_members(
                "/vsizip/" + scratch_path, self.ARCHIVE_MEMBER_PREFERENCE))
            chosen = None
            for suffix in self.ARCHIVE_MEMBER_PREFERENCE:
                chosen = next((member for member in members
                               if member.lower().endswith(suffix)), None)
                if chosen is not None:
                    break
            if chosen is None:
                raise ProviderUnavailable(
                    "%s: listed product %s is a zip with no raster member "
                    "(%s) - %s" % (code, source.get("source_id"),
                                   "/".join(self.ARCHIVE_MEMBER_PREFERENCE),
                                   source["download_url"]))
            staged[source["download_url"]] = chosen
        return staged

    def _prefetch_whole_stripped_sources(self, definition, sources,
                                         warp_input_for, destination_path,
                                         scratch_paths):
        """Every STRIPPED listed product downloaded WHOLE into scratch
        beside the destination, over the provider's fetch slots;
        ``({download_url: local path}, record)``; the map is empty
        when nothing stripped is remote, when a size could not be read,
        or when the bytes exceed the prefetch threshold, and the record
        says which of those happened (it becomes the provenance keys --
        without them a manifest reader cannot tell a 13-minute windowed
        fetch from a prefetched one, which is the whole question #158
        asks).

        WHY (#158, measured 2026-10-02 against a loopback server over a
        synthetic WA_NorthEast_B22 layout: 4 stripped tiles, 2000 x 2000
        px at 0.5 m in a State Plane foot CRS, 2000 x 1 DEFLATE strips,
        no overviews, 10.3 MB each).  The windowed ``/vsicurl`` warp
        issued 6.5 requests per tile and moved 1.14x (a 20 % x 20 % box)
        to 2.00x (the full box) the tiles' WHOLE bytes -- NEVER less
        than the files, whatever the window's shape, because a strip as
        wide as the raster must be decoded whole for any pixel in it.
        One whole GET per tile moves 1.00x in ONE request, and the warp
        then reads local files: 4 requests and 41.3 MB against 26
        requests and 67.3 MB, with byte-identical output (twin).

        Tiled Cloud-Optimized GeoTIFFs stay on ``/vsicurl``: a 256 x 256
        block IS the window read the strategy was built for, and the
        field numbers back it (PANC's 68 tiled COGs in 1:56 against
        KGEG's 64 stripped tiles in 13:42).

        The byte threshold is judged BEFORE any GET, and exceeding it is
        NOT the cap class (RULINGS 2026-09-30bm): ``/vsicurl`` is a
        complete and correct fetch of the same window, so the threshold
        switches strategy and SAYS SO on one line -- it never refuses a
        provider that would otherwise deliver.  A listed tile the server
        does not have (404) is ``unavailable``, exactly as a listed
        archive is in :meth:`_stage_archives`; a 5xx is transient and
        the caller's ``finally`` removes every partial scratch file.

        Only a source the warp would read THROUGH CURL is a candidate: a
        staged archive member and a local scratch file are already on
        this disk, and "downloading" one would be a copy with a GET
        bolted to it.
        """
        code = definition.get("code")
        airport = _las_airport_label(destination_path)
        remote = [source for source in sources
                  if str(warp_input_for(source)).startswith("/vsicurl/")
                  and _raster_source_is_stripped(source)]
        stripped = [source for source in remote if source.get("file_bytes")]
        unsized = [source for source in remote
                   if not source.get("file_bytes")]
        # Counted BEFORE the switch, so a manifest reader can see that
        # this fetch had stripped products and did not prefetch them.
        record = {"sources_stripped": len(remote),
                  "sources_prefetched_whole": 0,
                  "prefetched_whole_bytes": 0}
        if not _parse_boolean(definition.get("prefetch_whole_stripped",
                                             "True")):
            record["prefetch_whole_skipped"] = "prefetch_whole_stripped=False"
            return ({}, record)
        if unsized:
            # The threshold must be judged before any GET, and a source
            # whose size nobody could read cannot be judged: it stays on
            # the windowed read rather than be prefetched unbounded.
            UI.vprint(1, "    [inset] %s %s: %d stripped tile(s) report no "
                      "size - left on the windowed /vsicurl read (the "
                      "prefetch threshold must be judged before any GET)"
                      % (airport, code, len(unsized)))
            record["prefetch_whole_skipped"] = (
                "%d stripped tile(s) report no size" % len(unsized))
        if not stripped:
            return ({}, record)
        threshold = _parse_float(definition.get("prefetch_whole_max_bytes"),
                                 default=PREFETCH_WHOLE_MAX_BYTES)
        total_bytes = sum(int(source["file_bytes"]) for source in stripped)
        if threshold and total_bytes > threshold:
            UI.vprint(1, "    [inset] %s %s: %d stripped tile(s) = %s exceed "
                      "the %s whole-tile prefetch threshold "
                      "(prefetch_whole_max_bytes in %s.elv) - reading the "
                      "window through /vsicurl instead"
                      % (airport, code, len(stripped),
                         _las_size_text(total_bytes),
                         _las_size_text(threshold), code))
            record["prefetch_whole_skipped"] = (
                "%s over the %s prefetch_whole_max_bytes threshold"
                % (_las_size_text(total_bytes), _las_size_text(threshold)))
            return ({}, record)
        slots = provider_fetch_slots(definition)
        UI.vprint(1, "    [inset] %s %s: prefetching %d stripped tile(s) "
                  "WHOLE (%s) over %d connection(s) - a strip as wide as "
                  "the raster cannot be window-read (#158)"
                  % (airport, code, len(stripped),
                     _las_size_text(total_bytes), slots))
        os.makedirs(os.path.dirname(destination_path) or ".", exist_ok=True)
        wanted = []
        for (number, source) in enumerate(stripped):
            scratch_path = "%s.prefetch%d.tif" % (destination_path, number)
            # Appended BEFORE the GET so the caller's ``finally`` removes
            # a partial file (the #157 pattern).
            scratch_paths.append(scratch_path)
            wanted.append((number, source, scratch_path))

        def _download(item):
            (number, source, scratch_path) = item
            label = "%s %s stripped tile %d/%d %s" % (
                airport, code, number + 1, len(wanted),
                source.get("source_id"))
            with _held_provider_fetch_slot(code, slots):
                return download_whole(definition, source, scratch_path,
                                      label)

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=slots) as pool:
            results = list(pool.map(_download, wanted))
        prefetched = {}
        for ((_number, source, scratch_path), present) in zip(wanted,
                                                              results):
            if not present:
                raise ProviderUnavailable(
                    "%s: listed product %s is not on the server (HTTP 404) "
                    "- %s" % (code, source.get("source_id"),
                              source["download_url"]))
            prefetched[source["download_url"]] = scratch_path
        record["sources_prefetched_whole"] = len(prefetched)
        record["prefetched_whole_bytes"] = total_bytes
        record["prefetch_whole_slots"] = slots
        record.pop("prefetch_whole_skipped", None)
        return (prefetched, record)

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
        try:
            staged = self._stage_archives(definition, sources,
                                          destination_path, scratch_paths)

            def warp_input_for(source):
                return (staged.get(source.get("download_url"))
                        or self._warp_input_for(source))

            return self._fetch_listed(
                definition, sources, warp_input_for, bounding_box_wgs84,
                target_resolution_m, destination_path, scratch_paths)
        finally:
            for path in scratch_paths:
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:                      # pragma: no cover
                        pass

    def _fetch_listed(self, definition, sources, warp_input_for,
                      bounding_box_wgs84, target_resolution_m,
                      destination_path, scratch_paths=None):
        """The warp + record of the listed ``sources``; each is read
        through ``warp_input_for`` (a whole tile prefetched into
        scratch, else a staged archive member, else
        :meth:`_warp_input_for`)."""
        # R13-2 -- EVERY PIXEL TAKES THE NEWEST SOURCE WITH VALID DATA
        # THERE.  Keeping only the newest publication date is what lost
        # KMCI: a Missouri airport whose box straddles the state line took
        # the Kansas 2018 tiles WHOLESALE because they published latest,
        # and the assembled inset was 7993 x 10518 pixels of 100.00 %
        # nodata that every extent-based coverage answer called full.
        # Every discovered source now enters one mosaic, OLDEST FIRST:
        # gdal.Warp masks a source's own nodata out of the warp, so a
        # later -- newer -- input wins wherever it HAS data and leaves
        # what it does not have to the older source underneath (measured
        # 2026-08-11: two synthetic sources, newer nodata over the east
        # half, assembled 0.0 % nodata with each half from the right
        # source).  A project that is empty over the box therefore
        # contributes nothing instead of erasing everything.  The source
        # count stays whatever discovery returned: no new network reach.
        _refuse_mixed_vertical_datums(definition, sources)
        from_source = _definition_reads_source_units(definition)
        excluded = []
        scratch_inputs = []
        prefetched = {}
        prefetch_record = {}
        warp_configuration = None
        if from_source:
            # ORIGINAL PRODUCT RESOLUTION (#153): each product carries
            # its own grid, CRS and HEIGHT UNIT (Fairbanks 2017 is
            # posted in US survey feet with no vertical CRS; Montana
            # DNRC declares a NAVD88-in-feet compound CRS), so the
            # header of every source is read and a source in feet is
            # warped through a metre-scaling VRT.  A product coarser
            # than ``max_source_resolution_m`` (the 5 m Alaska IFSAR
            # DTMs TNM lists in the same dataset) is not lidar-class
            # and stays out of the mosaic.
            sources, excluded = _inspect_and_screen_raster_sources(
                definition, sources, warp_input_for)
            if not sources:
                return None
            # STRIPPED products come WHOLE (#158): the headers just read
            # say which are, so the switch costs no extra request.  The
            # local files then serve BOTH the warp and the per-source
            # contribution probe below.
            (prefetched, prefetch_record) = (
                self._prefetch_whole_stripped_sources(
                    definition, sources, warp_input_for, destination_path,
                    scratch_paths if scratch_paths is not None else []))
            if prefetched:
                remote_input_for = warp_input_for

                def warp_input_for(source):                  # noqa: F811
                    return (prefetched.get(source.get("download_url"))
                            or remote_input_for(source))
        oldest_first = list(reversed(sources))   # discover sorts newest first
        warp_inputs = []
        for source in oldest_first:
            warp_input = warp_input_for(source)
            z_to_m = source.get("z_to_m")
            if from_source and z_to_m not in (None, 1.0):
                warp_input = _metre_scaled_vrt(
                    warp_input, z_to_m,
                    "%s.src%d.vrt" % (destination_path, len(scratch_inputs)))
                scratch_inputs.append(warp_input)
            warp_inputs.append(warp_input)
        if scratch_inputs:
            # The local VRTs hide the remote extensions from the warp's
            # derived fence: name it here.
            warp_configuration = {
                "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.vrt"}

        failure_reasons = []
        try:
            warped = warp_vsicurl_sources_to_geotiff(
                warp_inputs,
                bounding_box_wgs84,
                target_resolution_m,
                destination_path,
                value_floor_m=float(definition.get("value_floor_m", -600.0)),
                vertical_unit=_raster_vertical_unit(definition),
                provider_code=definition.get("code"),
                gdal_configuration_options=warp_configuration,
                failure_reasons=failure_reasons,
            )
        finally:
            for path in scratch_inputs:
                if os.path.isfile(path):
                    os.remove(path)
        if not warped:
            # A LISTED product the engine could not decode is no answer
            # about coverage (#157, RULINGS 2026-09-13b): ``unavailable``
            # with the reason -- the ladder climbs and the re-check asks
            # again -- never the durable no-coverage a ``None`` records.
            raise ProviderUnavailable(
                "%s: %d listed product(s) could not be read (%s)"
                % (definition.get("code"), len(warp_inputs),
                   "; ".join(failure_reasons) or "the warp failed"))

        # R13-3 -- THE RECORD NAMES ITS SOURCES, PER CONTRIBUTION.  Which
        # project answered here, and which one was merely overhead, is the
        # question nobody could ask of the old record: KMCI's named three
        # Kansas tiles and looked like a successful fetch.
        used = []
        empty = []
        for source in sources:                  # newest first, as recorded
            if _source_holds_data_over_bbox(
                warp_input_for(source),
                _source_probe_box(source, bounding_box_wgs84)
                if from_source else bounding_box_wgs84,
                samples=(_SOURCE_FOOTPRINT_PROBE_SAMPLES if from_source
                         else _SOURCE_CONTRIBUTION_PROBE_SAMPLES),
            ):
                used.append(source)
            else:
                empty.append(source)
        # The flat ``source_*`` keys every older reader knows (the R11
        # empty-inset line reads ``project_titles``) name what
        # CONTRIBUTED; with nothing valid anywhere they name what was
        # tried, so an empty record still says which project produced it.
        recorded = used or sources
        valid_fraction = inset_valid_fraction(destination_path)
        projects = sorted(
            {_tnm_project_of(source["title"], source.get("download_url"))
             for source in used}
        )
        if len(projects) > 1:
            UI.vprint(
                0,
                "   [inset] %s: border-aware mosaic - %d source(s) across "
                "%d project(s), valid %.1f %%"
                % (os.path.basename(destination_path), len(used),
                   len(projects), 100.0 * valid_fraction),
            )

        provenance = {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [source["download_url"] for source in recorded],
            "source_ids": [source["source_id"] for source in recorded],
            "project_titles": [source["title"] for source in recorded],
            "publication_date": recorded[0]["publication_date"],
            "sources_used": [
                _source_contribution_entry(source) for source in used
            ],
            "sources_empty_over_bbox": [
                _source_contribution_entry(source) for source in empty
            ],
            "valid_fraction": round(valid_fraction, 6),
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "datum_note": (
                "Elevations are in the source vertical datum; lidar is "
                "treated as truth and is NOT shifted toward the base DEM."
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
        if from_source:
            provenance.update(
                _source_units_provenance(used or sources, excluded,
                                         definition))
            provenance.update(prefetch_record)
        return provenance
