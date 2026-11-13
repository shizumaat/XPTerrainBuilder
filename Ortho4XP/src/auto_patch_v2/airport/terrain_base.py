"""#1884 round 2 (A): A BUILDING AUTHORED ON ITS AUTHOR'S TERRAIN STANDS
ON OURS — the terrain-carried base.

A pack author who raised a hilltop house to HIS terrain drew its walls
starting 33.6 m over the placement's zero (LOWS, ``domiki_lows_14`` at
47.74974, 13.00860: 48 houses share one datum 435.51 m; the hill under
this one reads 474.5 m).  Every wall of it is ELEVATED (§13 (1):
``base_y`` above ``[rebake] elevated_base_m`` in the frame), nothing of
the placement stands under it, so §16 (3) wrote it on the ground under
its own footprint with its AUTHORED y kept — the whole house 33.6 m in
the air — and its unit (``fu:1:263``) took a zero of ``ground − 0``.

A walled structure authored in the air over NOTHING whose rigid
placement would not even clear our ground is the author's terrain
profile, not a lift: its walls' lowest plane ``b`` is its base.  The
WITNESS — (1), (2) and (4), else nothing changes (owner RULINGS
2026-11-13r: "if there's any doubt, objects stay with their group where
the author placed them"):

1. every WALLED part (not a line, not scatter, not a deck's or a plate's,
   solid height at least ``[placement] chain_min_height_m``) is in the
   air: its ``base_y`` above ``elevated_base_m``; ``b`` is the lowest
   plane of those bases (``footprint_unit``'s :data:`PLANE_SHARE` of
   them within :data:`AUTHOR_GROUND_M`);
2. the frame carries no authored lift (a lifted frame stands on its
   author's ground already, ``footprint_unit._wall_base``);
3. (MEASURED, no longer a gate) the MARGIN ``frame_zero + b − G``:
   ``frame_zero`` the zero X-Plane stands the rigid row at
   (``adapted_riders.frame_zero``) and ``G`` the median design surface
   under the walled parts (LOWS: 435.51 + 33.6 − 471.6 = −2.5).  The spec
   (§3 A) refused a base that clears our ground by more than
   ``elevated_base_m``; the owner REJECTED that (RULINGS 2026-11-13y (2):
   "A building can't be completely in the air, there must either be some
   structure or terrain supporting it") — such a building stands on our
   terrain too, and is counted (``terrain_carried_over_ground``) and
   named in its reason for the owner's read;
4. nothing carries it: the caller asks only where the carrier search
   found nothing (``placement_file._own_ground_file``) or the unit has no
   foot at all (``footprint_unit._wall_base``'s footless branch) — and NO
   STRUCTURE STANDS UNDER IT (:func:`_supported`): no part outside it whose
   plan box overlaps a wall's and which, in the same frame, reaches from
   below its base plane up to it, and no part of ANOTHER frame overlapping
   at all (two frames' heights are doubt, 13r).  MEASURED at LOWS
   (``domiki_lows_34`` 47.7920, 12.9888): an upper storey authored at
   y +3.8 on its own ground floor is a unit with no foot of its own, and
   without this test 13y's reading dropped it 3.97 m through that floor.

A piece with no walled part (a roof, a canopy) and no carrier keeps
§16 (3)'s own ground with its authored y (13y (3)).  NO LAW CONSTANT LIVES HERE: the three keys are
``[placement]``'s and ``[rebake]``'s, the plane constants
``footprint_unit``'s.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from . import anchor_rule as _ar
from .footprint_unit import AUTHOR_GROUND_M, PLANE_SHARE

__all__ = ["TerrainLaw", "TERRAIN_CARRIED", "law_of", "is_walled", "unit_base", "seat"]

#: the anchor reason's mark (after §16 (3)'s own-ground stem, which every
#: regrouping pass still reads: a group the law finds is doubt, 13r)
TERRAIN_CARRIED = "base is the author's terrain"


@_dc.dataclass(frozen=True)
class TerrainLaw:
    """What the witness reads (module doc)."""

    surface: _ar.Surface
    authored: tuple = ()           # ``adapted_riders.authored_zeros``
    wall_min_m: float = 0.0        # ``[placement] chain_min_height_m``
    elevated_base_m: float = 0.0   # ``[rebake] elevated_base_m``
    split_tol_m: float = 0.0       # ``[placement] split_tol_m``
    #: every part of the plan: ``(pid, frame, base_y, top_y, box)``
    parts: tuple = ()


@_dc.dataclass(frozen=True)
class _Witness:
    """``b`` the walls' base plane, ``margin`` = frame zero + b − G."""

    b: float
    margin: float

    def over_ground(self, law: TerrainLaw) -> bool:
        """Would the rigid row stand the base clear over our ground (13y (2))?"""
        return self.margin > law.elevated_base_m


def law_of(surface: _ar.Surface, plan: _t.Any, wall_min_m: float,
           elevated_base_m: float, split_tol_m: float = 0.0
           ) -> "TerrainLaw | None":
    """The witness's law over ``plan``; ``None`` (disarmed) where either
    threshold is not positive."""
    if wall_min_m <= 0.0 or elevated_base_m <= 0.0:
        return None
    from .adapted_riders import authored_zeros
    parts = tuple((p.pid, _frame(u), float(p.base_y),
                   float(p.base_y) + float(getattr(p, "height_m", 0.0) or 0.0),
                   tuple(p.box))
                  for u in getattr(plan, "units", ()) for m in u.members
                  for p in m.parts if getattr(p, "box", None))
    return TerrainLaw(surface, authored_zeros(getattr(plan, "authored_seats", ())
                                              or ()),
                      float(wall_min_m), float(elevated_base_m), float(split_tol_m),
                      parts)


def _frame(u: _t.Any) -> tuple:
    """A unit's frame key: its anchor and authored lift."""
    return (tuple(round(float(q), 9) for q in getattr(u, "anchor", ())),
            float(getattr(u, "agl_m", 0.0) or 0.0))


def _supported(walled: _t.Sequence[_t.Any], b: float, frame: tuple,
              own: _t.AbstractSet[int], law: TerrainLaw) -> bool:
    """_Witness (4)'s STRUCTURE test (module doc): does any part outside
    ``own`` overlap a wall of ``walled`` in plan and, in ``frame``, reach
    from under the base plane ``b`` up to it — or belong to another frame?"""
    boxes = [tuple(p.box) for p in walled if getattr(p, "box", None)]
    for pid, fr, base, top, bx in law.parts:
        if pid in own or not any(_overlap(bx, w) for w in boxes):
            continue
        if fr != frame:
            return True
        if base < b - AUTHOR_GROUND_M and top >= b - AUTHOR_GROUND_M:
            return True
    return False


def _overlap(a: tuple, c: tuple) -> bool:
    return a[0] <= c[2] and a[2] >= c[0] and a[1] <= c[3] and a[3] >= c[1]


def is_walled(p: _t.Any, m: _t.Any, wall_min_m: float) -> bool:
    """_Witness (1)'s WALLED part: solid height ``>= wall_min_m``, not a
    line or scatter piece, not part of a deck or a plate."""
    if getattr(p, "line", False) or getattr(p, "scatter", False):
        return False
    if m is not None and (getattr(m, "deck_kind", "")
                          or getattr(m, "plate_y", None) is not None):
        return False
    return float(getattr(p, "height_m", 0.0) or 0.0) >= wall_min_m > 0.0


def _base_plane(bases: _t.Sequence[float]) -> float:
    """The lowest plane of ``bases``: the median of the lowest
    :data:`AUTHOR_GROUND_M` band holding :data:`PLANE_SHARE` of them."""
    v = sorted(bases)
    need = max(1, math.ceil(PLANE_SHARE * len(v)))
    j = 0
    for i in range(len(v)):
        while v[i] - v[j] > AUTHOR_GROUND_M:
            j += 1
        if i - j + 1 >= need:
            return v[(i + j) // 2]
    return v[len(v) // 2]


def _outline(p: _t.Any) -> list[tuple[float, float]]:
    """The part's base outline: its footprint rings, else its box corners."""
    pts = [(float(a), float(b)) for rg in (getattr(p, "rings", ()) or ())
           for a, b in rg]
    if pts:
        return pts
    b = p.box
    return [(b[0], b[1]), (b[0], b[3]), (b[2], b[1]), (b[2], b[3])]


def _witness(walled: _t.Sequence[_t.Any], anchor: _t.Sequence[float],
            lift: float, law: TerrainLaw) -> "_Witness | None":
    """Witnesses (1)-(2) over ``walled`` (a frame's walled parts) and the
    margin (3) — ``None`` where (1) or (2) fails or the surface reads
    nothing."""
    if not walled or float(lift or 0.0) != 0.0 or len(anchor) < 2:
        return None
    bases = [float(p.base_y) for p in walled]
    if min(bases) <= law.elevated_base_m:
        return None
    from .adapted_riders import frame_zero
    fz = frame_zero(law.surface, anchor, 0.0, law.authored)
    zs = [law.surface(a, b) for p in walled for a, b in _outline(p)]
    zs = [float(z) for z in zs if z is not None]
    if fz is None or not zs:
        return None
    b = _base_plane(bases)
    return _Witness(b, float(fz) + b - _ar._median(zs))


def unit_base(walled: _t.Sequence[_t.Any], anchor: _t.Sequence[float],
              lift: float, law: TerrainLaw, counts: "dict | None" = None,
              own: _t.AbstractSet[int] = frozenset()) -> "float | None":
    """Site 1 (``footprint_unit._wall_base``'s footless branch): the
    unit's wall base ``b`` where the witness holds, else ``None``.
    ``own``: the unit's part ids."""
    w = _witness(walled, anchor, lift, law)
    if w is None:
        return None
    if _supported(walled, w.b, _frame_of(anchor, lift), own, law):
        _count(counts, "terrain_carried_refused_structure")
        return None
    if w.over_ground(law):
        _count(counts, "terrain_carried_over_ground")
    _count(counts, "terrain_carried_units")
    return w.b


def seat(parts: _t.Sequence[_t.Any], m: _t.Any, anchor: _t.Sequence[float],
         lift: float, law: TerrainLaw, counts: "dict | None" = None
         ) -> "tuple[float, float, float, float, float] | None":
    """Site 2 (``placement_file._own_ground_file``): ``(lat, lon, y_zero,
    surface_z, margin)`` for a body of ``parts`` (member ``m``, frame
    ``anchor``/``lift``) nothing carries — its walls' base ``b`` on the
    ground at the base-outline vertex anchor_rule's 11e (2) picks (the
    LOW SIDE where the ground under the base spreads more than
    ``split_tol_m``, else the vertex nearest the base's zero plane) — or
    ``None`` where the witness does not hold."""
    walled = [p for p in parts if is_walled(p, m, law.wall_min_m)]
    w = _witness(walled, anchor, lift, law)
    if w is None:
        return None
    if _supported(walled, w.b, _frame_of(anchor, lift), {p.pid for p in parts}, law):
        _count(counts, "terrain_carried_refused_structure")
        return None
    cands = []
    for p in walled:
        if float(p.base_y) > w.b + AUTHOR_GROUND_M:
            continue
        for a, b in _outline(p):
            z = law.surface(a, b)
            if z is not None:
                cands.append((a, b, w.b, float(z)))
    if not cands:
        return None
    zero = _ar._median([c[3] - c[2] for c in cands])
    pick = min(cands, key=lambda c: (round(abs(c[3] - c[2] - zero), 6), c[0], c[1]))
    spread = max(c[3] for c in cands) - min(c[3] for c in cands)
    if spread > law.split_tol_m:
        pick = _ar._low_side_foot(cands, ())[0]
    if w.over_ground(law):
        _count(counts, "terrain_carried_over_ground")
    _count(counts, "terrain_carried_bodies")
    return pick[0], pick[1], w.b, pick[3], w.margin


def _frame_of(anchor: _t.Sequence[float], lift: float) -> tuple:
    return (tuple(round(float(q), 9) for q in anchor), float(lift or 0.0))


def _count(counts: "dict | None", key: str) -> None:
    if counts is not None:
        counts[key] = counts.get(key, 0) + 1
