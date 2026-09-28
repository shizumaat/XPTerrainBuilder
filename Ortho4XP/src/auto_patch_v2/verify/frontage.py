"""``frontage_near_miss`` over the emitted rings (v1
``check_grade._check_frontage_near_miss``; the generator's twin in
``constraints.pads.frontage_near_miss``): for a ``frontage_soft_roles``
ring edge within ``frontage_near_miss_m`` of a pad, BOTH endpoints
unshared with that pad, each endpoint unshared with ANY pad must sit
within ``apron cap · d`` (+ the rounding envelope) of the pad's nearest
ring vertex, ``d`` its own distance to the pad polygon.  Identity is the
vertex id (v2: one node per coordinate at ``min_distinct_spacing_m`` —
the oracle's 0.5 m canonical grid).

THE PAD'S HOLES (spec-author ruling 2026-09-28, lane islands, #77/#73): a
pad is its outer ring MINUS its holes.  A hole-ring vertex is a pad vertex
(identity-reconciled), ``d`` is the distance to the holed pad, and a vertex
inside a hole is judged against that hole ring's vertices — never the
outer ring's."""
from __future__ import annotations

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law.tables import role_cap
from .frame import Patch, Row, noise_m, row

__all__ = ["frontage_near_miss"]


def frontage_near_miss(p: Patch) -> list[Row]:
    law = p.law
    bp = law.tables.structures.building_pad
    near = bp.frontage_near_miss_m
    cap = role_cap(law, "apron")
    if cap is None or near <= 0.0:
        return []
    budget = cap.longitudinal
    pads = [sh for sh in p.shapes if p.is_rigid(sh.role) and len(sh.xy) >= 3]
    soft = [sh for sh in p.shapes if sh.role in bp.frontage_soft_roles and len(sh.xy) >= 3]
    if not pads or not soft:
        return []
    ppolys = [_holed(p, sh) for sh in pads]
    pad_ids = {vid for sh in pads for vid in sh.vertex_ids}
    tree = STRtree(ppolys)
    out: list[Row] = []
    for sh in soft:
        spoly = Polygon(sh.xy)
        if spoly.is_empty:
            continue
        cand = tree.query(spoly, predicate="dwithin", distance=near)
        n = len(sh.ids)
        for pi in cand:
            pad = pads[int(pi)]
            ppoly = ppolys[int(pi)]
            pset = set(pad.vertex_ids)
            fired: set[int] = set()
            for a in range(n):
                b = (a + 1) % n
                if sh.ids[a] in pset or sh.ids[b] in pset:
                    continue
                if LineString([sh.xy[a], sh.xy[b]]).distance(ppoly) > near:
                    continue
                for e in (a, b):
                    vid = sh.ids[e]
                    if vid in pad_ids or e in fired:
                        continue
                    fired.add(e)
                    x, y = sh.xy[e]
                    d = float(ppoly.distance(Point(x, y)))
                    wit = _witnesses(p, pad, x, y)
                    j = min(wit, key=lambda v: (p.xy[v][0] - x) ** 2
                            + (p.xy[v][1] - y) ** 2)
                    de = abs(sh.z[e] - p.z[j])
                    if de <= budget * d + noise_m(law, sh.role):
                        continue
                    grade = de / d if d > 1e-9 else float("inf")
                    out.append(row("frontage_near_miss", (sh.role, pad.role),
                                   "airside", de, 100.0 * grade, 100.0 * budget, d,
                                   (x, y), p.xy[j], sh.key, pad.key))
    out.sort(key=lambda r: -r["magnitude_m"])
    return out


def _holed(p: Patch, sh) -> Polygon:
    """The pad as outer ring minus its hole rings."""
    rings = [[p.xy[v] for v in h] for h in sh.holes if len(h) >= 3]
    if not rings:
        return Polygon(sh.xy)
    poly = Polygon(sh.xy, rings)
    return poly if poly.is_valid else poly.buffer(0)


def _witnesses(p: Patch, pad, x: float, y: float) -> tuple[int, ...]:
    """The pad vertices a soft vertex at ``(x, y)`` is judged against: the
    ring of the hole it stands in, else every ring of the pad."""
    for h in pad.holes:
        if len(h) >= 3 and Polygon([p.xy[v] for v in h]).contains(Point(x, y)):
            return tuple(h)
    return tuple(pad.vertex_ids)
