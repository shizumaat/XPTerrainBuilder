"""The Qt map's tile overlay and imagery labels match the Mac app.

- #1256: built and selected tiles are outlined, never tinted: the imagery
  inside a tile is what the user is judging (MapCanvasView.swift strokes
  only).
- #1257: a tile's imagery label falls back to the provider the covering
  ortho pack's files name (MapCanvasLabels.swift), not ``imagery ?``.

Offscreen, no network.
"""

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Map as QTMAP  # noqa: E402
import O4_Qt_Map_Labels as QTLABELS  # noqa: E402
from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

TILE = (47, -6)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def view(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(QTMAP, "livemap_cache_dir", lambda: str(tmp_path))
    v = QTMAP.MapView()
    v._start_workers = lambda: None
    v._update_timer.stop()
    yield v
    v.deleteLater()


def _render_overlay(view, size=200):
    """The tile's overlay drawn over white, the tile filling the image."""
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(QColor("white"))
    rect = view._tile_rect(*TILE)
    scale = size / rect.width()
    painter = QPainter(image)
    painter.scale(scale, size / rect.height())
    painter.translate(-rect.x(), -rect.y())
    view._draw_tile_overlay(painter, TILE, scale)
    painter.end()
    return image


@pytest.mark.parametrize("selected", [False, True])
def test_a_built_tile_is_outlined_not_tinted(view, selected):
    view._built = {TILE: SimpleNamespace(provider="BI", zl=16)}
    view._installed = {TILE}
    if selected:
        view._selection = {TILE}
        view._active = TILE
    image = _render_overlay(view)
    assert image.pixelColor(100, 100) == QColor("white")
    assert image.pixelColor(100, 0) != QColor("white")


def test_a_dashed_selection_is_not_tinted_either(view):
    view._selection = {TILE, (47, -5)}
    view._active = (47, -5)
    image = _render_overlay(view)
    assert image.pixelColor(100, 100) == QColor("white")


def _labels(built, ortho_tiles, ortho_imagery):
    texts = []
    original = QTLABELS._pill
    QTLABELS._pill = lambda _p, text, *_a: texts.append(text)
    try:
        QTLABELS.paint_tile_labels(
            None, lambda lat, lon: QPointF(lon, -lat), 1e6,
            (47.2, 47.8, -5.8, -5.2), lambda lat, lon: "T", built,
            ortho_tiles, 1.0, ortho_imagery)
    finally:
        QTLABELS._pill = original
    return texts[1:]  # after the coordinate pill


def test_another_packs_tile_names_the_packs_imagery():
    assert _labels({}, {TILE}, {TILE: ("GO2", 18)}) == ["GO2 ZL18"]
    assert _labels({}, {TILE}, {}) == ["imagery ?"]


def test_a_built_tile_without_a_provider_borrows_the_packs():
    blank = {TILE: SimpleNamespace(provider="", zl=17, has_zones=False)}
    assert _labels(blank, {TILE}, {TILE: ("BI", None)}) == ["BI ZL17"]
    own = {TILE: SimpleNamespace(provider="EOX", zl=16, has_zones=False)}
    assert _labels(own, {TILE}, {TILE: ("BI", 18)}) == ["EOX ZL16"]


def test_the_map_keeps_the_first_packs_imagery(view):
    view.set_scenery_regions([
        ("A", [TILE], False, "ortho", ("BI", 16)),
        ("B", [TILE], False, "ortho", ("GO2", 18)),
        ("Mesh", [(46, -6)], False, "mesh", None),
    ])
    assert view._ortho_imagery == {TILE: ("BI", 16)}
