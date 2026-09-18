"""BETA2 GEN-1 / owner ruling RULINGS 2026-09-18a — tile cfgs are sparse.

P1 here: the user's ``modify_custom_airports`` switch is a STAND-DOWN of
the whole placement stage (one line, immediate return), while the lane /
env arms (``O4_PACK_WRITES=measure_only``, ``DSF_OBJECT_REANCHOR`` off)
still build and report the measurement.
"""

import pytest

import O4_File_Names as FNAMES
from auto_patch import engine_v2
from auto_patch import post_mesh


class _Tile:
    def __init__(self, build_dir, lat=30, lon=31):
        self.build_dir = build_dir
        self.lat = lat
        self.lon = lon
        self.modify_custom_airports = True


@pytest.fixture()
def rebake_stage(tmp_path, monkeypatch):
    """A tile whose patch dir holds ONE plan file that cannot be parsed.

    If the plan loop runs, the loop's own except arm books
    ``airports_failed`` -- so the counts tell us whether the stage ran at
    all, without needing a real pack.
    """
    patch_dir = tmp_path / "Patches" / "zOrtho4XP_+30+031"
    patch_dir.mkdir(parents=True)
    plan = patch_dir / "o4_v2_rebake_HECA.json"
    plan.write_text("{not json at all")
    mesh = tmp_path / "mesh.mes"
    mesh.write_text("")
    tile = _Tile(str(tmp_path))
    monkeypatch.setattr(post_mesh, "object_anchor_worklist_path",
                        lambda _t: str(patch_dir / "worklist.json"))
    monkeypatch.setattr(post_mesh, "_mesh_is_newer_than_alt",
                        lambda _t, _m: True)
    monkeypatch.setattr(FNAMES, "mesh_file",
                        lambda _b, _lat, _lon: str(mesh))
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    return tile, plan


def test_user_switch_off_skips_the_placement_stage(rebake_stage):
    tile, _plan = rebake_stage
    tile.modify_custom_airports = False

    counts = engine_v2.rebake_after_mesh(tile)

    assert counts == {"airports": 0, "airports_failed": 0, "packs_written": 0}


def test_lane_measure_only_arm_still_runs_the_stage(rebake_stage, monkeypatch):
    """``O4_PACK_WRITES=measure_only`` exists to keep the MEASUREMENT --
    it must not take the user switch's early return."""
    tile, _plan = rebake_stage
    monkeypatch.setenv("O4_PACK_WRITES", "measure_only")

    counts = engine_v2.rebake_after_mesh(tile)

    assert counts["airports_failed"] == 1  # the loop ran and read the plan


def test_switch_on_runs_the_stage(rebake_stage):
    tile, _plan = rebake_stage

    counts = engine_v2.rebake_after_mesh(tile)

    assert counts["airports_failed"] == 1
