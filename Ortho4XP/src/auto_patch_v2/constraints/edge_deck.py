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
:data:`RIGID` (``[design] hard_rulings``).  The taxiway on each side is
graded to the deck; the deck never tilts or shears.  The ground under the
deck that is no trench floor — the bank's top along its edge — takes the
span pair to its nearest seat (:func:`_deck_span`).
"""
from __future__ import annotations

import math

from ..law import Law
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
    if not tunnels and not decked:
        return []
    nearest = airside_nearest(planar, law)
    if nearest is None:
        return []
    rows: list[Row] = _deck_rows(planar, law, decked, nearest.air) if decked else []
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


def _deck_rows(planar: PlanarMap, law: Law, tunnels, air) -> list[Row]:
    """The hard-deck bridges' rigid rows and spans (module doc)."""
    from shapely.geometry import Point, Polygon
    from shapely.prepared import prep

    from .edge_floor import edge_seats_of
    seats_of = edge_seats_of(planar, law, combine=False)
    rows: list[Row] = []
    by_obj: dict[str, dict] = {}
    for tn in tunnels:
        got = seats_of(tn)
        for (oid, st, depth), (terms, _d) in zip(tn.edge_seats, got, strict=True):
            top = float(depth)                  # depth = top − bottom: the bottom cancels
            by_obj.setdefault(oid, {}).setdefault(tuple(st), (terms, top))
        seat_vs = sorted({v for terms, _d in got for v, _w in terms})
        if not seat_vs:
            continue
        ring = Polygon(tn.deck_ring).buffer(0.5)
        inside = prep(ring)
        reach = deck_reach(tn)
        beyond = prep(reach.buffer(0.5)) if reach is not None else inside
        src = Source(GEN, RULING, (tn.id, tn.deck_bridge, "deck span"))
        under = Source(GEN, RIGID, (tn.id, tn.deck_bridge, "under the deck"))
        flush = float(law.tables.structures.bridge.deck_flush_m)
        for v, vx in planar.vertices.items():
            if v in seat_vs or _FLOOR_ROLES & set(planar.roles_at(v)):
                continue
            p = Point(vx.xy)
            if not inside.contains(p) and not (beyond.contains(p)
                                               and _bridge_ground(planar, vx)):
                continue
            x, y = vx.xy
            a = min(seat_vs, key=lambda s: (planar.vertices[s].xy[0] - x) ** 2
                    + (planar.vertices[s].xy[1] - y) ** 2)
            if v in air:
                # #1692: the pavement under the deck never stands through it
                rows.append(Linear(((v, 1.0), (a, -1.0)), None, flush, under))
                continue
            rows.append(Linear(((v, 1.0), (a, -1.0)), None, 0.0, src))
            rows.append(Linear(((v, -1.0), (a, 1.0)), None, 0.0, src))
    flush = float(law.tables.structures.bridge.deck_flush_m)
    for oid in sorted(by_obj):
        ends = list(by_obj[oid].values())
        rows.extend(_station_rows(oid, ends, flush))
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


def _station_rows(oid: str, ends: list, flush: float) -> list[Row]:
    """EVERY STATION FLUSH (owner RULINGS 2026-10-30a (1), 30f (4); #1692):
    each seat vertex of every end line stands within ``flush`` of the deck
    top there, read from the ONE zero the object stage seats the deck at —
    the mean over every station, each once (``pipeline/rebake_inputs.
    _deck_plate``: ``zero = mean z[S] − mean top[S]``) — so
    ``z[v] − mean z[S] ∈ top(v) − mean top[S] ± flush``.  Read from the
    first end line's mean instead, a station could stand 0.07 m over the
    deck the plate set (KBNA round 5).  The rigid row holds the end means;
    a taxiway's cross-fall left the stations of one end line 0.76 m apart
    under a flat deck (KBNA round 4).  Hard, under :data:`RIGID`."""
    top_of: dict[int, float] = {}
    for terms, top in ends:
        for v, _w in terms:
            top_of.setdefault(v, float(top))
    if not top_of:
        return []
    n = len(top_of)
    mean_top = sum(top_of.values()) / n
    rows: list[Row] = []
    for v in sorted(top_of):
        acc = {u: -1.0 / n for u in top_of}
        acc[v] += 1.0
        ts = tuple((u, c) for u, c in sorted(acc.items()) if abs(c) > 1e-12)
        rhs = top_of[v] - mean_top
        if ts:
            rows.append(Linear(ts, rhs - flush, rhs + flush,
                               Source(GEN, RIGID, (oid, f"station v{v}"))))
    return rows


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


def release_governed(rows: list[Row], counts: dict[str, int] | None = None) -> list[Row]:
    """THE PAIR IS THE LEVEL (#1632, module doc): every vertex this module
    holds to the airside abeam (the first term of its pairs) sheds the
    one-vertex rows of :data:`_RELEASED` — a ``Pin``, a ``Band`` or a
    one-term ``Linear`` — that held it at the DEM or at a road's ramp.
    Pair rows (grades, steps) are kept: they bind it to its neighbours."""
    gov = {r.terms[0][0] for r in rows
           if isinstance(r, Linear) and r.source.generator == GEN and r.terms[0][1] > 0.0
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
        counts["edge_deck.released"] = n
    return out


def deck_floor(planar: PlanarMap) -> tuple[frozenset, frozenset]:
    """``(floor, trench)``: the vertices of a HARD-DECK BRIDGE's trench
    floor under its deck, and every vertex of a trench (its ramps and its
    void) — ``walled_plate.release_across``'s sets (owner RULINGS
    2026-10-30a: the outline is the step; nothing outside the trench pulls
    the floor)."""
    rings = [t.deck_ring for t in getattr(planar, "structures", ()) or ()
             if getattr(t, "deck_bridge", "") and len(t.deck_ring) >= 3]
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
            trench.add(v)
            if roles & _FLOOR_ROLES and inside.contains(Point(vx.xy)):
                floor.add(v)
    return frozenset(floor), frozenset(trench)
