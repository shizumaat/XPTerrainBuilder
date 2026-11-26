"""#2290: two tiles of one run share an airport (LOWS on +47+012 and
+47+013).  When +47+013 finishes first, its re-seat of the guests
+47+012's plan placed on it WAITS for +47+012's own build in the same run
(that tile's object stage places the airport over +47+013's new mesh) —
no "STALE MESH" placement, no not-fitted warning.  A neighbour the run is
not building, or one whose ground is already built, is re-seated as
before (#2129)."""
from __future__ import annotations

import json
import types

import pytest
from auto_patch_v2.airport import tile_route as TR

A, B_ = (47, 12), (47, 13)


@pytest.fixture
def two_tiles(tmp_path, monkeypatch):
    """+47+012's LOWS placement record has a guest on +47+013 seated on
    another ground than +47+013's new mesh; ``ran`` logs every re-run of
    +47+012's plan."""
    import O4_Config_Utils as CFG
    import O4_File_Names as FNAMES
    from auto_patch import guest_stage as GS
    from auto_patch import object_stage as OS
    from auto_patch import post_mesh as PM
    pack, patches, tiles = tmp_path / "pack", tmp_path / "Patches", tmp_path / "Tiles"
    monkeypatch.setattr(FNAMES, "Patch_dir", str(patches))
    origin = patches / "+40+010" / "+47+012"
    origin.mkdir(parents=True)
    (origin / "o4_v2_placement_LOWS.json").write_text(json.dumps(
        {"icao": "LOWS", "pack_root": str(pack)}), encoding="utf-8", newline="\n")
    monkeypatch.setattr(TR, "guest_mark", lambda root, there, key: (
        TR.DEM_MARK if (key, tuple(there)) == ("LOWS@+47+012", B_) else None))
    ran = []
    monkeypatch.setattr(OS, "_object_stage", lambda t, only=None, failed=None: (
        ran.append(((t.lat, t.lon), only)) or {"airports_failed": 0}))
    monkeypatch.setattr(CFG.Tile, "read_from_config", lambda self, *a, **k: None)
    fresh = {"value": False}
    monkeypatch.setattr(PM, "_mesh_is_newer_than_alt",
                        lambda tile, path: fresh["value"])
    monkeypatch.setattr(GS, "_MESH_PENDING", {})
    here_mesh = tiles / "zOrtho4XP_+47+013" / "Data+47+013.mesh"
    here_mesh.parent.mkdir(parents=True)
    here_mesh.write_bytes(b"new mesh")
    tile = types.SimpleNamespace(lat=B_[0], lon=B_[1],
                                 custom_build_dir=str(tiles) + "/")
    return types.SimpleNamespace(
        GS=GS, tile=tile, mesh=str(here_mesh), ran=ran, fresh=fresh,
        origin_mesh=tiles / "zOrtho4XP_+47+012" / "Data+47+012.mesh")


def test_the_reseat_waits_for_the_origin_still_building_in_the_run(two_tiles):
    """RED ON BASE: +47+013 re-ran +47+012's plan over +47+012's stale
    ground and raised "the buildings of LOWS were not fitted"."""
    t = two_tiles
    t.GS.note_mesh_pending(B_, [list(A)])
    failed = []
    assert t.GS.reseat_guests(t.tile, t.mesh, failed=failed) == {"guests_deferred": 1}
    assert t.ran == [] and failed == []
    # the origin's mesh on disk but older than its .alt: still not built
    t.origin_mesh.parent.mkdir(parents=True)
    t.origin_mesh.write_bytes(b"last build's mesh")
    assert t.GS.reseat_guests(t.tile, t.mesh, failed=failed) == {"guests_deferred": 1}
    assert t.ran == [] and failed == []


def test_an_origin_whose_ground_is_built_is_reseated_now(two_tiles):
    """The origin is still in the run but already wrote its mesh (its own
    object stage may have read this tile's OLD mesh): re-seat now."""
    t = two_tiles
    t.GS.note_mesh_pending(B_, [list(A)])
    t.origin_mesh.parent.mkdir(parents=True)
    t.origin_mesh.write_bytes(b"this run's mesh")
    t.fresh["value"] = True
    assert t.GS.reseat_guests(t.tile, t.mesh) == {"guests_reseated": 1,
                                                  "guests_reseat_failed": 0}
    assert t.ran == [(A, frozenset({"LOWS"}))]


def test_an_origin_the_run_is_not_building_is_reseated_as_before(two_tiles):
    """No pending neighbour (another tile's run, or none): #2129 unchanged —
    the origin's plan runs, and its own stage names a stale ground."""
    t = two_tiles
    t.GS.note_mesh_pending((10, 10), [list(A)])      # another tile's run
    assert t.GS.reseat_guests(t.tile, t.mesh) == {"guests_reseated": 1,
                                                  "guests_reseat_failed": 0}
    assert t.ran == [(A, frozenset({"LOWS"}))]


def _run(programs, at, queue):
    from o4_engine.parallel import ParallelBuildRun
    run = object.__new__(ParallelBuildRun)
    run._programs, run._next_step_index, run._queue = programs, at, list(queue)
    return run


def test_the_parallel_run_names_the_neighbours_still_owed_their_mesh():
    prog = ["vector", "mesh", "masks"]
    run = _run({A: prog, B_: prog, (48, 12): prog, (47, 11): prog,
                (46, 13): ["imagery"], (47, 15): prog},
               {B_: 2, A: 1, (48, 12): 2},          # A in its mesh step
               [(47, 11), (46, 13), (47, 15)])
    assert sorted(map(tuple, run._mesh_pending_locked(B_))) == [A]
    assert sorted(map(tuple, run._mesh_pending_locked(A))) == [(47, 11)]
