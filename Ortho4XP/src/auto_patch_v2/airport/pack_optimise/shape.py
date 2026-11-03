"""WHAT AN OBJECT LOOKS LIKE TO "OPTIMISE PACK" (issue #1707): the few
facts the library swap (:mod:`.swap`) matches a pack object and a
library object on.

* the FOOTPRINT — the authored box of every drawn triangle's vertices
  (x east, y up, z south; ``obj8``'s frame) and its height;
* the TRIANGLES the file draws (its ``POINT_COUNTS`` indices / 3);
* whether anything MOVES (``ANIM_begin``) — a moving object is never
  swapped for a still one;
* the LIGHTS: the self-contained light rows (``LIGHT_NAMED``,
  ``LIGHT_PARAM``, ``LIGHT_CUSTOM``, ``LIGHT_SPILL_CUSTOM``) outside any
  animation, which a swapped object keeps through a lights-only copy
  (owner 2026-11-03: the parked cars' spill lights stay), and whether
  it has lights that cannot be copied so (``LIGHTS`` from the vertex
  light table, or a light inside an animation, or smoke);
* the FRONT, when the file proves it: its head lights against its tail
  lights (a light name with ``head`` / ``front`` against ``tail`` /
  ``brake`` / ``rear``);
* the PROFILE: the top of the object along its long axis, which tells a
  stair's high end from its low one, or a bonnet from a boot.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np

from ..obj8 import parse_obj8

__all__ = ["Shape", "read_shape", "profile", "LIGHT_ROWS"]

#: the light rows that carry their own position (copyable as they stand)
LIGHT_ROWS = frozenset({"LIGHT_NAMED", "LIGHT_PARAM", "LIGHT_CUSTOM",
                        "LIGHT_SPILL_CUSTOM"})
#: rows that emit light or smoke and cannot be copied without the
#: object's vertex light table or its animation
_UNCOPYABLE = frozenset({"LIGHTS", "LIGHT_LEVEL", "SMOKE_BLACK",
                         "SMOKE_WHITE", "EMITTER"})
_FRONT_WORDS = ("head", "front", "grille")
_BACK_WORDS = ("tail", "brake", "rear", "reverse")
#: profile bins along the long axis
PROFILE_BINS = 8


@_dc.dataclass(frozen=True)
class Shape:
    """One object file as the swap reads it.  ``box`` is
    ``(xmin, xmax, ymin, ymax, zmin, zmax)`` of its drawn vertices."""

    path: str
    tris: int
    box: tuple[float, float, float, float, float, float]
    animated: bool
    lights: tuple[str, ...]            # copyable light rows, verbatim
    uncopyable_lights: bool
    front: tuple[float, float] | None  # (x, z) unit vector, head lights
    points: np.ndarray = _dc.field(repr=False, compare=False,
                                   default_factory=lambda: np.zeros((0, 3)))
    header: tuple[str, ...] = ()       # TEXTURE / TEXTURE_LIT rows

    @property
    def size(self) -> tuple[float, float, float]:
        """``(x extent, z extent, height)`` in metres."""
        b = self.box
        return (b[1] - b[0], b[5] - b[4], b[3] - b[2])

    @property
    def centre(self) -> tuple[float, float]:
        """The footprint's centre ``(x, z)``."""
        b = self.box
        return ((b[0] + b[1]) / 2.0, (b[4] + b[5]) / 2.0)


_MEMO: dict[tuple[str, int, int], Shape | None] = {}


def read_shape(path: str) -> Shape | None:
    """The :class:`Shape` of an OBJ8 file, ``None`` when it draws nothing
    or cannot be read.  Memoised on the file's size and time."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    if key not in _MEMO:
        try:
            _MEMO[key] = _read(path)
        except (OSError, ValueError):
            _MEMO[key] = None
    return _MEMO[key]


def _read(path: str) -> Shape | None:
    g = parse_obj8(path)
    tri = np.concatenate([g.solid, g.draped]) if g.draped.shape[0] else g.solid
    if not tri.shape[0]:
        return None
    pts = g.vertices[np.unique(tri.ravel())]
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    box = (float(lo[0]), float(hi[0]), float(lo[1]), float(hi[1]),
           float(lo[2]), float(hi[2]))
    lights, header = [], []
    uncopyable = animated = False
    depth = 0
    heads: list[tuple[float, float]] = []
    tails: list[tuple[float, float]] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            toks = raw.split()
            if not toks:
                continue
            kw = toks[0]
            if kw == "ANIM_begin":
                depth += 1
                animated = True
            elif kw == "ANIM_end":
                depth = max(0, depth - 1)
            elif kw in ("TEXTURE", "TEXTURE_LIT") and not lights:
                header.append(raw.strip())
            elif kw in _UNCOPYABLE:
                uncopyable = True
            elif kw in LIGHT_ROWS:
                if depth:
                    uncopyable = True
                    continue
                lights.append(raw.strip())
                if kw == "LIGHT_NAMED" and len(toks) >= 5:
                    _witness(toks[1].lower(), toks[2], toks[4], heads, tails)
    return Shape(path, int(tri.shape[0]), box, animated, tuple(lights),
                 uncopyable, _front(heads, tails), pts, tuple(header))


def _witness(name: str, x: str, z: str, heads: list, tails: list) -> None:
    try:
        p = (float(x), float(z))
    except ValueError:
        return
    if any(w in name for w in _FRONT_WORDS):
        heads.append(p)
    elif any(w in name for w in _BACK_WORDS):
        tails.append(p)


def _front(heads: list, tails: list) -> tuple[float, float] | None:
    """The unit vector from the tail lights to the head lights, ``None``
    without both."""
    if not heads or not tails:
        return None
    hx, hz = np.mean(heads, axis=0)
    tx, tz = np.mean(tails, axis=0)
    dx, dz = float(hx - tx), float(hz - tz)
    n = math.hypot(dx, dz)
    return (dx / n, dz / n) if n > 0.2 else None


def profile(points: np.ndarray, axis: int) -> np.ndarray:
    """The top of ``points`` along ``axis`` (0 = x, 2 = z), in
    :data:`PROFILE_BINS` bins from its low end to its high end, each the
    highest y in the bin over the object's height (``nan`` = empty)."""
    out = np.full(PROFILE_BINS, np.nan)
    if not points.shape[0]:
        return out
    a = points[:, axis]
    span = float(a.max() - a.min())
    height = float(points[:, 1].max() - points[:, 1].min()) or 1.0
    if span <= 0:
        return out
    k = np.minimum(((a - a.min()) / span * PROFILE_BINS).astype(int),
                   PROFILE_BINS - 1)
    y = points[:, 1] - points[:, 1].min()
    for b in range(PROFILE_BINS):
        sel = y[k == b]
        if sel.shape[0]:
            out[b] = float(sel.max()) / height
    return out
