"""Rescan the map's scenery overlays when Custom Scenery changes (#1258).

The Mac app's ``FileSystemWatcher`` port: the Custom Scenery folder, its
``Custom Scenery (Disabled)`` sibling and ``scenery_packs.ini`` are
watched, and a burst of changes (a pack added, deleted or renamed in the
file manager, X-Plane rewriting the ini) fires ``on_change`` ONCE after
it settles.  This replaces the toolbar's refresh button (owner
2026-10-22, both apps).
"""

import os

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer

__all__ = ["SceneryWatcher", "watched_paths"]

#: Seconds of quiet before a burst of changes fires (the Mac's debounce).
DEBOUNCE_MS = 2000


def watched_paths(custom_scenery_dir):
    """The folders and the ini the Mac app watches, those that exist."""
    if not custom_scenery_dir:
        return []
    root = os.path.normpath(custom_scenery_dir)
    candidates = (
        root,
        os.path.join(os.path.dirname(root), "Custom Scenery (Disabled)"),
        os.path.join(root, "scenery_packs.ini"),
    )
    return [path for path in candidates if os.path.exists(path)]


class SceneryWatcher(QObject):
    """Debounced watch over one Custom Scenery folder."""

    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._dir = None
        self._watcher = QFileSystemWatcher(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self._fire)
        self._watcher.directoryChanged.connect(self._bump)
        self._watcher.fileChanged.connect(self._bump)

    def watch(self, custom_scenery_dir):
        """Point the watch at ``custom_scenery_dir`` (idempotent)."""
        self._dir = custom_scenery_dir or None
        self._rearm()

    def _rearm(self):
        wanted = set(watched_paths(self._dir))
        current = set(self._watcher.files()) | set(self._watcher.directories())
        stale = sorted(current - wanted)
        fresh = sorted(wanted - current)
        if stale:
            self._watcher.removePaths(stale)
        if fresh:
            self._watcher.addPaths(fresh)

    def _bump(self, _path=""):
        # An atomic save replaces the ini's inode and drops it from the
        # watch; a folder that appears late joins it.  Re-arm, then wait
        # for the burst to settle.
        self._rearm()
        self._timer.start()

    def _fire(self):
        self._rearm()
        self._on_change()
