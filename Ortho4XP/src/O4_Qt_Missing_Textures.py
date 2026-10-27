"""The tile pane's missing-textures warning (Qt half; the Mac app's
``TileMissingTexturesRow``, same words).

An installed tile whose ``terrain/*.ter`` files name textures its
``textures/`` folder lacks is a tile X-Plane will not load
(:mod:`O4_Tile_Texture_Check`).  When the active tile is one, this row
says so in one line, explains in its tooltip, and offers "Rebuild Tile" —
the window's own build path for one tile (``MainWindow.
rebuild_patch_tile``: its recorded source and zoom).  Hidden otherwise.
The check reads the tile's terrain files, so it runs off the GUI thread;
a result for a tile no longer active is dropped.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

import O4_Tile_Texture_Check as CHECK

__all__ = ["MissingTexturesRow"]

WARNING_COLOR = "#D9822B"


class MissingTexturesRow(QWidget):
    """One line and a "Rebuild Tile" button; hidden while all is well."""

    #: (lat, lon) of the tile the user asked to rebuild.
    rebuild_requested = Signal(object)
    #: (tile, reply) from the checking thread.
    _checked = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: %s;" % WARNING_COLOR)
        layout.addWidget(self.label, 1)
        self.rebuild_button = QPushButton("Rebuild Tile")
        self.rebuild_button.setToolTip(
            "Build this tile again with the imagery it was built with.")
        self.rebuild_button.clicked.connect(self._rebuild)
        layout.addWidget(self.rebuild_button, 0)
        self._tile = None
        self._checked.connect(self._show)
        self.setVisible(False)

    def check(self, tile, build_dir) -> None:
        """Check ``tile``'s folder; the row updates when the answer lands."""
        self._tile = tuple(tile) if tile else None
        self.setVisible(False)
        if self._tile is None or not build_dir:
            return

        def _worker(tile=self._tile, build_dir=build_dir):
            reply = CHECK.tile_texture_check(build_dir=build_dir)
            try:
                self._checked.emit(tile, reply)
            except RuntimeError:
                pass  # the window closed meanwhile

        threading.Thread(target=_worker, daemon=True).start()

    def clear(self) -> None:
        self.check(None, "")

    def _show(self, tile, reply) -> None:
        if tile != self._tile:
            return
        count = int(reply.get("missing_count", 0))
        if not count:
            self.setVisible(False)
            return
        self.label.setText("⚠ " + CHECK.warning_text(count))
        self.label.setToolTip(CHECK.detail_text(reply))
        self.setVisible(True)

    def _rebuild(self) -> None:
        if self._tile is not None:
            self.rebuild_requested.emit(self._tile)
