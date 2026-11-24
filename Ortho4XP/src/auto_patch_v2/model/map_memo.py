"""THE MEMOS: one per planar map, held by the map's identity and dropped
with it (:func:`per_map`); one value per CONTENT, the last few held
(:class:`ContentSlots`).

A derivation computed once per map and read by several passes keeps its
answer here.  A ``PlanarMap`` is a frozen dataclass of dicts, so it is not
hashable (no ``WeakKeyDictionary``); keying on ``id(pm)`` alone ALIASES —
an id is reused once its map is collected, so a later map could read the
dead one's answer — and a store that is never cleared grows by one entry
per map.  :func:`per_map` keys on the id but checks a WEAK reference to the
map on every read, and the reference's callback removes the entry when the
map is collected: an entry is only ever read by its own map, and the store
holds no more entries than there are live maps (issue #412; the pattern
``model/islands`` used first).

ONE VALUE PER CONTENT (#2206; owner RULINGS 2026-11-24d: "recomputing
anything whose inputs did not change is the defect").  A build derives its
prefix more than once -- the main pass on the base classification, the
late stage on the full one -- and a derivation whose inputs are EQUAL in
both (the map's taxi stretches, which no gap piece, pad road or car lot
touches) is the same value both times.  :class:`ContentSlots` hands back
the object built for content EQUAL to the asked one -- keyed by the
content itself, compared by ``==``, so no digest can collide and no
object identity is trusted (the arrangement memo keyed on identity served
a changed map, lane lmemo) -- and keeps the last ``slots`` contents, most
recent last, as ``constraints/routes.route_pairs`` keeps its tables.  The
object it holds may carry its own answers to pure queries: they are
answers for that content, and so for every asker of it.
"""
from __future__ import annotations

import typing as _t
import weakref as _weakref

__all__ = ["per_map", "ContentSlots", "Same"]

_T = _t.TypeVar("_T")


def per_map(store: dict[int, tuple[_t.Any, dict]], pm: _t.Any) -> dict:
    """``pm``'s own memo in ``store`` (created empty on first asking).  A
    map that cannot be weakly referenced gets a fresh, unstored dict: its
    caller derives again, never reads another map's answer."""
    got = store.get(id(pm))
    if got is not None and got[0]() is pm:
        return got[1]
    key = id(pm)

    def _drop(ref, key=key) -> None:
        held = store.get(key)
        if held is not None and held[0] is ref:   # never a newer map's entry
            del store[key]
    try:
        ref = _weakref.ref(pm, _drop)
    except TypeError:                             # not weak-referenceable
        return {}
    d: dict = {}
    store[key] = (ref, d)
    return d


class ContentSlots(_t.Generic[_T]):
    """The last ``slots`` contents and the object built for each (module
    docstring)."""

    def __init__(self, slots: int = 3) -> None:
        self.slots = int(slots)
        self._held: dict[_t.Hashable, _T] = {}
        #: served / built since import -- a diagnostic, published nowhere
        self.reads = {"hit": 0, "miss": 0}

    def get(self, content: _t.Hashable, build: _t.Callable[[], _T]) -> _T:
        """The object held for ``content`` (now the most recent), else
        ``build()``'s, held in its place."""
        got = self._held.pop(content, None)
        if got is not None:
            self._held[content] = got
            self.reads["hit"] += 1
            return got
        self.reads["miss"] += 1
        got = build()
        self.put(content, got)
        return got

    def peek(self, content: _t.Hashable) -> _T | None:
        """The object held for ``content``, or ``None`` (nothing built)."""
        return self._held.get(content)

    def put(self, content: _t.Hashable, obj: _T) -> None:
        """Hold ``obj`` for ``content`` (now the most recent)."""
        self._held.pop(content, None)
        while len(self._held) >= self.slots:
            del self._held[next(iter(self._held))]
        self._held[content] = obj

    def clear(self) -> None:
        """Hold nothing (a test's clean slate)."""
        self._held.clear()


class Same:
    """An input of a memo key read by its IDENTITY (an object no value key
    names cheaply: the airport's partition) and HELD by the key, so its
    identity cannot be recycled while the key stands
    (``planar/pack_reads.held_read``)."""

    __slots__ = ("obj",)

    def __init__(self, obj: _t.Any) -> None:
        self.obj = obj

    def __hash__(self) -> int:
        return id(self.obj)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Same) and other.obj is self.obj
