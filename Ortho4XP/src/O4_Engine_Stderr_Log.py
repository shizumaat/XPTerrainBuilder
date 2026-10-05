"""The engine's stderr, persisted — one file per build run.

A Python ``RuntimeWarning`` (shapely, numpy) used to reach the terminal the
Qt app happened to be launched from and nowhere else: a warning the user saw
could not be read back afterwards.  ``EngineStderrLog`` tees ``sys.stderr``
into ``<data root>/logs/engine-stderr.log``.

TWIN of the mac app's ``EngineStderrLog``
(``Sources/SceneryKit/EngineStderrLog.swift``, which writes
``~/Library/Logs/XPTerrainBuilder/engine-stderr.log``).  The two follow the
same rules, and a change to one is a change to both:

* ``engine-stderr.log`` holds the CURRENT build run only.  ``start_run`` —
  called where the UI sends the build request that opens a run — shifts the
  file to ``engine-stderr.1.log`` and starts a fresh one.  (2026-10-05: the
  file used to append across app sessions for weeks, and errors from an old
  build were read as current.)
* The previous runs are kept as ``engine-stderr.1.log`` (most recent) …
  ``engine-stderr.5.log``; each new run shifts them and drops the oldest.
* The fresh file opens with a run header: time, app version, engine
  version and the tiles requested (``run_header``).
* Lines written between runs (start-up, idle warnings) land in the current
  file under a ``=== engine session <time> ===`` header — nothing is lost.
* Inside a run the file is capped at 20 MB: past it, the files shift the
  same way and the run continues in a fresh file under a continuation
  header, so one runaway run cannot fill the disk.
* Nothing here may raise: this object IS ``sys.stderr``, so a failure to
  log would take out the report of whatever was being logged.  A file that
  cannot be shifted or opened disables persistence until the next run; the
  original stream is always written first.
"""

from __future__ import annotations

import os
import threading
import time

import O4_File_Names as FNAMES

__all__ = [
    "ENGINE_STDERR_LOG_MAX_BYTES",
    "ENGINE_STDERR_LOG_KEPT_RUNS",
    "EngineStderrLog",
    "engine_stderr_log_path",
    "queued_line",
    "run_header",
]

ENGINE_STDERR_LOG_MAX_BYTES = 20 * 1024 * 1024
ENGINE_STDERR_LOG_KEPT_RUNS = 5


def engine_stderr_log_path():
    """Where the Qt window persists engine stderr.

    The mac app uses ``~/Library/Logs/XPTerrainBuilder/``; the Qt app has
    no platform log directory, so it uses the writable data root it
    already owns."""
    return FNAMES.data_path(os.path.join("logs", "engine-stderr.log"))


def _stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _tiles_text(tiles):
    tiles = [str(tile) for tile in tiles]
    return "%d tile%s: %s" % (
        len(tiles), "" if len(tiles) == 1 else "s", " ".join(tiles))


def run_header(app_version, engine_version, tiles, stamp=None):
    """The first line of a run's file (same text as the mac app's)."""
    return "=== engine run %s === app %s | engine %s | %s" % (
        stamp or _stamp(), app_version or "unknown",
        engine_version or "unknown", _tiles_text(tiles))


def queued_line(tiles, stamp=None):
    """Tiles added to the run in progress: a line, not a new file."""
    return "=== queued into this run %s === %s" % (
        stamp or _stamp(), _tiles_text(tiles))


class EngineStderrLog:
    """``sys.stderr`` duplicated into the per-run log (module docstring)."""

    def __init__(self, original, path, max_bytes=ENGINE_STDERR_LOG_MAX_BYTES,
                 kept_runs=ENGINE_STDERR_LOG_KEPT_RUNS):
        self._original = original
        self._path = path
        self._max_bytes = max_bytes
        self._kept_runs = kept_runs
        self._handle = None
        self._failed = False
        self._pending_header = None
        self._lock = threading.RLock()

    # -- the run boundary ------------------------------------------------

    def start_run(self, app_version, engine_version, tiles):
        """Shift the previous runs and open a fresh file for this one."""
        try:
            header = run_header(app_version, engine_version, tiles)
        except Exception:
            header = "=== engine run ==="
        with self._lock:
            self._close()
            self._failed = not self._shift()
            self._pending_header = header
            self._open()

    def note(self, line):
        """A line for the log only (never the console stream)."""
        with self._lock:
            self._persist(line + "\n")

    # -- file plumbing (never raises) ------------------------------------

    def _numbered(self, index):
        return "%s.%d.log" % (os.path.splitext(self._path)[0], index)

    def _shift(self):
        """live -> .1, .1 -> .2 …, the oldest dropped.  False on failure."""
        try:
            if not os.path.exists(self._path):
                return True
            oldest = self._numbered(self._kept_runs)
            if os.path.exists(oldest):
                os.remove(oldest)
            for index in range(self._kept_runs - 1, 0, -1):
                if os.path.exists(self._numbered(index)):
                    os.replace(self._numbered(index),
                               self._numbered(index + 1))
            os.replace(self._path, self._numbered(1))
            return True
        except Exception:
            return False

    def _close(self):
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                pass
        self._handle = None

    def _open(self):
        if self._handle is not None or self._failed:
            return
        try:
            directory = os.path.dirname(self._path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            self._handle = open(self._path, "a", encoding="utf-8",
                                errors="replace", newline="\n")
            header = self._pending_header or (
                "=== engine session %s ===" % _stamp())
            self._pending_header = None
            self._handle.write(header + "\n")
            self._handle.flush()
        except Exception:
            self._close()
            self._failed = True

    def _persist(self, text):
        self._open()
        if self._handle is None:
            return
        try:
            self._handle.write(text)
            self._handle.flush()
            oversize = self._handle.tell() > self._max_bytes
        except Exception:
            self._close()
            self._failed = True
            return
        if oversize:
            self._close()
            self._failed = not self._shift()
            self._pending_header = (
                "=== engine run continued %s === the %d MB size guard moved "
                "the earlier part to %s" % (
                    _stamp(), self._max_bytes // (1024 * 1024),
                    os.path.basename(self._numbered(1))))

    # -- the stream protocol ---------------------------------------------

    def write(self, text):
        try:
            self._original.write(text)
        except Exception:
            pass
        try:
            with self._lock:
                self._persist(text)
        except Exception:
            pass

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass
        handle = self._handle
        if handle is not None:
            try:
                handle.flush()
            except Exception:
                pass

    def isatty(self):
        try:
            return self._original.isatty()
        except Exception:
            return False
