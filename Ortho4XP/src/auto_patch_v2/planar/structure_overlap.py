"""TWO STRUCTURES MAY NOT OVERLAP — the pair test of the structure build
(``planar/structures.build_structures``): parallel mouths beyond 31h's
test (a diverging separation profile, a crossing approach) would be
polygonised into crumbs, so the narrower one is refused loudly — after
the ramps that can yield have been asked to (``unframed_ramp.
overlap_yield``: a run end, 2026-10-08d (1); the cap, owner RULINGS
2026-10-14j).
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from .unframed_ramp import overlap_yield
from .wall_corridor_ramps import KIND as WALL_KIND

__all__ = ["resolve_overlaps"]


def resolve_overlaps(tunnels, footprints, keep: list[bool], siblings: _t.Mapping[str, str],
                     run_limits, at_cap: _t.Mapping[str, str],
                     overlap_refused: dict[str, str], law: Law, gap: float, grid: float,
                     may_replan: bool, refused: list[str]
                     ) -> tuple[dict, dict, dict]:
    """Every overlapping pair of ``tunnels`` (``keep`` / ``refused`` /
    ``overlap_refused`` updated in place): ``(new run limits, ramps to
    steepen to the cap, survivors released from the cap)`` for the
    re-plan.  A survivor that steepened in vain for a bore refused all
    the same is released, and that refusal carried into the re-plan."""
    new_limits: dict[str, tuple[float, str]] = {}
    new_cap: dict[str, str] = {}
    released: dict[str, str] = {}
    for i in range(len(tunnels)):
        for j in range(i + 1, len(tunnels)):
            if not (keep[i] and keep[j]):
                continue
            if siblings.get(tunnels[i].id) == tunnels[j].id:
                continue            # two halves of one corridor meet at their mouth line
            if not footprints[i].intersects(footprints[j]):
                continue
            inter = footprints[i].intersection(footprints[j])
            wall_i, wall_j = tunnels[i].source == WALL_KIND, tunnels[j].source == WALL_KIND
            # a WALL CORRIDOR may not even TOUCH another structure (Law C):
            # a shared ring vertex carries the other's pin into its rows
            # (measured OTHH: a Parking_004 corridor's vertex on the door
            # ramp Parking-Right_000@1's ring — its 8 % rows over 1.6 m
            # yielded 13 mm); the OTHER structure is senior
            touches = (wall_i or wall_j) and (inter.area > 1e-9 or inter.length > grid)
            if inter.area > 1.0 or touches:
                yields, steepen = overlap_yield((tunnels[i], tunnels[j]), (footprints[i], footprints[j]),
                                                run_limits, at_cap, law, gap,
                                                may_replan)
                new_limits.update(yields)
                new_cap.update(steepen)
                if wall_i != wall_j:
                    drop = i if wall_i else j
                else:
                    drop = i if footprints[i].area < footprints[j].area else j
                other = j if drop == i else i
                keep[drop] = False
                line = (f"{tunnels[drop].id}: its corridor overlaps {tunnels[other].id} (not "
                        f"a dual under 31h's separation test)")
                refused.append(line)
                if not (yields or steepen) and at_cap.get(tunnels[other].id) == tunnels[drop].id:
                    # 2026-10-14j: steepened in vain for a bore refused anyway
                    released[tunnels[other].id] = line
                    overlap_refused[tunnels[drop].id] = line
    return new_limits, new_cap, released
