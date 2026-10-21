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
    its footprint pieces (frame xy), its solid height and its source.
    ``retains`` — the component RETAINS ITS OWN HEIGHT
    (:func:`_retains_its_height`): owner RULINGS 2026-10-15a (2) — "the
    wall is the step", a declared terrace for the roads and lots below it
    (``airport/road_ramp``)."""

    pieces: tuple
    height_m: float
    resource: str
    comp: int
    retains: bool = False


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
                # #1139: an object that IS one wall (its only part) may
                # retain only what stands under its zero
                depth = _depth_under_zero(p) if len(m.parts) == 1 else None
                retains = _retains_its_height(airport, whole, wide,
                                              float(p.height_m), cfg, depth)
                if wide > float(cfg.retaining_wall_max_width_m) and not retains:
                    continue
                out.append(WallComponent(tuple(polys), float(p.height_m),
                                         m.resource, int(p.comp), retains))
    return out


#: the share of a wall's outline that must step by its height: the 90th
#: percentile of the across-wall steps (a retaining wall's ends and returns
#: retain nothing; KATL ``muro_concreto5`` steps 7-9 m over its south run)
ACROSS_PERCENTILE = 90.0


def _depth_under_zero(part) -> float | None:
    """How far a part reaches UNDER its object's zero (``-base_y``), or
    ``None`` for a part standing on it.  A retaining wall's zero is the
    upper ground it holds (KATL ``muro_concreto5``: y −9.70 .. +0.95), so
    this is the face it retains; the rest of its height stands proud — a
    parapet (#1139, KATL ``muro_ladrillo``: 16.64 m solid, 10.52 m under
    its zero, the ground stepping 11.08 m across it)."""
    by = getattr(part, "base_y", None)
    return -float(by) if by is not None and float(by) < 0.0 else None


def _retains_its_height(airport: Airport, whole, wide: float, height: float, cfg,
                        depth: float | None = None) -> bool:
    """A WALL THAT RETAINS ITS OWN HEIGHT (owner RULINGS 2026-10-15a (2),
    issue #715): slender for its height (``wide <= height x
    retaining_wall_thick_width_per_height``: KATL's 10.65 m concrete
    retaining wall is 3.46 m thick) AND the ground stepping ACROSS it by
    ``retaining_wall_step_min_fraction`` .. ``_max_fraction`` of its height
    (the step equals the wall: #507, RULINGS 2026-10-03c) — read every 2 m
    round a ring outside its footprint, half its height out (at least
    ``retaining_wall_step_ring_m``: a lidar DEM smears a 10 m step over
    3-5 m either side): each ring point against the point as far out on the
    FAR side of the wall (through its nearest wall point, ``wide`` across),
    the :data:`ACROSS_PERCENTILE` of the absolute differences — the wall's
    retaining run, not its ends.  ACROSS, never round the ring: a long wall
    on a slope rises along itself without retaining anything (the ring's
    10th-90th percentile spread admitted 56 thin HECA strips that way).  A
    facade or a building on level ground has no step; a building on a
    slope is not slender.  MEASURED (dry census, registered captures):
    KATL ``muro_concreto5`` 10.65 m and ``muro_concreto`` 12.01 m admitted
    (#715); see ``docs/briefs/katl714-notes.md`` (#715) for the sweep airports.

    THE HEIGHT IT RETAINS (#1139): its solid height, or its ``depth`` under
    its own zero (:func:`_depth_under_zero`) where it stands proud of the
    upper ground — the step matches either.  The depth is read only for a
    placed object that IS one wall (its only part): read for every part it
    admitted 73 HECA, 32 EDDF and 22 KLAX building parts (facades on a
    slope stand under their zero too); read for single-part objects it
    admits KATL ``muro_ladrillo`` alone over the 33 registered captures.
    Slenderness is judged on the solid height, as before."""
    per = getattr(cfg, "retaining_wall_thick_width_per_height", None)
    lo = getattr(cfg, "retaining_wall_step_min_fraction", None)
    hi = getattr(cfg, "retaining_wall_step_max_fraction", None)
    ring_m = getattr(cfg, "retaining_wall_step_ring_m", None)
    dem = getattr(airport, "dem", None)
    if per is None or lo is None or hi is None or ring_m is None or dem is None:
        return False
    if wide > height * float(per):
        return False
    step = _step_across(dem, whole, wide, max(float(ring_m), height))
    if step is None:
        return False
    return any(float(lo) * h <= step <= float(hi) * h
               for h in (height, depth) if h is not None and h > 0.0)


def _step_across(dem, whole, wide: float, ring_m: float) -> float | None:
    """The median DEM step across ``whole`` (see :func:`_retains_its_height`)."""
    import numpy as np
    from shapely.ops import nearest_points
    from .dem import dem_z_many
    grown = whole.buffer(ring_m)
    near, far = [], []
    for g in getattr(grown, "geoms", [grown]):
        for t in np.arange(0.0, g.exterior.length, 2.0):
            p = g.exterior.interpolate(float(t))
            q = nearest_points(whole, p)[0]
            dx, dy = q.x - p.x, q.y - p.y
            n = (dx * dx + dy * dy) ** 0.5
            if n <= 1e-9:
                continue
            k = (wide + ring_m) / n
            near.append((p.x, p.y))
            far.append((q.x + dx * k, q.y + dy * k))
    if len(near) < 4:
        return None
    a = dem_z_many(dem, np.array([x for x, _ in near]), np.array([y for _, y in near]))
    b = dem_z_many(dem, np.array([x for x, _ in far]), np.array([y for _, y in far]))
    d = np.abs(a - b)
    d = d[np.isfinite(d)]
    return float(np.percentile(d, ACROSS_PERCENTILE)) if d.size >= 4 else None
