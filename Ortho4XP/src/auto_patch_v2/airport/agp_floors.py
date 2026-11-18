"""AN ``.agp`` PIECE'S FLOORS, READ ONCE PER PACK VERSION (#2090; spec
``2090-agp-group-groundside-spec.md`` Part D): the up-facing static floor
triangles of one OBJ8 piece — the one read every AGP reader shares
(``agp_ground``'s connector floors, the deck join and the ground-floor
plates of spec B1 / C1).

A floor is a solid face whose normal's vertical share is at least
``[agp] flat`` (X-Plane's front face is clockwise seen from the front: an
up-facing floor's ``(b - a) x (c - a)`` points DOWN in the OBJ frame); a
face under an animation (a jetway's tunnel) is no floor.

THE FLOOR CACHE (D1).  KDEN's terminal pieces reach 750k vertices; parsing
them costs ~26 s a build.  Each piece's floors (float32) and its plan box
are kept in ``<mod cache>/<pack>/o4_agp_floors.cache``, one record per
piece keyed on its PRISTINE file (``pack.authored_source``): its size and
mtime, its content sha256 kept and compared when the stat moved (the
discipline of ``airport/partition_cache``), with this reader's
:data:`VERSION` and ``flat``.  :func:`flush` writes the records a read
added (a temp file and ``os.replace``); a miss, a refused write, an
unreadable cache or no mod cache just computes.  The cache is a pure
function of the piece files it names, so it never needs the stage's file
witness: a moved file is a miss by its own stamp.

THE FEET (#2116 R2 C1b, :func:`feet_of`).  The same parse keeps each
piece's FEET: the bottom edge of every near-vertical solid face — where its
walls and slab edges stand — as ``(k, 2, 3)`` segments.
"""
from __future__ import annotations

import os
import pickle
import tempfile
import threading

import numpy as np

__all__ = ["VERSION", "CACHE_NAME", "floors_of", "feet_of", "flush"]

#: the reader's version: a change to :func:`_parse` bumps it
VERSION = 2
#: a wall face's edge within this of the face's lowest corner is its foot (m)
FOOT_SPAN_M = 0.05
#: a solid face whose normal's vertical share is at most this is a wall
_WALL_NY = 0.2
#: the feet's plan cell (m)
FOOT_CELL_M = 1.0
#: the per-pack cache file (``tools/harness/shared_repo_guard``'s families)
CACHE_NAME = "o4_agp_floors.cache"

_LOCK = threading.Lock()
#: cache path -> {"pieces": {rel: record}, "dirty": bool}
_OPEN: dict[str, dict] = {}


def _feet(g) -> np.ndarray:
    """``(k, 1, 3)`` float32 — the piece's FEET (module doc): along the
    bottom edge of every near-vertical solid face (its edges within
    :data:`FOOT_SPAN_M` of the face's lowest corner), samples every
    ``FOOT_CELL_M / 2``, kept per ``FOOT_CELL_M`` plan cell at the cell's
    LOWEST sample.  A reader keeps the ones at its own datum."""
    if g is None or not g.solid.shape[0]:
        return np.zeros((0, 1, 3), np.float32)
    v, t = g.vertices, g.solid
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, c - a)
    norm = np.linalg.norm(n, axis=1)
    t = t[(norm > 1e-9) & (np.abs(n[:, 1]) <= _WALL_NY * norm)]
    if not t.shape[0]:
        return np.zeros((0, 1, 3), np.float32)
    low = v[t, 1].min(axis=1) + FOOT_SPAN_M
    e = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    lo3 = np.concatenate([low, low, low])
    e = e[(v[e[:, 0], 1] <= lo3) & (v[e[:, 1], 1] <= lo3) & (e[:, 0] != e[:, 1])]
    if not e.shape[0]:
        return np.zeros((0, 1, 3), np.float32)
    e = np.unique(np.sort(e, axis=1), axis=0)
    p0, p1 = v[e[:, 0]].astype(np.float64), v[e[:, 1]].astype(np.float64)
    k = np.maximum(1, np.ceil(np.hypot(*(p1 - p0)[:, [0, 2]].T) / (0.5 * FOOT_CELL_M))).astype(int)
    seg = np.repeat(np.arange(len(e)), k + 1)
    start = np.repeat(np.cumsum(k + 1) - (k + 1), k + 1)
    f = (np.arange(len(seg)) - start) / k[seg]
    pts = p0[seg] + (p1 - p0)[seg] * f[:, None]
    cell = np.floor(pts[:, [0, 2]] / FOOT_CELL_M).astype(np.int64)
    order = np.lexsort((pts[:, 1], cell[:, 1], cell[:, 0]))
    cell, pts = cell[order], pts[order]
    first = np.ones(len(cell), bool)
    first[1:] = np.any(cell[1:] != cell[:-1], axis=1)
    return pts[first][:, None, :].astype(np.float32)


def _parse(path: str, flat: float) -> tuple[np.ndarray, np.ndarray]:
    """``(floors, feet)`` of the OBJ8 at ``path`` (one parse): ``floors``
    ``(k, 3, 3)`` float32, every up-facing static floor triangle as its three
    ``(x, y, z)`` corners (authored frame), and its feet (:func:`_feet`);
    empty when the file does not parse."""
    from . import obj8 as _obj8
    try:
        g = _obj8.parse_obj8(path, at_rest=True)
    except (OSError, ValueError):
        g = None
    out = np.zeros((0, 3, 3), np.float32)
    if g is not None and g.solid.shape[0]:
        v, t = g.vertices, g.solid
        a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        n = np.cross(b - a, c - a)
        norm = np.linalg.norm(n, axis=1)
        up = (norm > 1e-9) & (-n[:, 1] >= flat * norm)
        if g.animated.shape[0] == up.shape[0]:
            up &= ~g.animated          # a moving floor (a jetway) joins nothing
        if up.any():
            out = np.stack([a[up], b[up], c[up]], axis=1).astype(np.float32)
    return out, _feet(g)


_ROOTS: dict[str, "str | None"] = {}


def _pack_root_of(path: str) -> str | None:
    """The scenery pack holding ``path``: the nearest folder above it with
    an ``Earth nav data`` folder (any case), else ``None`` (memoised per
    folder)."""
    d = os.path.dirname(os.path.abspath(path))
    if d not in _ROOTS:
        _ROOTS[d] = _walk_up(d)
    return _ROOTS[d]


def _walk_up(d: str) -> str | None:
    for _ in range(12):
        try:
            if any(n.lower() == "earth nav data" for n in os.listdir(d)):
                return d
        except OSError:
            return None
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up
    return None


def _cache_path_for(pack_root: str, mod_cache_root: str | None = None) -> str | None:
    """``<mod cache>/<pack folder name>/o4_agp_floors.cache`` (``None``
    without a mod cache)."""
    if mod_cache_root is None:
        try:
            import O4_File_Names as FNAMES
            mod_cache_root = FNAMES.airport_mod_cache_root()
        except (ImportError, AttributeError, OSError):
            mod_cache_root = None
    if not mod_cache_root or not pack_root:
        return None
    from .dsf import mod_cache_dir
    return os.path.join(mod_cache_dir(mod_cache_root, os.path.basename(
        os.path.normpath(pack_root))), CACHE_NAME)


def _load(cpath: str) -> dict:
    if cpath in _OPEN:
        return _OPEN[cpath]
    pieces: dict = {}
    try:
        with open(cpath, "rb") as fh:
            doc = pickle.load(fh)
        if isinstance(doc, dict) and doc.get("version") == VERSION:
            pieces = dict(doc.get("pieces") or {})
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ValueError):
        pieces = {}
    _OPEN[cpath] = {"pieces": pieces, "dirty": False}
    return _OPEN[cpath]


def _stamp(path: str) -> tuple[int, float] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return int(st.st_size), float(st.st_mtime)


def floors_of(path: str, flat: float, mod_cache_root: str | None = None) -> np.ndarray:
    """The floors (:func:`_parse`) of the PRISTINE file of ``path``, through the
    pack's floor cache (module doc)."""
    return _record(path, flat, mod_cache_root)["floors"]


def feet_of(path: str, flat: float, mod_cache_root: str | None = None) -> np.ndarray:
    """The FEET of the PRISTINE file of ``path`` (module doc), through the
    same cache record as its floors."""
    return _record(path, flat, mod_cache_root)["feet"]


def _record(path: str, flat: float, mod_cache_root: str | None = None) -> dict:
    """The piece's cache record ``{"floors", "feet", ...}`` (module doc)."""
    from .file_hash import sha256_file_or_none
    from .pack import authored_source
    root = _pack_root_of(path)
    src = (authored_source(path, root)[0] if root else None) or path
    cpath = _cache_path_for(root, mod_cache_root) if root else None
    st = _stamp(src)
    if cpath is None or st is None:
        floors, feet = _parse(src, flat)
        return {"floors": floors, "feet": feet}
    rel = os.path.relpath(path, root)
    with _LOCK:
        rec = _load(cpath)
        got = rec["pieces"].get(rel)
        if got is not None and got["flat"] == float(flat) and got["size"] == st[0]:
            if got["mtime"] == st[1]:
                return got
            if got["sha256"] is not None and sha256_file_or_none(src) == got["sha256"]:
                got["mtime"] = st[1]
                rec["dirty"] = True
                return got
    out, feet = _parse(src, flat)
    box = (tuple(float(v) for v in out[:, :, [0, 2]].reshape(-1, 2).min(axis=0))
           + tuple(float(v) for v in out[:, :, [0, 2]].reshape(-1, 2).max(axis=0))
           if out.shape[0] else None)
    with _LOCK:
        rec = _load(cpath)
        got = {"size": st[0], "mtime": st[1], "flat": float(flat),
               "sha256": sha256_file_or_none(src), "floors": out, "box": box, "feet": feet}
        rec["pieces"][rel] = got
        rec["dirty"] = True
    return got


def flush() -> int:
    """Write every cache a read added to (temp file + ``os.replace``);
    returns the files written.  A refused write is dropped silently: the
    next read computes."""
    n = 0
    with _LOCK:
        for cpath, rec in _OPEN.items():
            if not rec["dirty"]:
                continue
            rec["dirty"] = False
            tmp = None
            try:
                os.makedirs(os.path.dirname(cpath), exist_ok=True)
                fd, tmp = tempfile.mkstemp(prefix=".o4_agp_floors.", suffix=".tmp",
                                           dir=os.path.dirname(cpath))
                with os.fdopen(fd, "wb") as fh:
                    pickle.dump({"version": VERSION, "pieces": rec["pieces"]}, fh,
                                protocol=pickle.HIGHEST_PROTOCOL)
                os.replace(tmp, cpath)
                n += 1
            except (OSError, PermissionError, pickle.PicklingError):
                if tmp is not None:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
    return n


def _forget() -> None:
    """Drop the in-process records (tests; a new pack version)."""
    with _LOCK:
        _OPEN.clear()
        _ROOTS.clear()


