"""THE SPANS OF ONE HARD DECK, AND WHERE IT LIES AT GRADE (owner RULINGS
2026-11-18i, #2157 KRDU: "my preference would be to drop that long straight
object for taxiway E between the two bridges and use real terrain and
taxiway grading instead").

A pack may author SEVERAL bridges and the pavement between them as ONE
hard-deck object (KRDU ``STH_TML``: taxiway E's two bridges 450 m apart on
a 1.5 % taxiway, 711 m of deck in a flat 119 m world).  Only its SPANS are
bridges; the rest lies at grade on the airport's own pavement.

THE AXIS.  The deck piece's long axis (its minimum rotated rectangle,
``geom/rotated_rect``) through its centroid, from its lowest to its highest
projection.

THE PROFILE.  The bare-earth ground along the axis, every ``step_m``.  A
SPAN is a run of stations standing more than ``drop_m`` (one storey) under
the water-fill level of the profile -- the lower of the highest ground
before and after it: a road, a void or lower ground the deck crosses.  Its
two ABUTMENTS are where the ground climbing out of it on either side turns
gentle (no steeper than ``rise_grade`` per metre): the tops of the cut's
banks, where a bare-earth survey reads the pavement that meets the deck.

THE CUT (:func:`span_pieces`): the piece clipped to each span's strip
across the axis, abutment to abutment.  What lies outside every span is AT
GRADE.

Pure geometry: no airport, pack or resource is named here.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

__all__ = ["SpanCut", "span_cut", "span_pieces"]

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class SpanCut:
    """A deck piece's axis ``a -> b`` (frame xy) and its SPANS ``(s_a,
    s_b)`` in metres from ``a``, in order (module doc)."""

    a: XY
    b: XY
    spans: tuple[tuple[float, float], ...]

    @property
    def length(self) -> float:
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])

    @property
    def unit(self) -> XY:
        L = self.length or 1.0
        return ((self.b[0] - self.a[0]) / L, (self.b[1] - self.a[1]) / L)

    def s_of(self, x: float, y: float) -> float:
        """The station of ``(x, y)`` along the axis (unclipped)."""
        ux, uy = self.unit
        return (x - self.a[0]) * ux + (y - self.a[1]) * uy

    def at_grade(self) -> list[tuple[float, float]]:
        """The stretches ``(s0, s1)`` of the axis outside every span."""
        out, s = [], 0.0
        for sa, sb in self.spans:
            if sa > s:
                out.append((s, sa))
            s = max(s, sb)
        if s < self.length:
            out.append((s, self.length))
        return out


def _profile_spans(s: _t.Sequence[float], g: _t.Sequence[float], drop_m: float,
                  rise_grade: float) -> list[tuple[int, int]]:
    """The spans of a ground profile (module doc) as abutment index pairs
    ``(i_a, i_b)``, in order; overlapping spans merge."""
    s_, g_ = np.asarray(s, float), np.asarray(g, float)
    n = len(g_)
    if n < 3:
        return []
    level = np.minimum(np.maximum.accumulate(g_), np.maximum.accumulate(g_[::-1])[::-1])
    dip = (level - g_) > drop_m
    out: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if not dip[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and dip[j + 1]:
            j += 1
        a = max(i - 1, 0)
        while a > 0 and g_[a - 1] - g_[a] > rise_grade * (s_[a] - s_[a - 1]):
            a -= 1
        b = min(j + 1, n - 1)
        while b < n - 1 and g_[b + 1] - g_[b] > rise_grade * (s_[b + 1] - s_[b]):
            b += 1
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
        i = j + 1
    return out


def span_cut(poly: _t.Any, z_of: _t.Callable[[float, float], "float | None"], *,
             drop_m: float, rise_grade: float, step_m: float = 2.0) -> SpanCut | None:
    """The spans of deck piece ``poly`` (a shapely polygon, frame xy) over
    the ground ``z_of`` (module doc); ``None`` where the ground cannot be
    read along its axis or it holds no span."""
    from .rotated_rect import rectangle_axes
    (ux, uy), long_m, _short = rectangle_axes(poly)
    if long_m <= 2.0 * step_m or drop_m <= 0.0:
        return None
    c = poly.centroid
    pr = [(x - c.x) * ux + (y - c.y) * uy for x, y in poly.exterior.coords]
    lo, hi = min(pr), max(pr)
    a = (c.x + lo * ux, c.y + lo * uy)
    b = (c.x + hi * ux, c.y + hi * uy)
    L = hi - lo
    ss = np.append(np.arange(0.0, L, step_m), L)
    zs = []
    for q in ss.tolist():
        z = z_of(a[0] + q * ux, a[1] + q * uy)
        if z is None or not math.isfinite(float(z)):
            return None
        zs.append(float(z))
    found = _profile_spans(ss, zs, drop_m, rise_grade)
    if not found:
        return None
    return SpanCut(a, b, tuple((float(ss[i]), float(ss[j])) for i, j in found))


def span_pieces(poly: _t.Any, cut: SpanCut) -> list:
    """``poly`` clipped to each span's strip across the axis (module doc),
    in order; a span the piece does not reach is left out."""
    from shapely.geometry import Polygon
    ux, uy = cut.unit
    nx, ny = -uy, ux
    big = 10.0 * (cut.length + 1.0) + 1e4
    out = []
    for sa, sb in cut.spans:
        p0 = (cut.a[0] + sa * ux, cut.a[1] + sa * uy)
        p1 = (cut.a[0] + sb * ux, cut.a[1] + sb * uy)
        strip = Polygon([(p0[0] - big * nx, p0[1] - big * ny),
                         (p1[0] - big * nx, p1[1] - big * ny),
                         (p1[0] + big * nx, p1[1] + big * ny),
                         (p0[0] + big * nx, p0[1] + big * ny)])
        got = poly.intersection(strip)
        parts = [g for g in getattr(got, "geoms", [got])
                 if g.geom_type == "Polygon" and g.area > 1.0]
        if parts:
            out.append(max(parts, key=lambda g: g.area))
    return out
