"""The map's tile right-click menu in the Qt app (#938).

One item today: show the tile's folder in the platform's file manager
(Finder, Explorer, or the default file manager; ``O4_Reveal``).  The item
is greyed out while the tile has no folder yet.
"""

from __future__ import annotations

import os

from PySide6.QtWidgets import QMenu, QMessageBox

import O4_File_Names as FNAMES
import O4_Reveal as REVEAL

__all__ = ["tile_menu"]


def tile_menu(parent, lat: int, lon: int, build_dir: str) -> QMenu:
    """The menu for tile (lat, lon) whose folder is ``build_dir``."""
    menu = QMenu(parent)
    menu.setTitle(FNAMES.short_latlon(lat, lon))
    action = menu.addAction(REVEAL.menu_label())
    exists = bool(build_dir) and os.path.isdir(build_dir)
    action.setEnabled(exists)
    if not exists:
        action.setToolTip("This tile has no folder yet: build it first.")

    def _reveal():
        try:
            REVEAL.reveal(build_dir)
        except OSError as exc:
            QMessageBox.warning(
                parent, REVEAL.menu_label(),
                "Could not show %s: %s" % (build_dir, exc))

    action.triggered.connect(_reveal)
    return menu
