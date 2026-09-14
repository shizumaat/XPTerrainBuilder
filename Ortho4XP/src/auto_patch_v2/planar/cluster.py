"""§30 (4) THE CLUSTER PAD — the planar-time half of §16f (7) (owner
RULINGS 2026-09-13bj item 1).

Owner, on KCLT 1.0.327: *"Terminal object families still settling at
different elevations resulting in passengers and seat objects ... sitting
on the ground under the building instead of on the floor inside the
building.  Roof elevations sank in some places as well.  These large
complex structures have to be seated as a unit.  As long as it remains
feasible with grade laws and taxiways, etc. it's acceptable to flatten
large apron areas around big terminals if needed to accommodate a large
terminal cluster."*

That is two laws in one sentence and they live on two sides of the
pipeline.  The OBJECT stage's is §16f (7): one unit, one plane, every
member — walls, roofs, floors, the interior furniture, the pieces
standing on the apron.  The DESIGN surface's is §30 (4): the plane the
object stage seats on must EXIST, which means ONE pad over the cluster's
footprint union, and the apron within ``[design] cluster_apron_reach_m``
of it targeting that plane.

**THE CLUSTER MUST BE KNOWN AT PLANAR TIME.**  §16f's family census runs
in the object stage, which runs after the design surface is emitted, so
a design surface that waited for it would be a round late.  The cluster
is therefore derived HERE from the pack partition the load stage already
read (``Airport.partition`` — the same ``units`` / ``contacts`` the
rebake plan carries), through
``airport.placement_family.plan_clusters`` — the SAME
``_clusters`` law the object stage applies to its own candidates, asked
of the plan instead.  One law, two readers; a second derivation of "what
is one terminal" is the census-wrapper defect in geometry
(RULINGS 2026-08-30l).

**WHAT THIS MODULE OWNS.**  The DERIVATION only.  The pad faces the
union stands on, the union polygon and the apron reach are
``constraints/pads.py``'s: ``constraints`` may not import ``planar``
(the layering twin), so the clusters travel the way the pack partition
and the groups already do — computed once at load and carried on
``Airport.clusters``, read from there by every consumer.

**THE PAD IS THE PADS.**  §30 (4) says "one ``building`` pad over the
family's footprint union".  What this module returns is the set of
emitted rigid FACES the union stands on, and
``constraints/pads.py`` prices them as ONE plane — the pad law's own
rows (``pad_flats`` at cap 0 over the merged rim, the hard 1 % ceiling,
one frontage fit).  No new polygon is minted into the planar map: the
union of the cluster's own pad faces IS the footprint union the pack
authored, and a synthesised outline would be a new shape class every
consumer of §28 / §30 would have to be censused against for no
measurable gain (see the MEASURED block of the spec).

No mesh, no environment: the planar map, the law and the airport.
"""
from __future__ import annotations

import typing as _t

from ..airport.placement_family import PlanCluster, plan_clusters
from ..law import Law
from ..model.airport import Airport

__all__ = ["cluster_min_m2", "clusters", "PlanCluster"]

#: The derivation is O(bodies^2) inside a unit and the constraint pass
#: asks for it once per generator.  A tiny memo keyed on the airport
#: object keeps the answer one derivation in fact as well as in law; two
#: entries cover a build's airport and a twin's fixture.
_MEMO: list[tuple[int, _t.Any, float, float, tuple[PlanCluster, ...]]] = []
_MEMO_MAX = 2


def cluster_min_m2(law: Law) -> float:
    """``[placement] cluster_pad_min_m2`` — ONE derivation site.  0
    disarms the cluster pad and leaves every pad its own plane."""
    return float(law.tables.structures.placement.cluster_pad_min_m2)


def _touch_m(law: Law) -> float:
    """§16g (1) (owner RULINGS 2026-09-13bo): ``[placement]
    footprint_touch_m`` — THE CLUSTER IS THE FOOTPRINT UNIT, so the
    design surface groups by the same 0.5 m touch the object stage
    binds by.  Until 13bo this read ``contact_eps_m`` (2 mm) and the two
    sides would have grouped differently."""
    return float(law.tables.structures.placement.footprint_touch_m)


#: §16g (8)/(9) (owner RULINGS 2026-09-14w): WHY a derivation came out
#: empty — the gate that closed, so a silent ``()`` is never mistaken for
#: "this airport has no terminal".  Read by the build's own say-line.
WHY: dict[str, object] = {}


def clusters(airport: Airport, law: Law) -> tuple[PlanCluster, ...]:
    """§16f (7)'s clusters of this airport's pack, or ``()`` where the
    law is disarmed or no pack was read."""
    min_m2 = cluster_min_m2(law)
    eps = _touch_m(law)
    part = getattr(airport, "partition", None)
    WHY.clear()
    WHY.update(min_m2=min_m2, touch_m=eps,
               partition=part is not None,
               units=len(getattr(part, "units", ()) or ()))
    if min_m2 <= 0.0 or eps <= 0.0 or part is None or not getattr(part, "units", ()):
        WHY["gate"] = ("law disarmed" if min_m2 <= 0.0 or eps <= 0.0
                       else "no pack partition" if part is None
                       else "partition carries no units")
        return ()
    key = id(airport)
    for k, ap, m0, e0, got in _MEMO:
        if k == key and ap is airport and m0 == min_m2 and e0 == eps:
            return got
    got = tuple(plan_clusters(part, eps, min_m2))
    WHY["clusters"] = len(got)
    if not got:
        # the three gates inside ``plan_clusters``, priced apart so the
        # empty answer names which one closed
        from ..airport.placement_family import (FAMILY_MIN_MEMBERS,
                                                FAMILY_SHARE_MIN)
        WHY["gate"] = (f"plan_clusters: none survived "
                       f"min_members {FAMILY_MIN_MEMBERS} / share "
                       f"{FAMILY_SHARE_MIN} / area {min_m2:,.0f} m2")
    _MEMO.append((key, airport, min_m2, eps, got))
    del _MEMO[:-_MEMO_MAX]
    return got
