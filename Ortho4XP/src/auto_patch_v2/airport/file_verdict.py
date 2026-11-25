"""One verdict per OBJ8 FILE VERSION, read off the caller's parse (#2206).

The candidate tests (``ground_shell.shape_of``, ``relief_skin.shape_of``)
are pure in the file, so each keeps one answer per ``(path, mtime_ns,
size)``.  Their callers in ``obj8.read_placed_objects`` already hold the
build's parse (``ResourceCache.geometry`` is ``parse_obj8(path)``), and an
``lru_cache`` keyed on the file version alone could not take it: every
miss parsed the file a second time (HECA: 241 of 858 parses, about 9 s of
a loaded pack stage).  A :class:`FileVerdict` derives from the geometry it
is offered and parses only when it is offered none.
"""
from __future__ import annotations

import collections
import os
import typing as _t

__all__ = ["FileVerdict"]


class FileVerdict:
    """``derive(path, geometry)`` memoised per file version, at most ``maxsize``
    versions (least recently used out).  ``OSError`` / ``ValueError`` from
    the stat, the parse or ``derive`` read ``None``."""

    def __init__(self, derive: _t.Callable[[str, _t.Any], _t.Any], maxsize: int = 256):
        self._derive = derive
        self._maxsize = maxsize
        self._memo: collections.OrderedDict = collections.OrderedDict()

    def __call__(self, path: str, geometry: _t.Any = None) -> _t.Any:
        try:
            st = os.stat(path)
        except (OSError, ValueError):
            return None
        key = (path, st.st_mtime_ns, st.st_size)
        if key in self._memo:
            self._memo.move_to_end(key)
            return self._memo[key]
        try:
            if geometry is None:
                from .obj8 import parse_obj8
                geometry = parse_obj8(path)
            got = self._derive(path, geometry)
        except (OSError, ValueError):
            got = None
        self._memo[key] = got
        if len(self._memo) > self._maxsize:
            self._memo.popitem(last=False)
        return got

    def cache_clear(self) -> None:
        self._memo.clear()
