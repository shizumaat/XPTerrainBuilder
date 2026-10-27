"""Issue #1537: Activity and Completed rows of selected tiles are filled;
the map keeps its focus ring in the palette highlight.

Which rows fill (``O4_Activity_Order.filled_rows``) is twin-tested against
the Mac app in ``test_activity_order.py``; the window tests drive a run's
rows and the map selection offscreen (the seam of
``test_qt_activity_keep.py``).
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Click_Row as ROW  # noqa: E402
import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Selection_Ring as RING  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

A, B, C = (47, -123), (48, -6), (49, -6)
SETTINGS = {"provider": "BI", "zoomlevel": 15, "do_vector": True,
            "do_imagery": True, "do_overlays": False}


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_the_map_ring_is_the_palette_highlight(qapp):
    palette = QPalette()
    palette.setColor(QPalette.Highlight, QColor("#123456"))
    assert RING.ring_color(palette) == QColor("#123456")


def _palette(window, base):
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(window))
    palette.setColor(QPalette.Base, QColor(base))
    return palette


@pytest.mark.parametrize("window_color, base, fill", [
    ("#353535", "#2a2a2a", "#151515"),   # dark: near-black
    ("#2a2a2a", "#2a2a2a", "#151515"),   # dark, Base as the box
    ("#efefef", "#ffffff", "#ffffff"),   # light: white
    ("#efefef", "#efefef", "#f7f7f7"),   # light, Base as the box
])
def test_the_fill_raises_contrast(qapp, window_color, base, fill):
    color = ROW.fill_color(_palette(window_color, base))
    assert color == QColor(fill)
    box = QColor(window_color)
    if box.lightness() < 128:
        assert color.lightness() < box.lightness()
    else:
        assert color.lightness() > box.lightness()


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


def _fills(window):
    return {tile: row[2].filled() for tile, row in window._tile_rows.items()}


def test_rows_fill_with_the_selection(window):
    window._start_run([A, B, C], dict(SETTINGS))
    window.map.set_selection([A, B, C])
    assert _fills(window) == {A: False, B: False, C: False}
    window.map.set_selection([A, B])
    assert _fills(window) == {A: True, B: True, C: False}
    window.map.set_active(*C)   # a plain click: C alone
    assert _fills(window) == {A: False, B: False, C: True}
    window.map.clear_selection()
    assert _fills(window) == {A: False, B: False, C: False}


def test_a_filled_row_paints_the_fill(window):
    window._start_run([A, B], dict(SETTINGS))
    window.map.set_active(*A)
    row = window._tile_rows[A][2]
    assert row.filled()
    row.resize(200, 60)
    image = QImage(row.size(), QImage.Format_ARGB32)
    image.fill(0)
    row.render(image)
    inside = image.pixelColor(100, 2)
    assert inside.rgb() == ROW.fill_color(row.palette()).rgb()
