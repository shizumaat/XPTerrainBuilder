"""THE WITNESS'S INPUTS FOR ONE FRAME (#2065; spec ``2065-bridge-class-A1.md``
§A4 S0 / S1): the placed solid faces of a frame's members, their plan
vertices (W6's bodies), the frame's faces near its decks (W4's open sky) and
every pack object's up-facing faces under a deck (W4b, A1-E1 E2) — ONE
assembly for the pack-stage read (``planar/free_bridge``) and the offline
census (``tools/bridge_census.py``), each handing in its own placements.

A placement is ``(geometry, xy, heading_deg)``: an OBJ8 geometry
(``obj8.ObjGeometry``: ``vertices``, ``solid``) placed in the airport frame.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from .bridge_witness import placed_faces, up_faces

__all__ = ["solid_faces", "body_points", "faces_in_box", "Under"]

XY = tuple[float, float]
#: W6 reads at most this many plan vertices per body (strided)
BODY_CAP = 4000


def solid_faces(g: _t.Any, xy: XY, heading_deg: float) -> np.ndarray:
    """The solid triangles of geometry ``g`` placed at ``xy`` /
    ``heading_deg`` as ``(n, 3, 3)`` frame x, y, authored y (empty for no
    geometry)."""
    if g is None or not len(g.solid):
        return np.zeros((0, 3, 3))
    return placed_faces(np.asarray(g.vertices)[:, :3], g.solid, xy, float(heading_deg or 0.0))


def body_points(faces: np.ndarray, cap: int = BODY_CAP) -> np.ndarray:
    """W6's body: the distinct plan vertices of ``faces`` (cm), strided to
    ``cap``."""
    if not len(faces):
        return np.zeros((0, 2))
    f = np.unique(np.round(faces[:, :, :2].reshape(-1, 2), 2), axis=0)
    return f[:: max(1, len(f) // cap)]


def faces_in_box(faces: _t.Iterable[np.ndarray], box: tuple) -> np.ndarray:
    """Every face of ``faces`` (one array per placement) whose plan box
    meets ``box`` ``(x0, y0, x1, y1)``."""
    parts = []
    for f in faces:
        if not len(f):
            continue
        lo, hi = f[:, :, :2].min(axis=1), f[:, :, :2].max(axis=1)
        parts.append(f[(hi[:, 0] >= box[0]) & (lo[:, 0] <= box[2])
                       & (hi[:, 1] >= box[1]) & (lo[:, 1] <= box[3])])
    return np.concatenate(parts) if parts else np.zeros((0, 3, 3))


class Under:
    """Every pack placement's up-facing faces, placed once on demand (W4b,
    A1-E1 E2).  ``placed``: ``(unit key, geometry, xy, heading_deg[, plan
    bounds])`` per placement — the bounds, where known, only skip placing a
    placement that cannot meet; ``datum(unit key)``: ``(G at the unit's anchor + its agl_m,
    shifted)`` — ``shifted`` false where no DEM read it.

    ``for_unit(own, same)(bounds)`` -> the faces of every placement whose
    placed solid faces' plan bounds meet ``bounds`` (never by origin
    distance), a unit other than ``own`` (or one of ``same``, its frame's)
    brought into ``own``'s frame by its datum less ``own``'s (the ``agl_m``
    difference alone with no DEM: ``unshifted`` names those units)."""

    def __init__(self, placed: _t.Sequence[tuple], datum: _t.Callable[[_t.Any], tuple],
                 normal: float) -> None:
        self._p = list(placed)
        self._datum, self._normal = datum, normal
        self._faces: dict[int, tuple] = {}
        self._z: dict = {}
        self.unshifted: set = set()

    def _of(self, k: int) -> tuple[np.ndarray, tuple]:
        if k not in self._faces:
            _u, g, xy, hd = self._p[k][:4]
            f = solid_faces(g, xy, hd)
            if not len(f):
                self._faces[k] = (f, (math.inf,) * 2 + (-math.inf,) * 2)
            else:
                lo, hi = f[:, :, :2].min(axis=(0, 1)), f[:, :, :2].max(axis=(0, 1))
                self._faces[k] = (up_faces(f, self._normal), (*lo, *hi))
        return self._faces[k]

    def _zero(self, u) -> tuple[float, bool]:
        if u not in self._z:
            self._z[u] = self._datum(u)
        return self._z[u]

    def for_unit(self, own, same: _t.Collection = ()) -> _t.Callable[[tuple], np.ndarray]:
        def under(b) -> np.ndarray:
            parts = []
            for k, p in enumerate(self._p):
                pb = p[4] if len(p) > 4 else None
                if pb is not None and (pb[2] < b[0] or pb[0] > b[2] or pb[3] < b[1]
                                       or pb[1] > b[3]):
                    continue
                f, fb = self._of(k)
                if not len(f) or fb[2] < b[0] or fb[0] > b[2] or fb[3] < b[1] or fb[1] > b[3]:
                    continue
                u = p[0]
                if u != own and u not in same:
                    (zu, su), (zo, so) = self._zero(u), self._zero(own)
                    f = f.copy()
                    f[:, :, 2] += zu - zo
                    if not (su and so):
                        self.unshifted.add(own)
                parts.append(f)
            return np.concatenate(parts) if parts else np.zeros((0, 3, 3))
        return under
