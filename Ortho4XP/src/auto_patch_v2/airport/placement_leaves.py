"""THE SMALL PIECES OF A BUILDING RIDE ITS WALLS (owner RULINGS 2026-10-14p
(3), #709): "Let's try option 1 for small pieces".

§9 cuts a placement into GROUND GROUPS by the terrain under them, and
§16g (10) (4) seats a LEAF — a body none of whose parts stands
``[placement] chain_min_height_m`` tall — on its own ground.  A building
drawn as many small panels then comes apart on a slope: KASE's
``Garage_1`` (39.2169308, -106.8637059, 13 x 45 m, 83 components of
10 m or less, only three of them 2.5 m or taller) was written as five
pieces seated 2376.28 / 2376.59 / 2377.33 / 2377.43 / 2377.82 on a mesh
falling 1.76 m under it.

THE RULE, inside ONE placement: a leaf ground group within
``[placement] piece_reach_m`` (plan gap of their part boxes, through other
leaves of the same placement) of a WALLED ground group joins it — one
group, one file, one zero (its senior's, the most feet), seated as one
rigid unit; two walls reached through the same pieces are one building.
A leaf reaching no walled group of its placement is left as it was (its
own ground).  The reach is wider than ``footprint_touch_m`` because a
panel building's pieces leave gaps between them (KASE's garage: 0.6 m
between its panels, 1.8–2.3 m across its doorways).  Basins, line
segments and groups holding a line part keep their own laws and never
join.  It runs after §9's coarsening, the plan-overlap bind and the
re-cut by terrain, so nothing later re-cuts what it joined.

NO LAW CONSTANT LIVES HERE: both numbers are handed in.
"""
from __future__ import annotations

import typing as _t

from . import anchor_rule as _ar
from .placement_boxes import box_gap_m, hull_of

__all__ = ["attach_leaves"]


def _walled(raw: _t.Sequence[_t.Any], grp: _t.Sequence[int], chain_h: float) -> bool:
    return any(float(getattr(p, "height_m", 0.0)) >= chain_h
               for i in grp for p in raw[i][0])


def _keeps_own_law(raw: _t.Sequence[_t.Any], grp: _t.Sequence[int]) -> bool:
    return any(raw[i][1] in (_ar.BASIN, _ar.LINE_SEGMENT)
               or any(getattr(p, "line", False) for p in raw[i][0])
               for i in grp)


def attach_leaves(groups: _t.Sequence[_t.Sequence[int]], raw: _t.Sequence[_t.Any],
                  part_boxes: _t.Sequence[_t.Sequence[tuple]], *,
                  reach_m: float, chain_min_height_m: float,
                  counts: dict[str, int]) -> list[list[int]]:
    """``groups`` (lists of ``raw`` indices) with every leaf group joined to
    the walled group(s) it reaches (module doc): groups link where their
    part boxes come within ``reach_m`` and at least one of the two is a
    leaf; a linked set holding a walled group becomes ONE group.  Two walls
    linked only through leaves are one building.  ``reach_m <= 0`` or
    ``chain_min_height_m <= 0`` returns the groups as given."""
    out = [list(g) for g in groups]
    if reach_m <= 0.0 or chain_min_height_m <= 0.0 or len(out) < 2:
        return out
    own = [_keeps_own_law(raw, g) for g in out]
    walled = [not own[k] and _walled(raw, g, chain_min_height_m)
              for k, g in enumerate(out)]
    if not any(walled) or all(walled[k] or own[k] for k in range(len(out))):
        return out
    boxes = [[b for i in g for b in part_boxes[i]] for g in out]
    hulls = [hull_of(bx) for bx in boxes]
    parent = list(range(len(out)))

    def root(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    live = [k for k in range(len(out)) if not own[k]]
    for x, a in enumerate(live):
        for b in live[x + 1:]:
            if walled[a] and walled[b]:
                continue                    # walls link through their pieces only
            if hulls[a] and hulls[b] and box_gap_m(hulls[a], hulls[b]) > reach_m:
                continue
            if any(box_gap_m(p, q) <= reach_m for p in boxes[a] for q in boxes[b]):
                parent[root(a)] = root(b)
    sets: dict[int, list[int]] = {}
    for k in live:
        sets.setdefault(root(k), []).append(k)
    joined: set[int] = set()
    merged: list[list[int]] = []
    for ks in sets.values():
        if len(ks) < 2 or not any(walled[k] for k in ks):
            continue
        merged.append(sorted(i for k in ks for i in out[k]))
        joined.update(ks)
        counts["leaf_groups_on_walls"] = counts.get("leaf_groups_on_walls", 0) \
            + sum(1 for k in ks if not walled[k])
        counts["buildings_joined_by_pieces"] = \
            counts.get("buildings_joined_by_pieces", 0) + 1
    if not joined:
        return out
    return [g for k, g in enumerate(out) if k not in joined] + merged
