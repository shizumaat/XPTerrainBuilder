"""The tile pane's "Path" row (Qt half; the Mac app's ``TilePathRow``,
same words — :mod:`O4_Tile_Volume` writes the note).

The active tile's folder with its links resolved (#1987: a
``zOrtho4XP_*`` link in Custom Scenery shows the folder on the drive it
points to) and a small button that shows it in the file manager (Finder,
Explorer, or the default one — :mod:`O4_Reveal`).  The button is disabled
while the folder cannot be reached, with the note "<drive> is not
connected." when the folder is on a drive that is away.
"""
from __future__ import annotations

import O4_Reveal as REVEAL
import O4_Tile_Volume as TVOL
import O4_World_State_Text as WORLD_TEXT
from O4_Qt_Widgets import ElidedRowLabel
from PySide6.QtWidgets import (QHBoxLayout, QMessageBox, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

__all__ = ["TilePathRow", "ROW_TITLE"]

ROW_TITLE = "Path"


class TilePathRow(QWidget):
    """The resolved folder, the reveal button, and the offline note.

    The row sits in the fixed-width side panel, so it must not put a
    font-sized floor under it (``TestPanelFitsItsViewport``): the path
    and the note elide (``ElidedRowLabel``), and the row as a whole takes
    an Ignored horizontal policy so the reveal button's width — a glyph,
    measured in the platform font — never becomes the panel's minimum.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        self.path_label = ElidedRowLabel("—")
        line.addWidget(self.path_label, 1)
        self.reveal_button = QToolButton()
        self.reveal_button.setText("↗")
        self.reveal_button.setAutoRaise(True)
        self.reveal_button.setToolTip(REVEAL.menu_label())
        self.reveal_button.clicked.connect(self._reveal)
        line.addWidget(self.reveal_button, 0)
        outer.addLayout(line)
        self.note_label = ElidedRowLabel("")
        self.note_label.setStyleSheet("color: palette(placeholder-text);")
        self.note_label.setVisible(False)
        outer.addWidget(self.note_label)
        self._path = ""

    def show_info(self, info, world=None) -> None:
        """The row for a tile's ``TileInfo`` (``None``: no tile folder) and
        its ``WorldTile``: the tile's DSF in the World pack when its
        folder holds only records (#2027, ``O4_World_State_Text.world_dsf``)."""
        path = WORLD_TEXT.world_dsf(info, world)
        volume = ""
        mounted = bool(path)
        if info is not None and not path:
            path = (getattr(info, "resolved_dir", "")
                    or getattr(info, "build_dir", "") or "")
            volume = getattr(info, "volume", "") or ""
            mounted = bool(getattr(info, "volume_mounted", True))
        self._path = path
        self.path_label.setText(path or "—")
        self.path_label.setToolTip(path)
        offline = bool(volume) and not mounted
        self.reveal_button.setEnabled(bool(path) and mounted)
        note = TVOL.offline_note(volume) if offline else ""
        self.note_label.setText(note)
        self.note_label.setToolTip(note)
        self.note_label.setVisible(offline)

    def _reveal(self) -> None:
        try:
            REVEAL.reveal(self._path)
        except OSError as exc:
            QMessageBox.warning(self, REVEAL.menu_label(),
                                "Could not show %s: %s" % (self._path, exc))
