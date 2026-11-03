"""THE HARD-DECK BRIDGE: ONE READING OF A PACK DECK THE AIRPORT'S PAVEMENT
DRIVES ACROSS (owner RULINGS 2026-10-30a (1)/(2), 2026-10-29a Q296–Q298,
2026-10-27c; #1640 / #1671; the edge bridge's sibling, ``planar/bridge_span``).

A pack may carry a taxiway over a road on a HARD DECK — an ``ATTR_hard_deck``
plate (``PlacedObject.deck_kind == "flag"``) or a deck plate the signature
read (``"signature"``) — and model nothing hanging under it (KBNA's taxiway-L
bridge: one object, two deck pieces over a dual carriageway) or a trench
beside it on the same placement (EDDF ``Bridge_3`` + ``Tunnel_3``).  This
module is the ONE derivation of such a deck, computed once in
``planar/build`` before ``build_structures``, which reads it at every
consumer (the terrain-tunnel witness, the corridor, the constraint rows and
the object stage's plate):

* the WITNESS is the airport's own pavement running ACROSS a deck piece
  (27c, ``airport/airside_deck_seat.facing_contacts``), read on the
  classification (:class:`CellRoles`, the roles the object stage reads off
  the solve) — never a name.  A frame holding a building beside the deck (a
  co-placed body standing on a ``building`` cell outside the ring, 22n) is
  no bridge;
* the END LINES are the two facing contacts — where the taxiway drives onto
  the deck — and their stations (every ``[bridge] abutment_sample_step_m``
  along the ring) are the SEATS the deck's zero is graded to (30a (1): one
  zero, flush at both end lines; ``constraints/edge_deck``);
* the DEPTH at each end is the deck top there less the frame's BOTTOM, its
  members' lowest genuine solid (30a (2), 20am "the bottom of the object is
  at the road", Q167);
* THE CUT (owner 2026-10-30, Q-A as ruled: "the cut should be the road
  width, then a bank sloping from the road edge up to just short of the
  bridge width"): the floor is the carriageway at the bottom, and the
  ground on each side banks up from the road edge to the deck, ending
  ``[tunnel] wall_gap_m`` inside the deck's edge (:func:`deck_cut`): the
  corridor's VOID face spans that ground, its rim at deck level, and the
  mesh makes the bank.  A frame whose co-placed trench object states its
  walls is no hard-deck bridge here: the walls define the cut, and the
  trench object's own reading governs (``planar/covered_bores``).
* WALLS (owner RULINGS 2026-10-30f (3), #1692): where the frame itself
  models abutment walls under the deck (``planar/deck_walls``: vertical
  faces rising from its bottom along the road), the floor runs to the
  walls' inner faces — under the deck and along the open stretch to the
  next deck — and the rim stands ``wall_gap_m`` behind them
  (:func:`_walled_trench`); the bank stands only where there is no wall.
  KBNA's taxiway-L frame: walls 31.7 m apart, the carriageway's banks
  had climbed 6 m up them.
* THE GROUND THE DECK RESTS ON (RULINGS 2026-10-30b "the deck still rests
  on ground at its edges", 30f (4) no bump at a deck's edge; #1692 round 5):
  every part of the deck's ring — and of the open stretch to the next deck
  over the same road — that no cell owns once the corridors are cut (behind
  a walled trench's rim, between it and the pavement) is a face of the
  design surface (:func:`deck_ground`), so the deck span rows
  (``constraints/edge_deck``) hold it flush and the mesh carries that
  value.  Left unowned it was bare ground, and the mesh gave its vertices
  and the rim's the DEM: KBNA's taxiway-L east end line stood a ridge
  1.14 m over the deck top 2 m behind the pavement.

THE RECORD (deck redesign §1): ``model/structures.DeckBridge`` (re-exported
here), published as ``PlanarMap.decks`` with its witness, family and carried
route (``planar/deck_route``) and, once the corridors are cut, how the cut
meets it (:func:`with_cuts`).  Stage 1's map reads the full map's decks
(``model/stage_one.from_full``), never derives its own.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import functools
import math
import types
import typing as _t

from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.airside_deck_seat import facing_contacts
from ..classify.roles import Cell
from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..geom.parts import polygon_parts_with_area
from ..law.tables import role_side
from ..model.stage_one import from_full, full_map  # one derivation for both maps
from ..model.structures import DECK_GROUND_REF, DeckBridge, deck_reach
from .deck_route import carried_route
from .deck_walls import inner_faces, wall_faces, wall_strip

__all__ = ["DeckBridge", "deck_polygon", "from_full", "full_map", "with_cuts",
           "deck_bridges", "deck_under", "deck_mouth", "deck_seats", "deck_side",
           "deck_cut", "deck_pin", "deck_ground", "DECK_GROUND_REF", "across_dir",
           "mid_line", "project_span"]

XY = tuple[float, float]


def deck_polygon(db: DeckBridge) -> Polygon:
    """The deck piece's outline as a valid polygon (the model holds no
    shapely: ``model/structures.DeckBridge``)."""
    return _ring_polygon(tuple(tuple(p) for p in db.ring))


@functools.lru_cache(maxsize=4096)
def _ring_polygon(ring: tuple) -> Polygon:
    p = Polygon(ring)
    return p if p.is_valid else p.buffer(0.0)


def with_cuts(decks: _t.Sequence[DeckBridge], tunnels) -> tuple[DeckBridge, ...]:
    """``decks`` with ``cut`` read off the corridors once they are cut: a
    deck whose end line a trench seats on (``Tunnel.edge_seats``, its own
    deck's or the one it runs on under) is cut — ``slab``, ``walls`` (its
    frame models walls under it) or ``bank``; every other is ``none``."""
    cut = {tuple(tuple(p) for p in st) for t in tunnels if getattr(t, "deck_bridge", "")
           for _o, st, _d in getattr(t, "edge_seats", ()) or ()}
    return tuple(_dc.replace(db, cut=("slab" if db.slab else "walls" if db.walls else "bank")
                             if tuple(tuple(p) for p in db.seats_a) in cut else "none")
                 for db in decks)


class CellRoles:
    """``roles_many(lats, lons)``: the classification cell role at each
    point (``None`` off every cell) — the ``Surface.roles`` reader
    ``airside_deck_seat`` reads, over the classify cells (planar time)."""

    def __init__(self, classification, airport) -> None:
        self._cells = [c for c in classification.cells if len(c.ring) >= 3]
        polys = []
        for c in self._cells:
            p = Polygon(c.ring, c.holes)
            polys.append(p if p.is_valid else p.buffer(0.0))
        self._tree = STRtree(polys) if polys else None
        self._to_xy = airport.frame.transformers()[0]

    def at_xy(self, xy: XY) -> "str | None":
        if self._tree is None:
            return None
        hit = self._tree.query(Point(xy), predicate="intersects")
        return self._cells[int(min(hit))].role if len(hit) else None

    def roles_many(self, lats, lons) -> list:
        return [self.at_xy(self._to_xy(lo, la)) for la, lo in zip(lats, lons, strict=True)]


def co_placed(a, b, tol: float) -> bool:
    """Two placements of ONE frame: different resources on one anchor
    (within ``tol``) at one heading (within a degree)."""
    return (a.path != b.path and math.hypot(a.xy[0] - b.xy[0], a.xy[1] - b.xy[1]) <= tol
            and abs(((a.heading_deg - b.heading_deg + 180.0) % 360.0) - 180.0) <= 1.0)


def _frames(objects, tol: float) -> list[tuple[list, list]]:
    """``(deck placements, frame placements)`` per frame holding a flag /
    signature hard deck, in object-id order."""
    decks = sorted((o for o in objects or ()
                    if str(getattr(o, "deck_kind", "") or "") in ("flag", "signature")
                    and getattr(o, "hard_deck", None) is not None
                    and not o.hard_deck.is_empty), key=lambda o: str(o.id))
    ids = {str(o.id) for o in decks}
    out: list[tuple[list, list]] = []
    seen: set[str] = set()
    for d in decks:
        if str(d.id) in seen:
            continue
        fr = [q for q in objects if q is d or co_placed(d, q, tol)]
        seen.update(str(q.id) for q in fr)
        out.append(([q for q in fr if str(q.id) in ids], fr))
    return out


def _plate(cache, decks) -> list[tuple[float, float, float]]:
    """Every deck placement's deck-plate vertex (``ObjGeometry.hard_deck``)
    as ``(x, y, top y)`` in the frame."""
    from ..airport.obj8 import _to_frame
    out = []
    for d in decks:
        g = cache.geometry(d.resolved) if d.resolved else None
        tri = g.hard_deck if g is not None else ()
        for i in sorted({int(i) for t in tri for i in t}):
            x, y, z = (float(v) for v in g.vertices[i][:3])
            px, py = _to_frame(d.xy, d.heading_deg, x, z)
            out.append((px, py, y))
    return out


def _is_slab(cache, decks) -> bool:
    """THE SLAB WITNESS (round 3 §1): a deck placement's plate is the
    ``ATTR_hard`` plate (``ObjGeometry.hard_plate``) — a hard surface solid
    from the ground up, which aircraft drive on and nothing passes under.
    A plate flagged ``ATTR_hard_deck`` is a deck the road passes under,
    however thin its frame (LFPG's plate-only decks: one 13 m plate)."""
    for d in decks:
        g = cache.geometry(d.resolved) if d.resolved else None
        if g is not None and g.hard_plate:
            return True
    return False


def _end_top(plate, seats, reach: float, top: float) -> float:
    """A SLAB's top AT its end line: the mean over the seat stations of the
    plate vertex nearest each, within ``reach`` — the end taper the plate
    authors (KIAH_Bridge1: 0.13 m) stated, never the plate's crown."""
    tops = []
    for s in seats:
        near = min(plate, key=lambda q: math.hypot(q[0] - s[0], q[1] - s[1]), default=None)
        if near is not None and math.hypot(near[0] - s[0], near[1] - s[1]) <= reach:
            tops.append(near[2])
    return sum(tops) / len(tops) if tops else top


def _top_at(plate, seats, reach: float, top: float) -> float:
    near = [y for x, yy, y in plate if any(math.hypot(x - s[0], yy - s[1]) <= reach
                                          for s in seats)]
    return max(near) if near else top


def _bottom_y(cache, frame, trenches, top: float) -> tuple[float, bool]:
    """``(the frame's bottom y, walled)``: a co-placed trench object's walls'
    bottom (``walled``: the frame is then the trench object's), else the
    lowest genuine solid of the frame's placements, else ``top``: a frame
    modelling nothing but its plate states no level under it (round 3 §1
    twin B, LFPG's plate-only decks: the authored y = 0 plane is no floor)."""
    ids = {str(q.id) for q in frame}
    tr = [t for t in trenches or () if str(t.object_id) in ids]
    if tr:
        return -max(float(t.depth_m) for t in tr), True
    ys = [c.min_y for q in frame if q.resolved for c in cache.genuine(q.resolved)]
    return (min(ys) if ys else top), False


def _beside_a_building(frame, ring: Polygon, roles: CellRoles) -> bool:
    """22n: a co-placed body outside the ring standing on a building pad."""
    for q in frame:
        box = getattr(q, "plan_bbox", None)
        if box is None or box.is_empty:
            continue
        c = box.centroid
        if not ring.buffer(1.0).contains(c) and roles.at_xy((c.x, c.y)) == "building":
            return True
    return False


def deck_bridges(objects, cache, classification, airport, law, trenches=(),
                 level_b: "float | None" = None
                 ) -> tuple[tuple[DeckBridge, ...], list[str]]:
    """``(every hard-deck bridge, one note per deck piece refused)``
    (module doc).  ``level_b``: the airport's level-B depth
    (``planar/level_depth.airport_level_b``), the floor under a deck whose
    frame states none (RULINGS 2026-11-03b)."""
    if not objects or cache is None or classification is None or not classification.cells:
        return (), []
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    roles = CellRoles(classification, airport)
    surface = types.SimpleNamespace(roles=roles)
    to_xy, to_ll = airport.frame.transformers()
    out: list[DeckBridge] = []
    notes: list[str] = []
    for decks, frame in _frames(objects, tol):
        d = decks[0]
        u = unary_union([q.hard_deck for q in decks])
        plate = _plate(cache, decks)
        solid = _is_slab(cache, decks)
        top = max((y for _x, _y, y in plate), default=None)
        if top is None or d.deck_top_z is None:
            continue
        bottom, walled = _bottom_y(cache, frame, trenches, top)
        if walled:
            # Q-A AS RULED: where the pack models walls the walls define the
            # cut — the co-placed trench object's own reading governs
            notes.append(f"{d.id} {str(d.path).rsplit('/', 1)[-1]}: a co-placed trench "
                         f"object states its walls — they define the cut (Q-A as ruled)")
            continue
        mine: list[DeckBridge] = []
        for piece in sorted(getattr(u, "geoms", [u]), key=lambda p: -p.area):
            if piece.geom_type != "Polygon" or piece.area < 1.0:
                continue
            ring_ll = [to_ll(x, y) for x, y in piece.exterior.coords[:-1]]
            pairs = facing_contacts(ring_ll, surface, step, every=True)
            where = f"{d.id} {str(d.path).rsplit('/', 1)[-1]} piece {piece.area:,.0f} m2"
            pair = _end_pair(pairs, _roads_under(airport, law, piece)
                             if len(pairs) > 1 else None, to_xy,
                             _routes_across(airport, piece) if len(pairs) > 1 else ())
            if pair is None:
                notes.append(f"{where}: no pavement runs across it (RULINGS 2026-10-27c)")
                continue
            if _beside_a_building(frame, piece, roles):
                notes.append(f"{where}: a building stands beside it in its frame (22n)")
                continue
            sa, sb = (tuple(to_xy(lo, la) for la, lo in e) for e in pair)
            reach = max(2.0 * step, 3.0)
            ta, tb = _top_at(plate, sa, reach, top), _top_at(plate, sb, reach, top)
            # the FAMILY and the ROUTE, one per deck (``planar/deck_route``)
            fam, route, ref = carried_route(airport, piece)
            mine.append(DeckBridge(str(d.id), str(d.path), tuple(str(q.id) for q in frame),
                                   tuple(piece.exterior.coords[:-1]), sa, sb, ta, tb,
                                   float(bottom), float(d.deck_top_z) - top + 0.5 * (ta + tb),
                                   family=fam, route=route, route_ref=ref))
        # ONE zero per object (30a (1)): every piece plans from one estimate
        z = _deck_z(airport, [p for db in mine for p in db.seats_a + db.seats_b], None)
        for db in (db if z is None else _dc.replace(db, deck_z=z) for db in mine):
            db = _road_floor(db, law, notes, level_b, _carries_movement(db, roles))
            if solid:
                notes.append(f"{db.object_id} {db.resource.rsplit('/', 1)[-1]}: an ATTR_hard "
                             f"plate (ATTR_hard_deck only on its edge-on faces) — a SLAB: the "
                             f"ground under it is kept at the deck and the cut stops at its "
                             f"edges (owner 2026-11-03T16:39Z)")
                db = _dc.replace(db, slab=True, witness="slab")
                reach = max(2.0 * step, 3.0)
                db = _dc.replace(db, top_a=_end_top(plate, db.seats_a, reach, db.top_a),
                                 top_b=_end_top(plate, db.seats_b, reach, db.top_b))
            r, n = _road_dir(db), across_dir(db)
            out.append(_dc.replace(db, walls=wall_faces(cache, frame, db.bottom_y,
                                                        0.5 * (db.top_a + db.top_b), r, n)))
    return tuple(out), notes


def _roads_under(airport, law, ring: Polygon) -> "XY | None":
    """The direction the mapped roads under ``ring`` run: the length-weighted
    mean of their stretches inside it (``structure_underpass.bore_roads``),
    ``None`` where none passes under — the witness :func:`_end_pair` picks
    the end lines by.  MEASURED kiahdeck2 (KIAH): a deck the airport's
    pavement meets along its long sides as well as at its ends read the
    FIRST facing pair as its end lines — ``KIAH_Bridge1`` obj24549 its
    south side and east end (the road under it 10° askew, the deck's
    midline at its north edge over one carriageway, the cut's rim on the
    road beyond), obj24551 its two long sides (the road read along the deck
    instead of across it)."""
    from .structure_underpass import bore_roads
    sx = sy = 0.0
    for w in bore_roads(airport, law, rail=True):
        x = LineString(w.points).intersection(ring)
        for g in getattr(x, "geoms", [x]):
            if g.geom_type != "LineString" or g.length <= 1.0:
                continue
            (x0, y0), (x1, y1) = g.coords[0], g.coords[-1]
            if (x1 - x0) * sx + (y1 - y0) * sy < 0.0:
                x0, y0, x1, y1 = x1, y1, x0, y0
            sx, sy = sx + x1 - x0, sy + y1 - y0
    n = math.hypot(sx, sy)
    return None if n <= 1.0 else (sx / n, sy / n)


def _routes_across(airport, ring: Polygon) -> list:
    """The CARRIED ROUTES over ``ring``: every runway axis (apt.dat ends) and
    every aircraft taxi route edge (row 1202) whose line crosses it — the
    witness the end lines are read by first (deck-end-anchors spec §2 (a))."""
    lines = [LineString([rw.ends[0].xy, rw.ends[1].xy]) for rw in airport.runways
             if len(rw.ends) == 2]
    nodes = getattr(airport, "taxi_nodes", {}) or {}
    lines += [LineString([nodes[e.a].xy, nodes[e.b].xy])
              for e in getattr(airport, "taxi_edges", ()) or ()
              if e.a in nodes and e.b in nodes and nodes[e.a].xy != nodes[e.b].xy]
    return [ln for ln in lines if ln.intersection(ring).length > 1.0]


def _end_pair(pairs, road: "XY | None", to_xy, routes=()):
    """The facing contacts that are the deck's END LINES.  First the pair a
    CARRIED ROUTE (``_routes_across``) runs across — it crosses both
    contacts' lines, the most nearly square; then, where a mapped road runs
    under the deck, the pair whose contacts run most nearly along it — an
    end line is parallel to the road the bridge crosses, a long side across
    it; else the first pair (``facing_contacts``).  MEASURED (deckanchor
    round 1): LFPG ``H18r`` read end B on a taxiway beside 09R/27L, which
    crosses the deck through the other pair."""
    if not pairs:
        return None
    if len(pairs) == 1:
        return pairs[0]
    crossed = _crossed_pair(pairs, routes, to_xy)
    if crossed is not None:
        return crossed
    if road is None:
        return pairs[0]

    def skew(stations) -> float:
        (x0, y0), (x1, y1) = to_xy(stations[0][1], stations[0][0]), \
            to_xy(stations[-1][1], stations[-1][0])
        L = math.hypot(x1 - x0, y1 - y0)
        return 1.0 if L <= 0.0 else abs((x1 - x0) * road[1] - (y1 - y0) * road[0]) / L
    return min(pairs, key=lambda p: skew(p[0]) + skew(p[1]))


def _crossed_pair(pairs, routes, to_xy):
    """The pair both of whose contacts a carried route crosses, the route
    most nearly square to them; ``None`` for none."""
    best = None
    for p in pairs:
        lines = [LineString([to_xy(lo, la) for la, lo in e]) if len(e) > 1 else None
                 for e in p]
        if None in lines:
            continue
        for r in routes:
            if not all(r.distance(ln) <= 1.0 for ln in lines):
                continue
            (x0, y0), (x1, y1) = r.coords[0], r.coords[-1]
            n = math.hypot(x1 - x0, y1 - y0) or 1.0
            skew = sum(abs(((ln.coords[-1][0] - ln.coords[0][0]) * (x1 - x0)
                            + (ln.coords[-1][1] - ln.coords[0][1]) * (y1 - y0)))
                       / (n * (ln.length or 1.0)) for ln in lines)
            if best is None or skew < best[0]:
                best = (skew, p)
    return None if best is None else best[1]


def _road_floor(db: DeckBridge, law, notes: list[str], level_b: "float | None",
                movement: bool) -> DeckBridge:
    """``db`` with the floor the road passes at under it (RULINGS 2026-10-30a
    (2): the road "passes completely under it").  It sets ONLY the floor;
    whether the deck is a slab is the plate's own witness (:func:`_is_slab`).
    A frame reaching ``[tunnel] clearance_m`` or more under its deck top
    reaches the road: its bottom is the floor (30g (2), KBNA's walled frame)
    -- the object states it.  A frame stopping short of it states no road
    level (LFPG's plate-only decks; KIAH's slabs: 0.12 m from top to
    bottom).  Its floor is the lower level's ladder (RULINGS 2026-11-03b
    Q344 a, spec two-level-regions §13): the airport's level B
    (``level_b``), else ``[tunnel] mouth_depth_m`` under a deck carrying a
    runway or taxiway (``movement``), else the clearance (30g) -- never
    shallower than the clearance, and never the survey, which reads the deck
    (Q344 a: lidar is never read under a deck)."""
    tn = law.tables.structures.tunnel
    clear = float(tn.clearance_m)
    top = 0.5 * (db.top_a + db.top_b)
    if top - db.bottom_y >= clear:
        return db
    if level_b is not None:
        depth, why = max(clear, float(level_b)), "the airport's level B"
    elif movement:
        depth, why = max(clear, float(tn.mouth_depth_m)), "under a runway or taxiway"
    else:
        depth, why = clear, "[tunnel] clearance_m"
    notes.append(f"{db.object_id} {db.resource.rsplit('/', 1)[-1]}: the frame stops "
                 f"{top - db.bottom_y:.2f} m under its deck, short of the road; the floor "
                 f"stands {depth:.2f} m under the deck ({why}, RULINGS 2026-11-03b / "
                 f"2026-10-30g)")
    return _dc.replace(db, bottom_y=top - depth)


def _carries_movement(db: DeckBridge, roles: "CellRoles") -> bool:
    """The deck carries a runway or a taxiway: the cells at its seats are
    runway- or taxi-family pavement (the classification's own roles)."""
    from ..classify.roles import TAXI_FAMILY
    fam = {"runway", "runway_crossing", *TAXI_FAMILY}
    return any(roles.at_xy(p) in fam for p in tuple(db.seats_a) + tuple(db.seats_b))


def _deck_z(airport, seats, rendered: "float | None") -> "float | None":
    """The pre-solve estimate of the deck top: the ground at its end lines,
    where the design solve will grade the taxiway it is flush with (the
    rendered top stands on the DEM at the anchor, under the road), else the
    rendered top."""
    dem = getattr(airport, "dem", None)
    zs = [float(dem.z(x, y)) for x, y in seats] if dem is not None else []
    zs = [z for z in zs if math.isfinite(z)]
    return sum(zs) / len(zs) if zs else rendered


def deck_under(mouth, decks: _t.Sequence[DeckBridge], reach: float,
               paved=None, far_reach: float = 0.0,
               carries_runway: "_t.Callable[[DeckBridge], bool] | None" = None
               ) -> "DeckBridge | None":
    """The hard-deck bridge a mouth's BORE runs under: its line crosses the
    deck's ring and the mapped end stands within ``reach`` of it — the
    nearest such.  A bore §34 (5) SYNTHESISED under an aeroway bridge
    (``structure_underpass.UNDERPASS_TAG``) is the crossing the deck makes,
    wherever its clip ribbon put its ends: the deck object states the
    crossing (kiahdeck2: a service road's ribbon off taxiway way −67 ended
    beyond ``reach`` of ``KIAH_Bridge1`` obj24549, and its own ramp ran
    into the next deck's cut).

    A mapped end farther from the deck than ``reach`` still takes it where
    no airside pavement (``paved``) lies over the bore between them (owner
    RULINGS 2026-11-03b Q340 a, accepted 2026-11-03T13:58Z: the trench runs
    through under the pack's deck, and the mapped tunnel past the deck is
    the same open cut — LFPG's A1 under ``H18r``, mapped as one 325 m tunnel
    under runway 09R/27L and its strips): the deck states the crossing.  No
    farther than ``far_reach`` (a deep tunnel is never opened, Q345 a), and
    only under a deck that CARRIES THE RUNWAY FAMILY (``carries_runway``;
    every other deck keeps the bore-end reach)."""
    from .structure_overlap import paved_over
    from .structure_underpass import UNDERPASS_TAG
    stated = all(UNDERPASS_TAG in (w.tags or {}) for w in getattr(mouth.bore, "ways", ()) or ())
    best = None
    pt = Point(mouth.xy)
    line = mouth.bore.line
    for db in decks:
        poly = deck_polygon(db)
        x = line.intersection(poly)
        if x.length <= 1.0:
            continue
        d = 0.0 if poly.contains(pt) else poly.exterior.distance(pt)
        far = paved is not None and d <= far_reach and carries_runway is not None \
            and carries_runway(db)
        if not (d <= reach or stated) and far:
            s_end = line.project(pt)
            s_x = [line.project(Point(q)) for g in getattr(x, "geoms", [x]) for q in g.coords]
            s_in = min(s_x, key=lambda v: abs(v - s_end))
            if paved_over(line, min(s_end, s_in), max(s_end, s_in), paved):
                continue
        elif not (d <= reach or stated):
            continue
        if best is None or d < best[0]:
            best = (d, db)
    return None if best is None else best[1]


def _road_dir(db: DeckBridge) -> XY:
    """The unit direction ACROSS the line between the deck's end lines —
    the way a road under it runs."""
    ax = sum(p[0] for p in db.seats_a) / len(db.seats_a)
    ay = sum(p[1] for p in db.seats_a) / len(db.seats_a)
    bx = sum(p[0] for p in db.seats_b) / len(db.seats_b)
    by = sum(p[1] for p in db.seats_b) / len(db.seats_b)
    n = math.hypot(bx - ax, by - ay) or 1.0
    return (-(by - ay) / n, (bx - ax) / n)


def across_dir(db: DeckBridge) -> XY:
    """The unit direction from end A to end B — across the road."""
    rx, ry = _road_dir(db)
    return (ry, -rx)


def project_span(ring, r: XY) -> tuple[float, float]:
    """``(least, greatest)`` of the ring's points projected on ``r``."""
    vals = [q[0] * r[0] + q[1] * r[1] for q in ring]
    return min(vals), max(vals)


def mid_line(db: DeckBridge) -> tuple[XY, float]:
    """``(normal, offset)`` of the deck's MIDLINE: the line between its end
    lines' directions halfway across the deck along the road — one line,
    whichever mouth reads it."""
    r = _road_dir(db)
    lo, hi = project_span(db.ring, r)
    return r, 0.5 * (lo + hi)


def _gap_line(db: DeckBridge, other: DeckBridge) -> tuple[XY, float]:
    """``(normal, offset)`` of the line halfway across the open stretch
    between two decks over one road — the same line from either side."""
    a, b = sorted((db, other), key=lambda d: d.ring)
    ca, cb = deck_polygon(a).centroid, deck_polygon(b).centroid
    n = math.hypot(cb.x - ca.x, cb.y - ca.y) or 1.0
    r = ((cb.x - ca.x) / n, (cb.y - ca.y) / n)
    return r, 0.5 * (project_span(a.ring, r)[1] + project_span(b.ring, r)[0])


def deck_mouth(axis: LineString, inward: XY, db: DeckBridge) -> tuple[LineString, float]:
    """``(axis, metres moved)``: the mouth of a bore under ``db`` stands at
    the deck's MIDLINE (:func:`mid_line`) — the two mouths of one bore
    each cut half the deck, flat at its floor, and climb beyond its edge.
    Under a SLAB (``db.slab``) the ground stays under the deck: the mouth
    stands at the deck's edge on its own side, and the cut stops there."""
    from .structure_mouth import _moved_in
    m = axis.coords[0]
    r, off = mid_line(db)
    dot = inward[0] * r[0] + inward[1] * r[1]
    if abs(dot) <= 1e-6:
        return axis, 0.0
    if db.slab:
        lo, hi = project_span(db.ring, r)
        off = hi if m[0] * r[0] + m[1] * r[1] > off else lo
    return _moved_in(axis, inward, (off - (m[0] * r[0] + m[1] * r[1])) / dot)


def _half_plane(line: tuple[XY, float], toward: XY, big: float) -> Polygon:
    """The side of ``line`` (``(normal, offset)``) holding the point
    ``toward``, as a ``big`` box."""
    (nx, ny), off = line
    sg = 1.0 if toward[0] * nx + toward[1] * ny >= off else -1.0
    px, py = nx * off, ny * off
    tx, ty = -ny, nx
    c0 = (px + tx * big, py + ty * big)
    c1 = (px - tx * big, py - ty * big)
    return Polygon([c0, c1, (c1[0] + sg * nx * big, c1[1] + sg * ny * big),
                    (c0[0] + sg * nx * big, c0[1] + sg * ny * big)])


def deck_cut(db: DeckBridge, axis: LineString, ramp, outer, inset: float,
             other: "DeckBridge | None" = None,
             band: "tuple[float, float] | None" = None, bank_run: float = 0.0,
             roads=None, uncut=None, rim_off: float = 0.0):
    """``(ramp, outer)`` of a corridor under ``db`` (module doc): clipped to
    its own side of the deck's midline (the mouth line — the bore's other
    mouth cuts the rest, so no end cap stands across the trench) and,
    toward ``other`` deck over the same road, to its own side of the line
    halfway across the open stretch; the footprint takes in the deck ring
    ``inset`` inside its edge — the bank from the road edge up to the deck
    (Q-A as ruled) — or, under a WALLED deck, the floor runs to the walls'
    inner faces and the rim stands ``inset`` behind them
    (:func:`_walled_trench`, RULINGS 2026-10-30f (3)).  ``band`` is this
    corridor's LANE of the deck — ``(lo, hi)`` across the road
    (``planar/deck_bores.lane_band``): the bank stops halfway to the next
    carriageway's own cut.  Under a SLAB the floor stops ``bank_run`` short
    of the deck's edge: no wall stands there, so the ground comes down from
    the deck to the trench floor as an embankment (owner 2026-11-03T16:56Z:
    "assume a sloping embankment coming down from bridge ends to the trench
    bottom").  ``roads``: the mapped road ribbons beside the cut — THE
    ROAD-EDGE WITNESS (16:56Z): the bank never cuts into one; the cut's
    rim stands at its edge (vertical where it meets the carriageway).

    Deck redesign §3 (owner 2026-11-03T21:16Z Q1 "yes"; RULINGS 2026-11-03b
    Q343 a): under a wall-less hard deck the cut takes the WHOLE ring
    ``inset`` inside its edge, its floor running at level B to the toe of a
    ``bank_run`` bank from each end line (:func:`_floor_under`; the road's
    own width where that is wider); and ``uncut`` — the runway-family
    pavement no deck ring carries, which the cut never takes — stands as a
    RIM: the cut stops at its edge and the floor ``rim_off`` short of it,
    so the void between them is the vertical step (never a floor vertex on
    the runway)."""
    big = 10.0 * (axis.length + 1000.0)
    ahead = axis.interpolate(min(axis.length, 1.0))
    keep = _half_plane(mid_line(db), (ahead.x, ahead.y), big)
    if other is not None:
        c = deck_polygon(db).centroid
        keep = keep.intersection(_half_plane(_gap_line(db, other), (c.x, c.y), big))
    if band is not None:
        keep = keep.intersection(_lane_strip(db, band, big))
    walled = None if db.slab else _walled_trench(db, inset, other)
    if db.slab:
        # owner 2026-11-03T16:39Z: no cut under a slab — the corridor stops
        # at the deck's edge, the ground under it is the deck's; and
        # (16:53Z) the trench beside it is as wide as the object, wall to
        # wall: the deck's whole extent across the road, ``inset`` inside it
        lo, hi = project_span(db.ring, across_dir(db))
        r, n = _road_dir(db), across_dir(db)
        s0, s1 = project_span(list(outer.exterior.coords), r)
        along = Polygon([(r[0] * t + n[0] * u, r[1] * t + n[1] * u)
                         for t, u in ((s0, -big), (s1, -big), (s1, big), (s0, big))])
        wide = _lane_strip(db, (lo + inset, hi - inset), big).intersection(along)
        outer = unary_union([outer, wide.intersection(keep)])
        ramp = ramp.difference(deck_polygon(db).buffer(bank_run, join_style="mitre")
                               if bank_run > 0.0 else deck_polygon(db))
        outer = outer.difference(deck_polygon(db))
    elif walled is not None:
        # 30f (3): the floor runs to the walls' inner faces, the rim stands
        # ``inset`` behind them — no bank climbs the walls
        floor, rim = walled
        ramp = unary_union([ramp, floor])
        outer = unary_union([outer, rim, floor])
    else:
        bank = deck_polygon(db).buffer(-inset, join_style="mitre")
        if not bank.is_empty:
            outer = unary_union([outer, bank])
            floor = _floor_under(db, bank, bank_run)
            if floor is not None:
                ramp = unary_union([ramp, floor])

    if uncut is not None and not uncut.is_empty and outer.intersects(uncut):
        outer = outer.difference(uncut)
        ramp = ramp.difference(uncut.buffer(rim_off, join_style="mitre"))
    if roads is not None and not roads.is_empty:
        beside = roads.difference(ramp.buffer(0.5, join_style="mitre"))
        if not beside.is_empty:
            outer = outer.difference(beside)

    def one(g, fallback):
        g = g.intersection(keep)
        parts = [q for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and q.area > 0]
        return max(parts, key=lambda q: q.area) if parts else fallback
    return one(ramp, ramp), one(outer, outer)


def _floor_under(db: DeckBridge, bank: Polygon, bank_run: float) -> "Polygon | None":
    """THE FLOOR UNDER A WALL-LESS DECK (deck redesign §3 (a)): the ring
    ``bank`` (already ``inset`` inside its edge) less a ``bank_run`` band
    along each end line — the banks rise from the floor to the end lines
    at ``[design] bank_slope``.  ``None`` where nothing is left."""
    if bank_run <= 0.0:
        return None
    big = 10.0 * (math.sqrt(max(bank.area, 1.0)) + bank_run)
    ends = [_end_band(st, bank_run, big) for st in (db.seats_a, db.seats_b) if st]
    floor = bank.difference(unary_union(ends)) if ends else bank
    parts = [q for q in getattr(floor, "geoms", [floor])
             if q.geom_type == "Polygon" and q.area > 1.0]
    return unary_union(parts) if parts else None


def _end_band(stations, run: float, big: float) -> Polygon:
    """The band ``run`` deep on the deck's side of an end line, run on
    ``big`` past its ends (the bank's plan, :func:`_floor_under`)."""
    (x0, y0), (x1, y1) = stations[0], stations[-1]
    n = math.hypot(x1 - x0, y1 - y0)
    if n <= 1e-9:
        return Point(x0, y0).buffer(run)
    ux, uy = (x1 - x0) / n, (y1 - y0) / n
    return LineString([(x0 - ux * big, y0 - uy * big), (x1 + ux * big, y1 + uy * big)]).buffer(
        run, cap_style="flat")


def _lane_strip(db: DeckBridge, band: tuple[float, float], big: float) -> Polygon:
    """The strip ``band[0] <= u <= band[1]`` across the road (``across_dir``),
    ``big`` long along it."""
    r, n = _road_dir(db), across_dir(db)
    lo, hi = max(band[0], -big), min(band[1], big)
    return Polygon([(r[0] * s + n[0] * u, r[1] * s + n[1] * u)
                    for s, u in ((-big, lo), (big, lo), (big, hi), (-big, hi))])


def _walled_trench(db: DeckBridge, inset: float, other: "DeckBridge | None" = None
                  ) -> "tuple[Polygon, Polygon] | None":
    """``(floor, rim)`` of a WALLED deck (``planar/deck_walls``; RULINGS
    2026-10-30f (3)): the floor is the strip between the walls' inner faces
    under the deck — and, toward ``other`` deck over the same road, along
    the open stretch to it, between that stretch's own inner faces — and
    the rim the same strip ``inset`` wider (behind the walls), inside the
    deck's ring under it.  ``None`` where either side of the deck has no
    wall: the 30b bank stands there."""
    if not db.walls:
        return None
    r, n, faces = db.walls
    u_lo, u_hi = project_span(db.ring, n)
    s_lo, s_hi = project_span(db.ring, r)
    ua, ub = inner_faces(faces, s_lo, s_hi, 0.5 * (u_lo + u_hi))
    if ua is None or ub is None:
        return None
    floors = [wall_strip(r, n, ua, ub, s_lo, s_hi)]
    rims = [wall_strip(r, n, ua - inset, ub + inset, s_lo, s_hi).intersection(deck_polygon(db))]
    if other is not None:
        o_lo, o_hi = project_span(other.ring, r)
        g0, g1 = (s_hi, o_lo) if o_lo >= s_hi else (o_hi, s_lo)
        if g1 > g0:
            va, vb = inner_faces(faces, g0, g1, 0.5 * (u_lo + u_hi))
            if va is not None and vb is not None:
                floors.append(wall_strip(r, n, va, vb, g0, g1))
                rims.append(wall_strip(r, n, va - inset, vb + inset, g0, g1))
    return unary_union(floors), unary_union(rims)


def deck_ground(classification, tunnels, law, decks: _t.Sequence[DeckBridge] = ()) -> tuple:
    """``(classification with the deck-ground cells, notes)`` (module doc,
    THE GROUND THE DECK RESTS ON): for each hard deck a corridor was cut
    under, the part of its reach (``model/structures.deck_reach``: the ring,
    and the open stretch to the next deck over the same road) no cell owns
    becomes a ``graded_strip``
    cell ``deck_ground:<object>`` — ground, never pavement; its level is the
    deck span's (``constraints/edge_deck``), so it carries no zone class.
    A piece narrower than the identity spacing is a seam of the overlay,
    not ground, and is dropped.  The slabs are ``decks`` (``cut`` set,
    :func:`with_cuts`): a deck no corridor runs under mints no ground."""
    rings: dict[tuple, Polygon] = {}
    for t in tunnels:
        pts = deck_reach(t)
        reach = MultiPoint(pts).convex_hull if pts is not None else None
        if reach is not None and reach.geom_type == "Polygon":
            rings.setdefault((t.deck_bridge, tuple(reach.exterior.coords)), reach)
    if not rings:
        return classification, []
    cells, notes = _slab_ground(list(classification.cells), decks, law)
    polys = [Polygon(c.ring, c.holes) for c in cells if len(c.ring) >= 3]
    taken = canonical_union([p if p.is_valid else p.buffer(0.0) for p in polys])
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    out: list = []
    for (oid, _ring), deck in sorted(rings.items(), key=lambda kv: kv[0]):
        free = [q for q in polygon_parts_with_area(fixed_difference(deck, taken))
                if not is_hairline(q, spacing)]
        out.extend(_ground_cell(law, oid, k, part) for k, part in enumerate(free))
        if free:
            taken = canonical_union([taken, *free])
            notes.append(f"{oid}: the ground the deck rests on, {len(free)} face(s) "
                         f"{sum(q.area for q in free):.0f} m2 no cell owned under its ring, "
                         f"held flush (RULINGS 2026-10-30b / 30f (4))")
    if not out and not notes:
        return classification, notes
    merged = [_dc.replace(c, id=i) for i, c in enumerate(cells + out)]
    return _dc.replace(classification, cells=tuple(merged)), notes


def _ground_cell(law, oid: str, k: int, part: Polygon) -> Cell:
    """One ``deck_ground:<object>[#k]`` face: ground, never pavement."""
    return Cell(0, "graded_strip", f"{DECK_GROUND_REF}:{oid}" + (f"#{k}" if k else ""),
                tuple(part.exterior.coords)[:-1],
                tuple(tuple(h.coords)[:-1] for h in part.interiors),
                None, None, role_side(law, "graded_strip"), "structure",
                {"deck_ground": 1.0, "area_m2": part.area})


def _slab_ground(cells: list, decks, law) -> tuple[list, list[str]]:
    """``(cells, notes)`` with the ground UNDER A SLAB the deck's (round 3
    §3): inside a slab's ring every cell aircraft do not roll on
    (``law.tables.rolled_on_roles``; never a road name list) becomes deck
    ground ``deck_ground:<object>#k``, so its vertices carry only the deck's
    span pair (``constraints/edge_deck``) — a mapped road or strip kept
    under the slab held its own rows and lifted the end line's seat
    (KIAH ``obj24551`` end B, 39 pairs on one seat)."""
    from ..law.tables import rolled_on_roles
    slabs: dict[str, Polygon] = {}
    for db in decks:
        if db.cut == "slab" and len(db.ring) >= 3:
            slabs.setdefault(db.object_id, deck_polygon(db))
    if not slabs:
        return cells, []
    keep = rolled_on_roles(law) | {"tunnel_ramp", "retaining_wall"}
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    out: list = []
    taken: dict[str, list] = {}
    for c in cells:
        if c.role in keep or len(c.ring) < 3 or str(c.ref).startswith(DECK_GROUND_REF + ":"):
            out.append(c)
            continue
        p = Polygon(c.ring, c.holes)
        p = p if p.is_valid else p.buffer(0.0)
        hit = [(oid, r) for oid, r in sorted(slabs.items()) if p.intersects(r)
               and p.intersection(r).area > 0.25]
        if not hit:
            out.append(c)
            continue
        rest = p
        for oid, r in hit:
            under = [q for q in polygon_parts_with_area(rest.intersection(r))
                     if not is_hairline(q, spacing)]
            taken.setdefault(oid, []).extend(under)
            rest = fixed_difference(rest, r)
        for k, part in enumerate(q for q in polygon_parts_with_area(rest)
                                 if not is_hairline(q, spacing)):
            out.append(_dc.replace(c, ref=c.ref if k == 0 else f"{c.ref}#{k}",
                                   ring=tuple(part.exterior.coords)[:-1],
                                   holes=tuple(tuple(h.coords)[:-1] for h in part.interiors)))
    notes = []
    for oid, parts in sorted(taken.items()):
        out.extend(_ground_cell(law, oid, 100 + k, q) for k, q in enumerate(parts))
        notes.append(f"{oid}: under the SLAB, {len(parts)} face(s) "
                     f"{sum(q.area for q in parts):.0f} m2 of ground the aircraft do not roll "
                     f"on are the deck's ground (round 3 §3)")
    return out, notes


def deck_pin(db: DeckBridge, mouth):
    """The deck bridge as the ``airport/portal_objects.Portal`` the
    structure pass pins ``mouth`` with: never slid, its depth the deck's."""
    from ..airport.portal_objects import Portal
    return Portal(db.object_id, db.resource, tuple(mouth.xy),
                  int(mouth.ways[0]) if mouth.ways else 0, db.depth_m, 0.0,
                  tuple(mouth.xy), False, db.ring, ())


def deck_seats(db: DeckBridge, axis: LineString, other: "DeckBridge | None",
               gap: float
               ) -> tuple[float, "float | None", tuple, tuple, "DeckBridge | None"]:
    """``(climb_from, level_to, floor stretch, seats, other deck)`` of a corridor under
    ``db`` (``Tunnel.edge_floor_s`` / ``edge_seats``): the floor is level
    under the whole deck and climbs ``gap`` beyond its far edge — or, running
    into another deck, stays at the floors to the midpoint between them
    (``level_to``), linear from this deck's floor at its edge to the other's
    at its own (Q271 b).  ``other`` is the deck this one RUNS THROUGH to (the pairing
    is ``structure_overlap.run_pair``'s, the one place two cuts on one road
    are paired, RULINGS 2026-11-03b Q340 a).  Each deck states two seats,
    end A then end B, as ``(object id, the end's stations, the depth
    there)``."""
    def two(d: DeckBridge) -> tuple:
        return ((d.object_id, d.seats_a, d.depth_a), (d.object_id, d.seats_b, d.depth_b))
    s_own = max((axis.project(Point(q)) for q in db.ring), default=0.0)
    x = axis.intersection(deck_polygon(other)) if other is not None and other is not db else None
    if x is None or x.is_empty:
        return s_own + gap, None, (), two(db), None
    s_other = max(s_own, min(axis.project(Point(q)) for g in getattr(x, "geoms", [x])
                             for q in g.coords))
    # the stop: where the axis meets the line halfway across the stretch
    (nx, ny), off = _gap_line(db, other)
    a, b = axis.interpolate(s_own), axis.interpolate(s_other)
    fa, fb = a.x * nx + a.y * ny - off, b.x * nx + b.y * ny - off
    stop = s_own if abs(fb - fa) <= 1e-9 else s_own + (s_other - s_own) * fa / (fa - fb)
    return stop, stop, (s_own, s_other), two(db) + two(other), other


def deck_side(db: DeckBridge, inward: XY) -> int:
    """Which way a mouth under ``db`` looks into its bore — ``+1`` / ``-1``
    across the line between the deck's two end lines: the carriageways
    whose mouths stand on one side of the deck are one cut, the two sides
    two."""
    ax = sum(p[0] for p in db.seats_a) / len(db.seats_a)
    ay = sum(p[1] for p in db.seats_a) / len(db.seats_a)
    bx = sum(p[0] for p in db.seats_b) / len(db.seats_b)
    by = sum(p[1] for p in db.seats_b) / len(db.seats_b)
    return 1 if inward[0] * -(by - ay) + inward[1] * (bx - ax) >= 0.0 else -1
