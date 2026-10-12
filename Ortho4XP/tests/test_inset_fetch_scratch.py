"""#583 -- an inset fetch works in a private scratch folder, never beside
the cache.

The measured defect: a tile build under the harness's shared-repo write
guard re-fetched two airport insets; the strategies cut 74 scratch files
(166 MB) beside the cached rasters through GDAL, which the Python-level
guard cannot see, and the guard then refused the ``os.remove`` of each.
The same scratch stayed for good after a killed app build.

No network: a fake strategy writes its raster AND its scratch through
GDAL, and never cleans the scratch -- what a killed fetch leaves.
"""
import errno
import importlib
import os
import sys
import time
from pathlib import Path

import pytest

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS
from elevation_access import base as ea_base
from elevation_access import definitions as ea_definitions
from elevation_access import fetch_scratch
from elevation_access import registry as ea_registry

from test_inset_resolution_ladder import BOX, HAS_GDAL, _write_raster

requires_gdal = pytest.mark.skipif(not HAS_GDAL, reason="no osgeo")
STRATEGY = "scratch_fake_strategy"
HARNESS = Path(__file__).resolve().parent.parent / "tools" / "harness"
WIDER_BOX = (BOX[0] - 0.02, BOX[1] - 0.02, BOX[2] + 0.02, BOX[3] + 0.02)


@pytest.fixture
def littering_strategy(monkeypatch, tmp_path):
    """One provider whose fetch leaves two scratch files beside the path
    it was asked to write.  ``plan["raise"]`` makes the fetch fail after
    writing them."""
    plan = {}
    calls = []

    @ea_registry.register_access_strategy(STRATEGY)
    class _Fake:
        def discover(self, definition, bounding_box_wgs84):
            return [{"source_id": "s1"}]

        def fetch(self, definition, bounding_box_wgs84,
                  target_resolution_m, destination_path):
            calls.append(destination_path)
            _write_raster(destination_path + ".tile0.tif", 1.0)
            _write_raster(destination_path + ".tile1.tif", 1.0)
            if plan.get("raise"):
                _write_raster(destination_path, 0.5)     # a partial file
                raise ea_base.TransientFetchError("server went away")
            _write_raster(destination_path, 1.0)
            return {"provider": definition["code"],
                    "native_resolution_m": 1.0,
                    "resolution_m": target_resolution_m,
                    "sources_used": [{"source_id": "s1"}]}

    definition = {
        "code": "FAKESCR", "access_strategy": STRATEGY,
        "role": ea_definitions.ROLE_AIRPORT_INSET, "enabled": True,
        "priority": 1.0, "native_resolution_m": 1.0,
    }
    monkeypatch.setattr(INSETS, "elevation_providers_dict",
                        {"FAKESCR": definition})
    monkeypatch.setenv(fetch_scratch.SCRATCH_ENV, str(tmp_path / "scratch"))
    try:
        yield plan, calls, definition
    finally:
        ea_registry.ACCESS_STRATEGIES.pop(STRATEGY, None)


def _corpus(tmp_path, monkeypatch):
    """A tmp corpus mounted as the engine's elevation directory."""
    repo = tmp_path / "corpus"
    (repo / "Elevation_data").mkdir(parents=True)
    monkeypatch.setattr(FNAMES, "Elevation_dir",
                        str(repo / "Elevation_data"))
    return repo


def _inset_dir():
    return FNAMES.airport_inset_directory(39, -107)


def _guard(repo, lane, requested=()):
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    guard_mod = importlib.import_module("shared_repo_guard")
    return guard_mod.SharedRepoWriteGuard(set(requested), str(lane),
                                          repo=str(repo))


@requires_gdal
def test_a_fetch_leaves_only_the_finished_inset_in_the_cache(
        tmp_path, monkeypatch, littering_strategy):
    _plan, calls, definition = littering_strategy
    _corpus(tmp_path, monkeypatch)
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition], None)
    assert sorted(os.listdir(_inset_dir())) == [
        "KASE_fakescr.json", "KASE_fakescr.tif", "index.json"]
    assert os.path.dirname(calls[0]).startswith(str(tmp_path / "scratch"))
    assert os.path.basename(calls[0]) == "KASE_fakescr.tif"
    assert os.listdir(tmp_path / "scratch") == []        # folder discarded


@requires_gdal
def test_a_failed_refetch_keeps_the_cached_inset_and_leaves_no_scratch(
        tmp_path, monkeypatch, littering_strategy):
    plan, calls, definition = littering_strategy
    _corpus(tmp_path, monkeypatch)
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition], None)
    cached = os.path.join(_inset_dir(), "KASE_fakescr.tif")
    with open(cached, "rb") as handle:
        body = handle.read()
    plan["raise"] = True
    for (box, refresh) in ((WIDER_BOX, False), (BOX, True)):
        failures = []
        INSETS.ensure_airport_insets(39, -107, {"KASE": box}, [definition],
                                     None, refresh=refresh,
                                     fetch_failures=failures)
        assert [row[:2] for row in failures] == [("KASE", "FAKESCR")]
        with open(cached, "rb") as handle:
            assert handle.read() == body
        assert sorted(os.listdir(_inset_dir())) == [
            "KASE_fakescr.json", "KASE_fakescr.tif", "index.json"]
        assert os.listdir(tmp_path / "scratch") == []
    assert len(calls) == 3


@requires_gdal
def test_an_armed_guard_refuses_the_refetch_before_a_byte_is_fetched(
        tmp_path, monkeypatch, littering_strategy):
    """THE #583 REPRODUCTION, as an intervention: a stale cached inset, a
    guard that authorises nothing.  Before the fix the fake's GDAL writes
    landed beside the cache and only the removal was refused."""
    _plan, calls, definition = littering_strategy
    repo = _corpus(tmp_path, monkeypatch)
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition], None)
    before = sorted(os.listdir(_inset_dir()))
    calls.clear()
    guard = _guard(repo, tmp_path / "lane")
    with guard:
        # The pass then records the wider box in the index: a Python
        # write, refused at the call as it always was.
        with pytest.raises(RuntimeError, match="index.json"):
            INSETS.ensure_airport_insets(39, -107, {"KASE": WIDER_BOX},
                                         [definition], None)
    assert calls == []                                   # nothing fetched
    assert sorted(os.listdir(_inset_dir())) == before    # nothing written
    assert (guard.blocked[0]["scope"], guard.blocked[0]["via"]) == (
        "dem", "spawn the airport inset fetch writing")
    assert guard.blocked[0]["path"].endswith("KASE_fakescr.tif")
    assert not any("remove" in row["via"] or "unlink" in row["via"]
                   for row in guard.blocked)             # no cleanup refused


@requires_gdal
def test_an_authorised_refresh_fetches_in_scratch_and_lands_the_raster(
        tmp_path, monkeypatch, littering_strategy):
    _plan, calls, definition = littering_strategy
    repo = _corpus(tmp_path, monkeypatch)
    guard = _guard(repo, tmp_path / "lane", requested={"dem"})
    with guard:
        INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition],
                                     None)
    assert guard.blocked == []
    assert len(calls) == 1
    assert sorted(os.listdir(_inset_dir())) == [
        "KASE_fakescr.json", "KASE_fakescr.tif", "index.json"]


def _aged(path, age_s):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    stamp = time.time() - age_s
    os.utime(path, (stamp, stamp))
    return path


def test_sweep_removes_what_a_killed_fetch_left_and_nothing_else(
        tmp_path, monkeypatch):
    monkeypatch.setenv(fetch_scratch.SCRATCH_ENV, str(tmp_path / "scratch"))
    insets = tmp_path / "N47W123_airport_insets"
    old = 2 * fetch_scratch.STALE_SCRATCH_S
    stale = [_aged(insets / name, old) for name in (
        "KGRF_usgs3dep.tif.refetch", "KGRF_usgs3dep.tif.refetch.rung2",
        "KTCM_usgs3dep.tif.tnm0.zip", "KTCM_usgs3dep.tif.lercblobs/7.blob")]
    kept = [_aged(insets / name, old) for name in (
        "KGRF_usgs3dep.tif", "KGRF_usgs3dep.json", "index.json",
        "complete.json", "KGRF_usgs3dep.tif.aux.xml",
        "KGRF_usgs3dep.tif.lock", "KGRF_usgs3dep.json.invalid-2026-09-18")]
    kept.append(_aged(insets / "KTCM_usgs3dep.tif.refetch", 60.0))
    old_folder = _aged(tmp_path / "scratch" / "old.1.aa" / "K.tif", old)
    new_folder = _aged(tmp_path / "scratch" / "new.2.bb" / "K.tif", 60.0)
    removed = fetch_scratch.sweep_stale(str(insets))
    assert len(removed) == 5
    assert not any(path.exists() for path in stale)
    assert not (insets / "KTCM_usgs3dep.tif.lercblobs").exists()
    assert all(path.exists() for path in kept)
    assert not old_folder.parent.exists() and new_folder.exists()


def test_sweep_never_touches_a_cache_an_armed_guard_refuses(
        tmp_path, monkeypatch):
    repo = _corpus(tmp_path, monkeypatch)
    monkeypatch.setenv(fetch_scratch.SCRATCH_ENV, str(tmp_path / "scratch"))
    litter = _aged(Path(_inset_dir()) / "KGRF_usgs3dep.tif.refetch",
                   2 * fetch_scratch.STALE_SCRATCH_S)
    guard = _guard(repo, tmp_path / "lane")
    with guard:
        INSETS._sweep_stale_fetch_scratch(39, -107)
    assert litter.exists() and guard.blocked == []
    INSETS._sweep_stale_fetch_scratch(39, -107)          # the app: no guard
    assert not litter.exists()


def test_land_copies_across_volumes_and_never_leaves_a_half_raster(
        tmp_path, monkeypatch):
    source = tmp_path / "scratch" / "K.tif"
    source.parent.mkdir()
    source.write_bytes(b"raster")
    destination = tmp_path / "cache" / "K.tif"
    real_replace = os.replace
    refused = []

    def _replace(src, dst):
        if not refused:
            refused.append(src)
            raise OSError(errno.EXDEV, "cross-device link")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _replace)
    fetch_scratch.land(str(source), str(destination))
    assert destination.read_bytes() == b"raster"
    assert os.listdir(destination.parent) == ["K.tif"]
