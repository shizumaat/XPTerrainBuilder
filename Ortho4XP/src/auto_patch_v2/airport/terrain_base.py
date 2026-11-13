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
WITNESS — all four, else nothing changes (owner RULINGS 2026-11-13r:
"if there's any doubt, objects stay with their group where the author
placed them"):

1. every WALLED part (not a line, not scatter, not a deck's or a plate's,
   solid height at least ``[placement] chain_min_height_m``) is in the
   air: its ``base_y`` above ``elevated_base_m``; ``b`` is the lowest
   plane of those bases (``footprint_unit``'s :data:`PLANE_SHARE` of
   them within :data:`AUTHOR_GROUND_M`);
2. the frame carries no authored lift (a lifted frame stands on its
   author's ground already, ``footprint_unit._wall_base``);
3. the authored base does NOT clear our ground: ``frame_zero + b − G <=
   elevated_base_m``, ``frame_zero`` the zero X-Plane stands the rigid
   row at (``adapted_riders.frame_zero``) and ``G`` the median design
   surface under the walled parts (LOWS: 435.51 + 33.6 − 474.5 = −5.4;
   Terminal_LOWS_46's lights, +13.7, are refused and counted);
4. nothing carries it: the caller asks only where the carrier search
   found nothing (``placement_file._own_ground_file``) or the unit has no
   foot at all (``footprint_unit._wall_base``'s footless branch).

A building authored for HIGHER terrain than ours (its rigid base clears
our ground) keeps §16 (3)'s own ground with its authored y (spec §9 (1),
the owner's default).  NO LAW CONSTANT LIVES HERE: the three keys are
``[placement]``'s and ``[rebake]``'s, the plane constants
``footprint_unit``'s.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from . import anchor_rule as _ar
from .footprint_unit import AUTHOR_GROUND_M, PLANE_SHARE

__all__ = ["TerrainLaw", "Witness", "TERRAIN_CARRIED", "law_of", "is_walled",
           "witness", "unit_base", "seat"]

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


@_dc.dataclass(frozen=True)
class Witness:
    """``b`` the walls' base plane, ``margin`` = frame zero + b − G."""

    b: float
    margin: float

    def holds(self, law: TerrainLaw) -> bool:
        return self.margin <= law.elevated_base_m


def law_of(surface: _ar.Surface, plan: _t.Any, wall_min_m: float,
           elevated_base_m: float, split_tol_m: float = 0.0
           ) -> "TerrainLaw | None":
    """The witness's law over ``plan``; ``None`` (disarmed) where either
    threshold is not positive."""
    if wall_min_m <= 0.0 or elevated_base_m <= 0.0:
        return None
    from .adapted_riders import authored_zeros
    return TerrainLaw(surface, authored_zeros(getattr(plan, "authored_seats", ())
                                              or ()),
                      float(wall_min_m), float(elevated_base_m), float(split_tol_m))


def is_walled(p: _t.Any, m: _t.Any, wall_min_m: float) -> bool:
    """Witness (1)'s WALLED part: solid height ``>= wall_min_m``, not a
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


def witness(walled: _t.Sequence[_t.Any], anchor: _t.Sequence[float],
            lift: float, law: TerrainLaw) -> "Witness | None":
    """Witnesses (1)-(3) over ``walled`` (a frame's walled parts) —
    ``None`` where (1) or (2) fails or the surface reads nothing; a
    :class:`Witness` whose :meth:`Witness.holds` answers (3)."""
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
    return Witness(b, float(fz) + b - _ar._median(zs))


def unit_base(walled: _t.Sequence[_t.Any], anchor: _t.Sequence[float],
              lift: float, law: TerrainLaw, counts: "dict | None" = None
              ) -> "float | None":
    """Site 1 (``footprint_unit._wall_base``'s footless branch): the
    unit's wall base ``b`` where the witness holds, else ``None``."""
    w = witness(walled, anchor, lift, law)
    if w is None:
        return None
    if not w.holds(law):
        _count(counts, "terrain_carried_refused_over_ground")
        return None
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
    w = witness(walled, anchor, lift, law)
    if w is None:
        return None
    if not w.holds(law):
        _count(counts, "terrain_carried_refused_over_ground")
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
    _count(counts, "terrain_carried_bodies")
    return pick[0], pick[1], w.b, pick[3], w.margin


def _count(counts: "dict | None", key: str) -> None:
    if counts is not None:
        counts[key] = counts.get(key, 0) + 1
