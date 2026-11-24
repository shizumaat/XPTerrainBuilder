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
keepouts and the cut lines (a pickled digest), the grid, the law (by
identity, held weakly) and the airport FIELD BY FIELD (by identity) but its
flat-site verdict, which the front reads only through its ground class
(``law.inset_class.ground_class``, compared by value) — the late stage's
derives are handed the main pass's airport WITH its verdict, a new object
(#2206 step 1; the test ``stage_one_ahead.Ahead.rebind`` applies).  A hit hands back the front's product with
every mutable container copied — the registries, the edge report and the
pad-clip record are deep-copied, the lists shallow (a ``Region`` and a
shapely geometry are immutable) — so the passes after it write into fresh
containers exactly as they would after computing it.  Outside a build
(every fixture, every tool) nothing is held."""
from __future__ import annotations

import copy
import dataclasses as _dc
import functools
import hashlib
import pickle
import threading
import typing as _t
import weakref

from ..geom import grid_pickle as _grid_pickle  # noqa: F401  (#1092: front copies carry the grid)

__all__ = ["scoped", "front_key", "served", "hold", "outcomes", "FRONTS_HELD"]

_STATE = threading.local()


def scoped(fn: _t.Callable) -> _t.Callable:
    """Hold the arrangement front for the duration of ``fn`` (one build)
    on the calling thread; nothing outlives the call."""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        outer = getattr(_STATE, "memo", None)
        _STATE.memo = {} if outer is None else outer
        if outer is None:
            _STATE.outcomes = []
        try:
            return fn(*args, **kwargs)
        finally:
            if outer is None:
                _STATE.memo = _STATE.outcomes = None
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


#: fronts held per build (named apart from the retired ``model.platform``
#: registry ``HELD`` — this is a per-build MEMO on the calling thread, not a
#: map registry, and is never captured): the base map, the ribbon-free stage-1 map and the
#: last stage's maps may interleave (each holds its own non-late set)
FRONTS_HELD = 3


def _airport_reads(airport, law) -> tuple:
    """What the front reads of ``airport``: every field but ``flat_site``
    (compared by identity) and the ground class that verdict names."""
    from ..law.inset_class import ground_class
    return (tuple(getattr(airport, f.name) for f in _dc.fields(airport)
                  if f.name != "flat_site"), ground_class(airport, law))


def _same_airport(held: tuple, airport, law) -> bool:
    fields, ground = _airport_reads(airport, law)
    return (len(fields) == len(held[0]) and all(a is b for a, b in zip(fields, held[0]))
            and ground == held[1])


def served(key: bytes | None, airport, law) -> dict | None:
    """The front held under ``key`` for this airport (field by field, its
    flat-site verdict by ground class) and law, copied for a fresh use;
    ``None`` on a miss."""
    memo = getattr(_STATE, "memo", None)
    got = memo.get(key) if (key is not None and memo) else None
    if got is None or got["law"]() is not law or not _same_airport(got["airport"], airport, law):
        _note("computed" if got is None else
              "held_other_law" if got["law"]() is not law else "held_other_airport")
        return None
    memo[key] = memo.pop(key)                       # most recently used last
    _note("served")
    return _fresh(got["front"])


def _note(outcome: str) -> None:
    """One :func:`served` call's outcome, in this build's order (#2206 step
    0); nothing outside a build."""
    seen = getattr(_STATE, "outcomes", None)
    if seen is not None and getattr(_STATE, "memo", None) is not None:
        seen.append(outcome)


def outcomes() -> list[str] | None:
    """This build's :func:`served` outcomes so far, in call order —
    ``served``, ``computed`` (no front held under the value key),
    ``held_other_airport`` / ``held_other_law`` (the value key held for
    another airport or law object) — or ``None`` outside a build.  A clock
    for ``report.json["prefix_clocks"]``, never in a digest."""
    seen = getattr(_STATE, "outcomes", None)
    return None if seen is None else list(seen)


def hold(key: bytes | None, airport, law, front: dict) -> None:
    """Keep ``front`` (a copy) among this build's :data:`FRONTS_HELD` fronts."""
    memo = getattr(_STATE, "memo", None)
    if key is None or memo is None:
        return
    try:
        law_ref = weakref.ref(law)
    except TypeError:                                   # pragma: no cover
        return
    memo.pop(key, None)
    # the airport's fields are the build's own objects, alive for the build
    memo[key] = {"airport": _airport_reads(airport, law), "law": law_ref,
                 "front": _fresh(front)}
    while len(memo) > FRONTS_HELD:
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
