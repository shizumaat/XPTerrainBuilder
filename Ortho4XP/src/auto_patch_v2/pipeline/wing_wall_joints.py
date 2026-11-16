"""A RAMP WING'S WALLS ARE ITS STEP, DECLARED (#2099 G4 W; owner RULINGS
2026-10-03c "the wall is the step", 2026-10-15b the declared wall step,
2026-11-13t a thin retaining wall hides its own step, 2026-11-16d).

A ramp wing's cut (``planar/wing_cut._ramp_cut``) holds the floor between
its walls at their feet and the strips behind them at their tops; the
change of level stands inside each wall's own plan (``WingCut.walls``,
``wing_wall:<ramp>`` ground).  One ``terrace_joints`` record (``kind``
``wall_terrace``) per wall plan, along the plan's OUTLINE (every segment
across the wall crosses it), declares the step: the solved step across it
where the solve put less there than the wall, never more than the wall's
own height (its top over its foot) -- plus the emit's rounding, as
``publication.wall_terrace_joints`` declares a pack retaining wall.  The
strip families forgive a pair across the line up to it and price any
excess.  Nothing here names an airport.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["wing_wall_joints", "LABEL"]

#: the joint's shape label (``wing_wall:<ramp>``, the plan's own ref)
LABEL = "wing_wall"

#: the patch writes elevations to the centimetre (``publication._EMIT_Z_ROUND_M``)
_EMIT_Z_ROUND_M = 0.01


def wing_wall_joints(planar: PlanarMap, law: Law,
                     z: _t.Sequence[float] | None = None) -> list[dict[str, _t.Any]]:
    """The module doc's records, one per ramp wall plan."""
    cuts = [c for c in getattr(planar, "wing_cuts", ()) or () if getattr(c, "walls", ())]
    if not cuts:
        return []
    from shapely.geometry import Point, Polygon

    from .ribbon_steps import _to_ll
    to_ll = _to_ll(planar)
    out: list[dict[str, _t.Any]] = []
    for cut in cuts:
        for ring in cut.walls:
            plan = Polygon(ring).buffer(0.0)
            near = [ln for ln in cut.lines
                    if any(plan.distance(Point(p)) <= 0.5 for p in (*ln.face, *ln.back))]
            height = max((t - f for ln in near for f, t in zip(ln.foot, ln.top, strict=True)),
                         default=0.0)
            step = _solved_step(planar, plan, z) if z is not None else None
            declared = round((height if step is None else min(height, step)) + _EMIT_Z_ROUND_M, 4)
            pts = [list(to_ll(x, y)) for x, y in (*ring, ring[0])]
            out.append({"points": pts, "step_m": declared, "declared_step_m": declared,
                        "faced": False, "kind": "wall_terrace", "faces": [],
                        "shapes": [cut.wall_ref], "gap": False, "roles": ["graded_strip"],
                        "pairs": 0, "length_m": round(plan.length / 2.0, 2),
                        "height_m": round(height, 3),
                        "emitted_step_m": None if step is None else round(step, 3)})
    return out


def _solved_step(planar: PlanarMap, plan, z) -> "float | None":
    """The largest solved step across ``plan``: the vertices within half a
    metre of its outline, the highest less the lowest; ``None`` with fewer
    than two."""
    from shapely.geometry import Point
    x0, y0, x1, y1 = plan.buffer(0.5).bounds
    zs = [float(z[v]) for v, vx in planar.vertices.items()
          if x0 <= vx.xy[0] <= x1 and y0 <= vx.xy[1] <= y1
          and plan.exterior.distance(Point(vx.xy)) <= 0.5 and not math.isnan(float(z[v]))]
    return max(zs) - min(zs) if len(zs) >= 2 else None
