"""THE GROUND'S 2-D LONG-WAVE TREND under a body (spec §8.7, owner RULINGS
2026-09-10ar).

The SIBLING of :mod:`constraints.trend`, one dimension up.  ``trend.py``
fits a moving quadratic along a CHAIN's station frame — a runway ridge
(§21), a taxi centreline (§8.6); this fits a moving quadratic SURFACE over
a body's plan frame, for a body that has no chain at all.  Neither imports
the other: they are two constructions of one idea, and the 1-D one is
untouched by this module's existence.

WHY A SURFACE AND NOT A PLANE.  §8.6 (2) gave an apron body three affine
rows — its mean and its two first moments against the same moments of the
DEM under it — so the body's least-squares PLANE follows the ground's.
Over a body larger than the fit window that plane has no LOCAL REACH: at
LEMD the T4S apron is 439 x 1,242 m and its pit corner sat 1.2 m under its
own DEM while the body's plane was satisfied (RULINGS 2026-09-10ar).  A
plane is the chain's "right mean, no tilt" defect (10t) one order up.

THE GROUND STILL ENTERS PAVEMENT ONLY THROUGH LONG-WAVE TRENDS (08t (1)).
The window is the guard: at ``[design] runway_profile_window_m`` the fit
sees half a kilometre of ground at every query, so it carries the ground's
trend and never its artefacts.  Two bounds make that true rather than
hoped for, both taken straight from :class:`trend.Trend`:

* THE WEIGHT IS TRICUBE (``(1 - |u|^3)^3`` over the window radius).  A
  boxcar makes the fit jump as a sample crosses the window edge, which is
  curvature the K law then has to spend the projection removing (measured
  in 1-D, RULINGS 2026-09-10x).
* THE DEGREE IS BOUNDED BY WHAT THE IN-WINDOW SAMPLES RESOLVE.  A
  quadratic through a handful of near points is INTERPOLATION — the
  per-vertex DEM pull wearing a trend's clothes — so the quadratic is used
  only where the samples actually span at least half the window; below
  that the fit falls back BY DEGREE (plane, then the weighted mean), never
  to an invented value (plan §2).

SAMPLES ARE THE DEM AVERAGED PER CELL, NEVER ONE SAMPLE OF IT.
``trend_of`` averages its samples per distinct station before fitting; the
2-D analogue averages per square cell of ``window / 10``.  Two reasons,
one of them MEASURED:

* A tenth of the window is far below the wavelength the fit can represent,
  so the binning costs the TREND nothing — and it is what makes the fit
  affordable, since a 500 m window puts most of a body inside every
  query's neighbourhood and the un-binned fit is quadratic in the body's
  vertex count.
* ONE SAMPLE PER CELL ALIASES.  An apron's own vertices sit on a lattice
  its edges make (the §8.7 fixture: a 50 m lattice), and ground noise at a
  20 m wavelength read on a 50 m lattice reappears as a 100 m wave at FULL
  amplitude: measured 0.86 m of target movement for 1 m of noise.  The
  cell's value is therefore the production DEM AVERAGED OVER THE CELL
  (``cell_samples``), which is also what "a fit of the production DEM"
  means; the same fixture then moves under 0.05 m.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

__all__ = ["SurfaceTrend", "surface_trend_of", "cell_samples"]

#: The relative singular-value cutoff below which a query's normal
#: equations are treated as singular and the fit falls back by degree.  A
#: numerical conditioning tolerance of the same kind as
#: ``trend.poly_at_zero``'s pivot test, not a law value.
_COND = 1e-9

#: The sample cell, as a fraction of the window (module docstring).  An
#: implementation choice of the same kind as the tricube kernel.
_CELL_FRACTION = 0.1

#: Sub-samples per cell EDGE: a cell's value is the mean of this many
#: squared DEM samples spread evenly over it (module docstring, the
#: aliasing measurement).
_CELL_SUBSAMPLES = 8

#: The largest (queries x samples) working block, so a body of any size
#: costs bounded memory.
_BLOCK = 2_000_000


@_dc.dataclass(frozen=True)
class SurfaceTrend:
    """THE GROUND'S 2-D LONG-WAVE TREND under one body (module docstring).

    ``x`` / ``y`` / ``z`` are the production DEM samples under the body's
    own vertices, averaged per cell.  :meth:`at` is a moving QUADRATIC
    SURFACE least squares over the samples within ``window_m`` of the
    query — the fit's own value AT the query, i.e. the constant term of
    the fit re-centred there.  Vectorised: one call values every vertex of
    the body.
    """

    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    window_m: float

    @property
    def samples(self) -> int:
        return int(self.x.size)

    def at(self, qx: _t.Sequence[float] | np.ndarray,
           qy: _t.Sequence[float] | np.ndarray) -> np.ndarray:
        """The trend at each ``(qx, qy)``; ``nan`` where no sample is in
        the window (the caller then keeps its own fallback)."""
        QX = np.asarray(qx, dtype=float).ravel()
        QY = np.asarray(qy, dtype=float).ravel()
        out = np.full(QX.size, np.nan, dtype=float)
        n_s = self.x.size
        if n_s == 0 or QX.size == 0:
            return out
        step = max(1, int(_BLOCK // max(1, n_s)))
        for lo in range(0, QX.size, step):
            hi = min(QX.size, lo + step)
            out[lo:hi] = self._block(QX[lo:hi], QY[lo:hi])
        return out

    # ── one block of queries ─────────────────────────────────────────
    def _block(self, qx: np.ndarray, qy: np.ndarray) -> np.ndarray:
        w_m = self.window_m
        u = (self.x[None, :] - qx[:, None]) / w_m
        v = (self.y[None, :] - qy[:, None]) / w_m
        d = np.sqrt(u * u + v * v)
        inside = d <= 1.0
        w = np.where(inside, (1.0 - np.minimum(d, 1.0) ** 3) ** 3, 0.0)
        z = np.broadcast_to(self.z[None, :], u.shape)
        n_in = inside.sum(axis=1)
        # the samples' own SPAN inside the window, as the diameter of the
        # disc they actually cover: the 2-D reading of ``Trend.at``'s
        # ``span`` test, and the same half-window bar
        span = 2.0 * np.where(n_in > 0, np.max(np.where(inside, d, 0.0), axis=1), 0.0)
        out = np.full(qx.size, np.nan, dtype=float)
        # QUADRATIC where the samples resolve one, then the PLANE, then
        # the weighted mean — the fallback is BY DEGREE, never invented
        want2 = (n_in >= 6) & (span >= 0.5)
        want1 = (n_in >= 3) & ~want2
        for mask, basis in ((want2, _quad), (want1, _plane)):
            if not mask.any():
                continue
            val = _fit_at_zero(basis(u[mask], v[mask]), w[mask], z[mask])
            sel = np.flatnonzero(mask)
            out[sel] = val
        bad = np.isnan(out) & (n_in > 0)
        if bad.any():
            sw = w[bad].sum(axis=1)
            sw = np.where(sw > 0.0, sw, 1.0)
            out[bad] = (w[bad] * z[bad]).sum(axis=1) / sw
        return out


def _quad(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """``[1, u, v, u^2, u v, v^2]``, the constant term FIRST."""
    one = np.ones_like(u)
    return np.stack([one, u, v, u * u, u * v, v * v], axis=-1)


def _plane(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """``[1, u, v]``, the constant term FIRST."""
    return np.stack([np.ones_like(u), u, v], axis=-1)


def _fit_at_zero(B: np.ndarray, w: np.ndarray, z: np.ndarray) -> np.ndarray:
    """The value AT the query of the WEIGHTED least-squares polynomial whose
    basis is ``B`` (queries x samples x terms) — the constant term, which
    the basis puts first.  ``nan`` where the normal equations are singular,
    so the caller falls back by degree."""
    A = np.einsum("qsi,qs,qsj->qij", B, w, B)
    r = np.einsum("qsi,qs,qs->qi", B, w, z)
    out = np.full(B.shape[0], np.nan, dtype=float)
    s = np.linalg.svd(A, compute_uv=False)
    ok = s[:, -1] > _COND * np.maximum(s[:, 0], np.finfo(float).tiny)
    if ok.any():
        # ``r`` as a STACK OF COLUMNS: numpy 2's ``solve`` reads a
        # trailing (q, k) operand as one matrix, not q vectors
        out[ok] = np.linalg.solve(A[ok], r[ok][..., None])[:, 0, 0]
    return out


def surface_trend_of(samples: _t.Iterable[tuple[float, float, float]],
                     window_m: float) -> SurfaceTrend | None:
    """The trend through ``(x, y, dem)`` samples, averaged per cell of
    ``window_m * _CELL_FRACTION`` (module docstring).  ``None`` where no
    sample carries a value — nothing to fit, so the caller keeps its own
    fallback (never an invented value, plan §2)."""
    pts = np.asarray([(float(a), float(b), float(c)) for a, b, c in samples],
                     dtype=float)
    if pts.size == 0:
        return None
    cell = float(window_m) * _CELL_FRACTION
    if not cell > 0.0:
        return None
    key = np.round(pts[:, :2] / cell).astype(np.int64)
    _u, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    n = int(inv.max()) + 1
    cnt = np.bincount(inv, minlength=n).astype(float)
    sx = np.bincount(inv, weights=pts[:, 0], minlength=n) / cnt
    sy = np.bincount(inv, weights=pts[:, 1], minlength=n) / cnt
    sz = np.bincount(inv, weights=pts[:, 2], minlength=n) / cnt
    return SurfaceTrend(sx, sy, sz, float(window_m))


def cell_samples(xy: np.ndarray, window_m: float,
                 sample: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
                 ) -> list[tuple[float, float, float]]:
    """The fit's samples for a body whose vertices are ``xy``: one per
    occupied CELL of ``window_m * _CELL_FRACTION``, its value the
    production DEM AVERAGED over that cell (module docstring).

    ``sample(xs, ys) -> zs`` is the DEM reader — the caller's, so this
    module still imports nothing of the model.  The cells are the body's
    own (a cell with no vertex in it is not under the body), but WITHIN a
    cell the value no longer depends on where the body's vertices happen
    to fall, which is what kills the aliasing."""
    pts = np.asarray(xy, dtype=float)
    cell = float(window_m) * _CELL_FRACTION
    if pts.size == 0 or not cell > 0.0:
        return []
    key = np.unique(np.round(pts / cell).astype(np.int64), axis=0)
    centres = key.astype(float) * cell
    k = _CELL_SUBSAMPLES
    off = ((np.arange(k, dtype=float) + 0.5) / k - 0.5) * cell
    ox, oy = np.meshgrid(off, off, indexing="ij")
    ox = ox.ravel()[None, :]
    oy = oy.ravel()[None, :]
    X = (centres[:, 0:1] + ox).ravel()
    Y = (centres[:, 1:2] + oy).ravel()
    Z = np.asarray(sample(X, Y), dtype=float).reshape(centres.shape[0], k * k)
    zc = Z.mean(axis=1)
    return [(float(a), float(b), float(c))
            for a, b, c in zip(centres[:, 0], centres[:, 1], zc)]
