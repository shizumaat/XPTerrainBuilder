"""Issue #1537: Activity rows of selected tiles wear the map's focus ring.

The rule (``O4_Qt_Selection_Ring.ringed_rows``) is twin-tested against
the Mac app's ``SelectionRing.rings`` through
``fixtures/selection_ring_cases.json``; the window test drives a run's
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

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Selection_Ring as RING  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

CASES = os.path.join(os.path.dirname(__file__), "fixtures",
                     "selection_ring_cases.json")
A, B, C = (47, -123), (48, -6), (49, -6)


def _cases():
    with open(CASES, encoding="utf-8") as handle:
        return json.load(handle)["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["name"])
def test_rings_like_the_mac_twin(case):
    assert RING.ringed_rows(case["rows"], set(case["selected"]),
                            case["active"]) == case["rings"]


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_the_ring_is_the_palette_highlight(qapp):
    palette = QPalette()
    palette.setColor(QPalette.Highlight, QColor("#123456"))
    assert RING.ring_color(palette) == QColor("#123456")


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


def _rings(window):
    return {tile: row[2].ring() for tile, row in window._tile_rows.items()}


def test_rows_ring_with_the_selection(window):
    window._start_run([A, B, C], {"provider": "BI", "zoomlevel": 15,
                                  "do_vector": True, "do_imagery": True,
                                  "do_overlays": False})
    window.map.set_selection([A, B, C])
    window.map.set_active(*A, select=False)
    assert _rings(window) == {A: None, B: None, C: None}
    window.map.set_selection([A, B])
    window.map.set_active(*B, select=False)
    assert _rings(window) == {A: RING.OTHER, B: RING.ACTIVE, C: None}
    window.map.set_active(*C)   # a plain click: C alone
    assert _rings(window) == {A: None, B: None, C: RING.ACTIVE}
    window.map.clear_selection()
    assert _rings(window) == {A: None, B: None, C: None}


def test_a_ringed_row_paints_the_highlight(window):
    window._start_run([A, B], {"provider": "BI", "zoomlevel": 15,
                               "do_vector": True, "do_imagery": True,
                               "do_overlays": False})
    window.map.set_active(*A)
    row = window._tile_rows[A][2]
    assert row.ring() == RING.ACTIVE
    row.resize(200, 60)
    image = QImage(row.size(), QImage.Format_ARGB32)
    image.fill(0)
    row.render(image)
    edge = image.pixelColor(100, RING.GLOW_REACH + 1)
    assert edge.rgb() == RING.ring_color(row.palette()).rgb()
