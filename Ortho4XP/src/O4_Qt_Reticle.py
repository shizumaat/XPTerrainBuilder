"""The coordinate-search reticle (issue #1317, Qt half; the Mac half is
``SearchReticleOverlay.swift``).

A typed latitude and longitude (:mod:`O4_Coordinate_Query`) centres the map
at ZL 19 and marks the point with a crosshair ring: a white stroke on a
dark halo, so it reads on imagery and on the plain map alike.  It stays
until the next search, or until the search field is cleared (Esc or
deleting the text).
"""

from __future__ import annotations

import typing as _t

from O4_Qt_Map import MERCATOR_LAT
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen

__all__ = ["ReticleLayer"]

RADIUS = 14.0
TICK = 9.0


class ReticleLayer:
    """A map layer (``MapView.add_layer``) that paints the searched point in
    viewport space and never takes the mouse."""

    def __init__(self, map_view) -> None:
        self._map = map_view
        self._point: _t.Optional[tuple[float, float]] = None

    def set_point(self, point) -> None:
        """``(lat, lon)`` to mark, or None to clear."""
        self._point = None if point is None else (float(point[0]), float(point[1]))
        self._map.viewport().update()

    def point(self):
        return self._point

    def path(self) -> QPainterPath:
        """The ring and its four ticks around the point, in viewport space."""
        path = QPainterPath()
        if self._point is None:
            return path
        (lat, lon) = self._point
        lat = max(-MERCATOR_LAT, min(lat, MERCATOR_LAT))
        centre = self._map._viewport_point(lat, lon)
        path.addEllipse(centre, RADIUS, RADIUS)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            path.moveTo(centre + QPointF(dx * (RADIUS - TICK / 2),
                                         dy * (RADIUS - TICK / 2)))
            path.lineTo(centre + QPointF(dx * (RADIUS + TICK),
                                         dy * (RADIUS + TICK)))
        return path

    def paint(self, painter) -> None:
        if self._point is None:
            return
        path = self.path()
        painter.setBrush(Qt.NoBrush)
        for color, width in ((QColor(0, 0, 0, 153), 4.0),
                             (QColor(255, 255, 255), 2.0)):
            pen = QPen(color, width)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawPath(path)

    def mouse_press(self, _event) -> bool:
        return False

    def mouse_move(self, _event) -> bool:
        return False

    def mouse_release(self, _event) -> bool:
        return False

    def viewport_moved(self) -> None:
        pass
