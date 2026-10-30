"""Per-tile build logs and the tile's build record (#1226).

The console is one live stream of every tile's lines, and the run's
``engine-stderr.log`` (``O4_Engine_Stderr_Log``) interleaves them all: a
user who selects a tile could not read back what its last build said.
The engine — not a front end, so Qt, the Mac app and a shell build all
get them — now writes, inside the tile's build folder:

* ``build_logs/<UTC stamp>_<tile>.log``: every line of one build of the
  tile, the run-level lines of other tiles excluded.  The newest
  ``KEPT_BUILDS`` (3) logs of a tile are kept; a log is capped at
  ``MAX_LOG_BYTES`` (5 MB) and says so where it stops.
* ``build_logs/build_record.json``: one row per kept build — ``tile``,
  ``start`` / ``end`` (epoch seconds), ``duration``, ``outcome``
  (``ok`` / ``warnings`` / ``failed`` / ``stopped``), ``warnings`` (a
  count), ``log`` (the file name) and ``builder``
  ``{tool, app_version, engine_version}`` (owner Q95: an older Ortho4XP
  tile is told apart from an XPTerrainBuilder one, and versions apart).

A grouped build folder holds several tiles, so every row and every log
name carries its tile and retention counts per tile.

TWIN of the Mac app's ``TileBuildRecord`` (``Sources/SceneryKit/
TileBuildRecord.swift``), which reads the same file, applies the same
date ranges (``DATE_RANGES``) and words "Built by" the same way.  A
change to one is a change to both.

Lines reach a tile's log two ways: the parallel orchestrator hands each
worker line over with its tile (``o4_engine.parallel``), and an
in-process build tags the process's own streams with ``TileStreamTag``
while one tile is building — the console then shows the same
``[+47-123] `` prefix in both run modes, and that prefix is what a front
end filters the console by (``tile_of_line``).

Nothing here may raise into a build: a log that cannot be written is
dropped, never the build.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time

import O4_File_Names as FNAMES

__all__ = [
    "BUILDER_TOOL",
    "DATE_RANGES",
    "KEPT_BUILDS",
    "LOGS_DIR",
    "MAX_LOG_BYTES",
    "RECORD_NAME",
    "TileBuildLogs",
    "TileStreamTag",
    "built_by_text",
    "creation_agent",
    "dsf_creation_agent",
    "in_date_range",
    "last_build",
    "read_log",
    "read_records",
    "tile_of_line",
]

LOGS_DIR = "build_logs"
RECORD_NAME = "build_record.json"
KEPT_BUILDS = 3
MAX_LOG_BYTES = 5 * 1024 * 1024
BUILDER_TOOL = "XPTerrainBuilder"
RECORD_SCHEMA = 1

#: The one date filter (owner Q139), key -> label; "all" is the default.
DATE_RANGES = (
    ("today", "Today"),
    ("48h", "Last 48 hours"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("all", "All"),
)
_RANGE_SECONDS = {"48h": 48 * 3600, "7d": 7 * 86400, "30d": 30 * 86400}

#: The console prefix of a tile's line: ``[+47-123] ``.
_PREFIX = re.compile(r"^\[([+-]\d{2}[+-]\d{3})\] ")


def build_logs_dir(build_dir):
    """The tile build folder's log folder."""
    return os.path.join(build_dir, LOGS_DIR)


def tile_of_line(line):
    """``(tile key, text)`` of a console line: the key of its ``[+47-123] ``
    prefix and the text after it, or ``(None, line)`` for a run-level
    line."""
    match = _PREFIX.match(line)
    if match is None:
        return None, line
    return match.group(1), line[match.end():]


def builder():
    """Who builds this tile: ``{tool, app_version, engine_version}``."""
    try:
        import O4_Build_Info as BUILD
        app, engine = BUILD.app_version(), BUILD.build_info().engine
    except Exception:                                    # pragma: no cover
        app = engine = "dev"
    return {"tool": BUILDER_TOOL, "app_version": app,
            "engine_version": engine}


def creation_agent(who=None):
    """The DSF ``sim/creation_agent`` of a tile this engine builds:
    ``XPTerrainBuilder 1.0.4xx (engine 1.50.x)`` — it still names the
    builder when the record is lost or the DSF is copied elsewhere."""
    who = who or builder()
    text = "%s %s (engine %s)" % (who["tool"], who["app_version"],
                                  who["engine_version"])
    # The DSF property atom is ASCII and NUL-terminated.
    return text.encode("ascii", "replace").decode("ascii").replace("\0", "")


def built_by_text(record=None, agent=None):
    """The "Built by" line of the tile info.

    From a build record's ``builder``; else from the DSF's
    ``creation_agent`` (``agent``): a bare ``Ortho4XP`` is an older
    Ortho4XP build, anything else is shown as it is.  ``""`` when
    neither is known."""
    who = (record or {}).get("builder") or {}
    if who.get("tool"):
        # The app version, as the user knows the build (owner 2026-10-30);
        # the engine version stays in the record and the DSF agent.  A
        # record from a build that did not know its app version names the
        # engine instead of "dev".
        app = who.get("app_version") or ""
        if app and app != "dev":
            return ("%s %s" % (who["tool"], app)).strip()
        if who.get("engine_version"):
            return "%s, engine %s" % (who["tool"], who["engine_version"])
        return ("%s %s" % (who["tool"], app)).strip()
    agent = (agent or "").strip()
    if agent == "Ortho4XP":
        return "Ortho4XP (older build, version unknown)"
    return agent


def dsf_creation_agent(dsf_path, head_bytes=65536):
    """The ``sim/creation_agent`` property of a DSF, read from its head
    only (the properties atom comes first).  ``""`` when the file cannot
    be read, is compressed, or carries none.  Asked for one SELECTED tile,
    never during a scan."""
    try:
        with open(dsf_path, "rb") as handle:
            head = handle.read(head_bytes)
    except OSError:
        return ""
    key = b"sim/creation_agent\0"
    at = head.find(key)
    if not head.startswith(b"XPLNEDSF") or at < 0:
        return ""
    start = at + len(key)
    end = head.find(b"\0", start)
    if end < 0:
        return ""
    return head[start:end].decode("utf-8", "replace")


def in_date_range(ts, range_key, now=None):
    """Whether a build that ended at epoch ``ts`` falls in ``range_key``
    (``DATE_RANGES``).  "today" is since local midnight; an unknown time
    is only in "all"."""
    if range_key == "all":
        return True
    if ts is None:
        return False
    now = time.time() if now is None else now
    if range_key == "today":
        local = time.localtime(now)
        midnight = time.mktime((local.tm_year, local.tm_mon, local.tm_mday,
                                0, 0, 0, 0, 0, -1))
        return ts >= midnight
    return ts >= now - _RANGE_SECONDS.get(range_key, 0)


# -- the record file --------------------------------------------------------

def _record_path(build_dir):
    return os.path.join(build_logs_dir(build_dir), RECORD_NAME)


def _read_rows(build_dir):
    try:
        with open(_record_path(build_dir), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    rows = data.get("builds") if isinstance(data, dict) else None
    return [row for row in rows or () if isinstance(row, dict)]


def read_records(build_dir, lat, lon):
    """The tile's kept build rows, newest first."""
    tile = FNAMES.short_latlon(lat, lon)
    rows = [row for row in _read_rows(build_dir) if row.get("tile") == tile]
    return sorted(rows, key=lambda row: row.get("start") or 0, reverse=True)


def last_build(build_dir, lat, lon):
    """The tile's newest build row, or ``None`` (built before logging)."""
    rows = read_records(build_dir, lat, lon)
    return rows[0] if rows else None


def read_log(build_dir, name):
    """One saved log's text, ``""`` when it is gone."""
    if not name or os.path.basename(name) != name:
        return ""
    try:
        with open(os.path.join(build_logs_dir(build_dir), name),
                  encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def _write_rows(build_dir, rows):
    path = _record_path(build_dir)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"schema": RECORD_SCHEMA, "builds": rows}, handle,
                  indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def _stamp(ts):
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(ts))


class _OpenLog:
    """One build of one tile, in progress."""

    def __init__(self, tile, build_dir, start):
        self.tile = tile
        self.build_dir = build_dir
        self.start = start
        self.name = ""
        self.handle = None
        self.size = 0
        self.capped = False


class TileBuildLogs:
    """The engine session's per-tile logs (module docstring)."""

    def __init__(self, kept=KEPT_BUILDS, max_bytes=MAX_LOG_BYTES,
                 who=None):
        self._kept = kept
        self._max_bytes = max_bytes
        self._who = who
        self._open = {}      # (lat, lon) -> _OpenLog
        self._finished = {}  # (lat, lon) -> (build_dir, log name)
        self._lock = threading.RLock()

    def is_open(self, tile):
        """A build of ``tile`` is being logged now."""
        return tile is not None and tuple(tile) in self._open

    def begin(self, tile, build_dir):
        """Start the log of a new build of ``tile`` in ``build_dir``."""
        tile = tuple(tile)
        try:
            with self._lock:
                self._close(self._open.pop(tile, None))
                entry = _OpenLog(tile, build_dir, time.time())
                folder = build_logs_dir(build_dir)
                os.makedirs(folder, exist_ok=True)
                base = "%s_%s" % (_stamp(entry.start),
                                  FNAMES.short_latlon(*tile))
                name, index = base + ".log", 1
                while os.path.exists(os.path.join(folder, name)):
                    index += 1
                    name = "%s-%d.log" % (base, index)
                entry.name = name
                entry.handle = open(os.path.join(folder, name), "a",
                                    encoding="utf-8", errors="replace",
                                    newline="\n")
                self._open[tile] = entry
                self._finished.pop(tile, None)
        except Exception:
            pass

    def line(self, tile, text):
        """One line of ``tile``'s build.  A line that arrives after the
        tile finished (the orchestrator's closing summary) joins its last
        log."""
        if tile is None:
            return
        tile = tuple(tile)
        try:
            with self._lock:
                entry = self._open.get(tile)
                if entry is not None:
                    self._write(entry, text)
                    return
                late = self._finished.get(tile)
            if late is not None:
                with self._lock, open(
                        os.path.join(build_logs_dir(late[0]), late[1]), "a",
                        encoding="utf-8", errors="replace",
                        newline="\n") as handle:
                    handle.write(text.rstrip("\n") + "\n")
        except Exception:
            pass

    def finish(self, tile, outcome, warnings=0, closing=()):
        """End ``tile``'s build: write ``closing`` lines, its record row,
        and drop all but its newest kept builds."""
        if tile is None:
            return
        tile = tuple(tile)
        try:
            with self._lock:
                entry = self._open.pop(tile, None)
                if entry is None:
                    return
                for text in closing:
                    self._write(entry, text)
                self._close(entry)
                end = time.time()
                self._finished[tile] = (entry.build_dir, entry.name)
                row = {
                    "tile": FNAMES.short_latlon(*tile),
                    "start": round(entry.start, 3),
                    "end": round(end, 3),
                    "duration": round(max(0.0, end - entry.start), 1),
                    "outcome": outcome,
                    "warnings": int(warnings),
                    "log": entry.name,
                    "builder": self._who or builder(),
                }
                self._record(entry.build_dir, row)
        except Exception:
            pass

    # -- plumbing ---------------------------------------------------------

    def _write(self, entry, text):
        if entry.handle is None or entry.capped:
            return
        data = text.rstrip("\n") + "\n"
        if entry.size + len(data) > self._max_bytes:
            entry.capped = True
            data = ("=== log stopped here: the %d MB cap of a tile's build "
                    "log was reached ===\n" % (self._max_bytes // 1048576))
        entry.handle.write(data)
        entry.handle.flush()
        entry.size += len(data)

    @staticmethod
    def _close(entry):
        if entry is not None and entry.handle is not None:
            try:
                entry.handle.close()
            except Exception:
                pass
            entry.handle = None

    def _record(self, build_dir, row):
        rows = [r for r in _read_rows(build_dir)
                if r.get("log") != row["log"]] + [row]
        mine = sorted((r for r in rows if r.get("tile") == row["tile"]),
                      key=lambda r: r.get("start") or 0, reverse=True)
        dropped = mine[self._kept:]
        rows = [r for r in rows if r not in dropped]
        _write_rows(build_dir, rows)
        kept_logs = {r.get("log") for r in rows}
        folder = build_logs_dir(build_dir)
        mine_name = re.compile(r"^\d{8}T\d{6}Z_%s(-\d+)?\.log$"
                               % re.escape(row["tile"]))
        for name in os.listdir(folder):
            if mine_name.match(name) and name not in kept_logs:
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass


class TileStreamTag:
    """A process stream that tags every line written while one tile is
    building in this process (an in-process run): the line reaches the
    original stream with the tile's ``[+47-123] `` prefix and the tile's
    build log without it.  With no tile building it passes text through
    untouched.

    ``tile_now`` returns the tile being logged, or ``None``.
    """

    def __init__(self, original, logs, tile_now):
        self._original = original
        self._logs = logs
        self._tile_now = tile_now
        self._pending = ""
        self._pending_tile = None
        self._lock = threading.RLock()

    @property
    def original(self):
        """The wrapped stream."""
        return self._original

    def write(self, text):
        try:
            tile = self._tile_now()
        except Exception:
            tile = None
        with self._lock:
            if tile != self._pending_tile:
                self._flush_pending()
            if tile is None:
                self._raw(text)
                return len(text)
            self._pending_tile = tile
            self._pending += text
            while True:
                cut = min((i for i in (self._pending.find("\n"),
                                       self._pending.find("\r")) if i >= 0),
                          default=-1)
                if cut < 0:
                    break
                line, end = self._pending[:cut], self._pending[cut]
                self._pending = self._pending[cut + 1:]
                self._emit(tile, line, end)
        return len(text)

    def _emit(self, tile, line, end):
        if line.strip():
            self._raw("[%s] %s%s" % (FNAMES.short_latlon(*tile), line, end))
            self._logs.line(tile, line)
        else:
            self._raw(line + end)

    def _flush_pending(self):
        if self._pending:
            self._emit(self._pending_tile, self._pending, "")
        self._pending = ""
        self._pending_tile = None

    def _raw(self, text):
        try:
            self._original.write(text)
        except Exception:
            pass

    def flush(self):
        with self._lock:
            self._flush_pending()
        try:
            self._original.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return self._original.isatty()
        except Exception:
            return False

    def __getattr__(self, name):
        return getattr(self._original, name)

    @classmethod
    def install(cls, logs, tile_now):
        """Tag ``sys.stdout`` and ``sys.stderr``; returns the undo."""
        saved = (sys.stdout, sys.stderr)
        same = sys.stdout is sys.stderr
        sys.stdout = cls(saved[0], logs, tile_now)
        sys.stderr = sys.stdout if same else cls(saved[1], logs, tile_now)

        def undo():
            for name, before in (("stdout", saved[0]), ("stderr", saved[1])):
                current = getattr(sys, name)
                if isinstance(current, cls):
                    try:
                        current.flush()
                    except Exception:
                        pass
                    if current.original is before:
                        setattr(sys, name, before)
        return undo
