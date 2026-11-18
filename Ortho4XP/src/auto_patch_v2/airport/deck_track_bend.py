"""A WARPED DECK'S TRACK BENDS TO FOLLOW THE GROUND BETWEEN ITS NODES,
UNDER THE RAIL CAP (#2144; owner 2026-11-18T00:32Z, RULINGS 2026-11-17t
(3): "As long it's under rail cap, yes").

``airport/deck_profile`` builds the deck's TRACK: its centreline with a
displacement ``D`` at each vertex, flat over every node (a building the
deck enters, a landing end) and straight between two.  :func:`bend`
replaces the straight stretch between two consecutive nodes by the
profile that follows the drawn ground under the track, offset by the
authored pier height -- each ground-contact foot of the warped bodies
asks for ``T = ground - (deck zero + its authored y)``, the ``D`` that
stands it on the ground at its authored height -- subject to:

* every node stays exactly as it was (flat over its stretch, held past
  the outer ones: only the stretches BETWEEN two nodes bend);
* every segment's grade ``|dD/ds| <= grade_max`` (the rail cap);
* THE VERTICAL CURVE: the grade changes by at most ``1/R`` per metre
  along the track (``[deck] track_vertical_radius_m``), a node's stretch
  reading grade 0 -- so the track leaves and enters every node smoothly.

The profile is the L1 fit (``scipy.optimize.linprog``, HiGHS): the sum of
``|D(s_f) - T_f|`` over the feet, plus :data:`HINGE_W` times what a foot
floats past the pier stretch (``[deck] pier_foot_stretch_max_m``, the
part no stretch mends), plus :data:`TIE_W` times ``|D - D_straight|`` at
each vertex (a stretch with no feet keeps the straight grade).  A stretch
too short to curve between its two levels at ``R`` takes the largest of
``R/2``, ``R/4``, ``R/8`` that fits (counted ``tight``); one that fits none
keeps its straight grade (counted ``infeasible``).  Where the ground falls
faster than the cap the track keeps the capped grade; the feet left
floating there are the ground GRADING's (RULINGS 2026-11-17t (3), not
built here).

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["bend", "HINGE_W", "TIE_W"]

#: the weight of a foot's float past the pier stretch, against 1 per
#: metre of plain misfit
HINGE_W = 10.0
#: the weight of a vertex's departure from the straight grade
TIE_W = 0.01
#: the vertical-curve radii a short stretch falls back to, as fractions of R
_TIGHTER = (1.0, 0.5, 0.25, 0.125)
#: a free vertex closer than this to a node's end is dropped (it would
#: read a grade over a sliver), metres
_SLIVER_M = 0.5


def _gaps(knots: _t.Sequence[tuple]) -> list:
    """``[(s_a, s_b)]``: the stretches between two consecutive nodes
    (``knots`` come in ``(lo, d), (hi, d)`` pairs, in order)."""
    return [(float(knots[j][0]), float(knots[j + 1][0]))
            for j in range(1, len(knots) - 2, 2)
            if knots[j + 1][0] - knots[j][0] > 2.0 * _SLIVER_M]


class _Rows:
    """Sparse linear rows over the free vertices and the slack variables;
    a fixed end vertex's term goes to the right-hand side."""

    def __init__(self, col: dict, fixed: np.ndarray) -> None:
        self.col, self.fixed = col, fixed
        self.rows: list[dict] = []
        self.rhs: list[float] = []

    def add(self, terms: _t.Mapping[int, float], rhs: float,
            slack: "_t.Mapping[int, float] | None" = None) -> None:
        row = dict(slack or {})
        for k, w in terms.items():
            if k in self.col:
                row[self.col[k]] = row.get(self.col[k], 0.0) + w
            else:
                rhs -= w * float(self.fixed[k])
        self.rows.append(row)
        self.rhs.append(rhs)

    def matrix(self, nv: int) -> _t.Any:
        from scipy.sparse import coo_matrix
        r = [i for i, row in enumerate(self.rows) for _q in row]
        q = [q for row in self.rows for q in row]
        w = [w for row in self.rows for w in row.values()]
        return coo_matrix((w, (r, q)), shape=(len(self.rows), nv)).tocsr()


def _fit(s: np.ndarray, lin: np.ndarray, fs: np.ndarray, ft: np.ndarray,
         grade_max: float, radius_m: float, stretch_m: float) -> "np.ndarray | None":
    """The fitted ``D`` at stations ``s`` (both ends fixed at ``lin``'s),
    or ``None`` where the constraints cannot all hold."""
    from scipy.optimize import linprog
    n, m = len(s), len(fs)
    nf = n - 2
    col = {k: k - 1 for k in range(1, n - 1)}
    # variables: D (free vertices) | e+ e- h per foot | t+ t- per vertex
    ep, em, hh, tp, tm = nf, nf + m, nf + 2 * m, nf + 3 * m, nf + 3 * m + nf
    nv = nf + 3 * m + 2 * nf
    c = np.concatenate([np.zeros(nf), np.ones(2 * m), np.full(m, HINGE_W),
                        np.full(2 * nf, TIE_W)])
    ub, eq = _Rows(col, lin), _Rows(col, lin)
    ds = np.diff(s)
    for k in range(n - 1):                         # the grade cap
        for sg in (1.0, -1.0):
            ub.add({k + 1: sg, k: -sg}, grade_max * ds[k])
    if radius_m > 0.0:                             # the vertical curve
        for k in range(n):
            terms: dict[int, float] = {}
            if k < n - 1:
                terms[k + 1] = terms.get(k + 1, 0.0) + 1.0 / ds[k]
                terms[k] = terms.get(k, 0.0) - 1.0 / ds[k]
            if k > 0:
                terms[k] = terms.get(k, 0.0) - 1.0 / ds[k - 1]
                terms[k - 1] = terms.get(k - 1, 0.0) + 1.0 / ds[k - 1]
            run = ((ds[k - 1] if k else 0.0) + (ds[k] if k < n - 1 else 0.0)) / 2.0
            for sg in (1.0, -1.0):
                ub.add({q: sg * w for q, w in terms.items()}, run / radius_m)
    at = np.clip(np.searchsorted(s, fs, side="right") - 1, 0, n - 2)
    for f in range(m):                             # the feet
        k = int(at[f])
        t = float((fs[f] - s[k]) / ds[k]) if ds[k] > 0 else 0.0
        terms = {k: 1.0 - t, k + 1: t}
        eq.add(terms, float(ft[f]), {ep + f: -1.0, em + f: 1.0})
        ub.add(terms, float(ft[f]) + stretch_m, {hh + f: -1.0})
    for i in range(nf):                            # the tie to the straight grade
        eq.add({i + 1: 1.0}, float(lin[i + 1]), {tp + i: -1.0, tm + i: 1.0})
    bounds = [(None, None)] * nf + [(0.0, None)] * (3 * m + 2 * nf)
    res = linprog(c, A_ub=ub.matrix(nv), b_ub=np.asarray(ub.rhs), A_eq=eq.matrix(nv),
                  b_eq=np.asarray(eq.rhs), bounds=bounds, method="highs")
    if res.status != 0:
        return None
    out = lin.copy()
    out[1:-1] = res.x[:nf]
    return out


def bend(st: np.ndarray, d: np.ndarray, knots: _t.Sequence[tuple],
         feet: _t.Sequence[tuple], *, grade_max: float, radius_m: float,
         stretch_m: float) -> tuple[np.ndarray, dict]:
    """``(D, report)``: the track's ``D`` at its stations ``st`` (straight
    between nodes in ``d``) bent between each two nodes to the feet
    ``[(station, T)]`` (module doc).  ``report``: the stretches ``bent``,
    those bent on a ``tight`` radius, those ``infeasible``, the largest
    ``moved`` |D - straight|."""
    st = np.asarray(st, float)
    d = np.asarray(d, float)
    out = d.copy()
    rep: dict = {"bent": 0, "tight": 0, "infeasible": 0, "moved": 0.0}
    if len(st) < 3 or not len(feet):
        return out, rep
    fa = np.asarray([f[0] for f in feet], float)
    ta = np.asarray([f[1] for f in feet], float)
    for sa, sb in _gaps(knots):
        inner = np.flatnonzero((st > sa + _SLIVER_M) & (st < sb - _SLIVER_M))
        near = (fa > sa) & (fa < sb)
        if not inner.size or not near.any():
            continue
        s = np.concatenate([[sa], st[inner], [sb]])
        lin = np.interp(s, st, d)
        got = None
        for q in _TIGHTER:
            got = _fit(s, lin, fa[near], ta[near], grade_max, radius_m * q, stretch_m)
            if got is not None:
                rep["tight"] += q < 1.0
                break
        if got is None:
            rep["infeasible"] += 1
            continue
        # every vertex inside the stretch, the slivers by a node too
        out[(st > sa) & (st < sb)] = np.interp(st[(st > sa) & (st < sb)], s, got)
        rep["bent"] += 1
        rep["moved"] = max(rep["moved"], float(np.abs(got - lin).max()))
    rep["moved"] = round(rep["moved"], 3)
    return out, rep
