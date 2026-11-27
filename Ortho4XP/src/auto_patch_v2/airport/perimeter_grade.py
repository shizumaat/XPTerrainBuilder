"""OUR GROUND IS GRADED TO EVERY SEATED GROUP'S PERIMETER (owner RULINGS
2026-11-25m (2)/(3), 25n (3)/(4); spec
``docs/specs/underside-height-map-20261125.md`` §3 G3/G5/G6, census rows
U21/U22) -- the tile raster's half; the patch's half is
``pipeline/perimeter_pass``.

THE GRADE (:func:`perimeter_grade`) on one ``terrain_fill.Raster``: every
FREE posting (never the tile's edge, never an airport patch: airside is
king) within ``unit_perimeter.REACH_M`` of a perimeter station takes the
field ``G'`` (``unit_perimeter.field``: raised or lowered into the
station's interval within the raster's shoulder ``W``, feathered to the
reach -- a wall-like step becomes a bank, 25n (3)); then every posting over
a below-grade interior is CUT to its ceiling (``unit_perimeter.
cut_ceiling``, 25m (3)), never raised.

THE JUDGE (:func:`judge`, spec G4): each station read on the raster after
the grade -- ``patch`` where all four postings round it are frozen (the
patch's surface is the patch pass's to judge), ``boundary`` where some are
(a station beside the patch: the raster cannot serve it alone, counted
apart), ``far`` (25f: left as authored), else FREE; a free station more
than ``unit_perimeter.GAP_M`` off its interval is ``over``.  A free
posting under an OPEN interior still standing more than ``SERVED_M`` over
its ceiling is ``uncut``; an open interior cell no posting stands on is
``subposting`` (smaller than the raster draws).

Pure numpy / scipy on one raster; nothing names a pack, an object or an
airport."""
from __future__ import annotations

import typing as _t

import numpy as np

from . import terrain_fill as _tf
from . import unit_perimeter as _up

__all__ = ["perimeter_grade", "judge"]


def _box(pers: _t.Sequence[_up.Perimeter], to_ll: _t.Callable, pad_m: float
         ) -> "tuple[float, float, float, float] | None":
    xs = [a for p in pers for a in (p.e, p.plan_e) if len(a)]
    ys = [a for p in pers for a in (p.n, p.plan_n) if len(a)]
    if not xs:
        return None
    x, y = np.concatenate(xs), np.concatenate(ys)
    lo, la = to_ll(np.r_[x.min() - pad_m, x.max() + pad_m],
                   np.r_[y.min() - pad_m, y.max() + pad_m])
    return float(np.min(lo)), float(np.min(la)), float(np.max(lo)), float(np.max(la))


def perimeter_grade(raster: "_tf.Raster", to_xy: _t.Callable, to_ll: _t.Callable,
                    pers: _t.Sequence[_up.Perimeter]) -> dict[str, int]:
    """THE GRADE (module doc) on ``raster`` (changed in place); ``to_xy``
    ``(lon, lat) -> (x, y)`` / ``to_ll`` ``(x, y) -> (lon, lat)`` the
    perimeters' frame (``terrain_cut.projector``'s convention).  ``{"postings", "raised", "lowered",
    "cut"}``."""
    rep = {"postings": 0, "raised": 0, "lowered": 0, "cut": 0}
    box = _box(pers, to_ll, _up.REACH_M)
    if box is None:
        return rep
    rows, cols, lons, lats = raster.window(*box)
    if not len(rows):
        return rep
    x, y = (np.asarray(a, float) for a in to_xy(lons, lats))
    old = raster.alt[rows, cols].astype(float)
    ix = _up.Index(pers)
    new, which, _d = _up.field(pers, x, y, old, raster.shoulder_m(), index=ix)
    graded = new.copy()
    new = np.minimum(new, _up.cut_ceiling(pers, x, y))
    moved = np.abs(new - old) > 1e-3
    raster.alt[rows[moved], cols[moved]] = new[moved]
    rep["postings"] = int((which >= 0).sum())
    rep["raised"] = int((moved & (new > old)).sum())
    rep["lowered"] = int((moved & (new < old) & (graded < old - 1e-3)).sum())
    rep["cut"] = int((moved & (new < graded - 1e-3)).sum())
    return rep


def _frozen_corners(raster: "_tf.Raster", lons: np.ndarray, lats: np.ndarray
                    ) -> np.ndarray:
    """Per point how many of the four postings round it are frozen."""
    ny, nx = raster.alt.shape
    fx = (np.asarray(lons, float) - raster.lon0) / raster.dlon
    fy = (raster.lat0 - np.asarray(lats, float)) / raster.dlat
    i = np.clip(np.floor(fx).astype(np.int64), 0, nx - 2)
    j = np.clip(np.floor(fy).astype(np.int64), 0, ny - 2)
    n = np.zeros(len(i), int)
    if raster.frozen is None:
        return n
    for di, dj in ((0, 0), (1, 0), (0, 1), (1, 1)):
        c, r = i + di, j + dj
        n += np.asarray(raster.frozen(r, c, raster.lon0 + c * raster.dlon,
                                      raster.lat0 - r * raster.dlat), bool).astype(int)
    return n


def _interior_postings(raster: "_tf.Raster", to_xy: _t.Callable, to_ll: _t.Callable,
                       p: _up.Perimeter) -> dict[str, int]:
    """The raster postings under ``p``'s OPEN interiors: ``in_patch`` (frozen),
    ``cut`` (free), ``uncut`` (free and still more than ``SERVED_M`` over
    their ceiling), and ``subposting`` -- open interior cells no posting
    stands on (smaller than the raster draws: the mesher's limit, G6)."""
    from scipy.spatial import cKDTree
    out = {"in_patch": 0, "cut": 0, "uncut": 0, "subposting": 0}
    op = p.cut_open
    if not op.any():
        return out
    ce, cn, cz = p.cut_e[op], p.cut_n[op], p.cut_z[op]
    lo, la = to_ll(np.r_[ce.min() - 2 * p.step, ce.max() + 2 * p.step],
                   np.r_[cn.min() - 2 * p.step, cn.max() + 2 * p.step])
    frozen_before = raster.frozen
    raster.frozen = None
    rows, cols, lons, lats = raster.window(float(lo.min()), float(la.min()),
                                           float(lo.max()), float(la.max()))
    raster.frozen = frozen_before
    if not len(rows):
        out["subposting"] = int(len(cz))
        return out
    x, y = to_xy(lons, lats)
    d, k = cKDTree(np.c_[ce, cn]).query(np.c_[x, y])
    on = d <= 0.5 * p.step * np.sqrt(2.0)
    fz = (np.asarray(frozen_before(rows, cols, lons, lats), bool) if frozen_before is not None
          else np.zeros(len(rows), bool))
    alt = raster.alt[rows, cols].astype(float)
    out["in_patch"] = int((on & fz).sum())
    out["cut"] = int((on & ~fz).sum())
    out["uncut"] = int((on & ~fz & (alt > cz[k] + _tf.SERVED_M)).sum())
    hit = np.zeros(len(cz), bool)
    hit[k[on]] = True
    out["subposting"] = int((~hit).sum())
    return out


def judge(raster: "_tf.Raster", to_xy: _t.Callable, to_ll: _t.Callable,
          pers: _t.Sequence[_up.Perimeter]) -> list[dict[str, _t.Any]]:
    """THE JUDGE (module doc): one row per perimeter -- its station counts
    by place and the free stations ``over`` with their p5/p95 offset."""
    out = []
    for p in pers:
        row: dict[str, _t.Any] = {"unit": p.unit, "row": p.row, "z0": round(p.z0, 3),
                                  "why": p.why, "stations": int(len(p.e))}
        if len(p.e):
            lons, lats = (np.asarray(a, float) for a in to_ll(p.e, p.n))
            fz = _frozen_corners(raster, lons, lats)
            off = _up.off_interval(raster.sample(lons, lats), p.lo, p.hi)
            free = (fz == 0) & ~p.far & np.isfinite(off)
            over = free & (np.abs(off) > _up.GAP_M)
            row.update(patch=int((fz == 4).sum()), boundary=int(((fz > 0) & (fz < 4)).sum()),
                       far=int(p.far.sum()), free=int(free.sum()), over=int(over.sum()))
            if over.any():
                row["p5"], row["p95"] = (round(float(v), 2)
                                         for v in np.percentile(off[over], [5, 95]))
        if len(p.cut_z):
            row["interior_cells"] = {"open": int(p.cut_open.sum()),
                                     "roofed": int((~p.cut_open).sum())}
            row.update(_interior_postings(raster, to_xy, to_ll, p))
        out.append(row)
    return out
