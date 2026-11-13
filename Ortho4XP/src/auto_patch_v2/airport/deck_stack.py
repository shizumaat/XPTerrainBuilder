"""THE DECK STACK, DERIVED ONCE (#1971; spec ``interchange-levels-20261113.md``
§3; record ``model/deck_stack``).

A pack may build an interchange from objects standing over one another: a
trench whose walls rise from its floor (``airport/stack_walls``), a road
deck over it, another over that.  Read alone, each object is wrong (the
walls become pads, the lower deck's zero sits on the road it carries, that
road is graded across the trench).  Read as ONE stack:

* LEVEL 0 is the floor between the walls; LEVELS 1..N the members' hard
  decks spanning it, by their plate's height (two within ``[bridge]
  clearance_minimum_m`` are one level);
* MEMBERS are the walls and every ``OBJECT`` placement standing on the floor
  at the walls' own AGL — the author stood them on that floor, so the stack
  has ONE zero, read off every deck end line as a bridge's is (RULINGS
  2026-10-30a; ``deck_anchor.derive``'s mean of ground less top, the ground
  one ``abutment_sample_step_m`` outside the deck, never under it);
* the TERRAIN is the lowest level only: the floor (``floor_level``) through
  under every deck, run out along the under-way at its own law
  (``geom/ramp_profile``); a road a deck carries is a mapped bridge between
  the deck's end lines (``airport/deck_carry.bridge_stretches``).

The stack is published in records the passes already read: the floor is an
``ObjectFloor`` (:func:`stack_floors`), the members' pads leave through
``Airport.stack_shade``.  Nothing here names a pack, a resource or an
airport; every number is a law-table value.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..model.deck_stack import STACK_PREFIX, DeckStack, StackDeck, floor_level
from . import obj8 as _obj8
from .deck_carry import Carry, bridge_stretches, carry_of
from .stack_walls import StackWalls, floor_between, read_stack_walls, run_beside, wall_hull

__all__ = ["stack_floors", "attach_stacks", "log_line"]

XY = tuple[float, float]
RouteOf = _t.Callable[[_t.Any], LineString]


def _is_deck(o) -> bool:
    """A hard deck of the population ``planar/deck_bridge`` reads."""
    return (str(getattr(o, "deck_kind", "") or "") in ("flag", "signature")
            and getattr(o, "hard_deck", None) is not None and not o.hard_deck.is_empty)


def _route_way(w) -> bool:
    return ("highway" in w.tags or "railway" in w.tags) and len(w.points) >= 2


def _layer(w) -> int:
    """The way's mapped layer: its ``layer`` tag, else 1 on a bridge, -1 in a
    tunnel, 0 (§3.4 the tag check)."""
    t = w.tags
    try:
        return int(str(t.get("layer", "")).strip())
    except ValueError:
        pass
    if t.get("bridge") and t.get("bridge") != "no":
        return 1
    if t.get("tunnel") and t.get("tunnel") != "no":
        return -1
    return 0


def _plate_tris(o, cache, piece: Polygon) -> np.ndarray:
    """The deck plate's triangles over ``piece`` as ``(n, 3, 3)`` frame x,
    y, authored y."""
    g = cache.geometry(o.resolved) if o.resolved else None
    if g is None:
        return np.zeros((0, 3, 3))
    tri = g.hard_deck
    v = np.asarray(g.vertices[:, :3], float)
    out = []
    near = piece.buffer(0.5)
    for t in tri:
        pts = [(*_obj8._to_frame(o.xy, o.heading_deg, v[i, 0], v[i, 2]), v[i, 1]) for i in t]
        c = Point(sum(p[0] for p in pts) / 3.0, sum(p[1] for p in pts) / 3.0)
        if near.contains(c):
            out.append(pts)
    return np.asarray(out, float).reshape(-1, 3, 3)


class _Ctx:
    """The airport's routes, once per derivation."""

    def __init__(self, airport, route_of: RouteOf) -> None:
        self.ways = [w for w in airport.osm_ways if _route_way(w)]
        self.lines = [LineString(w.points) for w in self.ways]
        self.tree = STRtree(self.lines) if self.lines else None
        self._route_of = route_of
        self._routes: dict[int, LineString] = {}

    def near(self, geom) -> list[int]:
        if self.tree is None:
            return []
        return sorted(int(i) for i in self.tree.query(geom, predicate="intersects"))

    def route(self, k: int) -> LineString:
        r = self._routes.get(k)
        if r is None:
            r = self._route_of(self.ways[k])
            self._routes[k] = r
        return r


def _under_way(walls: StackWalls, ctx: _Ctx, law, tries: int = 1):
    """``(way index, route, floor cast)`` of the route running furthest
    beside ``walls`` with a floor between them, or a note.  The ways are
    ranked by their own length inside the walls' hull; the route of the
    first (``tries``) is walked and the floor cast along it."""
    hull = wall_hull(walls)
    floor_min = float(law.tables.structures.tunnel.object.hull_min_length_m)
    own = sorted(((ctx.lines[k].intersection(hull).length, k) for k in ctx.near(hull)),
                 reverse=True)[:tries]
    cands = sorted(((run_beside(ctx.route(k), walls), k) for run, k in own if run > 0.0),
                   reverse=True)
    why = "no mapped highway or railway runs in it"
    for run, k in cands:
        if run < floor_min:
            break
        fc = floor_between(walls, ctx.route(k), law)
        if not isinstance(fc, str):
            return k, ctx.route(k), fc
        why = f"way {ctx.ways[k].id}: {fc}"
    return why


class _Anchors:
    """Every OBJECT placement's anchor, once per derivation (the members'
    test, §3.3)."""

    def __init__(self, objects) -> None:
        self.objs = [o for o in objects if o.kind == "OBJECT"]
        self.x = np.array([float(o.xy[0]) for o in self.objs])
        self.y = np.array([float(o.xy[1]) for o in self.objs])
        self.agl = np.array([float(o.agl_m) for o in self.objs])

    def members(self, W, floor: Polygon, tol: float, taken: set[str]) -> list:
        """W and every OBJECT placement on the floor at W's AGL."""
        import shapely
        near = floor.buffer(tol)
        x0, y0, x1, y1 = near.bounds
        box = (self.x >= x0) & (self.x <= x1) & (self.y >= y0) & (self.y <= y1) \
            & (np.abs(self.agl - float(W.agl_m)) <= 1e-3)
        k = np.flatnonzero(box)
        inside = shapely.contains_xy(near, self.x[k], self.y[k]) if k.size else []
        out = [W]
        for i, ok in zip(k.tolist(), list(inside), strict=True):
            o = self.objs[i]
            if ok and o is not W and str(o.id) not in taken:
                out.append(o)
        return out


def _spans(piece: Polygon, left: LineString, right: LineString) -> bool:
    return piece.intersects(left) and piece.intersects(right)


def _runout(route: LineString, s_end: float, outward: int, half: tuple[float, float], z0: float,
            airport, law, rail: bool, stop) -> "tuple | str":
    """One run-out strip off the floor's end at ``s_end`` (§3.7 (2)):
    ``(ring, z at the walls, z at the lip)`` or why none."""
    from ..geom.ramp_profile import runout_profile
    from .dem import dem_z_many
    tn = law.tables.structures.tunnel
    g, cap = ((float(tn.rail_ramp_grade), float(tn.rail_ramp_max_grade)) if rail
              else (float(tn.ramp_grade), float(tn.ramp_max_grade)))
    room = (route.length - s_end) if outward > 0 else s_end
    run = min(room, float(tn.max_ramp_length_m))
    if run < 1.0:
        return "the under-way ends at the walls"

    def at(u: float) -> XY:
        p = route.interpolate(s_end + outward * u)
        return p.x, p.y

    def dem_at(u: float) -> float:
        x, y = at(u)
        return float(dem_z_many(airport.dem, np.array([x]), np.array([y]))[0])

    prof = runout_profile(z0, dem_at, g, cap, run)
    note = ""
    for k, (u, _z) in enumerate(prof):
        if k and stop is not None and stop.contains(Point(at(u))):
            prof = prof[:k]
            note = "stops at airside pavement"
            break
    if len(prof) < 2:
        return note or "no room"
    left, right = [], []
    for u, _z in prof:
        x, y = at(u)
        a = route.interpolate(max(0.0, s_end + outward * u - 0.5))
        b = route.interpolate(min(route.length, s_end + outward * u + 0.5))
        d = math.hypot(b.x - a.x, b.y - a.y) or 1.0
        n = (-(b.y - a.y) / d, (b.x - a.x) / d)
        left.append((x + n[0] * half[0], y + n[1] * half[0]))
        right.append((x - n[0] * half[1], y - n[1] * half[1]))
    ring = tuple(left) + tuple(reversed(right))
    return ring, float(prof[0][1]), float(prof[-1][1]), note


class _Airside:
    """The apt.dat airside pavement and runways a run-out stops at."""

    def __init__(self, airport) -> None:
        polys = []
        for p in getattr(airport, "pavements", ()) or ():
            if len(p.outer) >= 3:
                q = Polygon(p.outer, p.holes)
                polys.append(q if q.is_valid else q.buffer(0.0))
        for rw in getattr(airport, "runways", ()) or ():
            if len(rw.ends) == 2:
                polys.append(LineString([rw.ends[0].xy, rw.ends[1].xy]).buffer(rw.width_m / 2.0))
        self._polys = polys
        self._tree = STRtree(polys) if polys else None

    def contains(self, p: Point) -> bool:
        return self._tree is not None and len(self._tree.query(p, predicate="within")) > 0


def _end_ground(airport, stations, out: XY, step: float) -> float:
    from .dem import dem_z_many
    xs = np.array([x + out[0] * step for x, _y in stations])
    ys = np.array([y + out[1] * step for _x, y in stations])
    z = dem_z_many(airport.dem, xs, ys)
    z = z[np.isfinite(z)]
    return float(np.median(z)) if z.size else math.nan


def _one(W, walls: StackWalls, ctx: _Ctx, anchors: _Anchors, cache, airport, law,
         taken: set[str], decks_all: list, notes: list[str]) -> "DeckStack | None":
    """The stack standing on W's floor, or ``None`` with a note."""
    ob = law.tables.structures.tunnel.object
    br = law.tables.structures.bridge
    step = float(br.abutment_sample_step_m)
    tag = f"{W.id} {str(W.path).rsplit('/', 1)[-1]}"
    got = _under_way(walls, ctx, law)
    if isinstance(got, str):
        notes.append(f"{tag}: floor-datum walls, no floor ({got})")
        return None
    k_under, route, fc = got
    floor = fc.polygon
    members = anchors.members(W, floor, float(ob.cover_placement_tol_m), taken)
    ids = {str(o.id) for o in members}
    left, right = LineString(fc.left), LineString(fc.right)
    for o in decks_all:
        if str(o.id) not in ids and any(_spans(p, left, right)
                                         for p in getattr(o.hard_deck, "geoms", [o.hard_deck])):
            notes.append(f"{tag}: deck {o.id} spans the floor but is no member "
                         f"(its anchor is off the floor or at another AGL): it keeps its reading")
    pieces: list[tuple[_t.Any, int, Polygon, np.ndarray, Carry]] = []
    spanning = False
    for o in members:
        if not _is_deck(o):
            continue
        parts = [p for p in getattr(o.hard_deck, "geoms", [o.hard_deck])
                 if p.geom_type == "Polygon" and p.area >= 1.0]
        for k, piece in enumerate(sorted(parts, key=lambda p: -p.area)):
            spanning = spanning or _spans(piece, left, right)
            plate = _plate_tris(o, cache, piece)
            routes = [(ctx.ways[j], ctx.route(j)) for j in ctx.near(piece.buffer(step))]
            c = carry_of(piece, plate, routes, law)
            where = f"{o.id} {str(o.path).rsplit('/', 1)[-1]} piece {k}"
            if isinstance(c, str):
                notes.append(f"{tag}: {where}: {c}")
                continue
            notes.extend(f"{tag}: {where}: {n}" for n in c.notes)
            if not c.carried:
                notes.append(f"{tag}: {where}: carries no mapped road — no level")
                continue
            pieces.append((o, k, piece, plate, c))
    if not spanning or not pieces:
        notes.append(f"{tag}: floor-datum walls, but no member's hard deck spans them — no stack")
        return None
    # LEVELS by the plate's mean height; within clearance_minimum_m = one
    order = sorted(pieces, key=lambda t: float(t[3][:, :, 2].mean()))
    levels: list[int] = []
    lvl, base = 0, None
    for t in order:
        y = float(t[3][:, :, 2].mean())
        if base is None or y - base >= float(br.clearance_minimum_m):
            lvl, base = lvl + 1, y
        levels.append(lvl)
    carried_by: dict[int, set[int]] = {}
    for (_o, _k, _p, _pl, c), L in zip(order, levels, strict=True):
        carried_by.setdefault(L, set()).update(c.carried)
    all_carried = set().union(*carried_by.values())
    if int(ctx.ways[k_under].id) in all_carried:
        notes.append(f"{tag}: the only route in the floor is one a deck carries "
                     f"(way {ctx.ways[k_under].id}) — nothing runs under, no stack")
        return None
    by_id = {int(w.id): w for w in ctx.ways}
    # the ways running IN the floor: no carried road, no mapped bridge (a
    # bridge stands over the floor, never on it)
    from .deck_signature import is_bridge_way
    under_ways = sorted({int(ctx.ways[j].id) for j in ctx.near(floor)
                         if int(ctx.ways[j].id) not in all_carried
                         and not is_bridge_way(ctx.ways[j].tags)
                         and ctx.lines[j].intersection(floor).length
                         >= float(ob.hull_min_length_m)} | {int(ctx.ways[k_under].id)})
    # THE TAG CHECK (§3.4): the mapped layers never contradict the levels
    lay = {L: [_layer(by_id[i]) for i in ws if i in by_id] for L, ws in carried_by.items()}
    for a in sorted(lay):
        for b in sorted(lay):
            if a < b and lay[a] and lay[b] and min(lay[b]) < max(lay[a]):
                notes.append(f"{tag}: the mapped layers contradict the levels (level {b} "
                             f"carries layer {min(lay[b])} under level {a}'s {max(lay[a])}) "
                             f"— no stack (a finding, never resolved in code)")
                return None
    u_lay = _layer(ctx.ways[k_under])
    if lay.get(1) and u_lay > min(lay[1]):
        notes.append(f"{tag}: the under-way's layer {u_lay} stands over level 1's "
                     f"{min(lay[1])} — no stack (a finding)")
        return None
    # ONE ZERO (§3.6)
    end_zeros = []
    decks: list[StackDeck] = []
    for (o, k, piece, plate, c), L in zip(order, levels, strict=True):
        under = sorted(i for i in c.across
                       if i in under_ways or any(i in carried_by.get(m, ()) for m in range(1, L)))
        for side, st, out, top in (("a", c.end_a, c.out_a, c.top_a), ("b", c.end_b, c.out_b,
                                                                        c.top_b)):
            gz = _end_ground(airport, st, out, step)
            if math.isfinite(gz):
                end_zeros.append((str(o.id), k, side, round(gz, 3), round(top, 3)))
        decks.append(StackDeck(str(o.id), str(o.path), k,
                               tuple((float(x), float(y)) for x, y in piece.exterior.coords[:-1]),
                               L, c.carried, tuple(under), c.end_a, c.end_b,
                               float(c.top_a), float(c.top_b),
                               tuple(tuple(tuple(float(v) for v in p) for p in t) for t in plate)))
    if not end_zeros:
        notes.append(f"{tag}: no deck end line stands on the DEM — no stack")
        return None
    zs = [g - t for _o, _k, _s, g, t in end_zeros]
    zero = sum(zs) / len(zs)
    spread = max(zs) - min(zs)
    if spread > float(law.tables.structures.tunnel.clearance_m):
        notes.append(f"{tag}: the end lines' zeros spread {spread:.2f} m > [tunnel] clearance_m "
                     f"({', '.join(f'{z:.2f}' for z in zs)}): the members do not stand in one "
                     f"frame on this ground — no stack")
        return None
    fz = floor_level(zero, walls.feet_y)
    # THE RUN-OUTS (§3.7 (2)) off each open end, at the under-way's law
    under_w = ctx.ways[k_under]
    rail = "railway" in under_w.tags and "highway" not in under_w.tags
    stop = _Airside(airport)
    runouts = []
    for end, s_end, outward in ((0, fc.s0, -1), (1, fc.s1, 1)):
        lp, rp = fc.end_width(end)
        p = route.interpolate(s_end)
        half = (math.dist((p.x, p.y), lp), math.dist((p.x, p.y), rp))
        r = _runout(route, s_end, outward, half, fz, airport, law, rail, stop)
        if isinstance(r, str):
            notes.append(f"{tag}: run-out {'start' if end == 0 else 'end'}: {r}")
            continue
        ring, z0, z1, why = r
        runouts.append((ring, round(z0, 3), round(z1, 3)))
        notes.append(f"{tag}: run-out {'start' if end == 0 else 'end'} "
                     f"{math.dist(ring[0], ring[len(ring) // 2 - 1]):.0f} m, "
                     f"{z0:.2f} -> {z1:.2f}" + (f" ({why})" if why else ""))
    return DeckStack(
        id=STACK_PREFIX + str(W.id), walls_id=str(W.id), walls_resource=str(W.path),
        members=tuple((str(o.id), str(o.path)) for o in members),
        zero_z=round(zero, 3), zero_spread_m=round(spread, 3), end_zeros=tuple(end_zeros),
        feet_y=float(walls.feet_y), crest_y=float(walls.crest_y),
        floor=fc.ring(), rim=fc.rim(), runouts=tuple(runouts),
        under_ways=tuple(under_ways), decks=tuple(decks),
        notes=tuple(n for n in notes if n.startswith(tag)))


def _deck_inside(W, walls: StackWalls, decks_all: list, geoms: np.ndarray, dx: np.ndarray,
                 dy: np.ndarray) -> list:
    """The cheap screen before the floor cast: the hard decks reaching over
    the walls' hull, and of them those that may be members — anchored inside
    it at W's AGL (a member stands on the floor, which lies between the
    walls).  ``[(deck, may be a member)]``."""
    import shapely
    hull = wall_hull(walls)
    shapely.prepare(hull)
    over = np.flatnonzero(shapely.intersects(hull, geoms))
    if not len(over):
        return []
    inside = shapely.contains_xy(hull, dx[over], dy[over])
    out = []
    for k, ok in zip(over.tolist(), inside.tolist(), strict=True):
        o = decks_all[k]
        out.append((o, bool(ok) and o.kind == "OBJECT"
                    and abs(float(o.agl_m) - float(W.agl_m)) <= 1e-3))
    return out


def _deck_stacks(airport, objects, cache, law, route_of: RouteOf, taken: _t.Iterable[str] = ()
                ) -> tuple[tuple[DeckStack, ...], list[str]]:
    """``(every deck stack, notes)`` (module doc).  ``route_of(way)``: the
    route through a mapped way (``planar/viaduct_road``'s walk, handed in
    by the planar caller); ``taken``: placements an earlier reader
    claimed."""
    notes: list[str] = []
    if not objects or cache is None or getattr(airport, "dem", None) is None:
        return (), notes
    decks_all = [o for o in objects if _is_deck(o)]
    if not decks_all:
        return (), notes
    used = {str(t) for t in taken}
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    tree = STRtree([d.hard_deck for d in decks_all])
    cand = [o for o in objects if o.kind == "OBJECT" and getattr(o, "plan_bbox", None) is not None]
    if not cand:
        return (), notes
    hit = tree.query([o.plan_bbox for o in cand], predicate="intersects")
    idx = sorted(set(int(i) for i in hit[0]), key=lambda i: str(cand[i].id))
    ctx: "_Ctx | None" = None
    anchors: "_Anchors | None" = None
    out: list[DeckStack] = []
    # the cheapest screen first: a member deck stands anchored on the floor,
    # inside W's own plan, at W's AGL
    import shapely
    dx = np.array([float(d.xy[0]) for d in decks_all])
    dy = np.array([float(d.xy[1]) for d in decks_all])
    dagl = np.array([float(d.agl_m) for d in decks_all])
    dobj = np.array([d.kind == "OBJECT" for d in decks_all])
    geoms = np.array([d.hard_deck for d in decks_all], dtype=object)
    for i in idx:
        W = cand[i]
        if str(W.id) in used:
            continue
        on = dobj & (np.abs(dagl - float(W.agl_m)) <= 1e-3)
        if not on.any() or not shapely.contains_xy(W.plan_bbox.buffer(tol), dx[on], dy[on]).any():
            continue
        walls = read_stack_walls(W, cache, law)
        if isinstance(walls, str):
            continue
        over = _deck_inside(W, walls, decks_all, geoms, dx, dy)
        if not any(ok for _o, ok in over):
            notes.extend(f"{W.id} {str(W.path).rsplit('/', 1)[-1]}: deck {o.id} spans the "
                         f"floor but is no member (anchored off the walls or at another AGL): "
                         f"it keeps its reading" for o, _ok in over if o is not W)
            continue
        ctx = ctx or _Ctx(airport, route_of)
        anchors = anchors or _Anchors(objects)
        st = _one(W, walls, ctx, anchors, cache, airport, law, used, decks_all, notes)
        if st is not None:
            out.append(st)
            used.update(pid for pid, _r in st.members)
    return tuple(out), notes


def _faces(ring: tuple[XY, ...], z0: float, z1: float) -> list:
    """The strip's triangles (a ``[left.., ..right]`` station ring), the
    level linear along its stations from ``z0`` to ``z1``."""
    n = len(ring) // 2
    left, right = ring[:n], tuple(reversed(ring[n:]))
    out = []
    for i in range(n - 1):
        za = z0 + (z1 - z0) * i / max(1, n - 1)
        zb = z0 + (z1 - z0) * (i + 1) / max(1, n - 1)
        la, lb, ra, rb = (*left[i], za), (*left[i + 1], zb), (*right[i], za), (*right[i + 1], zb)
        out += [(la, lb, rb), (la, rb, ra)]
    return out


def _poly(ring) -> "Polygon | None":
    if len(ring) < 3:
        return None
    p = Polygon(ring)
    p = p if p.is_valid else p.buffer(0.0)
    return None if p.is_empty else p


def stack_floors(stacks: _t.Sequence[DeckStack], taken: _t.Iterable[str] = ()
                 ) -> tuple[list, list[str]]:
    """``(ObjectFloor per stack, notes)`` (§3.8): the floor and its
    run-outs as ONE object floor — id ``object_floor:<stack id>``, the
    walls its object, the other members its covers, every member seated
    whole at the stack's zero.  A stack whose member an earlier floor
    reader claimed is left out, with a note."""
    from .object_floor import ObjectFloor
    taken = {str(t) for t in taken}
    out, notes = [], []
    for st in stacks:
        clash = sorted(pid for pid, _r in st.members if pid in taken)
        if clash:
            notes.append(f"{st.id}: member(s) {', '.join(clash)} already a floor's — not cut")
            continue
        fz = st.floor_z
        faces = _faces(st.floor, fz, fz)
        polys = [_poly(st.floor)]
        for ring, z0, z1 in st.runouts:
            faces += _faces(ring, z0, z1)
            polys.append(_poly(ring))
        foot = unary_union([p for p in polys if p is not None])
        if foot.is_empty or not faces:
            notes.append(f"{st.id}: an empty floor — not cut")
            continue
        out.append(ObjectFloor(
            st.floor_ref, st.walls_id, st.walls_resource,
            tuple(pid for pid, _r in st.members if pid != st.walls_id),
            float(st.zero_z), float(fz), foot, np.asarray(faces, float),
            notes=st.notes, seats=tuple((pid, res, float(st.zero_z)) for pid, res in st.members),
            kind="floor", decks=()))
    return out, notes


def _solid_plan(o, cache):
    """The plan of every genuine solid face of placement ``o`` (frame)."""
    import shapely
    comps = cache.genuine(o.resolved) if o.resolved else []
    g = cache.geometry(o.resolved) if o.resolved else None
    if not comps or g is None:
        return None
    v = np.asarray(g.vertices[:, :3], float)
    tris = np.concatenate([c.tris for c in comps])
    aff = _obj8.placement_affine(o.xy, o.heading_deg)
    pts = v[tris][:, :, [0, 2]]
    x = aff[0] * pts[..., 0] + aff[1] * pts[..., 1] + aff[4]
    y = aff[2] * pts[..., 0] + aff[3] * pts[..., 1] + aff[5]
    polys = shapely.polygons(np.stack([x, y], axis=-1))
    return shapely.union_all(polys[shapely.area(polys) > 1e-6])


def _stack_shade(stacks: _t.Sequence[DeckStack], objects, cache, law):
    """The planar region no pad takes (§3.9: a member's footprint is no
    pad): each stack's floor and run-outs, its walls' whole solid plan, its
    decks' plates and every other member's plan."""
    if not stacks:
        return None
    by_id = {str(o.id): o for o in objects}
    t = 0.5 * float(law.tables.structures.tunnel.object.wall_face_max_thickness_m)
    parts = []
    for st in stacks:
        parts += [p for p in [_poly(st.floor), *(_poly(r) for r, _a, _b in st.runouts)] if p]
        for pid, _r in st.members:
            o = by_id.get(pid)
            if o is None:
                continue
            if pid == st.walls_id:
                plan = _solid_plan(o, cache)
                if plan is not None:
                    parts.append(plan.buffer(t))
            elif _is_deck(o):
                parts.append(o.hard_deck)
            elif getattr(o, "plan_bbox", None) is not None:
                parts.append(o.plan_bbox)
    got = unary_union(parts)
    return None if got.is_empty else got


def _rewrite_ways(ways: _t.Sequence, stacks: _t.Sequence[DeckStack]) -> tuple:
    """``ways`` with every stack deck's carried stretch a mapped bridge
    (``deck_carry.bridge_stretches``, §3.5)."""
    cuts: dict[int, list] = {}
    for st in stacks:
        for d in st.decks:
            rect = Polygon(d.ring).minimum_rotated_rectangle
            for wid in d.carried:
                cuts.setdefault(int(wid), []).append((d.object_id, rect))
    return bridge_stretches(ways, cuts) if cuts else tuple(ways)


def attach_stacks(airport, objects, cache, law, route_of: RouteOf,
                  notes_out: "list | None" = None):
    """``airport`` with its deck stacks (§3.1): ``_deck_stacks``,
    ``_stack_shade`` and the carried stretches rewritten in ``osm_ways`` —
    always derived from the ways AS MAPPED (``osm_ways_mapped``), so
    running it twice gives the same airport.  With no stack the airport's
    ways are left as they are."""
    import dataclasses as _dc
    mapped = getattr(airport, "osm_ways_mapped", None) or airport.osm_ways
    base = airport if mapped is airport.osm_ways else _dc.replace(airport, osm_ways=mapped)
    stacks, notes = _deck_stacks(base, objects, cache, law, route_of)
    if notes_out is not None:
        notes_out.extend(notes)
    if not stacks:
        if getattr(airport, "osm_ways_mapped", None) is None:
            return airport
        return _dc.replace(airport, osm_ways=mapped, osm_ways_mapped=None, deck_stacks=(),
                           stack_shade=None)
    return _dc.replace(airport, osm_ways=_rewrite_ways(mapped, stacks), osm_ways_mapped=mapped,
                       deck_stacks=stacks, stack_shade=_stack_shade(stacks, objects, cache, law))


def log_line(icao: str, stacks: _t.Sequence[DeckStack], seconds: float | None = None) -> str:
    """One line for the build log."""
    t = f" ({seconds:.3f} s)" if seconds is not None else ""
    if not stacks:
        return f"[{icao}] [deck-stack] 0 stacks{t}"
    parts = [f"{st.id}: {len(st.members)} members, {st.levels} level(s), zero {st.zero_z:.2f} "
             f"(spread {st.zero_spread_m:.2f}), floor {st.floor_z:.2f}" for st in stacks]
    return f"[{icao}] [deck-stack] {len(stacks)} stack(s){t}: " + "; ".join(parts)

