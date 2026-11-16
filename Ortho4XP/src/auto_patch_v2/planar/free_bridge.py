"""THE FREE BRIDGE'S READ (#2065; spec ``2065-bridge-class-A1.md`` §A4
S1 / S2 / S4): the thin ``planar`` caller of the positive witness
(``airport/bridge_witness``), like ``planar/deck_stack_attach``.

* PACK STAGE (:func:`attach_free_bridges`, after ``attach_deck_stacks``):
  every frame (``deck_bridge._frames``: one anchor, one heading) holding a
  ``flag`` / ``signature`` deck is read W1-W7 + W4b; a deck of a deck stack,
  a plate with apt.dat pavement or a runway on it (``deck_stack._Airside``:
  class A's witness) and an all-deck frame (22d / 22p keep it,
  ``placement_family.frame_is_bridge``, or a deck and the structure riding
  it, ``deck_riders``) are read as KEPT bridges.  W1 reads ``highway`` /
  ``railway`` routes and the airport's own apt.dat ground routes
  (``airport/ground_route_ways``, #2062 R3b E: over a ``flag`` deck their
  bridge stretch is the part inside its plate).  The decks the classifier calls ``free_bridge``
  (``airport/bridge_class``) become ``Airport.free_bridges``, one
  :class:`~..model.free_bridge.FreeBridge` per group of touching decks.
  A deck no mapped way carries is a KEPT candidate by its join (#2090 B2,
  all-deck frames) or, in any frame, by its CROSSING (#1718 B1,
  :func:`_overpass_witness`: a road beneath at the overpass clearance and
  the stub witnesses on its own axis; the planar overpass read seats it).
* PLANAR STAGE (:func:`admitted`): the readers ahead of a free bridge in the
  class order that only the planar stage holds take theirs first — a frame
  holding a pack object cut (10-26d), a frame of a hard-deck bridge
  (``PlanarMap.decks``, class A) — and a frame with a body beside a
  building is refused (22n, ``deck_bridge._beside_a_building``, W6's
  building half, which reads the classification): ONE test per bridge
  against the UNION of the rings of every free deck of its frame (A2).
  R3 mints free stacks from ``PlanarMap.free_bridges`` (admitted), never
  ``Airport.free_bridges``.  ``planar/overpass_deck``
  then takes the kept decks as ``taken`` (S4).
* PUBLICATION (``model/free_bridge.published``): each kept deck's route
  ends in ``(lat, lon)`` for the rebake plan (``pipeline/rebake_inputs``).

One note per deck read or refused, with the witness that decided it.
Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..airport import bridge_frame as _bf
from ..airport import bridge_witness as _bw
from ..geom.rotated_rect import rotated_rectangle
from ..model.free_bridge import FREE_PREFIX, OVERPASS_PREFIX, FreeBridge, FreeDeck, FreeEnd

__all__ = ["attach_free_bridges", "read_bridges", "bridges_of", "admitted", "plated",
           "planar_stacks", "log_line"]


def _ring(o) -> Polygon:
    from ..airport.rebake_plan import _deck_ring_xy
    p = Polygon(_deck_ring_xy(o))
    if not p.is_valid:
        p = p.buffer(0)
    if p.geom_type != "Polygon":
        p = max(getattr(p, "geoms", [p]), key=lambda g: g.area)
    return p


def _name(o) -> str:
    return f"{o.id} {str(o.path).rsplit('/', 1)[-1]}"


def _routes(ways: _t.Sequence) -> list:
    """W1's ways: ``highway`` / ``railway`` (a taxiway route is class A's)."""
    return [w for w in ways if len(w.points) >= 2
            and ("highway" in (w.tags or {}) or "railway" in (w.tags or {}))]


class _Read:
    """The airport's ways, ground, water and W4b reader, once per read."""

    def __init__(self, airport, objects, cache, law) -> None:
        from ..airport.dem import dem_z_many
        self.law, self.cache = law, cache
        self.ways = _routes(getattr(airport, "osm_ways_mapped", None) or airport.osm_ways)
        # #2062 R3b E: the airport's own ground routes are W1 routes too
        from ..airport.ground_route_ways import ground_route_ways
        self.ground_routes = ground_route_ways(airport)
        #: the road-beneath read's ways, as ``planar/overpass_deck`` reads them
        self.all_ways = [w for w in airport.osm_ways or () if len(w.points) >= 2]
        dem = getattr(airport, "dem", None)
        self.dem = dem
        self.ground = None if dem is None else (
            lambda xs, ys: dem_z_many(dem, np.asarray(xs, float), np.asarray(ys, float)))
        normal = float(law.tables.structures.bridge.deck_plate_normal_y_min)
        self.by_id = {str(o.id): o for o in objects}
        placed = [(str(o.id), self.geometry(o), o.xy, float(o.heading_deg or 0.0),
                   getattr(getattr(o, "plan_bbox", None), "bounds", None))
                  for o in objects if o.resolved]
        self.under = _bf.Under(placed, self._datum, normal)

    def geometry(self, o):
        return self.cache.geometry(o.resolved) if o.resolved else None

    def _datum(self, oid: str) -> tuple[float, bool]:
        o = self.by_id[oid]
        g = 0.0 if self.ground is None else float(self.ground([o.xy[0]], [o.xy[1]])[0])
        ok = self.ground is not None and math.isfinite(g)
        return (g if ok else 0.0) + float(o.agl_m or 0.0), ok

    def water(self, box: tuple) -> list:
        fn = getattr(self.dem, "water_geometry", None)
        w = fn(box) if fn is not None else None
        return [] if w is None or w.is_empty else [w]


def _frame_witness(decks: list, frame: list, rd: _Read) -> dict:
    """W1-W7 + W4b over one frame (``bridge_witness.frame_witness``)."""
    law = rd.law
    normal = float(law.tables.structures.bridge.deck_plate_normal_y_min)
    plates = {}
    for d in decks:
        up = _bw.up_faces(_bf.solid_faces(rd.geometry(d), d.xy, d.heading_deg), normal)
        plates[str(d.id)] = (_ring(d), up, d.deck_kind)
    # #2062 R3b E: over a FLAG deck an apt.dat ground route's bridge stretch
    # is the part inside its plate (``airport/ground_route_ways``)
    from ..airport.ground_route_ways import bridged
    ways = list(rd.ways) + [w for r, _u, k in plates.values() if k == "flag"
                            for w in bridged(rd.ground_routes, r)]
    if not _bw.any_route([r for r, _u, _k in plates.values()], ways, law, rd.ground):
        return {k: _bw.Witness(None, failed="W1 route: no mapped route") for k in plates}
    b = np.array([r.bounds for r, _u, _k in plates.values()])
    box = (b[:, 0].min() - 2.0, b[:, 1].min() - 2.0, b[:, 2].max() + 2.0, b[:, 3].max() + 2.0)
    placed = {str(q.id): _bf.solid_faces(rd.geometry(q), q.xy, q.heading_deg) for q in frame}
    faces = _bf.faces_in_box(placed.values(), box)
    bodies = {k: _bf.body_points(f) for k, f in placed.items() if len(f)}
    own = str(decks[0].id)
    return _bw.frame_witness(plates, faces, bodies, ways, law, rd.ground, rd.water(box),
                             under=rd.under.for_unit(own, frozenset(placed)))


def _end(e) -> FreeEnd:
    line = tuple((float(x), float(y)) for x, y in (e.line or (e.point,)))
    return FreeEnd(line, float(e.top), (float(e.out[0]), float(e.out[1])), bool(e.land),
                   0.0 if math.isnan(e.run_on) else float(e.run_on))


def bridges_of(rings: _t.Mapping[str, Polygon], witnesses: _t.Mapping[str, _t.Any],
               free: _t.Collection[str], members: _t.Sequence[str], touch_m: float
               ) -> tuple[FreeBridge, ...]:
    """The free decks ``free`` of one frame (their ``rings`` and
    ``witnesses``) as bridges: decks whose rings come within ``touch_m``,
    transitively, are ONE bridge (22o); ``members`` every placement of the
    frame."""
    ids = sorted(free)
    root = {k: k for k in ids}

    def find(k: str) -> str:
        while root[k] != k:
            root[k] = root[root[k]]
            k = root[k]
        return k
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if rings[a].distance(rings[b]) <= touch_m:
                root[find(b)] = find(a)
    groups: dict[str, list[str]] = {}
    for k in ids:
        groups.setdefault(find(k), []).append(k)
    out = []
    for g in groups.values():
        decks = []
        for k in g:
            w = witnesses[k]
            decks.append(FreeDeck(k, tuple((float(x), float(y))
                                           for x, y in rings[k].exterior.coords[:-1]),
                                  tuple(int(x) for x in (w.route.ways if w.route else ())),
                                  tuple(_end(e) for e in w.ends), str(w.joined or "")))
        out.append(FreeBridge(FREE_PREFIX + g[0], tuple(members), tuple(decks)))
    return tuple(out)


@_dc.dataclass(frozen=True)
class _Frame:
    """A frame as ``frame_is_bridge`` reads a plan unit (its members)."""

    members: tuple = ()


def _bridge_frame(frame, cache) -> bool:
    """Does the object stage seat this frame as ONE bridge on its deck's own
    datum: every member a deck (``placement_family.frame_is_bridge``) or a
    deck and the structure riding it (``deck_riders.objects_ride``, #2086)?"""
    from ..airport.deck_riders import objects_ride
    from ..airport.placement_family import frame_is_bridge
    return frame_is_bridge(_Frame(tuple(frame))) or objects_ride(
        frame, [str(getattr(o, "deck_kind", "") or "") for o in frame], cache)


def _read_free_bridges(airport, objects, cache, law
                       ) -> tuple[tuple[FreeBridge, ...], tuple[FreeBridge, ...], list[str]]:
    """``(every free bridge of the pack, every KEPT bridge — the witness-
    holding decks of all-deck frames (#2065 A3 rule 1, RULINGS 2026-11-14d),
    one note per deck read)`` (module doc, pack stage)."""
    from ..airport.bridge_class import DeckFacts, classify
    from ..airport.deck_stack import _Airside
    from .deck_bridge import _frames
    if not objects or cache is None or law is None or getattr(airport, "frame", None) is None:
        return (), (), []
    from ..model.deck_stack import TRENCH
    st = law.tables.structures
    stacked = {str(pid) for s in getattr(airport, "deck_stacks", ()) or ()
               if s.kind == TRENCH for pid, _r in s.members}
    airside = _Airside(airport)
    rd: "_Read | None" = None
    out: list[FreeBridge] = []
    kept: list[FreeBridge] = []
    notes: list[str] = []
    for dks, frame in _frames(objects, float(st.tunnel.object.cover_placement_tol_m)):
        decks = [d for d in dks if d.deck_top_z is not None and str(d.id) not in stacked
                 and not airside.meets(d.hard_deck)]
        if not decks:
            continue
        # an all-deck frame keeps 22d / 22p's seat; its witness-holding decks
        # are KEPT bridges, their ends graded (#2065 A3 rule 1) — and so does
        # a deck with the structure riding it (#2086, ``deck_riders``)
        all_deck = _bridge_frame(frame, cache)
        rd = rd or _Read(airport, objects, cache, law)
        wit = _frame_witness(decks, frame, rd)
        free = []
        for d in decks:
            v = classify(DeckFacts(witness=wit[str(d.id)]))
            if v.cls == "free_bridge":
                free.append(str(d.id))
            if not wit[str(d.id)].failed.startswith("W1 route"):
                cls = ("kept_bridge (all-deck frame)" if all_deck and v.cls == "free_bridge"
                       else v.cls)
                notes.append(f"{_name(d)}: {cls} ({v.reason})")
        if free:
            (kept if all_deck else out).extend(
                bridges_of({str(d.id): _ring(d) for d in decks}, wit, free,
                           [str(q.id) for q in frame], float(st.placement.footprint_touch_m)))
        routeless = [d for d in decks if str(d.id) not in free
                     and wit[str(d.id)].failed.startswith("W1 route")]
        if all_deck:
            more, ns = _join_witness(routeless, frame, airport, law, rd)
            kept.extend(more)
            notes += ns
            joined = {d.object_id for fb in more for d in fb.decks}
            routeless = [d for d in routeless if str(d.id) not in joined]
        more, ns = _overpass_witness(dks, routeless, frame, rd)
        kept.extend(more)
        notes += ns
    return tuple(out), tuple(kept), notes


def _overpass_witness(dks, routeless, frame, rd: _Read) -> tuple[list[FreeBridge], list[str]]:
    """#1718 B1 / B2: a deck no mapped way carries (``routeless``: W1
    fails) is a KEPT candidate by its CROSSING when it holds the pack-stage
    half of the road-overpass witness (``planar/overpass_deck.
    road_crossings`` over the frame's decks ``dks``: a mapped non-bridge
    highway, not its own route, crosses a piece and the plate stands at
    least ``clearance_minimum_m`` over it there) — it is the frame's first
    deck, the one the overpass read seats — and the stub witnesses on its
    own axis (``bridge_witness.axis_witness``: W3, W4, W6, W4b; the crossing
    is its W5).  Its ends are its axis's (:func:`_axis_ends`, route
    :data:`AXIS_STUB`), ``under`` the road beneath's stations its zero is
    read on (``airport/bridge_stack._overpass_one``)."""
    d = dks[0] if dks else None
    if d is None or str(d.id) not in {str(q.id) for q in routeless}:
        return [], []
    from .overpass_deck import road_crossings
    clear = float(rd.law.tables.structures.bridge.clearance_minimum_m)
    _top, pieces = road_crossings(dks, rd.cache, rd.all_ways, rd.law)
    held = [(st, ids, at) for _p, st, ids, at in pieces if at is not None and at >= clear]
    if not held:
        return [], []
    tag = f"{_name(d)}: no mapped route; a road crosses beneath (ways " \
          f"{sorted({i for _s, ids, _a in held for i in ids})}, plate y " \
          f"{max(a for _s, _i, a in held):+.2f})"
    why = _axis_holds(d, frame, rd)
    ends = _axis_ends(d) if not why else None
    if ends is None:
        return [], [f"{tag} — not a kept candidate: {why or 'no axis'} (#1718 B2)"]
    oid = str(d.id)
    under = tuple((float(x), float(y)) for st, _i, _a in held for x, y in st)
    fd = FreeDeck(oid, tuple((float(x), float(y)) for x, y in _ring(d).exterior.coords[:-1]),
                  (), ends, AXIS_STUB + oid, under)
    return ([FreeBridge(OVERPASS_PREFIX + oid, tuple(str(q.id) for q in frame), (fd,))],
            [f"{tag} — a kept candidate by its crossing (#1718 B1)"])


def _axis_holds(d, frame, rd: _Read) -> str:
    """``bridge_witness.axis_witness`` for deck ``d`` of ``frame`` (its
    plate, the frame's faces and bodies, W4b's pack objects)."""
    normal = float(rd.law.tables.structures.bridge.deck_plate_normal_y_min)
    ring = _ring(d)
    up = _bw.up_faces(_bf.solid_faces(rd.geometry(d), d.xy, d.heading_deg), normal)
    placed = {str(q.id): _bf.solid_faces(rd.geometry(q), q.xy, q.heading_deg) for q in frame}
    x0, y0, x1, y1 = ring.bounds
    faces = _bf.faces_in_box(placed.values(), (x0 - 2.0, y0 - 2.0, x1 + 2.0, y1 + 2.0))
    bodies = {k: _bf.body_points(f) for k, f in placed.items() if len(f) and k != str(d.id)}
    return _bw.axis_witness(ring, up, faces, bodies, rd.law,
                            under=rd.under.for_unit(str(d.id), frozenset(placed)))


#: #2090 B2: a deck read only by its join is a stub along its own axis
AXIS_STUB = "axis:"


def _axis_ends(d, n: int = 5) -> "tuple[FreeEnd, FreeEnd] | None":
    """The deck's two END LINES along its own axis: the short sides of its
    plan's minimum rectangle, ``n`` stations each, the outward tangent from
    the rectangle's middle; the top the deck's (``deck_top_y``; the kept
    read replaces it by the top at each end)."""
    r = rotated_rectangle(_ring(d))
    if r.geom_type != "Polygon":
        return None
    c = list(r.exterior.coords)[:4]
    sides = sorted(range(4), key=lambda k: math.dist(c[k], c[(k + 1) % 4]))[:2]
    mid = (sum(p[0] for p in c) / 4.0, sum(p[1] for p in c) / 4.0)
    top = float(d.deck_top_z - getattr(d, "anchor_z", 0.0) - float(d.agl_m or 0.0)) \
        if getattr(d, "anchor_z", None) is not None else 0.0
    out = []
    for k in sorted(sides):
        a, b = c[k], c[(k + 1) % 4]
        st = tuple((a[0] + (b[0] - a[0]) * t / (n - 1), a[1] + (b[1] - a[1]) * t / (n - 1))
                   for t in range(n))
        m = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        L = math.dist(m, mid) or 1.0
        out.append(FreeEnd(st, top, ((m[0] - mid[0]) / L, (m[1] - mid[1]) / L), True))
    return out[0], out[1]


def _join_witness(decks, frame, airport, law, rd) -> tuple[list[FreeBridge], list[str]]:
    """#2090 B2: an all-deck hard-deck frame's deck no mapped way carries is
    a KEPT bridge when an end of it reaches an AGP follower's floor
    (``airport/agp_deck_join``) — a candidate here, kept by
    ``bridge_stack._kept_one`` only where the end JOINS; its other end is
    read as a stub's (the axis ray)."""
    groups = [g for g in getattr(airport, "agp_groups", ()) or () if g.governor]
    if not decks or not groups:
        return [], []
    from ..airport.agp_deck_join import DeckFloors
    floors = DeckFloors(airport, law)
    out, notes = [], []
    for d in decks:
        ends = _axis_ends(d)
        if ends is None or not any(floors.near(e.stations) for e in ends):
            continue
        oid = str(d.id)
        fd = FreeDeck(oid, tuple((float(x), float(y)) for x, y in _ring(d).exterior.coords[:-1]),
                      (), ends, AXIS_STUB + oid)
        out.append(FreeBridge(FREE_PREFIX + oid, tuple(str(q.id) for q in frame), (fd,)))
        notes.append(f"{_name(d)}: no mapped route; an end reaches an AGP follower's floor — "
                     "a kept candidate by its join (#2090 B2)")
    return out, notes


def _with_agp_groups(airport, law) -> tuple[_t.Any, list[str]]:
    """``(airport with agp_groups, notes)`` (#2090 A1, ``airport/agp_group``);
    a record already read is kept."""
    import time
    if getattr(airport, "agp_groups", ()) or law is None:
        return airport, []
    from ..airport.agp_group import attach_agp_groups, log_line
    t0, notes = time.perf_counter(), []
    airport = attach_agp_groups(airport, law, notes)
    # #2090 C1: each governed group's plates (its followers' ground floors)
    from ..airport.agp_plates import with_plates
    airport = with_plates(airport, law, notes)
    return airport, [log_line("", airport.agp_groups, time.perf_counter() - t0)
                     .split("] ", 1)[-1]] + notes


def read_bridges(airport, objects, cache, law) -> tuple[_t.Any, tuple, list[str]]:
    """``(airport with free_bridges, kept_bridges and their stacks, every
    bridge's end read — minted or not, notes)``: :func:`_read_free_bridges`,
    then each bridge's zero and land-end states (#2065 A3,
    ``airport/bridge_stack``); a bridge with a GRADED end is minted a stack
    and the ways rewritten (``airport/deck_stack.with_bridge_stacks``).  A
    free bridge rule 10 refuses leaves ``free_bridges`` (today's path)."""
    from ..airport.bridge_stack import bridge_stacks, log_lines
    from ..airport.deck_stack import with_bridge_stacks
    # #2090 A1: the AGP groups FIRST — the deck joins read them
    airport, notes = _with_agp_groups(airport, law)
    got, kept, more = _read_free_bridges(airport, objects, cache, law)
    notes += more
    if not (got or kept or getattr(airport, "free_bridges", ())
            or getattr(airport, "kept_bridges", ()) or getattr(airport, "agp_groups", ())):
        return with_bridge_stacks(airport, (), law), (), notes
    airport = _dc.replace(airport, free_bridges=got, kept_bridges=kept)
    stacks, every, refused, more = bridge_stacks(airport, objects, cache, law)
    notes += more + [ln.split("] ", 2)[-1] for ln in log_lines("", every)]
    if refused:
        airport = _dc.replace(airport, free_bridges=tuple(
            fb for fb in got if fb.id not in refused))
    airport = _with_deck_joins(airport, stacks)
    # #2062 R5 E′2: the kept reads not minted stay candidates -- a ramp the
    # deck carries a stop over keeps one at the planar stage
    from ..model.deck_stack import KEPT
    minted = {s.id for s in stacks}
    airport = _dc.replace(airport, kept_candidates=tuple(
        s for s in every if s.kind == KEPT and s.id not in minted
        and not str(s.bridge).startswith(OVERPASS_PREFIX)))
    return with_bridge_stacks(airport, stacks, law), every, notes


def _with_deck_joins(airport, stacks) -> _t.Any:
    """#2090 B1: each AGP group's ``deck_joins`` — the joins of the stacks
    whose zero rides its datum."""
    groups = getattr(airport, "agp_groups", ()) or ()
    joins = [j for st in stacks for j in getattr(st, "joins", ()) or ()]
    if not groups or not joins:
        return airport
    return _dc.replace(airport, agp_groups=tuple(
        _dc.replace(g, deck_joins=tuple(j for j in joins if j.group == g.id))
        for g in groups))


def attach_free_bridges(airport, objects, cache, law, notes_out: "list | None" = None):
    """``airport`` with its free and kept bridges read and their stacks
    minted (:func:`read_bridges`)."""
    airport, _every, notes = read_bridges(airport, objects, cache, law)
    if notes_out is not None:
        notes_out.extend(notes)
    return airport


def admitted(bridges: _t.Sequence[FreeBridge], objects, classification, airport,
             decks=(), cut_objects=()) -> tuple[tuple[FreeBridge, ...], list[str]]:
    """``(the free bridges no earlier planar reader takes, notes)`` (module
    doc, planar stage): ``decks`` the hard-deck bridges read
    (``DeckBridge.members``), ``cut_objects`` every pack object cut's
    placement ids."""
    if not bridges:
        return (), []
    from .deck_bridge import CellRoles, _beside_a_building
    roles = CellRoles(classification, airport) if classification is not None else None
    hard = {str(m) for db in decks or () for m in (*db.members, db.object_id)}
    cut = {str(o) for o in cut_objects or ()}
    by_id = {str(o.id): o for o in objects or ()}
    # 22n reads the UNION of every free deck's ring of a frame (A2): in a
    # bridge of several decks each deck's bodies stand "outside" the others
    frame_rings: dict[frozenset, list] = {}
    for fb in bridges:
        frame_rings.setdefault(frozenset(fb.members), []).extend(
            Polygon(d.ring) for d in fb.decks)
    out, notes = [], []
    for fb in bridges:
        mem = set(fb.members)
        why = ""
        if mem & cut:
            why = "its frame holds a pack object cut (10-26d): cut_deck"
        elif mem & hard:
            why = "its frame is a hard-deck bridge's (class A): airside_hard_deck"
        elif roles is not None:
            frame = [by_id[m] for m in fb.members if m in by_id]
            if _beside_a_building(frame, unary_union(frame_rings[frozenset(fb.members)]),
                                  roles):
                why = "W6 free frame: a body stands beside a building (22n): attached_bridge"
        if why:
            notes.append(f"{fb.id}: not a free bridge -- {why}")
            continue
        out.append(fb)
        notes.append(f"{fb.id}: a free bridge of {len(fb.decks)} deck(s) "
                     f"{list(fb.deck_ids())}; its zero at its land ends (RULINGS 2026-10-22m)")
    return tuple(out), notes


def plated(bridges: _t.Sequence[FreeBridge], basins=(), objects=()
           ) -> tuple[tuple[FreeBridge, ...], list[str]]:
    """``(the free bridges no deck of which carries a split-level or walled
    plate, notes)`` (#2065 A3 rule 1: A1's ``plated_deck``, OTHH B05 — listed,
    nothing built, owner Q3 (a); its plate's reader seats it).  Its stack,
    if it had one, is dropped by :func:`planar_stacks`."""
    if not bridges:
        return (), []
    split = {str(m) for b in basins or () if getattr(b, "kind", "") == "split_level"
             for m in (*getattr(b, "member_ids", ()), getattr(b, "witness_id", ""))}
    walled = {str(o.id) for o in objects or () if getattr(o, "walled_plate", None) is not None}
    out, notes = [], []
    for fb in bridges:
        hit = sorted(set(fb.deck_ids()) & (split | walled))
        if hit:
            notes.append(f"{fb.id}: plated_deck {hit} (split-level / walled plate) — listed, "
                         "nothing graded (owner Q3 (a))")
            continue
        out.append(fb)
    return tuple(out), notes


def planar_stacks(stacks, free: _t.Sequence[FreeBridge], overpasses: _t.Collection[str] = (),
                  candidates=(), carried: "_t.Mapping[str, tuple[str, ...]] | None" = None
                  ) -> tuple[tuple, list[str]]:
    """``(the free / kept stacks the planar stage keeps, notes)`` (#2065 A3
    C2 N2, rule 3): a FREE stack only of a bridge in ``free`` (admitted, no
    plated deck); a stack with no graded end is dropped.  A free bridge whose
    stack is dropped here is noted ``free_stack_refused_at_planar``.  A
    graded end's path entering a lot piece is graded like any other (owner
    2026-11-14T18:12Z drops RULINGS 2026-11-14f (4)'s hold: only a standing
    face read at the pack stage holds an end, ``airport/bridge_end_state``).
    A stack KEPT BY ITS CROSSING (#1718 B3) stands only where the planar
    overpass read seats its deck (``overpasses``: the road overpasses'
    placement ids): its zero is that seat.

    #2062 R5 E′2: a KEPT stack -- minted, or one of the pack stage's
    ``candidates`` (``Airport.kept_candidates``) -- whose deck a ramp
    carries a stop under (``carried``: deck object id -> the tunnel ids,
    ``Tunnel.carried``) is kept OVER THE FLOOR (``DeckStack.over_floor``),
    graded end or not."""
    from ..model.deck_stack import FREE, KEPT, TRENCH
    ok = {str(fb.id) for fb in free}
    seated = {str(o) for o in overpasses}
    carried = dict(carried or {})
    out, notes = [], []
    minted = {st.id for st in stacks}
    for st in (*stacks, *(c for c in candidates or () if c.id not in minted)):
        if st.kind == TRENCH:
            continue
        over = tuple(sorted({t for d in st.decks for t in carried.get(str(d.object_id), ())}))
        if st.kind == KEPT and over:
            out.append(_dc.replace(st, over_floor=over))
            notes.append(f"{st.id}: kept over the floor of {list(over)} (#2062 R5 E′2): "
                         f"rows its {[e.side + ' ' + e.state for e in st.ends]} ends")
            continue
        if st.id not in minted:
            continue
        if st.bridge.startswith(OVERPASS_PREFIX) \
                and st.bridge[len(OVERPASS_PREFIX):] not in seated:
            notes.append(f"{st.id}: kept by its crossing, but the planar stage reads no road "
                         "overpass of its deck — no stack (#1718 B3)")
            continue
        if st.kind == FREE and st.bridge not in ok:
            notes.append(f"{st.id}: free_stack_refused_at_planar (its bridge was not admitted "
                         "or carries a plate)")
            continue
        if not st.graded_ends() and not getattr(st, "datum_group", ""):
            notes.append(f"{st.id}: no GRADED end at the planar stage — no stack"
                         + ("; free_stack_refused_at_planar" if st.kind == FREE else ""))
            continue
        out.append(st)
    return tuple(out), notes


def log_line(icao: str, bridges: _t.Sequence[FreeBridge], seconds: "float | None" = None) -> str:
    """The build log's one line on the free bridges read."""
    took = "" if seconds is None else f" in {seconds:.2f} s"
    decks = [d.object_id for fb in bridges for d in fb.decks]
    return (f"[{icao}] free bridges (#2065): {len(bridges)} bridge(s), {len(decks)} deck(s)"
            f"{took}" + (f" {decks}" if decks else ""))
