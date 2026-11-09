"""WHICH DECK-FAMILY MEMBERS A DECK GOVERNS (#1969).

The screen's deck family (``rebake_plan.screen_of``) is every placement
sharing a deck's anchor spelling (``deck_signature.family_key``: frame
position + AGL).  For a bridge authored as one row that is the bridge —
its piers and railings, which 14.1 rule 4 keeps out of the line class so
they seat WITH the deck.  In a SHARED-DATUM pack it is the whole frame:
KBZN's ``T1`` row places 122 files at one anchor, three of them carpets
flagged ``ATTR_hard_deck``, so its 5.3 km perimeter ``Fence.obj`` (80 m
from any carpet) lost the line class, chained 8,191 bodies over
4 x 3.5 km into ONE footprint unit, and that unit's one zero floated
buildings 15-20 m over their ground.  ``bridge_family`` already refutes
the row as what names a bridge; the relation it uses is CONTACT with the
deck's own footprint.

A member of a deck family is GOVERNED by its deck only where it stands
ON that deck: at least ``[deck] on_fraction`` of its genuine components'
plan length lies within ``touch_m`` of a deck's ``hard_deck`` footprint in its
family (a railing, a pier under it: all of them).  Any contact is not
enough — KBZN's fence meets the terminal, and a carpet in it, at one post
(0.29 m; 0.4 % of its vertices).  A member not on a deck is ordinary: the
line class (10bb) reaches it again.  Pure geometry over the resource
cache.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from . import line_object as _line
from . import obj8 as _obj8

__all__ = ["ungoverned_members"]


def _frame_points(o: _obj8.PlacedObject, cache: _obj8.ResourceCache,
                  step_m: float) -> "np.ndarray | None":
    """``o``'s genuine components in the frame (east, north) as points
    every ``step_m`` along their triangles' plan edges — the share is of
    LENGTH, so a fence sheet two vertices long reads by its run, not its
    vertex count (``obj8._to_frame``, vectorised)."""
    import shapely

    g = cache.geometry(o.resolved) if o.resolved else None
    comps = cache.genuine(o.resolved) if g is not None else []
    if g is None or not comps:
        return None
    t = np.concatenate([np.asarray(c.tris).reshape(-1, 3) for c in comps])
    e = np.unique(np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]),
                          axis=1), axis=0)
    v = g.vertices
    h = math.radians(o.heading_deg)
    s, c = math.sin(h), math.cos(h)
    east = o.xy[0] + v[:, 0] * c - v[:, 2] * s
    north = o.xy[1] - (v[:, 0] * s + v[:, 2] * c)
    xy = np.column_stack([east, north])
    seg = xy[e]
    run = np.hypot(*(seg[:, 1] - seg[:, 0]).T) > step_m       # a riser is its foot
    pts = xy[np.unique(e)]
    if not run.any():
        return pts
    lines = shapely.segmentize(shapely.linestrings(seg[run]), step_m)
    return np.concatenate([pts, shapely.get_coordinates(lines)])


def ungoverned_members(objs: _t.Sequence[_obj8.PlacedObject],
                       family_of: _t.Mapping[str, _t.Hashable],
                       deck_family: _t.AbstractSet[str],
                       cache: _obj8.ResourceCache, touch_m: float,
                       on_fraction: float, rb: _t.Any) -> frozenset[str]:
    """The ids in ``deck_family`` that are not decks, are LINE OBJECTS
    (``rb``: the ``[rebake]`` line law — the one verdict being governed
    changes; a deck-family member is never a scatter body either way) and
    do not stand on a deck of their family (module doc).  ``family_of`` is ``id -> family key``.  A
    member whose geometry cannot be read stays governed (no evidence)."""
    import shapely
    from shapely.ops import unary_union

    decks: dict[_t.Hashable, list] = {}
    for o in objs:
        if (o.id in deck_family and o.deck_kind in ("flag", "signature")
                and o.hard_deck is not None and not o.hard_deck.is_empty):
            decks.setdefault(family_of.get(o.id), []).append(o.hard_deck)
    shape = {k: unary_union(v) for k, v in decks.items()}
    for d in shape.values():
        shapely.prepare(d)
    out = set()
    for o in objs:
        if o.id not in deck_family or o.deck_kind in ("flag", "signature"):
            continue
        d = shape.get(family_of.get(o.id))
        if d is None or not o.resolved or not _line.is_line_object(cache, o.resolved, rb):
            continue
        pts = _frame_points(o, cache, max(touch_m, 0.5))
        if pts is None:
            continue
        if float(shapely.dwithin(shapely.points(pts), d, touch_m).mean()) < on_fraction:
            out.add(o.id)
    return frozenset(out)
