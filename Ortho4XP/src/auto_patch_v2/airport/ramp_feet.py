"""THE FOOT OF AN OBJECT RAMP — where a pack's sloped road deck comes down
to its own zero, and which way it travels there (issue #669; owner RULINGS
2026-10-14c (5), amending 2026-10-03e in the direction of travel).

The owner, at a terminal's departures ramp: "If we grade terrain up to meet
an object ramp bottom, we should continue road grade until we get back to
raw dem so we don't have a sharp cliff even if there is no road evidence."
This module only FINDS the feet; the run-out is minted where the ground's
level at the foot is known (``classify/ramp_runout``, the last stage).

THE READING, on the member's own top surface (the raster
``airport/sunken_ramp`` judges a ramp on: ``_top_surface``, the highest
solid triangle over each cell centre, ``[placement] sunken_ramp_grid_m``):

* a SLOPED cell: its top surface's gradient (central differences over
  neighbours of the same deck, a step of at most ``sunken_ramp_step_grade``
  x the cell) lies between ``MIN_GRADE`` and that step grade — a road
  deck's grade, never a floor, a wall or a roof's pitch;
* a RAMP: a 4-way component of sloped cells that climbs at least
  ``sunken_ramp_climb_min_m`` and comes down to its own zero (its lowest
  ``T`` within ``[cockpit] visual_m`` of 0 — 10-03e's landing band; a
  roof's eave never does);
* its FOOT: the deck within ``FOOT_SPAN_M`` of its lowest cell; the
  DIRECTION OF TRAVEL off it is that deck's mean downhill gradient; the
  LIP is the farthest point along it of the cells within ``visual_m`` of
  the lowest ``T``, and the WIDTH the deck's extent across it.

Only the window around a member's low sloped TRIANGLES (``WINDOW_M``) is
rastered: a member with no sloped triangle at its zero is never rastered.

Only a member the partition read as a deck (``Member.deck_kind``) or an
elevated plate (``Member.elevated_deck``) is parsed — a ramp is a deck;
the parse is the cost.
"""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import typing as _t

import numpy as np
from shapely.ops import unary_union

__all__ = ["RampFoot", "ramp_feet", "MIN_GRADE", "FOOT_SPAN_M"]

#: the gentlest top-surface grade read as a ramp's slope: under it a deck
#: is a floor (a slab's authoring noise is well under 1 %)
MIN_GRADE = 0.01

#: the reach up the ramp from its foot whose gradient gives the direction
#: of travel (the last few metres of the deck, never its far bend)
FOOT_SPAN_M = 12.0

#: how far up a ramp from its low triangles the raster reads: the climb
#: ``sunken_ramp_climb_min_m`` (1 m) is met inside it at 2.5 %
WINDOW_M = 40.0


@_dc.dataclass(frozen=True)
class RampFoot:
    """One ramp's foot, in the planar frame (metres)."""
    unit: str
    member: str
    #: the LIP — the foot's farthest point along the direction of travel
    lip: tuple[float, float]
    #: the unit vector of travel off the foot (downhill, outward)
    direction: tuple[float, float]
    #: the foot's extent across the direction of travel
    width_m: float
    #: the deck's authored top at its foot (its unit's zero = 0)
    y_foot: float
    #: the ramp's climb from its foot
    climb_m: float


def _gradient(T: np.ndarray, grid: float, step: float):
    """``(gx, gy)`` per cell: central differences over the neighbours whose
    ``T`` is within ``step`` of the cell's (one deck), one-sided at a deck
    edge; NaN where a cell has no such neighbour on an axis."""
    H, W = T.shape
    gx = np.full(T.shape, np.nan)
    gy = np.full(T.shape, np.nan)
    for g, axis in ((gx, 1), (gy, 0)):
        nxt = np.full(T.shape, np.nan)
        prv = np.full(T.shape, np.nan)
        if axis == 1:
            nxt[:, :-1], prv[:, 1:] = T[:, 1:], T[:, :-1]
        else:
            nxt[:-1, :], prv[1:, :] = T[1:, :], T[:-1, :]
        with np.errstate(invalid="ignore"):
            okn = np.abs(nxt - T) <= step
            okp = np.abs(T - prv) <= step
        both = okn & okp
        g[both] = (nxt[both] - prv[both]) / (2.0 * grid)
        one = okn & ~okp
        g[one] = (nxt[one] - T[one]) / grid
        one = okp & ~okn
        g[one] = (T[one] - prv[one]) / grid
    return gx, gy


def _window(tris, climb: float, grade: float, band: float):
    """The box (planar metres) the member's ramp feet can lie in, or None —
    the cheap read before the raster: some SLOPED triangle (a road deck's
    grade) comes down to the member's zero, and the sloped triangles climb
    at least ``climb`` over it.  The box is those low triangles widened by
    :data:`WINDOW_M` (MEASURED OTHH: the raster over every deck member's
    whole footprint cost 29 s, a terminal's interior clutter 11 s of it)."""
    if tris is None or not len(tris):
        return None
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    n = np.cross(b - a, c - a)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = np.hypot(n[:, 0], n[:, 1]) / np.abs(n[:, 2])
    sl = (g >= MIN_GRADE) & (g <= grade) & (0.5 * np.abs(n[:, 2]) >= 0.05)
    if not sl.any():
        return None
    zlo = tris[:, :, 2].min(axis=1)
    low = sl & (np.abs(zlo) <= band)
    if not low.any() or float(tris[sl][:, :, 2].max()) < climb - band:
        return None
    pts = tris[low][:, :, :2].reshape(-1, 2)
    return (float(pts[:, 0].min()) - WINDOW_M, float(pts[:, 1].min()) - WINDOW_M,
            float(pts[:, 0].max()) + WINDOW_M, float(pts[:, 1].max()) + WINDOW_M)


def _member_feet(unit_id, m, origin, to_xy, law_v) -> list[RampFoot]:
    from .sunken_ramp import _components, _member_tris, _poly, _top_surface
    grid, climb, grade, band = law_v
    tris = _member_tris(m, origin, to_xy)
    win = _window(tris, climb, grade, band)
    if win is None:
        return []
    foot = unary_union([q for p in m.parts for r in (p.rings or ())
                        for q in [_poly(r, to_xy)] if q is not None])
    if foot.is_empty:
        return []
    x0, y0, x1, y1 = foot.bounds
    x0, y0, x1, y1 = max(x0, win[0]), max(y0, win[1]), min(x1, win[2]), min(y1, win[3])
    xs = np.arange(x0 + 0.5 * grid, x1, grid)
    ys = np.arange(y0 + 0.5 * grid, y1, grid)
    if len(xs) < 3 or len(ys) < 3:
        return []
    import shapely
    X, Y = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(foot.buffer(grid), X, Y)
    lo_xy, hi_xy = tris[:, :, :2].min(axis=1), tris[:, :, :2].max(axis=1)
    keep = ((hi_xy[:, 0] >= x0) & (lo_xy[:, 0] <= x1)
            & (hi_xy[:, 1] >= y0) & (lo_xy[:, 1] <= y1))
    T = _top_surface(tris[keep], xs, ys, inside)
    gx, gy = _gradient(T, grid, grade * grid)
    with np.errstate(invalid="ignore"):
        s = np.hypot(gx, gy)
        sloped = (~np.isnan(T) & (s >= MIN_GRADE) & (s <= grade))
    out: list[RampFoot] = []
    for cells in _components(sloped, T, grade * grid):
        ii = np.array([a for a, _b in cells])
        jj = np.array([b for _a, b in cells])
        t = T[ii, jj]
        lo = float(t.min())
        if abs(lo) > band or float(t.max()) - lo < climb:
            continue
        # the deck within FOOT_SPAN_M of its lowest cell: a long or curved
        # ramp's other reaches never set its foot's direction or width
        # (MEASURED OTHH: a bus bridge's whole low band read 394 m wide)
        k0 = int(np.argmin(t))
        cx, cy = X[ii, jj], Y[ii, jj]
        near = np.hypot(cx - cx[k0], cy - cy[k0]) <= FOOT_SPAN_M
        dx = -float(np.mean(gx[ii[near], jj[near]]))
        dy = -float(np.mean(gy[ii[near], jj[near]]))
        n = _math.hypot(dx, dy)
        if n < MIN_GRADE:
            continue
        dx, dy = dx / n, dy / n
        px, py = cx[near], cy[near]
        across = -px * dy + py * dx
        f = t[near] <= lo + band
        a = float((px[f] * dx + py[f] * dy).max()) + 0.5 * grid
        mid = 0.5 * (float(across.min()) + float(across.max()))
        lip = (a * dx - mid * dy, a * dy + mid * dx)
        out.append(RampFoot(str(unit_id), str(m.resource), lip, (dx, dy),
                            float(across.max() - across.min()) + grid,
                            round(lo, 3), round(float(t.max()) - lo, 3)))
    return out


_MEMO: list = []


def ramp_feet(airport, law, to_xy) -> tuple[RampFoot, ...]:
    """Every object ramp's foot of ``airport`` (module docstring), memoised
    per partition."""
    part = getattr(airport, "partition", None)
    if part is None or law is None:
        return ()
    for key, val in _MEMO:
        if key is part:
            return val
    from .sunken_ramp import _law
    lv = _law(law)
    feet: list[RampFoot] = []
    if lv[0] > 0.0:
        for u in part.units:
            for m in u.members:
                if not (getattr(m, "deck_kind", "") or getattr(m, "elevated_deck", False)):
                    continue
                org = getattr(m, "origin", None) or u.anchor
                feet.extend(_member_feet(u.id, m, org, to_xy, lv))
    val = tuple(feet)
    _MEMO.append((part, val))
    del _MEMO[:-2]
    return val
