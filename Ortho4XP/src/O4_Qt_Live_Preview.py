"""The map's "Live flight preview" in the Qt window (#2001): each visible
texture square drawn from the imagery installed for X-Plane.  The Mac
app's ``LivePreviewModel.swift`` is the same; the engine owns the rule
and the DDS read (``o4_engine.live_preview_commands``), this draws.

* :meth:`LivePreview.set_view` -- the map moved: the squares of the
  viewport are asked again (``live_preview_squares``) after
  :data:`SETTLE_MS` of quiet.
* :meth:`LivePreview.follow_landed` -- an ``ImageryFollowStatus``'s
  ``landed`` count; when it grows a tier landed and the squares are
  asked again (a square whose ``stamp`` changed is fetched again).
* :meth:`LivePreview.world_swapped` -- a ``WorldStatus``'s
  ``last_swap``; when it changes build-ahead put a tile in (#2020) and
  the squares are asked again.
* :meth:`LivePreview.paint` outlines the squares at full resolution
  (``sharp``) in ``outline``'s color (the legend's ``sharp``).
* Missing images are fetched (``live_preview_mip``) a few per event-loop
  turn, at most :data:`PUMP_BUDGET_S` each, so the window never stalls.
* At most ``O4_Live_Preview.APP_CACHE_IMAGES`` images are kept, the
  least recently listed dropped first; a square keeps its old image
  until the new one arrives.
"""

from __future__ import annotations

import base64
import time
from collections import OrderedDict

import O4_Live_Preview as LIVE
from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QImage

__all__ = ["LivePreview", "PUMP_BUDGET_S", "SETTLE_MS"]

#: Quiet after a map move before the squares are asked again.
SETTLE_MS = 200
#: Time spent fetching images per event-loop turn.
PUMP_BUDGET_S = 0.04


class LivePreview(QObject):
    """See the module docstring.  ``run(name, **arguments)`` is the
    window's command table."""

    changed = Signal()

    def __init__(self, run, parent=None) -> None:
        super().__init__(parent)
        self._run = run
        self.enabled = False
        self.view = None
        self.squares: list = []
        self.images: "OrderedDict[str, tuple]" = OrderedDict()
        self.pending: list = []
        self._landed = None
        self._swap = None
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self.refresh)
        self._pump_timer = QTimer(self)
        self._pump_timer.setSingleShot(True)
        self._pump_timer.setInterval(0)
        self._pump_timer.timeout.connect(self._pump)

    def set_enabled(self, on: bool) -> None:
        self.enabled = bool(on)
        if self.enabled:
            self.refresh()
        else:
            self.squares, self.pending = [], []
            self.images.clear()
            self.changed.emit()

    def set_view(self, south, west, north, east, px_per_deg) -> None:
        self.view = (south, west, north, east, px_per_deg)
        if self.enabled:
            self._settle.start()

    def follow_landed(self, landed) -> None:
        if landed != self._landed:
            self._landed = landed
            if self.enabled:
                self.refresh()

    def world_swapped(self, last_swap) -> None:
        """A ``WorldStatus``'s ``last_swap``: build-ahead put a tile in
        (a quick photo, a parked aircraft's full-detail core, #2020), so
        the squares are asked again."""
        token = tuple(last_swap or ())
        if token != self._swap:
            self._swap = token
            if self.enabled:
                self.refresh()

    def refresh(self) -> None:
        """Ask the engine for the viewport's squares."""
        if not self.enabled or self.view is None:
            return
        south, west, north, east, px_per_deg = self.view
        try:
            reply = self._run("live_preview_squares", south=south, west=west,
                              north=north, east=east, px_per_deg=px_per_deg)
        except Exception as error:      # noqa: BLE001 -- the map has no preview
            print("Live flight preview: %s" % error)
            reply = None
        self.squares = list((reply or {}).get("squares", []))
        for square in self.squares:
            if square["key"] in self.images:
                self.images.move_to_end(square["key"])
        self.pending = [s for s in self.squares if not self._current(s)]
        self.changed.emit()
        if self.pending:
            self._pump_timer.start()

    def _current(self, square) -> bool:
        held = self.images.get(square["key"])
        return bool(held) and held[0] == square["stamp"] and held[1] >= square["px"]

    def _pump(self) -> None:
        start = time.monotonic()
        fetched = False
        while self.pending and time.monotonic() - start < PUMP_BUDGET_S:
            square = self.pending.pop(0)
            try:
                mip = self._run("live_preview_mip", path=square["path"],
                                px=square["px"])
                image = QImage.fromData(base64.b64decode(mip["data"]))
            except Exception:           # noqa: BLE001 -- a texture being replaced
                continue
            if image.isNull():
                continue
            self.images[square["key"]] = (square["stamp"], square["px"], image)
            self.images.move_to_end(square["key"])
            while len(self.images) > LIVE.APP_CACHE_IMAGES:
                self.images.popitem(last=False)
            fetched = True
        if fetched:
            self.changed.emit()
        if self.pending:
            self._pump_timer.start()

    def paint(self, painter, point, outline=None) -> None:
        """Draw the squares that have an image; ``point(lat, lon)`` is the
        map's viewport point; ``outline`` (a pen) marks the full-
        resolution ones."""
        if not self.enabled:
            return
        sharp = []
        for square in self.squares:
            held = self.images.get(square["key"])
            if not held:
                continue
            rect = QRectF(point(square["north"], square["west"]),
                          point(square["south"], square["east"])).normalized()
            painter.drawImage(rect, held[2])
            if square.get("sharp"):
                sharp.append(rect)
        if outline is not None and sharp:
            painter.setPen(outline)
            painter.setBrush(Qt.NoBrush)
            for rect in sharp:
                painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))
