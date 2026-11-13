"""One window layout, two apps (issue #1244).

The Mac app (``Sources/XPTerrainBuilder``) is the layout authority; the Qt
window mirrors it.  The two drifted once: parity rounds ported behaviour
but not layout, and the Qt window kept a toolbar and build-area rows the
Mac app never had (#1243).  This twin holds the MANIFEST below — the
toolbar items and the build-box controls, in order — and requires both
apps to show exactly those: the Swift sources parsed statically, the Qt
window read from its live widgets.  A control added to one app fails here
until the other has it too (or the manifest records an owner-ruled
exception).

Offscreen (``QT_QPA_PLATFORM=offscreen``), no network, no engine.
"""

import inspect
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_GUI as GUI  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QWidget,
)

SWIFT = Path(__file__).resolve().parents[2] / "Sources" / "XPTerrainBuilder"

# ─── THE MANIFEST ──────────────────────────────────────────────────────────
#: The map toolbar, left to right: (key, Swift marker, Qt window attribute).
#: No refresh button in either app (#1258): both rescan Custom Scenery
#: when it changes.
TOOLBAR = (
    # RULINGS 2026-11-11k: Build · Fly leads (spec §14; 10j's Library
    # retired).
    ("mode", "ModeSwitch(model:", "mode_switch"),
    ("imagery_preview", 'Picker("Imagery Preview"', "map_provider_combo"),
    ("scenery_filter", 'Picker("Scenery"', "scenery_filter_combo"),
    ("search", "ToolbarSearchField(", "search_edit"),
    ("side_panel", 'Image(systemName: "sidebar.trailing")', "panel_toggle"),
)

#: The side pane per mode (RULINGS 2026-11-11k; spec §14): (key, Swift
#: marker in MapMainView.swift's ``ModePanes``, Qt window attribute).  One
#: map and one selection; the Fly offer stands above the pane.
MODE_PANES = (
    ("build", "BuildPane(", "build_pane"),
    ("fly", "FlyPane(", "fly_pane"),
)
FLY_OFFER = ("FlyOfferBanner(model:", "fly_offer")

#: Fly mode's pane, top to bottom (key, Swift marker in FlyPane.swift, Qt
#: ``O4_Qt_Fly_Pane.FlyPane`` attribute): spec §14's rows (lane U2), with
#: the departure + arrival quick entry after "Open plan file…" and the
#: intro text (U1's placeholder) leading while no flight is named.
FLY_PANE = (
    ("placeholder", "AppModeText.flyPlaceholder", "placeholder"),
    ("here", "FlyHereBlock(model:", "here_block"),                    # #2020
    ("plan_source", "Picker(FlyText.planSourceLabel", "plan_source_combo"),
    ("simbrief", "SimBriefRow(model:", "simbrief_row"),
    ("open_plan", "Button(FlyText.openPlan)", "open_plan_btn"),
    ("quick_route", "QuickRouteRow(model:", "quick_route_row"),
    ("flight_card", "FlightCard(model:", "flight_card"),
    ("build_alternate", "Toggle(FlyText.buildAlternate", "chk_build_alternate"),
    ("cruise_speed", "CruiseSpeedField(model:", "cruise_speed_edit"),
    ("corridor", "CorridorWidthField(model:", "corridor_edit"),
    ("readiness", "ReadinessChecklist(model:", "readiness_list"),
    ("offline_waiver", "OfflineWaiverRow(model:", "offline_waiver_row"),  # F2, 10k Q3
    ("countdown", "FlightCountdown(model:", "countdown_label"),
    ("world_line", "WorldStatusLine(model:", "world_line"),
    ("follow_line", "ImageryFollowLine(model:", "follow_line"),
    ("sim_priority", "Picker(FlyText.simPriorityLabel", "sim_priority_combo"),
    ("drape_px", "Picker(FlyText.drapePxLabel", "drape_px_combo"),   # 11j
    ("photo_source", "PhotoSourcePicker(model:", "photo_source_combo"),  # owner 11-12
    ("live_preview", "Toggle(FlyText.livePreview", "chk_live_preview"),   # #2001
    ("reload_offer", "ReloadOfferRow(model:", "reload_offer_row"),     # F2, S6 (b)
    ("divert", "Button(FlyText.divert)", "divert_btn"),
    ("end_flight", "Button(FlyText.endFlight)", "end_flight_btn"),
)

#: Settings ▸ Storage's rows, top to bottom, above the cleanup settings
#: (RULINGS 2026-11-11k (2); the Library pane's from #2007 until 11k, in
#: 11a's order without the patch library): (key, Swift marker in
#: LibraryStorage.swift's ``StorageSettingsRows``, Qt
#: ``O4_Qt_Library_Storage.StorageRows`` attribute).
STORAGE_ROWS = (
    ("data_folder", "DataFolderRow(", "folder_row"),
    ("disk_budget", "DiskBudgetSection(", "budget_box"),
    ("convert", "ConvertTilesSection(", "convert_box"),            # §13
    ("tiers", "StorageTiersSection(", "tiers_box"),                # 12g
    ("caches", "CachesLine(", "caches_box"),
)

#: The Caches line's two buttons and the start's World onboarding (#2007):
#: (key, Swift file, Swift marker, Qt owner, Qt attribute).
LIBRARY_STORAGE = (
    ("caches_clear", "LibraryStorage.swift", "model.askClearAll()",
     "caches_box", "clear_btn"),
    ("caches_details", "LibraryStorage.swift", "StorageDetailsSheet(model:",
     "caches_box", "details_btn"),
    # Owner 2026-11-12: "Budget (GB)" left, the slider beside it, the
    # number field right, on one row.
    ("budget_field_label", "LibraryStorage.swift", "Text(O4StorageText.budgetField)",
     "budget_box", "budget_field_label"),
    ("budget_field", "LibraryStorage.swift", "TextField(\"\", text: $field)",
     "budget_box", "budget_edit"),
    # #2022: the slider, its labelled ends, the preview while it moves and
    # the stacked usage bar.
    ("budget_slider", "LibraryStorage.swift", "Slider(value: $gigabytes",
     "budget_box", "budget_slider"),
    ("budget_ends", "LibraryStorage.swift", "O4StorageText.endLabels(",
     "budget_box", "min_label"),
    ("budget_preview", "LibraryStorage.swift", "O4StorageText.previewText(",
     "budget_box", "preview_label"),
    ("budget_notice", "LibraryStorage.swift", "O4StorageText.rangeNotice(",
     "budget_box", "budget_warning"),
    ("usage_bar", "LibraryStorage.swift", "StorageUsageBar(budget:",
     "budget_box", "usage_bar"),
    ("budget_downgrade", "LibraryStorage.swift", "O4StorageText.downgradeMessage(",
     "budget_box", "_ask"),
    # RULINGS 2026-11-11h (1): unconfirmed, Confirm records the default.
    ("budget_confirm", "LibraryStorage.swift", "Button(O4StorageText.budgetConfirm)",
     "budget_box", "confirm_btn"),
    ("world_onboard", "MapMainView.swift", "WorldOnboardSheet(offer:",
     "onboard", "OnboardDialog"),
)

#: Settings that are no plain Settings row in either app: the disk budget
#: is the Storage rows' ``DiskBudgetSection`` / ``DiskBudgetBox`` (RULINGS
#: 2026-11-11h (3), its home Settings ▸ Storage since 11k (2)).
STORAGE_BOX_SETTINGS = ("storage_budget_gb",
                        # RULINGS 2026-11-12g: the Storage tiers rows
                        "storage_tiers")

#: Fly mode's map layers, bottom to top (key, Swift marker in
#: FlyMapOverlay.swift, Qt marker in O4_Qt_Fly_Layer.py): "Live flight
#: preview"'s installed imagery (#2001) lies under the corridor, the route,
#: the track and the aircraft in both maps.
FLY_MAP_LAYERS = (
    ("live_preview", "drawPreview(cam", "self.preview.paint("),
    ("corridor", "for cell in model.cells", "self._pane.cells()"),
    ("route", "stroke(model.drawing", "FP.route_drawing("),
    ("track", "stroke(model.track.parts", "track.parts()"),
    ("aircraft", "drawAircraft(cam.point", "self._aircraft("),
)

#: The map's top-right controls, left to right (#2016): (key, Swift marker
#: in MapCanvasView.swift's ``zoomControls``, Qt
#: ``O4_Qt_Map_Controls.MapControls`` attribute).
MAP_CONTROLS = (
    ("zoom_out", "zoom(by: 1 / 1.5)", "zoom_out_btn"),
    ("zoom_in", "zoom(by: 1.5)", "zoom_in_btn"),
    ("center_on_aircraft", "CenterOnAircraftButton(model:", "center_btn"),
)

#: The Build box's controls, top to bottom: (key, Swift label, Qt attribute).
#: A Swift label is a ``Toggle``/``Picker`` title literal or its glossary
#: term.  The Detail level (#1242) and the per-tile texture and elevation
#: levels (#1243) are NOT here: both apps set them in Settings only.
#: #818: the Airports card leads (its two per-build switches), then the
#: imagery source, "When it's done", and the build steps under Advanced
#: (collapsed by default in both apps).
BUILD_BOX = (
    ("grade_airports", "grade_airports", "chk_grade_airports"),
    ("fit_buildings", "fit_buildings", "chk_modify_airports"),
    ("imagery", "Imagery", "imagery_combo"),
    ("auto_install", "Install in X-Plane automatically", "chk_auto_install"),
    ("skip_built", "Skip tiles already built", "chk_skip_built"),
    ("terrain_steps", "terrain_steps", "chk_vector"),
    ("imagery_and_scenery_file", "imagery_and_scenery_file", "chk_imagery"),
)

#: X-Plane's roads, forests and buildings are automatic (#2021, RULINGS
#: 2026-11-12e): no switch in either Build box, a line under Advanced of
#: these two glossary terms (Mac ``Text``s, Qt ``overlays_note``).
OVERLAYS_LINE = ("xplane_objects", "xplane_objects_auto")

#: The Airports card's sentences: (Swift ``static let``, Qt constant).
AIRPORTS_CARD_TEXT = (
    ("gradeSentence", "GRADE_SENTENCE"),
    ("fitSentence", "FIT_SENTENCE"),
    ("backupNote", "BACKUP_NOTE"),
)

#: The patch editor's Edit-mode right-click items, in menu order (#1318
#: Slice, #1963 Duplicate shape): (Swift ``TileContextMenu`` static let,
#: Qt module, Qt constant).
PATCH_EDIT_MENU = (
    ("sliceTitle", "O4_Qt_Patch_Editor", "SLICE_TITLE"),
    ("duplicateShapeTitle", "O4_Qt_Patch_Editor", "DUPLICATE_SHAPE_TITLE"),
)

#: The patch library's homes (#1699 phase 2), each in both apps:
#: (key, Swift file, Swift marker, Qt owner, Qt attribute).  The match
#: list sits in the Airports card under the airport list; the "Patch
#: library" section and the tiles' "Publish Patch…" are PARKED with the
#: tiles table (owner 2026-11-11T15:35Z, RULINGS 11k (3) waits): no window
#: shows them, both apps keep them alike.
PATCH_LIBRARY = (
    ("match_list", "BuildAirportsCard.swift", "LibraryMatchList(matches:",
     "airports_card", "library_match_list"),
    ("library_section", "PatchLibraryView.swift", "struct PatchLibrarySection",
     "library_tiles", "patch_box"),
    ("publish", "LibraryView.swift", 'Button("Publish Patch…")',
     "library_tiles", "publish_btn"),
)

#: The package actions' homes (#2014; owner 2026-11-11T15:35Z: a File
#: menu item for the selected tiles, the tile menu a shortcut to it; the
#: Library gets nothing new): (key, Swift file, Swift marker, Qt owner,
#: Qt attribute).
TILE_PACKAGE = (
    ("file_menu", "XPTerrainBuilderApp.swift", "TilePackageCommands(buildModel:",
     "window", "export_package_action"),
    ("tile_menu", "TileContextMenu.swift", "Self.exportPackageTitle",
     "window", "_export_package_at"),
    ("drop", "PatchDropInstall.swift", "TilePackageModel.shared.offer(",
     "window", "patch_drop"),
    # The export window is airport-first (owner 2026-11-11T16:10Z): the
    # airport picker, then each kind with the engine's estimate row.
    ("export_airport", "TilePackageSheets.swift", "O4TilePackageCopy.airportLabel",
     "package", "AIRPORT_LABEL"),
    ("export_kinds", "TilePackageSheets.swift", "row.figures",
     "package", "_ExportDialog"),
    ("export_estimate", "TilePackageSheets.swift", "client.packageEstimate(",
     "package", "export"),
    # RULINGS 2026-11-11m: the pack author's rows in the export window, and
    # a pack's shipped package noticed (and its conflict asked) on build.
    ("export_pack_rows", "TilePackageSheets.swift", "O4TilePackageCopy.intoPack",
     "package", "INTO_PACK"),
    ("pack_package_notice", "BuildModel.swift", "case .packPackage",
     "package", "on_pack_package"),
)

#: Imagery on demand's homes (#1992 §7, P4), each in both apps: (key,
#: Swift file, Swift marker, Qt owner, Qt attribute).  The follow line
#: is in the Fly pane (RULINGS 2026-11-10j); the pin sits in the tile pane under the
#: imagery check and in the (parked) tiles table's actions and tile menu;
#: the Storage details' ondemand row makes all low-res again.
IMAGERY_ON_DEMAND = (
    ("follow_line", "FlyPane.swift", "ImageryFollowLine(model:",
     "window", "follow_line"),
    ("tile_pin", "BuildPane.swift", "TilePinRow(pinned:",
     "window", "tile_pin_row"),
    ("library_pin", "LibraryView.swift", "model.togglePin(",
     "library_tiles", "pin_btn"),
    ("library_menu", "LibraryView.swift", ".contextMenu(forSelectionType:",
     "library_tiles", "_tile_menu"),
    ("make_low_res", "StorageSettingsView.swift", "model.askMakeLowRes(",
     "storage", "ask_make_low_res"),
    # RULINGS 2026-11-10d and the owner's 1.0.480 feedback: the one disk
    # budget's line and X-Plane's installed tiles, in the Data Folder box.
    ("disk_budget", "LibraryStorage.swift", "O4StorageText.budgetLines(",
     "budget_box", "budget_label"),
    ("installed_tiles", "StorageSettingsView.swift", "O4StorageText.installedLines(",
     "storage", "installed_label"),
)

#: What imagery on demand hides in the Build box (RULINGS 2026-11-10e
#: (1)): (key, Swift label, Qt attribute).  The Mac app wraps them in
#: :data:`ON_DEMAND_GUARD`; the Qt window lists them in
#: ``O4_Qt_Build_OnDemand.HIDDEN``.
ON_DEMAND_HIDDEN = (
    ("when_done", "Text(\"When it's done\")", "build_done_label"),
    ("auto_install", 'Toggle("Install in X-Plane automatically"', "chk_auto_install"),
    ("skip_built", 'Toggle("Skip tiles already built"', "chk_skip_built"),
)
ON_DEMAND_GUARD = "if !buildModel.onDemandBuilds {"

#: The build-cost panel (#820): last in the Build box, just above Build —
#: (Swift marker, Qt window attribute).
PLAN_PANEL = ("PlanEstimatePanel(", "plan_panel")

#: Settings ▸ General's app-level sections, top to bottom (#1267), and the
#: Application section's rows (#1266: the Data Folder chooser).  The Mac's
#: Appearance picker is a recorded exception: Qt follows the system theme.
GENERAL_SECTIONS = ("Application", "Build Engine", "Provider Accounts")

#: The console header after its title, left to right (#1226, owner Q139):
#: (key, Swift marker in BuildConsoleView.swift, Qt ConsoleDrawer
#: attribute).  The Build History list beside the console carries the one
#: date filter: (Swift marker in BuildHistoryView.swift, Qt attribute).
CONSOLE_HEADER = (
    ("filter_chip", "filterChip", "chip"),
    ("saved_logs", "savedLogsMenu", "saved_logs_btn"),
    ("history", 'Image(systemName: "clock.arrow.circlepath")', "history_btn"),
    ("clear", 'Image(systemName: "xmark.circle")', "console_clear_btn"),
)
HISTORY_DATE_FILTER = ('Picker("Built"', "range_combo")

#: The tile pane's "Path" row (#1987), just under "Built by": (Swift
#: marker in BuildPane.swift, Qt window attribute).
TILE_PATH_ROW = ("TilePathRow(info:", "tile_path_row")
APPLICATION_ROWS = ("Version", "X-Plane Folder", "Data Folder")

#: The Build pane's run sections, top to bottom (#1556), each a section
#: of ONE native list (#1537): (key, Swift marker in ActivitySections.swift,
#: Qt section item of ``window.activity_list``).  Completed collapses to
#: "Completed (N)" in both apps.
RUN_SECTIONS = (
    ("activity", 'Text("Activity")', "activity_item"),
    ("completed", "Self.completedTitle(", "completed_item"),
)
#: The one list both apps draw the sections in, and its native selection.
RUN_LIST = ("List(selection:", "Section(isExpanded:")
COMPLETED_TITLE = ('"Completed (\\(count))"', "Completed (12)", 12)


# ─── the Mac app, read statically ─────────────────────────────────────────

def _block(path: Path, start: str, end: str) -> str:
    text = path.read_text(encoding="utf-8")
    a = text.index(start)
    return text[a:text.index(end, a)]


def _swift_toolbar() -> str:
    return _block(SWIFT / "MapMainView.swift",
                  "var toolbarContent", "// MARK: - Search")


def _swift_build_box() -> list:
    block = _block(SWIFT / "BuildPane.swift",
                   "private var buildBox: some View",
                   "// MARK: - Imagery-source conflict")
    # The Airports card is its own view: its controls stand where it does.
    card = _block(SWIFT / "BuildAirportsCard.swift",
                  "var body: some View", "private func caption")
    block = block.replace("BuildAirportsCard(", card, 1)
    found = re.findall(
        r'\b(?:Toggle|Picker)\((?:O4Glossary\.term\("(\w+)"\)|"([^"]+)")', block)
    return [term or literal for term, literal in found]


def test_mac_toolbar_is_the_manifest():
    block = _swift_toolbar()
    assert block.count("ToolbarItem(") == len(TOOLBAR), (
        "the Mac toolbar's item count changed: update TOOLBAR (and the Qt "
        "window) to match")
    positions = [block.find(marker) for _key, marker, _attr in TOOLBAR]
    assert -1 not in positions, dict(zip((k for k, _m, _a in TOOLBAR), positions, strict=True))
    assert positions == sorted(positions), "Mac toolbar order differs from TOOLBAR"


def test_mac_build_box_is_the_manifest():
    assert _swift_build_box() == [label for _key, label, _attr in BUILD_BOX]


def test_mac_build_box_says_the_overlays_are_automatic():
    block = _block(SWIFT / "BuildPane.swift",
                   "private var buildBox: some View",
                   "// MARK: - Imagery-source conflict")
    for term in OVERLAYS_LINE:
        assert 'Text(O4Glossary.term("%s"))' % term in block, term
    assert "doOverlays" not in block


def test_the_airports_cards_say_the_same_words():
    import O4_Qt_Build_Airports as QTAIRPORTS

    swift = (SWIFT / "BuildAirportsCard.swift").read_text(encoding="utf-8")
    for name, constant in AIRPORTS_CARD_TEXT:
        said = re.search(r'static let %s = "([^"]+)"' % name, swift)
        assert said, name
        assert said.group(1) == getattr(QTAIRPORTS, constant), name


def test_the_patch_edit_menus_are_the_manifest(qapp):
    """Both apps' Edit-mode right-click menus start with the same items, in
    the same order, with the same words."""
    import importlib
    from types import SimpleNamespace as NS

    from O4_Qt_Patch_Editor import PatchEditor
    from PySide6.QtWidgets import QMenu

    swift = (SWIFT / "TileContextMenu.swift").read_text(encoding="utf-8")
    init = swift[swift.index("    init(coord:"):]
    titles, marks = [], []
    for name, module, constant in PATCH_EDIT_MENU:
        said = re.search(r'static let %s = "([^"]+)"' % name, swift)
        assert said, name
        assert said.group(1) == getattr(importlib.import_module(module), constant), name
        titles.append(said.group(1))
        marks.append(init.find("Self.%s" % name))
    assert -1 not in marks and marks == sorted(marks), "Mac patch menu order differs"
    model = NS(doc=object(), mode="Edit", shape_selection=set(),
               slice_args=lambda: {}, slice_selection=lambda: None,
               duplicate_shapes=lambda: None)
    menu = QMenu()
    menu.addAction("Show in Finder")
    PatchEditor.add_to_menu(NS(model=model), menu)
    assert [a.text() for a in menu.actions()][:len(titles)] == titles


def test_mac_plan_panel_closes_the_build_box():
    block = _block(SWIFT / "BuildPane.swift",
                   "private var buildBox: some View",
                   "// MARK: - Imagery-source conflict")
    marker = block.find(PLAN_PANEL[0])
    assert marker != -1, "the Mac Build box lost its cost panel"
    assert marker > block.rfind("Toggle("), "the cost panel must follow the toggles"


def test_mac_run_sections_are_the_manifest():
    block = _block(SWIFT / "ActivitySections.swift",
                   "struct ActivitySections", "\n}\n")
    marks = [block.find(marker) for _key, marker, _attr in RUN_SECTIONS]
    assert -1 not in marks, dict(zip((k for k, _m, _a in RUN_SECTIONS), marks, strict=True))
    assert marks == sorted(marks), "Mac run section order differs"
    assert COMPLETED_TITLE[0] in block
    for marker in RUN_LIST:
        assert marker in block, marker


def _swift_general() -> str:
    return _block(SWIFT / "SettingsView.swift",
                  "private struct GeneralPane", "private func pathText")


def test_mac_general_sections_are_the_manifest():
    general = _swift_general()
    marks = [general.find(f'Section("{GENERAL_SECTIONS[0]}")')]
    marks += [general.find(f'Text("{title}")') for title in GENERAL_SECTIONS[1:]]
    assert -1 not in marks, dict(zip(GENERAL_SECTIONS, marks, strict=True))
    assert marks == sorted(marks), "Mac General section order differs"


def test_mac_application_rows_are_the_manifest():
    general = _swift_general()
    start = general.index('Section("Application")')
    application = general[start:general.index("Section {", start)]
    rows = re.findall(r'LabeledContent\("([^"]+)"\)', application)
    assert [row for row in rows if row != "Status"] == list(APPLICATION_ROWS)


def test_mac_console_header_is_the_manifest():
    header = _block(SWIFT / "BuildConsoleView.swift",
                    "private var header: some View", "@ViewBuilder")
    positions = [header.find(marker) for _key, marker, _attr in CONSOLE_HEADER]
    assert -1 not in positions, dict(zip((k for k, _m, _a in CONSOLE_HEADER),
                                         positions, strict=True))
    assert positions == sorted(positions), "Mac console header order differs"
    history = (SWIFT / "BuildHistoryView.swift").read_text(encoding="utf-8")
    assert HISTORY_DATE_FILTER[0] in history


def test_mac_settings_holds_the_detail_level():
    # #1985: General holds the airport Detail choice under the cards; the
    # build zoom leads Imagery.
    general = _block(SWIFT / "SettingsView.swift",
                     "private struct GeneralPane", "private func pathText")
    assert general.index("PresetCardsView()") < general.index(
        "AirportDetailPicker()")
    assert "ImageryZoomPicker()" not in general
    pane = _block(SWIFT / "SettingsView.swift",
                  "private struct CategoryPane", "private struct ExpertSection")
    assert 'category.key == "imagery"' in pane and "ImageryZoomPicker()" in pane
    pickers = (SWIFT / "SettingsDetailPickers.swift").read_text(encoding="utf-8")
    assert 'Picker(O4Glossary.term("imagery_detail")' in pickers
    assert "Picker(AirportDetail.title" in pickers


# ─── the Qt window, read live ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    prefs = tmp_path / "prefs.json"
    # An EXISTING prefs file: an absent one arms the first-run wizard.
    prefs.write_text(json.dumps({"output_dir": str(tmp_path)}), encoding="utf-8", newline="")
    monkeypatch.setattr(GUI, "PREFS_FILE", str(prefs))
    monkeypatch.setattr(GUI.FNAMES, "Tile_dir", str(tmp_path))  # 12g
    monkeypatch.setattr(GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "scan.json"))
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    try:
        yield win
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        sys.stdout = saved_stdout


def _qt_toolbar(window) -> list:
    """The toolbar's controls, left to right (labels and the spacer are
    layout, not controls)."""
    controls = []
    for action in window.toolbar.actions():
        widget = window.toolbar.widgetForAction(action)
        if widget is None or isinstance(widget, QLabel) or type(widget) is QWidget:
            continue
        controls.append(widget)
    return controls


def test_qt_toolbar_is_the_manifest(window):
    expected = [getattr(window, attr) for _key, _marker, attr in TOOLBAR]
    assert _qt_toolbar(window) == expected


def _qt_build_box(window) -> list:
    """The Build box's combos and checkboxes, top to bottom."""
    group = window.build_btn.parentWidget()
    layout = group.layout()
    controls = []
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is None:
            continue
        if isinstance(widget, (QComboBox, QCheckBox)):
            controls.append(widget)
        else:
            controls.extend(child for child in widget.findChildren(QWidget)
                            if isinstance(child, (QComboBox, QCheckBox)))
    return controls


def test_qt_build_box_is_the_manifest(window):
    expected = [getattr(window, attr) for _key, _label, attr in BUILD_BOX]
    assert _qt_build_box(window) == expected


def test_qt_build_box_says_the_overlays_are_automatic(window):
    import O4_Glossary as GLOSSARY

    assert window.overlays_note.text() == "\n".join(
        GLOSSARY.TERMS[term] for term in OVERLAYS_LINE)
    assert window.overlays_note.parentWidget() is window.advanced_box
    assert not hasattr(window, "chk_overlays")


def test_qt_build_box_labels_are_the_macs(window):
    import O4_Glossary as GLOSSARY

    for key, label, attr in BUILD_BOX:
        widget = getattr(window, attr)
        if isinstance(widget, QCheckBox):
            assert widget.text() == GLOSSARY.TERMS.get(label, label), key


def test_qt_plumbing_is_collapsed_by_default(window):
    window.show()
    assert window.airports_card.isVisible()
    assert not window.chk_vector.isVisible()
    window.advanced_toggle.setChecked(True)
    assert window.chk_vector.isVisible()


def test_qt_grading_off_is_this_builds_only(window, tmp_path, monkeypatch):
    """#818: unticking grading sends ``auto_patch`` False in the batch,
    puts the switch back for the next press, and writes no cfg."""
    import O4_Settings_Model as SM

    sent = []
    writes = []
    monkeypatch.setattr(window, "xplane_block_reason", lambda: None)
    monkeypatch.setattr(window.map, "selection", lambda: {(47, -123)})
    monkeypatch.setattr(window._session, "boundary_airports",
                        lambda **_kw: None)
    monkeypatch.setattr(window._session, "enqueue_build",
                        lambda tiles, **kw: sent.append(kw) or False)
    monkeypatch.setattr(SM, "write_tile",
                        lambda *a, **kw: writes.append(a))
    monkeypatch.setattr(SM, "write_global",
                        lambda *a, **kw: writes.append(a))
    if window.imagery_combo.count() == 0:
        window.imagery_combo.addItem("BI")    # no provider list offscreen
    window.imagery_combo.setCurrentIndex(0)
    import O4_Qt_Build_Airports as QTAIRPORTS

    statuses = []
    monkeypatch.setattr(window, "_status", statuses.append)
    monkeypatch.setattr(QTAIRPORTS, "grade_by_default", lambda: True)
    window.chk_skip_built.setChecked(False)
    window.airports_card.refresh_switches()        # Settings: grading on
    assert window.chk_grade_airports.isChecked()
    window.chk_grade_airports.setChecked(False)
    window.start_build()
    assert sent, statuses
    assert sent[-1]["overrides"] == {"auto_patch": False}
    assert window.chk_grade_airports.isChecked()   # back to Settings
    assert not writes
    window.start_build()
    assert "overrides" not in sent[-1]


def test_qt_run_sections_are_the_manifest(window):
    import O4_Qt_Activity_List as QTACT

    listed = window.activity_list
    assert window._panel_layout.indexOf(window.activity_split) != -1
    assert window.activity_split.indexOf(window.activity_group) == 1
    assert window.activity_split.handleWidth() >= 9   # Mac: 9 pt band
    sections = [getattr(listed, attr) for _key, _marker, attr in RUN_SECTIONS]
    assert listed.sections() == sections
    assert QTACT.completed_title(COMPLETED_TITLE[2]) == COMPLETED_TITLE[1]


def test_qt_plan_panel_sits_just_above_build(window):
    layout = window.build_btn.parentWidget().layout()
    widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
    panel = getattr(window, PLAN_PANEL[1])
    assert widgets.index(panel) == widgets.index(window.build_btn) - 1
    assert widgets.index(panel) > widgets.index(window.chk_auto_install)


def test_qt_settings_holds_the_detail_level(window):
    import O4_Qt_Settings as QTSET

    window.prefs["zl"] = 17
    dialog = QTSET.SettingsWindow(window.prefs, [], window.output_dir(), window)
    try:
        # #1985: the zoom is Imagery's row; Detail sits under the cards.
        assert dialog.detail_combo is dialog.imagery_zoom_row.combo
        assert dialog.detail_combo.currentText() == "17"
        dialog.detail_combo.setCurrentText("18")
        assert dialog.result_prefs()["zl"] == 18
        layout = dialog.layout()
        items = [layout.itemAt(i).widget() for i in range(layout.count())]
        assert items.index(dialog.airport_detail_row) == \
            items.index(dialog.preset_cards) + 1
    finally:
        dialog.deleteLater()


def test_qt_general_sections_are_the_manifest(window):
    import O4_Qt_Settings as QTSET

    dialog = QTSET.SettingsWindow(window.prefs, [], window.output_dir(), window)
    try:
        layout = dialog.content_layout
        widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
        titles = [w.title if hasattr(w, "title") else "Provider Accounts"
                  for w in widgets if w in dialog._app_sections]
        # Provider Accounts shows only with a provider needing one, as on
        # the Mac (``if !providerAccounts.isEmpty``).
        assert titles == list(GENERAL_SECTIONS[:len(titles)])
        assert len(titles) >= 2
        dialog.show()
        dialog.category_list.setCurrentRow(0)  # General
        assert dialog.application_section.isVisible()
        dialog.category_list.setCurrentRow(1)
        assert not dialog.application_section.isVisible()
    finally:
        dialog.deleteLater()


def test_qt_application_rows_are_the_manifest(window):
    import O4_Qt_Settings_General as GENERAL

    section = GENERAL.ApplicationSection("")
    try:
        rows = []
        for i in range(section.layout_.count()):
            item = section.layout_.itemAt(i).layout()
            if item is not None and item.itemAt(0).widget() is not None:
                rows.append(item.itemAt(0).widget().text())
        assert [row for row in rows if row != "Status"] == list(APPLICATION_ROWS)
    finally:
        section.deleteLater()


def test_qt_console_header_is_the_manifest(window):
    drawer = window.console_drawer
    header = drawer.layout().itemAt(0).layout()
    expected = [getattr(drawer, attr) for _key, _marker, attr in CONSOLE_HEADER]
    widgets = [header.itemAt(i).widget() for i in range(header.count())]
    assert [w for w in widgets if w in expected] == expected
    assert getattr(drawer.history, HISTORY_DATE_FILTER[1]).currentData() == "all"


# ── the Airports explanations sit behind an "i" (owner 2026-10-27) ────
def test_both_airports_cards_hide_the_explanations_behind_an_i(window):
    swift = (SWIFT / "BuildAirportsCard.swift").read_text(encoding="utf-8")
    assert swift.count("infoButton($showing") == 2
    assert "if showingGradeInfo { caption(Self.gradeSentence) }" in swift
    card = window.airports_card
    card.fit_disabled_reason = lambda: None
    card._render()
    assert not card.grade_text.isVisibleTo(card)
    assert not card.fit_text.isVisibleTo(card)
    card.grade_info.setChecked(True)
    card.fit_info.setChecked(True)
    assert card.grade_text.isVisibleTo(card)
    assert card.fit_text.isVisibleTo(card)
    card.fit_info.setChecked(False)
    card.fit_disabled_reason = lambda: "Needs airport grading on."
    card._render()
    assert card.fit_text.isVisibleTo(card)          # a reason always shows


def test_both_patch_panels_say_checking_while_the_scan_runs(window):
    import O4_Qt_Patch_Controller as QTPC

    assert QTPC.absence(False, True) == QTPC.PatchController.CHECKING
    assert QTPC.absence(False, False) == QTPC.PatchController.NO_PATCH
    assert QTPC.absence(True, True) == QTPC.PatchController.NO_PATCH
    window._scanning = True
    assert window.patch_editor.controller.is_scanning()
    swift = (SWIFT / "PatchInspector.swift").read_text(encoding="utf-8")
    panel = (Path(GUI.__file__).with_name("O4_Qt_Patch_Panel.py")
             .read_text(encoding="utf-8"))
    sentence = "Checking which tiles are built…"
    assert sentence in swift and sentence in panel


def _parked_tiles_table():
    """The tiles table, parked with the developer tools (11k (3) waits):
    no window shows it, so the test makes one."""
    import O4_Qt_Library as QTLIB

    return QTLIB.LibraryTilesSection(None, "", "")


def test_the_patch_library_has_one_home_in_each_app(window):
    """#1699 phase 2: every patch-library control the Mac app shows, the
    Qt window shows too (and the reverse, by the manifest)."""
    owners = {"airports_card": window.airports_card,
              "library_tiles": _parked_tiles_table()}
    for key, swift_file, marker, owner, attr in PATCH_LIBRARY:
        assert marker in (SWIFT / swift_file).read_text(encoding="utf-8"), key
        assert getattr(owners[owner], attr, None) is not None, key
    card = window.airports_card.layout()
    assert card.indexOf(window.airports_card.library_match_list) == \
        card.indexOf(window.airports_card.airports_text) + 1


def test_imagery_on_demand_has_one_home_in_each_app(window):
    """#1992 P4: the follow line, the pins and "Make all low-res again"
    are in both apps (and, by the manifest, nowhere else)."""
    import O4_Qt_Library_Storage as QTLIBSTORE
    import O4_Qt_Settings_Storage as QTSTORE

    rows = QTLIBSTORE.StorageRows("")
    owners = {"window": window,
              "library_tiles": _parked_tiles_table(),
              "storage": QTSTORE.StorageSection(),
              "budget_box": rows.budget_box}
    for key, swift_file, marker, owner, attr in IMAGERY_ON_DEMAND:
        assert marker in (SWIFT / swift_file).read_text(encoding="utf-8"), key
        assert getattr(owners[owner], attr, None) is not None, key
    pane = (SWIFT / "BuildPane.swift").read_text(encoding="utf-8")
    # The follow line left the Build pane for Fly (10j); the pin follows
    # the imagery check.
    assert "ImageryFollowLine(model:" not in pane
    assert window.follow_line.parentWidget() is window.fly_pane
    assert pane.index("TilePinRow(pinned:") > pane.index("TileImageryFreshnessRow(")
    form = window._info_layout
    assert (form.getWidgetPosition(window.tile_pin_row)[0]
            == form.getWidgetPosition(window.imagery_freshness_row)[0] + 1)


def test_both_tile_panes_show_the_path_under_built_by(window):
    """#1987: the tile folder (links resolved) and its reveal button sit
    under "Built by" in both apps, titled alike."""
    import O4_Qt_Tile_Path_Row as QTPATHROW

    pane = (SWIFT / "BuildPane.swift").read_text(encoding="utf-8")
    marker, attr = TILE_PATH_ROW
    assert pane.index(marker) > pane.index('detailRow("Built by"')
    row = (SWIFT / "TilePathRow.swift").read_text(encoding="utf-8")
    assert 'static let title = "%s"' % QTPATHROW.ROW_TITLE in row
    assert isinstance(getattr(window, attr, None), QTPATHROW.TilePathRow)


def test_both_tile_panes_name_the_airports_the_build_stood_on(window):
    """Owner 2026-11-12T21:55Z (lane ltiledetail): "Airport elevation" and
    "Graded airports" sit after the Path row in both apps, titled alike,
    shown only when the tile's records name them."""
    import O4_Qt_GUI as QTGUI

    pane = (SWIFT / "BuildPane.swift").read_text(encoding="utf-8")
    for title in (QTGUI.TILE_AIRPORT_ELEVATION_TITLE,
                  QTGUI.TILE_AIRPORTS_TITLE):
        assert '"%s"' % title in pane
    assert (pane.index("Self.airportElevationTitle, text")
            > pane.index(TILE_PATH_ROW[0]))
    form = window._info_layout
    path_row = form.getWidgetPosition(window.tile_path_row)[0]
    assert form.getWidgetPosition(window.info_airport_elevation)[0] > path_row
    window._show_build_airports(None)
    assert not form.isRowVisible(window.info_airports)


def test_both_tile_panes_read_the_world_pack_first(window):
    """Owner 2026-11-12T20:23Z (lane ltilepane): the World-pack row stands
    right under the tile title in both apps, with the same three actions;
    a tile the World pack holds reads "(in the World pack)", never "(not
    built)"."""
    import O4_Qt_Tile_World_Row as QTWORLDROW
    import O4_World_State_Text as WORLD_TEXT
    from o4_engine.world_state import WorldTile

    pane = (SWIFT / "BuildPane.swift").read_text(encoding="utf-8")
    title = pane.index('Text("Tile \\(active.key)')
    assert title < pane.index("TileWorldRow(coord:") < pane.index('detailRow("Imagery"')
    assert "O4WorldStateText.titleInWorld" in pane
    row = (SWIFT / "TileWorldRow.swift").read_text(encoding="utf-8")
    for name in ("rebuildButton", "removeButton", "removeTitle", "removeMessage",
                 "removeConfirm"):
        assert "O4WorldStateText.%s" % name in row
    assert "O4TilePackageCopy.exportTitle" in row
    package = (SWIFT.parent / "SceneryKit" / "TilePackage.swift").read_text(encoding="utf-8")
    assert 'exportTitle = "%s"' % QTWORLDROW.EXPORT_BUTTON in package
    form = window._info_layout
    assert (form.getWidgetPosition(window.tile_world_row)[0]
            == form.getWidgetPosition(window.info_title)[0] + 1)
    window.map.set_world({(30, 31): WorldTile("full", "xptb", 1.0, "originals", "")})
    window._active_changed((30, 31))
    assert WORLD_TEXT.TITLE_IN_WORLD in window.info_title.text()
    assert not window.tile_world_row.isHidden()
    assert window.tile_world_row.status_label.text() == (
        "Built (in the World pack): mesh + full imagery")
    assert not window.tile_world_row.actions.isHidden()
    window._active_changed((30, 33))
    assert WORLD_TEXT.TITLE_IN_WORLD not in window.info_title.text()
    assert window.tile_world_row.isHidden()


def test_both_maps_share_the_tile_legend_and_the_stale_row(window):
    """#1958: one key (the same kinds in the same order; owner
    2026-11-12T22:05Z: one pill in the Build and Fly views) and one
    "Airport packs" row under the Path row, with the same rebuild words,
    in both apps."""
    import O4_Map_Key_Text as KEYTEXT
    import O4_Qt_Map_Legend as QTLEGEND
    import O4_Qt_Tile_Stale_Row as QTSTALEROW

    key = (SWIFT / "MapKey.swift").read_text(encoding="utf-8")
    kinds = key[key.index("static func buildItems"):key.index("static func flyItems")]
    swift_kinds = re.findall(r'present\.insert\("(\w+)"\)', kinds)
    python_kinds = [QTLEGEND.WORLD_FULL, QTLEGEND.WORLD_MESH, QTLEGEND.WORLD_DRAPE,
                    QTLEGEND.WORLD_PLACEHOLDER,
                    QTLEGEND.WORLD_OTHER_TOOL, QTLEGEND.BUILT, QTLEGEND.OTHER,
                    QTLEGEND.STALE, QTLEGEND.EXTERNAL, QTLEGEND.CUSTOM_PATCH]
    assert swift_kinds == python_kinds
    assert set(python_kinds) <= set(KEYTEXT.SHORT)
    canvas = (SWIFT / "MapCanvasView.swift").read_text(encoding="utf-8")
    assert canvas.index("zoomChip\n") < canvas.index("MapKey(buildModel:")
    wire = (SWIFT.parent / "SceneryKit" / "TileStalenessWire.swift").read_text(
        encoding="utf-8")
    for name, value in (("rowTitle", QTSTALEROW.ROW_TITLE),
                        ("rebuildNote", QTSTALEROW.REBUILD_NOTE),
                        ("rebuildButton", QTSTALEROW.REBUILD_BUTTON)):
        assert 'static let %s = "%s"' % (name, value) in wire
    pane = (SWIFT / "BuildPane.swift").read_text(encoding="utf-8")
    assert pane.index("TileStaleRow(stale:") > pane.index("TilePathRow(info:")
    assert isinstance(getattr(window, "tile_stale_row", None),
                      QTSTALEROW.TileStaleRow)
    view = (SWIFT / "MapCanvasView.swift").read_text(encoding="utf-8")
    assert "#BF5AF2" in view and QTLEGEND.STALE_COLOR == "#BF5AF2"


def test_both_libraries_filter_patches_alike():
    """#1958: the patch library's filter — same keys, words and states —
    in the Mac section and the Qt box, both from ``scan.FILTERS``."""
    import O4_Qt_Patch_Library as QTLIB
    from patch_library import scan as SCAN

    view = (SWIFT / "PatchLibraryView.swift").read_text(encoding="utf-8")
    swift = re.findall(r'\("(\w+)", "([^"]+)", \[([^\]]*)\]\)', view)
    assert [(k, label, set(re.findall(r'"(\w+)"', st))) for k, label, st in swift] == \
        [(k, label, set(st)) for k, label, st in SCAN.FILTERS]
    assert 'Picker("Show"' in view
    box = QTLIB.PatchLibraryBox("")
    assert [box.filter_combo.itemData(i) for i in range(box.filter_combo.count())] == \
        [k for k, _l, _s in SCAN.FILTERS]


def test_on_demand_hides_the_same_rows_in_both_apps(window):
    """RULINGS 2026-11-10e (1): under imagery on demand both Build boxes
    hide "When it's done" and its two switches, and both behave as on."""
    import O4_Qt_Build_OnDemand as QTONDEMAND_BUILD

    block = _block(SWIFT / "BuildPane.swift", ON_DEMAND_GUARD, "DisclosureGroup(")
    for key, marker, _attr in ON_DEMAND_HIDDEN:
        assert marker in block, key
    assert QTONDEMAND_BUILD.HIDDEN == tuple(a for _k, _m, a in ON_DEMAND_HIDDEN)
    window.show()
    window.chk_auto_install.setChecked(False)
    window.chk_skip_built.setChecked(False)
    QTONDEMAND_BUILD.apply(window, True)
    assert not any(getattr(window, a).isVisible() for a in QTONDEMAND_BUILD.HIDDEN)
    assert QTONDEMAND_BUILD.installs(window)
    assert QTONDEMAND_BUILD.skips_built(window)
    assert not QTONDEMAND_BUILD.skips_built(window, rebuild=True)
    QTONDEMAND_BUILD.apply(window, False)
    assert all(getattr(window, a).isVisible() for a in QTONDEMAND_BUILD.HIDDEN)
    assert not QTONDEMAND_BUILD.installs(window)
    assert not QTONDEMAND_BUILD.skips_built(window)
    window.chk_skip_built.setChecked(True)
    assert QTONDEMAND_BUILD.skips_built(window, rebuild=True)


def test_on_demand_rebuild_hint_is_the_macs():
    import O4_Qt_Build_OnDemand as QTONDEMAND_BUILD

    swift = (SWIFT / "BuildModel+OnDemandBuild.swift").read_text(encoding="utf-8")
    said = re.search(r'static let onDemandRebuildHint = "([^"]+)"', swift)
    assert said and said.group(1) == QTONDEMAND_BUILD.REBUILD_HINT


# ─── the two modes (RULINGS 2026-11-11k, spec §14) ─────────────────────────

def _swift_rows(path: Path, start: str, rows) -> list:
    block = (SWIFT / path).read_text(encoding="utf-8")
    block = block[block.index(start):]
    return [block.find(marker) for _key, marker, _attr in rows]


def test_mac_mode_panes_are_the_manifest():
    marks = _swift_rows("MapMainView.swift", "struct ModePanes", MODE_PANES)
    assert -1 not in marks and marks == sorted(marks), marks
    offer = _swift_rows("MapMainView.swift", "struct ModePanes",
                        [("offer", FLY_OFFER[0], None)])[0]
    assert -1 < offer < marks[0], "the Fly offer stands above the pane"
    fly = _swift_rows("FlyPane.swift", "struct FlyPane", FLY_PANE)
    assert -1 not in fly and fly == sorted(fly), fly
    main = (SWIFT / "MapMainView.swift").read_text(encoding="utf-8")
    assert "LibraryPane(" not in main and "LibraryTilesSection(" not in main
    assert not (SWIFT / "LibraryPane.swift").exists()


def test_mac_settings_storage_holds_the_storage_rows():
    """11k (2): the data folder, the budget, Convert and Caches lead
    Settings ▸ Storage, above its cleanup settings."""
    rows = _swift_rows("LibraryStorage.swift", "struct StorageSettingsRows",
                       STORAGE_ROWS)
    end = (SWIFT / "LibraryStorage.swift").read_text(encoding="utf-8")
    end = end[end.index("struct StorageSettingsRows"):].index("struct DataFolderRow")
    assert -1 not in rows and rows == sorted(rows) and rows[-1] < end, rows
    pane = _block(SWIFT / "SettingsView.swift",
                  "private struct CategoryPane", "private struct ExpertSection")
    assert 'category.key == "storage"' in pane and "StorageSettingsRows()" in pane
    assert "StoragePointer" not in pane


def _laid_out(widget) -> list:
    layout = widget.layout()
    return [layout.itemAt(i).widget() for i in range(layout.count())
            if layout.itemAt(i).widget() is not None]


def test_qt_mode_panes_are_the_manifest(window):
    stack = window.mode_stack
    panes = [stack.widget(i) for i in range(stack.count())]
    # Fly scrolls in its own area; Build is its scroll area.
    shown = [panes[0]] + [scroll.widget() for scroll in panes[1:]]
    assert shown == [getattr(window, attr) for _k, _m, attr in MODE_PANES]
    side = _laid_out(window.side_panel)
    assert side.index(getattr(window, FLY_OFFER[1])) < side.index(stack)
    fly = _laid_out(window.fly_pane)
    rows = [getattr(window.fly_pane, attr) for _k, _m, attr in FLY_PANE]
    assert [w for w in fly if w in rows] == rows
    assert not hasattr(window, "library_pane")
    assert not hasattr(window, "map_split")


def test_qt_settings_storage_holds_the_storage_rows(window, monkeypatch):
    """11k (2): Settings ▸ Storage shows the rows, in the manifest's order,
    and measures the data folder the first time it is shown."""
    import O4_Qt_Library_Storage as QTLIBSTORE
    import O4_Qt_Settings as QTSET

    measured = []
    monkeypatch.setattr(QTLIBSTORE.StorageRows, "refresh",
                        lambda self: measured.append(True))
    dialog = QTSET.SettingsWindow(window.prefs, [], window.output_dir(), window)
    try:
        section = dialog.storage_section
        assert isinstance(section, QTLIBSTORE.StorageRows)
        laid = _laid_out(section)
        assert laid == [getattr(section, attr) for _k, _m, attr in STORAGE_ROWS]
        dialog.show()
        dialog.category_list.setCurrentRow(
            [key for key, _title in QTSET.SM.CATEGORIES].index("storage"))
        assert section.isVisible() and measured
        assert section.matches("budget") and section.matches("cache")
    finally:
        dialog.deleteLater()


def test_the_library_storage_rows_have_one_home_in_each_app(window):
    import O4_Qt_Library_Storage as QTLIBSTORE
    import O4_Qt_World_Onboard as QTONBOARD

    assert "QTONBOARD.check_at_launch(" in Path(GUI.__file__).read_text(encoding="utf-8")
    rows = QTLIBSTORE.StorageRows("")
    owners = {"onboard": QTONBOARD,
              "caches_box": rows.caches_box,
              "budget_box": rows.budget_box}
    for key, swift_file, marker, owner, attr in LIBRARY_STORAGE:
        assert marker in (SWIFT / swift_file).read_text(encoding="utf-8"), key
        assert getattr(owners[owner], attr, None) is not None, key


def test_the_disk_budget_is_not_a_settings_row_in_either_app():
    import O4_Settings_Model as SM
    swift = (SWIFT / "SettingsLayout.swift").read_text(encoding="utf-8")
    rows = {member[0] for _key, _title, members in SM._LAYOUT for member in members}
    for name in STORAGE_BOX_SETTINGS:
        assert name not in rows and 'SettingItem("%s"' % name not in swift, name


def test_qt_modes_swap_the_pane_and_keep_the_selection(window, monkeypatch):
    import O4_App_Modes as MODES

    monkeypatch.setattr(GUI, "save_prefs", lambda prefs: None)
    window.map.set_selection({(47, -123), (47, -122)})
    assert window.mode() == MODES.DEFAULT          # nothing remembered yet
    for mode in ("fly", "build"):
        window.set_mode(mode)
        assert window.mode() == mode
        assert window.mode_stack.currentIndex() == MODES.MODES.index(mode)
        assert window.prefs[MODES.PREF_KEY] == mode
        assert window.map.selection() == {(47, -123), (47, -122)}
    window.panel_toggle.setChecked(False)
    window.set_mode("build")
    assert window.panel_toggle.isChecked()      # a chosen mode shows its pane


def test_qt_offers_fly_and_never_switches(window, monkeypatch):
    from types import SimpleNamespace as NS

    import O4_Qt_Modes as QTMODES

    monkeypatch.setattr(GUI, "save_prefs", lambda prefs: None)
    window.show()
    loaded = NS(state="following", xplane=True, flight_loads=0)
    window._on_imagery_follow_status(loaded)
    assert window.fly_offer.isVisible() and window.mode() == "build"
    window.fly_offer.open_btn.click()
    assert window.mode() == "fly" and not window.fly_offer.isVisible()
    assert QTMODES.ModeSwitch("fly").mode() == "fly"
    assert QTMODES.ModeSwitch("library").mode() == "build"   # retired (11k)
    assert QTMODES.ModeSwitch("nonsense").mode() == "build"


def test_both_fly_maps_stack_the_layers_alike():
    """The manifest's layers, in drawing order, in both apps (#2001)."""
    swift = (SWIFT / "FlyMapOverlay.swift").read_text(encoding="utf-8")
    swift = swift[swift.index("Canvas {"):]
    qt = (Path(GUI.__file__).with_name("O4_Qt_Fly_Layer.py")
          .read_text(encoding="utf-8"))
    qt = qt[qt.index("def paint("):]
    for source, column in ((swift, 1), (qt, 2)):
        marks = [source.find(row[column]) for row in FLY_MAP_LAYERS]
        assert -1 not in marks and marks == sorted(marks), (column, marks)


def test_the_package_actions_have_one_home_in_each_app(window):
    """#2014: Export Package… in both File menus and both tile menus, with
    the same words; the install sheet's and the airport-first export
    window's words are the Qt dialog's (the kinds' names, explanations and
    figures are the engine's, ``tile_bundle.kinds``, in both)."""
    import O4_Qt_Tile_Menu as QTTILEMENU
    import O4_Qt_Tile_Package as QTPKG

    for key, swift_file, marker, owner, attr in TILE_PACKAGE:
        assert marker in (SWIFT / swift_file).read_text(encoding="utf-8"), key
        assert getattr({"window": window, "package": QTPKG}[owner], attr, None) is not None, key
    assert "LIB.package_estimate(" in inspect.getsource(QTPKG.export)
    kit = (SWIFT.parent / "SceneryKit" / "TilePackage.swift").read_text(encoding="utf-8")
    for name, qt in (("exportTitle", QTPKG.EXPORT_TITLE), ("installTitle", QTPKG.INSTALL_TITLE),
                     ("install", QTPKG.INSTALL), ("keepMine", QTPKG.KEEP_MINE),
                     ("useTheirs", QTPKG.USE_THEIRS), ("combineTitle", QTPKG.COMBINE_TITLE),
                     ("airportLabel", QTPKG.AIRPORT_LABEL),
                     ("wholeTileOnly", QTPKG.WHOLE_TILE_ONLY),
                     ("estimateNote", QTPKG.ESTIMATE_NOTE),
                     ("intoPack", QTPKG.INTO_PACK), ("objectsLabel", QTPKG.OBJECTS_LABEL),
                     ("objectsDefault", QTPKG.OBJECTS_DEFAULT),
                     ("objectsFinal", QTPKG.OBJECTS_FINAL),
                     ("objectsApplied", QTPKG.OBJECTS_APPLIED),
                     ("applyFixes", QTPKG.APPLY_FIXES)):
        said = re.search(r'static let %s = "([^"]+)"' % name, kit)
        assert said and said.group(1) == qt, name
    owners = window.export_package_action.associatedObjects()
    assert "&File" in [getattr(o, "title", lambda: "")() for o in owners]
    menu = QTTILEMENU.tile_menu(window, 30, 31, "", export_package=lambda: None)
    assert menu.actions()[-1].text() == QTPKG.EXPORT_TITLE


def test_both_maps_show_the_map_controls_in_order(window):
    """#2016: zoom out, zoom in, then "Center on aircraft", top-right, in
    both maps."""
    view = (SWIFT / "MapCanvasView.swift").read_text(encoding="utf-8")
    body = view[view.index("private var zoomControls"):]
    at = [body.index(marker) for _key, marker, _attr in MAP_CONTROLS]
    assert at == sorted(at)
    assert ".overlay(alignment: .topTrailing) { zoomControls }" in view
    controls = window.map.controls
    buttons = [getattr(controls, attr) for _key, _marker, attr in MAP_CONTROLS]
    layout = controls.layout()
    order = [layout.indexOf(b) for b in buttons]
    assert -1 not in order and order == sorted(order)
