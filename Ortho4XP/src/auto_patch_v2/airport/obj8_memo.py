"""ONE PARSE PER OBJ8 FILE VERSION FOR THE OBJECT STAGE (#412).

The placement plan reads each member's authored OBJ8 through its cutter
(``placement_cut._LineCutter._read``) and, after the splits, the pack's
terrain-feature verdict (``terrain_feature._file_verdict``) parses the
pack's resources again: 967 parses of ~500 files, 23 s of the HECA plan
stage.  Inside :func:`_scope` (opened by ``placement_write.build_plan``)
:func:`parse` hands back the geometry already parsed for the same file
version — ``(absolute path, mtime_ns, size)`` — and outside a scope it is
:func:`obj8.parse_obj8` itself.  Both readers only read the geometry.

The memo dies with the scope: it holds what the cutters already hold
while the plan is built, never a later stage's (or a later airport's)
files.
"""
from __future__ import annotations

import os
import typing as _t

from ..geom.scoped_memo import ScopedMemo

__all__ = ["scoped", "parse", "components", "per_file"]

#: the open scope's memo (``memo``; ``None`` outside a scope: every call
#: computes), shared helper ``geom/scoped_memo``
_SCOPE = ScopedMemo()
_scope = _SCOPE.scope
scoped = _SCOPE.scoped


def parse(path: str) -> _t.Any:
    """``obj8.parse_obj8(path)``, once per file version inside a scope.
    Raises what the parse raises (``OSError`` / ``ValueError``); a failed
    parse is not remembered."""
    from .obj8 import parse_obj8
    return per_file(path, "geometry", parse_obj8)


def components(geom: _t.Any) -> list:
    """``obj8.solid_components(geom)``, once per geometry OBJECT inside a
    scope (the geometry is held with its components, so its id is never
    reused while remembered)."""
    from .obj8 import solid_components
    memo = _SCOPE.memo
    if memo is None:
        return solid_components(geom)
    key = ("components", id(geom))
    hit = memo.get(key)
    if hit is None or hit[0] is not geom:
        hit = memo[key] = (geom, solid_components(geom))
    return hit[1]


def per_file(path: str, kind: str, read: _t.Callable[[str], _t.Any]) -> _t.Any:
    """``read(path)``, once per ``(kind, file version)`` inside a scope —
    the version is ``(absolute path, mtime_ns, size)``.  The caller owns
    the answer's immutability: a reader whose result is mutated later
    copies it (``obj8_split._read``)."""
    memo = _SCOPE.memo
    if memo is None:
        return read(path)
    st = os.stat(path)
    key = (kind, os.path.abspath(path), st.st_mtime_ns, st.st_size)
    hit = memo.get(key)
    if hit is None:
        hit = memo[key] = read(path)
    return hit
