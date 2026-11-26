"""THE ROCK WITNESS: ONE TOP SHEET STANDING ON THE GROUND (RULINGS
2026-11-25j/l; spec ``docs/specs/rock-outcrop-witness-20261125.md`` 2).

Owner, 2026-11-25T23:09Z: built objects have right angles and flat
planes; rocks and terrain have none -- small facets at different angles,
almost no vertical planes.  Measured on the 5 named rocks against 651
built look-alikes, no whole-object area share separates them alone; what
does is that the top surface is ONE connected sheet and the object stands
on its own ground zero.  Five gates, read on the geometry only (RULINGS
05e: no name, no texture, no placement):

* ONE SHEET -- the upward faces (not walls; up by their stored vertex
  normals), welded at :data:`WELD_M` and joined across shared edges: the
  largest piece's share of their area is at least :data:`ROCK_MIN_SHEET`
  (a roof over a hall, a 747, a terrace of decks are many sheets);
* ON THE GROUND -- the plan grid's lowest surface stands at most
  :data:`ROCK_BASE_M` over the object's zero and its top's 95th percentile
  at least :data:`ROCK_TOP_M` over it (a curved roof stands on walls,
  metres up; a row's ``OBJECT_AGL`` lift counts, ``terrain_rock.row_datum``);
* NO STOREY WALLS -- faces with ``|n_y| <`` :data:`WALL_NY` at least
  :data:`STOREY_M` tall are at most :data:`ROCK_MAX_WALL` of the area;
* NO RIGHT-ANGLE CREASES -- of the shared-edge length between faces, at
  most :data:`ROCK_MAX_RIGHT` bends :data:`RIGHT_DEG` or more;
* NOT AXIS-ALIGNED -- the sloped upward faces' downhill azimuths, modulo
  90 degrees in 5-degree bins: the best two adjacent bins hold at most
  :data:`ROCK_MAX_AXIS` of their area (a building's roof planes face its
  four sides).

Stability (spec 2): each threshold alone may move sheet 0.5-0.95, base
0.1-5 m, wall 0.05-0.2, right 0.08-0.3, axis 0.4-0.8 with the same
verdicts; never relax one to chase a rock.  A composite of terrain and
built parts (KSRQ mesh_hill: hill, wall, tree cards, lights) is not a
rock: it is an ELLX-like partial shell (RULINGS 2026-11-25l (1)).
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["ROCK_MIN_SHEET", "ROCK_BASE_M", "ROCK_TOP_M", "ROCK_MAX_WALL", "ROCK_MAX_RIGHT",
           "ROCK_MAX_AXIS", "WALL_NY", "STOREY_M", "RIGHT_DEG", "WELD_M", "GATES",
           "features", "failed"]

ROCK_MIN_SHEET = 0.9
ROCK_BASE_M = 1.0
ROCK_TOP_M = 5.0
ROCK_MAX_WALL = 0.05
ROCK_MAX_RIGHT = 0.1
ROCK_MAX_AXIS = 0.5
#: a face is a wall when its unit normal's ``|y|`` is under this
WALL_NY = 0.1
#: a wall this tall or taller is a storey (m)
STOREY_M = 3.0
#: a crease bending this far or more is a right angle (degrees)
RIGHT_DEG = 80.0
#: vertices closer than this coincide (m)
WELD_M = 0.01
#: a sloped upward face: its unit normal's ``y`` under this
_SLOPED_NY = 0.995
#: the gates in their order, as :func:`failed` names them
GATES = ("one_sheet", "on_ground", "no_storey_walls", "no_right_creases", "not_axis_aligned")


def _edges(p: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(t1, t2, length)``: the face pairs sharing a welded edge of the
    triangles ``p`` (``(n, 3, 3)``) and that edge's length."""
    q = np.round(p.reshape(-1, 3) / WELD_M).astype(np.int64)
    _u, vid = np.unique(q, axis=0, return_inverse=True)
    vid = vid.reshape(-1, 3)
    e = np.sort(np.concatenate([vid[:, [0, 1]], vid[:, [1, 2]], vid[:, [2, 0]]]), axis=1)
    el = np.concatenate([np.linalg.norm(p[:, a] - p[:, b], axis=1)
                         for a, b in ((0, 1), (1, 2), (2, 0))])
    tid = np.tile(np.arange(len(p)), 3)
    key = e[:, 0] * (int(vid.max()) + 1) + e[:, 1]
    o = np.argsort(key, kind="stable")
    key, tid, el = key[o], tid[o], el[o]
    i = np.flatnonzero(key[1:] == key[:-1])
    return tid[i], tid[i + 1], el[i]


def _sheet(p: np.ndarray, area: np.ndarray) -> float:
    """ONE SHEET's value on the upward faces ``p`` (areas ``area``)."""
    from scipy import sparse
    from scipy.sparse.csgraph import connected_components
    t1, t2, _l = _edges(p)
    n = len(p)
    _nc, lab = connected_components(
        sparse.coo_matrix((np.ones(len(t1)), (t1, t2)), shape=(n, n)), directed=False)
    return float(np.bincount(lab, weights=area).max() / area.sum())


def _right(p: np.ndarray, unit: np.ndarray) -> float:
    """NO RIGHT-ANGLE CREASES' value on every face ``p`` (unit normals
    ``unit``; the bend is orientation-free, 0-90 degrees)."""
    t1, t2, length = _edges(p)
    if not len(t1):
        return 0.0
    c = np.clip(np.abs(np.einsum("ij,ij->i", unit[t1], unit[t2])), 0.0, 1.0)
    bent = np.degrees(np.arccos(c)) >= RIGHT_DEG
    return float(length[bent].sum() / max(float(length.sum()), 1e-9))


def _axis(unit_up: np.ndarray, area: np.ndarray) -> float:
    """NOT AXIS-ALIGNED's value on the upward faces' up-turned normals."""
    sl = unit_up[:, 1] < _SLOPED_NY
    if not area[sl].sum() > 0.0:
        return 1.0
    az = np.degrees(np.arctan2(unit_up[sl, 0], unit_up[sl, 2])) % 90.0
    h = np.histogram(az, bins=18, range=(0.0, 90.0), weights=area[sl])[0]
    return float((h + np.roll(h, 1)).max() / area[sl].sum())


def features(g: _t.Any, vt: np.ndarray, grid: _t.Any) -> dict[str, float]:
    """The five gates' values of a parsed OBJ8 ``g`` (its ``VT`` rows
    ``vt``, ``terrain_model._vt_rows``; its plan grid ``grid``, the
    ``terrain_model._grid``): ``sheet``, ``base_m``, ``top_m``, ``wall``,
    ``right``, ``axis`` (module doc)."""
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    p = g.vertices[tris].astype(float)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    a = 0.5 * np.linalg.norm(n, axis=1)
    k = a > 1e-6
    tris, p, a = tris[k], p[k], a[k]
    unit = n[k] / (2.0 * a[:, None])
    total = float(a.sum())
    cov = grid.covered
    out = {"sheet": 0.0, "base_m": float(np.nanmin(grid.bot[cov])),
           "top_m": float(np.percentile(grid.top[cov], 95.0)),
           "wall": 0.0, "right": 0.0, "axis": 1.0}
    if total <= 0.0:
        return out
    wall = np.abs(unit[:, 1]) < WALL_NY
    tall = wall & (np.ptp(p[:, :, 1], axis=1) >= STOREY_M)
    out["wall"] = float(a[tall].sum() / total)
    out["right"] = _right(p, unit)
    # up by the stored vertex normals (spec 8: assumed to point out)
    ny = vt[tris][:, :, 4].mean(axis=1) if len(vt) == len(g.vertices) else unit[:, 1]
    up = ~wall & (ny >= 0.0)
    if up.sum() >= 2:
        out["sheet"] = _sheet(p[up], a[up])
        out["axis"] = _axis(unit[up] * np.sign(unit[up][:, 1:2]), a[up])
    return out


def failed(f: _t.Mapping[str, float], lift: float = 0.0) -> list[str]:
    """The gates (:data:`GATES`) the values ``f`` (:func:`features`) fail,
    with a row's ``OBJECT_AGL`` ``lift`` (m) added to its heights."""
    ok = {"one_sheet": f["sheet"] >= ROCK_MIN_SHEET,
          "on_ground": (f["base_m"] + lift <= ROCK_BASE_M
                        and f["top_m"] + lift >= ROCK_TOP_M),
          "no_storey_walls": f["wall"] <= ROCK_MAX_WALL,
          "no_right_creases": f["right"] <= ROCK_MAX_RIGHT,
          "not_axis_aligned": f["axis"] <= ROCK_MAX_AXIS}
    return [k for k in GATES if not ok[k]]
