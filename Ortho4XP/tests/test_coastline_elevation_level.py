"""``coastline_elevation_level`` -- the coastline band's own detail level.

Whole tile (``elevation_level``), airports (``airport_elevation_level``)
and the coastline band each pick their elevation detail (owner
2026-11-27).  "auto" keeps the graded approach-visibility ladder exactly
as it was; a numeric level fetches every band cell at that level through
the same surround-rung machinery, never finer than the source publishes.
Headless: the fixtures of ``test_elevation_coastline`` (synthetic
coastline, synthetic provider, a fetch faking tiny GeoTIFFs).
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
)
sys.path.insert(0, os.path.dirname(__file__))

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_Cfg_Vars  # noqa: E402
import O4_Elevation_Level as ELEVATION_LEVEL  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402
import test_elevation_coastline as COAST  # noqa: E402

needs_gdal = pytest.mark.skipif(
    not COAST.HAS_GDAL, reason="requires the GDAL bindings")

AIRPORT_BOX = (COAST.TILE_LON + 0.14, COAST.TILE_LAT + 0.14,
               COAST.TILE_LON + 0.16, COAST.TILE_LAT + 0.16)


def _run_band(monkeypatch, tmp_path, provider, level=None, airports=True):
    """One synthetic band build; returns (fetch records, stamp, cell files)."""
    root = tmp_path / ("level-%s-%s" % (level, airports))
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(root))
    provider(monkeypatch)
    COAST._install_coastline(monkeypatch, COAST.FULL_HEIGHT_COASTLINE)
    monkeypatch.setattr(
        INSETS, "_airport_bounding_boxes",
        lambda tile, dico_airports, **_margin: {"KTEST": AIRPORT_BOX})
    records = []
    monkeypatch.setattr(INSETS, "fetch_inset", COAST._writing_fetch(records))
    tile = COAST._coastline_tile()
    if level is not None:
        tile.coastline_elevation_level = level
    ELEVATION_LEVEL.ensure_coastline_band(
        tile, {"KTEST": object()} if airports else None)
    stamp_path = FNAMES.coastline_band_index(COAST.TILE_LAT, COAST.TILE_LON)
    with open(stamp_path, encoding="utf-8") as handle:
        stamp = json.load(handle)
    stamp.pop("checked")
    cells = sorted(os.listdir(os.path.dirname(stamp_path)))
    return records, stamp, cells


# --- the setting -------------------------------------------------------
def test_the_setting_mirrors_airport_elevation_level():
    coast = O4_Cfg_Vars.cfg_vars["coastline_elevation_level"]
    airport = O4_Cfg_Vars.cfg_vars["airport_elevation_level"]
    assert coast["values"] == airport["values"]
    assert coast["default"] == "auto"
    for value in coast["values"][1:]:
        assert coast["value_labels"][value] == airport["value_labels"][value]
    assert "coastline_elevation_level" in O4_Cfg_Vars.list_vector_vars
    setting = SM.get_setting("coastline_elevation_level")
    assert setting.scope == "tile" and setting.category == "elevation"
    assert "coastline_elevation_level" in SM.CURATED_TILE_SETTINGS


def test_the_setting_round_trips_through_the_tile_cfg(tmp_path, monkeypatch):
    import O4_Config_Utils as CFG

    monkeypatch.chdir(tmp_path)
    build = tmp_path / "tile_build"
    build.mkdir()
    SM.write_tile(45, 5, str(build), {"coastline_elevation_level": "1"})
    assert SM.read_tile_raw(45, 5, str(build))[
        "coastline_elevation_level"] == "1"
    tile = CFG.Tile(45, 5, str(build))
    tile.read_from_config()
    assert tile.coastline_elevation_level == "1"
    assert ELEVATION_LEVEL._coastline_band_level_m(tile) == 1.0


@pytest.mark.parametrize("value, expected", [
    ("auto", None), ("", None), (None, None), ("bogus", None),
    ("0.5", 0.5), ("1", 1.0), ("5", 5.0), ("10", 10.0), ("30", 30.0)])
def test_level_parsing(value, expected):
    tile = COAST._coastline_tile(coastline_elevation_level=value)
    assert ELEVATION_LEVEL._coastline_band_level_m(tile) == expected


def test_auto_ladder_is_the_graded_table_and_a_level_is_one_rung():
    assert ELEVATION_LEVEL._coastline_band_ladder(None) == \
        ELEVATION_LEVEL.coastline_rung_ladder()
    (rung,) = ELEVATION_LEVEL._coastline_band_ladder(5.0)
    assert rung.resolution_m == 5.0 and rung.reach_m == float("inf")


# --- the band ----------------------------------------------------------
@needs_gdal
def test_auto_is_byte_identical_to_the_setting_absent(monkeypatch, tmp_path):
    """Default "auto": the same cells, names, resolutions and stamp as a
    tile that has no coastline_elevation_level at all (every existing
    tile)."""
    absent = _run_band(monkeypatch, tmp_path, COAST._install_provider)
    auto = _run_band(monkeypatch, tmp_path, COAST._install_provider, "auto")
    assert [(r["cell"], r["resolution_m"], os.path.basename(r["path"]))
            for r in absent[0]] == \
        [(r["cell"], r["resolution_m"], os.path.basename(r["path"]))
         for r in auto[0]]
    assert absent[1] == auto[1] and absent[2] == auto[2]
    assert {r["resolution_m"] for r in auto[0]} == {
        COAST.NEAR_RESOLUTION_M, COAST.MID_RESOLUTION_M,
        COAST.FAR_RESOLUTION_M}
    assert auto[1]["factor"] == 3


@needs_gdal
@pytest.mark.parametrize("level, resolution_m, rung_label, factor", [
    # A pin at or coarser than a seamless rung: that rung, warped AT the pin.
    ("30", 30.0, COAST.SEAMLESS_RUNG_LABEL, 1),
    ("10", 10.0, COAST.SEAMLESS_RUNG_LABEL, 3),
    # 5 m: the coarsest rung under it is the 1 m one, warped at 5 m.
    ("5", 5.0, COAST.LIDAR_RUNG_LABEL, 6),
    ("1", 1.0, COAST.LIDAR_RUNG_LABEL, 9),
    # Finer than any rung publishes: raised to the finest native (1 m).
    ("0.5", 1.0, COAST.LIDAR_RUNG_LABEL, 9),
])
def test_a_level_fetches_every_cell_at_that_level(
        monkeypatch, tmp_path, level, resolution_m, rung_label, factor):
    records, stamp, _cells = _run_band(
        monkeypatch, tmp_path, COAST._install_laddered_provider, level)
    assert records
    token = FNAMES.rung_path_token(rung_label)
    for record in records:
        assert record["resolution_m"] == resolution_m
        assert token in os.path.basename(record["path"])
    assert stamp["factor"] == factor
    assert stamp["finest_resolution_m"] == resolution_m


@needs_gdal
def test_a_level_ignores_airport_distance(monkeypatch, tmp_path):
    with_airports = _run_band(
        monkeypatch, tmp_path, COAST._install_provider, "10")
    without = _run_band(
        monkeypatch, tmp_path, COAST._install_provider, "10", airports=False)
    assert [r["cell"] for r in with_airports[0]] == \
        [r["cell"] for r in without[0]]
    assert {r["resolution_m"] for r in with_airports[0]} == {10.0}


def test_a_level_finer_than_a_coarse_only_provider_takes_its_native():
    definition = {"code": "FIVE", "native_resolution_m": 5.0,
                  "ladder_label": "5 m"}
    (rung,) = ELEVATION_LEVEL._coastline_band_ladder(1.0)
    source, resolution_m = ELEVATION_LEVEL._coastline_cell_source(
        definition, rung, 1.0)
    assert source.label == "5 m" and resolution_m == 5.0
    # "auto" never takes that fallback (cells without a rung stay base).
    (near, _mid, _far) = ELEVATION_LEVEL.coastline_rung_ladder()
    assert ELEVATION_LEVEL._coastline_cell_source(
        definition, near, None)[0].label == "5 m"
    assert ELEVATION_LEVEL._coastline_cell_source(
        {"code": "NORES"}, near, None) == (None, None)
    assert ELEVATION_LEVEL._coastline_cell_source(
        {"code": "NORES"}, rung, 1.0) == (None, None)


# --- THE ONE LADDER (owner RULINGS 2026-11-27e) ------------------------
import O4_Elevation_Ladder as LADDER  # noqa: E402
import test_elevation_level_providers as PROVIDERS  # noqa: E402

#: The synthetic tile's west half (columns 0-4) -- a regional service.
WEST_HALF = (COAST.TILE_LON, COAST.TILE_LAT,
             COAST.TILE_LON + 0.5, COAST.TILE_LAT + 1.0)


def _ladder_registry(monkeypatch, tmp_path):
    """A regional 1 m service over the west half (priority 90) above a
    national 1 m one over the whole tile (80), a coarser national 10 m
    product (70), a tile-download national service (95) that may never
    serve a cell, and a global 30 m fallback opted into ring 2."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "ladder"))
    whole = (COAST.TILE_LON - 1, COAST.TILE_LAT - 1,
             COAST.TILE_LON + 2, COAST.TILE_LAT + 2)
    definitions = [
        PROVIDERS._definition("REGIONAL", resolution_m=1.0, priority=90.0,
                              coverage_bbox=WEST_HALF),
        PROVIDERS._definition("NATIONAL", resolution_m=1.0, priority=80.0,
                              coverage_bbox=whole),
        PROVIDERS._definition("COARSENAT", resolution_m=10.0, priority=70.0,
                              coverage_bbox=whole),
        PROVIDERS._definition("TILEDOWNLOAD", access_strategy="narrow",
                              resolution_m=0.5, priority=95.0,
                              coverage_bbox=whole),
        dict(PROVIDERS._definition("GLOBAL30", access_strategy="narrow",
                                   resolution_m=30.0, priority=1.0,
                                   coverage_bbox=(-180, -90, 180, 90)),
             approach_ring_class="ring2"),
    ]
    PROVIDERS._install_registry(monkeypatch, definitions)
    return {definition["code"]: definition for definition in definitions}


def test_every_consumer_reads_the_inset_list(monkeypatch, tmp_path):
    _ladder_registry(monkeypatch, tmp_path)
    assert [d["code"] for d in LADDER.ranked_providers()] == [
        d["code"] for d in INSETS.select_provider_definitions("auto")]
    tile = [d["code"] for d in LADDER.providers_for_tile(
        COAST.TILE_LAT, COAST.TILE_LON)]
    # Whole tile: windowed readers only, in the inset order.
    assert tile == ["REGIONAL", "NATIONAL", "COARSENAT"]
    assert ELEVATION_LEVEL.select_tile_overlay_definition(
        COAST.TILE_LAT, COAST.TILE_LON, 1)["code"] == "REGIONAL"
    east_cell = ELEVATION_LEVEL.approach_ring_cell_box(
        COAST.TILE_LAT, COAST.TILE_LON, 8, 3)
    # A cell: the regional service does not reach it; the tile-download
    # reader is never asked for a cell; the global fallback only at its
    # opted ring-2 class or coarser.
    assert [d["code"] for d in LADDER.providers_for_cell(east_cell, 1.0)] \
        == ["NATIONAL", "COARSENAT"]
    assert [d["code"] for d in LADDER.providers_for_cell(east_cell, 31.0)] \
        == ["NATIONAL", "COARSENAT", "GLOBAL30"]
    # The rings walk the same order (priority, not the finest source).
    (ring1, _ring2) = ELEVATION_LEVEL.approach_rung_ladder()
    assert [d["code"] for d in ELEVATION_LEVEL._approach_ring_candidates(
        COAST.TILE_LAT, COAST.TILE_LON, "auto", ring1.resolution_m,
        rung_label=ring1.label)] == ["REGIONAL", "NATIONAL", "COARSENAT"]


@needs_gdal
def test_a_regional_service_serves_its_cells_and_the_rest_fall_through(
        monkeypatch, tmp_path):
    """At "1" the regional 1 m service answers the cells it covers; a cell
    it does not reach goes to the national one, as an airport's ranking
    does; a cell it reaches but answers no coverage for falls through at
    fetch time."""
    _ladder_registry(monkeypatch, tmp_path)
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "band"))
    # Two coasts: down column 1 (west half) and down column 7 (east).
    from shapely import geometry
    COAST._install_coastline(monkeypatch, geometry.MultiLineString(
        [[(0.15, 0.0), (0.15, 1.0)], [(0.75, 0.0), (0.75, 1.0)]]))
    records = []
    writing = COAST._writing_fetch(records)

    def fetch(definition, box, resolution_m, destination):
        column, row = COAST._bbox_to_cell(box)
        if definition["code"] == "REGIONAL" and row == 0:
            records.append({"cell": (column, row), "definition": definition,
                            "resolution_m": resolution_m,
                            "path": destination, "bbox": box})
            return None                       # a clean no-coverage
        return writing(definition, box, resolution_m, destination)

    monkeypatch.setattr(INSETS, "fetch_inset", fetch)
    tile = COAST._coastline_tile(coastline_elevation_level="1")
    assert ELEVATION_LEVEL.ensure_coastline_band(tile, None)
    by_cell = {}
    for record in records:
        by_cell.setdefault(record["cell"], []).append(
            record["definition"]["code"])
    assert by_cell[(1, 5)] == ["REGIONAL"]
    assert by_cell[(1, 0)] == ["REGIONAL", "NATIONAL"]
    assert by_cell[(7, 5)] == ["NATIONAL"]
    assert all(r["resolution_m"] == 1.0 for r in records)
    assert "TILEDOWNLOAD" not in {code for codes in by_cell.values()
                                  for code in codes}
    stamp = json.load(open(FNAMES.coastline_band_index(
        COAST.TILE_LAT, COAST.TILE_LON), encoding="utf-8"))
    assert stamp["cells"][os.path.splitext(os.path.basename(
        [r for r in records if r["cell"] == (1, 0)][0]["path"]))[0]] \
        == INSETS.NO_COVERAGE
