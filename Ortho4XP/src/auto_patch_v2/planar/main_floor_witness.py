"""THE MAIN FLOOR IS WHERE ITS PARTS STAND (owner RULINGS 2026-11-10n;
spec ``docs/specs/two-level-regions-20261103.md`` §18.1).

Owner, 2026-11-10T21:37Z: "It should be flush with the bottom of the
garage, which should stay seated as part of the terminal object group ...
All the objects in the vicinity there should stay as a group, then terrain
is cut or lifted to meet the various levels the author made."

A passage cut out of its unit's MAIN FLOOR (``level_regions._upper_floors``)
leaves the main floor wherever the passage seed's walls and roads do not
reach.  The main floor itself was read off every lower part of the unit
(``low_level.plan_low``: the footprints of the parts a storey under the
frontage, closed by ``pad_frontage_m``), so it also holds ground no
main-floor part stands on: the bands between the garage and the lots, the
slivers between the passage's lanes under the deck.  The author made no
level there at the main floor; that ground is the passage's, at the
garage's base.

A PIECE OF THE MAIN FLOOR (:func:`unwitnessed`) -- a connected part of the
host's upper-floor regions left after the cut, their riser strips aside --
JOINS THE PASSAGE where:

* it lies within two risers of the passage level (it meets it across the
  riser the cut left between them); pieces meeting across a neck narrower
  than two risers are two pieces;
* no part of the seed's unit stands on it at the main floor: no part whose
  authored base lies within one ``PLANE_BAND_M`` of the floor's plane
  (``top_y + y_lo`` of its level record) overlaps it by :data:`WITNESS_M2`;
* it fronts no pad of its block standing at or over the main floor: a piece
  within two risers of the held block, or of another level of the block at
  the main floor's plane (one ``PLANE_BAND_M``), is the hall's lower storey
  at its own facade and keeps the main floor (the riser off the block stays
  one storey, and no riser is minted against a floor the piece shares).

MEASURED KMCI ``building26`` (capture lkmci3): the passage ``p7`` (-4.63,
the garage's walls at y -10.36) beside the main floor ``p1`` (-2.51, the
hall's floor at y -8.23); ``p1`` pieces with no part at the main floor join
it: the 378 m2 band along the garage's north side (between the garage and
the ``p5`` lots level at -4.63 north of it), the 301 m2 band along its south
side, a 22 m2 sliver.  The plaza (planters at -8.2), the facade strip by the
garden (glazing at -8.1), the road plates north of the deck (-8.0 / -8.1)
and the strip over the tunnel (the garage aisle's slabs at -9.2 / -8.8) keep
the main floor.  The pieces join the level as they are, with the riser
between them (``level_regions._unwitnessed_to_passage``): re-cutting the
level with them in its footprint re-closed it elsewhere and moved its
riser's end against ``building26/p3``, 8 more riser-end steps in the census.

NOT DONE HERE (needs the owner): the parts standing at the main floor ON the
passage.  MEASURED KMCI: a 3.4 m x 377 m road plate (y -8.10, 302.6 m) runs
under the departures deck along the mapped road the passage carries at the
garage's base (300.3 m), and road plates at y -7.9 .. -8.1 cover the deck's
north end; 10n (1) puts that road at the garage's base, 10n (2) the ground at
the plates' level.  The passage keeps them (the plates stand 2.2-2.4 m over
it, as on lkmci2).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area
from ..model.planar import STRIP_SUFFIX

__all__ = ["WITNESS_M2", "unwitnessed", "upper_floor_ys"]

#: a part stands on a piece where its footprint overlaps it by this much
WITNESS_M2 = 1.0


def unwitnessed(unit, to_xy, upper: _t.Mapping[str, float], regs: _t.Sequence,
                L, high, w: float) -> list:
    """The pieces of the upper floors (``upper``: ``{level ref: authored
    floor y}``) among ``regs`` that join the passage level ``L`` (module
    docstring); ``high`` the pads of the block at or over the main floor
    (the held block left by the cut and its main-floor levels), ``w`` the riser
    width, ``unit`` the seed's partition unit, ``to_xy`` the frame entry."""
    if unit is None or not upper or L is None or L.is_empty:
        return []
    floors = sorted(set(float(y) for y in upper.values()))
    near_L = L.buffer(2.0 * w, join_style=2)
    near_B = None if high is None or high.is_empty else high.buffer(2.0 * w, join_style=2)
    U = valid_area(unary_union([r.polygon for r in regs
                                if str(r.ref) in upper and r.polygon is not None]))
    # a neck narrower than two risers joins no two pieces (MEASURED KMCI: the
    # garage's north band and the strip over the tunnel met across a 1 m
    # sliver of the main floor beside the riser's corner)
    opened = valid_area(U.buffer(-w, join_style=2).buffer(w, join_style=2))
    pieces = [valid_area(U.intersection(q.buffer(w, join_style=2)))
              for q in nonempty_polygon_parts(opened)
              if q.intersects(near_L) and (near_B is None or not q.intersects(near_B))]
    if not pieces:
        return []
    on = _standing(unit, to_xy, floors)
    return [q for q in pieces
            if on is None or valid_area(q.intersection(on)).area < WITNESS_M2]


def upper_floor_ys(host: _t.Iterable[str], landings: _t.Mapping[str, dict]) -> dict:
    """``{ref: authored floor y}`` of the upper floors in ``host`` (their
    level records' ``top_y + y_lo``; riser strips and the block aside)."""
    out = {}
    for k in host:
        rec = landings.get(k)
        if k.endswith(STRIP_SUFFIX) or not rec or rec.get("top_y") is None \
                or rec.get("y_lo") is None:
            continue
        out[k] = float(rec["top_y"]) + float(rec["y_lo"])
    return out


def _standing(unit, to_xy, floors: _t.Sequence[float]):
    """The union of the plan footprints of ``unit``'s parts whose authored
    base lies within one ``PLANE_BAND_M`` of one of ``floors``, or ``None``."""
    from ..airport.airside_group_seat import PLANE_BAND_M
    from .low_level import _ring_poly
    stand = [g for m in unit.members for p in m.parts
             if not getattr(p, "line", False)
             and any(abs(float(p.base_y) - y) <= float(PLANE_BAND_M) for y in floors)
             for rg in p.rings if (g := _ring_poly(rg, to_xy)) is not None]
    return valid_area(unary_union(stand)) if stand else None

