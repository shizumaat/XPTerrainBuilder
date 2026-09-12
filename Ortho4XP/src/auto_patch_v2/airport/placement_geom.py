"""THE WRITTEN GEOMETRY (spec ``object-placement-spec.md`` §16b (1)/(4);
owner RULINGS 2026-09-11ap).

What a body's file will actually contain, and the design surface under
it: the samples §16b's cut is pre-tested on, the terrain group a body
stands in, and the samples the plan publishes for the census to read.
ONE reading, so the cut and the instrument cannot disagree.

This lives apart from ``placement_cut`` for the 1,000-line law and for
nothing else; ``_LineCutter.geom_points`` (the sampling itself, which
needs the member's parsed OBJ8) stays with the cutter.
"""
from __future__ import annotations

import typing as _t

from ..model.rebake import Part
from . import anchor_rule as _ar
from . import line_object as _lo                        # noqa: F401

__all__ = ["GEOM_CELL_M", "GEOM_PTS_MAX", "thin_points", "surface_many",
           "_geom_ground", "_geom_span"]

#: §16b (4): the plan cell the WRITTEN GEOMETRY is sampled on, and how
#: many samples a body publishes.  A sampling resolution, never a law:
#: the census reads the ground under the body's own triangles, and the
#: design surface's faces are metres across.  The cap bounds the plan
#: file (LEMD writes ~1,400 bodies) and the farthest-point walk keeps
#: the EXTREMES, which is what a span reading needs.
GEOM_CELL_M = 10.0
GEOM_PTS_MAX = 32


def thin_points(pts: _t.Sequence[tuple[float, float, float]], cap: int
                ) -> tuple[tuple[float, float, float], ...]:
    """``pts`` thinned to ``cap`` by the farthest-point walk (the ONE
    spreading rule, :func:`line_object.farthest_point_stations`) — the
    EXTREMES survive, which is what a span reading needs."""
    if cap <= 0 or len(pts) <= cap:
        return tuple(pts)
    import numpy as np
    ml, mo = _ar._m_per_deg(pts[0][0])
    plan = np.asarray([[p[0] * ml, p[1] * mo] for p in pts], dtype=float)
    keep = _lo.farthest_point_stations(plan, cap)
    return tuple(pts[i] for i in keep.tolist())


def surface_many(surface: _ar.Surface,
                 pts: _t.Sequence[tuple[float, float, float]]) -> list[float]:
    """The design surface under ``pts``, in ONE call where the sampler
    offers one (``surface.many``, the graded interpolator's own vectorised
    form) and point by point otherwise.

    §16b's cut and census both read a body's whole written geometry, so
    the airport asks the surface hundreds of thousands of times: batching
    is most of what pays for the reading (the per-call overhead of a
    Delaunay interpolator dwarfs the interpolation)."""
    if not pts:
        return []
    many = getattr(surface, "many", None)
    if many is not None:
        return [float(z) for z in many([p[0] for p in pts],
                                       [p[1] for p in pts])
                if z is not None and z == z]
    return [float(z) for z in (surface(p[0], p[1]) for p in pts)
            if z is not None]


def _geom_ground(cutter: "_LineCutter", parts: _t.Sequence[Part],
                 tris: _t.Sequence[_t.Sequence[int]], surface: _ar.Surface
                 ) -> tuple[tuple[tuple[float, float, float], ...], float,
                            "float | None"]:
    """§16b (1): ``(the body's written-geometry samples, the RANGE of the
    design surface under them, its MEDIAN)`` — the terrain group a body
    stands in, read once and used three times: the cut's pre-test, the
    coarsening's "within one terrain group" test, and (through the plan's
    published samples) the census's own bar."""
    pts = cutter.geom_points(parts, tris)
    zs = sorted(surface_many(surface, pts))
    if not zs:
        return pts, 0.0, None
    return pts, zs[-1] - zs[0], zs[len(zs) // 2]


def _geom_span(cutter: "_LineCutter", parts: _t.Sequence[Part],
               tris: _t.Sequence[_t.Sequence[int]], surface: _ar.Surface
               ) -> tuple[tuple[tuple[float, float, float], ...], float]:
    """§16b (1): ``(the body's written-geometry samples, the range of the
    design surface under them)``.

    The pre-test of every terrain cut, and the SAME reading the census
    takes (``placement_census.census_v16b``): a body whose own ground
    spans more than ``split_tol_m`` is wider than the terrain it can
    stand on.  Where the plan-box reading of §16 (2) asked five points
    of a hull — which for a carried body is the patch its carrier covers
    — this asks the triangles themselves, and it is bounded by
    :data:`GEOM_PTS_MAX` reads."""
    pts, span, _g = _geom_ground(cutter, parts, tris, surface)
    return pts, span


