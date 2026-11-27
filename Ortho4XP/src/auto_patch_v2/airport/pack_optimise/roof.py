"""THE PACK'S OWN ROOF (issue #1707, "Optimise pack" step ``interior``).

Owner (2026-11-14): the props under an airport pack's own roof are drawn
only nearby and nothing under that roof casts a shadow.  "Under the
roof" is read from the pack's geometry alone, never from a name:

* the ROOF is every near-horizontal face (``|normal.y| >=``
  :data:`NORMAL_Y_MIN`) reaching :data:`ROOF_MIN_Y_M` or more above the
  ground, of every placed pack object that is not small
  (``objcopy.SMALL_M``) and does not move — a terminal's roof, its
  ceilings, a canopy, a deck;
* it is read on a :data:`CELL_M` grid around one origin: per cell the
  highest such face above the ground (:func:`read_roof`);
* a PLACEMENT is under it (:func:`under`) when its cell has a roof
  standing more than :data:`HEADROOM_M` over the row's own height above
  the ground (an ``OBJECT`` row: 0; ``OBJECT_AGL``: its height; an
  ``OBJECT_MSL`` row has no ground to measure from and is never under);
* a large INSTANCE is under it (:func:`covered`) when over
  :data:`COVERED_SHARE` of its plan another instance's roof stands more
  than :data:`HEADROOM_M` over its own top, a cell all round (so a wall
  standing at the roof's edge, whose shadow the roof's does not replace
  under a low sun, is not under it) — an interior shell under the
  terminal, never the roof itself.

The roof the recipe keeps (:func:`encode`) is the grid's cells with
their roof height in whole metres (rounded down), as row runs, so a
later write tests its rows exactly as the plan did (:func:`decode`);
the plan keeps only the cells it needs (``interior.plan_interior``).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np

from ..obj8 import parse_obj8

__all__ = ["CELL_M", "ROOF_MIN_Y_M", "NORMAL_Y_MIN", "HEADROOM_M",
           "COVERED_SHARE", "Roof", "Instance", "instances", "read_roof",
           "covered", "under", "cell_of", "encode", "decode"]

#: the grid's cell
CELL_M = 5.0
#: a face this high above the ground or higher can be a roof
ROOF_MIN_Y_M = 6.0
#: a face whose unit normal has at least this vertical part is near-horizontal
NORMAL_Y_MIN = 0.7
#: a roof must stand at least this much over what it covers
HEADROOM_M = 2.0
#: share of an instance's plan the roof must cover for it to be under it
COVERED_SHARE = 0.9
#: metres per degree of latitude (the grid's local frame)
_M_PER_DEG = 110540.0
_M_PER_DEG_LON_EQ = 111320.0
#: a triangle spanning more cells than this is not rasterised (a malformed face)
_MAX_CELLS = 40000


@_dc.dataclass
class Instance:
    """One placement of a pack object in the grid's frame: its roof
    faces (:func:`_roof_faces`) as ``(n, 3, 3)`` ``(east, north, up)``
    metres, ``up`` above the ground, and its plan — the cells its drawn
    vertices fall in (``keys``, :func:`_key`) with its top in each."""

    ordinal: int
    path: str
    faces: np.ndarray
    keys: np.ndarray
    tops: np.ndarray


@_dc.dataclass
class Roof:
    """The roof on the grid, per cell (``keys`` sorted, :func:`_key`):
    the highest roof face (``top``), whose instance it is (``owner``) and
    the highest of any other instance (``second``, ``-inf`` without)."""

    lat0: float
    lon0: float
    keys: np.ndarray
    top: np.ndarray
    owner: np.ndarray
    second: np.ndarray

    def above(self, keys: np.ndarray, ordinal: int = -1) -> np.ndarray:
        """Per cell of ``keys``, the highest roof of an instance other
        than ``ordinal`` (``-inf`` without one)."""
        out = np.full(len(keys), -np.inf)
        if not len(self.keys):
            return out
        at = np.minimum(np.searchsorted(self.keys, keys), len(self.keys) - 1)
        hit = self.keys[at] == keys
        mine = self.owner[at] == ordinal
        out[hit] = np.where(mine, self.second[at], self.top[at])[hit]
        return out


#: cell indices are offset into one int64 key
_OFF = 1 << 30


def _key(i: np.ndarray, j: np.ndarray) -> np.ndarray:
    return (i.astype(np.int64) + _OFF) * (2 * _OFF) + (j.astype(np.int64) + _OFF)


def _unkey(k: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return k // (2 * _OFF) - _OFF, k % (2 * _OFF) - _OFF


def _kx(lat0: float) -> float:
    return _M_PER_DEG_LON_EQ * math.cos(math.radians(lat0))


def _cell(lat0: float, lon0: float, lon: float, lat: float) -> tuple[int, int]:
    return (int(math.floor((lat - lat0) * _M_PER_DEG / CELL_M)),
            int(math.floor((lon - lon0) * _kx(lat0) / CELL_M)))


def _row_height(toks: _t.Sequence[str]) -> float | None:
    """A placement row's height above the ground: ``0`` for ``OBJECT``,
    the stated height for ``OBJECT_AGL``, ``None`` (unknown) for any
    other kind."""
    if toks[0] == "OBJECT":
        return 0.0
    if toks[0] == "OBJECT_AGL" and len(toks) >= 5:
        try:
            return float(toks[4])
        except ValueError:
            return None
    return None


def _heading(toks: _t.Sequence[str]) -> float:
    i = 4 if toks[0] == "OBJECT" else 5
    try:
        return float(toks[i]) if len(toks) > i else 0.0
    except ValueError:
        return 0.0


def _max_per_key(keys: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The unique ``keys`` and the highest ``z`` of each."""
    if not len(keys):
        return keys, z
    order = np.lexsort((-z, keys))
    keys, z = keys[order], z[order]
    first = np.r_[True, keys[1:] != keys[:-1]]
    return keys[first], z[first]


def instances(pack_root: str, rows: _t.Iterable[tuple[int, str, _t.Sequence[str]]],
              shapes: _t.Mapping[str, _t.Any], lat0: float, lon0: float
              ) -> list[Instance]:
    """``rows`` ``(ordinal, declared path, tokens)`` of objects with a
    ``shapes[path]`` (``shape.Shape``) that do not move, as
    :class:`Instance` in the frame of ``(lat0, lon0)``: turned by the
    row's heading and moved to its position.  An object's file is read
    for its roof faces only when it reaches :data:`ROOF_MIN_Y_M`; rows of
    unknown height are left out."""
    faces: dict[str, np.ndarray] = {}
    kx = _kx(lat0)
    out: list[Instance] = []
    for ordinal, path, toks in rows:
        s = shapes.get(path)
        h = _row_height(toks)
        if s is None or s.animated or h is None:
            continue
        if s.box[3] + h >= ROOF_MIN_Y_M and path not in faces:
            faces[path] = _local_faces(os.path.join(
                pack_root, *path.replace("\\", "/").split("/")))
        at = (math.radians(_heading(toks)), (float(toks[2]) - lon0) * kx,
              (float(toks[3]) - lat0) * _M_PER_DEG, h)
        f = faces.get(path)
        f = _roof_faces(_place(f, at)) if f is not None and len(f) else np.zeros((0, 3, 3))
        pts = _place(s.points, at)
        keys, tops = _max_per_key(
            _key(np.floor(pts[:, 1] / CELL_M), np.floor(pts[:, 0] / CELL_M)), pts[:, 2])
        out.append(Instance(ordinal, path, f, keys, tops))
    return out


def _place(p: np.ndarray, at: tuple[float, float, float, float]) -> np.ndarray:
    """Authored points ``p`` (``obj8``: x east, y up, z south) turned by
    the heading and moved: ``at = (heading rad, east, north, height)``."""
    hr, e0, n0, h = at
    x, n = p[..., 0], -p[..., 2]
    return np.stack([x * math.cos(hr) + n * math.sin(hr) + e0,
                     -x * math.sin(hr) + n * math.cos(hr) + n0,
                     p[..., 1] + h], axis=-1)


def _local_faces(phys: str) -> np.ndarray | None:
    """The authored solid triangles ``(n, 3, 3)`` of ``phys`` that are
    near-horizontal (any height: the row's own adds to it)."""
    try:
        g = parse_obj8(phys)
    except (OSError, ValueError):
        return None
    t = g.vertices[g.solid] if g.solid.shape[0] else np.zeros((0, 3, 3))
    return _horizontal(t, 1)


def _horizontal(t: np.ndarray, up: int) -> np.ndarray:
    """The near-horizontal faces of ``t`` (``up`` = the vertical axis)."""
    if not t.shape[0]:
        return t
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    length = np.linalg.norm(nrm, axis=1)
    ok = length > 1e-9
    vert = np.zeros(len(t))
    vert[ok] = np.abs(nrm[ok, up]) / length[ok]
    return t[ok & (vert >= NORMAL_Y_MIN)]


def _roof_faces(t: np.ndarray) -> np.ndarray:
    """The faces of ``t`` (placed) that can be a roof: near-horizontal
    and reaching :data:`ROOF_MIN_Y_M`."""
    if not t.shape[0]:
        return t
    return t[t[:, :, 2].max(axis=1) >= ROOF_MIN_Y_M]


def _raster(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(keys, height)`` of every grid cell whose centre a triangle of
    ``t`` holds, at the triangle's height there (one row per hit)."""
    if not t.shape[0]:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    xs, ys = t[:, :, 0] / CELL_M - 0.5, t[:, :, 1] / CELL_M - 0.5
    c0, c1 = np.ceil(xs.min(1)).astype(np.int64), np.floor(xs.max(1)).astype(np.int64)
    r0, r1 = np.ceil(ys.min(1)).astype(np.int64), np.floor(ys.max(1)).astype(np.int64)
    w, hgt = np.maximum(c1 - c0 + 1, 0), np.maximum(r1 - r0 + 1, 0)
    count = w * hgt
    keep = (count > 0) & (count <= _MAX_CELLS)
    t, xs, ys, c0, r0, w, count = (a[keep] for a in (t, xs, ys, c0, r0, w, count))
    tri = np.repeat(np.arange(len(t)), count)
    k = np.arange(int(count.sum())) - np.repeat(np.cumsum(count) - count, count)
    cx = c0[tri] + k % w[tri]
    cy = r0[tri] + k // w[tri]
    x, y = xs[tri], ys[tri]
    d = (y[:, 1] - y[:, 2]) * (x[:, 0] - x[:, 2]) + (x[:, 2] - x[:, 1]) * (y[:, 0] - y[:, 2])
    good = np.abs(d) > 1e-12
    d = np.where(good, d, 1.0)
    l1 = ((y[:, 1] - y[:, 2]) * (cx - x[:, 2]) + (x[:, 2] - x[:, 1]) * (cy - y[:, 2])) / d
    l2 = ((y[:, 2] - y[:, 0]) * (cx - x[:, 2]) + (x[:, 0] - x[:, 2]) * (cy - y[:, 2])) / d
    l3 = 1.0 - l1 - l2
    m = good & (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
    z = t[tri, :, 2]
    hz = l1 * z[:, 0] + l2 * z[:, 1] + l3 * z[:, 2]
    return _key(cy[m], cx[m]), hz[m]


def read_roof(insts: _t.Sequence[Instance], lat0: float, lon0: float) -> Roof:
    """The :class:`Roof` of the instances ``insts``."""
    ks, zs, os_ = [], [], []
    for inst in insts:
        k, z = _max_per_key(*_raster(inst.faces))
        ks.append(k)
        zs.append(z)
        os_.append(np.full(len(k), inst.ordinal, dtype=np.int64))
    k = np.concatenate(ks) if ks else np.zeros(0, dtype=np.int64)
    if not len(k):                          # no instance covers a cell
        e = np.zeros(0, dtype=np.int64)
        return Roof(lat0, lon0, e, np.zeros(0), e, np.zeros(0))
    z, o = np.concatenate(zs), np.concatenate(os_)
    order = np.lexsort((-z, k))
    k, z, o = k[order], z[order], o[order]
    first = np.r_[True, k[1:] != k[:-1]]
    nxt = np.r_[first[1:], True]            # the next row starts a new cell
    second = np.where(~nxt, np.r_[z[1:], -np.inf], -np.inf)
    return Roof(lat0, lon0, k[first], z[first], o[first], second[first])


def covered(roof: Roof, inst: Instance) -> bool:
    """Whether another instance's roof stands over ``inst`` — over
    :data:`COVERED_SHARE` of its plan (its vertices' cells), more than
    :data:`HEADROOM_M` over its own top there and a cell all round."""
    if not len(inst.keys):
        return False
    ok = np.ones(len(inst.keys), dtype=bool)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ok &= roof.above(inst.keys + di * 2 * _OFF + dj, inst.ordinal) > inst.tops + HEADROOM_M
    return int(ok.sum()) >= COVERED_SHARE * len(inst.keys)


def under(cells: _t.Mapping[tuple[int, int], float], lat0: float, lon0: float,
          toks: _t.Sequence[str]) -> bool:
    """Whether the placement row ``toks`` stands under the roof
    ``cells`` (``{(i, j): roof height}``, :func:`decode`)."""
    h = _row_height(toks)
    if h is None:
        return False
    try:
        key = cell_of(lat0, lon0, toks)
    except (ValueError, IndexError):
        return False
    return cells.get(key, -math.inf) > h + HEADROOM_M


def cell_of(lat0: float, lon0: float, toks: _t.Sequence[str]) -> tuple[int, int]:
    """The grid cell of the placement row ``toks``."""
    return _cell(lat0, lon0, float(toks[2]), float(toks[3]))


def encode(roof: Roof, keys: _t.Iterable[tuple[int, int]] | None = None
           ) -> list[list[int]]:
    """The roof's cells (only ``keys``, when given) as runs ``[i, j0,
    j1, height]`` (height in whole metres, rounded down) — what the
    recipe keeps."""
    ii, jj = _unkey(roof.keys)
    z = np.floor(roof.top).astype(np.int64)
    sel = np.ones(len(ii), dtype=bool)
    if keys is not None:
        want = list(keys)
        sel = np.isin(roof.keys, _key(np.array([k[0] for k in want], dtype=np.int64),
                                      np.array([k[1] for k in want], dtype=np.int64)))
    runs: list[list[int]] = []
    for i, j, h in zip(ii[sel].tolist(), jj[sel].tolist(), z[sel].tolist(), strict=True):
        if runs and runs[-1][0] == i and runs[-1][2] == j - 1 and runs[-1][3] == h:
            runs[-1][2] = j
        else:
            runs.append([i, j, j, h])
    return runs


def decode(runs: _t.Iterable[_t.Sequence[int]]) -> dict[tuple[int, int], float]:
    """:func:`encode`'s runs back as ``{(i, j): height}``."""
    out: dict[tuple[int, int], float] = {}
    for i, j0, j1, z in runs:
        for j in range(int(j0), int(j1) + 1):
            out[(int(i), int(j))] = float(z)
    return out
