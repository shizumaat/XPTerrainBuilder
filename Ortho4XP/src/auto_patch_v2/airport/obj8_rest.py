"""An OBJ8's ``ANIM`` blocks evaluated AT REST: where the sim draws each
animated triangle range when every dataref reads its rest value.

The vertices of an ``ANIM`` block are authored in the block's own frame
(#1984: KEGE's SAM jetway tunnel, cab and wheels are authored down to
y = -5.47 and drawn from y = 0 up once the block's translations apply).
A reader that wants the DRAWN shape (``tools/drawn_site.py``, #1903) runs
the ``ANIM_*`` commands through :class:`AnimStack` while it walks the
file and transforms each ``TRIS`` range by the pose in force.

The OBJ8 semantics read here: ``ANIM_begin`` / ``ANIM_end`` push and pop
the transform; each ``ANIM_trans`` / ``ANIM_rotate`` (two-value form or a
``*_begin`` / ``*_key`` / ``*_end`` keyframe table) post-multiplies it, so
the first command listed is the outermost; a rotation turns about its
axis through the block's origin by the right-hand rule, in degrees;
a value between two keys interpolates linearly and a value past the end
keys is CLAMPED to them; ``ANIM_hide`` / ``ANIM_show`` set the block's
visibility, in order, when the value lies in their range.  Every dataref
reads 0.0 at rest unless the caller names it.  Nothing here reads a file
or knows a pack."""
from __future__ import annotations

import math

import numpy as np

__all__ = ["AnimStack", "HIDDEN", "apply_pose"]

#: the pose of a range that is hidden at rest (draws nothing)
HIDDEN = "hidden"


def _interp(keys: list[tuple[float, np.ndarray]], value: float) -> np.ndarray:
    """The keyed quantity at ``value``: linear between keys, clamped past
    the ends (keys in any order)."""
    keys = sorted(keys, key=lambda k: k[0])
    if value <= keys[0][0]:
        return keys[0][1]
    if value >= keys[-1][0]:
        return keys[-1][1]
    for (v0, q0), (v1, q1) in zip(keys, keys[1:], strict=False):
        if v0 <= value <= v1:
            t = 0.0 if v1 == v0 else (value - v0) / (v1 - v0)
            return q0 + (q1 - q0) * t
    return keys[-1][1]


def _translate(d: np.ndarray) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = d
    return m


def _rotate(axis: np.ndarray, deg: float) -> np.ndarray:
    """Right-hand rotation by ``deg`` about ``axis`` (Rodrigues)."""
    n = float(np.linalg.norm(axis))
    m = np.eye(4)
    if n < 1e-12 or deg == 0.0:
        return m
    x, y, z = axis / n
    a = math.radians(deg)
    c, s, t = math.cos(a), math.sin(a), 1.0 - math.cos(a)
    m[:3, :3] = [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                 [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                 [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]
    return m


def _floats(toks: list[bytes], k: int) -> list[float] | None:
    try:
        return [float(t) for t in toks[1:1 + k]]
    except ValueError:
        return None


class AnimStack:
    """The transform, visibility and motion in force while an OBJ8 is
    walked line by line.  Feed every ``ANIM_*`` line's tokens to :meth:`feed`; read
    :meth:`pose` at each ``TRIS``."""

    def __init__(self, datarefs: dict[str, float] | None = None):
        self.datarefs = dict(datarefs or {})
        self._stack: list[tuple[np.ndarray, bool, bool]] = []
        self.matrix = np.eye(4)
        self.visible = True
        #: whether a DATAREF-DRIVEN command is in force (a constant offset
        #: -- an ``ANIM_trans`` whose two ends agree -- is no motion)
        self.moving = False
        self._table: tuple | None = None      # an open keyframe table

    def value(self, ref: bytes | str) -> float:
        name = ref.decode("utf-8", "replace") if isinstance(ref, bytes) else ref
        return float(self.datarefs.get(name, 0.0))

    def pose(self):
        """:data:`HIDDEN`, ``None`` (identity) or the 4x4 matrix in force."""
        if not self.visible:
            return HIDDEN
        if np.allclose(self.matrix, np.eye(4)):
            return None
        return self.matrix.copy()

    def feed(self, toks: list[bytes]) -> None:
        kw = toks[0]
        if kw == b"ANIM_begin":
            self._stack.append((self.matrix.copy(), self.visible, self.moving))
        elif kw == b"ANIM_end":
            if self._stack:
                self.matrix, self.visible, self.moving = self._stack.pop()
        elif kw == b"ANIM_trans":
            f = _floats(toks, 8 if len(toks) >= 10 else 6)
            if f is None:
                return
            a, b = np.array(f[0:3]), np.array(f[3:6])
            d = a if len(f) == 6 else _interp([(f[6], a), (f[7], b)], self.value(toks[9]))
            self.moving |= len(f) == 8 and not np.allclose(a, b)
            self.matrix = self.matrix @ _translate(d)
        elif kw == b"ANIM_rotate":
            f = _floats(toks, 7)
            if f is None or len(toks) < 9:
                return
            deg = _interp([(f[5], np.array([f[3]])), (f[6], np.array([f[4]]))],
                          self.value(toks[8]))[0]
            self.moving |= f[3] != f[4]
            self.matrix = self.matrix @ _rotate(np.array(f[0:3]), float(deg))
        elif kw == b"ANIM_trans_begin" and len(toks) >= 2:
            self._table = ("trans", None, toks[1], [])
        elif kw == b"ANIM_rotate_begin" and len(toks) >= 5:
            f = _floats(toks, 3)
            self._table = ("rotate", np.array(f) if f else None, toks[4], [])
        elif kw in (b"ANIM_trans_key", b"ANIM_rotate_key") and self._table is not None:
            f = _floats(toks, 4 if kw == b"ANIM_trans_key" else 2)
            if f is not None and len(f) == (4 if kw == b"ANIM_trans_key" else 2):
                self._table[3].append((f[0], np.array(f[1:])))
        elif kw in (b"ANIM_trans_end", b"ANIM_rotate_end") and self._table is not None:
            kind, axis, ref, keys = self._table
            self._table = None
            if keys:
                self.moving |= any(not np.allclose(k[1], keys[0][1]) for k in keys)
                q = _interp(keys, self.value(ref))
                self.matrix = self.matrix @ (_translate(q) if kind == "trans"
                                             else _rotate(axis, float(q[0])) if axis is not None
                                             else np.eye(4))
        elif kw in (b"ANIM_hide", b"ANIM_show"):
            f = _floats(toks, 2)
            self.moving = True
            if f is not None and len(toks) >= 4 and f[0] <= self.value(toks[3]) <= f[1]:
                self.visible = kw == b"ANIM_show"


def apply_pose(pose: np.ndarray, xyz: np.ndarray) -> np.ndarray:
    """``(n, 3)`` points moved by a 4x4 pose."""
    return xyz @ pose[:3, :3].T + pose[:3, 3]
