"""THE WALL-CLASS CLASSIFIER — which pack components are WALL-CLASS.

A pack component is WALL-CLASS when it is thin, tall and long enough
(``[service] retaining_wall_max_width_m`` / ``_min_height_m`` /
``_min_length_m``, read from the ``cfg`` the CALLER supplies), and its
resource does not name a fence (RULINGS 2026-09-29h, Q-72b).  A THICK
component is wall-class too where it retains its own height — slender for
its height and the ground stepping across it by that height (#715,
:func:`_retains_its_height`).

THE ONE implementation, read by three layers: ``classify/retaining_wall``
(§47's wall along a road edge), ``planar/shore`` (RULINGS 2026-09-29a (2):
a wall along the shore) and ``airport/road_ramp`` (RULINGS 2026-10-03c,
#291: the wall between the airside level and a lower lot).

WHY IT LIVES HERE (issue #303).  It was ``classify/retaining_wall``'s,
but ``airport`` may not read ``classify``
(``tests/auto_patch_v2/test_model.py::test_dependency_direction``), and
``airport/road_ramp`` is its third reader.  Nothing about it is a
``classify`` concept: it reads the AIRPORT's own pack partition and a
config record handed to it, so its whole dependency set is ``model`` —
at or below ``airport`` already.  ``classify/retaining_wall`` re-exports
it, so every caller's import path is unchanged.
"""
from __future__ import annotations

import dataclasses as _dc

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.airport import Airport

__all__ = ["WallComponent", "NOT_WALL_RESOURCE_WORDS", "wall_class_components"]


@_dc.dataclass(frozen=True)
class WallComponent:
    """One WALL-CLASS pack component (module docstring: thin, tall, long):
    its footprint pieces (frame xy), its solid height and its source."""

    pieces: tuple
    height_m: float
    resource: str
    comp: int


#: RULINGS 2026-09-29h (Q-72b): a FENCE is not a wall.  A footprint cannot
#: tell a fence from a retaining or sea wall (TFFJ ``beach_fence.obj``:
#: 92 m, 2.38 m, thin), so the pack's own resource name decides: a
#: component whose resource basename names one of these is never wall-class.
NOT_WALL_RESOURCE_WORDS = ("fence", "railing")


def _not_a_wall(resource: str) -> bool:
    base = str(resource or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    return any(w in base for w in NOT_WALL_RESOURCE_WORDS)


def wall_class_components(airport: Airport, cfg) -> list[WallComponent]:
    """THE WALL-CLASS CLASSIFIER, the one implementation: every pack
    component that is thin, at least ``retaining_wall_min_height_m`` tall
    and at least ``retaining_wall_min_length_m`` long.  Read by
    :func:`retaining_pieces` (a wall along a road edge) and by
    ``planar/shore`` (a wall along the shore — owner RULINGS 2026-09-29a
    (2)).  Retaining / sea-wall classes only: a fence resource is never
    wall-class (RULINGS 2026-09-29h, Q-72b)."""
    part = getattr(airport, "partition", None)
    if part is None:
        return []
    to_xy = airport.frame.entry()
    out: list[WallComponent] = []
    for u in part.units:
        for m in u.members:
            if _not_a_wall(m.resource):
                continue                    # 29h (Q-72b): a fence is no wall
            for p in m.parts:
                if not p.rings or getattr(p, "line", False) or \
                        p.height_m < float(cfg.retaining_wall_min_height_m):
                    continue
                polys = []
                for rg in p.rings:
                    if len(rg) < 3:
                        continue
                    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
                    if not g.is_valid:
                        g = g.buffer(0.0)
                    if not g.is_empty and g.geom_type == "Polygon":
                        polys.append(g)
                if not polys:
                    continue
                whole = unary_union(polys)
                if whole.length <= 0.0:
                    continue
                # the COMPONENT is judged thin and long; its PIECES are
                # judged against the road (or the shore) one by one
                wide = 2.0 * whole.area / whole.length
                if sum(g.length for g in polys) / 2.0 < \
                        float(cfg.retaining_wall_min_length_m):
                    continue
                if wide > float(cfg.retaining_wall_max_width_m) and not \
                        _retains_its_height(airport, whole, wide, float(p.height_m), cfg):
                    continue
                out.append(WallComponent(tuple(polys), float(p.height_m),
                                         m.resource, int(p.comp)))
    return out


def _retains_its_height(airport: Airport, whole, wide: float, height: float, cfg) -> bool:
    """A THICK WALL THAT RETAINS ITS OWN HEIGHT (issue #715): a component
    wider than ``retaining_wall_max_width_m`` is still WALL-CLASS when it is
    slender for its height (``wide <= height x
    retaining_wall_thick_width_per_height``: a 10.65 m concrete retaining
    wall is 3.46 m thick) AND the ground steps across it by its own height
    — the 10th / 90th percentile DEM on a ring ``retaining_wall_step_ring_m``
    outside its footprint differ by ``retaining_wall_step_min_fraction`` .. ``_max_fraction`` of the
    height (the step equals the wall: #507, RULINGS 2026-10-03c).  A thick
    facade or a building on level ground has no step; a building on a slope
    is not slender.  MEASURED (dry census over the registered captures):
    KATL ``muro_concreto5`` 10.65 m / step 12.14, ``muro_concreto`` 12.01 /
    11.10; nothing at HECA, OTHH, SPJC, CYXY, NLWF, KPDX, KCLT; at KASE two
    components of one hillside city building (8.74 m, steps 8.21 / 7.83)."""
    per = getattr(cfg, "retaining_wall_thick_width_per_height", None)
    lo = getattr(cfg, "retaining_wall_step_min_fraction", None)
    hi = getattr(cfg, "retaining_wall_step_max_fraction", None)
    ring_m = getattr(cfg, "retaining_wall_step_ring_m", None)
    dem = getattr(airport, "dem", None)
    if per is None or lo is None or hi is None or ring_m is None or dem is None:
        return False
    if wide > height * float(per):
        return False
    import numpy as np
    from .dem import dem_z_many
    grown = whole.buffer(float(ring_m))
    pts = [g.exterior.interpolate(float(t)) for g in getattr(grown, "geoms", [grown])
           for t in np.arange(0.0, g.exterior.length, 2.0)]
    z = dem_z_many(dem, np.array([q.x for q in pts]), np.array([q.y for q in pts]))
    z = z[np.isfinite(z)]
    if z.size < 4:
        return False
    step = float(np.percentile(z, 90) - np.percentile(z, 10))
    return float(lo) * height <= step <= float(hi) * height
