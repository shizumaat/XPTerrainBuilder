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

THE FOOT (issue #1662): :func:`foot_profile` is the mirror reading along
the LOWER face — the lowest sample within :data:`FOOT_FACE_M` of that face
per station, plus the seat: the bottom edge the low-side ground meets
(owner RULINGS 2026-10-03c "terrain should be flattened out to the bottom
of the wall"; 2026-10-27h Q188 "the bottom of the retaining wall").  Only
samples on the face count, so a footing buried under the hill is not read;
and a wall that retains less than its solid height has its foot where the
face it retains stops (:func:`_retained_floor`, #1952), never its footing.
Geometry only; no airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import math

import numpy as np
import shapely

__all__ = ["top_profile", "foot_profile", "EDGE_STEP_M", "BIN_M", "FOOT_FACE_M"]

#: triangle edges are sampled this fine
EDGE_STEP_M = 0.5
#: the profile's station spacing along the face
BIN_M = 1.0
#: how near the lower face a sample stands ON it (:func:`foot_profile`)
FOOT_FACE_M = 1.0


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
    got = _stations(comp, piece, face, to_xy, cache, piece.buffer(1.0), True)
    if got is None:
        return None
    st, z, seat = got
    z = np.minimum(z, _retaining_cap(comp))
    return tuple((float(a), seat + float(b)) for a, b in zip(st, z, strict=True))


def foot_profile(comp, piece, face, to_xy, cache=None) -> tuple | None:
    """``((s, z), ...)``: the absolute bottom edge of ``comp``'s member
    along ``face`` (the LOWER face line, #1662) — the lowest sample within
    :data:`FOOT_FACE_M` of it per :data:`BIN_M` station; ``None`` where
    unread."""
    if face is None:
        return None
    got = _stations(comp, piece, face, to_xy, cache,
                    face.buffer(FOOT_FACE_M).intersection(piece.buffer(1.0)), False)
    if got is None:
        return None
    st, z, seat = got
    z = np.maximum(z, _retained_floor(comp))
    return tuple((float(a), seat + float(b)) for a, b in zip(st, z, strict=True))


def _stations(comp, piece, face, to_xy, cache, where, high: bool):
    """``(stations, authored y, seat)``: the highest (``high``) or lowest
    triangle-edge sample of ``comp``'s member inside ``where`` per
    :data:`BIN_M` station along ``face``, empty bins interpolated; ``None``
    where the member, its seat or its triangles are unread."""
    seat = getattr(comp, "seat_z", None)
    member = getattr(comp, "member", None)
    if seat is None or member is None or face is None or face.length <= 0.0 \
            or where is None or where.is_empty:
        return None
    from .sunken_ramp import _member_tris
    tris = _member_tris(member, comp.origin, to_xy, cache)
    if tris is None or not len(tris):
        return None
    pts = _edge_samples(np.asarray(tris, float))
    pts = pts[shapely.contains_xy(where, pts[:, 0], pts[:, 1])]
    if not len(pts):
        return None
    s = shapely.line_locate_point(face, shapely.points(pts[:, :2]))
    n = int(math.ceil(face.length / BIN_M)) + 1
    k = np.clip(np.round(s / BIN_M).astype(int), 0, n - 1)
    if high:
        z = np.full(n, -np.inf)
        np.maximum.at(z, k, pts[:, 2])
    else:
        z = np.full(n, np.inf)
        np.minimum.at(z, k, pts[:, 2])
    ok = np.isfinite(z)
    st = np.arange(n) * BIN_M
    return st, np.interp(st, st[ok], z[ok]), float(seat)


def _retaining_cap(comp) -> float:
    """The highest authored ``y`` the wall retains to
    (``WallComponent.retained_top_y``: its zero, for a wall that retains
    only its depth under it); unbounded where the face it retains runs to
    its top — its solid height, or its height over the ground on its low
    side (RULINGS 2026-11-09a (14): the part under that ground is its
    footing, and the top is still the top)."""
    cap = getattr(comp, "retained_top_y", None)
    top_y = getattr(comp, "top_y", None)
    if cap is None or top_y is None or float(cap) >= float(top_y) - 1e-6:
        return math.inf
    return float(cap)


def _retained_floor(comp) -> float:
    """The lowest authored ``y`` of the face a wall RETAINS (#1952, owner
    RULINGS 2026-11-09a (14), the mirror of :func:`_retaining_cap`): the
    top of that face (its zero for a depth wall, else its top) less the
    height it retains, where that is under its solid height — the part
    below is its footing, authored under the low side's ground (KMCI's
    border wall: top y -0.93, retains 3.81 m, footing to -13.98); unbounded
    below where it retains its whole height."""
    held = float(getattr(comp, "retained_m", 0.0) or 0.0)
    solid = getattr(comp, "height_m", None)
    top_y = getattr(comp, "top_y", None)
    if held <= 0.0 or solid is None or top_y is None or held >= float(solid) - 1e-6:
        return -math.inf
    return min(float(top_y), _retaining_cap(comp)) - held
