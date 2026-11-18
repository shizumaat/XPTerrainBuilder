"""THE DECK WARP OF ONE OBJ8 CUT (#2144 P2; design-surface spec §49 (5)
"THE BODY IS SHEARED, NOT STEPPED"; ``airport/deck_profile`` decides it).

A warped body is written with every static vertex, line vertex and light
moved straight up by one displacement FIELD over the authored plan,
``y' = y + D(x, z)``: x and z never move, so piers stay vertical, the plan
footprint is the authored one and two triangles sharing a vertex move it
alike (the mesh stays closed with no clip).  The field is given by the
deck's TRACK (owner 2026-11-17T23:33Z: "if the rail is being sloped,
shouldn't the piers never need to be much taller?"), :data:`Track`
``("track", ((x, z, D), ...))``: the deck's centreline in the placement's
authored frame with the displacement at each vertex.  A point takes the
station of its nearest point on the centreline, and ``D`` there is linear
in distance ALONG the track between two vertices -- so the deck follows the
straight grade between its nodes and a pier under it stands near its
authored height.  A normal is carried by the inverse transpose of the shear
``[[1,0,0],[Dx,1,Dz],[0,0,1]]`` (``n' = (nx - Dx ny, ny, nz - Dz ny)``,
renormalised).  ``ANIM`` geometry is never displaced (the split writer
refuses the warp for a body owning a block, as it refuses the seat tilt).

A PIER FOOT (owner 2026-11-17T20:43Z: "a pier foot may stretch by at
most 3 m") is a second kind of item in the same list, :data:`Foot`
``("foot", x, z, y_max, drop)``: every static vertex within
:data:`FOOT_REACH_M` of ``(x, z)`` in plan with authored ``y <= y_max``
(the foot's bottom band) is lowered a further ``drop``, so the pier
lengthens down to the ground while its top stays with the deck.

With no track and no foot every function here is the identity, so an unwarped body's
file is byte-identical to the pre-warp writer's.
"""
from __future__ import annotations

import hashlib
import struct
import typing as _t

import numpy as np

__all__ = ["Track", "Foot", "FOOT_REACH_M", "Field", "warp_digest", "warp_rows"]

#: the deck's track: ``("track", ((x, z, D), ...))`` (module doc)
Track = tuple[str, tuple[tuple[float, float, float], ...]]

#: one pier foot: ``("foot", x, z, y_max, drop)`` (module doc)
Foot = tuple[str, float, float, float, float]

#: a foot's bottom vertices are those within this of its point in plan, m
FOOT_REACH_M = 1.5


def _is_foot(item: _t.Any) -> bool:
    return len(item) == 5 and item[0] == "foot"


def _is_track(item: _t.Any) -> bool:
    return len(item) == 2 and item[0] == "track"


#: the finite-difference step of the field's gradient, metres
GRAD_STEP_M = 0.25


class Field:
    """The displacement field of a body's track and feet (module doc)."""

    def __init__(self, items: _t.Sequence[_t.Any]) -> None:
        import shapely
        self.feet = np.asarray([[float(v) for v in f[1:]] for f in items if _is_foot(f)],
                               float).reshape(-1, 4)
        pts = [np.asarray(t[1], float).reshape(-1, 3) for t in items if _is_track(t)]
        pts = [p for p in pts if p.shape[0] >= 2]
        self._line = None
        if pts:
            p = pts[0]
            self._line = shapely.LineString(p[:, :2])
            self._station = np.concatenate(
                [[0.0], np.cumsum(np.hypot(*np.diff(p[:, :2], axis=0).T))])
            self._d = p[:, 2]

    def __bool__(self) -> bool:
        return self._line is not None or bool(self.feet.shape[0])

    def drop(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
        """The further lowering of each point by the pier feet: the largest
        ``drop`` of a foot within :data:`FOOT_REACH_M` whose bottom band
        (``y <= y_max``) holds it, else 0."""
        out = np.zeros(np.shape(x))
        for fx, fz, y_max, d in self.feet:
            hit = (np.hypot(x - fx, z - fz) <= FOOT_REACH_M) & (y <= y_max)
            out[hit] = np.maximum(out[hit], d)
        return out

    def at(self, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        """``D`` at the authored plan points ``(x, z)``: linear along the
        track at each point's nearest station."""
        import shapely
        x = np.atleast_1d(np.asarray(x, float))
        z = np.atleast_1d(np.asarray(z, float))
        if self._line is None:
            return np.zeros_like(x)
        st = shapely.line_locate_point(self._line, shapely.points(x, z))
        return np.interp(st, self._station, self._d)

    def grad(self, x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """``(dD/dx, dD/dz)`` by central differences of :data:`GRAD_STEP_M`."""
        h = GRAD_STEP_M
        x = np.asarray(x, float)
        z = np.asarray(z, float)
        gx = (self.at(x + h, z) - self.at(x - h, z)) / (2 * h)
        gz = (self.at(x, z + h) - self.at(x, z - h)) / (2 * h)
        return gx, gz


def warp_digest(items: _t.Sequence[_t.Any]) -> bytes:
    """The warp items as bytes (mm-rounded), for the file name's hash: two
    placements whose warps differ never share a file."""
    h = hashlib.blake2s(digest_size=8)
    for item in items:
        if _is_foot(item):
            h.update(b"F" + struct.pack("<4d", *(round(float(v), 3) for v in item[1:])))
        elif _is_track(item):
            h.update(b"T")
            for q in item[1]:
                h.update(struct.pack("<3d", *(round(float(v), 3) for v in q)))
    return h.digest()


def warp_rows(rows: _t.Sequence[str], first: int, field: "Field | None",
              normal_at: int = -1) -> list[str]:
    """``rows`` (``VT`` / ``VLINE`` / ``VLIGHT``-shaped: three coordinates at
    token ``first``) with each position raised by the field, a normal at
    ``normal_at`` carried by the shear's inverse transpose.  Positions are
    printed to the micrometre (the split writer rounds them again to the
    millimetre after its offset).  No field: the rows unchanged."""
    if field is None or not field or not rows:
        return list(rows)
    toks = [r.split() for r in rows]
    xs = np.zeros(len(rows))
    ys = np.zeros(len(rows))
    zs = np.zeros(len(rows))
    ok = np.zeros(len(rows), bool)
    for i, t in enumerate(toks):
        try:
            xs[i], ys[i], zs[i] = (float(t[first]), float(t[first + 1]),
                                   float(t[first + 2]))
            ok[i] = True
        except (IndexError, ValueError):
            pass
    d = field.at(xs, zs) - field.drop(xs, ys, zs)
    gx, gz = (field.grad(xs, zs) if normal_at >= 0
              else (np.zeros(len(rows)), np.zeros(len(rows))))
    out = []
    for i, t in enumerate(toks):
        if not ok[i]:
            out.append(rows[i])
            continue
        t = list(t)
        t[first + 1] = f"{float(t[first + 1]) + d[i]:.6f}"
        if normal_at >= 0:
            try:
                n = [float(t[normal_at + j]) for j in range(3)]
            except (IndexError, ValueError):
                n = [0.0, 0.0, 0.0]
            if n[0] or n[1] or n[2]:
                m = np.asarray([n[0] - gx[i] * n[1], n[1], n[2] - gz[i] * n[1]])
                m = m / (float(np.linalg.norm(m)) or 1.0)
                for j in range(3):
                    t[normal_at + j] = f"{m[j]:.6f}"
        out.append("\t".join(t))
    return out
