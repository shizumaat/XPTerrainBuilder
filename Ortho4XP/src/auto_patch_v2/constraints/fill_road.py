"""THE ROAD REACHES THE HIGH SIDE — the rows (owner RULINGS 2026-10-20d;
spec ``docs/specs/road-edge-drop-spec.md`` R3).

Every road vertex the channel ``road_terrace['fill_ramp']`` names
(``airport/fill_ramp``: its distance ``d`` along the road from a landing's
frontage) takes ONE hard one-way row per landing against that block's DATUM
COLUMN ``D`` — the run-out law (``constraints/ramp_runout.
landing_runout_rows``) keyed by route distance::

    y - g * d  <=  z_v - z_D  (<=  y, off the nearest landing)

so the road never falls off the landing faster than its design grade
(``[road_contact] ramp_grade``) and comes down to its own ground at that
grade.  These vertices carry no §37 (6) target or ceiling
(``airport/road_ramp.with_road_ramp`` withdraws them, as the pad road's).  ``D`` is stage
1's constant, so nothing airside follows the road."""
from __future__ import annotations

from ..law import Law
from ..model.constraints import Linear, Source
from ..model.planar import PlanarMap
from ..model.platform import datum_vertices

__all__ = ["GEN", "RULING", "fill_road_rows"]

GEN = "fill_road"
#: registered in ``[design] hard_rulings`` and ``one_way_rulings``
RULING = ("roads.fill_road ramp from the fill "
          "(owner 2026-10-20d R3; issues #712, #1003)")


def fill_road_rows(planar: PlanarMap, law: Law, airport=None) -> list:
    """One row per (road vertex, landing) the channel names."""
    ramp = (getattr(planar, "road_terrace", None) or {}).get("fill_ramp") or {}
    if not ramp:
        return []
    held = datum_vertices(planar, law)
    g = float(law.tables.emit.road_contact.ramp_grade)
    rows: list = []
    for v, items in sorted(ramp.items()):
        near = min(items, key=lambda it: (float(it[3]), it[0]))
        for ref, block, y, d in items:
            D = held.get(block)
            if D is None or D == v:
                continue
            # never above the NEAREST landing (the run-out's upper bound):
            # the road between two landings climbs from one to the other
            hi = float(y) if (ref, block, y, d) == near else None
            rows.append(Linear(((int(v), 1.0), (int(D), -1.0)), float(y) - g * float(d),
                               hi, Source(GEN, RULING, (f"vertex:{v}", ref)),
                               follows=(int(v),)))
    return rows
