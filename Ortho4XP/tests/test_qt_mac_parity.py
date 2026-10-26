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
import O4_Flight_Plan as FLIGHTPLAN  # noqa: E402
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
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
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
    with open(make_window.prefs_path, encoding="utf-8") as handle:
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
    """#1345: both menus read the engine's one list; the map picker greys
    out (never offers) a source the map cannot draw."""
    import O4_Qt_Imagery_Menu as QTIMENU

    rows = [
        {"code": "EUR", "name": "EUR", "region": "", "combined": True,
         "buildable": True, "previewable": False, "reason": "no layer"},
        {"code": "OSM", "name": "OSM", "region": "Global", "combined": False,
         "buildable": False, "previewable": True, "reason": ""},
    ]
    monkeypatch.setattr(GUI.SOURCES, "imagery_sources", lambda: rows)
    assert GUI.map_preview_codes() == ["OSM"]
    assert GUI.gui_provider_codes() == ["EUR"]
    entries = QTIMENU.menu_entries(rows, {}, for_map=True)
    assert [(e["code"], e["enabled"], e["tooltip"]) for e in entries] == [
        ("EUR", False, "no layer"), ("OSM", True, "")]


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
# Airport code list in the search field (#542; the Mac twin is
# Tests/SceneryKitTests/AirportCodeListTests.swift)
# ===========================================================================
def _batch_window(make_window, monkeypatch):
    alerts = []
    monkeypatch.setattr(GUI.QMessageBox, "warning",
                        lambda *args: alerts.append(args))
    window = make_window()
    window._airports = [
        APT.AirportEntry("KCLT", "Charlotte", "", "", 35.21, -80.94),
        APT.AirportEntry("OTHH", "Hamad", "", "", 25.27, 51.61),
        # Boundary straddles 48N/9E: four tiles.
        APT.AirportEntry("XEDG", "Edge", "", "", 47.95, 8.95,
                         extent=(47.9, 8.9, 48.02, 9.01)),
    ]
    statuses = []
    window._status = statuses.append
    window.alerts = alerts
    return window, statuses


def test_return_selects_every_tile_of_a_code_list(make_window, monkeypatch):
    window, statuses = _batch_window(make_window, monkeypatch)
    window.search_edit.setText("kclt, OTHH xedg")
    window._search_accept_first()
    assert window.map.selection() == {
        (35, -81), (25, 51), (47, 8), (47, 9), (48, 8), (48, 9)}
    assert window.search_edit.text() == ""
    assert statuses == ["Select 6 tiles for KCLT, OTHH, XEDG"]
    assert window.alerts == []   # every code resolved: no alert


def test_unknown_codes_alert_after_the_rest_are_selected(make_window,
                                                         monkeypatch):
    """Owner decision on #542: select all matching tiles and ALERT on the
    codes that could not be identified."""
    window, statuses = _batch_window(make_window, monkeypatch)
    window.search_edit.setText("KCLT; KZZZ, qqqq")
    window._search_accept_first()
    assert window.map.selection() == {(35, -81)}
    # The text stays so the unknown codes can be corrected.
    assert window.search_edit.text() == "KCLT; KZZZ, qqqq"
    assert statuses == [
        "Select 1 tile for KCLT — Unknown airport codes: KZZZ, QQQQ"]
    assert window.alerts == [(
        window, "Some airport codes were not found",
        "Not identified: KZZZ, QQQQ. The tiles of KCLT are selected.")]


def test_a_code_list_is_one_popup_choice(make_window, monkeypatch):
    window, _ = _batch_window(make_window, monkeypatch)
    window._update_search_popup("KCLT OTHH")
    assert window.search_popup.count() == 1
    kind, batch = window.search_popup.item(0).data(GUI.Qt.UserRole)
    assert kind == "batch" and batch.codes == ["KCLT", "OTHH"]


def test_a_single_code_searches_exactly_as_before(make_window, monkeypatch):
    window, statuses = _batch_window(make_window, monkeypatch)
    window._update_search_popup("KCLT")
    kind, tiles = window.search_popup.item(0).data(GUI.Qt.UserRole)
    assert (kind, tiles) == ("apt", [(35, -81)])
    window.search_edit.setText("KCLT")
    window._search_accept_first()
    assert window.map.selection() == {(35, -81)}
    assert statuses == []


def _row_labels(window, tiles):
    """The coordinate label of each tile's fresh progress row."""
    window._setup_progress_page(tiles)
    return [window._tile_rows[t][2].findChildren(GUI.QLabel)[0].text()
            for t in tiles]


def test_progress_rows_name_the_largest_airports_searched_first(
        make_window, monkeypatch):
    """#815 (after #667): every row names its tile's largest airports,
    however the tile was picked; a searched code not among them goes
    first; a tile with no airport shows only its coordinate."""
    window, _ = _batch_window(make_window, monkeypatch)
    window._airports = [
        APT.AirportEntry("KCLT", "Charlotte", "", "", 35.21, -80.94,
                         runway_m=3000, size_class=0),
        APT.AirportEntry("KJQF", "Concord", "", "", 35.39, -80.71,
                         runway_m=2300, size_class=1),
        APT.AirportEntry("KEQY", "Monroe", "", "", 35.02, -80.62,
                         runway_m=2100, size_class=1),
        APT.AirportEntry("KUZA", "Rock Hill", "", "", 35.05, -80.90,
                         runway_m=1700, size_class=2),
        APT.AirportEntry("NC00", "Strip", "", "", 35.50, -80.50,
                         runway_m=600, size_class=3),
        APT.AirportEntry("OTHH", "Hamad", "", "", 25.27, 51.61,
                         runway_m=4800, size_class=0),
    ]
    # By hand: the four largest, largest first.
    assert _row_labels(window, [(35, -81), (10, 10)]) == [
        "+35-081 (KCLT, KJQF, KEQY, KUZA)", "+10+010"]
    # Searched: a small field the user named goes first.
    window.search_edit.setText("NC00, OTHH")
    window._search_accept_first()
    window._tile_rows.clear()
    assert _row_labels(window, [(35, -81), (25, 51)]) == [
        "+35-081 (NC00, KCLT, KJQF, KEQY)", "+25+051 (OTHH)"]
    # Searched and already among the four: the order stays by size.
    window.search_edit.setText("KJQF")
    window._update_search_popup("KJQF")
    window._search_accept_first()
    window._tile_rows.clear()
    assert _row_labels(window, [(35, -81)]) == [
        "+35-081 (KCLT, KJQF, KEQY, KUZA)"]


def test_progress_row_title_owns_its_line_status_and_clock_share_the_next(
        make_window, monkeypatch):
    """#694: the title spans the whole first line; the gray status sits
    left on the second line and the clock right, before the button.  A
    narrow row elides the title at its tail and the status before the
    clock, which stays whole."""
    window, _ = _batch_window(make_window, monkeypatch)
    tile = (-13, -78)
    window._search_tags = {tile: ("SPJC", "KCLT", "OTHH", "KJQF")}
    window._setup_progress_page([tile])
    _bar, status, row, button, clock = window._tile_rows[tile]
    title = row.findChild(GUI.QLabel, "tile_title")
    status.setText("building the mesh with a long status text · 42%")
    clock.setText("1:23 · ~4:56")
    row.setParent(None)
    try:
        for width in (420, 200):
            row.resize(width, row.sizeHint().height())
            row.show()
            GUI.QApplication.processEvents()
            inner = row.contentsRect().width() - 12  # 6 px margins
            assert title.geometry().width() == inner
            assert status.geometry().top() > title.geometry().bottom()
            assert clock.geometry().top() > title.geometry().bottom()
            assert status.geometry().left() == title.geometry().left()
            assert status.geometry().right() < clock.geometry().left()
            assert clock.geometry().right() < button.geometry().left()
            assert button.geometry().right() == title.geometry().right()
            assert clock.alignment() & GUI.Qt.AlignRight
            # The clock is never squeezed: its whole text is painted.
            assert clock.geometry().width() >= (
                clock.fontMetrics().horizontalAdvance(clock.text()))
            painted = GUI.QLabel.text(status)
            if width == 200:
                assert painted.endswith("…")
                assert GUI.QLabel.text(title).endswith("…")
            else:
                assert GUI.QLabel.text(title) == title.text()
            assert title.text() == "-13-078 (SPJC, KCLT, OTHH, KJQF)"
    finally:
        row.hide()


# ===========================================================================
# Airport marks
# ===========================================================================
def _index_airport(code, lat, lon):
    return APT.AirportEntry(code, code, "", "", lat, lon)


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


def test_a_disabled_pack_leaves_its_airport_on_the_gray_layer(make_window):
    """Owner 2026-09-17, "revert to gray mark for disabled airports" —
    re-founding the old "a disabled pack dims its marks" assertion on the
    ruled behaviour.  The pack is not loaded by X-Plane and (RULINGS
    2026-09-17b) not read by the build, so the airport is graded from
    Global Airports and must carry the ordinary GRAY Global mark: no
    dimmed magenta mark, and NOT suppressed from the gray layer either.
    """
    window = make_window()
    window._airports = [_index_airport("EGKK", 51.1, -0.19)]
    window._scenery_packs = [
        PACKS.SceneryPack(
            name="Off", path="/p", content_root="/p", status="disabled",
            kind="airport",
            airports=(PACKS.PackAirport("EGKK", "Gatwick", 51.1, -0.19),)),
    ]
    window._push_airport_marks()
    assert window.map._custom_airports == []
    assert [row[0] for row in window.map._default_airports] == ["EGKK"]


def test_an_enabled_pack_beside_a_disabled_one_wins_undimmed(make_window):
    window = make_window()
    window._airports = [_index_airport("EGKK", 51.1, -0.19)]
    window._scenery_packs = [
        PACKS.SceneryPack(
            name="Off", path="/off", content_root="/off", status="disabled",
            kind="airport",
            airports=(PACKS.PackAirport("EGKK", "Gatwick", 51.1, -0.19),)),
        PACKS.SceneryPack(
            name="On", path="/on", content_root="/on", status="enabled",
            kind="airport",
            airports=(PACKS.PackAirport("EGKK", "Gatwick", 51.1, -0.19),)),
    ]
    window._push_airport_marks()
    assert window.map._custom_airports == [("EGKK", 51.1, -0.19, False)]
    assert window.map._default_airports == []


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
    (build / "Ortho4XP.cfg").write_text("default_zl=17\n", encoding="utf-8", newline="")
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


# ===========================================================================
# scenery_packs.ini — the two languages agree on the edge rules
# (owner RULINGS 2026-09-17b; Python's ONE derivation site is
# ``O4_Scenery_Packs``, Swift's is InstallationScanner + PackActions)
# ===========================================================================
def _swift(*parts):
    path = os.path.join(os.path.dirname(__file__), "..", "..",
                        "Sources", "SceneryKit", *parts)
    if not os.path.exists(path):
        pytest.skip("Swift sources not present in this tree")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def test_the_four_ini_edge_rules_match_the_mac_app(tmp_path):
    """Python's answers, then the Swift lines that give the same ones.

    Four rules, one per pair of assertions: EXACT token, unlisted =
    enabled, a non-``Custom Scenery/`` entry names no pack, and a pack not
    on disk (a dangling symlink onto an unmounted volume is the owner's
    common case) is simply absent — never an error.
    """
    import O4_Scenery_Packs as SP

    scanner = _swift("InstallationScanner.swift")
    actions = _swift("PackActions.swift")

    custom = tmp_path / "Custom Scenery"
    (custom / "on").mkdir(parents=True)
    (custom / "off").mkdir()
    (custom / "unlisted").mkdir()
    os.symlink(str(tmp_path / "unmounted" / "pack"), str(custom / "dangler"))
    (custom / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n"
        "SCENERY_PACK Custom Scenery/on/\n"
        "SCENERY_PACK_DISABLED Custom Scenery/off/\n"
        "SCENERY_PACK Custom Scenery/dangler/\n"
        "SCENERY_PACK *GLOBAL_AIRPORTS*\n", encoding="utf-8", newline="")

    # 1. EXACT first token — never startswith("SCENERY_PACK"), which
    #    SCENERY_PACK_DISABLED also satisfies.
    assert SP.pack_enabled("off", str(custom)) is False
    assert SP.pack_enabled("on", str(custom)) is True
    assert 'line.hasPrefix("SCENERY_PACK_DISABLED ")' in scanner
    assert '["SCENERY_PACK_DISABLED ", "SCENERY_PACK "]' in actions

    # 2. On disk but NOT LISTED = enabled (X-Plane adds it on next launch).
    assert SP.pack_enabled("unlisted", str(custom)) is True
    assert "(iniEntry?.enabled ?? true) ? .enabled : .disabled" in scanner

    # 3. An entry that is not a Custom Scenery path names no pack.
    assert SP.pack_name_from_ini_path("*GLOBAL_AIRPORTS*") is None
    assert SP.pack_name_from_ini_path(
        "Global Scenery/X-Plane 12 Global Scenery/") is None
    assert 'guard path.hasPrefix("Custom Scenery/") else { return nil }' \
        in actions

    # 4. Listed but not on disk (dangling symlink) = absent, never an
    #    error.  Swift keeps a pack whose symlink RESOLVES and drops one
    #    that does not, through the same isDirectory/fileExists test.
    assert SP.enabled_pack_names(str(custom)) == {"on", "unlisted"}
    assert "fm.fileExists(atPath: url.path, isDirectory: &isDir)" in scanner


# ===========================================================================
# #816: clicking an Activity row shows its tile (Mac: ActivityBox.showOnMap)
# ===========================================================================
def _click(widget, pos=None):
    from PySide6.QtTest import QTest
    QTest.mouseClick(widget, GUI.Qt.LeftButton,
                     pos=pos or widget.rect().center())


def test_clicking_a_progress_row_selects_and_frames_its_tile(make_window):
    window = make_window()
    window.resize(1200, 800)
    window.map.resize(800, 600)
    window._setup_progress_page([(48, -6), (10, 10)])
    window.map.set_selection([(48, -6), (10, 10)])
    row = window._tile_rows[(10, 10)][2]
    row.resize(260, 60)
    _click(row)
    assert window.map.selection() == {(10, 10)}
    assert window.map.active_tile() == (10, 10)
    (lat_lo, lat_hi, lon_lo, lon_hi) = window.map.visible_bounds()
    assert lat_lo < 10 and lat_hi > 11 and lon_lo < 10 and lon_hi > 11
    # Framed with a small margin, not left at world view.
    assert lon_hi - lon_lo < 4


def test_a_row_button_keeps_its_own_action(make_window, monkeypatch):
    window = make_window()
    window._setup_progress_page([(10, 10)])
    window.map.set_selection([(48, -6)])
    pressed = []
    monkeypatch.setattr(window, "_tile_button_clicked", pressed.append)
    _bar, _status, row, cancel, _clock = window._tile_rows[(10, 10)]
    row.resize(260, 60)
    # Re-wire: the lambda captured the original bound method.
    cancel.clicked.disconnect()
    cancel.clicked.connect(lambda _c=False: pressed.append((10, 10)))
    _click(cancel)
    assert pressed == [(10, 10)]
    assert window.map.selection() == {(48, -6)}


# ===========================================================================
# #817: tile labels and airport labels by size (Mac: MapCanvasLabels)
# ===========================================================================
def test_the_map_labels_large_airports_first_and_paints_tile_labels(
        make_window, tmp_path):
    window = make_window()
    window.map.resize(900, 700)
    window.map.set_airport_sizes({"BIGA": (0, 3500), "SMAL": (3, 600),
                                  "HELI": (4, 0)})
    window.map.set_default_airports([("BIGA", 48.50, -5.50),
                                     ("SMAL", 48.501, -5.499),
                                     ("HELI", 48.20, -5.20)])
    window.map.set_built({(48, -6): _tile_info(48, -6, str(tmp_path))})
    window.map.set_scenery_regions([("Other", [(47, -6)], False, "ortho")])
    assert window.map._ortho_tiles == {(47, -6)}
    # Far out: only the major airport is marked, nothing labelled yet.
    window.map.center_on_tile(48, -6, zoom=2.5)
    window.map.grab()
    (candidates, _dims, marks, labels, _r) = window.map._airport_layer._plan
    assert [candidates[i].code for i in marks] == ["BIGA"]
    assert labels == []
    # Close in: all three marked; the small field's label would sit on
    # the major one's, so only BIGA and HELI are labelled.
    window.map.center_on_tile(48, -6, zoom=9)
    window.map.grab()
    (candidates, _dims, marks, labels, _r) = window.map._airport_layer._plan
    assert sorted(candidates[i].code for i in marks) == ["BIGA", "HELI",
                                                         "SMAL"]
    assert [candidates[i].code for i, _ in labels] == ["BIGA", "HELI"]


# ===========================================================================
# #828: first-visit hint and empty states (Mac: MapHintOverlay, BuildPane)
# ===========================================================================
def test_the_map_hint_shows_until_the_first_selection_and_stays_gone(
        make_window):
    window = make_window()
    # The launch selection (the window's default tile) is not the user's.
    assert window.map.selection()
    assert not window.map_hint.isHidden()
    assert window.map_hint.label.text().endswith(GUI.GUIDE.HINT_TEXT)
    window.map.set_active(10, 10)
    assert window.map_hint.isHidden()
    assert _prefs(make_window)[GUI.GUIDE.HINT_DISMISSED_PREF] is True
    # Deselecting does not bring it back; a new window remembers.
    window.map.clear_selection()
    assert window.map_hint.isHidden()
    assert make_window().map_hint.isHidden()


def test_show_tips_brings_the_hint_back_and_close_dismisses_it(make_window):
    window = make_window()
    window.map_hint.close_button.click()
    assert window.map_hint.isHidden()
    assert _prefs(make_window)[GUI.GUIDE.HINT_DISMISSED_PREF] is True
    window.show_tips()
    assert not window.map_hint.isHidden()
    assert _prefs(make_window)[GUI.GUIDE.HINT_DISMISSED_PREF] is False
    titles = [a.text() for a in window.findChildren(GUI.QAction)]
    assert GUI.GUIDE.SHOW_TIPS_TITLE in titles


def test_the_empty_state_explains_tiles_and_how_to_start(make_window,
                                                         tmp_path):
    window = make_window()
    window._scanning = False
    window.map.clear_selection()
    assert not window.empty_state.isHidden()
    assert window.empty_state.text().startswith(GUI.GUIDE.EMPTY_SELECTION_TEXT)
    assert GUI.GUIDE.NOTHING_BUILT_TEXT in window.empty_state.text()
    window._built = {(48, -6): _tile_info(48, -6, str(tmp_path))}
    window.map.set_active(48, -6)
    assert window.empty_state.isHidden()
    window.map.clear_selection()
    assert GUI.GUIDE.NOTHING_BUILT_TEXT not in window.empty_state.text()



# ===========================================================================
# #543: search by airport name (Mac: AirportSearchResults, MapMainView)
# ===========================================================================
def test_a_name_finds_its_airport_accent_blind_and_selects_its_tiles(
        make_window, monkeypatch):
    window, _ = _batch_window(make_window, monkeypatch)
    window._airports.append(APT.AirportEntry(
        "XZRH", "Zürich Kloten", "Zürich", "Helvetia", 47.46, 8.55,
        extent=(47.44, 8.53, 47.48, 8.57), runway_m=3700, size_class=0))
    window._update_search_popup("zurich klo")
    item = window.search_popup.item(0)
    assert item.text() == "XZRH \u00b7 Zürich Kloten \u00b7 Zürich, Helvetia"
    window._search_accept_item(item)
    assert window.map.selection() == {(47, 8)}
    assert window.map.active_tile() == (47, 8)
    # A name straddling tiles selects every tile its extent touches.
    window._update_search_popup("edge")
    window._search_accept_first()
    assert window.map.selection() == {(47, 8), (47, 9), (48, 8), (48, 9)}
    assert window.map.active_tile() == (47, 8)


def test_no_match_says_so_and_selects_nothing(make_window, monkeypatch):
    window, _ = _batch_window(make_window, monkeypatch)
    before = window.map.selection()
    window.search_edit.setText("qqqq zzzz")
    window._update_search_popup("qqqq zzzz")
    assert window.search_popup.count() == 1
    assert window.search_popup.item(0).text() == (
        "No airport matches \u201cqqqq zzzz\u201d")
    window._search_accept_first()
    assert window.map.selection() == before


# ===========================================================================
# #829: select from flight plan (Mac: FlightPlanPanel, FlightRouteOverlay)
# ===========================================================================
_PLANS = os.path.join(os.path.dirname(__file__), "fixtures", "flight_plan")


def _flight_dialog(window, **seams):
    seams.setdefault("choose_file",
                     lambda: os.path.join(_PLANS, "short_hop_v11.fms"))
    return window.open_flight_plan_dialog(**seams)


def test_the_flight_plan_action_is_in_the_file_menu(make_window):
    window = make_window()
    from PySide6.QtWidgets import QMenu
    menus = [m for m in window.menuBar().findChildren(QMenu)
             if window.flight_plan_action in m.actions()]
    assert [m.title() for m in menus] == ["&File"]
    assert window.flight_plan_action.text() == FLIGHTPLAN.MENU_TITLE


def test_a_plan_file_selects_its_route_live_and_draws_it(make_window):
    window = make_window()
    window.map.set_selection({(10, 10)})
    dialog = _flight_dialog(window)
    dialog.unit_combo.setCurrentText("km")
    dialog.radius_spin.setValue(0)
    dialog.open_file()
    route = set(FLIGHTPLAN.route_tiles(FLIGHTPLAN.read_plan_file(
        os.path.join(_PLANS, "short_hop_v11.fms")).points(), 0))
    assert window.map.selection() == {(10, 10)} | route
    assert dialog.layer.parts() and dialog.layer in window.map._layers
    assert dialog.summary.text().startswith("KSEA \u2192 KPDX")
    assert dialog.minimumSizeHint().width() <= 640   # fits a small laptop
    small = window.map.selection()
    dialog.radius_spin.setValue(100)          # live: no button press
    assert window.map.selection() > small
    assert dialog.count_label.text() == FLIGHTPLAN.tiles_text(len(dialog.tiles()))
    dialog.accept()
    assert window.map.active_tile() == (47, -123)   # the departure tile
    assert dialog.layer.parts() == []
    assert (10, 10) in window.map.selection()


def test_cancel_puts_the_old_selection_back(make_window):
    window = make_window()
    window.map.set_active(10, 10)
    dialog = _flight_dialog(window)
    dialog.open_file()
    assert window.map.selection() != {(10, 10)}
    dialog.reject()
    assert window.map.selection() == {(10, 10)}
    assert dialog.layer.parts() == []


def test_the_unit_converts_the_radius_and_is_remembered(make_window):
    window = make_window()
    dialog = _flight_dialog(window)
    dialog.unit_combo.setCurrentText("km")
    dialog.radius_spin.setValue(93)
    dialog.unit_combo.setCurrentText("nm")
    assert dialog.radius_spin.value() == 50
    assert dialog.radius_spin.maximum() == FLIGHTPLAN.RADIUS_MAX["nm"]
    assert dialog.radius_km() == pytest.approx(92.6)
    prefs = _prefs(make_window)
    assert (prefs["flight_plan_unit"], prefs["flight_plan_radius"]) == ("nm", 50)


def test_simbrief_uses_the_fetch_seam_and_reports_errors(make_window):
    window = make_window()
    with open(os.path.join(_PLANS, "simbrief_ofp.xml"), encoding="utf-8") as fh:
        ofp = fh.read()
    asked = []

    def fake_fetch(user):
        asked.append(user)
        if user == "nobody":
            raise FLIGHTPLAN.FlightPlanError("SimBrief: Unknown UserID")
        return FLIGHTPLAN.parse_simbrief(ofp)

    dialog = _flight_dialog(window, fetch=fake_fetch)
    dialog.simbrief_edit.setText("nobody")
    dialog.fetch_simbrief()
    assert dialog.summary.text() == "SimBrief: Unknown UserID"
    assert not dialog.tiles()
    dialog.simbrief_edit.setText("123456")
    dialog.fetch_simbrief()
    assert asked == ["nobody", "123456"]
    assert dialog.summary.text().startswith("ENGM \u2192 ENTC")
    assert (60, 11) in window.map.selection() and (69, 18) in window.map.selection()
    assert _prefs(make_window)["simbrief_user"] == "123456"


# ===========================================================================
# A Qt run that cannot see its tiles or airports says so (#1240, #1241)
# ===========================================================================
def test_a_missing_tiles_folder_falls_back_to_the_default(make_window, tmp_path):
    """A remembered output folder that is gone (the owner's pointed at a
    deleted pytest folder) listed no built tiles, so the patch editor
    never appeared: the window falls back to the default Tiles folder."""
    with open(make_window.prefs_path, "w", encoding="utf-8", newline="") as handle:
        json.dump({"output_dir": str(tmp_path / "gone")}, handle)
    window = make_window()
    assert window.prefs["output_dir"] == ""
    assert window.working_dir() == GUI.FNAMES.Tile_dir


def test_search_without_an_airport_index_says_why(make_window):
    window = make_window()
    window._airports = []
    window._airport_search_index = None
    window._update_search_popup("KSEA")
    rows = [window.search_popup.item(i).text()
            for i in range(window.search_popup.count())]
    assert rows == [GUI.SEARCH.NO_INDEX_TEXT]


def test_the_x_plane_folder_is_found_above_custom_scenery(tmp_path, monkeypatch):
    import O4_Config_Utils as CFG

    apt = tmp_path / "X-Plane 12" / "Global Scenery" / "Global Airports" / "Earth nav data"
    apt.mkdir(parents=True)
    (apt / "apt.dat").write_text("I\n1100 Version\n99\n", encoding="utf-8", newline="")
    (tmp_path / "X-Plane 12" / "Custom Scenery").mkdir()
    monkeypatch.setattr(CFG, "custom_scenery_dir",
                        str(tmp_path / "X-Plane 12" / "Custom Scenery"))
    assert GUI._xplane_above_custom_scenery() == str(tmp_path / "X-Plane 12")
    monkeypatch.setattr(CFG, "custom_scenery_dir", "")
    assert GUI._xplane_above_custom_scenery() == ""


def test_an_unset_global_config_starts_from_sharper_airports(tmp_path, monkeypatch):
    """Owner 2026-10-22: the default preset is Sharper airports, also for
    a user who skipped the first-run assistant (it used to stay Balanced)."""
    import O4_Settings_Model as SM
    import O4_Settings_Presets as PRESETS

    cfg = tmp_path / "Ortho4XP.cfg"
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(cfg))
    monkeypatch.setattr(SM, "apply_runtime", lambda values: None)
    entry = PRESETS.preset("sharper_airports")
    assert GUI.write_default_preset_if_unset() == PRESETS.zoom_value(entry)
    written = SM.read_global_raw()
    assert all(written[name] == value
               for name, value in PRESETS.cfg_values(entry).items())
    # Once any preset key is set, nothing is overwritten.
    assert GUI.write_default_preset_if_unset() is None


def test_why_build_is_off_shows_as_text(make_window, monkeypatch):
    """The Mac's build box says why Build is off; a tooltip alone was
    never seen."""
    window = make_window()
    reason = "Your X-Plane folder has no runway data (CIFP)."
    monkeypatch.setattr(window, "xplane_block_reason", lambda: reason)
    window._update_build_summary()
    assert not window.build_btn.isEnabled()
    assert window.build_block_label.isVisibleTo(window)
    assert window.build_block_label.text() == reason
    monkeypatch.setattr(window, "xplane_block_reason", lambda: None)
    window._update_build_summary()
    assert window.build_btn.isEnabled()
    assert not window.build_block_label.isVisibleTo(window)
