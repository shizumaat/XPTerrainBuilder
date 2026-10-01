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
