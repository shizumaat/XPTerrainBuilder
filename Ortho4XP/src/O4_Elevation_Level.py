"""Tile-wide elevation detail level (the elevation analogue of imagery zoom).

Implements ``docs/specs/elevation-level-spec.md``: the per-tile
``elevation_level`` configuration value ("auto", "30", "10", "5", "1")
selects a tile-wide elevation overlay fetched through the declarative
provider registry of :mod:`O4_Airport_Elevation_Insets`, and drives the
working-grid densification factor.  ``auto`` is byte-inert: every entry
point returns immediately and the historic behaviour is untouched.

Import discipline: :mod:`O4_Airport_Elevation_Insets` is imported lazily
inside functions (it lazily imports this module from
``resolve_working_grid_factor``; keeping both directions lazy avoids any
import-order trap).  No GUI toolkit imports, per the core-module rule.
"""

import datetime
import json
import os

import numpy

try:
    from osgeo import gdal

    has_gdal = True
    gdal.UseExceptions()
except Exception:
    has_gdal = False

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_UI_Utils as UI

# Level (metres) -> working-grid densification factor (grid spacing is
# 1/factor arc-seconds).  The "1" level carries meter-class sources on a
# 1/9 arc-second grid (~3.4 m posting), the practical whole-tile ceiling
# for the in-memory raster architecture (spec section 2, honesty rule).
LEVEL_GRID_FACTORS = {30: 1, 10: 3, 5: 6, 1: 9}

# Factors a numeric level may select, coarsest first, for the data cap.
_CAP_CANDIDATE_FACTORS = (1, 3, 6, 9)

# Tolerated posting-vs-source slack in the data cap: a 1/3 arc-second
# grid (10.3 m posting) is allowed to carry a 10 m source.
_POSTING_SLACK = 1.15

# Cells of blend payload per bake strip (bounds bake memory at any grid
# factor); module-level so tests can force multi-strip processing on
# small synthetic rasters.
STRIP_CELL_BUDGET = 4_000_000

# The "90" level selects the 90 m (3 arc-second) BASE class rather than
# a wide-area overlay: it is what "auto" does by default, pinned
# explicitly.  It carries no grid factor and fetches nothing extra, so
# the numeric-level machinery treats it like auto.
BASE_90M_VALUE = "90"

# --- "Auto + coastline" mode (spec section 3.4) -----------------------
COASTLINE_MODE_VALUE = "coastline"

# Band decomposition: the coastline band is fetched as 0.1 degree cells
# of the tile whose centre lies within the configured band width (plus
# the cell half-diagonal) of the OpenStreetMap coastline.
COASTLINE_CELL_DEGREES = 0.1

# Approach-visibility ladder: per-cell warp resolution from the distance
# to the nearest airport bounding box on the tile.  On a 3 degree
# glideslope, 20 km out is roughly 11 nautical miles / 3,400 feet above
# ground (10 m detail plainly visible), 50 km out is roughly 8,500 feet,
# and beyond that sits the 15,000-feet-and-above regime where 1
# arc-second posting suffices -- far cells still buy lidar's vertical
# accuracy on the shoreline, where global bases are at their worst.
COASTLINE_NEAR_AIRPORT_KM = 20.0
COASTLINE_MID_AIRPORT_KM = 50.0
COASTLINE_MID_RESOLUTION_M = 20.0

# --- Approach-graded elevation rings (docs/specs/approach-graded-
# elevation-rings-spec.md; owner RULINGS 2026-10-01g/h) ---------------
#
# The coastline band's approach-visibility grading GENERALISED (the
# owner's words: it "is THE RULE TO GENERALISE, not a parallel one"):
# a tile-wide distance-graded overlay around every airport that holds an
# inset, measured from the AERODROME BOUNDARY polygon -- never the ARP,
# never the inset box.
#
# Each ladder rung is ``(reach_m, rung)``, coarsest reach last.  ``rung``
# is either an int WORKING-GRID FACTOR (whose posting is the warp target,
# :func:`grid_posting_metres`) or a float resolution in metres.  ONE
# grading function (:func:`approach_class`) reads both tables.
APPROACH_RING_LADDER = ((10_000.0, 3), (20_000.0, 1))

# The coastline band's own table, VALUES UNCHANGED (spec question Q2:
# keep both tables, one function, until a coastline-mode sim read).
COASTLINE_APPROACH_LADDER = (
    (COASTLINE_NEAR_AIRPORT_KM * 1000.0, 3),
    (COASTLINE_MID_AIRPORT_KM * 1000.0, COASTLINE_MID_RESOLUTION_M),
    (float("inf"), 1),
)

# A FEATHER IS A NUMBER OF POSTINGS OF THE COARSER SIDE, never a fixed
# metre count.  The 60 m feather was sized for the 1 m -> 10 m seam (6
# postings of the coarser class) and was then reused at a 10 m -> 90 m
# seam where it is 0.65 of ONE posting -- that is the measured defect
# (spec section 0 fact 1: a 33.1 % worst transition grade at the inset
# box edge, exactly ``emit.design.bank_slope``, which is why a 60 m band
# of it drawn as a rectangle around the airport reads as a built edge).
APPROACH_RING_FEATHER_POSTINGS = 10

# The BASE class ring 2 feathers out into: 3 arc-second posting (the
# VIEWFINDER3 / SRTM3 class ``auto`` takes by default).
BASE_CLASS_ARC_SECONDS = 3

# A feather is rounded to this grid so the law carries ROUND NUMBERS
# (10 x 30.9 m -> 300 m, 10 x 92.8 m -> 900 m) rather than the posting
# arithmetic's digits; a raw width below one step is kept as it is.
APPROACH_RING_FEATHER_ROUNDING_M = 100.0

# Native-resolution admission per ring: ring 1 carries only sources whose
# NATIVE posting is meter-to-10 m class; ring 2 accepts down to 30 m.
APPROACH_RING_MAX_NATIVE_M = (10.0, 30.0)

# Per-definition opt-in admitting a definition to a ring CLASS it would
# not otherwise serve (spec question Q1: Copernicus GLO-30 is a SURFACE
# model deliberately barred from tile-wide use, and may serve ring 2
# only, where no finer wide-area source exists).  No shipped definition
# declares it; flipping one on is the follow-up lane's act, measured on
# HECA, and this is the door it opens.
APPROACH_RING_OPT_IN_KEY = "approach_ring_class"

# Posting arithmetic puts a "30 m" class at 30.92 m, so a definition
# declaring ``approach_ring_class = 30`` must still match it.
_RING_CLASS_SLACK_M = 1.0

# A ring never reaches further than its ladder's last finite rung, so a
# neighbour tile's airport matters only within that distance of this one.
APPROACH_RING_REACH_M = max(reach for reach, _r in APPROACH_RING_LADDER)

#: ``approach_rings`` configuration values (spec section 7: ONE key, the
#: gate the owner's sim read adjudicates; radii, feathers and classes are
#: constants, never keys -- a user knob there is a second ladder).
APPROACH_RINGS_AUTO = "auto"
APPROACH_RINGS_OFF = "off"

#: The cell outcome recorded for a planned cell no provider covers.
NO_RING_COVERAGE = "no-coverage"


def approach_rings_enabled(tile):
    """True when this tile's ``approach_rings`` key admits the rings.

    Anything other than an explicit ``off`` is ``auto`` (the default),
    so a typo degrades to the feature being ON rather than silently
    disabling it -- the same direction :func:`parse_elevation_level`
    degrades in.
    """
    value = getattr(tile, "approach_rings", APPROACH_RINGS_AUTO)
    if value is None:
        return True
    return str(value).strip().lower() != APPROACH_RINGS_OFF


def approach_rung_resolution_m(rung):
    """The warp resolution in metres of one ladder rung.

    An ``int`` rung is a WORKING-GRID FACTOR (its posting is the target);
    a ``float`` rung is already a resolution in metres.
    """
    if isinstance(rung, bool):
        raise TypeError("a ladder rung is a grid factor or a resolution")
    if isinstance(rung, int):
        return round(grid_posting_metres(rung), 2)
    return round(float(rung), 2)


def approach_class(distance_m, ladder):
    """The approach-visibility class for a distance from an aerodrome.

    THE ONE grading function behind both ladders (spec section 3.1,
    census row 5): returns ``(resolution_m, ring_index)`` for the first
    rung whose reach contains ``distance_m`` (``ring_index`` is 1-based,
    so ring 1 is the finest), or ``(None, None)`` beyond the ladder's
    last rung -- where the tile's base DEM stands.
    """
    for index, (reach_m, rung) in enumerate(ladder, start=1):
        if distance_m <= reach_m:
            return approach_rung_resolution_m(rung), index
    return None, None


def approach_ring_feather_m(coarser_resolution_m):
    """The feather width for a seam whose COARSER side has this posting.

    ``APPROACH_RING_FEATHER_POSTINGS`` postings of the coarser class,
    rounded to ``APPROACH_RING_FEATHER_ROUNDING_M``: a 1 arc-second
    coarser side gives 300 m (ring 1 into ring 2), a 3 arc-second one
    900 m (ring 2 into the base DEM).  Both leave every measured
    transition an order of magnitude under ``emit.design.bank_slope``
    and their p95 under the taxiway transverse cap, and both are far
    smaller than the ring widths they sit inside.
    """
    raw_m = APPROACH_RING_FEATHER_POSTINGS * float(coarser_resolution_m)
    step_m = APPROACH_RING_FEATHER_ROUNDING_M
    if raw_m < step_m:
        return float(round(raw_m))
    return float(round(raw_m / step_m) * step_m)


def base_class_posting_m():
    """Posting of the 3 arc-second BASE class, in metres."""
    return round(BASE_CLASS_ARC_SECONDS * grid_posting_metres(1), 2)


def is_coastline_mode(value):
    """True when an ``elevation_level`` value selects "Auto + coastline"."""
    return (
        isinstance(value, str)
        and value.strip().lower() == COASTLINE_MODE_VALUE
    )


def parse_elevation_level(value):
    """Parse an ``elevation_level`` configuration value.

    Returns the level in metres (one of ``LEVEL_GRID_FACTORS``' keys) or
    ``None`` for "auto" (the default), empty, or anything unrecognised
    (with one warning, so a typo degrades to today's behaviour instead of
    failing the build).
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().lower()
        # "coastline" is a mode of its own (is_coastline_mode), and "90"
        # is a base-class pin (base_resolution_preference), not numeric
        # levels -- the numeric machinery treats both like auto.
        if value in ("", "auto", COASTLINE_MODE_VALUE, BASE_90M_VALUE):
            return None
    try:
        level = int(float(value))
    except (TypeError, ValueError):
        level = None
    if level not in LEVEL_GRID_FACTORS:
        UI.vprint(
            1,
            "   WARNING: unrecognised elevation_level",
            repr(value),
            "- using auto.",
        )
        return None
    return level


def base_prefers_coarse(value):
    """True when an ``elevation_level`` value wants the 90 m base class.

    "auto" (and its explicit pin "90", and "Auto + coastline") take the
    3 arc-second base tier: small downloads, with the visible detail
    carried by the airport lidar insets (and, for coastline mode, the
    shoreline band).  Numeric levels "30" and finer instead restore the
    historic 1 arc-second base-class preference underneath their
    wide-area overlay.  Unrecognised values degrade to auto (with
    :func:`parse_elevation_level`'s one warning) and therefore prefer
    coarse too.  An explicit non-auto ``base_elevation_source`` always
    overrides this preference at the selection site.
    """
    return parse_elevation_level(value) is None


def grid_posting_metres(factor):
    """North-south posting of the working grid at a densification factor."""
    return GEO.lat_to_m / (3600.0 * factor)


def grid_factor_for_level(level_m, finest_source_resolution_m):
    """Working-grid factor for a level, capped by the available data.

    The cap keeps memory honest: densifying the grid finer than the
    finest source covering the tile buys nothing (spec section 2).  A
    ``None`` resolution means no wide-area source covers the tile at all,
    in which case the level cannot help and the historic factor 1 grid is
    kept (the caller still applies the max() rule against the airport
    inset auto factor).
    """
    if level_m not in LEVEL_GRID_FACTORS:
        return 1
    if finest_source_resolution_m is None:
        return 1
    effective_resolution_m = max(
        float(level_m), float(finest_source_resolution_m)
    )
    level_factor = LEVEL_GRID_FACTORS[level_m]
    for factor in _CAP_CANDIDATE_FACTORS:
        if grid_posting_metres(factor) <= effective_resolution_m * (
            _POSTING_SLACK
        ):
            return min(factor, level_factor)
    return level_factor


def select_tile_overlay_definition(lat, lon, level_m, providers_config="auto",
                                   max_resolution_m=None, bounding_box=None,
                                   ring_class_m=None):
    """Pick the provider definition serving the tile-wide overlay.

    Candidates are the enabled ``.elv`` definitions (any role) whose
    coverage reaches the tile AND whose access strategy declares
    ``supports_wide_area = True`` (the windowed ``/vsicurl``/overview
    readers -- fetching a whole tile through a tile-download strategy
    would pull an entire national campaign at native resolution).
    ``providers_config`` follows the ``airport_elevation_providers``
    convention ("auto" or an explicit comma list of codes).

    Ranking: finest native resolution first, then priority (descending),
    then code.  Returns the winning definition dict or ``None``.

    ``max_resolution_m`` admits only definitions whose NATIVE resolution
    is at least that fine -- the one added filter the approach rings need
    (approach-graded-elevation-rings-spec section 2: ring 1 is the finest
    wide-area source with native <= 10 m, ring 2 the same product at the
    coarser class).  ``bounding_box`` tests coverage against that box
    instead of the whole tile (a ring CELL, not a tile), and
    ``ring_class_m`` additionally admits a definition that OPTS IN to
    serving that ring class.
    """
    import O4_Airport_Elevation_Insets as INSETS

    candidates = _wide_area_candidate_definitions(
        lat, lon, providers_config,
        max_resolution_m=max_resolution_m,
        bounding_box=bounding_box,
        ring_class_m=ring_class_m,
    )
    if not candidates:
        return None

    def _ranking_key(definition):
        resolution_m = INSETS._definition_resolution_m(definition)
        if resolution_m is None:
            # A wide-area source that does not declare its resolution ranks
            # last (finite resolutions are always preferred as finer).
            resolution_m = float("inf")
        return (
            resolution_m,
            -float(definition.get("priority", 0.0)),
            definition["code"],
        )

    return min(candidates, key=_ranking_key)


def _wide_area_candidate_definitions(lat, lon, providers_config="auto",
                                     max_resolution_m=None,
                                     bounding_box=None, ring_class_m=None):
    """Enabled wide-area definitions (any role) whose coverage reaches a tile.

    Shared candidate set for :func:`select_tile_overlay_definition` and
    :func:`finest_wide_area_resolution_m`.  Mirrors the filtering conventions
    of :func:`O4_Airport_Elevation_Insets.select_provider_definitions`:
    ``providers_config`` "auto" admits every enabled definition, while an
    explicit comma-separated list of codes restricts the set to those codes
    (the list ORDER is irrelevant here -- the resolution ranking of the
    caller decides the winner, so the config only filters).  A definition
    qualifies only when its access strategy class declares a truthy
    ``supports_wide_area`` attribute (the windowed readers) and its coverage
    reaches the tile: role=base definitions use the full
    :func:`O4_Airport_Elevation_Insets.base_definition_covers_tile` test,
    all others the cheap coverage-box intersection.  Bathymetry providers
    (role=bathymetry) are excluded outright -- their tidal-datum depths are
    never terrain (spec section 2.1).

    ``max_resolution_m`` additionally drops every definition whose native
    resolution is coarser than it, or undeclared: the approach rings'
    per-class admission (approach-graded-elevation-rings-spec section 2).
    ``bounding_box`` replaces the tile box in the coverage test, so ONE
    0.1 degree ring cell can be asked its own coverage question.
    ``ring_class_m``, when given, ALSO admits a definition that declares
    ``approach_ring_class`` at or finer than that class even though it
    opts out of tile-wide use -- the per-definition door of the ring
    spec's question Q1 (a SURFACE model may serve a far ring where no
    bare-earth wide-area source exists at all; no shipped definition
    declares it, so flipping one on is a later, measured act).
    """
    import O4_Airport_Elevation_Insets as INSETS

    if not INSETS.elevation_providers_dict:
        INSETS.initialize_elevation_providers_dict()

    config_value = (providers_config or "auto").strip()
    if config_value.lower() == "auto":
        allowed_codes = None
    else:
        allowed_codes = {
            token.strip()
            for token in config_value.split(",")
            if token.strip()
        }

    tile_bounding_box = (
        tuple(bounding_box) if bounding_box is not None
        else (lon, lat, lon + 1, lat + 1)
    )
    candidates = []
    for definition in INSETS.elevation_providers_dict.values():
        if not definition.get("enabled", True):
            continue
        if (
            allowed_codes is not None
            and definition["code"] not in allowed_codes
        ):
            continue
        strategy_factory = INSETS.ACCESS_STRATEGIES.get(
            definition.get("access_strategy")
        )
        if strategy_factory is None:
            continue
        ring_opted_in = _definition_opts_into_ring_class(
            definition, ring_class_m
        )
        if not getattr(strategy_factory, "supports_wide_area", False) \
                and not ring_opted_in:
            continue
        if (str(definition.get("supports_wide_area", "")).strip().lower()
                in ("false", "0", "no")) and not ring_opted_in:
            # A DEFINITION may opt out where its class reads windows: the
            # USGS Original Product Resolution tiles (#153) are ~1 km
            # GeoTIFFs, often stripped -- a whole-tile overlay would read
            # thousands of them in full.
            continue
        role = definition.get("role", INSETS.ROLE_AIRPORT_INSET)
        if role == INSETS.ROLE_BATHYMETRY:
            # Bathymetry providers deliver tidal-datum seabed depth and are
            # never terrain sources (spec section 2.1); they must never feed
            # the elevation_level wide-area overlay even if a future one uses
            # a wide-area access strategy.
            continue
        if role == INSETS.ROLE_BASE:
            if not INSETS.base_definition_covers_tile(definition, lat, lon):
                continue
        elif not INSETS._coverage_bbox_intersects(
            definition, tile_bounding_box
        ):
            continue
        if max_resolution_m is not None:
            resolution_m = INSETS._definition_resolution_m(definition)
            if resolution_m is None or resolution_m > float(max_resolution_m):
                # An UNDECLARED native resolution cannot be shown to be
                # fine enough, so it never enters a ring class.
                continue
        candidates.append(definition)
    return candidates


def _definition_opts_into_ring_class(definition, ring_class_m):
    """True when a definition declares ``approach_ring_class`` at or
    finer than ``ring_class_m`` (the ring spec's question-Q1 door).

    Unparsable or non-positive values are ignored rather than failing the
    registry read, and no ``ring_class_m`` means no opt-in at all -- the
    tile-wide overlay's admission is untouched by this key.
    """
    if ring_class_m is None:
        return False
    raw = (definition or {}).get(APPROACH_RING_OPT_IN_KEY)
    if raw in (None, ""):
        return False
    try:
        declared_m = float(str(raw).strip())
    except (TypeError, ValueError):
        return False
    return 0.0 < declared_m <= float(ring_class_m) + _RING_CLASS_SLACK_M


def finest_wide_area_resolution_m(lat, lon, providers_config="auto"):
    """Finest resolution (metres) among wide-area sources covering the tile.

    Same candidate set as :func:`select_tile_overlay_definition`; used by
    the working-grid data cap.  Returns ``None`` when nothing covers.
    """
    import O4_Airport_Elevation_Insets as INSETS

    resolutions = [
        INSETS._definition_resolution_m(definition)
        for definition in _wide_area_candidate_definitions(
            lat, lon, providers_config
        )
    ]
    resolutions = [
        resolution_m
        for resolution_m in resolutions
        if resolution_m is not None
    ]
    if not resolutions:
        return None
    return min(resolutions)


def resolve_tile_overlay_plan(tile):
    """The single source of truth mapping a tile to its overlay artefact.

    Purely offline and deterministic from the tile configuration and the
    provider registry, so the fetch (step 1) and the bake (steps 1 and 2)
    always agree on the same cache path.  Returns ``None`` when the level
    is auto, GDAL is unavailable, a ``custom_dem`` pins the raster, or no
    wide-area provider covers the tile; otherwise a dict with keys
    ``definition``, ``factor``, ``target_resolution_m``, ``path``.
    """
    raw_value = getattr(tile, "elevation_level", "auto")
    if is_coastline_mode(raw_value):
        return resolve_coastline_band_plan(tile)
    level = parse_elevation_level(raw_value)
    if level is None:
        return None
    if not has_gdal:
        UI.vprint(
            1,
            "   INFO: elevation_level",
            level,
            "requires the GDAL python bindings; keeping auto behaviour.",
        )
        return None
    if getattr(tile, "custom_dem", ""):
        UI.vprint(
            1,
            "   INFO: custom_dem is set; elevation_level",
            level,
            "keeps the custom raster and only densifies the grid.",
        )
        return None
    providers_config = getattr(tile, "airport_elevation_providers", "auto")
    definition = select_tile_overlay_definition(
        tile.lat, tile.lon, level, providers_config
    )
    if definition is None:
        UI.vprint(
            1,
            "   INFO: no wide-area elevation source finer than the base",
            "covers this tile; elevation_level",
            level,
            "has no effect.",
        )
        return None
    import O4_Airport_Elevation_Insets as INSETS

    finest = INSETS._definition_resolution_m(definition)
    factor = grid_factor_for_level(level, finest)
    if factor < LEVEL_GRID_FACTORS[level]:
        UI.vprint(
            1,
            "   INFO: finest source covering this tile is",
            definition["code"],
            "(",
            finest,
            "m ); elevation_level",
            level,
            "capped to a 1/%d arc-second grid." % factor,
        )
    target_resolution_m = round(grid_posting_metres(factor), 2)
    path = FNAMES.tile_overlay_dem(
        tile.lat, tile.lon, definition["code"], target_resolution_m
    )
    return {
        "definition": definition,
        "factor": factor,
        "target_resolution_m": target_resolution_m,
        "path": path,
    }


def ensure_tile_overlay(tile, dico_airports=None):
    """Fetch (or recycle) the tile-wide overlay artefact for the tile.

    Numeric levels: follows the airport-inset orchestration conventions —
    recycle an existing artefact, honour a cached no-coverage negative in
    the overlay ``index.json``, otherwise fetch through
    :func:`O4_Airport_Elevation_Insets.fetch_inset` with the whole-tile
    bounding box ``(lon, lat, lon + 1, lat + 1)``, write the provenance
    sidecar, and record the outcome in the index.  Logs the estimated
    raster size before fetching.  Returns the cached path or ``None``.

    "Auto + coastline" mode dispatches to :func:`ensure_coastline_band`
    instead; ``dico_airports`` (the step-1 airport dictionary) feeds its
    approach-visibility ladder and is unused by numeric levels.
    """
    if is_coastline_mode(getattr(tile, "elevation_level", "auto")):
        return ensure_coastline_band(tile, dico_airports)
    plan = resolve_tile_overlay_plan(tile)
    if plan is None:
        return None
    overlay_path = plan["path"]
    if os.path.isfile(overlay_path):
        UI.vprint(
            2,
            "   Recycling cached tile elevation overlay",
            os.path.basename(overlay_path),
        )
        return overlay_path

    import O4_Airport_Elevation_Insets as INSETS

    lat = tile.lat
    lon = tile.lon
    definition = plan["definition"]
    target_resolution_m = plan["target_resolution_m"]
    # Key the index by the artefact's basename stem so different levels
    # (different target resolutions -> different cache files) each carry
    # their own positive/negative record.
    index_key = os.path.splitext(os.path.basename(overlay_path))[0]
    index_path = FNAMES.tile_overlay_index(lat, lon)
    index = _read_overlay_index(index_path)
    if index.get(index_key) == INSETS.NO_COVERAGE:
        UI.vprint(
            2,
            "   No wide-area elevation coverage recorded for",
            definition["code"],
            "over this tile; skipping the overlay fetch.",
        )
        return None

    level = parse_elevation_level(
        getattr(tile, "elevation_level", "auto")
    )
    centre_latitude = lat + 0.5
    estimated_columns = max(
        int(GEO.lon_to_m(centre_latitude) / target_resolution_m), 1
    )
    estimated_rows = max(int(GEO.lat_to_m / target_resolution_m), 1)
    estimated_megabytes = (
        estimated_columns * estimated_rows * 4 / (1024.0 * 1024.0)
    )
    UI.vprint(
        1,
        "   Fetching tile elevation overlay from",
        definition["code"],
        "at",
        target_resolution_m,
        "m (about",
        round(estimated_megabytes, 1),
        "MB uncompressed float32 raster).",
    )

    bounding_box = (lon, lat, lon + 1, lat + 1)
    fetch_raised = False
    try:
        provenance = INSETS.fetch_inset(
            definition, bounding_box, target_resolution_m, overlay_path
        )
    except Exception as error:
        # Network/GDAL failures must never abort the build; degrade to the
        # base elevation source instead.  A raised failure is NOT recorded
        # as a no-coverage negative (it may be a transient outage).
        provenance = None
        fetch_raised = True
        UI.vprint(2, "   Tile elevation overlay fetch error:", str(error))

    if provenance is None:
        if not fetch_raised:
            # A clean "no usable coverage" answer is a durable fact; cache
            # it so a rebuild never re-queries the discovery service.
            index[index_key] = INSETS.NO_COVERAGE
            _write_overlay_index(index_path, index)
        UI.lvprint(
            0,
            "   WARNING: elevation_level",
            level,
            "was requested but the tile-wide elevation overlay fetch"
            " failed; the build continues on the base elevation source.",
        )
        return None

    provenance = dict(provenance)
    provenance["fetch_date"] = datetime.date.today().isoformat()
    provenance_path = FNAMES.tile_overlay_provenance(
        lat, lon, definition["code"], target_resolution_m
    )
    os.makedirs(os.path.dirname(provenance_path), exist_ok=True)
    with open(provenance_path, "w", newline="\n") as handle:
        json.dump(provenance, handle, indent=2, sort_keys=True)
    index[index_key] = "ok"
    _write_overlay_index(index_path, index)
    return overlay_path


def ensure_coastline_band(tile, dico_airports):
    """Fetch (or recycle) the coastline lidar band for the tile.

    Spec section 3.4.  Loads the tile's OpenStreetMap coastline through
    the pipeline's shared cache (``cached_suffix="coastline"``), selects
    the 0.1 degree cells whose centre lies within
    ``tile.elevation_coastline_band_km`` (plus the cell half-diagonal) of
    the coastline, grades each cell's warp resolution by the
    approach-visibility ladder (distance from the cell centre to the
    nearest airport bounding box from ``dico_airports``), fetches each
    missing cell through the wide-area provider machinery, mosaics the
    cells into a single band VRT, and writes the ``index.json`` stamp
    recording the chosen working-grid factor (3 when any near-airport
    cell exists, else 1) plus per-cell outcomes.  A cell whose raster is
    one constant value everywhere (a fill some providers serve beyond
    their true extent instead of nodata) fails the plausibility probe in
    :func:`O4_Airport_Elevation_Insets.geotiff_is_constant_value` and is
    recorded as no-coverage -- cached and freshly fetched cells alike --
    so the bake keeps the base elevation source there.  Returns the band VRT
    path, or ``None`` when the mode is inactive, GDAL is missing,
    ``custom_dem`` is set, no wide-area provider covers the tile, the
    tile has no coastline, or nothing could be fetched.  Failures never
    raise; they degrade loudly like the numeric-level fetch.
    """
    if not is_coastline_mode(getattr(tile, "elevation_level", "auto")):
        return None
    if not has_gdal:
        UI.vprint(
            1,
            "   INFO: elevation_level coastline requires the GDAL python"
            " bindings; keeping auto behaviour.",
        )
        return None
    if getattr(tile, "custom_dem", ""):
        UI.vprint(
            1,
            "   INFO: custom_dem is set; the coastline elevation band is"
            " skipped (the custom raster is kept).",
        )
        return None

    lat = tile.lat
    lon = tile.lon
    providers_config = getattr(tile, "airport_elevation_providers", "auto")
    definition = select_tile_overlay_definition(
        lat, lon, None, providers_config
    )
    if definition is None:
        UI.vprint(
            1,
            "   INFO: no wide-area elevation source covers this tile; the"
            " coastline elevation band has no effect.",
        )
        return None
    code = definition["code"]

    # Coastline geometry through the pipeline's shared cache (the vector
    # step prefetches the very same query, so no extra download here).
    import O4_OSM_Utils as OSM

    coastline_layer = OSM.OSM_layer()
    if not OSM.OSM_queries_to_OSM_layer(
        ['way["natural"="coastline"]'],
        coastline_layer,
        lat,
        lon,
        [],
        cached_suffix="coastline",
    ):
        UI.lvprint(
            0,
            "   WARNING: the coastline download for the elevation band"
            " failed; the band is skipped and the build continues.",
        )
        return None
    coastline = OSM.OSM_to_MultiLineString(coastline_layer, lat, lon)
    # OSM_to_MultiLineString subtracts (lon, lat) from every node, so the
    # geometry is in TILE-RELATIVE degree offsets (x = longitude offset,
    # y = latitude offset, each roughly 0..1 within the tile).
    if coastline.is_empty:
        UI.vprint(
            1,
            "   INFO: this tile has no coastline; the elevation band is"
            " skipped.",
        )
        return None

    from shapely.affinity import scale as _scale_geometry
    from shapely.geometry import Point

    metres_per_degree_longitude = GEO.lon_to_m(lat + 0.5)
    metres_per_degree_latitude = GEO.lat_to_m
    # Work in a metre-scaled plane so shapely's .distance is metric.
    scaled_coastline = _scale_geometry(
        coastline,
        xfact=metres_per_degree_longitude,
        yfact=metres_per_degree_latitude,
        origin=(0.0, 0.0),
    )
    cell_half_diagonal_m = 0.5 * (
        (COASTLINE_CELL_DEGREES * metres_per_degree_longitude) ** 2
        + (COASTLINE_CELL_DEGREES * metres_per_degree_latitude) ** 2
    ) ** 0.5
    band_reach_m = (
        float(getattr(tile, "elevation_coastline_band_km", 5.0)) * 1000.0
        + cell_half_diagonal_m
    )

    # Airport bounding boxes (west, south, east, north) drive the
    # approach-visibility ladder; none -> every cell is a far-tier cell.
    import O4_Airport_Elevation_Insets as INSETS

    if dico_airports:
        airport_boxes = list(
            INSETS._airport_bounding_boxes(tile, dico_airports).values()
        )
    else:
        airport_boxes = []

    # THE SHARED GRADING FUNCTION (consumer census row 5): the band's
    # own ladder table, VALUES UNCHANGED, read through the one
    # :func:`approach_class` the approach rings also use -- the
    # generalisation the owner asked for ("the coastline level's
    # approach-visibility grading is THE RULE TO GENERALISE, not a
    # parallel one"), with the band's radii left alone pending a
    # coastline-mode sim read (ring spec question Q2).
    COASTLINE_BAND_TIERS = ("near", "mid", "far")

    def _nearest_airport_distance_m(cell_centre_lon, cell_centre_lat):
        """Metre distance to the nearest airport box (0 inside), inf if none.

        True point-to-rectangle distance under axis-aligned metre scaling:
        the nearest point on an axis-aligned box is the per-axis clamp, and
        independent axis scaling preserves that, so each axis gap is scaled
        by its own metres-per-degree factor before combining.
        """
        best = float("inf")
        for west, south, east, north in airport_boxes:
            gap_longitude_deg = max(
                west - cell_centre_lon, 0.0, cell_centre_lon - east
            )
            gap_latitude_deg = max(
                south - cell_centre_lat, 0.0, cell_centre_lat - north
            )
            distance_m = (
                (gap_longitude_deg * metres_per_degree_longitude) ** 2
                + (gap_latitude_deg * metres_per_degree_latitude) ** 2
            ) ** 0.5
            if distance_m < best:
                best = distance_m
        return best

    # Select coastal cells and grade each by the approach ladder.
    cells = []
    cell_count = 10  # a 1 degree tile is a 10 x 10 grid of 0.1 degree cells
    for cell_column in range(cell_count):
        for cell_row in range(cell_count):
            centre_offset_longitude = (
                cell_column + 0.5
            ) * COASTLINE_CELL_DEGREES
            centre_offset_latitude = (
                cell_row + 0.5
            ) * COASTLINE_CELL_DEGREES
            distance_to_coast_m = scaled_coastline.distance(
                Point(
                    centre_offset_longitude * metres_per_degree_longitude,
                    centre_offset_latitude * metres_per_degree_latitude,
                )
            )
            if distance_to_coast_m > band_reach_m:
                continue
            centre_longitude = lon + centre_offset_longitude
            centre_latitude = lat + centre_offset_latitude
            airport_distance_m = _nearest_airport_distance_m(
                centre_longitude, centre_latitude
            )
            resolution_m, tier_index = approach_class(
                airport_distance_m, COASTLINE_APPROACH_LADDER
            )
            tier = COASTLINE_BAND_TIERS[tier_index - 1]
            cell_path = FNAMES.coastline_band_cell_dem(
                lat, lon, cell_column, cell_row, code, resolution_m
            )
            cells.append(
                {
                    "column": cell_column,
                    "row": cell_row,
                    "tier": tier,
                    "resolution_m": resolution_m,
                    "path": cell_path,
                    "stem": os.path.splitext(
                        os.path.basename(cell_path)
                    )[0],
                }
            )

    if not cells:
        UI.vprint(
            1,
            "   INFO: no tile cell lies within the coastline band; the"
            " elevation band is skipped.",
        )
        return None

    near_tier_cells = sum(1 for cell in cells if cell["tier"] == "near")
    mid_tier_cells = sum(1 for cell in cells if cell["tier"] == "mid")
    far_tier_cells = sum(1 for cell in cells if cell["tier"] == "far")
    UI.vprint(
        1,
        "   Coastline elevation band from",
        code,
        "-",
        len(cells),
        "cell(s) (",
        near_tier_cells,
        "near /",
        mid_tier_cells,
        "mid /",
        far_tier_cells,
        "far ).",
    )

    band_directory = FNAMES.coastline_band_directory(lat, lon)
    os.makedirs(band_directory, exist_ok=True)
    stamp_path = FNAMES.coastline_band_index(lat, lon)
    previous_stamp = _read_coastline_band_stamp(stamp_path)
    # Preserve every previously recorded per-cell negative when rewriting.
    cell_outcomes = {
        stem: outcome
        for stem, outcome in previous_stamp.get("cells", {}).items()
        if outcome == INSETS.NO_COVERAGE
    }

    def _discard_implausible_cell(cell_path, stem):
        """Delete a constant-value cell and record a durable negative.

        Some providers fill windows beyond their true data extent with a
        constant value instead of nodata (the Spanish PNOA Web Coverage
        Service serves 0.0 over Portugal), which would bake the coast
        flat to that constant; recording no-coverage makes the bake fall
        back to the base elevation source there.
        """
        try:
            os.remove(cell_path)
        except OSError:
            pass
        cell_outcomes[stem] = INSETS.NO_COVERAGE
        UI.vprint(
            1,
            "   INFO: coastline band cell",
            stem,
            "is one constant value everywhere (a fill served beyond the"
            " provider's true extent); recording no coverage so the base"
            " elevation source is kept there.",
        )

    for cell in cells:
        cell_path = cell["path"]
        stem = cell["stem"]
        if os.path.isfile(cell_path):
            # A cached cell is recycled, but only after the same
            # plausibility probe a fresh fetch gets: caches poisoned
            # before the guard existed heal here.
            if INSETS.geotiff_is_constant_value(cell_path):
                _discard_implausible_cell(cell_path, stem)
            else:
                cell_outcomes[stem] = "ok"
            continue
        if cell_outcomes.get(stem) == INSETS.NO_COVERAGE:
            # A durable no-coverage negative from a previous run: honour it
            # without re-querying the discovery service.
            continue
        try:
            provenance = INSETS.fetch_inset(
                definition,
                (
                    lon + cell["column"] * COASTLINE_CELL_DEGREES,
                    lat + cell["row"] * COASTLINE_CELL_DEGREES,
                    lon
                    + (cell["column"] + 1) * COASTLINE_CELL_DEGREES,
                    lat + (cell["row"] + 1) * COASTLINE_CELL_DEGREES,
                ),
                cell["resolution_m"],
                cell_path,
            )
        except Exception as error:
            # A raised failure (network/GDAL) is skipped and NOT recorded as
            # a durable negative -- it may be a transient outage.
            UI.vprint(
                2,
                "   Coastline band cell fetch error at",
                stem,
                ":",
                str(error),
            )
            continue
        if provenance is None:
            # A clean "no usable coverage" answer is durable; record it.
            cell_outcomes[stem] = INSETS.NO_COVERAGE
        elif INSETS.geotiff_is_constant_value(cell_path):
            # Fetched, but implausible: a constant raster is a fill served
            # beyond the provider's true extent, never genuine lidar.
            _discard_implausible_cell(cell_path, stem)
        else:
            cell_outcomes[stem] = "ok"

    existing_cells = [
        cell for cell in cells if os.path.isfile(cell["path"])
    ]
    if not existing_cells:
        stamp = {
            "provider": code,
            "factor": 1,
            "cells": cell_outcomes,
            "checked": datetime.date.today().isoformat(),
        }
        _write_coastline_band_stamp(stamp_path, stamp)
        UI.lvprint(
            0,
            "   WARNING: no coastline band cell could be fetched for this"
            " tile; the build continues on the base elevation source.",
        )
        return None

    vrt_path = FNAMES.coastline_band_vrt(lat, lon, code)
    mosaic = gdal.BuildVRT(
        vrt_path,
        [cell["path"] for cell in existing_cells],
        options=gdal.BuildVRTOptions(
            resolution="highest",
            resampleAlg="bilinear",
            srcNodata=-32768,
            VRTNodata=-32768,
        ),
    )
    # Release the handle so the virtual mosaic is flushed to disk.
    mosaic = None

    band_factor = (
        3 if any(cell["tier"] == "near" for cell in existing_cells) else 1
    )
    stamp = {
        "provider": code,
        "factor": band_factor,
        "finest_resolution_m": min(
            cell["resolution_m"] for cell in existing_cells
        ),
        "vrt": os.path.basename(vrt_path),
        "cells": cell_outcomes,
        "checked": datetime.date.today().isoformat(),
    }
    _write_coastline_band_stamp(stamp_path, stamp)
    return vrt_path


def resolve_coastline_band_plan(tile):
    """Plan-shaped view of the cached coastline band (stamp-driven).

    The coastline analogue of :func:`resolve_tile_overlay_plan`: purely
    disk-state-driven (the ``index.json`` stamp written by
    :func:`ensure_coastline_band`), so both build steps agree without a
    fetch.  Returns ``None`` when the mode is inactive, GDAL is missing,
    ``custom_dem`` is set, or no stamp/VRT exists; otherwise a dict with
    the same keys the bake consumes: ``definition`` (a minimal
    ``{"code": ...}`` from the stamp), ``factor``,
    ``target_resolution_m`` (the finest cell resolution in the band) and
    ``path`` (the band VRT).
    """
    if not is_coastline_mode(getattr(tile, "elevation_level", "auto")):
        return None
    if not has_gdal:
        return None
    if getattr(tile, "custom_dem", ""):
        return None
    stamp_path = FNAMES.coastline_band_index(tile.lat, tile.lon)
    stamp = _read_coastline_band_stamp(stamp_path)
    if not stamp:
        return None
    vrt_name = stamp.get("vrt")
    if not vrt_name:
        return None
    vrt_path = os.path.join(
        FNAMES.coastline_band_directory(tile.lat, tile.lon), vrt_name
    )
    if not os.path.isfile(vrt_path):
        return None
    return {
        "definition": {"code": stamp["provider"]},
        "factor": int(stamp["factor"]),
        "target_resolution_m": stamp["finest_resolution_m"],
        "path": vrt_path,
    }


def coastline_grid_factor(tile):
    """Working-grid factor recorded in the coastline band stamp.

    Returns 1 when no stamp exists (band never fetched -- the grid stays
    historic, keeping the mode inert until step 1 has run).
    """
    stamp = _read_coastline_band_stamp(
        FNAMES.coastline_band_index(tile.lat, tile.lon)
    )
    try:
        return int(stamp["factor"])
    except (KeyError, TypeError, ValueError):
        return 1


def _read_coastline_band_stamp(stamp_path):
    """Read the coastline band ``index.json`` stamp (factor + cell outcomes).

    Returns an empty dictionary when the stamp does not exist yet or cannot
    be parsed, mirroring :func:`_read_overlay_index`.
    """
    if not os.path.isfile(stamp_path):
        return {}
    try:
        with open(stamp_path, "r") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _write_coastline_band_stamp(stamp_path, stamp):
    """Write the coastline band stamp, creating its directory."""
    os.makedirs(os.path.dirname(stamp_path), exist_ok=True)
    with open(stamp_path, "w", newline="\n") as handle:
        json.dump(stamp, handle, indent=2, sort_keys=True)


def _read_overlay_index(index_path):
    """Read the tile-overlay discovery index (positives and negatives).

    Returns an empty dictionary when the index does not exist yet or cannot
    be parsed, mirroring the airport-inset ``_read_index`` conventions.
    """
    if not os.path.isfile(index_path):
        return {}
    try:
        with open(index_path, "r") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _write_overlay_index(index_path, index):
    """Write the tile-overlay discovery index, creating its directory."""
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", newline="\n") as handle:
        json.dump(index, handle, indent=2, sort_keys=True)


# ══════════════════════════════════════════════════════════════════════
# APPROACH-GRADED ELEVATION RINGS -- THE FETCH AND THE BAKE
# ══════════════════════════════════════════════════════════════════════

def ensure_approach_rings(tile, dico_airports):
    """Fetch (or recycle) the tile's approach ring cells -- STEP 1 ONLY.

    The band's own loop over a plan's cells (consumer census row 1),
    beside :func:`ensure_tile_overlay` in the tile prelude: one
    :func:`O4_Airport_Elevation_Insets.fetch_inset` per MISSING cell, a
    durable no-coverage negative for a clean "no usable coverage"
    answer, the constant-value plausibility probe every band cell gets,
    and a cell the coastline band already holds at the same stem reused
    BY REFERENCE (never copied -- one cell cache, two plans).

    THE HARNESS NEVER CALLS THIS (spec section 5): it derives the plan
    offline and REFUSES a cold one naming ``--refresh-data rings``.  A
    pass that fetched anything sets ``tile.rings_fetched`` so the build
    record can mark the run download-polluted
    (``features.rings_fetched``, the ``insets_fetched`` treatment).

    Returns the plan (with per-cell outcomes recorded), or ``None``.
    """
    plan = resolve_approach_ring_plan(tile, dico_airports)
    if plan is None:
        return None
    import O4_Airport_Elevation_Insets as INSETS

    lat, lon = int(tile.lat), int(tile.lon)
    directory = plan["directory"]
    stamp_path = FNAMES.approach_ring_index(lat, lon)
    previous = _read_coastline_band_stamp(stamp_path)
    outcomes = {
        stem: outcome
        for stem, outcome in (previous.get("cells") or {}).items()
        if outcome == NO_RING_COVERAGE
    }
    fetched = 0
    providers = {}
    for cell in plan["cells"]:
        stem = cell.get("stem")
        if stem is None:
            continue
        providers[stem] = cell["provider"]
        existing = approach_ring_cell_on_disk(lat, lon, cell)
        if existing:
            if INSETS.geotiff_is_constant_value(existing):
                _discard_implausible_ring_cell(existing, stem, outcomes)
            else:
                outcomes[stem] = "ok"
            continue
        if outcomes.get(stem) == NO_RING_COVERAGE:
            # A durable negative from a previous run: honoured without
            # re-querying.  Rings NEVER re-check in a build (spec
            # section 5); the once-per-engine-version re-probe door is
            # --refresh-data rings' business, never this pass's.
            continue
        definition = _approach_ring_definition(cell, tile)
        if definition is None:
            outcomes[stem] = NO_RING_COVERAGE
            continue
        os.makedirs(directory, exist_ok=True)
        try:
            provenance = INSETS.fetch_inset(
                definition, tuple(cell["box"]), cell["class_m"],
                cell["path"],
            )
        except Exception as error:
            # A raised failure (network/GDAL) is skipped and NOT recorded
            # as a durable negative -- it may be a transient outage.
            UI.vprint(
                2, "   Approach ring cell fetch error at", stem, ":",
                str(error),
            )
            continue
        fetched += 1
        if provenance is None:
            outcomes[stem] = NO_RING_COVERAGE
        elif INSETS.geotiff_is_constant_value(cell["path"]):
            _discard_implausible_ring_cell(cell["path"], stem, outcomes)
        else:
            outcomes[stem] = "ok"
            provenance = dict(provenance)
            provenance["fetch_date"] = datetime.date.today().isoformat()
            with open(cell["path"][:-4] + ".json", "w",
                      encoding="utf-8", newline="\n") as handle:
                json.dump(provenance, handle, indent=2, sort_keys=True)
    if fetched:
        tile.rings_fetched = True
    _write_approach_ring_stamp(lat, lon, plan, outcomes)
    UI.vprint(
        1,
        "   Approach elevation rings:", len(plan["cells"]), "planned cell(s),",
        fetched, "fetched,",
        sum(1 for o in outcomes.values() if o == NO_RING_COVERAGE),
        "no-coverage.",
    )
    return plan


def _approach_ring_definition(cell, tile):
    """The registry definition a planned cell names, or ``None``."""
    import O4_Airport_Elevation_Insets as INSETS

    if not INSETS.elevation_providers_dict:
        INSETS.initialize_elevation_providers_dict()
    for definition in INSETS.elevation_providers_dict.values():
        if definition.get("code") == cell.get("provider"):
            return definition
    return None


def _discard_implausible_ring_cell(cell_path, stem, outcomes):
    """Delete a constant-value ring cell and record a durable negative.

    Some providers fill windows beyond their true data extent with a
    constant instead of nodata (the band's own measured case: the
    Spanish PNOA service serves 0.0 over Portugal), which would bake a
    ring flat to that constant; the negative makes the base DEM stand.
    A cell borrowed from the COASTLINE BAND directory is never deleted
    here -- it is not this plan's file -- only recorded.
    """
    if os.path.basename(os.path.dirname(cell_path)).endswith(
            "_approach_rings"):
        try:
            os.remove(cell_path)
        except OSError:
            pass
    outcomes[stem] = NO_RING_COVERAGE
    UI.vprint(
        1,
        "   INFO: approach ring cell", stem, "is one constant value"
        " everywhere (a fill served beyond the provider's true extent);"
        " recording no coverage so the base elevation source is kept"
        " there.",
    )


def _write_approach_ring_stamp(lat, lon, plan, outcomes):
    """Write ``<ring dir>/index.json`` ONLY when it changed.

    A byte-identical stamp is never rewritten (owner ruling e9daef5: a
    build must not touch the shared repo as a side effect, and an
    mtime-only rewrite re-keys every stored arm through the corpus
    stamp's directory listing).
    """
    stamp = {
        "stamp": plan["stamp"],
        "cells": dict(sorted(outcomes.items())),
        "layers": [
            {"class_m": layer["class_m"], "ring": layer["ring"],
             "feather_m": layer["feather_m"],
             "providers": layer["providers"], "cells": len(layer["cells"])}
            for layer in plan["layers"]
        ],
        "airports": plan["airports"],
        "neighbours_unknown": plan["neighbours_unknown"],
        "feathers": plan["feathers"],
        "superseded": plan["superseded"],
    }
    stamp_path = FNAMES.approach_ring_index(lat, lon)
    payload = json.dumps(stamp, indent=2, sort_keys=True)
    try:
        with open(stamp_path, "r", encoding="utf-8") as handle:
            if handle.read() == payload:
                return
    except OSError:
        pass
    os.makedirs(os.path.dirname(stamp_path), exist_ok=True)
    with open(stamp_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def bake_approach_rings_into_alt_dem(tile, dico_airports):
    """Bake the tile's ring layers into ``tile.dem.alt_dem``, COARSEST
    FIRST (spec section 3.2; consumer census row 3).

    Called from ``O4_Vector_Map.compose_tile_dem_from_disk`` immediately
    AFTER the numeric-level overlay bake and BEFORE the airport
    smoothing pass: rings are BASE TERRAIN -- smoothed like base, with
    the airport insets still baking last, over them.  Coarsest first and
    one exact region mask per layer is what makes the finest class win
    per cell without a per-consumer veto.

    Each layer is mosaicked into a VRT in the tile's TMP directory (a
    DERIVED file -- never the shared repo, spec section 9 item 4) over
    the cells actually on disk; a missing cell is simply a hole the base
    DEM fills, which is what ``--allow-degraded-dem`` accepts.

    Returns ``True`` when at least one layer blended.
    """
    plan = resolve_approach_ring_plan(tile, dico_airports)
    if plan is None:
        return False
    if tile.dem is None or getattr(tile.dem, "alt_dem", None) is None:
        return False
    from shapely import wkt as _wkt

    lat, lon = int(tile.lat), int(tile.lon)
    by_stem = {
        cell["stem"]: cell for cell in plan["cells"] if cell.get("stem")
    }
    baked_layers = []
    for layer in plan["layers"]:
        paths = []
        for stem in layer["cells"]:
            path = approach_ring_cell_on_disk(lat, lon, by_stem[stem])
            if path:
                paths.append(path)
        if not paths:
            continue
        vrt_path = _approach_ring_layer_vrt(lat, lon, layer, paths)
        if vrt_path is None:
            continue
        region = _wkt.loads(plan["regions"][layer["region"]])
        if bake_overlay_layer_into_alt_dem(
            tile, vrt_path, feather_m=layer["feather_m"], region=region,
            label="approach ring %d (%s m)" % (layer["ring"],
                                               layer["class_m"]),
        ):
            baked_layers.append({
                "class_m": layer["class_m"],
                "ring": layer["ring"],
                "providers": layer["providers"],
                "cells": len(paths),
                "feather_m": layer["feather_m"],
            })
    if not baked_layers:
        return False
    tile.dem.approach_ring_provenance = {
        "layers": baked_layers,
        "plan_stamp": plan["stamp"],
        "neighbours_unknown": plan["neighbours_unknown"],
    }
    UI.vprint(
        1,
        "   Approach elevation rings baked:",
        ", ".join(
            "ring %d at %s m over %d cell(s), feather %d m"
            % (entry["ring"], entry["class_m"], entry["cells"],
               int(entry["feather_m"]))
            for entry in baked_layers
        ),
        ".",
    )
    return True


def _approach_ring_layer_vrt(lat, lon, layer, paths):
    """Mosaic one layer's cells into a VRT in the tile's TMP directory.

    Derived, per-build and lane-local by construction: the shared repo
    holds the CELLS, never a VRT a build wrote (spec section 9 item 4).
    """
    directory = FNAMES.Tmp_dir or "."
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        return None
    resolution_token = ("%.2f" % float(layer["class_m"])).rstrip(
        "0").rstrip(".")
    vrt_path = os.path.join(
        directory,
        "%s_approach_ring_%sm.vrt"
        % (FNAMES.hem_latlon(lat, lon), resolution_token),
    )
    mosaic = gdal.BuildVRT(
        vrt_path, sorted(paths),
        options=gdal.BuildVRTOptions(
            resolution="highest", resampleAlg="bilinear",
            srcNodata=-32768, VRTNodata=-32768,
        ),
    )
    # Release the handle so the virtual mosaic is flushed to disk.
    mosaic = None
    return vrt_path if os.path.isfile(vrt_path) else None


# ══════════════════════════════════════════════════════════════════════
# APPROACH-GRADED ELEVATION RINGS -- THE PLAN (one derivation site)
# ══════════════════════════════════════════════════════════════════════

def _approach_ring_cell_box(lat, lon, cell_column, cell_row):
    """The degree bounding box of one 0.1 degree plan cell."""
    return (
        lon + cell_column * COASTLINE_CELL_DEGREES,
        lat + cell_row * COASTLINE_CELL_DEGREES,
        lon + (cell_column + 1) * COASTLINE_CELL_DEGREES,
        lat + (cell_row + 1) * COASTLINE_CELL_DEGREES,
    )


def _approach_ring_inset_airports(tile, dico_airports):
    """The tile's OWN airports that a ring is drawn around.

    Spec section 1: every airport that HOLDS AN INSET on this tile --
    admitted by the tile's inset MODE (the same admission the inset
    selection uses) and with an inset raster actually on disk.  An
    airport production never cuts an inset for gets no ring.
    """
    import O4_Airport_Elevation_Insets as INSETS

    try:
        from auto_patch.selection import inset_keys, resolved_inset_mode
    except Exception:
        return []
    mode = resolved_inset_mode(tile)
    admitted = []
    for icao in inset_keys(dico_airports, mode):
        if INSETS.cached_inset_paths_for_icao(tile.lat, tile.lon, icao):
            admitted.append(icao)
    return sorted(admitted)


def _approach_ring_neighbour_polygons(tile, reach_m):
    """Boundary polygons of the 8 neighbour tiles' admitted airports.

    THE COASTLINE BAND'S RECORDED LIMIT, CLOSED WHERE THE DATA IS THERE
    (elevation-level spec section 3.4: "airports of neighbouring tiles
    are invisible").  A neighbour whose cached airports layer exists is
    parsed through the pipeline's OWN dictionary chain
    (``O4_Vector_Map.build_airports_dico``, never a replication) on a
    throwaway tile; one with no cached layer contributes nothing and is
    RECORDED as unknown -- never a refusal, because a plan that refused
    on an uncached neighbour would refuse every first build.

    Returns ``(polygons, unknown)``: ``{(lat, lon, icao): geometry}`` in
    absolute EPSG:4326 degrees, and the ``[lat, lon]`` of every neighbour
    whose airports layer is not cached.
    """
    from shapely.geometry import box as _box

    polygons = {}
    unknown = []
    tile_reach = _buffer_tile_square_m(tile.lat, tile.lon, reach_m)
    for d_lat in (-1, 0, 1):
        for d_lon in (-1, 0, 1):
            if d_lat == 0 and d_lon == 0:
                continue
            n_lat, n_lon = int(tile.lat) + d_lat, int(tile.lon) + d_lon
            layer_path = FNAMES.osm_cached(n_lat, n_lon, "airports")
            if not os.path.isfile(layer_path):
                unknown.append([n_lat, n_lon])
                continue
            if not tile_reach.intersects(
                _box(n_lon, n_lat, n_lon + 1, n_lat + 1)
            ):
                continue
            try:
                neighbour, dico = _load_neighbour_airports(n_lat, n_lon)
            except Exception as error:
                UI.vprint(
                    2,
                    "   Approach rings: neighbour tile %+03d%+04d airports "
                    "layer could not be read (%s); recorded as unknown."
                    % (n_lat, n_lon, type(error).__name__),
                )
                unknown.append([n_lat, n_lon])
                continue
            import O4_Airport_Elevation_Insets as INSETS

            try:
                from auto_patch.selection import (
                    inset_keys, resolved_inset_mode)
            except Exception:
                continue
            admitted = inset_keys(dico, resolved_inset_mode(neighbour))
            boundaries = INSETS.airport_boundary_polygons(
                neighbour, dico, only=admitted
            )
            for icao, geometry in boundaries.items():
                if tile_reach.intersects(geometry):
                    polygons[(n_lat, n_lon, icao)] = geometry
    return polygons, unknown


def _buffer_tile_square_m(lat, lon, metres):
    """This tile's 1 degree square grown by ``metres`` (degree space)."""
    import O4_Airport_Elevation_Insets as INSETS
    from shapely.geometry import box as _box

    return INSETS._buffer_geometry_m(
        _box(lon, lat, lon + 1, lat + 1), float(metres)
    )


def _load_neighbour_airports(lat, lon):
    """``(throwaway tile, dico_airports)`` from a neighbour's CACHED
    airports layer -- offline (``cached_suffix="airports"`` reads the
    cache the home tile's own step 1 wrote) and through the pipeline's
    own chain, so a neighbour's boundaries are the very polygons its own
    build would use."""
    import O4_Config_Utils as CFG
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP

    neighbour = CFG.Tile(int(lat), int(lon), "")
    try:
        neighbour.read_from_config()
    except Exception:
        pass
    layer = OSM.OSM_layer()
    OSM.OSM_queries_to_OSM_layer(
        VMAP.AIRPORTS_QUERIES, layer, int(lat), int(lon), ["all"],
        cached_suffix="airports",
    )
    return neighbour, VMAP.build_airports_dico(neighbour, layer)


def _approach_ring_superseded_classes(tile):
    """The ring classes a numeric ``elevation_level`` already delivers.

    Spec section 7: per cell the FINEST class wins, and a ring is baked
    only where it is finer than what the level already puts on the whole
    tile ("levels never coarsen what auto would have chosen", and rings
    never coarsen a level).  Level 30 supersedes ring 2 (its tile-wide
    overlay IS the 1 arc-second class); level 10 and finer supersede
    both; auto, 90 and coastline supersede nothing.
    """
    level = parse_elevation_level(getattr(tile, "elevation_level", "auto"))
    if level is None:
        return ()
    overlay_posting_m = grid_posting_metres(LEVEL_GRID_FACTORS[level])
    superseded = []
    for reach_m, rung in APPROACH_RING_LADDER:
        class_m = approach_rung_resolution_m(rung)
        if class_m >= overlay_posting_m - _RING_CLASS_SLACK_M:
            superseded.append(class_m)
    return tuple(superseded)


def resolve_approach_ring_plan(tile, dico_airports):
    """THE ONE derivation of the tile's approach-ring cells and regions.

    Pure and offline (spec section 3.1, consumer census row 2): both
    build steps, the harness frame check and ``--refresh-data rings``
    re-derive it from the SAME disk state, so the fetch and the bake can
    never disagree about which cell belongs to which class.

    Returns ``None`` when the feature is off, GDAL is missing, a
    ``custom_dem`` pins the raster, no airport on (or near) the tile
    holds an inset, or every ring class is superseded by the
    ``elevation_level`` overlay.  Otherwise a dict with keys:

    ``cells``
        one record per planned 0.1 degree cell: ``column``, ``row``,
        ``class_m`` (the warp target), ``reach_ring`` (1-based, the ring
        whose class it carries), ``collapsed`` (ring 1 fell back to the
        ring-2 class for want of a <= 10 m wide-area provider),
        ``provider``, ``path``, ``stem``, ``box``.
    ``layers``
        one record per class, COARSEST FIRST -- the bake order (spec
        section 3.2).  A list rather than a mapping because a float
        class is not a JSON object key and this plan is stamped verbatim.
    ``regions``
        ``{"R1": wkt, "R2": wkt}`` -- the EXACT ring unions (the
        aerodrome boundaries buffered by each ladder reach), as WKT so
        the plan stays plain data; the bake rasterises them per strip.
    ``airports``, ``neighbours_unknown``, ``feathers``, ``superseded``,
    ``directory``, ``stamp``.
    """
    if not approach_rings_enabled(tile):
        return None
    if not has_gdal:
        UI.vprint(
            1,
            "   INFO: approach elevation rings require the GDAL python"
            " bindings; keeping the base elevation source.",
        )
        return None
    if getattr(tile, "custom_dem", ""):
        UI.vprint(
            1,
            "   INFO: custom_dem is set; approach elevation rings are"
            " skipped (the custom raster is authoritative).",
        )
        return None
    import O4_Airport_Elevation_Insets as INSETS
    from shapely.geometry import box as _box
    from shapely.ops import unary_union

    lat, lon = int(tile.lat), int(tile.lon)
    superseded = _approach_ring_superseded_classes(tile)
    own = _approach_ring_inset_airports(tile, dico_airports or {})
    polygons = {
        (lat, lon, icao): geometry
        for icao, geometry in INSETS.airport_boundary_polygons(
            tile, dico_airports or {}, only=own
        ).items()
    }
    neighbour_polygons, neighbours_unknown = (
        _approach_ring_neighbour_polygons(tile, APPROACH_RING_REACH_M)
    )
    polygons.update(neighbour_polygons)
    if not polygons:
        return None

    boundary_union = unary_union(list(polygons.values()))
    tile_square = _box(lon, lat, lon + 1, lat + 1)
    # The ring regions: the boundary union buffered by each ladder reach,
    # measured FROM THE BOUNDARY as ruled (never the ARP, never the box),
    # clipped to the tile -- a neighbour's ring reaches in, and its own
    # tile bakes its own half.
    regions = []
    for index, (reach_m, rung) in enumerate(APPROACH_RING_LADDER, start=1):
        class_m = approach_rung_resolution_m(rung)
        region = INSETS._buffer_geometry_m(
            boundary_union, float(reach_m)
        ).intersection(tile_square)
        regions.append({"ring": index, "class_m": class_m,
                        "reach_m": float(reach_m), "geometry": region})
    # Each ring OWNS only what the finer rings do not: R2 as baked is the
    # 20 km union, and ring 1 bakes on top of it (finest class per cell).
    providers_config = getattr(tile, "airport_elevation_providers", "auto")
    cells = []
    for cell_column in range(_APPROACH_RING_CELLS_PER_SIDE):
        for cell_row in range(_APPROACH_RING_CELLS_PER_SIDE):
            cell_box = _approach_ring_cell_box(
                lat, lon, cell_column, cell_row
            )
            geometry = _box(*cell_box)
            ring = None
            for record in regions:
                if record["class_m"] in superseded:
                    continue
                if record["geometry"].intersects(geometry):
                    ring = record
                    break
            if ring is None:
                continue
            resolved = _approach_ring_cell_provider(
                lat, lon, cell_box, ring["ring"], providers_config
            )
            if resolved is None:
                # No wide-area provider covers this cell at any ring
                # class: a cached NEGATIVE, exactly as the band records
                # one, and the tile's base DEM stands there.
                cells.append({
                    "column": cell_column, "row": cell_row,
                    "class_m": ring["class_m"], "reach_ring": ring["ring"],
                    "collapsed": False, "provider": None,
                    "path": None, "stem": None, "box": list(cell_box),
                    "outcome": NO_RING_COVERAGE,
                })
                continue
            class_m, code, collapsed = resolved
            if class_m in superseded:
                continue
            cell_path = FNAMES.approach_ring_cell_dem(
                lat, lon, cell_column, cell_row, code, class_m
            )
            cells.append({
                "column": cell_column, "row": cell_row,
                "class_m": class_m,
                "reach_ring": ring["ring"] + (1 if collapsed else 0),
                "collapsed": collapsed, "provider": code,
                "path": cell_path,
                "stem": os.path.splitext(os.path.basename(cell_path))[0],
                "box": list(cell_box),
            })
    if not any(cell.get("provider") for cell in cells):
        return None

    layers = _approach_ring_layers(cells, regions, superseded)
    plan = {
        "cells": cells,
        "layers": layers,
        "regions": {
            "R%d" % record["ring"]: record["geometry"].wkt
            for record in regions
        },
        "airports": ["%+03d%+04d:%s" % key for key in sorted(polygons)],
        "neighbours_unknown": sorted(neighbours_unknown),
        "feathers": {
            "ring%d_m" % record["ring"]: _approach_ring_layer_feather_m(
                record["ring"]
            )
            for record in regions
        },
        "superseded": list(superseded),
        "directory": FNAMES.approach_ring_directory(lat, lon),
    }
    plan["stamp"] = _approach_ring_plan_stamp(plan)
    return plan


#: A 1 degree tile is a 10 x 10 grid of ``COASTLINE_CELL_DEGREES`` cells
#: -- the band's own decomposition, reused so the two caches share stems.
_APPROACH_RING_CELLS_PER_SIDE = 10


def _approach_ring_cell_provider(lat, lon, cell_box, ring, providers_config):
    """``(class_m, provider_code, collapsed)`` for one planned cell.

    Spec section 2, including THE COLLAPSE RULE: a ring-1 cell no
    <= 10 m wide-area provider covers is fetched at the RING-2 class
    instead (ring 1 collapses into ring 2) rather than left to the base
    DEM; a cell no ring-2 provider covers either is a negative and
    returns ``None``.  Ring 2 prefers the ring-1 product where it
    reaches, so one product, one datum and one vintage span the
    10 m -> 30 m seam and the step across it is pure resolution.
    """
    for index in range(ring, len(APPROACH_RING_LADDER) + 1):
        if index > len(APPROACH_RING_LADDER):
            break
        class_m = approach_rung_resolution_m(
            APPROACH_RING_LADDER[index - 1][1]
        )
        native_cap_m = APPROACH_RING_MAX_NATIVE_M[
            min(index, len(APPROACH_RING_MAX_NATIVE_M)) - 1
        ]
        definition = select_tile_overlay_definition(
            lat, lon, None, providers_config,
            max_resolution_m=native_cap_m,
            bounding_box=cell_box,
            ring_class_m=class_m,
        )
        if definition is not None:
            return class_m, definition["code"], index != ring
    return None


def _approach_ring_layer_feather_m(ring):
    """The feather of the ring whose 1-based index is ``ring``.

    A feather is a number of postings of the COARSER SIDE: ring 1's
    coarser side is ring 2's class, and the last ring's is the 3
    arc-second base class.
    """
    if ring < len(APPROACH_RING_LADDER):
        coarser_m = approach_rung_resolution_m(APPROACH_RING_LADDER[ring][1])
    else:
        coarser_m = base_class_posting_m()
    return approach_ring_feather_m(coarser_m)


def _approach_ring_layers(cells, regions, superseded):
    """Per-class layer records, COARSEST FIRST -- the bake order."""
    by_class = {}
    for cell in cells:
        if not cell.get("provider"):
            continue
        by_class.setdefault(cell["class_m"], []).append(cell)
    layers = []
    for class_m in sorted(by_class, reverse=True):
        members = by_class[class_m]
        ring = min(cell["reach_ring"] for cell in members)
        record = next(
            (r for r in regions if r["class_m"] == class_m), None
        )
        layers.append({
            "class_m": class_m,
            "ring": ring,
            "region": "R%d" % (record["ring"] if record else ring),
            "feather_m": _approach_ring_layer_feather_m(
                record["ring"] if record else ring
            ),
            "providers": sorted({cell["provider"] for cell in members}),
            "cells": [cell["stem"] for cell in members],
        })
    return layers


def _approach_ring_plan_stamp(plan):
    """A stable digest of the plan: which cells, which classes, which
    regions.  A changed provider set changes the cell stems and so the
    stamp -- the plan is then simply COLD (spec section 5: rings NEVER
    re-check at build time; ``--refresh-data rings`` is the one door)."""
    import hashlib

    payload = json.dumps(
        {
            "cells": [
                [cell["column"], cell["row"], cell["class_m"],
                 cell.get("provider"), cell.get("outcome")]
                for cell in plan["cells"]
            ],
            "regions": plan["regions"],
            "superseded": plan["superseded"],
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def approach_ring_frame_problem(lat, lon, plan):
    """THE ONE cold-frame predicate for the rings (census rows 7 + 14).

    A planned cell is ANSWERED when its raster is on disk, when a cell of
    the same stem is already in the tile's coastline band directory (one
    cell cache, two plans -- reused BY REFERENCE, never copied), or when
    a durable no-coverage NEGATIVE is recorded for it.  Anything else is
    UNANSWERED: the app's step-1 pass would fetch it, which in a harness
    build is a shared-repo write as a build side effect.

    Returns ``None`` for a warm (or absent) plan, else a dict with
    ``planned``, ``on_disk``, ``missing``, ``negatives``, ``providers``,
    ``stamp`` and a ready ``text`` naming ``--refresh-data rings``.
    """
    if not plan:
        return None
    state = approach_ring_state(lat, lon, plan)
    if not state["missing"]:
        return None
    state["text"] = (
        "COLD approach elevation rings for tile %+03d%+04d: %d of %d "
        "planned ring cell(s) are UNANSWERED (no raster, no negative) in "
        "%s -- the build would FETCH them mid-measurement (a shared-repo "
        "write as a build side effect, which owner ruling e9daef5 "
        "forbids) or bake rings with holes the base DEM fills, which is "
        "not the surface production renders.  Deliberate fetch: "
        "--refresh-data rings  (missing: %s%s)"
        % (int(lat), int(lon), len(state["missing"]), state["planned"],
           plan["directory"], ", ".join(state["missing"][:4]),
           ", ..." if len(state["missing"]) > 4 else "")
    )
    return state


def approach_ring_state(lat, lon, plan):
    """Disk warmth of a ring plan: what is answered and what is not.

    The shared reporting half of :func:`approach_ring_frame_problem` --
    ``frame.json``'s ``approach_rings`` row and the production provenance
    read the same numbers the refusal counts.
    """
    if not plan:
        return {"planned": 0, "on_disk": 0, "missing": [], "negatives": 0,
                "providers": [], "layers": [], "neighbours_unknown": [],
                "stamp": None}
    recorded = (_read_coastline_band_stamp(
        FNAMES.approach_ring_index(lat, lon)
    ).get("cells") or {})
    on_disk, missing, negatives = 0, [], 0
    for cell in plan["cells"]:
        stem = cell.get("stem")
        if stem is None:
            # A planned cell no provider covers: its negative IS the plan.
            negatives += 1
            continue
        if approach_ring_cell_on_disk(lat, lon, cell):
            on_disk += 1
        elif recorded.get(stem) == NO_RING_COVERAGE:
            negatives += 1
        else:
            missing.append(stem)
    return {
        "planned": len(plan["cells"]),
        "on_disk": on_disk,
        "missing": sorted(missing),
        "negatives": negatives,
        "providers": sorted({
            cell["provider"] for cell in plan["cells"] if cell.get("provider")
        }),
        "layers": [
            {"class_m": layer["class_m"], "ring": layer["ring"],
             "feather_m": layer["feather_m"], "cells": len(layer["cells"])}
            for layer in plan["layers"]
        ],
        "neighbours_unknown": plan.get("neighbours_unknown") or [],
        "stamp": plan.get("stamp"),
    }


def approach_ring_cell_on_disk(lat, lon, cell):
    """The path a planned cell's raster is actually readable at, or None.

    ONE CELL CACHE, TWO PLANS (spec section 5): a cell the coastline band
    already fetched at the same stem is reused BY REFERENCE -- the ring
    bake reads it where it lies and nothing is copied.
    """
    path = cell.get("path")
    if path and os.path.isfile(path):
        return path
    stem = cell.get("stem")
    if not stem:
        return None
    shared = os.path.join(
        FNAMES.coastline_band_directory(lat, lon), stem + ".tif"
    )
    return shared if os.path.isfile(shared) else None


def bake_tile_overlay_into_alt_dem(tile):
    """Blend the cached tile-wide overlay into ``tile.dem.alt_dem``.

    The tile-overlay CALLER of :func:`bake_overlay_layer_into_alt_dem`
    (consumer census row 4): one layer, the whole tile as its region,
    feathered by ``airport_elevation_inset_feather_m`` -- byte-identical
    to the single function this was before the approach rings needed a
    second caller.
    """
    plan = resolve_tile_overlay_plan(tile)
    if plan is None:
        return False
    feather_m = float(
        getattr(tile, "airport_elevation_inset_feather_m", 60.0)
    )
    blended_any = bake_overlay_layer_into_alt_dem(
        tile, plan["path"], feather_m=feather_m,
        label="tile elevation overlay " + plan["definition"]["code"],
    )
    if blended_any:
        tile.dem.tile_overlay_provenance = {
            "provider": plan["definition"]["code"],
            "path": plan["path"],
            "target_resolution_m": plan["target_resolution_m"],
        }
        UI.vprint(
            1,
            "   Tile elevation overlay baked:",
            plan["definition"]["code"],
            "at",
            plan["target_resolution_m"],
            "m.",
        )
    return blended_any


def bake_overlay_layer_into_alt_dem(tile, overlay_path, *, feather_m,
                                    region=None, label=""):
    """Blend ONE cached overlay layer into ``tile.dem.alt_dem``.

    Runs after :func:`O4_Airport_Elevation_Insets.
    densify_tile_dem_for_insets` and BEFORE the airport smoothing pass
    (the overlay is base terrain and is smoothed like base terrain;
    airport insets keep baking last, after smoothing).  Strip-wise
    windowed GDAL reads keep memory bounded at any grid factor.

    Blend weight per cell = (distance-to-tile-edge ramp over the overlay
    feather, ``airport_elevation_inset_feather_m``) x (box-blurred
    valid-data mask over ``feather_m``), so the outer feather band always
    returns to the shared base raster (cross-tile continuity) and
    interior no-coverage regions (ocean, campaign edges) hand back to the
    base softly.  Cells whose bilinear support touches overlay nodata
    keep the base value outright; base-nodata cells take the overlay
    outright (mirroring the airport-inset bake's sentinel guard).

    ``feather_m`` is THE WIDTH OF THIS LAYER'S HAND-BACK -- a number of
    postings of the coarser side it meets (:func:`approach_ring_feather_m`),
    not a fixed metre count.  ``region``, a shapely polygon in absolute
    EPSG:4326 degrees, restricts the layer to that exact area and makes
    its boundary a feathered edge like a data edge; ``None`` means the
    whole raster, which is what the tile-wide overlay wants.  ``label``
    names the layer in the datum warning.

    Returns ``True`` when at least one strip blended overlay data.
    """
    import O4_Airport_Elevation_Insets as INSETS

    if tile.dem is None or tile.dem.alt_dem is None:
        return False
    if not overlay_path or not os.path.isfile(overlay_path):
        return False

    base_dem = tile.dem
    dataset = gdal.Open(overlay_path)
    try:
        band = dataset.GetRasterBand(1)
        overlay_columns = dataset.RasterXSize
        overlay_rows = dataset.RasterYSize
        geotransform = dataset.GetGeoTransform()
        overlay_nodata = band.GetNoDataValue()
        if overlay_nodata is None:
            overlay_nodata = -32768.0
        overlay_nodata = numpy.float32(overlay_nodata)
        # Pixel-centre origin, matching read_elevation_from_file's
        # AREA_OR_POINT=Area convention.
        overlay_x_origin = geotransform[0] + 0.5 * geotransform[1]
        overlay_x_step = geotransform[1]
        overlay_y_origin = geotransform[3] + 0.5 * geotransform[5]
        overlay_y_step = -geotransform[5]  # positive, rows go north->south
        if overlay_x_step <= 0 or overlay_y_step <= 0:
            UI.vprint(
                1,
                "   WARNING: unexpected overlay geotransform in",
                os.path.basename(overlay_path),
                "- skipping the tile overlay bake.",
            )
            return False

        grid_columns = base_dem.nxdem
        grid_rows = base_dem.nydem
        x_step = (base_dem.x1 - base_dem.x0) / (grid_columns - 1)
        y_step = (base_dem.y1 - base_dem.y0) / (grid_rows - 1)
        # Absolute cell-centre coordinates of the working grid.
        grid_x = (
            tile.lon + base_dem.x0 + numpy.arange(grid_columns) * x_step
        )
        grid_y = (
            tile.lat + base_dem.y1 - numpy.arange(grid_rows) * y_step
        )

        centre_latitude = tile.lat + (base_dem.y0 + base_dem.y1) / 2.0
        metres_per_degree_longitude = GEO.lon_to_m(centre_latitude)
        metres_per_degree_latitude = GEO.lat_to_m
        feather_m = float(feather_m)
        # THE TILE-EDGE RAMP IS NOT THIS LAYER'S FEATHER (census row 23):
        # cross-tile continuity is the overlay's own constant, so a 900 m
        # ring feather never widens the seam band a neighbour tile has to
        # match.  For the tile-overlay caller the two are the same value,
        # which is what keeps that bake byte-identical.
        edge_feather_m = float(
            getattr(tile, "airport_elevation_inset_feather_m", 60.0)
        )

        # Fractional overlay pixel coordinates of every grid column (the
        # grid and the overlay are both axis-aligned in EPSG:4326, so the
        # bilinear sample separates into per-column and per-row terms).
        # The overlay pixels are areas: coordinates up to half a pixel
        # outside the outermost pixel CENTRE are still covered (this is
        # where the tile-edge grid rows land), sampled by clamping the
        # bilinear support to the edge pixel.
        # (A millionth of a pixel of slack absorbs degree-arithmetic
        # rounding at the exact half-pixel boundary.)
        half_pixel_slack = 0.5 + 1e-6
        column_pixel = (grid_x - overlay_x_origin) / overlay_x_step
        column_inside = (column_pixel >= -half_pixel_slack) & (
            column_pixel <= overlay_columns - 1 + half_pixel_slack
        )
        column_pixel = numpy.clip(column_pixel, 0.0, overlay_columns - 1)
        column_index = numpy.clip(
            numpy.floor(column_pixel).astype(numpy.int64),
            0,
            overlay_columns - 2,
        )
        column_fraction = (column_pixel - column_index).astype(numpy.float32)

        # Distance-to-tile-edge ramp along columns (metres); the overlay
        # bounding box is exactly the tile, so the ramp doubles as the
        # outside-the-tile guard for combined base rasters whose grid
        # extends past the 1 degree square.
        edge_west = (grid_x - tile.lon) * metres_per_degree_longitude
        edge_east = (tile.lon + 1.0 - grid_x) * metres_per_degree_longitude
        column_edge_m = numpy.minimum(edge_west, edge_east)

        # Feather radius in grid cells for the valid-mask blur.
        posting_m = y_step * metres_per_degree_latitude
        feather_cells = max(int(numpy.ceil(feather_m / posting_m)), 1)

        # Strip sizing: bounded payload per strip plus the blur halo.
        strip_rows = max(int(STRIP_CELL_BUDGET // max(grid_columns, 1)), 8)

        blended_any = False
        ring_samples = []

        def _read_overlay_rows(row_start, row_stop):
            """Read overlay rows [row_start, row_stop) clipped to the file."""
            row_start = max(row_start, 0)
            row_stop = min(row_stop, overlay_rows)
            if row_start >= row_stop:
                return row_start, None
            window = band.ReadAsArray(
                0, row_start, overlay_columns, row_stop - row_start
            )
            if window is None:
                return row_start, None
            return row_start, window.astype(numpy.float32, copy=False)

        def _strip_values_and_valid(row_indices):
            """Bilinear overlay values + validity for the given grid rows."""
            y_values = grid_y[row_indices]
            row_pixel = (overlay_y_origin - y_values) / overlay_y_step
            row_inside = (row_pixel >= -half_pixel_slack) & (
                row_pixel <= overlay_rows - 1 + half_pixel_slack
            )
            row_pixel = numpy.clip(row_pixel, 0.0, overlay_rows - 1)
            row_index = numpy.clip(
                numpy.floor(row_pixel).astype(numpy.int64),
                0,
                overlay_rows - 2,
            )
            row_fraction = (row_pixel - row_index).astype(numpy.float32)
            read_start, window = _read_overlay_rows(
                int(row_index.min()), int(row_index.max()) + 2
            )
            if window is None:
                shape = (len(row_indices), grid_columns)
                return (
                    numpy.zeros(shape, dtype=numpy.float32),
                    numpy.zeros(shape, dtype=bool),
                )
            local_row = row_index - read_start
            v00 = window[numpy.ix_(local_row, column_index)]
            v01 = window[numpy.ix_(local_row, column_index + 1)]
            v10 = window[numpy.ix_(local_row + 1, column_index)]
            v11 = window[numpy.ix_(local_row + 1, column_index + 1)]
            ry = row_fraction[:, None]
            rx = column_fraction[None, :]
            values = (1.0 - ry) * ((1.0 - rx) * v00 + rx * v01) + ry * (
                (1.0 - rx) * v10 + rx * v11
            )
            support_valid = (
                (v00 != overlay_nodata)
                & (v01 != overlay_nodata)
                & (v10 != overlay_nodata)
                & (v11 != overlay_nodata)
            )
            valid = (
                support_valid
                & row_inside[:, None]
                & column_inside[None, :]
            )
            if region is not None:
                # THE EXACT RING-UNION MASK (spec section 3.2): the region
                # polygon is rasterised on this strip's own working-grid
                # cells and ANDed into validity BEFORE the blur, so the
                # blurred hand-back ramps the layer to whatever is already
                # in ``alt_dem`` over the feather INSIDE the region edge.
                valid = valid & _rasterize_region_mask(
                    region, grid_x, y_values, x_step, y_step
                )
            return values.astype(numpy.float32), valid

        def _box_blur_mask(mask_float, radius):
            """Zero-padded separable box blur (both axes, same radius)."""
            window_length = 2 * radius + 1
            for axis in (0, 1):
                padded = numpy.zeros(
                    (
                        mask_float.shape[0]
                        + (window_length - 1) * (axis == 0),
                        mask_float.shape[1]
                        + (window_length - 1) * (axis == 1),
                    ),
                    dtype=numpy.float32,
                )
                offset = radius
                if axis == 0:
                    padded[offset : offset + mask_float.shape[0], :] = (
                        mask_float
                    )
                    summed = numpy.cumsum(padded, axis=0)
                    mask_float = (
                        summed[window_length - 1 :, :]
                        - numpy.vstack(
                            (
                                numpy.zeros(
                                    (1, padded.shape[1]), dtype=numpy.float32
                                ),
                                summed[: -window_length, :],
                            )
                        )
                    ) / window_length
                else:
                    padded[:, offset : offset + mask_float.shape[1]] = (
                        mask_float
                    )
                    summed = numpy.cumsum(padded, axis=1)
                    mask_float = (
                        summed[:, window_length - 1 :]
                        - numpy.hstack(
                            (
                                numpy.zeros(
                                    (padded.shape[0], 1), dtype=numpy.float32
                                ),
                                summed[:, : -window_length],
                            )
                        )
                    ) / window_length
            return mask_float

        for strip_start in range(0, grid_rows, strip_rows):
            strip_stop = min(strip_start + strip_rows, grid_rows)
            halo_start = max(strip_start - feather_cells, 0)
            halo_stop = min(strip_stop + feather_cells, grid_rows)
            extended_rows = numpy.arange(halo_start, halo_stop)
            values_ext, valid_ext = _strip_values_and_valid(extended_rows)
            if not valid_ext.any():
                continue
            # Soft hand-back near no-coverage regions: blur the validity
            # and rescale so cells deep inside data keep weight 1 while
            # the boundary ramps to 0 over ~the feather width.
            data_weight_ext = _box_blur_mask(
                valid_ext.astype(numpy.float32), feather_cells
            )
            data_weight_ext = numpy.clip(
                2.0 * data_weight_ext - 1.0, 0.0, 1.0
            )
            trim_lo = strip_start - halo_start
            trim_hi = trim_lo + (strip_stop - strip_start)
            values = values_ext[trim_lo:trim_hi]
            valid = valid_ext[trim_lo:trim_hi]
            data_weight = data_weight_ext[trim_lo:trim_hi]

            strip_y = grid_y[strip_start:strip_stop]
            edge_south = (strip_y - tile.lat) * metres_per_degree_latitude
            edge_north = (
                tile.lat + 1.0 - strip_y
            ) * metres_per_degree_latitude
            row_edge_m = numpy.minimum(edge_south, edge_north)
            edge_m = numpy.minimum(row_edge_m[:, None], column_edge_m[None, :])
            if edge_feather_m > 0:
                edge_weight = numpy.clip(edge_m / edge_feather_m, 0.0, 1.0)
            else:
                edge_weight = (edge_m >= 0).astype(numpy.float32)

            weight = edge_weight.astype(numpy.float32) * data_weight
            weight[~valid] = 0.0
            if not (weight > 0).any():
                continue

            window = base_dem.alt_dem[strip_start:strip_stop]
            base_nodata = window == base_dem.nodata
            ring = (weight > 0) & (weight < 1) & valid & ~base_nodata
            if ring.any() and len(ring_samples) < 40:
                differences = (values[ring] - window[ring]).ravel()
                ring_samples.append(differences[:10000])
            blended = weight * values + (1.0 - weight) * window
            if base_nodata.any():
                blended = numpy.where(
                    base_nodata,
                    numpy.where(valid, values, window),
                    blended,
                )
            base_dem.alt_dem[strip_start:strip_stop] = blended.astype(
                base_dem.alt_dem.dtype
            )
            blended_any = True
    finally:
        dataset = None

    if ring_samples:
        offset = float(numpy.median(numpy.concatenate(ring_samples)))
        # A few metres is the normal surface-vs-bare-earth gap along the
        # tile-edge feather band; only datum-class magnitudes are
        # actionable (see INSETS.INSET_DATUM_WARNING_THRESHOLD_M).
        if abs(offset) > INSETS.INSET_DATUM_WARNING_THRESHOLD_M:
            UI.vprint(
                1,
                "   WARNING:",
                label or os.path.basename(overlay_path),
                "differs from the base DEM by a median",
                round(offset, 2),
                "m over the feather band (>%d m; check vertical datum)."
                % int(INSETS.INSET_DATUM_WARNING_THRESHOLD_M),
            )
    return blended_any


def _rasterize_region_mask(region, grid_x, y_values, x_step, y_step):
    """Boolean mask of the working-grid cells inside ``region``.

    ``gdal.RasterizeLayer`` on a MEM raster whose geotransform is the
    strip's own cell lattice (pixel-CENTRE grid read as areas, the
    ``AREA_OR_POINT=Area`` convention the bilinear sampler above uses),
    so a cell is in the region when its centre is -- the exact ring
    union, not a cell-granular approximation of it.
    """
    from osgeo import ogr, osr

    columns = len(grid_x)
    rows = len(y_values)
    raster = gdal.GetDriverByName("MEM").Create(
        "", columns, rows, 1, gdal.GDT_Byte
    )
    raster.SetGeoTransform((
        float(grid_x[0]) - 0.5 * x_step, float(x_step), 0.0,
        float(y_values[0]) + 0.5 * y_step, 0.0, -float(y_step),
    ))
    reference = osr.SpatialReference()
    reference.ImportFromEPSG(4326)
    raster.SetProjection(reference.ExportToWkt())
    source = ogr.GetDriverByName("Memory").CreateDataSource("region")
    layer = source.CreateLayer(
        "region", srs=reference, geom_type=ogr.wkbMultiPolygon
    )
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(ogr.CreateGeometryFromWkt(region.wkt))
    layer.CreateFeature(feature)
    gdal.RasterizeLayer(raster, [1], layer, burn_values=[1])
    mask = raster.GetRasterBand(1).ReadAsArray().astype(bool)
    raster = None
    source = None
    return mask
