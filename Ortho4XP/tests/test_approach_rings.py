"""Twins for the approach-graded elevation rings (#164).

Covers ``src/O4_Elevation_Level.py``'s ring mechanism against
``docs/specs/approach-graded-elevation-rings-spec.md`` (owner RULINGS
2026-10-01g/h): the shared grading ladder, the plan (cells graded by
BOUNDARY distance, the ring union of overlapping airports, the collapse
rule, ``elevation_level`` precedence, neighbour-tile airports), the
per-class coarsest-first bake with its exact region mask and its
ten-postings feather, the cold-ring frame predicate, and the harness
``rings`` refresh scope.

Synthetic throughout, as the lane protocol requires: fake 1 m / 10 m /
30 m / base rasters written into ``tmp_path``, the provider registry and
``fetch_inset`` monkeypatched, every cache path routed through
``FNAMES.Elevation_dir``.  No network (the suite's socket guard would
fail the test anyway) and no shared data corpus.  Law bounds are READ
from the law tables -- the spec forbids law literals in this lane's code
and the same rule applies to its twins.
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import numpy
import pytest
from shapely import geometry

ENGINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_DIR / "src"))

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_Elevation_Level as RINGS  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Geo_Utils as GEO  # noqa: E402

try:
    from osgeo import gdal

    HAS_GDAL = True
except Exception:  # pragma: no cover - GDAL is required for the rings
    HAS_GDAL = False

pytestmark = pytest.mark.skipif(
    not HAS_GDAL, reason="requires the GDAL python bindings"
)

TILE_LAT = 39
TILE_LON = -107
NODATA = -32768.0
CELL_DEGREES = RINGS.COASTLINE_CELL_DEGREES

RING1_CLASS_M = round(RINGS.grid_posting_metres(3), 2)
RING2_CLASS_M = round(RINGS.grid_posting_metres(1), 2)

_LAW = ENGINE_DIR / "src" / "auto_patch_v2" / "law"
#: ``emit.design.bank_slope`` -- "an embankment / cut slope a pilot reads
#: as ground, not a wall": the CEILING every ring transition must stay
#: under (spec §1 / §8 (3)).
BANK_SLOPE = tomllib.loads(
    (_LAW / "emit.toml").read_text(encoding="utf-8")
)["design"]["bank_slope"]
#: ``ruleset.taxi.transverse`` -- the p95 target of the same acceptance row.
TAXI_TRANSVERSE = tomllib.loads(
    (_LAW / "rulesets.toml").read_text(encoding="utf-8")
)["icao"]["taxi"]["transverse"]["default"]


# =====================================================================
# Fixtures / helpers
# =====================================================================
def _definition(code, native_m, **extra):
    """A synthetic wide-area provider definition at a declared resolution."""
    definition = {
        "code": code,
        "enabled": True,
        "resolution_m": native_m,
        "priority": 1.0,
        "role": INSETS.ROLE_AIRPORT_INSET,
    }
    definition.update(extra)
    return definition


def _install_registry(monkeypatch, *definitions):
    """Route ring source selection to a synthetic registry.

    Patched at :func:`O4_Elevation_Level._wide_area_candidate_definitions`
    -- the ONE candidate set the ring filter narrows (spec §2: through the
    existing registry, never a second one) -- plus the per-definition
    lookup ``ensure_approach_rings`` fetches through.
    """
    by_code = {d["code"]: d for d in definitions}
    monkeypatch.setattr(
        RINGS,
        "_wide_area_candidate_definitions",
        lambda lat, lon, providers_config="auto": list(definitions),
    )
    monkeypatch.setattr(
        INSETS, "elevation_providers_dict", by_code, raising=False
    )
    monkeypatch.setattr(
        INSETS, "_definition_resolution_m",
        lambda definition: definition.get("resolution_m"),
    )
    monkeypatch.setattr(
        INSETS, "_coverage_bbox_intersects",
        lambda definition, box: definition.get("covers", True),
    )
    return by_code


def _boundary(centre_x, centre_y, half_degrees=0.004):
    """A small aerodrome boundary polygon in the TILE-RELATIVE degree frame.

    ``airport_boundary_polygons`` is what the plan reads, and it translates
    the dico geometry by the tile origin -- so a fixture boundary is
    authored tile-relative, exactly as the pipeline stores it.
    """
    return geometry.box(
        centre_x - half_degrees,
        centre_y - half_degrees,
        centre_x + half_degrees,
        centre_y + half_degrees,
    )


def _dico(**airports):
    return {name: {"boundary": poly} for name, poly in airports.items()}


def _tile(tmp_path, monkeypatch, stub_neighbours=True, **overrides):
    """A tile stub with every cache path inside ``tmp_path``."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "Elevation"))
    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM"))
    monkeypatch.setattr(FNAMES, "Tmp_dir", str(tmp_path / "tmp"))
    tile = SimpleNamespace(
        lat=TILE_LAT,
        lon=TILE_LON,
        elevation_level="auto",
        approach_rings="auto",
        custom_dem="",
        airport_elevation_providers="auto",
        airport_elevation_insets="ICAO",
        airport_elevation_inset_feather_m=60.0,
        dem=None,
    )
    for key, value in overrides.items():
        setattr(tile, key, value)
    # Every admitted aerodrome of the fixtures HOLDS an inset: the plan's
    # admission is "an inset exists on disk", and the lane has no corpus.
    monkeypatch.setattr(
        INSETS,
        "cached_inset_paths_for_icao",
        lambda lat, lon, icao, providers_config="auto": ["<synthetic>"],
    )
    if stub_neighbours:
        # No neighbour tile takes part unless a test exercises that half.
        monkeypatch.setattr(
            RINGS,
            "_neighbour_boundary_polygons",
            lambda lat, lon, reach_m: ({}, []),
        )
    return tile


def _write_geotiff(path, box, value, pixels=8, ramp=0.01):
    """A tiny north-up EPSG:4326 float32 GeoTIFF over a degree box.

    Carries a per-pixel ramp: genuine warped lidar is never bit-for-bit
    constant, and a constant cell would (rightly) be discarded by the
    constant-value plausibility guard the ring fetch shares with the band.
    """
    west, south, east, north = box
    array = numpy.full((pixels, pixels), float(value), dtype="float32")
    array += ramp * numpy.arange(
        pixels * pixels, dtype="float32"
    ).reshape(pixels, pixels)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), pixels, pixels, 1, gdal.GDT_Float32
    )
    dataset.SetGeoTransform(
        (west, (east - west) / pixels, 0.0, north, 0.0,
         -(north - south) / pixels)
    )
    dataset.SetProjection(
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
        '298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",'
        '0.0174532925199433],AUTHORITY["EPSG","4326"]]'
    )
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(array)
    band.FlushCache()
    dataset = None
    return path


def _cell(plan, column, row):
    for entry in plan["cells"]:
        if entry["column"] == column and entry["row"] == row:
            return entry
    return None


# =====================================================================
# The shared grading ladder (ONE function, two tables -- spec §9 Q2:
# the recommended answer, taken: both tables kept, one function)
# =====================================================================
def test_ring_ladder_is_ten_km_then_twenty_km():
    reaches = [rung.reach_m for rung in RINGS.approach_rung_ladder()]
    assert reaches == [10_000.0, 20_000.0]
    classes = [rung.resolution_m for rung in RINGS.approach_rung_ladder()]
    assert classes == [RING1_CLASS_M, RING2_CLASS_M]


def test_coastline_ladder_values_unchanged():
    """The band's table keeps ITS radii (10-01h Q2 recommendation)."""
    rungs = RINGS.coastline_rung_ladder()
    assert [r.reach_m for r in rungs] == [
        RINGS.COASTLINE_NEAR_AIRPORT_KM * 1000.0,
        RINGS.COASTLINE_MID_AIRPORT_KM * 1000.0,
        float("inf"),
    ]
    assert [r.label for r in rungs] == ["near", "mid", "far"]
    assert rungs[1].resolution_m == RINGS.COASTLINE_MID_RESOLUTION_M


@pytest.mark.parametrize(
    "distance_m,expected",
    [(0.0, "ring1"), (9_999.0, "ring1"), (10_000.0, "ring1"),
     (10_001.0, "ring2"), (20_000.0, "ring2")],
)
def test_approach_class_grades_the_ring_ladder(distance_m, expected):
    rung = RINGS.approach_class(distance_m, RINGS.approach_rung_ladder())
    assert rung is not None and rung.label == expected


def test_approach_class_is_none_beyond_the_last_ring():
    """Beyond ring 2 the tile's base DEM stands -- no rung, not a clamp."""
    assert RINGS.approach_class(
        20_001.0, RINGS.approach_rung_ladder()
    ) is None


def test_approach_class_serves_the_coastline_ladder_too():
    ladder = RINGS.coastline_rung_ladder()
    assert RINGS.approach_class(1_000.0, ladder).label == "near"
    assert RINGS.approach_class(30_000.0, ladder).label == "mid"
    assert RINGS.approach_class(1e9, ladder).label == "far"


def test_feathers_are_ten_postings_of_the_coarser_side():
    """The RULE behind the two constants (spec §1): a feather is a number
    of postings of the COARSER side, never a fixed metre count."""
    feathers = RINGS.approach_ring_feathers_m()
    assert feathers == {"ring1_m": 300.0, "ring2_m": 900.0}
    # Derived, not written down: 10 postings of ring 2's class, and of the
    # 3 arc-second base class, each rounded to 100 m.
    assert feathers["ring1_m"] == RINGS.approach_ring_feather_m(RING2_CLASS_M)
    assert feathers["ring2_m"] == RINGS.approach_ring_feather_m(
        RINGS.BASE_CLASS_ARC_SECONDS * RINGS.grid_posting_metres(1)
    )
    # Both are an order of magnitude under the bank and leave the p95 well
    # under the taxiway transverse cap (spec §1 table).
    assert 9.32 / feathers["ring1_m"] < BANK_SLOPE
    assert 33.2 / feathers["ring2_m"] < BANK_SLOPE


# =====================================================================
# Gates -- ``off`` is byte-identical to the pre-rings behaviour
# =====================================================================
def test_plan_is_none_when_rings_are_off(tmp_path, monkeypatch):
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch, approach_rings="off")
    assert RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    ) is None


def test_plan_is_none_with_custom_dem(tmp_path, monkeypatch):
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch, custom_dem="mine.tif")
    assert RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    ) is None


def test_plan_is_none_without_an_inset_holding_aerodrome(
    tmp_path, monkeypatch
):
    """Rings exist ONLY around airports that hold an inset (spec §1)."""
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch)
    monkeypatch.setattr(
        INSETS,
        "cached_inset_paths_for_icao",
        lambda lat, lon, icao, providers_config="auto": [],
    )
    assert RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    ) is None


def test_plan_is_none_without_any_aerodrome(tmp_path, monkeypatch):
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch)
    assert RINGS.resolve_approach_ring_plan(tile, {}) is None


def test_unrecognised_value_degrades_to_auto(tmp_path, monkeypatch):
    tile = _tile(tmp_path, monkeypatch, approach_rings="sometimes")
    assert RINGS.approach_rings_enabled(tile) is True


# =====================================================================
# The plan: cells graded by BOUNDARY distance (spec §8 (4))
# =====================================================================
def test_cells_are_graded_by_boundary_distance_not_the_box(
    tmp_path, monkeypatch
):
    """Ring class follows metre distance from the BOUNDARY POLYGON.

    A boundary at the tile centre puts the centre cells in ring 1, an
    annulus of cells in ring 2, and the tile's far corners in NO ring --
    which a box- or ARP-driven grading could not produce (the ring-2
    reach is 20 km and the tile is ~85 km wide at this latitude).
    """
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch)
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.55, 0.55))
    )
    assert plan is not None
    rings = {(c["column"], c["row"]): c["reach_ring"] for c in plan["cells"]}
    # The cell holding the boundary is ring 1 ...
    assert rings[(5, 5)] == "ring1"
    # ... a cell ~22 km east of it is ring 2 ...
    metres_per_degree = GEO.lon_to_m(TILE_LAT + 0.5)
    far_column = int((0.55 + 20_000.0 / metres_per_degree) / CELL_DEGREES)
    assert rings[(far_column, 5)] == "ring2"
    # ... and the opposite corner is in no ring at all.
    assert (0, 0) not in rings
    assert (9, 9) not in rings


def test_the_ring_union_of_two_overlapping_airports_is_baked_once(
    tmp_path, monkeypatch
):
    """Union by construction (spec §3 reason 1).

    Two aerodromes whose ring-1 buffers overlap must not produce a cell
    twice, and must not feather one's ring-2 OUTER edge down to the base
    inside the other's ring 1 -- the 900 m dip the per-airport design
    would have cut.  One distance field, one cell per (column, row), one
    region per ring.
    """
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch)
    plan = RINGS.resolve_approach_ring_plan(
        tile,
        _dico(KASE=_boundary(0.45, 0.5), KEGE=_boundary(0.55, 0.5)),
    )
    assert plan is not None
    keys = [(c["column"], c["row"]) for c in plan["cells"]]
    assert len(keys) == len(set(keys))
    for layer in plan["ring_layers"]:
        assert len(layer["cells"]) == len(set(layer["cells"]))
    # Both boundaries sit inside ONE ring-1 region, and the cell between
    # them (closer than 10 km to both) belongs to ring 1 once.
    from shapely import wkt as _wkt

    region1 = _wkt.loads(plan["regions"]["R1"])
    assert region1.contains(geometry.Point(TILE_LON + 0.50, TILE_LAT + 0.50))
    assert _cell(plan, 5, 5)["reach_ring"] == "ring1"
    assert sorted(plan["airports"]) == ["KASE", "KEGE"]


def test_ring_one_collapses_into_ring_two_without_a_fine_provider(
    tmp_path, monkeypatch
):
    """Collapse rule (spec §2): no wide-area provider native <= 10 m over a
    ring-1 cell -> the cell is fetched at the ring-2 class instead."""
    _install_registry(monkeypatch, _definition("COARSE", 30.0))
    tile = _tile(tmp_path, monkeypatch)
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    assert plan is not None
    collapsed = _cell(plan, 5, 5)
    assert collapsed["reach_ring"] == "ring1"
    assert collapsed["ring"] == "ring2"
    assert collapsed["class_m"] == RING2_CLASS_M
    assert collapsed["provider"] == "COARSE"
    # No ring-1 layer exists at all -- there is nothing to bake at 10 m.
    assert [layer["ring"] for layer in plan["ring_layers"]] == ["ring2"]


def test_no_coverage_cell_keeps_the_base_dem(tmp_path, monkeypatch):
    """No provider at all -> the cell carries no provider and the plan
    records it; the base DEM stands there (spec §2 collapse rule)."""
    _install_registry(monkeypatch, _definition("TOOCOARSE", 90.0))
    tile = _tile(tmp_path, monkeypatch)
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    assert plan is not None
    assert all(c["provider"] is None for c in plan["cells"])
    assert all(c["state"] == "no-provider" for c in plan["cells"])
    assert plan["ring_layers"] == []


def test_a_cell_only_the_coarse_provider_covers_collapses(
    tmp_path, monkeypatch
):
    """Per-CELL coverage, not per-tile: the fine provider's coverage box
    decides which cells can carry ring 1."""
    fine = _definition("FINE", 1.0)
    coarse = _definition("COARSE", 30.0)
    _install_registry(monkeypatch, fine, coarse)
    # The fine provider covers only the western half of the tile.
    monkeypatch.setattr(
        INSETS,
        "_coverage_bbox_intersects",
        lambda definition, box: (
            True if definition["code"] == "COARSE"
            else box[0] < TILE_LON + 0.5
        ),
    )
    tile = _tile(tmp_path, monkeypatch)
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    assert plan is not None
    assert _cell(plan, 4, 5)["provider"] == "FINE"
    assert _cell(plan, 4, 5)["class_m"] == RING1_CLASS_M
    assert _cell(plan, 5, 5)["provider"] == "COARSE"
    assert _cell(plan, 5, 5)["class_m"] == RING2_CLASS_M


# =====================================================================
# ``elevation_level`` precedence -- the finest class wins per cell
# (spec §7); a ring never coarsens a level
# =====================================================================
def test_level_thirty_supersedes_ring_two_only(tmp_path, monkeypatch):
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch, elevation_level="30")
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    assert plan is not None
    assert [layer["ring"] for layer in plan["ring_layers"]] == ["ring1"]
    ring2_cells = [c for c in plan["cells"] if c["reach_ring"] == "ring2"]
    assert ring2_cells
    assert all(
        c["state"] == RINGS.APPROACH_RING_SUPERSEDED for c in ring2_cells
    )


def test_level_ten_supersedes_both_rings(tmp_path, monkeypatch):
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch, elevation_level="10")
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    assert plan is not None
    assert plan["ring_layers"] == []
    assert all(
        c["state"] == RINGS.APPROACH_RING_SUPERSEDED for c in plan["cells"]
    )


def test_ring_layers_are_ordered_coarsest_first(tmp_path, monkeypatch):
    """The bake order the precedence rests on (spec §3.2)."""
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch)
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    classes = [layer["class_m"] for layer in plan["ring_layers"]]
    assert classes == sorted(classes, reverse=True)
    assert classes == [RING2_CLASS_M, RING1_CLASS_M]
    feathers = {
        layer["ring"]: layer["feather_m"] for layer in plan["ring_layers"]
    }
    assert feathers == {"ring1": 300.0, "ring2": 900.0}


# =====================================================================
# Neighbour-tile aerodromes (spec §5 / §8 (4)): included when the layer
# is cached, RECORDED as unknown when it is not -- never a refusal
# =====================================================================
def _install_neighbour(monkeypatch, tmp_path, boundaries, cached_stems):
    """Make the real ``_neighbour_boundary_polygons`` read a cached layer."""
    import O4_Config_Utils as CFG
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP

    for stem_lat, stem_lon in cached_stems:
        path = FNAMES.osm_cached(stem_lat, stem_lon, "airports")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("synthetic cached airports layer\n")
    monkeypatch.setattr(
        CFG, "Tile",
        lambda lat, lon, _dir: SimpleNamespace(
            lat=lat, lon=lon, airport_elevation_insets="ICAO",
            read_from_config=lambda: None,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        OSM, "OSM_layer",
        lambda *a, **k: SimpleNamespace(
            update_dicosm=lambda *args, **kwargs: True
        ),
    )
    monkeypatch.setattr(
        VMAP, "build_airports_dico",
        lambda tile, layer: _dico(
            **{name: poly for name, poly in boundaries.items()}
        ),
    )


def test_neighbour_aerodrome_is_included_when_its_layer_is_cached(
    tmp_path, monkeypatch
):
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch, stub_neighbours=False)
    # KPUB sits just NORTH of the tile edge, 0.02 deg (~2.2 km) up -- well
    # inside the 20 km neighbour reach, so its rings cross the seam.
    _install_neighbour(
        monkeypatch, tmp_path, {"KPUB": _boundary(0.5, 0.02)},
        cached_stems=[(TILE_LAT + 1, TILE_LON)],
    )
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    assert plan is not None
    assert "KPUB@+40-107" in plan["airports"]
    # The other seven neighbours have no cached layer: RECORDED, not refused.
    assert "+38-107" in plan["neighbours_unknown"]
    assert "+40-107" not in plan["neighbours_unknown"]
    # The neighbour's rings reach into the top rows of THIS tile.
    assert _cell(plan, 5, 9) is not None


def test_every_neighbour_without_a_cached_layer_is_recorded_unknown(
    tmp_path, monkeypatch
):
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch, stub_neighbours=False)
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    assert len(plan["neighbours_unknown"]) == 8


# =====================================================================
# THE SYNTHETIC 3-RING FIXTURE (spec §8 (1)(3), §10 step 2)
#
# A 300 x 300 working grid at the ring-1 posting, placed ON the ring-1
# edge 10 km from a synthetic boundary, with a fake base / 30 m / 10 m
# ladder: the ring-1 layer stands 9.32 m above the ring-2 layer (fact 2's
# measured max 10 m-vs-30 m step at KASE), so the transition grade across
# the 300 m feather is the number the spec's §1 table predicts.
# =====================================================================
#: The measured worst 10 m-vs-30 m step at KASE (spec §0 fact 2): the
#: height the ring-1 → ring-2 feather has to absorb.
RING1_STEP_M = 9.32
#: The measured worst 10 m-vs-90 m step over the same box (fact 2): what
#: the ring-2 → base feather absorbs.
RING2_STEP_M = 33.2
#: The measured p95 steps of the same two comparisons (spec §0 fact 2):
#: the figures the §1 table's p95 grades are derived from.
RING1_P95_STEP_M = 1.68
RING2_P95_STEP_M = 7.46
#: Half-width of the probe grid (its 300 cells at the ring-1 posting).
PROBE_CELLS = 600
#: Cells trimmed off every side of a probe before measuring.  The bake's
#: validity blur is zero-padded, so a SUB-WINDOW of the tile grid (which
#: a probe is, and the production grid is not) sees its layer ramp down at
#: the window's own border.  That border is not a ring transition, and the
#: trim has to exceed the widest feather in cells
#: (900 m / 10.31 m = 88 at the ring-2 posting).
PROBE_TRIM_CELLS = 95


def _interior(array):
    """``array`` without its probe-window border (see PROBE_TRIM_CELLS)."""
    trim = PROBE_TRIM_CELLS
    return array[trim:-trim, trim:-trim]


def _probe_dem(centre_x, centre_y, base_value=0.0):
    """A ``PROBE_CELLS`` square working grid at the ring-1 posting.

    Tile-relative degrees, as ``tile.dem`` carries them; the probe sits far
    from every tile edge so the bake's tile-edge ramp is weight 1 over it
    and the only weight in play is the region feather under test.
    """
    metres_per_degree_longitude = GEO.lon_to_m(TILE_LAT + centre_y)
    x_step = RING1_CLASS_M / metres_per_degree_longitude
    y_step = RING1_CLASS_M / GEO.lat_to_m
    half_x = 0.5 * (PROBE_CELLS - 1) * x_step
    half_y = 0.5 * (PROBE_CELLS - 1) * y_step
    return SimpleNamespace(
        nxdem=PROBE_CELLS,
        nydem=PROBE_CELLS,
        x0=centre_x - half_x,
        x1=centre_x + half_x,
        y0=centre_y - half_y,
        y1=centre_y + half_y,
        nodata=NODATA,
        alt_dem=numpy.full(
            (PROBE_CELLS, PROBE_CELLS), float(base_value), dtype=numpy.float32
        ),
    )


def _write_plan_cells(plan, values, pixels=24):
    """Write a flat GeoTIFF for every planned cell, valued by ring."""
    for cell in plan["cells"]:
        if not cell.get("provider"):
            continue
        _write_geotiff(
            cell["path"],
            RINGS.approach_ring_cell_box(
                TILE_LAT, TILE_LON, cell["column"], cell["row"]
            ),
            values[cell["ring"]],
            pixels=pixels,
            ramp=0.0,
        )


def _grade_fraction(array, posting_m):
    """Per-cell surface grade (rise/run) of a baked working grid."""
    d_rows, d_columns = numpy.gradient(array.astype(numpy.float64))
    return numpy.hypot(d_rows, d_columns) / posting_m


def _ring_one_edge_x(boundary_centre_y):
    """Tile-relative longitude of the ring-1 region's eastern edge."""
    return 0.5 + RINGS.APPROACH_RING_1_REACH_M / GEO.lon_to_m(
        TILE_LAT + boundary_centre_y
    )


def _three_ring_plan(tmp_path, monkeypatch, **tile_overrides):
    """The fixture: one aerodrome, both rings, every planned cell written."""
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch, **tile_overrides)
    dico = _dico(KASE=_boundary(0.5, 0.5))
    plan = RINGS.resolve_approach_ring_plan(tile, dico)
    assert plan is not None
    _write_plan_cells(
        plan, {"ring1": RING1_STEP_M, "ring2": 0.0}
    )
    return tile, dico, plan


def test_every_fixture_cell_is_valid_and_answered(tmp_path, monkeypatch):
    """The fixture itself: no nodata, no unanswered cell -- otherwise the
    grade numbers below would be measuring a hole, not a transition."""
    tile, _dico_airports, plan = _three_ring_plan(tmp_path, monkeypatch)
    planned = [c for c in plan["cells"] if c.get("provider")]
    assert planned
    for cell in planned:
        path = RINGS.approach_ring_cell_source(cell)
        assert path is not None, cell["stem"]
        dataset = gdal.Open(path)
        array = dataset.GetRasterBand(1).ReadAsArray()
        dataset = None
        assert numpy.all(array != NODATA)
    assert RINGS.approach_ring_frame_problem(TILE_LAT, TILE_LON, plan) is None


def _feather_grade(tmp_path, monkeypatch, step_m, feather_m):
    """Bake ONE layer standing ``step_m`` above the surface underneath, with
    a disc region and a ``feather_m`` hand-back, and return
    ``(worst, p95, inside_value, outside_value)`` of the baked grade field.

    The spec section 10 step 2 twin, exactly: the feather's job is to absorb a
    known step over a known width, and that is measured here against the
    LAYER function itself -- the one implementation every ring class, the
    coastline band and the numeric level bake through.
    """
    monkeypatch.setattr(FNAMES, "Tmp_dir", str(tmp_path / "tmp"))
    centre_x = centre_y = 0.5
    tile = SimpleNamespace(
        lat=TILE_LAT, lon=TILE_LON,
        dem=_probe_dem(centre_x, centre_y, base_value=0.0),
    )
    # The layer covers the whole probe window and stands step_m above it.
    span_x = tile.dem.x1 - tile.dem.x0
    span_y = tile.dem.y1 - tile.dem.y0
    layer_path = str(tmp_path / "layer.tif")
    _write_geotiff(
        layer_path,
        (
            TILE_LON + tile.dem.x0 - span_x,
            TILE_LAT + tile.dem.y0 - span_y,
            TILE_LON + tile.dem.x1 + span_x,
            TILE_LAT + tile.dem.y1 + span_y,
        ),
        step_m,
        pixels=32,
        ramp=0.0,
    )
    # A DISC whose edge runs north-south through the probe centre: its
    # radius is 10 km, so over the 3 km window the edge is near-straight
    # and the measured grade is the feather's, not the curvature's.
    metres_per_degree_longitude = GEO.lon_to_m(TILE_LAT + centre_y)
    radius_deg = RINGS.APPROACH_RING_1_REACH_M / metres_per_degree_longitude
    region = geometry.Point(
        TILE_LON + centre_x - radius_deg, TILE_LAT + centre_y
    ).buffer(radius_deg, quad_segs=256)
    outcome = RINGS.bake_overlay_layer_into_alt_dem(
        tile, layer_path, feather_m=feather_m, region=region, label="probe"
    )
    assert outcome["blended"] is True
    posting_m = span_y / (PROBE_CELLS - 1) * GEO.lat_to_m
    baked = tile.dem.alt_dem
    grade = _interior(_grade_fraction(baked, posting_m))
    # Columns 1.5-2.1 km INSIDE the region edge (beyond even the 900 m
    # feather plus the 10 km disc's ~0.5 km bow across the window)
    # and the matching band outside it.
    inside = _interior(baked)[:, :50]
    outside = _interior(baked)[:, -50:]
    return (
        float(grade.max()),
        float(numpy.percentile(grade, 95)),
        inside,
        outside,
    )


def test_ring_one_feather_absorbs_the_ten_to_thirty_metre_step(
    tmp_path, monkeypatch
):
    """Spec section 1 table / section 8 (3): the ring 1 -> ring 2 seam.

    KASE's measured worst 10 m-vs-30 m step (9.32 m, section 0 fact 2) over the
    300 m feather is 3.1 % worst and well under the taxiway transverse cap
    at p95 -- an order of magnitude under ``emit.design.bank_slope``.
    """
    feather_m = RINGS.approach_ring_feathers_m()["ring1_m"]
    worst, p95, inside, outside = _feather_grade(
        tmp_path, monkeypatch, RING1_STEP_M, feather_m
    )
    predicted = RING1_STEP_M / feather_m
    assert abs(worst - predicted) < 0.005, (worst, predicted)
    assert worst < BANK_SLOPE / 5.0
    # The ramp is linear, so the p95 of the grade over a window centred ON
    # the seam is the seam's own slope -- which is what makes the section 1
    # table's p95 ROW a statement about the terrain's p95 STEP, measured
    # next.
    assert abs(p95 - worst) < 0.005, (p95, worst)
    p95_worst, _p, _i, _o = _feather_grade(
        tmp_path, monkeypatch, RING1_P95_STEP_M, feather_m
    )
    assert p95_worst < TAXI_TRANSVERSE, p95_worst
    # Spec section 10 step 2: beyond the feather the baked value IS the layer's.
    assert numpy.allclose(inside, RING1_STEP_M, atol=1e-4)
    # Outside the region the surface underneath is untouched.
    assert numpy.allclose(outside, 0.0, atol=1e-6)


def test_ring_two_feather_absorbs_the_ten_to_ninety_metre_step(
    tmp_path, monkeypatch
):
    """The outer seam: the bounded worst 10 m-vs-90 m step (33.2 m) over the
    900 m feather -- the spec's 3.7 % worst / 0.83 % p95."""
    feather_m = RINGS.approach_ring_feathers_m()["ring2_m"]
    worst, p95, inside, outside = _feather_grade(
        tmp_path, monkeypatch, RING2_STEP_M, feather_m
    )
    predicted = RING2_STEP_M / feather_m
    assert abs(worst - predicted) < 0.005, (worst, predicted)
    assert worst < BANK_SLOPE / 5.0
    assert abs(p95 - worst) < 0.005, (p95, worst)
    p95_worst, _p, _i, _o = _feather_grade(
        tmp_path, monkeypatch, RING2_P95_STEP_M, feather_m
    )
    assert p95_worst < TAXI_TRANSVERSE, p95_worst
    assert numpy.allclose(inside, RING2_STEP_M, atol=1e-4)
    assert numpy.allclose(outside, 0.0, atol=1e-6)


def test_the_old_sixty_metre_feather_is_what_reads_as_a_built_edge(
    tmp_path, monkeypatch
):
    """The defect, measured: the SAME step over the inset box's 60 m
    feather is the bank itself (spec section 0 fact 1 -- 33.1 % at KASE, which
    is why a 60 m band of it drawn around the airport reads as a built
    edge).  This is the number the ring feathers replace; it is here so
    the twin fails if the feather law is ever quietly reverted."""
    old_feather_m = 60.0
    worst, _p95, _inside, _outside = _feather_grade(
        tmp_path, monkeypatch, RING2_STEP_M, old_feather_m
    )
    assert worst > BANK_SLOPE
    # And the ring-2 feather is an order of magnitude better on the same step.
    ring_worst, _p, _i, _o = _feather_grade(
        tmp_path, monkeypatch, RING2_STEP_M,
        RINGS.approach_ring_feathers_m()["ring2_m"],
    )
    assert ring_worst < worst / 10.0


#: A whole-tile probe grid: 300 cells across 1 degree is a ~370 m posting,
#: so both ring feathers are at most one cell wide and the per-cell
#: precedence shows CRISPLY -- the question this probe asks is which layer
#: won where, not how wide its ramp is (that is _feather_grade's).
TILE_PROBE_CELLS = 300


def _tile_probe_dem(base_value=0.0):
    return SimpleNamespace(
        nxdem=TILE_PROBE_CELLS, nydem=TILE_PROBE_CELLS,
        x0=0.0, x1=1.0, y0=0.0, y1=1.0, nodata=NODATA,
        alt_dem=numpy.full(
            (TILE_PROBE_CELLS, TILE_PROBE_CELLS), float(base_value),
            dtype=numpy.float32,
        ),
    )


def _probe_at(dem, x_offset, y_offset):
    """The baked value of the whole-tile probe at a tile-relative point."""
    column = int(round(x_offset * (TILE_PROBE_CELLS - 1)))
    row = int(round((1.0 - y_offset) * (TILE_PROBE_CELLS - 1)))
    return float(dem.alt_dem[row, column])


def test_coarsest_first_order_and_per_cell_precedence(
    tmp_path, monkeypatch
):
    """The precedence the bake order rests on (spec section 3.2 / section 7).

    Cells are valued by the ring REACH they serve, so the baked surface
    names which layer won where: inside R1 the FINE layer stands, out in
    the R2 annulus (beyond every ring-1 cell) the COARSE one does, and
    beyond R2 the base DEM is untouched.  Baking fine-first would instead
    leave the coarse layer's 900 m feather painted across the fine region.
    """
    centre_y = 0.5
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch)
    dico = _dico(KASE=_boundary(0.5, centre_y))
    plan = RINGS.resolve_approach_ring_plan(tile, dico)
    assert [layer["ring"] for layer in plan["ring_layers"]] == [
        "ring2", "ring1"
    ]
    for cell in plan["cells"]:
        if not cell.get("provider"):
            continue
        _write_geotiff(
            cell["path"],
            RINGS.approach_ring_cell_box(
                TILE_LAT, TILE_LON, cell["column"], cell["row"]
            ),
            500.0 if cell["reach_index"] == 1 else 100.0,
            pixels=24,
            ramp=0.0,
        )
    tile.dem = _tile_probe_dem(base_value=0.0)
    assert RINGS.bake_approach_rings_into_alt_dem(tile, dico) is True

    # On the aerodrome, deep inside R1: the FINE layer.
    assert _probe_at(tile.dem, 0.5, centre_y) == pytest.approx(500.0, abs=1e-2)
    # Out in the R2 annulus, in a cell no ring-1 reach touches (R1's edge
    # is ~0.617, R2's ~0.733, so 0.71 is 8 km outside R1 and 2 km inside
    # R2): the COARSE layer.
    assert _probe_at(tile.dem, 0.71, centre_y) == pytest.approx(
        100.0, abs=1e-2
    )
    # Beyond R2 the base DEM stands, untouched.
    assert _probe_at(tile.dem, 0.85, centre_y) == pytest.approx(0.0, abs=1e-6)
    provenance = tile.dem.approach_ring_provenance
    assert [layer["ring"] for layer in provenance["layers"]] == [
        "ring2", "ring1"
    ]
    assert provenance["plan_stamp"] == RINGS.approach_ring_plan_stamp(plan)


def test_rings_off_leaves_the_grid_untouched(tmp_path, monkeypatch):
    """The gate is byte-identical (spec §7): nothing is baked at all."""
    centre_y = 0.5
    tile, dico, plan = _three_ring_plan(tmp_path, monkeypatch)
    tile.approach_rings = "off"
    tile.dem = _probe_dem(_ring_one_edge_x(centre_y), centre_y, base_value=7.0)
    before = tile.dem.alt_dem.copy()
    assert RINGS.bake_approach_rings_into_alt_dem(tile, dico) is False
    assert numpy.array_equal(tile.dem.alt_dem, before)


def test_a_missing_cell_is_a_hole_the_surface_underneath_keeps(
    tmp_path, monkeypatch
):
    """``--allow-degraded-dem`` semantics at the engine level (spec §5):
    the bake uses the cells ON DISK, and a missing one is simply a hole
    the surface underneath keeps.  It never refuses, never raises, and
    never invents a value -- which is what makes proceeding without rings
    a lawful (recorded) degradation rather than a different surface."""
    centre_y = 0.5
    tile, dico, plan = _three_ring_plan(tmp_path, monkeypatch)
    removed = 0
    for cell in plan["cells"]:
        if cell.get("provider") and cell["ring"] == "ring1":
            os.remove(cell["path"])
            removed += 1
    assert removed
    tile.dem = _probe_dem(_ring_one_edge_x(centre_y), centre_y, base_value=3.0)
    before = tile.dem.alt_dem.copy()
    # No ring-1 cell on disk, and no ring-2 cell covers this window (its
    # cells are the ring-1 ones): nothing to bake, nothing changed.
    assert RINGS.bake_approach_rings_into_alt_dem(tile, dico) is False
    assert numpy.array_equal(tile.dem.alt_dem, before)
    # And the frame predicate SEES it, so the harness can refuse: the
    # degradation is recorded, never silent.
    problem = RINGS.approach_ring_frame_problem(TILE_LAT, TILE_LON, plan)
    assert problem is not None and problem[0] == "cold"
    assert "--refresh-data rings" in problem[1]


def test_no_vrt_or_stamp_is_written_outside_the_tmp_dir(
    tmp_path, monkeypatch
):
    """Spec STOP 4: a VRT is a DERIVED file and lives in the tile's tmp
    directory; the bake writes nothing into the elevation cache."""
    centre_y = 0.5
    tile, dico, plan = _three_ring_plan(tmp_path, monkeypatch)
    tile.dem = _probe_dem(_ring_one_edge_x(centre_y), centre_y)
    before = {
        str(p) for p in (tmp_path / "Elevation").rglob("*") if p.is_file()
    }
    assert RINGS.bake_approach_rings_into_alt_dem(tile, dico) is True
    after = {
        str(p) for p in (tmp_path / "Elevation").rglob("*") if p.is_file()
    }
    assert after == before
    assert list((tmp_path / "tmp").rglob("*.vrt"))


# =====================================================================
# THE HARNESS (spec §6 rows 14-16, §5): the ``rings`` refresh scope, the
# frame key and the corpus-stamp part
# =====================================================================
def _guard():
    sys.path.insert(0, str(ENGINE_DIR / "tools" / "harness"))
    import shared_repo_guard

    return shared_repo_guard


def test_scope_of_names_a_ring_cell_rings_not_dem():
    """Spec §6 row 16: authorising a DEM refresh must NOT authorise a ring
    warm.  The ring cells live INSIDE ``dem``'s prefix, so the mapping is
    by DIRECTORY SUFFIX (the ``shore``-inside-``osm_layers`` precedent)."""
    guard = _guard()
    assert guard.scope_of(
        "Elevation_data/+30-110/N39W107_approach_rings/"
        "cell_04_05_usgs3dep_10.31m.tif"
    ) == "rings"
    assert guard.scope_of(
        "Elevation_data/+30-110/N39W107_approach_rings/index.json"
    ) == "rings"
    # And nothing else under Elevation_data moved scope.
    assert guard.scope_of(
        "Elevation_data/+30-110/N39W107_airport_insets/KASE_usgs3dep.tif"
    ) == "dem"
    assert guard.scope_of("Elevation_data/+30-110/N39W107.hgt") == "dem"
    assert guard.scope_of("Elevation_data/_las_tiles/x.laz") == "las_tiles"


def test_rings_is_an_authorisable_scope_with_a_description():
    guard = _guard()
    assert "rings" in {s for s, _p, _w in guard.REFRESH_SCOPES}
    assert "approach" in guard.scope_description("rings")


def test_the_scope_suffix_is_read_from_the_engine():
    """A rename of ``FNAMES.APPROACH_RING_DIR_SUFFIX`` must not silently
    unmap the scope and let a ring warm pass as a ``dem`` write."""
    guard = _guard()
    assert (
        guard.APPROACH_RING_DIR_SUFFIX == FNAMES.APPROACH_RING_DIR_SUFFIX
    )


def test_approach_rings_is_a_dem_frame_key_and_cache_state_is_frozen():
    """Spec §7 (the gate shapes the surface) and STOP 3 (``dem_cache_state``
    keys are FROZEN -- adding one re-keys every stored arm)."""
    sys.path.insert(0, str(ENGINE_DIR / "tools" / "harness"))
    import build_airport

    assert "approach_rings" in build_airport.DEM_FRAME_KEYS
    state = build_airport.dem_cache_state(ENGINE_DIR, TILE_LAT, TILE_LON)
    assert set(state) == {
        "tile", "tile_stem", "base_raster", "base_raster_files",
        "airport_insets", "airport_inset_dirs", "tile_overlay",
        "airports_layer", "airports_layer_files",
    }


def test_the_cold_refusal_names_the_rings_scope(tmp_path, monkeypatch):
    """Spec §5: a planned cell with no raster and no negative REFUSES, in
    its own scope, and ``--allow-degraded-dem`` accepts it knowingly."""
    sys.path.insert(0, str(ENGINE_DIR / "tools" / "harness"))
    import build_airport

    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch)
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    problem = RINGS.approach_ring_frame_problem(TILE_LAT, TILE_LON, plan)
    assert problem is not None and problem[0] == "cold"
    assert "--refresh-data rings" in problem[1]

    warm_state = {
        "tile": [TILE_LAT, TILE_LON], "tile_stem": "+39-107",
        "base_raster": True, "base_raster_files": [],
        "airport_insets": True, "airport_inset_dirs": [],
        "tile_overlay": False, "airports_layer": True,
        "airports_layer_files": [],
    }
    with pytest.raises(SystemExit) as refusal:
        build_airport.require_dem_frame(warm_state, ring_problem=problem)
    assert "--refresh-data rings" in str(refusal.value)
    # The flag accepts it KNOWINGLY (and authorises no write).
    build_airport.require_dem_frame(
        warm_state, allow_degraded=True, ring_problem=problem
    )
    # An AUTHORISED ring refresh in the same run is not a refusal: the run
    # derives it and the frame is re-judged afterwards.
    build_airport.require_dem_frame(
        warm_state, requested={"rings"}, ring_problem=problem
    )


def test_a_recorded_negative_answers_a_planned_cell(tmp_path, monkeypatch):
    """A per-cell no-coverage negative is a durable ANSWER, not a hole:
    the frame is warm and no refusal follows (spec §2/§5)."""
    _install_registry(monkeypatch, _definition("FINE", 1.0))
    tile = _tile(tmp_path, monkeypatch)
    plan = RINGS.resolve_approach_ring_plan(
        tile, _dico(KASE=_boundary(0.5, 0.5))
    )
    RINGS.write_approach_ring_stamp(
        TILE_LAT, TILE_LON,
        {"cells": {
            cell["stem"]: RINGS.NO_RING_COVERAGE
            for cell in plan["cells"] if cell.get("provider")
        }},
    )
    assert RINGS.approach_ring_frame_problem(
        TILE_LAT, TILE_LON, plan
    ) is None


def test_the_corpus_stamp_moves_when_the_ring_cache_changes(tmp_path):
    """Spec §5: the ring state rides the ledger's ``corpus_stamp`` as its
    own ``parts`` component -- so a pre-rings control is never served to a
    post-rings build (the silent cross-corpus comparison the stamp exists
    to prevent)."""
    sys.path.insert(0, str(ENGINE_DIR / "tools" / "harness"))
    import artifact_ledger

    root = tmp_path / "repo"
    ring_dir = root / "Elevation_data" / "+30-110" / "N39W107_approach_rings"
    ring_dir.mkdir(parents=True)
    frame = {
        "data_repo": str(root),
        "mounts": {},
        "dem_frame_effective": {"approach_rings": "auto"},
        "dem_cache_before": {
            "tile_stem": "N39W107",
            "base_raster_files": [],
            "airports_layer_files": [],
            "airport_inset_dirs": [],
        },
    }
    empty = artifact_ledger.corpus_stamp(frame, root=root)
    with open(ring_dir / "index.json", "w", encoding="utf-8",
              newline="\n") as handle:
        handle.write('{"cells": {}}\n')
    warmed = artifact_ledger.corpus_stamp(frame, root=root)
    assert warmed["sha256"] != empty["sha256"]
    # It rides its OWN parts component, named, so a reader can see it.
    assert "rings_dir" in warmed["parts"]
    assert warmed["parts"]["rings_dir"][0]["path"].endswith(
        FNAMES.APPROACH_RING_DIR_SUFFIX
    )
    assert warmed["parts"]["rings_dir"][0]["entries"] == 1
    # ``dem_cache`` -- the FROZEN key set -- is untouched by the ring state.
    assert warmed["parts"]["dem_cache"] == empty["parts"]["dem_cache"]


def test_rings_fetched_is_a_build_time_download_qualifier():
    """Spec §5: a run that fetched ring cells is no build-time baseline --
    exactly as ``insets_fetched`` is not."""
    sys.path.insert(0, str(ENGINE_DIR / "tools"))
    import check_build_time

    source = (ENGINE_DIR / "tools" / "check_build_time.py").read_text(
        encoding="utf-8"
    )
    assert 'features.get("rings_fetched")' in source
    assert hasattr(check_build_time, "newest_tile_measurement")
