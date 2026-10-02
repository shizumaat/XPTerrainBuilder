"""BETA2 GEN-1 / owner ruling RULINGS 2026-09-18a — tile cfgs are sparse.

P1 here: the user's ``modify_custom_airports`` switch is a STAND-DOWN of
the whole placement stage (one line, immediate return), while the lane /
env arms (``O4_PACK_WRITES=measure_only``, ``DSF_OBJECT_REANCHOR`` off)
still build and report the measurement.
"""

import os
import pathlib

import pytest

import O4_File_Names as FNAMES
import O4_UI_Utils as UI
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
    plan.write_text("{not json at all", encoding="utf-8", newline="")
    mesh = tmp_path / "mesh.mes"
    mesh.write_text("", encoding="utf-8", newline="")
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
# ISSUE #42 -- THE STAND-DOWN IS SILENT, AND IT COMES FIRST
#
# The 09-18a arm sat BELOW the plan glob and the two mesh tests, so with
# the box unchecked a build still printed ``[v2 rebake] STALE MESH ...``
# (verbosity 0, so always), ``[v2 rebake] mesh not found ...``, or the
# wrapper's ``[v2 rebake] failed: ...`` -- the owner's report on build 350.
# ---------------------------------------------------------------------------


def _rebake_lines(capsys):
    """Every ``[v2 rebake]`` / ``[v2 placement]`` line the stage printed."""
    out = capsys.readouterr().out
    return [ln for ln in out.splitlines()
            if "[v2 rebake]" in ln or "[v2 placement]" in ln]


def test_switch_off_prints_no_rebake_line(rebake_stage, capsys):
    """Issue #42: at the default verbosity the console carries NO
    ``[v2 rebake]`` line when the box is unchecked."""
    tile, _plan = rebake_stage
    tile.modify_custom_airports = False
    assert UI.verbosity == 1                      # the app's own default

    counts = engine_v2.rebake_after_mesh(tile)

    assert _rebake_lines(capsys) == []
    assert counts == {"airports": 0, "airports_failed": 0, "packs_written": 0}


def test_switch_off_names_the_switch_at_v2(rebake_stage, capsys, monkeypatch):
    """...and ``-v2`` still says WHICH switch stood the stage down."""
    tile, _plan = rebake_stage
    tile.modify_custom_airports = False
    monkeypatch.setattr(UI, "verbosity", engine_v2._STAND_DOWN_VERBOSITY)

    engine_v2.rebake_after_mesh(tile)

    lines = _rebake_lines(capsys)
    assert len(lines) == 1 and "modify_custom_airports is off" in lines[0]


@pytest.mark.parametrize("break_", ["stale_mesh", "no_mesh", "no_worklist"])
def test_switch_off_outranks_every_other_rebake_print(rebake_stage, capsys,
                                                      monkeypatch, break_):
    """The gate is the FIRST statement of the stage: none of the three
    pre-09-18a leaks can print once the box is unchecked."""
    tile, _plan = rebake_stage
    tile.modify_custom_airports = False
    if break_ == "stale_mesh":
        monkeypatch.setattr(post_mesh, "_mesh_is_newer_than_alt",
                            lambda _t, _m: False)
    elif break_ == "no_mesh":
        monkeypatch.setattr(FNAMES, "mesh_file",
                            lambda _b, _lat, _lon: "/nonexistent/mesh.mes")
    else:
        def _boom(_t):
            raise RuntimeError("no worklist path")
        monkeypatch.setattr(post_mesh, "object_anchor_worklist_path", _boom)

    counts = engine_v2.rebake_after_mesh(tile)

    assert _rebake_lines(capsys) == []
    assert counts == {"airports": 0, "airports_failed": 0, "packs_written": 0}


@pytest.mark.parametrize("break_", ["stale_mesh", "no_mesh"])
def test_switch_on_still_reports_a_mesh_problem(rebake_stage, capsys,
                                                monkeypatch, break_):
    """The control: with the box CHECKED the mesh diagnostics are the
    whole point of the stage and still print."""
    tile, _plan = rebake_stage
    if break_ == "stale_mesh":
        monkeypatch.setattr(post_mesh, "_mesh_is_newer_than_alt",
                            lambda _t, _m: False)
    else:
        monkeypatch.setattr(FNAMES, "mesh_file",
                            lambda _b, _lat, _lon: "/nonexistent/mesh.mes")

    engine_v2.rebake_after_mesh(tile)

    assert len(_rebake_lines(capsys)) == 1


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
                          "color_harmonization=False\n", encoding="utf-8", newline="")
    monkeypatch.setattr(CFG, "global_cfg_file", str(global_cfg))
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(global_cfg))
    tile = CFG.Tile(30, 31, str(tmp_path / "Tiles") + "/")
    tile.build_dir = str(tmp_path / "Tiles" / "zOrtho4XP_+30+031")
    os.makedirs(tile.build_dir, exist_ok=True)
    return tile, global_cfg


def _cfg_keys(path):
    return {line.split("=", 1)[0]
            for line in open(path, encoding="utf-8").read().splitlines() if line.strip()}


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
    global_cfg.write_text("modify_custom_airports=True\n", encoding="utf-8", newline="")
    tile.modify_custom_airports = True
    assert tile.write_to_config() == 1
    assert "modify_custom_airports" not in _cfg_keys(tile._tile_cfg_path())

    global_cfg.write_text("modify_custom_airports=False\n", encoding="utf-8", newline="")
    fresh = CFG.Tile(tile.lat, tile.lon, tile.custom_build_dir)
    fresh.build_dir = tile.build_dir
    fresh.modify_custom_airports = True   # the stale in-memory seed
    assert fresh.read_from_config() == 1

    assert fresh.modify_custom_airports is False


def test_deliberate_override_survives_a_rewrite(sparse_tile):
    """The sparse rule must not eat a REAL override."""
    tile, global_cfg = sparse_tile
    global_cfg.write_text("modify_custom_airports=False\n", encoding="utf-8", newline="")
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


# ---------------------------------------------------------------------------
# P3 -- a PRE-1.0.352 tile cfg is MOVED to a backup (RULINGS 2026-09-18c (2))
#
# Owner, verbatim: "let's just move any config file created before 1.0.352,
# to a backup so everything going forward starts with no config and global
# defaults, any changes then write a new config file."  This RETIRED the
# 2026-09-18a key-by-key migration (the 80%-full-dump heuristic, Q 18b-1).
# ---------------------------------------------------------------------------
def _legacy_full_dump(path, global_cfg_values):
    """A pre-1.0.352 tile cfg: EVERY tile var, frozen, and NO stamp."""
    lines = []
    for var in O4_Cfg_Vars.list_tile_vars:
        value = global_cfg_values.get(
            var, str(O4_Cfg_Vars.cfg_vars[var]["default"]))
        lines.append(var + "=" + value)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def test_the_heuristic_is_GONE():
    """The retired mechanism is deleted, not kept gated."""
    assert not hasattr(SM, "migrate_tile_cfg")
    assert not hasattr(SM, "FULL_DUMP_FRACTION")


def test_an_unstamped_cfg_is_moved_and_the_global_resolves(sparse_tile):
    """The owner's 23 tiles: modify_custom_airports=True frozen in, global
    says False.  The whole file goes; the tile inherits."""
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    _legacy_full_dump(path, {"modify_custom_airports": "True",
                             "default_website": "BI", "default_zl": "17"})
    before = path.read_text(encoding="utf-8")

    infos = SM.retire_unstamped_tile_cfg(str(path))

    assert infos and "before 1.0.352" in infos[0]
    assert not path.exists()
    backup = pathlib.Path(str(path) + SM.PRE_STAMP_BACKUP_SUFFIX)
    assert backup.read_text(encoding="utf-8") == before          # losslessly beside the tile

    fresh = CFG.Tile(tile.lat, tile.lon, tile.custom_build_dir)
    fresh.build_dir = tile.build_dir
    fresh.read_from_config()
    assert fresh.modify_custom_airports is False   # the global wins now


def test_the_ZONES_go_to_the_backup_too(sparse_tile):
    """LOUD: the owner said ANY config file, so zone_list and the imagery
    provenance leave with it -- they are not special-cased back."""
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    path.write_text("zone_list=[[[30,31,30,31],'ZL17','BI']]\n"
                    "default_website=BI\ndefault_zl=17\n", encoding="utf-8", newline="")

    assert SM.retire_unstamped_tile_cfg(str(path))

    assert not path.exists()
    backup = pathlib.Path(str(path) + SM.PRE_STAMP_BACKUP_SUFFIX)
    assert "zone_list" in backup.read_text(encoding="utf-8")


def test_a_stamped_sparse_cfg_is_untouched_BYTE_FOR_BYTE(sparse_tile):
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    path.write_text(SM.tile_cfg_stamp_line()
                    + "color_harmonization=False\nmesh_zl=19\n", encoding="utf-8", newline="")
    before = path.read_text(encoding="utf-8")

    assert SM.retire_unstamped_tile_cfg(str(path)) == []

    assert path.read_text(encoding="utf-8") == before
    assert not pathlib.Path(str(path) + SM.PRE_STAMP_BACKUP_SUFFIX).exists()


def test_an_existing_backup_is_never_overwritten(sparse_tile):
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    first = pathlib.Path(str(path) + SM.PRE_STAMP_BACKUP_SUFFIX)
    first.write_text("an older backup\n", encoding="utf-8", newline="")
    path.write_text("mesh_zl=19\n", encoding="utf-8", newline="")

    assert SM.retire_unstamped_tile_cfg(str(path))

    assert first.read_text(encoding="utf-8") == "an older backup\n"
    assert pathlib.Path(
        str(path) + SM.PRE_STAMP_BACKUP_SUFFIX + ".2").read_text(encoding="utf-8") == \
        "mesh_zl=19\n"


def test_a_vanished_file_is_not_an_error(sparse_tile):
    """Parallel tile workers touch one cfg at the same moment."""
    tile, _global_cfg = sparse_tile
    assert SM.retire_unstamped_tile_cfg(tile._tile_cfg_path()) == []


def test_both_writers_stamp_what_they_write(sparse_tile):
    tile, _global_cfg = sparse_tile
    tile.color_harmonization = True
    assert tile.write_to_config() == 1
    assert SM.is_stamped(SM._parse_cfg(tile._tile_cfg_path()))

    SM.write_tile(30, 31, tile.custom_build_dir, {"mesh_zl": 19})
    assert SM.is_stamped(SM._parse_cfg(tile._tile_cfg_path()))


def test_a_change_after_the_move_writes_a_NEW_stamped_sparse_cfg(sparse_tile):
    """The ruling's last clause: 'any changes then write a new config
    file'.  A legacy cfg + one setting change = a two-line new file."""
    tile, global_cfg = sparse_tile
    global_cfg.write_text("modify_custom_airports=False\nmesh_zl=19\n", encoding="utf-8", newline="")
    path = pathlib.Path(tile._tile_cfg_path())
    _legacy_full_dump(path, {"modify_custom_airports": "True"})

    SM.write_tile(30, 31, tile.custom_build_dir,
                  {"modify_custom_airports": True})

    keys = _cfg_keys(str(path))
    assert keys == {SM.CFG_STAMP_KEY, "modify_custom_airports"}
    assert SM._parse_cfg(str(path))["modify_custom_airports"] == "True"
    assert pathlib.Path(
        str(path) + SM.PRE_STAMP_BACKUP_SUFFIX).is_file()


def test_the_stamp_is_not_read_as_a_setting(sparse_tile, capsys):
    """It must not warn as an unknown key, and must not become an attr."""
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    path.write_text(SM.tile_cfg_stamp_line() + "mesh_zl=19\n", encoding="utf-8", newline="")

    fresh = CFG.Tile(tile.lat, tile.lon, tile.custom_build_dir)
    fresh.build_dir = tile.build_dir
    assert fresh.read_from_config() == 1

    assert fresh.mesh_zl == 19
    assert not hasattr(fresh, SM.CFG_STAMP_KEY)
    assert SM.CFG_STAMP_KEY in path.read_text(encoding="utf-8")      # still stamped
    assert "WARNING" not in capsys.readouterr().out


def test_the_stamp_survives_the_retired_key_cleanup(sparse_tile):
    """A stamped cfg that also carries a retired key is rewritten by the
    cleanup -- and comes out still stamped, not re-legacied."""
    import O4_Cfg_Vars as CV
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    path.write_text(SM.tile_cfg_stamp_line()
                    + "auto_patch_engine=v1\nmesh_zl=19\n", encoding="utf-8", newline="")

    fresh = CFG.Tile(tile.lat, tile.lon, tile.custom_build_dir)
    fresh.build_dir = tile.build_dir
    assert fresh.read_from_config() == 1

    after = path.read_text(encoding="utf-8")
    assert "auto_patch_engine" not in after
    assert CV.cfg_stamp_key in after
    assert SM.retire_unstamped_tile_cfg(str(path)) == []


def test_read_tile_raw_moves_it_and_hides_the_stamp(sparse_tile):
    """The settings window / map overlay is a first touch like any other."""
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    path.write_text("mesh_zl=19\n", encoding="utf-8", newline="")

    assert SM.read_tile_raw(30, 31, tile.custom_build_dir) is None
    assert pathlib.Path(str(path) + SM.PRE_STAMP_BACKUP_SUFFIX).is_file()

    path.write_text(SM.tile_cfg_stamp_line() + "mesh_zl=19\n", encoding="utf-8", newline="")
    raw = SM.read_tile_raw(30, 31, tile.custom_build_dir)
    assert raw == {"mesh_zl": "19"}


def test_the_tile_info_scan_moves_it_too(sparse_tile):
    """O4_Tile_Info: consumer 8 of the P2 census (commit 8a40b115)."""
    import O4_Tile_Info as TI
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    path.write_text("default_website=BI\ndefault_zl=17\n", encoding="utf-8", newline="")

    info = TI._build_tile_info(tile.build_dir, 30, 31, "zOrtho4XP_+30+031")

    assert info is None or info.provider == ""      # nothing inherited from it
    assert not path.exists()
    assert pathlib.Path(str(path) + SM.PRE_STAMP_BACKUP_SUFFIX).is_file()


def test_the_move_runs_on_the_build_read_path(sparse_tile):
    tile, _global_cfg = sparse_tile
    path = pathlib.Path(tile._tile_cfg_path())
    _legacy_full_dump(path, {"modify_custom_airports": "True"})

    fresh = CFG.Tile(tile.lat, tile.lon, tile.custom_build_dir)
    fresh.build_dir = tile.build_dir
    assert fresh.read_from_config() == 1

    assert not path.exists()
    assert fresh.modify_custom_airports is False


# ---------------------------------------------------------------------------
# P4 -- write-through on a settings change / reset (RULINGS 2026-09-18a (2))
# ---------------------------------------------------------------------------
def test_engine_command_sets_then_removes_the_override(tmp_path, monkeypatch):
    """The owner's sentence, both halves: changing a setting SETS the key
    on the selected tiles, resetting it to the global REMOVES it."""
    from o4_engine.session import EngineSession
    from o4_engine import jsonl

    global_cfg = tmp_path / "Ortho4XP.cfg"
    global_cfg.write_text("modify_custom_airports=False\n", encoding="utf-8", newline="")
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(global_cfg))
    working = str(tmp_path / "Tiles") + "/"

    session = EngineSession.__new__(EngineSession)   # no build machinery
    out = session.tile_settings_write(
        [[30, 31]], {"modify_custom_airports": "True"}, working)
    assert out == {"written": [[30, 31]]}
    path = SM._tile_cfg_path(30, 31, working)
    assert SM._parse_cfg(path)["modify_custom_airports"] == "True"

    # reset to the global value -> the key is REMOVED, not set to False
    session.tile_settings_write(
        [[30, 31]], {"modify_custom_airports": "False"}, working)
    assert "modify_custom_airports" not in SM._parse_cfg(path)

    assert "tile_settings_write" in jsonl._build_handlers(session)


def test_the_command_is_announced_in_the_handshake():
    import inspect
    from o4_engine import jsonl
    source = inspect.getsource(jsonl.serve)
    assert "tile_settings_write" in source
