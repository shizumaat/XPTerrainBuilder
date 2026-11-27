"""One small machine-wide record file: what every build on this computer
has heard from the elevation providers, each record lapsing after a while.

The tiles of an app build are separate processes, so what one of them
heard (a refusal, an outage) is only every other's news through a file.
A :class:`RestFile` keeps one JSON object ``{key: record}`` under
``Elevation_data/``; a record carries ``"at"`` (epoch seconds) and lapses
``lapse_s`` after it.  Reads merge the file into memory whenever its mtime
changed, keeping the newer record per key; writes replace the file
atomically (scratch + ``os.replace``).  Under an ARMED shared-repo write
guard (a harness build) nothing is written and the record stays in this
process.  Users: :mod:`elevation_access.refusal_rest` (the 24 h refusal
rest) and :mod:`elevation_access.provider_outage` (the short outage).
"""

from __future__ import annotations

import json
import os
import threading

import O4_File_Names as FNAMES

from elevation_access.downloads import _write_refused_by_armed_guard

__all__ = ["RestFile"]


class RestFile:
    """``{key: record}`` shared through ``Elevation_data/<file_name>``."""

    def __init__(self, file_name, lapse_s):
        self.file_name = str(file_name)
        self.lapse_s = float(lapse_s)
        self.lock = threading.Lock()
        self.memory = {}
        self._loaded_from = None

    def path(self):
        """Where the file lives (``None`` with no elevation folder)."""
        root = getattr(FNAMES, "Elevation_dir", "") or ""
        return os.path.join(root, self.file_name) if root else None

    def _load_locked(self):
        """Merge the file into memory when it is new or changed since read."""
        path = self.path()
        if path is None:
            return
        try:
            stamp = (path, os.stat(path).st_mtime_ns)
        except OSError:
            stamp = (path, None)
        if self._loaded_from == stamp:
            return
        self._loaded_from = stamp
        try:
            with open(path, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(stored, dict):
            return
        for (key, record) in stored.items():
            mine = self.memory.get(str(key))
            if isinstance(record, dict) and (
                    mine is None
                    or float(record.get("at", 0)) > float(mine.get("at", 0))):
                self.memory[str(key)] = record

    def _save_locked(self, now):
        path = self.path()
        if path is None or not os.path.isdir(os.path.dirname(path)):
            return
        if _write_refused_by_armed_guard(path):
            return                        # a build is not a refresh event
        live = {key: record for (key, record) in self.memory.items()
                if now - float(record.get("at", 0)) < self.lapse_s}
        scratch = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())
        try:
            with open(scratch, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(live, handle, indent=2, sort_keys=True)
            os.replace(scratch, path)
        except OSError:
            try:
                os.remove(scratch)
            except OSError:
                pass

    def put(self, key, record, now):
        """Record ``record`` (stamped ``at`` = ``now``) under ``key``,
        merged with what the other processes wrote, and save."""
        with self.lock:
            self._load_locked()
            self.memory[str(key)] = dict(record, at=now)
            self._save_locked(now)

    def live(self, key, now):
        """The record under ``key`` that has not lapsed at ``now``, or None."""
        with self.lock:
            self._load_locked()
            record = self.memory.get(str(key))
        if record is None or now - float(record.get("at", 0)) >= self.lapse_s:
            return None
        return record
