"""THE STATE OF A BRIDGE'S LAND END (#2065 A3 rule 3; RULINGS 2026-11-14d /
e / f; spec ``docs/specs/2065-bridge-class-A3.md``), read ONCE at the pack
stage for every land end of a free or kept bridge (``airport/bridge_stack``)
and published on its stack (``model/deck_stack.StackEnd``).

* GAP = zero + top - G (the ground 1.5 m out, ``[bridge]
  free_end_ground_out_m``).
* PATH: the carried way outward from the end, then on through the feed's
  way joins by the straightest continuation (road or rail); a stub's path
  is its axis ray (:func:`_walk_path`).
* GRADE: ``[emit.road_contact] ramp_grade`` (5 %) for a road or a stub,
  ``[tunnel] rail_ramp_grade`` (1.25 %, 10-28k) for a rail.  RUN = gap /
  grade + ``abutment_sample_step_m``; no length cap where a road or rail is
  followed (14e).
* The NEAREST obstruction within max(RUN, the end line's length) decides
  (:func:`end_state`): FLUSH (gap within ``deck_flush_m``); HELD (14f (4),
  built as today): ``end_at_pack_solid`` (a non-deck solid of another frame
  standing ``end_solid_min_height_m`` over ``end_solid_min_area_m2``),
  ``end_route_stops`` (a routed deck whose path ends before RUN); LISTED
  (question B (a): nothing built): ``end_on_airside``, ``end_under_low_deck``
  (rule 8: another deck over the path less than ``[bridge] clearance_m``
  over the ramp; at or over it the ramp passes under, 14f (2)),
  ``end_on_water``, ``end_beyond_reach`` (a stub over ``[building_pad]
  fill_road_reach_m``), ``end_off_dem``; else GRADED.  ``end_on_lot`` is the
  planar stage's (``planar/free_bridge``).

No distance test anywhere (14f (1)).  Nothing here names a pack, a
resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point

from ..model.deck_stack import StackEnd

__all__ = ["Obstacles", "end_state", "cut"]

XY = tuple[float, float]
#: the walk's node join tolerance (m): way nodes shared in the feed project
#: onto one point
_JOIN_M = 0.05
#: a continuation turning more than this off the heading is no continuation
_COS_MIN = 0.5
#: the path is sampled this often (m) for the obstructions
_SAMPLE_M = 1.0
#: an end point this far off its carried way has no routed path
_ON_WAY_M = 2.0
_DECK_KINDS = ("flag", "signature")


def _route(w) -> bool:
    t = w.tags or {}
    return len(w.points) >= 2 and ("highway" in t or "railway" in t)


def _is_rail(ways: _t.Iterable) -> bool:
    """A carried route of railways only (rule 3: its grade is the rail's)."""
    tags = [w.tags or {} for w in ways]
    return bool(tags) and all("railway" in t and "highway" not in t for t in tags)


def _at_grade(tags: _t.Mapping[str, str]) -> bool:
    """A way at grade: no ``bridge`` / ``tunnel`` and layer 0 (14f (3): a way
    at another level is the bridge layer's, never seeded or graded)."""
    t = tags or {}
    if t.get("bridge", "no") not in ("", "no") or t.get("tunnel", "no") not in ("", "no"):
        return False
    try:
        return int(str(t.get("layer", "0")).strip() or 0) == 0
    except ValueError:
        return True


class _Graph:
    """The feed's routes and their nodes (one per read)."""

    def __init__(self, ways: _t.Sequence) -> None:
        self.ways = [w for w in ways if _route(w)]
        self.by_id = {int(w.id): k for k, w in enumerate(self.ways)}
        self.at: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for k, w in enumerate(self.ways):
            for i, p in enumerate(w.points):
                self.at.setdefault(self._key(p), []).append((k, i))

    @staticmethod
    def _key(p) -> tuple[int, int]:
        return (int(round(float(p[0]) / _JOIN_M)), int(round(float(p[1]) / _JOIN_M)))

    def joins(self, p) -> list[tuple[int, int]]:
        return self.at.get(self._key(p), [])


def _unit(dx: float, dy: float) -> "XY | None":
    n = math.hypot(dx, dy)
    return None if n < 1e-9 else (dx / n, dy / n)


def _pick(graph: _Graph, tip: XY, h: XY, used: list[int]):
    """The straightest continuation at ``tip`` off heading ``h``."""
    pick = None
    for k2, i2 in graph.joins(tip):
        if k2 in used:
            continue
        p2 = [tuple(map(float, p)) for p in graph.ways[k2].points]
        for nxt in (p2[i2 + 1:], p2[:i2][::-1]):
            d = _unit(nxt[0][0] - tip[0], nxt[0][1] - tip[1]) if nxt else None
            if d is None:
                continue
            c = d[0] * h[0] + d[1] * h[1]
            if c > _COS_MIN and (pick is None or c > pick[0]):
                pick = (c, k2, nxt)
    return pick


def _walk_path(start: XY, out: XY, carried: _t.Iterable[int], graph: _Graph,
              length: float, reach_m: float = _ON_WAY_M
              ) -> tuple[tuple[XY, ...], float, tuple[int, ...]]:
    """``(path, routed metres, way ids)`` (module doc): from the point of the
    carried way nearest ``start`` (within ``reach_m``) along it, outward
    (``out``), then through each node by the straightest continuation (within
    60 degrees), until ``length`` metres or the mapped route stops.
    ``((start,), 0, ())`` where no carried way passes within ``reach_m``."""
    best = None
    for wid in carried:
        k = graph.by_id.get(int(wid))
        if k is None:
            continue
        pts = graph.ways[k].points
        for i in range(len(pts) - 1):
            d = LineString([pts[i], pts[i + 1]]).distance(Point(start))
            if best is None or d < best[0]:
                best = (d, k, i)
    if best is None or best[0] > reach_m:
        return (start,), 0.0, ()
    _d, k, i = best
    pts = [tuple(map(float, p)) for p in graph.ways[k].points]
    seg = LineString([pts[i], pts[i + 1]])
    on = seg.interpolate(seg.project(Point(start)))
    fwd = (pts[i + 1][0] - pts[i][0]) * out[0] + (pts[i + 1][1] - pts[i][1]) * out[1] > 0.0
    # the path starts where the carried way passes the end line (the end
    # line's midpoint need not lie on the road: a skew or offset end)
    path: list[XY] = [(float(on.x), float(on.y))]
    path += [p for p in (pts[i + 1:] if fwd else pts[:i + 1][::-1])
             if math.dist(p, path[0]) > 1e-6]
    used = [k]
    run = LineString(path).length if len(path) > 1 else 0.0
    while run < length:
        h = _unit(path[-1][0] - path[-2][0], path[-1][1] - path[-2][1]) if len(path) > 1 else out
        pick = _pick(graph, path[-1], h, used) if h is not None else None
        if pick is None:
            break
        used.append(pick[1])
        path += pick[2]
        run = LineString(path).length
    return tuple(path), float(run), tuple(int(graph.ways[k].id) for k in used)


def cut(path: _t.Sequence[XY], length: float) -> LineString:
    """``path``'s first ``length`` metres."""
    line = LineString(path) if len(path) > 1 else None
    if line is None or line.length <= 0.0:
        p = tuple(path[0])
        return LineString([p, p])
    if line.length <= length:
        return line
    from shapely.ops import substring
    return substring(line, 0.0, length)


class Obstacles:
    """The airport's obstructions a land end's path may meet, read once per
    pack stage (module doc): the airside (``deck_stack._Airside``), the
    DEM's water and heights, the pack's decks and standing solids."""

    def __init__(self, airport, objects, cache, law, stack_zero: _t.Mapping[str, float]
                 ) -> None:
        from .deck_stack import _Airside
        br = law.tables.structures.bridge
        self.cache = cache
        self.dem = getattr(airport, "dem", None)
        self.airside = _Airside(airport)
        self.min_h = float(br.end_solid_min_height_m)
        self.min_a = float(br.end_solid_min_area_m2)
        self.graph = _Graph(getattr(airport, "osm_ways_mapped", None) or airport.osm_ways)
        self._objs = [o for o in objects or () if getattr(o, "resolved", None)
                      and getattr(o, "plan_bbox", None) is not None]
        from shapely.strtree import STRtree
        self._tree = STRtree([o.plan_bbox for o in self._objs]) if self._objs else None
        self._stack_zero = dict(stack_zero)
        self._solid: dict[str, _t.Any] = {}
        self._plate: dict[str, np.ndarray] = {}

    def z(self, xs, ys) -> np.ndarray:
        """The DEM under ``(xs, ys)`` (``nan`` off it)."""
        from .dem import dem_z_many
        if self.dem is None:
            return np.full(len(xs), np.nan)
        return dem_z_many(self.dem, np.asarray(xs, float), np.asarray(ys, float))

    def water(self, box):
        """The DEM's water in ``box`` (``None`` = none, or no witness)."""
        fn = getattr(self.dem, "water_geometry", None)
        if not callable(fn):
            return None
        try:
            w = fn(box)
        except Exception:                                 # pragma: no cover
            return None
        return None if w is None or w.is_empty else w

    def near(self, corridor, own: _t.Collection[str]) -> tuple[list, list]:
        """``(decks, solids)``: the pack decks (``flag`` / ``signature``)
        and the other placements whose plan meets ``corridor``, none of the
        frame ``own``."""
        decks, solids = [], []
        hits = (sorted(int(i) for i in self._tree.query(corridor, predicate="intersects"))
                if self._tree is not None else [])
        for o in (self._objs[i] for i in hits):
            if str(o.id) in own:
                continue
            hd = getattr(o, "hard_deck", None)
            if str(getattr(o, "deck_kind", "") or "") in _DECK_KINDS and hd is not None \
                    and not hd.is_empty:
                decks.append(o)
            else:
                solids.append(o)
        return decks, solids

    def standing(self, o):
        """The plan of placement ``o``'s solid faces standing at least
        ``end_solid_min_height_m`` over its zero, when it covers at least
        ``end_solid_min_area_m2``; else ``None``."""
        oid = str(o.id)
        if oid not in self._solid:
            import shapely

            from . import bridge_frame as _bf
            g = self.cache.geometry(o.resolved) if self.cache is not None else None
            f = _bf.solid_faces(g, o.xy, float(o.heading_deg or 0.0))
            got = None
            tri = f[f[:, :, 2].min(axis=1) >= self.min_h] if len(f) else f
            if len(tri):
                polys = [p for p in shapely.polygons(tri[:, :, :2])
                         if p.is_valid and p.area > 1e-3]
                if polys:
                    fp = shapely.union_all(polys, grid_size=0.01)
                    got = fp if fp.area >= self.min_a else None
            self._solid[oid] = got
        return self._solid[oid]

    def underside(self, o, x: float, y: float) -> float:
        """Rule 8: deck ``o``'s underside over ``(x, y)`` — its stack's zero
        (else the DEM at its anchor + its ``agl_m``) + its plate's lowest
        face there; ``nan`` off its plate."""
        from ..geom.lowest_face import floor_z_at
        from .deck_stack import _plate_tris
        oid = str(o.id)
        if oid not in self._plate:
            self._plate[oid] = (_plate_tris(o, self.cache, o.hard_deck.buffer(1.0))
                                if self.cache is not None else np.zeros((0, 3, 3)))
        plate = self._plate[oid]
        if not len(plate):
            return math.nan
        base = self._stack_zero.get(oid)
        if base is None:
            base = float(self.z([o.xy[0]], [o.xy[1]])[0]) + float(o.agl_m or 0.0)
        y_at = float(floor_z_at(plate, [x], [y], edge_m=0.5)[0])
        return base + y_at if math.isfinite(y_at) else math.nan


def _hits_on_path(line: LineString, run: float, corridor, own, mid: XY, top_at,
                  obs: Obstacles, clear: float) -> tuple[list, list[str]]:
    """``([(s, state, why)], decks passed under)`` along ``line``."""
    hits: list[tuple[float, str, str]] = []
    ss = np.arange(_SAMPLE_M, line.length + 1e-9, _SAMPLE_M)
    pts = [line.interpolate(s) for s in ss]
    if not pts:
        return hits, []
    xs = np.array([p.x for p in pts])
    ys = np.array([p.y for p in pts])
    off = np.flatnonzero(~np.isfinite(obs.z(xs, ys)))
    if off.size:
        hits.append((float(ss[off[0]]), "listed", "end_off_dem: the path leaves the DEM"))
    water = obs.water(corridor.bounds) if obs.dem is not None else None
    if water is not None:
        import shapely
        wet = np.flatnonzero(shapely.contains_xy(water, xs, ys))
        if wet.size:
            hits.append((float(ss[wet[0]]), "listed", "end_on_water"))
    air = next((s for s, p in zip(ss.tolist(), pts, strict=True) if obs.airside.contains(p)),
               None)
    if air is not None:
        hits.append((air, "listed", "end_on_airside"))
    decks, solids = obs.near(corridor, own)
    for o in solids:
        fp = obs.standing(o)
        if fp is None or not fp.intersects(line):
            continue
        meet = fp.intersection(line)
        s = min((line.project(Point(c)) for g in getattr(meet, "geoms", [meet])
                 for c in getattr(g, "coords", [])), default=0.0)
        hits.append((s, "held", f"end_at_pack_solid: {o.id} "
                                f"{str(getattr(o, 'path', '')).rsplit('/', 1)[-1]}"))
    under: list[str] = []
    for o in decks:
        ring = o.hard_deck
        for s, p in zip(ss.tolist(), pts, strict=True):
            if s > run or not ring.contains(p):
                continue
            room = obs.underside(o, p.x, p.y) - top_at(s)
            if math.isfinite(room) and room >= clear:
                under.append(str(o.id))
            else:
                hits.append((s, "listed", f"end_under_low_deck: {o.id} {room:.2f} m over "
                                          "the ramp < clearance_m"))
            break
    return hits, sorted(set(under))


def end_state(*, oid: str, side: str, stations: _t.Sequence[XY], top: float, out: XY,
              ground: float, zero: float, carried: _t.Sequence[int], stub: bool,
              own: _t.Collection[str], obs: Obstacles, law) -> StackEnd:
    """One land end's :class:`~..model.deck_stack.StackEnd` (module doc)."""
    br = law.tables.structures.bridge
    flush, step = float(br.deck_flush_m), float(br.abutment_sample_step_m)
    stations = tuple((float(x), float(y)) for x, y in stations)
    mid = (sum(p[0] for p in stations) / len(stations),
           sum(p[1] for p in stations) / len(stations))
    line_len = math.dist(stations[0], stations[-1]) if len(stations) > 1 else 0.0
    base = dict(object_id=oid, side=side, stations=stations, top=float(top),
                out=(float(out[0]), float(out[1])), ground=float(ground))
    if not math.isfinite(ground):
        return StackEnd(**base, gap=math.nan, state="unread",
                        why="free_end_unread: no ground read 1.5 m out (rule 10)")
    gap = float(zero) + float(top) - float(ground)
    if gap <= flush:
        return StackEnd(**base, gap=gap, state="flush", why=f"gap {gap:+.2f} <= deck_flush_m")
    by_id = {int(w.id): w for w in obs.graph.ways}
    rail = not stub and _is_rail([by_id[int(i)] for i in carried if int(i) in by_id])
    g = (float(law.tables.structures.tunnel.rail_ramp_grade) if rail
         else float(law.tables.emit.road_contact.ramp_grade))
    run = gap / g + step
    reach = max(run, line_len)
    if stub:
        path, routed, used = (mid, (mid[0] + out[0] * reach, mid[1] + out[1] * reach)), reach, ()
    else:
        path, routed, used = _walk_path(mid, out, carried, obs.graph, reach,
                                       reach_m=_ON_WAY_M + 0.5 * line_len)
    line = cut(path, reach)
    end = StackEnd(**base, gap=gap, state="graded", why="", run=run, grade=g, rail=rail,
                   path=tuple((float(x), float(y)) for x, y in line.coords))
    hits: list[tuple[float, str, str]] = []
    if stub and run > float(law.tables.structures.building_pad.fill_road_reach_m):
        hits.append((0.0, "listed", f"end_beyond_reach: a stub's run {run:.0f} m > "
                                    "fill_road_reach_m"))
    if not stub and routed + 1e-6 < run:
        hits.append((routed, "held", f"end_route_stops: the mapped route stops "
                                     f"{routed:.0f} m out, run {run:.0f} m"))
    corridor = (line.buffer(0.5 * max(line_len, 1.0), cap_style="flat")
                if line.length > 0 else Point(mid).buffer(1.0))
    more, under = _hits_on_path(line, run, corridor, own, mid,
                                lambda s: end.profile(zero, s, step), obs,
                                float(br.clearance_m))
    hits += [h for h in more if h[0] <= reach + 1e-6]
    crossing = []
    seg = cut(line.coords, run)
    if seg.length > 0:
        skip = {int(i) for i in carried} | set(used)
        crossing = sorted(int(w.id) for w in obs.graph.ways
                          if int(w.id) not in skip and _at_grade(w.tags)
                          and LineString(w.points).intersects(seg))
    import dataclasses as _dc
    if hits:
        s, state, why = min(hits, key=lambda h: h[0])
        return _dc.replace(end, state=state, why=f"{why} (at {s:.0f} m)",
                           crossings=tuple(crossing), under=tuple(under))
    return _dc.replace(end, why=f"graded: gap {gap:.2f} m over {run:.0f} m at {g:.2%}",
                       crossings=tuple(crossing), under=tuple(under))

