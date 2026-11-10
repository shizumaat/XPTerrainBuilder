"""THE PACK PARTITION'S DECK PRINTS, DERIVED ONCE PER PARTITION OBJECT.

``bridge_family.deck_prints`` over the partition, each deck parsed once,
held for as long as the partition object lives.  One build's prefix runs
(the main map, the ribbon-free map, the last stage's derives) and both of
its readers — the ramp landings (``planar/landing``) and the carried-road
witness (``airport/carried_roads``) — read the SAME partition object, so
its prints, and the memos they carry (``deck_components``' pieces: 94 s of
EDDF's 923 s planar stage, issue #1706), are derived once."""
from __future__ import annotations

import weakref

__all__ = ["partition_prints", "under_a_deck"]

#: ``id(partition) -> (weak reference, its prints)``
_PRINTS: dict[int, tuple] = {}


def partition_prints(part) -> list:
    """The deck model footprints of the pack partition ``part`` (module
    doc), memoised on the partition object."""
    held = _PRINTS.get(id(part))
    if held is not None and held[0]() is part:
        return held[1]
    prints = _derive(part)
    try:
        ref = weakref.ref(part, _forget)
    except TypeError:                         # not weakly referable: not held
        return prints
    _PRINTS[id(part)] = (ref, prints)
    return prints


def under_a_deck(part, to_ll, xys) -> list[bool]:
    """Per plan point ``(x, y)``: does it stand inside a pack deck's model
    footprint (``to_ll(x, y) -> (lat, lon)``, the frame's inverse)?"""
    if part is None or not xys:
        return [False] * len(xys)
    ll = [to_ll(float(x), float(y)) for x, y in xys]
    out = [False] * len(xys)
    for p in partition_prints(part):
        for i, h in enumerate(p.contains_many([a for a, _b in ll], [b for _a, b in ll], 0.0)):
            out[i] = out[i] or bool(h)
    return out


def _forget(ref) -> None:
    """A held partition died: drop its prints (only its own entry)."""
    for k, held in list(_PRINTS.items()):
        if held[0] is ref:
            del _PRINTS[k]


def _derive(part) -> list:
    from . import bridge_family as _bf
    from .placement_cut import _LineCutter

    def _cutter(ui: int, _mi: int, m):
        u = part.units[ui]
        return _LineCutter(m, 0.0, 0, 0.0, 0.0, 0.0,
                           float(u.anchor[0]), float(u.anchor[1]))
    return _bf.deck_prints(part, _cutter)
