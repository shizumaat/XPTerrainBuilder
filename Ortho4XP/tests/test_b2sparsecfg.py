"""BETA2 GEN-1 / owner ruling RULINGS 2026-09-18a — tile cfgs are sparse.

P1 here: the user's ``modify_custom_airports`` switch is a STAND-DOWN of
the whole placement stage (one line, immediate return), while the lane /
env arms (``O4_PACK_WRITES=measure_only``, ``DSF_OBJECT_REANCHOR`` off)
still build and report the measurement.
"""

import os

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


# ---------------------------------------------------------------------------
# P2 -- Tile.write_to_config is SPARSE (RULINGS 2026-09-18a (1))
# ---------------------------------------------------------------------------
import O4_Cfg_Vars  # noqa: E402
import O4_Config_Utils as CFG  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402


@pytest.fixture()
def sparse_tile(tmp_path, monkeypatch):
    """A Tile whose global cfg and build dir both live under tmp_path."""
    global_cfg = tmp_path / "Ortho4XP.cfg"
    global_cfg.write_text("modify_custom_airports=False\n"
                          "color_harmonization=False\n")
    monkeypatch.setattr(CFG, "global_cfg_file", str(global_cfg))
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(global_cfg))
    tile = CFG.Tile(30, 31, str(tmp_path / "Tiles") + "/")
    tile.build_dir = str(tmp_path / "Tiles" / "zOrtho4XP_+30+031")
    os.makedirs(tile.build_dir, exist_ok=True)
    return tile, global_cfg


def _cfg_keys(path):
    return {line.split("=", 1)[0]
            for line in open(path).read().splitlines() if line.strip()}


def test_write_to_config_writes_only_the_differences(sparse_tile):
    tile, _global_cfg = sparse_tile
    tile.modify_custom_airports = False   # equals the global -> no override
    tile.color_harmonization = True       # differs -> an override

    assert tile.write_to_config() == 1

    keys = _cfg_keys(tile._tile_cfg_path())
    assert "modify_custom_airports" not in keys
    assert "color_harmonization" in keys
    # provenance always survives
    assert {"zone_list", "default_website", "default_zl"} <= keys
    # and the dump is a handful of keys, not the whole registry
    assert len(keys) < len(O4_Cfg_Vars.list_tile_vars)


def test_global_beats_a_built_tile_on_the_next_read(sparse_tile):
    """GEN-1 itself: build a tile with the switch ON, turn the GLOBAL off,
    re-read -> the tile must resolve False."""
    tile, global_cfg = sparse_tile
    global_cfg.write_text("modify_custom_airports=True\n")
    tile.modify_custom_airports = True
    assert tile.write_to_config() == 1
    assert "modify_custom_airports" not in _cfg_keys(tile._tile_cfg_path())

    global_cfg.write_text("modify_custom_airports=False\n")
    fresh = CFG.Tile(tile.lat, tile.lon, tile.custom_build_dir)
    fresh.build_dir = tile.build_dir
    fresh.modify_custom_airports = True   # the stale in-memory seed
    assert fresh.read_from_config() == 1

    assert fresh.modify_custom_airports is False


def test_deliberate_override_survives_a_rewrite(sparse_tile):
    """The sparse rule must not eat a REAL override."""
    tile, global_cfg = sparse_tile
    global_cfg.write_text("modify_custom_airports=False\n")
    tile.modify_custom_airports = True
    tile.write_to_config()

    fresh = CFG.Tile(tile.lat, tile.lon, tile.custom_build_dir)
    fresh.build_dir = tile.build_dir
    fresh.read_from_config()
    assert fresh.modify_custom_airports is True


def test_both_writers_share_one_rule(sparse_tile):
    """``write_tile`` and ``write_to_config`` are the same diffing rule."""
    assert SM.write_tile.__module__ == SM.sparse_tile_values.__module__
    out = SM.sparse_tile_values(
        {"modify_custom_airports": True, "color_harmonization": False},
        always_keep=(), global_cfg={"modify_custom_airports": "True",
                                    "color_harmonization": "True"})
    assert out == {"color_harmonization": "False"}


def test_sparse_tile_values_refuses_a_foreign_key():
    with pytest.raises(ValueError):
        SM.sparse_tile_values({"not_a_tile_var": 1})
