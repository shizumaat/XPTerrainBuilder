"""Regional OpenStreetMap extracts: the local-first OSM data backend.

Serves the per-tile OSM layer caches from Geofabrik regional extracts
(daily ``.osm.pbf`` snapshots on a plain HTTPS CDN, no rate limits)
instead of querying public Overpass servers, which are shared query
infrastructure and throttle exactly the bulk-extraction workload a
batch tile build produces (docs/specs/osm-regional-extracts-spec.md).

Life cycle, designed so users never manage it by hand:

* Nothing downloads up front.  The first build touching a region
  downloads its extract IN THE FOREGROUND (owner ruling 2026-07-18:
  the Geofabrik CDN serves a whole country in about the time ONE
  throttled Overpass query round takes — measured HECA: the lazy
  fallback spent 21 minutes on Overpass while egypt.osm.pbf landed 60
  seconds after the build needed it) and then serves the build locally.
  ``osm_extract_foreground_download=False`` restores the previous lazy
  behaviour: record the region as wanted (``wanted.json``), use
  Overpass this once, and let the maintenance thread download it.
* :func:`start_background_maintenance` (called once at application
  start — Qt or CLI, never by parallel-build worker children) refreshes
  the region index when stale, re-downloads extracts older than the
  ``osm_extract_refresh_days`` setting, and drains the wanted list on a
  rescan loop.  Every transfer goes through ``O4_Download_Manager``: one
  per region across all processes, whoever asks.

Failure discipline: this backend is an accelerator, never a
dependency.  Every public entry point swallows its own errors and
returns ``None`` / no-ops, leaving the historic Overpass path exactly
as it was.  No GUI-toolkit imports (core-module rule).
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from typing import Optional

import O4_Download_Manager as DOWNLOADS
import O4_File_Names as FNAMES
import O4_Step_Wait as STEP_WAIT
import O4_UI_Utils as UI
import requests

INDEX_URL = "https://download.geofabrik.de/index-v1.json"
INDEX_REFRESH_DAYS = 7.0
DEFAULT_EXTRACT_REFRESH_DAYS = 180.0
WANTED_RESCAN_SECONDS = 60.0
DOWNLOAD_PROGRESS_EVERY_BYTES = 50 << 20
# ...and at least this often while bytes arrive (#2299: at ~2 MB/min the
# byte cadence alone left a build silent for 25 minutes and the app read
# it as stuck); a joiner waiting on another tile's download says so too.
DOWNLOAD_PROGRESS_EVERY_SECONDS = 10.0
HTTP_TIMEOUT_SECONDS = 60
# An extract address that answered 404 is not asked again for this long
# (#2201), and a 404 re-reads the index only when the stored one is
# older than NOT_FOUND_INDEX_FRESH_SECONDS (a fresh index that still
# 404s means Geofabrik publishes nothing there).
# #2299: a day, never a week -- an address is asked again the next day
# (a week-long entry blocked Oregon's extract for every build).
NOT_FOUND_RETRY_DAYS = 1.0
# A 404 reached through a redirect (Geofabrik -latest answers 307 to a
# dated file that is briefly 404 while the region regenerates), or one no
# fresh index confirmed, is transient: asked again after this.
NOT_FOUND_TRANSIENT_HOURS = 6.0
NOT_FOUND_INDEX_FRESH_SECONDS = 3600.0

# Module-level and mutable so tests monkeypatch it at a tmp_path.
STORE_DIRECTORY = os.path.join(FNAMES.OSM_dir, "_regional_extracts")

_maintenance_started = threading.Event()
_store_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def _setting(name: str, default):
    """The setting ``name``, ``default`` when it cannot be read.

    From ``O4_Config_Utils`` once that module has it.  Before then (the
    engine starts extract maintenance before it loads the configuration)
    from the global config file: importing ``O4_Config_Utils`` here would
    trigger its side effects (global config creation) from a passive
    check, and assuming the default contacted Geofabrik with the backend
    switched off."""
    try:
        CFG = sys.modules.get("O4_Config_Utils")
        if CFG is not None and hasattr(CFG, name):
            return type(default)(getattr(CFG, name))
        import O4_Settings_Model as SETTINGS

        (ok, text, _error) = SETTINGS.coerce(
            name, SETTINGS.global_effective_value(name))
        if not ok:
            return default
        return text == "True" if isinstance(default, bool) else float(text)
    except Exception:
        return default


def extracts_enabled() -> bool:
    """The ``osm_regional_extracts`` setting (True when unavailable)."""
    return _setting("osm_regional_extracts", True)


def _extract_refresh_days() -> float:
    return _setting("osm_extract_refresh_days", DEFAULT_EXTRACT_REFRESH_DAYS)


def foreground_download_enabled() -> bool:
    """The ``osm_extract_foreground_download`` setting (True when
    unavailable)."""
    return _setting("osm_extract_foreground_download", True)


# ---------------------------------------------------------------------------
# Store primitives (all JSON writes atomic: temp + os.replace)
# ---------------------------------------------------------------------------
def _store_path(*names: str) -> str:
    return os.path.join(STORE_DIRECTORY, *names)


def _read_json(path: str):
    try:
        with open(path) as json_file:
            return json.load(json_file)
    except Exception:
        return None


def _write_json_atomic(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary_path = _private_temporary(path)
    with open(temporary_path, "w", newline="\n") as json_file:
        json.dump(payload, json_file, indent=1)
    os.replace(temporary_path, path)


def _private_temporary(path: str) -> str:
    """A sibling only this thread writes: several processes rewrite the
    store's JSON files."""
    return "%s.tmp-%d-%d" % (path, os.getpid(), threading.get_ident())


def _region_file(region_id: str) -> str:
    # Region ids may carry a path ("us/california"); flatten for storage.
    return _store_path(region_id.replace("/", "__") + ".osm.pbf")


def record_wanted_regions(region_ids) -> None:
    """Append regions to the wanted list (any process may call this)."""
    with _store_lock:
        wanted = _read_json(_store_path("wanted.json")) or []
        merged = sorted(set(wanted) | set(region_ids))
        if merged != sorted(wanted):
            _write_json_atomic(_store_path("wanted.json"), merged)


def _consume_wanted_regions() -> list:
    with _store_lock:
        wanted = _read_json(_store_path("wanted.json")) or []
        if wanted:
            _write_json_atomic(_store_path("wanted.json"), [])
    return list(wanted)


# ---------------------------------------------------------------------------
# Region index
# ---------------------------------------------------------------------------
def _index_path() -> str:
    return _store_path("index-v1.json")


def _index_is_stale() -> bool:
    """True when the stored region index is due to be asked for again.

    OWNER RULINGS 2026-11-13o (#2050): OpenStreetMap data is not even
    CHECKED until the user's cache expiry has passed — the index is
    re-asked only when older than ``osm_extract_refresh_days`` (never
    sooner than :data:`INDEX_REFRESH_DAYS`), the same age the extracts
    themselves are re-downloaded at.  A missing index is asked at once."""
    try:
        age_seconds = time.time() - os.path.getmtime(_index_path())
        return age_seconds > max(INDEX_REFRESH_DAYS,
                                 _extract_refresh_days()) * 86400
    except OSError:
        return True


def _refresh_index() -> bool:
    try:
        UI.vprint(1, "   Refreshing the Geofabrik region index...")
        response = requests.get(INDEX_URL, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()          # validates before storing
        os.makedirs(STORE_DIRECTORY, exist_ok=True)
        temporary_path = _private_temporary(_index_path())
        with open(temporary_path, "w", newline="\n") as index_file:
            json.dump(payload, index_file)
        os.replace(temporary_path, _index_path())
        _leaf_regions.cache = None
        return True
    except Exception as error:
        UI.vprint(1, "   Geofabrik index refresh failed:", str(error))
        return False


def _leaf_regions() -> Optional[list]:
    """[(region_id, pbf_url, shapely geometry)] for index leaves, cached.

    Leaves are regions that are no other region's parent — the finest
    partition Geofabrik offers (states where they exist, countries
    elsewhere).  ``None`` when no index is stored yet.
    """
    cached = getattr(_leaf_regions, "cache", None)
    if cached is not None:
        return cached
    index = _read_json(_index_path())
    if not index:
        return None
    try:
        from shapely.geometry import shape

        features = index.get("features", [])
        parents = {
            (feature.get("properties") or {}).get("parent")
            for feature in features
        }
        (leaves, parent_regions) = ([], [])
        for feature in features:
            properties = feature.get("properties") or {}
            region_id = properties.get("id")
            pbf_url = (properties.get("urls") or {}).get("pbf")
            if not region_id or not pbf_url:
                continue
            try:
                region_geometry = shape(feature["geometry"])
            except Exception:
                continue
            (parent_regions if region_id in parents else leaves).append(
                (region_id, pbf_url, region_geometry))
        _leaf_regions.parents = parent_regions
        _leaf_regions.cache = leaves
        return leaves
    except Exception:
        return None


def _parent_regions() -> list:
    """[(region_id, pbf_url, geometry)] for the index's PARENT regions
    (those some leaf names as parent), parsed with :func:`_leaf_regions`."""
    if _leaf_regions() is None:
        return []
    return getattr(_leaf_regions, "parents", [])


# The largest parent region (polygon area, degrees squared) that may
# serve a box whose leaves miss land (#1731, owner 2026-10-31 "(b)").
# Index polygon area is the size proxy (the index carries no pbf
# sizes).  1500 admits country/sub-continent parents — central-america
# 663, china 1077, brazil 1189, nunavut 1267 — and refuses every
# continent-scale extract: canada 3070, europe 3170, russia 5526 and
# the continents above (south-america 6343 ... asia 11756).
PARENT_FALLBACK_MAX_AREA = 1500.0


def _parent_cover(bbox_polygon, unknown_land=True) -> Optional[tuple]:
    """(region_id, pbf_url, area, basis) of the smallest parent region,
    within the cap, whose polygon holds every land post of the box —
    or, while the box's land is not known (#2234: no elevation on disk
    yet), the whole box; ``None`` when the box holds no land or no
    lawful parent holds it.

    ``unknown_land=False`` takes the whole-box parent only when it is
    stored already (#2218 (2): TLPL's reef box fetched the 758 MB
    central-america for land a few MB of elevation could have shown is
    sea); the caller fetches the witness's elevation and asks again."""
    import O4_Land_Witness as LAND
    import shapely

    land = LAND.land_points(bbox_polygon)
    if land is not None and not land[0].size:
        return None
    candidates = sorted(
        (region_geometry.area, region_id, pbf_url, region_geometry)
        for (region_id, pbf_url, region_geometry) in _parent_regions()
        if region_geometry.area <= PARENT_FALLBACK_MAX_AREA
        and region_geometry.intersects(bbox_polygon))
    for (area, region_id, pbf_url, region_geometry) in candidates:
        holder = region_geometry.intersection(
            bbox_polygon.buffer(2 * _COVERAGE_BUFFER_DEGREES)
        ).buffer(_COVERAGE_BUFFER_DEGREES)
        if land is None:
            if holder.contains(bbox_polygon) and (
                    unknown_land
                    or not _stored_regions_missing([(region_id, pbf_url)])):
                return (region_id, pbf_url, area, "all of it")
        elif shapely.contains_xy(holder, *land).all():
            return (region_id, pbf_url, area, "all of its land")
    return None


def _parent_cover_reason(parent, lead: str) -> str:
    return (f"{lead}; {parent[0]} is the smallest parent region holding"
            f" {parent[3]} ({parent[2]:.0f} deg2, cap"
            f" {PARENT_FALLBACK_MAX_AREA:.0f})")


def _cover_beyond_leaves(bounding_box, bbox_polygon,
                         unknown_land_parent=True) -> Optional[list]:
    """The cover of a box no leaf extract reaches: the smallest lawful
    parent holding it, or NO region (an empty answer) when the box
    holds no land; ``None`` (Overpass) when neither can be shown."""
    import O4_Land_Witness as LAND

    parent = _parent_cover(bbox_polygon, unknown_land_parent)
    if parent is not None:
        _log_cover_reason(
            bounding_box,
            _parent_cover_reason(parent, "no leaf extract reaches it"),
            verdict="uses a parent regional extract")
        return [(parent[0], parent[1])]
    land = LAND.holds_land(bbox_polygon)
    if land is False:
        _log_cover_reason(
            bounding_box,
            "no regional extract reaches it and elevation shows it holds"
            " no land", verdict="is served as an empty answer")
        return []
    _log_cover_reason(
        bounding_box,
        "no regional extract reaches it"
        + (" and no lawful parent region holds its land" if land else
           ", no parent region holds it and no cached elevation shows"
           " it is sea"))
    return None


# Region-boundary tolerance for coverage tests, in degrees (~1 km):
# Geofabrik region polygons are simplified and sea-buffered, so
# adjacent regions' shared borders never coincide exactly.
_COVERAGE_BUFFER_DEGREES = 0.01
# A region whose unique contribution to the bbox is below this area
# (degrees squared, float-dust scale) duplicates the other selected
# regions and is pruned.
_REDUNDANT_COVER_AREA = 1e-9


_logged_cover_reasons: set = set()


def _log_cover_reason(bounding_box, reason: str,
                      verdict: str = "uses Overpass, not a regional extract"
                      ) -> None:
    """One log line per box and reason: why it is (not) extract-served."""
    key = (tuple(round(float(v), 3) for v in bounding_box), reason)
    if key in _logged_cover_reasons:
        return
    _logged_cover_reasons.add(key)
    UI.vprint(1, "      OSM box", key[0], verdict + ":", reason + ".")


def covering_regions(bounding_box, unknown_land_parent=True
                     ) -> Optional[list]:
    """[(region_id, pbf_url)] of leaves covering the bbox, or ``None``.

    ``unknown_land_parent=False`` (the build's first ask, #2218 (2)): a
    parent region not stored yet is not chosen for land the witness does
    not know — ``None`` instead, so the caller fetches the elevation that
    decides it and asks again (:func:`_parent_cover`).

    An EMPTY list means the box lies beyond every leaf, no parent holds
    it and the land witness shows it holds no land: it is served as an
    empty answer, never from Overpass (RULINGS 2026-11-24h).

    ``bounding_box`` is (lat_min, lon_min, lat_max, lon_max).  ``None``
    means the tile is not extract-servable: no index yet, or the
    intersecting leaves leave more than a sliver of it uncovered and
    the offline land witness cannot show that remainder is sea (index
    gaps, an uncached DEM) — the caller keeps using Overpass.  Where
    that remainder holds land, the smallest parent region under
    ``PARENT_FALLBACK_MAX_AREA`` holding all the box's land serves it
    alone (Turks and Caicos: only ``central-america`` has it).

    The result is a MINIMAL cover, not every intersecting leaf: the
    Geofabrik index declares each United States state's parent as
    ``north-america`` rather than ``us``, so the aggregate ``us``
    extract (11 GB) and the grouping extracts (``us-pacific``, ...)
    pass the leaf test alongside the states that duplicate them (the
    same pattern covers ``great-britain`` over the English counties).
    Every selected region is read end-to-end on every query, so
    redundant covers are pruned, largest first: a region is kept only
    for bbox area no other kept region serves (a Whitehorse masks
    query, 2026-07-18, selected yukon + north-admreg + us/alaska AND
    the duplicate us + us-pacific — an eight-minute filtering stall
    and a 12 GB download for data the us/alaska extract already
    served).
    """
    leaves = _leaf_regions()
    if leaves is None:
        return None
    try:
        from shapely.geometry import box
        from shapely.ops import unary_union

        (lat_min, lon_min, lat_max, lon_max) = bounding_box
        bbox_polygon = box(lon_min, lat_min, lon_max, lat_max)
        intersecting = [
            (region_id, pbf_url, region_geometry)
            for (region_id, pbf_url, region_geometry) in leaves
            if region_geometry.intersects(bbox_polygon)
        ]
        if not intersecting:
            return _cover_beyond_leaves(bounding_box, bbox_polygon,
                                        unknown_land_parent)
        # All coverage arithmetic happens inside the bbox neighbourhood,
        # so clip once: region polygons carry whole coastlines the
        # repeated buffer/difference calls below must not chew through.
        bbox_neighbourhood = bbox_polygon.buffer(
            2 * _COVERAGE_BUFFER_DEGREES)
        clipped = {
            region_id: region_geometry.intersection(bbox_neighbourhood)
            for (region_id, _u, region_geometry) in intersecting
        }
        # Reverse-delete pruning, largest region first (geometry area is
        # the proxy for extract size: the index carries no pbf sizes), so
        # aggregates fall before the smaller regions that duplicate them.
        # A region whose unique part of the box is SEA serves no land the
        # others miss and falls too (#1735): a grouping region's polygon
        # is sea-buffered wider than its leaves', and on a coastal box
        # that buffer alone kept the 6 GB dach over the German states.
        import O4_Land_Witness as LAND

        intersecting.sort(
            key=lambda entry: (-entry[2].area, entry[0]))
        kept = list(intersecting)
        for entry in intersecting:
            if len(kept) == 1:
                break
            (region_id, _url, _geometry) = entry
            others = unary_union([
                clipped[other_id]
                for (other_id, _u, _g) in kept if other_id != region_id
            ])
            unique = clipped[region_id].intersection(bbox_polygon) \
                .difference(others.buffer(_COVERAGE_BUFFER_DEGREES))
            if (unique.area <= _REDUNDANT_COVER_AREA
                    or LAND.holds_land(unique) is False):
                kept.remove(entry)
        union = unary_union(
            [clipped[region_id] for (region_id, _u, _g) in kept]
        )
        # Residue the leaves do not cover is OPEN OCEAN by construction
        # (Geofabrik regions jointly cover all land, with sea buffers),
        # and no extract exists for it — so a small residue must not
        # disqualify local serving (the Strait of Gibraltar tile's
        # margined queries poke ~0.02 deg2 of Atlantic).  A LARGE
        # residue means a hole in the index (a region missing) — keep
        # the Overpass fallback there rather than silently losing data.
        uncovered = bbox_polygon.difference(
            union.buffer(_COVERAGE_BUFFER_DEGREES))
        if uncovered.area > 0.10 * bbox_polygon.area:
            # An island or coastal box: most of it is sea outside every
            # region polygon.  Serve it locally only when the offline
            # land witness (#1731) says that remainder holds no land.
            land = LAND.holds_land(uncovered)
            share = round(100 * uncovered.area / bbox_polygon.area)
            parent = (_parent_cover(bbox_polygon, unknown_land_parent)
                      if land is not False else None)
            if parent is not None:
                _log_cover_reason(
                    bounding_box,
                    _parent_cover_reason(
                        parent,
                        f"{share}% of it lies outside every leaf extract"
                        + (" and holds land" if land else
                           " and no cached elevation shows it is sea")),
                    verdict="uses a parent regional extract")
                return [(parent[0], parent[1])]
            if land is not False:
                _log_cover_reason(
                    bounding_box,
                    f"{share}% of it lies outside every regional extract"
                    + (" and holds land" if land else
                       " and no cached elevation shows it is sea"))
                return None
            _log_cover_reason(
                bounding_box,
                f"{round(100 * uncovered.area / bbox_polygon.area)}% of it"
                " lies outside them and cached elevation shows it is sea",
                verdict="can use regional extract(s)")
        return sorted(
            (region_id, pbf_url) for (region_id, pbf_url, _g) in kept
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# The build-time entry point
# ---------------------------------------------------------------------------
# A pbf file's first blob is its header blob: a four-byte length, then
# a BlobHeader whose type string "OSMHeader" sits within the first few
# dozen bytes.  An HTML "not found" page served with HTTP 200 — the
# live enfield.osm.pbf case, 2026-07-17: the Geofabrik index lists
# regions whose download address serves a web page — has neither.
_PBF_MAGIC_PROBE_BYTES = 64


def _file_looks_like_pbf(path: str) -> bool:
    try:
        with open(path, "rb") as pbf_file:
            head = pbf_file.read(_PBF_MAGIC_PROBE_BYTES)
        return b"OSMHeader" in head
    except OSError:
        return False


def _stored_regions_missing(regions) -> list:
    """Region ids not usable from the store.

    Absent files are missing; a present file that is not actually pbf
    data (a poisoned download from before content validation) is
    DELETED on sight and reported missing, so the wanted/maintenance
    path can retry and every consumer falls back to Overpass instead
    of erroring on it forever.
    """
    missing = []
    for (region_id, _url) in regions:
        path = _region_file(region_id)
        if not os.path.isfile(path):
            missing.append(region_id)
            continue
        if not _file_looks_like_pbf(path):
            UI.vprint(
                1,
                "      Stored OSM extract", region_id,
                "is not valid pbf data; removing it.",
            )
            try:
                os.remove(path)
            except OSError:
                pass
            missing.append(region_id)
    return missing


def local_extracts_cover(bounding_box) -> bool:
    """True when every region covering the box is stored locally.

    An OSM request for such a box is served entirely from the local
    extracts — no Overpass involvement — so callers whose only purpose
    is sparing the Overpass servers (the parallel-run cache warmer)
    have nothing to do for it.  Never raises; any failure reads as
    "not covered".
    """
    try:
        if not extracts_enabled():
            return False
        regions = covering_regions(bounding_box)
        if regions is None:
            return False
        return not _stored_regions_missing(regions)
    except Exception:
        return False


def _bounding_boxes_list(bounding_box) -> list:
    """Normalize one ``(lat_min, lon_min, lat_max, lon_max)`` box or a
    list of such boxes into a list of boxes."""
    boxes = list(bounding_box)
    # Multi-box form: the first element is itself a box (a sequence),
    # not a coordinate scalar.  Sequence detection (rather than scalar
    # type checks) keeps numpy scalar coordinates classified correctly.
    if boxes and isinstance(boxes[0], (tuple, list)):
        return [tuple(box) for box in boxes]
    return [tuple(boxes)]


def _extract_ready(region_id: str) -> bool:
    path = _region_file(region_id)
    return os.path.isfile(path) and _file_looks_like_pbf(path)


def _extract_resource(region_id: str, url: str) -> DOWNLOADS.Resource:
    """The region's extract as the download manager knows it: one key per
    region, whatever address the index gives it now."""
    return DOWNLOADS.Resource("osm-extract:" + region_id, url,
                              _region_file(region_id), _file_looks_like_pbf)


def extract_download_running(bounding_box) -> bool:
    """Is a region this box needs missing and being downloaded right now?
    The build that needs it joins that transfer; nobody need fetch for it
    ahead of time.  Never raises."""
    try:
        regions = covering_regions(bounding_box) or []
        missing = set(_stored_regions_missing(regions))
        return any(DOWNLOADS.in_flight(_extract_resource(region_id, url or ""))
                   for (region_id, url) in regions if region_id in missing)
    except Exception:
        return False


def _ensure_extracts_foreground(regions) -> bool:
    """Make every ``(region_id, pbf_url)`` present in the store, joining
    or starting its one download.  The step holds no scheduler slot
    meanwhile (``O4_Step_Wait``).  True only when all are ready; False on
    stop (red_flag), download failure, or a region with no usable url —
    callers fall back to Overpass exactly as with the lazy path.

    The store is swept of dead downloads' partial files first, once per
    process (#2294): only the Qt window's maintenance thread swept it, so
    the Mac app's engine left ~30 ``*.osm.pbf.tmp-<pid>-*`` files (~1 GB)
    of killed builds; a live writer's file is kept
    (:func:`_sweep_interrupted_downloads`)."""
    if not _swept_this_process.is_set():
        _swept_this_process.set()
        _sweep_interrupted_downloads()
    with STEP_WAIT.waiting():
        for (region_id, pbf_url) in regions:
            if _extract_ready(region_id):
                continue
            if UI.red_flag:
                return False
            url = pbf_url or _url_for_region(region_id)
            if url is None and _refresh_index():
                url = _url_for_region(region_id)
            if not _acquire_extract(region_id, url, foreground=True):
                return False
            if not _extract_ready(region_id):
                return False
    return True


def osm_xml_from_local_extracts(statements, bounding_box,
                                request_description="") -> Optional[bytes]:
    """OSM XML bytes for the statements, served from local extracts.

    Drop-in stand-in for an Overpass response (same union + recursion
    semantics, see O4_OSM_Extract_Filter).  Returns ``None`` whenever
    the extracts cannot serve this request — backend disabled, region
    index absent, extracts not downloaded yet (they are recorded as
    wanted for the maintenance thread), or any failure — in which case
    the caller proceeds to Overpass exactly as before.  Under a stop
    (``UI.red_flag``) it is also ``None``, with nothing queued: the
    caller ends its request there instead of falling back (#704).

    ``bounding_box`` may also be a LIST of boxes: the pbf filtering cost
    is dominated by reading the whole extract file, so serving N disjoint
    areas in one filtering pass costs one read instead of N (the
    per-airport inset footprint queries batch this way).  Every box must
    be extract-servable, and each box's missing regions are queued for
    download exactly as in the single-box case.
    """
    try:
        if not extracts_enabled():
            return None
        boxes = _bounding_boxes_list(bounding_box)
        if not boxes:
            return None
        regions = []
        region_ids_seen = set()
        for box in boxes:
            box_regions = covering_regions(box, unknown_land_parent=False)
            if (box_regions is None and _leaf_regions() is None
                    and foreground_download_enabled() and not UI.red_flag
                    and _foreground_index_refresh_once()):
                # No region index stored yet (fresh install, or a front
                # end whose maintenance thread hasn't landed it): fetch
                # it in-band once — a few MB, negligible next to any
                # extract — so the very first build is extract-served.
                box_regions = covering_regions(box, unknown_land_parent=False)
            if box_regions is None and _leaf_regions() is not None:
                # Unknown land: the elevation that decides it first (a
                # few MB the tile build fetches anyway), then the cover
                # again — a parent extract only for land it shows, or,
                # the elevation not to be had, for the whole box.
                if foreground_download_enabled() and not UI.red_flag:
                    _fetch_witness_elevation(box)
                box_regions = covering_regions(box)
            if box_regions is None:
                return None
            for region in box_regions:
                if region[0] not in region_ids_seen:
                    region_ids_seen.add(region[0])
                    regions.append(region)
        if not regions:
            # Every box lies beyond the extracts and holds no land: the
            # answer Overpass gives for open sea.
            import O4_OSM_Extract_Filter as FILTER

            return FILTER.filter_extracts_to_osm_xml([], statements, boxes)
        missing = _stored_regions_missing(regions)
        if missing and foreground_download_enabled() and not UI.red_flag:
            # Owner ruling 2026-07-18: acquire the extract NOW rather
            # than falling back to Overpass for the whole first build in
            # a region (a country downloads from the CDN in about the
            # time one throttled Overpass round takes).
            missing_set = set(missing)
            if _ensure_extracts_foreground(
                    [r for r in regions if r[0] in missing_set]):
                missing = _stored_regions_missing(regions)
        if missing and UI.red_flag:
            # Stop is a cancellation, not "not stored yet": nothing is
            # queued (a stopped build must not start a download after
            # the stop — a fresh engine's maintenance thread would drain
            # the want at once, #704) and nothing announces a fallback.
            return None
        if missing:
            # A region whose address answered 404 is not queued again
            # (#2201): its 404 was logged once when it happened.
            gone = {region_id for (region_id, url) in regions
                    if region_id in missing
                    and _url_not_found(url, transient=False)}
            queued = [region_id for region_id in missing
                      if region_id not in gone]
            if queued:
                record_wanted_regions(queued)
                UI.vprint(
                    1,
                    "      Regional extract(s)",
                    ", ".join(queued),
                    "not stored yet; queued for background download —"
                    " using Overpass this time.",
                )
            return None
        # Real work, also when an Overpass backoff polls this function.
        with STEP_WAIT.working():
            return _filter_stored_extracts(
                regions, boxes, statements, request_description)
    except Exception as error:
        if UI.red_flag:
            return None
        UI.vprint(
            1, "      Regional extract filtering failed",
            "(" + str(error) + "); using Overpass.",
        )
        return None


def _fetch_witness_elevation(box) -> bool:
    """Fetch the elevation the land witness lacks for ``box`` (#2234),
    so the cover can be decided offline instead of on Overpass."""
    import O4_Land_Witness as LAND

    with STEP_WAIT.waiting():
        return LAND.fetch_elevation(box)


def _filter_stored_extracts(regions, boxes, statements,
                            request_description) -> Optional[bytes]:
    """The statements' OSM XML from the stored extracts, through the area
    clip when one can be had."""
    import O4_OSM_Extract_Filter as FILTER

    label = f" ({request_description})" if request_description else ""
    clip_files = _clip_for_query(regions, boxes)
    if clip_files is not None:
        served = _filter_through_clip(
            regions, boxes, clip_files, statements, label)
        if served is not None:
            return served
    UI.vprint(
        1,
        f"      Filtering OSM data{label} from regional extract(s):",
        ", ".join(region_id for (region_id, _url) in regions),
    )
    return FILTER.filter_extracts_to_osm_xml(
        [_region_file(region_id) for (region_id, _url) in regions],
        statements,
        boxes,
    )


# ---------------------------------------------------------------------------
# Background maintenance (application process only)
# ---------------------------------------------------------------------------
class _ExtractWatcher(DOWNLOADS.Watcher):
    """One extract request's console lines, meter and progress bar."""

    def __init__(self, region_id: str, foreground: bool) -> None:
        self.region_id = region_id
        self.foreground = foreground
        self.metering = False              # the meter module imported
        self.metered = False               # registered with its ETA
        self.next_report = DOWNLOAD_PROGRESS_EVERY_BYTES
        self.reported_at = time.time()     # the last progress line
        self.chunk_started = 0.0
        self.waited_at = None              # (time, bytes) a joiner last saw

    def joined(self) -> None:
        UI.vprint(1, "   OSM regional extract", self.region_id,
                  "is already downloading for another tile; waiting for it.")

    def leading(self) -> None:
        UI.vprint(0, "   Downloading OSM regional extract", self.region_id,
                  "(needed by this build)..." if self.foreground
                  else "in the background...")

    def started(self, total_bytes: int) -> None:
        self.chunk_started = time.time()
        try:
            from o4_engine import download_meter as METER
        except Exception:
            return
        self.metering = True
        if self.foreground:
            # Foreground downloads block the build: register with the
            # meter so the ETA prices the unmoved bytes at the measured
            # throughput.
            METER.begin("extract:" + self.region_id, total_bytes)
            self.metered = True

    def chunk(self, size: int, received: int, total_bytes: int) -> None:
        if self.metering:
            from o4_engine import download_meter as METER
            now = time.time()
            METER.record(size, now - self.chunk_started)
            self.chunk_started = now
            if self.metered:
                METER.update("extract:" + self.region_id, received)
        if self.foreground and total_bytes > 0:
            # An in-band download blocks the vector step: drive its bar
            # so the front ends' progress ring moves.
            UI.progress_bar(1, int(min(received * 100 // total_bytes, 99)))
        self._progress_line(received, total_bytes)

    def _progress_line(self, received: int, total_bytes: int,
                       lead: str = "") -> None:
        """One ``... N/M MB so far`` line each DOWNLOAD_PROGRESS_EVERY_BYTES
        and at least each DOWNLOAD_PROGRESS_EVERY_SECONDS (#2299)."""
        now = time.time()
        if (received < self.next_report
                and now - self.reported_at < DOWNLOAD_PROGRESS_EVERY_SECONDS):
            return
        UI.vprint(1, "      ...", self.region_id, "%s%d%s MB so far" % (
            lead, received >> 20,
            "/%d" % (total_bytes >> 20) if total_bytes else ""))
        self.reported_at = now
        while self.next_report <= received:
            self.next_report += DOWNLOAD_PROGRESS_EVERY_BYTES

    def waited(self, received: int, total_bytes: int) -> None:
        """A foreground joiner prices the flight it waits on the same
        way the leader does (#2218): registered with the meter, the
        bytes landing on disk sampled as throughput, the bar driven --
        and says how far it is, as the leader does (#2299)."""
        if not self.foreground:
            return
        self._progress_line(received, total_bytes, "(another tile's download) ")
        if total_bytes <= 0:
            return
        try:
            from o4_engine import download_meter as METER
        except Exception:
            return
        now = time.time()
        key = "extract:" + self.region_id
        if not self.metered:
            METER.begin(key, total_bytes)
            self.metered = True
        elif self.waited_at is not None and received > self.waited_at[1]:
            METER.record(received - self.waited_at[1],
                         now - self.waited_at[0], now=now)
        self.waited_at = (now, received)
        METER.update(key, received)
        UI.progress_bar(1, int(min(received * 100 // total_bytes, 99)))

    def finished(self) -> None:
        if self.metered:
            from o4_engine import download_meter as METER
            with contextlib.suppress(Exception):
                METER.end("extract:" + self.region_id)


def _record_extract_downloaded(region_id: str, pbf_url: str) -> None:
    """Note the install in ``state.json`` (several processes write it)."""
    from O4_File_Lock import hold_file_lock

    with _store_lock, hold_file_lock(_store_path("state.json")):
        state = _read_json(_store_path("state.json")) or {}
        state[region_id] = {"downloaded_at": time.time(), "url": pbf_url}
        _write_json_atomic(_store_path("state.json"), state)


def _download_extract(region_id: str, pbf_url: str,
                      foreground: bool = False) -> bool:
    """Fetch one extract through the download manager: one transfer per
    region across every process, joined by whoever else needs it.  A
    background call refreshes a stored extract; a Stop leaves nothing
    queued (the app respawns an engine after a hard stop, and its
    maintenance thread would start the download again, #704)."""
    os.makedirs(STORE_DIRECTORY, exist_ok=True)
    result = DOWNLOADS.fetch(
        _extract_resource(region_id, pbf_url),
        refresh=not foreground,
        should_stop=lambda: UI.red_flag,
        watcher=_ExtractWatcher(region_id, foreground),
        open_stream=lambda url, **options: requests.get(url, **options),
    )
    if result.ok:
        if result.transferred:
            _record_extract_downloaded(region_id, pbf_url)
            UI.vprint(0, "   OSM regional extract", region_id,
                      "ready (%d MB); future builds in this region skip"
                      " Overpass." % (result.received >> 20))
            UI.vprint(1, "      Requests made for this extract so far:",
                      DOWNLOADS.request_counts(STORE_DIRECTORY).get(
                          "osm-extract:" + region_id, 0))
        return True
    _report_extract_failure(region_id, pbf_url, result)
    return False


def _report_extract_failure(region_id: str, pbf_url: str,
                            result: DOWNLOADS.Result) -> None:
    """Say why the request ended without a file; remember a 404."""
    if result.status == DOWNLOADS.STOPPED:
        UI.vprint(0, "   OSM regional extract download for", region_id,
                  "stopped with the build.")
    elif result.status == DOWNLOADS.INVALID:
        # Some indexed regions answer with an HTML page under HTTP 200
        # (no extract published at that address).
        UI.vprint(0, "   The download for OSM regional extract", region_id,
                  "returned something other than pbf data (no extract is"
                  " published at its address); builds in this region use"
                  " Overpass instead.")
    elif result.error is not None:
        if _is_not_found(result.error):
            _remember_not_found(region_id, pbf_url, transient=True,
                                redirected=_redirected(result.error))
        UI.vprint(1, "   Extract download for", region_id, "failed:",
                  str(result.error))
    else:
        UI.vprint(1, "   The download of extract", region_id,
                  "this tile waited for failed.")


def _is_not_found(error) -> bool:
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None) == 404


def _redirected(error) -> bool:
    """True when the 404 came after a redirect (a dated file mid-rebuild)."""
    response = getattr(error, "response", None)
    return bool(getattr(response, "history", None))


def _remember_not_found(region_id: str, url: str, transient: bool,
                        redirected: bool = False) -> None:
    with _store_lock:
        gone = _read_json(_store_path("not_found.json")) or {}
        gone[url] = {"region": region_id, "at": time.time(),
                     "transient": bool(transient),
                     "redirected": bool(redirected)}
        _write_json_atomic(_store_path("not_found.json"), gone)


def _not_found_entry(url):
    return (_read_json(_store_path("not_found.json")) or {}).get(url)


def _url_not_found(url, transient=None) -> bool:
    """True when ``url`` answered 404 within its memory window.

    A transient 404 is remembered NOT_FOUND_TRANSIENT_HOURS, a confirmed
    one NOT_FOUND_RETRY_DAYS; ``transient`` True/False asks for one kind
    only.  An entry WITHOUT the flag (an older engine's, which recorded
    redirects and 404s alike) is transient: it cannot show the address
    is gone (#2299: Oregon's flagless entry of 11-23 kept the extract
    from every build while the address answered 307 -> 200).
    """
    entry = _not_found_entry(url) if url else None
    if not entry:
        return False
    is_transient = bool(entry.get("transient", True))
    if transient is not None and transient != is_transient:
        return False
    window = (NOT_FOUND_TRANSIENT_HOURS * 3600 if is_transient
              else NOT_FOUND_RETRY_DAYS * 86400)
    return time.time() - float(entry.get("at", 0)) < window


def _keep_wanted_if_transient(region_id: str, url) -> None:
    """A transient 404 leaves the region wanted: the background retries."""
    if _url_not_found(url, transient=True):
        record_wanted_regions([region_id])


def _index_recent() -> bool:
    try:
        return (time.time() - os.path.getmtime(_index_path())
                < NOT_FOUND_INDEX_FRESH_SECONDS)
    except OSError:
        return False


def _acquire_extract(region_id: str, url, foreground: bool = False) -> bool:
    """Download one extract; a 404 re-reads the index once (#2201).

    Geofabrik moves extracts (2026-11: leaves into per-region folders,
    and the old address's redirect 404s), while the stored index waits
    for the user's expiry (RULINGS 2026-11-13o).  A 404 proves the
    stored address wrong, so the index is asked again — unless it was
    just fetched — and the download retried at its new address.

    Every 404 is first remembered as transient (``not_found.json``,
    NOT_FOUND_TRANSIENT_HOURS): this build uses Overpass and the region
    stays wanted, so the background download retries after the window
    (Geofabrik's -latest redirects to a dated file that is briefly 404
    while the region regenerates).  Only a 404 with no redirect on the
    address a fresh index still lists is remembered NOT_FOUND_RETRY_DAYS.
    """
    if not url:
        return False
    if _url_not_found(url):
        _keep_wanted_if_transient(region_id, url)
        return False
    if _download_extract(region_id, url, foreground=foreground):
        return True
    entry = _not_found_entry(url)
    if not _url_not_found(url):
        return False      # not a 404: nothing remembered
    if not _index_recent() and not _refresh_index():
        _keep_wanted_if_transient(region_id, url)
        return False
    fresh_url = _url_for_region(region_id)
    if fresh_url and fresh_url != url and not _url_not_found(fresh_url):
        if _download_extract(region_id, fresh_url, foreground=foreground):
            return True
        url = fresh_url
    elif fresh_url == url and not entry.get("redirected"):
        _remember_not_found(region_id, url, transient=False)
    _keep_wanted_if_transient(region_id, url)
    return False


def _regions_to_refresh() -> list:
    """[(region_id, url)] of stored extracts past the refresh age.

    An entry whose pbf file is gone means the user deleted it (e.g. a
    multi-gigabyte aggregate made redundant by covering-region pruning):
    the state entry is dropped, never re-downloaded.  A build that
    genuinely needs the region again re-acquires it through the
    wanted-list / foreground-download path.
    """
    with _store_lock:
        state = _read_json(_store_path("state.json")) or {}
        deleted = [region_id for region_id in state
                   if not os.path.isfile(_region_file(region_id))]
        if deleted:
            for region_id in deleted:
                del state[region_id]
            _write_json_atomic(_store_path("state.json"), state)
            UI.vprint(
                1,
                "   Forgetting deleted OSM regional extract(s):",
                ", ".join(sorted(deleted)),
            )
    refresh_age_seconds = _extract_refresh_days() * 86400
    now = time.time()
    stale = []
    for region_id, entry in state.items():
        if now - float(entry.get("downloaded_at", 0)) \
                > refresh_age_seconds:
            stale.append((region_id, entry.get("url")))
    return stale


def _url_for_region(region_id: str) -> Optional[str]:
    for (leaf_id, pbf_url, _g) in (_leaf_regions() or []):
        if leaf_id == region_id:
            return pbf_url
    return None


def _refresh_stale_store() -> None:
    """Re-read a stale index and re-download extracts past their age."""
    if _index_is_stale():
        _refresh_index()
    for (region_id, pbf_url) in _regions_to_refresh():
        if UI.red_flag or not extracts_enabled():
            # Keep the network quiet.  Refreshes resume at the next
            # application start.
            break
        # The index's address first: a stored one may predate a move.
        _acquire_extract(region_id, _url_for_region(region_id) or pbf_url)


_swept_this_process = threading.Event()


def _sweep_interrupted_downloads() -> int:
    """Remove what interrupted extract downloads left in the store
    (``<region>.osm.pbf.tmp-<pid>-<thread>`` of a dead writer, or one
    unwritten past ``ABANDONED_SECONDS``; a live writer's is kept) and
    say so (#2218).  The count removed; never raises."""
    try:
        removed = DOWNLOADS.sweep_stale_temporaries(STORE_DIRECTORY)
    except Exception:
        return 0
    if removed:
        UI.vprint(1, "   Removed %d file(s) left by interrupted OSM"
                  " regional extract downloads." % removed)
    return removed


def _maintenance_loop() -> None:
    _sweep_interrupted_downloads()
    refreshed = False
    while True:
        # While a stop is in flight the wanted list is left untouched —
        # consuming it and aborting would drop the regions until some
        # later build re-recorded them.  With the backend switched off
        # nothing here touches the network.
        if extracts_enabled() and not UI.red_flag:
            if not refreshed:
                refreshed = True
                _refresh_stale_store()
            for region_id in _consume_wanted_regions():
                if os.path.isfile(_region_file(region_id)):
                    continue
                url = _url_for_region(region_id)
                if url is None:
                    # No index yet (first run): fetch it, then retry once.
                    if _refresh_index():
                        url = _url_for_region(region_id)
                _acquire_extract(region_id, url)
        time.sleep(WANTED_RESCAN_SECONDS)


# ---------------------------------------------------------------------------
# Per-area clip cache
# ---------------------------------------------------------------------------
# Padding past the enclosing integer-degree box, so every query a tile
# build issues (tile bbox + epsilon, airport-inset footprints reaching a
# little over the border) stays INSIDE the clip box.
_CLIP_PAD_DEGREES = 0.05


def _clip_directory() -> str:
    return _store_path("clips")


def _clip_bounding_box(boxes) -> tuple:
    """Integer-degree box enclosing every query box, padded."""
    import math

    lat_min = min(box[0] for box in boxes)
    lon_min = min(box[1] for box in boxes)
    lat_max = max(box[2] for box in boxes)
    lon_max = max(box[3] for box in boxes)
    return (math.floor(lat_min) - _CLIP_PAD_DEGREES,
            math.floor(lon_min) - _CLIP_PAD_DEGREES,
            math.ceil(lat_max) + _CLIP_PAD_DEGREES,
            math.ceil(lon_max) + _CLIP_PAD_DEGREES)


def _clip_path(regions, clip_box) -> str:
    """Clip cache BASE path (no extension), keyed by area + the exact
    extract files it was cut from (id, size, mtime): a re-downloaded
    extract changes the key, so stale clips can never serve.  The cache
    itself is ``<base>-part<N>.osm.pbf`` per extract plus the
    ``<base>.parts.json`` completeness manifest.

    The base is ``clip_<corner>_<area>-<stamp>``: ``<area>`` digests the
    clip box and the region ids, ``<stamp>`` the extract files' sizes
    and mtimes, so a clip is SUPERSEDED only by one with the same
    ``<area>`` and a newer ``<stamp>`` (:func:`_prune_stale_clips`)."""
    import hashlib

    area = hashlib.sha1()
    stamp = hashlib.sha1()
    for region_id, _url in regions:
        stat = os.stat(_region_file(region_id))
        area.update(("%s;" % region_id).encode())
        stamp.update(("%s|%d|%d;" % (
            region_id, stat.st_size, int(stat.st_mtime))).encode())
    area.update(repr(clip_box).encode())
    prefix = "clip_%+04d%+05d" % (
        int(round(clip_box[0] + _CLIP_PAD_DEGREES)),
        int(round(clip_box[1] + _CLIP_PAD_DEGREES)))
    return os.path.join(
        _clip_directory(),
        "%s_%s-%s" % (prefix, area.hexdigest()[:12], stamp.hexdigest()[:12]))


# Clip bases a filter of THIS process is reading now (base -> readers):
# the prune never removes one (#1734).  Another process whose clip is
# pruned under it recovers through :func:`_filter_through_clip`.
_clips_in_use: dict = {}
_clips_in_use_lock = threading.Lock()
# A clip in the pre-#1734 naming (no ``<area>-<stamp>`` split, or the
# single-file layout) is removed only once untouched this long: an older
# engine process may still be reading it.
_LEGACY_CLIP_AGE_SECONDS = 3600.0


@contextlib.contextmanager
def _clip_in_use(base: str):
    with _clips_in_use_lock:
        _clips_in_use[base] = _clips_in_use.get(base, 0) + 1
    try:
        yield
    finally:
        with _clips_in_use_lock:
            _clips_in_use[base] -= 1
            if not _clips_in_use[base]:
                del _clips_in_use[base]


def _clip_base_of_name(name: str) -> str:
    """The clip base a cache file name belongs to (parts, manifest,
    its lock, a legacy single-file clip)."""
    for marker in ("-part", ".parts.json", ".osm.pbf"):
        if marker in name:
            return name[:name.index(marker)]
    return name


def _prune_stale_clips(keep_base: str) -> None:
    """Drop clips ``keep_base`` supersedes: the SAME area and regions cut
    from older extract files (a re-download), never a clip of another
    area or region set — two cuts sharing a corner used to evict each
    other mid-read (#1734) — and never one a filter here is reading.
    Legacy-named clips go once they are an hour old."""
    keep_name = os.path.basename(keep_base)
    (prefix, keep_key) = keep_name.rsplit("_", 1)
    area_prefix = "%s_%s-" % (prefix, keep_key.split("-")[0])
    with _clips_in_use_lock:
        in_use = set(_clips_in_use)
    try:
        for name in os.listdir(_clip_directory()):
            if not name.startswith(prefix + "_"):
                continue
            base = _clip_base_of_name(name)
            if base == keep_name or os.path.join(
                    _clip_directory(), base) in in_use:
                continue
            path = os.path.join(_clip_directory(), name)
            legacy = "-" not in base[len(prefix) + 1:]
            if legacy:
                if time.time() - os.path.getmtime(path) \
                        < _LEGACY_CLIP_AGE_SECONDS:
                    continue
            elif not name.startswith(area_prefix):
                continue
            os.remove(path)
    except OSError:
        pass


def _osmium_binary() -> Optional[str]:
    """Path of an osmium-tool executable, or ``None``.

    Bundled binary first (``Utils/<platform>/osmium``, the same
    per-platform layout Triangle4XP and DSFTool use), then the PATH.
    On Linux, where one ``lin`` directory serves several CPU
    architectures, an arch-suffixed name (``osmium-aarch64``) wins over
    the plain one (x86_64, like every other ``lin`` binary); macOS
    needs no suffix because ``mac/osmium`` is a universal binary.
    Cached per process; missing everywhere just means the pyosmium
    cutter does the work.
    """
    cached = getattr(_osmium_binary, "cache", "unset")
    if cached != "unset":
        return cached
    import shutil

    if "dar" in sys.platform:
        subdirectory, names = "mac", ("osmium",)
    elif "win" in sys.platform:
        subdirectory, names = "win", ("osmium.exe",)
    else:
        import platform

        subdirectory, names = (
            "lin", ("osmium-" + platform.machine(), "osmium"))
    found = None
    for name in names:
        bundled = os.path.join(FNAMES.Utils_dir, subdirectory, name)
        if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
            found = bundled
            break
    if found is None:
        found = shutil.which("osmium")
    _osmium_binary.cache = found
    return found


def _clip_manifest_path(base: str) -> str:
    return base + ".parts.json"


def _clip_part_path(base: str, index: int) -> str:
    return "%s-part%d.osm.pbf" % (base, index)


def _read_clip_parts(base: str) -> Optional[list]:
    """The cached clip's part paths (extract order), or None.

    The manifest is the completeness marker: written atomically AFTER
    every part landed, so a crashed cutter can never leave a plausible
    partial cache."""
    names = _read_json(_clip_manifest_path(base))
    if not isinstance(names, list) or not names:
        return None
    parts = [os.path.join(_clip_directory(), str(name)) for name in names]
    if all(os.path.isfile(part) for part in parts):
        return parts
    return None


def _cut_clip(regions, clip_box, base) -> list:
    """Cut the area clip as ONE PART PER EXTRACT and return the paths.

    No merge, ever: the query-time filter consumes an ordered file list
    with first-file-wins semantics, which is exactly what the parts are
    — merging them into one file bought nothing and cost minutes of
    pyosmium callbacks whenever an area spans several extracts
    (observed 2026-07-23: tile +46+006, three extracts, 161 MB of
    clips).  osmium-tool cuts when a binary is available (C++, seconds);
    the pyosmium cutter otherwise, also per extract.

    Any osmium failure falls back to the pyosmium cutter — EXCEPT under
    a stop request, where the fallback's minutes of decoding would
    outlive the build it serves, so the failure propagates instead.
    """
    import O4_OSM_Extract_Filter as FILTER

    source_files = [_region_file(region_id) for (region_id, _url) in regions]
    parts = [_clip_part_path(base, i) for i in range(len(source_files))]
    binary = _osmium_binary()
    if binary is not None:
        try:
            FILTER.cut_clip_parts_with_osmium(
                source_files, clip_box, parts, binary,
                should_stop=lambda: UI.red_flag,
                spawn_kwargs=UI.external_tool_keyword_arguments(),
            )
            return parts
        except Exception as error:
            if UI.red_flag:
                raise
            UI.vprint(
                1,
                "      osmium-tool cut failed (%s); using the built-in"
                " cutter." % error,
            )
    for source_file, part in zip(source_files, parts):
        FILTER.clip_extracts_to_pbf([source_file], clip_box, part)
    return parts


def _clip_for_query(regions, boxes) -> Optional[list]:
    """Part paths of the area clip covering the query boxes (extract
    order — the filter's first-file-wins order), building them on first
    use (seconds through the bundled osmium-tool; one full read of the
    covering extracts — the same cost as a single query round — with
    the pyosmium cutter), repaid by every later round reading a few MB
    instead.  ``None`` on any failure: the caller filters the full
    extracts exactly as before.
    """
    try:
        clip_box = _clip_bounding_box(boxes)
        base = _clip_path(regions, clip_box)
        parts = _read_clip_parts(base)
        if parts is not None:
            return parts
        from O4_File_Lock import hold_file_lock

        os.makedirs(_clip_directory(), exist_ok=True)
        # Concurrent query rounds (the vector step, the bathymetry
        # prefetch, auto-patch) race to cut the SAME clip: without the
        # lock each spent minutes decoding the full extracts and the
        # losers' atomic rename then failed under the winner's.  One
        # cutter works; everyone else waits and reads the result.
        with hold_file_lock(_clip_manifest_path(base)):
            parts = _read_clip_parts(base)
            if parts is not None:
                return parts
            started = time.time()
            UI.vprint(
                1,
                "      Cutting a clipped OSM cache for this area "
                "(one-time per area and extract refresh)...",
            )
            parts = _cut_clip(regions, clip_box, base)
            _write_json_atomic(
                _clip_manifest_path(base),
                [os.path.basename(part) for part in parts])
            UI.vprint(
                1,
                "      ...clipped OSM cache ready (%.0f s, %d MB)."
                % (time.time() - started,
                   sum(os.path.getsize(part) for part in parts) >> 20),
            )
        _prune_stale_clips(base)
        return parts
    except Exception as error:
        UI.vprint(
            1,
            "      Clipped OSM cache unavailable (%s); filtering the "
            "full extracts." % error,
        )
        return None


def _filter_through_clip(regions, boxes, clip_files, statements,
                         label) -> Optional[bytes]:
    """Filter the statements from the area clip (same first-file-wins
    order as the extracts it was cut from), or ``None`` to filter the
    full extracts.  A clip whose part vanished under the read (another
    process pruned or re-cut it, #1734) is re-cut from the extracts on
    disk and read once more — never an Overpass fallback while the
    extract is present.  Any other filter error propagates."""
    import O4_OSM_Extract_Filter as FILTER

    for attempt in (0, 1):
        UI.vprint(1, f"      Filtering OSM data{label} from",
                  "the clipped area cache")
        base = clip_files[0][:clip_files[0].rindex("-part")]
        try:
            with _clip_in_use(base):
                return FILTER.filter_extracts_to_osm_xml(
                    clip_files, statements, boxes)
        except Exception:
            if UI.red_flag or all(os.path.isfile(p) for p in clip_files):
                raise
        UI.vprint(1, "      The clipped OSM cache for this area went"
                  " missing during the read; cutting it again from the"
                  " extract(s) on disk.")
        if attempt:
            return None
        clip_files = _clip_for_query(regions, boxes)
        if clip_files is None:
            return None
    return None


def _foreground_index_refresh_once() -> bool:
    """One in-band Geofabrik index download per process.

    Keeps the first-ever build extract-servable before background
    maintenance has stored the index; the single-attempt gate means an
    offline machine pays one failed request per process, not one per
    query round.
    """
    if getattr(_foreground_index_refresh_once, "attempted", False):
        return False
    _foreground_index_refresh_once.attempted = True
    return _refresh_index()


def start_background_maintenance() -> None:
    """Start the extract maintenance thread (idempotent, never raises).

    Call once from the APPLICATION process (Qt window or CLI main) —
    never from parallel-build worker children, which only append wants.
    """
    try:
        if not extracts_enabled():
            return
        if _maintenance_started.is_set():
            return
        _maintenance_started.set()
        threading.Thread(
            target=_maintenance_loop,
            name="osm_extract_maintenance",
            daemon=True,
        ).start()
    except Exception:
        pass
