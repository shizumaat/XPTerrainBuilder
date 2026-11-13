"""The Favorite star on the Qt Build map (#2033; #1992, RULINGS 2026-11-10c
(1)): a five-pointed star in the TOP-RIGHT corner of every built tile's
square -- filled yellow on a favorite (``TileInfo.pinned``), outlined on
the others -- that a click toggles, as ``MapCanvasView.swift`` draws it
(``FavoriteStar``).

Sized in SCREEN points (11-20, a sixth of the square) and converted back
into scene units, like the mixed-imagery badge, so it stays legible at
every zoom.  Drawn, and clickable, only once the square is big enough to
carry it (:data:`MIN_SQUARE_PX`).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen

__all__ = ["STAR_COLOR", "MIN_SQUARE_PX", "hit", "draw_star"]

STAR_COLOR = "#FFD60A"
#: Below this square size on screen the star is not drawn.
MIN_SQUARE_PX = 14.0


def _star_points(cx: float, cy: float, radius: float):
    """The ten corners of a five-pointed star centred on ``(cx, cy)``, the
    first point straight up (y grows downward)."""
    inner = radius * 0.45
    return [(cx + (radius if k % 2 == 0 else inner) * math.sin(k * math.pi / 5),
             cy - (radius if k % 2 == 0 else inner) * math.cos(k * math.pi / 5))
            for k in range(10)]


def _star_box(r, px: float, scale: float):
    """``(cx, cy, size)`` of the star in tile rect ``r`` (scene units), or
    None when the square (``px`` wide on screen; ``scale`` screen points
    per scene unit) is too small to carry it."""
    if px <= MIN_SQUARE_PX:
        return None
    size = min(max(px * 0.16, 11.0), 20.0) / max(scale, 1e-12)
    return r.right() - size * 0.7, r.top() + size * 0.7, size


def hit(r, px: float, scale: float, point) -> bool:
    """Does scene ``point`` fall on the star of tile rect ``r``?"""
    box = _star_box(r, px, scale)
    if box is None:
        return False
    cx, cy, size = box
    return abs(point.x() - cx) <= size * 0.7 and abs(point.y() - cy) <= size * 0.7


def draw_star(painter, r, px: float, scale: float, pinned: bool = True) -> None:
    """The star of tile rect ``r``: filled for a favorite, outlined
    otherwise."""
    box = _star_box(r, px, scale)
    if box is None:
        return
    cx, cy, size = box
    corners = _star_points(cx, cy, size * 0.5)
    path = QPainterPath()
    path.moveTo(QPointF(*corners[0]))
    for point in corners[1:]:
        path.lineTo(QPointF(*point))
    path.closeSubpath()
    if pinned:
        outline = QPen(QColor(15, 23, 32, 200))
        outline.setWidth(1)
        painter.setBrush(QColor(STAR_COLOR))
    else:
        # A dark halo under the yellow line, so it reads on any imagery.
        halo = QPen(QColor(15, 23, 32, 160))
        halo.setCosmetic(True)
        halo.setWidthF(3.0)
        painter.setPen(halo)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        outline = QPen(QColor(STAR_COLOR))
        outline.setWidthF(1.4)
    outline.setCosmetic(True)
    painter.setPen(outline)
    painter.drawPath(path)
