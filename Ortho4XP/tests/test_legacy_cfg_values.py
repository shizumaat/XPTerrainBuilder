"""Foreign-fork config values normalize at read time (registry-driven
legacy_values), so rebuilding a foreign-built tile keeps its meaning."""

import sys

sys.path.insert(0, "src")


def test_progressive_cover_reads_as_true(tmp_path):
    import O4_Config_Utils as CFG

    import O4_Settings_Model as SM

    cfg = tmp_path / "Ortho4XP_+46+006.cfg"
    # STAMPED (owner RULINGS 2026-09-18c (2)): an unstamped tile cfg is a
    # pre-1.0.352 file, MOVED aside on first touch rather than read.
    cfg.write_text(
        SM.tile_cfg_stamp_line()
        + "default_website='Arc'\n"
        "default_zl=16\n"
        "cover_airports_with_highres=Progressive\n"
        "cover_zl=17\n"
        "unknown_future_setting=whatever\n"   # unknown keys skip silently
    )
    tile = CFG.Tile(46, 6, str(tmp_path))
    assert tile.read_from_config(config_file=str(cfg)) == 1
    assert tile.cover_airports_with_highres == "True"
    # Legacy quotes are stripped by config_compatibility on the build path.
    assert tile.default_website == "Arc"
    assert tile.default_zl == 16


# ── Layered tile config (2026-09-04) ─────────────────────────────────────
# A tile cfg is a SPARSE OVERRIDE (O4_Settings_Model.write_tile): a key it
# does not carry is INHERITED from the global config, never left at
# whatever the Tile instance happened to hold.  The 2026-09-04 08:53 app
# build read −13-077 / −13-078 (July cfgs carrying no line for a setting
# added after they were written) on a different auto-patch engine from
# the +60-136 beside them in the same run, because the reader opened
# EITHER the tile file OR the global one.  (Both keys the twins once used
# are retired — ``auto_patch_engine`` 2026-09-13au, ``solve_model``
# 2026-09-13bh — so they now pin the same reader on ``texture_mode``.)  One
# reader serves the CLI, the JSONL session and its worker children; these
# twins pin it.

import os


def _layered_tile(tmp_path, monkeypatch, *, global_lines, tile_lines,
                  session=None):
    """A Tile whose global cfg is *global_lines* (None = no file) and
    whose own cfg is *tile_lines* (None = no file); *session* patches the
    in-memory module global, as ``O4_Settings_Model.apply_runtime`` does
    for a front end's live setting."""
    import O4_Config_Utils as CFG

    global_cfg = tmp_path / "Ortho4XP.cfg"
    if global_lines is not None:
        global_cfg.write_text(global_lines)
    monkeypatch.setattr(CFG, "global_cfg_file", str(global_cfg))
    if session is not None:
        for key, value in session.items():
            monkeypatch.setattr(CFG, key, value)
    # Trailing separator: the per-tile-subdirectory mode every front end
    # passes (build_dir = <tmp>/zOrtho4XP_+46+006).
    tile = CFG.Tile(46, 6, str(tmp_path) + os.sep)
    if tile_lines is not None:
        os.makedirs(tile.build_dir, exist_ok=True)
        import O4_Settings_Model as SM
        with open(tile._tile_cfg_path(), "w") as handle:
            # STAMPED through the one helper (RULINGS 2026-09-18c (2)).
            handle.write(SM.tile_cfg_stamp_line() + tile_lines)
    return tile


def test_tile_cfg_missing_key_inherits_global(tmp_path, monkeypatch):
    tile = _layered_tile(
        tmp_path, monkeypatch,
        global_lines="texture_mode=airport_ortho\ncover_zl=17\n",
        tile_lines="default_website=Arc\ndefault_zl=16\ncover_zl=18\n",
    )
    assert tile.read_from_config() == 1
    # Absent from the tile file -> the global's value, not the default.
    assert tile.texture_mode == "airport_ortho"
    # Present in the tile file -> the tile's value.
    assert tile.cover_zl == 18
    assert tile.default_website == "Arc"


def test_tile_cfg_key_wins_over_global(tmp_path, monkeypatch):
    tile = _layered_tile(
        tmp_path, monkeypatch,
        global_lines="texture_mode=airport_ortho\n",
        tile_lines="texture_mode=default_xplane\n",
    )
    assert tile.read_from_config() == 1
    assert tile.texture_mode == "default_xplane"


def test_no_tile_cfg_reads_global(tmp_path, monkeypatch):
    tile = _layered_tile(
        tmp_path, monkeypatch,
        global_lines="texture_mode=airport_ortho\n", tile_lines=None,
    )
    assert tile.read_from_config() == 1
    assert tile.texture_mode == "airport_ortho"


def test_session_setting_survives_sparse_files(tmp_path, monkeypatch):
    # Neither file carries the key: the value a front end applied in
    # memory (apply_runtime -> module global, seeded into the instance)
    # is what the tile resolves — never the registry default.
    tile = _layered_tile(
        tmp_path, monkeypatch,
        global_lines="cover_zl=17\n", tile_lines="default_zl=16\n",
        session={"texture_mode": "airport_ortho"},
    )
    assert tile.read_from_config() == 1
    assert tile.texture_mode == "airport_ortho"
    assert tile.cover_zl == 17


def test_use_global_reads_only_the_global(tmp_path, monkeypatch):
    tile = _layered_tile(
        tmp_path, monkeypatch,
        global_lines="texture_mode=airport_ortho\n",
        tile_lines="texture_mode=default_xplane\n",
    )
    assert tile.read_from_config(use_global=True) == 1
    assert tile.texture_mode == "airport_ortho"


def test_explicit_config_file_is_layered_over_global(tmp_path, monkeypatch):
    tile = _layered_tile(
        tmp_path, monkeypatch,
        global_lines="texture_mode=airport_ortho\n", tile_lines=None,
    )
    explicit = tmp_path / "elsewhere.cfg"
    explicit.write_text("cover_zl=18\n")
    assert tile.read_from_config(config_file=str(explicit)) == 1
    assert tile.texture_mode == "airport_ortho"
    assert tile.cover_zl == 18


def test_no_config_at_all_returns_zero(tmp_path, monkeypatch):
    tile = _layered_tile(
        tmp_path, monkeypatch, global_lines=None, tile_lines=None,
    )
    assert tile.read_from_config() == 0


def test_retired_key_in_tile_cfg_still_skipped(tmp_path, monkeypatch):
    tile = _layered_tile(
        tmp_path, monkeypatch,
        global_lines="texture_mode=airport_ortho\n",
        tile_lines="airport_elevation_inset_resolution_m=5\n"
                   "flat_site_declared_corridors=\n"
                   "solve_model=constructive\n",
    )
    assert tile.read_from_config() == 1
    assert tile.texture_mode == "airport_ortho"
    assert not hasattr(tile, "airport_elevation_inset_resolution_m")
    # RULINGS 2026-09-13bh: v1's solver switch, retired as
    # ``auto_patch_engine`` was — no attribute, and the line is DELETED
    # from the cfg on read (RULINGS 2026-09-13a (2)), never warned about.
    assert not hasattr(tile, "solve_model")
    assert "solve_model" not in open(tile._tile_cfg_path()).read()
