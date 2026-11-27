"""A PAD PAST THE RETAINING WALL IS THE UPPER GROUNDSIDE LEVEL (owner
2026-11-26: "yes, everything past the retaining wall is at the upper
groundside level"; RULINGS 2026-11-26c; #2279, lane lfront3).

A unit standing on two floors meets its landside lot a storey up across
its airside floor's wall (``classify/storey_edge``: the storey lots and
their kerb line, the airside floor).  A held pad of the unit that stands
past that wall -- touching the storey lots, with less than a pad's worth
(``[building_pad] min_area_m2``, the block ``plan_up`` refuses to keep)
on the airside floor -- has nothing at the airside level to stand with:
it is the unit's upper level, whole.  It is minted as a landing
``<pad>/p1`` of the unit's MAIN block (its held block over the airside
floor), at the storey's rise, so
it stands at ``z_D + rise`` with the lot it touches (``constraints/
platform.landing_rows``), never at its own airside seat.  MEASURED PHLI:
``building15`` (the kerb canopy ``dsf:obj7697`` over roads -552/-217/-551
and the kerb island past them) was held at 47.56 m by its own seat, 4.1 m
under the forecourt on both sides (gate 1.0.583: -217 3.12 m).

A pad keeping a block on the floor keeps ``plan_up``'s reading (its upper
level where the lots meet it, and every piece of it past the floor).  The
rule reads the floor, the lots and the pack's units, never the airport's
name."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..model.planar import STRIP_SUFFIX, plane_ref

__all__ = ["past_the_wall"]


def past_the_wall(groups: _t.Mapping[str, list], done: dict, storey_lots: _t.Sequence,
                  floor, airport, law, grid: float, reg, up_kind: str,
                  air_of: _t.Callable, others_of: _t.Callable) -> set[str]:
    """Mint every held pad of ``groups`` past ``floor`` as its main
    block's upper landing (module docstring); returns the pads taken
    (their regions go to ``done``).  ``air_of(P)`` -- the airside about a
    pad: the landing keeps a riser off it (MEASURED PHLI: minted whole,
    ``building15/p1`` shared two vertices with the airside floor and stood
    at 47.6 m) -- a riser only, never ``plan_up``'s frontage room: a 4 m
    remnant of the pad at the airside level held the corridor lot beside it
    there (48.1 m, the lot welded to the remnant's rim, 3 m past the kerb's
    reach).  ``others_of(ref, P)`` -- the other pads beside it: a riser
    off them too (MEASURED PHLI: ``building15/p1`` shared vertices with
    ``building11``, the main block, whose flat rows held it at 47.3 m)."""
    if floor is None or floor.is_empty or airport is None or not storey_lots:
        return set()
    from .low_level import unit_share
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    to_xy = airport.frame.entry()
    near = floor.buffer(w, join_style=2)
    polys = {ref: unary_union([r.polygon for r in regs if r.polygon is not None])
             for ref, regs in groups.items()}
    unit: dict[str, _t.Any] = {}

    def unit_of(ref: str):
        if ref not in unit:
            unit[ref] = unit_share(polys[ref], airport, to_xy)[0]
        return unit[ref]
    taken: set[str] = set()
    for ref, P in sorted(polys.items()):
        if ref in done:
            continue                      # a block split already (a lower level)
        rises = [float(y) for g, y in storey_lots if g.distance(P) <= w]
        if P.is_empty or not rises or P.intersection(near).area >= pmin:
            continue
        ui = unit_of(ref)
        main = [(-Q.area, k) for k, Q in polys.items() if k != ref and k not in taken
                and Q.intersects(floor) and ui is not None and unit_of(k) == ui]
        if not main:
            continue
        block = min(main)[1]
        U = P.difference(air_of(P).buffer(w, join_style=2))
        others = others_of(ref, P)
        if others is not None and not others.is_empty:
            U = U.difference(others.buffer(w, join_style=2))
        if U.is_empty:
            continue
        # what the riser leaves is the riser: no remnant of the pad stays at
        # its own airside seat for the lot beside it to front (MEASURED PHLI:
        # a 1 m remnant of ``building15`` held the corridor lot and the
        # landing at 47.2 m through its §28 frontage row)
        S = P.difference(U)
        up = plane_ref(ref, 1)
        tmpl = groups[ref][0]
        done[ref] = ([_dc.replace(tmpl, ref=up, polygon=q) for q in nonempty_polygon_parts(U)]
                     + [_dc.replace(tmpl, ref=up + STRIP_SUFFIX, polygon=q)
                        for q in nonempty_polygon_parts(S)])
        reg.landings[up] = {"block": block, "deck": None, "kind": up_kind,
                            "y": round(min(rises), 3), "area_m2": round(U.area, 1),
                            "past_wall": ref}
        taken.add(ref)
    return taken
