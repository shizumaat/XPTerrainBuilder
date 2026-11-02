"""#1736: a tile being built draws as building on the Qt map, whatever is
on disk -- never the built border of a DSF an earlier build left.  The Mac
twin is ``ActivitySectionsTests.testABuildingTileStaysInActivityUntilItsTerminal``
(``BuildActivityModel.isBuilding``, drawn by ``MapCanvasView``)."""

import os
import sys
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

pytest.importorskip("PySide6")

import O4_Qt_Map as QTMAP  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

TILE = (60, 11)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def view(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        QTMAP, "livemap_cache_dir", lambda: str(tmp_path / "livemap")
    )
    v = QTMAP.MapView()
    v._start_workers = lambda: None
    v._update_timer.stop()
    yield v
    v.deleteLater()


@pytest.mark.parametrize("state,label,building", [
    ("queued", "queued", True),
    ("active", "Imagery", True),
    ("indeterminate", "Imagery", True),
    ("done", "", False),
    ("error", "failed", False),
    ("stopped", "stopped", False),
    ("queued", "stopped", False),     # drained by the engine
])
def test_a_live_row_is_building(view, state, label, building):
    view.set_progress({TILE: (state, label, 40.0)})
    assert view.is_building(TILE) is building


def test_no_row_is_not_building(view):
    assert view.is_building(TILE) is False


def _built_border_drawn(view):
    painter = mock.MagicMock()
    with mock.patch.object(view, "_draw_progress_badge"):
        view._draw_tile_overlay(painter, TILE, 1.0)
    return painter.drawRect.called


def test_a_building_tile_has_no_built_border(view):
    # A DSF from an earlier build is on disk: the scan reads it as built.
    view.set_built({TILE: object()})
    assert _built_border_drawn(view)
    view.set_progress({TILE: ("active", "Imagery", 40.0)})
    assert not _built_border_drawn(view)
    view.set_progress({TILE: ("done", "", 100.0)})
    assert _built_border_drawn(view)
