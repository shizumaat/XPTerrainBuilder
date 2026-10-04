"""THE WALL-CLASS CLASSIFIER — which pack components are WALL-CLASS.

A pack component is WALL-CLASS when it is thin, tall and long enough
(``[service] retaining_wall_max_width_m`` / ``_min_height_m`` /
``_min_length_m``, read from the ``cfg`` the CALLER supplies), and its
resource does not name a fence (RULINGS 2026-09-29h, Q-72b).

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
                if wide > float(cfg.retaining_wall_max_width_m) or \
                        sum(g.length for g in polys) / 2.0 < \
                        float(cfg.retaining_wall_min_length_m):
                    continue
                out.append(WallComponent(tuple(polys), float(p.height_m),
                                         m.resource, int(p.comp)))
    return out
