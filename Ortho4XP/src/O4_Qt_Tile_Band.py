"""Paints the map's tile-state band (``O4_Tile_Band``, the rule; Mac:
``TileBandDrawing.swift``): the World states, the built tiles and the Fly
view's corridor cells all draw their colour through :func:`paint_bands`.

Thousands of tiles are on screen at a far zoom, where every tile is a
plain line: those are batched, one pen and one ``drawRects`` per colour.
"""
from __future__ import annotations

import O4_Tile_Band as BAND
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPen, QPolygonF

__all__ = ["paint_band", "paint_bands", "paint_outline"]


def paint_band(painter, rect: QRectF, px_per_unit: float, color,
               alpha: float = 1.0, dash=None) -> None:
    """``color``'s band inside ``rect`` (painter units; ``px_per_unit``
    screen points per unit, 1 in viewport space).  ``alpha`` scales the
    colour's opacity (a dimmed tile); ``dash`` a dash pattern drawn as a
    line along the band's outer side (points, as on the Mac)."""
    paint_bands(painter, ((rect, color, alpha, dash),), px_per_unit)


def paint_bands(painter, items, px_per_unit: float) -> None:
    """:func:`paint_band` of each ``(rect, color, alpha, dash)``."""
    scale = max(px_per_unit, 1e-12)
    unit = 1.0 / scale
    lines: dict = {}
    painter.save()
    painter.setPen(Qt.NoPen)
    for rect, color, alpha, dash in items:
        band = BAND.band_for(rect.width() * scale)
        base = QColor(color)
        opacity = base.alphaF() * alpha
        if band.mode == BAND.LINE:
            _add_line(lines, rect, unit, band.inset, band.width, base, opacity, dash)
            continue
        outer = opacity * (BAND.DASHED_OUTER_ALPHA if dash else BAND.OUTER_ALPHA)
        frame = _frame(base, outer, rect.width() * scale, rect.height() * scale, band)
        if frame is not None:
            painter.drawImage(rect, frame)
        else:
            _paint_sides(painter, rect, unit, band, _brushes(base, outer))
        if dash:
            _add_line(lines, rect, unit, band.inset, BAND.DASH_LINE_PT, base, opacity, dash)
    painter.setBrush(Qt.NoBrush)
    for (rgba, width, dash), rects in lines.items():
        painter.setPen(_pen(rgba, width, dash))
        painter.drawRects(rects)
    painter.restore()


def paint_outline(painter, rect: QRectF, px_per_unit: float, color) -> None:
    """A placeholder's faint outline: a TINY_LINE_PT line just inside the
    edge (the Build map's World placeholders draw the same, batched)."""
    lines: dict = {}
    base = QColor(color)
    _add_line(lines, rect, 1.0 / max(px_per_unit, 1e-12), BAND.TINY_LINE_PT / 2,
              BAND.TINY_LINE_PT, base, base.alphaF(), None)
    painter.save()
    painter.setBrush(Qt.NoBrush)
    for (rgba, width, dash), rects in lines.items():
        painter.setPen(_pen(rgba, width, dash))
        painter.drawRects(rects)
    painter.restore()


def _paint_sides(painter, rect, unit, band, brushes) -> None:
    """The band's four mitred sides, each filled with its gradient."""
    for brush, (polygon, _start, _end) in zip(brushes, BAND.trapezoids(
            rect.left(), rect.top(), rect.right(), rect.bottom(),
            band.inset * unit, band.width * unit)):
        painter.setBrush(brush)
        painter.drawConvexPolygon(QPolygonF([QPointF(x, y) for x, y in polygon]))


#: Tiles up to this many pixels draw a cached image of their band (one
#: blit a tile: tiles of a zoom and latitude share a size); larger ones,
#: few on screen, fill their sides.
FRAME_CACHE_MAX_PX = 512
_FRAMES: dict = {}


def _frame(base: QColor, opacity: float, w_px: float, h_px: float, band):
    """The band of a ``w_px`` x ``h_px`` tile as an image, or None."""
    w, h = round(w_px), round(h_px)
    if max(w, h) > FRAME_CACHE_MAX_PX:
        return None
    outer = QColor(base)
    outer.setAlphaF(opacity)
    key = (outer.rgba(), w, h, band.width)
    image = _FRAMES.get(key)
    if image is None:
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        painter.setPen(Qt.NoPen)
        _paint_sides(painter, QRectF(0, 0, w, h), 1.0, band, _brushes(base, opacity))
        painter.end()
        if len(_FRAMES) > 256:
            _FRAMES.clear()
        _FRAMES[key] = image
    return image


#: (rgba, side) -> the side's gradient brush: in object mode its ends are
#: the side's own bounding box, so one brush serves every tile.
_BRUSHES: dict = {}
#: Each side's gradient, outer -> inner, in object coordinates (the order
#: of ``O4_Tile_Band.trapezoids``: top, right, bottom, left).
_SIDE_ENDS = (((0, 0), (0, 1)), ((1, 0), (0, 0)), ((0, 1), (0, 0)), ((0, 0), (1, 0)))


def _brushes(base: QColor, opacity: float) -> list:
    outer = QColor(base)
    outer.setAlphaF(opacity)
    key = outer.rgba()
    found = _BRUSHES.get(key)
    if found is None:
        clear = QColor(base)
        clear.setAlphaF(0.0)
        found = []
        for start, end in _SIDE_ENDS:
            gradient = QLinearGradient(QPointF(*start), QPointF(*end))
            gradient.setCoordinateMode(QLinearGradient.ObjectMode)
            gradient.setColorAt(0.0, outer)
            gradient.setColorAt(1.0, clear)
            found.append(QBrush(gradient))
        if len(_BRUSHES) > 256:
            _BRUSHES.clear()
        _BRUSHES[key] = found
    return found


def _add_line(lines, rect, unit, inset, width, base, opacity, dash) -> None:
    """A stroke ``width`` points wide whose outer side is ``inset`` inside,
    queued under its pen."""
    c = QColor(base)
    c.setAlphaF(opacity)
    d = (inset + width / 2) * unit
    key = (c.rgba(), width, tuple(dash) if dash else None)
    lines.setdefault(key, []).append(rect.adjusted(d, d, -d, -d))


def _pen(rgba: int, width: float, dash) -> QPen:
    pen = QPen(QColor.fromRgba(rgba))
    pen.setCosmetic(True)
    pen.setWidthF(width)
    pen.setJoinStyle(Qt.MiterJoin)
    if dash:  # a QPen's dash is in pen widths; ours in points
        pen.setDashPattern([d / width for d in dash])
    return pen
