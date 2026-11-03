"""The map's rotate cursor (#1746): a circular arrow, white under black so
it reads on any imagery — the Mac app's ``NSCursor.patchRotate``
(``PatchRotateGesture.swift``).  Qt has no stock rotate shape, so it is
drawn once and cached."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QPixmap

__all__ = ["rotate_cursor"]

_CACHE: list[QCursor] = []


def _paths() -> list[QPainterPath]:
    c, r = QPointF(12, 12), 7.0
    arc = QPainterPath()
    # 300 degrees counter-clockwise from 120 to 60 (screen y points down)
    arc.arcMoveTo(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), 120)
    arc.arcTo(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), 120, 300)
    end = QPointF(c.x() + r * math.cos(math.pi / 3), c.y() - r * math.sin(math.pi / 3))
    head = QPainterPath(QPointF(end.x() + 6, end.y()))
    head.lineTo(end)
    head.lineTo(QPointF(end.x() + 3, end.y() + 5))
    return [arc, head]


def rotate_cursor() -> QCursor:
    """The cursor (built on first use: a QPixmap needs the application)."""
    if not _CACHE:
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        for colour, width in ((QColor("#FFFFFF"), 4.0), (QColor("#000000"), 2.0)):
            painter.setPen(QPen(colour, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for path in _paths():
                painter.drawPath(path)
        painter.end()
        _CACHE.append(QCursor(pixmap, 12, 12))
    return _CACHE[0]
