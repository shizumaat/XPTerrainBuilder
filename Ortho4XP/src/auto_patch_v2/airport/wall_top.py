"""THE TOP EDGE OF A RETAINING WALL AS IT SITS (owner RULINGS 2026-10-29a
Q299 (a), issue #1661): "the top of a retaining wall, which the hill grades
down to, is the wall object's top edge as it sits".

A pack wall's top is rarely level: KATL ``muro_27R.obj`` (479 m) stands
+0.68 m over its zero at one end and +6.82 m along its middle.  This module
reads the top as a PROFILE along the wall's upper face: the member's solid
triangles (``sunken_ramp._member_tris``, the one placed-triangle reader),
their edges sampled every :data:`EDGE_STEP_M`, the samples inside the
footprint projected onto the face, the highest per :data:`BIN_M` station —
plus the member's seat (``WallComponent.seat_z``: DEM at its origin plus
its ``agl``), so each station is absolute (read back at a point by
``constraints/wall_zone.face_top``).

A wall that retains only the depth under its own zero and stands proud of
it (``wall_class._depth_under_zero``, #1139: ``retained_m`` under its solid
height — KATL ``muro_ladrillo.obj``, 10.52 m retained of 16.64 m, a 6.1 m
parapet) retains its upper ground AT that zero: the profile is capped
there (:func:`_retaining_cap`), so the hill never climbs a parapet.
Geometry only; no airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import math

import numpy as np
import shapely

__all__ = ["top_profile", "EDGE_STEP_M", "BIN_M"]

#: triangle edges are sampled this fine
EDGE_STEP_M = 0.5
#: the profile's station spacing along the face
BIN_M = 1.0


def _edge_samples(tris: np.ndarray) -> np.ndarray:
    """Every triangle edge of ``tris`` (``(n, 3, 3)``: x, y, authored y)
    sampled every :data:`EDGE_STEP_M` — ``(m, 3)``."""
    a = tris.reshape(-1, 3)
    b = np.roll(tris, -1, axis=1).reshape(-1, 3)
    ln = np.hypot(b[:, 0] - a[:, 0], b[:, 1] - a[:, 1])
    k = np.maximum(1, np.ceil(ln / EDGE_STEP_M).astype(int)) + 1
    idx = np.repeat(np.arange(len(a)), k)
    start = np.repeat(np.cumsum(k) - k, k)
    t = (np.arange(len(idx)) - start) / np.repeat(k - 1, k)
    return a[idx] + (b[idx] - a[idx]) * t[:, None]


def top_profile(comp, piece, face, to_xy, cache=None) -> tuple | None:
    """``((s, z), ...)``: the absolute top of ``comp``'s member over the
    footprint ``piece``, per :data:`BIN_M` station ``s`` along ``face``
    (the upper face line); ``None`` where the member, its seat or its
    triangles are unread."""
    seat = getattr(comp, "seat_z", None)
    member = getattr(comp, "member", None)
    if seat is None or member is None or face is None or face.length <= 0.0:
        return None
    from .sunken_ramp import _member_tris
    tris = _member_tris(member, comp.origin, to_xy, cache)
    if tris is None or not len(tris):
        return None
    pts = _edge_samples(np.asarray(tris, float))
    inside = shapely.contains_xy(piece.buffer(1.0), pts[:, 0], pts[:, 1])
    pts = pts[inside]
    if not len(pts):
        return None
    s = shapely.line_locate_point(face, shapely.points(pts[:, :2]))
    n = int(math.ceil(face.length / BIN_M)) + 1
    k = np.clip(np.round(s / BIN_M).astype(int), 0, n - 1)
    top = np.full(n, -np.inf)
    np.maximum.at(top, k, pts[:, 2])
    ok = np.isfinite(top)
    st = np.arange(n) * BIN_M
    z = np.minimum(np.interp(st, st[ok], top[ok]), _retaining_cap(comp))
    return tuple((float(a), float(seat) + float(b)) for a, b in zip(st, z, strict=True))


def _retaining_cap(comp) -> float:
    """The highest authored ``y`` the wall retains to: its zero plus the
    part of its solid height it retains (``top_y - height + retained``) for
    a wall that retains less than its height; unbounded otherwise."""
    h = float(getattr(comp, "height_m", 0.0) or 0.0)
    kept = float(getattr(comp, "retained_m", 0.0) or 0.0)
    top_y = getattr(comp, "top_y", None)
    if top_y is None or kept <= 0.0 or kept >= h - 1e-6:
        return math.inf
    return float(top_y) - h + kept
