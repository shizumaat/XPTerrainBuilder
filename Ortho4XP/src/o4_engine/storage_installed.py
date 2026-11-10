"""The ortho tiles installed in X-Plane (Settings > Storage, "Installed
ortho tiles"; owner feedback on 1.0.480): the ``zOrtho4XP_*`` entries of
the Custom Scenery folder, measured without walking another volume.

* A REAL FOLDER is sized (allocated bytes of its files, symlinks not
  followed); the size is cached per folder, keyed by the modification
  times of the folder and its direct sub-folders, so a second scan stats
  only those (:data:`CACHE_NAME` under the data folder's ``logs``).
* A LINK (symlink, or a Windows junction) is counted, never followed or
  sized: its target's volume is read from the link text alone (macOS
  ``/Volumes/<name>``, a Windows drive, else "this disk"), and whether
  that volume is mounted.

The Storage pane's "Caches" and "Your tiles and patches" measure the
app's own data folder only; this row is the scenery X-Plane loads, which
may live elsewhere.  No tile or airport is named here.
"""
from __future__ import annotations

import json
import os
import stat

import O4_File_Names as FNAMES

__all__ = ["PREFIX", "CACHE_NAME", "installed_tiles", "write_json"]

PREFIX = "zOrtho4XP_"
CACHE_NAME = "installed_tiles_sizes.json"
THIS_DISK = "this disk"


def _is_link(path: str) -> bool:
    isjunction = getattr(os.path, "isjunction", None)
    return os.path.islink(path) or bool(isjunction and isjunction(path))


def _link_volume(target: str) -> str:
    """The volume a link's target text names: ``/Volumes/<name>`` ->
    ``<name>``, a Windows drive -> ``D:``, otherwise :data:`THIS_DISK`."""
    if len(target) >= 2 and target[1] == ":" and target[0].isalpha():
        return target[0].upper() + ":"
    parts = target.replace("\\", "/").split("/")
    if len(parts) > 2 and parts[0] == "" and parts[1] == "Volumes":
        return parts[2]
    return THIS_DISK


def _volume_mounted(volume: str) -> bool:
    if volume == THIS_DISK:
        return True
    if volume.endswith(":"):
        return os.path.isdir(volume + os.sep)
    return os.path.ismount(os.path.join("/Volumes", volume))


def _stamp(folder: str) -> list:
    """The modification times of ``folder`` and its direct sub-folders."""
    stamps = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    stamps.append([entry.name, entry.stat(follow_symlinks=False).st_mtime])
        stamps.append([".", os.stat(folder).st_mtime])
    except OSError:
        pass
    return sorted(stamps)


def _folder_bytes(folder: str) -> int:
    """Allocated bytes of every regular file under ``folder``."""
    total = 0
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in names:
            try:
                st = os.lstat(os.path.join(root, name))
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                blocks = getattr(st, "st_blocks", None)
                total += blocks * 512 if blocks is not None else st.st_size
    return total


def _cache_path() -> str:
    return os.path.join(FNAMES.data_path("logs"), CACHE_NAME)


def _read_cache(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path: str, data: dict) -> None:
    """Write ``data`` to ``path`` atomically; a failure is silent (a cache)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def installed_tiles(custom_scenery: str, cache_path: "str | None" = None) -> dict:
    """``{"custom_scenery", "local_count", "local_bytes", "linked_count",
    "linked": [{"volume", "count", "mounted"}], "measured"}`` of the
    ``zOrtho4XP_*`` entries of ``custom_scenery`` ("measured" False when
    the folder is not set or not readable)."""
    out = {"custom_scenery": custom_scenery or "", "local_count": 0,
           "local_bytes": 0, "linked_count": 0, "linked": [],
           "measured": False}
    try:
        names = sorted(n for n in os.listdir(custom_scenery) if n.startswith(PREFIX))
    except (OSError, TypeError):
        return out
    out["measured"] = True
    cache_path = cache_path or _cache_path()
    old, new, volumes = _read_cache(cache_path), {}, {}
    for name in names:
        path = os.path.join(custom_scenery, name)
        if _is_link(path):
            try:
                target = os.readlink(path)
            except OSError:
                target = ""
            volume = _link_volume(target)
            volumes[volume] = volumes.get(volume, 0) + 1
            continue
        if not os.path.isdir(path):
            continue
        stamp = _stamp(path)
        known = old.get(path)
        size = (known["bytes"] if isinstance(known, dict)
                and known.get("stamp") == stamp else _folder_bytes(path))
        new[path] = {"stamp": stamp, "bytes": size}
        out["local_count"] += 1
        out["local_bytes"] += size
    if new != old:
        write_json(cache_path, new)
    out["linked"] = [{"volume": v, "count": c, "mounted": _volume_mounted(v)}
                     for v, c in sorted(volumes.items())]
    out["linked_count"] = sum(volumes.values())
    return out
