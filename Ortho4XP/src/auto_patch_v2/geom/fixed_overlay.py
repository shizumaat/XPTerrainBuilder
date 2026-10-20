"""THE FIXED-PRECISION OVERLAY: a union / difference whose result is a
function of the geometry near each point, not of every input or its order.

A floating-point ``unary_union`` of many polygons is input-chaotic: its
cascade order follows the input set, and GEOS's robustness fallback (the
snapping noder, its tolerance sized from the WHOLE input) re-nodes every
edge when any member trips it — so adding one cell can move a vertex a
kilometre away in its last bits, or mint a sub-millimetre hairline part
along a runway edge (issue #486, HECA; #637, KCLT).  Here every operand
is put on a fixed grid (snap-rounding, which is local and needs no
fallback) and a union's members are read in a canonical order.

``geom`` imports nothing of v2.
"""
from __future__ import annotations

import shapely
from shapely.geometry import Polygon

__all__ = ["OVERLAY_GRID_M", "canonical_union", "fixed_difference",
           "is_hairline"]

#: The grid the overlays are rounded to.  1e-6 m is the value the frame's
#: union ladder was measured at (``airport/frame_entry.union``): on 1 mm
#: aligned inputs (the §46 (4) input quantum) it moves only NEW
#: intersection nodes, by <= 0.7 um — far under the 0.5 m identity lattice.
OVERLAY_GRID_M = 1e-6


def _canonical(geoms) -> list:
    """``geoms`` without empties, in an order fixed by their own shape."""
    live = [g for g in geoms if g is not None and not g.is_empty]
    return sorted(live, key=lambda g: shapely.to_wkb(shapely.normalize(g)))


def canonical_union(geoms, grid: float = OVERLAY_GRID_M):
    """The union of ``geoms`` on ``grid``, independent of their order (an
    empty Polygon for none)."""
    live = _canonical(geoms)
    if not live:
        return Polygon()
    return shapely.union_all(live, grid_size=grid)


def fixed_difference(a, b, grid: float = OVERLAY_GRID_M):
    """``a`` minus ``b`` on ``grid`` (``b`` ``None`` or empty: ``a``)."""
    if b is None or b.is_empty or a.is_empty:
        return a
    return shapely.difference(a, b, grid_size=grid)


def is_hairline(poly, width_m: float) -> bool:
    """True when ``poly`` is nowhere ``width_m`` wide: an inward offset of
    half that width leaves nothing.  ``width_m`` <= 0 reads nothing as a
    hairline."""
    if width_m <= 0.0:
        return False
    return bool(poly.buffer(-0.5 * width_m, join_style="mitre").is_empty)
