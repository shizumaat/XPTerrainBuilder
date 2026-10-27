"""The Qt console drawer's per-tile view and Build History (#1226, Q139).

Offscreen: the console filters to the map selection (run-level lines
stay), a selected tile with no lines this session shows its newest saved
log, the chip's ✕ shows everything again, the Saved logs menu shows one
build alone, and the one date filter drives the history list and the
map's dimming.  TWIN of the Mac app's BuildConsoleModel / BuildHistory.
"""

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Build_History as QTHIST  # noqa: E402
import O4_Tile_Build_Log as TILELOG  # noqa: E402
from PySide6.QtWidgets import QApplication, QPlainTextEdit  # noqa: E402

WHO = {"tool": "XPTerrainBuilder", "app_version": "1.0.999",
       "engine_version": "1.50.9"}


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _info(build_dir, tile, mesh_date=None):
    return SimpleNamespace(
        build_dir=str(build_dir), mesh_date=mesh_date,
        last_build=TILELOG.last_build(str(build_dir), *tile), built_by="")


@pytest.fixture
def drawer(qapp, tmp_path):
    logs = TILELOG.TileBuildLogs(who=WHO)
    logs.begin((47, -123), str(tmp_path))
    logs.line((47, -123), "saved line of +47-123")
    logs.finish((47, -123), "ok")
    built = {(47, -123): _info(tmp_path, (47, -123)),
             (48, -123): _info(tmp_path, (48, -123), mesh_date=1.0)}
    selected = []
    dimmed = []
    console = QPlainTextEdit()
    console.setMaximumBlockCount(5000)
    widget = QTHIST.ConsoleDrawer(
        console, lambda: built, lambda lat, lon: selected.append((lat, lon)),
        dimmed.append)
    widget.test_selected, widget.test_dimmed = selected, dimmed
    yield widget
    widget.deleteLater()


def test_unfiltered_console_shows_everything_as_it_comes(drawer):
    drawer.append_text("[+10+020] one\n=== run line ===\n[+11+021] tw")
    drawer.append_text("o\n")
    assert drawer.console.toPlainText() == (
        "[+10+020] one\n=== run line ===\n[+11+021] two\n")


def test_selection_filters_and_keeps_run_level_lines(drawer):
    drawer.append_text("[+10+020] one\n=== run line ===\n[+11+021] two\n")
    drawer.set_selection({(10, 20)}, (10, 20))
    assert drawer.console.toPlainText() == "[+10+020] one\n=== run line ===\n"
    assert drawer.chip.isVisibleTo(drawer)
    assert drawer.chip_label.text() == "Showing +10+020"
    drawer.append_text("[+11+021] three\n[+10+020] four\n")
    assert drawer.console.toPlainText().endswith("[+10+020] four\n")
    assert "three" not in drawer.console.toPlainText()
    drawer.chip_clear_btn.click()
    assert "three" in drawer.console.toPlainText()
    assert not drawer.chip.isVisibleTo(drawer)


def test_selected_tile_without_lines_shows_its_saved_log(drawer):
    drawer.set_selection({(47, -123), (48, -123)}, (47, -123))
    text = drawer.console.toPlainText()
    assert "=== +47-123: saved log of the build of" in text
    assert "saved line of +47-123" in text
    assert "=== +48-123: Log not saved (built before logging) ===" in text


def test_saved_logs_menu_shows_one_build_alone(drawer):
    drawer.append_text("[+47-123] live line\n")
    drawer.set_selection({(47, -123)}, (47, -123))
    assert drawer.saved_logs_btn.isEnabled()
    drawer._fill_saved_logs()
    actions = drawer.saved_logs_menu.actions()
    assert len(actions) == 1 and "Built" in actions[0].text()
    actions[0].trigger()
    text = drawer.console.toPlainText()
    assert "saved line of +47-123" in text and "live line" not in text
    assert drawer.chip_label.text() == "Saved log of +47-123"
    drawer.chip_clear_btn.click()
    assert "live line" in drawer.console.toPlainText()


def test_history_rows_and_date_filter_dim_the_map(drawer):
    drawer.history_btn.setChecked(True)
    texts = [drawer.history.list.item(i).text()
             for i in range(drawer.history.list.count())]
    assert len(texts) == 2
    assert texts[0].split()[1] == "+47-123"           # newest first
    assert "XPTerrainBuilder 1.0.999" in texts[0]
    assert QTHIST.NOT_SAVED in texts[1]
    assert drawer.test_dimmed[-1] == set()
    drawer.history.range_combo.setCurrentIndex(0)      # Today
    assert drawer.history.list.count() == 1
    assert drawer.test_dimmed[-1] == {(48, -123)}
    item = drawer.history.list.item(0)
    drawer.history.list.itemClicked.emit(item)
    assert drawer.test_selected == [(47, -123)]


def test_clear_clears_the_view_only(drawer, tmp_path):
    drawer.append_text("[+47-123] live\n")
    drawer.clear()
    assert drawer.console.toPlainText() == ""
    assert TILELOG.last_build(str(tmp_path), 47, -123) is not None
