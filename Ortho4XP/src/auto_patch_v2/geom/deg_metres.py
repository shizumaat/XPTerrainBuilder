"""METRES PER DEGREE at a latitude, computed and never memoised (moved from
``model/frame`` unchanged so ``geom`` readers take the same number;
``model/frame`` re-exports it).  Pure arithmetic; ``geom`` imports nothing
of v2.  Nothing here names an airport.
"""
from __future__ import annotations

import math

__all__ = ["m_per_deg_exact"]


def m_per_deg_exact(lat: float) -> tuple[float, float]:
    """``(metres per degree of latitude, of longitude)`` at ``lat``,
    computed and NOT memoised.

    ``anchor_rule._m_per_deg`` buckets on ``int(lat * 1e4)``, so whoever
    calls it FIRST inside a bucket fixes the value every later caller
    sees — this lane measured the consequence in round 1 (a ring node at
    exactly 50 m of longitude reads 50.00000000000935 cold and
    49.99999999998842 once the bucket was warmed at 40.00009 N, and
    `test_a_basin_wall_follows_its_ring_...` flips).  §16g (7)'s scaling
    is wanted ONCE per cluster, so the memo buys nothing here and taking
    it would make this law an order-dependence for every reader after
    it.  The memo's own defect is NAMED, not fixed here: it is another
    law's instrument."""
    r = math.radians(lat)
    return (111_132.954 - 559.822 * math.cos(2 * r) + 1.175 * math.cos(4 * r),
            111_412.84 * math.cos(r) - 93.5 * math.cos(3 * r))
