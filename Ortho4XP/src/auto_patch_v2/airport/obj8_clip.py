"""OBJ8 plane clipping — the Sutherland–Hodgman triangle clip and the
plan-union helpers ``obj8.py`` uses to cut a solid component at a
horizontal plane (split from ``obj8.py`` by the 1,000-line file law,
2026-09-09; the laws and the readers stay there).  Private to the
``airport`` package; nothing numeric lives here.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.errors import GEOSException
from shapely.geometry import Polygon
from shapely.ops import unary_union

import typing as _t

if _t.TYPE_CHECKING:  # annotations only — obj8 imports this module
    from .obj8 import Component

__all__ = ["_clip", "_union_rings", "_split_at_plane", "_bulk_polys",
           "_clip_component", "_clip_both"]

def _clip(corners, plane_y: float, below: bool) -> list[tuple[float, float]] | None:
    """Sutherland–Hodgman clip of one triangle to ``y <= plane_y``
    (``below``) or ``y >= plane_y``, as the sub-polygon's authored
    ``(x, z)`` ring (3–4 points) or ``None``.  THE CLIP, NOT A TEST: a
    ramp panel running +1 → −6 contributes only its below part."""
    ring: list[tuple[float, float]] = []
    for i in range(3):
        cur, nxt = corners[i], corners[(i + 1) % 3]
        ci = cur[1] <= plane_y if below else cur[1] >= plane_y
        ni = nxt[1] <= plane_y if below else nxt[1] >= plane_y
        if ci:
            ring.append((cur[0], cur[2]))
        if ci != ni:
            span = nxt[1] - cur[1]
            if span == 0.0:
                continue
            f = (plane_y - cur[1]) / span
            ring.append((cur[0] + f * (nxt[0] - cur[0]), cur[2] + f * (nxt[2] - cur[2])))
    return ring if len(ring) >= 3 else None


def _union_rings(rings: list[list[tuple[float, float]]]):
    """The union of clipped-triangle rings, REPAIRED at the contribution
    (a clip of a folded or sliver triangle is invalid; one invalid member
    refuses the whole union — measured OTHH, a side-location conflict at
    the millimetre) and unioned under a snapping precision when the exact
    union still refuses."""
    if not rings:
        return None
    polys = []
    for r in rings:
        try:
            p = Polygon(r)
        except (ValueError, TypeError):
            continue
        if p.is_empty:
            continue
        if not p.is_valid:
            p = shapely.make_valid(p)
        if p.is_empty or p.area <= 1e-9:
            continue
        polys.append(p)
    if not polys:
        return None
    try:
        u = unary_union(polys)
    except GEOSException:
        try:
            u = shapely.union_all(polys, grid_size=1e-6)
        except GEOSException:
            u = unary_union([p.buffer(1e-6) for p in polys])
    if not u.is_valid:
        u = shapely.make_valid(u)
    parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon" and g.area > 1e-9]
    if not parts:
        return None
    return unary_union(parts) if len(parts) > 1 else parts[0]


def _split_at_plane(v: np.ndarray, comp: Component, plane_y: float, below: bool
                    ) -> tuple[np.ndarray, np.ndarray]:
    """``(wholly-inside triangles, straddling triangles)`` of the
    component against the plane — the bulk fast path: a mega-shell's
    triangles are mostly wholly on one side (OTHH's terminal: 254 s of
    per-triangle Python clips read the car-park wells' cover)."""
    t = comp.tris
    ys = v[t][:, :, 1]
    inside = (ys <= plane_y) if below else (ys >= plane_y)
    n_in = inside.sum(axis=1)
    return t[n_in == 3], t[(n_in > 0) & (n_in < 3)]


def _bulk_polys(v: np.ndarray, tris: np.ndarray) -> list:
    """The plan polygons of ``tris`` (authored ``(x, z)``) in bulk."""
    if tris.shape[0] == 0:
        return []
    pts = v[tris][:, :, [0, 2]]
    polys = shapely.polygons(pts)
    keep = shapely.is_valid(polys) & (shapely.area(polys) > 1e-9)
    return [p for p, k in zip(polys, keep.tolist()) if k]


def _clip_component(v: np.ndarray, comp: Component, plane_y: float, below: bool):
    whole, part = _split_at_plane(v, comp, plane_y, below)
    rings = []
    for t in part.tolist():
        r = _clip((v[t[0]], v[t[1]], v[t[2]]), plane_y, below)
        if r is not None:
            rings.append(r)
    polys = _bulk_polys(v, whole)
    if not rings:
        if not polys:
            return None
        u = unary_union(polys)
        if not u.is_valid:
            u = shapely.make_valid(u)
        parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon" and g.area > 1e-9]
        return (unary_union(parts) if len(parts) > 1 else parts[0]) if parts else None
    u = _union_rings(rings)
    if polys:
        u2 = unary_union(polys + ([u] if u is not None else []))
        if not u2.is_valid:
            u2 = shapely.make_valid(u2)
        parts = [g for g in shapely.get_parts(u2) if g.geom_type == "Polygon" and g.area > 1e-9]
        return (unary_union(parts) if len(parts) > 1 else parts[0]) if parts else None
    return u


def _clip_both(v: np.ndarray, comp: Component, plane_y: float):
    """The component's geometry AT OR ABOVE ``plane_y`` as plan LINEWORK
    (every clipped triangle's ring as a ``LineString``) and as the union
    of the clipped polygons: ``(lines, polygons)``, either ``None``.  A
    vertical wall projects to a line of zero area, which a polygon union
    drops — and a pit's rim IS its vertical walls."""
    from shapely.geometry import LineString
    whole, part = _split_at_plane(v, comp, plane_y, False)
    lines = []
    rings = []
    for t in part.tolist():
        r = _clip((v[t[0]], v[t[1]], v[t[2]]), plane_y, False)
        if r is None:
            continue
        rings.append(r)
        try:
            lines.append(LineString(r + [r[0]]))
        except (ValueError, TypeError):
            continue
    # the wholly-above triangles in bulk: their rings as linework and polygons
    if whole.shape[0]:
        pts = v[whole][:, :, [0, 2]]
        closed = np.concatenate([pts, pts[:, :1, :]], axis=1)
        lines.extend(shapely.linestrings(closed).tolist())
    polys = _bulk_polys(v, whole)
    if not lines:
        return None, None
    u = unary_union(lines)
    pg = _union_rings(rings)
    if polys:
        pg = unary_union(polys + ([pg] if pg is not None else []))
        if not pg.is_valid:
            pg = shapely.make_valid(pg)
        parts = [g for g in shapely.get_parts(pg) if g.geom_type == "Polygon" and g.area > 1e-9]
        pg = (unary_union(parts) if len(parts) > 1 else parts[0]) if parts else None
    return (None if u.is_empty else u), pg
