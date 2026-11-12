"""The map's tile-state band (``O4_Tile_Band`` / ``O4_Qt_Tile_Band``; Mac:
SceneryKit ``TileBand``): the band sits inside its tile, neighbours never
overlap, the gradient fades inward, small tiles fall back to a line, the
numbers are the Mac's, and a green tile among pink ones shows green along
all four inner edges (owner 2026-11-12T22:01Z, HECA)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Tile_Band as BAND  # noqa: E402
import pytest  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SWIFT = REPO / "Sources" / "SceneryKit" / "TileBand.swift"


def _camel(name: str) -> str:
    head, *rest = name.lower().split("_")
    return head + "".join(part.title() for part in rest)


def test_the_numbers_are_the_macs():
    text = SWIFT.read_text(encoding="utf-8", newline="\n")
    swift = {k: float(v) for k, v in re.findall(
        r"static let (\w+): (?:CGFloat|Double) = ([0-9.]+)", text)}
    python = {_camel(n): float(getattr(BAND, n)) for n in BAND.__all__
              if isinstance(getattr(BAND, n), float)}
    assert python and swift == python


def test_the_band_scales_within_its_limits_and_small_tiles_get_a_line():
    assert BAND.band_for(100) == BAND._Band(BAND.BAND, 1.5, 6.0)
    assert BAND.band_for(BAND.GRADIENT_MIN_PX).width == BAND.WIDTH_MIN_PT
    assert BAND.band_for(5000).width == BAND.WIDTH_MAX_PT
    assert BAND.band_for(20) == BAND._Band(BAND.LINE, BAND.INSET_PT, BAND.LINE_WIDTH_PT)
    assert BAND.band_for(5) == BAND._Band(BAND.LINE, 0.0, BAND.TINY_LINE_PT)
    # every form stays inside half the tile
    for px in (2, 5, 10, 20, 39, 40, 80, 200, 2000):
        b = BAND.band_for(px)
        assert 0 <= b.inset and b.inset + b.width <= px / 2


def test_the_band_is_inside_its_tile_and_neighbours_never_overlap():
    b = BAND.band_for(120)
    a = BAND.trapezoids(0, 0, 120, 120, b.inset, b.width)
    n = BAND.trapezoids(120, 0, 240, 120, b.inset, b.width)
    xs_a = [x for poly, _, _ in a for x, _ in poly]
    xs_n = [x for poly, _, _ in n for x, _ in poly]
    assert min(xs_a) == b.inset and max(xs_a) == 120 - b.inset
    assert max(xs_a) < min(xs_n)


def test_the_gradient_runs_from_the_edge_toward_the_centre():
    b = BAND.band_for(120)
    for _poly, outer, inner in BAND.trapezoids(0, 0, 120, 120, b.inset, b.width):
        d_outer = abs(outer[0] - 60) + abs(outer[1] - 60)
        d_inner = abs(inner[0] - 60) + abs(inner[1] - 60)
        assert d_outer - d_inner == pytest.approx(b.width)


def test_installed_line_sits_inside_the_band():
    b = BAND.band_for(200)
    assert BAND.inner_inset(200) == b.inset + b.width + BAND.INNER_GAP_PT
    assert BAND.inner_inset(20) == pytest.approx(0.6)


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _paint_3x3(px):
    """A 3 x 3 block of tiles ``px`` wide: the centre full (green), the
    rest drape (pink); painted by the Build map's World states."""
    import O4_Qt_Map_World as QTWORLD
    from o4_engine import world_state as WS
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter
    rows = [[la, lo, WS.FULL if (la, lo) == (1, 1) else WS.DRAPE, "", 0, "", ""]
            for la in range(3) for lo in range(3)]
    world = QTWORLD.from_wire(rows)
    image = QImage(3 * px, 3 * px, QImage.Format_ARGB32)
    image.fill(QColor("black"))
    painter = QPainter(image)
    QTWORLD.paint_world(painter, world, list(world),
                        lambda la, lo: QRectF(lo * px, la * px, px, px), 1.0)
    painter.end()
    return image


def _greenish(color) -> bool:
    return color.green() > 2 * color.red() and color.green() > 60


def _pinkish(color) -> bool:
    return color.red() > 2 * color.green() and color.red() > 60


@pytest.mark.parametrize("px", [24, 120])
def test_a_green_tile_among_pink_shows_green_along_all_four_inner_edges(qapp, px):
    image = _paint_3x3(px)
    b = BAND.band_for(px)
    d = int(b.inset + 1)          # one point into the band / line
    lo, hi = px, 2 * px - 1
    mid = px + px // 2
    edges = {"top": (mid, lo + d), "bottom": (mid, hi - d),
             "left": (lo + d, mid), "right": (hi - d, mid)}
    for name, (x, y) in edges.items():
        assert _greenish(image.pixelColor(x, y)), (name, image.pixelColor(x, y).name())
    # the neighbours' pink stays on their side of the shared edge
    assert _pinkish(image.pixelColor(mid, lo - d - 1))
    assert _pinkish(image.pixelColor(lo - d - 1, mid))
    # and the fade: the tile's centre is untouched
    assert image.pixelColor(mid, mid).name() == "#000000"
