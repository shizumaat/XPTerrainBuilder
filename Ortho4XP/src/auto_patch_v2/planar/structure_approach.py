"""THE BORES, MOUTHS AND APPROACHES of the OSM tunnel ways (M4; split out
of ``planar/structures.py`` for lane v2tunnelobj2 so that file stays
under its line budget — no behaviour moved with it): the way predicates,
the carriageway width, bore chains, the approach centreline outward
from a mouth, the mouths themselves and 31h's dual-carriageway merge.
Law ``structures.toml [tunnel]``; see ``planar/structures.py``'s module
doc for the model.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString

from ..law import Law
from ..model.airport import OsmWay
from ..model.frame import XY
from ..airport.deck_signature import is_bridge_way, is_tunnel_way

__all__ = ["carriageway_width_m", "Bore", "Mouth", "chains", "approach", "resample",
           "mouths", "merge_duals", "unit", "is_tunnel", "is_bridge", "MAX_HOPS",
           "PARALLEL_COS", "NODE_TOL"]

#: Two OSM node coordinates closer than this (frame metres) are one node.
NODE_TOL = 0.05
#: Approach ways are followed at most this many hops from the mouth.
MAX_HOPS = 6
#: Two directions within 30° are parallel (31h's dual test; the approach kink test).
PARALLEL_COS = math.cos(math.radians(30))


# ── tags ─────────────────────────────────────────────────────────────────

def is_tunnel(w: OsmWay) -> bool:
    """One predicate with ``airport/deck_signature.is_tunnel_way``."""
    return is_tunnel_way(w.tags)


def is_bridge(w: OsmWay) -> bool:
    """One predicate with the deck signature's (``airport/deck_signature``)."""
    return is_bridge_way(w.tags)


def carriageway_width_m(tags: _t.Mapping[str, str], law: Law) -> float:
    """The way's stated ``width``, else ``lanes × lane_width_m`` (a
    railway counts as ``default_lanes``)."""
    tn = law.tables.structures.tunnel
    w = tags.get("width")
    if w:
        try:
            return max(1.0, float(w.replace("m", "").strip()))
        except ValueError:
            pass
    lanes = tags.get("lanes")
    try:
        n = int(lanes) if lanes else tn.default_lanes
    except ValueError:
        n = tn.default_lanes
    return max(1, n) * tn.lane_width_m


# ── bores (chains of tunnel ways) ────────────────────────────────────────

def _key(p: XY) -> tuple[int, int]:
    return (int(round(p[0] / NODE_TOL)), int(round(p[1] / NODE_TOL)))


@_dc.dataclass
class Bore:
    ways: list[OsmWay]
    points: list[XY]          # the chain, in order

    @property
    def line(self) -> LineString:
        return LineString(self.points)


def chains(ways: list[OsmWay]) -> list[Bore]:
    """Join tunnel ways end to end where exactly two of them meet."""
    ends: dict[tuple[int, int], list[int]] = {}
    for i, w in enumerate(ways):
        ends.setdefault(_key(w.points[0]), []).append(i)
        ends.setdefault(_key(w.points[-1]), []).append(i)
    used = [False] * len(ways)
    out: list[Bore] = []
    for i, w in enumerate(ways):
        if used[i]:
            continue
        used[i] = True
        pts = list(w.points)
        members = [w]
        for direction in (1, -1):
            while True:
                end = pts[-1] if direction == 1 else pts[0]
                cands = [j for j in ends.get(_key(end), ()) if not used[j]]
                if len(cands) != 1 or len(ends.get(_key(end), ())) != 2:
                    break
                j = cands[0]
                used[j] = True
                nxt = list(ways[j].points)
                if _key(nxt[-1]) == _key(end):
                    nxt.reverse()
                if direction == 1:
                    pts.extend(nxt[1:])
                else:
                    pts = list(reversed(nxt[1:])) + pts
                members.append(ways[j])
        out.append(Bore(members, pts))
    return out


# ── the approach ─────────────────────────────────────────────────────────

def approach(mouth: XY, inward: XY, ways: list[OsmWay], reach_m: float
              ) -> list[XY]:
    """The centreline OUTWARD from the mouth: non-tunnel ways joined at
    the mouth node, followed up to ``reach_m``; a straight extension of
    the bore's own end direction where no way continues."""
    idx: dict[tuple[int, int], list[tuple[int, bool]]] = {}
    for i, w in enumerate(ways):
        if is_tunnel(w) or ("highway" not in w.tags and "railway" not in w.tags):
            continue
        idx.setdefault(_key(w.points[0]), []).append((i, True))
        idx.setdefault(_key(w.points[-1]), []).append((i, False))
    path: list[XY] = [mouth]
    cur = mouth
    length = 0.0
    seen: set[int] = set()
    for _hop in range(MAX_HOPS):
        best = None
        for i, forward in idx.get(_key(cur), ()):
            if i in seen:
                continue
            pts = list(ways[i].points) if forward else list(reversed(ways[i].points))
            # outward: the way must leave the mouth AWAY from the bore
            dx, dy = pts[min(1, len(pts) - 1)][0] - cur[0], pts[min(1, len(pts) - 1)][1] - cur[1]
            if dx * inward[0] + dy * inward[1] > 0.0 and len(path) == 1:
                continue
            best = (i, pts)
            break
        if best is None:
            break
        i, pts = best
        seen.add(i)
        for p in pts[1:]:
            length += math.hypot(p[0] - cur[0], p[1] - cur[1])
            path.append(p)
            cur = p
            if length >= reach_m:
                return path
    if length < reach_m:
        # straight on, along the last direction (or away from the bore)
        if len(path) >= 2:
            ax, ay = path[-1][0] - path[-2][0], path[-1][1] - path[-2][1]
        else:
            ax, ay = -inward[0], -inward[1]
        L = math.hypot(ax, ay) or 1.0
        path.append((cur[0] + ax / L * (reach_m - length + 1.0),
                     cur[1] + ay / L * (reach_m - length + 1.0)))
    return path


def resample(path: _t.Sequence[XY], ss: _t.Sequence[float]) -> list[XY]:
    ln = LineString(path)
    out = []
    for s in ss:
        p = ln.interpolate(min(s, ln.length))
        out.append((p.x, p.y))
    return out


# ── the mouths ───────────────────────────────────────────────────────────

@_dc.dataclass
class Mouth:
    bore: Bore
    xy: XY
    inward: XY               # unit vector INTO the bore
    width_m: float
    approach: list[XY]
    ways: tuple[int, ...]


def unit(a: XY, b: XY) -> XY:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def mouths(bores: list[Bore], osm: list[OsmWay], law: Law, reach_m: float
            ) -> list[Mouth]:
    out: list[Mouth] = []
    for b in bores:
        width = max(carriageway_width_m(w.tags, law) for w in b.ways)
        wids = tuple(w.id for w in b.ways)
        for end, nxt in ((b.points[0], b.points[1]), (b.points[-1], b.points[-2])):
            inward = unit(end, nxt)
            out.append(Mouth(b, end, inward, width,
                              approach(end, inward, osm, reach_m), wids))
    return out


def _parallel(a: Mouth, b: Mouth, sep_max: float) -> bool:
    """31h's test: mouths within the dual separation, approaches parallel
    and holding that separation 50 m out."""
    if b.bore is a.bore:
        return False
    d0 = math.hypot(a.xy[0] - b.xy[0], a.xy[1] - b.xy[1])
    if d0 > sep_max:
        return False
    if a.inward[0] * b.inward[0] + a.inward[1] * b.inward[1] < PARALLEL_COS:
        return False
    pa, pb = resample(a.approach, [50.0])[0], resample(b.approach, [50.0])[0]
    d1 = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
    return abs(d1 - d0) <= 0.5 * d0 + 2.0


def merge_duals(mouths: list[Mouth], law: Law, stats
                 ) -> list[tuple[list[Mouth], XY, XY, float, list[XY]]]:
    """Cluster mouths of DIFFERENT bores that stand within the dual
    separation with parallel approaches (31h — transitively, so a 2+2
    with service lanes is ONE ramp): returns ``(members, mouth_xy,
    inward, full_width, axis_path)`` per ramp.  The mouth line stands at
    the OUTER of the mapped ends (a mapped bore is never cut open, 08-07
    ruling 2); the width spans every carriageway."""
    sep_max = law.tables.structures.tunnel.dual_carriageway_max_separation_m
    n = len(mouths)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if _parallel(mouths[i], mouths[j], sep_max):
                parent[find(i)] = find(j)
    groups: dict[int, list[Mouth]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(mouths[i])
    out = []
    for members in groups.values():
        if len(members) == 1:
            a = members[0]
            out.append(([a], a.xy, a.inward, a.width_m, list(a.approach)))
            continue
        stats.duals_merged += 1
        sx = sum(m.inward[0] for m in members)
        sy = sum(m.inward[1] for m in members)
        inward = unit((0.0, 0.0), (sx, sy))
        nx, ny = -inward[1], inward[0]
        # along: outward is -inward; the mouth line at the outermost end
        along = [-(m.xy[0] * inward[0] + m.xy[1] * inward[1]) for m in members]
        s_out = max(along)
        lat = [m.xy[0] * nx + m.xy[1] * ny for m in members]
        lo = min(l - m.width_m / 2 for l, m in zip(lat, members))
        hi = max(l + m.width_m / 2 for l, m in zip(lat, members))
        centre_lat = (lo + hi) / 2
        width = hi - lo
        # the axis: the mean of the approaches, re-based on the centre line
        length = max(LineString(m.approach).length for m in members)
        ss = [5.0 * k for k in range(int(length // 5.0) + 2)]
        rs = [resample(m.approach, ss) for m in members]
        axis = [(sum(r[k][0] for r in rs) / len(rs), sum(r[k][1] for r in rs) / len(rs))
                for k in range(len(ss))]
        a0 = axis[0]
        along0 = -(a0[0] * inward[0] + a0[1] * inward[1])
        lat0 = a0[0] * nx + a0[1] * ny
        dx = (centre_lat - lat0) * nx - (s_out - along0) * inward[0]
        dy = (centre_lat - lat0) * ny - (s_out - along0) * inward[1]
        axis = [(p[0] + dx, p[1] + dy) for p in axis]
        out.append((members, axis[0], inward, width, axis))
    return out
