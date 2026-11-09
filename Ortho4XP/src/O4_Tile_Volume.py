"""Which drive a tile's folder lives on (issue #1987).

Users keep tiles on an external drive and link them into ``Custom
Scenery`` (a ``zOrtho4XP_*`` symlink or junction).  Both maps draw such a
tile in brown with "Requires <drive>" and the tile pane shows the folder
the link resolves to, with a "Show in Finder" button that is disabled
while the drive is not connected.  This module is the ONE rule both apps
read, through the scan's ``TileInfo`` (``resolved_dir``, ``volume``,
``volume_mounted``):

* :func:`volume_name` — the drive a path names, mounted or not: ``<name>``
  of macOS ``/Volumes/<name>/…``, of Linux ``/media/<user>/<name>/…``,
  ``/run/media/<user>/<name>/…`` and ``/mnt/<name>/…``, and the ``X:`` of
  a Windows path; ``""`` for the system drive.
* :func:`tile_volume` — ``(resolved_dir, volume, mounted)`` of one tile
  folder: ``volume`` is named only when the folder resolves onto a drive
  OTHER than the one holding the folder it sits in (a whole Custom
  Scenery on an external drive is not "external" tile by tile).
* :func:`offline_note` — the tile pane's words while the drive is away.

Standard library only (plus :mod:`O4_Unmounted_Links`' target cleaner).
"""

from __future__ import annotations

import os
import re
from typing import Tuple

from O4_Unmounted_Links import clean_target

__all__ = ["volume_name", "tile_volume", "offline_note", "requires_label"]

_DRIVE_RE = re.compile(r"^([A-Za-z]):")


def volume_name(path: str) -> str:
    """The drive ``path`` names, whether or not it is connected; ``""``
    when the path is on the system drive (or names none)."""
    norm = clean_target(path or "").replace("\\", "/")
    parts = [p for p in norm.split("/") if p]
    if norm.startswith("/Volumes/") and len(parts) >= 2:
        return parts[1]
    if (norm.startswith("/media/") or norm.startswith("/run/media/")):
        skip = 1 if parts[0] == "media" else 2
        if len(parts) >= skip + 2:
            return parts[skip + 1]
        return ""
    if norm.startswith("/mnt/") and len(parts) >= 2:
        return parts[1]
    drive = _DRIVE_RE.match(norm)
    if drive:
        return drive.group(1).upper() + ":"
    return ""


def _resolved(path: str) -> str:
    """``path`` with every link resolved as far as it goes — a dangling
    link (drive away) still yields its target."""
    return clean_target(os.path.realpath(path))


def tile_volume(build_dir: str) -> Tuple[str, str, bool]:
    """``(resolved_dir, volume, mounted)`` of the tile folder ``build_dir``.

    ``volume`` is ``""`` unless the folder resolves onto another drive
    than its parent folder (Custom Scenery, or the working dir);
    ``mounted`` is whether the resolved folder can be reached now."""
    if not build_dir:
        return "", "", False
    full = os.path.abspath(build_dir)
    resolved = _resolved(full)
    home = volume_name(_resolved(os.path.dirname(full)))
    volume = volume_name(resolved)
    if volume == home:
        volume = ""
    return resolved, volume, os.path.isdir(resolved)


def offline_note(volume: str) -> str:
    """Why the tile pane's reveal button is disabled."""
    return "%s is not connected." % volume


def requires_label(volume: str) -> str:
    """The map's top-right label on a tile that lives on ``volume``."""
    return "Requires %s" % volume
