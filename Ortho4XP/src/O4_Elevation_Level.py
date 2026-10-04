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

import collections
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


# --- The approach-visibility grading ladder (one function, two tables)
# (approach-graded-elevation-rings-spec §1/§3.1; owner RULINGS 2026-10-01g:
# the coastline level's grading is THE RULE TO GENERALISE, not a parallel
# one).  A rung is (reach in metres from the reference geometry, warp
# resolution in metres, label).  Rungs are listed FINEST FIRST and the
# first rung whose reach covers the distance wins.
ApproachRung = collections.namedtuple(
    "ApproachRung", ("reach_m", "resolution_m", "label")
)

#: Reach of each approach ring, measured from the AERODROME BOUNDARY
#: polygon (owner ruling 2026-10-01g, radii CONFIRMED).
APPROACH_RING_1_REACH_M = 10_000.0
APPROACH_RING_2_REACH_M = 20_000.0

#: A feather is a number of POSTINGS OF THE COARSER SIDE, never a fixed
#: metre count (spec §1: the 60 m feather was sized for the 1 m -> 10 m
#: seam and then reused at a 10 m -> 90 m seam where it is 0.65 of one
#: posting -- that is the defect this mechanism fixes).
APPROACH_RING_FEATHER_POSTINGS = 10

#: Feather widths are rounded to this multiple so the law reads as a
#: round number of metres (10 x 30.92 m -> 300 m, 10 x 92.77 m -> 900 m).
APPROACH_RING_FEATHER_ROUNDING_M = 100.0

#: The BASE elevation class a ring 2 hands back to: 3 arc-second posting.
BASE_CLASS_ARC_SECONDS = 3.0

#: The PER-DEFINITION ring opt-in (owner RULINGS 2026-10-02c, spec §9 Q1).
#: A ``.elv`` carrying ``approach_ring_class=<rung label>`` (``ring2``)
#: may serve approach-ring cells of THAT rung and coarser ones even though
#: its access strategy is not wide-area -- Copernicus GLO-30, a SURFACE
#: model, serving ring 2 (1 arc-second to 20 km) only.  It is eligible
#: only where NO wide-area candidate covers the cell (it ranks after every
#: one of them), it never serves a finer rung (the 1 m core and the 10 m
#: ring are never a DSM), and it never enters
#: :func:`_wide_area_candidate_definitions` -- the tile-wide overlay, the
#: coastline band and the working-grid data cap stay blind to it.
APPROACH_RING_CLASS_KEY = "approach_ring_class"


def approach_rung_ladder():
    """The ring ladder: 10 m to 10 km, 1 arc-second to 20 km, base beyond."""
    return (
        ApproachRung(
            APPROACH_RING_1_REACH_M, round(grid_posting_metres(3), 2), "ring1"
        ),
        ApproachRung(
            APPROACH_RING_2_REACH_M, round(grid_posting_metres(1), 2), "ring2"
        ),
    )


def coastline_rung_ladder():
    """The coastline band's own ladder, VALUES UNCHANGED (spec §9 Q2: keep
    both tables, one function, until a coastline-mode sim read)."""
    return (
        ApproachRung(
            COASTLINE_NEAR_AIRPORT_KM * 1000.0,
            round(grid_posting_metres(3), 2),
            "near",
        ),
        ApproachRung(
            COASTLINE_MID_AIRPORT_KM * 1000.0,
            float(COASTLINE_MID_RESOLUTION_M),
            "mid",
        ),
        ApproachRung(
            float("inf"), round(grid_posting_metres(1), 2), "far"
        ),
    )


#: The provenance-sidecar key recording the ladder rung a graded cell was
#: fetched from (owner RULINGS 2026-10-02f).
SURROUND_RUNG_PROVENANCE_KEY = "ring_rung"

#: One chosen ladder rung: its label, the definition to fetch THROUGH, its
#: native resolution in metres, and its filename token.
SurroundRung = collections.namedtuple(
    "SurroundRung",
    ("label", "definition", "native_resolution_m", "token"),
)


def surround_rung_for_class(definition, class_m):
    """THE one derivation of the ladder RUNG a graded cell of ``class_m``
    is fetched from -- shared by the approach rings and the coastline band
    (owner RULINGS 2026-10-02f, the ruling this function exists for).

    A ring or band cell is a SURROUND: one seamless whole-cell raster of
    the cell's class.  Fetching it through the provider's own definition
    takes RUNG 0 -- for USGS3DEP the 1 m lidar PROJECTS resampled to the
    class, which carry the #130 Aspen hole: KASE's ring-1 cells read
    0.0003-0.99 valid and the bake handed the holes back to the 90 m base.

    THE RULE: the rung is the COARSEST rung whose native resolution is at
    most the class, among the rungs that can be a surround
    (:func:`O4_Airport_Elevation_Insets._rung_can_be_surround` -- never a
    point-cloud tile index, never an AOI polygon POST, never a rung judged
    by airport cover: each lists or serves the AIRPORT, not the cell).
    For USGS3DEP that is the ``1/3 arc-second`` rung at BOTH classes --
    ring 1 (10.29 m) because it is the coarsest rung at or under the
    class, and ring 2 (30.87 m) because it is the coarsest rung the
    provider HAS, which is the ruling's "the same product at 30.87 m":
    one product, one datum, one vintage across the 10 m -> 30 m seam
    (spec section 2).

    The ladder is read WITHOUT a bounding box on purpose: the box turns on
    GLOBAL ASSEMBLY (RULINGS 2026-09-30bm), which would join a global 30 m
    member to the chain and make it the coarsest rung under the ring-2
    class -- handing ring 2 to a DIFFERENT product, datum and vintage than
    ring 1, which is exactly what spec section 2 forbids.  "The provider's
    ladder rung" is the provider's own chain.

    Returns a :class:`SurroundRung`, or ``None`` when the provider has no
    surround-capable rung at or under the class -- it is then not a ring
    source for that class, and the caller walks on to the next candidate
    (the collapse rule, unchanged).
    """
    import O4_Airport_Elevation_Insets as INSETS

    if definition is None or class_m is None:
        return None
    limit_m = float(class_m)
    best = None
    for label, rung_definition in INSETS._ladder_rung_definitions(definition):
        if not INSETS._rung_can_be_surround(rung_definition):
            continue
        native_m = INSETS._definition_resolution_m(rung_definition)
        if native_m is None or native_m > limit_m:
            continue
        if best is not None and native_m <= best.native_resolution_m:
            # Strictly coarser wins, so a tie keeps the FINEST-FIRST
            # ladder's own order (the file's rung before a cross-provider
            # rung of the same resolution).
            continue
        best = SurroundRung(
            label,
            rung_definition,
            native_m,
            FNAMES.rung_path_token(label),
        )
    return best


def approach_class(distance_m, ladder):
    """The ladder rung serving a point ``distance_m`` from the reference.

    THE one grading function behind both the coastline band's
    approach-visibility tiers and the approach rings (spec §6 row 5).
    Returns the finest rung whose reach covers the distance, or ``None``
    when every rung is out of reach (the ring ladder's "beyond" case --
    the tile's base DEM stands there).
    """
    for rung in ladder:
        if distance_m <= rung.reach_m:
            return rung
    return None


def approach_ring_feather_m(coarser_posting_m):
    """Feather width for a seam whose COARSER side has this posting.

    :data:`APPROACH_RING_FEATHER_POSTINGS` postings of the coarser class,
    rounded to :data:`APPROACH_RING_FEATHER_ROUNDING_M`.
    """
    raw_m = APPROACH_RING_FEATHER_POSTINGS * float(coarser_posting_m)
    return APPROACH_RING_FEATHER_ROUNDING_M * round(
        raw_m / APPROACH_RING_FEATHER_ROUNDING_M
    )


def approach_ring_feathers_m():
    """``{"ring1_m": 300.0, "ring2_m": 900.0}`` -- each ring's OUTER feather,
    sized on the class it hands back to (ring 1 -> ring 2, ring 2 -> base)."""
    ladder = approach_rung_ladder()
    return {
        "ring1_m": approach_ring_feather_m(ladder[1].resolution_m),
        "ring2_m": approach_ring_feather_m(
            BASE_CLASS_ARC_SECONDS * grid_posting_metres(1)
        ),
    }


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


def select_tile_overlay_definition(lat, lon, level_m, providers_config="auto"):
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
    """
    import O4_Airport_Elevation_Insets as INSETS

    candidates = _wide_area_candidate_definitions(
        lat, lon, providers_config
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


def _wide_area_candidate_definitions(lat, lon, providers_config="auto"):
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
    :func:`elevation_access.base_tiles.base_definition_covers_tile` test,
    all others the cheap coverage-box intersection.  Bathymetry providers
    (role=bathymetry) are excluded outright -- their tidal-datum depths are
    never terrain (spec section 2.1).
    """
    return _registry_definitions_reaching_tile(
        lat, lon, providers_config, require_wide_area=True
    )


def _registry_definitions_reaching_tile(
    lat, lon, providers_config="auto", require_wide_area=True
):
    """The registry walk behind :func:`_wide_area_candidate_definitions`.

    ``require_wide_area=False`` drops ONLY the access-strategy class test
    (the per-definition ``supports_wide_area=False`` opt-out still holds)
    -- the approach-ring opt-in reads the registry through it so the ring
    source set and the wide-area set can never disagree on enablement,
    the providers config, bathymetry exclusion or tile coverage.
    """
    import O4_Airport_Elevation_Insets as INSETS
    from elevation_access import base_tiles as ea_base_tiles
    from elevation_access import definitions as ea_definitions
    from elevation_access import registry as ea_registry

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

    tile_bounding_box = (lon, lat, lon + 1, lat + 1)
    candidates = []
    for definition in INSETS.elevation_providers_dict.values():
        if not definition.get("enabled", True):
            continue
        if (
            allowed_codes is not None
            and definition["code"] not in allowed_codes
        ):
            continue
        strategy_factory = ea_registry.ACCESS_STRATEGIES.get(
            definition.get("access_strategy")
        )
        if strategy_factory is None:
            continue
        if require_wide_area and not getattr(
            strategy_factory, "supports_wide_area", False
        ):
            continue
        if str(definition.get("supports_wide_area", "")).strip().lower() \
                in ("false", "0", "no"):
            # A DEFINITION may opt out where its class reads windows: the
            # USGS Original Product Resolution tiles (#153) are ~1 km
            # GeoTIFFs, often stripped -- a whole-tile overlay would read
            # thousands of them in full.
            continue
        role = definition.get("role", ea_definitions.ROLE_AIRPORT_INSET)
        if role == ea_definitions.ROLE_BATHYMETRY:
            # Bathymetry providers deliver tidal-datum seabed depth and are
            # never terrain sources (spec section 2.1); they must never feed
            # the elevation_level wide-area overlay even if a future one uses
            # a wide-area access strategy.
            continue
        if role == ea_definitions.ROLE_BASE:
            if not ea_base_tiles.base_definition_covers_tile(definition, lat, lon):
                continue
        elif not ea_definitions._coverage_bbox_intersects(
            definition, tile_bounding_box
        ):
            continue
        candidates.append(definition)
    return candidates


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

    # THE shared grading function (spec section 6 row 5): the band's own
    # ladder table, graded by :func:`approach_class` -- the same function
    # the approach rings use, values unchanged (section 9 Q2).
    band_ladder = coastline_rung_ladder()

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
    #: Cells whose class the provider has no surround-capable rung for
    #: (RULINGS 2026-10-02f): the base elevation source stands there.
    cells_without_a_rung = 0
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
            rung = approach_class(airport_distance_m, band_ladder)
            tier = rung.label
            resolution_m = rung.resolution_m
            # THE SAME RULING AS THE RINGS (2026-10-02f): a band cell is a
            # SURROUND of its tier's class, so it is fetched from the
            # ladder rung whose native resolution is at most that class --
            # one derivation site, shared (the band took the ring's defect
            # through the very same no-ladder ``fetch_inset`` call).
            source_rung = surround_rung_for_class(definition, resolution_m)
            if source_rung is None:
                cells_without_a_rung += 1
                continue
            cell_path = FNAMES.coastline_band_cell_dem(
                lat, lon, cell_column, cell_row, code, resolution_m,
                source_rung.token,
            )
            cells.append(
                {
                    "column": cell_column,
                    "row": cell_row,
                    "tier": tier,
                    "resolution_m": resolution_m,
                    "source_rung": source_rung,
                    "path": cell_path,
                    "stem": os.path.splitext(
                        os.path.basename(cell_path)
                    )[0],
                }
            )

    if cells_without_a_rung:
        UI.vprint(
            1,
            "   INFO:",
            cells_without_a_rung,
            "coastline band cell(s) have no",
            code,
            "ladder rung at or under their class (owner ruling"
            " 2026-10-02f); the base elevation source stands there.",
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
                cell["source_rung"].definition,
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


def bake_tile_overlay_into_alt_dem(tile):
    """Blend the cached tile-wide numeric-level overlay into ``alt_dem``.

    The numeric-``elevation_level`` caller of
    :func:`bake_overlay_layer_into_alt_dem`: ONE layer, the whole tile as
    its region (none), feathered over
    ``airport_elevation_inset_feather_m``.  Byte-identical to the
    pre-refactor behaviour (spec section 6 row 4; twin
    ``test_elevation_level.py``).

    Returns ``True`` when at least one strip blended overlay data.
    """
    plan = resolve_tile_overlay_plan(tile)
    if plan is None:
        return False
    if tile.dem is None or tile.dem.alt_dem is None:
        return False
    overlay_path = plan["path"]
    if not os.path.isfile(overlay_path):
        return False
    outcome = bake_overlay_layer_into_alt_dem(
        tile,
        overlay_path,
        feather_m=float(
            getattr(tile, "airport_elevation_inset_feather_m", 60.0)
        ),
        region=None,
        label="tile elevation overlay",
    )
    if outcome["blended"]:
        tile.dem.tile_overlay_provenance = {
            "provider": plan["definition"]["code"],
            "path": overlay_path,
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
    return outcome["blended"]


def _region_strip_mask(
    region_wkt, grid_x, grid_y, row_start, row_stop, x_step, y_step
):
    """Boolean mask of the working-grid rows ``[row_start, row_stop)`` that
    lie INSIDE ``region_wkt`` (EPSG:4326 degrees).

    The exact ring-union mask of spec section 3.2: the region polygon is
    rasterised onto a MEM raster of exactly this strip's cells, so a ring
    edge is the polygon's edge rather than a cell-grid staircase.  No new
    geometry code -- GDAL's own rasteriser.
    """
    from osgeo import ogr, osr

    columns = len(grid_x)
    rows = int(row_stop) - int(row_start)
    raster = gdal.GetDriverByName("MEM").Create(
        "", columns, rows, 1, gdal.GDT_Byte
    )
    # Pixel-AREA geotransform around the grid's cell CENTRES.
    raster.SetGeoTransform(
        (
            float(grid_x[0]) - 0.5 * x_step,
            x_step,
            0.0,
            float(grid_y[row_start]) + 0.5 * y_step,
            0.0,
            -y_step,
        )
    )
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    raster.SetProjection(srs.ExportToWkt())
    source = ogr.GetDriverByName("Memory").CreateDataSource("region")
    try:
        layer = source.CreateLayer("region", srs, ogr.wkbPolygon)
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(ogr.CreateGeometryFromWkt(region_wkt))
        layer.CreateFeature(feature)
        feature = None
        gdal.RasterizeLayer(raster, [1], layer, burn_values=[1])
        mask = raster.GetRasterBand(1).ReadAsArray()
    finally:
        source = None
        raster = None
    if mask is None:
        return numpy.zeros((rows, columns), dtype=bool)
    return mask.astype(bool)


def bake_overlay_layer_into_alt_dem(
    tile, overlay_path, *, feather_m, region=None, label="overlay"
):
    """Blend ONE cached elevation layer into ``tile.dem.alt_dem``.

    The tile-overlay bake's body, parameterised (spec section 3.2 / section 6
    row 4) so the numeric level, the coastline band and each approach
    ring class bake through ONE implementation.  Runs after
    :func:`O4_Airport_Elevation_Insets.densify_tile_dem_for_insets` and
    BEFORE the airport smoothing pass (every layer here is base terrain
    and is smoothed like base terrain; airport insets keep baking last,
    after smoothing).  Strip-wise windowed GDAL reads keep memory bounded
    at any grid factor.

    Blend weight per cell = (distance-to-tile-edge ramp over the feather
    width) x (box-blurred valid-data mask), so the outer feather band
    always returns to the shared base raster (cross-tile continuity) and
    interior no-coverage regions (ocean, campaign edges) hand back to the
    base softly.  Cells whose bilinear support touches overlay nodata
    keep the base value outright; base-nodata cells take the overlay
    outright (mirroring the airport-inset bake's sentinel guard).

    ``feather_m`` is the hand-back width, a number of POSTINGS OF THE
    COARSER SIDE for a ring layer (:func:`approach_ring_feather_m`).
    ``region`` is an optional EPSG:4326 polygon WKT (or any shapely
    geometry) ANDed into the strip's validity: the layer is blended only
    inside it, and the blurred-mask hand-back then ramps the layer to
    whatever is already in ``alt_dem`` over ``feather_m`` INSIDE the
    region edge.  ``label`` names the layer in log lines.

    Returns ``{"blended": bool, "offset_m": float | None}`` -- the median
    layer-minus-current difference over the feather band, the datum
    comparator (``None`` when no feather cell carried data).
    """
    import O4_Airport_Elevation_Insets as INSETS

    if tile.dem is None or tile.dem.alt_dem is None:
        return {"blended": False, "offset_m": None}
    if not os.path.isfile(overlay_path):
        return {"blended": False, "offset_m": None}
    region_wkt = None
    if region is not None:
        region_wkt = (
            region if isinstance(region, str) else region.wkt
        )

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
            if region_wkt is not None and valid_ext.any():
                # The exact ring-union mask: a layer is blended only
                # inside its own region, and the blurred hand-back below
                # feathers it to whatever already sits in ``alt_dem``
                # over ``feather_m`` INSIDE the region edge.
                valid_ext = valid_ext & _region_strip_mask(
                    region_wkt,
                    grid_x,
                    grid_y,
                    halo_start,
                    halo_stop,
                    x_step,
                    y_step,
                )
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
            if feather_m > 0:
                edge_weight = numpy.clip(edge_m / feather_m, 0.0, 1.0)
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

    offset = None
    if ring_samples:
        offset = float(numpy.median(numpy.concatenate(ring_samples)))
        # A few metres is the normal surface-vs-bare-earth gap along the
        # feather band; only datum-class magnitudes are actionable (see
        # INSETS.INSET_DATUM_WARNING_THRESHOLD_M).
        if abs(offset) > INSETS.INSET_DATUM_WARNING_THRESHOLD_M:
            UI.vprint(
                1,
                "   WARNING:",
                label,
                os.path.basename(overlay_path),
                "differs from the surface underneath by a median",
                round(offset, 2),
                "m over the feather band (>%d m; check vertical datum)."
                % int(INSETS.INSET_DATUM_WARNING_THRESHOLD_M),
            )
    return {"blended": blended_any, "offset_m": offset}


# ══════════════════════════════════════════════════════════════════════
# APPROACH-GRADED ELEVATION RINGS
# docs/specs/approach-graded-elevation-rings-spec.md (#164);
# owner RULINGS 2026-10-01g (the ruling, radii CONFIRMED, measured from
# the AERODROME BOUNDARY) / 10-01h (the spec's mechanism).
#
# The coastline band mechanism GENERALISED, as the owner ruled: per-tile
# 0.1 degree cells graded by distance to the nearest aerodrome boundary
# (this tile's and a cached neighbour's), cached per cell, assembled per
# CLASS and baked coarsest-first through the strip bake as base terrain
# -- NOT a per-airport N-layer raster.  The inset box, the core buffer
# and the inset bake are UNCHANGED (spec section 4).
# ══════════════════════════════════════════════════════════════════════

#: ``approach_rings`` configuration values.  ``off`` is byte-identical to
#: the pre-rings behaviour (the gate the owner's sim read adjudicates;
#: BUILD ECONOMY says it is removed once adjudicated).
APPROACH_RINGS_AUTO = "auto"
APPROACH_RINGS_OFF = "off"

#: A NEIGHBOUR tile's aerodrome contributes rings to this tile when its
#: boundary lies within the outermost ring's reach of the tile square.
APPROACH_RING_NEIGHBOUR_REACH_M = APPROACH_RING_2_REACH_M

#: The eight neighbouring tile cells, in a deterministic order.
APPROACH_RING_NEIGHBOUR_OFFSETS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1), (0, 1),
    (1, -1), (1, 0), (1, 1),
)

#: Recorded per cell in the stamp when a FINER tile-wide product already
#: delivers that class (spec section 7 precedence: the finest class wins per
#: cell, and a ring never coarsens a level).
APPROACH_RING_SUPERSEDED = "superseded"


def approach_rings_enabled(tile):
    """True when ``approach_rings`` admits the ring overlay on this tile.

    ``auto`` (the default) bakes the rings; ``off`` is the gate that keeps
    the pre-rings behaviour byte-identical.  An unrecognised value
    degrades to ``auto`` with one warning, like every other level value.
    """
    value = getattr(tile, "approach_rings", APPROACH_RINGS_AUTO)
    if value is None:
        return True
    text = str(value).strip().lower()
    if text in ("", APPROACH_RINGS_AUTO):
        return True
    if text == APPROACH_RINGS_OFF:
        return False
    UI.vprint(
        1,
        "   WARNING: unrecognised approach_rings",
        repr(value),
        "- using auto.",
    )
    return True


def _approach_ring_candidates(
    lat, lon, providers_config, max_native_m, rung_label=None, ladder=None
):
    """Wide-area definitions covering the tile whose NATIVE resolution is at
    most ``max_native_m``, in :func:`select_tile_overlay_definition`'s own
    ranking (finest first, then priority, then code) -- FOLLOWED BY the
    ring opt-in definitions eligible for ``rung_label`` (RULINGS
    2026-10-02c), ranked the same way among themselves.

    Spec section 2: ring sources come through the EXISTING registry -- the
    wide-area candidate set with ONE added native-resolution filter -- never
    a second registry.  A definition that does not declare its resolution
    is not a candidate: a ring's class is the whole point of the ring.
    The opt-ins rank strictly AFTER every wide-area candidate: the surface
    model serves a cell only where no wide-area source covers it (the
    caller walks the list and takes the first that covers the cell).
    """
    import O4_Airport_Elevation_Insets as INSETS

    def _ranked(definitions, seen):
        rows = []
        for definition in definitions:
            if definition["code"] in seen:
                continue
            native_m = INSETS._definition_resolution_m(definition)
            if native_m is None or native_m > max_native_m:
                continue
            rows.append(
                (
                    native_m,
                    -float(definition.get("priority", 0.0)),
                    definition["code"],
                    definition,
                )
            )
        rows.sort(key=lambda row: row[:3])
        return [row[3] for row in rows]

    wide_area = _ranked(
        _wide_area_candidate_definitions(lat, lon, providers_config), set()
    )
    if rung_label is None:
        return wide_area
    opt_ins = _ranked(
        _approach_ring_opt_in_definitions(
            lat, lon, providers_config, rung_label, ladder
        ),
        {definition["code"] for definition in wide_area},
    )
    return wide_area + opt_ins


def approach_ring_opt_in_rung(definition, ladder=None):
    """The finest ring rung label a definition opted into, or ``None``.

    ``approach_ring_class`` names a rung of :func:`approach_rung_ladder`
    by its label; an unknown label opts into nothing (fail closed -- a
    typo must never let a surface model into a finer ring).
    """
    value = str((definition or {}).get(APPROACH_RING_CLASS_KEY, "") or "")
    value = value.strip().lower()
    if not value:
        return None
    labels = [rung.label for rung in (ladder or approach_rung_ladder())]
    return value if value in labels else None


def _approach_ring_opt_in_definitions(
    lat, lon, providers_config, rung_label, ladder=None
):
    """Registry definitions that opted into the ring ``rung_label``.

    A definition opted into rung ``k`` serves rung ``k`` and every
    COARSER rung, never a finer one.  Read through
    :func:`_registry_definitions_reaching_tile` WITHOUT the wide-area
    strategy test -- the only filter dropped; everything else (enabled,
    providers config, bathymetry, coverage) is the wide-area walk's own.
    """
    labels = [rung.label for rung in (ladder or approach_rung_ladder())]
    if rung_label not in labels:
        return []
    rung_index = labels.index(rung_label)
    eligible = []
    for definition in _registry_definitions_reaching_tile(
        lat, lon, providers_config, require_wide_area=False
    ):
        opted = approach_ring_opt_in_rung(definition, ladder)
        if opted is None:
            continue
        if labels.index(opted) <= rung_index:
            eligible.append(definition)
    return eligible


def approach_ring_cell_box(lat, lon, column, row):
    """The ``(west, south, east, north)`` degree box of one 0.1 degree cell."""
    return (
        lon + column * COASTLINE_CELL_DEGREES,
        lat + row * COASTLINE_CELL_DEGREES,
        lon + (column + 1) * COASTLINE_CELL_DEGREES,
        lat + (row + 1) * COASTLINE_CELL_DEGREES,
    )


def _definition_covers_box(definition, box):
    """Cheap per-cell coverage test, the candidate filter's own convention."""
    from elevation_access import definitions as ea_definitions

    role = definition.get("role", ea_definitions.ROLE_AIRPORT_INSET)
    if role == ea_definitions.ROLE_BASE:
        # A base definition's coverage was already resolved for the whole
        # tile by the candidate filter; every cell of the tile is covered.
        return True
    return bool(ea_definitions._coverage_bbox_intersects(definition, box))


def _neighbour_boundary_polygons(lat, lon, reach_m):
    """Aerodrome boundaries of the eight neighbour tiles that reach into this
    tile, read ONLY from the cached airports layers.

    Returns ``(polygons, unknown)``: ``polygons`` is
    ``{"<ICAO>@<stem>": geometry}`` for each admitted aerodrome of a
    neighbour whose cached layer exists and whose boundary lies within
    ``reach_m`` of this tile square; ``unknown`` lists the stems of
    neighbours with NO cached airports layer.  A neighbour with no cached
    layer contributes nothing and is RECORDED -- never a refusal (the
    coastline spec's recorded limit, closed where the data is there).
    """
    import O4_Airport_Elevation_Insets as INSETS
    from elevation_access import las_tiles as ea_las_tiles
    import O4_Airport_Modes as MODES
    import O4_Config_Utils as CFG
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP
    from shapely.geometry import box as _box

    polygons = {}
    unknown = []
    tile_square = _box(lon, lat, lon + 1.0, lat + 1.0)
    for d_lat, d_lon in APPROACH_RING_NEIGHBOUR_OFFSETS:
        n_lat, n_lon = lat + d_lat, lon + d_lon
        stem = "%+03d%+04d" % (n_lat, n_lon)
        cached = FNAMES.osm_cached(n_lat, n_lon, "airports")
        if not os.path.isfile(cached):
            unknown.append(stem)
            continue
        try:
            neighbour = CFG.Tile(n_lat, n_lon, "")
            neighbour.read_from_config()
            layer = OSM.OSM_layer()
            layer.update_dicosm(cached)
            dico = VMAP.build_airports_dico(neighbour, layer)
            selected = MODES.inset_keys(
                dico, MODES.resolved_inset_mode(neighbour)
            )
            boundaries = INSETS.airport_boundary_polygons(
                neighbour, dico, only=selected
            )
        except Exception as error:
            # A neighbour whose cached layer cannot be parsed is UNKNOWN,
            # not absent: the difference is recorded, never guessed.
            UI.vprint(
                2,
                "   Approach rings: neighbour tile",
                stem,
                "airports layer unreadable (",
                type(error).__name__,
                "); recorded as unknown.",
            )
            unknown.append(stem)
            continue
        for airport, geometry in boundaries.items():
            grown = ea_las_tiles._buffer_geometry_m(geometry, reach_m)
            if grown.is_empty or not grown.intersects(tile_square):
                continue
            polygons["%s@%s" % (airport, stem)] = geometry
    return polygons, sorted(unknown)


def resolve_approach_ring_plan(tile, dico_airports):
    """THE one derivation of the tile's ring cells, classes and regions.

    Pure and offline (spec section 3.1 / section 6 row 2): both build steps, the
    harness frame check and the app's fetch pass re-derive it from the
    same disk state, so they can never disagree.  Returns ``None`` when
    the feature is off, GDAL is missing, ``custom_dem`` pins the raster,
    or no admitted aerodrome on (or next to) the tile holds an inset.

    The plan:

    * **airports** -- every string-keyed aerodrome of ``dico_airports``
      admitted by the tile's inset MODE whose inset exists on disk, PLUS
      the admitted aerodromes of each neighbour tile whose cached
      airports layer exists and whose boundary reaches into this tile
      (:func:`_neighbour_boundary_polygons`; the rest are recorded in
      ``neighbours_unknown``);
    * **regions** -- ``R1`` / ``R2``, the unions of the boundary polygons
      buffered by each rung's reach.  Measured from the BOUNDARY, as
      ruled -- not the ARP, not the inset box;
    * **cells** -- the tile's 10 x 10 grid of 0.1 degree cells; a cell is
      fetched at the FINEST class any part of it needs (the exact ring
      edge is the bake's business, not the fetch's), from the finest
      wide-area provider covering it.  Ring 1 collapses into ring 2
      where no provider native <= 10 m covers the cell; a cell no ring-2
      provider covers either is ``no-coverage`` and the base DEM stands;
    * **layers** -- the cells grouped by class, plus ``ring_layers``
      coarsest-first with each layer's region and feather, the order the
      bake must use.
    """
    if not approach_rings_enabled(tile):
        return None
    if not has_gdal:
        return None
    if getattr(tile, "custom_dem", ""):
        # The user's raster is authoritative (as for the band, spec section 7).
        return None

    import O4_Airport_Elevation_Insets as INSETS
    from elevation_access import las_tiles as ea_las_tiles
    import O4_Airport_Modes as MODES
    from shapely.ops import unary_union

    lat, lon = int(tile.lat), int(tile.lon)
    providers_config = getattr(tile, "airport_elevation_providers", "auto")
    level_m = parse_elevation_level(getattr(tile, "elevation_level", "auto"))

    mode = MODES.resolved_inset_mode(tile)
    selected = MODES.inset_keys(dico_airports or {}, mode)
    holders = [
        airport
        for airport in selected
        if INSETS.cached_inset_paths_for_icao(
            lat, lon, airport, providers_config
        )
    ]
    boundaries = INSETS.airport_boundary_polygons(
        tile, dico_airports or {}, only=holders
    )
    neighbours, neighbours_unknown = _neighbour_boundary_polygons(
        lat, lon, APPROACH_RING_NEIGHBOUR_REACH_M
    )
    boundaries = dict(boundaries)
    boundaries.update(neighbours)
    if not boundaries:
        return None

    ladder = approach_rung_ladder()
    feathers = approach_ring_feathers_m()
    regions = {}
    for index, rung in enumerate(ladder, start=1):
        grown = [
            ea_las_tiles._buffer_geometry_m(geometry, rung.reach_m)
            for geometry in boundaries.values()
        ]
        regions["R%d" % index] = unary_union(grown)

    cells = []
    layers = {}
    cell_count = int(round(1.0 / COASTLINE_CELL_DEGREES))
    for column in range(cell_count):
        for row in range(cell_count):
            box = approach_ring_cell_box(lat, lon, column, row)
            reach_ring = None
            reach_index = None
            for index, rung in enumerate(ladder, start=1):
                if regions["R%d" % index].intersects(_box_geometry(box)):
                    reach_ring = rung
                    reach_index = index
                    break
            if reach_ring is None:
                continue
            cell = _approach_ring_cell(
                lat, lon, column, row, box, reach_ring, ladder,
                providers_config, level_m, feathers,
            )
            cell["reach_index"] = reach_index
            cells.append(cell)
    for cell in cells:
        if cell["provider"] is None or cell.get("state") == \
                APPROACH_RING_SUPERSEDED:
            continue
        layers.setdefault(_class_key(cell["class_m"]), []).append(cell["stem"])

    ring_layers = []
    for index, rung in enumerate(ladder, start=1):
        key = "ring%d" % index
        # A layer's VRT carries every planned cell whose raster COVERS any
        # part of that ring's region -- which is every cell at or inside
        # the ring's own reach, because the regions nest (R1 subset R2).
        #
        # DEVIATION from spec §3.2's letter (reported to the spec author,
        # never decided here): §3.2 names the ring-2 layer "the VRT of the
        # plan's 30.87 m cells".  But a cell STRADDLING the R1 edge is
        # fetched at the ring-1 class (§3.1: "a cell is fetched at the
        # FINEST class any part of it needs"), so under the letter its
        # ring-2 part would be served by NEITHER layer -- an unfeathered
        # hole in the ring-2 annulus that the 90 m base fills, which is
        # the defect the rings exist to remove.  Including the finer cell
        # in the coarser layer costs no fetch and no memory (§3.1's
        # "over-delivery") and the finer layer still bakes over it.
        members = [
            cell
            for cell in cells
            if cell.get("reach_index") is not None
            and cell["reach_index"] <= index
            and cell["provider"] is not None
            and cell.get("state") != APPROACH_RING_SUPERSEDED
        ]
        if not members:
            continue
        if not any(cell["ring"] == rung.label for cell in members):
            # Nothing was fetched AT this class -- the collapse rule sent
            # every cell of this reach to a coarser rung, and that coarser
            # layer already covers this region with the same data.  A
            # layer with no data of its own class would re-bake the
            # coarser raster behind a narrower feather.
            continue
        if level_m is not None and level_m <= rung.resolution_m:
            # The tile-wide level already delivers this class: the layer
            # is SUPERSEDED even though finer cells exist for the ring
            # inside it (spec §7 -- a ring never coarsens a level).
            continue
        ring_layers.append(
            {
                "ring": key,
                "class_m": rung.resolution_m,
                "feather_m": feathers["%s_m" % key],
                "region": regions["R%d" % index].wkt,
                "cells": [cell["stem"] for cell in members],
            }
        )
    # COARSEST FIRST (spec section 3.2): a finer layer baked after a coarser
    # one is what makes "the finest class wins per cell" true of the
    # baked surface, feather bands included.
    ring_layers.sort(key=lambda layer: -layer["class_m"])

    return {
        "cells": cells,
        "layers": layers,
        "ring_layers": ring_layers,
        "regions": {name: geometry.wkt for name, geometry in regions.items()},
        "airports": sorted(boundaries),
        "neighbours_unknown": neighbours_unknown,
        "feathers": feathers,
        "elevation_level": level_m,
        "coastline_mode": is_coastline_mode(
            getattr(tile, "elevation_level", "auto")
        ),
    }


def _box_geometry(box):
    from shapely.geometry import box as _box

    return _box(*box)


def _class_key(class_m):
    """Stable string key for a ring class resolution (the stamp is JSON)."""
    return "%.2f" % float(class_m)


def _approach_ring_cell(
    lat, lon, column, row, box, reach_ring, ladder, providers_config,
    level_m, feathers,
):
    """One plan cell: its class, its provider and its cache path.

    Collapse rule (spec section 2): the cell is fetched at ``reach_ring``'s
    class from the finest wide-area provider native-fine enough for it;
    when none covers the cell, ring 1 COLLAPSES into ring 2 (the cell is
    fetched at the coarser class instead), and when no provider covers it
    at all the cell carries ``provider: None`` -- a no-coverage cell where
    the tile's base DEM stands.
    """
    rungs = list(ladder)
    start = rungs.index(reach_ring)
    for rung in rungs[start:]:
        if level_m is not None and level_m <= rung.resolution_m:
            # A tile-wide level already delivers this class or finer:
            # SUPERSEDED (spec section 7 -- a ring never coarsens a level).
            return {
                "column": column,
                "row": row,
                "ring": rung.label,
                "class_m": rung.resolution_m,
                "reach_ring": reach_ring.label,
                "provider": None,
                "source_rung": None,
                "state": APPROACH_RING_SUPERSEDED,
                "path": None,
                "band_path": None,
                "stem": None,
            }
        for definition in _approach_ring_candidates(
            lat, lon, providers_config, rung.resolution_m,
            rung_label=rung.label, ladder=rungs,
        ):
            if not _definition_covers_box(definition, box):
                continue
            # THE RULING (2026-10-02f): the cell is fetched from the
            # provider's ladder rung whose native resolution is at most
            # this class -- never the provider's own 1 m discovery.  A
            # provider with no such rung is not a ring source for the
            # class: walk on (the collapse rule, unchanged).
            source_rung = surround_rung_for_class(
                definition, rung.resolution_m
            )
            if source_rung is None:
                continue
            code = definition["code"]
            path = FNAMES.approach_ring_cell_dem(
                lat, lon, column, row, code, rung.resolution_m,
                source_rung.token,
            )
            return {
                "column": column,
                "row": row,
                "ring": rung.label,
                "class_m": rung.resolution_m,
                "reach_ring": reach_ring.label,
                "provider": code,
                "source_rung": source_rung.label,
                "source_rung_native_m": source_rung.native_resolution_m,
                "source_rung_token": source_rung.token,
                "state": None,
                "path": path,
                # ONE cell cache, two plans (spec section 5): a cell already
                # fetched for the coastline band at the same stem is
                # reused BY REFERENCE, never copied.  The rung is part of
                # the stem, so the two plans share a cell only when they
                # fetched it from the same rung.
                "band_path": FNAMES.coastline_band_cell_dem(
                    lat, lon, column, row, code, rung.resolution_m,
                    source_rung.token,
                ),
                "stem": os.path.splitext(os.path.basename(path))[0],
            }
    return {
        "column": column,
        "row": row,
        "ring": reach_ring.label,
        "class_m": reach_ring.resolution_m,
        "reach_ring": reach_ring.label,
        "provider": None,
        "source_rung": None,
        "state": "no-provider",
        "path": None,
        "band_path": None,
        "stem": None,
    }


def approach_ring_cell_source(cell):
    """The on-disk raster answering a plan cell, or ``None``.

    The ring cache first, then the coastline band's cell of the SAME stem
    (reused by reference, spec section 5).
    """
    for key in ("path", "band_path"):
        path = cell.get(key)
        if path and os.path.isfile(path):
            return path
    return None


def read_approach_ring_stamp(lat, lon):
    """The ring ``index.json`` stamp (plan digest, per-cell outcomes)."""
    return _read_coastline_band_stamp(FNAMES.approach_ring_index(lat, lon))


#: The stamp's date-of-derivation key; a change in it alone never rewrites.
APPROACH_RING_STAMP_DATE_KEY = "checked"


def write_approach_ring_stamp(lat, lon, stamp):
    """Write the ring stamp -- ONLY when it changed.

    A byte-identical stamp is never rewritten (owner ruling e9daef5: a
    build must not touch the shared repo as a side effect).
    """
    path = FNAMES.approach_ring_index(lat, lon)
    payload = json.dumps(stamp, indent=2, sort_keys=True)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                previous = handle.read()
            if previous == payload:
                return False
            # A DATE-ONLY change is not a change (the ladder re-check's own
            # rule): a stamp warmed yesterday and re-derived today must not
            # be rewritten, or every build after a warm is a shared-repo
            # write the guard refuses (measured 2026-10-02, KASE tile).
            try:
                before = json.loads(previous)
            except ValueError:
                before = None
            if isinstance(before, dict):
                strip = lambda d: {k: v for k, v in d.items()
                                   if k != APPROACH_RING_STAMP_DATE_KEY}
                if strip(before) == strip(stamp):
                    return False
        except OSError:
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    return True


def approach_ring_plan_stamp(plan):
    """Digest of a plan -- the stamp key a changed provider set moves."""
    import hashlib

    payload = json.dumps(
        {
            "airports": plan["airports"],
            "cells": [
                # The chosen RUNG is part of the key (owner RULINGS
                # 2026-10-02f): a cell fetched under the old no-ladder
                # rule is not the planned file and the stamp moves with it.
                [
                    c["column"],
                    c["row"],
                    c["stem"],
                    c["provider"],
                    c["ring"],
                    c.get("source_rung"),
                ]
                for c in plan["cells"]
            ],
            "feathers": plan["feathers"],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def approach_ring_frame_problem(lat, lon, plan):
    """THE one cold-ring predicate, shared by the harness and production.

    An UNANSWERED planned cell -- no raster on disk and no recorded
    negative -- means a build would either fetch into the shared repo as a
    side effect or silently bake a hole the base DEM fills.  Returns
    ``None`` when every planned cell is answered, else
    ``("cold", text)`` naming the count and ``--refresh-data rings``.

    Rings NEVER re-check (spec section 5): a changed provider set changes the
    planned stem, so the old cell is simply not the planned file.
    """
    if not plan:
        return None
    outcomes = (read_approach_ring_stamp(lat, lon) or {}).get("cells", {})
    unanswered = [
        cell
        for cell in plan["cells"]
        if cell.get("provider")
        and approach_ring_cell_source(cell) is None
        and outcomes.get(cell["stem"]) != NO_RING_COVERAGE
    ]
    if not unanswered:
        return None
    sample = ", ".join(cell["stem"] for cell in unanswered[:3])
    return (
        "cold",
        "%d of %d planned approach-ring cell(s) for %+03d%+04d are "
        "UNANSWERED (no raster, no recorded negative; e.g. %s) -- the "
        "build would either FETCH them into the shared data repo as a "
        "side effect (owner ruling e9daef5 forbids it) or bake a ring "
        "with holes the 90 m base fills, which is the grade ring the "
        "rings exist to remove.  Deliberate fetch: --refresh-data rings"
        % (len(unanswered), len(plan["cells"]), lat, lon, sample),
    )


#: A cell no provider covers.  The band's own spelling, so one decoder
#: reads both stamps.
NO_RING_COVERAGE = "no-coverage"


def summarize_approach_rings(lat, lon, plan):
    """``frame.json``'s ``approach_rings`` row (spec section 5).

    Pure disk state plus the plan -- recorded whether or not anything is
    cold, because "which ring cells did this build bake" is a question
    later readers ask of numbers already in a report.
    """
    if not plan:
        return None
    outcomes = (read_approach_ring_stamp(lat, lon) or {}).get("cells", {})
    planned = [cell for cell in plan["cells"] if cell.get("provider")]
    on_disk = [c for c in planned if approach_ring_cell_source(c) is not None]
    negatives = [
        c["stem"]
        for c in plan["cells"]
        if outcomes.get(c["stem"]) == NO_RING_COVERAGE
    ]
    return {
        "planned": len(planned),
        "on_disk": len(on_disk),
        "missing": len(planned) - len(on_disk),
        "negatives": sorted(negatives),
        "providers": sorted(
            {c["provider"] for c in planned if c.get("provider")}
        ),
        # WHICH RUNG answered each class (owner RULINGS 2026-10-02f): the
        # provider alone does not say -- USGS3DEP's 1 m discovery and its
        # 1/3 arc-second rung are the same provider and a different
        # product, and only one of them is a lawful ring source.
        "rungs": sorted(
            {c["source_rung"] for c in planned if c.get("source_rung")}
        ),
        "layers": {
            layer["ring"]: {
                "class_m": layer["class_m"],
                "feather_m": layer["feather_m"],
                "cells": len(layer["cells"]),
            }
            for layer in plan["ring_layers"]
        },
        "superseded": sum(
            1
            for c in plan["cells"]
            if c.get("state") == APPROACH_RING_SUPERSEDED
        ),
        "neighbours_unknown": plan["neighbours_unknown"],
        "airports": plan["airports"],
        "stamp": approach_ring_plan_stamp(plan),
    }


def ensure_approach_rings(tile, dico_airports, refresh=False):
    """Fetch (or recycle) every planned approach-ring cell -- the step-1
    download hook, beside :func:`ensure_tile_overlay` (spec section 6 row 1).

    The coastline band's loop over the plan's cells: one
    :func:`O4_Airport_Elevation_Insets.fetch_inset` per MISSING cell, a
    cached cell recycled, a clean "no usable coverage" answer recorded as
    a durable negative, a raised failure skipped WITHOUT a negative (it
    may be a transient outage), and a constant-value raster discarded as
    a fill served beyond the provider's true extent.  A cell already in
    the tile's coastline-band directory under the same stem is reused by
    reference and never re-fetched.

    Sets ``tile.rings_fetched_last_build`` -- mirrored into the tile build
    record as ``features.rings_fetched``, which disqualifies the run as a
    build-time measurement exactly as ``insets_fetched`` does.  Returns
    the number of cells fetched.
    """
    import O4_Airport_Elevation_Insets as INSETS

    tile.rings_fetched_last_build = 0
    plan = resolve_approach_ring_plan(tile, dico_airports)
    if plan is None:
        return 0
    lat, lon = int(tile.lat), int(tile.lon)
    stamp = read_approach_ring_stamp(lat, lon) or {}
    outcomes = {
        stem: outcome
        for stem, outcome in (stamp.get("cells") or {}).items()
        if outcome == NO_RING_COVERAGE
    }
    fetched = 0
    for cell in plan["cells"]:
        if not cell.get("provider"):
            continue
        stem = cell["stem"]
        existing = approach_ring_cell_source(cell)
        if existing is not None and not refresh:
            if INSETS.geotiff_is_constant_value(existing):
                _discard_implausible_ring_cell(existing, stem, outcomes)
            else:
                outcomes[stem] = "ok"
            continue
        if outcomes.get(stem) == NO_RING_COVERAGE and not refresh:
            continue
        definition = INSETS.elevation_providers_dict.get(cell["provider"])
        if definition is None:
            continue
        # THE RULING (2026-10-02f): fetch THROUGH the planned rung, not
        # through the provider's own (1 m, project-discovered) definition.
        source_rung = surround_rung_for_class(definition, cell["class_m"])
        if source_rung is None or source_rung.label != cell.get("source_rung"):
            # The registry moved under the plan derived at the top of this
            # function: the planned stem is not what this rung would write.
            UI.vprint(
                2,
                "   Approach ring cell",
                stem,
                "plans rung",
                cell.get("source_rung"),
                "but the registry now offers",
                None if source_rung is None else source_rung.label,
                "- skipping it.",
            )
            continue
        os.makedirs(FNAMES.approach_ring_directory(lat, lon), exist_ok=True)
        try:
            provenance = INSETS.fetch_inset(
                source_rung.definition,
                approach_ring_cell_box(lat, lon, cell["column"], cell["row"]),
                cell["class_m"],
                cell["path"],
            )
        except Exception as error:
            UI.vprint(
                2,
                "   Approach ring cell fetch error at",
                stem,
                ":",
                str(error),
            )
            continue
        if provenance is None:
            outcomes[stem] = NO_RING_COVERAGE
        elif INSETS.geotiff_is_constant_value(cell["path"]):
            _discard_implausible_ring_cell(cell["path"], stem, outcomes)
        else:
            outcomes[stem] = "ok"
            fetched += 1
            record = dict(provenance)
            record["fetch_date"] = datetime.date.today().isoformat()
            # The sidecar records the RUNG (owner RULINGS 2026-10-02f): a
            # cell's class alone does not say which product answered it.
            record[SURROUND_RUNG_PROVENANCE_KEY] = {
                "label": source_rung.label,
                "native_resolution_m": source_rung.native_resolution_m,
                "provider": source_rung.definition.get(
                    "code", cell["provider"]
                ),
            }
            sidecar = FNAMES.approach_ring_cell_provenance(
                lat, lon, cell["column"], cell["row"], cell["provider"],
                cell["class_m"], cell.get("source_rung_token"),
            )
            with open(
                sidecar, "w", encoding="utf-8", newline="\n"
            ) as handle:
                json.dump(record, handle, indent=2, sort_keys=True)
    write_approach_ring_stamp(
        lat,
        lon,
        {
            "plan_stamp": approach_ring_plan_stamp(plan),
            "cells": outcomes,
            "feathers": plan["feathers"],
            "layers": {
                layer["ring"]: layer["class_m"]
                for layer in plan["ring_layers"]
            },
            "neighbours_unknown": plan["neighbours_unknown"],
            "checked": datetime.date.today().isoformat(),
        },
    )
    tile.rings_fetched_last_build = fetched
    if fetched:
        UI.vprint(
            1,
            "   Approach elevation rings:",
            fetched,
            "cell(s) fetched for",
            "%+03d%+04d" % (lat, lon),
        )
    return fetched


def _discard_implausible_ring_cell(cell_path, stem, outcomes):
    """Delete a constant-value ring cell and record a durable negative."""
    try:
        os.remove(cell_path)
    except OSError:
        pass
    outcomes[stem] = NO_RING_COVERAGE
    UI.vprint(
        1,
        "   INFO: approach ring cell",
        stem,
        "is one constant value everywhere (a fill served beyond the"
        " provider's true extent); recording no coverage so the base"
        " elevation source is kept there.",
    )


def _coastline_band_finer_footprint(tile, class_m):
    """Union of the 0.1 degree cell boxes where the COASTLINE BAND already
    delivers a class FINER than ``class_m``.

    Spec section 7: in coastline mode a coastal cell takes the finer of the
    band class and the ring class.  The band bakes before the rings, so a
    coarser ring must not paint over it -- its region is trimmed here, at
    the ring's single derivation site, rather than by a per-consumer veto.
    """
    from shapely.ops import unary_union

    stamp = _read_coastline_band_stamp(
        FNAMES.coastline_band_index(tile.lat, tile.lon)
    )
    boxes = []
    for stem, outcome in (stamp.get("cells") or {}).items():
        if outcome != "ok":
            continue
        parts = stem.split("_")
        if len(parts) < 4 or parts[0] != "cell":
            continue
        try:
            column, row = int(parts[1]), int(parts[2])
            resolution_m = float(parts[-1].rstrip("m"))
        except ValueError:
            continue
        if resolution_m >= class_m:
            continue
        boxes.append(
            _box_geometry(
                approach_ring_cell_box(tile.lat, tile.lon, column, row)
            )
        )
    return unary_union(boxes) if boxes else None


def bake_approach_rings_into_alt_dem(tile, dico_airports):
    """Bake the tile's approach rings into ``tile.dem.alt_dem``, coarsest
    first (spec section 3.2).

    Placed in :func:`O4_Vector_Map.compose_tile_dem_from_disk` immediately
    AFTER the tile-wide overlay bake and BEFORE the airport smoothing
    pass: rings are BASE TERRAIN -- smoothed like base terrain, with the
    airport insets still baking last, over them.

    Each class layer is a ``gdal.BuildVRT`` mosaic of its on-disk cells
    (written to the tile's tmp directory -- a DERIVED file, never the
    shared data repo), blended through
    :func:`bake_overlay_layer_into_alt_dem` with its ring region as the
    validity mask and its own feather.  A missing cell is simply a hole
    the layer underneath fills, exactly as the band behaves.

    Returns ``True`` when at least one ring layer blended.
    """
    plan = resolve_approach_ring_plan(tile, dico_airports)
    if plan is None:
        return False
    if tile.dem is None or tile.dem.alt_dem is None:
        return False
    sources = {}
    for cell in plan["cells"]:
        path = approach_ring_cell_source(cell)
        if path is not None:
            sources[cell["stem"]] = path
    baked = []
    for layer in plan["ring_layers"]:
        paths = [
            sources[stem] for stem in layer["cells"] if stem in sources
        ]
        if not paths:
            continue
        vrt_path = _approach_ring_layer_vrt(tile, layer, paths)
        if vrt_path is None:
            continue
        region = layer["region"]
        if plan.get("coastline_mode"):
            trim = _coastline_band_finer_footprint(tile, layer["class_m"])
            if trim is not None:
                from shapely import wkt as _wkt

                region = _wkt.loads(region).difference(trim)
                if region.is_empty:
                    continue
                region = region.wkt
        outcome = bake_overlay_layer_into_alt_dem(
            tile,
            vrt_path,
            feather_m=layer["feather_m"],
            region=region,
            label="approach ring %s" % layer["ring"],
        )
        if not outcome["blended"]:
            continue
        baked.append(
            {
                "ring": layer["ring"],
                "class_m": layer["class_m"],
                "feather_m": layer["feather_m"],
                "cells": len(paths),
                "provider": sorted(
                    {
                        cell["provider"]
                        for cell in plan["cells"]
                        if cell["ring"] == layer["ring"] and cell["provider"]
                    }
                ),
            }
        )
        UI.vprint(
            1,
            "   Approach ring baked:",
            layer["ring"],
            "at",
            layer["class_m"],
            "m from",
            len(paths),
            "cell(s), feather",
            layer["feather_m"],
            "m.",
        )
    if not baked:
        return False
    tile.dem.approach_ring_provenance = {
        "layers": baked,
        "plan_stamp": approach_ring_plan_stamp(plan),
        "neighbours_unknown": plan["neighbours_unknown"],
    }
    return True


def _approach_ring_layer_vrt(tile, layer, paths):
    """The per-class VRT mosaic of a ring layer's cells.

    Written to the tile's TMP directory, never the shared data repo (spec
    STOP 4): it is derived from the cells, and a build must not write the
    corpus as a side effect.
    """
    directory = os.path.join(
        FNAMES.Tmp_dir or ".", "%+03d%+04d" % (tile.lat, tile.lon)
    )
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        directory = FNAMES.Tmp_dir or "."
    vrt_path = os.path.join(
        directory,
        "approach_ring_%s_%s.vrt" % (layer["ring"], _class_key(
            layer["class_m"]).replace(".", "_")),
    )
    mosaic = gdal.BuildVRT(
        vrt_path,
        list(paths),
        options=gdal.BuildVRTOptions(
            resolution="highest",
            resampleAlg="bilinear",
            srcNodata=-32768,
            VRTNodata=-32768,
        ),
    )
    mosaic = None
    return vrt_path if os.path.isfile(vrt_path) else None
