"""Show a folder (or a file: a World pack tile's DSF, #2027) in the
platform's file manager (#938).

Finder on macOS (the folder selected in its parent window), Explorer on
Windows (likewise), and the default file manager elsewhere (the folder
opened, since ``xdg-open`` cannot select).  The Qt app's tile right-click
menu uses it; the Mac app does the same with
``NSWorkspace.activateFileViewerSelecting`` (``TileContextMenu.swift``).
No GUI toolkit here: a command line and a launcher.
"""

from __future__ import annotations

import os
import subprocess
import sys

__all__ = ["menu_label", "reveal_command", "reveal"]


def menu_label(platform: str | None = None) -> str:
    """The menu item's words on this platform."""
    platform = platform or sys.platform
    if platform == "darwin":
        return "Show in Finder"
    if platform.startswith("win"):
        return "Show in Explorer"
    return "Show in File Manager"


def reveal_command(path: str, platform: str | None = None) -> list:
    """The command that shows ``path`` in the file manager."""
    platform = platform or sys.platform
    if platform == "darwin":
        return ["open", "-R", path]
    if platform.startswith("win"):
        return ["explorer", "/select,", os.path.normpath(path)]
    return ["xdg-open", path]


def reveal(path: str, platform: str | None = None,
           launch=subprocess.Popen) -> None:
    """Start the file manager on ``path`` (a folder, or a file selected in
    its folder) without waiting for it.  Raises ``OSError`` when it is
    gone or the launcher is missing."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    platform = platform or sys.platform
    if not os.path.isdir(path) and not platform.startswith(("darwin", "win")):
        path = os.path.dirname(path)    # xdg-open would open the file itself
    launch(reveal_command(path, platform))
