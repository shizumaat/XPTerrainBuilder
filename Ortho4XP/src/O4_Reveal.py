"""Show a folder in the platform's file manager (#938).

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
    """Start the file manager on ``path`` without waiting for it.
    Raises ``OSError`` when the folder is gone or the launcher is missing."""
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    launch(reveal_command(path, platform))
