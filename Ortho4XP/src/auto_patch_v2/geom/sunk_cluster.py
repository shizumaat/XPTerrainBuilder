"""K1's BELOW-GRADE CLUSTERS AND THE GROUND THEY KEEP (owner RULINGS
2026-11-19k (1), amended by lane ``lk1fix``).

K1 refuses a pad to a cluster that rises nowhere ``chain_min_height_m``
above its own grade.  Lane ``lk1fix`` narrowed it to what the rule was
written for: a cluster that LIES UNDER its grade (a road bed, a trench
floor, a pit — ``pad_evidence.mostly_under_grade``); an at-grade slab under
the walled height (a landside apron slab, a fuel-farm base, a hub floor)
keeps its pad.

A sunk cluster mints no pad, and its ground is no other region's either:
a cluster standing mostly over it (a car-park slab over a road-bed trench)
is a slab of the sunk frame and mints none (``cluster_outlines``), and a
viaduct's ramp landing never fills it (``planar/landing``: a landing
minted over a refused fake trench lifted the tunnel ramp's end 5.08 m).
:func:`sunk_ground` is that ground, :func:`is_sunk` the one verdict both
readers take; :func:`closed_outline` is the cluster outline every pad
reader closes (``cluster_outlines`` rule 2).

No law value is read here — the caller passes ``law.tables.pad_admission``.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from .pad_evidence import mostly_under_grade

__all__ = ["closed_outline", "is_sunk", "sunk_ground"]


def closed_outline(c: _t.Any, to_xy: _t.Callable[[float, float], tuple[float, float]],
                   touch_m: float, simplify_m: float = 0.0):
    """The union of cluster ``c``'s footprint rings (``(lat, lon)``) in the
    planar frame, closed at the touch tolerance (a mitred dilate/erode) and
    simplified back; ``None`` where it has no ring."""
    ps: list[Polygon] = []
    for r in (getattr(c, "rings", ()) or ()):
        if len(r) < 3:
            continue
        g = Polygon([to_xy(lo, la) for la, lo in r])
        if not g.is_valid:
            g = g.buffer(0.0)
        if isinstance(g, MultiPolygon):
            ps.extend(q for q in g.geoms if not q.is_empty)
        elif isinstance(g, Polygon) and not g.is_empty:
            ps.append(g)
        else:
            ps.extend(q for q in getattr(g, "geoms", ()) if isinstance(q, Polygon)
                      and not q.is_empty)
    if not ps:
        return None
    u = unary_union(ps)
    if touch_m > 0.0:
        u = u.buffer(touch_m, join_style=2).buffer(-touch_m, join_style=2)
        if simplify_m > 0.0:
            u = u.simplify(simplify_m)
        if not u.is_valid:
            u = u.buffer(0.0)
    return u


def is_sunk(c: _t.Any, admission: _t.Any) -> "bool | None":
    """K1's verdict on cluster ``c``: ``True`` — under the walled height
    and lying under its grade (refused, its ground kept); ``False`` — not
    K1's (above the walled height, or an at-grade slab under it); ``None``
    — under the walled height but measured before the component tops
    (refused as before, no ground kept)."""
    ev = getattr(c, "evidence", None)
    bar = float(getattr(admission, "above_grade_min_m", 0.0) or 0.0)
    if ev is None or bar <= 0.0 or float(getattr(ev, "tallest_extent_m", 0.0)) >= bar:
        return False
    sunk_m = float(getattr(admission, "sunk_min_m", 0.0) or 0.0)
    if sunk_m <= 0.0:
        return None
    v = mostly_under_grade(ev, sunk_m)
    return v


def sunk_ground(clusters: _t.Sequence[_t.Any],
                to_xy: _t.Callable[[float, float], tuple[float, float]],
                admission: _t.Any, touch_m: float, simplify_m: float = 0.0,
                walled_only: bool = True) -> list:
    """The closed outline of every WALLED cluster :func:`is_sunk` reads
    ``True`` — the ground K1's refusals keep from every pad and landing."""
    out = []
    if admission is None:
        return out
    for c in clusters or ():
        if walled_only and not int(getattr(c, "walled", 0) or 0):
            continue
        if is_sunk(c, admission) is not True:
            continue
        u = closed_outline(c, to_xy, touch_m, simplify_m)
        if u is not None and not u.is_empty:
            out.append(u)
    return out
