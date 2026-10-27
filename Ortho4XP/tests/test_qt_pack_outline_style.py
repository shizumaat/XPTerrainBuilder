"""Scenery-pack outlines on the patch map (issue #1316): darker, heavier,
long-dashed strokes over a light translucent fill, labelled from ZL 18,
with the label under the cursor in the map's readout.

- The look is ONE set of constants per app; the Mac app's
  ``PackOutlineStyle`` (parsed statically, as ``test_qt_layout_parity``
  reads the Swift sources) and ``O4_Qt_Pack_Outlines`` must agree.
- Only the pack outlines are filled: a tile overlay's interior stays the
  imagery (#1256).

Offscreen, no network, no engine.
"""

import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Map as QTMAP  # noqa: E402
import O4_Qt_Pack_Outlines as POL  # noqa: E402
from O4_Qt_Cursor_Readout import readout_text  # noqa: E402
from O4_Qt_Patch_Geometry import scene_xy  # noqa: E402
from PySide6.QtCore import QObject, QRectF, Signal  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

SWIFT = (Path(__file__).resolve().parents[2] / "Sources" / "XPTerrainBuilder"
         / "PatchPackOutlines.swift")
TILE = (47, -6)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


# ─── one look, two apps ───────────────────────────────────────────────────

def _swift_style() -> dict[str, str]:
    text = SWIFT.read_text(encoding="utf-8")
    body = text[text.index("enum PackOutlineStyle {"):]
    return dict(re.findall(r"static let (\w+)(?:: [\w\[\]]+)? = ([^\n]+)", body))


def _num(literal: str) -> float:
    literal = literal.strip()
    return float(int(literal, 16)) if literal.startswith("0x") else float(literal)


@pytest.mark.parametrize("swift, qt", [
    ("strokeRGB", "STROKE_RGB"), ("strokeAlpha", "STROKE_ALPHA"),
    ("lineWidth", "LINE_WIDTH"), ("fillRGB", "FILL_RGB"), ("fillAlpha", "FILL_ALPHA"),
    ("labelMinZL", "LABEL_MIN_ZL"), ("labelPointSize", "LABEL_POINT_SIZE"),
    ("labelBackAlpha", "LABEL_BACK_ALPHA"), ("labelGap", "LABEL_GAP"),
])
def test_the_two_apps_share_one_look(swift, qt):
    assert _num(_swift_style()[swift]) == pytest.approx(float(getattr(POL, qt)))


def test_the_two_apps_share_one_dash():
    dash = _swift_style()["dash"].strip()
    assert tuple(float(v) for v in re.findall(r"[\d.]+", dash)) == tuple(POL.DASH)


def test_darker_heavier_long_dash_and_a_light_fill():
    """#1316's ask, as numbers: darker than the old #9AA4B5 at 0.7 and
    heavier than 1.2 px; the fill light and about 12 %."""
    old = QColor(0x9A, 0xA4, 0xB5)
    assert POL.OUTLINE_COLOR.lightness() < old.lightness()
    assert POL.OUTLINE_COLOR.alphaF() > 0.7
    assert 1.5 <= POL.LINE_WIDTH <= 2.0 and POL.DASH[0] > 5
    assert POL.FILL_COLOR.lightness() > 180 and POL.FILL_ALPHA == pytest.approx(0.12)


# ─── labels and the hit test ──────────────────────────────────────────────

def test_labels_come_from_the_pack():
    ring = [[0, 0], [0, 1], [1, 1]]
    reply = {"pavement": [{"kind": "pavement", "label": "Apron A", "rings": [ring]},
                          {"kind": "boundary", "rings": [ring]}]}
    assert [label for label, _ in POL.pavement_outlines(reply)] == ["Apron A", "boundary"]
    assert POL.file_label("lib/terminals/T1.obj", "object") == "T1.obj"
    assert POL.file_label("lib\\gate.fac", "facade") == "gate.fac"
    assert POL.file_label(None, "facade") == "facade"


class _Model(QObject):
    document_changed = Signal()


def _outlines(on: bool = True) -> POL.PackOutlines:
    out = POL.PackOutlines(SimpleNamespace(), _Model(), QTMAP.SCENE_ZL, enabled=on)
    sq = lambda la, lo, d: [(la, lo), (la, lo + d), (la + d, lo + d), (la + d, lo)]  # noqa: E731
    out.pavement = POL._outlines([("Apron A", [sq(30.0, 31.0, 0.01), sq(30.004, 31.004, 0.002)])],
                                 QTMAP.SCENE_ZL)
    out.footprints = POL._outlines([("T1.obj", [sq(30.001, 31.001, 0.001)])], QTMAP.SCENE_ZL)
    return out


def test_the_label_under_the_cursor_is_the_smallest_outline(qapp):
    out = _outlines()
    assert out.label_at(30.0015, 31.0015) == "T1.obj"           # the building on the apron
    assert out.label_at(30.008, 31.008) == "Apron A"
    assert out.label_at(30.005, 31.005) is None                  # in the apron's hole
    assert out.label_at(29.9, 31.0) is None
    out.enabled = False
    assert out.label_at(30.0015, 31.0015) is None


def test_the_readout_appends_the_pack_label():
    assert readout_text(30.0, 31.0, "12.0 m", "T1.obj").endswith(" · 12.0 m · pack: T1.obj")
    assert "pack" not in readout_text(30.0, 31.0, "12.0 m")


def test_colliding_labels_are_skipped():
    within = QRectF(0, 0, 200, 100)
    kept = POL.place_labels([("a", QRectF(10, 10, 40, 14)), ("b", QRectF(30, 12, 40, 14)),
                             ("c", QRectF(100, 10, 40, 14)), ("d", QRectF(190, 10, 40, 14))],
                            within)
    assert [t for t, _ in kept] == ["a", "c"]                    # b overlaps a, d leaves the view


# ─── what the map paints ──────────────────────────────────────────────────

def _view_transform(lat: float, lon: float, zl: float, size: int) -> QTransform:
    """Centre ``(lat, lon)`` in a ``size`` px image at zoom ``zl``."""
    k = 2.0 ** (zl - QTMAP.SCENE_ZL)
    x, y = scene_xy(lat, lon, QTMAP.SCENE_ZL)
    return QTransform(k, 0, 0, k, size / 2 - float(x) * k, size / 2 - float(y) * k)


def _render(out, zl: float, size: int = 400) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    out.paint(painter, _view_transform(30.0005, 31.008, zl, size))
    painter.end()
    return image


def test_an_outline_is_filled_and_stroked(qapp):
    out = _outlines()
    image = _render(out, 17.0)
    inside = image.pixelColor(200, 200)             # inside the apron; no label at ZL 17
    assert inside.alpha() > 0
    assert inside.alpha() == pytest.approx(round(POL.FILL_ALPHA * 255), abs=2)
    out.enabled = False
    assert _render(out, 17.0).pixelColor(200, 200).alpha() == 0


def test_labels_show_from_zl_18_only(qapp):
    out = _outlines()
    out.pavement = []
    ring = [(30.0, 31.0075), (30.0, 31.0085), (30.001, 31.0085), (30.001, 31.0075)]
    out.footprints = POL._outlines([("T1.obj", [ring])], QTMAP.SCENE_ZL)

    def darkest(image: QImage) -> int:
        """The most opaque pixel near the centre (the label's pill)."""
        return max(image.pixelColor(x, y).alpha() for x in range(190, 211) for y in range(195, 206))
    fill = round(POL.FILL_ALPHA * 255)
    assert darkest(_render(out, 17.5)) <= fill + 2
    assert darkest(_render(out, 18.0)) > 100


def test_a_tile_overlay_stays_unfilled(qapp, monkeypatch, tmp_path):
    """#1256 holds: the fill is the pack outlines' alone."""
    monkeypatch.setattr(QTMAP, "livemap_cache_dir", lambda: str(tmp_path))
    view = QTMAP.MapView()
    view._start_workers = lambda: None
    view._update_timer.stop()
    view.set_built({TILE: SimpleNamespace(provider="BI", zl=16)})
    image = QImage(200, 200, QImage.Format_ARGB32)
    image.fill(QColor("white"))
    rect = view._tile_rect(*TILE)
    scale = 200 / rect.width()
    painter = QPainter(image)
    painter.scale(scale, 200 / rect.height())
    painter.translate(-rect.x(), -rect.y())
    view._draw_tile_overlay(painter, TILE, scale)
    painter.end()
    assert image.pixelColor(100, 100) == QColor("white")
    view.deleteLater()
