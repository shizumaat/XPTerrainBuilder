"""THE ARRANGEMENT'S FRONT, READ ONCE PER BUILD (late-stage prefix reuse
spec §5 phase 2; owner Q21 (b), #1056; issue #803).

``overlay.build_arrangement`` runs the weld, the zones, the apron cut, the
pad terraces and the platforms (its FRONT) on the cells that are NOT late
cells — the late ones (mapped-road ribbons, facade cells, gap pieces) join
only at pass C (30aa).  The last stage re-derives the whole map once or
twice per build (gap pieces, then pad roads, 13a (1)) with exactly the same
non-late cells as the base, so the front is the same computation each time:
HECA, about 40 s per derive.

The front is therefore held for the build (:func:`scoped`, which wraps
``pipeline/build.build``) and served again when its inputs are the same
OBJECTS of the same build and the same VALUES: the non-late cells, the
keepouts and the cut lines (a pickled digest), the grid, the airport and the
law (by identity, held weakly).  A hit hands back the front's product with
every mutable container copied — the registries, the edge report and the
pad-clip record are deep-copied, the lists shallow (a ``Region`` and a
shapely geometry are immutable) — so the passes after it write into fresh
containers exactly as they would after computing it.  Outside a build
(every fixture, every tool) nothing is held."""
from __future__ import annotations

import copy
import functools
import hashlib
import pickle
import threading
import typing as _t
import weakref

__all__ = ["scoped", "front_key", "served", "hold"]

_STATE = threading.local()


def scoped(fn: _t.Callable) -> _t.Callable:
    """Hold the arrangement front for the duration of ``fn`` (one build)
    on the calling thread; nothing outlives the call."""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        outer = getattr(_STATE, "memo", None)
        _STATE.memo = {} if outer is None else outer
        try:
            return fn(*args, **kwargs)
        finally:
            if outer is None:
                _STATE.memo = None
    return wrapped


def front_key(non_late: tuple, classification, grid: float) -> bytes | None:
    """The VALUE half of the key, or ``None`` outside a build (no memo)."""
    if getattr(_STATE, "memo", None) is None:
        return None
    # a cell's ID is not read by the front (the weld orders by POSITION,
    # ``weld.weld_cells``; regions carry no id) and the last stage renumbers
    # cells it never changed (measured HECA: 20 ``gapapron`` cells, ids only)
    cells = tuple((c.role, c.ref, c.ring, c.holes, c.code_number, c.code_letter,
                   c.side, c.kind, c.evidence) for c in non_late)
    blob = pickle.dumps((cells, tuple(classification.keepouts),
                         tuple(classification.cut_lines), float(grid)), protocol=5)
    return hashlib.sha256(blob).digest()


#: fronts held per build: the base map, the ribbon-free stage-1 map and the
#: last stage's maps may interleave (each holds its own non-late set)
HELD = 3


def served(key: bytes | None, airport, law) -> dict | None:
    """The front held under ``key`` for this airport and law, copied for a
    fresh use; ``None`` on a miss."""
    memo = getattr(_STATE, "memo", None)
    got = memo.get(key) if (key is not None and memo) else None
    if got is None or got["airport"]() is not airport or got["law"]() is not law:
        return None
    memo[key] = memo.pop(key)                       # most recently used last
    return _fresh(got["front"])


def hold(key: bytes | None, airport, law, front: dict) -> None:
    """Keep ``front`` (a copy) among this build's :data:`HELD` fronts."""
    memo = getattr(_STATE, "memo", None)
    if key is None or memo is None:
        return
    try:
        refs = (weakref.ref(airport), weakref.ref(law))
    except TypeError:                                   # pragma: no cover
        return
    memo.pop(key, None)
    memo[key] = {"airport": refs[0], "law": refs[1], "front": _fresh(front)}
    while len(memo) > HELD:
        memo.pop(next(iter(memo)))


#: the front's MUTABLE records, deep-copied together (one memo, so a value
#: shared between two of them — the platform record inside the pad-clip
#: record — stays shared in the copy)
_DEEP = ("reg", "erep", "pad_clip", "plat")


def _fresh(front: dict) -> dict:
    out = copy.deepcopy({k: front[k] for k in _DEEP if k in front})
    for name, value in front.items():
        if name not in _DEEP:
            out[name] = list(value) if isinstance(value, list) else value
    return out
