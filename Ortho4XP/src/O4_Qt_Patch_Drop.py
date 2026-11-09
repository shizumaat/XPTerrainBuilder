"""Patches dropped on the window, the app icon or the command line (#1979;
mac-app parity: PatchDropInstall.swift).

The engine says what was dropped and where it goes
(``o4_engine.patch_drop``); this module shows that plan, installs it on
"Install", and prints what was installed to the console.  Drops reach it
three ways: a drag onto the main window (:class:`DropFilter` on the window
and the map's viewport), a file opened on the app icon (``QFileOpenEvent``,
macOS; :class:`DropFilter` on the application) and paths given as launch
arguments (Windows "Open with" / a drop on the executable, Linux desktop
files; :func:`launch_paths`).
"""
from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QMessageBox

from o4_engine import patch_drop as PD

__all__ = ["TITLE", "INSTALL", "local_paths", "launch_paths", "DropFilter",
           "offer"]

#: The confirmation's title and button (the Mac app: PatchDropCopy).
TITLE = "Install dropped patches?"
INSTALL = "Install"


def local_paths(mime) -> list[str]:
    """The local files and folders a drag carries."""
    if mime is None or not mime.hasUrls():
        return []
    return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]


def launch_paths(argv) -> list[str]:
    """The paths among the launch arguments (never an option)."""
    return [a for a in argv[1:] if not a.startswith("-") and os.path.exists(a)]


def _tiles_in_run(window, plan) -> list[str]:
    import O4_File_Names as FNAMES
    busy = getattr(window, "_tile_in_run", lambda tile: False)
    return [key for key in plan["tiles"] if busy(FNAMES.parse_tile_key(key))]


def offer(window, paths) -> bool:
    """Show what dropping *paths* installs and install it on "Install".
    True when something was installed."""
    try:
        plan = PD.patch_drop_plan(paths)
    except ValueError as error:
        QMessageBox.warning(window, TITLE, str(error))
        return False
    busy = _tiles_in_run(window, plan)
    if busy:
        QMessageBox.warning(window, TITLE, "Tile %s is building; install the "
                            "patches when its build finishes." % ", ".join(busy))
        return False
    box = QMessageBox(QMessageBox.Question, TITLE, "\n".join(plan["summary"]),
                      QMessageBox.Cancel, window)
    install = box.addButton(INSTALL, QMessageBox.AcceptRole)
    box.setDefaultButton(install)
    box.exec()
    if box.clickedButton() is not install:
        return False
    try:
        done = PD.patch_drop_install(paths)
    except (ValueError, OSError) as error:
        QMessageBox.warning(window, TITLE, str(error))
        return False
    for row in done["items"]:
        print("Tile %s: installed %s; the next build applies it."
              % (row["tile"], os.path.basename(row["destination"])))
    refresh = getattr(window, "_refresh_custom_patch_tiles", None)
    if refresh is not None:
        refresh()
    return True


class DropFilter(QObject):
    """Accepts file drags on the widgets it :meth:`watch` es and a file
    opened on the app icon (``QFileOpenEvent``, delivered to the
    application); both go to :func:`offer`."""

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._targets = []

    def watch(self, widget) -> None:
        widget.setAcceptDrops(True)
        widget.installEventFilter(self)
        self._targets.append(widget)

    def eventFilter(self, obj, event):      # noqa: N802 (Qt's name)
        kind = event.type()
        if kind == QEvent.FileOpen and event.file():
            offer(self._window, [event.file()])
            return True
        if obj not in self._targets:
            return False
        paths = (local_paths(event.mimeData())
                 if kind in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop)
                 else [])
        if not paths:
            return False
        event.acceptProposedAction()
        if kind == QEvent.Drop:
            offer(self._window, paths)
        return True
