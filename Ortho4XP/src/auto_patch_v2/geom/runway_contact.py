"""RUNWAY CONTACT — which runways' pavements touch, and where a runway
end's height pin sits (owner RULINGS 2026-11-10b (2), (3); issues #1912,
#1945).  A leaf (no v2 import: the runways are duck-typed
``model.airport.Runway``), read by ``airport/runway_peers`` (the
close-ends split and the parallel corroboration) and by
``constraints/runway_profile.end_pin_cases`` (an apt.dat-only runway
takes its touching survey's level) — one witness for both layers."""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import Polygon

__all__ = ["slabs_touch", "pin_xy", "touching_pins"]


def slabs_touch(a: _t.Any, b: _t.Any, gap_m: float) -> bool:
    """Whether runways ``a`` and ``b``'s slabs lie within ``gap_m`` of each
    other (their pavement touches)."""
    return Polygon(a.slab_corners).distance(Polygon(b.slab_corners)) <= gap_m


def pin_xy(rw: _t.Any, k: int) -> tuple[float, float]:
    """Where end ``k``'s height pin sits: the end advanced along the axis by
    its pin station (``RunwayEnd.pin_along``)."""
    (ax, ay), (bx, by) = rw.ends[k].xy, rw.ends[1 - k].xy
    L = math.hypot(bx - ax, by - ay)
    if L <= 0.0:
        return ax, ay
    d = rw.ends[k].pin_along()
    return ax + (bx - ax) / L * d, ay + (by - ay) / L * d


def touching_pins(airport: _t.Any, rw: _t.Any, gap_m: float
                  ) -> list[tuple[tuple[float, float], float, str]]:
    """(2): every surveyed pin of a runway whose slab touches ``rw``'s —
    ``[(pin xy, z, runway id)]``."""
    out = []
    for other in airport.runways:
        if other is rw or not slabs_touch(rw, other, gap_m):
            continue
        for k, e in enumerate(other.ends):
            if e.threshold_elev_m is not None:
                out.append((pin_xy(other, k), float(e.threshold_elev_m), other.id))
    return out
