"""The tile pane's "World pack" row (Qt half; the Mac app's
``TileWorldRow``, same words from ``O4_World_State_Text`` — owner
2026-11-12T20:23Z: a tile fully built in the World pack must not read
"not built").

What the World pack holds for the tile — "Built (in the World pack): mesh
+ full imagery", who made it and where its own files live — and, for a
real tile, Rebuild Tile (its rebuild inputs, even when the tiles folder
holds only those), Export Package… and Remove from World Pack… (its
package first, then the placeholder: ``o4_engine.world_tile_remove``;
confirmed first).  A built tile waiting for X-Plane to finish loading it,
or in over the version X-Plane loaded, says so, the latter with "Reload
scenery" (#2175, ``WorldTilesWaiting``, ``TEXT.waiting_note``).  Hidden
when the World pack holds nothing of the tile and nothing waits.
"""
from __future__ import annotations

import threading

import O4_World_State_Text as TEXT
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

__all__ = ["TileWorldRow", "EXPORT_BUTTON"]

#: The Mac app's ``O4TilePackageCopy.exportTitle``.
EXPORT_BUTTON = "Export Package…"


def _remove_tile(tile, scenery_dir: str) -> str:
    """Worker thread: the engine's ``world_tile_remove`` in process; the
    note to show (its refusal sentence when it refuses)."""
    from o4_engine.world_tile_remove import world_tile_remove
    try:
        return TEXT.removed_note(world_tile_remove(tile[0], tile[1], scenery_dir,
                                              confirm=True))
    except (OSError, ValueError) as error:
        return str(error)


class TileWorldRow(QWidget):
    """The status, its detail and the three actions (module doc)."""

    #: (lat, lon) of the tile to rebuild / export.
    rebuild_requested = Signal(object)
    export_requested = Signal(object)
    #: (lat, lon) removed (the window rescans).
    removed = Signal(object)
    #: The user's "Reload scenery" (the window sends ``scenery_reload``).
    reload_requested = Signal()
    _note_ready = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)
        self.waiting_label = QLabel("")
        self.waiting_label.setWordWrap(True)
        layout.addWidget(self.waiting_label)
        import O4_Imagery_OnDemand_Text as ONDEMAND_TEXT
        self.reload_button = QPushButton(ONDEMAND_TEXT.RELOAD_SCENERY_TITLE)
        self.reload_button.clicked.connect(self.reload_requested.emit)
        layout.addWidget(self.reload_button)
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(self.detail_label)
        self.actions = QWidget()
        buttons = QHBoxLayout(self.actions)
        buttons.setContentsMargins(0, 0, 0, 0)
        self.rebuild_button = QPushButton(TEXT.REBUILD_BUTTON)
        self.rebuild_button.clicked.connect(
            lambda: self._tile and self.rebuild_requested.emit(self._tile))
        self.export_button = QPushButton(EXPORT_BUTTON)
        self.export_button.clicked.connect(
            lambda: self._tile and self.export_requested.emit(self._tile))
        self.remove_button = QPushButton(TEXT.REMOVE_BUTTON)
        self.remove_button.clicked.connect(self._confirm_remove)
        for button in (self.rebuild_button, self.export_button, self.remove_button):
            buttons.addWidget(button)
        layout.addWidget(self.actions)
        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)
        self._note_ready.connect(self._show_note)
        self._tile = None
        self._shown = None
        self._waiting = ((), ())
        self.scenery_dir = ""
        self.setVisible(False)

    def show_world(self, tile, world) -> None:
        """The row for ``tile``'s World state (a ``WorldTile``, its
        ``fields()`` dict, or ``None``, which hides it)."""
        fields = world.fields() if hasattr(world, "fields") else world
        self._shown = (tuple(tile) if tile else None, fields)
        status = TEXT.pane_status(fields)
        waiting = self._waiting_text(tile)
        changed = self._tile != (tuple(tile) if tile else None)
        self._tile = tuple(tile) if tile and (status or waiting) else None
        if changed:
            self.note_label.setText("")
        self.setVisible(bool(self._tile))
        if not self._tile:
            return
        self.waiting_label.setText(waiting)
        self.waiting_label.setVisible(bool(waiting))
        self.reload_button.setVisible(
            bool(waiting) and self._name(tile) in self._waiting[1])
        self.status_label.setText(status)
        self.status_label.setVisible(bool(status))
        detail = TEXT.pane_detail(fields)
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))
        self.actions.setVisible(TEXT.built_in_world(fields))

    def show_waiting(self, event) -> None:
        """A ``WorldTilesWaiting``: its names, and the row again."""
        self._waiting = (tuple(getattr(event, "waiting", ()) or ()),
                         tuple(getattr(event, "reload", ()) or ()))
        if self._shown is not None:
            self.show_world(*self._shown)

    def waiting_tiles(self) -> tuple:
        """The tile names the last ``WorldTilesWaiting`` said wait."""
        return self._waiting[0]

    @staticmethod
    def _name(tile) -> str:
        import O4_World_Pack as WP
        return WP.tile_name(*tile) if tile else ""

    def _waiting_text(self, tile) -> str:
        return TEXT.waiting_note(self._name(tile), *self._waiting) if tile else ""

    def ask(self, tile) -> bool:
        """The confirmation (Mac: the same title, message and button)."""
        import O4_File_Names as FNAMES
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setText(TEXT.REMOVE_TITLE.format(tile=FNAMES.short_latlon(*tile)))
        box.setInformativeText(TEXT.REMOVE_MESSAGE)
        remove = box.addButton(TEXT.REMOVE_CONFIRM, QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        return box.clickedButton() is remove

    def _confirm_remove(self) -> None:
        tile = self._tile
        if not tile or not self.ask(tile):
            return
        self.remove_button.setEnabled(False)
        threading.Thread(target=lambda: self._note_ready.emit(
            tile, _remove_tile(tile, self.scenery_dir)), daemon=True,
            name="o4-world-remove").start()

    def _show_note(self, tile, note: str) -> None:
        self.remove_button.setEnabled(True)
        if tile == self._tile:
            self.note_label.setText(note)
        self.removed.emit(tile)
