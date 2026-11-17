"""A ROAD DECK OVER AN EDGE BRIDGE'S TRENCH IS LEVEL WITH THE AIRSIDE ABEAM
(owner RULINGS 2026-10-28d Q211 a; 2026-10-27r "the top of the objects
flush with the airside surface"; #1138).

Where a pack models a bridge by its edges (``planar/bridge_span``), the
road the bridge carries beside the airside pavement — a mapped bridge way
over the trench, a terrain deck (spec §33 (4), ``Tunnel.decks``) — is the
bridge's own slab: it stands at the level of the airside pavement edge
abeam it and follows whatever that pavement does over the bridge.  It is
RELATIONAL, never a pre-solve deck height: each deck vertex takes an
EQUALITY to the nearest airside pavement vertex — stated as a two-sided
PAIR of one-sided rows under a head ``[design] hard_rulings`` names, so it
is a CONSTRAINT of the active set (the ``tunnel.mouth_depth_m`` idiom,
``constraints/structures``): MEASURED on the KATL capture, the one-way
equality at the law weight left the deck 1.8-7.8 m under the taxiway, the
road's DEM fit over the bare-earth trench winning the contest.  The road
deck has no other hard row there (its end ties stand down over an edge
trench, ``constraints/structures``), so the taxiway is never pulled.

THE SPAN TOO (RULINGS 28d Q212 "lifted to deck level"; owner sim read
2026-10-28T14:26Z points 4 / 5: "Runway edge should be flat and paved to
the edge of the tunnel object, no gap between them"): every vertex inside
an edge bridge's COVER (``Tunnel.edge_covers``) and on its BACK — the rim
stand-off band along the back line, the top edge of the objects — that is
on no trench floor takes the same pair to its nearest airside vertex —
measured on the KATL capture, ``tunel_A`` south's span (a pack parking lot)
stood 2.9 m under to 1.8 m over the runway edge abeam.

TO THE TOP EDGE (#1632, owner sim read of 1.0.444: "the ground should be
flat airside all the way to the top edge of those tunnel bridge objects").
The span stopped the rim stand-off short of the back, and the trench's rim
along the back was pinned at its own DEM (``constraints/structures``): on
the KATL capture the rim stood 8.8-20.7 m under the cover 0.2-0.7 m away,
and a road piece inside the cover kept its ramp to the bare-earth DEM
11 m down, its hard ceiling winning the pair.  The governed vertices now
reach the back, and :func:`release_governed` withdraws the rows that held
them elsewhere — the rim's DEM pin and the road ramp's target and ceiling
— so the pair is the one level they carry.

A HARD-DECK BRIDGE (``planar/deck_bridge``; owner RULINGS 2026-10-30a (1))
has ONE zero, flush at both end lines: per object, every end line's seat set
is held to the first one's by the deck-top difference between them —
``mean z[S_k] − mean z[S_0] = top_k − top_0`` — a two-sided pair under
:data:`RIGID` (``[design] hard_rulings``).  The decks are the map's
(``PlanarMap.decks``, deck redesign §1), whether or not a trench runs under
one, and each station of an end line its anchor holds stands at that
anchor's level (:func:`_station_rows`).  The taxiway on each side is
graded to the deck; the deck never tilts or shears.  The ground under the
deck that is no trench floor — the bank's top along its edge — takes the
span pair to its nearest seat (:func:`_deck_span`).
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import family
from ..model.airport import Airport
from ..model.constraints import Band, Linear, Pin, Row, Source
from ..model.planar import PlanarMap
from ..model.structures import DECK_GROUND_REF, deck_reach

__all__ = ["edge_deck_rows", "release_governed", "deck_floor", "GEN", "RULING", "RIGID"]

GEN = "edge_deck"
#: the ruling head (``[design] hard_rulings``)
RULING = "roads.edge bridge deck level with the airside abeam"
#: the hard-deck bridge's rigid row's head (``[design] hard_rulings``)
RIGID = ("structures.hard-deck bridge: one zero, flush at both end lines "
         "(RULINGS 2026-10-30a (1))")


def airside_nearest(planar: PlanarMap, law: Law):
    """``nearest(x, y) -> vertex id``: the airside pavement vertex nearest
    a point (``roads.stage_one_vertices``), or ``None`` with no airside."""
    from .geometry import nearest_vertex_fn
    from .roads import stage_one_vertices
    return nearest_vertex_fn(planar, stage_one_vertices(planar, law))


def edge_deck_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every terrain-deck vertex over an edge bridge's trench, held equal to
    its nearest airside pavement vertex (module doc)."""
    tunnels = [t for t in getattr(planar, "structures", ()) or ()
               if getattr(t, "edge_back", ()) and (
                   getattr(t, "edge_covers", ()) or any(d.datum != "deck_top" for d in t.decks))]
    decked = [t for t in getattr(planar, "structures", ()) or ()
              if getattr(t, "deck_bridge", "")]
    floor_rows = _floor_deck_rows(planar, law)
    if not tunnels and not getattr(planar, "decks", ()):
        return floor_rows
    nearest = airside_nearest(planar, law)
    if nearest is None:
        return floor_rows
    rows: list[Row] = _deck_rows(planar, law, decked, nearest.air) \
        if getattr(planar, "decks", ()) else []
    rows.extend(floor_rows)
    for tn in tunnels:
        src = Source(GEN, RULING, (tn.id, tn.portal, "span"))
        for v in _span_vertices(planar, law, tn) - nearest.air:
            a = nearest(*planar.vertices[v].xy)
            rows.append(Linear(((v, 1.0), (a, -1.0)), None, 0.0, src))
            rows.append(Linear(((v, -1.0), (a, 1.0)), None, 0.0, src))
    faces_by_ref: dict[str, list] = {}
    for f in planar.faces.values():
        faces_by_ref.setdefault(f.ref, []).append(f)
    for tn in tunnels:
        for d in tn.decks:
            if d.datum == "deck_top":
                continue
            vs = sorted({v for f in faces_by_ref.get(d.ref, ())
                         for v in planar.ring_vertices(f.ring)} - nearest.air)
            src = Source(GEN, RULING, (tn.id, tn.portal, f"osm:{d.way}"))
            for v in vs:
                a = nearest(*planar.vertices[v].xy)
                rows.append(Linear(((v, 1.0), (a, -1.0)), None, 0.0, src))
                rows.append(Linear(((v, -1.0), (a, 1.0)), None, 0.0, src))
    return rows


#: the role of an edge trench's FLOOR: never part of its span (the rim
#: along the back is — it is the objects' top edge)
_FLOOR_ROLES = frozenset({"tunnel_ramp"})
#: ``runway_profile.RUNWAY_FAMILY`` (not imported: its closure is not this
#: generator's stage key)
_RUNWAY_FAMILY = frozenset({"runway", "runway_crossing"})


def _deck_rows(planar: PlanarMap, law: Law, tunnels, air) -> list[Row]:
    """The pack decks' spans, station rows and rigid rows (module doc), per
    object of ``PlanarMap.decks`` (``constraints/deck_lines``) — a deck no
    corridor runs under included; ``tunnels``: the trenches under one."""
    from .deck_lines import end_lines, plate_of
    flush = float(law.tables.structures.bridge.deck_flush_m)
    lines = end_lines(planar, law)
    seats_of = {oid: {v for e in es for v, _w in e.terms} for oid, es in lines.items()}
    # a groundside road never takes a deck's level off its seats: a mapped
    # road deck has its own pair (``Tunnel.decks``), a road under or beside
    # the deck is the ground's (PR B round 3, LFPG H18r)
    roads = frozenset(family(law, "road_cross_section").roles)
    rows: list[Row] = []
    done: set[int] = set()
    for oid, es in sorted(lines.items()):
        ends = [(e.terms, e.depth) for e in es]
        under = [t for t in tunnels if t.deck_bridge == oid]
        # THE TRENCH'S SEATS (deck redesign PR B, attributing PR A's LFPG
        # strip_seam_tear 27 -> 106): the open stretch a trench runs on to the
        # next deck is graded to the nearest seat of EVERY deck the trench
        # seats on (``Tunnel.edge_seats``), as each trench read it before the
        # rows went per object — read off this object's seats alone, the
        # deck ground beside H18r's neighbour obj13020 stood 3.04 m over it
        pool = set(seats_of[oid]).union(*(seats_of.get(o, set()) for t in under
                                          for o, _s, _d in t.edge_seats))
        # #2112: a deck in disjoint plates has one zero PER PLATE
        # (``deck_lines.plate_of``), each held at its own end lines
        plates = plate_of(es, law)
        groups = sorted(set(plates))
        tops = None
        if len(groups) > 1:
            tops = {}
            for g in groups:
                tg = _station_tops([ends[i] for i, q in enumerate(plates) if q == g])
                tops.update({v: tg for v in tg})
        rows.extend(_span_rows(planar, oid, es, under, air, ends, flush, sorted(pool), done,
                               _FLOOR_ROLES | roads, tops, _bank_slope(law, es),
                               float(law.tables.structures.deck_gen.bank_past_edge_m)))
        held = _held_levels(planar, oid, es)
        for g in groups:
            idx = [i for i, q in enumerate(plates) if q == g]
            eg = [ends[i] for i in idx]
            rows.extend(_station_rows(oid, eg, flush, [held[i] for i in idx]))
            rows.extend(_rigid_rows(oid if len(groups) == 1 else f"{oid} plate {g}", eg))
    return rows


def _floor_deck_rows(planar: PlanarMap, law: Law) -> list[Row]:
    """A DECK OVER THE PACK'S CUT (#1883 r3 B2, ``planar/floor_decks``;
    owner RULINGS 2026-11-04a (16)): per piece, every station flush with
    the piece's ONE zero, both end lines held to it by the deck-top
    difference (:func:`_station_rows`, :func:`_rigid_rows`) and the ground
    under the deck outside the cut flush with its seats, an airside vertex
    there never through it (:func:`_span_rows`) — the pavement flattens to
    the deck end, the deck never tilts.  The cut under it is the floor's:
    its pinned faces are never spanned."""
    from .deck_lines import floor_end_lines
    lines = floor_end_lines(planar, law)
    if not lines:
        return []
    from ..model.platform import stage_air_vertices
    flush = float(law.tables.structures.bridge.deck_flush_m)
    air = stage_air_vertices(planar, law)
    rows: list[Row] = []
    done: set[int] = set()
    for pid, es in sorted(lines.items()):
        ends = [(e.terms, e.depth) for e in es]
        rows.extend(_span_rows(planar, pid, es, (), air, ends, flush, None, done,
                               _FLOOR_ROLES | {"tunnel_trench"}))
        rows.extend(_station_rows(pid, ends, flush))
        rows.extend(_rigid_rows(pid, ends))
    return rows


def _span_rows(planar: PlanarMap, oid: str, es, tunnels, air, ends, flush: float,
               pool: "_t.Sequence[int] | None" = None, done: "set[int] | None" = None,
               skip: "_t.AbstractSet[str]" = _FLOOR_ROLES,
               plate_tops: "dict[int, dict[int, float]] | None" = None,
               bank: "float | None" = None, past: float = 0.0) -> list[Row]:
    """The object's SPAN: every vertex inside its deck rings — or, on the
    bridge's own ground (:func:`_bridge_ground`), inside the reach of a
    trench under it (``model/structures.deck_reach``) — that is no seat and
    no trench floor takes the pair to its nearest seat; an airside vertex
    there a ceiling from the deck's zero instead (#1692: the pavement under
    the deck never stands through it).  ``pool``: the seats a
    span vertex may take (the object's own and its trenches' other decks');
    ``done``: the vertices an earlier object already spans (each once);
    ``skip``: the roles no span vertex carries (the trench floor's, the
    groundside road's).  NOT THE CUT (PR B round 3, LFPG H18r / H19
    0.205 / 0.283 m): a vertex off the airside inside a cut under the deck
    (:func:`_in_cut`) stands at the cut's level — pulled to the deck's, the
    floor beside it followed and the stations moved.  ``plate_tops``
    (#2112): per seat, its PLATE's station tops -- an airside vertex under
    a deck in plates is read from its nearest seat's plate's zero.
    ``bank`` (a GENERATED deck, :func:`_bank_slope`): the pair holds the
    vertex on the BANK instead of flush -- :func:`_bank_drop` under its
    seat -- and runs on ``past`` metres beyond the ring's edges on the
    bridge's own ground (owner sim read 2026-11-17T19:42Z: "that embankment
    needs to extend about 1m past the bridge edges")."""
    from shapely.geometry import MultiPoint, Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    seat_vs = sorted({v for e in es for v, _w in e.terms})
    if not seat_vs:
        return []
    near_vs = list(pool) if pool else seat_vs
    done = set() if done is None else done
    decks = list({tuple(e.deck.ring): e.deck for e in es}.values())
    inside = prep(unary_union([Polygon(d.ring).buffer(0.5) for d in decks]))
    ring_past = unary_union([Polygon(d.ring).buffer(past if bank is not None else -0.5,
                                                    join_style="mitre") for d in decks])
    ring_in = prep(ring_past)
    # THE BANK BLENDS OUT (:func:`_blend_drop`): the ground the bank's
    # daylight cone reaches past the ring's run-on
    wide_g = ring_past.buffer(max(float(e.depth) for e in es) / bank) \
        if bank is not None and bank > 0.0 else None
    wide = prep(wide_g) if wide_g is not None else None
    kerb = _kerb(planar, air, decks, wide_g) if wide_g is not None else None
    hulls = [MultiPoint(pts).convex_hull for t in tunnels if (pts := deck_reach(t)) is not None]
    # THE DECK'S GROUND IS ITS OWN CELL (#2072): ``planar/deck_bridge.
    # deck_ground`` minted it from the reach the planar stage read, which can
    # stand wider than the final trenches' reach -- a face of it beyond
    # that hull had no span row and (``solve/design_ground``) no datum, and
    # bending alone stood its corner 21.9 m over the ground (KIAH obj24551)
    mine = f"{DECK_GROUND_REF}:{oid}"
    own = [Polygon([planar.vertices[v].xy for v in planar.ring_vertices(f.ring)])
           for f in planar.faces.values() if str(f.ref).split("#")[0] == mine]
    hulls += [g if g.is_valid else g.buffer(0.0) for g in own if len(g.exterior.coords) >= 4]
    beyond = prep(unary_union(hulls).buffer(0.5)) if hulls else inside
    in_cut = _in_cut(planar, tunnels)
    # a vertex under ANOTHER generated deck's ring is that deck's bank, never
    # this one's flush ground (MEASURED KJFK: two decks over one road 80 m
    # apart, the open stretch between them held db1cfe30's bank vertex
    # 6.1 m up, flush with o4gen_0abbd35b's seat)
    mine_rings = {tuple(d.ring) for d in decks}
    others = [Polygon(d.ring).buffer(-0.5) for d in getattr(planar, "decks", ()) or ()
              if getattr(d, "witness", "") == "generated" and tuple(d.ring) not in mine_rings]
    others_in = prep(unary_union(others)) if others else None
    src = Source(GEN, RULING, (oid, oid, "deck span"))
    under = Source(GEN, RIGID, (oid, oid, "under the deck"))
    top_of = _station_tops(ends)
    seats = set(seat_vs) | set(near_vs)
    rows: list[Row] = []
    for v, vx in planar.vertices.items():
        if v in seats or skip & set(planar.roles_at(v)):
            continue
        p = Point(vx.xy)
        if v not in air and in_cut(p):
            continue
        if others_in is not None and v not in air and others_in.contains(p) \
                and not ring_in.contains(p):
            continue
        if not inside.contains(p) and not (beyond.contains(p) and _bridge_ground(planar, vx)):
            if wide is not None and v not in air and v not in done and wide.contains(p) \
                    and _open_ground(planar, vx):
                rows.extend(_blend_rows(planar, v, p, es, ring_past, bank, near_vs, src, kerb))
            continue
        x, y = vx.xy
        a = min(near_vs, key=lambda s: (planar.vertices[s].xy[0] - x) ** 2
                + (planar.vertices[s].xy[1] - y) ** 2)
        if v not in air and v in done:
            continue
        done.add(v)
        if v in air:
            t = plate_tops.get(a, top_of) if plate_tops else top_of
            rows.append(_from_zero(v, t, t.get(a), None, flush, under))
            continue
        # the bank is the ring's own ground, inside its edge; past it the
        # bridge's ground blends out on the bank's daylight cone
        # (:func:`_blend_drop`); a vertex of any other cell -- a building pad
        # under the ring (KJFK building39: its edge pulled 2 m down with the
        # bank) -- keeps the seat's level
        drop = 0.0
        if bank is not None and (_bridge_ground(planar, vx) or _open_ground(planar, vx)):
            drop = _bank_drop(es, p, bank) if ring_in.contains(p) \
                else _blend_drop(es, p, ring_past, bank, kerb)
        rows.append(Linear(((v, 1.0), (a, -1.0)), None, -drop, src))
        rows.append(Linear(((v, -1.0), (a, 1.0)), None, drop, src))
    return rows


def _bank_slope(law: Law, es) -> "float | None":
    """``[channel] bank_slope`` for a GENERATED deck's span, ``None`` (flush)
    for a pack deck.  #2141 item 4 (owner sim read 2026-11-17: "little jags
    sticking up under the bridge preventing the cut from running smoothly
    under the deck"): a generated deck has no walls and stands on no ground
    between its end lines -- the ground its cut leaves under the ring is the
    BANK, from each end line down to the floor (``planar/deck_bridge.
    deck_cut``, #2072 C).  Held flush with the seats, every vertex of it the
    cut's knife left behind stood a spike at deck level under the deck:
    MEASURED ESSA (``v2_solve_replay`` capture on e7b8406f0): W 7 vertices of
    the bank's toe +6.0-7.0 m over the floor (a cliff, the bank a shelf at
    deck level), U -74 one +6.28 m, -141 one +6.25 m mid-bank."""
    if any(getattr(e.deck, "witness", "") != "generated" for e in es):
        return None
    # the bank under a generated deck: the run the cut made (one reader)
    from ..model.structures import generated_bank_slope
    return generated_bank_slope(law)


def _bank_drop(es, p, slope: float) -> float:
    """How far under its seat a span vertex at ``p`` stands on a generated
    deck's bank: ``slope`` x its distance from the nearest end line, at
    most that line's depth (its top over the frame's bottom, the floor) --
    the bank's head on the end line, its toe on the floor and the floor
    beyond."""
    from shapely.geometry import LineString
    best = None
    for e in es:
        if len(e.line) < 2:
            continue
        d = LineString(e.line).distance(p)
        if best is None or d < best[0]:
            best = (d, float(e.depth))
    return 0.0 if best is None else max(0.0, min(best[1], slope * best[0]))


def _blend_drop(es, p, ring_past, slope: float, kerb=None) -> float:
    """THE BANK BLENDS OUT (owner sim read 2026-11-17T22:25Z, ESSA 1.0.557:
    "just past the bridge edge the bank changes suddenly from what's under
    it to what's next to it"; RULINGS 17p: the cut runs ``past`` metres
    beyond the bridge, then blends back to the cut and the natural
    terrain).  How far under its seat the ground at ``p``, beyond the
    ring's run-on ``ring_past``, stands on the cut: the bank's drop at the
    nearest point of the run-on's edge (:func:`_bank_drop`) less ``slope``
    x the distance out -- the bank's own face carried on past the edge
    line, so the surface is continuous there and daylights into the ground
    beside it.  MEASURED ESSA (``v2_solve_replay`` of the lessa4 capture on
    test-557 721317bb0): beside o4gen_44525b99 the run-on band stood on the
    floor (30.91 at +0.85 m) and the zone ground at +1.0-1.3 m at the seat
    (35.8-36.3), a 5 m step in 0.3 m.

    ``kerb`` (:func:`_kerb`): the airside pavement beside the deck -- the
    cut never undercuts it (airside is king): the drop is at most ``slope``
    x the distance from it, the bank rising to its edge."""
    from shapely.ops import nearest_points
    s = ring_past.distance(p)
    q = nearest_points(ring_past, p)[0]
    drop = _bank_drop(es, q, slope) - slope * s
    if kerb is not None and not kerb.is_empty:
        drop = min(drop, slope * kerb.distance(p))
    return max(0.0, drop)


def _kerb(planar: PlanarMap, air, decks, region):
    """The edges of the airside pavement beside a generated deck: every
    edge of two airside vertices inside ``region``, less the part on the
    deck's own ring (its carried pavement, which the slab stands over)."""
    from shapely.geometry import LineString, MultiLineString, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    own = unary_union([Polygon(d.ring).buffer(0.5) for d in decks])
    reg = prep(region)
    segs = []
    for e in planar.edges.values():
        if e.a not in air or e.b not in air:
            continue
        ln = LineString([planar.vertices[e.a].xy, planar.vertices[e.b].xy])
        if reg.intersects(ln):
            rest = ln.difference(own)
            if not rest.is_empty:
                segs.extend(getattr(rest, "geoms", [rest]))
    return MultiLineString([g for g in segs if g.geom_type == "LineString"]) if segs else None


def _open_ground(planar: PlanarMap, vx) -> bool:
    """A vertex every face of which is open ground (``graded_strip``: a
    zone band, the bridge's own ground) -- never a pavement's, a wall's or
    a building pad's, which keep their own law."""
    faces = [planar.faces.get(f) for f in vx.incident_faces]
    return bool(faces) and all(f is not None and f.role == "graded_strip" for f in faces)


def _blend_rows(planar: PlanarMap, v: int, p, es, ring_past, slope: float, near_vs,
                src: Source, kerb=None) -> list[Row]:
    """The ground beside a generated deck's run-on stands no higher than the
    bank blending out (:func:`_blend_drop`) under its nearest seat: a
    one-sided CEILING -- the cut takes ground away, never fills it; ground
    already under the cone keeps its own law."""
    drop = _blend_drop(es, p, ring_past, slope, kerb)
    if drop <= 0.0:
        return []
    x, y = p.x, p.y
    a = min(near_vs, key=lambda s: (planar.vertices[s].xy[0] - x) ** 2
            + (planar.vertices[s].xy[1] - y) ** 2)
    return [Linear(((v, 1.0), (a, -1.0)), None, -drop, src)]


def _in_cut(planar: PlanarMap, tunnels) -> "_t.Callable[[_t.Any], bool]":
    """Whether a point stands inside a cut under the deck — the floor and
    void faces of the trenches ``tunnels`` (``deck_lines.cut_faces``) and
    their footprints."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep

    from .deck_lines import cut_faces
    rings = list(cut_faces(planar, tunnels))
    rings += [fp for t in tunnels if len(fp := tuple(getattr(t, "footprint", ()) or ())) >= 3]
    if not rings:
        return lambda _p: False
    cut = unary_union([Polygon(r).buffer(0.0) for r in rings])
    if cut.is_empty:
        return lambda _p: False
    within = prep(cut)
    return within.contains


def _held_levels(planar: PlanarMap, oid: str, es) -> list["float | None"]:
    """Per end line, the level its anchor HOLDS (``PlanarMap.deck_anchors``:
    pinned and not yielding), else ``None``."""
    from .deck_lines import anchor_of
    out: list[float | None] = []
    for e in es:
        a = anchor_of(planar, oid, e.line)
        out.append(float(a.z_m) if a is not None and a.pinned and not a.yielding else None)
    return out


def _rigid_rows(oid: str, ends: list) -> list[Row]:
    """ONE ZERO (30a (1)): each end line's seat mean held to the first's by
    the deck-top difference — ``mean z[S_k] − mean z[S_0] = top_k − top_0``
    — a two-sided pair under :data:`RIGID`."""
    rows: list[Row] = []
    for k, (terms, top) in enumerate(ends[1:], 1):
        src = Source(GEN, RIGID, (oid, f"end {k}"))
        acc: dict[int, float] = {}
        for v, w in terms:
            acc[v] = acc.get(v, 0.0) + w
        for v, w in ends[0][0]:
            acc[v] = acc.get(v, 0.0) - w
        ts = tuple((v, c) for v, c in sorted(acc.items()) if abs(c) > 1e-12)
        if not ts:
            continue
        rhs = top - ends[0][1]
        rows.append(Linear(ts, None, rhs, src))
        rows.append(Linear(tuple((v, -c) for v, c in ts), None, -rhs, src))
    return rows



def _bridge_ground(planar: PlanarMap, vx) -> bool:
    """A vertex of the bridge's own ground beyond its rings — every face it
    touches is a trench's void or the deck's ground (``planar/deck_bridge.
    deck_ground``): the open stretch's rim and the ground behind it, never a
    zone band's or a pavement's vertex, which keep their own law there."""
    faces = [planar.faces.get(f) for f in vx.incident_faces]
    return bool(faces) and all(
        f is not None and (f.role == "retaining_wall"
                           or str(f.ref).startswith(DECK_GROUND_REF + ":"))
        for f in faces)


def _station_rows(oid: str, ends: list, flush: float,
                  level: "_t.Sequence[float | None]" = ()) -> list[Row]:
    """EVERY STATION FLUSH (owner RULINGS 2026-10-30a (1), 30f (4); #1692),
    hard, under :data:`RIGID`.  Where its end line's anchor HOLDS a level
    (``level[k]``, :func:`_held_levels`), each station stands ABSOLUTELY
    within ``flush`` of it — ``z[v] ∈ z_end ± flush`` (deck redesign §1:
    the two maps' stations read one level, never their own mean; KIAH
    round 3: a station stage 1 never held solved 0.26 m off its deck).
    Elsewhere (a yielding anchor, or none) it is RELATIONAL, read from the
    ONE zero the object stage seats the deck at — the mean over every
    station, each once (``pipeline/rebake_inputs._deck_plate``) — so
    ``z[v] − mean z[S] ∈ top(v) − mean top[S] ± flush``.  The rigid row
    holds the end means; a taxiway's cross-fall left the stations of one
    end line 0.76 m apart under a flat deck (KBNA round 4)."""
    top_of = _station_tops(ends)
    held: dict[int, "float | None"] = {}
    for k, (terms, _top) in enumerate(ends):
        for v, _w in terms:
            held.setdefault(v, level[k] if k < len(level) else None)
    out: list[Row] = []
    for v in sorted(top_of):
        src = Source(GEN, RIGID, (oid, f"station v{v}"))
        z = held.get(v)
        out.append(Band(v, z - flush, z + flush, src) if z is not None
                   else _from_zero(v, top_of, top_of[v], -flush, flush, src))
    return out


def _station_tops(ends: list) -> dict[int, float]:
    """Every station vertex of a deck's end lines, each once, with its end
    line's top (the first end line naming it)."""
    top_of: dict[int, float] = {}
    for terms, top in ends:
        for v, _w in terms:
            top_of.setdefault(v, float(top))
    return top_of


def _from_zero(v: int, top_of: dict, top: "float | None", lo: "float | None",
               hi: float, src: Source) -> Row:
    """``z[v] − mean z[S] − (top − mean top[S]) ∈ [lo, hi]``: ``v`` against
    the deck top ``top`` above it, read from the zero the object stage
    seats (:func:`_station_rows`); ``top`` ``None`` reads the mean top."""
    n = len(top_of)
    mean_top = sum(top_of.values()) / n
    acc = {u: -1.0 / n for u in top_of}
    acc[v] = acc.get(v, 0.0) + 1.0
    ts = tuple((u, c) for u, c in sorted(acc.items()) if abs(c) > 1e-12)
    rhs = (mean_top if top is None else top) - mean_top
    return Linear(ts, None if lo is None else rhs + lo, rhs + hi, src)


def _span_vertices(planar: PlanarMap, law: Law, tn) -> set[int]:
    """The vertices inside ``tn``'s edge covers or on its back — within the
    rim stand-off (``wall_gap_m + wall_band_width_m``) of the back line
    run on ``wall_gap_m`` past each end (the rim's corner vertex there),
    flat-capped — on no trench floor (module doc)."""
    covers = getattr(tn, "edge_covers", ()) or ()
    if not covers:
        return set()
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    t = law.tables.structures.tunnel
    parts = [Polygon(c).buffer(0.0) for c in covers if len(c) >= 4]
    if len(getattr(tn, "edge_back", ()) or ()) >= 2:
        parts.append(LineString(_run_on(tn.edge_back, t.wall_gap_m)).buffer(
            t.wall_gap_m + t.wall_band_width_m, cap_style="flat"))
    span = unary_union([q for q in parts if not q.is_empty])
    if span.is_empty:
        return set()
    inside = prep(span)
    out: set[int] = set()
    for v, vx in planar.vertices.items():
        if inside.contains(Point(vx.xy)) and not _FLOOR_ROLES & set(planar.roles_at(v)):
            out.add(v)
    return out


def _run_on(line, d: float) -> list:
    """``line`` (points) run on ``d`` metres past each end along its end
    segments."""
    pts = [tuple(p) for p in line]

    def past(a, b):
        n = math.dist(a, b)
        return b if n <= 1e-9 else (b[0] + (b[0] - a[0]) * d / n, b[1] + (b[1] - a[1]) * d / n)
    return [past(pts[1], pts[0]), *pts[1:-1], past(pts[-2], pts[-1])] if len(pts) > 2 else \
        [past(pts[1], pts[0]), past(pts[0], pts[1])]


#: the generators whose one-vertex rows a governed vertex no longer
#: carries: the trench rim's DEM pin (``constraints/structures``) and the
#: road ramp's target and hard ceiling (``constraints/road_ramp``)
_RELEASED = frozenset({"structures", "road_ramp"})


def release_governed(rows: list[Row], counts: dict[str, int] | None = None,
                     gen: str = GEN) -> list[Row]:
    """THE PAIR IS THE LEVEL (#1632, module doc): every vertex generator
    ``gen`` holds by a pair (the first term of its rows: this module's to the
    airside abeam; ``constraints/wing_cut``'s to its wings' feet, #2099 R2)
    sheds the one-vertex rows of :data:`_RELEASED` — a ``Pin``, a ``Band`` or
    a one-term ``Linear`` — that held it at the DEM or at a road's ramp.
    Pair rows (grades, steps) are kept: they bind it to its neighbours."""
    gov = {r.terms[0][0] for r in rows
           if isinstance(r, Linear) and r.source.generator == gen and r.terms[0][1] > 0.0
           and r.source.ruling != RIGID}
    if not gov:
        return rows
    out: list[Row] = []
    n = 0
    for r in rows:
        if r.source.generator in _RELEASED and (
                (isinstance(r, (Pin, Band)) and r.v in gov)
                or (isinstance(r, Linear) and len(r.terms) == 1 and r.terms[0][0] in gov)):
            n += 1
            continue
        out.append(r)
    if counts is not None:
        counts[f"{gen}.released"] = n
    return out


def deck_floor(planar: PlanarMap, air_roles: "_t.AbstractSet[str]" = frozenset(),
               air: "_t.AbstractSet[int]" = frozenset()) -> tuple[frozenset, frozenset]:
    """``(floor, trench)``: the vertices of a HARD-DECK BRIDGE's trench
    floor under its deck, and every vertex of a trench (its ramps and its
    void) — ``walled_plate.release_across``'s sets (owner RULINGS
    2026-10-30a: the outline is the step; nothing outside the trench pulls
    the floor).  A vertex carrying a RUNWAY-family role is never floor: a
    runway cell inside the outline is not cut (the knife's 08-07 ruling 4
    exemption, ``planar/structure_service``), so its rows stay — MEASURED
    (LFPG 09L/27R over a hard-deck road underpass, batch AR): the release
    withdrew the runway's transverse rows at the trench outline and the
    runway edge fell 1.02 m off its crown (3.34 % against 1.52 %).

    THE AIRSIDE STANDS OUTSIDE THE TRENCH (#2072, #1902; airside is king):
    a vertex carrying one of ``air_roles`` (the airside pavement, the
    runway family aside) that is no floor vertex is never ``trench``, even
    where it stands on the trench's wall — a deck station is the airside's,
    and an airside row joining it to the floor is withdrawn like any other
    row from outside.  MEASURED (KIAH replay, deaddf5e8): the deck stations
    stood on the walls, so the taxiway's transverse and no-step rows to the
    floor were kept; at obj24551 a floor ceiling pulled the taxi deck 2.89 m
    under its route level (the airside bumps at both ends of #2072), and at
    the other decks the deck lifted every floor to its 5 m bound, 2.3-2.7 m
    over the ramp's own floor (the steps along the roads of #1902).

    A VERTEX A STAGE-1 AIRSIDE FACE CARRIES (``air``,
    ``model/platform.stage_air_vertices``) IS NEVER FLOOR (#2099 R3b A4):
    it is ``trench`` only by the clause above (no airside role), so the
    release keeps its airside rows and withdraws the rows joining it to the
    floor.  MEASURED (lcyyz3, KBNA): R3 A1 took such a vertex out of every
    floor row while this still called it floor; the release withdrew its
    taxiway rows, nothing held it, and it fell 3.29 m to the floor."""
    rings = [db.ring for db in getattr(planar, "decks", ()) or ()
             if db.cut != "none" and len(db.ring) >= 3]
    if not rings:
        return frozenset(), frozenset()
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    inside = prep(unary_union([Polygon(r).buffer(0.5) for r in rings]))
    floor, trench = set(), set()
    for v, vx in planar.vertices.items():
        roles = set(planar.roles_at(v))
        if roles & (_FLOOR_ROLES | {"retaining_wall"}):
            is_floor = bool(roles & _FLOOR_ROLES) and not roles & _RUNWAY_FAMILY \
                and v not in air and inside.contains(Point(vx.xy))
            if is_floor:
                floor.add(v)
            if is_floor or not roles & (set(air_roles) - _RUNWAY_FAMILY):
                trench.add(v)
    return frozenset(floor), frozenset(trench)
