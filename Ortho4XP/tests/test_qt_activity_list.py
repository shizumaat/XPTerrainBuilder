"""Issue #1537, RULINGS 2026-10-28n: the run list is a native item view
whose own selection model is the map's tile selection, both ways, with
the Activity and Completed sections as its collapsible items; no custom
row fill is left.  The map keeps its focus ring in the palette highlight.

The list-edit rule itself (``O4_Activity_Order.list_edit``) is twin-tested
against the Mac app in ``test_activity_order.py``; these tests drive a
run's rows and the map selection offscreen (the seam of
``test_qt_activity_keep.py``).
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Activity_List as QTACT  # noqa: E402
import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Selection_Ring as RING  # noqa: E402
from PySide6.QtCore import QItemSelectionModel  # noqa: E402
from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import QAbstractItemView, QApplication  # noqa: E402

A, B, C = (47, -123), (48, -6), (49, -6)
SETTINGS = {"provider": "BI", "zoomlevel": 15, "do_vector": True,
            "do_imagery": True, "do_overlays": False}
SRC = os.path.join(os.path.dirname(__file__), "..", "src")


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    path = str(tmp_path / "prefs.json")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        json.dump({}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", path)
    import O4_UI_Utils as UI
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    win.prefs["output_dir"] = str(tmp_path)
    win.prefs[GUI.AUTO_INSTALL_KEY] = False
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win._session, "enqueue_build",
                        lambda tiles, **kwargs: True)
    monkeypatch.setattr(win._session, "boundary_airports",
                        lambda tiles=None: None)
    monkeypatch.setattr(win, "_after", lambda ms, callback: None)
    try:
        yield win
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def test_the_map_ring_is_the_palette_highlight(qapp):
    palette = QPalette()
    palette.setColor(QPalette.Highlight, QColor("#123456"))
    assert RING.ring_color(palette) == QColor("#123456")


def test_the_list_is_a_native_multi_selection_view(window):
    listed = window.activity_list
    assert isinstance(listed, QAbstractItemView)
    assert listed.selectionMode() == QAbstractItemView.ExtendedSelection
    # Section headers are items the view collapses, never selectable.
    assert listed.sections() == [listed.activity_item, listed.completed_item]
    for section in listed.sections():
        assert not section.flags() & GUI.Qt.ItemIsSelectable


def test_the_map_selection_shows_in_the_list(window):
    window._start_run([A, B, C], dict(SETTINGS))
    listed = window.activity_list
    window.map.set_selection([A, B])
    assert listed.selected_tiles() == {A, B}
    window.map.set_selection([A, B, C])    # every row: every row shows it
    assert listed.selected_tiles() == {A, B, C}
    window.map.set_active(*C)              # a plain map click: C alone
    assert listed.selected_tiles() == {C}
    window.map.clear_selection()
    assert listed.selected_tiles() == set()


def _select(listed, tiles, flags):
    model = listed.selectionModel()
    for tile in tiles:
        index = listed.indexFromItem(listed._items[tile])
        model.select(index, flags)


def test_a_selection_made_in_the_list_is_the_map_selection(window,
                                                           monkeypatch):
    framed = []
    monkeypatch.setattr(window, "_show_tile_on_map",
                        lambda tile: (framed.append(tile),
                                      window.map.set_active(*tile)))
    window._start_run([A, B, C], dict(SETTINGS))
    listed = window.activity_list
    window.map.set_selection([A])
    window.map.set_active(*A, select=False)
    # A click on B (the selection model's ClearAndSelect): B alone,
    # active, framed.
    _select(listed, [B], QItemSelectionModel.ClearAndSelect)
    assert window.map.selection() == {B}
    assert window.map.active_tile() == B
    assert framed == [B]
    # ⌘/Ctrl-click adds C: both selected, C active, nothing framed.
    _select(listed, [C], QItemSelectionModel.Select)
    assert window.map.selection() == {B, C}
    assert window.map.active_tile() == C
    assert framed == [B]
    # Clearing the list's selection clears the map's.
    listed.clearSelection()
    assert window.map.selection() == set()


def test_rows_move_between_sections_and_keep_their_selection(window):
    window._start_run([A, B], dict(SETTINGS))
    window.map.set_selection([A, B])
    from o4_engine import events as EV
    window._on_tile_state(EV.TileState(lat=A[0], lon=A[1], state="done",
                                       percent=100.0))
    listed = window.activity_list
    assert listed.section_tiles(GUI.ACTORDER.COMPLETED) == [A]
    assert listed.completed_item.text(0) == QTACT.completed_title(1)
    assert not listed.completed_item.isHidden()
    assert listed.selected_tiles() == {A, B}
    # The row widget moved with its tile: it is still the tile's own.
    assert listed.itemWidget(listed._items[A], 0).row() is (
        window._tile_rows[A][2])


def test_rows_take_the_styles_item_margins(window):
    window._start_run([A], dict(SETTINGS))
    row = window._tile_rows[A][2]
    margins = row.layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(),
            margins.bottom()) == QTACT.row_margins(row.style())


def test_no_custom_row_fill_is_left():
    """RULINGS 2026-10-28n: no custom fill, ring or box-spanning code is
    left for the rows; the selection is the view's own."""
    assert not os.path.exists(os.path.join(SRC, "O4_Qt_Click_Row.py"))
    assert not os.path.exists(os.path.join(SRC, "O4_Qt_Completed.py"))
    for name in ("O4_Qt_GUI.py", "O4_Qt_Activity_List.py",
                 "O4_Qt_Row_Status.py", "O4_Qt_Selection_Ring.py"):
        with open(os.path.join(SRC, name), encoding="utf-8") as handle:
            text = handle.read()
        for symbol in ("ClickableRow", "fill_color", "span_box",
                       "apply_fills", "set_filled", "filled_rows"):
            assert symbol not in text, (name, symbol)
