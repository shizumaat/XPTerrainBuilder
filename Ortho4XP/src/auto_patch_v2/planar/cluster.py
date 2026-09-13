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

from shapely.geometry import Polygon, box as _box

from ..airport.placement_family import PlanCluster, plan_clusters
from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["cluster_min_m2", "clusters", "cluster_pad_faces",
           "cluster_polys", "PlanCluster"]

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


def _contact_eps_m(law: Law) -> float:
    return float(law.tables.structures.placement.contact_eps_m)


def clusters(airport: Airport, law: Law) -> tuple[PlanCluster, ...]:
    """§16f (7)'s clusters of this airport's pack, or ``()`` where the
    law is disarmed or no pack was read."""
    min_m2 = cluster_min_m2(law)
    eps = _contact_eps_m(law)
    part = getattr(airport, "partition", None)
    if min_m2 <= 0.0 or eps <= 0.0 or part is None or not getattr(part, "units", ()):
        return ()
    key = id(airport)
    for k, ap, m0, e0, got in _MEMO:
        if k == key and ap is airport and m0 == min_m2 and e0 == eps:
            return got
    got = tuple(plan_clusters(part, eps, min_m2))
    _MEMO.append((key, airport, min_m2, eps, got))
    del _MEMO[:-_MEMO_MAX]
    return got


def cluster_polys(airport: Airport, law: Law) -> list[tuple[PlanCluster, Polygon]]:
    """Each cluster with its footprint union as ONE plan polygon in the
    PLANAR FRAME's metres — the union of its part boxes, which is exactly
    what :func:`airport.placement_family.union_area_m2` measures the area
    of.  The reach and the face selection both read it."""
    out: list[tuple[PlanCluster, Polygon]] = []
    to_xy, _to_ll = airport.frame.transformers()
    for c in clusters(airport, law):
        rects = []
        for la0, lo0, la1, lo1 in c.boxes:
            x0, y0 = to_xy(lo0, la0)
            x1, y1 = to_xy(lo1, la1)
            if x1 > x0 and y1 > y0:
                rects.append(_box(x0, y0, x1, y1))
        if not rects:
            continue
        from shapely.ops import unary_union
        u = unary_union(rects)
        if u.is_empty:
            continue
        out.append((c, u))
    return out


def cluster_pad_faces(planar: PlanarMap, law: Law, airport: Airport
                      ) -> dict[str, list[int]]:
    """``cluster id -> the rigid FACE ids its footprint union stands on``,
    in face-id order.  A cluster holding fewer than two faces still counts
    (its one pad is already one plane) and is kept, so every reader —
    the plane, the apron reach, the publication — sees the same set.

    The test is INTERSECTION with the union itself, never with its hull:
    a terminal's hull spans the apron between its concourses and would
    swallow every stand's own structure (measured at KCLT: the hull is
    864,000 m2 against a 379,000 m2 union)."""
    got: dict[str, list[int]] = {}
    pairs = cluster_polys(airport, law)
    if not pairs:
        return got
    from ..constraints.pads import _pad_polys          # ONE derivation
    polys = _pad_polys(planar, law)
    if not polys:
        return got
    from shapely.strtree import STRtree
    tree = STRtree([p[3] for p in polys])
    for c, u in pairs:
        hit = sorted({int(polys[int(i)][0])
                      for i in tree.query(u, predicate="intersects")})
        if hit:
            got[c.id] = hit
    return got
