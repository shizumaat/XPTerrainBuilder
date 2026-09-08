"""THE OBJECT CORRIDOR as a structure to build (RULINGS 2026-09-05n; spec
``docs/specs/auto-patch-v2/tunnel-wall-objects-round2-spec.md`` §3):
the wall object's corridor (``airport/tunnel_objects.Corridor``) turned
into the build group ``planar/structures.py`` runs through its ONE ramp
/ wall / footprint machinery, plus the two readings that are the
corridor's own — the per-mouth precedence over OSM bores (05n-3) and the
05n-2 assertion that no trench vertex stands outside the inner faces.

THE PROFILE (05n-1): s = 0 at the MOUTH, floor = ground(mouth) − plate
height; the ramp climbs INSIDE the walls at ``min(ramp_max_grade,
needed)`` — ``needed`` the depth over the wall length — and reaches the
ground at the wall's far end; only when ``needed`` exceeds the law (or
the ring pairs' direct distance cannot carry the depth at the cap: the
census prices chords) does the climb continue beyond the wall end along
the OSM approach at ``ramp_max_grade`` (the existing ``_ramp_top`` /
``max_ramp_length_m`` refusal).  A corridor with a bore at both ends is
FLAT at the mouth depth.

THE TRENCH (RULINGS 2026-09-06b (1), 2026-09-08a; ``[cutout]``): the
ramp's edges are the walls' inner faces PLUS ``floor_overlap_m`` (the
floor overlaps the wall's own footprint), the at-grade rim stands INSIDE
the walls' OUTER faces by ``rim_inset_fraction`` of their measured
thickness — by station, ``structure_geometry.rim_standoff`` of each
wall's own thickness off the ramp edge (never under the identity
spacing) — and the end cap the end wall's; no wall band is emitted
between them (the 09-01c/e ``wall_gap_m`` is superseded here).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon

from ..law import Law
from ..model.airport import OsmWay
from ..model.frame import XY
from .structure_approach import PARALLEL_COS, approach, is_tunnel, unit
from .structure_geometry import rim_standoff

__all__ = ["Group", "object_groups", "mouth_covered_by", "trench_outside_m", "climb_path"]


@_dc.dataclass
class Group:
    """One structure to build: ``members`` the OSM mouths (empty for an
    object corridor), ``mouth`` the s = 0 point, ``inward`` the cap's
    direction, ``width`` the ramp width, ``axis`` the path outward; for
    an object corridor ``corridor`` its record, ``tid`` its tunnel id,
    ``hull_s`` where the walls end (the ramp's top when the depth fits
    inside them), ``climbs`` whether the far end climbs to the ground,
    ``capped`` / ``far_capped`` the rim's shape, ``half_fn`` /
    ``rim_fn`` the ramp half-widths and rim stand-offs by station,
    ``cap_off`` / ``far_off`` the end caps' stand-off (``rim_standoff``
    of the end wall's thickness), ``design_grade`` the ramp's design
    grade."""

    members: list
    mouth: XY
    inward: XY
    width: float
    axis: list[XY]
    corridor: object = None
    tid: str = ""
    hull_s: float = 0.0
    climbs: bool = True
    capped: bool = True
    far_capped: bool = False
    half_fn: _t.Callable[[float], tuple[float, float]] | None = None
    rim_fn: _t.Callable[[float], tuple[float, float]] | None = None
    cap_off: float | None = None
    far_off: float | None = None
    design_grade: float = 0.0


def climb_path(end: XY, out_dir: XY, width: float, osm: list[OsmWay], reach: float) -> list[XY]:
    """The centreline BEYOND a ground end: the mapped (non-tunnel) way
    whose node stands nearest the end within the corridor's width and
    leaves it the way the corridor points (31h's parallel angle — a
    kinked path folds the rings), else the straight extension."""
    best = None
    for w in osm:
        if is_tunnel(w) or ("highway" not in w.tags and "railway" not in w.tags) \
                or len(w.points) < 2:
            continue
        for e, nxt in ((w.points[0], w.points[1]), (w.points[-1], w.points[-2])):
            d = math.hypot(e[0] - end[0], e[1] - end[1])
            if d <= width and (best is None or d < best[0]):
                best = (d, e, unit(e, nxt))
    if best is not None:
        path = approach(best[1], (-out_dir[0], -out_dir[1]), osm, reach)
        dx, dy = end[0] - path[0][0], end[1] - path[0][1]
        path = [end] + [(p[0] + dx, p[1] + dy) for p in path[1:]]
        d0 = unit(path[0], path[1])
        if d0[0] * out_dir[0] + d0[1] * out_dir[1] >= PARALLEL_COS:
            return path
    return [end, (end[0] + out_dir[0] * (reach + 1.0), end[1] + out_dir[1] * (reach + 1.0))]


def _interp(stations, attr_l: str, attr_r: str, s: float, band_beyond: float | None
            ) -> tuple[float, float]:
    """Linear interpolation of a station pair over ``s``; beyond the last
    station the last values (``band_beyond`` for the rim: the OSM ramp
    law's rim stand-off beyond the walls)."""
    if s >= stations[-1].s - 1e-9:
        st = stations[-1]
        if band_beyond is not None and s > stations[-1].s + 1e-6:
            return band_beyond, band_beyond
        return getattr(st, attr_l), getattr(st, attr_r)
    if s <= stations[0].s + 1e-9:
        return getattr(stations[0], attr_l), getattr(stations[0], attr_r)
    lo = max((st for st in stations if st.s <= s), key=lambda st: st.s)
    hi = min((st for st in stations if st.s >= s), key=lambda st: st.s)
    if hi.s - lo.s < 1e-9:
        return getattr(lo, attr_l), getattr(lo, attr_r)
    f = (s - lo.s) / (hi.s - lo.s)
    return (getattr(lo, attr_l) + (getattr(hi, attr_l) - getattr(lo, attr_l)) * f,
            getattr(lo, attr_r) + (getattr(hi, attr_r) - getattr(lo, attr_r)) * f)


def object_groups(corridors: _t.Sequence, osm: list[OsmWay], law: Law, reach: float
                  ) -> list[Group]:
    """The object corridors as build groups (spec §3.3): the axis starts
    at the MOUTH and runs the walls to the far end, then — unless the
    corridor is flat — continues along the ground end's mapped way (or
    straight on) so a climb the walls cannot hold has a centreline."""
    tn = law.tables.structures.tunnel
    co = law.tables.structures.cutout
    overlap = co.floor_overlap_m
    spacing = law.tables.emit.identity.min_distinct_spacing_m
    osm_rim = tn.wall_gap_m + tn.wall_band_width_m

    def standoff(thickness_m: float) -> float:
        return rim_standoff(thickness_m, co, spacing)[1]
    out: list[Group] = []
    for c in corridors:
        axis = list(c.axis)
        L = c.length_m
        sts = c.stations
        u_end = unit(axis[-2], axis[-1])
        u0 = unit(axis[0], axis[1])
        inward = (-u0[0], -u0[1])

        def half_fn(s: float, _sts=sts, _ov=overlap) -> tuple[float, float]:
            # the floor overlaps the inner faces by floor_overlap_m
            hl, hr = _interp(_sts, "half_l", "half_r", s, None)
            return hl + _ov, hr + _ov

        def rim_fn(s: float, _sts=sts, _beyond=osm_rim) -> tuple[float, float]:
            # the rim INSIDE the outer face (09-08a): rim_standoff of the
            # wall's measured thickness off the ramp edge; beyond the
            # walls the OSM law's stand-off
            if s > _sts[-1].s + 1e-6:
                return _beyond, _beyond
            tl, tr = _interp(_sts, "thick_l", "thick_r", s, None)
            return standoff(tl), standoff(tr)

        path = axis if c.flat else axis + climb_path(axis[-1], u_end, c.width_m, osm, reach)[1:]
        needed = c.depth_m / max(L, 1e-9)
        out.append(Group([], axis[0], inward, c.width_m, path, c, c.id, L, not c.flat,
                         c.mouth_closed, c.far_closed, half_fn, rim_fn,
                         standoff(c.mouth_thickness_m) if c.mouth_closed else None,
                         standoff(c.far_thickness_m) if c.far_closed else None,
                         min(tn.ramp_max_grade, needed) if not c.flat else 0.0))
    return out


def mouth_covered_by(pt: XY, corridors: _t.Sequence, tol: float) -> str | None:
    """The id of the object corridor whose footprint (walls ∪ trench,
    ``tol`` around) an OSM bore mouth stands inside (05n-3: that mouth
    is the object's), or ``None`` — the mouth keeps its OSM ramp."""
    p = Point(pt)
    for c in corridors:
        if c.footprint.buffer(tol).contains(p):
            return c.id
    return None


def trench_outside_m(ramp_rings: _t.Sequence[Polygon], corridor, overlap_m: float = 0.0,
                     grid_m: float = 0.0) -> float:
    """The largest distance any emitted trench (ramp) vertex INSIDE the
    walls stands outside the region between the inner faces ⊕
    ``overlap_m`` (``cutout.floor_overlap_m``) ⊕ the outward snap's
    diagonal (``grid_m·√2``: the edge snaps away from the axis onto the
    grid in both coordinates) — the 05n-2 assertion as 2026-09-06b (1)
    amends it (expect 0.0).  Vertices beyond the walls (a climb the walls
    could not hold) are the OSM ramp law's and are not measured."""
    region = corridor.trench.buffer(overlap_m + grid_m * math.sqrt(2.0) + 1e-6,
                                    join_style="mitre", mitre_limit=2.0)
    ext = region.exterior
    end = LineString(corridor.axis).interpolate(corridor.length_m)
    a, b = corridor.axis[-2], corridor.axis[-1]
    u = unit(a, b)
    worst = 0.0
    for ring in ramp_rings:
        for x, y in ring.exterior.coords:
            # beyond the wall end (along the axis) is the extension
            if (x - end.x) * u[0] + (y - end.y) * u[1] > 1e-6:
                continue
            p = Point(x, y)
            if not region.contains(p):
                worst = max(worst, float(ext.distance(p)))
    return worst
