""""Insert shape" from the map's right-click menu in the Qt app (issue
#1314; the Mac app's ``PatchEditModel.insertShape``).

The engine plans it (``patch_insert_shape``: a 20 m square at the click,
each corner at the elevation under it, the airport whose extent holds the
point), asked again while an elevation source is still loading, as the
cursor readout does.  The open patch of that airport takes the square as
ONE undoable edit (``PatchEditModel.add_shape``: Edit mode, the shape
selected, the save bar counts it); any other airport's patch gets it on
disk through ``patch_add_shape``, which starts the airport's edited patch
when it has none, and the engine's sentence says what was written.
"""
from __future__ import annotations

import math
import typing as _t

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMessageBox

__all__ = ["ShapeInserter", "INSERT_SHAPE_TITLE"]

#: The right-click item (the Mac app's ``TileContextMenu.insertShapeTitle``).
INSERT_SHAPE_TITLE = "Insert shape"
#: How often a pending plan is asked again, and how many times.
PENDING_MS = 400
MAX_TRIES = 20


class ShapeInserter(QObject):
    """``insert(lat, lon)`` for the window's patch editor."""

    def __init__(self, engine, controller, built: _t.Callable[[], dict], parent=None):
        super().__init__(parent)
        self._engine, self._controller, self._built = engine, controller, built
        #: ``notify(text)``: the outcome the user reads (a message box).
        self.notify: _t.Callable[[str], None] = (
            lambda text: QMessageBox.information(parent, INSERT_SHAPE_TITLE, text))
        self._gen = 0

    def available(self) -> bool:
        return self._engine.has("patch_insert_shape")

    def insert(self, lat: float, lon: float) -> None:
        """Plan the square at ``(lat, lon)`` and add it (module doc)."""
        self._gen += 1
        self._ask(self._gen, lat, lon, 1)

    def _ask(self, gen: int, lat: float, lon: float, tries: int) -> None:
        info = (self._built() or {}).get((math.floor(lat), math.floor(lon)))
        build_dir = getattr(info, "build_dir", None) or None

        def answered(reply, error):
            if gen != self._gen:
                return
            if error is not None:
                self.notify(error)
            elif reply.get("pending"):
                if tries >= MAX_TRIES:
                    self.notify("The elevation there is still loading; try Insert shape again.")
                else:
                    QTimer.singleShot(PENDING_MS, lambda: self._ask(gen, lat, lon, tries + 1))
            else:
                self._place(reply)
        self._engine.call("patch_insert_shape", answered, lat=lat, lon=lon, build_dir=build_dir)

    def _place(self, plan: dict) -> None:
        model = self._controller.model
        p = model.patch
        is_open = p is not None and (p.tile, p.icao) == (plan["tile"], plan["icao"])
        if model.doc is not None and is_open:
            model.add_shape(plan["corners"])
            return

        def added(reply, error):
            if error is not None:
                self.notify(error)
                return
            self._controller.relist(plan["tile"])
            self.notify(reply["message"])
        self._engine.call("patch_add_shape", added, tile=plan["tile"], icao=plan["icao"],
                          corners=plan["corners"])
