"""A TWO-LEVEL HARD DECK READS ITS DATUM OVER ITS DECK PLANE, NEVER OVER ITS
OWN FLOOR (owner RULINGS 2026-11-18f; #2157 KRDU, part A).

A cut-and-cover trench object carries the taxiway deck, the trench walls and
the road floor in ONE ``ATTR_hard_deck`` set (KRDU's ``STH_TML`` / ``CTR_TML``):
its deck ring holds the road floor more than a storey under the deck plane.
The rebake plan's ``deck_datum_z`` is the median of the solved surface under
the ring (``emit/rebake.deck_datum_from_surface``), so the trench floor the
solve cut under it drags the deck's datum down -- the #2157 scout measured
KRDU dsf:obj140 at 113.09 against the taxiway's ~119.

THE DECK PLANE is the resource's dominant near-horizontal hard-deck plate
(``deck_signature.dominant_plate``, the tie to the higher bin); the deck is
TWO-LEVEL when its near-horizontal hard-deck faces more than one storey
(``[building_pad] low_level_min_step_m``) under that plate hold at least
``[bridge] deck_min_area_m2`` of plan.  Its DATUM RING is then the plan
outline of the faces standing within a storey of the plate (closed at
``[bridge] deck_close_m``), the largest piece: the floor never enters it.
A single-level deck answers ``None`` and keeps its whole ring.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..model.frame import XY
from . import deck_signature as _ds
from . import obj8 as _obj8

__all__ = ["DeckPlane", "deck_plane", "deck_plane_ring"]


class DeckPlane(_t.NamedTuple):
    """One two-level deck in its AUTHORED frame: the plate's height ``y``,
    the floor's plan area and lowest face height, and the plan rings
    ``(x, z)`` of the faces standing within a storey of the plate."""

    y: float
    floor_m2: float
    floor_y: float
    rings: tuple[tuple[tuple[float, float], ...], ...]


def deck_plane(cache: _obj8.ResourceCache, path: str, law) -> DeckPlane | None:
    """The two-level reading of resource ``path`` (module doc), or ``None``
    for a single-level deck or one with no hard-deck plate."""
    br = law.tables.structures.bridge
    from .airside_group_seat import storey_m
    storey = storey_m(law)
    plate = _ds.dominant_plate(cache, path, law)
    got = _ds._faces_memo(cache, path)
    if plate is None or got is None:
        return None
    f, _ylo, _yhi, hd = got
    flat = (f.ny >= br.deck_plate_normal_y_min) & hd
    y0 = float(plate[0])
    low = flat & (f.cy < y0 - storey)
    floor_m2 = float(f.area[low].sum())
    top = np.flatnonzero(flat & (f.cy >= y0 - storey))
    if floor_m2 < float(br.deck_min_area_m2) or not top.size:
        return None
    rings = tuple(tuple(r) for r in _ds._rings(f, top))
    return DeckPlane(y0, floor_m2, float(f.cy[low].min()), rings)


def deck_plane_ring(o: _obj8.PlacedObject, cache: _obj8.ResourceCache | None,
                    law) -> list[XY] | None:
    """The frame ring placement ``o``'s datum is read over when its hard
    deck is TWO-LEVEL (module doc): the largest piece of its deck plane.
    ``None`` when ``o`` is no flag deck, the cache or the law is not to
    hand, or the deck is one level."""
    if (cache is None or law is None or o.hard_deck is None
            or o.resolved is None or o.deck_kind != "flag"):
        return None
    dp = deck_plane(cache, o.resolved, law)
    if dp is None:
        return None
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [p for p in (Polygon([tuple(q) for q in _ds._place_xz(o, np.asarray(r))])
                         for r in dp.rings) if p.is_valid and p.area > 0.0]
    if not polys:
        return None
    c = float(law.tables.structures.bridge.deck_close_m)
    u = unary_union(polys).buffer(c).buffer(-c)
    if u.is_empty:
        return None
    if u.geom_type != "Polygon":
        u = max(u.geoms, key=lambda g: g.area)
    return [(float(x), float(y)) for x, y in u.exterior.coords[:-1]]
