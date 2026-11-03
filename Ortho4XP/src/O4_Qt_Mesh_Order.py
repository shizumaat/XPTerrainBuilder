"""The tile pane's scenery-order warning (Qt half; the Mac app's
``TileMeshOrderRow``, same words and buttons).

X-Plane draws a tile's ground from the first pack in its scenery order
that ships a base mesh for it (:mod:`O4_Mesh_Order`, #1729).  When another
pack's mesh is drawn instead of the active tile, this row says so and
offers "Move Tile Above" and "Disable Scenery"; when the tile hides a
local mesh (an airport's own ground), it says so and offers "Show Its
Ground", which moves the tile below that pack.  Hidden otherwise.  The
check reads DSF headers, so it runs off the GUI thread; a result for a
tile no longer active is dropped.
"""
from __future__ import annotations

import threading

import O4_Mesh_Order as MESH
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

__all__ = ["MeshOrderRow", "BUTTONS"]

WARNING_COLOR = "#D9822B"

#: ``kind -> [(button title, action, which pack)]`` — ``first`` is the
#: highest pack named, ``last`` the lowest (the Mac row: the same).
BUTTONS = {
    "hidden_by": [("Move Tile Above", "raise", "first"),
                  ("Disable Scenery", "disable", "first")],
    "hides": [("Show Its Ground", "lower", "last")],
}


class MeshOrderRow(QWidget):
    """Up to two warning lines with their buttons; hidden while all is
    well."""

    #: (tile, reply or error sentence) from a worker thread.
    _answered = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.lines = {}
        for kind, buttons in BUTTONS.items():
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            label = QLabel("")
            label.setWordWrap(True)
            label.setStyleSheet("color: %s;" % WARNING_COLOR)
            row_layout.addWidget(label, 1)
            for (title, action, which) in buttons:
                button = QPushButton(title)
                button.clicked.connect(
                    lambda _=False, a=action, w=which, k=kind:
                    self._apply(k, a, w))
                row_layout.addWidget(button, 0)
            row.setVisible(False)
            layout.addWidget(row)
            self.lines[kind] = (row, label)
        self.refusal = QLabel("")
        self.refusal.setWordWrap(True)
        self.refusal.setVisible(False)
        layout.addWidget(self.refusal)
        self._tile = None
        self._where = ("", "")
        self._reply = {}
        self._answered.connect(self._show)
        self.setVisible(False)

    def check(self, tile, build_dir, custom_scenery_dir) -> None:
        """Check ``tile``; the row updates when the answer lands."""
        self._tile = tuple(tile) if tile else None
        self._where = (str(build_dir or ""), str(custom_scenery_dir or ""))
        self.setVisible(False)
        if self._tile is None or not all(self._where):
            return
        self._run(MESH.tile_mesh_order)

    def clear(self) -> None:
        self.check(None, "", "")

    def _run(self, call, **choice) -> None:
        tile, (build_dir, scenery) = self._tile, self._where

        def _worker():
            try:
                answer = call(custom_scenery_dir=scenery, lat=tile[0],
                              lon=tile[1], build_dir=build_dir, **choice)
            except ValueError as exc:
                answer = str(exc)
            except Exception:
                answer = None
            try:
                self._answered.emit(tile, answer)
            except RuntimeError:
                pass  # the window closed meanwhile

        threading.Thread(target=_worker, daemon=True).start()

    def _apply(self, kind, action, which) -> None:
        packs = list(self._reply.get(kind) or [])
        if self._tile is None or not packs:
            return
        self._run(MESH.apply_mesh_order, action=action,
                  pack=packs[0] if which == "first" else packs[-1])

    def _show(self, tile, answer) -> None:
        if tile != self._tile or answer is None:
            return
        if isinstance(answer, str):
            self.refusal.setText(answer)
            self.refusal.setVisible(True)
            return
        self._reply = answer
        self.refusal.setVisible(False)
        shown = {kind: (line, detail)
                 for kind, line, detail in MESH.warning_lines(answer)}
        for kind, (row, label) in self.lines.items():
            line, detail = shown.get(kind, ("", ""))
            label.setText("⚠ " + line if line else "")
            label.setToolTip(detail)
            row.setVisible(bool(line))
        self.setVisible(bool(shown))
