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
    ("imagery_preview", 'Picker("Imagery Preview"', "map_provider_combo"),
    ("scenery_filter", 'Picker("Scenery"', "scenery_filter_combo"),
    ("search", "ToolbarSearchField(", "search_edit"),
    ("side_panel", 'Image(systemName: "sidebar.trailing")', "panel_toggle"),
)

#: The Build box's controls, top to bottom: (key, Swift label, Qt attribute).
#: A Swift label is a ``Toggle``/``Picker`` title literal or its glossary
#: term.  The Detail level (#1242) and the per-tile texture and elevation
#: levels (#1243) are NOT here: both apps set them in Settings only.
BUILD_BOX = (
    ("imagery", "Imagery", "imagery_combo"),
    ("terrain_steps", "terrain_steps", "chk_vector"),
    ("imagery_and_scenery_file", "imagery_and_scenery_file", "chk_imagery"),
    ("xplane_objects", "xplane_objects", "chk_overlays"),
    ("fit_buildings", "fit_buildings", "chk_modify_airports"),
    ("skip_built", "Skip already-built tiles", "chk_skip_built"),
    # Label differs on purpose: Qt's fixed 280 px panel cannot fit the
    # Mac's "Install finished tiles automatically" (a checkbox cannot
    # elide), so Qt says "Auto-install finished tiles".
    ("auto_install", "Install finished tiles automatically", "chk_auto_install"),
)

#: The build-cost panel (#820): last in the Build box, just above Build —
#: (Swift marker, Qt window attribute).
PLAN_PANEL = ("PlanEstimatePanel(", "plan_panel")

#: Settings ▸ General's app-level sections, top to bottom (#1267), and the
#: Application section's rows (#1266: the Data Folder chooser).  The Mac's
#: Appearance picker is a recorded exception: Qt follows the system theme.
GENERAL_SECTIONS = ("Application", "Build Engine", "Provider Accounts")
APPLICATION_ROWS = ("Version", "X-Plane Folder", "Data Folder")


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


def test_mac_plan_panel_closes_the_build_box():
    block = _block(SWIFT / "BuildPane.swift",
                   "private var buildBox: some View",
                   "// MARK: - Imagery-source conflict")
    marker = block.find(PLAN_PANEL[0])
    assert marker != -1, "the Mac Build box lost its cost panel"
    assert marker > block.rfind("Toggle("), "the cost panel must follow the toggles"


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


def test_mac_settings_holds_the_detail_level():
    general = _block(SWIFT / "SettingsView.swift",
                     "private struct GeneralPane", "private func pathText")
    assert 'Picker(O4Glossary.term("detail")' in general


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
        assert dialog.detail_combo.currentText() == "17"
        dialog.detail_combo.setCurrentText("18")
        assert dialog.result_prefs()["zl"] == 18
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
