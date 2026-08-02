"""The station walk of the LATERAL-CONTIGUITY grade law — ONE instrument,
both readers.

The law itself (which cap a cross-section takes, how stations group into
segments) lives in :mod:`auto_patch.grade_law`, which is deliberately
geometry-library free.  This module is the geometric half: given a road
polygon and the pavement around it, WHERE the stations are and WHAT the
laterally-contiguous cross-section holds at each of them.

It exists as its own module because the emitter
(``groundside.apply_lateral_contiguity_law``) and the validator
(``tools/check_grade._check_lateral_contiguity``) must census the IDENTICAL
population.  Two independent walks — even from the same law — would be two
instruments describing different station sets, and the validator would flag
stations the emitter never saw (measured: SPLP way -10009 survived a walk
the emitter had made with its own axis convention).  With one walker, every
station the validator can flag is a station the emitter capped.

Frame: whatever planar metre frame the caller's polygons live in (the
builder's layout frame for the emitter, ``check_grade``'s anchor frame for
the validator).  The law is frame-independent — it reads roles and metres.
"""
from __future__ import annotations

import math
from typing import Optional

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Point

from .grade_law import lateral_contiguity_cap

_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

__all__ = [
    "STATION_STEP_M", "PROBE_M", "GAP_TOL_M", "MIN_MEMBER_M", "ROAD_ROLES",
    "long_axis", "cross_section_roles", "station_caps",
]

# Station spacing and cross-section probe: the SAME numbers
# ``groundside.free_road_subsegments`` / ``_svc_contiguous_width`` use,
# because this is the same measurement — one sample every 5 m, 60 m of probe
# each side.
STATION_STEP_M = 5.0
PROBE_M = 60.0
# A "real gap" for the closure.  Adjacency is a LITERAL shared boundary in
# the sliced arrangement (owner: "never proximity"), so the run breaks at
# anything wider than emitted-coordinate noise.
GAP_TOL_M = 0.05
# A cross-section class must occupy at least this much of the run to count —
# a probe grazing the corner of a neighbour is not a shared flank.  (The
# station's OWN shape always counts, whatever its width.)
MIN_MEMBER_M = 0.5
ROAD_ROLES = frozenset({"service_road", "service_junction"})


def long_axis(poly):
    """``((ux, uy), length, (mx, my))`` — the unit long axis, length and
    mid-point of ``poly``'s minimum-area rectangle, or ``None``.

    The road's own direction.  A blobby service JUNCTION has no natural
    axis; the minimum-area rectangle still gives both readers the SAME
    answer, which is what the law needs (a shared convention), and the
    cross-section is then measured across the shape's short dimension —
    exactly where a laterally-touching neighbour lies.
    """
    try:
        pts = list(poly.exterior.coords)[:-1]
    except _GEOM_EXC:
        return None
    if len(pts) < 3:
        return None
    best = None
    for i in range(len(pts)):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % len(pts)]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        ux, uy = dx / L, dy / L
        us = [p[0] * ux + p[1] * uy for p in pts]
        vs = [-p[0] * uy + p[1] * ux for p in pts]
        w = max(us) - min(us)
        h = max(vs) - min(vs)
        if best is not None and w * h >= best[0]:
            continue
        umid = 0.5 * (max(us) + min(us))
        vmid = 0.5 * (max(vs) + min(vs))
        mid = (umid * ux - vmid * uy, umid * uy + vmid * ux)
        best = ((w * h), (ux, uy), w, mid) if w >= h else \
               ((w * h), (-uy, ux), h, mid)
    if best is None or best[2] <= 0.0:
        return None
    return best[1], best[2], best[3]


def cross_section_roles(px, py, nx, ny, tree, polys, roles, own_index):
    """The roles present in the laterally-contiguous paved cross-section at
    one station, or ``None`` when the station is not on pavement.

    Casts the perpendicular ``(nx, ny)`` through ``(px, py)``, cuts it
    against every pavement polygon, merges the pieces that TOUCH (gap ≤
    ``GAP_TOL_M``) into runs, and returns the role set of the run containing
    the station.  Any real gap ends the run — the owner's "genuinely unpaved
    ground" test — and the run never continues past the probe, so a road
    dying INTO an apron (the apron is ahead of the station, not beside it)
    can never pick the apron up.
    """
    cut = LineString([(px - nx * PROBE_M, py - ny * PROBE_M),
                      (px + nx * PROBE_M, py + ny * PROBE_M)])
    segs = []
    for k in tree.query(cut):
        k = int(k)
        try:
            inter = cut.intersection(polys[k])
        except _GEOM_EXC:
            continue
        if inter.is_empty:
            continue
        parts = ([inter] if inter.geom_type == "LineString"
                 else [g for g in getattr(inter, "geoms", ())
                       if g.geom_type == "LineString"])
        for g in parts:
            ts = [((x - px) * nx + (y - py) * ny) for x, y in g.coords]
            if ts:
                segs.append((min(ts), max(ts), k))
    if not segs:
        return None
    segs.sort()
    runs = []
    cur = [segs[0][0], segs[0][1], [segs[0]]]
    for s in segs[1:]:
        if s[0] <= cur[1] + GAP_TOL_M:
            cur[1] = max(cur[1], s[1])
            cur[2].append(s)
        else:
            runs.append(cur)
            cur = [s[0], s[1], [s]]
    runs.append(cur)
    for lo, hi, members in runs:
        if not (lo - GAP_TOL_M <= 0.0 <= hi + GAP_TOL_M):
            continue
        return {roles[k] for t0, t1, k in members
                if k == own_index or (t1 - t0) >= MIN_MEMBER_M}
    return None


def station_caps(poly, tree, polys, roles, own_index, keepout=None):
    """``(stations, caps)`` for one road shape — THE census both readers run.

    ``stations[i]`` is ``(x, y)`` or ``None``; ``caps[i]`` is the station's
    lawful cap (``grade_law.lateral_contiguity_cap`` of its cross-section) or
    ``None`` where there is no verdict: off the shape, inside ``keepout``
    (the runway-strip footprint — clause 5, whose own law supersedes there),
    or an unmeasurable cross-section.

    Stations sit at interval CENTRES, never on the road's END FACE: a road
    butting an apron SHARES that face, and a probe cast exactly along it
    reads the apron's whole span as "beside" the road.  That is the end
    connection the owner excluded from the closure, so the law never samples
    there.
    """
    axis = long_axis(poly)
    if axis is None:
        return [], []
    (ux, uy), length, mid = axis
    nx, ny = -uy, ux
    n_st = max(1, int(length / STATION_STEP_M))
    stations = []
    caps: list[Optional[float]] = []
    for k in range(n_st):
        t = -0.5 * length + length * (k + 0.5) / n_st
        px, py = mid[0] + ux * t, mid[1] + uy * t
        pt = Point(px, py)
        try:
            inside = poly.contains(pt)
        except _GEOM_EXC:
            inside = False
        if not inside:
            stations.append(None)
            caps.append(None)
            continue
        if keepout is not None:
            try:
                if keepout.covers(pt):
                    stations.append((px, py))
                    caps.append(None)
                    continue
            except _GEOM_EXC:
                pass
        present = cross_section_roles(px, py, nx, ny, tree, polys, roles,
                                      own_index)
        stations.append((px, py))
        caps.append(lateral_contiguity_cap(present) if present else None)
    return stations, caps


def station_normal(poly):
    """The unit NORMAL of ``poly``'s long axis (the probe direction), or
    ``None`` — the direction the segment cuts are made along."""
    axis = long_axis(poly)
    if axis is None:
        return None
    (ux, uy), _length, _mid = axis
    return (-uy, ux)
