"""THE FLAT PLANE AT THE BASE OF OBJECTS IS PAVEMENT (owner RULINGS
2026-10-10o (B); 2026-10-02v (3b); issues #229, #519).

"If objects are connected by a flat plane at their base, this is a strong
indicator that the author created object based roads, paved lots, or
sidewalks and they should be treated as such."  Such a plane is PAVEMENT,
admitted through the gap-sheet path, and never a reason to fuse the
buildings it touches into one pad.

THE WITNESS, read per component of the load-time pack partition
(``Airport.partition``; ``model.rebake.Part``).  A part is a BASE SLAB when
it is:

1. AT GROUND — it has ground feet (it is not an elevated part);
2. AT THE OBJECTS' ZERO — its lowest authored ``y`` is within
   ``base_y_max_m`` of 0;
3. THIN — its solid height (``Part.height_m``) is at most
   ``max_height_m``: a plane with kerbs, never a storey;
4. LARGE — its plan outline reaches ``min_m2``.

Only its OPEN part counts: the outline minus every other part ring of the
partition (the walls, the roofs, the floors above it, the booths standing
on it, whichever object file they come from).  Ground under a roof is the
building's floor and stays its pad.  The open part must be at least
``open_min_share`` of the outline and ``min_m2`` in area.  The slab must
also TOUCH a walled part (``tall_min_m`` solid height, within ``touch_m``,
of any unit): it is the plane at the BASE OF OBJECTS.

MEASURED on the r5b rebake plans (lane slab229): KCLT 3 slabs, 27,663 m2
open (the terminal forecourt ``techos_1`` comp 8 and the
``suelos_interiores`` comp 45 plate); HECA 17, 42,729 m2 (the T3 road and
sidewalk planes, the hangar-tower concrete, twelve ``OB-asphalt`` ground
planes beside buildings); OTHH 4, 4,821 m2; KASE, SPJC none (CYXY, NLWF
have no candidate).  Refused for touching no walled part: KASE's
``Aspen_Rockwall`` and a city plaza, two OTHH Emiri plates, twenty-one
HECA ``OB-asphalt`` planes.

The reading is used in TWO places, and both read THIS function:

* :func:`pad_shades` — with ``leaves_pads`` (``[placement]
  base_slab_leaves_pads``, OWNER-PENDING, off) the slab's open part leaves
  every pad outline, beside the welded decks' shades
  (``cluster_outline.deck_shades``); the pad mint, the pad census and the
  fallback footprint trim read it.  Off, the slab is pavement where no pad
  stands and every pad is as it was.
* ``classify/gap_mint`` — each open part is a GAP SHEET body, so the
  ground under it is graded as groundside pavement.

Only shape lives here, as in all of ``geom``: the law values come in as
:class:`SlabLaw` (``law.tables.base_slab_law``).  Duck-typed on the
partition, like ``deck_shades``.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .cluster_outline import _parts, deck_shades

__all__ = ["SlabLaw", "Slab", "base_slabs", "slab_polygons", "pad_shades"]


class SlabLaw(_t.NamedTuple):
    """The witness's law values (``[placement] base_slab_*``)."""

    max_height_m: float
    base_y_max_m: float
    min_m2: float
    open_min_share: float
    tall_min_m: float
    touch_m: float
    #: OWNER-PENDING (lane slab229 report): the slab's open part also leaves
    #: the pads it lies under.  Off, a slab is pavement only where no pad
    #: stands (the measured HECA pad moves of the ON arm await the owner).
    leaves_pads: bool = False

    @property
    def armed(self) -> bool:
        return self.min_m2 > 0.0 and self.max_height_m > 0.0


class Slab(_t.NamedTuple):
    """One admitted base slab: where it came from and its open part, in the
    planar frame's metres."""

    unit: str
    member: str
    resource: str
    comp: int
    outline_m2: float
    open: Polygon


def _ring_poly(part: _t.Any, to_xy) -> "Polygon | None":
    ps: list[Polygon] = []
    for r in getattr(part, "rings", ()) or ():
        if len(r) < 3:
            continue
        g = Polygon([to_xy(lo, la) for la, lo in r])
        if not g.is_valid:
            g = g.buffer(0.0)
        ps.extend(_parts(g))
    if not ps:
        return None
    if len(ps) == 1:            # the common case: one blob, no union paid
        return ps[0]
    g = unary_union(ps)
    return None if g.is_empty else g


def _is_candidate(part: _t.Any, lw: SlabLaw) -> bool:
    return (bool(getattr(part, "feet", ()))
            and abs(float(part.base_y)) <= lw.base_y_max_m
            and float(getattr(part, "height_m", 0.0)) <= lw.max_height_m)


_MEMO: list = []


#: the plan-box prefilter's margin, in degrees: >= ~9 m of longitude below
#: 40 deg latitude, far over ``touch_m`` — it only ever keeps too much
_NEAR_DEG = 1e-4


def _box_m2(box: tuple) -> float:
    """The plan area of a ``(min_lat, min_lon, max_lat, max_lon)`` box in
    square metres — an upper bound on any outline inside it."""
    a0, o0, a1, o1 = box
    return ((a1 - a0) * 110574.0) * ((o1 - o0) * 111320.0
                                      * math.cos(math.radians(0.5 * (a0 + a1))))


def _near_mask(boxes: np.ndarray, cand: np.ndarray) -> np.ndarray:
    """Which of ``boxes`` (n, 4) come within :data:`_NEAR_DEG` of any of
    ``cand`` (k, 4)."""
    hit = np.zeros(len(boxes), dtype=bool)
    for b in cand:
        hit |= ((boxes[:, 0] <= b[2] + _NEAR_DEG) & (boxes[:, 2] >= b[0] - _NEAR_DEG)
                & (boxes[:, 1] <= b[3] + _NEAR_DEG) & (boxes[:, 3] >= b[1] - _NEAR_DEG))
    return hit


def base_slabs(partition: _t.Any, to_xy, lw: SlabLaw) -> tuple[Slab, ...]:
    """Every base slab of ``partition`` (see the module doc), in unit order.
    ``()`` where the law is disarmed or there is no partition.

    The base of objects is not one object file's: a slab is covered by,
    and touches, the parts of EVERY unit (HECA's ``OB-asphalt`` planes
    carry other files' buildings).  Only parts whose plan box
    (``Part.box``, lat/lon) comes near a candidate's are read, so the cost
    is the candidates', not the pack's."""
    if partition is None or not lw.armed:
        return ()
    for p0, l0, got in _MEMO:
        if p0 is partition and l0 == lw:
            return got
    cands: list = []
    rest: list = []
    for u in (getattr(partition, "units", ()) or ()):
        for m in u.members:
            for q in m.parts:
                if getattr(q, "line", False) or getattr(q, "scatter", False):
                    continue
                if (_is_candidate(q, lw) and float(q.area_m2) > 0.0
                        and _box_m2(tuple(q.box)) >= lw.min_m2):
                    cands.append((u, m, q))
                else:
                    rest.append(q)
    if not cands:
        _MEMO.append((partition, lw, ()))
        return ()
    near = _near_mask(np.array([tuple(q.box) for q in rest], dtype=float).reshape(-1, 4),
                      np.array([tuple(q.box) for _u, _m, q in cands], dtype=float))
    polys = [(q, _ring_poly(q, to_xy)) for q, k in zip(rest, near) if k]
    rings = [g for _q, g in polys if g is not None]
    tall = [g for q, g in polys if g is not None
            and float(getattr(q, "height_m", 0.0)) >= lw.tall_min_m]
    tree = STRtree(rings) if rings else None
    tall_tree = STRtree(tall) if tall else None
    out: list[Slab] = []
    for u, m, q in cands:
        g = _ring_poly(q, to_xy)
        if g is None or g.area < lw.min_m2:
            continue
        if tall_tree is None or not any(
                tall[int(i)].distance(g) <= lw.touch_m
                for i in tall_tree.query(g.buffer(lw.touch_m))):
            continue
        cover = ([rings[int(i)] for i in tree.query(g)]
                 if tree is not None else [])
        op = g.difference(unary_union(cover)) if cover else g
        if not op.is_valid:
            op = op.buffer(0.0)
        if op.area < lw.min_m2 or op.area < lw.open_min_share * g.area:
            continue
        for piece in _parts(op):
            if piece.area >= lw.min_m2:
                out.append(Slab(u.id, m.id, m.resource, int(q.comp),
                                float(g.area), piece))
    got = tuple(out)
    _MEMO.append((partition, lw, got))
    del _MEMO[:-4]
    return got


def slab_polygons(partition: _t.Any, to_xy, lw: SlabLaw) -> list[Polygon]:
    """The open parts of every base slab — the gap mint's extra sheets."""
    return [s.open for s in base_slabs(partition, to_xy, lw)]


def pad_shades(partition: _t.Any, to_xy, lw: SlabLaw):
    """What leaves every pad outline: the welded decks' shades
    (:func:`cluster_outline.deck_shades`) and the base slabs' open parts.
    The ONE reading the pad mint (``classify/evidence``), the pad census
    (``constraints/cluster_pad``) and the fallback trim pass, so they cannot
    disagree.  ``None`` where there is neither."""
    deck = deck_shades(partition, to_xy)
    slabs = slab_polygons(partition, to_xy, lw) if lw.leaves_pads else []
    if not slabs:
        return deck
    got = unary_union(([deck] if deck is not None else []) + slabs)
    if not got.is_valid:
        got = got.buffer(0.0)
    return None if got.is_empty else got
