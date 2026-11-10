"""#1930: three harness refresh/refusal gaps found in the 1.0.476 verify.

(1) a provider ranked above a cached inset that never answered made the
    build rewrite the inset index mid-build -- the frame check now names it
    up front with its cure (``--refresh-data dem``);
(2) ``--refresh-data dem --refresh-only`` answered "nothing to derive"
    over a completion stamp that no longer settled the tile -- the refresh
    now re-runs the tile's inset pass, which rewrites the stamp;
(3) a refused run left ``<tag>.progress`` at an explicit tag, so the
    re-run collided -- the record is renamed and the stem freed.
Headless, no network.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import O4_Airport_Elevation_Insets as INSETS              # noqa: E402
import O4_File_Names as FNAMES                            # noqa: E402

LAT, LON, ICAO = 40, -4, "LEMD"
BOX = (-3.62, 40.43, -3.50, 40.56)


@pytest.fixture(scope="module")
def build_mod():
    spec = importlib.util.spec_from_file_location(
        "harness_refresh1930_build",
        ROOT / "tools" / "harness" / "build_airport.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Notes:
    def __init__(self):
        self.lines = []

    def note(self, msg):
        self.lines.append(msg)


# (1) ---------------------------------------------------------------------
def test_an_unasked_provider_above_the_cached_raster_is_named(
        tmp_path, monkeypatch):
    codes = [d["code"] for d in INSETS.select_provider_definitions("auto")]
    above, cached = codes.index("SPAIN5M"), codes.index("COPERNICUSGLO30")
    assert above < cached
    record = {code: INSETS.NO_COVERAGE for code in codes[:cached]}
    del record["SPAIN5M"]                 # a provider added since the fetch
    record["COPERNICUSGLO30"] = "ok"
    monkeypatch.setattr(FNAMES, "Elevation_dir",
                        str(tmp_path / "Elevation_data"))
    directory = FNAMES.airport_inset_directory(LAT, LON)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "index.json"), "w") as handle:
        json.dump({ICAO: record}, handle)
    monkeypatch.setattr(
        INSETS, "cached_inset_paths_for_icao",
        lambda *a, **k: [os.path.join(directory,
                                      f"{ICAO}_COPERNICUSGLO30.tif")])
    problem = INSETS.airport_inset_frame_problem(LAT, LON, ICAO, BOX)
    assert problem is not None and problem[0] == "missing"
    assert "SPAIN5M" in problem[1] and "--refresh-data dem" in problem[1]


# (2) ---------------------------------------------------------------------
def _stamp_world(build_mod, tmp_path, monkeypatch, answers):
    import O4_Config_Utils as CFG
    layer = tmp_path / "airports.osm"
    layer.write_text("")
    monkeypatch.setattr(FNAMES, "osm_cached", lambda *a: str(layer))
    monkeypatch.setattr(CFG.Tile, "read_from_config", lambda self: None)
    monkeypatch.setattr(INSETS, "is_cached", lambda tile: answers.pop(0))
    passes = []
    monkeypatch.setattr(INSETS, "ensure_insets_for_tile",
                        lambda tile, dico, refresh=False:
                        passes.append(refresh))
    monkeypatch.setattr(build_mod, "_tile_airports_dico",
                        lambda tile, lat, lon: {})
    return passes


def test_a_stale_stamp_is_resettled_by_the_tile_pass(
        build_mod, tmp_path, monkeypatch):
    passes = _stamp_world(build_mod, tmp_path, monkeypatch, [False, True])
    derived = build_mod._resettle_inset_stamp(LAT, LON, _Notes())
    assert passes == [False]              # as a build runs it
    assert derived and derived[0].endswith("complete.json")


def test_a_settled_stamp_derives_nothing(build_mod, tmp_path, monkeypatch):
    passes = _stamp_world(build_mod, tmp_path, monkeypatch, [True])
    assert build_mod._resettle_inset_stamp(LAT, LON, _Notes()) == []
    assert passes == []


def test_a_stamp_still_stale_after_the_pass_refuses(
        build_mod, tmp_path, monkeypatch):
    _stamp_world(build_mod, tmp_path, monkeypatch, [False, False])
    with pytest.raises(SystemExit, match="STILL does not settle"):
        build_mod._resettle_inset_stamp(LAT, LON, _Notes())


# (3) ---------------------------------------------------------------------
def test_a_refused_run_frees_its_explicit_tag(build_mod, tmp_path):
    def refused(argv):
        tag = build_mod.claim_tag(tmp_path, "XXXX", "T1930")
        build_mod._CLAIMED_TAGS.append((tmp_path, tag))
        (tmp_path / f"{tag}.progress").write_text("REFUSING: test\n")
        raise SystemExit("REFUSING: test")

    for _ in range(2):                    # the re-run no longer collides
        with pytest.raises(SystemExit, match="REFUSING: test"):
            build_mod.main_releasing_refused_tags([], run=refused)
    assert not (tmp_path / "T1930.progress").exists()
    assert (tmp_path / "T1930.refused.progress").read_text().startswith(
        "REFUSING")
    assert (tmp_path / "T1930.refused_2.progress").exists()


def test_a_run_that_built_keeps_its_artifacts(build_mod, tmp_path):
    (tmp_path / "T2.progress").write_text("x")
    (tmp_path / "T2.osm").write_text("x")
    assert build_mod.release_refused_tag(tmp_path, "T2") is None
    assert (tmp_path / "T2.progress").exists()
