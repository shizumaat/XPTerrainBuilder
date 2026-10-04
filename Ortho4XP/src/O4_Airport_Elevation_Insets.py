"""Automatic per-airport high-resolution elevation insets.

This module fetches meter-class public elevation (for example the United
States Geological Survey 3D Elevation Program, "3DEP") for the neighbourhood
of every airport on a tile, caches it under ``Elevation_data/``, overlays it
on the base elevation, and -- crucially -- bakes the overlaid values into the
raster that the Triangle4XP mesher actually reads.  See
``docs/airport_elevation_insets_spec.md`` for the full design.

The provider framework is DECLARATIVE, mirroring Ortho4XP's imagery
providers: a source is described by a ``Providers/Elevation/<CODE>.elv``
``key=value`` file (parsed by :func:`initialize_elevation_providers_dict`),
and the genuinely-logic part -- how bytes are fetched -- lives in a named
ACCESS STRATEGY.  The strategies are NOT in this file: each is one module
of the ``elevation_access`` package (``src/elevation_access/strategies/``),
whose package docstring says how to add one.  This file is the
strategy-agnostic pipeline -- discovery loop, cache, index, composite,
bake -- and looks a strategy up only by the key a definition names.

Phase C1 additionally densifies the working grid over inset tiles (the
``densify_tile_dem_for_insets`` / ``resolve_working_grid_factor`` section
below): the ``.alt`` raster the mesher reads is built on a finer grid so the
meter-class inset relief survives the Triangle4XP one-working-pixel
refinement floor, chosen per tile by a cheap numpy ideal-bake check on the
cached inset before any build.

--------------------------------------------------------------------------
G2 flow finding -- how a composite source reaches the ``.alt`` raster
--------------------------------------------------------------------------
The mandatory first investigation (spec section 3.3, goal G2) traced how a
composite ``custom_dem`` (the ``base;sub1;sub2`` syntax in
``O4_DEM_Utils.py``) reaches the ``.alt`` file that Triangle4XP consumes.

What the composite mechanism actually does (``O4_DEM_Utils.py``):
  * ``DEM.load_data`` splits ``base;sub1;sub2`` into a BASE raster
    (``self.alt_dem``, an in-memory array) plus a tuple of strict
    ``self.subdems``.
  * The subdems are consulted ONLY at QUERY TIME by ``alt_composite`` /
    ``alt_vec_composite`` (i.e. ``dem.alt(node)`` / ``dem.alt_vec(way)``),
    which return the highest-priority sub-DEM value at a point, else the
    base.  Later tokens win (``subdems[::-1]`` in ``alt_composite``).
  * ``DEM.write_to_file`` writes ONLY ``self.alt_dem`` -- the base array.
    It never consults the subdems.

Who writes and who reads the ``.alt`` file:
  * Step 1 (``O4_Vector_Map.build_poly_file`` ->
    ``O4_Airport_Utils.smooth_raster_over_airports``) smooths
    ``tile.dem.alt_dem`` in place and calls ``write_to_file`` -> ``.alt``.
  * Step 2 (``O4_Mesh_Utils.build_mesh``) loads the DEM ``info_only=True``
    (so ``alt_dem`` is ``None``) and hands Triangle4XP the on-disk ``.alt``
    file directly; the mesh vertex elevations come from that raster.

CONCLUSION: sub-DEM / inset values do NOT reach the ``.alt`` raster through
the composite mechanism.  The composite only feeds the QUERY path
(``alt_vec`` -- used for OSM vector node elevations and, via
``auto_patch.elevation._load_airport_dem(override_dem=tile.dem)``, for the
grading seeds).  So this feature needs BOTH:

  1. Composite-source augmentation (``assemble_inset_composite_source``) so
     inset values reach the vector / grading QUERY path automatically.
  2. An explicit RASTER BAKE (``bake_airport_insets_into_alt_dem``) so inset
     values reach the ``.alt`` file the mesher reads.  The bake samples each
     cached inset into ``tile.dem.alt_dem`` over its footprint with a
     feathered blend band (``airport_elevation_inset_feather_m``, default
     60 m) so the inset->base seam is a ramp, not a cliff.  It runs in
     step 1 just before ``write_to_file``, so both steps see one raster,
     and again on step 2's ITERATIVE-refinement branch, which rewrites the
     ``.alt`` from the ``tile.iterate``-th user sub-DEM (that load keeps
     nodata, so the bake takes the inset outright over base nodata cells
     instead of blending against the sentinel).

The synthetic-inset unit test in ``tests/test_airport_elevation_insets.py``
proves the bake: a flat inset over a flat base appears at inset cells, ramps
across the feather, and leaves the base untouched outside.

G2 addendum (owner ruling 2026-07-25) -- ONE SURFACE, TWO READERS
--------------------------------------------------------------------------
Steps 1 and 2 above left TWO surfaces standing: the query path returned the
inset's own nearest-neighbour value on its native 30 m posting, while the
mesh renders BILINEAR over the baked working raster.  They agree exactly at
the 30 m block centres and diverge by up to ~0.9 m at the block edges -- a
sawtooth, and the source of the owner-visible seam dip at SPLP, because
every auto_patch "pin this vertex to the DEM" pinned to a surface X-Plane
never shows.  ``bake_airport_insets_into_alt_dem`` therefore ends by calling
``DEM.enable_baked_query``, which re-points ``dem.alt``/``dem.alt_vec`` at a
Python reproduction of ``Triangle4XP.altitude()`` over the very array just
baked.  The composite is then bypassed -- but only when the baked raster
provably represents the WHOLE composite (every sub-DEM baked); a legacy
hand-written ``custom_dem = "base;local"`` keeps ``alt_composite``.

G2 addendum II (owner ruling 2026-07-25) -- HOW THE INSET REACHES THE GRID
--------------------------------------------------------------------------
The bake itself was NEAREST NEIGHBOUR, which quantises the inset onto the
working grid in the worst way available in both directions: a coarser
inset became a literal staircase for the mesher to refine (2,482,100
triangles at +30+031 against 1,140,668 for identical content baked
smoothly), and a finer inset was point-subsampled below its Nyquist limit
and aliased.  It now resamples BILINEARLY when the inset is coarser than
the grid and AREA-AVERAGES when it is finer -- see the section comment
above ``inset_bake_resample_mode`` (gate ``O4_INSET_BAKE_INTERP``).

Two consequences ride along.  The working-grid BALLOT
(``ideal_bake_errors_per_probe``) modelled the built value with a
two-triangle split it wrongly attributed to the mesher; it now scores the
real chain -- bilinear bake, then Triangle4XP's true bilinear read.  And
adjacent tiles sharing a seam-straddling inset now ballot over the MERGED
inset sets of their whole seam-connected component, so they cannot pick
different working grids and disagree along the seam (measured at SPLP:
3.7995 m -> 0.0000 m); see the section comment above
``seam_harmonized_ballot_insets`` (gate ``O4_INSET_SEAM_HARMONIZE``).
"""

import os
import json
import glob
import math
import datetime
import threading

from O4_Airport_Modes import (                    # core; stdlib-only module (#59, #70)
    MODE_RANK,
    MODES,
    inset_keys,
    mode_admits,
    resolved_inset_mode,
)

import numpy

# The access strategies (one module each) and what they share live in
# the ``elevation_access`` package; importing it registers every strategy.
import elevation_access  # noqa: F401  (registers the strategies)
from elevation_access.gdal_support import gdal, ogr, osr, has_gdal
from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.base_tiles import (
    base_definition_covers_tile,
    cached_elevation_file_is_valid,
)
from elevation_access.capabilities import (
    CAPABILITY_LAS,
    CAPABILITY_LAZ,
    CAPABILITY_LERC,
    _definition_needs_laz,
    las_reader_available,
    laz_reader_available,
    lerc_decode_available,
)
from elevation_access.definitions import (
    ROLE_AIRPORT_INSET,
    ROLE_BASE,
    ROLE_BATHYMETRY,
    _coverage_bbox_intersects,
    _parse_boolean,
    _parse_bounding_boxes,
    _parse_float,
    coverage_boxes,
    export_image_definition_refusal,
)
from elevation_access.downloads import _write_refused_by_armed_guard
from elevation_access.fetch_slots import _held_provider_fetch_slot
from elevation_access.las_tiles import LAS_FOOTPRINT_KEY, _buffer_geometry_m
from elevation_access.registry import ACCESS_STRATEGIES
from elevation_access.vertical_units import (
    VERTICAL_UNIT_STAMP_APPLIED,
    VERTICAL_UNIT_STAMP_DECLARED,
    VERTICAL_UNIT_STAMP_SOURCE,
)
from elevation_access.warp import inset_valid_fraction

import O4_UI_Utils as UI
import O4_File_Names as FNAMES
import O4_File_Lock as O4_File_Lock
import O4_Geo_Utils as GEO
import O4_DEM_Utils as DEM
# The ONE derivation site for pack enablement (RULINGS 2026-09-17b).
import O4_Scenery_Packs as _scenery_packs

# The .elv provider CODE is lower-cased in cache file names so the cache key
# survives access-strategy refactors (spec section 3.2).
NO_COVERAGE = "no-coverage"

# =====================================================================
# THE STATUS CLASSES OF THE INSET INDEX (owner RULINGS 2026-09-13b)
# =====================================================================
# ``no-coverage`` is a DURABLE NEGATIVE: the provider answered about this
# box and has nothing.  It is never re-queried.  That makes it the most
# expensive value in the index to write by mistake -- and 1.0.324 wrote
# one for NEWZEALAND1M at NZQN because the PACKAGED engine could not
# decode LERC at all: the fetcher returned an empty asset list, the warp
# had nothing to warp, the strategy returned ``None``, and ``None`` means
# no-coverage.  NZQN's 1 m lidar became a permanent "there is no lidar
# here" and the tile has been cut from 30 m COPERNICUS ever since.
#
# So a provider skipped for a MISSING CAPABILITY -- no LERC decoder, no
# GDAL, a download that failed for anything but a 404 -- records
# ``unavailable:<reason>`` instead.  It is its own status class: the
# reader never treats it as no-coverage, nothing is cached against it,
# and the next run simply tries again (the ``TransientFetchError``
# discipline, made durable-in-the-index so a human reading the file can
# see WHY the tier is degraded).
UNAVAILABLE_PREFIX = "unavailable:"

# ``empty:<reason>`` is the THIRD status class (2026-09-18, the LSGP /
# LSGY class): the provider ANSWERED, a raster was written, and it holds
# no data -- ``LSGP_swissalti3d.tif``, 9,733 bytes, 0.00 % valid pixels,
# stamped ``"SWISSALTI3D": "ok"`` on 2026-07-23 and reused as a warm
# cache ever since, because the cache gate asks only whether the FILE
# exists.  An empty raster is NOT a cache: it is a fetch that produced
# nothing, so it takes the retry policy of a fetch that produced nothing
# -- its own status, never ``ok``, never a durable ``no-coverage``, and
# asked again on the next fetch pass (exactly what ``unavailable:``
# does).  The refetch's own outcome then overwrites it: ``ok``, a
# durable ``no-coverage`` (with the relic deleted by the existing
# failure path), or this status again.
EMPTY_PREFIX = "empty:"

#: Keys of a per-airport index record that are NOT provider statuses.
#: One list, so a consumer counting statuses can never mistake a
#: bookkeeping key for a provider (``probes_for`` was already being
#: counted as one).
INDEX_NON_PROVIDER_KEYS = (
    "bounding_box",
    "capabilities",
    "checked",
    "probes",
    "probes_for",
)


def unavailable_status(reason):
    """The index value for "this run could not ASK this provider"."""
    return UNAVAILABLE_PREFIX + str(reason)


def status_is_unavailable(status):
    """True for an ``unavailable:<reason>`` record.  NOT no-coverage."""
    return isinstance(status, str) and status.startswith(UNAVAILABLE_PREFIX)


def empty_status(reason):
    """The index value for "the fetch wrote a raster that holds no data"."""
    return EMPTY_PREFIX + str(reason)


def status_is_empty(status):
    """True for an ``empty:<reason>`` record.  NOT no-coverage, NOT ok."""
    return isinstance(status, str) and status.startswith(EMPTY_PREFIX)


def unavailable_reason(status):
    """The reason out of an ``unavailable:<reason>`` record, or ``None``."""
    if not status_is_unavailable(status):
        return None
    return status[len(UNAVAILABLE_PREFIX):]


def provider_statuses(airport_record):
    """``{provider code: status}`` of one per-airport index record."""
    if not isinstance(airport_record, dict):
        return {}
    return {
        key: value
        for (key, value) in airport_record.items()
        if key not in INDEX_NON_PROVIDER_KEYS
    }


# GDAL's /vsicurl and WCS drivers ship with NO transfer timeouts: a server
# that accepts the connection and then stalls (observed: FRANCE50CM) wedges
# the warp forever.  These guards make stalls raise instead — the fetch is
# then treated as transient and retried on the next run.  The low-speed
# pair is the health check proper: a transfer under 1 KB/s for 60 s is
# dead, while a slow-but-moving large window is left alone.  Environment /
# user-set values always win; applied once per process.
_GDAL_HTTP_GUARD_DEFAULTS = {
    "GDAL_HTTP_CONNECTTIMEOUT": "30",
    "GDAL_HTTP_TIMEOUT": "600",
    "GDAL_HTTP_LOW_SPEED_LIMIT": "1024",
    "GDAL_HTTP_LOW_SPEED_TIME": "60",
    "GDAL_HTTP_MAX_RETRY": "2",
    "GDAL_HTTP_RETRY_DELAY": "5",
    # Remote-read efficiency (curl-backed filesystems only; local files,
    # /vsizip members of local archives and the WCS driver never consult
    # these).  Without a readdir policy, every /vsicurl open probes for
    # sidecar metadata next to the COG (Landsat .met and friends, via
    # GDALMDReaderManager) at one HTTPS round trip per probe — measured
    # at ~30% of a SWISSALTI3D inset warp's wall time.  EMPTY_DIR skips
    # the directory listing AND hands the open an empty sibling list, so
    # the probes die without touching the network.  Consequence accepted:
    # remote sidecars (external .ovr overviews, .aux.xml) are invisible;
    # the COG strategies never rely on them.
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    # Block cache over curl range reads: mosaic overlap and the warp's
    # overview-then-detail access pattern re-read the same ranges.
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "33554432",
    # Swallow a COG's whole header in the first ranged request (default
    # 16 KB is one IFD too small for some providers) and read 256 KB per
    # range thereafter (default 16 KB) — fewer HTTPS round trips per
    # window.
    "GDAL_INGESTED_BYTES_AT_OPEN": "32768",
    "CPL_VSIL_CURL_CHUNK_SIZE": "262144",
}
_gdal_http_guards_applied = False


def _configure_gdal_http_guards():
    global _gdal_http_guards_applied
    if _gdal_http_guards_applied or not has_gdal:
        return
    _gdal_http_guards_applied = True
    for key, value in _GDAL_HTTP_GUARD_DEFAULTS.items():
        if os.environ.get(key) is None and gdal.GetConfigOption(key) is None:
            gdal.SetConfigOption(key, value)

#: Strategies whose ``vertical_unit`` key names the unit of POINTS that the
#: strategy itself converts while gridding (``grid_las_tile``) -- their
#: rasters are metres before the warp, so the key is never a raster unit.
_POINT_UNIT_STRATEGIES = frozenset({"las_tile_index"})


def raster_vertical_unit_stamp(path):
    """The vertical-unit stamp the shared warp left on ``path``:
    ``{"declared", "source", "applied"}`` (absent items ``None``), or
    ``None`` when the raster carries no stamp (its provider declared no
    key, or it predates the key)."""
    if not has_gdal or not path or not os.path.isfile(path):
        return None
    try:
        dataset = gdal.Open(path)
        metadata = (dataset.GetMetadata() or {}) if dataset is not None else {}
        dataset = None
    except Exception:
        return None
    stamp = {
        "declared": metadata.get(VERTICAL_UNIT_STAMP_DECLARED),
        "source": metadata.get(VERTICAL_UNIT_STAMP_SOURCE),
        "applied": metadata.get(VERTICAL_UNIT_STAMP_APPLIED),
    }
    return stamp if any(stamp.values()) else None


def raster_vertical_unit_held(path):
    """The unit the CELLS of ``path`` are in: the stamp's ``applied`` unit;
    a stamp that declares a non-metre unit and was never applied holds that
    unit; an unstamped raster is metres (no key = ``m``)."""
    stamp = raster_vertical_unit_stamp(path)
    if stamp is None:
        return "m"
    if stamp.get("applied"):
        return stamp["applied"]
    return stamp.get("declared") or "m"

# Populated lazily by initialize_elevation_providers_dict(); keyed by the
# .elv file basename (the provider CODE, e.g. "USGS3DEP").
elevation_providers_dict = {}


# =====================================================================
# Declarative provider definition (.elv) parsing
# =====================================================================
def elevation_providers_directory():
    """Return the ``Providers/Elevation`` directory path."""
    return os.path.join(FNAMES.Provider_dir, "Elevation")


#: Keys a ``.elv`` file may repeat, one record per line, instead of
#: overwriting.  Repeated lines are joined with ``;`` -- the separator the
#: list parsers already use -- so the accumulated value parses exactly like
#: a single ``;``-separated line.  Only ``coverage_bbox`` is in the set
#: (owner RULINGS 2026-09-16c: a provider declares DISJOINT regions).
#: ``resolution_ladder`` repeats the same way, one coarser rung per line
#: (#130, see :func:`_parse_resolution_ladder`).
MULTI_VALUE_KEYS = frozenset(("coverage_bbox", "resolution_ladder"))


#: The third field of a ``resolution_ladder`` line that names ANOTHER
#: provider as the rung (RULINGS 2026-09-30aw (2)).
LADDER_PROVIDER_PREFIX = "provider:"


def _parse_resolution_ladder(value, provider_code="?"):
    """The coarser rungs a provider declares, finest first (#130).

    A ``.elv`` line reads ``resolution_ladder=<native_m>|<label>|<url>``:
    the rung's native posting in metres, a human label for the log and
    the record, and the discovery URL template that lists the rung's
    products (same placeholders as ``discovery_url_template``).  Repeated
    lines join with ``;`` (:data:`MULTI_VALUE_KEYS`).  The provider's own
    definition is rung 0 and is not repeated here.  A malformed rung is
    dropped with one warning -- a ladder with a hole still climbs.
    Rungs are returned sorted finest first whatever the file order, so
    the ladder can only ever step DOWN in resolution; the sort is STABLE,
    so rungs of equal resolution keep their file order.

    CROSS-PROVIDER RUNGS (owner RULINGS 2026-09-30aw (2)): a third field
    ``provider:<CODE>`` names ANOTHER provider definition instead of a
    discovery URL -- the rung is that provider's own definition, strategy
    and coverage (:func:`_ladder_rung_definitions`).  Such a rung carries
    ``provider`` and no ``discovery_url_template``.
    """
    rungs = []
    for token in str(value or "").split(";"):
        token = token.strip()
        if not token:
            continue
        parts = [part.strip() for part in token.split("|", 2)]
        native = _parse_float(parts[0], default=None) if parts else None
        if len(parts) != 3 or native is None or native <= 0 or not parts[2]:
            UI.vprint(
                0,
                "   WARNING: elevation provider %s: malformed "
                "resolution_ladder rung %r - skipping it."
                % (provider_code, token),
            )
            continue
        rung = {
            "native_resolution_m": native,
            "label": parts[1] or ("%g m" % native),
        }
        if parts[2].startswith(LADDER_PROVIDER_PREFIX):
            other = parts[2][len(LADDER_PROVIDER_PREFIX):].strip()
            if not other:
                UI.vprint(
                    0,
                    "   WARNING: elevation provider %s: resolution_ladder "
                    "rung %r names no provider - skipping it."
                    % (provider_code, token),
                )
                continue
            rung["provider"] = other
        else:
            rung["discovery_url_template"] = parts[2]
        rungs.append(rung)
    rungs.sort(key=lambda rung: rung["native_resolution_m"])
    return rungs


def initialize_elevation_providers_dict(providers_directory=None):
    """Parse every ``Providers/Elevation/<CODE>.elv`` file.

    Same tolerant style as ``O4_Imagery_Utils.initialize_providers_dict``:
    comments (``#``) and blank lines are ignored, ``key=value`` pairs are
    kept verbatim (unknown keys preserved), and a file that cannot be read
    or lacks the mandatory ``access_strategy`` key is skipped with one
    warning line rather than aborting the run.

    Returns the populated dictionary and also stores it in the module-level
    :data:`elevation_providers_dict`.  Keyed by file basename (the CODE).
    """
    global elevation_providers_dict
    result = {}
    directory = providers_directory or elevation_providers_directory()
    if not os.path.isdir(directory):
        elevation_providers_dict = result
        return result
    for file_name in sorted(os.listdir(directory)):
        if "." not in file_name or file_name.split(".")[-1] != "elv":
            continue
        provider_code = file_name.split(".")[0]
        definition = {"code": provider_code}
        try:
            with open(os.path.join(directory, file_name), "r") as handle:
                lines = handle.readlines()
        except Exception:
            UI.vprint(
                0,
                "   WARNING: could not read elevation provider file",
                file_name,
                "- skipping it.",
            )
            continue
        for line in lines:
            line = line.strip()
            if "#" in line:
                if line[0] == "#":
                    continue
                line = line.split("#")[0]
            if "=" not in line:
                continue
            items = line.split("=")
            key = items[0].strip()
            value = "=".join(items[1:]).strip()
            if key in MULTI_VALUE_KEYS and key in definition:
                # A REPEATED key accumulates instead of overwriting, so a
                # provider with disjoint regions can give each box its own
                # line and its own citation comment (owner 2026-09-16c).
                # The accumulated value is the same ``;``-separated string
                # a single line may carry, so both spellings parse
                # identically.  Every other key keeps last-line-wins.
                definition[key] = definition[key] + ";" + value
            else:
                definition[key] = value
        if "access_strategy" not in definition:
            UI.vprint(
                0,
                "   WARNING: elevation provider",
                provider_code,
                "has no access_strategy field - skipping it.",
            )
            continue
        # Normalise the handful of typed fields we understand; unknown keys
        # remain untouched strings for future strategies.
        definition["role"] = (
            str(definition.get("role", ROLE_AIRPORT_INSET)).strip().lower()
            or ROLE_AIRPORT_INSET
        )
        definition["enabled"] = _parse_boolean(
            definition.get("enabled", "True")
        )
        definition["priority"] = _parse_float(
            definition.get("priority"), default=0.0
        )
        if "native_resolution_m" in definition:
            definition["native_resolution_m"] = _parse_float(
                definition.get("native_resolution_m"), default=None
            )
        if "resolution_ladder" in definition:
            definition["resolution_ladder_rungs"] = _parse_resolution_ladder(
                definition["resolution_ladder"], provider_code
            )
        if "coverage_bbox" in definition:
            boxes = _parse_bounding_boxes(definition["coverage_bbox"])
            definition["coverage_bboxes"] = boxes
            # ``coverage_bbox`` remains ONE box -- the hull -- so every
            # single-box provider parses exactly as before and consumers
            # that want a single extent are untouched.  The precise
            # declaration is ``coverage_bboxes`` (owner 2026-09-16c).
            definition["coverage_bbox"] = _bounding_box_hull(boxes)
        # role=bathymetry sources whose data stops at the waterline
        # (exposed-flats lidar): visually a binary "flats" layer, so the
        # automatic paths prefer the free OpenStreetMap fallback and only
        # masks_use_DEM_too=True fetches them (spec section 4.5).
        definition["intertidal"] = _parse_boolean(
            definition.get("intertidal", "False")
        )
        # Surface-model (DSM) providers opt into the post-fetch building
        # masking pass (see mask_building_footprints_in_surface_model).
        definition[SURFACE_MODEL_BUILDING_MASKING] = _parse_boolean(
            definition.get(SURFACE_MODEL_BUILDING_MASKING, "False")
        )
        # Residual structure masking rides the same pass.  DEFAULT OFF
        # (2026-07-18 late: live SPJC regression — the airfield itself
        # fits the estimator's bite profile, a flat plateau with lower
        # coastal land in the wide window and a scarp at its edge, and
        # sea reads as exact 0.0 ground; the mask pulled the runway-mid
        # DEM from ~28 m to ~19.6 m while runways anchor to CIFP/apt.dat
        # elevations, tearing every taxiway between the two — plus
        # coastal city substituted toward sea level).  Re-enable per
        # provider with residual_structure_masking=True once the
        # airport-region protection and water exclusion are designed.
        definition[RESIDUAL_STRUCTURE_MASKING] = _parse_boolean(
            definition.get(RESIDUAL_STRUCTURE_MASKING, "False")
        )
        # Base-tier (role=base) fields, spec section 3.6.
        if "resolution_arc_seconds" in definition:
            definition["resolution_arc_seconds"] = _parse_float(
                definition.get("resolution_arc_seconds"), default=None
            )
        if "dem1_zones" in definition:
            definition["dem1_zones"] = frozenset(
                token.strip()
                for token in str(definition["dem1_zones"]).split(",")
                if token.strip()
            )
        if "exclude_tiles" in definition:
            definition["exclude_tiles"] = _parse_tile_list(
                definition["exclude_tiles"]
            )
        # The global-ladder membership key (spec us-holder-providers §1):
        # parsed here, consumed by the ladder assembly.  Only a file that
        # carries it gains the key.
        if "ladder_member" in definition:
            definition["ladder_member"] = _parse_boolean(
                definition["ladder_member"])
        # A definition that cannot be asked SAFELY is refused at parse
        # (#155: an exportImage provider without nodata reads 0.0 = a
        # false sea level): disabled, the reason kept and printed once.
        refusal = export_image_definition_refusal(definition)
        if refusal:
            UI.vprint(0, "   WARNING: elevation provider refused at parse:",
                      refusal, "- disabled.")
            definition["enabled"] = False
            definition["definition_refusal"] = refusal
        result[provider_code] = definition
    elevation_providers_dict = result
    return result


def provider_required_capabilities(definition):
    """The capabilities a provider's fetch NEEDS, as a sorted list.

    Today that is LERC decoding, declared either by
    ``asset_compression=lerc`` (New Zealand's STAC COGs) or by the
    ``arcgis_lerc_tiles`` access strategy (the LERC blob pyramids), and
    LAS reading (``laspy``) for the ``las_tile_index`` strategy.  A
    provider needing nothing special returns ``[]`` -- its negatives
    were never in doubt and are never re-probed.
    """
    if not isinstance(definition, dict):
        return []
    needs = set()
    if str(definition.get("asset_compression", "")).lower() == "lerc":
        needs.add(CAPABILITY_LERC)
    if str(definition.get("access_strategy", "")) == "arcgis_lerc_tiles":
        needs.add(CAPABILITY_LERC)
    if str(definition.get("access_strategy", "")) == "las_tile_index":
        needs.add(CAPABILITY_LAS)
        if _definition_needs_laz(definition):
            needs.add(CAPABILITY_LAZ)
    return sorted(needs)


def run_capability_record(definition):
    """What to stamp beside a durable status for ``definition``.

    ``{"engine": <version>, "capabilities": [...]}`` -- the engine that
    wrote the status and which of the provider's required capabilities
    that engine HAD.  A provider that requires NONE still gets the
    engine stamp with an empty capability list (owner RULINGS
    2026-09-15aq (4)): nothing about it can be capability-degraded, but
    the VERSION is what decides whether its durable negative is re-asked
    once on the next engine.
    """
    required = provider_required_capabilities(definition)
    if not required:
        return {"engine": _engine_version(), "capabilities": []}
    have = []
    for capability in required:
        if capability == CAPABILITY_LERC and lerc_decode_available():
            have.append(capability)
        elif capability == CAPABILITY_LAS and las_reader_available():
            have.append(capability)
        elif capability == CAPABILITY_LAZ and laz_reader_available():
            have.append(capability)
    return {"engine": _engine_version(), "capabilities": have}


def _engine_version():
    try:
        import O4_Version

        return str(O4_Version.version)
    except Exception:
        return "unknown"


def engine_version():
    """The running engine's version string (``"unknown"`` if unreadable).

    Public because the harness's pre-build refusal names it beside the
    version a negative was recorded under.
    """
    return _engine_version()


def _record_run_capabilities(airport_record, code, definition):
    """Stamp the run's capability record for ``code`` into the record."""
    record = run_capability_record(definition)
    if record is None:
        return
    capabilities = airport_record.get("capabilities")
    if not isinstance(capabilities, dict):
        capabilities = {}
        airport_record["capabilities"] = capabilities
    capabilities[code] = record


def negative_is_unverified(airport_record, code, definition,
                           bounding_box=None):
    """Is this record's ``no-coverage`` for ``code`` UNVERIFIED?

    True when the provider needs a capability (LERC today), its declared
    coverage box REACHES this airport, and the record carries NO
    capability stamp for it: the negative was written by an engine whose
    capabilities are unknown, and 1.0.324 is proof that such an engine
    could mint one out of its own inability.  Exactly once -- the
    re-probe writes the stamp, so a genuine negative (the provider
    answered, zero pixels) is never asked again.

    False for every other status, for a provider that needs nothing, and
    -- the reason a tile in Madrid is never disturbed by New Zealand's
    LiDAR -- for a negative that only says "this provider's own declared
    box does not reach here".  That one needed no capability to write
    and cannot be a capability artefact.  ``bounding_box`` defaults to
    the box the record itself was evaluated against.
    """
    if not isinstance(airport_record, dict):
        return False
    if airport_record.get(code) != NO_COVERAGE:
        return False
    if not provider_required_capabilities(definition):
        return False
    if bounding_box is None:
        bounding_box = airport_record.get("bounding_box")
    if bounding_box is not None and not _coverage_bbox_intersects(
        definition, bounding_box
    ):
        return False
    capabilities = airport_record.get("capabilities")
    if not isinstance(capabilities, dict):
        return True
    stamp = capabilities.get(code)
    if not isinstance(stamp, dict):
        return True
    # A stamp that says the run LACKED what the provider needs verifies
    # nothing: it records the 1.0.324 condition instead of ruling it out.
    recorded = stamp.get("capabilities")
    if not isinstance(recorded, list):
        return True
    return any(
        capability not in recorded
        for capability in provider_required_capabilities(definition)
    )


def recorded_engine_version(airport_record, code):
    """The engine version stamped beside ``code``'s status, or ``None``."""
    if not isinstance(airport_record, dict):
        return None
    capabilities = airport_record.get("capabilities")
    if not isinstance(capabilities, dict):
        return None
    stamp = capabilities.get(code)
    if not isinstance(stamp, dict):
        return None
    engine = stamp.get("engine")
    return str(engine) if engine is not None else None


def negative_is_version_stale(airport_record, code, definition,
                              bounding_box=None):
    """Is this ``no-coverage`` a CAPABILITY-FREE one from another engine?

    Owner RULINGS 2026-09-15aq (4).  The 13b door above
    (:func:`negative_is_unverified`) can only reach a provider that
    DECLARES a required capability -- USGS3DEP declares none, so the 20
    false negatives the TNM outage of 2026-09-15 wrote across the two
    Phoenix tiles (RULINGS 2026-09-15q attributed the writer) were
    PERMANENT: nothing in the index could ever call them into question.

    The ruling makes the ENGINE VERSION the discriminator: each version
    re-asks every capability-free negative once (one discovery query per
    airport per version, ~0.4 s when the service is up).  The re-probe
    stamps the running version whatever the answer, so a genuine empty
    listing stays no-coverage and is not asked again until the next
    version.

    False for a capability-GATED provider (13b's door owns those,
    unchanged), for any status but ``no-coverage``, and -- so no engine
    release churns every index on earth -- for a negative that only says
    "this provider's own declared box does not reach here".  That one is
    re-derived from the boxes, needs no query, and is short-circuited
    before any fetch.
    """
    if not isinstance(airport_record, dict):
        return False
    if airport_record.get(code) != NO_COVERAGE:
        return False
    if provider_required_capabilities(definition):
        return False
    if bounding_box is None:
        bounding_box = airport_record.get("bounding_box")
    if bounding_box is not None and not _coverage_bbox_intersects(
        definition, bounding_box
    ):
        return False
    return recorded_engine_version(airport_record, code) != _engine_version()


def _bounding_box_hull(boxes):
    """The single ``(W, S, E, N)`` box enclosing ``boxes`` (or ``None``).

    ``coverage_bbox`` keeps meaning exactly what it meant -- ONE box --
    so every consumer that wants a single extent (the root-item
    pseudo-collection in the STAC strategy) is unchanged, and a
    single-box provider parses byte-identically.  The PRECISE
    declaration lives beside it in ``coverage_bboxes``.
    """
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _parse_tile_list(value):
    """Parse ``lat,lon;lat,lon;...`` into a tuple of integer tile corners."""
    tiles = []
    for pair in str(value).split(";"):
        parts = pair.split(",")
        if len(parts) != 2:
            continue
        try:
            tiles.append((int(parts[0].strip()), int(parts[1].strip())))
        except ValueError:
            continue
    return tuple(tiles)


def definition_is_ladder_only(definition):
    """``ladder_only=true``: the provider is a RUNG of another provider's
    resolution ladder (the USGS OPR / LPC rungs of USGS3DEP, #153) and is
    never ranked on its own in ``auto`` -- so it is asked exactly where
    its ladder reaches it, never recorded as an "unanswered" covering
    provider of an airport its parent already answered.  An explicit
    ``airport_elevation_providers`` list may still pin it."""
    return str((definition or {}).get("ladder_only", "")).strip().lower() \
        in ("true", "1", "yes")


def select_provider_definitions(providers_config, role=ROLE_AIRPORT_INSET):
    """Rank the provider definitions to try, honouring the config value.

    ``providers_config`` is the ``airport_elevation_providers`` string:
    ``"auto"`` uses every ``enabled=True`` definition ranked by descending
    ``priority``; an explicit comma-separated list of CODES pins and orders
    the providers exactly as listed (still skipping disabled ones).

    ``role`` filters by detail tier (spec section 3.6): the airport-inset
    path passes ``"airport_inset"`` and never sees ``role=base``
    definitions.  Definitions of another role are dropped silently -- a
    ``role=base`` file living in ``Providers/Elevation`` is simply not an
    inset provider, not a misconfiguration.  Keeping the role a parameter
    lets the Phase A2 base-selection path reuse this function unchanged.
    """
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    value = (providers_config or "auto").strip()
    if value.lower() == "auto":
        candidates = [
            definition
            for definition in elevation_providers_dict.values()
            if definition.get("enabled", True)
            and definition.get("role", ROLE_AIRPORT_INSET) == role
            and not definition_is_ladder_only(definition)
        ]
        candidates.sort(
            key=lambda definition: (
                -definition.get("priority", 0.0),
                definition["code"],
            )
        )
        return candidates
    ordered = []
    for token in value.split(","):
        code = token.strip()
        if not code:
            continue
        definition = elevation_providers_dict.get(code)
        if definition is None:
            UI.vprint(
                1,
                "   WARNING: unknown elevation provider code",
                code,
                "- ignoring it.",
            )
            continue
        if definition.get("role", ROLE_AIRPORT_INSET) != role:
            # Wrong tier for this path; ignore silently (not an error).
            continue
        if definition.get("enabled", True):
            ordered.append(definition)
    return ordered


def select_bathymetry_definition(lat, lon):
    """Return the bathymetry provider serving a tile, or ``None``.

    The single entry point for coastal bathymetry (spec section 2.1): the
    highest-``priority`` ENABLED definition whose ``role`` is
    :data:`ROLE_BATHYMETRY` and whose ``coverage_bbox`` intersects the
    one-degree tile ``(lon, lat, lon + 1, lat + 1)``, or ``None`` when no
    bathymetry provider covers the tile.  Ties on priority break on the
    provider CODE so the choice is deterministic.

    Bathymetry providers are deliberately invisible to every terrain path
    (their vertical datum is local tidal); this function is the only place
    that returns them.  ``O4_Bathymetry.ensure_bathymetry_band`` calls it.
    """
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    tile_bounding_box = (lon, lat, lon + 1, lat + 1)
    candidates = [
        definition
        for definition in elevation_providers_dict.values()
        if definition.get("enabled", True)
        and definition.get("role") == ROLE_BATHYMETRY
        and _coverage_bbox_intersects(definition, tile_bounding_box)
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda definition: (
            -definition.get("priority", 0.0),
            definition["code"],
        )
    )
    return candidates[0]


def select_bathymetry_definitions(lat, lon):
    """Every bathymetry provider covering a tile, priority-sorted.

    Like :func:`select_bathymetry_definition` but returning the full
    ordered candidate list: a provider whose coverage claim is broader
    than its actual data (the Allen Coral Atlas local library covers the
    whole reef belt on paper but only holds what the user downloaded)
    must not starve the ones behind it — the band fetch walks this list
    and falls through when a provider yields nothing.
    """
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    tile_bounding_box = (lon, lat, lon + 1, lat + 1)
    candidates = [
        definition
        for definition in elevation_providers_dict.values()
        if definition.get("enabled", True)
        and definition.get("role") == ROLE_BATHYMETRY
        and _coverage_bbox_intersects(definition, tile_bounding_box)
    ]
    candidates.sort(
        key=lambda definition: (
            -definition.get("priority", 0.0),
            definition["code"],
        )
    )
    return candidates


def fetch_inset(
    definition,
    bounding_box_wgs84,
    target_resolution_m,
    destination_path,
    footprint_prefetch=None,
    resolution_ladder=False,
    footprint_polygon=None,
):
    """Dispatch a fetch to the strategy named by the provider definition.

    This is the strategy-agnostic seam: the orchestration (discovery loop,
    caching, index, provenance, composite assembly, bake) calls only this
    function and never mentions a concrete strategy.  A new strategy plugs
    in by registering itself; nothing here changes.

    ``footprint_prefetch`` (optional :class:`TileBuildingFootprintPrefetch`)
    is handed to the surface-model masking pass so a multi-airport tile
    shares one building-footprint extract pass instead of one per airport.

    ``resolution_ladder`` (the airport-inset fetch passes ``True``): when
    the provider declares coarser rungs (``resolution_ladder=`` in its
    ``.elv``), a finest-rung result below ``INSET_MIN_VALID_FRAC`` valid
    climbs down to the next rung instead of ending in the base DEM
    (#130, KASE); see :func:`_fetch_through_resolution_ladder`.  The
    whole-tile overlay callers leave it off: there a sparse 1 m tile must
    not be traded for a coarser one.

    Returns the provenance metadata dictionary produced by the strategy, or
    ``None`` when the strategy reports no usable coverage.
    """
    _configure_gdal_http_guards()
    strategy_name = definition.get("access_strategy")
    strategy_factory = ACCESS_STRATEGIES.get(strategy_name)
    if strategy_factory is None:
        UI.vprint(
            1,
            "   WARNING: no access strategy named",
            strategy_name,
            "for elevation provider",
            definition.get("code"),
            "- skipping it.",
        )
        return None
    strategy = strategy_factory()
    if resolution_ladder and definition.get("resolution_ladder_rungs"):
        provenance = _fetch_through_resolution_ladder(
            strategy,
            definition,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            footprint_polygon=footprint_polygon,
        )
    else:
        provenance = strategy.fetch(
            definition,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
        )
    # BOTH BOXES, from here on: what was ASKED for and what the raster
    # actually CARRIES.  ``bounding_box_wgs84`` has always been the
    # request, and a warp snaps its target extent to the pixel grid (and
    # some providers clip to their own coverage), so the two differ by up
    # to about one source pixel -- measured over the whole corpus,
    # 2026-09-17.  Every existing consumer keeps reading
    # ``bounding_box_wgs84``; these are ADDITIVE, and a manifest that
    # carries neither new key is simply older.
    if provenance is not None:
        # THE VERTICAL-UNIT PROVENANCE (spec §2): what the shared warp
        # stamped on the delivered raster.  A raster from a provider with
        # no ``vertical_unit`` key carries no stamp and its record gains
        # no key (byte-identical sidecars for every pre-key provider).
        stamp = raster_vertical_unit_stamp(destination_path)
        # ``setdefault`` on the source: the LAS strategy already records
        # ``vertical_unit_source`` as its POINT unit (``ftUS`` at KASE,
        # converted while gridding) and that record is kept as written.
        if stamp is not None:
            provenance.setdefault("vertical_unit_source", stamp.get("source"))
            provenance["vertical_unit_applied"] = stamp.get("applied")
        provenance["requested_bounding_box_wgs84"] = list(bounding_box_wgs84)
        delivered = delivered_inset_bounding_box(destination_path)
        if delivered is not None:
            provenance["delivered_bounding_box_wgs84"] = list(delivered)
    # Surface-model providers (radar DSMs) opt into a post-fetch pass that
    # replaces building-contaminated pixels by interpolated ground; the
    # pass and its summary live with the fetch so every consumer of the
    # cached inset (composite source, bake, probes) sees corrected values.
    if provenance is not None and definition.get(
        SURFACE_MODEL_BUILDING_MASKING
    ):
        provenance[SURFACE_MODEL_BUILDING_MASKING] = (
            mask_building_footprints_in_surface_model(
                destination_path,
                bounding_box_wgs84,
                definition,
                footprint_prefetch=footprint_prefetch,
            )
        )
    return provenance


def _is_global_ladder_member(definition):
    """``ladder_member=True`` on an enabled ``role=airport_inset``
    definition that declares a coverage box: a rung of EVERY ladder whose
    airport box its coverage reaches (spec us-holder-providers §1, RULINGS
    2026-09-30bm).  A member with no ``coverage_bbox`` would cover the
    whole world and join every ladder; it is not a global member."""
    return (
        (definition or {}).get("ladder_member") is True
        and definition.get("enabled", True)
        and definition.get("role", ROLE_AIRPORT_INSET) == ROLE_AIRPORT_INSET
        and bool(coverage_boxes(definition))
    )


def _ladder_rung_sort_key(rung_definition, owner):
    """THE LADDER ORDER (spec us-holder-providers §1): native resolution
    ascending, then priority descending, then code.  ``owner`` is the
    definition whose priority and code the rung sorts by: the chain's own
    rungs -- its coarser discovery rungs and its explicit ``provider:``
    lines (PITKIN1M, the #153 OPR/LPC rungs) -- sort as the CHAIN (the
    root's priority and code), so among themselves they keep the file
    order and a holder tying them at one resolution sorts after them
    ("USGS when USGS has it", spec §1: holders 90 < USGS3DEP 100); a
    global member sorts as itself."""
    native = _definition_resolution_m(rung_definition)
    return (
        native if native is not None else float("inf"),
        -float(owner.get("priority", 0.0) or 0.0),
        str(owner.get("code") or ""),
    )


def _ladder_rung_definitions(definition, bounding_box_wgs84=None):
    """``[(label, definition)]`` for every rung, finest (the provider's
    own definition) first.  A coarser rung is the provider's definition
    with the rung's ``native_resolution_m`` and
    ``discovery_url_template`` -- everything else (licence, datum,
    coverage, value floor) is the provider's, by construction.

    A CROSS-PROVIDER rung (``provider:<CODE>``, RULINGS 2026-09-30aw (2))
    is the named provider's OWN definition -- its keys, its strategy, its
    coverage -- so :func:`_fetch_through_resolution_ladder` resolves the
    strategy per rung.  A rung naming an unknown or disabled provider is
    dropped with one line (a ladder with a hole still climbs).

    GLOBAL ASSEMBLY (spec us-holder-providers §1, RULINGS 2026-09-30bm):
    given the AIRPORT box (``bounding_box_wgs84``, the inset request box),
    every global member (:func:`_is_global_ladder_member`) whose coverage
    reaches the box and which no rung already names joins the ladder, and
    rungs 1.. are STABLE-sorted by :func:`_ladder_rung_sort_key`; rung 0
    stays pinned first.  A member outside its box is not a rung (no row,
    no call).  Without a box (or with no covering member) the list is the
    chain alone, exactly as before -- the chain's rungs are already
    finest-first and sort as one owner, so the sort cannot reorder them.
    THE one assembly site: the ladder, :func:`ladder_recheck`, the harness
    and the gap census all read rungs here."""
    native = _definition_resolution_m(definition)
    rungs = [
        (definition.get("ladder_label")
         or ("%g m" % native if native else definition.get("code")),
         definition)
    ]
    for rung in definition.get("resolution_ladder_rungs") or ():
        other_code = rung.get("provider")
        if other_code:
            if not elevation_providers_dict:
                initialize_elevation_providers_dict()
            other = elevation_providers_dict.get(other_code)
            if other is None or not other.get("enabled", True):
                UI.vprint(
                    1,
                    "   [inset] %s: resolution ladder rung '%s' names "
                    "provider %s, which is %s - skipping the rung."
                    % (definition.get("code"), rung["label"], other_code,
                       "unknown" if other is None else "disabled"),
                )
                continue
            rung_definition = dict(other)
            rung_definition.pop("resolution_ladder_rungs", None)
            rungs.append((rung["label"], rung_definition))
            continue
        rung_definition = dict(definition)
        rung_definition["native_resolution_m"] = rung["native_resolution_m"]
        rung_definition["discovery_url_template"] = (
            rung["discovery_url_template"])
        rung_definition.pop("resolution_ladder_rungs", None)
        rungs.append((rung["label"], rung_definition))
    if bounding_box_wgs84 is None:
        return rungs
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    named = {str(rung_definition.get("code"))
             for (_label, rung_definition) in rungs}
    labels = {label for (label, _rung_definition) in rungs}
    ordered = [(_ladder_rung_sort_key(rung_definition, definition), label,
                rung_definition)
               for (label, rung_definition) in rungs[1:]]
    for code in sorted(elevation_providers_dict):
        member = elevation_providers_dict[code]
        if (str(member.get("code")) in named
                or not _is_global_ladder_member(member)
                or not _coverage_bbox_intersects(member,
                                                 bounding_box_wgs84)):
            continue
        label = member.get("ladder_label") or member.get("code")
        if label in labels:
            label = member.get("code")
        member_definition = dict(member)
        member_definition.pop("resolution_ladder_rungs", None)
        ordered.append((_ladder_rung_sort_key(member_definition,
                                              member_definition),
                        label, member_definition))
        named.add(str(member.get("code")))
        labels.add(label)
    ordered.sort(key=lambda entry: entry[0])
    return [rungs[0]] + [(label, rung_definition)
                         for (_key, label, rung_definition) in ordered]


def _listing_ids(sources):
    """The sorted ids of a DISCOVERY listing (tnm: ``sourceId``; a LAS
    tile index: the tile name) -- what the ladder records per rung and
    what :func:`ladder_recheck` compares against."""
    ids = set()
    for source in sources or ():
        if isinstance(source, dict) and source.get("source_id") is not None:
            ids.add(str(source["source_id"]))
    return sorted(ids)


def _provenance_listing_ids(provenance):
    """The discovery listing a fetch saw, read back out of its record:
    every source it names -- contributing, empty over the box, or listed
    and missing on the server -- so a rung's ``listing_ids`` is the whole
    listing, not only what held data."""
    ids = set()
    for key in ("source_ids", "tiles_missing"):
        for value in provenance.get(key) or ():
            if value is not None:
                ids.add(str(value))
    for key in ("sources_used", "sources_empty_over_bbox",
                "sources_excluded_too_coarse"):
        for entry in provenance.get(key) or ():
            if isinstance(entry, dict) and entry.get("source_id") is not None:
                ids.add(str(entry["source_id"]))
    return sorted(ids)


def _fetch_through_resolution_ladder(
    strategy,
    definition,
    bounding_box_wgs84,
    target_resolution_m,
    destination_path,
    footprint_polygon=None,
):
    """THE RESOLUTION LADDER (#130): finest product first, coarser only
    when the finer one carries no coverage.

    KASE (Aspen) sits in the one 10 km cell of the only 1 m 3DEP project
    around it that was never flown: its 1 m mosaic -- every overlapping
    source, R13-2 -- held 0.22 % valid pixels, the bake refused it, and
    the airport was graded on the 30 m base DEM while 3DEP publishes a
    seamless 1/3 arc-second (~10 m) layer over the same box.  A rung is
    judged by the bake's own rule, :func:`inset_is_effectively_empty`
    (``INSET_MIN_VALID_FRAC``): below it the next rung is fetched; the
    first rung at or above it is delivered.  The rungs and their
    discovery live in the provider's ``.elv`` (``resolution_ladder=``);
    the threshold is the bake's.  No literal here.

    Every rung tried prints one ``[inset]`` line (none when the finest
    rung answers, the ordinary case), and the record carries a
    ``ladder`` block naming each rung, its outcome and valid fraction,
    and the rung delivered.  When every rung is below the threshold the
    FINEST sub-threshold raster is kept (the pre-ladder behaviour: the
    bake refuses it loudly and the next run asks again); ``None`` --
    no-coverage -- only when no rung listed any product at all.  A rung
    that raises a transient outage is recorded ``transient`` (no listing,
    so the build-time re-check asks it again) and the ladder climbs on
    (owner RULINGS 2026-09-30bl: every failure class falls through); only
    a ladder that delivers NOTHING re-raises it -- an unfinished ladder
    with no delivery is no durable answer.

    AIRPORT-COVER RUNGS (#153): a rung whose definition declares
    ``ladder_judge=airport_cover`` (the USGS Original Product Resolution
    rung) is judged like a surgical core -- delivered only when it holds
    ``INSET_MIN_AIRPORT_COVER_FRAC`` of the aerodrome boundary box.

    CROSS-PROVIDER (RULINGS 2026-09-30aw (2)): a rung may be ANOTHER
    provider (``provider:<CODE>``); its strategy is resolved PER RUNG, a
    rung whose own ``coverage_bbox`` misses the box is
    ``out-of-coverage`` with no network call, and a rung that cannot be
    ASKED on this engine (:class:`ProviderUnavailable` -- a missing
    capability, a size cap) is ``unavailable`` and the ladder climbs on
    (the chain's own rungs keep serving; the build-time re-check asks the
    rung again).  Each rung records its provider and ``listing_ids`` --
    the discovery listing at fetch time, which :func:`ladder_recheck`
    compares against on every later build.

    TWO-LAYER (spec §4, owner 30ay).  ``footprint_polygon`` (the
    aerodrome boundary, EPSG:4326) rides every provider rung as
    :data:`LAS_FOOTPRINT_KEY`; a rung that answers with a ``core`` block
    (a surgical LAS fetch) is judged over the AIRPORT
    (``airport_valid_fraction`` >= :data:`INSET_MIN_AIRPORT_COVER_FRAC`
    over the boundary box) and, when delivered, the ladder fetches the
    next covering rung over the whole box as the SURROUND and
    :class:`LadderInsetAssembly` writes ONE raster: surround, then the
    core, blended over ``core_feather_m`` inside the core edge.

    HOLES FILL DOWN THE LADDER (spec §12, owner RULINGS 2026-10-01d).  A
    delivered core -- a surgical core, an airport-cover rung, or a
    PARTIAL rung (30bu) -- is assembled over the ladder's own coarser
    covering rungs (never an airport-cover, point-cloud or AOI rung,
    :func:`_rung_can_be_surround`): fetched FINEST FIRST, one more while a
    cell the fills must answer (outside a surgical core's region, or in
    an EDGE NoData island -- one touching the core's coverage or box
    edge) is still unanswered -- 3 m, then 10 m.  An INTERIOR island
    (ringed by valid core) is interpolated from the core's own ring
    instead (spec-author refinement 2026-10-01).  The base DEM is the
    floor of last resort.  An airport-cover or partial rung without an
    edge island fetches nothing more.  The sidecar records ``holes`` (one row per
    interior hole), ``fills`` (the layers, the box-wide
    ``filled_fraction``, the rung the ladder ran out at) and
    ``airport_filled_fraction`` beside the core's own
    ``airport_valid_fraction``.
    """
    threshold = INSET_MIN_VALID_FRAC
    base_name = os.path.basename(destination_path)
    footprint_mapping = None
    boundary_box = None
    if footprint_polygon is not None and not footprint_polygon.is_empty:
        footprint_mapping = _polygon_mapping(footprint_polygon)
        boundary_box = tuple(footprint_polygon.bounds)
    rungs = _ladder_rung_definitions(definition, bounding_box_wgs84)
    if footprint_mapping is not None:
        rungs = [
            (label, dict(rung_definition, **{LAS_FOOTPRINT_KEY:
                                             footprint_mapping})
             if rung_definition.get("code") != definition.get("code")
             else rung_definition)
            for (label, rung_definition) in rungs
        ]
    attempts = []
    delivered = None          # (index, path, provenance)
    fallback = None           # finest sub-threshold (index, path, provenance)
    scratch_paths = []
    transient_errors = []
    unavailable_errors = []   # rung 0's ProviderUnavailable, raised last

    def _try_rung(index, label, rung_definition, rung_path, rung_target,
                  rung_strategy):
        """Fetch ONE rung; ``(attempt, provenance)``.  Transient raises."""
        attempt = {
            "rung": index,
            "label": label,
            "provider": rung_definition.get("code"),
            "native_resolution_m": rung_definition.get(
                "native_resolution_m"),
            "resolution_m": rung_target,
        }
        provenance = None
        unavailable = None
        if index > 0 and not _coverage_bbox_intersects(
                rung_definition, bounding_box_wgs84):
            attempt["outcome"] = "out-of-coverage"
            attempt["valid_fraction"] = 0.0
            return (attempt, None)
        if rung_strategy is None:
            factory = ACCESS_STRATEGIES.get(
                rung_definition.get("access_strategy"))
            rung_strategy = factory() if factory else None
        if rung_strategy is None:
            unavailable = "no access strategy named %r" % (
                rung_definition.get("access_strategy"),)
        else:
            try:
                provenance = rung_strategy.fetch(
                    rung_definition, bounding_box_wgs84, rung_target,
                    rung_path)
            except ProviderUnavailable as error:
                # RUNG 0 CLIMBS TOO (spec us-holder-providers §1 outcome
                # table: ``unavailable`` -> next rung, "only transient
                # raises"; RULINGS 2026-09-30bu (1)): an undecodable USGS
                # 1 m product must not skip the 1/9" and 1/3" rungs.  When
                # NOTHING is delivered or kept the rung-0 refusal is raised
                # after the ladder (below), so the provider still records
                # ``unavailable:<reason>`` -- never a durable no-coverage.
                if index == 0:
                    unavailable_errors.append(error)
                unavailable = error.reason
            except TransientFetchError as error:
                # EVERY FAILURE CLASS FALLS THROUGH (owner RULINGS
                # 2026-09-30bl): an outage on one rung is no answer FOR
                # THAT RUNG -- it records no listing, so the build-time
                # re-check asks it again -- and the ladder climbs on.
                # Only a ladder that delivers NOTHING re-raises it.
                attempt["outcome"] = "transient"
                attempt["transient_reason"] = str(error)
                attempt["valid_fraction"] = 0.0
                transient_errors.append(error)
                if os.path.isfile(rung_path):
                    os.remove(rung_path)
                return (attempt, None)
        if unavailable is not None:
            attempt["outcome"] = "unavailable"
            attempt["unavailable_reason"] = unavailable
            attempt["valid_fraction"] = 0.0
            if os.path.isfile(rung_path):
                os.remove(rung_path)
            return (attempt, None)
        if provenance is None:
            attempt["outcome"] = "no-coverage"
            attempt["valid_fraction"] = 0.0
            # What discovery listed although nothing usable came of it
            # (a listing of products all too coarse, a warp that held
            # nothing): recorded, so the re-check does not read the same
            # listing as new on every build.
            attempt["listing_ids"] = _listing_ids(
                getattr(rung_strategy, "last_listing", None))
            if os.path.isfile(rung_path):
                os.remove(rung_path)       # a failed warp's partial file
            return (attempt, None)
        valid_fraction = inset_valid_fraction(rung_path)
        attempt["valid_fraction"] = round(valid_fraction, 6)
        attempt["sources_used"] = len(
            provenance.get("sources_used")
            or provenance.get("source_urls") or ())
        attempt["listing_ids"] = _provenance_listing_ids(provenance)
        _record_rung_units_and_bytes(attempt, provenance, rung_path)
        if boundary_box and (
                isinstance(provenance.get("core"), dict)
                or _rung_judged_by_airport_cover(rung_definition)):
            # A SURGICAL CORE -- or a rung that declares
            # ``ladder_judge=airport_cover`` (the USGS OPR rung, #153) --
            # is judged over the AIRPORT, not the box.
            airport_fraction = raster_valid_fraction_in_box(
                rung_path, boundary_box)
            attempt["airport_valid_fraction"] = round(airport_fraction, 6)
            attempt["judge"] = "airport_cover"
            attempt["outcome"] = (
                "delivered"
                if airport_fraction >= INSET_MIN_AIRPORT_COVER_FRAC
                else "below-threshold")
        else:
            attempt["outcome"] = (
                "delivered" if valid_fraction >= threshold
                else "below-threshold")
            if boundary_box and attempt["outcome"] == "delivered":
                # Recorded so the loop can tell a box-rule rung that
                # misses part of the AIRPORT (KGEG's 1 m: 54 %) from one
                # that covers it (#153).
                attempt["airport_valid_fraction"] = round(
                    raster_valid_fraction_in_box(rung_path, boundary_box),
                    6)
        return (attempt, provenance)

    def _say(attempt, total):
        index = attempt["rung"]
        if attempt["outcome"] == "no-coverage":
            what = "no product listed over the box"
        elif attempt["outcome"] == "transient":
            what = ("%s did not answer (%s)"
                    % (attempt["provider"], attempt["transient_reason"]))
        elif attempt["outcome"] == "out-of-coverage":
            what = ("%s's coverage does not reach the box (not "
                    "asked)" % attempt["provider"])
        elif attempt["outcome"] == "unavailable":
            what = ("%s could not be asked: %s"
                    % (attempt["provider"], attempt["unavailable_reason"]))
        elif attempt["outcome"] == "partial":
            what = ("valid %.2f %% but airport cover %.2f %% (< %.2f %%)"
                    % (100.0 * attempt["valid_fraction"],
                       100.0 * attempt["airport_valid_fraction"],
                       100.0 * INSET_MIN_AIRPORT_COVER_FRAC))
        elif attempt.get("judge") == "airport_cover":
            what = ("airport cover %.2f %% (%s %.2f %%)"
                    % (100.0 * attempt["airport_valid_fraction"],
                       ">=" if attempt["outcome"] == "delivered" else "<",
                       100.0 * INSET_MIN_AIRPORT_COVER_FRAC))
        else:
            what = ("valid %.2f %% (%s %.2f %%)"
                    % (100.0 * attempt["valid_fraction"],
                       ">=" if attempt["outcome"] == "delivered" else "<",
                       100.0 * threshold))
        if attempt.get("role") in ("surround", "fill"):
            tail = ((" - %s" % attempt["role"].upper())
                    if attempt["outcome"] == "delivered"
                    else " - next %s rung" % attempt["role"])
        elif attempt["outcome"] == "partial":
            tail = (" - kept; asking the same-resolution rungs for the "
                    "whole airport")
        else:
            tail = (" - DELIVERED" if attempt["outcome"] == "delivered"
                    else (" - trying the next rung" if index + 1 < total
                          else " - no rung left"))
        UI.vprint(
            0,
            "   [inset] %s: resolution ladder rung %d/%d '%s' (%g m): %s%s"
            % (base_name, index + 1, total, attempt["label"],
               attempt["resolution_m"], what, tail),
        )

    def _rung_target(index, rung_definition):
        if index == 0:
            return target_resolution_m
        return max(
            float(target_resolution_m),
            float(_definition_resolution_m(rung_definition)
                  or target_resolution_m))

    partial = None            # (index, path, provenance, native metres)
    try:
        for index, (label, rung_definition) in enumerate(rungs):
            if partial is not None and (
                    _definition_resolution_m(rung_definition)
                    or float("inf")) > partial[3]:
                # Past the partial rung's resolution class: the partial
                # rung is the best this ladder has (below).
                break
            if index == 0:
                rung_path = destination_path
                rung_strategy = strategy
            else:
                rung_path = "%s.rung%d" % (destination_path, index)
                scratch_paths.append(rung_path)
                if os.path.isfile(rung_path):
                    os.remove(rung_path)
                rung_strategy = None
            (attempt, provenance) = _try_rung(
                index, label, rung_definition, rung_path,
                _rung_target(index, rung_definition), rung_strategy)
            attempts.append(attempt)
            native = _definition_resolution_m(rung_definition) or 0.0
            if (attempt["outcome"] == "delivered" and partial is None
                    and attempt.get("judge") != "airport_cover"
                    and attempt.get("airport_valid_fraction") is not None
                    and attempt["airport_valid_fraction"]
                    < INSET_MIN_AIRPORT_COVER_FRAC
                    and any((_definition_resolution_m(other) or 0.0)
                            <= native for (_l, other) in rungs[index + 1:])):
                # BEST AVAILABLE AT THIS RESOLUTION (#153, owner RULINGS
                # 2026-09-30bl): the box rule delivers a mosaic that
                # misses part of the AIRPORT (KGEG: USGS 1 m covers
                # 54 %, its holes fall to the 30 m base DEM).  The rungs
                # of the SAME resolution class are asked whether they
                # cover the whole airport (the OPR tiles of the same
                # flight do); the first that does wins, else this rung
                # is delivered exactly as before.  Coarser rungs are
                # never traded for it.
                attempt["outcome"] = "partial"
                partial = (index, rung_path, provenance, native)
                _say(attempt, len(rungs))
                continue
            if index > 0 or attempt["outcome"] != "delivered":
                _say(attempt, len(rungs))
            if attempt["outcome"] == "delivered":
                delivered = (index, rung_path, provenance)
                break
            if attempt["outcome"] == "below-threshold":
                if fallback is None:
                    fallback = (index, rung_path, provenance)
                elif rung_path != destination_path:
                    os.remove(rung_path)
        partial_delivered = False
        if delivered is None and partial is not None:
            (index, rung_path, provenance, _native) = partial
            attempts[index]["outcome"] = "delivered"
            delivered = (index, rung_path, provenance)
            partial_delivered = True
        if delivered is None and transient_errors:
            # Nothing delivered and a rung never answered: no durable
            # answer (30t) -- the caller records nothing, the next run
            # asks again.
            raise transient_errors[0]
        chosen = delivered or fallback
        if chosen is None and unavailable_errors:
            # Rung 0 could not be asked and no other rung listed anything:
            # the provider's answer is ``unavailable`` (13b), as before.
            raise unavailable_errors[0]
        if chosen is None:
            return None
        (index, rung_path, provenance) = chosen
        provenance = dict(provenance)
        delivered_attempt = attempts[index]
        is_core = (delivered is not None
                   and isinstance(provenance.get("core"), dict))
        if delivered is not None and (
                is_core or partial_delivered
                or delivered_attempt.get("judge") == "airport_cover"):
            # HOLES FILL DOWN THE LADDER (spec §12): the surround of a
            # surgical core, and every interior hole of a delivered core.
            _assemble_down_the_ladder(
                provenance, index, rung_path, rungs, is_core,
                attempts, delivered_attempt, boundary_box, destination_path,
                scratch_paths,
                lambda other, label, definition, path: _try_rung(
                    other, label, definition, path,
                    _rung_target(other, definition), None),
                lambda attempt: _say(attempt, len(rungs)))
        if rung_path != destination_path:
            os.replace(rung_path, destination_path)
        provenance["ladder"] = {
            "threshold_valid_fraction": threshold,
            "airport_cover_threshold": INSET_MIN_AIRPORT_COVER_FRAC,
            "rungs_tried": attempts,
            "delivered_rung": index if delivered is not None else None,
            "delivered_label": (
                attempts[index]["label"] if delivered is not None else None),
            "delivered_provider": (
                (provenance.get("provider") or attempts[index]["provider"])
                if delivered is not None else None),
        }
        if footprint_mapping is not None:
            provenance["ladder"][LAS_FOOTPRINT_KEY] = footprint_mapping
        return provenance
    finally:
        for path in scratch_paths:
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:                          # pragma: no cover
                    pass


def _assemble_down_the_ladder(provenance, index, rung_path, rungs, is_core,
                              attempts, delivered_attempt, boundary_box,
                              destination_path, scratch_paths, try_rung,
                              say):
    """The fill climb of :func:`_fetch_through_resolution_ladder` (spec
    §12): assemble the delivered raster at ``rung_path`` over the ladder's
    coarser covering rungs, finest first, until the box is valid; stamp
    ``provenance`` in place.  ``try_rung(other, label, definition, path)``
    is the ladder's own rung fetch."""
    rung_definition = rungs[index][1]
    if is_core:
        from shapely.geometry import shape

        core = dict(provenance["core"])
        core["rung"] = index
        feather_m = core.get("feather_m")
        if feather_m is None:
            feather_m = LAS_DEFAULT_CORE_FEATHER_M
        core["feather_m"] = float(feather_m)
        assembly = LadderInsetAssembly(
            rung_path,
            shape(core["boundary_polygon_wgs84"]) if core.get(
                "boundary_polygon_wgs84") else None,
            float(core.get("footprint_buffer_m") or 0.0),
            core["feather_m"])
    else:
        core = None
        assembly = LadderInsetAssembly(
            rung_path,
            feather_m=_parse_float(rung_definition.get("core_feather_m"),
                                   default=LAS_DEFAULT_CORE_FEATHER_M),
            core_region_is_box=True)
    tried = {attempt["rung"] for attempt in attempts}
    used = []                 # [(rung, provenance, attempt)]
    last_tried = None
    if assembly.needs_fill():
        for (other, (label, fill_definition)) in enumerate(rungs):
            if other <= index or other in tried:
                continue
            if not _rung_can_be_surround(fill_definition):
                continue
            if used and not assembly.needs_fill():
                break
            fill_path = "%s.surround%d" % (destination_path, other)
            scratch_paths.append(fill_path)
            if os.path.isfile(fill_path):
                os.remove(fill_path)
            (attempt, fill_provenance) = try_rung(other, label,
                                                  fill_definition, fill_path)
            attempt["role"] = "surround" if is_core else "fill"
            last_tried = label
            answered = 0
            if (fill_provenance is not None
                    and attempt["valid_fraction"] > 0.0):
                answered = assembly.add_fill(fill_path, {
                    "provider": fill_provenance.get("provider"),
                    "rung": other, "label": label})
                if answered == 0:
                    assembly.fills.pop()     # holds nothing a fill must
            if answered > 0:
                attempt["outcome"] = "delivered"
            elif attempt["outcome"] == "delivered":
                attempt["outcome"] = "below-threshold"
            attempts.append(attempt)
            say(attempt)
            if answered > 0:
                used.append((other, fill_provenance, attempt))
    if used or assembly.interpolated():
        record = assembly.write(rung_path)
    else:
        # Nothing to assemble over: the raster stands as fetched.
        record = assembly.unwritten_record()
    ran_out = None
    if assembly.needs_fill():
        ran_out = last_tried or "no coarser covering rung"
    layers = [{
        "provider": fill_provenance.get("provider"),
        "rung": other,
        "label": rungs[other][0],
        "native_resolution_m": fill_provenance.get("native_resolution_m"),
        "source_ids": list(fill_provenance.get("source_ids") or ()),
        "valid_fraction": attempt["valid_fraction"],
    } for (other, fill_provenance, attempt) in used]
    if is_core:
        core.update({key: record[key] for key in (
            "region_pixels", "seam_median_offset_m",
            "core_holes_left_nodata")})
        provenance["surround"] = layers[0] if layers else None
        provenance["core"] = core
    provenance["holes"] = record["holes"]
    provenance["fills"] = {
        "layers": layers,
        "hole_min_cells": record["hole_min_cells"],
        "feather_m": assembly.feather_m,
        "filled_fraction": record["filled_fraction"],
        "fill_share": record["fill_share"],
        "islands": record["islands"],
        "interior_islands": record["interior_islands"],
        "interior_cells": record["interior_cells"],
        "edge_islands": record["edge_islands"],
        "edge_cells": record["edge_cells"],
        "interpolation_left_cells": record["interpolation_left_cells"],
        "sub_threshold_voids": record["sub_threshold_voids"],
        "sub_threshold_cells": record["sub_threshold_cells"],
        "unanswered_cells": record["unanswered_cells"],
        "box_edge_sliver_cells": record["box_edge_sliver_cells"],
        "ran_out": ran_out,
    }
    provenance["airport_valid_fraction"] = delivered_attempt.get(
        "airport_valid_fraction")
    provenance["airport_filled_fraction"] = (
        round(raster_valid_fraction_in_box(rung_path, boundary_box), 6)
        if boundary_box else None)
    provenance["valid_fraction"] = round(inset_valid_fraction(rung_path), 6)


def _record_rung_units_and_bytes(attempt, provenance, rung_path):
    """Per-rung record (spec us-holder-providers §1/§2): the vertical unit
    the rung's raster was read in and whether the shared warp converted it
    (``vertical_unit_source`` / ``vertical_unit_applied`` -- from the
    strategy's own record, else the warp's stamp on the rung raster), and
    ``bytes_fetched`` where the strategy counts it.  A rung with none of
    them gains no key (pre-key providers keep byte-identical rows)."""
    stamp = raster_vertical_unit_stamp(rung_path) or {}
    source = provenance.get("vertical_unit_source") or stamp.get("source")
    applied = provenance.get("vertical_unit_applied") or stamp.get("applied")
    if source:
        attempt["vertical_unit_source"] = source
    if applied:
        attempt["vertical_unit_applied"] = applied
    if provenance.get("bytes_fetched") is not None:
        attempt["bytes_fetched"] = provenance["bytes_fetched"]


def _rung_judged_by_airport_cover(rung_definition):
    """``ladder_judge=airport_cover``: the rung is delivered only when it
    covers the AIRPORT (``INSET_MIN_AIRPORT_COVER_FRAC`` of the aerodrome
    boundary box), the rule a surgical LAS core is judged by (#153)."""
    return str((rung_definition or {}).get("ladder_judge", "")).strip() \
        .lower() == "airport_cover"


def _rung_can_be_surround(rung_definition):
    """A two-layer SURROUND is the coarse WHOLE-BOX layer: never a
    surgical point-cloud rung (it lists only the airport's tiles) and
    never a rung judged by airport cover (its box may be partial -- the
    surround's holes would fall to the base DEM where the next seamless
    rung covers them)."""
    if str((rung_definition or {}).get("access_strategy")) in \
            SURGICAL_ONLY_STRATEGIES:
        return False
    return not _rung_judged_by_airport_cover(rung_definition)


#: Strategies that list or POST only the airport's own footprint (a
#: surgical core), never the whole box: a point-cloud tile index and the
#: polygon-POST portals (aoi154).  None of them is ever a two-layer
#: SURROUND (RULINGS 2026-09-30bu (5); spec us-holder-providers §1).
SURGICAL_ONLY_STRATEGIES = ("las_tile_index", "aoi_zip_download")


#: The core's seam blend when a provider declares no ``core_feather_m``:
#: the bake's own ``airport_elevation_inset_feather_m`` default.
LAS_DEFAULT_CORE_FEATHER_M = 60.0


def feather_weight(distance_to_edge_m, feather_m):
    """THE ONE FEATHER (spec §4): ``clip(d / feather, 0, 1)`` -- the
    weight an inside value takes at ``d`` metres inside its edge.  The
    bake (:func:`_bake_one_inset`) and the ladder assembler
    (:class:`LadderInsetAssembly`) both call this; a zero feather is
    a hard edge (weight 1 from the edge in)."""
    distance_to_edge_m = numpy.asarray(distance_to_edge_m)
    if feather_m and feather_m > 0:
        return numpy.clip(distance_to_edge_m / float(feather_m), 0.0, 1.0)
    return (distance_to_edge_m >= 0).astype(numpy.float32)


def raster_valid_fraction_in_box(raster_path, box_wgs84):
    """Share of ``raster_path``'s pixels inside ``box_wgs84`` that hold
    data (not nodata, finite).  ``0.0`` when unreadable or outside."""
    if not has_gdal:
        return 0.0
    try:
        dataset = gdal.Open(raster_path)
        transform = dataset.GetGeoTransform()
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        (west, south, east, north) = box_wgs84
        col0 = int(math.floor((west - transform[0]) / transform[1]))
        col1 = int(math.ceil((east - transform[0]) / transform[1]))
        row0 = int(math.floor((north - transform[3]) / transform[5]))
        row1 = int(math.ceil((south - transform[3]) / transform[5]))
        col0, row0 = max(col0, 0), max(row0, 0)
        col1 = min(col1, dataset.RasterXSize)
        row1 = min(row1, dataset.RasterYSize)
        if col1 <= col0 or row1 <= row0:
            return 0.0
        values = band.ReadAsArray(col0, row0, col1 - col0, row1 - row0)
        dataset = None
    except Exception:
        return 0.0
    valid = numpy.isfinite(values)
    if nodata is not None:
        valid &= values != nodata
    return float(valid.mean()) if valid.size else 0.0


#: THE HOLE REPORT THRESHOLD (spec las-tile-lidar-provider §12, owner
#: RULINGS 2026-10-01d; spec-author refinement 2026-10-01): a NoData island
#: of at least this many cells gets its own sidecar ``holes`` row; smaller
#: ones are counted (``sub_threshold_voids``).  It never chooses the fill:
#: an INTERIOR island (ringed by valid core cells) interpolates from the
#: core's own ring, an EDGE island fills down the ladder, whatever the size.
INSET_HOLE_MIN_CELLS = 4

#: The assembled raster's NoData (every inset layer the ladder writes).
LADDER_INSET_NODATA = -32768.0

#: ``filled_by`` of an interior island: interpolated from the core's ring.
HOLE_FILLED_BY_CORE_INTERPOLATION = "core_interpolation"


def _distance_to_mask_m(mask, transform, feather_m):
    """Metres from every pixel to the nearest ``mask`` pixel, saturated a
    little beyond ``feather_m`` (the only distances the feather reads):
    the two-layer assembler's proximity, verbatim (pixel distance times
    the cell's north-south metres)."""
    height, width = mask.shape
    driver = gdal.GetDriverByName("MEM")
    source = driver.Create("", width, height, 1, gdal.GDT_Byte)
    source.SetGeoTransform(transform)
    source.GetRasterBand(1).WriteArray(mask.astype(numpy.uint8))
    proximity = driver.Create("", width, height, 1, gdal.GDT_Float32)
    proximity.SetGeoTransform(transform)
    pixel_m = abs(transform[5]) * GEO.lat_to_m
    gdal.ComputeProximity(
        source.GetRasterBand(1), proximity.GetRasterBand(1),
        ["VALUES=1", "DISTUNITS=PIXEL",
         "MAXDIST=%d" % (int(math.ceil(feather_m / pixel_m)) + 2),
         "NODATA=%d" % (int(math.ceil(feather_m / pixel_m)) + 3)])
    distance_m = proximity.GetRasterBand(1).ReadAsArray() * pixel_m
    source = proximity = None
    return distance_m


def _dilate_8(mask):
    """``mask`` grown by one cell in all 8 directions."""
    grown = mask.copy()
    padded = numpy.pad(mask, 1)
    (height, width) = mask.shape
    for (dr, dc) in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1),
                     (1, -1), (1, 0), (1, 1)):
        grown |= padded[1 + dr:1 + dr + height, 1 + dc:1 + dc + width]
    return grown


def inset_void_islands(void, outside):
    """The 8-connected NoData islands of ``void`` (a boolean grid),
    classified: ``(labels, islands)``.  ``labels`` is an int32 grid, ``k``
    (1-based) on the cells of the k-th island, 0 elsewhere; ``islands``
    lists ``{"label", "cells", "box_px": (col0, row0, col1, row1),
    "interior": bool}`` largest first (ties by position).  An island is
    INTERIOR when its 8-neighbour ring holds only valid core cells: it
    touches neither ``outside`` (the cells beyond the core region) nor the
    raster's own edge (the inset box edge).  GDAL's polygoniser labels in
    pixel space (an identity transform: a polygon's area IS its cell
    count); no new dependency."""
    height, width = void.shape
    labels = numpy.zeros((height, width), dtype=numpy.int32)
    if not void.any():
        return (labels, [])
    driver = gdal.GetDriverByName("MEM")
    identity = (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    raster = driver.Create("", width, height, 1, gdal.GDT_Byte)
    raster.SetGeoTransform(identity)
    band = raster.GetRasterBand(1)
    band.WriteArray(void.astype(numpy.uint8))
    vector_driver = (ogr.GetDriverByName("MEM")
                     or ogr.GetDriverByName("Memory"))
    vector = vector_driver.CreateDataSource("voids")
    layer = vector.CreateLayer("voids", None, ogr.wkbPolygon)
    layer.CreateField(ogr.FieldDefn("v", ogr.OFTInteger))
    gdal.Polygonize(band, band, layer, 0, ["8CONNECTED=8"])
    found = []
    for feature in layer:
        geometry = feature.GetGeometryRef()
        (x0, x1, y0, y1) = geometry.GetEnvelope()
        found.append((int(round(geometry.GetArea())),
                      (int(round(x0)), int(round(y0)),
                       int(round(x1)), int(round(y1))),
                      geometry.Clone()))
    found.sort(key=lambda item: (-item[0], item[1][1], item[1][0]))
    keep = vector.CreateLayer("islands", None, ogr.wkbPolygon)
    keep.CreateField(ogr.FieldDefn("label", ogr.OFTInteger))
    islands = []
    for (number, (cells, box_px, geometry)) in enumerate(found, start=1):
        feature = ogr.Feature(keep.GetLayerDefn())
        feature.SetField("label", number)
        feature.SetGeometry(geometry)
        keep.CreateFeature(feature)
        islands.append({"label": number, "cells": cells, "box_px": box_px})
    label_raster = driver.Create("", width, height, 1, gdal.GDT_Int32)
    label_raster.SetGeoTransform(identity)
    gdal.RasterizeLayer(label_raster, [1], keep,
                        options=["ATTRIBUTE=label"])
    labels = label_raster.GetRasterBand(1).ReadAsArray().astype(numpy.int32)
    labels[~void] = 0
    vector = raster = label_raster = None
    # EDGE: an island cell 8-adjacent to ``outside`` or on the raster edge.
    touching = _dilate_8(outside) & void
    touching[0, :] |= void[0, :]
    touching[-1, :] |= void[-1, :]
    touching[:, 0] |= void[:, 0]
    touching[:, -1] |= void[:, -1]
    edge_labels = set(numpy.unique(labels[touching]).tolist()) - {0}
    for island in islands:
        island["interior"] = island["label"] not in edge_labels
    return (labels, islands)


def _interpolate_interior_islands(values, valid, labels, islands):
    """Fill every INTERIOR island of ``values`` from its own valid ring
    (``gdal.FillNodata``, the bake's footprint-fill interpolation:
    ``DEFAULT_FILL_SMOOTHING_ITERATIONS`` smoothing passes), one window
    per island, the search reaching across it.  Writes ``values`` /
    ``valid`` in place on the island cells only; returns the island cells
    left unfilled (none, unless the ring itself is missing)."""
    (height, width) = values.shape
    driver = gdal.GetDriverByName("MEM")
    left = 0
    for island in islands:
        if not island["interior"]:
            continue
        (c0, r0, c1, r1) = island["box_px"]
        search = max(c1 - c0, r1 - r0) + 2
        (wc0, wr0) = (max(c0 - search, 0), max(r0 - search, 0))
        (wc1, wr1) = (min(c1 + search, width), min(r1 + search, height))
        window = values[wr0:wr1, wc0:wc1].copy()
        window_valid = valid[wr0:wr1, wc0:wc1]
        dataset = driver.Create("", wc1 - wc0, wr1 - wr0, 1,
                                gdal.GDT_Float32)
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(LADDER_INSET_NODATA)
        band.WriteArray(numpy.where(window_valid, window,
                                    LADDER_INSET_NODATA).astype(
                                        numpy.float32))
        mask = driver.Create("", wc1 - wc0, wr1 - wr0, 1, gdal.GDT_Byte)
        mask.GetRasterBand(1).WriteArray(
            window_valid.astype(numpy.uint8) * 255)
        gdal.FillNodata(targetBand=band, maskBand=mask.GetRasterBand(1),
                        maxSearchDist=float(search),
                        smoothingIterations=DEFAULT_FILL_SMOOTHING_ITERATIONS)
        filled = band.ReadAsArray()
        dataset = mask = None
        cells = labels[wr0:wr1, wc0:wc1] == island["label"]
        good = cells & (filled != LADDER_INSET_NODATA) & numpy.isfinite(
            filled)
        values[wr0:wr1, wc0:wc1][good] = filled[good]
        valid[wr0:wr1, wc0:wc1] |= good
        left += int((cells & ~good).sum())
    return left


class LadderInsetAssembly:
    """THE LADDER ASSEMBLER (spec las-tile-lidar-provider §12, owner
    RULINGS 2026-10-01d, spec-author refinement 2026-10-01) -- the one
    derivation site of every delivered inset assembled over its ladder.

    The CORE is the delivered raster (a surgical LAS core, an
    airport-cover rung, or a partial 1 m mosaic).  Its NoData islands
    inside the core region are classified (:func:`inset_void_islands`):

    * an INTERIOR island -- ringed by valid core cells only (a building
      footprint void in class-2 lidar ground, a pond) -- is a void in a
      measured surface, and the 1 m ring around it is a better estimate
      of its pad than any coarser rung: it is INTERPOLATED from that ring
      (``gdal.FillNodata``), whatever its size, ``filled_by`` =
      :data:`HOLE_FILLED_BY_CORE_INTERPOLATION`;
    * an EDGE island -- touching the core region's edge or the inset box
      edge (missing tiles, a partial mosaic) -- FILLS DOWN THE LADDER.

    The FILLS are the coarser covering rungs the ladder fetched over the
    whole box, added FINEST FIRST (:meth:`add_fill`) while
    :meth:`needs_fill` says a cell they must answer (beyond the core
    region, or in an edge island) is unanswered.  :meth:`write` composes
    ONE raster on the core's grid: fills first, coarsest at the bottom,
    the core last (later input wins), and every edge -- the core region's
    edge and the boundary of each edge island -- feathered over
    ``feather_m`` INSIDE the finer layer by :func:`feather_weight` of the
    distance to the nearest filled pixel; a fill's own NoData edge is
    feathered into the fill below by the same rule.
    ``hole_min_cells`` decides only which islands get a ``holes`` row.

    ``core_region_is_box``: the core's region is its whole raster (a
    partial mosaic, an airport-cover rung); otherwise the buffered
    ``boundary_polygon`` (a surgical core), or, with no polygon, the
    core's own valid cells (the pre-§12 two-layer fallback).

    UNITS (spec us-holder-providers §2): every layer must hold METRES; a
    raster stamped with a declared unit that was never applied REFUSES
    as :class:`ProviderUnavailable` before a cell is read."""

    def __init__(self, core_path, boundary_polygon=None, buffer_m=0.0,
                 feather_m=None, hole_min_cells=INSET_HOLE_MIN_CELLS,
                 core_region_is_box=False):
        self.core_unit = raster_vertical_unit_held(core_path)
        if self.core_unit != "m":
            raise ProviderUnavailable(
                "ladder inset: the core holds %s - refused, a "
                "vertical-unit mismatch is never feathered "
                "(vertical_unit_applied must be m on every layer)"
                % (self.core_unit,))
        self.core_stamp = raster_vertical_unit_stamp(core_path)
        self.feather_m = float(LAS_DEFAULT_CORE_FEATHER_M
                               if feather_m is None else feather_m)
        self.hole_min_cells = int(hole_min_cells)
        dataset = gdal.Open(core_path)
        self.transform = dataset.GetGeoTransform()
        self.projection = dataset.GetProjection()
        self.width = dataset.RasterXSize
        self.height = dataset.RasterYSize
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        self.core_values = band.ReadAsArray().astype(numpy.float32)
        dataset = None
        self.core_valid = numpy.isfinite(self.core_values)
        if nodata is not None:
            self.core_valid &= self.core_values != nodata
        if core_region_is_box:
            self.region = numpy.ones((self.height, self.width), dtype=bool)
        elif boundary_polygon is not None and not boundary_polygon.is_empty:
            self.region = self._rasterise_region(boundary_polygon, buffer_m)
        else:
            self.region = self.core_valid.copy()
        self.measured = self.core_valid.copy()
        (self.labels, self.islands) = inset_void_islands(
            self.region & ~self.core_valid, ~self.region)
        # INTERIOR islands: interpolated from the core's own ring now --
        # they are core cells from here on.
        self.interpolation_left = _interpolate_interior_islands(
            self.core_values, self.core_valid, self.labels, self.islands)
        edge_labels = numpy.zeros(len(self.islands) + 1, dtype=bool)
        for island in self.islands:
            edge_labels[island["label"]] = not island["interior"]
        self.edge = edge_labels[self.labels]
        # Every cell a fill must answer: beyond the core region, and the
        # edge islands.
        self.need = ~self.region | self.edge
        self.fills = []        # [(values, valid, filled_by)], finest first
        self.fill_extent = numpy.zeros((self.height, self.width), dtype=bool)

    def _rasterise_region(self, boundary_polygon, buffer_m):
        driver = gdal.GetDriverByName("MEM")
        mask_ds = driver.Create("", self.width, self.height, 1,
                                gdal.GDT_Byte)
        mask_ds.SetGeoTransform(self.transform)
        mask_ds.SetProjection(self.projection)
        region_geometry = _buffer_geometry_m(boundary_polygon, buffer_m)
        # GDAL >= 3.11 names the in-memory vector driver MEM (Memory is
        # deprecated there); older builds (Linux 3.9) only know Memory.
        vector_driver = (ogr.GetDriverByName("MEM")
                         or ogr.GetDriverByName("Memory"))
        layer_ds = vector_driver.CreateDataSource("core")
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        layer = layer_ds.CreateLayer("core", srs, ogr.wkbUnknown)
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(ogr.CreateGeometryFromWkt(region_geometry.wkt))
        layer.CreateFeature(feature)
        gdal.RasterizeLayer(mask_ds, [1], layer, burn_values=[1])
        region = mask_ds.GetRasterBand(1).ReadAsArray().astype(bool)
        layer_ds = mask_ds = None
        return region

    def interpolated(self):
        """Whether an interior island was interpolated (the raster
        changes even with no fill)."""
        return bool((self.core_valid & ~self.measured).any())

    def add_fill(self, fill_path, filled_by):
        """Warp one coarser rung (bilinear) onto the core's grid; the
        next-coarser one is added AFTER it (finest first).  Returns the
        cells it answers that the fills must answer."""
        unit = raster_vertical_unit_held(fill_path)
        if unit != "m":
            raise ProviderUnavailable(
                "ladder inset: the core holds %s and the fill '%s' holds "
                "%s - refused, a vertical-unit mismatch is never feathered "
                "(vertical_unit_applied must be m on every layer)"
                % (self.core_unit, (filled_by or {}).get("label"), unit))
        (values, valid) = self._warp(fill_path, "bilinear")
        if self.need.any() and (self.need & ~valid).any():
            # The bilinear kernel leaves the box's outermost cells NoData
            # where the source ends at the box edge (KASE witness: the last
            # row and column, 22,784 cells); the rung HOLDS data there --
            # its own nearest cell answers them.  Elsewhere bilinear stands.
            (nearest, nearest_valid) = self._warp(fill_path, "near")
            edge = nearest_valid & ~valid
            values[edge] = nearest[edge]
            valid |= edge
        self.fill_extent |= self._warp_extent(fill_path)
        self.fills.append((values, valid, dict(filled_by or {})))
        return int((valid & self.need).sum())

    def _warp_extent(self, fill_path):
        """The core cells inside the fill raster's own EXTENT (whatever its
        values).  A rung warped to its native grid can stop a cell short of
        the box (KASE witness: 497 ten-metre columns for a 4,972 m box --
        the last metre or two of the box lies beyond every rung); such a
        BOX-EDGE SLIVER is no rung's to answer and the bake's own outer
        feather gives it zero weight -- it never makes the ladder climb
        or 'run out'."""
        source = gdal.Open(fill_path)
        driver = gdal.GetDriverByName("MEM")
        ones = driver.Create("", source.RasterXSize, source.RasterYSize, 1,
                             gdal.GDT_Byte)
        ones.SetGeoTransform(source.GetGeoTransform())
        ones.SetProjection(source.GetProjection())
        ones.GetRasterBand(1).Fill(1)
        source = None
        west = self.transform[0]
        north = self.transform[3]
        east = west + self.transform[1] * self.width
        south = north + self.transform[5] * self.height
        warped = gdal.Warp(
            "", ones,
            options=gdal.WarpOptions(
                format="MEM", dstSRS=self.projection or "EPSG:4326",
                outputBounds=(west, south, east, north), width=self.width,
                height=self.height, resampleAlg="near", dstNodata=0))
        extent = warped.GetRasterBand(1).ReadAsArray() > 0
        warped = ones = None
        return extent

    def _left(self):
        """The cells a fill must answer and none does -- less the box-edge
        sliver beyond every fill's extent (:meth:`_warp_extent`)."""
        left = self.need.copy()
        for (_values, valid, _by) in self.fills:
            left &= ~valid
        if self.fills:
            left &= self.fill_extent
        return left

    def _warp(self, fill_path, resample):
        west = self.transform[0]
        north = self.transform[3]
        east = west + self.transform[1] * self.width
        south = north + self.transform[5] * self.height
        warped = gdal.Warp(
            "", fill_path,
            options=gdal.WarpOptions(
                format="MEM", outputType=gdal.GDT_Float32,
                dstSRS=self.projection or "EPSG:4326",
                options=["-novshift"],
                outputBounds=(west, south, east, north), width=self.width,
                height=self.height, resampleAlg=resample,
                dstNodata=LADDER_INSET_NODATA))
        values = warped.GetRasterBand(1).ReadAsArray().astype(
            numpy.float32)
        warped = None
        return (values,
                numpy.isfinite(values) & (values != LADDER_INSET_NODATA))

    def needs_fill(self):
        """Whether a cell the fills must answer is still unanswered -- the
        ladder climbs to the next coarser rung while this holds."""
        return bool(self._left().any())

    def _compose_fills(self):
        """``(values, valid, source)`` of the fill stack: the coarsest at
        the bottom, each finer fill over it, its own NoData edge feathered
        inside it; ``source`` = index (finest 0) of the fill that holds
        each cell, -1 where none does."""
        stack = numpy.full((self.height, self.width), LADDER_INSET_NODATA,
                           dtype=numpy.float32)
        stack_valid = numpy.zeros((self.height, self.width), dtype=bool)
        source = numpy.full((self.height, self.width), -1, dtype=numpy.int8)
        for index in range(len(self.fills) - 1, -1, -1):
            (values, valid, _by) = self.fills[index]
            under = valid & stack_valid
            if under.any() and (~valid).any():
                weight = feather_weight(
                    _distance_to_mask_m(~valid, self.transform,
                                        self.feather_m),
                    self.feather_m).astype(numpy.float32)
                stack[under] = (weight[under] * values[under]
                                + (1.0 - weight[under]) * stack[under])
                alone = valid & ~stack_valid
                stack[alone] = values[alone]
            else:
                stack[valid] = values[valid]
            stack_valid |= valid
            source[valid] = index
        return (stack, stack_valid, source)

    def write(self, destination_path):
        """Compose and write the raster; returns the SEAM RECORD."""
        (stack, stack_valid, source) = self._compose_fills()
        region = self.region
        core_values = self.core_values
        core_valid = self.core_valid
        core_region = region & ~self.edge
        out = numpy.full((self.height, self.width), LADDER_INSET_NODATA,
                         dtype=numpy.float32)
        offset = None
        if not self.fills:
            # Interpolation only: the raster as fetched, its interior
            # islands answered (no region masking -- nothing composes).
            out[core_valid] = core_values[core_valid]
            band_zone = numpy.zeros_like(core_valid)
        else:
            distance_m = _distance_to_mask_m(self.need, self.transform,
                                             self.feather_m)
            weight = numpy.where(core_region,
                                 feather_weight(distance_m, self.feather_m),
                                 0.0).astype(numpy.float32)
            band_zone = core_region & (weight < 1.0)
            answered = self.need & stack_valid
            out[answered] = stack[answered]
            both = core_region & core_valid & stack_valid
            out[both] = (weight[both] * core_values[both]
                         + (1.0 - weight[both]) * stack[both])
            core_only = core_region & core_valid & ~stack_valid
            out[core_only] = core_values[core_only]
            seam_fill = band_zone & ~core_valid & stack_valid
            out[seam_fill] = stack[seam_fill]
            ring = band_zone & core_valid & stack_valid
            offset = (float(numpy.median(core_values[ring] - stack[ring]))
                      if ring.any() else None)

        scratch = destination_path + ".assemble"
        target = gdal.GetDriverByName("GTiff").Create(
            scratch, self.width, self.height, 1, gdal.GDT_Float32,
            options=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"])
        target.SetGeoTransform(self.transform)
        target.SetProjection(self.projection)
        target_band = target.GetRasterBand(1)
        target_band.SetNoDataValue(LADDER_INSET_NODATA)
        target_band.WriteArray(out)
        if self.core_stamp is not None:
            for (item, key) in ((VERTICAL_UNIT_STAMP_DECLARED, "declared"),
                                (VERTICAL_UNIT_STAMP_SOURCE, "source"),
                                (VERTICAL_UNIT_STAMP_APPLIED, "applied")):
                if self.core_stamp.get(key):
                    target.SetMetadataItem(item, self.core_stamp[key])
        target = None
        os.replace(scratch, destination_path)
        out_valid = out != LADDER_INSET_NODATA
        record = self._record(stack, stack_valid, source, out, out_valid)
        record.update({
            "seam_median_offset_m": (round(offset, 4)
                                     if offset is not None else None),
            "core_holes_left_nodata": int((core_region & ~core_valid
                                           & ~band_zone).sum()),
            "filled_fraction": round(float(out_valid.mean()), 6),
            "fill_share": round(float(
                (out_valid & ~(core_region & self.measured)).mean()), 6),
        })
        return record

    def unwritten_record(self):
        """The seam record when nothing was written (no fill used and no
        interior island interpolated): the raster stands as fetched."""
        empty = numpy.zeros((self.height, self.width), dtype=bool)
        stack = numpy.full((self.height, self.width), LADDER_INSET_NODATA,
                           dtype=numpy.float32)
        source = numpy.full((self.height, self.width), -1, dtype=numpy.int8)
        out = numpy.where(self.core_valid, self.core_values,
                          LADDER_INSET_NODATA).astype(numpy.float32)
        record = self._record(stack, empty, source, out, self.core_valid)
        record.update({
            "seam_median_offset_m": None,
            "core_holes_left_nodata": int((self.region & ~self.edge
                                           & ~self.core_valid).sum()),
            "filled_fraction": round(float(self.core_valid.mean()), 6),
            "fill_share": 0.0,
        })
        return record

    def _record(self, stack, stack_valid, source, out, out_valid):
        interior = [island for island in self.islands if island["interior"]]
        edge = [island for island in self.islands
                if not island["interior"]]
        small = [island for island in self.islands
                 if island["cells"] < self.hole_min_cells]
        return {
            "region_pixels": int(self.region.sum()),
            "holes": self._hole_rows(stack, stack_valid, source, out,
                                     out_valid),
            "hole_min_cells": self.hole_min_cells,
            "islands": len(self.islands),
            "interior_islands": len(interior),
            "interior_cells": int(sum(i["cells"] for i in interior)),
            "edge_islands": len(edge),
            "edge_cells": int(sum(i["cells"] for i in edge)),
            "interpolation_left_cells": int(self.interpolation_left),
            "sub_threshold_voids": len(small),
            "sub_threshold_cells": int(sum(i["cells"] for i in small)),
            "unanswered_cells": int(self._left().sum()),
            "box_edge_sliver_cells": int((self.need & ~stack_valid
                                          & ~self.fill_extent).sum())
            if self.fills else 0,
        }

    def _hole_rows(self, stack, stack_valid, source, out, out_valid):
        """One row per island of at least ``hole_min_cells``: ``kind``
        (interior / edge), ``cells``, ``area_m2``, its
        ``bounding_box_wgs84``, ``filled_by`` (``core_interpolation``, or
        the fill rung holding most of an edge island), ``fill_cells`` per
        rung, ``unfilled_cells``, ``fill_median_m`` (what now stands in
        it), ``ring_median_m`` (the valid MEASURED core cells touching it)
        and, for an edge island, ``seam_median_m`` (median ``core -
        fill`` over that ring: its datum sanity)."""
        rows_wanted = [island for island in self.islands
                       if island["cells"] >= self.hole_min_cells]
        if not rows_wanted:
            return []
        labels = self.labels
        count = len(self.islands) + 1
        flat_labels = labels.ravel()
        in_island = flat_labels > 0
        per_source = [numpy.bincount(
            flat_labels[in_island & (source.ravel() == index)],
            minlength=count) for index in range(len(self.fills))]
        unfilled = numpy.bincount(flat_labels[in_island & ~out_valid.ravel()],
                                  minlength=count)
        # The 1-cell ring: measured core cells 8-adjacent to an island.
        neighbour = numpy.zeros_like(labels)
        padded = numpy.pad(labels, 1)
        for (dr, dc) in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1),
                         (1, -1), (1, 0), (1, 1)):
            shifted = padded[1 + dr:1 + dr + self.height,
                             1 + dc:1 + dc + self.width]
            neighbour = numpy.where(neighbour > 0, neighbour, shifted)
        ring = (neighbour > 0) & self.measured & (labels == 0) & self.region

        def _group(keys, data):
            order = numpy.argsort(keys, kind="stable")
            keys = keys[order]
            return (data[order].astype(numpy.float64),
                    numpy.searchsorted(keys, numpy.arange(count)),
                    numpy.searchsorted(keys, numpy.arange(count),
                                       side="right"))

        ring_core = _group(neighbour[ring], self.core_values[ring])
        ring_delta = None
        if self.fills:
            seam = ring & stack_valid
            ring_delta = _group(neighbour[seam],
                                (self.core_values - stack)[seam])
        filled = (labels > 0) & out_valid
        inside = _group(labels[filled], out[filled])

        def _median(block, label):
            (data, starts, ends) = block
            chunk = data[starts[label]:ends[label]]
            return round(float(numpy.median(chunk)), 4) if chunk.size \
                else None

        (x0, dx, _rx, y0, _ry, dy) = self.transform
        centre_lat = y0 + dy * self.height / 2.0
        cell_m2 = (abs(dx) * GEO.lon_to_m(centre_lat)) * (
            abs(dy) * GEO.lat_to_m)
        rows = []
        for island in rows_wanted:
            label = island["label"]
            (c0, r0, c1, r1) = island["box_px"]
            row = {
                "kind": "interior" if island["interior"] else "edge",
                "cells": int(island["cells"]),
                "area_m2": round(island["cells"] * cell_m2, 1),
                "bounding_box_wgs84": [round(x0 + c0 * dx, 8),
                                       round(y0 + r1 * dy, 8),
                                       round(x0 + c1 * dx, 8),
                                       round(y0 + r0 * dy, 8)],
                "unfilled_cells": int(unfilled[label]),
                "fill_median_m": _median(inside, label),
                "ring_median_m": _median(ring_core, label),
            }
            if island["interior"]:
                row["filled_by"] = HOLE_FILLED_BY_CORE_INTERPOLATION
            else:
                fill_cells = [int(per_source[i][label])
                              for i in range(len(self.fills))]
                best = (max(range(len(fill_cells)),
                            key=lambda i: (fill_cells[i], -i))
                        if fill_cells and max(fill_cells) > 0 else None)
                row["filled_by"] = (None if best is None
                                    else dict(self.fills[best][2]))
                row["fill_cells"] = [
                    {"label": self.fills[i][2].get("label"),
                     "rung": self.fills[i][2].get("rung"),
                     "cells": fill_cells[i]}
                    for i in range(len(self.fills)) if fill_cells[i]]
                row["seam_median_m"] = (_median(ring_delta, label)
                                        if ring_delta is not None else None)
            rows.append(row)
        return rows


def assemble_ladder_inset(core_path, fills, destination_path,
                          boundary_polygon=None, buffer_m=0.0,
                          feather_m=None,
                          hole_min_cells=INSET_HOLE_MIN_CELLS,
                          core_region_is_box=False):
    """ONE raster from a delivered CORE and the coarser rungs of its
    ladder (spec §12; :class:`LadderInsetAssembly` is the mechanism).
    ``fills`` = ``[(path, filled_by)]`` FINEST FIRST, ``filled_by`` =
    ``{"provider", "rung", "label"}``.  Returns the seam record."""
    assembly = LadderInsetAssembly(
        core_path, boundary_polygon=boundary_polygon, buffer_m=buffer_m,
        feather_m=feather_m, hole_min_cells=hole_min_cells,
        core_region_is_box=core_region_is_box)
    for (fill_path, filled_by) in fills:
        assembly.add_fill(fill_path, filled_by)
    return assembly.write(destination_path)


def discover_inset(definition, bounding_box_wgs84):
    """Ask the provider's strategy whether it covers a bounding box.

    Returns a list of opaque source descriptors, or ``None`` for no
    coverage / not applicable.  Strategy-agnostic, like :func:`fetch_inset`.
    """
    strategy_factory = ACCESS_STRATEGIES.get(definition.get("access_strategy"))
    if strategy_factory is None:
        return None
    return strategy_factory().discover(definition, bounding_box_wgs84)


def geotiff_is_constant_value(geotiff_path):
    """Are ALL valid samples in the raster one single constant value?

    A plausibility probe for coastline band cells.  Some national Web
    Coverage Services answer requests beyond their true data extent with
    a constant FILL instead of nodata (the Spanish PNOA endpoint serves
    0.0 across the border over Portugal), so the raster passes both the
    post-warp sentinel sanitizer (0.0 is a plausible height) and
    :func:`_geotiff_has_valid_data` (nothing equals the nodata marker)
    and would bake a sea-level plateau over foreign land.  Genuine warped
    lidar is never bit-for-bit constant across a whole 0.1 degree cell,
    while an all-water cell that IS legitimately constant loses nothing
    by falling back to the base elevation source (which models the sea
    anyway) -- so callers may safely treat a constant cell as
    no-coverage.  Note the check is deliberately NOT "mostly zero":
    genuine coastal cells hold large exactly-0.0 sea areas next to varied
    land, so any zero-share threshold would reject real data.  Returns
    False when the raster cannot be read or holds no valid sample (those
    cases belong to :func:`_geotiff_has_valid_data`).
    """
    if not has_gdal:
        return False
    try:
        dataset = gdal.Open(geotiff_path)
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        values = band.ReadAsArray()
    except Exception:
        return False
    if values is None:
        return False
    values = values.ravel()
    if nodata is not None:
        values = values[values != nodata]
    if values.size == 0:
        return False
    return bool((values == values[0]).all())




def _polygon_mapping(geometry):
    """A shapely geometry as a JSON-safe GeoJSON-like mapping."""
    from shapely.geometry import mapping

    return json.loads(json.dumps(mapping(geometry)))


# =====================================================================
# Surface-model building masking (strategy-agnostic post-fetch pass)
# =====================================================================
# Definition flag naming the pass; parsed to bool at registry load.
SURFACE_MODEL_BUILDING_MASKING = "surface_model_building_masking"

# One buffered pixel of a 30 m grid plus a margin for radar layover: the
# X-band return of a building smears roughly one resolution cell beyond
# its walls, so the mask must reach past the mapped footprint.
DEFAULT_FOOTPRINT_MASK_BUFFER_M = 35.0
# Residual structure masking (2026-07-18, SPJC east-side mounds): surface
# models bake UNMAPPED structures into the terrain too — dense city blocks
# outside any OpenStreetMap/package footprint (measured SPJC: a +4-6 m
# plateau of unmapped Lima rooftops right behind the terminal, zero
# footprints within 90 m).  A morphological-opening ground estimate flags
# pixels standing more than the threshold above it; the opening window
# must exceed the widest unmapped structure while staying invariant on
# planar slopes (opening of a plane is the plane, so genuine hillsides
# never mask).  Broad ridges wider than the window are preserved.
DEFAULT_RESIDUAL_MASK_THRESHOLD_M = 2.0
DEFAULT_RESIDUAL_MASK_OPENING_WINDOW_M = 105.0
# Dense-city DSM fabric is CONTIGUOUS rooftop plateau for hundreds of
# metres (measured SPJC east wall: +5-6 m with no ground pixel inside any
# window — 30 m native resolution never sees the streets), so a single
# opening cannot recover ground there.  Iterate: each mask+fill round
# recedes the plateau's SHARP edge by ~half a window from every recovered-
# ground side; gradual (natural) terrain edges produce no opening residual
# and never start eroding, so real sloped-flank mesas are preserved.  The
# pass count bounds the reach (~5 x 52 m = ~260 m) — deep-city plateau
# beyond it keeps its DSM height, which only matters past the graded
# strips' reach where the sim draws the buildings anyway.
DEFAULT_RESIDUAL_MASK_EROSION_PASSES = 12
RESIDUAL_STRUCTURE_MASKING = "residual_structure_masking"


def _residual_structure_mask(
    values,
    exclude_mask,
    pixel_size_m,
    opening_window_m=DEFAULT_RESIDUAL_MASK_OPENING_WINDOW_M,
    threshold_m=DEFAULT_RESIDUAL_MASK_THRESHOLD_M,
    erosion_passes=DEFAULT_RESIDUAL_MASK_EROSION_PASSES,
):
    """Boolean mask of pixels standing above the local ground estimate.

    The ground estimate is a grey (morphological) OPENING of the raster:
    erosion then dilation with a square window of ``opening_window_m``.
    Structures narrower than the window are levelled out of the estimate,
    so their pixels show a positive residual; a planar slope is invariant
    under opening, so genuine hillsides show none; terrain features with
    GRADUAL flanks survive into the estimate and are preserved regardless
    of width.  Contiguous cliff-edged plateau wider than the window
    (dense-city rooftop fabric) is recovered ITERATIVELY: each pass fills
    the masked cells from the nearest trusted ground and re-runs the
    opening, so the plateau's sharp edge recedes ~half a window per pass;
    ``erosion_passes`` bounds the total reach.  ``exclude_mask`` cells
    (genuine nodata) are replaced by the finite median for the estimate —
    they can neither poison the estimate with sentinel lows nor appear in
    the returned mask.

    ESTIMATOR (2026-07-18, second iteration): the ground reference is a
    LOCAL MEDIAN, not a morphological opening — an opening is exactly
    invariant on a half-plane step (erosion shifts the cliff edge, the
    dilation shifts it back), so it can never start biting into wide
    city-plateau fabric.  The median over a symmetric window of a plane
    is its centre value (slopes and gradual flanks are invariant), while
    any pixel whose window is MAJORITY ground gets pulled down to
    ground, which both levels isolated structures and lets the fill
    iteration recede a plateau edge pass by pass.  Computed on a grid
    decimated to ~15 m cells: the interesting sources are 30 m-native
    DSMs oversampled to 3 m, so decimation loses nothing and keeps the
    median filter fast."""
    import numpy
    from scipy import ndimage

    finite = ~exclude_mask
    if not finite.any():
        return numpy.zeros(values.shape, dtype=bool)
    decimation = max(1, int(round(15.0 / max(pixel_size_m, 0.5))))
    small_values = values[::decimation, ::decimation].astype(
        numpy.float64, copy=True)
    small_finite = finite[::decimation, ::decimation]
    if not small_finite.any():
        return numpy.zeros(values.shape, dtype=bool)
    small_pixel_m = pixel_size_m * decimation
    window_pixels = int(round(opening_window_m / small_pixel_m))
    window_pixels = max(3, window_pixels)
    if window_pixels % 2 == 0:
        window_pixels += 1
    border = window_pixels // 2
    small_values[~small_finite] = float(
        numpy.median(small_values[small_finite]))
    small_mask = numpy.zeros(small_values.shape, dtype=bool)
    for _erosion_pass in range(max(1, erosion_passes)):
        # Slope-safe criteria per pass, evaluated over a WINDOW LADDER
        # (1x, 2x, 4x the base window): one window cannot fit every
        # structure scale — a 105 m window around a 150 m warehouse band
        # or inside wide city fabric sees under a quarter of true
        # ground, so its low quartile carries no signal, while the
        # airport's abundant ground IS visible at 420 m.  The uphill and
        # steepness gates below are scale-independent, so growing the
        # quartile's reach never unprotects slopes.
        #   BUMP — the pixel stands above the base-window MEDIAN
        #   (features covering under half the window; the median of a
        #   plane is its centre, so slopes never fire);
        #   EDGE BITE — the pixel stands above SOME window's LOW
        #   QUARTILE (ground visible at that scale), has nothing
        #   significantly higher within ~30 m uphill (plateau top, not
        #   mid-slope — pixel-relative, so staircase levels recede
        #   top-down across passes), and drops by the threshold within
        #   ~30 m somewhere nearby (a real structure edge; natural
        #   flanks up to ~6 % never do — steeper cliff-flanked terrain
        #   accepts a bounded shoulder band being re-interpolated,
        #   which inside an airport-neighbourhood inset is the right
        #   trade).
        window_median = ndimage.median_filter(
            small_values, size=window_pixels, mode="nearest"
        )
        ground_visible_below = numpy.zeros(small_values.shape, dtype=bool)
        believed_ground = None
        for scale in (1, 2, 4):
            ladder_window = window_pixels * scale
            if ladder_window % 2 == 0:
                ladder_window += 1
            low_quartile = ndimage.percentile_filter(
                small_values, 25, size=ladder_window, mode="nearest"
            )
            ground_visible_below |= (
                (small_values - low_quartile) > threshold_m
            )
            believed_ground = (low_quartile if believed_ground is None
                               else numpy.minimum(believed_ground,
                                                  low_quartile))
        uphill_is_flat = (
            (ndimage.grey_dilation(small_values, size=5, mode="nearest")
             - small_values) < threshold_m / 2.0
        )
        local_drop = small_values - ndimage.grey_erosion(
            small_values, size=5, mode="nearest"
        )
        pass_mask = ((
            ((small_values - window_median) > threshold_m)
            | (ground_visible_below
               & uphill_is_flat
               & (local_drop > threshold_m))
        ) & small_finite & ~small_mask)
        # Nearest-padding makes the window asymmetric at the raster
        # border (a slope reads high there), which would mask and
        # re-fill a border strip and mint an inset-boundary seam; the
        # estimate is untrustworthy there, so the border band never
        # masks.
        if border > 0:
            pass_mask[:border, :] = False
            pass_mask[-border:, :] = False
            pass_mask[:, :border] = False
            pass_mask[:, -border:] = False
        if not pass_mask.any():
            break
        small_mask |= pass_mask
        # Substitute the BELIEVED GROUND at the newly masked cells (a
        # nearest-source fill would copy plateau values back in from the
        # plateau side and stall the recession); the next pass then sees
        # the edge receded.  The real raster fill happens once, in the
        # caller, over the accumulated mask.
        small_values = small_values.copy()
        small_values[pass_mask] = believed_ground[pass_mask]
    if not small_mask.any():
        return numpy.zeros(values.shape, dtype=bool)
    full_mask = numpy.kron(
        small_mask,
        numpy.ones((decimation, decimation), dtype=bool),
    )[: values.shape[0], : values.shape[1]]
    if full_mask.shape != values.shape:
        padded = numpy.zeros(values.shape, dtype=bool)
        padded[: full_mask.shape[0], : full_mask.shape[1]] = full_mask
        full_mask = padded
    return full_mask & finite

# Upper bound, in pixels, on how far the legacy gdal.FillNodata inpainting
# looks for valid ground values.  100 pixels at a 30 m grid is 3 km --
# beyond any single terminal complex while keeping gdal.FillNodata cheap.
DEFAULT_FOOTPRINT_FILL_SEARCH_PIXELS = 100

# The masked-hole fill algorithm.  The default vectorized distance-transform
# fill replaces every masked (building) cell with the value of its nearest
# trusted-ground cell in one O(N) exact-Euclidean pass, then applies a fixed
# number of deterministic masked smoothing passes -- reproducing what
# gdal.FillNodata does (interpolate holes from surrounding ground) as a
# single deterministic array operation instead of an iterative search whose
# cost grows with maxSearchDist.  The result is exactly reproducible (no
# floating iteration-order dependence) and never touches unmasked cells.
INSET_FILL_METHOD_DISTANCE_TRANSFORM = "distance_transform"
INSET_FILL_METHOD_LEGACY = "gdal_fillnodata"

# Smoothing passes applied to the filled cells only, matching the legacy
# gdal.FillNodata(smoothingIterations=2) so the two paths stay comparable.
DEFAULT_FILL_SMOOTHING_ITERATIONS = 2


def _inset_fill_method():
    """The masked-hole fill method, environment-overridable (default-on).

    ``O4_INSET_FILL_METHOD=gdal_fillnodata`` restores the legacy in-place
    ``gdal.FillNodata`` inpaint (the byte-for-byte fallback); any other or
    absent value selects the vectorized distance-transform fill.
    """
    value = os.environ.get("O4_INSET_FILL_METHOD", "").strip().lower()
    if value == INSET_FILL_METHOD_LEGACY:
        return INSET_FILL_METHOD_LEGACY
    return INSET_FILL_METHOD_DISTANCE_TRANSFORM


def _fill_masked_by_distance_transform(
    values, source_mask, smoothing_iterations=DEFAULT_FILL_SMOOTHING_ITERATIONS
):
    """Fill every non-source cell from its nearest trusted-ground cell.

    SOURCE-AGNOSTIC by contract: it takes a boolean ``source_mask`` marking
    the cells whose values are trusted ground, and knows nothing about where
    the holes came from (building footprints, package objects, both).  Every
    cell outside ``source_mask`` is overwritten with the value of the nearest
    source cell in exact Euclidean distance (``scipy.ndimage`` distance
    transform with ``return_indices``); the ground under an airport terminal
    is nearly planar, so a nearest-ground value is an excellent estimate --
    the same assumption the legacy fill relied on.  ``smoothing_iterations``
    deterministic 3x3 masked-mean passes then soften the piecewise-constant
    Voronoi seams; each pass only ever writes non-source cells, so every
    source (unmasked) cell stays byte-identical.

    Returns a new float64 array; ``values`` is not mutated.  The caller
    restores genuine nodata afterwards, exactly as with gdal.FillNodata
    (which also fills every non-source cell and lets the caller re-stamp the
    sentinel).  Determinism: the distance transform and the fixed-count
    box-mean passes have no iteration-order or thread dependence.
    """
    from scipy import ndimage

    filled = numpy.asarray(values, dtype=numpy.float64).copy()
    source_mask = numpy.asarray(source_mask, dtype=bool)
    fill_mask = ~source_mask
    if not source_mask.any() or not fill_mask.any():
        # No trusted ground to source from, or nothing to fill: unchanged.
        return filled
    # Nearest source-cell index for every cell (exact Euclidean).  The EDT
    # runs on the complement of the source mask, so each cell's returned
    # index is that of the closest source cell.
    nearest_indices = ndimage.distance_transform_edt(
        fill_mask, return_distances=False, return_indices=True
    )
    nearest_values = filled[tuple(nearest_indices)]
    filled[fill_mask] = nearest_values[fill_mask]
    # Masked smoothing: average over a 3x3 window but write only the filled
    # cells, so source cells (and thus every unmasked pixel) are untouched.
    for _ in range(int(smoothing_iterations)):
        blurred = ndimage.uniform_filter(filled, size=3, mode="nearest")
        filled[fill_mask] = blurred[fill_mask]
    return filled


_BUILDING_QUERY_STATEMENTS = ['way["building"]', 'rel["building"]']


def _load_building_layer_from_extracts(osm_layer, bbox_south_west_north_east):
    """Populate ``osm_layer`` with buildings from local Geofabrik extracts.

    ``bbox_south_west_north_east`` may also be a LIST of such boxes; the
    extracts backend then serves all of them in one filtering pass (the
    tile-level footprint prefetch batches every airport's box this way).

    The airport-inset footprint query previously went straight to Overpass,
    bypassing the regional-extract accelerator the tile vector pipeline
    already uses -- and for a large airport box that meant multi-minute
    Overpass queue waits (the profiled dominant cost of a cold inset build).
    When the downloaded extracts cover the box (the common airport case),
    the ``building`` ways/relations are filtered out of the local pbf
    instead, which is bounded by local disk I/O.  Returns ``True`` when the
    layer was populated locally, ``False`` to fall through to Overpass --
    the accelerator is never a dependency (missing index, region not stored
    yet, or any failure all read as ``False``).
    """
    try:
        import O4_OSM_Extracts as EXTRACTS
    except Exception:
        return False
    try:
        xml_bytes = EXTRACTS.osm_xml_from_local_extracts(
            _BUILDING_QUERY_STATEMENTS,
            bbox_south_west_north_east,
            request_description="inset_buildings",
        )
    except Exception:
        return False
    if not xml_bytes:
        return False
    # Mirror OSM_query_to_OSM_layer's tag setup for this fixed query so
    # update_dicosm keeps every building way/relation and its child nodes.
    building_tags = {"n": [], "w": [("building", "")], "r": [("building", "")]}
    try:
        osm_layer.update_dicosm(xml_bytes, building_tags, building_tags)
    except Exception:
        return False
    return True


def _building_footprint_polygons_from_layer(osm_layer):
    """Convert a populated building OSM layer to shapely polygons.

    Plain (longitude, latitude) coordinates (``OSM_to_MultiPolygon`` with
    a zero origin, so nothing here is tile-relative); ``[]`` on failure.
    """
    import O4_OSM_Utils as OSM

    try:
        footprints = OSM.OSM_to_MultiPolygon(osm_layer, 0, 0)
    except Exception as error:
        UI.vprint(
            1,
            "   WARNING: OpenStreetMap building polygons unreadable:",
            str(error),
        )
        return []
    return [polygon for polygon in getattr(footprints, "geoms", []) if polygon.area]


def openstreetmap_building_footprints(
    bounding_box_wgs84, footprint_prefetch=None
):
    """Absolute-WGS84 building footprint polygons from OpenStreetMap.

    Returns a list of shapely polygons in plain (longitude, latitude)
    coordinates for every ``building`` way and relation in the box
    (``OSM_to_MultiPolygon`` with a zero origin, so nothing here is
    tile-relative).  The data is served from the local Geofabrik regional
    extracts when they cover the box, and from Overpass otherwise; returns
    ``[]`` on any failure -- the caller then skips the masking pass rather
    than failing the fetch: an uncorrected surface-model inset is still
    better than no inset.

    When ``footprint_prefetch`` (a :class:`TileBuildingFootprintPrefetch`)
    can serve the box, the polygons come from its one shared extract pass
    instead of a fresh per-box pass -- the per-box pbf filtering cost is
    box-size-INDEPENDENT (three full osmium reads of the regional
    extract), so a tile with N airports otherwise pays that read N times.
    A prefetch answer of ``None`` (box not covered, extracts unable to
    serve) falls through to the unchanged per-box path.

    Deliberately NOT cached on disk: an inset fetch is already a rare,
    cached event, and reusing a footprint file fetched for a smaller
    margin would silently miss buildings in the enlarged ring (the exact
    staleness class the margin-aware inset cache invalidation fixed).
    """
    if footprint_prefetch is not None:
        prefetched = footprint_prefetch.footprints_intersecting_box(
            bounding_box_wgs84
        )
        if prefetched is not None:
            return prefetched
    import O4_OSM_Utils as OSM

    (west, south, east, north) = bounding_box_wgs84
    bbox = (south, west, north, east)
    osm_layer = OSM.OSM_layer()
    if not _load_building_layer_from_extracts(osm_layer, bbox):
        try:
            queried = OSM.OSM_query_to_OSM_layer(
                _BUILDING_QUERY_STATEMENTS, bbox, osm_layer,
            )
        except Exception as error:
            UI.vprint(
                1,
                "   WARNING: OpenStreetMap building query failed:",
                str(error),
            )
            return []
        if not queried:
            return []
    return _building_footprint_polygons_from_layer(osm_layer)


class TileBuildingFootprintPrefetch:
    """ONE regional-extract pass serving every airport's footprint query.

    Each per-airport OpenStreetMap building query independently filters
    the ENTIRE regional pbf (three osmium passes over hundreds of
    megabytes), and that cost does not depend on the box size -- so a
    tile with N airports paid the full read N times (93% of the profiled
    cold +25+051 inset build).  This prefetch runs the filter once with
    the full LIST of airport boxes -- never their bounding rectangle,
    which would sweep up every building between airports in a metro tile
    -- and answers each airport's query by clipping in memory.

    Lazy: nothing is read until the first query, so builds that never
    reach a masking pass (warm caches, no surface-model provider) never
    pay the extract pass.  Failure-neutral: when the extracts cannot
    serve (backend disabled, region not downloaded, osmium missing),
    every query returns ``None`` and the caller falls back to the
    unchanged per-box path (extracts, then Overpass).  Margin semantics
    are preserved because the boxes given here are the same margin-grown
    boxes each per-airport fetch would have queried with.
    """

    def __init__(self, bounding_boxes_wgs84):
        """``bounding_boxes_wgs84``: iterable of (west, south, east,
        north) boxes, one per airport."""
        self._boxes = [
            tuple(float(value) for value in box)
            for box in bounding_boxes_wgs84
        ]
        self._load_attempted = False
        # None until a successful load; a list afterwards.
        self._footprints = None
        # Airports now fetch concurrently: the lazy one-time load must
        # happen exactly once, with other workers waiting on it.
        self._load_lock = threading.Lock()

    def _box_is_covered(self, bounding_box_wgs84):
        """True when the request sits inside one of the construction
        boxes (tolerance for float round-trips)."""
        (west, south, east, north) = (
            float(value) for value in bounding_box_wgs84
        )
        epsilon = 1e-9
        for (p_west, p_south, p_east, p_north) in self._boxes:
            if (
                west >= p_west - epsilon
                and south >= p_south - epsilon
                and east <= p_east + epsilon
                and north <= p_north + epsilon
            ):
                return True
        return False

    def _load_once(self):
        with self._load_lock:
            if self._load_attempted:
                return
            self._load_attempted = True
            import O4_OSM_Utils as OSM

            osm_layer = OSM.OSM_layer()
            boxes_south_west_north_east = [
                (south, west, north, east)
                for (west, south, east, north) in self._boxes
            ]
            if not _load_building_layer_from_extracts(
                osm_layer, boxes_south_west_north_east
            ):
                return
            self._footprints = _building_footprint_polygons_from_layer(
                osm_layer)

    def footprints_intersecting_box(self, bounding_box_wgs84):
        """Prefetched footprints intersecting the box, or ``None`` when
        the prefetch cannot serve it (caller falls back per-box)."""
        if not self._boxes or not self._box_is_covered(bounding_box_wgs84):
            return None
        self._load_once()
        if self._footprints is None:
            return None
        from shapely.geometry import box as shapely_box

        (west, south, east, north) = bounding_box_wgs84
        clip_box = shapely_box(west, south, east, north)
        selected = []
        for polygon in self._footprints:
            (b_west, b_south, b_east, b_north) = polygon.bounds
            if (
                b_east < west
                or b_west > east
                or b_north < south
                or b_south > north
            ):
                continue
            if polygon.intersects(clip_box):
                selected.append(polygon)
        return selected


def _xplane_root_for_package_footprints():
    """X-Plane installation root from download-time configuration.

    The inset fetch runs at step 1, before any DSF is read, so there is no
    build context to hand a pack root in -- the root has to come from plain
    configuration.  The resolution order mirrors what ``O4_Vector_Map``
    already does to locate CIFP data (the reverse direction of the same
    derivation): ``cifp_data_path`` walked up two levels via
    ``auto_patch.cifp_reader.xplane_root_from_cifp_path``, then the parent
    of ``custom_scenery_dir``.  A CIFP path pointing outside an X-Plane
    install (a Navigraph folder) is rejected by requiring ``Custom
    Scenery`` under the derived root, and falls through to the next source.

    The config module is fetched through ``sys.modules`` (the established
    core-module idiom, see ``O4_OSM_Extracts``): this module must not
    import ``O4_Config_Utils`` at top level, and when it was never loaded
    (unit tests, library use) there is simply no root.  Returns ``None``
    when no root is resolvable.
    """
    import sys

    configuration = sys.modules.get("O4_Config_Utils")
    if configuration is None:
        return None
    cifp_path = getattr(configuration, "cifp_data_path", "") or ""
    if cifp_path:
        try:
            from auto_patch.cifp_reader import xplane_root_from_cifp_path

            root = xplane_root_from_cifp_path(cifp_path)
        except Exception:
            root = None
        if root and os.path.isdir(os.path.join(root, "Custom Scenery")):
            return root
    custom_scenery_directory = (
        getattr(configuration, "custom_scenery_dir", "") or ""
    )
    if custom_scenery_directory and os.path.isdir(custom_scenery_directory):
        return os.path.dirname(os.path.normpath(custom_scenery_directory))
    return None


def _dsf_tile_coordinates_for_bounding_box(bounding_box_wgs84):
    """Integer (latitude, longitude) of every 1x1 degree DSF tile the box
    touches -- usually one, up to four when an airport straddles a tile
    corner (the margin ring routinely crosses a tile edge)."""
    import math

    (west, south, east, north) = bounding_box_wgs84
    return [
        (tile_latitude, tile_longitude)
        for tile_latitude in range(
            int(math.floor(south)), int(math.floor(north)) + 1
        )
        for tile_longitude in range(
            int(math.floor(west)), int(math.floor(east)) + 1
        )
    ]


def _disabled_custom_scenery_pack_names(custom_scenery_directory):
    """Pack directory names marked SCENERY_PACK_DISABLED in
    ``scenery_packs.ini``.  A disabled pack does not render, so its object
    footprints are not authoritative for the mask (the whole point of the
    package source is matching what renders in the simulator).

    Delegated to :mod:`O4_Scenery_Packs`, the ONE derivation site (owner
    RULINGS 2026-09-17b)."""
    return _scenery_packs.disabled_pack_names(custom_scenery_directory)


def _airport_pack_dsf_paths(xplane_root, bounding_box_wgs84):
    """Overlay DSFs of installed AIRPORT packs covering the box's tile(s).

    Candidate packs are ``Custom Scenery`` entries that carry an ``Earth
    nav data/apt.dat`` -- the marker of an airport pack, which keeps ortho
    tiles, mesh packs and object libraries out of the scan -- and a tile
    DSF for a 1x1 degree tile the box touches (a couple of ``os.path``
    checks per pack, no file is parsed here).  ``Global Airports`` is
    excluded: its per-tile DSFs cover everywhere, its buildings are
    library-resolved by the thousand (an expensive cold parse at download
    time), and the OpenStreetMap side of the union already covers those
    real-world buildings; per-airport custom packs are the placements this
    source exists for.  Disabled packs (``scenery_packs.ini``) do not
    render and are skipped.
    """
    custom_scenery_directory = os.path.join(xplane_root, "Custom Scenery")
    if not os.path.isdir(custom_scenery_directory):
        return []
    disabled = _disabled_custom_scenery_pack_names(custom_scenery_directory)
    tile_relative_paths = [
        FNAMES.long_latlon(tile_latitude, tile_longitude) + ".dsf"
        for (tile_latitude, tile_longitude) in (
            _dsf_tile_coordinates_for_bounding_box(bounding_box_wgs84)
        )
    ]
    dsf_paths = []
    for pack_name in sorted(os.listdir(custom_scenery_directory)):
        if pack_name == "Global Airports" or pack_name in disabled:
            continue
        nav_data_directory = os.path.join(
            custom_scenery_directory, pack_name, "Earth nav data"
        )
        if not os.path.isfile(os.path.join(nav_data_directory, "apt.dat")):
            continue
        for tile_relative_path in tile_relative_paths:
            candidate = os.path.join(nav_data_directory, tile_relative_path)
            if os.path.isfile(candidate):
                dsf_paths.append(candidate)
    return dsf_paths


#: Manifest key (inside :data:`SURFACE_MODEL_BUILDING_MASKING`) holding the
#: SORTED pack directory names that served object footprints to the mask.
#: Owner ruling 2026-09-17c (1): record the contributing pack NAMES.
FOOTPRINT_PACKS = "footprint_packs"


def package_footprint_pack_names(bounding_box_wgs84):
    """Sorted directory names of the installed airport packs that serve
    object footprints over ``bounding_box_wgs84``.

    THE CHEAP SCAN, and deliberately the SAME one both sides of the reuse
    test use (:func:`_airport_pack_dsf_paths`: a ``Custom Scenery``
    listing plus an ``os.path.isfile`` per pack — no DSF is parsed, no
    OBJ8 is read).  Recomputing this on a warm pass therefore costs a
    directory walk, while asking "did the footprints CHANGE" would cost
    the object parse the scan exists to avoid.  Enabling or disabling a
    pack in ``scenery_packs.ini`` moves a NAME in this list, which is
    exactly the signal the mask's reuse test needs.

    ``[]`` when no X-Plane root is configured, when nothing covers the box,
    or on any error — the same defensive degradation
    :func:`package_object_footprints` takes.
    """
    try:
        xplane_root = _xplane_root_for_package_footprints()
        if not xplane_root:
            return []
        custom_scenery_directory = os.path.join(xplane_root, "Custom Scenery")
        names = set()
        for dsf_path in _airport_pack_dsf_paths(
            xplane_root, bounding_box_wgs84
        ):
            relative = os.path.relpath(dsf_path, custom_scenery_directory)
            head = relative.split(os.sep)[0]
            if head and head not in (os.pardir, os.curdir):
                names.add(head)
        return sorted(names)
    except Exception:
        return []


def package_object_footprints(bounding_box_wgs84, definition):
    """Authoritative building footprints from installed airport packages.

    The installed airport scenery package's DSF/OBJ8 object placements are
    the footprints that actually render in the simulator, so they are the
    PRIMARY footprint source for the inset mask (owner ruling 2026-07-18;
    OpenStreetMap supplements them, and since the mask is a boolean union
    precedence never has to be arbitrated).

    Pack resolution is bbox-driven and needs no airport identifier and no
    build context: the X-Plane root comes from download-time configuration
    (:func:`_xplane_root_for_package_footprints`), candidate packs from a
    cheap directory scan (:func:`_airport_pack_dsf_paths`), and each
    candidate DSF goes through
    ``auto_patch.dsf_reader.read_dsf_object_buildings`` -- the same reader
    the build pipeline uses, so the expensive OBJ8 parse + partition is
    served from (and primes) the shared ``o4_object_footprints_*`` sidecar
    caches under ``Airport_mod_cache/``.  Rings come back in plain
    (longitude, latitude); they are repaired like the pipeline's building
    pool (``buffer(0)``) and clipped to the box.

    Defensive throughout: no configured root, no candidate pack, an
    unreadable DSF, or any exception all degrade to ``[]`` -- the mask then
    falls back to OpenStreetMap alone, and an uncorrected inset still beats
    a failed fetch.

    (``O4_INSET_PACKAGE_FOOTPRINTS`` DELETED 2026-08-05, audit Tier 2:
    "debug" in name only — dropping a footprint source changes the inset
    MASK, i.e. the terrain the patch is graded against.  The union of both
    sources is the law.)
    """
    try:
        from shapely.geometry import Polygon
        from shapely.geometry import box as shapely_box

        xplane_root = _xplane_root_for_package_footprints()
        if not xplane_root:
            return []
        dsf_paths = _airport_pack_dsf_paths(xplane_root, bounding_box_wgs84)
        if not dsf_paths:
            return []
        from auto_patch.dsf_reader import read_dsf_object_buildings
    except Exception as error:
        UI.vprint(
            2,
            "   Package footprint sourcing unavailable:",
            str(error),
        )
        return []
    (west, south, east, north) = bounding_box_wgs84
    bounding_geometry = shapely_box(west, south, east, north)
    footprints = []
    for dsf_path in dsf_paths:
        try:
            buildings = read_dsf_object_buildings(
                dsf_path, xplane_root=xplane_root
            )
        except Exception as error:
            UI.vprint(
                2,
                "   Package footprint read failed for",
                dsf_path,
                ":",
                str(error),
            )
            continue
        for (outer_ring, hole_rings, _role) in buildings:
            if len(outer_ring) < 3:
                continue
            try:
                polygon = Polygon(
                    outer_ring,
                    [ring for ring in hole_rings if len(ring) >= 3],
                )
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
                if (
                    polygon.is_empty
                    or not polygon.area
                    or not polygon.intersects(bounding_geometry)
                ):
                    continue
            except Exception:
                continue
            footprints.append(polygon)
    if footprints:
        UI.vprint(
            2,
            "   ",
            len(footprints),
            "building footprints from installed airport package(s).",
        )
    return footprints


def _collect_inset_building_footprints(
    bounding_box_wgs84, definition, footprint_prefetch=None
):
    """UNION of building footprints for the inset mask (package + OSM).

    Package (installed airport scenery) object footprints are authoritative
    where present; OpenStreetMap footprints supplement them.  The mask built
    from these is a boolean UNION, so precedence is moot -- a cell is masked
    if ANY source covers it, and the downstream fill is completely agnostic
    to which source contributed a polygon (requirement: sourcing rule and
    fill algorithm stay decoupled).  Either source may be empty.

    Returns ``(footprints, source_label)``.
    """
    package = package_object_footprints(bounding_box_wgs84, definition)
    osm = openstreetmap_building_footprints(
        bounding_box_wgs84, footprint_prefetch=footprint_prefetch
    )
    footprints = list(package) + list(osm)
    if package and osm:
        label = "installed package objects + OpenStreetMap footprints"
    elif package:
        label = "installed package objects"
    else:
        label = "OpenStreetMap building footprints"
    return footprints, label


def _buffer_footprints_in_metres(footprints, buffer_m, centre_latitude):
    """Buffer WGS84 polygons by ``buffer_m`` true metres.

    Degrees are anisotropic away from the equator, so each polygon is
    scaled into a local equirectangular metre frame at the box's centre
    latitude, buffered there, and scaled back.
    """
    from shapely.ops import transform as shapely_transform

    metres_per_degree_longitude = GEO.lon_to_m(centre_latitude)
    metres_per_degree_latitude = GEO.lat_to_m
    buffered = []
    for polygon in footprints:
        in_metres = shapely_transform(
            lambda x, y: (
                x * metres_per_degree_longitude,
                y * metres_per_degree_latitude,
            ),
            polygon,
        )
        back_in_degrees = shapely_transform(
            lambda x, y: (
                x / metres_per_degree_longitude,
                y / metres_per_degree_latitude,
            ),
            in_metres.buffer(buffer_m),
        )
        if back_in_degrees.is_valid and not back_in_degrees.is_empty:
            buffered.append(back_in_degrees)
    return buffered


def _rasterize_footprint_mask(footprints, reference_dataset):
    """Boolean array marking ``reference_dataset`` pixels under a footprint."""
    memory_raster = gdal.GetDriverByName("MEM").Create(
        "",
        reference_dataset.RasterXSize,
        reference_dataset.RasterYSize,
        1,
        gdal.GDT_Byte,
    )
    memory_raster.SetGeoTransform(reference_dataset.GetGeoTransform())
    memory_raster.SetProjection(reference_dataset.GetProjection())
    # GDAL 3.11 renamed the in-memory OGR driver "Memory" -> "MEM";
    # accept both so older installs keep working.
    vector_driver = ogr.GetDriverByName("MEM") or ogr.GetDriverByName(
        "Memory"
    )
    vector_dataset = vector_driver.CreateDataSource("")
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    vector_layer = vector_dataset.CreateLayer(
        "footprints", spatial_reference, ogr.wkbPolygon
    )
    for polygon in footprints:
        feature = ogr.Feature(vector_layer.GetLayerDefn())
        feature.SetGeometry(ogr.CreateGeometryFromWkb(polygon.wkb))
        vector_layer.CreateFeature(feature)
        feature = None
    gdal.RasterizeLayer(memory_raster, [1], vector_layer, burn_values=[1])
    mask = memory_raster.GetRasterBand(1).ReadAsArray().astype(bool)
    memory_raster = None
    vector_dataset = None
    return mask


def mask_building_footprints_in_surface_model(
    inset_path, bounding_box_wgs84, definition, footprint_prefetch=None
):
    """Replace building-contaminated surface-model pixels by ground.

    Surface models (radar DSMs like Copernicus GLO-30) bake rooftop
    heights into the terrain.  Height subtraction cannot repair that (a
    30 m pixel straddling a wall holds a roof/ground mixture, radar
    layover smears the return past the footprint, and mapped heights
    rarely match what the radar saw), so contaminated pixels are simply
    NOT TRUSTED: every pixel within ``footprint_mask_buffer_m`` of an
    OpenStreetMap building footprint is masked and re-interpolated from
    the surrounding ground with ``gdal.FillNodata``.  Under an airport
    terminal the true ground is nearly planar, which makes the fill an
    excellent estimate.  Genuine nodata cells are excluded from the
    interpolation sources and restored verbatim afterwards.

    Returns a summary dictionary for the provenance sidecar; on any
    failure the summary carries a ``skipped`` reason and the raster is
    left as fetched (an uncorrected inset beats a failed fetch).
    """
    if not has_gdal:
        return {"skipped": "GDAL unavailable"}
    (footprints, footprint_source) = _collect_inset_building_footprints(
        bounding_box_wgs84, definition, footprint_prefetch=footprint_prefetch
    )
    # WHICH PACKS SERVED THIS MASK (owner ruling 2026-09-17c (1)).  The
    # prose ``footprint_source`` label says only WHETHER packages
    # contributed; the reuse test needs the NAMES, because enabling or
    # disabling one changes the mask and therefore the terrain the patch
    # is graded against.  Recorded on every path that got as far as
    # collecting footprints; a manifest WITHOUT the key is
    # unknown-and-reusable (:func:`_sidecar_footprint_packs_mismatch`).
    footprint_packs = package_footprint_pack_names(bounding_box_wgs84)
    buffer_m = _parse_float(
        definition.get("footprint_mask_buffer_m"),
        default=DEFAULT_FOOTPRINT_MASK_BUFFER_M,
    )
    residual_masking_on = definition.get(RESIDUAL_STRUCTURE_MASKING, True)
    if not footprints and not residual_masking_on:
        return {
            "skipped": "no building footprints in the box",
            "footprint_count": 0,
            FOOTPRINT_PACKS: footprint_packs,
        }
    (west, south, east, north) = bounding_box_wgs84
    centre_latitude = (south + north) / 2.0
    try:
        buffered = _buffer_footprints_in_metres(
            footprints, buffer_m, centre_latitude
        ) if footprints else []
        dataset = gdal.Open(inset_path, gdal.GA_Update)
        band = dataset.GetRasterBand(1)
        values = band.ReadAsArray()
        nodata_value = band.GetNoDataValue()
        if nodata_value is None:
            nodata_value = -32768.0
        if buffered:
            building_mask = _rasterize_footprint_mask(buffered, dataset)
        else:
            building_mask = numpy.zeros(values.shape, dtype=bool)
        genuine_nodata = (values == nodata_value) | ~numpy.isfinite(values)
        # RESIDUAL STRUCTURE MASK (2026-07-18): footprint masking can only
        # erase what is MAPPED; unmapped structures (dense city blocks with
        # no OpenStreetMap coverage — the SPJC east-side mounds) survive it.
        # Flag every pixel standing above the morphological ground estimate
        # and heal it through the SAME source-agnostic fill.
        residual_mask = numpy.zeros(values.shape, dtype=bool)
        residual_masked_pixel_count = 0
        if residual_masking_on:
            import math
            geotransform = dataset.GetGeoTransform()
            pixel_size_m = abs(geotransform[1]) * 111320.0 * math.cos(
                math.radians(centre_latitude))
            residual_mask = _residual_structure_mask(
                values, genuine_nodata, pixel_size_m
            )
            residual_masked_pixel_count = int(residual_mask.sum())
        combined_mask = building_mask | residual_mask
        pixels_to_fill = combined_mask & ~genuine_nodata
        # Trusted-ground sources: every cell that is neither under a
        # footprint nor genuine nodata (so sentinels are never fill
        # sources).  Both fill methods fill every non-source cell and let
        # the caller restore genuine nodata, so only building pixels change.
        interpolation_sources = ~combined_mask & ~genuine_nodata
        if not pixels_to_fill.any() or not interpolation_sources.any():
            dataset = None
            return {
                "footprint_source": footprint_source,
                "footprint_count": len(footprints),
                "masked_pixel_count": 0,
                "residual_masked_pixel_count": residual_masked_pixel_count,
                "residual_mask_threshold_m":
                    DEFAULT_RESIDUAL_MASK_THRESHOLD_M,
                "residual_mask_opening_window_m":
                    DEFAULT_RESIDUAL_MASK_OPENING_WINDOW_M,
                "footprint_mask_buffer_m": buffer_m,
                "fill_method": _inset_fill_method(),
                FOOTPRINT_PACKS: footprint_packs,
            }
        fill_method = _inset_fill_method()
        if fill_method == INSET_FILL_METHOD_DISTANCE_TRANSFORM:
            filled_values = _fill_masked_by_distance_transform(
                values,
                interpolation_sources,
                smoothing_iterations=DEFAULT_FILL_SMOOTHING_ITERATIONS,
            )
            filled_values[genuine_nodata] = nodata_value
            band.WriteArray(filled_values)
            band.FlushCache()
            dataset = None
        else:
            source_mask_raster = gdal.GetDriverByName("MEM").Create(
                "", dataset.RasterXSize, dataset.RasterYSize, 1,
                gdal.GDT_Byte,
            )
            source_mask_raster.SetGeoTransform(dataset.GetGeoTransform())
            source_mask_band = source_mask_raster.GetRasterBand(1)
            source_mask_band.WriteArray(
                interpolation_sources.astype(numpy.uint8) * 255
            )
            search_pixels = _parse_float(
                definition.get("footprint_fill_search_pixels"),
                default=DEFAULT_FOOTPRINT_FILL_SEARCH_PIXELS,
            )
            gdal.FillNodata(
                targetBand=band,
                maskBand=source_mask_band,
                maxSearchDist=float(search_pixels),
                smoothingIterations=DEFAULT_FILL_SMOOTHING_ITERATIONS,
            )
            filled_values = band.ReadAsArray()
            filled_values[genuine_nodata] = nodata_value
            band.WriteArray(filled_values)
            band.FlushCache()
            dataset = None
            source_mask_raster = None
    except Exception as error:
        UI.vprint(
            1,
            "   WARNING: building-footprint masking failed:",
            str(error),
        )
        return {"skipped": str(error), "footprint_count": len(footprints),
                FOOTPRINT_PACKS: footprint_packs}
    return {
        "footprint_source": footprint_source,
        FOOTPRINT_PACKS: footprint_packs,
        "footprint_count": len(footprints),
        "masked_pixel_count": int(pixels_to_fill.sum()),
        "masked_fraction": round(
            float(pixels_to_fill.sum()) / float(values.size), 4
        ),
        "residual_masked_pixel_count": residual_masked_pixel_count,
        "residual_mask_threshold_m": DEFAULT_RESIDUAL_MASK_THRESHOLD_M,
        "residual_mask_opening_window_m":
            DEFAULT_RESIDUAL_MASK_OPENING_WINDOW_M,
        "footprint_mask_buffer_m": buffer_m,
        "fill_method": fill_method,
    }


# =====================================================================
# Orchestration (strategy-agnostic): discovery loop, cache, index
# =====================================================================
def _read_index(lat, lon):
    index_path = FNAMES.airport_inset_index(lat, lon)
    if not os.path.isfile(index_path):
        return {}
    try:
        with open(index_path, "r") as handle:
            return json.load(handle)
    except Exception:
        return {}


#: Index fields a settled warm pass may re-derive without the manifest
#: having CHANGED: ``checked`` is a date stamp (a pass that re-checks and
#: finds something different also changes the provider's own value beside
#: it), and ``bounding_box`` is recomputed in floating point every pass.
_INDEX_FRESHNESS_KEYS = ("checked",)


def _index_records_differ(old_record, new_record):
    """The MATERIAL keys in which two per-airport index records differ.

    Freshness-only re-derivation is not a difference: the ``checked`` date
    stamp, and a ``bounding_box`` that moved by less than
    :data:`INSET_BOUNDING_BOX_TOLERANCE_DEGREES` (the same tolerance the
    staleness test already uses, ~0.1 m — float noise from recomputing the
    same box, never a real margin change).
    """
    if not isinstance(old_record, dict) or not isinstance(new_record, dict):
        return ["<record>"] if old_record != new_record else []
    differing = []
    for key in sorted(set(old_record) | set(new_record)):
        before, after = old_record.get(key), new_record.get(key)
        if before == after or key in _INDEX_FRESHNESS_KEYS:
            continue
        if key == "bounding_box":
            try:
                if len(before) == len(after) and all(
                    abs(float(a) - float(b))
                    <= INSET_BOUNDING_BOX_TOLERANCE_DEGREES
                    for a, b in zip(before, after)
                ):
                    continue
            except (TypeError, ValueError):
                pass
        differing.append(key)
    return differing


def _write_index(lat, lon, index):
    """Persist the tile's inset index, but ONLY when its content changed.

    ``ensure_airport_insets`` calls this at the end of every pass, warm or
    cold, and a settled warm pass produces MATERIALLY identical content:
    the write then changes nothing a consumer reads, but it is still a
    WRITE INTO THE SHARED DATA REPO.  A build is not a refresh event
    (owner ruling e9daef5 — cache regenerations are explicit, locked,
    hash-stamped acts through ``build_airport.py --refresh-data``), so a
    settled pass must leave the repo untouched.  Same discipline the
    bathymetry band stamp already had; measured 2026-08-08, when two
    mesh-only runs rewrote five of these manifests with unchanged content.

    BYTE equality is too strict a test for that (measured 2026-09-10, a
    CYXY mesh-only run: the guard blocked
    ``N60W136_airport_insets/index.json`` and REFUSED the whole run, on a
    warm corpus where every inset was already cached).  The comparison is
    therefore MATERIAL — :func:`_index_records_differ` — and a write that
    does happen names the airports and keys that moved, so a real change
    is never silent.
    """
    index_path = FNAMES.airport_inset_index(lat, lon)
    payload = json.dumps(index, indent=2, sort_keys=True)
    try:                       # absent, unreadable or different: write it
        with open(index_path, "r") as handle:
            current = handle.read()
    except Exception:
        current = None
    if current is not None:
        if current == payload:
            return
        try:
            old = json.loads(current)
        except Exception:
            old = None
        if isinstance(old, dict):
            changed = {}
            for icao in sorted(set(old) | set(index)):
                keys = _index_records_differ(old.get(icao), index.get(icao))
                if keys:
                    changed[icao] = keys
            if not changed:
                return                     # freshness only: not a change
            UI.vprint(
                1,
                "   Airport inset index CHANGED, rewriting it:",
                "; ".join(f"{k}: {', '.join(v)}" for k, v in changed.items()),
            )
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", newline="\n") as handle:
        handle.write(payload)


# ~0.1 m at the equator: a real margin change (metres) always exceeds it,
# while float noise from recomputing the same box never does.
INSET_BOUNDING_BOX_TOLERANCE_DEGREES = 1e-6


def _bounding_box_extends_beyond(
    requested_box, recorded_box,
    tolerance=INSET_BOUNDING_BOX_TOLERANCE_DEGREES,
):
    """True when ``requested_box`` reaches outside ``recorded_box`` anywhere.

    Both are ``(west, south, east, north)`` in EPSG:4326 degrees.  A
    requested box fully inside the recorded one (margin shrunk or equal)
    is NOT beyond it: a superset raster stays valid.
    """
    (requested_west, requested_south, requested_east, requested_north) = (
        requested_box
    )
    (recorded_west, recorded_south, recorded_east, recorded_north) = (
        recorded_box
    )
    return (
        requested_west < recorded_west - tolerance
        or requested_south < recorded_south - tolerance
        or requested_east > recorded_east + tolerance
        or requested_north > recorded_north + tolerance
    )


def _sidecar_residual_masking_mismatch(lat, lon, icao, provider_code,
                                       residual_masking_wanted):
    """True when the cached inset was produced with a DIFFERENT residual
    structure-masking configuration than the provider now wants — both
    directions: an inset built without it while the gate is ON, and an
    inset carrying residual-masked pixels while the gate is OFF (the
    2026-07-18 live regression left damaged caches that must regenerate
    clean).  A missing or unreadable sidecar reads as False —
    pre-sidecar caches keep the established leave-alone policy."""
    provenance_path = FNAMES.airport_inset_provenance(
        lat, lon, icao, provider_code
    )
    try:
        with open(provenance_path, "r") as handle:
            provenance = json.load(handle)
    except (OSError, ValueError):
        return False
    summary = provenance.get(SURFACE_MODEL_BUILDING_MASKING)
    if not isinstance(summary, dict):
        return False
    if residual_masking_wanted:
        return "residual_masked_pixel_count" not in summary
    return bool(summary.get("residual_masked_pixel_count"))


def recorded_footprint_packs(lat, lon, icao, provider_code):
    """The pack names a cached inset's manifest RECORDS as having served
    its building mask, or ``None`` when the manifest does not say.

    ``None`` is "unknown", not "none": it is what a manifest written
    before 2026-09-17 says, and what a provider that runs no masking pass
    says.  Both are REUSABLE (:func:`_sidecar_footprint_packs_mismatch`).
    """
    provenance_path = FNAMES.airport_inset_provenance(
        lat, lon, icao, provider_code
    )
    try:
        with open(provenance_path, "r") as handle:
            provenance = json.load(handle)
    except (OSError, ValueError):
        return None
    summary = provenance.get(SURFACE_MODEL_BUILDING_MASKING)
    if not isinstance(summary, dict):
        return None
    recorded = summary.get(FOOTPRINT_PACKS)
    if not isinstance(recorded, (list, tuple)):
        return None
    return [str(name) for name in recorded]


def _masking_definition_for_code(provider_code, providers_config="auto"):
    """The airport-inset provider definition named by ``provider_code``
    WHEN IT RUNS THE BUILDING-MASK PASS, else ``None``.

    The fetch loop gates both mask-related reuse tests on
    ``definition[SURFACE_MODEL_BUILDING_MASKING]`` (:func:`ensure_airport_
    insets`), so anything that predicts that loop must apply the SAME
    gate — a provider that masks nothing can never be pack-set-stale.
    """
    try:
        for definition in select_provider_definitions(
                providers_config, role=ROLE_AIRPORT_INSET):
            if str(definition.get("code") or "").upper() == \
                    str(provider_code or "").upper():
                return (definition
                        if definition.get(SURFACE_MODEL_BUILDING_MASKING)
                        else None)
    except Exception:
        return None
    return None


def _sidecar_footprint_packs_mismatch(lat, lon, icao, provider_code,
                                      bounding_box_wgs84):
    """True when the cached inset's mask was served by a DIFFERENT SET of
    installed scenery packs than serves this box now (owner ruling
    2026-09-17c (1)).

    Compared as SETS, so pack order and the scan's path layout never
    matter.  A manifest that carries no
    :data:`FOOTPRINT_PACKS` key is UNKNOWN, and unknown reads as
    REUSABLE -- the established leave-alone policy every other sidecar
    test here takes (:func:`_sidecar_residual_masking_mismatch`): the key
    is stamped lazily the next time the inset is derived for its own
    reasons, never by a corpus-wide re-cut.  Also False when the
    provenance is missing or unreadable.
    """
    recorded = recorded_footprint_packs(lat, lon, icao, provider_code)
    if recorded is None:
        return False                      # unknown => reusable
    return set(recorded) != set(
        package_footprint_pack_names(bounding_box_wgs84)
    )


def requested_inset_bounding_box(lat, lon, icao, provider_code):
    """The box a cached inset's fetch ASKED the provider for.

    ``requested_bounding_box_wgs84`` when the manifest has it (written
    since 2026-09-17), else the historic ``bounding_box_wgs84`` -- which
    IS the requested box: every access strategy records the box it was
    handed, verbatim, before any warp.  ``None`` when the sidecar is
    missing or unreadable: a cache that cannot be judged is REUSABLE, the
    established leave-alone policy.

    This is the input to THE RE-CUT RULE
    (:func:`inset_recut_is_needed`); what the raster actually carries is
    :func:`delivered_inset_bounding_box`, and the two are not the same
    box (measured 2026-09-17 over 559 pairs).
    """
    provenance_path = FNAMES.airport_inset_provenance(
        lat, lon, icao, provider_code
    )
    try:
        with open(provenance_path, "r") as handle:
            provenance = json.load(handle)
        for key in ("requested_bounding_box_wgs84", "bounding_box_wgs84"):
            recorded_box = provenance.get(key)
            if (isinstance(recorded_box, (list, tuple))
                    and len(recorded_box) == 4):
                return tuple(float(value) for value in recorded_box)
    except (OSError, ValueError, TypeError):
        pass
    return None


#: Historic spelling, kept so nothing that reads "what was this inset
#: fetched with" has to change; the answer is the REQUESTED box.
_fetched_bounding_box = requested_inset_bounding_box


def inset_recut_is_needed(lat, lon, icao, provider_code, required_box):
    """THE RE-CUT RULE (named by the session 2026-09-17, on the corpus
    census in ``tools/inset_coverage_census.py``).

    An inset is STALE -- worth asking the provider again -- exactly when
    the box this airport requires TODAY is not contained in the box that
    was REQUESTED when the inset was cut.  What we asked for then is no
    longer what we need now, so re-asking WILL do better.

    This is the predicate the engine has always applied here; naming it
    changes no behaviour and marks no additional raster stale (measured
    2026-09-17: 215 of 565, identically before and after).  Deliberately
    NOT judged against the delivered raster: a warp snaps the target
    extent to its pixel grid, so the delivered box is up to a source
    pixel off the request in either direction, and judging by it would
    have marked 453 of 565 stale -- including every battery airport --
    for shortfalls of under a metre.  A raster the PROVIDER could not
    fill is a different question and a different answer
    (:func:`inset_delivery_shortfall`): re-asking cannot help there, so
    it warns and never re-cuts.

    An unjudgeable manifest returns False: reusable.
    """
    requested_box = requested_inset_bounding_box(lat, lon, icao,
                                                 provider_code)
    if requested_box is None:
        return False
    return _bounding_box_extends_beyond(required_box, requested_box)


def _stored_rung_listing(attempt):
    """What a recorded ladder attempt says its discovery listed: the ids,
    ``[]`` for a rung that listed nothing (or was never in coverage), and
    ``None`` when the record cannot say (a rung recorded before listings
    were -- every id it lists now is then NEW)."""
    if not isinstance(attempt, dict):
        return None
    if isinstance(attempt.get("listing_ids"), list):
        return [str(value) for value in attempt["listing_ids"]]
    if attempt.get("outcome") in ("no-coverage", "out-of-coverage"):
        return []
    return None


def ladder_recheck_ids_text(ids, shown=5):
    """``a, b, c, d, e (+58 more)`` -- a re-check's new ids for one log /
    refusal line (a LAS index lists 63 tiles at KASE)."""
    ids = list(ids or ())
    text = ", ".join(ids[:shown])
    if len(ids) > shown:
        text += " (+%d more)" % (len(ids) - shown)
    return text


def ladder_recheck(lat, lon, icao, provider_code, bounding_box,
                   record=False):
    """THE BUILD-TIME LADDER RE-CHECK (owner RULINGS 2026-09-30aw (2)) --
    the ONE stale-reason predicate for "a finer rung may exist now".

    Runs only when ``icao``'s cached inset from ``provider_code`` was
    delivered by a COARSER ladder rung (``ladder.delivered_rung > 0``),
    or when the ladder recorded a rung that never answered (``transient``,
    RULINGS 2026-09-30bl) or delivered a rung that only PARTLY covers the
    airport (its same-resolution alternatives, #153).  For every finer
    rung of the provider's CURRENT ladder -- plus those -- it asks that
    rung's ``discover()`` ONLY -- one index query each, no download -- and
    compares the listing with the rung's recorded ``listing_ids``:

    * a NEW id           -> ``result: "new-listing"`` (the caller re-runs
      the whole ladder; a product that lists but grids below the bake's
      threshold leaves the delivered rung where it was);
    * nothing new        -> ``"unchanged"`` (no download);
    * discovery transient -> ``"transient"``: the cached inset stands
      (RULINGS 2026-09-30t: an outage is no answer).

    A rung whose own coverage box misses ``bounding_box`` is not asked.
    Returns ``None`` when nothing applies (no sidecar, no ladder, rung 0
    or no rung delivered), else ``{"rung", "rungs_checked", "checked",
    "result", "new_source_ids"}``.  ``record=True`` (the fetch loop)
    stamps it into the sidecar's ``ladder.recheck`` -- only when
    ``result`` / ``new_source_ids`` differ from the stored block (a
    date-only change is no change; a byte-identical sidecar is never
    rewritten).  The harness frame check calls it with ``record=False``:
    a read.
    """
    sidecar = FNAMES.airport_inset_provenance(lat, lon, icao, provider_code)
    try:
        with open(sidecar, "r") as handle:
            meta = json.load(handle)
    except (OSError, ValueError):
        return None
    ladder = meta.get("ladder") if isinstance(meta, dict) else None
    if not isinstance(ladder, dict):
        return None
    delivered_rung = ladder.get("delivered_rung")
    # Rungs that never ANSWERED (a transient outage the ladder climbed
    # past, owner RULINGS 2026-09-30bl) and, when the delivered rung only
    # PARTLY covers the airport, the same-resolution rungs asked after it
    # (#153) are re-asked too: either may cover the airport now.
    tried = [attempt for attempt in ladder.get("rungs_tried") or ()
             if isinstance(attempt, dict) and attempt.get("role") is None]
    reask_labels = [str(attempt.get("label")) for attempt in tried
                    if attempt.get("outcome") == "transient"]
    delivered_attempt = next(
        (attempt for attempt in tried
         if attempt.get("rung") == delivered_rung
         and attempt.get("outcome") == "delivered"), None)
    if (isinstance(delivered_rung, int) and delivered_attempt is not None
            and delivered_attempt.get("judge") != "airport_cover"
            and delivered_attempt.get("airport_valid_fraction") is not None
            and delivered_attempt["airport_valid_fraction"]
            < INSET_MIN_AIRPORT_COVER_FRAC):
        reask_labels.extend(
            str(attempt.get("label")) for attempt in tried
            if isinstance(attempt.get("rung"), int)
            and attempt["rung"] > delivered_rung)
    if (not isinstance(delivered_rung, int) or delivered_rung <= 0) \
            and not reask_labels:
        return None
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    definition = elevation_providers_dict.get(provider_code)
    if definition is None:
        wanted = str(provider_code).upper()
        definition = next(
            (value for (key, value) in elevation_providers_dict.items()
             if str(key).upper() == wanted), None)
    if definition is None:
        return None
    rungs = _ladder_rung_definitions(definition, bounding_box)
    footprint = ladder.get(LAS_FOOTPRINT_KEY)
    if footprint:
        # The SAME surgical footprint the fetch listed over -- or every
        # re-check would read the box-wide listing as "new" (spec §2).
        rungs = [
            (label, dict(rung_definition, **{LAS_FOOTPRINT_KEY: footprint})
             if rung_definition.get("code") != definition.get("code")
             else rung_definition)
            for (label, rung_definition) in rungs
        ]
    stored = {}
    for attempt in ladder.get("rungs_tried") or ():
        if isinstance(attempt, dict) and attempt.get("label") is not None:
            stored[str(attempt["label"])] = attempt
    labels = [label for (label, _definition) in rungs]
    delivered_label = ladder.get("delivered_label")
    if not isinstance(delivered_rung, int) or delivered_rung <= 0:
        finer = []
    elif delivered_label in labels:
        finer = rungs[:labels.index(delivered_label)]
    else:
        delivered_native = _parse_float(
            (stored.get(str(delivered_label)) or {}).get(
                "native_resolution_m"))
        finer = [
            (label, rung_definition)
            for (label, rung_definition) in rungs
            if delivered_native is None
            or (_definition_resolution_m(rung_definition) or 0.0)
            < delivered_native
        ]
    finer = list(finer) + [
        (label, rung_definition) for (label, rung_definition) in rungs
        if label in reask_labels
        and label not in [other for (other, _d) in finer]]
    new_ids = []
    checked = []
    transient = False
    for (label, rung_definition) in finer:
        if not _coverage_bbox_intersects(rung_definition, bounding_box):
            continue
        factory = ACCESS_STRATEGIES.get(rung_definition.get("access_strategy"))
        if factory is None:
            continue
        checked.append(labels.index(label))
        try:
            sources = factory().discover(rung_definition, bounding_box)
        except Exception as error:
            # An outage is no answer (30t): THIS rung stands as recorded,
            # and the other finer rungs are still asked -- one rung's
            # outage must not hide another rung's new listing.
            UI.vprint(
                0,
                "    [inset] %s: ladder re-check of rung '%s' (%s) did not "
                "answer (%s) - that rung stands as recorded."
                % (icao, label, rung_definition.get("code"), error),
            )
            transient = True
            continue
        listed = _listing_ids(sources)
        known = _stored_rung_listing(stored.get(str(label)))
        fresh = [value for value in listed
                 if known is None or value not in set(known)]
        new_ids.extend(fresh)
    result = ("new-listing" if new_ids
              else "transient" if transient else "unchanged")
    recheck = {
        "rung": checked[0] if checked else None,
        "rungs_checked": checked,
        "checked": datetime.date.today().isoformat(),
        "result": result,
        "new_source_ids": sorted(set(new_ids)),
    }
    if record:
        before = ladder.get("recheck") if isinstance(
            ladder.get("recheck"), dict) else {}
        if (before.get("result"), before.get("new_source_ids")) != (
                recheck["result"], recheck["new_source_ids"]):
            if _write_refused_by_armed_guard(sidecar):
                # §11 (4e): under an ARMED shared-repo guard the stamp is
                # NOT ATTEMPTED (an attempted-and-caught refusal fails the
                # run as a swallowed block); the harness carries the
                # result in frame.json instead.
                recheck["stamp"] = "not attempted (shared-repo guard armed)"
            else:
                ladder["recheck"] = recheck
                with open(sidecar, "w", newline="\n") as handle:
                    json.dump(meta, handle, indent=2, sort_keys=True)
    return recheck


#: THE FUNCTIONAL MARGIN of the WARN rule, in metres: how far beyond the
#: aerodrome boundary an inset must actually REACH before the shortfall is
#: worth a word.  It is far smaller than
#: ``airport_elevation_inset_margin_m`` (2000 m) on purpose -- the margin
#: exists so the airport and its surroundings sit on fine elevation, and
#: an inset delivering 1,998 m of it instead of 2,000 harms nothing.
#:
#: Measured 2026-09-17 over all 565 cached rasters
#: (``tools/inset_coverage_census.py --section sweep``): ZERO fail at any
#: m_min <= 1000 m; the battery's worst edge is OTHH south at 1985 m; and
#: every provider delivers its own request to within 0.5 delivered pixels,
#: england1m included.  So this arm fires on NOTHING today.  It is the
#: guard for a provider that really does clip -- where the request was
#: honoured but the data stops -- and there re-asking would not help,
#: which is why it warns and never re-cuts.
INSET_FUNCTIONAL_MARGIN_M = 1000.0


def inset_delivery_shortfall(inset_path, boundary_box, mid_latitude,
                             functional_margin_m=INSET_FUNCTIONAL_MARGIN_M):
    """THE WARN RULE: the edges on which the DELIVERED raster fails to
    reach ``functional_margin_m`` beyond the aerodrome boundary.

    ``{edge: metres_short}`` for the failing edges only, ``{}`` when the
    raster covers what matters, and ``None`` when it cannot be opened (no
    GDAL, absent, corrupt -- never a guess).  Judged against the raster's
    OWN geotransform with a tolerance of one DELIVERED pixel per axis:
    the pixel comes from the file, so this needs no ``native_resolution_m``
    (which not every manifest carries) and never fires on warp rounding.

    NEVER a staleness test.  A shortfall here means the provider did not
    fill what it was asked for, and asking again returns the same raster.
    """
    delivered_box = delivered_inset_bounding_box(inset_path)
    if delivered_box is None:
        return None
    header = _inset_header_geometry(inset_path)
    pixel_lon = abs(header[0][1])
    pixel_lat = abs(header[0][5])
    metres_per_degree_longitude = GEO.lon_to_m(mid_latitude)
    margin_lon = functional_margin_m / metres_per_degree_longitude
    margin_lat = functional_margin_m / GEO.lat_to_m
    (west, south, east, north) = boundary_box
    required = (west - margin_lon, south - margin_lat,
                east + margin_lon, north + margin_lat)
    shortfalls = {
        "west": (delivered_box[0] - required[0] - pixel_lon)
        * metres_per_degree_longitude,
        "south": (delivered_box[1] - required[1] - pixel_lat) * GEO.lat_to_m,
        "east": (required[2] - delivered_box[2] - pixel_lon)
        * metres_per_degree_longitude,
        "north": (required[3] - delivered_box[3] - pixel_lat) * GEO.lat_to_m,
    }
    return {edge: metres for edge, metres in shortfalls.items()
            if metres > 0.0}


def warn_if_delivered_inset_clips_airport(tile, icao, boundary_box):
    """LOUD when a cached inset for ``icao`` was DELIVERED short of the
    functional margin (:data:`INSET_FUNCTIONAL_MARGIN_M`).

    One line per raster, naming it, the short edges in metres, and that a
    RE-CUT WOULD NOT HELP -- the request itself was delivered, so the
    provider's data simply stops there.  Returns the number of warnings
    emitted (the twins read that).
    """
    warned = 0
    for inset_path in cached_inset_paths_for_airport(tile, icao):
        shortfalls = inset_delivery_shortfall(
            inset_path, boundary_box, tile.lat + 0.5
        )
        if not shortfalls:
            continue
        UI.loud_warning(
            "   WARNING: the elevation inset %s reaches less than %.0f m "
            "beyond %s's aerodrome boundary (%s) - the ground beyond it is "
            "graded on the BASE elevation source.  A re-cut would NOT help: "
            "the provider delivered the box that was requested."
            % (os.path.basename(inset_path), INSET_FUNCTIONAL_MARGIN_M, icao,
               ", ".join("%s short %.0f m" % (edge, shortfalls[edge])
                         for edge in sorted(shortfalls)))
        )
        warned += 1
    return warned


# A cached inset counts as over-sampled only when its posting is
# materially finer than native, so ordinary warp/rounding slack (a 30 m
# source landing on a 29.95 m posting) never triggers a refetch.
OVERSAMPLED_INSET_RATIO = 0.9


def _cached_inset_oversamples(inset_path, definition):
    """True when a cached inset is stored FINER than its source publishes.

    Such a raster is interpolation, not detail (see
    :func:`_inset_target_resolution_m`): it wastes disk and reports a
    resolution the data does not have.  False whenever the question
    cannot be answered — no GDAL, an unreadable header, or a provider
    that declares no native resolution — so an undecidable cache keeps
    the established leave-alone policy rather than refetching forever.
    """
    native_resolution_m = _definition_resolution_m(definition)
    if not has_gdal or native_resolution_m is None or native_resolution_m <= 0:
        return False
    header = _inset_header_geometry(inset_path)
    if header is None:
        return False
    stored_pixel_m = abs(header[0][5]) * GEO.lat_to_m
    return stored_pixel_m < native_resolution_m * OVERSAMPLED_INSET_RATIO


def _clear_poisoned_insets(lat, lon, index):
    """Delete EMPTY cached inset rasters — with their provenance sidecars
    and index records — so the fetch pass rebuilds what is still wanted.

    A run killed hard mid-fetch skips the failure path's partial-file
    cleanup (2026-07-23: two 0-byte ``*_italy10m.tif`` relics), and a
    relic whose provider never wins the ranking again is otherwise
    revisited by nobody — while every consumer globbing ``*.tif`` still
    trips over it.  Only zero-byte files are swept: a nonempty file is
    treated as a valid cache (the hermetic-test contract), and a
    nonempty-but-corrupt raster degrades gracefully at load time
    (:func:`_load_inset_raster`) instead.
    """
    directory = FNAMES.airport_inset_directory(lat, lon)
    if not os.path.isdir(directory):
        return
    for path in sorted(glob.glob(os.path.join(directory, "*.tif"))):
        if _file_size_or_zero(path) > 0:
            continue
        UI.vprint(
            1,
            "   WARNING: removing unreadable cached elevation inset "
            + os.path.basename(path)
            + " - it will be refetched if still needed.",
        )
        base = os.path.basename(path)[:-len(".tif")]
        icao, _, code = base.rpartition("_")
        try:
            os.remove(path)
        except OSError:
            continue
        sidecar = os.path.join(directory, base + ".json")
        if os.path.isfile(sidecar):
            try:
                os.remove(sidecar)
            except OSError:
                pass
        record = index.get(icao)
        if isinstance(record, dict):
            for key in [k for k in record if k.lower() == code]:
                record.pop(key, None)


def cached_inset_declined_reason(inset_path):
    """Why the BAKE will DECLINE this on-disk inset, or ``None``.

    THE ONE PREDICATE for the declared-empty state (2026-09-18, the
    LSGP/LSGY class).  It is the bake's own rule, by name: an inset
    holding less than ``INSET_MIN_VALID_FRAC`` valid pixels is not baked
    and carries no coverage, and the build proceeds on the base DEM
    (``bake_airport_insets_into_alt_dem`` -- the line that says so, and
    the ``airport_inset_nodata_refusals`` record it writes).

    Before this, three readers disagreed about the same file: the bake
    DECLARED it (loud line, provenance record, base DEM), the v2 frame
    check read "file exists but nothing baked" as the 2026-08-07 silent
    degrade and REFUSED the airport (taking LSGP and LSGY -- and with
    them the whole +46+006 tile -- down in app 1.0.351), and the fetch
    loop read "file exists" as a warm cache and re-stamped it ``ok``
    forever.  All three now ask this function.

    Content, never the index: an ``ok`` stamped in July over an empty
    raster is recognised at READ time, so the relics migrate themselves
    with no index rewrite.  ``None`` when the file is absent (the
    ordinary uncached case) or holds data.
    """
    if not os.path.isfile(inset_path):
        return None
    (is_empty, valid_fraction) = inset_is_effectively_empty(inset_path)
    if not is_empty:
        return None
    return ("it holds %.2f %% valid pixels (< %.2f %%) — it carries no "
            "coverage and the bake DECLINES it"
            % (100.0 * valid_fraction, 100.0 * INSET_MIN_VALID_FRAC))


def _void_inset_record_reason(inset_path, definition=None):
    """Why a cached fetch record describes NO usable inset, or ``None``.

    R13-1 -- A FETCH RECORD WITHOUT A VALID RASTER IS NO RECORD.  Two
    shapes, and both used to survive every rebuild: a sidecar whose
    ``.tif`` is gone (the cache check reads the raster, so the orphan
    record simply lingered), and a sidecar beside a raster that holds
    less than ``INSET_MIN_VALID_FRAC`` valid pixels (the KMCI class --
    structurally perfect, cut from the wrong state's project, and
    indistinguishable from a good cache until somebody deleted the json
    by hand).  ``None`` when there is no record at all: an absent sidecar
    is the ordinary uncached case the fetch path already handles.

    A third shape (spec us-holder-providers §2): the provider
    ``definition`` declares a non-metre RASTER ``vertical_unit`` and the
    record carries no ``vertical_unit_applied`` -- a pre-key engine wrote
    it, its cells are in the source unit, and it must never reach a bake
    as metres.  Point-cloud strategies (their key is the POINT unit,
    converted while gridding since #130) are not raster units and are
    never voided by it.
    """
    sidecar = os.path.splitext(inset_path)[0] + ".json"
    if not os.path.isfile(sidecar):
        return None
    if not os.path.isfile(inset_path):
        return "the raster it recorded is gone"
    pre_key = _pre_vertical_unit_key_reason(sidecar, definition)
    if pre_key is not None:
        return pre_key
    (is_empty, valid_fraction) = inset_is_effectively_empty(inset_path)
    if is_empty:
        return (
            "its raster holds %.2f %% valid pixels (< %.2f %%)"
            % (100.0 * valid_fraction, 100.0 * INSET_MIN_VALID_FRAC)
        )
    return None


def _pre_vertical_unit_key_reason(sidecar, definition):
    """Why ``sidecar`` is a pre-``vertical_unit`` record of a unit-bearing
    raster provider (see :func:`_void_inset_record_reason`), or ``None``."""
    if not definition:
        return None
    unit = str(definition.get("vertical_unit") or "").strip()
    if unit in ("", "m"):
        return None
    if definition.get("access_strategy") in _POINT_UNIT_STRATEGIES:
        return None
    try:
        with open(sidecar, "r") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        record = None
    if isinstance(record, dict) and record.get("vertical_unit_applied"):
        return None
    return ("%s declares vertical_unit=%s and the record carries no "
            "vertical_unit_applied - a pre-key engine wrote it in source "
            "units, which must never be baked as metres"
            % (definition.get("code"), unit))


def _archive_void_inset_record(inset_path, icao, code, reason):
    """Rename a void fetch record aside -- evidence, not deletion (R13-1).

    ``<name>.json.invalid-<date>``: the next pass sees no record and
    fetches, while what the failed fetch believed it had stays readable.
    """
    sidecar = os.path.splitext(inset_path)[0] + ".json"
    archived = sidecar + ".invalid-" + datetime.date.today().isoformat()
    try:
        os.replace(sidecar, archived)
    except OSError as error:                             # pragma: no cover
        UI.vprint(
            1,
            "   WARNING: could not archive the void elevation-inset record",
            os.path.basename(sidecar),
            ":",
            str(error),
        )
        return
    UI.vprint(
        0,
        "   [inset] %s from %s: %s - that is NO record; it is kept as %s "
        "and the fetch runs again."
        % (icao, code, reason, os.path.basename(archived)),
    )


def ensure_airport_insets(
    lat,
    lon,
    airport_bounding_boxes,
    provider_definitions,
    target_resolution_m,
    refresh=False,
    fetch_counter=None,
    meter_key="airport-insets",
    fetch_failures=None,
    airport_polygons=None,
):
    """Ensure a cached inset exists for each airport, per provider ranking.

    ``airport_polygons`` (optional ``{airport: shapely geometry}``, the
    aerodrome boundaries :func:`_airport_bounding_boxes` fills) rides the
    resolution ladder as each airport's FOOTPRINT: a LAS-tile rung is cut
    to it (spec las-tile-lidar-provider §2).  Without it a LAS rung lists
    the whole request box.

    ``airport_bounding_boxes`` maps airport identifier -> ``(west, south,
    east, north)`` in EPSG:4326 degrees.  For each airport the providers are
    tried in order; the first with coverage wins and its GeoTIFF +
    provenance sidecar are written.  ``target_resolution_m`` is the warp
    resolution in metres, or ``None`` for the "auto" airport elevation
    level: each provider then warps at its own best available native
    resolution, floored at ``AIRPORT_INSET_MIN_TARGET_RESOLUTION_M``.
    Either way the per-provider target is never finer than what that
    provider publishes (see :func:`_inset_target_resolution_m`), and a
    cached inset that predates that clamp is regenerated
    (:func:`_cached_inset_oversamples`).  ``index.json`` records positives and
    NEGATIVE (``no-coverage``) results so a rebuild never re-queries the
    discovery API; ``refresh`` forces a re-query and re-fetch.  A fetch
    that RAISES (:class:`TransientFetchError` or any strategy crash) is
    treated as transient: nothing is recorded for that provider and the
    next run retries it.

    The caches are margin-aware: a cached GeoTIFF whose provenance sidecar
    records a smaller bounding box than requested (the user enlarged
    ``airport_elevation_inset_margin_m``) is refetched, and negative results
    are re-checked when the request outgrows the box they were evaluated
    against (stored per airport under ``"bounding_box"``).  A request equal
    to or inside what is cached never refetches.  Records written before
    this key existed keep their negative results until a ``refresh``.

    ``fetch_counter`` (optional one-element list) is incremented once per
    network fetch ATTEMPTED — successful, no-coverage or raised alike, since
    each spends download wall time the build-time budgets exclude
    (``tools/check_build_time.py``).  ``fetch_failures`` (optional list)
    receives one ``(airport, provider code, error text)`` per fetch that
    RAISED -- the failures that left no durable answer -- so the caller
    can SURFACE them (issue #121) instead of settling a warm-looking pass.  A fully warm-cache pass leaves it at
    zero.

    Returns the updated index dictionary.  Strategy-agnostic: it only calls
    :func:`discover_inset` / :func:`fetch_inset`.
    """
    index = _read_index(lat, lon)
    # Poison sweep before any worker consults the cache: unreadable
    # rasters are deleted (index records scrubbed) so the ranking below
    # refetches them where still wanted; _write_index at the end of this
    # pass persists the scrub.
    _clear_poisoned_insets(lat, lon, index)
    checked_stamp = datetime.date.today().isoformat()
    # One shared, LAZY footprint prefetch for the whole tile: the first
    # surface-model masking pass triggers a single extract read covering
    # every airport's box; later airports clip from it in memory.  Tiles
    # that never reach a masking fetch never pay the read.
    footprint_prefetch = TileBuildingFootprintPrefetch(
        airport_bounding_boxes.values()
    )
    # One airport's whole provider chain, ready to run on a worker
    # thread: the chain stays strictly ordered inside its airport
    # (ranking + negative caching semantics untouched); workers share
    # only the index dict (each touches its own airport's key), the
    # footprint prefetch (internally locked) and the fetch counter
    # (guarded here).
    fetch_counter_lock = threading.Lock()

    def _count_fetch_attempt():
        if fetch_counter is not None:
            with fetch_counter_lock:
                fetch_counter[0] += 1

    def _fetch_airport_insets(icao):
        bounding_box = airport_bounding_boxes[icao]
        airport_record = index.get(icao, {})
        recorded_box = airport_record.get("bounding_box")
        negatives_are_stale = (
            recorded_box is not None
            and _bounding_box_extends_beyond(bounding_box, recorded_box)
        )
        for definition in provider_definitions:
            code = definition["code"]
            destination = FNAMES.airport_inset_dem(lat, lon, icao, code)
            # R13-1, BEFORE the cache is consulted: a record whose raster
            # is gone or holds no data is treated as UNFETCHED.  Without
            # this the empty-cut inset is a permanent cache -- the reuse
            # branch below breaks on it every run -- and the only cure
            # was deleting the sidecar by hand.
            void_reason = _void_inset_record_reason(destination,
                                                    definition)
            if void_reason is not None:
                _archive_void_inset_record(destination, icao, code,
                                           void_reason)
            # AN EMPTY RASTER IS NO CACHE (2026-09-18, the LSGP/LSGY
            # class).  R13-1 above catches an empty raster WITH a fetch
            # record; without one -- the state a killed or half-written
            # July fetch leaves -- the reuse gate below saw only
            # ``os.path.isfile`` and re-stamped ``ok`` on every run, so
            # a 0.00 %-valid file was a permanent cache.  One predicate
            # (:func:`cached_inset_declined_reason`, the BAKE's own
            # rule) now answers for the fetch loop, the frame check and
            # the bake alike.  The status goes in BEFORE the fetch: a
            # transient failure below leaves the record honest instead
            # of leaving it ``ok``.
            empty_reason = cached_inset_declined_reason(destination)
            if empty_reason is not None:
                airport_record[code] = empty_status(empty_reason)
                airport_record["checked"] = checked_stamp
                UI.vprint(
                    0,
                    "   [inset] %s from %s: the cached raster %s - that is "
                    "NO cache; it is recorded as %s (never 'ok') and the "
                    "fetch runs again."
                    % (icao, code, empty_reason, EMPTY_PREFIX.rstrip(":")),
                )
            cached_inset_is_stale = False
            if os.path.isfile(destination) and not refresh and (
                void_reason is None
            ) and empty_reason is None:
                # THE RE-CUT RULE, by name.  Same predicate as ever --
                # required today vs REQUESTED at cut time -- now stated
                # once, so the harness's refusal and the production
                # warm path judge with this function and never a copy.
                cached_inset_is_stale = inset_recut_is_needed(
                    lat, lon, icao, code, bounding_box
                )
                stale_reason = (
                    "was cut for a smaller box than this airport now needs"
                    if cached_inset_is_stale
                    else None
                )
                if (not cached_inset_is_stale
                        and definition.get(SURFACE_MODEL_BUILDING_MASKING)
                        and _sidecar_residual_masking_mismatch(
                            lat, lon, icao, code,
                            definition.get(RESIDUAL_STRUCTURE_MASKING))):
                    # One-time reconcile (2026-07-18): the cached inset was
                    # produced under the OTHER residual-masking setting —
                    # either it predates the feature while the gate is on,
                    # or it carries residual-masked pixels while the gate
                    # is off (the live-regression caches) — refetch once.
                    cached_inset_is_stale = True
                    stale_reason = (
                        "was built with a different residual-masking setting"
                    )
                if (not cached_inset_is_stale
                        and definition.get(SURFACE_MODEL_BUILDING_MASKING)
                        and _sidecar_footprint_packs_mismatch(
                            lat, lon, icao, code, bounding_box)):
                    # THE PACK SET MOVED (owner ruling 2026-09-17c (1)).
                    # The mask is built from the object footprints of the
                    # installed airport packs that RENDER here; installing
                    # one, removing one, or toggling one in
                    # scenery_packs.ini changes the mask and therefore the
                    # terrain this airport is graded against, and nothing
                    # in the cache used to notice.
                    cached_inset_is_stale = True
                    stale_reason = (
                        "was masked with a different set of installed "
                        "scenery packs"
                    )
                if not cached_inset_is_stale and _cached_inset_oversamples(
                    destination, definition
                ):
                    # One-time reconcile: the cached inset was warped FINER
                    # than the provider publishes (an airport_elevation_level
                    # pinned below native, before _inset_target_resolution_m
                    # clamped it).  The interpolation carries no detail and
                    # over-reports the source's resolution to the smoothing
                    # radius, so regenerate it at native posting.
                    cached_inset_is_stale = True
                    stale_reason = (
                        "was stored finer than this source publishes"
                        " (interpolated detail)"
                    )
                if not cached_inset_is_stale:
                    # THE BUILD-TIME LADDER RE-CHECK (owner RULINGS
                    # 2026-09-30aw (2)): an inset a coarser rung delivered
                    # re-asks the finer rungs' discovery on every build
                    # (one index query each, no download).  A new listing
                    # re-runs the whole ladder beside the cached raster.
                    recheck = ladder_recheck(lat, lon, icao, code,
                                             bounding_box, record=True)
                    if recheck is not None and (
                            recheck.get("result") == "new-listing"):
                        cached_inset_is_stale = True
                        stale_reason = (
                            "a finer ladder rung now lists new coverage "
                            "(%s)" % ladder_recheck_ids_text(
                                recheck["new_source_ids"])
                        )
                if not cached_inset_is_stale:
                    airport_record[code] = airport_record.get(code) or "ok"
                    _store_acceptance_probes_in_record(
                        airport_record, destination
                    )
                    break
                UI.vprint(
                    1,
                    "    Cached elevation inset for",
                    icao,
                    "from",
                    code,
                    stale_reason,
                    "- refetching.",
                )
            unverified = negative_is_unverified(
                airport_record, code, definition, bounding_box
            )
            version_stale = negative_is_version_stale(
                airport_record, code, definition, bounding_box
            )
            if (
                not refresh
                and not negatives_are_stale
                and airport_record.get(code) == NO_COVERAGE
                and not unverified
                and not version_stale
            ):
                continue
            if not _coverage_bbox_intersects(definition, bounding_box):
                # The honest, capability-free negative: this provider's
                # own declared box does not reach this airport.  No
                # capability stamp -- ``negative_is_unverified`` reads the
                # same boxes and never calls this one into question, so
                # stamping it would be pure churn in the shared repo.
                airport_record[code] = NO_COVERAGE
                airport_record["checked"] = checked_stamp
                continue
            if unverified:
                # A RECORDED REFRESH, not a content refresh: the negative
                # on disk was written by an engine whose capabilities the
                # index does not record, and 1.0.324 proved such an
                # engine could mint one out of its own inability.  It
                # completes a cache that was cut at a DEGRADED TIER.  It
                # happens exactly once -- the probe below stamps the
                # capability set, and a genuine negative is never asked
                # again.  Owner RULINGS 2026-09-13b (2).
                UI.vprint(
                    1,
                    "    [insets] %s: re-probing %s (recorded no-coverage "
                    "by a run without %s) - refresh"
                    % (icao, code,
                       "/".join(provider_required_capabilities(definition))
                       .upper()),
                )
            elif version_stale:
                # ONCE PER ENGINE VERSION (owner RULINGS 2026-09-15aq (4)).
                # This provider declares no capability, so 13b's door
                # above cannot reach it and the negative on disk would
                # otherwise be permanent -- as the 20 the TNM outage of
                # 2026-09-15 wrote across the Phoenix tiles were.  The
                # probe below stamps THIS version whatever it answers, so
                # a genuine empty listing is not asked again until the
                # next one.
                UI.vprint(
                    1,
                    "    [insets] %s: re-probing %s (no-coverage recorded "
                    "by engine %s, this is %s) - once per version"
                    % (icao, code,
                       recorded_engine_version(airport_record, code)
                       or "an unrecorded version",
                       _engine_version()),
                )
            if not has_gdal:
                airport_record[code] = unavailable_status(
                    "GDAL is not available"
                )
                airport_record["checked"] = checked_stamp
                _record_run_capabilities(airport_record, code, definition)
                UI.vprint(
                    1,
                    "    [insets] %s: %s SKIPPED - GDAL is not available; "
                    "recorded as unavailable, NOT as no-coverage (it will "
                    "be asked again)" % (icao, code),
                )
                continue
            UI.vprint(
                1,
                "    Fetching elevation inset for",
                icao,
                "from",
                code,
            )
            _count_fetch_attempt()
            fetch_destination = destination
            if cached_inset_is_stale:
                # A failed warp can leave a partial file behind; the
                # still-valid smaller inset must survive a failed
                # enlargement, so fetch beside it and replace on success.
                fetch_destination = destination + ".refetch"
            fetch_raised = False
            provider_unavailable = None
            # One-shot heartbeat so a long transfer is visibly alive:
            # stalls are aborted by the GDAL low-speed guard and retried
            # next run, so "still fetching" genuinely means still moving.
            # Armed only once the provider slot is HELD: with several
            # tiles fetching, airports queue behind the per-provider
            # concurrency cap, and a heartbeat that counts queue time
            # reads as a fleet of stalled transfers (field report
            # 2026-07-23: eight "still fetching 2+ minutes" lines that
            # were six airports politely waiting their turn).
            slow_note = threading.Timer(
                120.0, UI.vprint,
                (1, "    ...still fetching", icao, "from", code,
                 "(2+ minutes; a stalled transfer aborts automatically"
                 " and is retried on the next run)"))
            slow_note.daemon = True
            try:
                with _held_provider_fetch_slot(code):
                    slow_note.start()
                    provenance = fetch_inset(
                        definition,
                        bounding_box,
                        _inset_target_resolution_m(
                            definition, target_resolution_m
                        ),
                        fetch_destination,
                        footprint_prefetch=footprint_prefetch,
                        resolution_ladder=True,
                        **_footprint_kwargs(
                            (airport_polygons or {}).get(icao),
                            "footprint_polygon"),
                    )
            except ProviderUnavailable as error:
                # A MISSING CAPABILITY (owner RULINGS 2026-09-13b (1)):
                # the engine could not ask, so the answer is
                # ``unavailable:<reason>`` -- its own status class, which
                # the reader never treats as no-coverage and which no
                # later run short-circuits on.  INFO, not WARNING: the
                # build is fine, the TIER here is degraded and the line
                # says which provider and why.
                provenance = None
                fetch_raised = True
                provider_unavailable = error.reason
                UI.vprint(
                    1,
                    "    [insets] %s: %s SKIPPED - %s; recorded as "
                    "unavailable, NOT as no-coverage (it will be asked "
                    "again).  The inset here is cut at a LOWER TIER."
                    % (icao, code, error.reason),
                )
            except Exception as error:
                # A raised failure (a network timeout, a server outage, a
                # strategy crash) says nothing about coverage: skip the
                # provider for THIS run without caching a no-coverage
                # negative, so the next run retries the fetch.
                provenance = None
                fetch_raised = True
                UI.vprint(
                    1,
                    "   WARNING: elevation inset fetch for",
                    icao,
                    "from",
                    code,
                    "failed without a durable answer:",
                    str(error),
                    "- it will be retried on the next run.",
                )
                if fetch_failures is not None:
                    fetch_failures.append((icao, code, str(error)))
            finally:
                slow_note.cancel()
            if provenance is None:
                if cached_inset_is_stale:
                    if os.path.isfile(fetch_destination):
                        os.remove(fetch_destination)
                    UI.vprint(
                        1,
                        "   WARNING: could not refetch a larger inset for",
                        icao,
                        "from",
                        code,
                        "- keeping the previous smaller one.",
                    )
                    airport_record[code] = "ok"
                    airport_record["checked"] = checked_stamp
                    break
                if os.path.isfile(destination):
                    # No cache existed before this fetch (that branch breaks
                    # or refetches beside it), so this is a partial file
                    # from a broken warp; left in place it would pass the
                    # cache check and bake garbage on the next run.
                    os.remove(destination)
                if provider_unavailable is not None:
                    # Legible in the file: WHY this tier is missing.  Not
                    # a negative -- the next run asks again.
                    airport_record[code] = unavailable_status(
                        provider_unavailable
                    )
                    airport_record["checked"] = checked_stamp
                    _record_run_capabilities(airport_record, code, definition)
                    continue
                if fetch_raised:
                    # Transient: no durable record for this provider; a
                    # lower-ranked provider may still cover the airport
                    # this run, and this one retries next run.
                    continue
                airport_record[code] = NO_COVERAGE
                airport_record["checked"] = checked_stamp
                _record_run_capabilities(airport_record, code, definition)
                continue
            if cached_inset_is_stale:
                os.replace(fetch_destination, destination)
            provenance_path = FNAMES.airport_inset_provenance(
                lat, lon, icao, code
            )
            with open(provenance_path, "w", newline="\n") as handle:
                json.dump(provenance, handle, indent=2, sort_keys=True)
            airport_record[code] = "ok"
            airport_record["checked"] = checked_stamp
            _record_run_capabilities(airport_record, code, definition)
            # refresh=True: the raster on disk is new, so cached acceptance
            # probes from a previous (smaller) fetch must recompute.
            _store_acceptance_probes_in_record(
                airport_record, destination, refresh=True
            )
            break
        airport_record["bounding_box"] = [
            float(value) for value in bounding_box
        ]
        index[icao] = airport_record

    # key=str: callers pass string airport codes, but a mixed-type dict must
    # never abort the whole tile's fetches with an unorderable-keys
    # TypeError (defense in depth behind _airport_bounding_boxes' filter).
    icaos = sorted(airport_bounding_boxes, key=str)

    # Live progress for the fetch phase: per-airport completion drives the
    # vector step's bar, so the session's rate-based ETA gets a real
    # signal (without it, a long inset phase reads as an ever-growing
    # overrun) and the front ends' ring moves. Airports are not equal
    # cost, but the completion RATE is an honest live estimator.  The
    # task meter carries the same counts to the session's ETA floor,
    # which extrapolates them even while every bar sits still.
    try:
        from o4_engine import task_meter as TASK_METER
    except Exception:
        TASK_METER = None
    progress_lock = threading.Lock()
    progress_done = [0]

    def _fetch_airport_insets_with_progress(icao):
        try:
            # A Stop mid-phase drains the queued airports without
            # fetching (in-flight ones abort inside the warp); their
            # index entries stay unwritten, so the next run resumes.
            if not UI.red_flag:
                _fetch_airport_insets(icao)
        finally:
            with progress_lock:
                progress_done[0] += 1
                done = progress_done[0]
            UI.progress_bar(
                1, int(min(done * 100 // max(len(icaos), 1), 99)))
            if TASK_METER is not None:
                TASK_METER.advance(meter_key, done)
    # Airports fetch CONCURRENTLY: the work is network-bound (windowed
    # WCS/COG reads per airport — separate windows on purpose: one merged
    # request would cover the airports' bounding rectangle, i.e. most of
    # the tile at meter resolution).  A small pool bounds total load and
    # the per-provider slots below keep any single server at two
    # in-flight requests.
    if TASK_METER is not None:
        TASK_METER.begin(meter_key, len(icaos))
    try:
        if len(icaos) > 1:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(
                max_workers=min(4, len(icaos)),
                thread_name_prefix="inset-fetch",
            ) as pool:
                list(pool.map(_fetch_airport_insets_with_progress, icaos))
        else:
            for icao in icaos:
                _fetch_airport_insets_with_progress(icao)
    finally:
        if TASK_METER is not None:
            TASK_METER.end(meter_key)
    _write_index(lat, lon, index)
    return index


def _store_acceptance_probes_in_record(airport_record, inset_path, refresh=False):
    """Record the Phase C1 acceptance probes for an inset in its index entry.

    Stores ``[[latitude, longitude], ...]`` under ``"probes"`` so the
    working-grid decision is transparent and inspectable per airport (spec
    section 4, C1: "store the probe list with the tile's inset index"),
    and ties the list to the probed file's identity under ``"probes_for"``
    so the working-grid decision can consume it back without re-deriving
    the probes from a full raster decode (see
    ``_acceptance_probes_with_source_from_index``).  Computed once and
    cached in the index; recomputed when ``refresh`` is set or when the
    cached list belongs to a DIFFERENT file (a legacy record without
    ``"probes_for"`` upgrades here once).  A no-op without GDAL or when
    the probes cannot be derived.
    """
    identity = _inset_file_identity(inset_path)
    if (
        not refresh
        and "probes" in airport_record
        and airport_record.get("probes_for") == identity
    ):
        return
    try:
        probes = acceptance_probes_for_inset(inset_path)
    except Exception:
        return
    if probes:
        airport_record["probes"] = [
            [float(latitude), float(longitude)]
            for (latitude, longitude) in probes
        ]
        if identity is not None:
            airport_record["probes_for"] = identity


def list_cached_inset_dems(lat, lon, provider_codes=None):
    """Deterministically list the cached inset GeoTIFFs for a tile.

    Both build steps derive their composite from this same disk state, so
    the composite is idempotent and identical between steps.  Restricted to
    ``provider_codes`` (lower-cased) when given; otherwise every ``*.tif``
    in the inset directory.  Sorted by file name for determinism.
    """
    directory = FNAMES.airport_inset_directory(lat, lon)
    if not os.path.isdir(directory):
        return []
    # Empty files are poison a hard-killed fetch left behind — the sweep
    # in ensure_airport_insets removes them, but this listing must never
    # hand one to a consumer even before that pass has run.
    paths = sorted(
        path
        for path in glob.glob(os.path.join(directory, "*.tif"))
        if _file_size_or_zero(path) > 0
    )
    if provider_codes is None:
        return paths
    suffixes = tuple("_" + code.lower() + ".tif" for code in provider_codes)
    return [path for path in paths if path.endswith(suffixes)]


def _file_size_or_zero(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# =====================================================================
# Inset-derived water supplement (hydro-flat basins) — RETIRED
# =====================================================================
# RETIRED from production (owner ruling 2026-07-26): ``include_water``
# no longer calls ``ensure_inset_water_supplement`` — water comes from
# OpenStreetMap / custom data only.  The scan re-read every cached
# inset raster in a tile whenever any one raster changed (~11 min on
# +35-081 / 54 rasters / 658 detected farm ponds) and never fixed the
# KBNA case it was built for.  The machinery below is kept importable
# (unit-tested, and callable from tools) but has no production caller.
#
# Lidar reads water surfaces as (near-)constant elevation, so real
# basins appear in the inset rasters as large flat plateaus sitting
# BELOW their rims — the KBNA wastewater ponds measure a 0.02 m
# internal range against rims 10+ m higher.  Such basins are usually
# absent from OpenStreetMap (no ``natural=water`` way exists over the
# KBNA ponds), so the mesh keeps raw noisy terrain there instead of the
# flat water the ``WATER`` seed + ``water_smoothing`` pipeline would
# produce.  These functions derive the missing polygons from the inset
# rasters themselves and write a per-tile OSM fragment which
# ``include_water`` merges ADDITIVELY into the water layer.

# Detection is TWO-TIER (measured on the real KBNA 3DEP inset,
# 2026-07-14):
#
# * STRICT, whole raster — exact hydro-flat plateaus (providers
#   hydro-flatten sizeable water bodies; KBNA's south-east lake is a
#   16,000 m2 plateau with 0.000 m internal range).  At the strict
#   thresholds exactly one basin qualifies at KBNA and every apron,
#   pavement plateau and void-fill artefact is rejected.
# * FACILITY-SCOPED, loose — INSIDE OpenStreetMap water-facility
#   outlines only (man_made=wastewater_plant, landuse=basin/reservoir).
#   Working ponds are NOT hydro-flat (the KBNA aeration ponds carry
#   0.3-0.5 m of lidar surface texture), so the loose thresholds would
#   over-detect hollows tile-wide (109 candidates measured) — but
#   inside a mapped water facility the outline itself authorises the
#   looser read; the lidar only traces the geometry.
#
# Strict tier:
INSET_WATER_LOCAL_FLATNESS_M = 0.05
INSET_WATER_COMPONENT_RANGE_M = 0.15
# The surrounding rim (75th percentile over an ~8-cell collar) must
# rise at least this above the water — flat PAVEMENT sits level with
# its surroundings and must never become water.
INSET_WATER_RIM_RISE_M = 0.3
# Plateaus further than this from the raster's median elevation are
# void-fill artefacts (a 40 m plateau inside the 150-180 m KBNA
# raster), never water.
INSET_WATER_PLAUSIBILITY_BAND_M = 30.0
INSET_WATER_MINIMUM_AREA_M2 = 500.0
# Facility-scoped tier (loose).  A WORKING pond's lidar surface is
# rough: the KBNA aeration ponds measure 0.25-0.55 m of 3-by-3 relief
# and a 1.8 m whole-pond range (foam, aerators, shore transition
# cells) — the mapped outline is the authorisation; these thresholds
# only trace the geometry within it.
INSET_WATER_FACILITY_LOCAL_FLATNESS_M = 0.6
INSET_WATER_FACILITY_COMPONENT_RANGE_M = 2.5
INSET_WATER_FACILITY_RIM_RISE_M = 0.3
INSET_WATER_FACILITY_MINIMUM_AREA_M2 = 300.0
# The OpenStreetMap outlines that authorise the loose tier.
INSET_WATER_FACILITY_QUERIES = (
    'way["man_made"="wastewater_plant"]',
    'way["landuse"="basin"]',
    'way["landuse"="reservoir"]',
)
# Schema stamp written into the supplement's ``generator`` attribute.
# Bump it whenever the detection rules change: a cached supplement can
# be NEWER than its rasters yet written under wrong rules (the
# 2026-07-18 SPJC regression left supplements with 1060 phantom urban
# basins), and mtime comparison alone would keep it forever.
INSET_WATER_SUPPLEMENT_SCHEMA = "hydro-flat-2026-07-18"


def detect_hydro_flat_water_rings(
    inset_tif_path,
    *,
    minimum_area_m2=None,
    local_flatness_m=None,
    component_range_m=None,
    rim_rise_m=None,
    plausibility_band_m=None,
):
    """Detect hydro-flat basins in one inset GeoTIFF.

    Returns a list of ``(ring, water_elevation_m)`` where ``ring`` is an
    unclosed ``[(longitude, latitude), ...]`` exterior; empty list when
    nothing qualifies (or GDAL/scipy are unavailable).  Pure read — no
    files written.
    """
    if minimum_area_m2 is None:
        minimum_area_m2 = INSET_WATER_MINIMUM_AREA_M2
    if local_flatness_m is None:
        local_flatness_m = INSET_WATER_LOCAL_FLATNESS_M
    if component_range_m is None:
        component_range_m = INSET_WATER_COMPONENT_RANGE_M
    if rim_rise_m is None:
        rim_rise_m = INSET_WATER_RIM_RISE_M
    if plausibility_band_m is None:
        plausibility_band_m = INSET_WATER_PLAUSIBILITY_BAND_M
    loaded = _load_inset_raster(inset_tif_path)
    if loaded is None:
        return []
    values, valid, geotransform = loaded
    return _detect_water_components(
        values, valid, geotransform,
        minimum_area_m2=minimum_area_m2,
        local_flatness_m=local_flatness_m,
        component_range_m=component_range_m,
        rim_rise_m=rim_rise_m,
        plausibility_band_m=plausibility_band_m,
    )


def _load_inset_raster(inset_tif_path):
    """``(median_filtered_values, valid_mask, geotransform)`` or ``None``
    (GDAL or scipy unavailable, unreadable file).  The 3-by-3 median
    pre-filter repairs isolated lidar dropouts (11 m pits inside the
    KBNA ponds) that would otherwise fragment flat components."""
    if not has_gdal:
        return None
    try:
        from scipy import ndimage
    except ImportError:
        UI.vprint(
            1,
            "   INFO: scipy is unavailable - inset water detection "
            "skipped.",
        )
        return None
    # gdal.UseExceptions() is on module-wide, so a poisoned cache file (a
    # hard-killed fetch's empty/truncated GeoTIFF) RAISES here rather than
    # returning None — and one bad file must degrade to "no inset", never
    # crash the tile build (2026-07-24: a 0-byte LSZC_italy10m.tif killed
    # +46+008 from ensure_inset_water_supplement).
    try:
        dataset = gdal.Open(inset_tif_path)
        if dataset is None:
            return None
        geotransform = dataset.GetGeoTransform()
        band = dataset.GetRasterBand(1)
        raw = band.ReadAsArray().astype(numpy.float64)
        nodata = band.GetNoDataValue()
    except Exception as error:
        UI.vprint(
            1,
            "   WARNING: unreadable elevation inset "
            + os.path.basename(inset_tif_path)
            + " - skipped: "
            + str(error),
        )
        return None
    valid = numpy.isfinite(raw)
    if nodata is not None:
        valid &= raw != nodata
    values = ndimage.median_filter(raw, size=3)
    return values, valid, geotransform


def _detect_water_components(
    values,
    valid,
    geotransform,
    *,
    minimum_area_m2,
    local_flatness_m,
    component_range_m,
    rim_rise_m,
    plausibility_band_m,
    restrict_mask=None,
):
    """The shared component scan behind both detection tiers.

    ``restrict_mask`` (boolean, raster-shaped) limits candidate cells —
    the facility-scoped tier passes the rasterized OpenStreetMap
    water-facility outlines.  Returns ``[(ring, water_elevation_m)]``.
    """
    from scipy import ndimage
    from shapely.errors import GEOSException
    from shapely.geometry import box as shapely_box
    from shapely.ops import unary_union

    # Metric cell size at the raster's own latitude.
    centre_latitude = geotransform[3] + (
        geotransform[5] * values.shape[0] / 2.0
    )
    metres_per_degree_longitude = GEO.lat_to_m * numpy.cos(
        numpy.radians(centre_latitude)
    )
    cell_area_m2 = abs(
        geotransform[1] * metres_per_degree_longitude
        * geotransform[5] * GEO.lat_to_m
    )
    if cell_area_m2 <= 0.0:
        return []
    minimum_cells = max(9, int(minimum_area_m2 / cell_area_m2))

    # 3-by-3 local relief (max minus min over the neighbourhood).
    local_maximum = ndimage.maximum_filter(values, size=3)
    local_minimum = ndimage.minimum_filter(values, size=3)
    flat = (local_maximum - local_minimum) <= local_flatness_m
    flat &= valid
    if restrict_mask is not None:
        flat &= restrict_mask
    flat[0, :] = flat[-1, :] = False
    flat[:, 0] = flat[:, -1] = False

    labels, label_count = ndimage.label(flat)
    if label_count == 0:
        return []
    sizes = numpy.bincount(labels.ravel())
    overall_median = float(numpy.median(values[valid])) if valid.any() \
        else 0.0

    rings = []
    for label_index in range(1, label_count + 1):
        if sizes[label_index] < minimum_cells:
            continue
        component = labels == label_index
        component_values = values[component]
        if (float(component_values.max())
                - float(component_values.min())) > component_range_m:
            continue
        water_elevation = float(numpy.median(component_values))
        if abs(water_elevation - overall_median) > plausibility_band_m:
            continue
        # The rim must RISE above the water (a flat apron sits level
        # with its surroundings and must never become water).  75th
        # percentile over an 8-cell collar: shores shelve gently, so a
        # thin median under-reads real rims (measured KBNA lake:
        # 3-cell median rim +0.12 m, 8-cell 75th percentile +5.7 m).
        dilated = ndimage.binary_dilation(component, iterations=8)
        rim = dilated & ~component & valid
        if not rim.any():
            continue
        if float(numpy.percentile(values[rim], 75)) < (
                water_elevation + rim_rise_m):
            continue
        # Draw the polygon one cell INSIDE the shore so every enclosed
        # mesh triangle converges cleanly under water smoothing.
        eroded = ndimage.binary_erosion(component)
        if not eroded.any():
            eroded = component
        # Row-run rectangles -> union -> simplify (runs, not cells,
        # keep the union cheap).
        boxes = []
        for row_index in numpy.flatnonzero(eroded.any(axis=1)):
            row = eroded[row_index]
            occupied_columns = numpy.flatnonzero(row)
            runs = numpy.split(
                occupied_columns, numpy.flatnonzero(
                    numpy.diff(occupied_columns) > 1) + 1)
            for run in runs:
                if run.size == 0:
                    continue
                column_start, column_end = int(run[0]), int(run[-1])
                longitude_west = geotransform[0] + (
                    column_start * geotransform[1])
                longitude_east = geotransform[0] + (
                    (column_end + 1) * geotransform[1])
                latitude_north = geotransform[3] + (
                    row_index * geotransform[5])
                latitude_south = geotransform[3] + (
                    (row_index + 1) * geotransform[5])
                boxes.append(shapely_box(
                    min(longitude_west, longitude_east),
                    min(latitude_north, latitude_south),
                    max(longitude_west, longitude_east),
                    max(latitude_north, latitude_south),
                ))
        if not boxes:
            continue
        try:
            union = unary_union(boxes)
        except (ValueError, GEOSException):
            continue
        polygons = ([union] if union.geom_type == "Polygon"
                    else [geometry for geometry in getattr(
                        union, "geoms", [])
                        if geometry.geom_type == "Polygon"])
        for polygon in polygons:
            # Metric area floor PER POLYGON: a 55-cell component that is
            # a 2-cell-wide creek thread erodes to slivers — a linear
            # water body is OpenStreetMap's business, not a basin.
            polygon_area_m2 = (polygon.area * GEO.lat_to_m
                               * metres_per_degree_longitude)
            if polygon_area_m2 < minimum_area_m2:
                continue
            simplified = polygon.simplify(
                abs(geotransform[1]) * 2.0, preserve_topology=True)
            if simplified.is_empty \
                    or simplified.geom_type != "Polygon":
                simplified = polygon
            ring = [(float(x), float(y))
                    for x, y in simplified.exterior.coords[:-1]]
            if len(ring) >= 3:
                rings.append((ring, water_elevation))
    return rings


def _facility_outline_polygons(lat, lon):
    """Closed OpenStreetMap water-facility outlines for the tile
    (absolute longitude/latitude shapely polygons), fetched through the
    normal cached Overpass machinery (``cached_suffix="water_basins"``).
    Empty list when the fetch fails or nothing is mapped."""
    import O4_OSM_Utils as OSM
    from shapely.geometry import Polygon as ShapelyPolygon

    facility_layer = OSM.OSM_layer()
    if not OSM.OSM_queries_to_OSM_layer(
        list(INSET_WATER_FACILITY_QUERIES),
        facility_layer,
        lat,
        lon,
        tags_of_interest=["man_made", "landuse"],
        cached_suffix="water_basins",
    ):
        return []
    polygons = []
    for way_identifier in (facility_layer.dicosmfirst["w"]
                           or facility_layer.dicosmw):
        node_references = facility_layer.dicosmw.get(way_identifier, [])
        if len(node_references) < 4 \
                or node_references[0] != node_references[-1]:
            continue
        ring = [facility_layer.dicosmn[reference]
                for reference in node_references[:-1]]
        try:
            polygon = ShapelyPolygon(ring)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if not polygon.is_empty and polygon.area > 0.0:
                polygons.append(polygon)
        except ValueError:
            continue
    return polygons


def _facility_restrict_mask(polygons, values_shape, geotransform):
    """Boolean raster mask of the cells whose centres fall inside any
    facility polygon, or ``None`` when no polygon overlaps the raster."""
    import shapely

    if not polygons:
        return None
    rows, columns = values_shape
    mask = numpy.zeros(values_shape, dtype=bool)
    for polygon in polygons:
        minimum_x, minimum_y, maximum_x, maximum_y = polygon.bounds
        column_start = int((minimum_x - geotransform[0])
                           / geotransform[1]) - 1
        column_end = int((maximum_x - geotransform[0])
                         / geotransform[1]) + 2
        row_start = int((maximum_y - geotransform[3])
                        / geotransform[5]) - 1
        row_end = int((minimum_y - geotransform[3])
                      / geotransform[5]) + 2
        column_start = max(0, column_start)
        column_end = min(columns, column_end)
        row_start = max(0, row_start)
        row_end = min(rows, row_end)
        if column_start >= column_end or row_start >= row_end:
            continue
        window_rows = numpy.arange(row_start, row_end)
        window_columns = numpy.arange(column_start, column_end)
        latitudes = geotransform[3] + (
            (window_rows + 0.5) * geotransform[5])
        longitudes = geotransform[0] + (
            (window_columns + 0.5) * geotransform[1])
        longitude_grid, latitude_grid = numpy.meshgrid(
            longitudes, latitudes)
        inside = shapely.contains_xy(
            polygon, longitude_grid.ravel(), latitude_grid.ravel()
        ).reshape(longitude_grid.shape)
        mask[row_start:row_end, column_start:column_end] |= inside
    return mask if mask.any() else None


def _restrict_to_inset_core_box(inset_path, valid, geotransform):
    """``valid`` limited to the MEASURED part of a ladder-assembled inset:
    the sidecar's ``core.bounding_box_wgs84`` when the inset is a
    two-layer one, and never inside the box of an interior hole the
    ladder FILLED from a coarser rung (spec las-tile §12 -- a 3 m / 10 m
    fill upsampled to 1 m is the upsampled class this detector skips,
    the §5 ruling for the surround applied to every fill).  Unchanged for
    an inset with neither."""
    provenance_path = os.path.splitext(inset_path)[0] + ".json"
    try:
        with open(provenance_path, "r") as handle:
            provenance = json.load(handle) or {}
    except (OSError, ValueError):
        return valid
    if not isinstance(provenance, dict):
        return valid
    rows, cols = valid.shape
    xs = geotransform[0] + (numpy.arange(cols) + 0.5) * geotransform[1]
    ys = geotransform[3] + (numpy.arange(rows) + 0.5) * geotransform[5]

    def _inside(box):
        (west, south, east, north) = box
        return ((ys >= south) & (ys <= north))[:, None] & (
            (xs >= west) & (xs <= east))[None, :]

    core = provenance.get("core")
    box = core.get("bounding_box_wgs84") if isinstance(core, dict) else None
    if box and len(box) == 4:
        valid = valid & _inside(box)
    for hole in provenance.get("holes") or ():
        hole_box = (hole.get("bounding_box_wgs84")
                    if isinstance(hole, dict) else None)
        if hole_box and len(hole_box) == 4 and hole.get("filled_by"):
            valid = valid & ~_inside(hole_box)
    return valid


def _water_detection_trusts_inset_raster(inset_path):
    """Whether hydro-flat water detection may read this inset raster.

    The detector's physical premise is a MEASURED surface at the
    working resolution: lidar reads real water as hydro-flat plateaus
    while dry ground keeps centimetre texture in every 3-by-3
    neighbourhood.  Two raster classes break that premise and are
    skipped outright (live SPJC regression 2026-07-18: 1060 phantom
    basins over urban Lima and Callao):

    * surface models with building-footprint masking — the masked
      pixels are ``gdal.FillNodata`` interpolation, synthetic smooth
      "ground" that reads as hydro-flat across whole city blocks
      (the SPJC GLO-30 inset had 29% of its pixels interpolated);
    * rasters upsampled beyond their native resolution (Copernicus
      GLO-30's 30 m cells fetched at 3 m) — every 3-by-3 window then
      samples one native cell's resampling ramp, so the flatness
      measure reads interpolation smoothness, not surface texture.

    A missing or unreadable provenance sidecar reads as trusted:
    pre-sidecar caches are the established lidar providers.
    """
    provenance_path = os.path.splitext(inset_path)[0] + ".json"
    try:
        with open(provenance_path, "r") as handle:
            provenance = json.load(handle)
    except (OSError, ValueError):
        return True
    if isinstance(provenance.get(SURFACE_MODEL_BUILDING_MASKING), dict):
        return False
    native_resolution_m = _parse_float(
        provenance.get("native_resolution_m"), default=None
    )
    fetched_resolution_m = _parse_float(
        provenance.get("resolution_m"), default=None
    )
    if (native_resolution_m is not None
            and fetched_resolution_m is not None
            and native_resolution_m > fetched_resolution_m):
        return False
    return True


def _inset_water_supplement_schema_current(supplement_path):
    """Whether a cached supplement was written under the current
    detection schema (the stamp lives in its ``generator`` attribute).
    Old-schema files regenerate even when newer than their rasters —
    their RULES were wrong when they were written, which mtime
    comparison cannot see.  Unreadable files read as stale."""
    import bz2

    try:
        with bz2.open(supplement_path, "rt", encoding="utf-8") as handle:
            handle.readline()
            return INSET_WATER_SUPPLEMENT_SCHEMA in handle.readline()
    except OSError:
        return False


def ensure_inset_water_supplement(lat, lon):
    """Write (or refresh) the per-tile inset-water OSM supplement and
    return its path, or ``None`` when no basin qualifies.

    Derived from every cached inset GeoTIFF for the tile
    (``list_cached_inset_dems``) whose provenance passes
    :func:`_water_detection_trusts_inset_raster`; regenerated when
    missing, older than any raster, or written under an older
    detection schema; removed when the qualifying rasters leave
    nothing behind.  The fragment is standard OSM XML (closed
    ``natural=water`` ways with negative identifiers), consumed
    additively by ``include_water``.
    """
    import bz2

    supplement_path = FNAMES.inset_water(lat, lon)
    inset_paths = list_cached_inset_dems(lat, lon)
    if not inset_paths:
        if os.path.isfile(supplement_path):
            os.remove(supplement_path)
        return None
    newest_raster = max(os.path.getmtime(path) for path in inset_paths)
    if (os.path.isfile(supplement_path)
            and os.path.getmtime(supplement_path) >= newest_raster
            and _inset_water_supplement_schema_current(supplement_path)):
        return supplement_path

    facility_polygons = _facility_outline_polygons(lat, lon)
    all_rings = []
    for inset_path in inset_paths:
        if not _water_detection_trusts_inset_raster(inset_path):
            UI.vprint(
                2,
                "   Inset water detection skips "
                + os.path.basename(inset_path)
                + " (surface model or upsampled raster).",
            )
            continue
        loaded = _load_inset_raster(inset_path)
        if loaded is None:
            continue
        values, valid, geotransform = loaded
        # A TWO-LAYER inset (spec las-tile-lidar-provider §4): only the
        # 1 m CORE is a measured surface; the surround is a coarser rung
        # upsampled to 1 m (the upsampled class above), so detection is
        # restricted to the core's box.
        valid = _restrict_to_inset_core_box(inset_path, valid, geotransform)
        # Strict tier: exact hydro-flat plateaus, whole raster.
        for ring, water_elevation in _detect_water_components(
                values, valid, geotransform,
                minimum_area_m2=INSET_WATER_MINIMUM_AREA_M2,
                local_flatness_m=INSET_WATER_LOCAL_FLATNESS_M,
                component_range_m=INSET_WATER_COMPONENT_RANGE_M,
                rim_rise_m=INSET_WATER_RIM_RISE_M,
                plausibility_band_m=INSET_WATER_PLAUSIBILITY_BAND_M):
            all_rings.append((ring, water_elevation, inset_path))
        # Facility-scoped tier: loose thresholds, only inside mapped
        # water-facility outlines (working ponds carry real surface
        # texture and are never exactly flat).
        restrict_mask = _facility_restrict_mask(
            facility_polygons, values.shape, geotransform)
        if restrict_mask is not None:
            for ring, water_elevation in _detect_water_components(
                    values, valid, geotransform,
                    minimum_area_m2=INSET_WATER_FACILITY_MINIMUM_AREA_M2,
                    local_flatness_m=INSET_WATER_FACILITY_LOCAL_FLATNESS_M,
                    component_range_m=(
                        INSET_WATER_FACILITY_COMPONENT_RANGE_M),
                    rim_rise_m=INSET_WATER_FACILITY_RIM_RISE_M,
                    plausibility_band_m=INSET_WATER_PLAUSIBILITY_BAND_M,
                    restrict_mask=restrict_mask):
                all_rings.append((ring, water_elevation, inset_path))
    if not all_rings:
        if os.path.isfile(supplement_path):
            os.remove(supplement_path)
        return None

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<osm version="0.6" generator="O4_Airport_Elevation_Insets '
             + INSET_WATER_SUPPLEMENT_SCHEMA + '">']
    node_identifier = -1
    way_identifier = -1
    for ring, water_elevation, inset_path in all_rings:
        node_identifiers = []
        for longitude, latitude in ring:
            lines.append(
                f'  <node id="{node_identifier}" lat="{latitude:.8f}" '
                f'lon="{longitude:.8f}" version="1"/>')
            node_identifiers.append(node_identifier)
            node_identifier -= 1
        lines.append(f'  <way id="{way_identifier}" version="1">')
        for reference in node_identifiers + [node_identifiers[0]]:
            lines.append(f'    <nd ref="{reference}"/>')
        lines.append('    <tag k="natural" v="water"/>')
        lines.append(
            '    <tag k="source" v="airport elevation inset '
            'hydro-flat detection"/>')
        lines.append(f'  </way>')
        way_identifier -= 1
        UI.vprint(
            1,
            "   Inset water basin detected at "
            f"{water_elevation:.2f} m "
            f"({os.path.basename(inset_path)}).",
        )
    lines.append("</osm>")
    with bz2.open(supplement_path, "wt", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return supplement_path


# =====================================================================
# Tile-aware wrappers (read tile config attributes)
# =====================================================================
def insets_enabled_for_tile(tile):
    """Master gate for the tile: config on AND GDAL present.

    Emits exactly one clear line when the gate is on but GDAL is missing,
    then disables the feature so the build is byte-identical to gate-off.
    """
    if resolved_inset_mode(tile) == "None":
        # HAZARD: the STRING "None" is TRUTHY.  This gate was a bare
        # truthiness read while the key was a bool; after the 2026-09-18
        # enum relabel (RULINGS 18c/18e) a truthiness read would turn Off
        # into On.  "None" keeps the full old ``False`` meaning: nothing
        # fetched AND nothing on disk composited, baked, balloted or used
        # for the smoothing radius (owner OQ2).
        return False
    if not has_gdal:
        UI.vprint(
            1,
            "   INFO: airport elevation insets are enabled but the GDAL "
            "python bindings (osgeo) are unavailable - insets are disabled "
            "for this build.",
        )
        return False
    return True


def _airport_bounding_boxes(tile, dico_airports, only=None, margin_m=None,
                            boundary_polygons=None):
    """Build ``{airport: (west, south, east, north)}`` in EPSG:4326.

    ``margin_m`` overrides ``airport_elevation_inset_margin_m`` (``0`` =
    the aerodrome boundary's own box).  ``boundary_polygons``, when a
    dict, is FILLED with ``{airport: shapely geometry}`` -- the aerodrome
    boundary in EPSG:4326 degrees, the extent a surgical LAS fetch is cut
    to (spec las-tile-lidar-provider §2, #130).  The return value is
    unchanged for every existing caller.

    Ortho4XP geometry is in tile-relative degrees; this adds the tile origin
    back and expands by ``airport_elevation_inset_margin_m`` converted to
    degrees at the tile latitude.

    *only*, when given, is the collection of ``dico_airports`` keys the
    INSET SELECTION admits (spec §A.4).  ``only=None`` is every airport,
    byte-identical to the pre-2026-09-18 behaviour, and stays that way for
    the other callers of this function (the coastline visibility ladder,
    ``_required_inset_box``, the harness's ``--warm-insets``): the trim is
    applied at the ONE fetch entry, :func:`ensure_insets_for_tile`.
    """
    admitted = None if only is None else set(only)
    if margin_m is None:
        margin_m = getattr(tile, "airport_elevation_inset_margin_m", 2000.0)
    metres_per_degree_latitude = GEO.lat_to_m
    metres_per_degree_longitude = GEO.lon_to_m(tile.lat + 0.5)
    margin_lon = margin_m / metres_per_degree_longitude
    margin_lat = margin_m / metres_per_degree_latitude
    boxes = {}
    skipped_without_code = 0
    for airport in dico_airports:
        # dico_airports keys are ICAO/IATA/local_ref/name STRINGS for real
        # airports but REPRESENTATIVE-NODE TUPLES for unnamed strips
        # (O4_Airport_Utils key_type "repr_node").  Tuple keys cannot name a
        # cache file (FNAMES.airport_inset_dem concatenates the key) and made
        # ensure_airport_insets' sorted() raise "'<' not supported between
        # instances of 'str' and 'tuple'" — the 2026-07-14 CYXY fetch abort.
        # Unnamed strips do not get elevation insets; skip them loudly.
        if not isinstance(airport, str):
            skipped_without_code += 1
            continue
        if admitted is not None and airport not in admitted:
            continue
        record = dico_airports[airport]
        boundary = record.get("boundary")
        if boundary is None or boundary.is_empty:
            continue
        (xmin, ymin, xmax, ymax) = boundary.bounds
        boxes[airport] = (
            tile.lon + xmin - margin_lon,
            tile.lat + ymin - margin_lat,
            tile.lon + xmax + margin_lon,
            tile.lat + ymax + margin_lat,
        )
    if skipped_without_code:
        UI.vprint(
            1,
            "   INFO: airport elevation insets skipped",
            skipped_without_code,
            "unnamed airport(s) (no code to cache under).",
        )
    if isinstance(boundary_polygons, dict):
        boundary_polygons.update(airport_boundary_polygons(
            tile, {key: dico_airports[key] for key in boxes}))
    return boxes


def _footprint_kwargs(value, name):
    """``{name: value}`` only when there IS a footprint, so every caller
    and test double that predates footprints keeps its call shape."""
    return {name: value} if value else {}


def airport_boundary_polygons(tile, dico_airports, only=None):
    """``{airport: shapely geometry}`` -- each named aerodrome's BOUNDARY
    in EPSG:4326 degrees (the tile-relative boundary moved by the tile
    origin): the extent a surgical LAS fetch is cut to (spec
    las-tile-lidar-provider §2).  Same admission as
    :func:`_airport_bounding_boxes` (string keys, the ``only`` set, a
    non-empty boundary)."""
    from shapely import affinity as _affinity

    admitted = None if only is None else set(only)
    polygons = {}
    for airport, record in dico_airports.items():
        if not isinstance(airport, str):
            continue
        if admitted is not None and airport not in admitted:
            continue
        boundary = (record or {}).get("boundary") if isinstance(
            record, dict) else None
        if boundary is None or getattr(boundary, "is_empty", True):
            continue
        polygons[airport] = _affinity.translate(
            boundary, xoff=tile.lon, yoff=tile.lat)
    return polygons


# "Auto" airport elevation detail never warps finer than this: sub-half-
# metre lidar buys nothing the mesh can carry while multiplying the
# stored bytes, so best-available bottoms out at 0.5 m.
AIRPORT_INSET_MIN_TARGET_RESOLUTION_M = 0.5


def parse_airport_elevation_level(value):
    """Parse an ``airport_elevation_level`` configuration value.

    Returns the target inset resolution in metres (a positive float) for
    a numeric level, or ``None`` for "auto" (the default), empty, or
    anything unrecognised (with one warning, so a typo degrades to the
    automatic best-available behaviour instead of failing the build).
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ("", "auto"):
            return None
    try:
        resolution_m = float(value)
    except (TypeError, ValueError):
        resolution_m = None
    if resolution_m is None or resolution_m <= 0:
        UI.vprint(
            1,
            "   WARNING: unrecognised airport_elevation_level",
            repr(value),
            "- using auto.",
        )
        return None
    return resolution_m


def _auto_inset_target_resolution_m(definition):
    """Best-available inset target for one provider ("auto" level).

    The provider's declared native resolution, floored at
    ``AIRPORT_INSET_MIN_TARGET_RESOLUTION_M``.  A definition that
    declares no resolution is assumed meter-class (the quality tier this
    feature exists for) and warps at 1 m.
    """
    native_resolution_m = _definition_resolution_m(definition)
    if native_resolution_m is None:
        return 1.0
    return max(
        AIRPORT_INSET_MIN_TARGET_RESOLUTION_M, float(native_resolution_m)
    )


def _inset_target_resolution_m(definition, target_resolution_m):
    """The warp target for one provider, NEVER finer than its native grid.

    ``target_resolution_m`` is the ``airport_elevation_level`` decision:
    ``None`` for "auto" (each provider warps at its own best available
    resolution) or a pinned figure in metres.  A pin FINER than what the
    provider publishes is raised to native: resampling 30 m radar onto a
    3 m grid manufactures no detail, it just spends the transfer, the
    warp and ~100x the disk on interpolation -- and it lies to every
    consumer that reads a cached inset's posting as its resolution (the
    per-airport smoothing radius among them).  A pin COARSER than native
    is honoured: that is a real, deliberate trade of detail for bytes.

    A provider that declares no native resolution cannot be clamped, so
    its pin is honoured as given.
    """
    if target_resolution_m is None:
        return _auto_inset_target_resolution_m(definition)
    native_resolution_m = _definition_resolution_m(definition)
    if native_resolution_m is None or native_resolution_m <= 0:
        return target_resolution_m
    return max(float(target_resolution_m), float(native_resolution_m))


def ensure_insets_for_tile(tile, dico_airports, refresh=False,
                           meter_key="airport-insets"):
    """Fetch/refresh every airport inset on the tile (step-1 download hook).

    ``meter_key`` names the pass on the task meter: a NEIGHBOUR tile's pass
    (``O4_Vector_Map.ensure_tile_frame``) runs as ``"airport-insets
    +38-009"`` so it never collides with the home tile's own (§D.3)."""
    # How many inset fetches this build performed, mirrored into the tile
    # build record as ``features.insets_fetched``: a non-zero count marks
    # the run's step-1 wall time as download-polluted, which disqualifies
    # it as a build-time measurement (tools/check_build_time.py).
    tile.insets_fetched_last_build = 0
    if not insets_enabled_for_tile(tile):
        return
    provider_definitions = select_provider_definitions(
        getattr(tile, "airport_elevation_providers", "auto")
    )
    if not provider_definitions:
        return
    # THE ONE TRIM (spec §A.4): the inset set follows the tile's OWN
    # ``airport_elevation_insets`` mode, applied to the dico_airports KEY.
    # Every downstream reader stays disk-driven (owner Q3, RULINGS 18c):
    # an orphan inset already cached for an airport outside the selection
    # keeps being composited, baked and balloted.
    mode = resolved_inset_mode(tile)
    selected = inset_keys(dico_airports, mode)
    named = sum(1 for key in dico_airports if isinstance(key, str))
    boxes = _airport_bounding_boxes(tile, dico_airports, only=selected)
    if not boxes:
        if named:
            UI.vprint(
                1,
                "   Airport insets: none of the %d named aerodrome(s) on "
                "this tile are in the inset selection (airport lidar "
                "insets = %s) - nothing to fetch." % (named, mode))
        return
    tile.inset_selection_mode = mode
    tile.inset_selection_keys = sorted(selected)
    # None = "auto": each provider warps at its own best available
    # resolution (ensure_airport_insets resolves it per definition).
    resolution_m = parse_airport_elevation_level(
        getattr(tile, "airport_elevation_level", "auto")
    )
    fetch_counter = [0]
    fetch_failures = []
    # Only a NEIGHBOUR pass names its own meter key; the home pass keeps
    # the historic call shape.
    extra = {} if meter_key == "airport-insets" else {"meter_key": meter_key}
    try:
        ensure_airport_insets(
            tile.lat,
            tile.lon,
            boxes,
            provider_definitions,
            resolution_m,
            refresh=refresh,
            fetch_counter=fetch_counter,
            fetch_failures=fetch_failures,
            **extra,
            **_footprint_kwargs(airport_boundary_polygons(
                tile, dico_airports, only=selected), "airport_polygons"),
        )
    except Exception as error:
        # Never let inset fetching abort a build (G4 safety) -- but never
        # let it pass QUIETLY either (issue #121): the loud channel
        # reaches the app's log pane (a Log warning event) and
        # Ortho4XP.log, not only the console drawer.
        UI.loud_warning(
            "   WARNING: airport elevation inset fetch for tile %+03d%+04d "
            "raised %s: %s - continuing without insets; the frame is NOT "
            "warm and the next build retries it."
            % (tile.lat, tile.lon, type(error).__name__, error))
    else:
        if fetch_failures:
            # THE FETCH FAILED ON TRANSPORT (or crashed) for these
            # providers: nothing durable was recorded for them, so the
            # pass is NOT settled -- no completion stamp, and the frame
            # check (:func:`airport_inset_frame_problem`) reads the
            # unanswered provider as a MISSING inset, never as a warm
            # "no provider covers it".  Named, provider by provider, on
            # the loud channel (issue #121: every such line used to reach
            # the console drawer only, and the build exited 0 on the base
            # DEM).
            for (icao, code, text) in fetch_failures:
                UI.loud_warning(
                    "   WARNING: airport elevation inset for %s from %s "
                    "FAILED (%s) - this build uses NO inset from %s; check "
                    "the network / TLS (antivirus or proxy HTTPS "
                    "inspection) and rebuild." % (icao, code, text, code))
            return
        # The pass settled every airport against every provider without
        # raising: nothing is left to fetch for THIS configuration, so
        # stamp it for the scheduler's fetch-admission predicate
        # (:func:`is_cached`).  A raised pass deliberately leaves no
        # stamp — the next run retries it.
        _write_inset_completion_stamp(tile)
    finally:
        tile.insets_fetched_last_build = fetch_counter[0]


# ---------------------------------------------------------------------
# Inset step-completion stamp + the cache predicate built on it
# (docs/specs/apron-string-and-scheduling-spec.md §A.2)
#
# Whether a cached inset is STALE is decided per airport per provider
# against the box that airport currently requests (_fetch_airport_insets
# above: margin shrink, residual-masking mismatch, over-sampling).  That
# needs ``dico_airports`` — parsed out of the OSM airports layer — so it
# is not a cheap question, and re-deriving it scheduler-side is exactly
# the duplicated derivation the spec forbids.  ``ensure_insets_for_tile``
# therefore STAMPS a settled pass together with the inputs that decided
# it, and the predicate compares only those.  Any mismatch, and every
# unknown, reads as NOT cached.
# ---------------------------------------------------------------------

INSET_COMPLETION_SCHEMA = "2026-07-30"


def inset_completion_stamp_path(lat, lon):
    """Where a tile's settled-inset stamp lives."""
    return os.path.join(
        FNAMES.airport_inset_directory(lat, lon), "complete.json")


def _inset_completion_key(tile):
    """The cheap inputs that decide what an inset pass would fetch.

    The airport SET comes from the tile's OSM airports layer, so that
    cache's identity stands in for the set itself: an unchanged cache
    means an unchanged set, and a refreshed one invalidates the stamp
    without anybody parsing it.
    """
    try:
        airports_cache = FNAMES.osm_cached(tile.lat, tile.lon, "airports")
        stat = os.stat(airports_cache)
        airports_identity = [stat.st_size, round(stat.st_mtime, 3)]
    except OSError:
        airports_identity = None
    return {
        "schema": INSET_COMPLETION_SCHEMA,
        "margin_m": float(
            getattr(tile, "airport_elevation_inset_margin_m", 2000.0)),
        "providers": str(
            getattr(tile, "airport_elevation_providers", "auto")),
        "level": str(getattr(tile, "airport_elevation_level", "auto")),
        "airports_layer": airports_identity,
        # §B.2: WHICH airports the pass was settled over.  The inset set
        # is a pure function of (airports layer, inset mode) and both are
        # now in the key, so the stamp is EXACT rather than a proxy.
        "selection_mode": resolved_inset_mode(tile),
    }


def _stamp_key_validates(stamp, wanted):
    """True when an on-disk stamp settles the key fields ``wanted`` asks.

    THE ONE comparison of a stamp's key fields, shared by :func:`is_cached`
    and :func:`_write_inset_completion_stamp` (issue #78): the writer must
    not rewrite a stamp the predicate already accepts.
    """
    if not isinstance(stamp, dict):
        return False
    for key, value in wanted.items():
        if key == "selection_mode":
            # ORDERED, not equality (§B.2): None < ICAO < All, and the
            # tile is cached when the stamp settled a SUPERSET of what
            # is wanted now.  A stamp WITHOUT the key — every stamp on
            # disk today, schema 2026-07-30 — was settled over every
            # string-keyed aerodrome, which is a superset of any
            # selection, so it reads as "All".  INSET_COMPLETION_SCHEMA
            # is deliberately NOT bumped: a bump makes every tile on
            # the shared corpus uncached, and the next guarded build
            # would try to REWRITE complete.json — a shared-repo write
            # inside DEM prep, which the harness refuses.
            stamped = stamp.get(key, "All")
            if (MODE_RANK.get(str(stamped), len(MODES))
                    < MODE_RANK.get(str(value), 0)):
                return False
            continue
        if stamp.get(key) != value:
            return False
    return True


def _write_inset_completion_stamp(tile):
    """Record that an inset pass left nothing to fetch.  Never raises.

    Written only when the content CHANGED: every settled pass rebuilds the
    same stamp, and rewriting it with identical bytes is still a write into
    the shared data repo, which a build may not make (owner ruling e9daef5
    — a cache regeneration is an explicit, locked, hash-stamped event, not
    a build side effect).  Same discipline as :func:`_write_index` and the
    bathymetry band stamp.
    """
    try:
        stamp = _inset_completion_key(tile)
        if stamp["airports_layer"] is None:
            # Without an airports layer on disk the set is unknowable and
            # the stamp could never be validated — do not write one.
            return
        # Informational (§B.2): the keys the pass was settled FOR.
        # ``ensure_insets_for_tile`` lands them on the tile at the one
        # trim site; a caller that never ran it records nothing rather
        # than re-deriving a second answer.
        stamp["selected"] = sorted(
            getattr(tile, "inset_selection_keys", None) or [])
        stamp["insets"] = sorted(
            os.path.basename(path)
            for path in list_cached_inset_dems(tile.lat, tile.lon)
        )
        path = inset_completion_stamp_path(tile.lat, tile.lon)
        payload = json.dumps(stamp, indent=2, sort_keys=True)
        try:                   # absent, unreadable or different: write it
            with open(path, "r") as handle:
                on_disk = handle.read()
            if on_disk == payload:
                return
            # Issue #78: a stamp that already VALIDATES for the key fields
            # :func:`is_cached` reads, over the same inset set, is not
            # rewritten merely because the payload grew informational
            # keys (§B.2 ``selection_mode`` / ``selected``).  A stamp-only
            # rewrite is still a real write into the shared data repo, and
            # it changes no answer the predicate gives.
            existing = json.loads(on_disk)
            key_fields = {k: v for (k, v) in stamp.items()
                          if k not in ("selected", "insets")}
            if (_stamp_key_validates(existing, key_fields)
                    and sorted(existing.get("insets") or [])
                    == stamp["insets"]):
                return
        except Exception:
            pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = path + ".tmp"
        with open(temporary, "w", newline="\n") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    except Exception as error:
        UI.vprint(2, "Could not stamp the airport-inset cache:", error)


def unverified_capability_negatives(lat, lon, provider_definitions=None):
    """Every UNVERIFIED no-coverage negative in a tile's inset index.

    ``[(icao, provider code, [required capabilities]), ...]`` -- the
    records a next pass would RE-PROBE under owner RULINGS 2026-09-13b
    (2), sorted.  Cheap: one JSON read, no network, no raster.

    THE ONE PREDICATE for that question.  The engine's fetch loop asks it
    per provider (:func:`negative_is_unverified`); ``is_cached`` asks it
    to refuse to call such a tile settled; and the harness asks it to
    REFUSE a build up front, because a re-probe is a write into the
    shared data repo and a build never makes one as a side effect.
    """
    if provider_definitions is None:
        provider_definitions = select_provider_definitions(
            "auto", role=ROLE_AIRPORT_INSET
        )
    gated = [
        definition
        for definition in provider_definitions
        if provider_required_capabilities(definition)
    ]
    if not gated:
        return []
    out = []
    for (icao, airport_record) in sorted(_read_index(lat, lon).items()):
        for definition in gated:
            code = definition["code"]
            if negative_is_unverified(airport_record, code, definition):
                out.append(
                    (icao, code, provider_required_capabilities(definition))
                )
    return out


def version_stale_capability_free_negatives(lat, lon,
                                            provider_definitions=None):
    """Every CAPABILITY-FREE no-coverage negative from another engine.

    ``[(icao, provider code, recorded version or None), ...]`` -- the
    records a next pass would RE-PROBE under owner RULINGS 2026-09-15aq
    (4), sorted.  Cheap: one JSON read, no network, no raster.

    THE ONE PREDICATE for that question, exactly as
    :func:`unverified_capability_negatives` is for 13b's door: the
    engine's fetch loop asks it per provider
    (:func:`negative_is_version_stale`), ``is_cached`` asks it to refuse
    to call such a tile settled, and the harness asks it to REFUSE a
    build up front -- the re-probe fetches into the shared data repo, and
    a build never writes it as a side effect.
    """
    if provider_definitions is None:
        provider_definitions = select_provider_definitions(
            "auto", role=ROLE_AIRPORT_INSET
        )
    free = [
        definition
        for definition in provider_definitions
        if not provider_required_capabilities(definition)
    ]
    if not free:
        return []
    out = []
    for (icao, airport_record) in sorted(_read_index(lat, lon).items()):
        for definition in free:
            code = definition["code"]
            if negative_is_version_stale(airport_record, code, definition):
                out.append(
                    (icao, code,
                     recorded_engine_version(airport_record, code))
                )
    return out


def is_cached(tile) -> bool:
    """True when this tile's airport-inset pass would fetch nothing.

    One of the per-subsystem fetch-admission predicates of
    docs/specs/apron-string-and-scheduling-spec.md §A.2.  Cheap (one
    JSON read plus a ``stat`` per recorded inset), never a network
    probe, and conservative in every unknown.  A tile with insets
    DISABLED is trivially cached — the pass returns before touching the
    network.
    """
    try:
        if not insets_enabled_for_tile(tile):
            return True
        with open(inset_completion_stamp_path(tile.lat, tile.lon),
                  "r") as handle:
            stamp = json.load(handle)
        if not isinstance(stamp, dict):
            return False
        wanted = _inset_completion_key(tile)
        if wanted["airports_layer"] is None:
            return False
        if not _stamp_key_validates(stamp, wanted):
            return False
        directory = FNAMES.airport_inset_directory(tile.lat, tile.lon)
        for name in stamp.get("insets") or ():
            if _file_size_or_zero(os.path.join(directory, name)) <= 0:
                return False
        tile_definitions = select_provider_definitions(
            getattr(tile, "airport_elevation_providers", "auto"),
            role=ROLE_AIRPORT_INSET,
        )
        if version_stale_capability_free_negatives(
            tile.lat, tile.lon, tile_definitions
        ):
            # ONCE PER ENGINE VERSION (owner RULINGS 2026-09-15aq (4)):
            # a capability-free provider's negative -- the 20 the TNM
            # outage wrote on the Phoenix tiles -- is re-asked by each
            # new engine, so a stamp from another version does not mean
            # "nothing left to fetch".
            return False
        if unverified_capability_negatives(
            tile.lat, tile.lon, tile_definitions,
        ):
            # The stamp says "nothing left to fetch", and it was written
            # by the engine that could not ASK (owner RULINGS
            # 2026-09-13b): NZQN's cache is marked complete around a
            # negative that a decoder-less run minted.  A tile carrying
            # one is not settled -- the pass must run and re-probe.
            return False
        return True
    except Exception:
        return False


def assemble_inset_composite_source(tile, base_source):
    """Return ``base_source`` augmented in-memory with cached inset paths.

    The user's ``custom_dem`` config value is never rewritten.  Inset paths
    are APPENDED after the base (and after any user sub-DEMs) so, under the
    composite's last-token-wins priority (``O4_DEM_Utils`` ``alt_composite``
    / ``alt_vec_composite``), the high-resolution insets win at query time,
    while the first token stays the base source so step 2's
    ``split(';')[0]`` still yields the correct raster dimensions.

    (The spec's illustrative ``inset;...;custom_dem`` ordering is written
    highest-priority-first; the concrete code is last-wins, so we append.)

    Deterministic and disk-state-driven: step 1 and step 2 both call this and
    get the identical composite string.
    """
    if not insets_enabled_for_tile(tile):
        return base_source
    provider_definitions = select_provider_definitions(
        getattr(tile, "airport_elevation_providers", "auto")
    )
    codes = [definition["code"] for definition in provider_definitions]
    inset_paths = list_cached_inset_dems(
        tile.lat, tile.lon, provider_codes=codes or None
    )
    if not inset_paths:
        return base_source
    return ";".join([base_source] + inset_paths)


# Feather-ring offset sanity thresholds.  A few metres of median offset
# between an inset and the base DEM is the NORMAL surface-vs-bare-earth
# gap (the coarse base reads canopy, hedgerows and buildings; lidar reads
# ground) and warrants no action, so a single inset only warns at the
# magnitude a genuine datum/height-system mistake produces (the SWEDEN1M
# compound-CRS shift measured +23..36 m).  The OTHER actionable signature
# is systematic: many insets from ONE provider offset in the same
# direction, which vegetation cannot explain -- that fires at a lower
# per-inset magnitude but only across several airports agreeing in sign.
INSET_DATUM_WARNING_THRESHOLD_M = 10.0
SYSTEMATIC_OFFSET_MINIMUM_INSETS = 3
SYSTEMATIC_OFFSET_THRESHOLD_M = 3.0
SYSTEMATIC_OFFSET_SIGN_FRACTION = 0.8


def _warn_if_provider_offsets_systematic(provider_ring_offsets):
    """One warning per provider whose insets share a consistent DEM offset.

    ``provider_ring_offsets`` maps a provider code (the cache-file suffix)
    to the median feather-ring offsets of its baked insets.  A provider
    with at least SYSTEMATIC_OFFSET_MINIMUM_INSETS measured insets whose
    overall median exceeds SYSTEMATIC_OFFSET_THRESHOLD_M and whose
    per-inset offsets agree in sign (SYSTEMATIC_OFFSET_SIGN_FRACTION)
    looks datum-shifted, not vegetated, and is worth reporting.
    """
    for (provider_code, offsets) in sorted(provider_ring_offsets.items()):
        if len(offsets) < SYSTEMATIC_OFFSET_MINIMUM_INSETS:
            continue
        median_offset = float(numpy.median(offsets))
        if abs(median_offset) <= SYSTEMATIC_OFFSET_THRESHOLD_M:
            continue
        agreeing = sum(
            1
            for offset in offsets
            if (offset > 0) == (median_offset > 0)
        )
        if agreeing / len(offsets) < SYSTEMATIC_OFFSET_SIGN_FRACTION:
            continue
        UI.vprint(
            1,
            "   WARNING:",
            len(offsets),
            "airport insets from",
            provider_code,
            "differ from the base DEM in the same direction (median",
            str(round(median_offset, 2)) + " m)",
            "- a provider-wide vertical-datum problem is likely.",
        )


# =====================================================================
# Bake RESAMPLING (O1) -- how an inset's posting reaches the working grid
# =====================================================================
# The bake stamps an inset raster onto the tile's working grid.  Until
# now it did so with ``DEM.alt_vec_strict`` -- NEAREST NEIGHBOUR -- which
# is wrong in both directions:
#
# * INSET COARSER THAN THE GRID (a 30 m Copernicus inset on a 1/3
#   arc-second, ~10.3 m grid): nearest neighbour writes each inset post
#   into a 3x3 block of working cells, i.e. a literal 30 m STAIRCASE, into
#   the very ``.alt`` file Triangle4XP reads with TRUE BILINEAR
#   interpolation (``Utils/src/Triangle4XP.c:3571`` ``altitude()``).  The
#   mesher then spends its error budget refining the staircase risers --
#   measured at +30+031 (Cairo): 2,482,100 triangles / ~870 s against
#   383,390 / 2.6 s for the identical content baked bilinearly.  Zero
#   fidelity is gained (the risers are a resampling artefact, not data)
#   and X-Plane renders the staircase.  BILINEAR is the right reader:
#   every inset post is still reproduced EXACTLY (bilinear at a post
#   returns that post), only the cells between posts stop stepping.
#
# * INSET FINER THAN THE GRID (1 m / 3 m lidar on a 1/2 arc-second,
#   ~15.4 m grid): nearest neighbour is point SUBSAMPLING of a signal
#   with detail far above the grid's Nyquist limit -- textbook aliasing,
#   which folds real high-frequency relief down into false long-wavelength
#   ripples ("mirror images") that look like terrain but are not.  The
#   fix is to LOW-PASS before sampling: AREA-AVERAGE every inset post
#   whose centre falls inside the destination cell (a box filter), which
#   is also the physically honest answer -- a working-grid post stands for
#   its cell, and the cell's mean elevation is what the coarser mesh can
#   represent.
#
# Choice is per inset and purely geometric (the ratio of postings in
# DEGREES, so it is latitude-free and identical on both axes for the
# square-in-degrees rasters both sides actually use).  Area-averaging is
# taken only when the inset is finer on BOTH axes: a mixed case would
# leave the coarse axis stepping while the fine axis smoothed.
#
# GATE ``O4_INSET_BAKE_INTERP`` (default "1" = ON).  Set to "0" to restore
# the historic nearest-neighbour bake BYTE-IDENTICALLY.
INSET_BAKE_FINER_RATIO = 0.999


def inset_bake_interpolation_enabled():
    """True when the bake may interpolate/area-average (gate default ON).

    ``O4_INSET_BAKE_INTERP=0`` restores the historic nearest-neighbour
    stamp byte-for-byte.
    """
    return os.environ.get("O4_INSET_BAKE_INTERP", "1") == "1"


def inset_bake_resample_mode(inset, x_step, y_step):
    """The resampling mode for one inset onto a working grid.

    ``x_step``/``y_step`` are the WORKING grid's node spacing in degrees.
    Returns ``"nearest"`` (gate off, or geometry unusable), ``"area"``
    (inset finer than the grid on both axes -> box filter) or
    ``"bilinear"`` (everything else).
    """
    if not inset_bake_interpolation_enabled():
        return "nearest"
    if inset is None or getattr(inset, "alt_dem", None) is None:
        return "nearest"
    if inset.nxdem < 2 or inset.nydem < 2:
        return "nearest"
    if not x_step or not y_step:
        return "nearest"
    inset_x_step = abs(inset.x1 - inset.x0) / (inset.nxdem - 1)
    inset_y_step = abs(inset.y1 - inset.y0) / (inset.nydem - 1)
    finer_x = inset_x_step < abs(x_step) * INSET_BAKE_FINER_RATIO
    finer_y = inset_y_step < abs(y_step) * INSET_BAKE_FINER_RATIO
    return "area" if (finer_x and finer_y) else "bilinear"


def _inset_area_average_onto_grid(
    inset, x_coordinates, y_coordinates, x_step, y_step, fallback
):
    """Box-filter a FINER inset onto the working grid's cells.

    Every working-grid node owns the cell ``+/- half a step`` around it;
    its baked value is the mean of the inset posts whose centres fall in
    that cell.  Implemented as a separable two-pass slab reduction (see the
    comment at the loops), so the cost is one pass over the inset window
    regardless of how many destination nodes it feeds -- a per-node loop
    over a 1 m lidar inset would be minutes -- and the peak extra memory is
    one (inset rows x destination columns) array, not a second copy of the
    inset.

    Nodes whose cell contains no valid inset post (a nodata hole, or a
    destination cell narrower than one inset post after clamping) take the
    corresponding entry of ``fallback`` -- the bilinear value, computed by
    the caller -- so coverage is never smaller than the interpolating path.
    Nodes outside the inset extent keep ``inset.nodata`` via ``fallback``.
    """
    inset_x_step = (inset.x1 - inset.x0) / (inset.nxdem - 1)
    inset_y_step = (inset.y1 - inset.y0) / (inset.nydem - 1)
    half_x = abs(x_step) / 2.0
    half_y = abs(y_step) / 2.0

    # Inset column indices whose post centre lies in [x-half, x+half].
    column_low = numpy.ceil(
        (x_coordinates - half_x - inset.x0) / inset_x_step - 1e-9
    ).astype(numpy.int64)
    column_high = numpy.floor(
        (x_coordinates + half_x - inset.x0) / inset_x_step + 1e-9
    ).astype(numpy.int64)
    # Row 0 is the NORTHERN edge of the inset, so a node's north edge maps
    # to the low row index.
    row_low = numpy.ceil(
        (inset.y1 - (y_coordinates + half_y)) / inset_y_step - 1e-9
    ).astype(numpy.int64)
    row_high = numpy.floor(
        (inset.y1 - (y_coordinates - half_y)) / inset_y_step + 1e-9
    ).astype(numpy.int64)
    column_low = numpy.clip(column_low, 0, inset.nxdem - 1)
    column_high = numpy.clip(column_high, 0, inset.nxdem - 1)
    row_low = numpy.clip(row_low, 0, inset.nydem - 1)
    row_high = numpy.clip(row_high, 0, inset.nydem - 1)

    # SEPARABLE two-pass reduction.  Pass 1 collapses the inset's columns
    # onto the destination columns, pass 2 collapses the (already narrow)
    # result's rows onto the destination rows.  The only full-width
    # intermediate is (inset rows x destination columns), so a metre-class
    # inset never materialises a second full-resolution float64 copy of
    # itself -- the summed-area-table formulation would have needed two,
    # gigabytes for a big lidar airport.  The Python loop runs once per
    # destination column/row (hundreds), each iteration a vectorised slab
    # sum, so the total work is still one pass over the inset.
    array = inset.alt_dem
    column_totals = numpy.zeros(
        (inset.nydem, len(column_low)), dtype=numpy.float64
    )
    column_counts = numpy.zeros_like(column_totals)
    for index in range(len(column_low)):
        slab = array[:, column_low[index]:column_high[index] + 1]
        if slab.size == 0:
            continue
        slab_valid = slab != inset.nodata
        column_totals[:, index] = numpy.where(slab_valid, slab, 0.0).sum(
            axis=1, dtype=numpy.float64
        )
        column_counts[:, index] = slab_valid.sum(axis=1)
    totals = numpy.zeros((len(row_low), len(column_low)), dtype=numpy.float64)
    counts = numpy.zeros_like(totals)
    for index in range(len(row_low)):
        rows_slice = slice(row_low[index], row_high[index] + 1)
        totals[index] = column_totals[rows_slice].sum(axis=0)
        counts[index] = column_counts[rows_slice].sum(axis=0)
    averaged = totals / numpy.where(counts > 0, counts, 1.0)
    # The clamped index window is never empty even for a node well outside
    # the raster, so the EXTENT decides nodata (exactly as
    # ``alt_vec_strict``/``alt_vec_bilinear_strict`` do), not the box.
    inside = (
        (x_coordinates >= inset.x0) & (x_coordinates <= inset.x1)
    )[None, :] & (
        (y_coordinates >= inset.y0) & (y_coordinates <= inset.y1)
    )[:, None]
    return numpy.where(
        inside, numpy.where(counts > 0, averaged, fallback), inset.nodata
    )


def sample_inset_onto_working_grid(
    inset, query, shape, x_coordinates, y_coordinates, x_step, y_step
):
    """The inset's values at the working-grid nodes of the bake window.

    Dispatches on :func:`inset_bake_resample_mode`; returns an array shaped
    like the destination window.  Every mode keeps ``inset.nodata`` outside
    the inset extent, so the caller's ``valid`` mask and feather logic are
    unchanged.
    """
    mode = inset_bake_resample_mode(inset, x_step, y_step)
    if mode == "nearest":
        return inset.alt_vec_strict(query).reshape(shape)
    bilinear = inset.alt_vec_bilinear_strict(query).reshape(shape)
    if mode == "bilinear":
        return bilinear
    return _inset_area_average_onto_grid(
        inset, x_coordinates, y_coordinates, x_step, y_step, bilinear
    )


# =====================================================================
# R11-3 -- AN EMPTY INSET IS NO INSET
# (docs/specs/round11-kmci-flat-claim-spec.md)
# =====================================================================
# A fetched raster can be structurally perfect and hold no data at all:
# ``KMCI_usgs3dep.tif`` is 7993 x 10518 pixels of 1 m lidar, 100.00 %
# nodata, cut from the Kansas project KS_Statewide_2018_A18 for a
# Missouri airport.  Every coverage answer in this module was judged by
# raster EXTENTS -- rectangles -- so that file reported 100 % coverage at
# 1 m and set the airport's smoothing radius as if it carried metre-class
# detail, while the bake laid down nothing.  An inset with fewer than
# ``INSET_MIN_VALID_FRAC`` valid pixels is treated as ABSENT: it is not
# baked, it contributes no coverage, it is recorded with its measured
# nodata fraction, and the build proceeds on the base DEM.
#
# ONE INSTRUMENT.  The bake and the coverage metric both read the
# fraction from :func:`inset_valid_fraction` -- two counts of one
# population is how this repo gets two instruments that disagree.
INSET_MIN_VALID_FRAC = _parse_float(
    os.environ.get("O4_INSET_MIN_VALID_FRAC"), 0.05
)

#: THE AIRPORT-COVERAGE RULE (spec las-tile-lidar-provider §4, owner
#: 30ay): a SURGICAL core (a LAS rung cut to the aerodrome footprint) is
#: delivered only when it holds data over at least this share of the
#: aerodrome BOUNDARY box -- the box-wide fraction above cannot judge a
#: raster that is NoData outside the airport by design.
INSET_MIN_AIRPORT_COVER_FRAC = 0.80


def _inset_source_project(inset_path):
    """The project titles the fetch recorded beside an inset, as one
    string -- what a reader needs to see WHY a raster is empty (KMCI's
    names a Kansas project for a Missouri airport).  ``"?"`` when the
    sidecar is missing or carries no titles."""
    sidecar = inset_path[:-4] + ".json" if inset_path.endswith(".tif") else None
    if not sidecar or not os.path.isfile(sidecar):
        return "?"
    try:
        with open(sidecar, "r") as handle:
            meta = json.load(handle)
    except Exception:                                    # pragma: no cover
        return "?"
    titles = meta.get("project_titles") or meta.get("source_ids") or []
    return "; ".join(str(title) for title in titles) or "?"


def inset_is_effectively_empty(inset_path):
    """``(is_empty, valid_fraction)`` for one cached inset (R11-3)."""
    fraction = inset_valid_fraction(inset_path)
    return (fraction < INSET_MIN_VALID_FRAC, fraction)


def bake_candidate_inset_paths(tile):
    """The cached inset rasters the bake step considers for ``tile``, in
    bake order: every cached ``*.tif`` of a provider the tile's
    ``airport_elevation_providers`` selects.  ONE listing for the bake
    (:func:`bake_airport_insets_into_alt_dem`) and for every later reader
    of "which insets does this tile's raster carry" that runs without the
    step-1 DEM object — the mesh's curvature weight map (#233) derives
    its inset boxes from it in step 2, where ``tile.dem`` is header-only.
    Empty when the feature is gated off."""
    if not insets_enabled_for_tile(tile):
        return []
    provider_definitions = select_provider_definitions(
        getattr(tile, "airport_elevation_providers", "auto")
    )
    codes = [definition["code"] for definition in provider_definitions]
    return list_cached_inset_dems(
        tile.lat, tile.lon, provider_codes=codes or None
    )


def baked_inset_boxes(tile):
    """``[(box, resolution_m, path)]`` for every inset the bake step puts
    into ``tile``'s raster: the box the raster DELIVERS
    (:func:`delivered_inset_bounding_box`, ``(west, south, east, north)``
    in EPSG:4326) and the resolution its data HONESTLY carries
    (:func:`_honest_inset_resolution_m`).  Disk-state driven, like the
    bake itself: an effectively-empty inset (refused by the bake) and one
    whose header cannot be read are left out."""
    boxes = []
    for inset_path in bake_candidate_inset_paths(tile):
        try:
            (is_empty, _valid_fraction) = inset_is_effectively_empty(
                inset_path)
            if is_empty:
                continue
            box = delivered_inset_bounding_box(inset_path)
            resolution_m = _honest_inset_resolution_m(inset_path)
        except Exception:
            continue
        if box is None or not resolution_m or resolution_m <= 0:
            continue
        boxes.append((box, float(resolution_m), inset_path))
    return boxes


def bake_airport_insets_into_alt_dem(tile):
    """Bake cached insets into ``tile.dem.alt_dem`` with a feather band.

    See the module docstring's G2 note: this is the step that puts inset
    values into the ``.alt`` raster the mesher reads (the composite alone
    only feeds the query path).  Runs in step 1 immediately before
    ``write_to_file``.  A no-op -- byte-identical output -- when the feature
    is gated off, no inset covers the tile, or GDAL is missing.

    FLAT-SITE mode is NOT wired here: it is a DEM-ASSEMBLY step, not a
    bake step, and it must run on every build whether or not this
    feature has anything to bake.  Its call site is
    ``O4_Airport_Utils.smooth_raster_over_airports``, immediately after
    this one and before the ``.alt`` write.
    """
    if not insets_enabled_for_tile(tile):
        return
    if tile.dem is None or tile.dem.alt_dem is None:
        return
    inset_paths = bake_candidate_inset_paths(tile)
    # Record which insets actually bake into this DEM so the auto_patch
    # provenance stamp can report the true elevation source per airport (see
    # auto_patch.provenance).  An EMPTY list means the bake step ran but found
    # no cached inset -- the silent-raw-DEM case the provenance exists to make
    # loud.  Absence of the attribute (never set) means the bake never ran.
    baked_provenance = []
    tile.dem.airport_inset_provenance = baked_provenance
    # R11-3: insets that hold no data.  Kept OFF ``baked_provenance`` --
    # nothing of theirs reached the raster, so ``raw`` must stay true --
    # and recorded on their own attribute, which
    # ``auto_patch.provenance.dem_provenance_from_dem`` reports beside
    # the baked insets as ``nodata_refused``.
    nodata_refused = []
    tile.dem.airport_inset_nodata_refusals = nodata_refused
    if not inset_paths:
        return
    feather_m = getattr(tile, "airport_elevation_inset_feather_m", 60.0)
    provider_ring_offsets = {}
    for inset_path in inset_paths:
        (is_empty, valid_fraction) = inset_is_effectively_empty(inset_path)
        if is_empty:
            entry = _inset_bake_provenance_entry(inset_path)
            entry["nodata_fraction"] = round(1.0 - valid_fraction, 6)
            entry["fallback"] = "base DEM (inset treated as absent)"
            nodata_refused.append(entry)
            UI.vprint(
                0,
                "   [inset] %s holds %.2f %% valid pixels (< %.2f %%) - NO "
                "INSET: it is not baked and carries no coverage; the build "
                "proceeds on the base DEM. Source project(s): %s."
                % (os.path.basename(inset_path), 100.0 * valid_fraction,
                   100.0 * INSET_MIN_VALID_FRAC,
                   _inset_source_project(inset_path)),
            )
            continue
        try:
            ring_offset_m = _bake_one_inset(tile, inset_path, feather_m)
        except Exception as error:
            UI.vprint(
                1,
                "   WARNING: could not bake inset",
                os.path.basename(inset_path),
                ":",
                str(error),
            )
            continue
        if ring_offset_m is not None:
            stem = os.path.basename(inset_path)
            stem = stem[:-4] if stem.endswith(".tif") else stem
            provider_code = stem.rsplit("_", 1)[-1]
            provider_ring_offsets.setdefault(provider_code, []).append(
                ring_offset_m
            )
        entry = _inset_bake_provenance_entry(inset_path)
        entry["nodata_fraction"] = round(1.0 - valid_fraction, 6)
        baked_provenance.append(entry)
    _warn_if_provider_offsets_systematic(provider_ring_offsets)
    # The raster is now the surface the mesher will render, so the QUERY
    # path must read it too: the grading law measures the surface the
    # mesher renders -- one surface, two readers.  Before this, an inset
    # query returned ``subdem.alt_strict`` = nearest neighbour on the
    # inset's native 30 m posting, up to ~0.9 m off the bilinear ramp the
    # mesh draws from these very cells, and every auto_patch "pin to DEM"
    # pinned to a surface X-Plane never shows.  Refused (byte-identical)
    # when the ``O4_DEM_QUERY_BAKED`` gate is off or a sub-DEM did not
    # bake -- see ``O4_DEM_Utils.DEM.enable_baked_query``.
    enable_baked_query = getattr(tile.dem, "enable_baked_query", None)
    if enable_baked_query is not None:
        enable_baked_query([entry["path"] for entry in baked_provenance])


def _inset_bake_provenance_entry(inset_path):
    """One baked-inset provenance record for the DEM stamp.

    Reads the provenance sidecar (``<icao>_<code>.json``) the fetch wrote —
    provider, source_ids, fetch_date — and derives the airport ICAO from the
    cache file name so ``auto_patch`` can attribute the inset to its airport.
    Always returns a dict; missing/unreadable sidecars degrade to just the
    parsed name fields.
    """
    basename = os.path.basename(inset_path)
    stem = basename[:-4] if basename.endswith(".tif") else basename
    icao = stem.rsplit("_", 1)[0] if "_" in stem else stem
    entry = {"icao": icao, "path": inset_path}
    sidecar = inset_path[:-4] + ".json" if inset_path.endswith(".tif") else None
    if sidecar and os.path.isfile(sidecar):
        try:
            with open(sidecar, "r") as handle:
                meta = json.load(handle)
            entry["provider"] = meta.get("provider")
            entry["source_ids"] = meta.get("source_ids") or []
            entry["fetch_date"] = meta.get("fetch_date")
            # §45 (18) (owner RULINGS 2026-09-15bo): BOTH keys are
            # stamped, each falling back to the other.  The fetchers
            # write ``resolution_m`` (see the USGS3DEP sidecar); stamping
            # only ``native_resolution_m`` minted the 2026-08-15 N32W098
            # manifests that read ``null`` over a composed 1 m lidar
            # frame, so every reader of the manifest called KDFW coarse.
            native = meta.get("native_resolution_m")
            stated = meta.get("resolution_m")
            entry["native_resolution_m"] = (
                native if native is not None else stated)
            entry["resolution_m"] = (
                stated if stated is not None else native)
        except Exception:
            pass
    return entry


def _bake_one_inset(tile, inset_path, feather_m, inset=None,
                    refuse_datum_offset_over_m=None):
    """Blend a single inset GeoTIFF into the working grid over its footprint.

    The blend weight ramps linearly from 0 at the inset's data edge to 1 at
    ``feather_m`` inside it, so the seam is a ramp not a cliff.  Cells with
    inset nodata keep the base value.

    Returns the median inset-vs-base offset (metres) measured over the
    feather ring, or ``None`` when nothing was measured -- the caller
    aggregates these per provider for the systematic-offset warning.

    ``inset`` may be an ALREADY-LOADED inset raster, in which case
    ``inset_path`` is only a label and no file is opened.  That is how
    FLAT-SITE mode's synthetic constant inset (:class:`_ConstantInset`)
    rides this exact blend: one feathering implementation in the tree,
    the fetched-GeoTIFF path byte-identical when ``inset`` is omitted.

    ``refuse_datum_offset_over_m`` (R11-2) turns the ring measurement
    into a GATE: when the measured median exceeds it, the blend is
    ABANDONED -- the working grid is not written and the offset is
    returned for the caller to report and count.  The measurement is the
    same one the warning has always printed, taken at the same point;
    only what happens next changes, and only for the callers that ask.
    """
    base_dem = tile.dem
    label = os.path.basename(inset_path) if inset_path else (
        getattr(inset, "label", None) or "synthetic inset")
    if inset is None:
        # The composite load already decoded every cached inset into
        # ``base_dem.subdems`` (same file, same ``fill_nodata=False``
        # constructor) for the query-time composite: reuse that array
        # instead of decoding the GeoTIFF a second time.  Fresh read only
        # when the bake runs on a DEM without a matching subdem (tests,
        # partial loads).
        for subdem in getattr(base_dem, "subdems", ()) or ():
            if (
                getattr(subdem, "source_path", None) == inset_path
                and getattr(subdem, "alt_dem", None) is not None
            ):
                inset = subdem
                break
    if inset is None:
        inset = DEM.DEM(
            tile.lat, tile.lon, inset_path, fill_nodata=False, info_only=False
        )
    if inset.alt_dem is None:
        return

    number_of_columns = base_dem.nxdem
    number_of_rows = base_dem.nydem
    x0 = base_dem.x0
    x1 = base_dem.x1
    y0 = base_dem.y0
    y1 = base_dem.y1
    # Cell-centre coordinates (tile-relative degrees), matching the sampling
    # convention in O4_DEM_Utils.DEM.alt_nostrict.
    x_step = (x1 - x0) / (number_of_columns - 1)
    y_step = (y1 - y0) / (number_of_rows - 1)

    # Working-grid column/row window that overlaps the inset extent.
    column_min = max(int(numpy.floor((inset.x0 - x0) / x_step)), 0)
    column_max = min(
        int(numpy.ceil((inset.x1 - x0) / x_step)), number_of_columns - 1
    )
    # Row 0 is the northern edge (y == y1): row grows as y decreases.
    row_min = max(int(numpy.floor((y1 - inset.y1) / y_step)), 0)
    row_max = min(int(numpy.ceil((y1 - inset.y0) / y_step)), number_of_rows - 1)
    if column_min > column_max or row_min > row_max:
        return

    columns = numpy.arange(column_min, column_max + 1)
    rows = numpy.arange(row_min, row_max + 1)
    x_coordinates = x0 + columns * x_step
    y_coordinates = y1 - rows * y_step
    mesh_x, mesh_y = numpy.meshgrid(x_coordinates, y_coordinates)
    query = numpy.column_stack(
        (mesh_x.ravel(), mesh_y.ravel())
    )

    # RESAMPLING (O1): bilinear when the inset is coarser than the working
    # grid (no fabricated staircase for the mesher to refine), area-average
    # when it is finer (no aliasing).  Nearest neighbour -- the historic,
    # byte-identical path -- only under ``O4_INSET_BAKE_INTERP=0``.  See the
    # module comment above ``inset_bake_resample_mode``.
    inset_values = sample_inset_onto_working_grid(
        inset,
        query,
        mesh_x.shape,
        x_coordinates,
        y_coordinates,
        x_step,
        y_step,
    )
    valid = inset_values != inset.nodata

    # Distance in metres to the nearest inset-extent edge (rectangular data
    # region), converted from the per-axis degree distances.
    centre_latitude = tile.lat + (y0 + y1) / 2.0
    metres_per_degree_longitude = GEO.lon_to_m(centre_latitude)
    metres_per_degree_latitude = GEO.lat_to_m
    distance_west = (mesh_x - inset.x0) * metres_per_degree_longitude
    distance_east = (inset.x1 - mesh_x) * metres_per_degree_longitude
    distance_south = (mesh_y - inset.y0) * metres_per_degree_latitude
    distance_north = (inset.y1 - mesh_y) * metres_per_degree_latitude
    distance_to_edge = numpy.minimum(
        numpy.minimum(distance_west, distance_east),
        numpy.minimum(distance_south, distance_north),
    )
    weight = feather_weight(distance_to_edge, feather_m)
    weight = numpy.where(valid, weight, 0.0)

    window = base_dem.alt_dem[
        row_min : row_max + 1, column_min : column_max + 1
    ]
    base_nodata = window == base_dem.nodata
    # Datum sanity: median base-vs-inset offset across the feather ring
    # (base nodata cells carry the sentinel, not terrain -- exclude them).
    ring = (weight > 0) & (weight < 1) & valid & ~base_nodata
    ring_offset_m = None
    if numpy.any(ring):
        ring_offset_m = float(
            numpy.median(inset_values[ring] - window[ring])
        )
        # R11-2: for a caller that asked, the ring is a GATE and this is
        # the last point before the write -- refuse here and the working
        # grid keeps the surface it already had.
        if (refuse_datum_offset_over_m is not None
                and abs(ring_offset_m) > float(refuse_datum_offset_over_m)):
            return ring_offset_m
        # A few metres is the normal surface-vs-bare-earth gap (canopy in
        # the coarse base); only datum-class magnitudes warrant a warning.
        if abs(ring_offset_m) > INSET_DATUM_WARNING_THRESHOLD_M:
            UI.vprint(
                1,
                "   WARNING: elevation inset",
                label,
                "differs from the base DEM by a median",
                round(ring_offset_m, 2),
                "m over the feather ring (>%d m; check vertical datum)."
                % int(INSET_DATUM_WARNING_THRESHOLD_M),
            )
    blended = weight * inset_values + (1.0 - weight) * window
    # Where the base holds its nodata sentinel (possible on the step-2
    # iterative-refinement path, which loads with fill_nodata=False),
    # blending against the sentinel would fabricate huge negative ramps:
    # take the inset outright where it has data, keep the sentinel where
    # neither has data.
    if numpy.any(base_nodata):
        blended = numpy.where(
            base_nodata,
            numpy.where(valid, inset_values, window),
            blended,
        )
    base_dem.alt_dem[
        row_min : row_max + 1, column_min : column_max + 1
    ] = blended.astype(base_dem.alt_dem.dtype)
    return ring_offset_m


# =====================================================================
# FLAT-SITE mode -- the synthetic constant inset
# (docs/specs/flat-site-mode-spec.md, 2026-08-09 FROZEN)
# =====================================================================
# A DEM SOURCE SUBSTITUTION, not a new solve path.  For an airport the
# detector calls ``flat_candidate``, the instrument truth for the site is
# the CIFP threshold consensus Z0 and the DEM's metres of "relief" are
# its own source's noise.  So DEM prep manufactures a CONSTANT raster at
# Z0 over the detector's extent and blends it in through ``_bake_one_inset``
# -- the same feather a Copernicus or LIDAR inset gets.  Downstream is
# blind to it: apt_smoothing is a no-op on a constant, the runway profile
# stays CIFP-absolute, drainage and basins cut below Z0 as always.
#
# THE SURFACE IS NEVER CACHED (spec section 3.3).  It is arithmetic, not
# data: an in-memory raster for the length of one build.  A synthetic
# GeoTIFF in ``Elevation_data`` would poison the real-DEM path and the
# refresh ledger's meaning, so nothing here writes a file -- the value
# reaches the mesher only through ``tile.dem.alt_dem`` and the tile's own
# ``.alt`` build product.


def _feather_outward_extent(tile, x0, y0, x1, y1, feather_m):
    """R17c-2 -- THE FEATHER STOPS AT THE WALL.

    ``_bake_one_inset`` ramps its blend weight from 0 at the inset's own
    data edge to 1 ``feather_m`` INSIDE it.  For a fetched GeoTIFF that is
    right: the ramp lives over ground the inset also covers.  For the
    FLAT-SITE synthetic constant inset it eats the last ``feather_m`` of
    the site itself -- and at a reclaimed island the site's edge IS the
    shoreline, so the ramp is the beach the owner ruled is a vertical sea
    wall (measured VHHH 2026-08-11: the north-shore transect falls 7.315
    -> 0 over 33-44 m, four mesh samples, with the wall breakline already
    admitted beside it).

    THE LAW (round-17 amendment 2, R17c-2): the constant inset extends AT
    Z0 to the wall line and the feather happens SEAWARD of it.  The
    mechanism is one line of geometry -- the synthetic raster is built
    ``feather_m`` LARGER than the declared extent, so weight reaches 1
    exactly ON the declared boundary and the whole ramp lies outside it.
    Nothing in the bake changes; the declared extent is what every
    consumer still reads, because the PROVENANCE stamp keeps it (the
    wall's admission geometry must stay the island, never the grown box).

    Returns the grown ``(x0, y0, x1, y1)`` in tile-relative degrees.
    """
    if not feather_m or feather_m <= 0:
        return (x0, y0, x1, y1)
    centre_latitude = tile.lat + (float(y0) + float(y1)) / 2.0
    d_lat = float(feather_m) / GEO.lat_to_m
    metres_per_degree_longitude = GEO.lon_to_m(centre_latitude)
    d_lon = (float(feather_m) / metres_per_degree_longitude
             if metres_per_degree_longitude else d_lat)
    return (float(x0) - d_lon, float(y0) - d_lat,
            float(x1) + d_lon, float(y1) + d_lat)


class _ConstantInset:
    """An in-memory inset raster holding one elevation everywhere.

    Carries exactly the surface ``_bake_one_inset`` reads from a fetched
    inset -- ``alt_dem`` / ``nxdem`` / ``nydem`` / ``x0``..``y1`` /
    ``nodata`` plus the two strict readers -- so the blend, the feather
    ring and the datum probe all run unmodified.  The readers are
    ``O4_DEM_Utils.DEM``'s own (bound to this object), never a second
    implementation: extent semantics, nodata handling and the bilinear
    weights are the raster path's, verbatim.

    Two posts on each axis is all a constant needs, and it keeps the bake
    on the vectorised bilinear branch (a 2x2 grid is coarser than any
    working grid, so ``inset_bake_resample_mode`` never picks the
    area-average path and never the per-node nearest one unless the
    interpolation gate is off).
    """

    def __init__(self, x0, y0, x1, y1, elevation_m, *, label=None,
                 nodata=-32768.0):
        self.x0 = float(x0)
        self.y0 = float(y0)
        self.x1 = float(x1)
        self.y1 = float(y1)
        self.elevation_m = float(elevation_m)
        self.nodata = float(nodata)
        self.nxdem = 2
        self.nydem = 2
        self.alt_dem = numpy.full((2, 2), self.elevation_m,
                                  dtype=numpy.float32)
        self.label = label or "synthetic flat-site inset"
        self.source_path = None

    def alt_vec_strict(self, way):
        return DEM.DEM.alt_vec_strict(self, way)

    def alt_vec_bilinear_strict(self, way):
        return DEM.DEM.alt_vec_bilinear_strict(self, way)


#: R21 — how many mask posts the isthmus raster puts inside one working
#: grid cell, per axis, and the hard cap on either axis.  Finer than the
#: working grid on both axes on purpose: the bake then AREA-AVERAGES it
#: (``inset_bake_resample_mode``), so a working node takes Z0 when its
#: own cell holds land and keeps the base DEM when it does not.  The cap
#: bounds the memory of a pathological extent (4096² float32 = 64 MB is
#: never reached; the isthmus at VHHH is 76 x 123 posts).
_ISTHMUS_MASK_SUBDIVISION = 4
_ISTHMUS_MASK_MAX_POSTS = 4096


class _MaskedConstantInset(_ConstantInset):
    """A constant-Z0 inset raster MASKED to a polygon (R21).

    ``_ConstantInset`` holds one elevation over a rectangle; the isthmus
    is not a rectangle.  It is LAND, measured from the tile's coastline,
    and the water beside it must keep the surface it has — so the raster
    carries Z0 on the posts inside the polygon and ``nodata`` outside it.
    Nothing in ``_bake_one_inset`` changes: nodata posts are exactly what
    it already means by "the base keeps its value", and the mask edge is
    a hard step at the shoreline, which is the vertical sea wall the
    owner ruled a reclaimed edge is (R17b-2) rather than a beach ramp.

    Rasterised with PIL — the tree's mask rasteriser (``O4_Mask_Utils``)
    — never with a per-cell Python containment loop.
    """

    def __init__(self, polygon, elevation_m, x_step, y_step, *, label=None,
                 nodata=-32768.0, base_reader=None, band_m=None, bounds=None):
        # ``bounds`` pins the RECTANGLE (2026-09-09o (2)): the flat-site
        # water cut hands in a polygon that may not reach its own
        # rectangle's corners, and the bake's feather is driven from the
        # data edge — a clipped corner must not move it.
        minx, miny, maxx, maxy = bounds if bounds is not None else polygon.bounds
        step_x = abs(float(x_step)) / _ISTHMUS_MASK_SUBDIVISION
        step_y = abs(float(y_step)) / _ISTHMUS_MASK_SUBDIVISION
        nx = int(numpy.ceil((maxx - minx) / step_x)) + 1 if step_x else 2
        ny = int(numpy.ceil((maxy - miny) / step_y)) + 1 if step_y else 2
        nx = int(min(max(nx, 2), _ISTHMUS_MASK_MAX_POSTS))
        ny = int(min(max(ny, 2), _ISTHMUS_MASK_MAX_POSTS))
        super().__init__(minx, miny, maxx, maxy, elevation_m,
                         label=label or "synthetic flat-site isthmus inset",
                         nodata=nodata)
        self.nxdem = nx
        self.nydem = ny
        self.alt_dem = numpy.full((ny, nx), self.nodata, dtype=numpy.float32)
        mask = self._rasterise(polygon, nx, ny)
        self.mask_land_posts = int(mask.sum())
        self.mask_band_dropped = 0
        if base_reader is not None and band_m:
            mask = self._within_band(mask, base_reader, float(band_m))
        self.alt_dem[mask] = numpy.float32(self.elevation_m)
        self.mask_valid_posts = int(mask.sum())

    def _within_band(self, mask, base_reader, band_m):
        """R21 datum band — grade only ground already NEAR Z0.

        MEASURED 2026-08-12 (+22+113, VMMC): "the land between the
        footprints" as geometry alone put 0.0536 km² of Taipa hillside
        standing at 60-72 m onto the airport's 6.10 m datum — a hill is
        not a causeway.  So the connecting land is graded only where the
        surface the build already has sits within ``band_m`` of Z0: the
        seam this law exists to close is between grounds that BELONG
        together, which is the same evidence question the R11-2 cluster
        datum gate asks (and the same threshold).  Ground outside the
        band keeps the real surface and is counted, never dropped
        silently.
        """
        rows, columns = numpy.nonzero(mask)
        if not len(rows):
            return mask
        span_x = (self.x1 - self.x0) or 1.0
        span_y = (self.y1 - self.y0) or 1.0
        xs = self.x0 + columns * (span_x / max(self.nxdem - 1, 1))
        ys = self.y1 - rows * (span_y / max(self.nydem - 1, 1))
        try:
            base = numpy.asarray(
                base_reader(numpy.column_stack((xs, ys))), dtype=float
            ).reshape(-1)
        except Exception:                                  # pragma: no cover
            return mask
        keep = numpy.abs(base - float(self.elevation_m)) <= band_m
        out = numpy.zeros_like(mask)
        out[rows[keep], columns[keep]] = True
        self.mask_band_dropped = int((~keep).sum())
        return out

    def _rasterise(self, polygon, nx, ny):
        """Boolean post mask, row 0 NORTH (the working grid's convention)."""
        from PIL import Image, ImageDraw

        image = Image.new("1", (nx, ny), 0)
        draw = ImageDraw.Draw(image)
        span_x = (self.x1 - self.x0) or 1.0
        span_y = (self.y1 - self.y0) or 1.0

        def to_pixels(coords):
            return [((x - self.x0) / span_x * (nx - 1),
                     (self.y1 - y) / span_y * (ny - 1)) for x, y in coords]

        for piece in getattr(polygon, "geoms", [polygon]):
            if piece is None or piece.is_empty:
                continue
            try:
                draw.polygon(to_pixels(piece.exterior.coords), fill=1)
                for hole in piece.interiors:
                    draw.polygon(to_pixels(hole.coords), fill=0)
            except Exception:                              # pragma: no cover
                continue
        return numpy.array(image, dtype=bool)


def _flat_site_inset(tile, extent_deg, z0_m, feather_m, label, water):
    """The synthetic flat-site raster for one rectangle — WATER CUT OUT.

    Owner RULINGS 2026-09-09m, mechanism 09o (2).  ``water`` is the
    tile's water geometry (``auto_patch.flat_site_mode.water_cutout``,
    tile-relative) or ``None``.  With no water over the rectangle this
    returns exactly the ``_ConstantInset`` the pre-change code built, so
    an inland airport (CYXY, HECA, LEMD) is untouched; with water it
    returns a ``_MaskedConstantInset`` over ``rectangle − water``,
    pinned to the SAME rectangle so the bake's feather does not move.

    Returns ``(inset, water_cut_frac)`` — the fraction of the rectangle
    the water removed (``0.0`` when none), for the provenance stamp.
    """
    rect = _feather_outward_extent(tile, *extent_deg, feather_m)
    if water is None or water.is_empty:
        return _ConstantInset(*rect, z0_m, label=label), 0.0
    from shapely import geometry as _geometry

    box = _geometry.box(*rect)
    try:
        if not water.intersects(box):
            return _ConstantInset(*rect, z0_m, label=label), 0.0
        land = box.difference(water)
    except Exception:                                      # pragma: no cover
        return _ConstantInset(*rect, z0_m, label=label), 0.0
    if land.is_empty:
        return None, 1.0
    frac = 0.0 if box.area <= 0 else float(1.0 - land.area / box.area)
    if frac < 1e-6:
        return _ConstantInset(*rect, z0_m, label=label), 0.0
    base_dem = tile.dem
    x_step = ((base_dem.x1 - base_dem.x0) / (base_dem.nxdem - 1)
              if base_dem.nxdem > 1 else 0.0)
    y_step = ((base_dem.y1 - base_dem.y0) / (base_dem.nydem - 1)
              if base_dem.nydem > 1 else 0.0)
    inset = _MaskedConstantInset(land, z0_m, x_step, y_step, label=label,
                                 bounds=rect)
    if not inset.mask_valid_posts:                         # pragma: no cover
        return None, 1.0
    return inset, round(frac, 4)


def _bake_island_continuity(tile, stamped, feather_m):
    """R21 — grade the CONNECTING LAND with the family it joins.

    Runs after every airport's core and admitted clusters are baked and
    stamped, because the family is what LANDED, not what was requested
    (a cluster the R11-2 datum gate refused is not connected to
    anything).  ``stamped`` is extended in place with one
    ``flat_site_isthmus`` entry per airport that has an isthmus.

    NO FEATHER.  The isthmus edge is either the family's own footprint,
    already at the same Z0, or the shoreline, where the ramp is the beach
    R17c-2 moved outside the site.  A feather here would ramp Z0 down
    across the isthmus itself.

    NO DATUM REFUSAL.  The R11-2 gate weighs whether a CLAIMED rectangle
    belongs to the airport; the isthmus is measured land BETWEEN two
    footprints that already passed their own gates.  What the ring would
    have told us is printed instead: the median metres the base DEM sits
    from Z0 over the ground this grades.
    """
    base_dem = getattr(tile, "dem", None)
    if base_dem is None or getattr(base_dem, "alt_dem", None) is None:
        return
    try:
        from auto_patch import flat_site_mode as FLAT_SITE_MODE

        regions = FLAT_SITE_MODE.island_continuity_regions(tile, stamped)
    except Exception as error:
        UI.vprint(
            0,
            "   ERROR: FLAT-SITE mode could not measure land-connected "
            "continuity (", type(error).__name__, ":", str(error),
            ") - the connecting ground stays on the real surface.",
        )
        return
    if not regions:
        return
    x_step = ((base_dem.x1 - base_dem.x0) / (base_dem.nxdem - 1)
              if base_dem.nxdem > 1 else 0.0)
    y_step = ((base_dem.y1 - base_dem.y0) / (base_dem.nydem - 1)
              if base_dem.nydem > 1 else 0.0)
    for region in regions:
        icao = region["icao"]
        polygon = region["polygon"]
        offset_m = _isthmus_base_offset_m(tile, polygon, region["z0_m"])
        try:
            inset = _MaskedConstantInset(
                polygon, region["z0_m"], x_step, y_step,
                label="%s synthetic flat-site isthmus inset" % icao,
                base_reader=base_dem.alt_vec,
                band_m=INSET_DATUM_WARNING_THRESHOLD_M)
            if not inset.mask_valid_posts:
                UI.vprint(
                    0,
                    "   [flat-site] %s: no isthmus — the connecting land "
                    "(%.4f km2) stands more than %d m from Z0 %.2f m "
                    "everywhere (a hill is not a causeway); it keeps the "
                    "real surface."
                    % (icao, region["area_km2"],
                       int(INSET_DATUM_WARNING_THRESHOLD_M), region["z0_m"]),
                )
                continue
            _bake_one_inset(tile, None, 0.0, inset=inset)
        except Exception as error:
            UI.vprint(
                0,
                "   ERROR: FLAT-SITE mode could not bake the ISTHMUS inset "
                "for", icao, "(", type(error).__name__, ":", str(error),
                ") - the connecting ground stays on the real surface.",
            )
            continue
        minx, miny, maxx, maxy = polygon.bounds
        stamped.append({
            "icao": icao,
            "kind": FLAT_SITE_MODE.ISTHMUS_INSET_KIND,
            "z0_m": region["z0_m"],
            "extent_tile_degrees": [minx, miny, maxx, maxy],
            "extent_wgs84": [tile.lon + minx, tile.lat + miny,
                             tile.lon + maxx, tile.lat + maxy],
            "extent_area_km2": region["area_km2"],
            "island_area_km2": region["island_area_km2"],
            "members": region["members"],
            "between_clip_cut": region["clipped"],
            "base_offset_m": offset_m,
            "datum_band_m": float(INSET_DATUM_WARNING_THRESHOLD_M),
            "band_kept_posts": int(inset.mask_valid_posts),
            "band_dropped_posts": int(inset.mask_band_dropped),
            "feather_m": 0.0,
        })
        UI.vprint(
            0,
            "   [flat-site] %s: ISTHMUS inset at Z0 %.2f m over %.4f km2 of "
            "LAND joining %d family footprint(s) on a %.2f km2 sea-bounded "
            "island (lat %.7f..%.7f lon %.7f..%.7f; base DEM sat %s m from "
            "Z0 there; %d of %d mask post(s) kept, %d outside the %d m "
            "datum band keep the real surface%s)."
            % (icao, region["z0_m"], region["area_km2"], region["members"],
               region["island_area_km2"],
               tile.lat + miny, tile.lat + maxy,
               tile.lon + minx, tile.lon + maxx,
               "%.2f" % offset_m if offset_m is not None else "?",
               inset.mask_valid_posts, inset.mask_land_posts,
               inset.mask_band_dropped,
               int(INSET_DATUM_WARNING_THRESHOLD_M),
               "; the between-clip cut a connecting piece"
               if region["clipped"] else ""),
        )


def _isthmus_base_offset_m(tile, polygon, z0_m):
    """Median metres the base DEM sits BELOW/above ``z0_m`` over ``polygon``.

    Attribution only — nothing refuses on it.  Sampled on a bounded grid
    inside the polygon; ``None`` when no sample lands on it.
    """
    try:
        minx, miny, maxx, maxy = polygon.bounds
        xs = numpy.linspace(minx, maxx, 40)
        ys = numpy.linspace(miny, maxy, 40)
        grid_x, grid_y = numpy.meshgrid(xs, ys)
        points = numpy.column_stack((grid_x.ravel(), grid_y.ravel()))
        from shapely import geometry
        from shapely.prepared import prep

        ready = prep(polygon)
        inside = numpy.array([ready.contains(geometry.Point(px, py))
                              for px, py in points], dtype=bool)
        if not inside.any():
            return None
        altitudes = numpy.asarray(tile.dem.alt_vec(points[inside]),
                                  dtype=float)
        return round(float(numpy.median(altitudes - float(z0_m))), 2)
    except Exception:                                      # pragma: no cover
        return None


def overlay_flat_site_insets(tile, dico_airports=None):
    """Blend a constant-Z0 inset over every flat airport on the tile.

    THE DEM-ASSEMBLY STEP (spec section 2.1), called by
    ``O4_Airport_Utils.smooth_raster_over_airports`` on EVERY build --
    warm cache or cold, insets or none, patch path or tile path -- after
    the airport smoothing and the cached-inset bake have produced the
    honest surface the detector must classify, and BEFORE the ``.alt``
    write, so the raster the mesher renders and the array the solve
    samples are the same surface.  It is deliberately NOT called from
    ``bake_airport_insets_into_alt_dem``: that function returns early
    whenever the inset FEATURE has nothing to do, and a substitution
    that only happens when some other feature fires is a substitution
    that silently does not happen.

    It PERSISTS NOTHING (spec section 3.3): the constant raster lives in
    memory for the length of one build and no file is opened here.

    "Flat" is the detector's ``flat_candidate`` (measured) or
    ``flat_declared`` (the owner's declaration) — the mode treats them
    identically; see ``flat_site_mode.substituting_verdicts``.

    Records one ``synthetic_flat_site`` provenance entry per airport on
    the DEM object, written HERE and only here, so the stamp can never
    claim a substitution the solve did not see (spec section 2.3).

    Never takes a build down: a failure here leaves the real surface in
    place (the pre-change behaviour) and says so at verbosity 0.
    """
    base_dem = getattr(tile, "dem", None)
    if base_dem is None or getattr(base_dem, "alt_dem", None) is None:
        return
    try:
        from auto_patch import flat_site_mode as FLAT_SITE_MODE

        substitutions = FLAT_SITE_MODE.flat_site_substitutions(
            tile, dico_airports=dico_airports
        )
    except Exception as error:
        UI.vprint(
            0,
            "   ERROR: FLAT-SITE mode skipped (",
            type(error).__name__,
            ":",
            str(error),
            ") - DEM prep left on the real surface.",
        )
        return
    if not substitutions:
        return

    feather_m = getattr(tile, "airport_elevation_inset_feather_m", 60.0)
    stamped = list(getattr(base_dem, "synthetic_flat_site_provenance", None)
                   or [])
    # THE WATER CUT-OUT (owner RULINGS 2026-09-09m; 09o (2)) — read once
    # per tile, from the cached coastline/water layers only.
    try:
        water = FLAT_SITE_MODE.water_cutout(tile)
    except Exception as error:                             # pragma: no cover
        UI.vprint(0, "   [flat-site] water cut-out FAILED (",
                  type(error).__name__, ":", str(error),
                  ") - synthetic insets cover their whole bbox.")
        water = None
    for substitution in substitutions:
        icao = substitution["icao"]
        x0, y0, x1, y1 = substitution["extent_deg"]
        # R17c-2: the raster is grown by the feather so the ramp lands
        # OUTSIDE the declared extent -- Z0 holds to the wall line.  The
        # provenance below keeps the DECLARED box.
        inset, water_frac = _flat_site_inset(
            tile, (x0, y0, x1, y1), substitution["z0_m"], feather_m,
            "%s synthetic flat-site inset" % icao, water)
        if inset is None:
            UI.vprint(
                0,
                "   [flat-site] %s: the whole synthetic extent is WATER — "
                "nothing substituted, the real surface stands." % icao)
            continue
        if water_frac:
            UI.vprint(
                1,
                "   [flat-site] %s: %.1f %% of the synthetic extent is WATER "
                "and is CUT OUT of the Z0 raster (the base DEM stands there; "
                "the mask edge is the sea wall)." % (icao, 100.0 * water_frac))
        try:
            _bake_one_inset(tile, None, feather_m, inset=inset)
        except Exception as error:
            UI.vprint(
                0,
                "   ERROR: FLAT-SITE mode could not bake the synthetic inset "
                "for",
                icao,
                "(",
                type(error).__name__,
                ":",
                str(error),
                ") - that airport stays on the real surface.",
            )
            continue
        airport_entry = {
            "icao": icao,
            "kind": "synthetic_flat_site",
            "verdict": substitution.get("verdict"),
            "z0_m": substitution["z0_m"],
            "extent_tile_degrees": [x0, y0, x1, y1],
            "extent_wgs84": [
                tile.lon + x0, tile.lat + y0,
                tile.lon + x1, tile.lat + y1,
            ],
            "extent_area_km2": substitution.get("extent_area_km2"),
            "feather_m": float(feather_m),
            # 09o (2): the fraction of the (feathered) rectangle the water
            # cut removed.  0.0 is "measured, none" — never absent.
            "water_cut_frac": float(water_frac),
            "record": substitution["record"],
            # R11-1/R11-2: the clusters this airport was REFUSED, filled
            # in below.  Stamped on the AIRPORT's entry because a refused
            # cluster has no entry of its own -- that is the point.
            "cluster_findings": [],
        }
        stamped.append(airport_entry)
        # R8-1 (round-8 VHHH close-out spec): ONE MORE CONSTANT INSET PER
        # CLAIMED-PLACEMENT CLUSTER.  An airport's pack can place hundreds
        # of objects on ground the apt.dat record never mentions (VHHH's
        # HZMB reclamation: 121+ placements, 894 m outside the extent, a
        # 7.32 m step at its edge).  Those clusters are the airport's
        # claimed ground and take the same Z0 — but each gets its OWN
        # rectangle, never a grown bbox: the measured 450 m open channel
        # between the airport and the island must stay SEA, and one box
        # spanning both would flatten it.
        #
        # R11-2: and the DATUM CHECK REFUSES for these.  A cluster inset
        # carries the airport's Z0 onto ground the apt.dat record never
        # mentions, so the feather ring is the only evidence that the two
        # surfaces belong together -- at KMCI it read a median -64.5 m
        # and the bake substituted anyway.  Over the threshold, the
        # cluster is DROPPED and counted.  The airport's OWN extent
        # substitution above is untouched by this: its Z0 comes from ITS
        # CIFP consensus over ITS apt.dat footprint.
        for cluster in (substitution.get("object_clusters") or ()):
            cx0, cy0, cx1, cy1 = cluster["extent_deg"]
            # 09o (2): a cluster rectangle is cut at the water too — the
            # channel this law already refuses to span must not be
            # flattened from either side.
            cluster_inset, cluster_water_frac = _flat_site_inset(
                tile, (cx0, cy0, cx1, cy1), substitution["z0_m"], feather_m,
                "%s synthetic flat-site object-cluster inset" % icao, water)
            cluster["water_cut_frac"] = float(cluster_water_frac)
            if cluster_inset is None:
                UI.vprint(
                    0,
                    "   [flat-site] %s: a claimed-object cluster rectangle is "
                    "entirely WATER — not substituted." % icao)
                continue
            try:
                ring_offset_m = _bake_one_inset(
                    tile, None, feather_m, inset=cluster_inset,
                    refuse_datum_offset_over_m=(
                        INSET_DATUM_WARNING_THRESHOLD_M),
                )
            except Exception as error:
                UI.vprint(
                    0,
                    "   ERROR: FLAT-SITE mode could not bake the synthetic "
                    "object-cluster inset for",
                    icao,
                    "(",
                    type(error).__name__,
                    ":",
                    str(error),
                    ") - that cluster stays on the real surface.",
                )
                continue
            if (ring_offset_m is not None
                    and abs(ring_offset_m)
                    > INSET_DATUM_WARNING_THRESHOLD_M):
                FLAT_SITE_MODE.record_cluster_finding(
                    substitution,
                    FLAT_SITE_MODE.CLUSTER_FINDING_DATUM,
                    placements=cluster.get("placements"),
                    fallback_placements=cluster.get("fallback_placements"),
                    ring_offset_m=round(float(ring_offset_m), 2),
                    threshold_m=float(INSET_DATUM_WARNING_THRESHOLD_M),
                    extent_area_km2=cluster.get("extent_area_km2"),
                )
                UI.vprint(
                    0,
                    "   [flat-site] %s: REFUSED a CLAIMED-OBJECT cluster "
                    "inset at Z0 %.2f m (%d placement(s), %d "
                    "fallback-claimed, %.2f km2) - it differs from the base "
                    "DEM by a median %.2f m over the feather ring (>%d m; "
                    "check vertical datum). The cluster stays on the real "
                    "surface."
                    % (icao, substitution["z0_m"],
                       cluster.get("placements") or 0,
                       cluster.get("fallback_placements") or 0,
                       cluster.get("extent_area_km2") or 0.0,
                       float(ring_offset_m),
                       int(INSET_DATUM_WARNING_THRESHOLD_M)),
                )
                continue
            stamped.append(
                {
                    "icao": icao,
                    "kind": "synthetic_flat_site_object_cluster",
                    "verdict": substitution.get("verdict"),
                    "z0_m": substitution["z0_m"],
                    "extent_tile_degrees": [cx0, cy0, cx1, cy1],
                    "extent_wgs84": [
                        tile.lon + cx0, tile.lat + cy0,
                        tile.lon + cx1, tile.lat + cy1,
                    ],
                    "extent_area_km2": cluster.get("extent_area_km2"),
                    "claimed_placements": cluster.get("placements"),
                    "feather_m": float(feather_m),
                }
            )
            UI.vprint(
                0,
                "   [flat-site] %s: SYNTHETIC CONSTANT INSET at Z0 %.2f m "
                "over a CLAIMED-OBJECT cluster of %d placement(s), %.2f km2 "
                "(feather %g m)."
                % (icao, substitution["z0_m"],
                   cluster.get("placements") or 0,
                   cluster.get("extent_area_km2") or 0.0, feather_m),
            )
        # R11-1/R11-2: the refusals this airport collected, counted once
        # and carried on its provenance entry.  Refusals raised BEFORE
        # the bake (the R11-1 distance bound, recorded by
        # ``flat_site_mode``) and refusals raised here (R11-2's datum
        # gate) are one list -- a reader asking "what was refused" must
        # not have to know which half of the machinery said no.
        airport_entry["cluster_findings"] = list(
            substitution.get("cluster_findings") or ())
        if airport_entry["cluster_findings"]:
            UI.vprint(
                0,
                "   [flat-site] %s: %d claimed-object cluster(s) REFUSED "
                "(%s)."
                % (icao, len(airport_entry["cluster_findings"]),
                   ", ".join(str(finding.get("kind"))
                             for finding in airport_entry["cluster_findings"])),
            )
        UI.vprint(
            0,
            "   [flat-site] %s: SYNTHETIC CONSTANT INSET at Z0 %.2f m over "
            "%.2f km2 (feather %g m) - DEM source substituted."
            % (icao, substitution["z0_m"],
               substitution.get("extent_area_km2") or 0.0, feather_m),
        )
    # R21 -- LAND-CONNECTED CONTINUITY, after every family member has
    # actually landed: the connecting land between two admitted
    # footprints on one sea-bounded island grades with them.  Automatic
    # and universal; nothing here reads a declaration (the retired
    # ``flat_site_declared_corridors``).
    _bake_island_continuity(tile, stamped, feather_m)
    base_dem.synthetic_flat_site_provenance = stamped
    # The substitution lives in ``alt_dem``.  Every reader of a baked DEM
    # reads that array (``alt_baked``, ``alt_nostrict``, the ``.alt`` file
    # the mesher renders) EXCEPT the legacy composite query, which reads
    # the sub-DEMs directly.  If that is still the active reader, the
    # grading law and the mesh would see two different surfaces -- say so
    # loudly rather than measure one and render the other.
    if stamped and getattr(base_dem, "subdems", None) and not getattr(
        base_dem, "baked_query_active", False
    ):
        UI.vprint(
            0,
            "   WARNING: FLAT-SITE mode substituted the working raster but "
            "the DEM QUERY path is still the composite (O4_DEM_QUERY_BAKED "
            "off, or a sub-DEM did not bake): the mesh would render the "
            "flat surface while the grading law reads the real one.",
        )


# =====================================================================
# Automatic per-airport smoothing radius (spec section 3.4)
# =====================================================================
# The airport smoothing blur exists to hide the pixel staircase of the
# elevation SOURCE, so its radius should scale with the source's pixel
# size, not sit fixed at apt_smoothing_pix working-grid pixels (a fixed
# 8-pixel tent blur is ~250 m and was measured to erase engineered
# relief -- the KBNA taxiway M plateau dropped 9.5 m).  The rule, in
# metres so the mask upscaling step never changes the physical footprint:
#
#   blur_radius_m    = apt_smoothing_pix * source_pixel_m,
#                      capped at apt_smoothing_pix * working_pixel_m
#   radius_pixels(a) = round(blur_radius_m / working_pixel_m)
#                    = min(apt_smoothing_pix,
#                          round(apt_smoothing_pix
#                                * source_pixel_m / working_pixel_m))
#
# where source_pixel_m is the finest inset resolution that actually
# COVERS at least INSET_COVERAGE_THRESHOLD of the airport's smoothing
# mask (inset_coverage_of_airport_mask), else the base source's TRUE
# pixel size capped at the working pixel.  The base loader either reads a
# source at its native grid or UPSAMPLES coarser data onto the working
# grid, so no base source is ever finer than the working grid: the cap
# makes the base path's ratio exactly 1 and the radius exactly
# apt_smoothing_pix -- identical to today (goal G3).  Consequences:
# 30 m-class base -> apt_smoothing_pix unchanged; a 10 m source -> 3
# pixels (of 8); 3 m inset -> 1; 1 m inset -> 0.
#
# "Resolution" here is the honest resolution of the DATA, never the
# posting of the file (_honest_inset_resolution_m), and it must blanket
# THIS mask rather than merely clip it.  Both corrections come from the
# 2026-07-24 OTHH report: Copernicus GLO-30 is the only source in Qatar,
# yet OTHH smoothed at radius 2 (31 m of blur over 30 m data, the
# staircase left bare) because neighbouring OTBD's inset had been warped
# onto a 3 m grid and its extent clipped a third of OTHH's mask.  Honest
# resolution 30 m + a coverage gate per resolution restores radius 16.

INSET_COVERAGE_THRESHOLD = 0.8


def smoothing_radius_pixels_for_source(
    apt_smoothing_pix, source_pixel_m, working_pixel_m, reference_pixel_m=None
):
    """The spec section 3.4 radius rule (pure arithmetic).

    Half-up rounding (not banker's) so the boundary cases are
    deterministic and monotone in ``source_pixel_m``; floored at 0 (no
    blur).

    The radius expresses a PHYSICAL blur footprint of
    ``apt_smoothing_pix * min(source_pixel_m, reference_pixel_m)`` metres,
    divided by the working-grid pixel to yield a pixel count.
    ``reference_pixel_m`` is the 1 arc-second (~30.9 m) pixel that the
    historic ``apt_smoothing_pix`` was expressed in; it defaults to
    ``working_pixel_m`` so the non-densified path is byte-identical to
    before.  On the Phase C densified path the caller passes the true
    1 arc-second pixel so that halving the grid does not silently halve
    the physical smoothing footprint (the section 3.4 "radius in metres"
    principle).  ``min(source_pixel_m, reference_pixel_m)`` also supplies
    the historic "never exceed today" cap: no base source is finer than
    the reference pixel, so a coarse source yields exactly
    ``apt_smoothing_pix`` reference-pixels of blur.
    """
    if apt_smoothing_pix <= 0 or working_pixel_m <= 0:
        return max(int(apt_smoothing_pix), 0)
    if reference_pixel_m is None:
        reference_pixel_m = working_pixel_m
    effective_source_pixel_m = min(source_pixel_m, reference_pixel_m)
    scaled = apt_smoothing_pix * effective_source_pixel_m / working_pixel_m
    return int(scaled + 0.5)


def inset_coverage_of_airport_mask(tile, mask_geometry):
    """Coverage of an airport's smoothing mask by the cached insets.

    Returns ``(coverage_fraction, finest_covering_inset_pixel_m)``.
    Coverage is judged by the insets' raster EXTENTS (rectangles in
    tile-relative degrees), each WEIGHTED BY ITS VALID-PIXEL FRACTION
    (R11-3): a rectangle is where an inset could have data, and the
    fraction is how much of it does.  An inset under
    ``INSET_MIN_VALID_FRAC`` valid is absent here exactly as it is
    absent from the bake -- KMCI's 100 %-nodata 1 m raster reported
    100 % coverage at 1 m and set the smoothing radius to 0 over a
    surface it never touched.  A fully-valid inset weighs exactly 1 and
    the answer is the pre-change answer.  ``(0.0, None)`` when no cached
    inset touches the mask.

    The second element is the resolution the smoothing radius may assume
    over THIS mask, and it is deliberately not the finest pixel of every
    raster that merely clips the mask.  Two corrections apply:

    * Each inset is judged at its HONEST resolution
      (:func:`_honest_inset_resolution_m`) -- a 30 m source stored on a
      3 m grid carries 30 m of information and is treated as 30 m.
    * A resolution only counts when insets at least that fine actually
      COVER ``INSET_COVERAGE_THRESHOLD`` of the mask.  Airport bounding
      boxes overlap generously (``airport_elevation_inset_margin_m`` is
      2 km), so a neighbour's finer inset routinely clips a corner of
      this airport's mask; letting that set the radius smooths this
      airport as if it had detail it does not have.  Candidates are
      tested finest-first and CUMULATIVELY (every inset at least that
      fine), so genuinely mixed coverage still resolves to the finest
      resolution that blankets the mask.
    """
    if (
        not has_gdal
        or mask_geometry is None
        or mask_geometry.is_empty
        or mask_geometry.area == 0
    ):
        return (0.0, None)
    from shapely import geometry as shapely_geometry
    from shapely import ops as shapely_ops

    provider_definitions = select_provider_definitions(
        getattr(tile, "airport_elevation_providers", "auto")
    )
    codes = [definition["code"] for definition in provider_definitions]
    inset_paths = list_cached_inset_dems(
        tile.lat, tile.lon, provider_codes=codes or None
    )
    boxes = []
    resolved_boxes = []
    weighted_boxes = []
    for inset_path in inset_paths:
        try:
            dataset = gdal.Open(inset_path)
            geotransform = dataset.GetGeoTransform()
            columns = dataset.RasterXSize
            rows = dataset.RasterYSize
        except Exception:
            continue
        west = geotransform[0]
        north = geotransform[3]
        east = west + columns * geotransform[1]
        south = north + rows * geotransform[5]
        extent_box = shapely_geometry.box(
            west - tile.lon, south - tile.lat, east - tile.lon, north - tile.lat
        )
        if not extent_box.intersects(mask_geometry):
            continue
        (is_empty, valid_fraction) = inset_is_effectively_empty(inset_path)
        if is_empty:
            # R11-3: no data, no coverage, no resolution claim.
            continue
        boxes.append(extent_box)
        stored_pixel_m = abs(geotransform[5]) * GEO.lat_to_m
        resolved_boxes.append(
            (
                _honest_inset_resolution_m(inset_path, stored_pixel_m),
                extent_box,
            )
        )
        weighted_boxes.append((valid_fraction, extent_box))
    if not boxes:
        return (0.0, None)
    mask_area = mask_geometry.area
    # Best-available-data accounting: walk the insets richest-first and
    # give each piece of the mask the valid fraction of the best inset
    # that reaches it, so nothing is double-counted and an all-valid set
    # returns the union area it always returned.
    covered_area = 0.0
    remaining = mask_geometry
    for valid_fraction, extent_box in sorted(
        weighted_boxes, key=lambda item: item[0], reverse=True
    ):
        piece = remaining.intersection(extent_box)
        if piece.is_empty:
            continue
        covered_area += piece.area * valid_fraction
        remaining = remaining.difference(extent_box)
        if remaining.is_empty:
            break
    # Finest-first, cumulative: the coarsest candidate is the union of
    # everything, so this terminates on the same total coverage the
    # caller's gate sees (None only when even that falls short).
    finest_pixel_m = None
    for candidate_pixel_m in sorted({res for (res, _) in resolved_boxes}):
        at_least_this_fine = [
            box for (res, box) in resolved_boxes if res <= candidate_pixel_m
        ]
        candidate_coverage = (
            shapely_ops.unary_union(at_least_this_fine)
            .intersection(mask_geometry)
            .area
            / mask_area
        )
        if candidate_coverage >= INSET_COVERAGE_THRESHOLD:
            finest_pixel_m = candidate_pixel_m
            break
    return (covered_area / mask_area, finest_pixel_m)


def _inset_provider_code_from_path(inset_path):
    """The provider code encoded in a cached inset file name, lower-cased.

    The mirror of :func:`_inset_icao_from_path` over ``<airport>_<code>``
    stems; ``""`` when the name carries no code.
    """
    stem = os.path.splitext(os.path.basename(inset_path))[0]
    return stem.rsplit("_", 1)[1].lower() if "_" in stem else ""


def _honest_inset_resolution_m(inset_path, stored_pixel_m=None):
    """The resolution a cached inset's data ACTUALLY carries, in metres.

    A warp can only ever store data on a grid; it cannot add information.
    An inset written at a posting FINER than its provider's native
    resolution -- an ``airport_elevation_level`` pinned below native
    before :func:`_inset_target_resolution_m` clamped it, or a cache from
    that era -- therefore still carries native-resolution detail, and the
    honest figure is the COARSER of the two.  A warp to a coarser posting
    is real coarsening, so the stored pixel wins there.

    The native resolution comes from the provenance sidecar, else from
    the provider definition named in the file name.  When neither knows
    (a hand-dropped raster), the stored pixel is taken at face value.
    """
    if stored_pixel_m is None:
        header = _inset_header_geometry(inset_path)
        if header is None:
            return None
        stored_pixel_m = abs(header[0][5]) * GEO.lat_to_m
    native_resolution_m = None
    try:
        with open(os.path.splitext(inset_path)[0] + ".json", "r") as handle:
            native_resolution_m = _parse_float(
                json.load(handle).get("native_resolution_m")
            )
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    if native_resolution_m is None:
        # Sidecar-less relics still resolve: the file name names the
        # provider, and the definition declares what it publishes.
        definition = elevation_providers_dict.get(
            _inset_provider_code_from_path(inset_path).upper()
        )
        if definition:
            native_resolution_m = _definition_resolution_m(definition)
    if native_resolution_m is None or native_resolution_m <= 0:
        return stored_pixel_m
    return max(stored_pixel_m, native_resolution_m)


def cached_inset_paths_for_icao(lat, lon, icao, providers_config="auto"):
    """The cached inset rasters whose file name names ``icao`` (case
    insensitively), in the PROVIDER RANKING order ``providers_config``
    selects -- the order the fetch loop consults them in.

    Cache files are ``<airport key>_<code>.tif`` and the airport key is
    the dico key the box was cut for, so this is the same identity
    :func:`_inset_icao_from_path` recovers.
    """
    if not icao:
        return []
    wanted = str(icao).upper()
    cached = {
        _inset_provider_code_from_path(path): path
        for path in list_cached_inset_dems(lat, lon)
        if _inset_icao_from_path(path).upper() == wanted
    }
    ordered = []
    for definition in select_provider_definitions(providers_config):
        path = cached.pop(definition["code"].lower(), None)
        if path is not None:
            ordered.append(path)
    # A raster from a provider this config does not select is still ON
    # DISK and still bakes; it ranks last rather than vanishing.
    return ordered + [cached[code] for code in sorted(cached)]


def inset_fill_summary(provenance):
    """THE FILL RECORD of one inset sidecar (spec las-tile §12) -- the one
    reader the harness frame check, the census header and the witness
    share.  A sidecar written before §12 carries no ``holes`` key and
    reads ``holes == 0`` with ``recorded`` False: no hole was ever filled
    there (none was asked).  ``airport_valid_fraction`` is the core's own
    cover (the rung-selection number); ``airport_filled_fraction`` the
    cover after the fills -- < 1.0, or a ``ran_out`` rung, is REPORTED by
    the harness, never refused."""
    provenance = provenance if isinstance(provenance, dict) else {}
    holes = [row for row in provenance.get("holes") or ()
             if isinstance(row, dict)]
    fills = provenance.get("fills")
    fills = fills if isinstance(fills, dict) else {}
    return {
        "recorded": "holes" in provenance,
        "holes": len(holes),
        "hole_cells": int(sum(int(row.get("cells") or 0) for row in holes)),
        "unfilled_hole_cells": int(sum(int(row.get("unfilled_cells") or 0)
                                       for row in holes)),
        "filled_by": sorted({
            str(row["filled_by"].get("label")
                if isinstance(row.get("filled_by"), dict)
                else row.get("filled_by"))
            for row in holes if row.get("filled_by")}),
        "interior_islands": fills.get("interior_islands"),
        "edge_islands": fills.get("edge_islands"),
        "fill_layers": [layer.get("label")
                        for layer in fills.get("layers") or ()
                        if isinstance(layer, dict)],
        "sub_threshold_voids": fills.get("sub_threshold_voids"),
        "filled_fraction": fills.get("filled_fraction"),
        "ran_out": fills.get("ran_out"),
        "airport_valid_fraction": provenance.get("airport_valid_fraction"),
        "airport_filled_fraction": provenance.get("airport_filled_fraction"),
    }


def inset_fill_shortfall(summary):
    """The reportable condition of :func:`inset_fill_summary`: the cover
    after fills is below 1.0 over the airport, or the ladder ran out of
    rungs with a hole unanswered.  ``None`` when nothing to report."""
    if not summary:
        return None
    reasons = []
    filled = summary.get("airport_filled_fraction")
    if filled is not None and filled < 1.0:
        reasons.append("airport filled %.4f < 1.0" % filled)
    if summary.get("ran_out"):
        reasons.append("the ladder ran out at %s" % summary["ran_out"])
    return "; ".join(reasons) or None


def inset_fill_summary_text(summary):
    """One line: ``holes N (C cells) filled by [...], airport valid V ->
    filled F``."""
    if not summary:
        return "no cached inset"
    if not summary.get("recorded"):
        return "holes 0 (sidecar predates the ladder fill, spec §12)"

    def _fraction(value):
        return "None" if value is None else "%.4f" % value

    text = ("holes %d (%d cells; islands interior %s / edge %s) filled "
            "by %s, airport valid %s -> filled %s, box filled %s, "
            "sub-threshold voids %s"
            % (summary["holes"], summary["hole_cells"],
               summary.get("interior_islands"), summary.get("edge_islands"),
               summary["filled_by"] or "[]",
               _fraction(summary.get("airport_valid_fraction")),
               _fraction(summary.get("airport_filled_fraction")),
               _fraction(summary.get("filled_fraction")),
               summary.get("sub_threshold_voids")))
    shortfall = inset_fill_shortfall(summary)
    return text + (" -- REPORT: " + shortfall if shortfall else "")


def cached_inset_fill_summary(lat, lon, icao):
    """:func:`inset_fill_summary` of the airport's FIRST-ranked cached
    inset (the one the bake reads first), plus its ``inset`` file name;
    ``None`` when no inset is cached.  A read: nothing is written."""
    paths = cached_inset_paths_for_icao(lat, lon, icao)
    if not paths:
        return None
    sidecar = os.path.splitext(paths[0])[0] + ".json"
    try:
        with open(sidecar, "r", encoding="utf-8") as handle:
            provenance = json.load(handle)
    except (OSError, ValueError):
        provenance = {}
    summary = inset_fill_summary(provenance)
    summary["inset"] = os.path.basename(paths[0])
    return summary


def cached_inset_paths_for_airport(tile, icao):
    """:func:`cached_inset_paths_for_icao` for a tile object."""
    return cached_inset_paths_for_icao(
        tile.lat, tile.lon, icao,
        getattr(tile, "airport_elevation_providers", "auto"))


def airport_has_inset_index_record(lat, lon, icao):
    """True when the tile's inset index already holds a record for this
    airport -- i.e. some pass HAS considered it.

    An airport with a record but no raster is a lawful absence (every
    provider answered ``no-coverage``, and that negative is the cache).
    An airport with NEITHER has simply never been asked, which is a cold
    frame for this airport inside a warm-looking directory -- the gap
    ``frame_state`` could not see.
    """
    wanted = str(icao).upper()
    return any(str(key).upper() == wanted
               for key in _read_index(lat, lon))


def unanswered_inset_providers(lat, lon, icao, required_box,
                               providers_config="auto"):
    """The provider codes whose declared coverage reaches ``required_box``
    but whose answer for ``icao`` is ABSENT from the tile's index record.

    A raised fetch -- a transport or TLS failure, a strategy crash --
    deliberately records nothing (:class:`TransientFetchError`), so an
    absent status is exactly "this provider was asked and never
    answered".  A record holding ``no-coverage`` from every covering
    provider is a lawful absence; one with a covering provider MISSING is
    a cold frame dressed as a warm one (issue #121).
    """
    wanted = str(icao).upper()
    record = None
    for (key, value) in _read_index(lat, lon).items():
        if str(key).upper() == wanted:
            record = value
            break
    if not isinstance(record, dict):
        return []
    statuses = provider_statuses(record)
    unanswered = []
    # Walk in the FETCH LOOP's ranking: it stops at the first ``ok``, so a
    # provider ranked below one is never asked and its absence is lawful.
    for definition in select_provider_definitions(providers_config):
        status = statuses.get(definition["code"])
        if status == "ok":
            break
        if status is None and _coverage_bbox_intersects(definition,
                                                        required_box):
            unanswered.append(definition["code"])
    return unanswered


def airport_inset_frame_problem(lat, lon, icao, required_box,
                                providers_config="auto"):
    """Why THIS airport's elevation inset cannot serve a build over
    ``required_box``, as ``(kind, text)``, or ``None`` when it can.

    THE ONE DERIVATION SITE for the per-airport frame check: production
    (``auto_patch_v2.airport.dem_production.frame_state``) and the
    harness (``tools/harness/build_airport.py``) both call this, so the
    thing the app RE-CUTS and the thing the harness REFUSES can never
    drift apart.

    ``("missing", ...)``  no raster for this airport AND no index record
                          -- nothing has ever asked this provider chain;
                          OR a record in which a provider covering the
                          airport has NO answer (its fetch raised and
                          recorded nothing -- issue #121).
    ``("stale", ...)``    the highest-ranked cached raster was cut for a
                          box that no longer contains what is required
                          (:func:`inset_recut_is_needed`, THE RE-CUT
                          RULE).  The text names the inset, both boxes
                          and the ``--refresh-data dem`` scope.
    ``("empty", ...)``    the highest-ranked cached raster is one the
                          BAKE DECLINES (:func:`cached_inset_declined_
                          reason`).  A KNOWN, DECLARED state, never a
                          refusal: the airport solves on the base DEM.
                          Callers report it and carry on.

    A raster whose manifest cannot be judged is REUSABLE, so it yields
    ``None``; and the DELIVERY shortfall is NOT judged here at all --
    that arm warns (:func:`warn_if_delivered_inset_clips_airport`) and
    never re-cuts, because re-asking returns the same raster.
    """
    paths = cached_inset_paths_for_icao(lat, lon, icao, providers_config)
    if not paths:
        if airport_has_inset_index_record(lat, lon, icao):
            # A record and no raster is lawful ONLY when every provider
            # that covers the airport gave a DURABLE answer.  One that
            # never answered (its fetch raised: transport, TLS, a crash)
            # leaves no status, and reading that as "no provider covers
            # it" is the silent degrade of issue #121.
            unanswered = unanswered_inset_providers(
                lat, lon, icao, required_box, providers_config)
            if not unanswered:
                return None        # every provider answered no-coverage
            return ("missing",
                    "NO airport elevation inset for %s in %s: provider(s) "
                    "%s cover it but NEVER ANSWERED (the last fetch failed "
                    "on the network/TLS or crashed, and recorded nothing) "
                    "-- the build would re-fetch it (--refresh-data dem)"
                    % (icao, FNAMES.airport_inset_directory(lat, lon),
                       ", ".join(unanswered)))
        return ("missing",
                "NO airport elevation inset for %s in %s, and no index "
                "record either — this airport's provider chain has never "
                "been asked, so the build would fetch it (--refresh-data "
                "dem)" % (icao, FNAMES.airport_inset_directory(lat, lon)))
    # The fetch loop reuses the FIRST ranked provider whose cache is
    # usable, so that raster is the one whose staleness decides.
    path = paths[0]
    code = _inset_provider_code_from_path(path)
    declined = cached_inset_declined_reason(path)
    if declined is not None:
        # DECLARED EMPTY (2026-09-18).  Not a silent degrade and not a
        # cold frame: the bake says so out loud, records it as a nodata
        # refusal and grades on the base DEM.  Named here so both
        # readers of this one predicate -- the harness pre-flight and
        # production's frame_state -- report the same known state and
        # neither refuses the airport for it.
        return ("empty",
                "DECLARED-EMPTY airport elevation inset %s — %s, so %s "
                "solves on the BASE DEM (the bake says so in its own line "
                "and records a nodata refusal).  Re-fetch it deliberately: "
                "--refresh-data dem (an airport build never fetches one; "
                "--warm-insets %s fetches exactly this one)"
                % (path, declined, icao, icao))
    if not inset_recut_is_needed(lat, lon, icao, code, required_box):
        if _masking_definition_for_code(code) is not None and \
                _sidecar_footprint_packs_mismatch(lat, lon, icao, code,
                                                  required_box):
            # THE PACK SET MOVED (owner ruling 2026-09-17c (1)), named
            # here so the pre-flight sees what the FETCH LOOP sees.
            # MEASURED 2026-09-18 on +17-063: the owner's
            # ``scenery_packs.ini`` was rewritten at 19:53 disabling two
            # TFFJ packs the 15:39 sidecars record as having served the
            # mask, so all FOUR airports of the tile refetched mid-build
            # and the shared-repo guard blocked four ``os.replace``es
            # AFTER the download had already run.  The pre-flight said
            # nothing because this reuse test was not among the ones it
            # asked.  Same predicate as the fetch loop
            # (:func:`_sidecar_footprint_packs_mismatch`), same masking
            # gate — imported, never copied.
            recorded = recorded_footprint_packs(lat, lon, icao, code) or []
            now = package_footprint_pack_names(required_box)
            gone = sorted(set(recorded) - set(now))
            new = sorted(set(now) - set(recorded))
            return ("packs",
                    "PACK-SET-STALE airport elevation inset %s — its "
                    "building mask was served by a DIFFERENT set of "
                    "installed scenery packs (%s%s%s), so the build would "
                    "RE-FETCH and re-mask it (--refresh-data dem)"
                    % (path,
                       "no longer installed/enabled: " + ", ".join(gone)
                       if gone else "",
                       "; " if gone and new else "",
                       "newly installed/enabled: " + ", ".join(new)
                       if new else ""))
        return None
    requested = requested_inset_bounding_box(lat, lon, icao, code)
    return ("stale",
            "STALE airport elevation inset %s — it was cut for %s but %s "
            "now requires %s, so the build would RE-CUT it (--refresh-data "
            "dem)"
            % (path,
               ",".join("%.6f" % value for value in requested),
               icao,
               ",".join("%.6f" % value for value in required_box)))


def warn_if_inset_does_not_cover_airport(tile, icao, coverage_fraction):
    """LOUD when an airport HAS a cached elevation inset that does not
    cover it (lane insetbounds, brief gap (ii)).

    :func:`resolve_airport_smoothing_radius` used to consume a
    below-threshold coverage fraction SILENTLY -- it picked the base
    source's radius and returned, and the airport ground outside the
    inset stayed on the base DEM with nothing said anywhere.  That is the
    difference between "this airport has no lidar" (ordinary, and visible
    in the inset index) and "this airport has lidar over PART of itself",
    which is a cache defect and used to be invisible.

    Silent when the airport has no cached inset at all: that is the
    ordinary base-source case, not a shortfall, and a tile of a hundred
    unnamed airstrips must not shout a hundred times.  Returns True when
    it warned (the twins read that).
    """
    if coverage_fraction >= INSET_COVERAGE_THRESHOLD:
        return False
    paths = cached_inset_paths_for_airport(tile, icao)
    if not paths:
        return False
    UI.loud_warning(
        "   WARNING: airport elevation inset(s) %s cover only %.0f %% of %s "
        "(threshold %.0f %%) - the airport ground outside them is graded on "
        "the BASE elevation source, not on the inset."
        % (", ".join(os.path.basename(path) for path in paths),
           100.0 * coverage_fraction, icao, 100.0 * INSET_COVERAGE_THRESHOLD)
    )
    return True


def resolve_airport_smoothing_radius(
    tile, airport_record, working_pixel_m, mask_geometry=None,
    reference_pixel_m=None, icao=None,
):
    """Resolve the smoothing radius (in working-grid pixels) for one airport.

    Returns ``(radius_pixels, source_pixel_m, coverage_fraction)``; the
    last two are ``None`` whenever the LEGACY fixed radius applies (so a
    caller can log only the automatic decisions).  ``source_pixel_m`` is
    the honest resolution of inset data that blankets THIS airport's mask
    -- a neighbour's finer inset clipping the mask does not qualify (see
    :func:`inset_coverage_of_airport_mask`).  Precedence:

    1. The per-airport ``smoothing_pix`` apt.dat/config override always
       wins (unchanged from the historic behaviour).  An unparseable
       override falls through to the rules below (historically it fell to
       the tile default; with the automatic gate off that is still exactly
       what happens).
    2. ``apt_smoothing_auto`` off, insets gated off, or GDAL absent ->
       the fixed ``tile.apt_smoothing_pix``.
    3. Otherwise the section 3.4 rule above.

    ``reference_pixel_m`` is the physical size of one 1 arc-second working
    pixel (~30.9 m).  On the Phase C densified path it differs from
    ``working_pixel_m`` (the dense pixel) so the physical blur footprint
    is preserved across densification; when omitted it defaults to
    ``working_pixel_m`` and the behaviour is byte-identical to before.
    Note the explicit ``smoothing_pix`` override stays a PIXEL count of the
    working grid (its historic meaning), so densifying scales its physical
    footprint -- an override is a deliberate manual value and is left
    literal.

    ``icao`` is the airport's dico key.  It is used ONLY to make a
    coverage shortfall LOUD (:func:`warn_if_inset_does_not_cover_airport`)
    and never to pick a radius; omitting it keeps the historic silence.
    """
    if "smoothing_pix" in airport_record:
        try:
            return (int(airport_record["smoothing_pix"]), None, None)
        except (TypeError, ValueError):
            pass
    default_radius = tile.apt_smoothing_pix
    if not getattr(tile, "apt_smoothing_auto", False):
        return (default_radius, None, None)
    if resolved_inset_mode(tile) == "None" or not has_gdal:
        # Same truthiness hazard as ``insets_enabled_for_tile`` (row 24).
        return (default_radius, None, None)
    (coverage_fraction, finest_pixel_m) = inset_coverage_of_airport_mask(
        tile, mask_geometry
    )
    if reference_pixel_m is None:
        reference_pixel_m = working_pixel_m
    if coverage_fraction >= INSET_COVERAGE_THRESHOLD and finest_pixel_m:
        source_pixel_m = finest_pixel_m
    else:
        # A SHORTFALL IS LOUD, not a silent fall-through to the base
        # source (gap (ii)); the threshold itself is untouched.
        warn_if_inset_does_not_cover_airport(tile, icao, coverage_fraction)
        # Base source: TRUE pixel capped at the reference pixel (see the
        # section comment -- the cap makes this the reference pixel, and
        # the radius identical to today on the non-densified path).
        source_pixel_m = reference_pixel_m
    radius_pixels = smoothing_radius_pixels_for_source(
        default_radius, source_pixel_m, working_pixel_m, reference_pixel_m
    )
    return (radius_pixels, source_pixel_m, coverage_fraction)


# =====================================================================
# Densified working grid over inset tiles (spec section 4, Phase C1)
# =====================================================================
# The Phase B acceptance proved the last KBNA residual is the GRID, not
# the bake: Triangle4XP cannot refine a mesh below one working pixel
# (Utils/src/Triangle4XP.c:7297), so a meter-class scarp captured in a
# 3 m inset is still resolved to +/-1.6 m when the working grid posts at
# ~30.9 m (1 arc-second).  When any airport inset is cached for the tile,
# the combined working raster (and the .alt the mesher reads) is built on
# a denser grid: the base is upsampled bilinearly to the target posting
# and the insets are baked at that denser posting, so their relief
# survives to the mesh.  No-inset tiles keep the 1 arc-second grid and are
# byte-identical to before.
#
# The target spacing is chosen BEFORE any tile build with a cheap numpy
# check on the cached inset GeoTIFF (no mesh, no Triangle4XP): for a small
# set of acceptance PROBES, the "ideal bake" value the probe would read
# from a working raster at a candidate grid is modelled and compared to
# the inset's own bilinear value there.  We pick the COARSEST candidate of
# {1/2, 1/3} arc-second whose worst-probe error stays within
# WORKING_GRID_IDEAL_TOLERANCE_M, so we never pay for more grid (bytes,
# memory, mesh time) than the data actually needs.

# Candidate densification FACTORS relative to the 1 arc-second base grid
# (factor f => spacing 1/f arc-second => (n-1)*f + 1 samples).  The
# candidate set is the coarsest-first {1/2, 1/3} arc-second of the spec.
WORKING_GRID_CANDIDATE_FACTORS = (2, 3)

# An inset counts as BASE-CLASS -- carrying nothing the 1 arc-second base
# grid could not already hold -- when its honest resolution is no more
# than marginally finer than the base posting.  Copernicus GLO-30 (30 m)
# against a ~30.87 m base posting is base-class; a 10 m or 1 m lidar inset
# is not.  The margin absorbs the grid/source mismatch (30 vs 30.87) that
# would otherwise read as "finer".
BASE_CLASS_INSET_RATIO = 0.9

# Worst-probe ideal-bake tolerance for the automatic grid decision.
# Deliberately tighter than the +/-1.5 m mesh acceptance so the modelled
# .alt error leaves headroom for the mesh-floor gap the model omits.
WORKING_GRID_IDEAL_TOLERANCE_M = 1.0

# Number of steepest-gradient probes derived per inset for tiles/airports
# without a hand-seeded probe list.
DERIVED_PROBE_COUNT = 8

# Hand-seeded acceptance probes keyed by ICAO (spec section 5 seed set).
# Each probe is (latitude, longitude) in EPSG:4326 degrees.  Airports not
# listed here derive probes generically from the steepest-gradient cells
# of their inset footprint (see derive_acceptance_probes).
SEED_ACCEPTANCE_PROBES = {
    "KBNA": (
        (36.1374844, -86.6760939),  # 45 m gantry south-west foot
        (36.1376421, -86.6759065),  # gantry anchor
        (36.1377853, -86.6757619),  # 45 m gantry north-east foot
        (36.13715, -86.67650),      # taxiway M plateau
    ),
}


def parse_working_grid_arc_seconds(value):
    """Parse the ``working_grid_arc_seconds`` config into a decision.

    Returns ``"auto"`` for the automatic rule, or an integer densification
    FACTOR (1, 2, 3, 6 or 9) for an explicit pin.  Accepts ``"1"``, ``"1/2"``,
    ``"0.5"``, ``"1/3"``, the finer ``"1/6"``/``"6"`` and ``"1/9"``/``"9"``
    pins (reachable only through an explicit pin or a numeric
    ``elevation_level``), and friends; an unrecognised value falls back to
    ``"auto"`` (conservative -- the automatic rule keeps 1 arc-second when
    no inset covers the tile).
    """
    text = str(value or "auto").strip().lower()
    if text == "auto":
        return "auto"
    if text in ("1", "1/1", "1.0", "1\"", "1''"):
        return 1
    if text in ("1/2", "0.5", ".5", "2"):
        return 2
    if text in ("1/3", "3"):
        return 3
    if text in ("1/6", "6"):
        return 6
    if text in ("1/9", "9"):
        return 9
    # A bare fraction "a/b" -> snap b/a to the nearest allowed factor.
    if "/" in text:
        try:
            numerator, denominator = text.split("/", 1)
            arc_seconds = float(numerator) / float(denominator)
            if arc_seconds > 0:
                factor = 1.0 / arc_seconds
                return min(
                    (1, 2, 3, 6, 9),
                    key=lambda candidate: (abs(candidate - factor), candidate),
                )
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    return "auto"


def _inset_icao_from_path(inset_path):
    """The ICAO/airport key encoded in a cached inset file name.

    Cache files are ``<airport>_<code>.tif`` (the code lower-cased); strip
    the trailing ``_<code>`` to recover the airport key used for probe
    seeding.  Returns the whole stem if there is no underscore.
    """
    stem = os.path.splitext(os.path.basename(inset_path))[0]
    return stem.rsplit("_", 1)[0] if "_" in stem else stem


def _inset_file_identity(inset_path):
    """JSON-stable identity of a cached inset: ``[basename, size, mtime_ns]``.

    Ties an index record's cached acceptance probes to the exact raster
    they were derived from -- a refetched or hand-replaced file must never
    be trusted with another file's probes.  ``None`` when the file cannot
    be stat'ed.
    """
    try:
        stat = os.stat(inset_path)
    except OSError:
        return None
    return [os.path.basename(inset_path), stat.st_size, stat.st_mtime_ns]


# Single-slot memo for the most recently decoded inset: one
# ``(key, value)`` tuple with key ``(path, mtime_ns, size)``, or None.
# The grid decision reads the SAME file several times in a row (probe
# derivation, then the ideal-bake error at each candidate factor); with
# native-resolution insets (airport elevation level "auto", 2026-07-24)
# each decode is up to ~40x the 3 m-era bytes, so re-decoding dominated
# the whole decision.  One slot bounds the extra memory to a single
# decoded inset; callers that switch files (multi-airport tiles) simply
# refill the slot.  The entry is read and replaced as one atomic dict
# item assignment because the fetch phase's worker threads also derive
# probes concurrently -- a stale entry costs a wasted decode, never a
# wrong result.  Cleared by ``_release_inset_array_memo`` when the grid
# decision finishes so the array does not linger through the mesh phase.
_INSET_ARRAY_MEMO = {"entry": None}


def _release_inset_array_memo():
    """Drop the decoded-inset memo (frees up to one inset of memory)."""
    _INSET_ARRAY_MEMO["entry"] = None


def _open_inset_array(inset_path):
    """Read a cached inset GeoTIFF into ``(array, geotransform, nodata)``.

    Returns ``(None, None, None)`` when GDAL is unavailable or the file
    cannot be read -- callers treat that inset as contributing no probes /
    no error (the grid decision then rests on the other insets, or falls
    back to the finest candidate).  Float32 (the storage dtype: ~0.5 mm
    resolution at terrain elevations, far inside the 1 m grid-decision
    tolerance), memoised for consecutive reads of the same unchanged
    file.
    """
    if not has_gdal:
        return (None, None, None)
    try:
        stat = os.stat(inset_path)
        memo_key = (inset_path, stat.st_mtime_ns, stat.st_size)
        memo_entry = _INSET_ARRAY_MEMO["entry"]
        if memo_entry is not None and memo_entry[0] == memo_key:
            return memo_entry[1]
        dataset = gdal.Open(inset_path)
        band = dataset.GetRasterBand(1)
        array = band.ReadAsArray().astype(numpy.float32, copy=False)
        geotransform = dataset.GetGeoTransform()
        nodata = band.GetNoDataValue()
    except Exception:
        return (None, None, None)
    _INSET_ARRAY_MEMO["entry"] = (memo_key, (array, geotransform, nodata))
    return (array, geotransform, nodata)


def _windowed_bilinear_samples(
    band, geotransform, rows, columns, longitudes, latitudes, nodata=None
):
    """Bilinear samples of a few NEARBY points via one windowed read.

    Same index math and interior clamp as :func:`_bilinear_sample_raster`
    against the FULL raster dimensions, but only the pixel window jointly
    covering the points' 2x2 bilinear cells is decoded (``ReadAsArray``
    with offsets) -- for the grid decision's probe clusters that is a few
    dozen pixels instead of a whole native-resolution inset.  Bit-identical
    to sampling a full decode.  The points must be near one another (the
    window spans their joint bounding box).

    ``nodata`` makes the sample NODATA-AWARE: a point any of whose four
    bilinear corners is a nodata sentinel returns NaN rather than a blend
    of real metres with the sentinel.  Insets routinely cover only part of
    their airport box (a 3DEP fetch over a rural strip came back 96.4%
    nodata), and blending -32768 with ~256 m produced "elevation errors"
    of 21848 m in the working-grid decision -- see the 2026-07-24 KCLT
    report.  Omitted, the behaviour is the raw historic blend.
    """
    west = geotransform[0]
    north = geotransform[3]
    pixel_width = geotransform[1]
    pixel_height = geotransform[5]  # negative for north-up
    fractional_x = (numpy.asarray(longitudes) - (west + 0.5 * pixel_width)) / pixel_width
    fractional_y = (numpy.asarray(latitudes) - (north + 0.5 * pixel_height)) / pixel_height
    column0 = numpy.clip(numpy.floor(fractional_x).astype(int), 0, columns - 2)
    row0 = numpy.clip(numpy.floor(fractional_y).astype(int), 0, rows - 2)
    tx = numpy.clip(fractional_x - column0, 0.0, 1.0)
    ty = numpy.clip(fractional_y - row0, 0.0, 1.0)
    column_start = int(column0.min())
    row_start = int(row0.min())
    window = band.ReadAsArray(
        column_start,
        row_start,
        int(column0.max()) - column_start + 2,
        int(row0.max()) - row_start + 2,
    ).astype(numpy.float32, copy=False)
    window_row = row0 - row_start
    window_column = column0 - column_start
    top_left = window[window_row, window_column]
    top_right = window[window_row, window_column + 1]
    bottom_left = window[window_row + 1, window_column]
    bottom_right = window[window_row + 1, window_column + 1]
    samples = (
        top_left * (1 - tx) * (1 - ty)
        + top_right * tx * (1 - ty)
        + bottom_left * (1 - tx) * ty
        + bottom_right * tx * ty
    )
    if nodata is not None:
        contaminated = (
            (top_left == nodata)
            | (top_right == nodata)
            | (bottom_left == nodata)
            | (bottom_right == nodata)
        )
        samples = numpy.where(contaminated, numpy.nan, samples)
    return samples


# The generic probe derivation targets TERRAIN-SCALE relief -- engineered
# embankments, plateaus and shelves a few metres tall over tens of metres,
# the class the KBNA seed probes represent -- NOT pixel-scale vertical
# discontinuities (building walls, trees) that NO working grid can resolve
# to +/-1 m and that would otherwise force every tile to the finest grid.
# So the gradient is computed on the inset BLOCK-AVERAGED to roughly the
# 1 arc-second working-pixel scale, where a resolvable embankment shows a
# strong slope and a vertical wall averages out.
PROBE_TERRAIN_SCALE_M = 30.0


def derive_acceptance_probes(inset_path, count=DERIVED_PROBE_COUNT):
    """Generic acceptance probes: the steepest TERRAIN-SCALE cells of an inset.

    Airports without a hand-seeded probe list (every non-KBNA tile) still
    need a sensible grid decision, so we probe where the inset's
    terrain-scale relief is steepest -- exactly the engineered embankments
    a coarse working grid smears worst, and the cells densifying actually
    helps.  The inset is block-averaged to roughly the working-pixel scale
    (:data:`PROBE_TERRAIN_SCALE_M`) before the gradient is taken, so
    unresolvable pixel-scale walls do not dominate.  The ``count`` strongest
    coarse cells, spread at least a tenth of the footprint apart, are
    returned as ``(latitude, longitude)`` cell-centre pairs.
    """
    (array, geotransform, nodata) = _open_inset_array(inset_path)
    if array is None:
        return []
    pixel_height_m = abs(geotransform[5]) * GEO.lat_to_m
    block = max(1, int(round(PROBE_TERRAIN_SCALE_M / max(pixel_height_m, 1e-6))))
    rows, columns = array.shape
    valid = numpy.ones(array.shape, dtype=bool)
    if nodata is not None:
        valid &= array != nodata
    # Block-mean the inset (ignoring nodata) to ~working-pixel posting.
    coarse_rows = rows // block
    coarse_columns = columns // block
    if coarse_rows < 3 or coarse_columns < 3:
        block = 1
        coarse_rows, coarse_columns = rows, columns
        coarse = numpy.where(valid, array, numpy.nan)
    else:
        trimmed = array[: coarse_rows * block, : coarse_columns * block]
        trimmed_valid = valid[: coarse_rows * block, : coarse_columns * block]
        blocks = trimmed.reshape(
            coarse_rows, block, coarse_columns, block
        )
        blocks_valid = trimmed_valid.reshape(
            coarse_rows, block, coarse_columns, block
        )
        with numpy.errstate(invalid="ignore"):
            summed = numpy.where(blocks_valid, blocks, 0.0).sum(axis=(1, 3))
            counted = blocks_valid.sum(axis=(1, 3))
            coarse = numpy.where(counted > 0, summed / numpy.maximum(counted, 1), numpy.nan)
    gradient_y, gradient_x = numpy.gradient(numpy.nan_to_num(coarse, nan=0.0))
    magnitude = numpy.hypot(gradient_x, gradient_y)
    magnitude[numpy.isnan(coarse)] = -1.0
    minimum_separation = max(1, int(0.1 * min(coarse_rows, coarse_columns)))
    order = numpy.argsort(magnitude, axis=None)[::-1]
    west = geotransform[0]
    north = geotransform[3]
    pixel_width = geotransform[1]
    pixel_height = geotransform[5]
    chosen_cells = []
    probes = []
    for flat_index in order:
        if len(probes) >= count:
            break
        coarse_row = int(flat_index // coarse_columns)
        coarse_column = int(flat_index % coarse_columns)
        if magnitude[coarse_row, coarse_column] < 0:
            break
        too_close = any(
            abs(coarse_row - r) < minimum_separation
            and abs(coarse_column - c) < minimum_separation
            for (r, c) in chosen_cells
        )
        if too_close:
            continue
        chosen_cells.append((coarse_row, coarse_column))
        # Cell centre of the coarse block, back in inset pixel coordinates.
        column = (coarse_column + 0.5) * block
        row = (coarse_row + 0.5) * block
        longitude = west + column * pixel_width
        latitude = north + row * pixel_height
        probes.append((latitude, longitude))
    return probes


def acceptance_probes_with_source(inset_path):
    """The acceptance probes for one inset plus whether they are seeded.

    Returns ``(probes, is_seeded)``.  A hand-seeded ICAO probe set (spec
    section 5) is used when the file's airport key matches AND the probes
    fall inside the inset footprint (``is_seeded=True``); otherwise probes
    are derived from the steepest terrain-scale cells (``is_seeded=False``).
    Seeded probes are the airport's acceptance requirement and always drive
    the grid decision; derived probes drive it only where densification can
    actually bring them within tolerance (see resolve_working_grid_factor).
    """
    icao = _inset_icao_from_path(inset_path)
    seeded = SEED_ACCEPTANCE_PROBES.get(icao)
    if seeded:
        (array, geotransform, nodata) = _open_inset_array(inset_path)
        if array is not None:
            rows, columns = array.shape
            west = geotransform[0]
            north = geotransform[3]
            east = west + columns * geotransform[1]
            south = north + rows * geotransform[5]
            inside = [
                (latitude, longitude)
                for (latitude, longitude) in seeded
                if west <= longitude <= east and south <= latitude <= north
            ]
            if inside:
                return (inside, True)
    return (derive_acceptance_probes(inset_path), False)


def acceptance_probes_for_inset(inset_path):
    """The acceptance probes for one cached inset (seeded or derived)."""
    return acceptance_probes_with_source(inset_path)[0]


def _inset_header_geometry(inset_path):
    """``(geotransform, rows, columns)`` from a GeoTIFF header, or ``None``.

    A header-only ``gdal.Open`` (no ``ReadAsArray``): enough for footprint
    checks without paying a full raster decode.
    """
    if not has_gdal:
        return None
    try:
        dataset = gdal.Open(inset_path)
        if dataset is None:
            return None
        return (
            dataset.GetGeoTransform(),
            dataset.RasterYSize,
            dataset.RasterXSize,
        )
    except Exception:
        return None


def delivered_inset_bounding_box(inset_path):
    """The box a written inset raster ACTUALLY delivers, from its OWN
    geotransform: ``(west, south, east, north)`` in EPSG:4326, or ``None``
    when the file cannot be opened (no GDAL, absent, corrupt).

    THE MANIFEST OVERSTATES THE RASTER.  Measured 2026-09-17 over 559
    tif/manifest pairs on the shared corpus: the manifest's
    ``bounding_box_wgs84`` (the box that was REQUESTED) differs from the
    box the raster carries by a median 5.1e-6 deg and up to 2.45e-4 deg
    (~27 m, about one 30 m source pixel), in BOTH directions -- a warp
    snaps the target extent to its pixel grid, and some providers clip to
    their own coverage.  So a manifest is a record of the ASK, and only
    the file answers what was delivered.  Written alongside the requested
    box by :func:`fetch_inset` from here on.
    """
    header = _inset_header_geometry(inset_path)
    if header is None:
        return None
    (geotransform, rows, columns) = header
    west = geotransform[0]
    north = geotransform[3]
    return (west, north + rows * geotransform[5],
            west + columns * geotransform[1], north)


def _acceptance_probes_with_source_from_index(inset_path, airport_record):
    """``acceptance_probes_with_source``, preferring the index-cached list.

    The working-grid decision runs in BOTH build steps over every cached
    inset, and deriving probes there re-decoded each raster in full.  The
    fetch phase already stores each inset's derived probes in
    ``index.json`` (``_store_acceptance_probes_in_record``), so the
    decision reads them back -- trusting them only when ``"probes_for"``
    matches the file's current identity -- and falls back to a full
    derivation otherwise (legacy records upgrade on the next fetch pass).
    Seeded probes (the curated KBNA set) are re-checked against the inset
    footprint from the GeoTIFF HEADER alone: same decision, no decode.
    """
    icao = _inset_icao_from_path(inset_path)
    seeded = SEED_ACCEPTANCE_PROBES.get(icao)
    if seeded:
        header = _inset_header_geometry(inset_path)
        if header is not None:
            (geotransform, rows, columns) = header
            west = geotransform[0]
            north = geotransform[3]
            east = west + columns * geotransform[1]
            south = north + rows * geotransform[5]
            inside = [
                (latitude, longitude)
                for (latitude, longitude) in seeded
                if west <= longitude <= east and south <= latitude <= north
            ]
            if inside:
                return (inside, True)
    stored = (airport_record or {}).get("probes")
    if stored and (
        airport_record.get("probes_for") == _inset_file_identity(inset_path)
    ):
        return (
            [
                (float(latitude), float(longitude))
                for (latitude, longitude) in stored
            ],
            False,
        )
    return (derive_acceptance_probes(inset_path), False)


def ideal_bake_errors_per_probe(inset_path, probes, factor, base_geometry):
    """Modelled .alt error of an inset baked at a densified grid, per probe.

    For each probe, ``truth`` is the inset's own bilinear value there.
    ``built`` models the value the probe would read from a working raster
    posting at ``factor`` x the base grid, by walking the REAL surface
    chain end to end:

      1. the BAKE writes each surrounding working-grid node with the
         inset's BILINEAR value there (``_bake_one_inset`` via
         ``DEM.alt_vec_bilinear_strict`` -- the O1 resampling);
      2. the MESHER reads that ``.alt`` raster with TRUE BILINEAR
         interpolation across the working-grid cell
         (``Utils/src/Triangle4XP.c:3571`` ``altitude()``: corner weights
         (1-rx)(1-ry), rx(1-ry), (1-rx)ry, rx*ry).

    So the number is the grid-quantisation error the rendered mesh
    actually carries.  This model previously used a two-triangle
    (barycentric) split, described as "identical to ``DEM.alt_nostrict``";
    that was a factual error about the mesher -- Triangle4XP has never
    been a triangle-split reader, and the two interpolants differ by
    +-(t1+t2-t3-t4)/4 at the cell centre, mis-scoring every candidate
    factor by up to that much.  Returns a list of ``|built - truth|``
    aligned with ``probes`` (empty when the inset is unreadable).

    LIMIT, stated honestly: step 1 is modelled as bilinear for every
    inset, while the bake AREA-AVERAGES an inset that is FINER than the
    working grid (the ``"area"`` mode).  Modelling the box filter here
    would need a full window read per candidate node instead of four
    point samples, and the two agree wherever the inset is smooth at the
    grid scale; where they differ the box filter is the SMOOTHER of the
    two, so the ballot's error is the conservative (larger) figure and can
    only ever err towards a finer grid.

    ``base_geometry`` is ``(x0, x1, y0, y1, nxdem, nydem)`` of the base
    working grid in tile-relative degrees; the densified node spacing is
    that grid refined by ``factor``.  Probes carry both tile-relative and
    absolute coordinates (the geometry math and the inset sampling each get
    the frame they need -- see resolve_working_grid_factor).

    Each probe needs only its own bilinear value plus the four surrounding
    working-grid nodes' -- five sample points within one working-grid cell
    -- so the raster is read through per-probe pixel WINDOWS
    (``_windowed_bilinear_samples``), never decoded in full.
    """
    if not has_gdal or not probes:
        return []
    try:
        dataset = gdal.Open(inset_path)
        if dataset is None:
            return []
        band = dataset.GetRasterBand(1)
        geotransform = dataset.GetGeoTransform()
        rows = dataset.RasterYSize
        columns = dataset.RasterXSize
        nodata = band.GetNoDataValue()
    except Exception:
        return []
    (x0, x1, y0, y1, nxdem, nydem) = base_geometry
    dense_columns = (nxdem - 1) * factor + 1
    dense_rows = (nydem - 1) * factor + 1
    x_step = (x1 - x0) / (dense_columns - 1)
    y_step = (y1 - y0) / (dense_rows - 1)

    errors = []
    try:
        for (relative_x, relative_y, longitude, latitude) in probes:
            # Working-grid cell containing the probe (row grows southward).
            column_index = (relative_x - x0) / x_step
            row_index = (y1 - relative_y) / y_step
            column0 = int(numpy.floor(column_index))
            row0 = int(numpy.floor(row_index))
            rx = column_index - column0
            ry = row_index - row0

            # The probe itself plus its four surrounding working-grid
            # nodes: one windowed read covers all five sample points.
            sample_longitudes = [longitude]
            sample_latitudes = [latitude]
            for (column, row) in (
                (column0, row0),
                (column0 + 1, row0),
                (column0, row0 + 1),
                (column0 + 1, row0 + 1),
            ):
                sample_longitudes.append(
                    longitude + ((x0 + column * x_step) - relative_x)
                )
                sample_latitudes.append(
                    latitude + ((y1 - row * y_step) - relative_y)
                )
            values = _windowed_bilinear_samples(
                band,
                geotransform,
                rows,
                columns,
                sample_longitudes,
                sample_latitudes,
                nodata=nodata,
            )
            if not numpy.all(numpy.isfinite(values)):
                # The probe or one of its surrounding working-grid nodes
                # lands on a nodata hole: the inset carries no surface
                # there for a bake to quantise, so this factor is simply
                # NOT MEASURABLE at this probe.  NaN keeps the returned
                # list aligned with ``probes`` (callers index into it) and
                # is filtered where the errors are compared.
                errors.append(float("nan"))
                continue
            truth = float(values[0])
            top_left = float(values[1])
            top_right = float(values[2])
            bottom_left = float(values[3])
            bottom_right = float(values[4])
            # TRUE BILINEAR -- the interpolation Triangle4XP.altitude()
            # applies to the .alt raster (rx eastward, ry southward, row 0
            # being the northern edge exactly as there).
            built = (
                top_left * (1 - rx) * (1 - ry)
                + top_right * rx * (1 - ry)
                + bottom_left * (1 - rx) * ry
                + bottom_right * rx * ry
            )
            errors.append(abs(built - truth))
    except Exception:
        return []
    return errors


def ideal_bake_error_at_probes(inset_path, probes, factor, base_geometry):
    """Worst MEASURABLE modelled .alt error over the probes.

    Probes the model cannot evaluate (a nodata hole under the probe or its
    working-grid neighbours -- NaN from the per-probe variant) are skipped:
    ``0.0`` when nothing is measurable, matching the no-probe case.
    """
    errors = [
        error
        for error in ideal_bake_errors_per_probe(
            inset_path, probes, factor, base_geometry
        )
        if not math.isnan(error)
    ]
    return max(errors) if errors else 0.0


def _base_geometry_of_dem(dem):
    """Extract ``(x0, x1, y0, y1, nxdem, nydem)`` from a loaded base DEM."""
    return (dem.x0, dem.x1, dem.y0, dem.y1, dem.nxdem, dem.nydem)


def resolve_working_grid_factor(tile, base_dem):
    """Choose the working-grid densification factor for a tile.

    Returns the historic airport-inset decision (1, 2 or 3) RAISED, never
    lowered, by any numeric ``elevation_level`` override:
    ``max(historic_factor, level_factor)`` (spec section 3.2).  An explicit
    non-auto ``working_grid_arc_seconds`` pin still wins outright, and when
    ``elevation_level`` is auto/invalid the return is behaviourally
    IDENTICAL to the historic decision (the byte-inert auto path).
    """
    historic = _historic_working_grid_factor(tile, base_dem)
    configured = parse_working_grid_arc_seconds(
        getattr(tile, "working_grid_arc_seconds", "auto")
    )
    if configured != "auto":
        # An explicit working-grid pin governs the grid outright; the
        # elevation-level override never overrules a user pin.
        return historic
    # Lazy import keeps both directions of the O4_Elevation_Level <-> this
    # module dependency lazy (that module lazily imports this one too).
    import O4_Elevation_Level as ELEVATION_LEVEL

    raw_level_value = getattr(tile, "elevation_level", "auto")
    if ELEVATION_LEVEL.is_coastline_mode(raw_level_value):
        # "Auto + coastline": the factor comes from the band stamp written
        # by ensure_coastline_band (disk-state-driven, so both build steps
        # agree; 1 while no band has been fetched -> historic unchanged).
        if not ELEVATION_LEVEL.has_gdal:
            return historic
        return max(historic, ELEVATION_LEVEL.coastline_grid_factor(tile))
    level = ELEVATION_LEVEL.parse_elevation_level(raw_level_value)
    if level is None or not ELEVATION_LEVEL.has_gdal:
        return historic
    if getattr(tile, "custom_dem", ""):
        # The user's pinned raster is trusted to carry the finer detail, so
        # the grid is densified to the full level factor, uncapped.
        level_factor = ELEVATION_LEVEL.LEVEL_GRID_FACTORS[level]
    else:
        level_factor = ELEVATION_LEVEL.grid_factor_for_level(
            level,
            ELEVATION_LEVEL.finest_wide_area_resolution_m(
                tile.lat,
                tile.lon,
                getattr(tile, "airport_elevation_providers", "auto"),
            ),
        )
    return max(historic, level_factor)


def _working_grid_candidate_factors(inset_paths, base_geometry):
    """The densification factors to evaluate for a tile, coarsest first.

    ``WORKING_GRID_CANDIDATE_FACTORS`` ({1/2, 1/3} arc-second) with ``1``
    -- no densification -- PREPENDED when no cached inset on the tile
    carries data finer than the base grid already holds
    (:data:`BASE_CLASS_INSET_RATIO`).

    The spec's candidate set floors at 1/2 arc-second because the feature
    was designed around meter-class lidar insets: if you fetched one, the
    airport has detail worth a denser grid.  The global 30 m radar
    fallback rides the same path, and for a tile whose only insets are
    that coarse there is nothing for densification to carry -- so "keep 1
    arc-second" belongs on the ballot.  It still has to WIN on the same
    ideal-bake measurement as every other candidate, so a base-class tile
    whose relief genuinely needs a denser grid (Nyquist against a 30.87 m
    posting costs 1-2 m on real 30 m terrain) still densifies.  A tile
    with any finer inset never even offers the coarse option, so lidar
    airports are untouched.
    """
    if not inset_paths:
        return WORKING_GRID_CANDIDATE_FACTORS
    (_x0, _x1, y0, y1, _nxdem, nydem) = base_geometry
    if nydem < 2:
        return WORKING_GRID_CANDIDATE_FACTORS
    base_pixel_m = abs(y1 - y0) / (nydem - 1) * GEO.lat_to_m
    finest_m = None
    for inset_path in inset_paths:
        resolution_m = _honest_inset_resolution_m(inset_path)
        if resolution_m is None:
            # An unreadable inset cannot be vouched for as base-class.
            return WORKING_GRID_CANDIDATE_FACTORS
        finest_m = (
            resolution_m if finest_m is None else min(finest_m, resolution_m)
        )
    if finest_m is None or finest_m < base_pixel_m * BASE_CLASS_INSET_RATIO:
        return WORKING_GRID_CANDIDATE_FACTORS
    return (1,) + tuple(WORKING_GRID_CANDIDATE_FACTORS)


# =====================================================================
# SEAM FACTOR HARMONIZATION (O3) -- owner ruling 2026-07-25
# =====================================================================
# RULE: adjacent tiles that share a seam-straddling inset MUST resolve
# IDENTICAL working-grid factors.
#
# Why it is not optional.  SPLP's inset (W-77.0282 .. W-76.9750) crosses
# the lon = -77 tile seam and is cached under BOTH S13W077 and S13W078.
# Balloted independently the two tiles picked 1/3" (11017^2) and 1/2"
# (7345^2).  Their baked rasters agree EXACTLY where their postings
# coincide (225 exactly-shared posts, 0.0000 m), but the surface a mesh
# renders is the BILINEAR interpolant BETWEEN posts -- and bilinear
# between DIFFERENT post sets straddling the same escarpment diverges by
# up to 3.7995 m (p90 0.36 m) along the seam.  That is a visible cliff in
# the rendered scenery today.  Pinning both tiles to the same factor --
# either one -- drives the seam disagreement to exactly 0.0000 m.
#
# HOW the two sides are made to agree, without either knowing about the
# other's build.  Both extend _historic_working_grid_factor's stated
# principle (the decision is DISK-STATE DRIVEN, so any two callers on the
# same disk state agree): the ballot runs over the MERGED cached inset
# sets of the whole seam-connected COMPONENT of tiles, not just the
# tile's own.  Because the adjacency relation is symmetric by
# construction and the merge is a deterministic function of the component
# (sorted, deduplicated by cache-file name), every member of a component
# assembles the SAME ballot and therefore returns the SAME factor.
#
#   adjacency(A, B) := A and B are 4-neighbours
#                      AND some inset cached under A *or* under B has a
#                          footprint crossing their shared edge.
#
# The "or" is what makes it symmetric, and it costs nothing: a straddling
# inset is fetched footprint-first, so it is normally cached under both
# sides anyway (SPLP's two copies are byte-identical).
#
# TERMINATION.  The traversal only enters a tile that has a NON-EMPTY
# cached inset directory on disk; ``component`` never re-admits a tile;
# the set of such directories is finite and fixed for the duration of one
# ballot.  So the frontier empties after at most that many expansions.
# The explicit SEAM_HARMONIZATION_COMPONENT_LIMIT is a runtime guard, not
# a correctness one -- and because "the component exceeds the limit" is a
# property of the component rather than of the traversal's starting
# point, every member reaches the same fallback decision.
#
# KNOWN LIMITS, stated rather than hidden:
#  * a neighbour that has NEVER been fetched contributes nothing (it has
#    no cache); when it is built later it will see this tile's cache and
#    harmonize to it, but this tile -- already built -- will not be
#    revisited.  Rebuild order therefore still matters for a first-ever
#    build of one side only;
#  * the component is listed with the BALLOTING tile's provider codes, so
#    two neighbours configured with different ``airport_elevation_providers``
#    can still disagree.  That configuration is global in practice.
#
# GATE ``O4_INSET_SEAM_HARMONIZE`` (default "1" = ON); "0" restores the
# per-tile ballot exactly.
SEAM_HARMONIZATION_COMPONENT_LIMIT = 32


def seam_harmonization_enabled():
    """True when the ballot merges seam-neighbour inset sets (default ON)."""
    return os.environ.get("O4_INSET_SEAM_HARMONIZE", "1") == "1"


def _inset_footprint_degrees(inset_path):
    """``(west, south, east, north)`` of a cached inset, absolute degrees.

    Header-only (no raster decode); ``None`` when the file cannot be read.
    """
    header = _inset_header_geometry(inset_path)
    if header is None:
        return None
    (geotransform, rows, columns) = header
    west = geotransform[0]
    north = geotransform[3]
    east = west + columns * geotransform[1]
    south = north + rows * geotransform[5]
    return (
        min(west, east),
        min(south, north),
        max(west, east),
        max(south, north),
    )


def _footprint_crosses_meridian(footprint, longitude, south, north):
    """The footprint straddles ``longitude`` over the ``[south, north]`` edge."""
    return (
        footprint[0] < longitude < footprint[2]
        and footprint[1] < north
        and footprint[3] > south
    )


def _footprint_crosses_parallel(footprint, latitude, west, east):
    """The footprint straddles ``latitude`` over the ``[west, east]`` edge."""
    return (
        footprint[1] < latitude < footprint[3]
        and footprint[0] < east
        and footprint[2] > west
    )


def _seam_neighbour_tiles(lat, lon, footprints_of):
    """Neighbours of ``(lat, lon)`` across a seam an inset footprint crosses.

    ``footprints_of(lat, lon)`` yields that tile's cached inset footprints.
    A neighbour with NO cached inset is skipped: it has nothing to merge
    and no inset of its own to carry the component further.  The crossing
    test unions BOTH tiles' footprints, which is what makes the relation
    symmetric (and hence the component identical from either side).
    """
    own = footprints_of(lat, lon)
    found = []
    for (neighbour, axis, value) in (
        ((lat, lon - 1), "lon", lon),
        ((lat, lon + 1), "lon", lon + 1),
        ((lat - 1, lon), "lat", lat),
        ((lat + 1, lon), "lat", lat + 1),
    ):
        other = footprints_of(*neighbour)
        if not other:
            continue
        if axis == "lon":
            crosses = any(
                _footprint_crosses_meridian(
                    footprint, value, lat, lat + 1
                )
                for footprint in own + other
            )
        else:
            crosses = any(
                _footprint_crosses_parallel(
                    footprint, value, lon, lon + 1
                )
                for footprint in own + other
            )
        if crosses:
            found.append(neighbour)
    return sorted(found)


def seam_harmonized_ballot_insets(lat, lon, provider_codes):
    """The inset set the working-grid ballot runs over, seam-harmonized.

    Returns a list of ``(inset_path, owner_lat, owner_lon)``, sorted by
    cache-file name and deduplicated by it, covering this tile plus every
    tile in its seam-connected component (see the section comment above).
    ``owner_lat``/``owner_lon`` name the tile whose ``index.json`` holds
    that inset's cached acceptance probes.

    Degrades to this tile's own insets -- the pre-O3 behaviour -- when the
    gate is off, GDAL is missing (no footprints readable), the tile has no
    inset, or the component exceeds
    :data:`SEAM_HARMONIZATION_COMPONENT_LIMIT`.
    """
    own = list_cached_inset_dems(lat, lon, provider_codes=provider_codes)
    solo = [(path, lat, lon) for path in own]
    if not own or not has_gdal or not seam_harmonization_enabled():
        return solo

    listing_memo = {}
    footprint_memo = {}

    def _insets_of(tile_lat, tile_lon):
        key = (tile_lat, tile_lon)
        if key not in listing_memo:
            listing_memo[key] = list_cached_inset_dems(
                tile_lat, tile_lon, provider_codes=provider_codes
            )
        return listing_memo[key]

    def _footprints_of(tile_lat, tile_lon):
        key = (tile_lat, tile_lon)
        if key not in footprint_memo:
            footprint_memo[key] = [
                footprint
                for footprint in (
                    _inset_footprint_degrees(path)
                    for path in _insets_of(tile_lat, tile_lon)
                )
                if footprint is not None
            ]
        return footprint_memo[key]

    component = {(lat, lon)}
    frontier = [(lat, lon)]
    overflowed = False
    while frontier:
        (current_lat, current_lon) = frontier.pop(0)
        for neighbour in _seam_neighbour_tiles(
            current_lat, current_lon, _footprints_of
        ):
            if neighbour in component:
                continue
            if len(component) >= SEAM_HARMONIZATION_COMPONENT_LIMIT:
                overflowed = True
                continue
            component.add(neighbour)
            frontier.append(neighbour)
    if overflowed:
        UI.vprint(
            1,
            "   WARNING: airport elevation insets: more than",
            SEAM_HARMONIZATION_COMPONENT_LIMIT,
            "tiles are chained by seam-straddling insets around",
            FNAMES.hem_latlon(lat, lon)
            + "; skipping working-grid seam harmonization for this tile.",
        )
        return solo
    if len(component) == 1:
        return solo

    merged = []
    seen = set()
    for (tile_lat, tile_lon) in sorted(component):
        for path in _insets_of(tile_lat, tile_lon):
            name = os.path.basename(path)
            if name in seen:
                continue
            seen.add(name)
            merged.append((path, tile_lat, tile_lon))
    merged.sort(key=lambda entry: os.path.basename(entry[0]))
    UI.vprint(
        2,
        "   Airport elevation insets: working-grid ballot harmonized over",
        len(component),
        "seam-connected tiles (" + ", ".join(
            FNAMES.hem_latlon(t_lat, t_lon)
            for (t_lat, t_lon) in sorted(component)
        ) + ");",
        len(merged),
        "inset(s) on the ballot.",
    )
    return merged


def _historic_working_grid_factor(tile, base_dem):
    """The pre-elevation-level working-grid decision (1, 2 or 3).

    The decision is deterministic and disk-state-driven (both build steps
    call it on the same cached insets and the same base geometry), so
    steps 1 and 2 always agree on the grid.  Returns ``1`` -- the
    byte-identical 1 arc-second path -- whenever the feature is gated off,
    GDAL is missing, no inset is cached, or the config pins ``"1"``.  An
    explicit ``"1/2"`` / ``"1/3"`` pin is honoured outright.  In ``"auto"``
    mode with insets present it evaluates the ideal-bake error over every
    cached inset's acceptance probes and returns the COARSEST candidate
    factor whose worst error is within WORKING_GRID_IDEAL_TOLERANCE_M,
    falling back to the finest candidate if none qualifies.  The candidate
    set includes ``1`` when no inset is finer than the base grid (see
    :func:`_working_grid_candidate_factors`), so a tile carrying only the
    30 m global fallback can decline densification on measurement.

    SEAM HARMONIZATION (O3): the ballot runs over
    :func:`seam_harmonized_ballot_insets` -- this tile's cached insets
    PLUS those of every tile chained to it by a seam-straddling inset
    footprint -- so two neighbours sharing such an inset provably resolve
    the SAME factor and their rendered surfaces meet at the seam.  The
    BAKE is untouched: a tile still bakes only its own cached insets.
    """
    if not insets_enabled_for_tile(tile):
        return 1
    configured = parse_working_grid_arc_seconds(
        getattr(tile, "working_grid_arc_seconds", "auto")
    )
    provider_definitions = select_provider_definitions(
        getattr(tile, "airport_elevation_providers", "auto")
    )
    codes = [definition["code"] for definition in provider_definitions]
    inset_paths = list_cached_inset_dems(
        tile.lat, tile.lon, provider_codes=codes or None
    )
    if not inset_paths:
        return 1
    if configured != "auto":
        return configured
    base_geometry = _base_geometry_of_dem(base_dem)
    finest_factor = WORKING_GRID_CANDIDATE_FACTORS[-1]
    tolerance = WORKING_GRID_IDEAL_TOLERANCE_M

    # The BALLOT set (O3) -- this tile's insets plus every seam-connected
    # neighbour's, so both sides of a straddling inset decide alike.  The
    # BAKE set (``inset_paths`` above) is untouched.
    ballot_insets = seam_harmonized_ballot_insets(
        tile.lat, tile.lon, codes or None
    )
    ballot_paths = [path for (path, _lat, _lon) in ballot_insets]

    # Assemble every probe once, carrying its tile-relative and absolute
    # coordinates (the geometry math and the inset sampling each need one
    # frame) plus whether it is a hand-seeded acceptance probe.  Probes
    # come back from the inset index where the fetch phase cached them
    # (derivation is only the fallback for legacy/foreign records), so in
    # the common case no inset raster is decoded in full here.  A merged-in
    # neighbour's probes come from THAT tile's index, and its probe
    # coordinates are expressed in THIS tile's frame -- the working grids
    # of adjacent tiles share one lattice, so the modelled quantisation
    # error of a given probe is the same number on either side.
    index_memo = {}

    def _index_for(owner_lat, owner_lon):
        key = (owner_lat, owner_lon)
        if key not in index_memo:
            index_memo[key] = _read_index(owner_lat, owner_lon)
        return index_memo[key]

    all_probes = []  # (inset_path, adjusted_probe, is_seeded)
    for (inset_path, owner_lat, owner_lon) in ballot_insets:
        (probes, is_seeded) = _acceptance_probes_with_source_from_index(
            inset_path,
            _index_for(owner_lat, owner_lon).get(
                _inset_icao_from_path(inset_path)
            ),
        )
        for (latitude, longitude) in probes:
            all_probes.append(
                (
                    inset_path,
                    (
                        longitude - tile.lon,
                        latitude - tile.lat,
                        longitude,
                        latitude,
                    ),
                    is_seeded,
                )
            )
    if not all_probes:
        # Insets present but no probes derivable -> take the finest grid
        # (the data is there; be safe rather than leave it on the floor).
        _release_inset_array_memo()
        return finest_factor

    # A tile with a CURATED seed set (KBNA, spec section 5) is decided by
    # those probes ALONE: the seed set is the acceptance requirement for
    # the tile, and letting an arbitrary co-tile rural strip's steepest
    # slope override it would ignore the curation.  DERIVED probes are the
    # generic fallback for tiles nobody has seeded.
    if any(is_seeded for (_, _, is_seeded) in all_probes):
        all_probes = [
            probe for probe in all_probes if probe[2]  # is_seeded
        ]

    # Per-probe error at every candidate factor.  A DERIVED probe that
    # stays above tolerance even at the FINEST candidate models relief no
    # working grid resolves to +/-1 m (a natural cliff, a data spike); it
    # must NOT drive the grid finer, since no candidate would satisfy it,
    # and letting it would force every steep tile to the max grid.  Seeded
    # acceptance probes are the airport's requirement and always count.
    # Iterated inset-major (all factors for one inset, then the next);
    # per-factor lists stay inset-major and therefore aligned with
    # all_probes exactly as a factor-major loop would produce them.  The
    # error model reads only small pixel windows around each probe, so no
    # full inset decode happens in this loop.
    candidate_factors = _working_grid_candidate_factors(
        ballot_paths, base_geometry
    )
    errors_by_factor = {factor: [] for factor in candidate_factors}
    for (inset_path, probes) in _group_probes_by_inset(all_probes):
        for factor in candidate_factors:
            errors_by_factor[factor].extend(
                ideal_bake_errors_per_probe(
                    inset_path, probes, factor, base_geometry
                )
            )
    _release_inset_array_memo()
    finest_errors = errors_by_factor[finest_factor]
    seeded_flags = [is_seeded for (_, _, is_seeded) in all_probes]
    # A NaN finest-factor error is a probe the model cannot evaluate at all
    # (nodata under it or its working-grid neighbours); it carries no
    # requirement, so it is not actionable.
    actionable = [
        seeded or (not math.isnan(finest_error)
                   and finest_error <= tolerance)
        for (seeded, finest_error) in zip(seeded_flags, finest_errors)
    ]
    if not any(actionable):
        return finest_factor
    for factor in candidate_factors:  # coarsest first
        # NaN again means "no evidence about this factor from this probe"
        # rather than a failure: a nodata hole has no inset surface for the
        # grid to lose, and the bake falls back to base there.
        measurable = [
            error
            for (error, keep) in zip(errors_by_factor[factor], actionable)
            if keep and not math.isnan(error)
        ]
        worst = max(measurable) if measurable else 0.0
        if worst <= tolerance:
            if factor == 1:
                UI.vprint(
                    1,
                    "   Airport elevation insets: working grid kept at 1"
                    " arc-second (no cached inset is finer than the base"
                    " grid; worst actionable ideal-bake error "
                    + str(round(worst, 3))
                    + " m).",
                )
                return factor
            UI.vprint(
                1,
                "   Airport elevation insets: working grid densified to 1/"
                + str(factor)
                + " arc-second (worst actionable ideal-bake error "
                + str(round(worst, 3))
                + " m).",
            )
            return factor
    UI.vprint(
        1,
        "   Airport elevation insets: working grid densified to the finest "
        "1/"
        + str(finest_factor)
        + " arc-second (no coarser candidate met the "
        + str(tolerance)
        + " m tolerance).",
    )
    return finest_factor


def _group_probes_by_inset(all_probes):
    """Group ``(inset_path, adjusted_probe, is_seeded)`` by inset path.

    Preserves order so the flattened per-probe error lists stay aligned
    with ``all_probes`` (both iterate insets then probes in the same
    order).
    """
    grouped = []
    for (inset_path, adjusted_probe, _is_seeded) in all_probes:
        if grouped and grouped[-1][0] == inset_path:
            grouped[-1][1].append(adjusted_probe)
        else:
            grouped.append((inset_path, [adjusted_probe]))
    return [(path, probes) for (path, probes) in grouped]


def resample_grid_by_factor(array, factor):
    """Bilinearly resample a 2-D grid to ``factor`` x its resolution.

    A new grid of ``(rows - 1) * factor + 1`` by ``(columns - 1) * factor
    + 1`` samples over the SAME extent; the four corners and every original
    node are preserved exactly (integer-factor, endpoint-anchored bilinear),
    so the densified base carries no new invented relief -- the added
    detail comes only from the insets baked at the finer posting.  Done as
    two separable 1-D passes to keep the peak memory to one intermediate.
    """
    if factor == 1:
        return array
    array = numpy.ascontiguousarray(array, dtype=numpy.float32)

    def _upsample_axis(source, axis):
        length = source.shape[axis]
        new_length = (length - 1) * factor + 1
        target_indices = numpy.arange(new_length)
        lower = numpy.minimum(target_indices // factor, length - 2)
        fraction = (target_indices - lower * factor) / float(factor)
        lower_slice = numpy.take(source, lower, axis=axis)
        upper_slice = numpy.take(source, lower + 1, axis=axis)
        shape = [1] * source.ndim
        shape[axis] = new_length
        fraction = fraction.reshape(shape).astype(numpy.float32)
        return lower_slice * (1.0 - fraction) + upper_slice * fraction

    densified = _upsample_axis(array, 1)
    densified = _upsample_axis(densified, 0)
    return densified.astype(numpy.float32)


def densify_tile_dem_for_insets(tile):
    """Densify ``tile.dem`` onto the Phase C1 working grid, in place.

    Called immediately after the base DEM is loaded in BOTH build steps.
    A no-op -- and a byte-identical build -- when the resolved factor is 1
    (feature gated off, GDAL missing, no inset cached, or the grid pinned
    to 1 arc-second).  With a factor of 2 or 3 it rewrites ``nxdem`` /
    ``nydem`` (and, for a full load, resamples ``alt_dem``) so the extent
    is unchanged but the posting is finer; the subsequent inset bake and
    ``.alt`` write then land at that finer posting, and the info-only step
    2 load sees matching dimensions for its raster-size check.  Returns the
    factor applied.
    """
    if tile.dem is None:
        return 1
    factor = resolve_working_grid_factor(tile, tile.dem)
    if factor == 1:
        return 1
    tile.dem.nxdem = (tile.dem.nxdem - 1) * factor + 1
    tile.dem.nydem = (tile.dem.nydem - 1) * factor + 1
    if tile.dem.alt_dem is not None:
        tile.dem.alt_dem = resample_grid_by_factor(tile.dem.alt_dem, factor)
    tile.working_grid_factor = factor
    return factor

# Legacy short keywords (the O4_DEM_Utils.available_sources tokens and
# hence every existing tile config) resolving onto registry codes.
# "View" is special-cased in resolve_base_definition: it picks the
# 1 arc-second archive where its zone list covers, else 3 arc-second --
# exactly the choice the legacy code made inside ensure_elevation.
LEGACY_BASE_KEYWORD_ALIASES = {
    "SRTM": "SRTM",
    "ALOS": "ALOS",
    "NED1": "NED1",
    "NED1/3": "NED13",
}


def select_base_definitions_auto(lat, lon, prefer_coarse=False):
    """Rank the automatic base-source candidates for one tile.

    Enabled ``role=base`` definitions COVERING the tile, ranked by
    descending priority, CAPPED at 1 arc-second: the working mesh grid is
    3601 per degree (1 arc-second), so tile-wide data finer than that
    (e.g. the 1/3 arc-second national dataset) is wasted download and
    memory and is never auto-picked -- it stays selectable explicitly.
    A definition without a declared ``resolution_arc_seconds`` is
    excluded from auto (conservative), still selectable explicitly.

    ``prefer_coarse`` (the ``elevation_level`` auto/"90" base-class
    preference, see :func:`O4_Elevation_Level.base_prefers_coarse`)
    ranks the 3 arc-second tier FIRST -- much smaller downloads, with
    the visible detail carried by the airport insets -- keeping the
    finer tier as the fallback where no 3 arc-second source covers.
    """
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    candidates = []
    for definition in elevation_providers_dict.values():
        if definition.get("role") != ROLE_BASE:
            continue
        if not definition.get("enabled", True):
            continue
        resolution = definition.get("resolution_arc_seconds")
        if resolution is None or resolution < 1.0:
            continue
        strategy_factory = ACCESS_STRATEGIES.get(
            definition.get("access_strategy")
        )
        if strategy_factory is None:
            continue
        if not strategy_factory().covers(definition, lat, lon):
            continue
        candidates.append(definition)
    candidates.sort(
        key=lambda definition: (
            (
                0
                if not prefer_coarse
                or definition.get("resolution_arc_seconds", 0.0) >= 3.0
                else 1
            ),
            -definition.get("priority", 0.0),
            definition["code"],
        )
    )
    return candidates


def resolve_base_definition(lat, lon, selector="auto", prefer_coarse=False):
    """Resolve the base-source selector to one role=base definition.

    ``selector`` is the ``base_elevation_source`` config value, a registry
    CODE, or a legacy short keyword:

    * ``"auto"`` -- best automatic candidate (see
      :func:`select_base_definitions_auto`), or ``None`` when nothing
      covers the tile.
    * ``"View"`` -- the 1 arc-second Viewfinderpanoramas definition where
      its zone list covers this tile, else the 3 arc-second one: exactly
      the per-tile choice the legacy ensure_elevation made (including the
      Wellington exclusion, now the ``exclude_tiles`` field).
    * ``"SRTM"`` / ``"ALOS"`` / ``"NED1"`` / ``"NED1/3"`` -- direct legacy
      aliases onto their registry codes.
    * any registry CODE with ``role=base`` -- returned unconditionally
      (explicit selection bypasses both the ``enabled`` flag and the
      coverage test, matching the legacy behaviour where an explicit
      keyword always attempted its download / cache read).

    ``prefer_coarse`` is the ``elevation_level`` 90 m base-class
    preference: it reranks the ``"auto"`` candidates coarse-tier-first,
    and keeps the ``"View"`` per-tile choice on the 3 arc-second archive
    inside the 1 arc-second zone whitelist ("View" is how the automatic
    ranking round-trips through the legacy long-name dispatch, so it
    must honour the preference too).  Explicit registry CODES and the
    other legacy aliases pin their exact source regardless.

    Returns ``None`` for an unknown selector.
    """
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    selector = (selector or "auto").strip()
    if selector.lower() == "auto":
        candidates = select_base_definitions_auto(
            lat, lon, prefer_coarse=prefer_coarse
        )
        return candidates[0] if candidates else None
    if selector == "View":
        one_arc_second = elevation_providers_dict.get("VIEWFINDER1")
        three_arc_second = elevation_providers_dict.get("VIEWFINDER3")
        if (
            not prefer_coarse
            and one_arc_second is not None
            and one_arc_second.get("enabled", True)
            and base_definition_covers_tile(one_arc_second, lat, lon)
        ):
            return one_arc_second
        return three_arc_second
    alias_code = LEGACY_BASE_KEYWORD_ALIASES.get(selector)
    if alias_code is not None:
        return elevation_providers_dict.get(alias_code)
    definition = elevation_providers_dict.get(selector)
    if definition is not None and definition.get("role") == ROLE_BASE:
        return definition
    return None


def base_tile_is_cached(source, lat, lon, prefer_coarse=False):
    """True when :func:`ensure_base_tile` would download NOTHING.

    The read-only twin of :func:`ensure_base_tile`: it resolves the
    source through the same :func:`resolve_base_definition` call and asks
    the same strategy for the same ``tile_cache_path``, then stops at
    :func:`cached_elevation_file_is_valid` instead of taking the file
    lock and fetching.  Feeds the parallel scheduler's fetch-admission
    predicate (docs/specs/apron-string-and-scheduling-spec.md §A.2), so
    it is filesystem-only and answers False for everything it cannot
    decide — an unknown selector, an unknown strategy, or a strategy
    that publishes no cache path.
    """
    try:
        definition = resolve_base_definition(
            lat, lon, source, prefer_coarse=prefer_coarse
        )
        if definition is None:
            return False
        strategy_factory = ACCESS_STRATEGIES.get(
            definition.get("access_strategy"))
        if strategy_factory is None:
            return False
        cache_path_of = getattr(
            strategy_factory(), "tile_cache_path", None)
        if cache_path_of is None:
            return False
        return cached_elevation_file_is_valid(
            cache_path_of(definition, lat, lon))
    except Exception:
        return False


def ensure_base_tile(source, lat, lon, verbose=True, prefer_coarse=False):
    """Ensure the whole-tile base file for a legacy keyword or CODE.

    The target of the ``O4_DEM_Utils.ensure_elevation`` shim: resolves
    the selector, dispatches the strategy's ``ensure_tile``, and preserves
    the legacy unknown-source error line and 0/1 return convention.
    ``prefer_coarse`` carries the ``elevation_level`` 90 m base-class
    preference into the selector resolution (see
    :func:`resolve_base_definition`).
    """
    definition = resolve_base_definition(
        lat, lon, source, prefer_coarse=prefer_coarse
    )
    if definition is None:
        UI.vprint(1, "   ERROR: Unknown elevation source.")
        return 0
    strategy_factory = ACCESS_STRATEGIES.get(definition.get("access_strategy"))
    if strategy_factory is None:
        UI.vprint(1, "   ERROR: Unknown elevation source.")
        return 0
    # Serialise the download-if-missing critical section across concurrent
    # tile-build processes: adjacent tiles fetch an overlapping three-by-three
    # neighbourhood and would otherwise race to download the SAME base file
    # into this shared cache (docs/specs/parallel-tile-builds.md section 3.5).
    # The lock is keyed per (base definition code, latitude, longitude) inside
    # the tile's Elevation_data block directory; only the ``.lock`` sibling is
    # created, so the lock target file itself need not exist.
    lock_target = os.path.join(
        FNAMES.Elevation_dir,
        FNAMES.round_latlon(lat, lon),
        ".lock_" + definition["code"] + "_" + FNAMES.hem_latlon(lat, lon),
    )
    os.makedirs(os.path.dirname(lock_target), exist_ok=True)
    # The double-checked-locking re-check is inherent: every strategy's
    # ensure_tile is a no-op that recycles the cached tile when it is already
    # present, so a waiter that blocked until the first downloader finished
    # simply finds the file cached and returns without re-downloading.
    with O4_File_Lock.hold_file_lock(lock_target):
        return strategy_factory().ensure_tile(definition, lat, lon, verbose)


# =====================================================================
# Offline per-tile source summary (for the GUI tile-info surface)
# =====================================================================
def summarize_tile_elevation_sources(
    lat,
    lon,
    base_selector="auto",
    inset_providers_config="auto",
    elevation_level="auto",
):
    """One offline snapshot of the elevation sources a build would use.

    Feeds the GUI's tile-info surface, so it is offline BY DESIGN:
    registry lookups, local file checks (including the manual
    drop-folder state) and the tile's cached inset ``index.json`` only
    -- never a discovery request -- making it safe to call on every
    selection change.  Returns a dictionary:

    * ``base_code`` / ``base_resolution_arc_seconds`` -- what the
      ``base_selector`` (the ``base_elevation_source`` configuration)
      resolves to for this tile right now, under the tile's
      ``elevation_level`` base-class preference (auto/"90"/"coastline"
      prefer the 90 m tier).  When it resolves nothing the historic
      fallback (Viewfinderpanoramas 3 arc-second) is reported and
      ``base_is_fallback`` is True.
    * ``inset_providers`` -- ordered ``(code, native_resolution_m)``
      for every enabled airport-inset definition whose coverage box
      reaches this tile.
    * ``fetched_airports`` / ``no_coverage_airports`` -- ground truth
      from the cached inset index when the tile has been built or
      fetched before (both ``None`` when no index exists): airports
      with a fetched inset, and airports checked against every
      provider without coverage.
    """
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    # Lazy import: O4_Elevation_Level lazily imports this module, so both
    # directions stay lazy (the resolve_working_grid_factor convention).
    import O4_Elevation_Level as ELEVATION_LEVEL

    base_definition = resolve_base_definition(
        lat,
        lon,
        base_selector,
        prefer_coarse=ELEVATION_LEVEL.base_prefers_coarse(elevation_level),
    )
    base_is_fallback = base_definition is None
    if base_definition is None:
        base_definition = elevation_providers_dict.get("VIEWFINDER3")
    tile_bounding_box = (lon, lat, lon + 1, lat + 1)
    inset_providers = [
        (
            definition["code"],
            _parse_float(definition.get("native_resolution_m")),
        )
        for definition in select_provider_definitions(
            inset_providers_config, role=ROLE_AIRPORT_INSET
        )
        if _coverage_bbox_intersects(definition, tile_bounding_box)
    ]
    fetched_airports = None
    no_coverage_airports = None
    if os.path.isfile(FNAMES.airport_inset_index(lat, lon)):
        index = _read_index(lat, lon)
        fetched_airports = 0
        no_coverage_airports = 0
        for airport_record in index.values():
            # ONE list of the bookkeeping keys (INDEX_NON_PROVIDER_KEYS):
            # this site had its own, which omitted ``probes_for`` and so
            # counted a probe identity as a provider status.
            statuses = list(provider_statuses(airport_record).values())
            if "ok" in statuses:
                fetched_airports += 1
            elif any(status == NO_COVERAGE for status in statuses):
                # ``unavailable:`` is NOT no-coverage: an airport whose
                # only records are capability skips has not been answered
                # about at all.
                no_coverage_airports += 1
    return {
        "base_code": (
            base_definition["code"] if base_definition else None
        ),
        "base_resolution_arc_seconds": (
            _parse_float(base_definition.get("resolution_arc_seconds"))
            if base_definition
            else None
        ),
        "base_is_fallback": base_is_fallback,
        "inset_providers": inset_providers,
        "fetched_airports": fetched_airports,
        "no_coverage_airports": no_coverage_airports,
    }


def _definition_resolution_m(definition):
    """A definition's ground resolution in metres (arc-seconds ~ x30)."""
    meters = _parse_float(definition.get("native_resolution_m"))
    if meters is not None:
        return meters
    arc_seconds = _parse_float(definition.get("resolution_arc_seconds"))
    if arc_seconds is not None:
        return arc_seconds * 30.0
    return None


def _finest_automatic_resolution_m(lat, lon):
    """The finest resolution any AUTOMATIC provider offers at a tile.

    "Automatic" = enabled definitions whose strategy has no manual
    workflow; base definitions count only where their real coverage
    test passes (zone whitelists included), inset definitions where
    their coverage box reaches the tile.  Returns metres, or ``None``
    when nothing automatic covers (never in practice -- the worldwide
    Viewfinderpanoramas base always does).
    """
    tile_bounding_box = (lon, lat, lon + 1, lat + 1)
    finest = None
    for definition in elevation_providers_dict.values():
        if not definition.get("enabled", True):
            continue
        # Bathymetry providers are not terrain sources (spec section 2.1);
        # their resolution must never inform the "better elevation is
        # available" comparison.
        if definition.get("role") == ROLE_BATHYMETRY:
            continue
        # Surface models (radar DSMs, building-masked only at airport
        # footprints) are a FALLBACK quality class: whatever their grid
        # size says, they never make a genuine terrain model "not
        # better", so they must not veto the affordance (the global
        # 30 m GLO-30 would otherwise suppress the ~30.9 m lidar-derived
        # Sonny drop folder over all of Europe).
        if definition.get(SURFACE_MODEL_BUILDING_MASKING):
            continue
        strategy_factory = ACCESS_STRATEGIES.get(
            definition.get("access_strategy")
        )
        if strategy_factory is None:
            continue
        if hasattr(strategy_factory(), "manual_setup_information"):
            continue
        if definition.get("role") == ROLE_BASE:
            if not base_definition_covers_tile(definition, lat, lon):
                continue
        elif not _coverage_bbox_intersects(definition, tile_bounding_box):
            continue
        meters = _definition_resolution_m(definition)
        if meters is None:
            continue
        finest = meters if finest is None else min(finest, meters)
    return finest


def manual_elevation_setup_for_tile(lat, lon):
    """The manual-download providers WORTH setting up for a tile (MODEL).

    The model half of the GUI's "better elevation is available -- here
    is how" affordance: for every ENABLED definition (base or inset
    role) whose coverage box reaches the tile and whose access
    strategy declares a manual workflow (a
    ``manual_setup_information`` method), return one entry::

        {"code", "role", "native_resolution", "download_page",
         "drop_directory", "steps": [str, ...], "already_dropped": bool}

    A manual source is offered ONLY when it is strictly FINER than the
    best automatic source covering the tile (user ruling 2026-07-15):
    a Norwegian tile already gets 1 m airport lidar automatically, so
    the 30 m Sonny drop folder is not "better" and is not suggested
    there -- while a German tile, whose best automatic source is the
    90 m worldwide base, is exactly where the suggestion belongs.

    Pure data, computed offline (registry + a directory listing) --
    the view renders it verbatim and the controller only decides WHEN
    to ask.  ``already_dropped`` lets the view drop the affordance for
    providers the user has set up (their drop folder has content).
    """
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    tile_bounding_box = (lon, lat, lon + 1, lat + 1)
    finest_automatic = _finest_automatic_resolution_m(lat, lon)
    entries = []
    for definition in sorted(
        elevation_providers_dict.values(),
        key=lambda entry: entry["code"],
    ):
        if not definition.get("enabled", True):
            continue
        # The coverage BOX is deliberately the only geographic test: a
        # manual source's covers() also requires dropped data, and this
        # affordance exists precisely for tiles where that data is
        # still missing.
        if not _coverage_bbox_intersects(definition, tile_bounding_box):
            continue
        strategy_factory = ACCESS_STRATEGIES.get(
            definition.get("access_strategy")
        )
        if strategy_factory is None:
            continue
        strategy = strategy_factory()
        if not hasattr(strategy, "manual_setup_information"):
            continue
        meters = _definition_resolution_m(definition)
        if (
            finest_automatic is not None
            and meters is not None
            and finest_automatic <= meters
        ):
            continue
        information = strategy.manual_setup_information(definition)
        if information is not None:
            entries.append(information)
    return entries


def tiles_with_inset_coverage(tiles, inset_providers_config="auto"):
    """The subset of ``(lat, lon)`` tiles any inset provider reaches.

    Pure bounding-box arithmetic against the enabled airport-inset
    definitions -- no file or network access -- so the GUI can call it
    for arbitrarily large selections.
    """
    if not elevation_providers_dict:
        initialize_elevation_providers_dict()
    definitions = select_provider_definitions(
        inset_providers_config, role=ROLE_AIRPORT_INSET
    )
    covered = []
    for (lat, lon) in tiles:
        tile_bounding_box = (lon, lat, lon + 1, lat + 1)
        if any(
            _coverage_bbox_intersects(definition, tile_bounding_box)
            for definition in definitions
        ):
            covered.append((lat, lon))
    return covered
