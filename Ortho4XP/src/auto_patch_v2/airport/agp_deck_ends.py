"""THE ENDS OF AN AGP FOLLOWER'S DRIVEN DECKS (#2116; RULINGS 2026-11-14f (1)
"all bridges in a scenery pack should be seated and graded", 2026-11-15g the
R6 bridge-end band; the AGP group of #2090).

A follower of a governed AGP group (``model/agp_group``) can carry roads on
its own elevated floors -- KDEN's departures and arrivals decks are pieces of
the terminal's ``.agp``.  Lifting the group (#2090) leaves those decks' ends
hanging over, or buried under, the road that carries on at grade.  Each such
end is read here as the LAND END of a KEPT stack (``model/deck_stack``) whose
zero is the group's predicted datum and whose ``datum_group`` is the group,
so every reader of a kept bridge's graded end grades it -- the end-line road
held at the deck top (R1), the road ramp seeded there, the ground along the
path (R6) and the stack ground (``planar/stack_ground``) -- and the stage-2
datum rewrite moves its rows by the group's delta (``constraints/agp_level``).

AN END: a mapped bridge way (``deck_signature.is_bridge_way``, no tunnel)
over a follower's connector floors (``agp_ground._connector_floors``, the
floors ``[agp] connector_floor_m`` or more over the datum) runs on a DECK
LEVEL -- the floor level under the most of its stations (the road surface,
never a kerb beside it; a slab's two faces a hair apart are one level, its
upper face the top; a deck drawn twice a metre apart reads its lower copy;
stacked storeys tied under it are no one deck and are listed).  That
level is FOLLOWED along the route (the way, run on one hop each way along
its straightest continuation) station to station, a ramp's slope kept, to
where it stops; there the route must run on in the open (off every floor
of the member) -- the last station on the deck is the END, its level the
deck's TOP there, the outward heading ``out``, and the END LINE the run of
that level's floor across the way.  Two ways ending one deck end read it
once.  An end whose road goes on over a pack deck is no end
(the deck's own read joins it).  The end's state is ``bridge_end_state.
end_state``'s; an end standing UNDER its ground (gap under ``-deck_flush_m``)
is a CUT end: ``graded`` over the slab alone, its road leaving on the road
ramp's cut (``road_descent.climb``).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..model.deck_stack import KEPT, DeckStack, StackDeck
from ..model.frame import XY

__all__ = ["AGP_END_PREFIX", "agp_end_stacks"]

#: ``DeckStack.bridge`` / the end's object id of an AGP deck end
AGP_END_PREFIX = "agp_end:"
#: the way is sampled this often (m) for the floor under it
_STEP = 0.5
#: two floor heights closer than this are one level (m): a slab's two faces
_PAIR = 0.3
#: the end line is sought this far either side of the way (m)
_ACROSS_M = 30.0
#: the plate kept for an end: floor triangles within this of the end (m) ...
_PLATE_M = 15.0
#: ... rising or falling from the end's top at most this grade (a deck ramp,
#: ``[tunnel] ramp_max_grade``'s 10 %)
_PLATE_GRADE = 0.1
#: a route outside the floor must run on at least this far to its end (m) ...
_OUT_MIN_M = 3.0
#: ... or this far before it comes back under the member's floors (m): a short
#: open stretch between two parts of the building is no end
_OPEN_MIN_M = 15.0
#: a continuation turning more than this off the heading is no continuation
_COS_MIN = 0.5
#: the way's deck is the lowest level held on this share of the most-held
#: level's stations (``bridge_witness.SURFACE_SHARE``'s 80 %)
_SHARE = 0.8
#: a deck level is followed station to station within this (m): a 10 % ramp
#: over one station and the floors' own seams
_TRACK_TOL = _PAIR + 0.1 * _STEP


def _unit(dx: float, dy: float) -> "XY | None":
    n = math.hypot(dx, dy)
    return None if n < 1e-9 else (dx / n, dy / n)


class _Floors:
    """One follower's connector floors in the frame: triangles, plan
    polygons, their tree and the heights (mean ``y`` per triangle)."""

    def __init__(self, tris: np.ndarray) -> None:
        import shapely
        self.tris, self.polys, self.y, self.tree = tris[:0], np.array([]), np.zeros(0), None
        if not len(tris):
            return
        polys = shapely.polygons(tris[:, :, :2])
        ok = shapely.area(polys) > 1e-6
        self.tris, self.polys = tris[ok], polys[ok]
        self.y = self.tris[:, :, 2].mean(axis=1)
        self.tree = shapely.STRtree(self.polys) if len(self.polys) else None

    def levels_at(self, xy: XY) -> list[float]:
        """The floor heights ``y`` AT plan point ``xy`` of the triangles
        holding it (each triangle's plane, a ramp's slope kept)."""
        import shapely
        if self.tree is None:
            return []
        out = []
        for i in self.tree.query(shapely.Point(xy), predicate="intersects"):
            (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = self.tris[i]
            det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(det) < 1e-12:
                out.append(float(self.y[i]))
                continue
            a = ((y1 - y2) * (xy[0] - x2) + (x2 - x1) * (xy[1] - y2)) / det
            b = ((y2 - y0) * (xy[0] - x2) + (x0 - x2) * (xy[1] - y2)) / det
            out.append(float(a * z0 + b * z1 + (1.0 - a - b) * z2))
        return out

    def on(self, xy: XY, level: "float | None" = None, tol: float = 0.5) -> bool:
        """Plan point ``xy`` stands on a floor (of ``level`` within ``tol``)."""
        ys = self.levels_at(xy)
        return bool(ys) if level is None else any(abs(y - level) <= tol for y in ys)


def _route_line(w, at: _t.Mapping, key) -> tuple[list[XY], tuple[int, ...]]:
    """``(points, way ids)``: way ``w``'s points run on ONE hop at each end
    along the straightest continuation (within 60 degrees) of a non-tunnel
    route way."""
    pts = [tuple(map(float, p)) for p in w.points]
    ids = [int(w.id)]

    def hop(tip: XY, prev: XY) -> list[XY]:
        h = _unit(tip[0] - prev[0], tip[1] - prev[1])
        best = None
        for w2 in at.get(key(tip), ()):
            if w2 is w or h is None:
                continue
            p2 = [tuple(map(float, p)) for p in w2.points]
            nxt = p2[1:] if key(p2[0]) == key(tip) else p2[:-1][::-1]
            d = _unit(nxt[0][0] - tip[0], nxt[0][1] - tip[1]) if nxt else None
            if d is None:
                continue
            c = d[0] * h[0] + d[1] * h[1]
            if c > _COS_MIN and (best is None or c > best[0]):
                best = (c, nxt, int(w2.id))
        if best is None:
            return []
        ids.append(best[2])
        return best[1]
    return [*hop(pts[0], pts[1])[::-1], *pts, *hop(pts[-1], pts[-2])], tuple(ids)


def _vote(levels: _t.Sequence[_t.Sequence[float]], storey: float
          ) -> "tuple[float | None, str]":
    """``(the way's deck level, why not)``: a reading counts at every
    station holding a level within :data:`_PAIR` of it (a slab drawn as two
    faces a hair apart is one level); the LOWEST level held on
    :data:`_SHARE` of the most-held count is the road surface (a copy drawn
    over it, a canopy, is not); two more so held, storeys apart (stacked
    floors, a parking structure's), leave it unread."""
    cands = sorted({round(y, 2) for ys in levels for y in ys})
    if not cands:
        return None, ""
    votes = {c: sum(1 for ys in levels if any(abs(y - c) <= _PAIR for y in ys)) for c in cands}
    top = max(votes.values())
    best = min(c for c in cands if votes[c] >= _SHARE * top)
    held = [c for c in cands if votes[c] >= _SHARE * top]
    tied = [c for c in held if abs(c - best) >= storey]
    if len({round(c / storey) for c in tied}) >= 2:
        return None, (f"floors {sorted({best, *tied})} tied under the way (stacked "
                      "storeys): no one deck, listed")
    return best, ""


def _track(levels, start: int, y0: float, step: int) -> tuple[int, float]:
    """``(last station, its level)``: the deck level followed from station
    ``start`` at ``y0`` in direction ``step``, each station taking the level
    nearest the last within :data:`_TRACK_TOL` (a ramp's slope kept)."""
    i, y = start, y0
    while 0 <= i + step < len(levels):
        near = [q for q in levels[i + step] if abs(q - y) <= _TRACK_TOL]
        if not near:
            break
        i, y = i + step, min(near, key=lambda q: abs(q - y))
    return i, y


def _open(levels, i: int, step: int) -> bool:
    """The route runs off every floor from station ``i`` on for
    :data:`_OUT_MIN_M` to the line's end, or :data:`_OPEN_MIN_M` before it
    comes back under one."""
    run, k = 0, i
    while 0 <= k < len(levels) and not levels[k]:
        run, k = run + 1, k + step
    return run * _STEP >= (_OPEN_MIN_M if 0 <= k < len(levels) else _OUT_MIN_M)


def _deck_ends(line, own, fl: _Floors, storey: float
               ) -> "tuple[list[tuple[XY, XY, float]], str]":
    """``([(end point, outward unit, the deck's top there)], why none)``:
    the deck level the bridge way ``own`` runs on (:func:`_vote` over its
    stations) followed both ways along ``line`` (:func:`_track`) to where it
    stops, each stop an end where the route then runs in the open
    (:func:`_open`)."""
    n = int(line.length / _STEP)
    if n < 2:
        return [], ""
    pts = [line.interpolate(i * _STEP) for i in range(n + 1)]
    levels = [fl.levels_at((p.x, p.y)) for p in pts]
    mine = [i for i, p in enumerate(pts) if own.distance(p) <= 0.5]
    best, why = _vote([levels[i] for i in mine], storey)
    if best is None:
        return [], why
    start = next((i for i in mine if any(abs(q - best) <= _PAIR for q in levels[i])), None)
    if start is None:
        return [], ""
    y0 = min((q for q in levels[start]), key=lambda q: abs(q - best))
    out = []
    for step in (1, -1):
        i, y = _track(levels, start, y0, step)
        if not 0 <= i + step <= n or not _open(levels, i + step, step):
            continue
        u = _unit(pts[i + step].x - pts[i].x, pts[i + step].y - pts[i].y)
        if u is not None:
            # the deck's TOP there: the lowest level within half a storey under
            # the one followed (a copy drawn over the road is not it), its
            # upper face
            low = min(q for q in levels[i] if y - 0.5 * storey <= q <= y + _PAIR)
            top = max(q for q in levels[i] if abs(q - low) <= _PAIR)
            out.append(((pts[i].x, pts[i].y), u, top))
    return out, ""


def _end_line(p: XY, out: XY, fl: _Floors, level: float) -> tuple[XY, ...]:
    """The run of ``level``'s floor across the way at end point ``p``."""
    q = (p[0] - out[0] * _STEP, p[1] - out[1] * _STEP)
    nrm = (-out[1], out[0])
    side = []
    for sgn in (-1.0, 1.0):
        far, t = 0.0, _STEP
        while t <= _ACROSS_M and fl.on((q[0] + sgn * t * nrm[0], q[1] + sgn * t * nrm[1]),
                                       level):
            far, t = t, t + _STEP
        side.append(sgn * far)
    a, b = side
    if b - a < 2.0:
        return ()
    k = max(2, int(b - a) + 1)
    return tuple((q[0] + (a + (b - a) * i / (k - 1)) * nrm[0],
                  q[1] + (a + (b - a) * i / (k - 1)) * nrm[1]) for i in range(k))


def _plate(stations: _t.Sequence[XY], out: XY, fl: _Floors, top: float):
    """``(ring, triangles)`` of the deck piece at the end: the floor
    triangles of the END'S OWN LANE -- centroids within :data:`_PLATE_M`
    inside the end line and across it no wider than the line (plus one
    metre) -- standing on the deck's own surface (within :data:`_PAIR` of
    ``top`` plus a ramp's :data:`_PLATE_GRADE` over their distance in): a
    neighbouring deck beside it, a copy drawn over it, is not this end's.
    ``None`` with none."""
    import shapely
    mid = (sum(q[0] for q in stations) / len(stations),
           sum(q[1] for q in stations) / len(stations))
    half = 0.5 * math.dist(stations[0], stations[-1]) + 1.0
    c = fl.tris[:, :, :2].mean(axis=1)
    rel = c - np.array(mid)
    inward = -(rel[:, 0] * out[0] + rel[:, 1] * out[1])
    across = np.abs(-rel[:, 0] * out[1] + rel[:, 1] * out[0])
    keep = (inward >= -1.0) & (inward <= _PLATE_M) & (across <= half) \
        & (np.abs(fl.y - top) <= _PAIR + _PLATE_GRADE * np.maximum(inward, 0.0))
    if not keep.any():
        return None
    u = shapely.union_all(fl.polys[keep], grid_size=0.01)
    parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon"]
    part = max(parts, key=lambda g: g.area, default=None)
    if part is None:
        return None
    ring = tuple((float(x), float(y)) for x, y in part.simplify(0.05).exterior.coords[:-1])
    return ring, fl.tris[keep]


def _ground(stations: _t.Sequence[XY], out: XY, dem, out_m: float) -> float:
    """G_e: the DEM's median along the end line shifted ``out_m`` out."""
    from .dem import dem_z_many
    if dem is None:
        return math.nan
    xs = np.array([x + out[0] * out_m for x, _y in stations], float)
    ys = np.array([y + out[1] * out_m for _x, y in stations], float)
    z = dem_z_many(dem, xs, ys)
    z = z[np.isfinite(z)]
    return float(np.median(z)) if z.size else math.nan


def _cut(end, law):
    """A CUT end (module doc): graded over the slab alone."""
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    g = float(law.tables.emit.road_contact.ramp_grade)
    mid = (sum(p[0] for p in end.stations) / len(end.stations),
           sum(p[1] for p in end.stations) / len(end.stations))
    path = (mid, (mid[0] + end.out[0] * step, mid[1] + end.out[1] * step))
    return _dc.replace(end, state="graded", run=step, grade=g, path=path,
                       why=f"cut: the deck end stands {-end.gap:.2f} m under its ground — the "
                           "slab is held at the deck top and the road climbs out on the road "
                           "ramp's cut (#2116)")


def _route_ways(airport) -> list:
    from .deck_signature import is_tunnel_way
    ways = list(getattr(airport, "osm_ways_mapped", None) or airport.osm_ways)
    return [w for w in ways if len(w.points) >= 2 and not is_tunnel_way(w.tags or {})
            and ("highway" in (w.tags or {}) or "railway" in (w.tags or {}))]


def _key(p) -> tuple[int, int]:
    return (int(round(float(p[0]) / 0.05)), int(round(float(p[1]) / 0.05)))


def _ends_of(cx, g, fm, fl: _Floors, ways, at, notes: list) -> list[DeckStack]:
    """The minted stacks of one follower's deck ends (module doc)."""
    from shapely.geometry import LineString, Point

    from .bridge_end_state import end_state
    from .bridge_stack import _stack
    from .deck_signature import is_bridge_way
    law, airport = cx.law, cx.airport
    flush = float(law.tables.structures.bridge.deck_flush_m)
    zp = float(g.zero_pred(fm.row))
    out = []
    seen: list[XY] = []
    for w in ways:
        if not is_bridge_way(w.tags or {}):
            continue
        own = LineString(w.points)
        if not len(fl.tree.query(own, predicate="intersects")):
            continue
        pts, carried = _route_line(w, at, _key)
        line = LineString(pts)
        got, why = _deck_ends(line, own, fl, float(law.tables.structures.agp.connector_floor_m))
        if why:
            notes.append(f"{g.id} {fm.row} way {w.id}: {why}")
        for k, (p, u, lvl) in enumerate(got):
            if any(math.dist(p, q) <= 2.0 for q in seen):
                continue                        # another way of the route read it
            seen.append(p)
            tag = f"{g.id} {fm.row} way {w.id} end {k}"
            stations = _end_line(p, u, fl, lvl)
            if not stations:
                notes.append(f"{tag}: no end line across the way at y {lvl:.2f}, listed")
                continue
            mid = (sum(q[0] for q in stations) / len(stations),
                   sum(q[1] for q in stations) / len(stations))
            look = Point(mid[0] + u[0] * 2.0, mid[1] + u[1] * 2.0)
            decks, _solids = cx.obs.near(look.buffer(0.5), {fm.row})
            if any(d.hard_deck.contains(look) for d in decks):
                notes.append(f"{tag}: the road goes on over a pack deck — that deck's end "
                             "(its own read), not graded here")
                continue
            pl = _plate(stations, u, fl, lvl)
            if pl is None:
                continue
            ring, tris = pl
            oid = f"{AGP_END_PREFIX}{fm.row}:{w.id}:{k}"
            ground = _ground(stations, u, getattr(airport, "dem", None), cx.out_m)
            end = end_state(oid=oid, side="a", stations=stations, top=lvl, out=u,
                            ground=ground, zero=zp, carried=carried, stub=False,
                            own={fm.row, oid}, obs=cx.obs, law=law)
            if end.state == "flush" and end.gap < -flush:
                end = _cut(end, law)
            note = (f"{tag}: AGP deck end y {lvl:.2f} (top {zp + lvl:.2f}), ground "
                    f"{ground:.2f}, gap {end.gap:+.2f} — {end.state}: {end.why}")
            notes.append(note)
            if end.state != "graded":
                continue
            deck = StackDeck(oid, str(fm.resource), 0, ring, 1, (int(w.id),), (), stations,
                             (), float(lvl), 0.0,
                             tuple(tuple(tuple(float(v) for v in q) for q in t) for t in tris))
            st = _stack(oid, KEPT, [(oid, str(fm.resource))], [deck], [end], zp, [note])
            out.append(_dc.replace(st, datum_group=g.id))
    return out


def agp_end_stacks(cx) -> tuple[list[DeckStack], list[str]]:
    """``(minted stacks, notes)``: one KEPT stack per GRADED (or cut) end of
    every governed group's followers' driven decks (module doc); ``cx`` is
    ``airport/bridge_stack._Ctx``."""
    from .agp_plates import _frame_tris
    floors = cx.floors
    if floors is None or not floors.groups:
        return [], []
    ways = _route_ways(cx.airport)
    at: dict[tuple[int, int], list] = {}
    for w in ways:
        at.setdefault(_key(w.points[0]), []).append(w)
        at.setdefault(_key(w.points[-1]), []).append(w)
    out: list[DeckStack] = []
    notes: list[str] = []
    for g in floors.groups:
        for fm in g.followers():
            loc = floors.floors(fm.row)
            if g.zero_pred(fm.row) is None or not loc.shape[0]:
                continue
            fl = _Floors(_frame_tris(loc, floors.lat0, floors.lon0, cx.airport.frame.crs))
            if fl.tree is not None:
                out += _ends_of(cx, g, fm, fl, ways, at, notes)
    return out, notes
