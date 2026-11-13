"""Fly mode's map layer in the Qt window (spec flight-manager-and-world-
20261110 §4.3, §14; #2001; lane U2): the corridor tiles by key item
(#2031: a build under way pulses, a tile not built yet is not drawn), the
route, the aircraft's track and the aircraft, drawn in Fly mode only.
The Mac app's ``FlyMapOverlay.swift`` is the same.  Under them, while
"Live flight preview" is checked, each visible square's installed imagery
(``O4_Qt_Live_Preview``, #2001): asked again when the map moves; "Sharp
photo" (default on) outlines its full-resolution squares.

A map layer (``MapView.add_layer``): paints in viewport space; it takes
a click only when the pane fills From or To from it (#2026).
"""

from __future__ import annotations

import time

import O4_Flight_Plan as FP
import O4_Fly_Layers as LAYERS
import O4_Fly_Text as TEXT
import O4_Map_Key_Text as KEYTEXT
import O4_Qt_Map_Key as QTKEY
import O4_Qt_Tile_Band as QTBAND
from O4_Qt_Flight_Plan import ROUTE_COLOR
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPen, QPolygonF

__all__ = ["FlyLayer", "SHARP_COLOR", "PULSE_MS", "cell_color",
           "AIRCRAFT_COLOR", "AIRCRAFT_FILL", "AIRCRAFT_OUTLINE"]

#: The live preview's "Sharp photo" outline (#2020, #2031: a toggle, not
#: a key item; Mac ``FlyMapOverlay.sharp``).
SHARP_COLOR = QColor(255, 214, 10)                      # #FFD60A
#: The "Building" pulse's repaint interval while a cell is building.
PULSE_MS = 80
#: The track line's color; the aircraft itself is ``O4_Fly_Layers.
#: AIRCRAFT_SYMBOL`` filled white with a dark outline (G1000 style).
AIRCRAFT_COLOR = QColor(10, 132, 255)
AIRCRAFT_FILL = QColor("white")
AIRCRAFT_OUTLINE = QColor(20, 20, 20)


def cell_color(key: str) -> QColor | None:
    """A corridor cell's colour: its map-key item's (``O4_Map_Key_Text.
    FLY_KEY_ITEMS``, #2031; Mac ``FlyMapOverlay.color``); ``None`` for a
    cell with no item (a tile not built yet says nothing)."""
    item = KEYTEXT.FLY_KEY_ITEMS.get(key)
    return None if item is None else QTKEY.item_color(item)


class FlyLayer:
    """See the module docstring.  ``pane`` is the window's
    ``O4_Qt_Fly_Pane.FlyPane``; :attr:`shown` follows the mode."""

    def __init__(self, map_view, pane, preview=None) -> None:
        self._map = map_view
        self._pane = pane
        self.preview = preview
        self.shown = False
        self._pulse = QTimer()
        self._pulse.setInterval(PULSE_MS)
        self._pulse.timeout.connect(self._repaint)
        pane.changed.connect(self._repaint)
        pane.changed.connect(self._sync_pulse)
        pane.chk_live_preview.toggled.connect(lambda _on: self._repaint())
        pane.chk_sharp_photo.toggled.connect(lambda _on: self._repaint())
        if preview is not None:
            pane.changed.connect(
                lambda: preview.world_swapped((pane.world or {}).get("last_swap")))
            preview.changed.connect(self._repaint)
            map_view.view_changed.connect(self._view_moved)
            pane.chk_live_preview.toggled.connect(lambda _on: self._preview_on())

    def set_shown(self, shown: bool) -> None:
        self.shown = bool(shown)
        # ONE key on both views: the map's pill, with the Fly view's items
        # while it shows (owner 2026-11-12T22:05Z).
        self._map.fly_key = self.key_items if self.shown else None
        self._preview_on()
        self._sync_pulse()
        self._repaint()

    def key_items(self) -> list:
        """The key's items on the Fly view (``O4_Map_Key_Text``): every
        cell key's item."""
        return KEYTEXT.ordered(KEYTEXT.FLY_KEY_ITEMS[key] for key, _words in TEXT.LEGEND)

    def _preview_on(self) -> None:
        if self.preview is None:
            return
        self._view_moved()
        self.preview.set_enabled(self.shown and self._pane.chk_live_preview.isChecked())

    def _view_moved(self) -> None:
        """The viewport and its pixels per degree of longitude."""
        if self.preview is None:
            return
        south, north, west, east = self._map.visible_bounds()
        # clamped to the Mercator range: before the map is first laid out
        # its bounds can reach a pole, where the projection is undefined
        mid = max(-85.0, min(85.0, (south + north) / 2))
        px = self._point(mid, west + 1).x() - self._point(mid, west).x()
        self.preview.set_view(south, west, north, east, px)

    def _repaint(self) -> None:
        self._map.viewport().update()

    def _point(self, lat, lon) -> QPointF:
        return self._map._viewport_point(lat, lon)

    def paint(self, painter) -> None:
        if not self.shown:
            return
        if self.preview is not None:
            sharp = None
            if self._pane.chk_sharp_photo.isChecked():
                sharp = QPen(SHARP_COLOR, 1)
                sharp.setCosmetic(True)
            self.preview.paint(painter, self._point, sharp)
        painter.setBrush(Qt.NoBrush)
        pulse = KEYTEXT.building_alpha(time.monotonic())
        # Each cell's colour is the shared band inside its edge
        # (O4_Tile_Band; the Build map's World states draw the same).
        for lat, lon, key in self._pane.cells():
            color = cell_color(key)
            if color is None:
                continue
            rect = QRectF(self._point(lat + 1, lon), self._point(lat, lon + 1))
            if key == "placeholder":
                QTBAND.paint_outline(painter, rect.normalized(), 1.0, color)
                continue
            QTBAND.paint_band(painter, rect.normalized(), 1.0, color,
                              pulse if key in TEXT.BUILDING_KEYS else 1.0)
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
        """The G1000-style airplane (``O4_Fly_Layers.aircraft_symbol``)
        pointing along the track, the same size at every zoom."""
        at = self._point(lat, lon)
        pen = QPen(AIRCRAFT_OUTLINE, 1.5)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(AIRCRAFT_FILL)
        painter.drawPolygon(QPolygonF([
            QPointF(x, y) for x, y in LAYERS.aircraft_symbol(at.x(), at.y(), track_deg)]))
        painter.setBrush(Qt.NoBrush)

    def mouse_press(self, _event) -> bool:
        return False

    def mouse_move(self, _event) -> bool:
        return False

    def mouse_release(self, event) -> bool:
        """A click on a cell in the Fly view fills From / To (#2026);
        anything else falls through to the map."""
        if not self.shown:
            return False
        cell = self._map.clicked_cell(event)
        if cell is None:
            return False
        command = bool(event.modifiers() & Qt.ControlModifier)  # Cmd on macOS
        return self._pane.map_click(cell[0], cell[1], command)

    def pointer_at(self, _pos) -> str | None:
        return None

    def viewport_moved(self) -> None:
        pass

    def _sync_pulse(self) -> None:
        """Repaint on a timer while a cell is building (it pulses)."""
        building = self.shown and any(
            key in TEXT.BUILDING_KEYS for *_tile, key in self._pane.cells())
        if building and not self._pulse.isActive():
            self._pulse.start()
        elif not building:
            self._pulse.stop()
