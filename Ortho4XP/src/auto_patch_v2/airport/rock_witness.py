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
  four sides);
* A NATURAL SURFACE (RULINGS 2026-11-26b (1)) -- owner: "no natural
  terrain or rock would have that large a continuous curve, it would have
  undulations and imperfections and changes in curvature".  On the top
  sheet seen from above (the upward faces no other face covers), each
  face's curvature (its shape operator, from its neighbours' normals,
  :func:`_smooth_curve`) is CURVED when its larger principal curvature
  times the plan span is :data:`CURVED_SPAN` or more (a radius of at
  most two thirds of the plan: a dome, a tube) and SMOOTH when it
  differs from its neighbours' by less than :data:`SMOOTH_CHANGE` of
  their sum.  The
  curved-and-smooth share of the sheet's area is at most
  :data:`ROCK_MAX_SMOOTH` (measured 2026-11-26: domes, a capsule, a
  tarp, a faceted cap of regular rings 0.54-0.82; the six named rocks,
  the other hills and the terrain shells 0.02-0.40).

Stability (spec 2): each threshold alone may move sheet 0.5-0.95, base
0.1-5 m, wall 0.05-0.2, right 0.08-0.3, axis 0.4-0.8, smooth 0.40-0.54
(and ``CURVED_SPAN`` 1.25-1.75) with the same verdicts; never relax one
to chase a rock.  A composite of terrain and built parts (KSRQ
mesh_hill: hill, wall, tree cards, lights) is not a rock: it is an
ELLX-like partial shell (RULINGS 2026-11-25l (1)).
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["ROCK_MIN_SHEET", "ROCK_BASE_M", "ROCK_TOP_M", "ROCK_MAX_WALL", "ROCK_MAX_RIGHT",
           "ROCK_MAX_AXIS", "ROCK_MAX_SMOOTH", "CURVED_SPAN", "SMOOTH_CHANGE", "WALL_NY",
           "STOREY_M", "RIGHT_DEG", "WELD_M", "GATES",
           "features", "failed"]

ROCK_MIN_SHEET = 0.9
ROCK_BASE_M = 1.0
ROCK_TOP_M = 5.0
ROCK_MAX_WALL = 0.05
ROCK_MAX_RIGHT = 0.1
ROCK_MAX_AXIS = 0.5
ROCK_MAX_SMOOTH = 0.45
#: a face is curved when its larger principal curvature times the plan
#: span is at least this (a radius of curvature of two thirds of the plan or less)
CURVED_SPAN = 1.5
#: a face's curvature is smooth when it differs from its neighbours' by
#: less than this share of their sum (Frobenius norms)
SMOOTH_CHANGE = 0.3
#: the plan raster of the top seen from above: span / this, at least
#: :data:`_SEEN_MIN_CELL_M`
_SEEN_CELLS = 128
_SEEN_MIN_CELL_M = 0.25
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
GATES = ("one_sheet", "on_ground", "no_storey_walls", "no_right_creases", "not_axis_aligned",
         "natural_surface")


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


def _seen(p_all: np.ndarray, p: np.ndarray, unit: np.ndarray, span: float) -> np.ndarray:
    """Which faces ``p`` (unit normals ``unit``, up-turned) are the top
    seen from above: no face of the solid ``p_all`` stands over their
    centroid by more than the raster's slope allowance."""
    from .terrain_shaped import bin_triangles
    cell = max(span / _SEEN_CELLS, _SEEN_MIN_CELL_M)
    x0, z0, _bot, top = bin_triangles(p_all, cell)
    c = p.mean(axis=1)
    i = np.clip(np.round((c[:, 0] - x0) / cell).astype(int), 0, top.shape[0] - 1)
    j = np.clip(np.round((c[:, 2] - z0) / cell).astype(int), 0, top.shape[1] - 1)
    t = top[i, j]
    ny = np.clip(np.abs(unit[:, 1]), 0.05, 1.0)
    allow = np.sqrt(1.0 - ny ** 2) / ny * cell + 0.05
    return ~np.isfinite(t) | (c[:, 1] >= t - allow)


def _smooth_curve(p: np.ndarray, unit: np.ndarray, area: np.ndarray, span: float) -> float:
    """A NATURAL SURFACE's value (module doc) on the top faces ``p``
    (up-turned unit normals ``unit``, areas ``area``) of an object spanning
    ``span`` metres: each face's shape operator ``S`` (2 x 2, in its
    tangent frame) is the least-squares fit of ``n_j - n_i = S (c_j -
    c_i)`` over its edge neighbours ``j``; the curved-and-smooth share of
    the area."""
    n = len(p)
    if n < 2 or area.sum() <= 0.0:
        return 0.0
    t1, t2, _l = _edges(p)
    if not len(t1):
        return 0.0
    c = p.mean(axis=1)
    h = np.where(np.abs(unit[:, :1]) < 0.9, [[1.0, 0.0, 0.0]], [[0.0, 0.0, 1.0]])
    e1 = np.cross(unit, h)
    e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
    e2 = np.cross(unit, e1)
    ata, aty, deg = np.zeros((n, 3, 3)), np.zeros((n, 3)), np.zeros(n)
    for i, j in ((t1, t2), (t2, t1)):
        dc, dn = c[j] - c[i], unit[j] - unit[i]
        d1, d2 = np.einsum("ij,ij->i", dc, e1[i]), np.einsum("ij,ij->i", dc, e2[i])
        m1, m2 = np.einsum("ij,ij->i", dn, e1[i]), np.einsum("ij,ij->i", dn, e2[i])
        z = np.zeros_like(d1)
        for r, m in ((np.stack([d1, d2, z], 1), m1), (np.stack([z, d1, d2], 1), m2)):
            np.add.at(ata, i, r[:, :, None] * r[:, None, :])
            np.add.at(aty, i, r * m[:, None])
        np.add.at(deg, i, 1.0)
    s = np.einsum("nij,nj->ni", np.linalg.pinv(ata), aty)        # (a, b, c): [[a, b], [b, c]]
    s[deg < 2] = np.nan
    k = np.abs(0.5 * (s[:, 0] + s[:, 2])) + np.hypot(0.5 * (s[:, 0] - s[:, 2]), s[:, 1])
    big = np.stack([e1, e2], 2)                                   # (n, 3, 2)
    sm = np.stack([np.stack([s[:, 0], s[:, 1]], 1), np.stack([s[:, 1], s[:, 2]], 1)], 1)
    tt = np.einsum("nik,nkl,njl->nij", big, sm, big)              # 3-D shape operators
    norm = np.sqrt((tt ** 2).sum(axis=(1, 2)))
    dv = np.sqrt(((tt[t1] - tt[t2]) ** 2).sum(axis=(1, 2))) / (norm[t1] + norm[t2] + 1e-12)
    ok = np.isfinite(dv)
    tot, cnt = np.zeros(n), np.zeros(n)
    for i in (t1, t2):
        np.add.at(tot, i[ok], dv[ok])
        np.add.at(cnt, i[ok], 1.0)
    change = np.where(cnt > 0, tot / np.maximum(cnt, 1.0), np.inf)
    smooth = np.isfinite(k) & (k * span >= CURVED_SPAN) & (change < SMOOTH_CHANGE)
    return float(area[smooth].sum() / area.sum())


def features(g: _t.Any, vt: np.ndarray, grid: _t.Any) -> dict[str, float]:
    """The five gates' values of a parsed OBJ8 ``g`` (its ``VT`` rows
    ``vt``, ``terrain_model._vt_rows``; its plan grid ``grid``, the
    ``terrain_model._grid``): ``sheet``, ``base_m``, ``top_m``, ``wall``,
    ``right``, ``axis``, ``smooth`` (module doc)."""
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
           "wall": 0.0, "right": 0.0, "axis": 1.0, "smooth": 0.0}
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
        u_up = unit[up] * np.sign(unit[up][:, 1:2])
        out["axis"] = _axis(u_up, a[up])
        span = float(max(np.ptp(p[:, :, 0]), np.ptp(p[:, :, 2])))
        top = _seen(p, p[up], u_up, span)
        out["smooth"] = _smooth_curve(p[up][top], u_up[top], a[up][top], span)
    return out


def failed(f: _t.Mapping[str, float], lift: float = 0.0) -> list[str]:
    """The gates (:data:`GATES`) the values ``f`` (:func:`features`) fail,
    with a row's ``OBJECT_AGL`` ``lift`` (m) added to its heights."""
    ok = {"one_sheet": f["sheet"] >= ROCK_MIN_SHEET,
          "on_ground": (f["base_m"] + lift <= ROCK_BASE_M
                        and f["top_m"] + lift >= ROCK_TOP_M),
          "no_storey_walls": f["wall"] <= ROCK_MAX_WALL,
          "no_right_creases": f["right"] <= ROCK_MAX_RIGHT,
          "not_axis_aligned": f["axis"] <= ROCK_MAX_AXIS,
          "natural_surface": f["smooth"] <= ROCK_MAX_SMOOTH}
    return [k for k in GATES if not ok[k]]
