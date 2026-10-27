"""OBJ8 plane clipping — the Sutherland–Hodgman triangle clip and the
plan-union helpers ``obj8.py`` uses to cut a solid component at a
horizontal plane (split from ``obj8.py`` by the 1,000-line file law,
2026-09-09; the laws and the readers stay there).  Private to the
``airport`` package; nothing numeric lives here.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from shapely.errors import GEOSException
from shapely.geometry import Polygon

from ..geom.parts import areal_part
from . import frame_entry as _fe

if _t.TYPE_CHECKING:  # annotations only — obj8 imports this module
    from .obj8 import Component

__all__ = ["_clip", "_union_rings", "_split_at_plane", "_edge_on", "_plan_admitted",
           "_bulk_polys", "_clip_component", "_clip_both"]

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


def _polygon_parts(u) -> list:
    """The POLYGON parts of ``u`` above the sliver area, vectorised (owner
    RULINGS 2026-09-14q): ``geom_type`` and ``area`` are property reads per
    part, and this filter runs on every clip of every component."""
    parts = shapely.get_parts(u)
    if not parts.size:
        return []
    keep = (shapely.get_type_id(parts) == 3) & (shapely.area(parts) > 1e-9)
    return parts[keep].tolist()


def _union_rings(rings: list[list[tuple[float, float]]]):
    """The union of clipped-triangle rings, REPAIRED at the contribution
    (a clip of a folded or sliver triangle is invalid; one invalid member
    refuses the whole union — measured OTHH, a side-location conflict at
    the millimetre) and unioned under a snapping precision when the exact
    union still refuses.

    EVERY PREDICATE HERE IS VECTORISED (owner RULINGS 2026-09-14q, scout
    ``v2partcost2``): ``is_empty`` / ``is_valid`` / ``area`` are PROPERTY
    reads on one geometry each, and this runs over every clipped triangle
    of every component — the same per-object property cost that made
    ``_rim_index`` 137 s at VHHH.  Same predicates, same order, same
    survivors; one C call per predicate instead of one per ring."""
    if not rings:
        return None
    built = []
    for r in rings:
        try:
            built.append(Polygon(r))
        except (ValueError, TypeError):
            continue
    if not built:
        return None
    arr = np.empty(len(built), dtype=object)
    arr[:] = built
    arr = arr[~shapely.is_empty(arr)]
    if arr.size:
        bad = ~shapely.is_valid(arr)
        if bad.any():
            # the AREA of each repair (``geom/parts.areal_part``): the lines
            # a collapsed sliver leaves would ride into the union (#1472)
            arr[bad] = [areal_part(r) for r in shapely.make_valid(arr[bad])]
        arr = arr[~shapely.is_empty(arr) & (shapely.area(arr) > 1e-9)]
    if not arr.size:
        return None
    polys = arr.tolist()
    # §51 (4) row 16: the LOCAL repair above is KEPT (a clip of a folded
    # or sliver triangle is born invalid, before any placement), and the
    # ladder that used to be spelled here IS ``frame_entry.union``.
    return _repaired_union(polys, "obj8_clip._union_rings")


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


def _edge_on(pts: np.ndarray) -> np.ndarray:
    """Which plan triangles (``(n, 3, 2)`` authored ``(x, z)``) are a face
    seen EDGE-ON: their plan WIDTH — the altitude on the longest edge —
    is at or below the resolution of their own coordinates.

    OBJ8 vertices are SINGLE PRECISION (the files print float32 values),
    so a wall authored vertical can stand off its own plan line by one
    float32 step: at 200 m from the object's origin that is 15 um, and a
    10 m wall is then a 10 m x 15 um needle of 1e-4 m2.  AREA cannot tell
    that needle from a small real plate — it passes any area floor a real
    face passes — and it is no area: it is the rounding of a line.  The
    width can, and the bound is no tuned number: it is ``np.spacing`` of
    the triangle's largest coordinate AS A float32, the step below which
    the file cannot say which side of the line a vertex lies on.

    #559: thousands of such needles through one exact overlay are what
    GEOS refuses (``Ring edge missing``) — every operand valid, every
    area above the floor.  They are dropped HERE, where a triangle
    becomes a plan polygon, so no consumer meets them."""
    e = pts - np.roll(pts, 1, axis=1)
    longest = np.hypot(e[:, :, 0], e[:, :, 1]).max(axis=1)
    a, b = pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0]
    twice_area = np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])
    reach = np.abs(pts).reshape(-1, 6).max(axis=1)
    step = np.spacing(reach.astype(np.float32)).astype(float)
    return twice_area <= step * longest


def _plan_admitted(authored: np.ndarray, polys: np.ndarray,
                   floor: float = 1e-9) -> np.ndarray:
    """THE PLAN-TRIANGLE ADMISSION (#559, #581): which of ``polys`` — the
    plan polygons of triangles whose AUTHORED ``(x, z)`` are ``authored``
    (``(n, 3, 2)``), in the authored frame or placed — are plan area: valid,
    area above ``floor``, and not a face seen edge-on (:func:`_edge_on`).

    Every site that turns pack triangles into plan polygons admits them
    HERE, so no consumer's union meets a needle.  The edge-on test reads
    the AUTHORED coordinates — the file's own resolution; a placement is a
    rotation and a translation, which keep a triangle's width — while
    validity and area are the polygons' own (a site that snaps its frame
    coordinates passes its own ``floor``)."""
    return (shapely.is_valid(polys) & (shapely.area(polys) > floor)
            & ~_edge_on(authored))


def _bulk_polys(v: np.ndarray, tris: np.ndarray) -> list:
    """The plan polygons of ``tris`` (authored ``(x, z)``) in bulk, as
    :func:`_plan_admitted` admits them."""
    if tris.shape[0] == 0:
        return []
    pts = v[tris][:, :, [0, 2]]
    polys = shapely.polygons(pts)
    keep = _plan_admitted(pts, polys)
    return [p for p, k in zip(polys, keep.tolist()) if k]


def _repaired_union(polys: list, site: str):
    """The plan union of admitted triangle polygons (and a clipped part):
    §51 Law B's union (``frame_entry.union`` — pack geometry, so it cannot
    abort a tile), repaired, as its polygon parts unioned again; ``None``
    when nothing is left."""
    u = _fe.union(polys, site)
    if not u.is_valid:
        u = shapely.make_valid(u)
    parts = _polygon_parts(u)
    if not parts:
        return None
    return _fe.union(parts, site) if len(parts) > 1 else parts[0]


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
        return _repaired_union(polys, "obj8_clip._clip_component")
    u = _union_rings(rings)
    if polys:
        return _repaired_union(polys + ([u] if u is not None else []),
                               "obj8_clip._clip_component")
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
    u = _fe.union(lines, "obj8_clip._clip_both.lines")
    pg = _union_rings(rings)
    if polys:
        pg = _repaired_union(polys + ([pg] if pg is not None else []),
                             "obj8_clip._clip_both")
    return (None if u.is_empty else u), pg
