"""THE FILES A CACHED STAGE OPENED (stage-cache spec §5's witness pattern,
issue #843).

A stage's key names its inputs and code, but a stage may also open a file
none of them names.  Census 2026-10-18 (CYXY, an audit hook over the real
build): ``classify`` re-opens the pack's ``apt.dat``; the planar stage
opens the tile's OSM water and coastline extracts and ``Ortho4XP.cfg`` (the
core's water reading) and ``classify/rules.toml``.  So while a recording
window is open, every file opened for READING is recorded by an audit hook
(``sys.addaudithook``: Python's own ``open`` event — ``open()``,
``os.open``, ``io.open_code``), and the record keeps each file's size and
modification time.  A later read :func:`holds` only when every one still
has both; a file gone, resized or touched REFUSES the record (no content
hash: a touched file is a miss, never a wrong hit).

A recorder made with ``writes=True`` also keeps the files written in the
window (opened for writing, or renamed onto): the object stage's outputs,
which its reuse re-hashes before it serves a record (#879).

NOT RECORDED: code (``.py``, ``.pyc``, extension modules — a stage's code
is its ``stage_code`` digest), the stage cache's own files (``o4_stage*``)
and files opened for writing.  What a file
opened outside Python (a C library, a subprocess) reads is not seen; the
DEM's rasters, the one such read the front half makes, are witnessed by
their answers (``airport/dem_record``).

The hook is installed once per process and does nothing while no window
is open.
"""
from __future__ import annotations

import os
import sys
import threading
import typing as _t
import weakref

__all__ = ["FileRecorder", "holds"]

_CODE = (".py", ".pyc", ".pyd", ".so", ".dylib", ".dll")
#: the stage cache's own records and index (``airport/stage_cache``)
_OWN = "o4_stage"
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC

_LOCK = threading.Lock()
#: the open windows, held weakly: a build that raised mid-window leaves none
_ACTIVE: "weakref.WeakSet[FileRecorder]" = weakref.WeakSet()
_HOOKED = False


def _as_str(path: _t.Any) -> "str | None":
    if isinstance(path, bytes):
        return os.fsdecode(path)
    if isinstance(path, os.PathLike):
        return os.fspath(path)
    return path if isinstance(path, str) else None


def _hook(event: str, args: tuple) -> None:
    if event not in ("open", "os.rename") or not _ACTIVE:
        return
    if event == "os.rename":            # ``os.rename`` / ``os.replace``
        dst = _as_str((tuple(args) + (None, None))[1])
        if dst is not None and not os.path.basename(dst).startswith(_OWN):
            for rec in tuple(_ACTIVE):
                if rec._written is not None:
                    rec._written.add(dst)
        return
    path, mode, flags = (tuple(args) + (None, None, None))[:3]
    path = _as_str(path)
    if (path is None or path.endswith(_CODE)
            or os.path.basename(path).startswith(_OWN)):
        return
    if isinstance(mode, str):
        writing = any(c in mode for c in "wax+")
    else:
        writing = isinstance(flags, int) and bool(flags & _WRITE_FLAGS)
    for rec in tuple(_ACTIVE):
        if not writing:
            rec._paths.add(path)
        elif rec._written is not None:
            rec._written.add(path)


def _install() -> None:
    global _HOOKED
    with _LOCK:
        if not _HOOKED:
            sys.addaudithook(_hook)
            _HOOKED = True


def _stamp(path: str) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return int(st.st_size), int(st.st_mtime_ns)


class FileRecorder:
    """Records the files opened for reading while it is
    :meth:`recording` (module doc)."""

    def __init__(self, *, writes: bool = False) -> None:
        self._paths: set[str] = set()
        #: with ``writes``: every file opened for writing or renamed onto
        #: (``os.rename`` / ``os.replace``) — the object stage's outputs (#879)
        self._written: "set[str] | None" = set() if writes else None
        _install()

    def recording(self, on: bool) -> None:
        """Open (``True``) or close the window."""
        with _LOCK:
            if on:
                _ACTIVE.add(self)
            else:
                _ACTIVE.discard(self)

    def record(self) -> dict[str, tuple[int, int] | None]:
        """``{absolute path: (size, mtime_ns)}`` of every regular file
        opened so far (``None`` for one already gone)."""
        out: dict[str, tuple[int, int] | None] = {}
        for p in sorted(self._paths):
            ap = os.path.abspath(p)
            if os.path.isdir(ap):
                continue
            out[ap] = _stamp(ap)
        return out

    def written(self) -> list[str]:
        """The absolute paths of the regular files written while recording
        that still exist (a ``writes`` recorder; ``[]`` otherwise)."""
        return sorted({os.path.abspath(p) for p in self._written or ()
                       if os.path.isfile(p)})

    def replay(self, record: _t.Mapping[str, _t.Any] | None) -> None:
        """Merge a stored record's files (a stage served from cache)."""
        self._paths.update(record or ())


def holds(record: _t.Mapping[str, _t.Any] | None) -> str | None:
    """``None`` when every recorded file still has its size and mtime;
    else the first that does not."""
    for path, stamp in (record or {}).items():
        now = _stamp(path)
        if now != (tuple(stamp) if stamp is not None else None):
            return f"file:{path}"
    return None
