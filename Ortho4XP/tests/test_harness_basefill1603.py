"""#1603 -- the ``dem`` refresh fetches the base-void fill rasters, and a
guard-refused base-tile fetch leaves nothing in the shared repo.

MEASURED 2026-10-28 (LFLL, N45E005).  The closing build's DEM load asked
Copernicus GLO-30 and GLO-90 for the base cell's void posts (#1465); the
write guard refused both renames and flagged the run CONTAMINATED, but
the GDAL-written ``*.tif.part`` scratch (32 MB, 27 MB) stayed beside the
cache, and ``--refresh-data dem --refresh-only`` could not clear the
block: no refresh pass asked the void fill.

OFFLINE: the fallback strategy is a local writer (``_Donor``) and the
base load is the engine's own rule over a holed raster.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import types
from pathlib import Path

import numpy
import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"
sys.path.insert(0, str(ROOT / "src"))

import O4_Airport_Elevation_Insets as INSETS              # noqa: E402
import O4_DEM_Utils as DEM                                # noqa: E402
import O4_File_Names as FNAMES                            # noqa: E402
import O4_UI_Utils as UI                                  # noqa: E402
from elevation_access import fetch_scratch                # noqa: E402
from elevation_access import registry as ea_registry      # noqa: E402
from elevation_access.gdal_support import gdal, has_gdal  # noqa: E402
from elevation_access.strategies import (                 # noqa: E402
    degree_cog_base_tile as ea_cog_base)

from test_base_elevation_voids import (                   # noqa: E402
    NODATA, _Donor, _slope, _with_void)

STATE = {"tile_stem": "N45E005", "airport_insets": True,
         "airports_layer": True, "base_raster": True}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def build_mod():
    return _load("harness_basefill1603_build", HARNESS / "build_airport.py")


class _Notes:
    def __init__(self):
        self.lines = []

    def note(self, msg):
        self.lines.append(msg)


@pytest.fixture
def warm_tile(build_mod, tmp_path, monkeypatch):
    """A warm tile (base raster, insets, airports layer all present) whose
    base cell holds a void too wide for the neighbour fill."""
    import O4_Config_Utils as CFG

    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "Elev"))
    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "_donor", _Donor)
    monkeypatch.setattr(UI, "red_flag", False)
    _Donor.calls, _Donor.failing = [], False
    monkeypatch.setattr(INSETS, "elevation_providers_dict", {
        "SPARE1": {"code": "SPARE1", "role": "base", "fallback_rank": "1",
                   "access_strategy": "_donor"}})
    monkeypatch.setattr(build_mod, "dem_cache_state",
                        lambda root, lat, lon: dict(STATE))
    monkeypatch.setattr(build_mod, "_refresh_airport_inset",
                        lambda *a, **k: [])
    monkeypatch.setattr(build_mod, "_complete_pending_insets",
                        lambda *a, **k: [])
    monkeypatch.setattr(CFG, "Tile", lambda lat, lon, _s: types.
                        SimpleNamespace(lat=lat, lon=lon, custom_dem="",
                                        fill_nodata=True,
                                        elevation_level="auto",
                                        read_from_config=lambda: None))
    loads = []
    engine_dem = DEM.DEM

    def _load_base(lat, lon, source="", fill_nodata=True, info_only=False,
                   elevation_level="auto"):
        """The engine's DEM load over a holed base cell: its own
        ``fill_base_voids`` decides and fetches."""
        loads.append((lat, lon, source, fill_nodata, info_only))
        dem = engine_dem.__new__(engine_dem)
        (dem.lat, dem.lon, dem.nodata) = (lat, lon, NODATA)
        (dem.x0, dem.y0, dem.x1, dem.y1) = (0.0, 0.0, 1.0, 1.0)
        (dem.alt_dem, dem.base_void_fills) = (_with_void(_slope()), [])
        if fill_nodata and fill_nodata != "to zero":
            dem.fill_base_voids()
        return dem

    monkeypatch.setattr(DEM, "DEM", _load_base)
    return loads


def test_a_refresh_only_dem_run_fetches_the_base_void_fill(
        build_mod, warm_tile, tmp_path):
    """THE #1603 GAP: a warm frame used to answer "nothing to derive"
    while the build's DEM load would fetch the fallback raster."""
    notes = _Notes()
    out = build_mod.refresh_tile_dem(tmp_path, 45, 5, notes, icao="LFLL")
    path = "%s_SPARE1.hgt" % FNAMES.base_file_name(45, 5)
    assert os.path.isfile(path)
    assert _Donor.calls == ["SPARE1"]
    assert warm_tile == [(45, 5, "", True, False)]       # as a build loads
    assert len(out["derived"]) == 1
    assert out["derived"][0].startswith(path + " [base voids: ")
    assert not any("nothing to derive" in line for line in notes.lines)
    # A second refresh recycles the cached fallback: nothing derived.
    out = build_mod.refresh_tile_dem(tmp_path, 45, 5, _Notes(), icao="LFLL")
    assert out["derived"] == []


def test_a_tile_that_fills_voids_to_zero_asks_no_fallback(
        build_mod, warm_tile, tmp_path, monkeypatch):
    import O4_Config_Utils as CFG

    monkeypatch.setattr(CFG, "Tile", lambda lat, lon, _s: types.
                        SimpleNamespace(lat=lat, lon=lon, custom_dem="",
                                        fill_nodata=False,
                                        read_from_config=lambda: None))
    out = build_mod.refresh_tile_dem(tmp_path, 45, 5, _Notes())
    assert out["derived"] == [] and warm_tile == [] and _Donor.calls == []


# ---------------------------------------- the guarded base-tile fetch
def _guard(repo, lane, requested=()):
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    guard_mod = importlib.import_module("shared_repo_guard")
    return guard_mod.SharedRepoWriteGuard(set(requested), str(lane),
                                          repo=str(repo))


@pytest.fixture
def cog_fetch(tmp_path, monkeypatch):
    """A fake shared root mounted as the elevation directory, and a
    strategy whose warp writes its scratch through GDAL."""
    repo = tmp_path / "corpus"
    (repo / "Elevation_data").mkdir(parents=True)
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(repo / "Elevation_data"))
    monkeypatch.setenv(fetch_scratch.SCRATCH_ENV, str(tmp_path / "scratch"))
    warped = []

    def _fake_warp(sources, bounds, resolution, destination, **keywords):
        warped.append(destination)
        dataset = gdal.GetDriverByName("GTiff").Create(
            destination, 6, 6, 1, gdal.GDT_Float32)
        dataset.GetRasterBand(1).WriteArray(
            numpy.full((6, 6), 300.0, dtype=numpy.float32))
        dataset.GetRasterBand(1).SetNoDataValue(-32768)
        dataset = None
        return True

    strategy = ea_cog_base.DegreeCogBaseTileStrategy()
    monkeypatch.setattr(strategy, "_sources",
                        lambda definition, lat, lon: ["/vsicurl/cell"])
    monkeypatch.setattr(ea_cog_base, "warp_vsicurl_sources_to_geotiff",
                        _fake_warp)
    definition = {"code": "COPERNICUSGLO30BASE"}
    return repo, strategy, definition, warped


def _files(folder):
    return sorted(str(p.relative_to(folder)) for p in Path(folder).rglob("*")
                  if p.is_file())


@pytest.mark.skipif(not has_gdal, reason="needs GDAL")
def test_a_refused_base_tile_write_leaves_no_part_in_the_shared_root(
        cog_fetch, tmp_path):
    """THE #1603 REPRODUCTION, as an intervention: a guard that authorises
    nothing.  Before the fix the warp cut ``<cache>.tif.part`` beside the
    cache through GDAL, and the guard refused the rename AND the cleanup."""
    repo, strategy, definition, warped = cog_fetch
    guard = _guard(repo, tmp_path / "lane")
    with guard:
        with pytest.raises(RuntimeError, match="COPERNICUSGLO30BASE"):
            strategy.ensure_tile(definition, 45, 5, False)
    assert warped == []                                  # nothing fetched
    assert _files(repo) == []                            # no .part, nothing
    assert guard.blocked[0]["scope"] == "dem"
    assert guard.blocked[0]["via"] == (
        "spawn the base elevation tile fetch writing")


@pytest.mark.skipif(not has_gdal, reason="needs GDAL")
def test_an_authorised_base_tile_fetch_cuts_in_scratch_and_lands(
        cog_fetch, tmp_path):
    repo, strategy, definition, warped = cog_fetch
    with _guard(repo, tmp_path / "lane", requested={"dem"}):
        assert strategy.ensure_tile(definition, 45, 5, False) == 1
    cache = strategy.tile_cache_path(definition, 45, 5)
    assert _files(repo) == [
        str(Path(cache).relative_to(repo))]              # the raster only
    assert warped[0].startswith(str(tmp_path / "scratch"))
    assert os.listdir(tmp_path / "scratch") == []        # folder discarded
