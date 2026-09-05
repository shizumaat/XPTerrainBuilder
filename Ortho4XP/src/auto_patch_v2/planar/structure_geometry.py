"""THE RAMP / WALL-BAND GEOMETRY of a tunnel structure (M4; split out of
``planar/structures.py`` for lane v2tunnelobj so that file stays under
its line budget — no behaviour moved with it).

One corridor = a RAMP polygon (the carriageway, ``half`` each side of
the axis), ``gap`` of unowned ground, and a WALL BAND ``bw`` wide on
both sides, closed across the mouth (s = 0) by an END CAP — the U of
2026-08-30 / 2026-09-01c.  Every vertex is born ON the identity grid,
the band's rounded AWAY from the ramp (``snap_out``) so the gap
survives the arrangement's snap-rounding.

Lane v2tunnelobj (RULINGS 2026-09-05k-1) adds two shapes for the object
corridors, both the SAME faces and refs: ``capped=False`` leaves s = 0
open (an open+open corridor is two capless halves meeting at its
midpoint — the halves' mid-line vertices coincide, born from one axis
point) and ``far_capped=True`` closes the far end too (a corridor
closed at both ends: the band is an O with the ramp in its hole).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from ..model.frame import XY

__all__ = ["RampGeometry", "geometry", "normals", "offset_line", "snap", "snap_out"]


@_dc.dataclass(frozen=True)
class RampGeometry:
    """The stations' axis points and normals, the ramp's left / right
    edges, the ramp, the wall band (a Polygon, or a MultiPolygon of two
    side bands when capless), the outer footprint, and the cap points
    (inner / outer, ``[left, centre, right]``; empty when capless) and
    the far cap's (``[right, centre, left]``; empty unless far-capped)."""

    axis: list[XY]
    normals: list[XY]
    left: list[XY]
    right: list[XY]
    ramp: Polygon
    wall: Polygon | MultiPolygon
    outer: Polygon
    cap_in: list[XY]
    cap_out: list[XY]
    far_in: list[XY]
    far_out: list[XY]
    #: The band's inner / outer edges per station (round 2: an object
    #: corridor's ``wall_path`` is their middle; empty for round-1 callers).
    left_in: list[XY] = _dc.field(default_factory=list)
    left_out: list[XY] = _dc.field(default_factory=list)
    right_in: list[XY] = _dc.field(default_factory=list)
    right_out: list[XY] = _dc.field(default_factory=list)


def normals(axis: _t.Sequence[XY]) -> list[XY]:
    """Left-hand unit normal per axis point (averaged at joints)."""
    n = len(axis)
    out: list[XY] = []
    for i in range(n):
        a = axis[max(0, i - 1)]
        b = axis[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        out.append((-dy / L, dx / L))
    return out


def offset_line(axis: _t.Sequence[XY], nrm: _t.Sequence[XY], off: float) -> list[XY]:
    return [(p[0] + nv[0] * off, p[1] + nv[1] * off) for p, nv in zip(axis, nrm)]


def snap(p: XY, grid: float) -> XY:
    """The nearest identity-grid point."""
    return (round(p[0] / grid) * grid, round(p[1] / grid) * grid)


def snap_out(p: XY, origin: XY, grid: float) -> XY:
    """``p`` snapped to the identity grid AWAY from ``origin`` on both
    axes, so a designed stand-off (the 0.6 m gap, 09-01e "never ON a
    weld tolerance") survives the arrangement's snap-rounding: two
    points 0.85 m apart both round to ONE 0.5 m grid point (measured
    OTHH: the ramp's mouth corner and the cap's inner corner merged into
    vertex 14058 — an IIS of its two pins)."""
    out = []
    for c, o in zip(p, origin):
        k = c / grid
        if c > o + 1e-9:
            out.append(math.ceil(k - 1e-9) * grid)
        elif c < o - 1e-9:
            out.append(math.floor(k + 1e-9) * grid)
        else:
            out.append(round(k) * grid)
    return (out[0], out[1])


def _offset_out(axis: _t.Sequence[XY], nrm: _t.Sequence[XY], off: "float | _t.Sequence[float]",
                base: _t.Sequence[XY], grid: float) -> list[XY]:
    """``axis`` offset by ``off`` along ``nrm`` (one value, or one per
    point), each point snapped away from its ``base`` point."""
    offs = [off] * len(axis) if isinstance(off, (int, float)) else list(off)
    return [snap_out((p[0] + nv[0] * o, p[1] + nv[1] * o), b, grid)
            for p, nv, b, o in zip(axis, nrm, base, offs)]


def _clear(p: XY, direction: XY, ramp: Polygon, gap: float, grid: float) -> XY:
    """``p`` moved along ``direction`` by grid steps (snapped away from
    where it came from) until it stands ≥ ``gap`` off the ramp."""
    L = math.hypot(direction[0], direction[1]) or 1.0
    ux, uy = direction[0] / L, direction[1] / L
    q = p
    for _k in range(6):
        if ramp.distance(Point(q)) >= gap - 1e-9:
            return q
        q = snap_out((q[0] + ux * grid, q[1] + uy * grid), q, grid)
    return q


def _cap(m: XY, lin: XY, rin: XY, lbase: XY, rbase: XY, d: XY, nv: XY, ramp: Polygon,
         gap: float, bw: float, grid: float) -> tuple[list[XY], list[XY]]:
    """An end cap across the axis point ``m`` in direction ``d`` (away
    from the ramp): inner points ``[+nv corner, centre, −nv corner]``
    cleared off the ramp by the gap, and their outer points ``bw`` on."""
    dirs = [(d[0] + nv[0], d[1] + nv[1]), d, (d[0] - nv[0], d[1] - nv[1])]
    cin = [_clear(snap_out((lin[0] + d[0] * gap, lin[1] + d[1] * gap), lbase, grid),
                  dirs[0], ramp, gap, grid),
           _clear(snap_out((m[0] + d[0] * gap, m[1] + d[1] * gap), m, grid), d, ramp, gap, grid),
           _clear(snap_out((rin[0] + d[0] * gap, rin[1] + d[1] * gap), rbase, grid),
                  dirs[2], ramp, gap, grid)]
    cout = [snap_out((c[0] + dd[0] * bw, c[1] + dd[1] * bw), c, grid) for c, dd in zip(cin, dirs)]
    return cin, cout


def _geometry_at(axis_fn, ss: list[float], half: float, gap: float, bw: float, inward: XY,
                 grid: float, capped: bool, far_capped: bool, half_fn=None, bw_fn=None,
                 cap_bw: float | None = None, far_bw: float | None = None
                 ) -> RampGeometry | None:
    """The ramp, the wall band and the outer footprint for stations
    ``ss`` (see the module doc).  ``None`` when a bend tighter than the
    offsets folds a ring over itself (a buffer would repair it with
    off-grid vertices — the merge class).  ``half_fn(s) -> (left,
    right)`` / ``bw_fn(s) -> (left, right)`` give a corridor whose ramp
    edges and band widths vary by station (a wall object's inner faces
    and its walls' thickness, round 2); ``cap_bw`` / ``far_bw`` the end
    caps' thickness (an object's end wall)."""
    axis = [axis_fn(s) for s in ss]
    nrm = normals(axis)
    hl = [half_fn(s)[0] for s in ss] if half_fn is not None else [half] * len(ss)
    hr = [half_fn(s)[1] for s in ss] if half_fn is not None else [half] * len(ss)
    bl = [bw_fn(s)[0] for s in ss] if bw_fn is not None else [bw] * len(ss)
    br = [bw_fn(s)[1] for s in ss] if bw_fn is not None else [bw] * len(ss)
    left = [snap((p[0] + nv[0] * h, p[1] + nv[1] * h), grid) for p, nv, h in zip(axis, nrm, hl)]
    right = [snap((p[0] - nv[0] * h, p[1] - nv[1] * h), grid) for p, nv, h in zip(axis, nrm, hr)]
    ramp = Polygon(left + list(reversed(right)))
    if not ramp.is_valid or ramp.area < 1.0:
        return None
    # the band's inner points: offset, snapped away, then PUSHED one grid
    # step further along their direction until each clears the ramp by
    # the gap (a component-wise outward snap can shorten a diagonal
    # offset's projection; the law is the plan distance to the ramp)
    left_in = [_clear(p, d, ramp, gap, grid) for p, d in
               zip(_offset_out(left, nrm, gap, left, grid), nrm)]
    right_in = [_clear(p, (-d[0], -d[1]), ramp, gap, grid) for p, d in
                zip(_offset_out(right, nrm, -gap, right, grid), nrm)]
    left_out = _offset_out(left_in, nrm, bl, left_in, grid)
    right_out = _offset_out(right_in, nrm, [-b for b in br], right_in, grid)
    cap_in: list[XY] = []
    cap_out: list[XY] = []
    far_in: list[XY] = []
    far_out: list[XY] = []
    if capped:
        # the cap: left corner, CENTRE (the mouth wall node, 09-03b), right corner
        cap_in, cap_out = _cap(axis[0], left_in[0], right_in[0], left[0], right[0], inward,
                               nrm[0], ramp, gap, cap_bw if cap_bw is not None else bw, grid)
    if far_capped:
        a, b = axis[-2], axis[-1]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        outward = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        # in ring order after the right band's top: right corner, centre, left corner
        far_in, far_out = _cap(axis[-1], right_in[-1], left_in[-1], right[-1], left[-1], outward,
                               (-nrm[-1][0], -nrm[-1][1]), ramp, gap,
                               far_bw if far_bw is not None else bw, grid)
    outer_ring = (list(reversed(left_out)) + list(cap_out) + list(right_out) + list(far_out))
    if capped and not far_capped:
        # the U: back along the inner edge
        ring = (outer_ring + list(reversed(right_in)) + list(reversed(cap_in)) + list(left_in))
        wall: Polygon | MultiPolygon = Polygon(ring)
    elif capped and far_capped:
        # the O: the band with the ramp in its hole
        inner_ring = (list(left_in) + list(reversed(far_in)) + list(reversed(right_in))
                      + list(reversed(cap_in)))
        wall = Polygon(outer_ring, [inner_ring])
    else:
        # capless: two side bands (a far cap alone is the same two bands
        # joined across the far end — one polygon)
        if far_capped:
            # a U facing the other way: right outer mouth→far, the far
            # cap, left outer far→mouth, left inner mouth→far, the far
            # cap's inner, right inner far→mouth (closes across the
            # band's open end at the mouth)
            wall = Polygon(list(right_out) + list(far_out) + list(reversed(left_out))
                           + list(left_in) + list(reversed(far_in)) + list(reversed(right_in)))
        else:
            wall = MultiPolygon([Polygon(list(left_in) + list(reversed(left_out))),
                                 Polygon(list(right_in) + list(reversed(right_out)))])
    outer = Polygon(outer_ring)
    if not wall.is_valid or not outer.is_valid:
        return None
    return RampGeometry(axis, nrm, left, right, ramp, wall, outer, cap_in, cap_out,
                        far_in, far_out, left_in, left_out, right_in, right_out)


def geometry(axis_fn, ss: list[float], half: float, gap: float, bw: float, inward: XY,
             grid: float, capped: bool = True, far_capped: bool = False, half_fn=None,
             bw_fn=None, cap_bw: float | None = None, far_bw: float | None = None
             ) -> RampGeometry | None:
    """:func:`_geometry_at` with the gap widened by grid steps (at most
    three) until the ramp and the wall rings clear each other by the
    law's gap everywhere — the snapped rings are jagged by up to half a
    grid step, so an edge can stand closer than its vertices do.  THE GAP
    IS THE LAW: a bend that cannot be cleared this way is refused, never
    welded."""
    for k in range(4):
        g = _geometry_at(axis_fn, ss, half, gap + k * grid, bw, inward, grid, capped, far_capped,
                         half_fn, bw_fn, cap_bw, far_bw)
        if g is None:
            return None
        if g.ramp.distance(g.wall) >= gap - 1e-6:
            return g
    return None
