"""The map's tile right-click menu in the Qt app (#938).

Show the tile's folder in the platform's file manager (Finder, Explorer,
or the default file manager; ``O4_Reveal``), greyed out while the tile has
no folder yet.  The patch editor adds its own items for the selection
(``extra``: "Set elevation…" on selected shapes, #1357).
"""

from __future__ import annotations

import os
import typing as _t

import O4_File_Names as FNAMES
import O4_Reveal as REVEAL
from PySide6.QtWidgets import QMenu, QMessageBox

__all__ = ["tile_menu"]


def tile_menu(parent, lat: int, lon: int, build_dir: str,
              extra: _t.Sequence[tuple[str, _t.Callable[[], _t.Any]]] = ()) -> QMenu:
    """The menu for tile (lat, lon) whose folder is ``build_dir``; each
    ``(title, run)`` of ``extra`` comes first, above a separator."""
    menu = QMenu(parent)
    for title, run in extra:
        menu.addAction(title).triggered.connect(lambda _c=False, run=run: run())
    if extra:
        menu.addSeparator()
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
