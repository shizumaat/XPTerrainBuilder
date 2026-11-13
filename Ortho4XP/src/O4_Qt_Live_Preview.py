"""The map's "Live flight preview" in the Qt window (#2001): each visible
texture square drawn from the imagery installed for X-Plane, at the
resolution the map shows it, marked where X-Plane shows something else
(owner 2026-11-12T19:28Z).  The Mac app's ``LivePreviewModel.swift`` is
the same; the engine owns the rule and the DDS read
(``o4_engine.live_preview_commands``), this draws.

* :meth:`LivePreview.set_view` -- the map moved: the squares of the
  viewport are asked again (``live_preview_squares``, with the screen's
  device pixel ratio) after :data:`SETTLE_MS` of quiet.
* :meth:`LivePreview.follow_landed` -- an ``ImageryFollowStatus``'s
  ``landed`` count; when it grows a tier landed and the squares are
  asked again (a square whose ``stamp`` changed is fetched again).
* :meth:`LivePreview.world_swapped` -- a ``WorldStatus``'s
  ``last_swap``; when it changes build-ahead put a tile in (#2020) and
  the squares are asked again.
* Every command runs on ONE background thread (the command table is
  called in-process: a 4096 px level takes ~0.5 s), results come back
  through a queued signal, so the window never waits.  Images are
  fetched in ``O4_Live_Preview.fetch_plan`` order (coarse first, then
  each square at its own size), with ``wait=True``.
* At most ``O4_Live_Preview.APP_CACHE_MB`` of decoded images are kept
  (``ByteLRU``, the least recently listed dropped first); a square keeps
  its old image until the new one arrives.
* :meth:`LivePreview.paint` outlines the squares at full resolution
  (``sharp``) in ``outline``'s color (the legend's ``sharp``), hatches
  the ``stale`` squares and ``reload`` tiles, and washes the ``own``
  tiles (``O4_Live_Preview_Text``), each labelled when large enough.
"""

from __future__ import annotations

import base64
import threading
from collections import deque

import O4_Live_Preview as LIVE
import O4_Live_Preview_Text as TEXT
from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPen

__all__ = ["LABEL_MIN_PX", "LivePreview", "SETTLE_MS"]

#: Quiet after a map move before the squares are asked again.
SETTLE_MS = 200
#: A mark's words are drawn on a rect at least this wide (points).
LABEL_MIN_PX = 140


class _Worker:
    """The one background thread: the latest squares request first, then
    the fetches in plan order.  ``done(kind, generation, payload)`` is
    called on the thread (the owner re-emits it as a queued signal)."""

    def __init__(self, run, done) -> None:
        self._run, self._done = run, done
        self._cond = threading.Condition()
        self._squares = None            # (generation, arguments)
        self._fetches: deque = deque()  # (generation, square, px)
        self._thread = None

    def ask_squares(self, generation, arguments) -> None:
        with self._cond:
            self._squares = (generation, arguments)
            self._start()
            self._cond.notify()

    def set_fetches(self, generation, plan) -> None:
        with self._cond:
            self._fetches = deque((generation, sq, px) for sq, px in plan)
            if self._fetches:
                self._start()
                self._cond.notify()

    def clear(self) -> None:
        with self._cond:
            self._squares, self._fetches = None, deque()

    def busy(self) -> bool:
        with self._cond:
            return self._squares is not None or bool(self._fetches)

    def _start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="live-preview")
            self._thread.start()

    def _take(self):
        with self._cond:
            if self._squares is None and not self._fetches:
                self._cond.wait(timeout=30.0)
            if self._squares is not None:
                job, self._squares = self._squares, None
                return "squares", job
            if self._fetches:
                return "fetch", self._fetches.popleft()
            return None, None

    def _loop(self) -> None:
        try:
            self._serve()
        except RuntimeError:            # the preview was deleted: stop
            return

    def _serve(self) -> None:
        while True:
            kind, job = self._take()
            if kind == "squares":
                generation, arguments = job
                try:
                    reply = self._run("live_preview_squares", **arguments)
                except Exception as error:      # noqa: BLE001 -- the map has no preview
                    print("Live flight preview: %s" % error)
                    reply = None
                self._done("squares", generation, reply or {})
            elif kind == "fetch":
                generation, square, px = job
                try:
                    mip = self._run("live_preview_mip", path=square["path"],
                                    px=px, wait=True)
                    image = QImage.fromData(base64.b64decode(mip["data"]))
                except Exception:               # noqa: BLE001 -- a texture being replaced
                    continue
                if not image.isNull():
                    self._done("image", generation, (square, px, image))


class LivePreview(QObject):
    """See the module docstring.  ``run(name, **arguments)`` is the
    window's command table."""

    changed = Signal()
    _arrived = Signal(str, int, object)

    def __init__(self, run, parent=None) -> None:
        super().__init__(parent)
        self.enabled = False
        self.view = None
        self.squares: list = []
        self.tiles: list = []
        self._listed: dict = {}
        self.images = LIVE.ByteLRU(LIVE.APP_CACHE_MB << 20)
        self._generation = 0
        self._landed = None
        self._swap = None
        self._arrived.connect(self._on_arrived, Qt.QueuedConnection)
        self._worker = _Worker(run, self._arrived.emit)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self.refresh)

    def set_enabled(self, on: bool) -> None:
        self.enabled = bool(on)
        if self.enabled:
            self.refresh()
        else:
            self._generation += 1
            self._worker.clear()
            self.squares, self.tiles, self._listed = [], [], {}
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

    def busy(self) -> bool:
        """Work is queued or running (tests wait on it)."""
        return self._worker.busy()

    def refresh(self) -> None:
        """Ask the engine for the viewport's squares (on the worker)."""
        if not self.enabled or self.view is None:
            return
        south, west, north, east, px_per_deg = self.view
        self._generation += 1
        self._worker.ask_squares(self._generation, dict(
            south=south, west=west, north=north, east=east,
            px_per_deg=px_per_deg, scale=_device_scale()))

    def _held(self, key):
        held = self.images.peek(key)
        return None if held is None else (held[0], held[1])

    def _on_arrived(self, kind, generation, payload) -> None:
        if not self.enabled:
            return
        if kind == "squares":
            if generation != self._generation:
                return                  # a newer view was asked for
            self.squares = list(payload.get("squares", []))
            self.tiles = list(payload.get("tiles", []))
            self._listed = {s["key"]: s["stamp"] for s in self.squares}
            self.images.touch([s["key"] for s in self.squares])
            self._worker.set_fetches(generation,
                                     LIVE.fetch_plan(self.squares, self._held))
        else:
            square, px, image = payload
            if self._listed.get(square["key"]) != square["stamp"]:
                return                  # no longer in view, or replaced
            held = self._held(square["key"])
            if held is not None and held[0] == square["stamp"] and held[1] >= px:
                return                  # a finer one is already here
            self.images.put(square["key"], (square["stamp"], px, image),
                            image.sizeInBytes())
        self.changed.emit()

    def paint(self, painter, point, outline=None) -> None:
        """Draw the squares that have an image and the marks; ``point(lat,
        lon)`` is the map's viewport point; ``outline`` (a pen) marks the
        full-resolution squares."""
        if not self.enabled:
            return
        def rect_of(north, west, south, east):
            return QRectF(point(north, west), point(south, east)).normalized()
        sharp, stale = [], []
        for square in self.squares:
            held = self.images.peek(square["key"])
            if not held:
                continue
            rect = rect_of(square["north"], square["west"],
                           square["south"], square["east"])
            painter.drawImage(rect, held[2])
            if square.get("sharp"):
                sharp.append(rect)
            if square.get("stale"):
                stale.append(rect)
        if outline is not None and sharp:
            painter.setPen(outline)
            painter.setBrush(Qt.NoBrush)
            for rect in sharp:
                painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))
        reload_tiles = [rect_of(t["lat"] + 1, t["lon"], t["lat"], t["lon"] + 1)
                        for t in self.tiles if t.get("state") == "reload"]
        own = [rect_of(t["lat"] + 1, t["lon"], t["lat"], t["lon"] + 1)
               for t in self.tiles if t.get("state") == "own"]
        _marks(painter, stale + reload_tiles, "reload", Qt.BDiagPattern,
               TEXT.RELOAD_LABEL)
        _marks(painter, own, "own", Qt.Dense6Pattern, None)   # no words


def _marks(painter, rects, key, pattern, label) -> None:
    """``rects`` hatched in the mark's color, outlined and labelled
    (``label`` None: no words)."""
    if not rects:
        return
    color = QColor(*TEXT.MARK_COLORS[key])
    pen = QPen(color, 1)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(QBrush(color, pattern))
    for rect in rects:
        painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))
    painter.setBrush(Qt.NoBrush)
    for rect in rects if label else ():
        _label(painter, rect, label, color)


def _label(painter, rect, text, color) -> None:
    """``text`` on a dark plate at the centre of the visible part of
    ``rect``, when that part is at least :data:`LABEL_MIN_PX` wide."""
    shown = rect.intersected(QRectF(painter.window()))
    if shown.width() < LABEL_MIN_PX:
        return
    metrics = painter.fontMetrics()
    box = QRectF(0, 0, metrics.horizontalAdvance(text) + 12,
                 metrics.height() + 6)
    box.moveCenter(shown.center())
    painter.fillRect(box, QColor(0, 0, 0, 170))
    painter.setPen(QColor("white"))
    painter.drawText(box, Qt.AlignCenter, text)
    painter.setPen(QPen(color, 1))


def _device_scale() -> float:
    screen = QGuiApplication.primaryScreen()
    return float(screen.devicePixelRatio()) if screen is not None else 1.0
