"""Headless tests for the Qt UI's mac-app parity round.

What the macOS application does and the Qt window now does too: airport
marks on the map, other-installed-scenery awareness with its layer
filter, a map-preview imagery source independent of the BUILD source,
auto-install of finished tiles, the legacy per-tile-config offer, and the
cleanup of the unused imagery a source change leaves behind.

Offscreen (``QT_QPA_PLATFORM=offscreen``), no network, no engine: the
window is driven through its own handlers, the seam the other Qt tests
use.  The prefs and scan-cache stores are monkeypatched BEFORE the window
is constructed — it loads them in ``__init__`` and writes them on close,
so an unisolated window clobbers the user's real files.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Airport_Index as APT  # noqa: E402
import O4_Custom_Scenery as PACKS  # noqa: E402
import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Map as QTMAP  # noqa: E402
import O4_Tile_Info as TINFO  # noqa: E402
from o4_engine import events as EV  # noqa: E402


TILE = (48, -6)


def _tile_info(lat, lon, build_dir, provider="BI", zl=16):
    return TINFO.TileInfo(
        lat=lat, lon=lon, build_dir=build_dir,
        dir_name=os.path.basename(build_dir), dsf_present=True,
        provider=provider, zl=zl)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w") as handle:
        # An EXISTING prefs file: an absent one arms the onboarding
        # wizard, whose modal exec would sit there forever headless.
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    import O4_UI_Utils as UI
    saved_stdout = sys.stdout
    windows = []

    def _make():
        win = GUI.MainWindow()
        monkeypatch.setattr(win, "refresh_tiles", lambda: None)
        monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
        windows.append(win)
        return win

    _make.prefs_path = prefs_path
    try:
        yield _make
    finally:
        for win in windows:
            win._building = False
            win.close()
            win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def _prefs(make_window):
    with open(make_window.prefs_path) as handle:
        return json.load(handle)


# ===========================================================================
# Map preview source, decoupled from the build source
# ===========================================================================
def test_the_build_source_no_longer_repaints_the_basemap(make_window):
    """Choosing what the next build downloads is not choosing what you
    are looking at (mac-app parity: MapMainView's mapPreviewProvider)."""
    window = make_window()
    seen = []
    window.map.set_provider = lambda code: seen.append(code)
    window.imagery_combo.addItems(["TEST_A", "TEST_B"])
    window.imagery_combo.setCurrentText("TEST_B")
    assert seen == []


def test_the_map_picker_repaints_and_persists(make_window):
    window = make_window()
    seen = []
    window.map.set_provider = lambda code: seen.append(code)
    window.map_provider_combo.addItems(["TEST_MAP"])
    window.map_provider_combo.setCurrentText("TEST_MAP")
    assert seen == ["TEST_MAP"]
    assert _prefs(make_window)[GUI.MAP_PROVIDER_KEY] == "TEST_MAP"


def test_the_map_picker_offers_only_sources_the_map_can_draw(monkeypatch):
    monkeypatch.setattr(GUI, "gui_provider_codes", lambda: ["OSM", "EUR"])
    monkeypatch.setattr(
        QTMAP, "provider_is_mappable", lambda code: code == "OSM")
    assert GUI.map_preview_codes() == ["OSM"]


# ===========================================================================
# Scenery layer filter
# ===========================================================================
def test_scenery_filter_reaches_the_map_and_persists(make_window):
    window = make_window()
    assert window.map.scenery_filter() == QTMAP.SCENERY_FILTER_ALL
    window._set_scenery_filter(QTMAP.SCENERY_FILTER_OTHERS)
    assert window.map.scenery_filter() == QTMAP.SCENERY_FILTER_OTHERS
    assert _prefs(make_window)[GUI.SCENERY_FILTER_KEY] == "others"
    # The menu ticks follow the map, and a nonsense value falls back.
    assert window._scenery_filter_actions["others"].isChecked()
    window._set_scenery_filter("nonsense")
    assert window.map.scenery_filter() == QTMAP.SCENERY_FILTER_ALL
    assert window._scenery_filter_actions["all"].isChecked()


# ===========================================================================
# Airport marks
# ===========================================================================
def test_a_custom_pack_replaces_the_gray_mark_it_duplicates(make_window):
    """A gray disc under a magenta one is only noise (mac-app parity:
    MapOverlays.withDefaultAirports)."""
    window = make_window()
    window._airports = [
        APT.AirportEntry("EGLL", "Heathrow", "", "", 51.47, -0.46),
        APT.AirportEntry("LFPG", "De Gaulle", "", "", 49.01, 2.55),
    ]
    window._scenery_packs = [
        PACKS.SceneryPack(
            name="Aerosoft EGLL", path="/p", content_root="/p",
            status="enabled", kind="airport",
            airports=(PACKS.PackAirport("EGLL", "Heathrow", 51.47, -0.46),)),
    ]
    window._push_airport_marks()
    assert [row[0] for row in window.map._default_airports] == ["LFPG"]
    assert window.map._custom_airports == [("EGLL", 51.47, -0.46, False)]


def test_a_disabled_pack_dims_its_marks(make_window):
    window = make_window()
    window._scenery_packs = [
        PACKS.SceneryPack(
            name="Off", path="/p", content_root="/p", status="disabled",
            kind="airport",
            airports=(PACKS.PackAirport("EGKK", "Gatwick", 51.1, -0.19),)),
    ]
    window._push_airport_marks()
    assert window.map._custom_airports == [("EGKK", 51.1, -0.19, True)]


# ===========================================================================
# Other installed scenery
# ===========================================================================
def _pack(name, kind, tiles, root="/packs/x"):
    return PACKS.SceneryPack(name=name, path=root, content_root=root,
                             status="enabled", kind=kind,
                             tiles=frozenset(tiles))


def test_only_ortho_and_mesh_packs_become_coverage_outlines(make_window):
    window = make_window()
    window._on_packs_ready((window._scenery_generation, [
        _pack("SpainUHD", "ortho", [(40, -4)]),
        _pack("SomeMesh", "mesh", [(45, 5)]),
        _pack("Aerosoft EGLL", "airport", [(51, -1)]),
        _pack("Landmarks", "landmark", [(40, -74)]),
    ]))
    assert sorted(row[0] for row in window.map._regions) == [
        "SomeMesh", "SpainUHD"
    ]


def test_a_stale_survey_is_discarded(make_window):
    window = make_window()
    window._scenery_generation = 7
    window._on_packs_ready((6, [_pack("SpainUHD", "ortho", [(40, -4)])]))
    assert window._scenery_packs == []
    window._on_packs_ready((7, [_pack("SpainUHD", "ortho", [(40, -4)])]))
    assert [pack.name for pack in window._scenery_packs] == ["SpainUHD"]


def test_other_scenery_rows_appear_only_where_a_pack_covers(make_window):
    window = make_window()
    window._scenery_packs = [_pack("SpainUHD", "ortho", [(40, -4)])]
    window._refresh_other_scenery((40, -4))
    assert window._info_layout.isRowVisible(window.other_scenery_row)
    assert window._other_scenery_rows.count() == 1
    window._refresh_other_scenery((41, -4))
    assert not window._info_layout.isRowVisible(window.other_scenery_row)
    assert window._other_scenery_rows.count() == 0


# ===========================================================================
# Auto-install of finished tiles
# ===========================================================================
def test_auto_install_links_a_finished_tile_and_persists(
        make_window, monkeypatch, tmp_path):
    window = make_window()
    import O4_Config_Utils as CFG
    import O4_Scenery_Links as LINKS

    monkeypatch.setattr(CFG, "custom_scenery_dir", str(tmp_path / "cs"))
    installed = []
    monkeypatch.setattr(
        LINKS, "install",
        lambda lat, lon, build, scenery: installed.append((lat, lon)))
    window._built = {TILE: _tile_info(*TILE, build_dir=str(tmp_path / "t"))}
    # Default ON, as in the mac app; a round trip proves it persists.
    assert window.chk_auto_install.isChecked() is True
    window.chk_auto_install.setChecked(False)
    window.chk_auto_install.setChecked(True)
    assert _prefs(make_window)[GUI.AUTO_INSTALL_KEY] is True

    window._on_build_done(EV.BuildDone(lat=TILE[0], lon=TILE[1], ok=True))
    assert installed == [TILE]
    assert TILE in window._installed


def test_auto_install_skips_failures_and_stays_off_when_unchecked(
        make_window, monkeypatch, tmp_path):
    window = make_window()
    import O4_Config_Utils as CFG
    import O4_Scenery_Links as LINKS

    monkeypatch.setattr(CFG, "custom_scenery_dir", str(tmp_path / "cs"))
    installed = []
    monkeypatch.setattr(
        LINKS, "install",
        lambda lat, lon, build, scenery: installed.append((lat, lon)))
    window._built = {TILE: _tile_info(*TILE, build_dir=str(tmp_path / "t"))}

    window.chk_auto_install.setChecked(True)
    window._on_build_done(
        EV.BuildDone(lat=TILE[0], lon=TILE[1], ok=False, error="boom"))
    assert installed == []

    window.chk_auto_install.setChecked(False)
    window._on_build_done(EV.BuildDone(lat=TILE[0], lon=TILE[1], ok=True))
    assert installed == []
    assert _prefs(make_window)[GUI.AUTO_INSTALL_KEY] is False


def test_auto_install_failure_is_reported_not_raised(
        make_window, monkeypatch, tmp_path, capsys):
    """A batch of twenty tiles must not produce twenty modal errors."""
    window = make_window()
    import O4_Config_Utils as CFG
    import O4_Scenery_Links as LINKS

    monkeypatch.setattr(CFG, "custom_scenery_dir", str(tmp_path / "cs"))

    def _boom(*_args):
        raise OSError("no permission")

    monkeypatch.setattr(LINKS, "install", _boom)
    window._built = {TILE: _tile_info(*TILE, build_dir=str(tmp_path / "t"))}
    window.chk_auto_install.setChecked(True)
    window._on_build_done(EV.BuildDone(lat=TILE[0], lon=TILE[1], ok=True))
    assert TILE not in window._installed


# ===========================================================================
# Legacy per-tile config offer
# ===========================================================================
def test_legacy_offer_shows_for_a_built_tile_only(make_window, tmp_path):
    window = make_window()
    build = tmp_path / "zOrtho4XP_+48-006"
    build.mkdir()
    (build / "Ortho4XP.cfg").write_text("default_zl=17\n")
    # Unbuilt: nothing to say, even with a legacy file on disk.
    window._built = {}
    window._refresh_legacy_config(TILE)
    assert window.legacy_config_btn.isHidden() is True

    window._built = {TILE: _tile_info(*TILE, build_dir=str(build))}
    window._legacy_prompted.add(TILE)   # suppress the modal auto-prompt
    window._refresh_legacy_config(TILE)
    assert window._legacy_tile_settings["uses_legacy_name"] is True


def test_legacy_message_names_every_marker(make_window):
    window = make_window()
    text = window._legacy_config_message({
        "lat": 48, "lon": -6,
        "uses_legacy_name": True,
        "foreign_enums": [("texture_mode", "weird", "full_ortho")],
        "quoted_keys": ["default_website"],
        "missing_pins": ["/gone/dem.tif"],
    })
    assert "+48-006" in text
    assert "texture_mode = weird" in text and "full_ortho" in text
    assert "dem.tif" in text
    assert "1 setting" in text
    assert "Ortho4XP.cfg" in text


# ===========================================================================
# Foreign-imagery cleanup offer
# ===========================================================================
def test_selection_offer_appears_only_for_a_conflicted_multi_selection(
        make_window):
    window = make_window()
    window._conflict_tiles = {TILE}
    window._refresh_selection_conflict_offer([TILE])
    assert window.selection_conflict_btn.isHidden() is True  # one tile
    window._refresh_selection_conflict_offer([TILE, (49, -6)])
    assert window.selection_conflict_btn.isHidden() is False
    assert "1 selected tile mix" in window.selection_conflict_btn.text()
    window._conflict_tiles = set()
    window._refresh_selection_conflict_offer([TILE, (49, -6)])
    assert window.selection_conflict_btn.isHidden() is True


def test_the_warning_button_follows_the_active_tiles_badge(make_window):
    window = make_window()
    window._built = {TILE: _tile_info(*TILE, build_dir="/w/zOrtho4XP_+48-006")}
    window._conflict_tiles = {TILE}
    window._refresh_conflict_indicator(TILE)
    assert window.imagery_conflict_btn.isHidden() is False
    window._conflict_tiles = set()
    window._refresh_conflict_indicator(TILE)
    assert window.imagery_conflict_btn.isHidden() is True


def test_provider_label_names_one_source_or_says_multiple():
    assert GUI._provider_label({"BI"}) == "BI"
    assert GUI._provider_label({"BI", "Arc"}) == "Multiple"
    assert GUI._provider_label(set()) == "—"
