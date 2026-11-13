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

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402

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
    with open(os.path.join(directory, "index.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump({ICAO: record}, handle)
    monkeypatch.setattr(
        INSETS, "cached_inset_paths_for_icao",
        lambda *a, **k: [os.path.join(directory,
                                      f"{ICAO}_COPERNICUSGLO30.tif")])
    problem = INSETS.airport_inset_frame_problem(LAT, LON, ICAO, BOX)
    assert problem is not None and problem[0] == "missing"
    assert "SPAIN5M" in problem[1] and "--refresh-data dem" in problem[1]


def _unanswered_world(build_mod, tmp_path, monkeypatch, *, answers):
    """Test (1)'s index (SPAIN5M ranked above the cached COPERNICUSGLO30
    and never answered), behind the REAL per-airport verdict, and a FAKE
    provider: the warm pass records SPAIN5M's answer only when
    ``answers``.  Returns the warm calls' ``refresh`` flags."""
    codes = [d["code"] for d in INSETS.select_provider_definitions("auto")]
    cached = codes.index("COPERNICUSGLO30")
    record = {code: INSETS.NO_COVERAGE for code in codes[:cached]}
    del record["SPAIN5M"]
    record["COPERNICUSGLO30"] = "ok"
    monkeypatch.setattr(FNAMES, "Elevation_dir",
                        str(tmp_path / "Elevation_data"))
    directory = FNAMES.airport_inset_directory(LAT, LON)
    os.makedirs(directory, exist_ok=True)
    index = os.path.join(directory, "index.json")
    with open(index, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({ICAO: record}, handle)
    monkeypatch.setattr(
        INSETS, "cached_inset_paths_for_icao",
        lambda *a, **k: [os.path.join(directory,
                                      f"{ICAO}_COPERNICUSGLO30.tif")])
    monkeypatch.setattr(build_mod.IPF, "inset_selection_admits",
                        lambda *a: True)
    monkeypatch.setattr(build_mod.IPF, "required_boxes",
                        lambda *a, **k: {ICAO: BOX})
    monkeypatch.setattr(build_mod, "apply_xplane_install_paths_for_preflight",
                        lambda: None)
    monkeypatch.setattr(build_mod, "_ladder_recheck_problem",
                        lambda *a: None)
    monkeypatch.setattr(build_mod, "dem_cache_state", lambda *a: _STATE)
    calls = []

    def fake_provider_pass(icaos, root, lat, lon, prog, *, refresh=True):
        calls.append(refresh)
        if answers:
            with open(index, encoding="utf-8") as handle:
                data = json.load(handle)
            data[ICAO]["SPAIN5M"] = INSETS.NO_COVERAGE
            with open(index, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle)

    monkeypatch.setattr(build_mod, "warm_airport_insets", fake_provider_pass)
    return calls


_STATE = {"airport_insets": True, "airports_layer": True,
          "tile_stem": "+40-004"}


def test_refresh_only_asks_the_unanswered_provider_above_the_cache(
        build_mod, tmp_path, monkeypatch):
    """LFMN 2026-11-10: ``--refresh-data dem --refresh-only`` printed
    "nothing to derive" over a MISSING verdict (FRANCE50CM above the
    cached raster, never answered) and the re-judge refused.  The named
    airport's pass now runs AS A BUILD (``refresh=False``) and clears it."""
    calls = _unanswered_world(build_mod, tmp_path, monkeypatch, answers=True)
    derived = build_mod._refresh_airport_inset(tmp_path, _STATE, LAT, LON,
                                               ICAO, _Notes())
    assert calls == [False]
    assert derived and derived[0].endswith("[missing]")
    assert build_mod.this_airports_inset_problem(_STATE, LAT, LON,
                                                 ICAO) is None


def test_a_provider_that_still_never_answers_refuses(
        build_mod, tmp_path, monkeypatch):
    _unanswered_world(build_mod, tmp_path, monkeypatch, answers=False)
    with pytest.raises(SystemExit, match="STILL MISSING"):
        build_mod._refresh_airport_inset(tmp_path, _STATE, LAT, LON, ICAO,
                                         _Notes())


def test_the_refreshable_verdicts_are_the_preflights_own(build_mod):
    assert build_mod.REFRESHABLE_INSET_PROBLEMS is build_mod.IPF.REFRESHABLE_KINDS
    assert "missing" in build_mod.REFRESHABLE_INSET_PROBLEMS


# (2) ---------------------------------------------------------------------
def _stamp_world(build_mod, tmp_path, monkeypatch, answers):
    import O4_Config_Utils as CFG
    layer = tmp_path / "airports.osm"
    layer.write_text("", encoding="utf-8", newline="\n")
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
        (tmp_path / f"{tag}.progress").write_text("REFUSING: test\n", encoding="utf-8", newline="\n")
        raise SystemExit("REFUSING: test")

    for _ in range(2):                    # the re-run no longer collides
        with pytest.raises(SystemExit, match="REFUSING: test"):
            build_mod.main_releasing_refused_tags([], run=refused)
    assert not (tmp_path / "T1930.progress").exists()
    assert (tmp_path / "T1930.refused.progress").read_text(encoding="utf-8").startswith(
        "REFUSING")
    assert (tmp_path / "T1930.refused_2.progress").exists()


def test_a_run_that_built_keeps_its_artifacts(build_mod, tmp_path):
    (tmp_path / "T2.progress").write_text("x", encoding="utf-8", newline="\n")
    (tmp_path / "T2.osm").write_text("x", encoding="utf-8", newline="\n")
    assert build_mod.release_refused_tag(tmp_path, "T2") is None
    assert (tmp_path / "T2.progress").exists()


def test_a_refused_run_past_its_env_snapshot_frees_its_tag(build_mod,
                                                            tmp_path):
    """eidw1980 (2026-11-10): ``.progress`` + ``.env.json`` blocked the
    re-run.  Both move under ONE refused stem."""
    for suffix in (".progress", ".env.json"):
        (tmp_path / f"T3{suffix}").write_text("x", encoding="utf-8",
                                              newline="\n")
    (tmp_path / "T3.refused.progress").write_text("older", encoding="utf-8",
                                                  newline="\n")
    moved = build_mod.release_refused_tag(tmp_path, "T3")
    assert moved == tmp_path / "T3.refused_2.progress"
    assert (tmp_path / "T3.refused_2.env.json").exists()
    assert build_mod.tag_artifacts_present(tmp_path, "T3") == []


def test_a_run_refused_by_the_write_guard_frees_its_tag(build_mod, tmp_path):
    """A shared-repo write refusal raised at its call site is a
    ``RuntimeError`` (``SharedRepoWriteBlocked``), never a SystemExit."""
    def refused(argv):
        tag = build_mod.claim_tag(tmp_path, "XXXX", "T4")
        build_mod._CLAIMED_TAGS.append((tmp_path, tag))
        (tmp_path / f"{tag}.env.json").write_text("{}", encoding="utf-8",
                                                  newline="\n")
        raise build_mod.SharedRepoWriteBlocked("BLOCKED: test")

    with pytest.raises(build_mod.SharedRepoWriteBlocked):
        build_mod.main_releasing_refused_tags([], run=refused)
    assert build_mod.tag_artifacts_present(tmp_path, "T4") == []
    assert (tmp_path / "T4.refused.env.json").exists()


# #2038 -------------------------------------------------------------------
def test_a_resting_unanswered_provider_is_no_side_effect_fetch(tmp_path,
                                                               monkeypatch):
    """#2038 (USGS 3DEP's TNM 504, KSFO 2026-11-12): a MISSING verdict
    whose never-answered providers all REST is not a fetch the build would
    make (the fetch loop skips a resting provider), so the pre-flight reads
    it ``resting`` -- the degraded frame ``--allow-degraded-dem`` accepts --
    and the same verdict with the provider awake stays ``missing``."""
    import elevation_access.refusal_rest as REST

    test_an_unasked_provider_above_the_cached_raster_is_named(tmp_path, monkeypatch)
    spec = importlib.util.spec_from_file_location(
        "harness_inset_preflight_2038", ROOT / "tools" / "harness" / "inset_preflight.py")
    ipf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ipf)
    problem = INSETS.airport_inset_frame_problem(LAT, LON, ICAO, BOX)
    monkeypatch.setattr(REST, "resting_refusal", lambda code, now=None: None)
    assert ipf.resting_verdict(INSETS, LAT, LON, ICAO, BOX, problem)[0] == "missing"
    monkeypatch.setattr(REST, "resting_refusal",
                        lambda code, now=None: {"at": 0} if code == "SPAIN5M" else None)
    kind, text = ipf.resting_verdict(INSETS, LAT, LON, ICAO, BOX, problem)
    assert kind == "resting" and "SPAIN5M" in text
    assert kind not in ipf.REFRESHABLE_KINDS
