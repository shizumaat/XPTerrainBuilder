"""What Measure reads from a tile folder, kept between runs (owner
2026-11-12T19:08Z: "automatically kickoff the measure process in the
background so when the user opens settings it's already done").

Measure (``world_migrate_size``, ``world_adopt.plan``) reads, for every
tile folder it sizes, the headers of its DSF, ``.ter`` and DDS files --
on the owner's disk 2,221 folders on another drive, minutes each run.
:class:`TileFacts` keeps each answer per folder under the folder's
STAMP: the ``(mtime_ns, size)`` of the folder, its ``terrain/`` and
``textures/`` folders and its DSF.  A tile is (re)written by adding,
removing or replacing files, which moves those stamps; a second Measure
of the same tiles reads four ``stat`` per folder and nothing else.

The facts live in one JSON file in the app's data folder
(:func:`default_path`, beside ``storage_installed``'s cache), written
atomically by :meth:`TileFacts.save`; an unreadable file is an empty
cache.  No tile or airport is named here.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Callable, Optional

import O4_World_Pack as WP

__all__ = ["CACHE_NAME", "default_path", "file_stamp", "TileFacts"]

CACHE_NAME = "world_tile_facts.json"
_VERSION = 1


def default_path() -> str:
    """The cache file: ``logs/`` of the data folder."""
    import O4_File_Names as FNAMES
    return os.path.join(FNAMES.data_path("logs"), CACHE_NAME)


def file_stamp(path: str) -> Optional[list]:
    """``[mtime_ns, size]`` of ``path`` (``None`` when absent)."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return [st.st_mtime_ns, st.st_size]


def _stamp(folder: str, lat: int, lon: int) -> list:
    """The folder's stamp: ``(mtime_ns, size)`` of the folder, its
    ``terrain/`` and ``textures/`` and its DSF (``None`` when absent)."""
    return [file_stamp(folder), file_stamp(os.path.join(folder, "terrain")),
            file_stamp(os.path.join(folder, "textures")),
            file_stamp(os.path.join(folder, WP.dsf_relpath(lat, lon)))]


class TileFacts:
    """``get(folder, lat, lon, key, compute)``: ``compute()`` once per
    folder stamp; thread-safe.  ``path`` ``None`` keeps nothing on disk;
    ``read`` counts the computes (the twins read it)."""

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.read = 0
        self._lock = threading.Lock()
        self._changed = False
        self._folders: dict = {}
        if path:
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict) and data.get("version") == _VERSION:
                    self._folders = dict(data.get("folders") or {})
            except (OSError, ValueError):
                pass

    def _entry(self, folder: str, lat: int, lon: int) -> dict:
        now = _stamp(folder, lat, lon)
        with self._lock:
            entry = self._folders.get(folder)
            if not isinstance(entry, dict) or entry.get("stamp") != now:
                entry = {"stamp": now}
                self._folders[folder] = entry
                self._changed = True
            return entry

    def get(self, folder: str, lat: int, lon: int, key: str,
            compute: Callable[[], Any]) -> Any:
        """The fact ``key`` of ``folder`` (JSON-able), computed when the
        folder changed since it was kept."""
        entry = self._entry(folder, lat, lon)
        with self._lock:
            if key in entry:
                return entry[key]
        value = compute()
        with self._lock:
            entry[key] = value
            self.read += 1
            self._changed = True
        return value

    def save(self) -> None:
        """Write the cache when it changed (a failure is silent: a cache)."""
        if not self.path or not self._changed:
            return
        from .storage_installed import write_json
        with self._lock:
            data = {"version": _VERSION, "folders": dict(self._folders)}
            self._changed = False
        write_json(self.path, data)
