"""#1229 / owner RULINGS 2026-10-26c: this app's own config names and the
one-time hand-over (``O4_Config_Names``).

An Ortho4XP config is never moved or modified; a stamped ``Ortho4XP_`` file
(one this app wrote under the old name) takes the new name; the oldest
``.pre352.bak`` that 2026-09-18c made goes back to its own name, once, and
never over a file.
"""

import os
import pathlib

import O4_Config_Names as CN
import O4_Settings_Model as SM

STAMP = SM.tile_cfg_stamp_line()


def _tile_dir(tmp_path):
    build = tmp_path / "zOrtho4XP_+30+031"
    build.mkdir()
    return build


def test_the_names():
    assert CN.tile_cfg_name(30, 31) == "XPTerrainBuilder_+30+031.cfg"
    assert CN.ortho4xp_tile_cfg_name(-5, -120) == "Ortho4XP_-05-120.cfg"
    assert CN.GLOBAL_CFG_NAME == "XPTerrainBuilder.cfg"
    assert SM.PRE_STAMP_BACKUP_SUFFIX == CN.PRE_STAMP_BACKUP_SUFFIX


def test_an_unstamped_ortho4xp_cfg_is_never_touched(tmp_path):
    build = _tile_dir(tmp_path)
    theirs = build / "Ortho4XP_+30+031.cfg"
    theirs.write_bytes(b"default_website=BI\r\nmesh_zl=19\r\n")
    stat = theirs.stat()

    assert CN.adopt_tile_cfg(str(build), 30, 31) == []

    assert theirs.read_bytes() == b"default_website=BI\r\nmesh_zl=19\r\n"
    assert theirs.stat().st_mtime_ns == stat.st_mtime_ns
    assert sorted(os.listdir(build)) == ["Ortho4XP_+30+031.cfg"]


def test_a_stamped_ortho4xp_cfg_takes_this_apps_name(tmp_path):
    build = _tile_dir(tmp_path)
    theirs = build / "Ortho4XP_+30+031.cfg"
    theirs.write_text(STAMP + "mesh_zl=19\n", encoding="utf-8", newline="")

    infos = CN.adopt_tile_cfg(str(build), 30, 31)

    assert len(infos) == 1 and "XPTerrainBuilder_+30+031.cfg" in infos[0]
    assert not theirs.exists()
    assert (build / "XPTerrainBuilder_+30+031.cfg").read_text(
        encoding="utf-8") == STAMP + "mesh_zl=19\n"


def test_a_stamped_cfg_never_replaces_an_existing_own_cfg(tmp_path):
    build = _tile_dir(tmp_path)
    (build / "Ortho4XP_+30+031.cfg").write_text(STAMP + "mesh_zl=19\n",
                                                encoding="utf-8", newline="")
    ours = build / "XPTerrainBuilder_+30+031.cfg"
    ours.write_text(STAMP + "mesh_zl=17\n", encoding="utf-8", newline="")

    assert CN.adopt_tile_cfg(str(build), 30, 31) == []

    assert ours.read_text(encoding="utf-8") == STAMP + "mesh_zl=17\n"
    assert (build / "Ortho4XP_+30+031.cfg").is_file()


def test_the_oldest_backup_is_restored_once(tmp_path):
    build = _tile_dir(tmp_path)
    oldest = build / "Ortho4XP_+30+031.cfg.pre352.bak"
    later = build / "Ortho4XP_+30+031.cfg.pre352.bak.2"
    oldest.write_text("default_website=BI\n", encoding="utf-8", newline="")
    later.write_text("default_website=GO2\n", encoding="utf-8", newline="")
    theirs = build / "Ortho4XP_+30+031.cfg"

    infos = CN.adopt_tile_cfg(str(build), 30, 31)

    assert len(infos) == 1 and "restored" in infos[0]
    assert theirs.read_text(encoding="utf-8") == "default_website=BI\n"
    assert not oldest.exists()
    assert later.read_text(encoding="utf-8") == "default_website=GO2\n"

    # ONCE: the user removes the restored file; .bak.2 is never promoted.
    theirs.unlink()
    assert CN.adopt_tile_cfg(str(build), 30, 31) == []
    assert not theirs.exists()
    assert later.is_file()


def test_a_restore_never_overwrites(tmp_path):
    build = _tile_dir(tmp_path)
    backup = build / "Ortho4XP_+30+031.cfg.pre352.bak"
    backup.write_text("default_website=BI\n", encoding="utf-8", newline="")
    theirs = build / "Ortho4XP_+30+031.cfg"
    theirs.write_text("default_website=Arc\n", encoding="utf-8", newline="")

    assert CN.adopt_tile_cfg(str(build), 30, 31) == []

    assert theirs.read_text(encoding="utf-8") == "default_website=Arc\n"
    assert backup.read_text(encoding="utf-8") == "default_website=BI\n"


def test_ours_moves_first_then_the_backup_comes_back(tmp_path):
    """The usual beta tile: this app's stamped cfg under the old name AND
    the user's Ortho4XP cfg in the backup 09-18c made."""
    build = _tile_dir(tmp_path)
    (build / "Ortho4XP_+30+031.cfg").write_text(STAMP + "mesh_zl=19\n",
                                                encoding="utf-8", newline="")
    (build / "Ortho4XP_+30+031.cfg.pre352.bak").write_text(
        "default_website=BI\n", encoding="utf-8", newline="")

    assert len(CN.adopt_tile_cfg(str(build), 30, 31)) == 2

    assert sorted(os.listdir(build)) == ["Ortho4XP_+30+031.cfg",
                                         "XPTerrainBuilder_+30+031.cfg"]
    assert (build / "Ortho4XP_+30+031.cfg").read_text(
        encoding="utf-8") == "default_website=BI\n"


def test_a_missing_build_dir_is_not_an_error(tmp_path):
    assert CN.adopt_tile_cfg(str(tmp_path / "nope"), 30, 31) == []


def test_the_global_of_this_apps_data_folder_is_copied(tmp_path):
    theirs = tmp_path / "Ortho4XP.cfg"
    theirs.write_bytes(b"mesh_zl=19\n")
    stat = theirs.stat()

    assert CN.adopt_global_cfg(str(tmp_path))

    assert (tmp_path / "XPTerrainBuilder.cfg").read_bytes() == b"mesh_zl=19\n"
    assert theirs.read_bytes() == b"mesh_zl=19\n"
    assert theirs.stat().st_mtime_ns == stat.st_mtime_ns
    # once: an existing own global is never replaced
    theirs.write_bytes(b"mesh_zl=17\n")
    assert CN.adopt_global_cfg(str(tmp_path)) == []
    assert (tmp_path / "XPTerrainBuilder.cfg").read_bytes() == b"mesh_zl=19\n"


def test_an_ortho4xp_installations_global_is_ignored(tmp_path):
    """The data folder IS an Ortho4XP folder (its launcher beside it):
    owner Q97, "Ignore" -- the app starts from its defaults."""
    (tmp_path / "Ortho4XP_v130.py").write_text("", encoding="utf-8", newline="")
    (tmp_path / "Ortho4XP.cfg").write_text("mesh_zl=19\n", encoding="utf-8", newline="")

    assert CN.is_ortho4xp_install(str(tmp_path))
    assert CN.adopt_global_cfg(str(tmp_path)) == []
    assert not (tmp_path / "XPTerrainBuilder.cfg").exists()


def test_this_engines_checkout_is_not_an_ortho4xp_install():
    engine = pathlib.Path(CN.__file__).resolve().parents[1]
    assert (engine / "Ortho4XP.py").is_file()
    assert not CN.is_ortho4xp_install(str(engine))


def test_the_global_write_never_touches_ortho4xps(tmp_path, monkeypatch):
    """A Settings write goes to XPTerrainBuilder.cfg; Ortho4XP.cfg stays
    byte-identical (and grows no .bak)."""
    import O4_File_Names as FNAMES

    (tmp_path / "Ortho4XP_v130.py").write_text("", encoding="utf-8", newline="")
    theirs = tmp_path / "Ortho4XP.cfg"
    theirs.write_bytes(b"mesh_zl=19\n")
    monkeypatch.setattr(FNAMES, "data_path",
                        lambda rel: os.path.join(str(tmp_path), rel))

    SM.write_global({"mesh_zl": "17"})

    assert theirs.read_bytes() == b"mesh_zl=19\n"
    assert not (tmp_path / "Ortho4XP.cfg.bak").exists()
    assert SM.read_global_raw()["mesh_zl"] == "17"
    assert SM._default_global_cfg() == str(tmp_path / "XPTerrainBuilder.cfg")
