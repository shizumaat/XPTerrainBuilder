"""THE LADDER'S FALL-THROUGH for every consumer (owner RULINGS 2026-11-27e,
follow-up lane lladder2).

The approach rings walk each cell's sources at fetch time -- a provider
answering no coverage, a fill or a raised failure hands the cell to the
next ladder provider, as the coastline band and the airport insets do --
and the tile-wide numeric overlay is fetched PER CELL on a border tile
(and after a whole-tile no coverage), through the band's own walk.
Headless: synthetic registries, a fetch faking tiny GeoTIFFs.
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
import O4_Elevation_Level as ELEVATION_LEVEL  # noqa: E402
import O4_Elevation_Overlay_Cells as OVERLAY_CELLS  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import test_approach_rings as RING_FIXTURES  # noqa: E402
import test_coastline_elevation_level as LADDER_FIXTURES  # noqa: E402
import test_elevation_coastline as COAST  # noqa: E402

needs_gdal = pytest.mark.skipif(
    not COAST.HAS_GDAL, reason="requires the GDAL bindings")


# --- approach rings ----------------------------------------------------
def _ring_tile(tmp_path, monkeypatch, first_answer):
    """Two 1 m ring sources, FIRST above SECOND; FIRST answers every cell
    with ``first_answer`` ("none", "raise", "constant" or "data")."""
    first = RING_FIXTURES._definition("FIRST", 1.0)
    second = RING_FIXTURES._definition("SECOND", 1.0)
    RING_FIXTURES._install_registry(monkeypatch, first, second)
    tile = RING_FIXTURES._tile(tmp_path, monkeypatch)
    calls = []

    def fetch(definition, box, class_m, path):
        calls.append(definition["code"])
        if definition["code"] == "FIRST" and first_answer[0] != "data":
            if first_answer[0] == "none":
                return None
            if first_answer[0] == "raise":
                raise RuntimeError("transient outage")
            RING_FIXTURES._write_geotiff(path, box, 0.0, ramp=0.0)
            return {"provider": "FIRST"}
        RING_FIXTURES._write_geotiff(path, box, 1500.0)
        return {"provider": definition["code"]}

    monkeypatch.setattr(INSETS, "fetch_inset", fetch)
    dico = RING_FIXTURES._dico(KASE=RING_FIXTURES._boundary(0.5, 0.5))
    return tile, dico, calls


def _stamp_cells():
    return RING_FIXTURES.RINGS.read_approach_ring_stamp(
        RING_FIXTURES.TILE_LAT, RING_FIXTURES.TILE_LON)["cells"]


@needs_gdal
@pytest.mark.parametrize("answer, recorded", [
    ("none", ELEVATION_LEVEL.NO_RING_COVERAGE),
    ("constant", ELEVATION_LEVEL.NO_RING_COVERAGE),
    ("raise", ELEVATION_LEVEL.RING_FELL_THROUGH),
])
def test_a_ring_cell_falls_through_to_the_next_provider(
        tmp_path, monkeypatch, answer, recorded):
    tile, dico, calls = _ring_tile(tmp_path, monkeypatch, [answer])
    before = ELEVATION_LEVEL.resolve_approach_ring_plan(tile, dico)
    planned = [cell for cell in before["cells"] if cell["provider"]]
    assert planned and {c["provider"] for c in planned} == {"FIRST"}
    assert all([s["provider"] for s in c["sources"]][:2]
               == ["FIRST", "SECOND"] for c in planned)

    fetched = ELEVATION_LEVEL.ensure_approach_rings(tile, dico)
    assert fetched == len(planned)
    cells = _stamp_cells()
    after = ELEVATION_LEVEL.resolve_approach_ring_plan(tile, dico)
    for old, new in zip(planned, [c for c in after["cells"]
                                  if c["provider"]], strict=True):
        assert new["provider"] == "SECOND"
        assert cells[old["stem"]] == recorded
        assert cells[new["stem"]] == "ok"
        assert not os.path.isfile(old["path"])
        assert os.path.isfile(new["path"])
    # The stamp's plan digest names what was fetched.
    assert json.load(open(FNAMES.approach_ring_index(
        RING_FIXTURES.TILE_LAT, RING_FIXTURES.TILE_LON), encoding="utf-8"))["plan_stamp"] \
        == ELEVATION_LEVEL.approach_ring_plan_stamp(after)
    assert ELEVATION_LEVEL.approach_ring_frame_problem(
        RING_FIXTURES.TILE_LAT, RING_FIXTURES.TILE_LON, after) is None

    # A second build asks nobody: the cells stand on SECOND.
    del calls[:]
    assert ELEVATION_LEVEL.ensure_approach_rings(tile, dico) == 0
    assert calls == []


@needs_gdal
def test_a_refresh_asks_the_first_provider_again(tmp_path, monkeypatch):
    answer = ["raise"]
    tile, dico, calls = _ring_tile(tmp_path, monkeypatch, answer)
    ELEVATION_LEVEL.ensure_approach_rings(tile, dico)
    answer[0] = "data"
    ELEVATION_LEVEL.ensure_approach_rings(tile, dico, refresh=True)
    plan = ELEVATION_LEVEL.resolve_approach_ring_plan(tile, dico)
    assert {c["provider"] for c in plan["cells"] if c["provider"]} \
        == {"FIRST"}


@needs_gdal
def test_a_ring_cell_every_source_fails_stays_unanswered(
        tmp_path, monkeypatch):
    """Raised everywhere: no outcome is recorded (a transient outage), so
    the cell stays on its first source and reads cold."""
    tile, dico, _calls = _ring_tile(tmp_path, monkeypatch, ["raise"])

    def raising(*_args):
        raise RuntimeError("down")

    monkeypatch.setattr(INSETS, "fetch_inset", raising)
    assert ELEVATION_LEVEL.ensure_approach_rings(tile, dico) == 0
    plan = ELEVATION_LEVEL.resolve_approach_ring_plan(tile, dico)
    assert {c["provider"] for c in plan["cells"] if c["provider"]} \
        == {"FIRST"}
    assert ELEVATION_LEVEL.approach_ring_frame_problem(
        RING_FIXTURES.TILE_LAT, RING_FIXTURES.TILE_LON, plan)[0] == "cold"


# --- the tile-wide numeric overlay --------------------------------------
def _overlay_tile(level="1"):
    return COAST._coastline_tile(elevation_level=level)


def _whole_tile_registry(monkeypatch, tmp_path):
    """One national 1 m service over the whole tile, nothing else."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "uniform"))
    whole = (COAST.TILE_LON - 1, COAST.TILE_LAT - 1,
             COAST.TILE_LON + 2, COAST.TILE_LAT + 2)
    LADDER_FIXTURES.PROVIDERS._install_registry(monkeypatch, [
        LADDER_FIXTURES.PROVIDERS._definition(
            "NATIONAL", resolution_m=1.0, priority=80.0,
            coverage_bbox=whole)])


def test_a_tile_one_provider_covers_keeps_the_single_fetch(
        monkeypatch, tmp_path):
    _whole_tile_registry(monkeypatch, tmp_path)
    plan = ELEVATION_LEVEL.resolve_tile_overlay_plan(_overlay_tile())
    assert not plan.get("cellular")
    assert plan["path"] == FNAMES.tile_overlay_dem(
        COAST.TILE_LAT, COAST.TILE_LON, "NATIONAL",
        plan["target_resolution_m"])


def test_a_border_tile_plans_its_overlay_per_cell(monkeypatch, tmp_path):
    """The regional service reaches only the west half: the tile's cells
    have different first providers, so the overlay is cellular."""
    LADDER_FIXTURES._ladder_registry(monkeypatch, tmp_path)
    plan = ELEVATION_LEVEL.resolve_tile_overlay_plan(_overlay_tile())
    assert plan["cellular"] and plan["definition"]["code"] == "REGIONAL"
    assert plan["path"] == FNAMES.tile_overlay_cells_vrt(
        COAST.TILE_LAT, COAST.TILE_LON, plan["target_resolution_m"])


@needs_gdal
def test_a_border_tile_takes_each_cells_provider_and_falls_through(
        monkeypatch, tmp_path):
    """Two regional providers (west half, then the national one over the
    whole tile): the west cells come from REGIONAL, the east ones from
    NATIONAL, and a west cell REGIONAL answers no coverage for falls
    through to NATIONAL at fetch time."""
    LADDER_FIXTURES._ladder_registry(monkeypatch, tmp_path)
    records = []
    writing = COAST._writing_fetch(records)

    def fetch(definition, box, resolution_m, destination):
        column, row = COAST._bbox_to_cell(box)
        if definition["code"] == "REGIONAL" and (column, row) == (0, 0):
            return None
        return writing(definition, box, resolution_m, destination)

    monkeypatch.setattr(INSETS, "fetch_inset", fetch)
    tile = _overlay_tile()
    path = ELEVATION_LEVEL.ensure_tile_overlay(tile)
    assert path and path.endswith(".vrt") and os.path.isfile(path)
    by_cell = {record["cell"]: record["definition"]["code"]
               for record in records}
    assert len(by_cell) == 100
    # The regional box's east edge lies ON column 5's west edge, and a box
    # that touches a cell reaches it (the coverage test's own convention).
    for (column, row), code in by_cell.items():
        if column >= 6 or (column, row) == (0, 0):
            assert code == "NATIONAL", (column, row)
        else:
            assert code == "REGIONAL", (column, row)
    assert OVERLAY_CELLS.recorded_cell_providers(path) == {
        "REGIONAL": 59, "NATIONAL": 41}
    index = json.load(open(FNAMES.tile_overlay_index(
        COAST.TILE_LAT, COAST.TILE_LON), encoding="utf-8"))
    assert INSETS.NO_COVERAGE in index.values()
    # A second build recycles the mosaic: nobody is asked.
    del records[:]
    assert ELEVATION_LEVEL.ensure_tile_overlay(tile) == path
    assert records == []


@needs_gdal
def test_a_whole_tile_no_coverage_falls_through_per_cell(
        monkeypatch, tmp_path):
    """One provider over the tile answers the whole-tile request with no
    coverage: the overlay goes cellular at once, each cell walking the
    ladder (here the same provider, which serves the cells it has)."""
    _whole_tile_registry(monkeypatch, tmp_path)
    records = []
    writing = COAST._writing_fetch(records)

    def fetch(definition, box, resolution_m, destination):
        if box == (COAST.TILE_LON, COAST.TILE_LAT,
                   COAST.TILE_LON + 1, COAST.TILE_LAT + 1):
            return None
        column, _row = COAST._bbox_to_cell(box)
        if column > 2:
            return None
        return writing(definition, box, resolution_m, destination)

    monkeypatch.setattr(INSETS, "fetch_inset", fetch)
    path = ELEVATION_LEVEL.ensure_tile_overlay(_overlay_tile())
    assert path == FNAMES.tile_overlay_cells_vrt(
        COAST.TILE_LAT, COAST.TILE_LON,
        ELEVATION_LEVEL.resolve_tile_overlay_plan(
            _overlay_tile())["target_resolution_m"])
    assert OVERLAY_CELLS.recorded_cell_providers(path) == {"NATIONAL": 30}
