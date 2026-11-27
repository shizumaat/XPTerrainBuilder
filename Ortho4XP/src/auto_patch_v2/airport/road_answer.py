"""ONE ROAD-PROFILE ANSWER PER CONTENT, ACROSS THE BUILD'S PREFIX RUNS (#2206,
spec ``docs/specs/stage1-prefix-reuse-20261127.md``).

``road_profile.RoadProfiles.answer`` reads a vertex's position, its DEM
value (the fallback), the ways it may be answered by -- each way's kind,
ref, stations, arclengths and clamped profile, in the order they are
offered, with their radii -- the core's radius and the retaining walls.
Nothing else: the answer is a pure function of those.  The late map's
road vertices and their ways are the main pass's wherever no late cell
reaches them, and the road ramp reads the same vertices again within one
run (``airport/road_ramp``: the route frame, the targets), so the answer
is held here by exactly that content (``geom/item_memo``), the ways by
their CONTENT (never their identity: each run builds its own), and handed
back with the asking run's own way objects (:func:`answer_key`'s caller
rebuilds the ``Answer`` around ``cands[k]``)."""
from __future__ import annotations

import typing as _t

from ..geom.item_memo import ItemMemo
from ..model.map_memo import Same

__all__ = ["ANSWERS", "answer_key"]

#: ``key -> (k, z, kind, ref, lateral, s, t)``: the winning candidate's
#: index (``-1``: the DEM fallback) and the answer's numbers
ANSWERS = ItemMemo("road_profile.answer")
#: a way's content, interned (one object per content: the keys compare by
#: identity first)
_WAYS = ItemMemo("road_profile.way")


def _way(holder: dict, w: _t.Any) -> tuple:
    """``w``'s content key (``holder``: the profiles' own id -> (way, key)
    table, checked by identity)."""
    got = holder.get(id(w))
    if got is None or got[0] is not w:
        c = (w.kind, w.ref, w.xy.dtype.str, w.xy.shape, w.xy.tobytes(),
             w.s.tobytes(), w.z.tobytes())
        got = holder[id(w)] = (w, _WAYS.get(c, lambda: c))
    return got[1]


def answer_key(prof: _t.Any, pt: _t.Sequence[float], dem: float, through: _t.Sequence,
               near: _t.Sequence) -> tuple:
    """The content :meth:`RoadProfiles.answer` reads for one vertex
    (module docstring): ``through`` are ``(way, radius)``, ``near`` ways
    (both after ``skip``)."""
    d = prof.__dict__
    holder = d.setdefault("_way_keys", {})
    walls = d.get("_walls_key")
    if walls is None:
        walls = d["_walls_key"] = tuple(Same(w) for w in prof.walls)
    return (float(pt[0]), float(pt[1]), float(dem), float(prof.radius_m), walls,
            tuple((_way(holder, w), float(r)) for w, r in through),
            tuple(_way(holder, w) for w in near))
