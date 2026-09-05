"""Twin for the bathymetry band's fetch-admission stamp (2026-09-04).

``index.json`` is corpus-adjacent fetch-admission state in the shared
data repo (scope ``dem``, no churn allowance in the harness write guard),
so a SETTLED warm pass must make NO write at all: no stamp, no
``fetch.lock``, no mosaic rebuild.  Measured 2026-09-04 on +25+051 (the
OTHH tile): the masks step (auto gating → CORALATLAS) and the DSF step
(all providers → GEBCO2024) each rewrote the stamp with their own
provider/gating, the masks writer dropping the other provider's ``ok``
cells, and the guard refused the first of them in step 3.

What is pinned here:

  * the masks-then-DSF sequence over a settled band directory (cells on
    disk, negatives recorded, mosaic present) under a REFUSE-mode
    ``SharedRepoWriteGuard`` pointed at the band's root makes no write
    and no lock churn, leaves every file byte-for-byte alone (size +
    mtime, which is how the harness's after-snapshot would catch a GDAL
    write the guard cannot intercept), and returns the right mosaics;
  * a band with one missing cell DOES attempt the write — the guard
    raises — so the fix suppresses churn, not real refreshes;
  * ``is_cached`` is True for the settled directory and False for the
    missing-cell one, under both gatings;
  * the LEGACY stamp shape (``provider`` / ``cells`` / ``checked`` /
    ``gating``, the OTHH stamp on disk) reads as settled with no
    rewrite; and a stamp the fixed pass writes settles itself the same
    way on the next run;
  * two gatings mosaicking different subsets of one provider's cells
    each keep their own VRT (legacy name first, content-keyed second),
    so a warm pass never rebuilds a shared file at every step.

Headless: ``tmp_path`` for the whole "shared repo", the cell download
monkeypatched, synthetic registry and coastline.  Skipped without the
GDAL python bindings (the band is a no-op without them).
"""

import importlib.util
import json
import os
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))

try:
    from osgeo import gdal, osr

    HAS_GDAL = True
except Exception:
    HAS_GDAL = False

import numpy
from shapely.geometry import MultiLineString

import O4_Airport_Elevation_Insets as INSETS
import O4_Bathymetry_Band as BATHYBAND
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

pytestmark = pytest.mark.skipif(
    not HAS_GDAL, reason="osgeo (GDAL python bindings) not available"
)

FINE = "FINEBATHY"      # admitted by the auto (masks) gating
COARSE = "COARSEBATHY"  # filtered out by auto, walked by the DSF gating

# A short coastline along longitude 0.15 degrees: with
# ``bathymetry_band_km=0.1`` exactly the four cells (column 1, rows
# 0..3) of the +00+000 tile are selected (see test_bathymetry_band_fetch).
FOUR_CELL_COASTLINE = MultiLineString([[(0.15, 0.05), (0.15, 0.35)]])
FOUR_CELLS = [(1, 0), (1, 1), (1, 2), (1, 3)]


def _guard_module():
    path = os.path.join(os.path.dirname(_HERE), "tools", "harness",
                        "shared_repo_guard.py")
    spec = importlib.util.spec_from_file_location(
        "band_stamp_twin_shared_repo_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tile():
    return SimpleNamespace(lat=0, lon=0, bathymetry_band_km=0.1,
                           masks_use_DEM_too="auto")


def _definitions():
    return [
        {"code": FINE, "role": "bathymetry", "enabled": True,
         "priority": 100.0, "native_resolution_m": 3.0},
        {"code": COARSE, "role": "bathymetry", "enabled": True,
         "priority": 10.0, "native_resolution_m": 450.0},
    ]


def _cell_path(code, cell_column, cell_row):
    return FNAMES.bathymetry_band_cell(
        0, 0, cell_column, cell_row, code,
        BATHYBAND.BATHYMETRY_CELL_RESOLUTION_M)


def _stem(code, cell_column, cell_row):
    return os.path.splitext(
        os.path.basename(_cell_path(code, cell_column, cell_row)))[0]


def _write_cell_geotiff(path, west, south, east, north):
    columns = rows = 4
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform(
        (west, (east - west) / columns, 0, north, 0, (south - north) / rows))
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    dataset.SetProjection(spatial_reference.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    values = numpy.full((rows, columns), -32768.0, dtype=numpy.float32)
    values[1:, :] = -5.0
    band.WriteArray(values)
    band.FlushCache()
    dataset = None


def _cell_bbox(cell_column, cell_row):
    d = BATHYBAND.BATHYMETRY_CELL_DEGREES
    return (cell_column * d, cell_row * d, (cell_column + 1) * d,
            (cell_row + 1) * d)


def _install_fake_fetch(monkeypatch, fetch_calls, yields):
    """``yields``: provider codes that return data; the others report
    no coverage (a durable negative)."""

    def _fake_fetch_inset(definition, bounding_box, resolution,
                          destination_path):
        fetch_calls.append((definition["code"], bounding_box))
        if definition["code"] not in yields:
            return None
        _write_cell_geotiff(destination_path, *bounding_box)
        return {"provider": definition["code"]}

    monkeypatch.setattr(INSETS, "fetch_inset", _fake_fetch_inset)


@pytest.fixture(autouse=True)
def _band_environment(monkeypatch, tmp_path):
    """The whole 'shared repo' under tmp_path: Elevation_data/... ."""
    repo = tmp_path / "repo"
    (repo / "Elevation_data").mkdir(parents=True)
    monkeypatch.setattr(FNAMES, "Elevation_dir",
                        str(repo / "Elevation_data"))
    monkeypatch.setattr(INSETS, "select_bathymetry_definitions",
                        lambda lat, lon: _definitions())
    monkeypatch.setattr(BATHYBAND, "_band_geometry",
                        lambda tile: (FOUR_CELL_COASTLINE, None))
    # No airport index in a headless test: the auto gate disengages and
    # the fine gating walks the same four cells (a subset case is built
    # explicitly below).
    monkeypatch.setattr(BATHYBAND, "BAND_LOCK_POLL_SECONDS", 0.05)
    monkeypatch.setattr(UI, "red_flag", False)
    BATHYBAND._prefetch_futures.clear()
    BATHYBAND._foreground_wait.clear()
    yield
    UI.red_flag = False
    BATHYBAND._prefetch_futures.clear()
    BATHYBAND._foreground_wait.clear()


def _repo(tmp_path):
    return tmp_path / "repo"


def _snapshot(root):
    out = {}
    for directory, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(directory, name)
            stat = os.stat(path)
            out[path] = (stat.st_size, stat.st_mtime_ns)
    return out


def _settle_legacy_band():
    """The OTHH situation: FINE recorded as no-coverage everywhere, COARSE
    cells on disk with the LEGACY stamp (provider/cells/checked/gating
    of the DSF pass) and the legacy-named mosaic."""
    directory = FNAMES.bathymetry_band_directory(0, 0)
    os.makedirs(directory, exist_ok=True)
    cells = {}
    coarse_paths = []
    for (column, row) in FOUR_CELLS:
        cells[_stem(FINE, column, row)] = BATHYBAND.NO_COVERAGE
        path = _cell_path(COARSE, column, row)
        _write_cell_geotiff(path, *_cell_bbox(column, row))
        cells[_stem(COARSE, column, row)] = "ok"
        coarse_paths.append(path)
    vrt_path = FNAMES.bathymetry_band_vrt(0, 0, COARSE)
    mosaic = gdal.BuildVRT(vrt_path, coarse_paths)
    mosaic = None
    stamp = {
        "provider": COARSE,
        "cells": cells,
        "checked": "2026-09-03",
        "gating": [False, False, 0.1],
    }
    BATHYBAND._write_band_stamp(FNAMES.bathymetry_band_index(0, 0), stamp)
    return vrt_path


def _guarded_sequence(tmp_path, monkeypatch, fetch_calls=None):
    """The masks-then-DSF sequence under a refuse-mode guard on the
    tmp 'shared repo'; returns (masks_vrt, dsf_vrt, guard, before, after)."""
    SRG = _guard_module()
    _install_fake_fetch(monkeypatch, fetch_calls if fetch_calls is not None
                        else [], yields={FINE, COARSE})
    repo = _repo(tmp_path)
    lane = tmp_path / "lane"
    lane.mkdir(exist_ok=True)
    before = _snapshot(repo)
    guard = SRG.SharedRepoWriteGuard(set(), root=str(lane), repo=str(repo))
    with guard:
        masks_vrt = BATHYBAND.ensure_bathymetry_band(_tile(), True, False)
        dsf_vrt = BATHYBAND.ensure_bathymetry_band(_tile())
    after = _snapshot(repo)
    return (masks_vrt, dsf_vrt, guard, before, after)


# =====================================================================
# (a) + (c) + legacy: the settled band, the OTHH shape
# =====================================================================
def test_settled_legacy_band_makes_no_write_under_the_guard(
    tmp_path, monkeypatch
):
    vrt_path = _settle_legacy_band()
    stamp_path = FNAMES.bathymetry_band_index(0, 0)
    stamp_before = open(stamp_path).read()

    assert BATHYBAND.is_cached(_tile()) is True, "masks gating"
    assert BATHYBAND.is_cached(_tile(), False, False) is True, "DSF gating"

    fetch_calls = []
    (masks_vrt, dsf_vrt, guard, before, after) = _guarded_sequence(
        tmp_path, monkeypatch, fetch_calls)

    # The masks gating admits FINE only, every FINE cell is a durable
    # negative: nothing to fetch, nothing to mosaic.
    assert masks_vrt is None
    # The DSF gating falls through to COARSE and finds its mosaic.
    assert dsf_vrt == vrt_path
    assert fetch_calls == []
    assert guard.blocked == []
    assert guard.lock_churn == []
    assert after == before, "a settled warm pass wrote the shared repo"
    assert open(stamp_path).read() == stamp_before
    assert not [n for n in os.listdir(os.path.dirname(stamp_path))
                if ".part" in n or n == BATHYBAND.BAND_LOCK_FILE_NAME]


# =====================================================================
# (b) + (c): a missing cell IS a refresh — the write is attempted
# =====================================================================
def test_missing_cell_attempts_the_write_and_the_guard_refuses(
    tmp_path, monkeypatch
):
    _settle_legacy_band()
    os.remove(_cell_path(COARSE, 1, 2))

    assert BATHYBAND.is_cached(_tile()) is True, (
        "the masks gating never walks COARSE: still settled")
    assert BATHYBAND.is_cached(_tile(), False, False) is False, (
        "the DSF gating would refetch the missing COARSE cell")

    SRG = _guard_module()
    fetch_calls = []
    # The provider answers no-coverage: a durable negative to record — a
    # stamp write, which the guard must refuse at the call.
    _install_fake_fetch(monkeypatch, fetch_calls, yields=set())
    repo = _repo(tmp_path)
    lane = tmp_path / "lane"
    lane.mkdir()
    guard = SRG.SharedRepoWriteGuard(set(), root=str(lane), repo=str(repo))
    with guard:
        assert BATHYBAND.ensure_bathymetry_band(_tile(), True, False) is None
        with pytest.raises(SRG.SharedRepoWriteBlocked):
            BATHYBAND.ensure_bathymetry_band(_tile())
    assert [c for c, _b in fetch_calls] == [COARSE]
    assert guard.blocked and guard.blocked[0]["scope"] == "dem"
    assert "index.json" in guard.blocked[0]["path"]


# =====================================================================
# The stamp the FIXED pass writes settles itself the same way
# =====================================================================
def test_fresh_fetch_then_warm_sequence_writes_nothing(
    tmp_path, monkeypatch
):
    fetch_calls = []
    # FINE has no coverage anywhere; COARSE has data: the OTHH shape,
    # written by this code.
    _install_fake_fetch(monkeypatch, fetch_calls, yields={COARSE})
    assert BATHYBAND.ensure_bathymetry_band(_tile(), True, False) is None
    dsf_vrt = BATHYBAND.ensure_bathymetry_band(_tile())
    assert dsf_vrt == FNAMES.bathymetry_band_vrt(0, 0, COARSE)
    assert len(fetch_calls) == 8, "4 FINE negatives + 4 COARSE cells"

    stamp = json.load(open(FNAMES.bathymetry_band_index(0, 0)))
    assert stamp["provider"] == COARSE
    assert stamp["gating"] == [False, False, 0.1]
    # MERGE semantics: both providers' outcomes, all in one map.
    assert sorted(set(stamp["cells"].values())) == ["no_coverage", "ok"]
    assert len(stamp["cells"]) == 8
    # Both gatings ran to a settle and are recorded with what they walked
    # and mosaicked.
    gatings = stamp["gatings"]
    fine_key = BATHYBAND._gating_key_text([True, False, 0.1])
    all_key = BATHYBAND._gating_key_text([False, False, 0.1])
    assert gatings[fine_key] == {"provider": FINE, "reached": [FINE],
                                 "mosaic": []}
    assert gatings[all_key]["provider"] == COARSE
    assert gatings[all_key]["reached"] == [FINE, COARSE]
    assert len(gatings[all_key]["mosaic"]) == 4

    assert BATHYBAND.is_cached(_tile()) is True
    assert BATHYBAND.is_cached(_tile(), False, False) is True

    warm_calls = []
    (masks_vrt, dsf_vrt_again, guard, before, after) = _guarded_sequence(
        tmp_path, monkeypatch, warm_calls)
    assert (masks_vrt, dsf_vrt_again) == (None, dsf_vrt)
    assert warm_calls == []
    assert guard.blocked == [] and guard.lock_churn == []
    assert after == before


def test_checked_date_alone_never_triggers_a_write(tmp_path, monkeypatch):
    _settle_legacy_band()
    stamp_path = FNAMES.bathymetry_band_index(0, 0)
    stamp = json.load(open(stamp_path))
    stamp["checked"] = "2020-01-01"
    BATHYBAND._write_band_stamp(stamp_path, stamp)
    mtime = os.stat(stamp_path).st_mtime_ns
    _install_fake_fetch(monkeypatch, [], yields=set())
    BATHYBAND.ensure_bathymetry_band(_tile(), True, False)
    BATHYBAND.ensure_bathymetry_band(_tile())
    assert os.stat(stamp_path).st_mtime_ns == mtime
    assert json.load(open(stamp_path))["checked"] == "2020-01-01"


# =====================================================================
# Two gatings, two subsets of one provider: two mosaics, no rebuilds
# =====================================================================
def test_two_gatings_keep_their_own_mosaics(tmp_path, monkeypatch):
    fetch_calls = []
    _install_fake_fetch(monkeypatch, fetch_calls, yields={FINE})
    # The auto gating keeps two of the four cells (an engaged airport
    # gate); the DSF gating wants all four.
    real_filter = BATHYBAND._filter_cells_to_airport_reach

    def _gate(tile, categories, cell_indices, *rest):
        kept = [c for c in cell_indices if c[1] < 2]
        return (kept, len(cell_indices) - len(kept), True)

    monkeypatch.setattr(BATHYBAND, "_filter_cells_to_airport_reach", _gate)
    monkeypatch.setattr(BATHYBAND, "_enabled_anchor_categories",
                        lambda tile: frozenset({"icao_airport"}))

    masks_vrt = BATHYBAND.ensure_bathymetry_band(_tile(), True, False)
    assert masks_vrt == FNAMES.bathymetry_band_vrt(0, 0, FINE), (
        "the first mosaic of a provider takes the legacy name")
    assert len(BATHYBAND._vrt_source_paths(masks_vrt)) == 2
    dsf_vrt = BATHYBAND.ensure_bathymetry_band(_tile())
    assert dsf_vrt != masks_vrt
    assert os.path.basename(dsf_vrt).startswith("band_finebathy_")
    assert len(BATHYBAND._vrt_source_paths(dsf_vrt)) == 4
    assert len(fetch_calls) == 4, "the two extra cells only"
    assert len(BATHYBAND._vrt_source_paths(masks_vrt)) == 2, (
        "the DSF pass must not rebuild the masks gating's mosaic")

    assert BATHYBAND.is_cached(_tile()) is True
    assert BATHYBAND.is_cached(_tile(), False, False) is True

    (masks_again, dsf_again, guard, before, after) = _guarded_sequence(
        tmp_path, monkeypatch)
    assert (masks_again, dsf_again) == (masks_vrt, dsf_vrt)
    assert guard.blocked == [] and guard.lock_churn == []
    assert after == before
    del real_filter


# =====================================================================
# The harness admission uses the engine predicate, per gating
# =====================================================================
def test_harness_admission_names_the_band_and_the_dem_scope(
    tmp_path, monkeypatch
):
    path = os.path.join(os.path.dirname(_HERE), "tools", "harness",
                        "build_airport.py")
    spec = importlib.util.spec_from_file_location(
        "band_stamp_twin_build_airport", path)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)

    tile = _tile()
    tile.dsf_bathymetry = "True"
    # Cold band: both gatings would fetch.
    missing = harness.bathymetry_band_admission(
        tile, str(_repo(tmp_path)), dsf_step_runs=True)
    assert [m[0] for m in missing] == ["dem", "dem"]
    assert all("bathymetry_band" in m[1] for m in missing)
    with pytest.raises(SystemExit) as refusal:
        harness.require_no_implicit_refresh(missing, set())
    assert "--refresh-data dem" in str(refusal.value)
    harness.require_no_implicit_refresh(missing, {"dem"})

    # Settled band: nothing to name.
    _settle_legacy_band()
    assert harness.bathymetry_band_admission(
        tile, str(_repo(tmp_path)), dsf_step_runs=True) == []
    # A missing COARSE cell is the DSF gating's refresh only — and only
    # when step 4 runs and the DSF dispatch consults the band.
    os.remove(_cell_path(COARSE, 1, 2))
    assert [m[0] for m in harness.bathymetry_band_admission(
        tile, str(_repo(tmp_path)), dsf_step_runs=True)] == ["dem"]
    assert harness.bathymetry_band_admission(
        tile, str(_repo(tmp_path)), dsf_step_runs=False) == []
    tile.dsf_bathymetry = "False"
    assert harness.bathymetry_band_admission(
        tile, str(_repo(tmp_path)), dsf_step_runs=True) == []
