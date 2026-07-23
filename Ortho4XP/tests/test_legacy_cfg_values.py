"""Foreign-fork config values normalize at read time (registry-driven
legacy_values), so rebuilding a foreign-built tile keeps its meaning."""

import sys

sys.path.insert(0, "src")


def test_progressive_cover_reads_as_true(tmp_path):
    import O4_Config_Utils as CFG

    cfg = tmp_path / "Ortho4XP_+46+006.cfg"
    cfg.write_text(
        "default_website='Arc'\n"
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
