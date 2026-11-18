"""THE ZERO-LEVEL DATUM of a §16g unit whose walls are not its ground
(#2118, owner sim reads OTHH 2026-11-16).

``footprint_unit.plan_unit_datums`` seats a unit on the median ground
under its part centres less its WALLS' authored base (RULINGS 2026-10-22b:
the walls seat the unit).  Two structures have walls that never reach the
plane their author stood them on, and that reading moves them by the depth
of those walls:

* A BASIN.  The patch cuts the pit to the object's own depth, so the part
  centres read the CUT FLOOR and the walls stand on the pit's floor; the
  unit came out at floor ground less floor walls, 4.3 m under the rim the
  patch cut for it (OTHH ``Dewatering_02``: -0.32 where the rim is 3.96;
  owner 18:54:49Z "seated too low, about 2 m below the lip of the
  trench").  The object's zero is the rim (§14 (2)): :func:`rim_unit_zero`
  gives the unit the value ``anchor_rule._basin_rim_anchor`` gives its
  basin bodies, so the group no longer outvotes its own rim (22o keeps ONE
  zero; the rim is it, as a walled plate's datum leads its unit, #1977).
  Only a BASIN ring (``basin_wall:``) is a rim the object's zero stands
  on; a tunnel's or a road pit's ring is not.

* A STRUCTURE ON PILES.  Every wall is a COLUMN (``free_column``'s
  reading, ``[placement] free_column_*``), every column's foot stands a
  storey or more under the object's zero (the piles reach the author's
  sea bed), and the structure
  meets the ground at its zero elsewhere — a pier's land end.  Owner
  19:04:27Z (OTHH 34R approach-light pier): "seat that object lower and
  let it's supports be under water".  :func:`pile_unit_zero` seats the
  unit on those zero-level contacts; the piles bury.

Both read only a unit whose walls ALL stand a storey or more under its
zero (:func:`walls_below_zero`); a building with any wall on its zero
level keeps the walls' reading.
"""
from __future__ import annotations

import statistics as _st
import typing as _t

from . import anchor_rule as _ar
from . import placement_boxes as _pb

__all__ = ["unit_zero", "walls_below_zero", "rim_unit_zero", "pile_unit_zero",
           "RIM_SRC", "PILE_SRC", "BASIN_REF"]

#: the §16g datum sources this module writes
RIM_SRC = "basin_rim"
PILE_SRC = "zero_level"
#: the emitted ring a basin object is cut into (``planar`` names it so); a
#: tunnel's or a road pit's ring is not the object's rim
BASIN_REF = "basin_wall:"


def unit_zero(un: _t.Any, unit_pids: _t.AbstractSet[int],
              parts: _t.Mapping[int, _t.Any], member_of: _t.Mapping[int, _t.Any],
              origin_of: _t.Mapping[int, _t.Sequence[float]],
              rims: _t.Sequence[_t.Any], surface: _t.Any, wall_min_m: float,
              storey_m: float, band_m: float, column: _t.Any = None
              ) -> "tuple[float, str, str] | None":
    """``(zero, where, source)`` for a unit whose walls are not its ground
    (:func:`walls_below_zero`): the RIM of the basin ring it stands in
    (:func:`rim_unit_zero`), else, where every wall is a COLUMN
    (``column``: ``free_column.law_of([placement])``), its zero-level
    contacts (:func:`pile_unit_zero`); ``None`` otherwise — the walls'
    reading stands."""
    mine = [parts[q] for q in sorted(un.pids) if q in parts]
    walls = walls_below_zero(mine, wall_min_m, storey_m)
    if not walls:
        return None
    rz = rim_unit_zero(un.pids, parts, origin_of, rims, surface)
    if rz is not None:
        return rz[0], rz[1], RIM_SRC
    if column is None or len(walls) < max(1, int(column.min_count)) or not all(
            _is_column(p, column) for p in walls):
        return None
    pz = pile_unit_zero(un, unit_pids, mine, member_of, surface, band_m)
    return None if pz is None else (pz, "", PILE_SRC)


def walls_below_zero(mine: _t.Sequence[_t.Any], wall_min_m: float,
                     storey_m: float) -> list:
    """The unit's walled parts (solid height >= ``wall_min_m``, not a line,
    with feet) when EVERY one of their feet stands ``storey_m`` or more
    under the object's zero — the walls of a pit, the piles of a pier;
    ``[]`` when any foot reaches the zero level or there is no wall."""
    if storey_m <= 0.0 or wall_min_m <= 0.0:
        return []
    walls = [p for p in mine if not getattr(p, "line", False) and p.feet
             and float(getattr(p, "height_m", 0.0) or 0.0) >= wall_min_m]
    if not walls or max(float(f[2]) for p in walls for f in p.feet) > -storey_m:
        return []
    return walls


def _is_column(p: _t.Any, law: _t.Any) -> bool:
    """``free_column``'s COLUMN reading of one part: solid height at least
    ``min_h_m``, plan width at most ``max_w_m`` and height at least
    ``aspect`` times it."""
    from .free_column import _plan_box_span_m
    h = float(getattr(p, "height_m", 0.0) or 0.0)
    if not getattr(p, "box", None) or h < law.min_h_m:
        return False
    w = _plan_box_span_m(p.box)
    return w <= law.max_w_m and h >= law.aspect * w


def rim_unit_zero(pids: _t.Iterable[int], parts: _t.Mapping[int, _t.Any],
                  origin_of: _t.Mapping[int, _t.Sequence[float]],
                  rims: _t.Sequence[_t.Any], surface: _t.Any
                  ) -> "tuple[float, str] | None":
    """``(zero, ring ref)`` of a unit a part of which stands in an emitted
    BASIN ring (``anchor_rule.ring_of_part``: its centroid, else its feet):
    the surface at the ring's rim point nearest that part's placement
    origin (``anchor_rule.rim_point``), the basin body's own zero.  The
    lowest part decides, as it does for the body; ``None`` where no part
    stands in a basin ring or the surface reads nothing there."""
    basins = [r for r in rims if str(r.ref).startswith(BASIN_REF)]
    if not basins:
        return None
    mine = sorted((parts[q] for q in pids if q in parts),
                  key=lambda p: (float(p.base_y), p.pid))
    for p in mine:
        origin = origin_of.get(p.pid)
        if not origin:
            continue
        ring = _ar.ring_of_part(basins, float(p.lat), float(p.lon), tuple(p.feet or ()))
        if ring is None:
            continue
        la, lo = _ar.rim_point(ring, float(origin[0]), float(origin[1]))
        z = surface(la, lo)
        if z is not None:
            return float(z), str(ring.ref)
    return None


def pile_unit_zero(un: _t.Any, unit_pids: _t.AbstractSet[int],
                   mine: _t.Sequence[_t.Any], member_of: _t.Mapping[int, _t.Any],
                   surface: _t.Any, band_m: float) -> "float | None":
    """The zero of a unit ON PILES: the median of ``ground - y`` over its
    contacts at the zero level (feet with ``|y| <= band_m``) — its own
    parts ``mine``, and the parts of its members in no unit (``unit_pids``)
    within ``band_m`` of its boxes (a pier's land end, too low to chain).
    ``None`` where no such contact reads a surface."""
    near = list(mine) + _loose_beside(un, unit_pids, member_of, band_m)
    zs = []
    for p in near:
        for f in p.feet or ():
            if abs(float(f[2])) <= band_m:
                g = surface(float(f[0]), float(f[1]))
                if g is not None:
                    zs.append(float(g) - float(f[2]))
    return _st.median(zs) if zs else None


def _loose_beside(un: _t.Any, unit_pids: _t.AbstractSet[int],
                  member_of: _t.Mapping[int, _t.Any], gap_m: float) -> list:
    """The footed parts of ``un``'s members that are in NO unit and stand
    within ``gap_m`` of one of its boxes."""
    boxes = [tuple(b) for b in un.boxes]
    members = {id(member_of[q]): member_of[q] for q in un.pids if q in member_of}
    out = []
    for m in members.values():
        for p in m.parts:
            if p.pid in unit_pids or not p.feet:
                continue
            if any(_pb.box_gap_m(tuple(p.box), b) <= gap_m for b in boxes):
                out.append(p)
    return out
