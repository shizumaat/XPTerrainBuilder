"""Fly mode's map layer in the Qt window (spec flight-manager-and-world-
20261110 §4.3, §14; #2001; lane U2): the corridor tiles by legend, the
route, the aircraft's track and the aircraft, drawn in Fly mode only.
The Mac app's ``FlyMapOverlay.swift`` is the same.  "Live flight preview"
(each square's installed imagery) is a stub behind its checkbox.

A map layer (``MapView.add_layer``): paints in viewport space and never
takes the mouse.
"""

from __future__ import annotations

import math

import O4_Flight_Plan as FP
from O4_Qt_Flight_Plan import ROUTE_COLOR
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen, QPolygonF

__all__ = ["FlyLayer", "LEGEND_COLORS", "AIRCRAFT_COLOR"]

#: The legend's colors (Mac: ``FlyMapOverlay.color``).
LEGEND_COLORS = {"own": QColor(140, 140, 140), "quick": QColor(48, 176, 199),
                 "built": QColor(77, 176, 110), "building": QColor(255, 159, 10)}
AIRCRAFT_COLOR = QColor(10, 132, 255)


class FlyLayer:
    """See the module docstring.  ``pane`` is the window's
    ``O4_Qt_Fly_Pane.FlyPane``; :attr:`shown` follows the mode."""

    def __init__(self, map_view, pane) -> None:
        self._map = map_view
        self._pane = pane
        self.shown = False
        pane.changed.connect(self._repaint)

    def set_shown(self, shown: bool) -> None:
        self.shown = bool(shown)
        self._repaint()

    def _repaint(self) -> None:
        self._map.viewport().update()

    def _point(self, lat, lon) -> QPointF:
        return self._map._viewport_point(lat, lon)

    def paint(self, painter) -> None:
        if not self.shown:
            return
        painter.setBrush(Qt.NoBrush)
        for lat, lon, key in self._pane.cells():
            pen = QPen(LEGEND_COLORS[key], 2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            rect = QRectF(self._point(lat + 1, lon), self._point(lat, lon + 1))
            painter.drawRect(rect.normalized().adjusted(2, 2, -2, -2))
        plan = self._pane.plan
        if plan and plan.get("waypoints"):
            points = [(w["lat"], w["lon"]) for w in plan["waypoints"]]
            self._polylines(painter, FP.route_drawing(points), ROUTE_COLOR, 2.5)
        track = self._pane.track
        self._polylines(painter, track.parts(), AIRCRAFT_COLOR, 2)
        if track.last is not None:
            self._aircraft(painter, *track.last)

    def _polylines(self, painter, parts, color, width) -> None:
        pen = QPen(color, width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        for part in parts:
            painter.drawPolyline(QPolygonF([self._point(lat, lon) for lat, lon in part]))

    def _aircraft(self, painter, lat, lon, track_deg) -> None:
        """A triangle pointing along the track."""
        at = self._point(lat, lon)
        r = math.radians(track_deg)

        def corner(angle, length):
            return QPointF(at.x() + length * math.sin(r + angle),
                           at.y() - length * math.cos(r + angle))
        pen = QPen(QColor("white"), 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(AIRCRAFT_COLOR)
        painter.drawPolygon(QPolygonF([corner(0, 11), corner(2.5, 8), corner(-2.5, 8)]))
        painter.setBrush(Qt.NoBrush)

    def mouse_press(self, _event) -> bool:
        return False

    def mouse_move(self, _event) -> bool:
        return False

    def mouse_release(self, _event) -> bool:
        return False

    def pointer_at(self, _pos) -> str | None:
        return None

    def viewport_moved(self) -> None:
        pass
