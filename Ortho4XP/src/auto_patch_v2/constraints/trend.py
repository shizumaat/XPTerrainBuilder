"""THE GROUND'S LONG-WAVE TREND along a chain (spec §21.2 (1), §8.6).

ONE construction, TWO consumers.  ``constraints/runway_chord.py`` fits it
along a runway's crown ridge (RULINGS 2026-09-10x); ``constraints/
taxi_trend.py`` fits it along every taxi centreline chain (owner RULINGS
2026-09-10v (1), "taxiways are designed like runways").  The helper lived
inside ``runway_chord`` until the second consumer arrived; it is here so
neither module imports the other and the dependency direction holds (M0
§1: ``constraints`` imports ``law`` and ``model`` only).

:class:`Trend` is a moving QUADRATIC least-squares fit of the production
DEM along a chain's own station frame, TRICUBE-weighted over a window;
:func:`shift_through` is the LINEAR correction that carries it through
the chain's pins.  An affine correction leaves the fit's SECOND
DERIVATIVE untouched, so a pin costs the profile no curvature at all —
the window alone bounds it.
"""
from __future__ import annotations

import bisect as _bisect
import dataclasses as _dc
import typing as _t

__all__ = ["Trend", "poly_at_zero", "trend_of", "shift_through"]

@_dc.dataclass(frozen=True)
class Trend:
    """THE GROUND'S LONG-WAVE TREND along one runway's ridge (spec §21.2
    (1), module docstring).

    ``s`` / ``z`` are the PRODUCTION DEM samples under that runway's own
    ridge vertices, in the chord's station frame, ascending and unique.
    :meth:`at` is a moving QUADRATIC least squares over the samples within
    ``+/- window_m`` — the fit's own value at the query station, i.e. the
    constant term of the fit re-centred there.

    THE WEIGHT IS TAPERED (tricube, ``(1 - |u|^3)^3`` over the window; the
    spec says "moving quadratic least squares over +/- the window" and
    leaves the kernel open — this is the choice, and the measurement that
    made it).  A UNIFORM (boxcar) weight makes the fit jump as a sample
    enters or leaves the window: measured on the §21.4 sag twin at a 12 m
    ridge spacing, the target's largest second difference is 0.0357 m
    boxcar against 0.0154 m tricube, and on the 30 m / 20 m noise twin
    2.97 m against 0.029 m — a boxcar target carries curvature the K law
    (0.0047 m over a 12 m station) has to spend the projection to remove,
    which is exactly the "long gentle curves" the ruling asks for being
    thrown away at the fit.  Tricube is the standard moving-least-squares
    kernel and costs one multiply per sample.

    Degenerate windows fall back by DEGREE, never to an invented value: two
    samples give the line through them, one gives itself, none gives
    ``None`` (and the caller then keeps the straight chord).  ``u`` is
    scaled by the window before the normal equations are formed, so the
    3x3 stays conditioned on a 1 km ridge."""

    s: tuple[float, ...]
    z: tuple[float, ...]
    window_m: float
    _memo: dict = _dc.field(default_factory=dict, compare=False, repr=False)

    def at(self, q: float) -> float | None:
        key = round(q, 3)
        if key in self._memo:
            return self._memo[key]
        lo = _bisect.bisect_left(self.s, q - self.window_m)
        hi = _bisect.bisect_right(self.s, q + self.window_m)
        n = hi - lo
        val: float | None
        if n <= 0:
            val = None
        elif n == 1:
            val = self.z[lo]
        else:
            us = [(self.s[i] - q) / self.window_m for i in range(lo, hi)]
            zs = [self.z[i] for i in range(lo, hi)]
            ws = [(1.0 - abs(u) ** 3) ** 3 for u in us]
            # THE DEGREE IS BOUNDED BY WHAT THE SAMPLES CAN RESOLVE.  A
            # quadratic is a LONG-WAVE statement only when the samples
            # actually span the window: through four points 40 m apart it
            # is near-exact INTERPOLATION, i.e. the per-vertex DEM pull
            # 08t (1) removed, wearing a trend's clothes.  Measured at
            # HECA (lane v2taxidatum round 2): the taxi family's chains
            # are mostly short junctions, and an unbounded degree raised
            # `junction` undulation 8.4 % over control against a +5 % bar;
            # bounded, the same build reads +1.6 %.  A runway ridge always
            # spans more than half a 500 m window, so §21's own fit is
            # untouched (its twins assert it).  The HALF-WINDOW is an
            # implementation choice of the same kind as the tricube
            # kernel (RULINGS 2026-09-10x), not a law value.
            span = self.s[hi - 1] - self.s[lo]
            deg = 2 if (n >= 3 and span >= 0.5 * self.window_m) else 1
            val = poly_at_zero(us, zs, ws, deg)
            if val is None:
                val = poly_at_zero(us, zs, ws, 1)
            if val is None:
                sw = sum(ws) or float(len(zs))
                val = sum(w * z for w, z in zip(ws, zs)) / sw
        self._memo[key] = val
        return val


def poly_at_zero(us: _t.Sequence[float], zs: _t.Sequence[float],
                  ws: _t.Sequence[float], degree: int) -> float | None:
    """The value AT u = 0 of the WEIGHTED least-squares polynomial of
    ``degree`` through ``(us, zs)`` — the constant term.  ``None`` when the
    normal equations are singular (every sample at one station, or a degree
    the sample count cannot carry), so the caller falls back by degree."""
    k = degree + 1
    if len(us) < k:
        return None
    m = [0.0] * (2 * degree + 1)
    b = [0.0] * k
    for u, zv, w in zip(us, zs, ws):
        p = w
        for j in range(2 * degree + 1):
            m[j] += p
            if j < k:
                b[j] += p * zv
            p *= u
    a = [[m[i + j] for j in range(k)] + [b[i]] for i in range(k)]
    for col in range(k):                      # Gaussian elimination, partial pivot
        piv = max(range(col, k), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        for r in range(k):
            if r == col:
                continue
            f = a[r][col] / a[col][col]
            for c in range(col, k + 1):
                a[r][c] -= f * a[col][c]
    return a[0][k] / a[0][0]




def trend_of(samples: _t.Iterable[tuple[float, float]], window_m: float,
             *, min_samples: int = 3) -> Trend | None:
    """The trend through ``(station, dem)`` samples — averaged per distinct
    station, ascending.  ``None`` where fewer than ``min_samples`` distinct
    stations carry a sample: nothing to fit a quadratic to, so the caller
    keeps its own fallback (never an invented value, plan §2)."""
    by_s: dict[float, list[float]] = {}
    for s, z in samples:
        by_s.setdefault(round(float(s), 3), []).append(float(z))
    if len(by_s) < min_samples:
        return None
    ss = sorted(by_s)
    return Trend(tuple(ss), tuple(sum(by_s[s]) / len(by_s[s]) for s in ss),
                 float(window_m))


def shift_through(trend: Trend, pins: _t.Sequence[tuple[float, float]]
                  ) -> _t.Callable[[float], float | None]:
    """The trend SHIFTED LINEARLY through ``pins`` (``(station, z)``), the
    §21.2 (1) correction generalised to a chain with any number of pins.

    No pin: the trend stands unshifted (owner RULINGS 2026-09-10v (1), "for
    a chain with no pins the fit is unshifted").  One pin: a CONSTANT shift
    puts the trend exactly through it.  Two or more: the correction is
    PIECEWISE LINEAR in station between consecutive pins and constant
    outside the outermost pair — the same affine-per-interval shape §21's
    two-pin correction has, so the fit's second derivative is untouched
    everywhere except at a pin station itself.

    The returned callable is ``None`` where the trend's own window is empty
    (the caller then keeps its fallback)."""
    ps = sorted((float(s), float(z)) for s, z in pins)
    deltas: list[tuple[float, float]] = []
    for s, z in ps:
        t = trend.at(s)
        if t is not None:
            deltas.append((s, z - t))

    def at(q: float) -> float | None:
        base = trend.at(q)
        if base is None:
            return None
        if not deltas:
            return base
        if len(deltas) == 1 or q <= deltas[0][0]:
            return base + deltas[0][1]
        if q >= deltas[-1][0]:
            return base + deltas[-1][1]
        k = _bisect.bisect_right([d[0] for d in deltas], q) - 1
        (sa, da), (sb, db) = deltas[k], deltas[k + 1]
        f = 0.0 if sb <= sa else (q - sa) / (sb - sa)
        return base + da + (db - da) * f

    return at
