"""The object inspector on the Qt patch layer (issue #1702; the Mac app's
``PatchObjectInspector``).

In Edit mode a click on a pack object's footprint (no node, "+" handle or
line under it) selects the object: its outline is drawn in the selection
colour over a light tint, as a selected shape is, and its name box grows
to show its height and the elevations (m MSL) of its top and bottom as
the last build seated it.  Those come from the engine's ``object_seat``
(``o4_engine.object_seat``), which reads the build's placement plan; the
text is the engine's ``lines``, so both apps show the same words.  A node
or shape selection, Esc, a click on open map or a new document clears it.

The selection (:attr:`ObjectInspector.selected` and its ``object`` dict)
is what "Set object elevation…" acts on, and a node dropped on an object's
snap point is asked Top / Bottom here (#1703, :mod:`O4_Qt_Object_Seat`).
"""
from __future__ import annotations

import math
import typing as _t

from o4_engine import patch_edit as PE
from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPen

__all__ = ["ObjectInspector", "ASK_AGAIN_MS", "ASK_LIMIT"]

#: While the engine says ``pending`` (the ground still loading): ask again
#: this often, at most this many times (the Mac app's 400 ms × 20).
ASK_AGAIN_MS = 400
ASK_LIMIT = 20


def _box_lines(label: str, seat: _t.Mapping | None, failure: str | None = None) -> list[str]:
    """The grown name box: the name, then the engine's lines."""
    if seat is not None:
        return [label] + [str(s) for s in seat.get("lines") or ()]
    return [label, failure or "Reading its seat…"]


class ObjectInspector(QObject):
    """The selected pack object and its seat."""

    changed = Signal()

    def __init__(self, engine, model, outlines, built: _t.Callable[[], dict], parent=None):
        super().__init__(parent)
        self.engine, self.model, self.outlines, self._built = engine, model, outlines, built
        self.selected = None                    # an O4_Qt_Pack_Outlines.Outline
        self.seat: dict | None = None
        self.failure: str | None = None
        self._ask = 0                           # bumps on every new selection
        self.top_or_bottom = None               # the snap's open pop-up (#1703)
        outlines.changed.connect(self._outlines_changed)
        model.selection_changed.connect(self._selection_changed)

    # ─── selection ─────────────────────────────────────────────────────
    def select_at(self, lat: float, lon: float) -> bool:
        """Select the object under ``(lat, lon)``; False when there is none."""
        found = self.outlines.at(lat, lon, objects_only=True)
        if found is None:
            return False
        if self.selected is not None and self.selected.object == found.object:
            return True
        self.clear()
        self.selected = found
        self._query(found.object, self._ask, 0)
        self.changed.emit()
        return True

    def clear(self) -> None:
        self._ask += 1
        if self.selected is None and self.seat is None and self.failure is None:
            return
        self.selected, self.seat, self.failure = None, None, None
        self.changed.emit()

    @property
    def lines(self) -> list[str]:
        return [] if self.selected is None else _box_lines(self.selected.label, self.seat,
                                                          self.failure)

    # ─── #1703: the elevation by hand, the snap's question ─────────────
    @property
    def can_set_elevation(self) -> bool:
        return self.selected is not None and self.engine.has("object_seat_set")

    def set_elevation(self, bottom_m: float | None) -> None:
        """Store the selected object's bottom (m MSL); None: back to the
        object stage's own seat.  ONE undo step (``SeatStep``)."""
        from O4_Qt_Object_Seat import SeatStep
        patch, o = self.model.patch, self.selected
        if patch is None or o is None:
            return
        obj, tile, icao = o.object, patch.tile, patch.icao
        name = "Clear Object Elevation" if bottom_m is None else "Set Object Elevation"

        def stored(error) -> None:
            if error is not None:
                self.model.set_error("The object's elevation could not be set: %s" % error)
                return
            self.model.tiles_needing_rebuild.add(tile)
            self.model.status_changed.emit()
            if self.selected is not None and self.selected.object == obj:
                self._ask += 1
                self._query(obj, self._ask, 0)

        def send(zero_m) -> None:
            self._seat_set(tile, icao, obj, lambda _r, e: stored(e), zero_m=zero_m)

        def first(reply, error) -> None:
            stored(error)
            if error is None:
                self.model.undo_stack.push(SeatStep(name, send, reply.get("previous_zero_m"),
                                                    reply.get("zero_m")))
        self._seat_set(tile, icao, obj, first, bottom_m=bottom_m, y_min=obj.get("y_min") or 0.0)

    def _seat_set(self, tile: str, icao: str, obj: dict, callback, **values) -> None:
        self.engine.call("object_seat_set", callback, tile=tile, icao=icao, index=obj["index"],
                         model=obj.get("model") or "", lat=obj["lat"], lon=obj["lon"],
                         **{k: v for k, v in values.items() if v is not None})

    def offer_top_or_bottom(self, node: int, obj: dict, parent, global_pos, tries: int = 0) -> None:
        """A node dropped on ``obj``'s snap point: when the object has a
        height, ask at ``global_pos`` whether the node takes its top or
        bottom."""
        from O4_Qt_Object_Seat import has_height, top_or_bottom_menu
        patch = self.model.patch
        if patch is None or not self.engine.has("object_seat"):
            return
        info = (self._built() or {}).get((math.floor(obj["lat"]), math.floor(obj["lon"])))
        kwargs = {k: obj[k] for k in ("index", "lat", "lon", "agl_m", "y_min", "y_max")}
        generation = self.model.generation

        def answered(reply, error) -> None:
            if error is not None or generation != self.model.generation:
                return
            if reply.get("pending") and tries + 1 < ASK_LIMIT:
                QTimer.singleShot(ASK_AGAIN_MS, lambda: self.offer_top_or_bottom(
                    node, obj, parent, global_pos, tries + 1))
                return
            if not has_height(reply) or node not in self.model.doc.nodes:
                return
            self.top_or_bottom = top_or_bottom_menu(
                parent, reply["top_m"], reply["bottom_m"],
                lambda alt, name: self.model.perform(
                    name, lambda doc: PE.set_alt(doc, [node], alt)))
            self.top_or_bottom.popup(global_pos)
        self.engine.call("object_seat", answered, tile=patch.tile, icao=patch.icao,
                         build_dir=getattr(info, "build_dir", None) or None, **kwargs)

    def _outlines_changed(self) -> None:
        """A new document reloads the outlines: its objects are new ones."""
        if self.selected is not None and not any(o is self.selected
                                                 for o in self.outlines.footprints):
            self.clear()

    def _selection_changed(self) -> None:
        if self.model.has_selection:
            self.clear()

    # ─── the engine ────────────────────────────────────────────────────
    def _query(self, obj: dict, ask: int, tries: int) -> None:
        patch = self.model.patch
        if patch is None or not self.engine.has("object_seat"):
            self.failure = "This engine cannot read object seats; update the app."
            return
        info = (self._built() or {}).get((math.floor(obj["lat"]), math.floor(obj["lon"])))
        kwargs = {k: obj[k] for k in ("index", "lat", "lon", "agl_m", "y_min", "y_max")}

        def answered(reply, error) -> None:
            if ask != self._ask:
                return                          # another object since
            if error is not None:
                self.failure = "Its seat could not be read: %s" % error
            else:
                self.seat = reply
                if reply.get("pending") and tries + 1 < ASK_LIMIT:
                    QTimer.singleShot(ASK_AGAIN_MS, lambda: self._query(obj, ask, tries + 1))
            self.changed.emit()
        self.engine.call("object_seat", answered, tile=patch.tile, icao=patch.icao,
                         build_dir=getattr(info, "build_dir", None) or None, **kwargs)

    # ─── drawing (viewport space) ──────────────────────────────────────
    def paint(self, painter, view_transform, colour: QColor) -> None:
        """The selected outline in ``colour`` over a light tint, then its
        grown name box at the outline's label anchor."""
        o = self.selected
        if o is None:
            return
        from O4_Qt_Pack_Outlines import LABEL_POINT_SIZE, LINE_WIDTH
        painter.save()
        painter.setTransform(view_transform)
        tint = QColor(colour)
        tint.setAlphaF(0.18)
        painter.fillPath(o.path, tint)
        pen = QPen(colour)
        pen.setCosmetic(True)
        pen.setWidthF(2 * LINE_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(o.path)
        painter.resetTransform()
        font = QFont(painter.font())
        font.setPointSizeF(LABEL_POINT_SIZE + 1)
        painter.setFont(font)
        fm = painter.fontMetrics()
        lines = self.lines
        w = max(fm.horizontalAdvance(t) for t in lines) + 16
        h = fm.height() * len(lines) + 10
        c = view_transform.map(o.anchor)
        box = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
        painter.setPen(QPen(colour, 1.5))
        painter.setBrush(QColor(0, 0, 0, round(0.78 * 255)))
        painter.drawRoundedRect(box, 7, 7)
        painter.setPen(QColor(255, 255, 255))
        for k, text in enumerate(lines):
            font.setBold(k == 0)
            painter.setFont(font)
            painter.drawText(QRectF(box.x() + 8, box.y() + 5 + k * fm.height(), w - 16,
                                    fm.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()
