"""The tile pane's "Airport packs" row (Qt half; the Mac app's
``TileStaleRow``, same words — #1958).

Shown only on a tile whose airport pack changed since its build
(:mod:`O4_Tile_Staleness`): why, airport by airport, and "Rebuild Tile" —
the window's own build path for one tile (its recorded source and zoom).
:func:`check_stale` is the window's background probe: the same engine
function the Mac app reaches through the ``tile_staleness`` command.
"""
from __future__ import annotations

import O4_Qt_Map_Legend as QTLEGEND
import O4_Tile_Staleness as STALE
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

__all__ = ["TileStaleRow", "ROW_TITLE", "REBUILD_NOTE", "REBUILD_BUTTON",
           "check_stale"]

#: The words of #1958 (Mac: ``O4TileStaleText``).
ROW_TITLE = "Airport packs"
REBUILD_NOTE = "Rebuild to fit the airports X-Plane draws now."
REBUILD_BUTTON = "Rebuild Tile"


def check_stale(tiles, scenery_dir, should_stop=None) -> dict:
    """Worker thread: ``{(lat, lon): verdict}`` of the stale tiles among
    ``tiles`` (``[(lat, lon, build_dir), ...]``)."""
    reply = STALE.check_tiles(scenery_dir, tiles)
    return {(row["lat"], row["lon"]): row for row in reply["tiles"]
            if row["stale"]}


class TileStaleRow(QWidget):
    """The reasons and a "Rebuild Tile" button; hidden while the tile fits."""

    #: (lat, lon) of the tile the user asked to rebuild.
    rebuild_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.title_label = QLabel("⚠ %s: changed since the build" % ROW_TITLE)
        self.title_label.setStyleSheet("color: %s;" % QTLEGEND.STALE_COLOR)
        layout.addWidget(self.title_label)
        self.reasons_label = QLabel("")
        self.reasons_label.setWordWrap(True)
        layout.addWidget(self.reasons_label)
        self.note_label = QLabel(REBUILD_NOTE)
        self.note_label.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(self.note_label)
        self.rebuild_button = QPushButton(REBUILD_BUTTON)
        self.rebuild_button.setToolTip(
            "Build this tile again with the imagery it was built with.")
        self.rebuild_button.clicked.connect(self._rebuild)
        layout.addWidget(self.rebuild_button)
        self._tile = None
        self.setVisible(False)

    def show_verdict(self, tile, verdict) -> None:
        """The row for ``tile``'s stale verdict; ``None`` hides it."""
        self._tile = tuple(tile) if tile and verdict else None
        if self._tile is None:
            self.setVisible(False)
            return
        self.reasons_label.setText(
            "\n".join(a["text"] for a in verdict.get("airports") or ()))
        self.setVisible(True)

    def _rebuild(self) -> None:
        if self._tile is not None:
            self.rebuild_requested.emit(self._tile)
