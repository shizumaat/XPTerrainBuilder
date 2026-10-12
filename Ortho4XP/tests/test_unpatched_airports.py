"""A failed airport no longer aborts its tile (owner RULINGS 2026-10-12a, #564).

Synthetic twins over a STUB airport builder that fails for one of several
airports.  What each holds:

1. the tile continues: ``include_airports`` returns, the other airports'
   patches are in the mesh inputs, the failed one's is not;
2. H1's protection stays: the failed airport's STALE patch on disk — and
   every file beside it a later stage reads by name — is set aside, so the
   real patch ingest, the road-pin readers and the object stage's
   admission test find nothing of it;
3. the unpatched list is published (tile state, the sidecar, the engine
   log) with each airport's stage and cause;
4. STRICT mode (the harness, the release checks) still fails step 1;
5. a whole-tile refusal and an un-movable stale file still end the tile;
6. every airport failing still builds the tile, ungraded, with warnings;
7. a later successful build of the airport needs no manual cleanup.
"""
from __future__ import annotations

import json
import os
import types

import pytest

from auto_patch import driver as DRIVER
import O4_Airport_Utils as APT
import O4_File_Names as FNAMES
import O4_UI_Utils as UI
import O4_Unpatched_Airports as UNPATCHED
import O4_Vector_Map as VMAP
import O4_Vector_Utils as VECT

_EMPTY_OSM = "<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n</osm>\n"
AIRPORTS = ("KAAA", "KBBB", "KCCC")


def _patch(patch_dir, icao):
    return os.path.join(str(patch_dir), icao + "_auto.patch.osm")


def _write_family(patch_dir, icao, marker):
    """Everything a completed build leaves beside one airport's patch."""
    for path in UNPATCHED.airport_patch_family(str(patch_dir), icao):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            if path.endswith(".patch.osm"):
                handle.write(_EMPTY_OSM.replace(
                    "</osm>", "<!-- %s -->\n</osm>" % marker))
            elif path.endswith(".axes.json"):
                # one record a road-pin reader would take (lat, lon, level)
                json.dump({"road_join_yield": [[30.5, 31.5, 10.0, 9.0]]},
                          handle)
            else:
                handle.write(json.dumps({"marker": marker}))


def _task(patch_dir, icao):
    return {"icao": icao, "tile_lat": 30, "tile_lon": 31,
            "auto_patch_file": _patch(patch_dir, icao),
            "verify_log_path": os.path.join(str(patch_dir), icao + ".part")}


def _builder(failing, error="geometry exception"):
    """The stub airport builder: writes the patch pair, or fails."""
    def build(task):
        if task["icao"] in failing:
            return {"icao": task["icao"], "ok": False, "stage": "build",
                    "error": error}
        _write_family(os.path.dirname(task["auto_patch_file"]),
                      task["icao"], "this build")
        return {"icao": task["icao"], "ok": True, "summary": "1 shape",
                "build_s": 1.0, "verify_s": 0.0, "verify_err": None,
                "verify_log_path": task["verify_log_path"],
                "object_pad_records": [], "provenance_log": None}
    return build


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A tile whose auto-patch pass is the REAL driver results loop over
    the stub builder, and whose patch ingest is the REAL ``include_patches``."""
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    build_dir = tmp_path / "tile"
    from auto_patch import config as CFG
    monkeypatch.setattr(CFG, "PARALLEL_AIRPORTS", False, raising=False)
    monkeypatch.setattr(DRIVER, "_WORKER_DEM",
                        getattr(DRIVER, "_WORKER_DEM", None), raising=False)
    monkeypatch.delenv(UNPATCHED.STRICT_ENV, raising=False)
    monkeypatch.setattr(FNAMES, "patch_dir", lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(VMAP, "load_airports_and_prepare_dem",
                        lambda tile: (object(), {}))
    seen = types.SimpleNamespace(
        patch_dir=patch_dir, events=[], warnings=[], ordinary=None,
        tile=types.SimpleNamespace(lat=30, lon=31, auto_patch="All",
                                   dem=None, build_dir=str(build_dir)))
    monkeypatch.setattr(UI, "auto_patch_failed",
                        lambda *record: seen.events.append(record))
    monkeypatch.setattr(UI, "loud_warning",
                        lambda *words: seen.warnings.append(
                            " ".join(str(w) for w in words)))

    def generate(tile, airport_layer, dico_airports):
        DRIVER._run_build_tasks(
            [_task(patch_dir, icao) for icao in AIRPORTS], tile, [],
            str(patch_dir / "auto_patch_verify_debug.log"))

    monkeypatch.setattr(VMAP, "run_auto_patch_generation", generate)

    def ordinary_handling(tile, layer, airports, vector_map, patches_list,
                          patches_area=None):
        seen.ordinary = sorted(patches_list)     # who is NOT handled here
        from shapely import geometry
        return geometry.Polygon()

    monkeypatch.setattr(APT, "encode_runways_taxiways_and_aprons",
                        ordinary_handling)
    monkeypatch.setattr(APT, "encode_hangars", lambda *a, **k: None)
    monkeypatch.setattr(APT, "flatten_helipads", lambda *a, **k: None)
    monkeypatch.setattr(APT, "build_airport_array", lambda *a, **k: 0)
    return seen


def _fail(monkeypatch, *icaos, **kwargs):
    monkeypatch.setattr(DRIVER, "_build_write_verify_one",
                        _builder(set(icaos), **kwargs))


# ── 1 + 2 + 3: one of three fails ───────────────────────────────────────


def test_one_failed_airport_does_not_stop_the_tile(world, monkeypatch):
    _write_family(world.patch_dir, "KBBB", "the previous build")
    _fail(monkeypatch, "KBBB")

    VMAP.include_airports(VECT.Vector_Map(), world.tile)

    # the mesh inputs: the real ingest loaded the two patches this build
    # wrote, and the failed airport is left to the ordinary handling
    assert world.ordinary == ["KAAA", "KAAA_auto", "KCCC", "KCCC_auto"]
    assert world.tile.auto_patch_unpatched == [
        {"icao": "KBBB", "stage": "build", "error": "geometry exception"}]
    assert world.events == [("KBBB", "build", "geometry exception")]


def test_the_stale_patch_is_out_of_every_readers_sight(world, monkeypatch):
    _write_family(world.patch_dir, "KBBB", "the previous build")
    _fail(monkeypatch, "KBBB")

    VMAP.include_airports(VECT.Vector_Map(), world.tile)

    family = UNPATCHED.airport_patch_family(str(world.patch_dir), "KBBB")
    assert len(family) == 6
    for path in family:
        assert not os.path.exists(path), path
        assert os.path.isfile(path + UNPATCHED.STALE_SUFFIX), path
    # not deleted: the last good patch is still there to be looked at
    with open(family[0] + UNPATCHED.STALE_SUFFIX, encoding="utf-8") as handle:
        assert "the previous build" in handle.read()
    # the consumers that select by name, each through its own code:
    names = os.listdir(str(world.patch_dir))
    assert sorted(n for n in names if n[-10:] == ".patch.osm") == [
        "KAAA_auto.patch.osm", "KCCC_auto.patch.osm"]        # ingest, mesh
    assert len(VMAP.road_join_yield_pins(world.tile)) == 2   # road pins
    assert "no KBBB_auto.patch.osm" in VMAP.auto_patch_not_applied(
        world.tile, "KBBB")                                  # object stage
    assert VMAP.auto_patch_not_applied(world.tile, "KAAA") is None
    import glob
    plans = glob.glob(os.path.join(str(world.patch_dir), "o4_v2_rebake_*.json"))
    assert not [p for p in plans if "KBBB" in p]             # plan glob


def test_the_unpatched_list_reaches_the_log_and_the_sidecar(world, monkeypatch):
    _fail(monkeypatch, "KBBB")

    VMAP.include_airports(VECT.Vector_Map(), world.tile)

    assert "KBBB" in world.warnings[0] and "WITHOUT" in world.warnings[0]
    assert "geometry exception" in world.warnings[1]
    # another process (the app's last step) reads it from the tile's dir
    later = types.SimpleNamespace(build_dir=world.tile.build_dir)
    assert UNPATCHED.read(later) == world.tile.auto_patch_unpatched
    assert [r["icao"] for r in UNPATCHED.read(later)] == ["KBBB"]


def test_a_clean_build_restates_an_empty_list(world, monkeypatch):
    _fail(monkeypatch, "KBBB")
    VMAP.include_airports(VECT.Vector_Map(), world.tile)
    _fail(monkeypatch)                                # the next build is clean

    VMAP.include_airports(VECT.Vector_Map(), world.tile)

    assert world.tile.auto_patch_unpatched == []
    assert UNPATCHED.read(
        types.SimpleNamespace(build_dir=world.tile.build_dir)) == []
    # (7) the airport built again with no manual cleanup: its patch is in
    assert world.ordinary == ["KAAA", "KAAA_auto", "KBBB", "KBBB_auto",
                              "KCCC", "KCCC_auto"]
    assert VMAP.auto_patch_not_applied(world.tile, "KBBB") is None


# ── 6: every airport fails ──────────────────────────────────────────────


def test_all_airports_failing_still_builds_the_tile(world, monkeypatch):
    for icao in AIRPORTS:
        _write_family(world.patch_dir, icao, "the previous build")
    _fail(monkeypatch, *AIRPORTS)

    VMAP.include_airports(VECT.Vector_Map(), world.tile)

    assert world.ordinary == []                       # nothing is patched
    assert [r["icao"] for r in world.tile.auto_patch_unpatched] == list(AIRPORTS)
    assert len(world.warnings) == 1 + len(AIRPORTS)
    assert not [n for n in os.listdir(str(world.patch_dir))
                if n[-10:] == ".patch.osm"]


# ── 4: strict mode ──────────────────────────────────────────────────────


def test_strict_mode_still_fails_the_tile(world, monkeypatch):
    _write_family(world.patch_dir, "KBBB", "the previous build")
    _fail(monkeypatch, "KBBB")
    monkeypatch.setenv(UNPATCHED.STRICT_ENV, "1")

    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        VMAP.include_airports(VECT.Vector_Map(), world.tile)

    assert [f["icao"] for f in raised.value.failures] == ["KBBB"]
    assert world.warnings == []
    # the stale patch is set aside in strict mode too: H1 does not depend
    # on which way the tile goes
    assert not os.path.exists(_patch(world.patch_dir, "KBBB"))


def _step_one(monkeypatch, tile, include_airports):
    """``build_poly_file`` as far as its airport stage."""
    import O4_Bathymetry_Band as BATHYBAND
    monkeypatch.setattr(UI, "is_working", 0)
    monkeypatch.setattr(UI, "red_flag", 0)
    monkeypatch.setattr(VMAP, "_refuse_on_broken_proj", lambda: False)
    monkeypatch.setattr(BATHYBAND, "prefetch_bathymetry_band", lambda t: None)
    monkeypatch.setattr(FNAMES, "osm_dir", lambda lat, lon: tile.build_dir)
    monkeypatch.setattr(FNAMES, "input_node_file", lambda t: "")
    monkeypatch.setattr(FNAMES, "input_poly_file", lambda t: "")
    monkeypatch.setattr(VMAP, "include_airports", include_airports)
    return VMAP.build_poly_file(tile)


def test_step_one_returns_failure_in_strict_mode(world, monkeypatch):
    """The predicate every harness entry reads: ``build_poly_file`` == 0."""
    _fail(monkeypatch, "KBBB")
    monkeypatch.setenv(UNPATCHED.STRICT_ENV, "1")
    real = VMAP.include_airports

    assert _step_one(monkeypatch, world.tile, real) == 0


def test_step_one_goes_past_the_airports_when_not_strict(world, monkeypatch):
    _fail(monkeypatch, "KBBB")
    real = VMAP.include_airports

    class _PastTheAirports(Exception):
        pass

    def include_then_stop(vector_map, tile):
        real(vector_map, tile)
        raise _PastTheAirports()         # the rest of step 1 is not this twin's

    with pytest.raises(_PastTheAirports):
        _step_one(monkeypatch, world.tile, include_then_stop)
    assert [r["icao"] for r in world.tile.auto_patch_unpatched] == ["KBBB"]


def test_the_harness_environment_is_strict():
    """The harness sets strict mode where it sets the pack stand-down; the
    release check sets it in the frozen engine's environment."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(root, "tools", "harness", "build_airport.py"),
                 os.path.join(os.path.dirname(root), "scripts",
                              "check_frozen_tile.py")):
        with open(path, encoding="utf-8") as handle:
            assert '["%s"] = "1"' % UNPATCHED.STRICT_ENV in handle.read(), path


def test_the_family_names_are_their_writers_own():
    """The set-aside spells the names itself (it must work when the v2
    package cannot be imported); each is held against its writer."""
    from auto_patch import engine_v2
    from auto_patch_v2.airport import object_plan, rebake_screen
    from auto_patch_v2.model.rebake import PLAN_FILENAME

    patch = os.path.basename(_patch("", "{icao}"))
    assert UNPATCHED.PATCH_FAMILY == (
        patch, patch + ".axes.json", engine_v2.GRADED_SURFACE_FILENAME,
        PLAN_FILENAME, rebake_screen.SCREEN_FILENAME,
        object_plan.REFUSED_FILENAME)
    # and none of them, set aside, matches a reader's pattern
    for name in UNPATCHED.PATCH_FAMILY:
        stale = name.format(icao="KBBB") + UNPATCHED.STALE_SUFFIX
        assert stale[-10:] != ".patch.osm"
        assert not stale.endswith(".patch.osm.axes.json")
        assert not engine_v2._PLAN_NAME_RE.match(stale)
        assert not object_plan.SCREEN_NAME_RE.match(stale)
        assert not stale.endswith(".json")


# ── 5: what still ends the tile ─────────────────────────────────────────


def test_a_whole_tile_refusal_is_not_an_airport_failure(monkeypatch):
    monkeypatch.delenv(UNPATCHED.STRICT_ENV, raising=False)
    config = DRIVER.AutoPatchBuildFailure(
        [{"icao": "*", "stage": "config", "error": "no CIFP directory"}])
    airport = DRIVER.AutoPatchBuildFailure(
        [{"icao": "KBBB", "stage": "verify", "error": "a structural DEFECT"}])

    assert not UNPATCHED.may_continue(config)
    assert UNPATCHED.may_continue(airport)


def test_a_stale_file_that_cannot_be_moved_ends_the_tile(world, monkeypatch):
    _write_family(world.patch_dir, "KBBB", "the previous build")
    _fail(monkeypatch, "KBBB")
    real_replace = os.replace

    def locked(src, dst):
        if src.endswith("KBBB_auto.patch.osm"):
            raise PermissionError("file is in use")
        return real_replace(src, dst)

    monkeypatch.setattr(UNPATCHED.os, "replace", locked)

    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        VMAP.include_airports(VECT.Vector_Map(), world.tile)

    assert raised.value.stale_left == [_patch(world.patch_dir, "KBBB")]
    assert world.tile.auto_patch_unpatched == []
