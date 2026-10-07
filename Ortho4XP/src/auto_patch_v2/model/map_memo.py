"""ONE MEMO PER PLANAR MAP, held by the map's identity and dropped with it.

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
"""
from __future__ import annotations

import typing as _t
import weakref as _weakref

__all__ = ["per_map"]


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
