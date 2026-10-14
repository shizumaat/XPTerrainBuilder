"""THE TAXI PROFILE CONTINUES THROUGH A JUNCTION (issue #517; spec §8 /
owner RULINGS 2026-09-09b (2), "taxiways should follow terrain less and be
more like runways").

``solve/design_assemble`` states the taxi design profile as the second
difference of z at every INTERIOR station of each ``taxi_centerline``
breakline.  A breakline ENDS where taxiway centrelines meet, so the station
where one taxiway runs straight on into the next carried no curvature cost
at all, and the solve was free to put a kink there: SPJC taxiway L read a
+2.99 % grade change at one such vertex (all three centrelines meeting
there end at it), against <= 1.23 % once the station is priced.

This module writes the SAME second-difference row, at the SAME
``[design] taxi_profile`` weight, at every pair of taxi centreline ends
that meet at one vertex and continue within
``[design] taxi_profile_through_max_deg`` of straight.  A T or a cross
(the branch leaves at ~90 deg) is a turn an aircraft takes slowly, not a
profile it rolls along, and takes no row.  Soft rows only: nothing here is
hard, and nothing reads which airport it is building.
"""
from __future__ import annotations

import collections
import math
import typing as _t

from ..model.planar import PlanarMap

__all__ = ["second_difference", "deflection_deg", "through_junction_pairs",
           "through_junction_rows"]


def second_difference(planar: PlanarMap, a: int, m: int, c: int
                      ) -> tuple[tuple[int, float], ...] | None:
    """The scaled second difference of z at ``m`` between ``a`` and ``c``
    (the stencil every chain-curvature row uses), or ``None`` when two of
    the three stations coincide."""
    if len({a, m, c}) < 3:
        return None
    (ax, ay), (mx, my), (cx, cy) = (planar.vertices[i].xy for i in (a, m, c))
    dp, dn = math.hypot(mx - ax, my - ay), math.hypot(cx - mx, cy - my)
    if dp <= 1e-6 or dn <= 1e-6:
        return None
    sc = 0.5 * (dp + dn)
    return ((c, sc / dn), (m, -sc * (1.0 / dn + 1.0 / dp)), (a, sc / dp))


def deflection_deg(planar: PlanarMap, a: int, m: int, c: int) -> float | None:
    """The plan turn, in degrees, of the path ``a -> m -> c`` at ``m``
    (0 = straight on, 180 = straight back); ``None`` if degenerate."""
    (ax, ay), (mx, my), (cx, cy) = (planar.vertices[i].xy for i in (a, m, c))
    v1, v2 = (mx - ax, my - ay), (cx - mx, cy - my)
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 <= 1e-6 or n2 <= 1e-6:
        return None
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def through_junction_pairs(planar: PlanarMap, max_deg: float
                           ) -> list[tuple[int, int, int]]:
    """Every ``(a, m, c)``: ``m`` the END vertex of two taxi centreline
    breaklines (or both ends of one closed chain), ``a`` and ``c`` their
    stations next to it, and the path ``a -> m -> c`` turning at most
    ``max_deg``.  Sorted, so the rows are written in a fixed order."""
    ends: dict[int, list[int]] = collections.defaultdict(list)
    for bl in planar.breaklines.values():
        if bl.kind != "taxi_centerline":
            continue
        ch = bl.vertices(planar)
        if len(ch) < 2:
            continue
        ends[ch[0]].append(ch[1])
        ends[ch[-1]].append(ch[-2])
    out: list[tuple[int, int, int]] = []
    for m in sorted(ends):
        nb = sorted(set(ends[m]))
        for i in range(len(nb)):
            for j in range(i + 1, len(nb)):
                ang = deflection_deg(planar, nb[i], m, nb[j])
                if ang is not None and ang <= max_deg:
                    out.append((nb[i], m, nb[j]))
    return out


def through_junction_rows(planar: PlanarMap, rows: _t.Any, weight: float,
                          max_deg: float) -> int:
    """Write one ``taxi_profile`` curvature row per through-junction pair
    (``through_junction_pairs``) into ``rows``; the number written."""
    n = 0
    for a, m, c in through_junction_pairs(planar, max_deg):
        terms = second_difference(planar, a, m, c)
        if terms is not None and rows.add(terms, 0.0, weight,
                                          ("taxi_profile_junction", m)):
            n += 1
    return n
