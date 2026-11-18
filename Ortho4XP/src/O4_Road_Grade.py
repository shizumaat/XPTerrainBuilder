"""THE ROAD ON WRONG GROUND (owner RULINGS 2026-11-18e, LPPD bluff).

"We should only follow terrain where it's able to keep the road under 20%
grade, and shouldn't allow super sharp changes in angle, so we don't have
jagged peaks and valleys" (14:50Z); "the ones near the airport we are
grading" (14:51Z); "railways have to be much lower grade than roads".

Pure numpy / LP pieces, so the core clamp
(``O4_Vector_Utils.neighbourhood_road_profile``) and v2's
``airport/road_profile`` call ONE definition:

* :func:`steep_limits` -- a way's STEEP CAP (the most it follows its DEM:
  a road ``terrain_cap``, 20 %; a railway ``rail_cap``, 1.25 %, RULINGS
  2026-11-14g) and its vertical-curve rate (grade change per metre).
* :func:`steep_windows` -- the DEM-WRONG WINDOWS of one way: every station
  within ``runout_m`` of arclength of a TRIGGER segment (DEM grade over the
  steep cap, in the airport area), outside the existing neighbourhood runs.
  The clamp solves each one like a run with no band.
* :func:`smooth_grade_changes` -- THE VERTICAL CURVE: the profile closest
  (L1, arclength-weighted) to a capped profile that also holds
  ``|g[k+1] - g[k]| <= rate * (ds[k] + ds[k+1]) / 2`` between consecutive
  segments, the cap per segment and the pins; ``None`` when no such
  profile exists (the caller then keeps what it had and counts it).
"""

from __future__ import annotations

import numpy
from scipy import sparse
from scipy.optimize import linprog

__all__ = ["is_rail", "steep_limits", "grade_change_excess",
           "steep_windows", "smooth_grade_changes", "hold_curve"]

#: A grade change this far over the curve's allowance is rounding, not a
#: kink.
CURVE_TOL = 1e-6


def is_rail(way_class):
    """A railway way (the core's class spelling ``railway:<value>``)."""
    return bool(way_class) and str(way_class).startswith("railway:")


def steep_limits(way_class, law):
    """``(steep_cap, grade_change_per_m)`` of one way under ``law``
    (``O4_Cfg_Vars.road_neighbourhood_law``)."""
    if is_rail(way_class):
        return (float(law["rail_cap"]), float(law["rail_grade_change_per_m"]))
    return (float(law["terrain_cap"]), float(law["grade_change_per_m"]))


def _grades(s, z):
    ds = numpy.diff(s)
    dz = numpy.diff(z)
    g = numpy.zeros(len(ds))
    ok = ds > 1e-9
    g[ok] = dz[ok] / ds[ok]
    return g, ds


def grade_change_excess(s, z, rate):
    """The worst ``|Δgrade|`` over the vertical curve's allowance along
    ``(s, z)`` (``<= 0`` where the curve holds)."""
    s = numpy.asarray(s, dtype=numpy.float64)
    z = numpy.asarray(z, dtype=numpy.float64)
    if len(s) < 3:
        return 0.0
    g, ds = _grades(s, z)
    allow = float(rate) * 0.5 * (ds[:-1] + ds[1:])
    return float((numpy.abs(numpy.diff(g)) - allow).max())


def _segment_distance(s, seg_mask):
    """Arclength from each station to the nearest flagged SEGMENT
    (``inf`` when none is) -- a station on a flagged segment is 0."""
    n = len(s)
    on = numpy.zeros(n, dtype=bool)
    on[:-1] |= seg_mask
    on[1:] |= seg_mask
    idx = numpy.nonzero(on)[0]
    if not len(idx):
        return numpy.full(n, numpy.inf)
    pos = numpy.searchsorted(idx, numpy.arange(n))
    lo = idx[numpy.clip(pos - 1, 0, len(idx) - 1)]
    hi = idx[numpy.clip(pos, 0, len(idx) - 1)]
    return numpy.minimum(numpy.abs(s - s[lo]), numpy.abs(s[hi] - s))


def steep_windows(s, dem, in_area, taken, steep_cap, runout_m):
    """The DEM-wrong windows of one way: ``([(i0, i1)], trigger)``, the
    inclusive station ranges -- each a maximal stretch of stations within
    ``runout_m`` of arclength of a trigger segment and outside ``taken``
    (the stations an existing neighbourhood run solves) -- and the
    per-segment trigger mask.

    A TRIGGER is a segment whose DEM grade exceeds ``steep_cap`` with a
    station in ``in_area``, not wholly inside a run (a run holds its own
    steep ground through its ceiling).
    """
    s = numpy.asarray(s, dtype=numpy.float64)
    z = numpy.asarray(dem, dtype=numpy.float64)
    area = numpy.asarray(in_area, dtype=bool)
    taken = numpy.asarray(taken, dtype=bool)
    if len(s) < 2:
        return [], numpy.zeros(0, dtype=bool)
    g, _ds = _grades(s, z)
    trig = (numpy.abs(g) > float(steep_cap)) & (area[:-1] | area[1:]) \
        & ~(taken[:-1] & taken[1:])
    if not trig.any():
        return [], trig
    near = (_segment_distance(s, trig) <= float(runout_m)) & ~taken
    out = []
    i, n = 0, len(s)
    while i < n:
        if not near[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and near[j + 1]:
            j += 1
        out.append((i, j))
        i = j + 1
    return out, trig


def _curve_rows(ds, rate):
    """The vertical curve's rows over ``z`` (n = len(ds) + 1 columns):
    ``(z[k+2]-z[k+1]) ds[k] - (z[k+1]-z[k]) ds[k+1]`` within
    ``rate * ds[k] ds[k+1] (ds[k] + ds[k+1]) / 2``, both signs."""
    m = len(ds) - 1
    if m < 1:
        return None, None
    a, b = ds[:-1], ds[1:]
    k = numpy.arange(m)
    rows = numpy.repeat(numpy.arange(m), 3)
    cols = numpy.column_stack([k + 2, k + 1, k]).ravel()
    vals = numpy.column_stack([a, -a - b, b]).ravel()
    M = sparse.csr_matrix((vals, (rows, cols)), shape=(m, len(ds) + 1))
    lim = rate * a * b * 0.5 * (a + b) + 1e-9
    return M, lim


def smooth_grade_changes(s, target, caps, rate, pin_idx=(), pin_val=(),
                         lead=None, tail=None, lower=None, upper=None):
    """THE VERTICAL CURVE (RULINGS 2026-11-18e): the profile closest to
    ``target`` (sum of ``|z - target|`` weighted by each station's share of
    arclength) that holds the per-segment ``caps``, the grade-change
    ``rate`` (per metre) and ``z[pin_idx] == pin_val``.

    ``lead`` / ``tail`` -- ``(ds, z)`` of a FIXED station just before the
    first / after the last station: the curve is held across that junction
    too, so the profile meets the ground beyond it without a kink.
    ``lower`` / ``upper`` -- per-station bounds on ``z`` (``±inf`` free).

    Returns the profile, or ``None`` when the constraints admit none.
    """
    s = numpy.asarray(s, dtype=numpy.float64)
    t = numpy.asarray(target, dtype=numpy.float64)
    n = len(s)
    if n < 2:
        return t.copy()
    caps = numpy.broadcast_to(numpy.asarray(caps, dtype=numpy.float64),
                              (n - 1,))
    lead_ok = lead is not None and float(lead[0]) > 1e-9
    tail_ok = tail is not None and float(tail[0]) > 1e-9
    # the fixed outside stations join the chain as pinned variables
    ss = s.copy()
    tt = t.copy()
    cc = numpy.array(caps, dtype=numpy.float64)
    off = 0
    pins = [(int(i), float(v)) for i, v in zip(pin_idx, pin_val, strict=True)
            if 0 <= int(i) < n]
    if lead_ok:
        ss = numpy.concatenate(([s[0] - float(lead[0])], ss))
        tt = numpy.concatenate(([float(lead[1])], tt))
        cc = numpy.concatenate(([numpy.inf], cc))
        off = 1
        pins = [(i + 1, v) for i, v in pins] + [(0, float(lead[1]))]
    if tail_ok:
        ss = numpy.concatenate((ss, [s[-1] + float(tail[0])]))
        tt = numpy.concatenate((tt, [float(tail[1])]))
        cc = numpy.concatenate((cc, [numpy.inf]))
        pins = pins + [(len(ss) - 1, float(tail[1]))]
    N = len(ss)
    ds = numpy.diff(ss)
    w = numpy.zeros(N)
    w[:-1] += 0.5 * ds
    w[1:] += 0.5 * ds
    w += 1e-3
    I = sparse.identity(N, format="csr")
    D = sparse.diags([-numpy.ones(N - 1), numpy.ones(N - 1)], [0, 1],
                     shape=(N - 1, N), format="csr")
    fin = numpy.isfinite(cc)
    blocks = [sparse.hstack([I, -I]), sparse.hstack([-I, -I])]
    rhs = [tt, -tt]
    if fin.any():
        Df = D[fin]
        Z = sparse.csr_matrix((int(fin.sum()), N))
        lim = cc[fin] * ds[fin] + 1e-9
        blocks += [sparse.hstack([Df, Z]), sparse.hstack([-Df, Z])]
        rhs += [lim, lim]
    M, lim = _curve_rows(ds, float(rate))
    if M is not None:
        Z = sparse.csr_matrix((M.shape[0], N))
        blocks += [sparse.hstack([M, Z]), sparse.hstack([-M, Z])]
        rhs += [lim, lim]
    A = sparse.vstack(blocks, format="csr")
    lb = numpy.full(2 * N, -numpy.inf)
    ub = numpy.full(2 * N, numpy.inf)
    lb[N:] = 0.0
    if lower is not None:
        lb[off:off + n] = numpy.asarray(lower, dtype=numpy.float64)
    if upper is not None:
        ub[off:off + n] = numpy.asarray(upper, dtype=numpy.float64)
    for i, v in pins:
        lb[i] = ub[i] = v
    c = numpy.concatenate([numpy.zeros(N), w])
    res = linprog(c, A_ub=A, b_ub=numpy.concatenate(rhs),
                  bounds=numpy.column_stack([lb, ub]), method="highs")
    if res.status != 0 or res.x is None:
        return None
    z = numpy.asarray(res.x[:N], dtype=numpy.float64)
    return z[off:off + n]


def hold_curve(s, prof, dem, judged, caps_of, cap_eff, cap_top, rate,
               pin_idx=(), pin_val=(), lead=None, tail=None, allow=None):
    """THE VERTICAL CURVE on one run or window: ``(profile, cap, curve)``.

    Where the capped ``prof`` (with the fixed ``lead`` / ``tail`` stations
    beside it) changes grade faster than ``rate`` per metre, the profile
    becomes the closest one that does not (:func:`smooth_grade_changes`),
    standing no more than ``allow`` off ``dem`` at the ``judged`` stations
    -- under ``caps_of(cap_eff)`` first; the curve needs room the gentlest
    cap may not leave, so then under ``caps_of(cap_top)``, then past
    ``allow``, then with the junctions let go.  ``curve`` is ``None`` (nothing to do), ``"held"``,
    ``"free_ends"`` (held inside, the junctions let go) or ``"infeasible"``
    (``prof`` stands).
    """
    s = numpy.asarray(s, dtype=numpy.float64)
    ss, zz = s, numpy.asarray(prof, dtype=numpy.float64)
    if lead is not None:
        ss = numpy.concatenate(([s[0] - lead[0]], ss))
        zz = numpy.concatenate(([lead[1]], zz))
    if tail is not None:
        ss = numpy.concatenate((ss, [s[-1] + tail[0]]))
        zz = numpy.concatenate((zz, [tail[1]]))
    if grade_change_excess(ss, zz, rate) <= CURVE_TOL:
        return prof, cap_eff, None
    lower = upper = None
    if allow is not None:
        dem = numpy.asarray(dem, dtype=numpy.float64)
        a = numpy.where(judged, float(allow) + 1e-6, numpy.inf)
        lower, upper = dem - a, dem + a
    ends_given = lead is not None or tail is not None
    tried = set()
    for c, ends, bounded in ((cap_eff, True, True), (cap_top, True, True),
                             (cap_top, True, False), (cap_top, False, True),
                             (cap_top, False, False)):
        ends = ends and ends_given
        bounded = bounded and lower is not None
        if (c, ends, bounded) in tried:
            continue
        tried.add((c, ends, bounded))
        sm = smooth_grade_changes(s, prof, caps_of(c), rate, pin_idx,
                                  pin_val, lead if ends else None,
                                  tail if ends else None,
                                  lower if bounded else None,
                                  upper if bounded else None)
        if sm is not None:
            return sm, c, ("held" if ends or not ends_given else "free_ends")
    return prof, cap_eff, "infeasible"
