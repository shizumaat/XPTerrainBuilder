"""The favorite star on the Qt map (#1992, RULINGS 2026-11-10c (1)): a
yellow five-pointed star in the bottom-right corner of a favorite tile's
square (``TileInfo.pinned``), as ``MapCanvasView.swift`` draws it.

Sized in SCREEN points (11-20, a sixth of the square) and converted back
into scene units, like the mixed-imagery badge, so it stays legible at
every zoom.  Drawn only once the square is big enough to carry it.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainterPath, QPen

__all__ = ["STAR_COLOR", "MIN_SQUARE_PX", "draw_star", "star_points"]

STAR_COLOR = "#FFD60A"
#: Below this square size on screen the star is not drawn.
MIN_SQUARE_PX = 14.0


def star_points(cx: float, cy: float, radius: float):
    """The ten corners of a five-pointed star centred on ``(cx, cy)``, the
    first point straight up (y grows downward)."""
    inner = radius * 0.45
    return [(cx + (radius if k % 2 == 0 else inner) * math.sin(k * math.pi / 5),
             cy - (radius if k % 2 == 0 else inner) * math.cos(k * math.pi / 5))
            for k in range(10)]


def draw_star(painter, r, px: float, scale: float) -> None:
    """The star in the bottom-right corner of tile rect ``r`` (scene
    units); ``px`` is the square's width on screen, ``scale`` screen
    points per scene unit."""
    if px <= MIN_SQUARE_PX:
        return
    size = min(max(px * 0.16, 11.0), 20.0) / max(scale, 1e-12)
    corners = star_points(r.right() - size * 0.7, r.bottom() - size * 0.7,
                          size * 0.5)
    path = QPainterPath()
    path.moveTo(QPointF(*corners[0]))
    for point in corners[1:]:
        path.lineTo(QPointF(*point))
    path.closeSubpath()
    outline = QPen(QColor(15, 23, 32, 200))
    outline.setCosmetic(True)
    outline.setWidth(1)
    painter.setPen(outline)
    painter.setBrush(QColor(STAR_COLOR))
    painter.drawPath(path)
