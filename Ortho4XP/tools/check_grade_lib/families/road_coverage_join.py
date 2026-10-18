"""§37 (9) THE COVERAGE-EDGE JOIN family ``road_coverage_join`` (owner
RULINGS 2026-09-13be), SIDECAR-DECLARED.  Moved verbatim from
``check_grade.py`` (issue #857), which re-exports it."""
from __future__ import annotations

from typing import Dict, List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # §37 (9) THE COVERAGE-EDGE JOIN (owner RULINGS 2026-09-13be):
    # sidecar-declared like ``seam_residual`` — ``road_coverage_join`` =
    # ``[lat, lon, the CORE ribbon's altitude just outside the coverage]``.
    ("road_coverage_join",
     "ROAD at the COVERAGE EDGE off the core ribbon it joins",
     "within"),
)


#: §37 (9) reads the coverage-edge join at the same quantum: the join is a
#: PIN and a pin holds exactly, so anything above this is surface.
_ROAD_JOIN_TOL_M = 0.05


def _check_road_coverage_join(road_join_ll, nodes, ways) -> List[Violation]:
    """§37 (9) THE COVERAGE-EDGE JOIN (owner RULINGS 2026-09-13be): a road
    vertex where the patch's road meets the CORE's levelled ribbon stands
    off the ribbon's own altitude there.

    The core's ``include_roads`` levelling is REMOVED inside the patch
    coverage + 6 m (``O4_Vector_Map.py:1749-1757``), so the patch owns the
    road inside and the core owns it outside, and NOTHING made them agree:
    at KCLT way 10826 station 0 (35.2077398, −80.9290045) the patch's kerb
    stood 2.36 m over the ribbon across 7.9 m of road — a step the driver
    takes at the airport gate and no other family can see (the patch is
    lawful on its own side of the edge, and the core ribbon is not in the
    patch at all).

    The value is LAW INPUT, published per pinned vertex by the solve
    (sidecar ``road_coverage_join``: ``[lat, lon, the ribbon altitude]``),
    and the join is the canonical 11-dp lat/lon identity — never a
    proximity match.  A patch with no key reports nothing, which is every
    patch built before §37 (9).
    """
    if not road_join_ll:
        return []
    by_ll: Dict[Tuple[float, float], Tuple[float, Way]] = {}
    for w in ways:
        for nid, z in zip(w.nids, w.elevs):
            if z is None or nid not in nodes:
                continue
            lat, lon = nodes[nid]
            by_ll.setdefault((round(lat, 7), round(lon, 7)), (float(z), w))
    out: List[Violation] = []
    for rec in road_join_ll:
        if len(rec) < 3 or rec[2] is None:
            continue
        try:
            lat, lon, ribbon = float(rec[0]), float(rec[1]), float(rec[2])
        except (TypeError, ValueError):
            continue
        got = by_ll.get((round(lat, 7), round(lon, 7)))
        if got is None:
            continue
        z, way = got
        if abs(z - ribbon) <= _ROAD_JOIN_TOL_M:
            continue
        v = Violation(
            grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
            de_m=abs(z - ribbon), way_a=way, way_b=way,
            pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=z, elev_b=ribbon)
        v.lat, v.lon = lat, lon
        out.append(v)
    return out
