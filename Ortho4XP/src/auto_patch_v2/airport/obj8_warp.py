"""THE DECK WARP OF ONE OBJ8 CUT (#2144 P2; design-surface spec §49 (5)
"THE BODY IS SHEARED, NOT STEPPED"; ``airport/deck_profile`` decides it).

A warped body is written with every static vertex, line vertex and light
moved straight up by one displacement FIELD over the authored plan,
``y' = y + D(x, z)``: x and z never move, so piers stay vertical, the plan
footprint is the authored one and two triangles sharing a vertex move it
alike (the mesh stays closed with no clip).  The field is given by its
NODES -- ``(D_k, rings)``, each ring a plan polygon ``((x, z), ...)`` in the
placement's authored frame -- and is the inverse-distance blend

    D(p) = sum(D_k / d_k(p)) / sum(1 / d_k(p))

with ``d_k`` the plan distance from ``p`` to node k's polygons: exactly
``D_k`` inside node k, the straight grade between two nodes.  A normal is
carried by the inverse transpose of the shear ``[[1,0,0],[Dx,1,Dz],[0,0,1]]``
(``n' = (nx - Dx ny, ny, nz - Dz ny)``, renormalised).  ``ANIM`` geometry is
never displaced (the split writer refuses the warp for a body owning a
block, as it refuses the seat tilt).

A PIER FOOT (owner 2026-11-17T20:43Z: "a pier foot may stretch by at
most 3 m") is a second kind of item in the same list, :data:`Foot`
``("foot", x, z, y_max, drop)``: every static vertex within
:data:`FOOT_REACH_M` of ``(x, z)`` in plan with authored ``y <= y_max``
(the foot's bottom band) is lowered a further ``drop``, so the pier
lengthens down to the ground while its top stays with the deck.

With no node every function here is the identity, so an unwarped body's
file is byte-identical to the pre-warp writer's.
"""
from __future__ import annotations

import hashlib
import struct
import typing as _t

import numpy as np

__all__ = ["Node", "Foot", "FOOT_REACH_M", "Field", "warp_digest", "warp_rows"]

#: one node: ``(D, rings)`` -- the displacement and the plan polygons,
#: authored ``(x, z)``, inside which the field is exactly ``D``
Node = tuple[float, tuple[tuple[tuple[float, float], ...], ...]]

#: one pier foot: ``("foot", x, z, y_max, drop)`` (module doc)
Foot = tuple[str, float, float, float, float]

#: a foot's bottom vertices are those within this of its point in plan, m
FOOT_REACH_M = 1.5


def _is_foot(item: _t.Any) -> bool:
    return len(item) == 5 and item[0] == "foot"


#: the finite-difference step of the field's gradient, metres
GRAD_STEP_M = 0.25


class Field:
    """The displacement field of a body's nodes (module doc)."""

    def __init__(self, items: _t.Sequence[_t.Any]) -> None:
        import shapely
        nodes = [n for n in items if not _is_foot(n)]
        self.feet = np.asarray([[float(v) for v in f[1:]] for f in items if _is_foot(f)],
                               float).reshape(-1, 4)
        self.values = np.asarray([float(n[0]) for n in nodes], float)
        polys, segs = [], []
        for _d, rings in nodes:
            ps = [shapely.Polygon(r) for r in rings if len(r) >= 3]
            polys.append(shapely.union_all([p if p.is_valid else p.buffer(0.0) for p in ps]))
            e = []
            for r in rings:
                a = np.asarray(r, float)
                if a.shape[0] >= 2:
                    e.append(np.concatenate([a, np.roll(a, -1, axis=0)], axis=1))
            segs.append(np.concatenate(e) if e else np.zeros((0, 4)))
        self._polys = polys
        self._segs = segs

    def __bool__(self) -> bool:
        return bool(self._polys) or bool(self.feet.shape[0])

    def drop(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
        """The further lowering of each point by the pier feet: the largest
        ``drop`` of a foot within :data:`FOOT_REACH_M` whose bottom band
        (``y <= y_max``) holds it, else 0."""
        out = np.zeros(np.shape(x))
        for fx, fz, y_max, d in self.feet:
            hit = (np.hypot(x - fx, z - fz) <= FOOT_REACH_M) & (y <= y_max)
            out[hit] = np.maximum(out[hit], d)
        return out

    def _distance(self, k: int, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        """Plan distance from the points to node k (0 inside it): the
        nearest ring edge, by segments, in chunks."""
        import shapely
        s = self._segs[k]
        out = np.full(x.shape, np.inf)
        for c in range(0, s.shape[0], 64):
            e = s[c:c + 64]
            ax, az, bx, bz = (e[:, i][None, :] for i in range(4))
            dx, dz = bx - ax, bz - az
            ll = dx * dx + dz * dz
            t = np.clip(((x[:, None] - ax) * dx + (z[:, None] - az) * dz)
                        / np.where(ll > 0, ll, 1.0), 0.0, 1.0)
            d = np.hypot(x[:, None] - (ax + t * dx), z[:, None] - (az + t * dz))
            out = np.minimum(out, d.min(axis=1))
        out[shapely.contains_xy(self._polys[k], x, z)] = 0.0
        return out

    def at(self, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        """``D`` at the authored plan points ``(x, z)``."""
        x = np.atleast_1d(np.asarray(x, float))
        z = np.atleast_1d(np.asarray(z, float))
        if not self._polys:
            return np.zeros_like(x)
        d = np.stack([self._distance(k, x, z) for k in range(len(self._polys))], axis=1)
        inside = d <= 1e-9
        w = 1.0 / np.where(inside, 1.0, d)
        out = (w * self.values).sum(axis=1) / w.sum(axis=1)
        hit = inside.any(axis=1)
        if hit.any():
            iv = inside[hit].astype(float)
            out[hit] = (iv * self.values).sum(axis=1) / iv.sum(axis=1)
        return out

    def grad(self, x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """``(dD/dx, dD/dz)`` by central differences of :data:`GRAD_STEP_M`."""
        h = GRAD_STEP_M
        x = np.asarray(x, float)
        z = np.asarray(z, float)
        gx = (self.at(x + h, z) - self.at(x - h, z)) / (2 * h)
        gz = (self.at(x, z + h) - self.at(x, z - h)) / (2 * h)
        return gx, gz


def warp_digest(nodes: _t.Sequence[Node]) -> bytes:
    """The node list as bytes (mm-rounded), for the file name's hash: two
    placements whose warps differ never share a file."""
    h = hashlib.blake2s(digest_size=8)
    for item in nodes:
        if _is_foot(item):
            h.update(b"F" + struct.pack("<4d", *(round(float(v), 3) for v in item[1:])))
            continue
        d, rings = item
        h.update(struct.pack("<d", round(float(d), 3)))
        for r in rings:
            for x, z in r:
                h.update(struct.pack("<2d", round(float(x), 3), round(float(z), 3)))
            h.update(b"|")
        h.update(b"#")
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
