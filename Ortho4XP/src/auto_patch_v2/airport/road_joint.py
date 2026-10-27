"""THE JUNCTION JOINT: A SIDE STREET LEAVES THE MAIN ROAD'S KERB AND REACHES
ITS OWN PROFILE OVER A CAR-SMOOTH TRANSITION (owner RULINGS 2026-10-27f,
Q186; sized by 2026-10-27s, Q197; issue #1254).

27f: across a junction mouth between two DIFFERENT public roads the pair is
the side street's longitudinal grade into the main road's kerb
(``constraints/roads.road_pair_reading``), "so long as the side road
connection to the main road is smooth enough for cars".  27s gives the
numbers (town street, about 30 km/h; ``rulesets.toml [common]``):

* a grade change up to ``road_joint_free_grade_change`` (8 %) at the joint
  needs no curve;
* a bigger change is spread over at least ``road_joint_k_m_per_pct`` (3 m)
  of road per 1 % (``vertical_curve_k_grade_unit``) of change.

MEASURED before this module (LGAV, -1276 into -1190 at 37.95121, 23.98649):
each road's target is its own centreline value across its section, so on
the 16-21 % hillside the side street's kerb corner stood 1.77 m over the
main road's kerb 3.0 m away (a 0.60 m ``mid_edge_step``) and the street ran
18 %, 36 % over 4 m, 16 %.

THE RULE.  The side street is the road whose centreline ENDS on the main
road's (:func:`_side_end`); a crossing (neither ends) is left alone.  The
JOINT is the side street's station farthest from that end that still pairs
with the main road; its level is the main road's
kerb there (the median target of the paired main-road vertices).  From the
joint the side street's profile ``P(u)`` (``u`` = route distance away from
the main road):

* leaves at the main road's own grade along the side street's direction,
  changed at the joint by at most the free change toward the street's own
  grade;
* changes grade at no more than ``1 % / K`` per metre after that;
* reaches the street's own target (the core's clamp ``T``) in value and
  grade at ``u_end`` — the shortest such transition (the slope runs up to
  a peak and back, a plateau at ``cap_ceiling`` where the peak would be
  steeper), :func:`transition`;
* stations between the joint and the route's end stand at the joint level.

The profile is a TARGET (``PlanarMap.road_ramp_z``), one value per (route,
station), so the section stays level (§37 (8)) and the public-road release
(``constraints/public_road_release``) widens the side street's rows to it.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..law import Law
from ..model.planar import PlanarMap, is_osm_ribbon_ref

__all__ = ["junction_joints"]


def transition(z0: float, g0: float, line_z0: float, g1: float, free: float,
               rate: float, ceiling: float) -> tuple[float, _t.Callable[[float], float]] | None:
    """The shortest profile from ``(u = 0, z0)`` onto the line
    ``line_z0 + g1 u`` (value AND grade), leaving at a grade within ``free``
    of ``g0`` and changing grade at no more than ``rate`` per metre, never
    steeper than ``ceiling``.  ``(u_end, P)``, or ``None`` when no grade
    under the ceiling reaches the line."""
    s0 = min(max(g1, g0 - free), g0 + free)        # the free break, toward g1
    r0 = s0 - g1                                   # slope relative to the line
    d = line_z0 - z0                               # height still to gain
    if abs(r0) < 1e-12 and abs(d) < 1e-9:
        return 0.0, lambda u: line_z0 + g1 * u
    # the relative slope runs r0 -> rp -> 0 at ``rate``; its area is d
    sign = 1.0 if d + r0 * abs(r0) / (2.0 * rate) >= 0.0 else -1.0
    rp = sign * math.sqrt(max(rate * sign * d + 0.5 * r0 * r0, 0.0))
    lim = (ceiling - g1) if sign > 0 else (-ceiling - g1)
    plateau = 0.0
    if abs(rp) > abs(lim):
        if lim * sign <= 0.0:
            return None
        area = (lim * lim - r0 * r0) / (2.0 * rate) * sign + lim * lim / (2.0 * rate) * sign
        plateau = (d - area) / lim
        rp = lim
    u1 = abs(rp - r0) / rate                       # r0 -> rp
    u2 = u1 + plateau                              # the plateau
    u3 = u2 + abs(rp) / rate                       # rp -> 0
    a1 = math.copysign(rate, rp - r0) if u1 > 0 else 0.0
    a3 = -math.copysign(rate, rp) if rp else 0.0

    def rel(u: float) -> float:
        """height relative to the line (starts at -d, ends at 0)."""
        if u <= u1:
            return -d + r0 * u + 0.5 * a1 * u * u
        h1 = -d + r0 * u1 + 0.5 * a1 * u1 * u1
        if u <= u2:
            return h1 + rp * (u - u1)
        h2 = h1 + rp * (u2 - u1)
        w = min(u, u3) - u2
        return h2 + rp * w + 0.5 * a3 * w * w

    return u3, (lambda u: line_z0 + g1 * u + rel(min(max(u, 0.0), u3)))


def _side_end(wa, wb, sa: float, sb: float, lat: float) -> int | None:
    """Which END of way ``wa`` (0 / 1) makes it the SIDE STREET of the pair
    ``(sa on wa, sb on wb)``: that end of ``wa``'s centreline stands within
    ``2 lat`` of ``wb``'s (the street runs into the main road), ``sa`` is
    within ``4 lat`` of it along the street, and ``wb`` does not end there
    itself (a corner, not a T).  ``None`` otherwise (a crossing, or ``wb``
    is the side street)."""
    if wa is None or wb is None:
        return None
    from shapely.geometry import Point
    s_lo, s_hi = float(wa.s[0]), float(wa.s[-1])
    end = 1 if (s_hi - sa) <= (sa - s_lo) else 0
    s_end = s_hi if end == 1 else s_lo
    xy = wa.xy[-1] if end == 1 else wa.xy[0]
    if abs(s_end - sa) > 4.0 * lat:
        return None
    if wb.line.distance(Point(float(xy[0]), float(xy[1]))) > 2.0 * lat:
        return None
    if min(sb - float(wb.s[0]), float(wb.s[-1]) - sb) <= lat:
        return None
    return end


def _size(w, sj: float, sgn: float, zk: float, g0: float, avail: float,
          law3: tuple[float, float, float]):
    """``(u_end, P, g1)``: :func:`transition` onto the street's own clamp
    ``T`` read as the chord over the transition it needs (iterated, since
    the length sets the chord), or ``None`` when the street is shorter."""
    def street(u: float) -> float:
        return float(w.at(sj + sgn * u))
    u_end, got, g1 = 30.0, None, 0.0
    for _it in range(6):
        ue = min(max(u_end, 1.0), avail)
        g1 = (street(ue) - street(0.0)) / ue if ue > 0 else 0.0
        got = transition(zk, g0, street(0.0), g1, *law3)
        if got is None:
            return None
        done = abs(got[0] - u_end) < 0.5
        u_end = got[0]
        if done:
            break
    if got is None or u_end > avail:
        return None
    return u_end, got[1], g1


def _grade(w, s: float, d: float = 5.0) -> float:
    lo, hi = max(float(w.s[0]), s - d), min(float(w.s[-1]), s + d)
    return (float(w.at(hi)) - float(w.at(lo))) / (hi - lo) if hi > lo else 0.0


def _tangent(w, s: float) -> np.ndarray:
    ln = w.line
    a = ln.interpolate(max(0.0, s - 2.0))
    b = ln.interpolate(min(ln.length, s + 2.0))
    v = np.array([b.x - a.x, b.y - a.y])
    n = float(np.hypot(*v))
    return v / n if n > 0 else v


def _mouths(pm: PlanarMap, frame, targets, route_ways, public, lat: float
            ) -> dict[tuple[int, int], list[tuple[int, int]]]:
    """``(side-street route, end) -> [(street vertex, main-road vertex)]``:
    every pair within ``lat`` of two DIFFERENT public roads where the first
    is the side street (:func:`_side_end`)."""
    from scipy.spatial import cKDTree
    vs = [v for v in targets if v in frame and int(frame[v][0]) in public]
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    if len(vs) < 2:
        return groups
    tree = cKDTree([pm.vertices[v].xy for v in vs])
    for i, j in sorted(tree.query_pairs(lat)):
        for a, b in ((vs[i], vs[j]), (vs[j], vs[i])):
            ra, rb = int(frame[a][0]), int(frame[b][0])
            if ra == rb or public[ra] == public[rb]:
                continue
            end_a = _side_end(route_ways.get(ra), route_ways.get(rb),
                              float(frame[a][1]), float(frame[b][1]), lat)
            if end_a is not None:
                groups.setdefault((ra, end_a), []).append((a, b))
    return groups


def _street_vertices(pm: PlanarMap, road_ref: str) -> set[int]:
    """Every ring vertex of the ribbon faces of the OSM way ``road_ref``
    (``osm:<id>``; the mint spells its faces ``<feed>:<id>[#k]``)."""
    wid = str(road_ref).split(":", 1)[-1]
    out: set[int] = set()
    for f in pm.faces.values():
        if is_osm_ribbon_ref(f.ref) and str(f.ref).split("#", 1)[0].split(":", 1)[-1] == wid:
            for ring in (f.ring, *f.holes):
                out.update(pm.ring_vertices(ring))
    return out


def _route_level(frame, targets, r: int):
    """``s -> target`` along route ``r``, interpolated over its vertices'
    stations (the target is one value per station, §37 (8))."""
    pts = sorted((float(f[1]), float(targets[v])) for v, f in frame.items()
                 if int(f[0]) == r and v in targets)
    ss = np.array([p[0] for p in pts]) if pts else np.zeros(0)
    zz = np.array([p[1] for p in pts]) if pts else np.zeros(0)
    return lambda s_: float(np.interp(s_, ss, zz)) if len(ss) else math.nan


def junction_joints(pm: PlanarMap, law: Law,
                    frame: _t.Mapping[int, tuple],
                    targets: _t.Mapping[int, float],
                    route_ways: _t.Mapping[int, _t.Any],
                    public: _t.Mapping[int, str]
                    ) -> tuple[dict[int, float], dict[int, tuple], dict[int, str],
                               dict[str, _t.Any]]:
    """``(targets, frame, roads, report)`` with every side street re-sized from its
    junction joint (module docstring).  The street's MOUTH — its vertices
    from the joint to its end, the ones lying along the main road's kerb —
    moves onto the main road's frame and takes the main road's level there,
    so the street meets the kerb with no step and its mouth is the main
    road's surface, not a cross-section of its own.  ``roads`` names the
    public road of every vertex of a sized joint (``PlanarMap.
    road_junction_road``)."""
    rep: dict[str, _t.Any] = {"joints": 0, "too_short": 0, "longest_m": 0.0,
                              "worst_change": 0.0, "mouth_vertices": 0,
                              "street_vertices_reframed": 0, "sites": []}
    out, fr = dict(targets), dict(frame)
    roads: dict[int, str] = {}           # a sized joint's vertex -> its road
    lat = float(law.tables.emit.road_contact.pair_lateral_m)
    common = law.tables.common
    law3 = (float(common.road_joint_free_grade_change),
            float(common.vertical_curve_k_grade_unit) / float(common.road_joint_k_m_per_pct),
            float(law.tables.emit.road_profile.cap_ceiling))
    from shapely.geometry import Point
    for (r, end), pairs in sorted(_mouths(pm, frame, targets, route_ways, public, lat).items()):
        w = route_ways.get(r)
        b0 = pairs[0][1]
        rb = int(frame[b0][0])
        wb = route_ways.get(rb)
        if w is None or wb is None:
            continue
        sgn = -1.0 if end == 1 else 1.0          # u grows away from the end
        sj = (min if end == 1 else max)(float(frame[a][1]) for a, _b in pairs)
        main = _route_level(frame, targets, rb)
        c = w.line.interpolate(sj)
        sb = float(wb.line.project(c))
        zk = main(sb)
        g0 = _grade(wb, sb) * float(np.dot(_tangent(wb, sb), sgn * _tangent(w, sj)))
        avail = (sj - float(w.s[0])) if end == 1 else (float(w.s[-1]) - sj)
        sized = _size(w, sj, sgn, zk, g0, avail, law3)
        if sized is None or math.isnan(zk):
            rep["too_short"] += 1
            continue
        u_end, prof, g1 = sized
        for v, f in frame.items():
            if int(f[0]) != r or v not in out:
                continue
            u = sgn * (float(f[1]) - sj)
            if u <= 1e-6:                        # the mouth: the main road's kerb
                p_ = Point(*pm.vertices[v].xy)
                s_m = float(wb.line.project(p_))
                q, tg = wb.line.interpolate(s_m), _tangent(wb, s_m)
                lat_m = float(tg[0] * (p_.y - q.y) - tg[1] * (p_.x - q.x))
                fr[v] = (rb, s_m, lat_m)
                out[v] = main(s_m)
                roads[v] = public[rb]
                rep["mouth_vertices"] += 1
            elif u <= u_end:
                out[v] = prof(u)
                roads[v] = public[r]
        for _a, b in pairs:
            roads[b] = public[rb]
        # the street's OWN faces: a ring vertex the frame handed to another
        # route (LGAV -1276's kerb v22038 read the track -1258 that carries
        # on past it, 2 m over the transition across one section) takes the
        # street's frame and its transition too
        for v in _street_vertices(pm, public[r]):
            if v not in out or int(fr.get(v, (r,))[0]) == r or v in roads:
                continue
            p_ = Point(*pm.vertices[v].xy)
            s_v = float(w.line.project(p_))
            u = sgn * (s_v - sj)
            if 0.0 < u <= u_end:
                q, tg = w.line.interpolate(s_v), _tangent(w, s_v)
                fr[v] = (r, s_v, float(tg[0] * (p_.y - q.y) - tg[1] * (p_.x - q.x)))
                out[v] = prof(u)
                roads[v] = public[r]
                rep["street_vertices_reframed"] += 1
        rep["joints"] += 1
        rep["longest_m"] = max(rep["longest_m"], round(u_end, 1))
        g_lv = (prof(1e-3) - zk) / 1e-3
        rep["worst_change"] = max(rep["worst_change"], round(abs(g_lv - g0), 4))
        rep["sites"].append({"route": r, "road": public[r], "joint_station": round(sj, 2),
                             "kerb_m": round(zk, 3), "main_grade": round(g0, 4),
                             "street_grade": round(g1, 4), "length_m": round(u_end, 1)})
    return out, fr, roads, rep
