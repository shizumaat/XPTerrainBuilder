"""The patch layer over the Qt map (spec patch-editor-20261015 §4 "Display";
mockup ``docs/mockups/patch-editor-20261015.html``; the Mac app's
``PatchOverlay``).

Fills and strokes by role, node squares where nodes are ≥ 6 px apart, the
legend and the bottom-left chip, viewport-culled.  Shapes are kept per way
as paths in map scene units (drawn through the view transform with cosmetic
pens), rebuilt when the document changes; during a node drag the moved
shapes are skipped here and drawn by the gesture layer
(``O4_Qt_Patch_Gestures``).  The layer is installed on ``MapView`` with
``add_layer``: the map calls :meth:`paint` and offers it the mouse first.
"""
from __future__ import annotations

import typing as _t

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen, QPolygonF

import O4_Geo_Utils as GEO
import O4_Qt_Map as QTMAP
from O4_Qt_Patch_Geometry import DRAW_ORDER, PatchScreenIndex, scene_xy, style_class

__all__ = ["PatchOverlay", "STYLES", "paint_styled"]


def _hex(rgb: int, alpha: float = 1.0) -> QColor:
    return QColor((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF, round(alpha * 255))


#: The mockup's colours per class: (fill, stroke, width, halo).  Widths
#: are the mockup's × 1.5 (owner, #759: "increase the line weight about
#: 50%"); node squares and hit radii are unchanged.
STYLES = {
    "runway": (_hex(0x8A8F99, 0.28), _hex(0xD6DAE2), 2.4, None),
    "taxiway": (_hex(0xD2B14A, 0.22), _hex(0xE6C95C), 2.1, None),
    "apron": (_hex(0x5AA0E0, 0.22), _hex(0x7DB8EF), 2.4, None),
    "building": (_hex(0xB07AD0, 0.25), _hex(0xC497E0), 1.95, None),
    "road": (_hex(0x9FD18B, 0.18), _hex(0x9FD18B), 1.8, _hex(0x9FD18B, 0.35)),
    "ground": (None, _hex(0x9AA4B5, 0.55), 1.2, None),
}
#: The road halo's width (× 1.5 with the strokes).
HALO_WIDTH = 7.5
NODE_FILL = _hex(0x0B0D12)
NODE_STROKE = _hex(0xE7EBF2)
SELECTION = QColor("#FFD60A")
_LEGEND = (("runway", "runway"), ("taxiway", "taxiway"), ("apron", "apron"),
           ("building", "building"), ("road", "road"), ("ground", "graded ground"))
NODE_SIZE = 6.0


def paint_styled(painter, shapes: _t.Iterable[tuple[str, bool, QPainterPath]]) -> None:
    """Fill and stroke ``(style, closed, path)`` in draw order (the base
    layer and the gesture layer's moved shapes)."""
    by_style: dict[str, list] = {}
    for style, closed, path in shapes:
        by_style.setdefault(style, []).append((closed, path))
    for style in DRAW_ORDER:
        fill, stroke, width, halo = STYLES[style]
        for closed, path in by_style.get(style, ()):
            if closed and fill is not None:
                painter.fillPath(path, fill)
            painter.setBrush(Qt.NoBrush)
            if halo is not None:
                pen = QPen(halo, HALO_WIDTH)
                pen.setCosmetic(True)
                painter.strokePath(path, pen)
            pen = QPen(stroke, width)
            pen.setCosmetic(True)
            painter.strokePath(path, pen)


class _Shape(_t.NamedTuple):
    way: int
    style: str
    closed: bool
    path: QPainterPath         # map scene units
    bounds: QRectF


class PatchOverlay:
    """The patch layer: base drawing here, interaction in ``gestures``."""

    def __init__(self, map_view, controller, outlines=None):
        self.map = map_view
        self.controller = controller
        self.model = controller.model
        self.outlines = outlines
        self.gestures = None            # set by O4_Qt_Patch_Gestures
        self.toolbar = None             # O4_Qt_Patch_Toolbar, pinned top-left
        self.index: PatchScreenIndex | None = None
        self._shapes: list[_Shape] = []
        self.model.document_changed.connect(self._rebuild)
        self.model.selection_changed.connect(self.update)
        self.model.status_changed.connect(self.update)
        controller.state_changed.connect(self.update)
        if outlines is not None:
            outlines.changed.connect(self.update)

    def update(self) -> None:
        self.map.viewport().update()

    @property
    def showing(self) -> bool:
        return self.controller.is_showing

    # ─── geometry ──────────────────────────────────────────────────────
    def _rebuild(self) -> None:
        doc = self.model.doc
        if doc is None:
            self.index, self._shapes = None, []
            self.update()
            return
        self.index = PatchScreenIndex(doc, self.model.patch.identity_dp, QTMAP.SCENE_ZL)
        shapes = []
        for w, way in enumerate(doc.ways):
            path = self.way_path(way.refs, lambda r: self._scene(r))
            if path is None:
                continue
            shapes.append(_Shape(w, style_class(way.tags), way.closed, path, path.boundingRect()))
        rank = {s: k for k, s in enumerate(DRAW_ORDER)}
        self._shapes = sorted(shapes, key=lambda s: (rank[s.style], s.way))
        self.update()

    def _scene(self, nid: int) -> QPointF | None:
        k = self.index.row.get(nid)
        return None if k is None else QPointF(float(self.index.x[k]), float(self.index.y[k]))

    @staticmethod
    def way_path(refs, point: _t.Callable[[int], QPointF | None]) -> QPainterPath | None:
        pts = [p for p in (point(r) for r in refs) if p is not None]
        if len(pts) < 2:
            return None
        path = QPainterPath()
        path.addPolygon(QPolygonF(pts))
        if len(refs) > 2 and refs[0] == refs[-1]:
            path.closeSubpath()
        return path

    def transform(self) -> tuple[float, float, float, float]:
        t = self.map.viewportTransform()
        return (t.m11(), t.m22(), t.dx(), t.dy())

    def lat_lon(self, p: QPointF) -> tuple[float, float]:
        """The ground under a viewport point."""
        scene = self.map.viewportTransform().inverted()[0].map(QPointF(p))
        return GEO.pix_to_wgs84(scene.x(), scene.y(), QTMAP.SCENE_ZL)

    def screen_of(self, lat: float, lon: float) -> QPointF:
        x, y = scene_xy(lat, lon, QTMAP.SCENE_ZL)
        sx, sy, dx, dy = self.transform()
        return QPointF(float(x) * sx + dx, float(y) * sy + dy)

    # ─── drawing ───────────────────────────────────────────────────────
    def paint(self, painter) -> None:
        if not self.showing or self.index is None:
            return
        vp = self.map.viewport().rect()
        self.index.project(self.transform())
        skip = self.gestures.skip if self.gestures is not None else None
        view_t = self.map.viewportTransform()
        visible = view_t.inverted()[0].mapRect(QRectF(vp))
        if self.outlines is not None:
            self.outlines.paint(painter, view_t)
        painter.save()
        painter.setTransform(view_t)
        paint_styled(painter, ((s.style, s.closed, s.path) for s in self._shapes
                               if (skip is None or s.way not in skip.ways)
                               and s.bounds.intersects(visible)))
        painter.restore()
        self._paint_nodes(painter, vp.width(), vp.height(), skip.nodes if skip else ())
        if self.gestures is not None and self.model.mode == "Edit":
            self.gestures.paint(painter)
        self._paint_legend(painter)

    def _paint_nodes(self, painter, width: float, height: float, skip) -> None:
        half = NODE_SIZE / 2
        painter.setPen(QPen(NODE_STROKE, 1.2))
        painter.setBrush(NODE_FILL)
        for x, y in self.index.visible_nodes(width, height, skip):
            painter.drawRect(QRectF(x - half, y - half, NODE_SIZE, NODE_SIZE))

    def _panel_font(self, painter, size: float) -> None:
        font = QFont(painter.font())
        font.setPointSizeF(size)
        painter.setFont(font)

    def _paint_legend(self, painter) -> None:
        rows = [(STYLES[k][1], label, False) for k, label in _LEGEND]
        if self.outlines is not None and self.outlines.enabled:
            from O4_Qt_Pack_Outlines import OUTLINE_COLOR
            rows.append((OUTLINE_COLOR, "pack apt.dat", True))
        painter.save()
        self._panel_font(painter, 10)
        fm = painter.fontMetrics()
        line = fm.height() + 3
        width = max(fm.horizontalAdvance(r[1]) for r in rows) + 40
        vp = self.map.viewport().rect()
        box = QRectF(vp.right() - width - 10, 44, width, line * len(rows) + 10)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 115))
        painter.drawRoundedRect(box, 8, 8)
        for k, (color, label, dashed) in enumerate(rows):
            y = box.top() + 5 + k * line
            swatch = QRectF(box.left() + 9, y + (line - 8) / 2 - 1, 14, 8)
            if dashed:                  # the pack outlines' swatch (#1316)
                from O4_Qt_Pack_Outlines import LEGEND_FILL
                pen = QPen(color, 1.5)
                pen.setDashPattern([3, 2])
                painter.setPen(pen)
                painter.setBrush(LEGEND_FILL)
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
            painter.drawRoundedRect(swatch, 2, 2)
            painter.setPen(QColor(255, 255, 255, 217))
            painter.drawText(QRectF(box.left() + 29, y, width - 30, line),
                             Qt.AlignVCenter | Qt.AlignLeft, label)
        painter.restore()

    def viewport_moved(self) -> None:
        """The map scrolled or resized: re-pin the toolbar."""
        if self.toolbar is not None:
            self.toolbar.place()

    # ─── the map offers the mouse first ────────────────────────────────
    def _editing(self) -> bool:
        return self.showing and self.gestures is not None and self.model.mode == "Edit"

    def mouse_press(self, event) -> bool:
        return self._editing() and self.gestures.press(event)

    def mouse_move(self, event) -> bool:
        return self._editing() and self.gestures.move(event)

    def mouse_release(self, event) -> bool:
        return self._editing() and self.gestures.release(event)
