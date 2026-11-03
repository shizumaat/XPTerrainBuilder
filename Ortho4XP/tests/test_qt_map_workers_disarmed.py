"""The suite never starts the Qt map's tile-download workers (issue #1786).

Workers left by one test looked up tile.openstreetmap.org during the next
one, and the network guard failed the wrong test.  conftest disarms
``MapView._start_workers`` on the class; this twin pins that."""
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

import O4_Qt_Map as QTMAP  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def test_a_new_map_view_starts_no_tile_workers():
    QApplication.instance() or QApplication([])
    # Compare thread sets, not counts: an unrelated thread may END while
    # the view is built (ubuntu CI saw 3 == 4); none may START.
    before = set(threading.enumerate())
    view = QTMAP.MapView()
    view._start_workers()
    assert QTMAP.MapView._o4_suite_no_workers is True
    assert not set(threading.enumerate()) - before
    view.deleteLater()
