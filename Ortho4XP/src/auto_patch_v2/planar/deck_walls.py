"""THE WALLS A HARD-DECK BRIDGE MODELS UNDER ITS DECK (owner RULINGS
2026-10-30f (3), 2026-10-30b; #1692): "where the bridge object provides
walls, the trench is cut wide enough to expose the walls' inside faces
fully.  The banks of 2026-10-30b apply only where the object has no walls."

A pack's taxiway bridge may stand its deck on ABUTMENT WALLS that line the
road under it (KBNA's taxiway-L frame: vertical faces from the road up to
the deck's underside along both sides of the carriageway, under both deck
pieces and along the open stretch between them).  This module reads them
off the frame's own geometry — never a name: every VERTICAL solid triangle
of the frame's genuine static components that rises from near the frame's
bottom (within ``reach_frac`` of the depth) through at least
``height_frac`` of the depth, laid out in the deck's (along-road ``s``,
across-road ``u``) frame (``deck_bridge._road_dir``).  The INNER FACE on
each side of the road is the face line nearest the deck's middle across the
road that covers at least half of the stretch asked about; the trench there
is the strip between the two.  A side with no such face has no wall, and the
30b bank stands there.

Geometry only; the depth is ``deck_bridge``'s (deck top less the frame's
bottom).  Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Polygon

from ..geom.wall_lines import inner_faces, project_span

__all__ = ["wall_faces", "inner_faces", "wall_strip"]

#: a triangle is VERTICAL when its normal's y component is under this
_VERTICAL_NY = 0.3
#: a face runs ALONG the road when its plan segment is within this of it
_ALONG_DEG = 20.0
#: a face rises from the bottom when it starts within this share of the
#: depth over the frame's bottom, and is a wall when it rises this share
_REACH_FRAC = 0.25
_HEIGHT_FRAC = 0.5
#: K2 (kord-trench-frame-spec): a FLOOR solid is a triangle at least this
#: near-horizontal (``|normal_y|``; the complement of :data:`_VERTICAL_NY`)
#: standing wholly within :data:`_REACH_FRAC` of the depth over the bottom,
#: of a component holding no wall triangle (a wall block's own bottom cap
#: is the wall, never the floor beside it)
_FLOOR_NY = 1.0 - _VERTICAL_NY



def _frame_tris(cache, q) -> "tuple[np.ndarray, np.ndarray, np.ndarray] | None":
    """``(vertices, triangles, component of each)`` of placement ``q``'s
    genuine static components, or ``None``."""
    if not q.resolved:
        return None
    g = cache.geometry(q.resolved)
    comps = cache.genuine(q.resolved)
    if g is None or not comps:
        return None
    return (g.vertices[:, :3], np.concatenate([c.tris for c in comps]),
            np.concatenate([np.full(len(c.tris), k) for k, c in enumerate(comps)]))


def wall_faces(cache, frame, bottom_y: float, top_y: float, r: tuple[float, float],
               n: tuple[float, float]) -> tuple:
    """``(r_w, n_w, faces, floor)``: the frame's walls (module doc) — ``r_w``
    the walls' own direction (the length-weighted mean of the faces running
    within :data:`_ALONG_DEG` of the road ``r``), ``n_w`` across it on
    ``n``'s side, every face as ``(u, s0, s1)`` in that frame and (K2) every
    FLOOR solid as ``(u_lo, u_hi, s0, s1)`` (``geom/wall_lines.Floor``) — or
    ``()`` with no wall face."""
    segs, flats = _wall_segments(cache, frame, bottom_y, top_y)
    cos_along = math.cos(math.radians(_ALONG_DEG))
    sx = sy = 0.0
    kept = []
    for p, q in segs:
        dx, dy = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(dx, dy)
        if ln <= 0.1 or abs(dx * r[0] + dy * r[1]) < cos_along * ln:
            continue
        th = 2.0 * math.atan2(dy, dx)
        sx += ln * math.cos(th)
        sy += ln * math.sin(th)
        kept.append((p, q))
    if not kept:
        return ()
    th = 0.5 * math.atan2(sy, sx)
    rw = (math.cos(th), math.sin(th))
    if rw[0] * r[0] + rw[1] * r[1] < 0.0:
        rw = (-rw[0], -rw[1])
    nw = (-rw[1], rw[0])
    if nw[0] * n[0] + nw[1] * n[1] < 0.0:
        nw = (-nw[0], -nw[1])
    faces = tuple((0.5 * (p[0] * nw[0] + p[1] * nw[1] + q[0] * nw[0] + q[1] * nw[1]),
                   min(p[0] * rw[0] + p[1] * rw[1], q[0] * rw[0] + q[1] * rw[1]),
                   max(p[0] * rw[0] + p[1] * rw[1], q[0] * rw[0] + q[1] * rw[1]))
                  for p, q in kept)
    floor = tuple(project_span(tri, nw) + project_span(tri, rw) for tri in flats)
    return rw, nw, faces, floor


def _wall_segments(cache, frame, bottom_y: float, top_y: float) -> tuple[list, list]:
    """``(segments, floor)``: the plan segment (its farthest pair of points,
    frame xy) of every wall triangle of ``frame`` (module doc), and the plan
    corners of every FLOOR triangle (:data:`_FLOOR_NY`, K2)."""
    from ..airport.obj8 import _to_frame
    depth = top_y - bottom_y
    if depth <= 0.0:
        return [], []
    out: list = []
    flats: list = []
    for q in frame:
        got = _frame_tris(cache, q)
        if got is None:
            continue
        v, tris, owner = got
        a, b, c = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
        nrm = np.cross(b - a, c - a)
        ln = np.linalg.norm(nrm, axis=1)
        ok = ln > 1e-12
        ny = np.ones(len(tris))
        ny[ok] = np.abs(nrm[ok, 1] / ln[ok])
        ys = np.stack([a[:, 1], b[:, 1], c[:, 1]], axis=1)
        lo, hi = ys.min(axis=1), ys.max(axis=1)
        keep = ok & (ny < _VERTICAL_NY) & (lo <= bottom_y + _REACH_FRAC * depth) \
            & (hi - lo >= _HEIGHT_FRAC * depth)
        for k in np.flatnonzero(keep):
            pts = [_to_frame(q.xy, q.heading_deg, float(p[0]), float(p[2]))
                   for p in (a[k], b[k], c[k])]
            out.append(max(((pts[i], pts[j]) for i, j in ((0, 1), (0, 2), (1, 2))),
                           key=lambda e: math.dist(*e)))
        flat = ok & (ny >= _FLOOR_NY) & (hi <= bottom_y + _REACH_FRAC * depth) \
            & ~np.isin(owner, owner[keep])
        for k in np.flatnonzero(flat):
            flats.append(tuple(_to_frame(q.xy, q.heading_deg, float(p[0]), float(p[2]))
                               for p in (a[k], b[k], c[k])))
    return out, flats


def wall_strip(r: tuple[float, float], n: tuple[float, float], u0: float, u1: float,
               s0: float, s1: float) -> Polygon:
    """The plan rectangle ``u0 <= u <= u1``, ``s0 <= s <= s1``."""
    def at(s: float, u: float) -> tuple[float, float]:
        return (r[0] * s + n[0] * u, r[1] * s + n[1] * u)
    return Polygon([at(s0, u0), at(s1, u0), at(s1, u1), at(s0, u1)])
