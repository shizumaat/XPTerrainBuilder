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

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import types
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.airside_deck_seat import facing_contacts
from ..classify.roles import Cell
from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..geom.parts import polygon_parts_with_area
from ..law.tables import role_side
from ..model.structures import DECK_GROUND_REF, deck_reach
from .deck_walls import inner_faces, wall_faces, wall_strip

__all__ = ["deck_bridges", "deck_under", "deck_mouth", "deck_seats", "deck_side",
           "deck_cut", "deck_pin", "deck_ground", "DECK_GROUND_REF"]

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class DeckBridge:
    """One hard-deck piece the airport's pavement drives across (module doc)."""

    object_id: str
    resource: str
    #: every placement of the bridge's frame (the deck's anchor, heading)
    members: tuple[str, ...]
    #: the deck piece's outline (frame xy)
    ring: tuple[XY, ...]
    #: the seat stations of end A and end B (frame xy, on the ring)
    seats_a: tuple[XY, ...]
    seats_b: tuple[XY, ...]
    #: the authored deck top at end A / end B, and the frame's bottom (y)
    top_a: float
    top_b: float
    bottom_y: float
    #: the pre-solve rendered deck top: the estimate a mouth plans from
    deck_z: float
    #: the frame's WALLS under the deck, ``(r_w, n_w, faces)``: their own
    #: direction, across it, and each face as ``(u, s0, s1)`` in that frame
    #: (``planar/deck_walls.wall_faces``, RULINGS 2026-10-30f (3)); ``()``
    #: for a deck the pack models no wall under
    walls: tuple = ()

    @property
    def depth_a(self) -> float:
        return self.top_a - self.bottom_y

    @property
    def depth_b(self) -> float:
        return self.top_b - self.bottom_y

    @property
    def depth_m(self) -> float:
        return 0.5 * (self.depth_a + self.depth_b)

    @property
    def polygon(self) -> Polygon:
        p = Polygon(self.ring)
        return p if p.is_valid else p.buffer(0.0)


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


def _slab(cache, decks) -> list[tuple[float, float, float]]:
    """Every deck placement's ``ATTR_hard_deck`` vertex as ``(x, y, top y)``
    in the frame."""
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


def _top_at(slab, seats, reach: float, top: float) -> float:
    near = [y for x, yy, y in slab if any(math.hypot(x - s[0], yy - s[1]) <= reach
                                          for s in seats)]
    return max(near) if near else top


def _bottom_y(cache, frame, trenches) -> tuple[float, bool]:
    """``(the frame's bottom y, walled)``: a co-placed trench object's walls'
    bottom (``walled``: the frame is then the trench object's), else the
    lowest genuine solid of the frame's placements."""
    ids = {str(q.id) for q in frame}
    tr = [t for t in trenches or () if str(t.object_id) in ids]
    if tr:
        return -max(float(t.depth_m) for t in tr), True
    ys = [c.min_y for q in frame if q.resolved for c in cache.genuine(q.resolved)]
    return (min(ys) if ys else 0.0), False


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


def deck_bridges(objects, cache, classification, airport, law, trenches=()
                 ) -> tuple[tuple[DeckBridge, ...], list[str]]:
    """``(every hard-deck bridge, one note per deck piece refused)``
    (module doc)."""
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
        slab = _slab(cache, decks)
        top = max((y for _x, _y, y in slab), default=None)
        if top is None or d.deck_top_z is None:
            continue
        bottom, walled = _bottom_y(cache, frame, trenches)
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
            pair = facing_contacts(ring_ll, surface, step)
            where = f"{d.id} {str(d.path).rsplit('/', 1)[-1]} piece {piece.area:,.0f} m2"
            if pair is None:
                notes.append(f"{where}: no pavement runs across it (RULINGS 2026-10-27c)")
                continue
            if _beside_a_building(frame, piece, roles):
                notes.append(f"{where}: a building stands beside it in its frame (22n)")
                continue
            sa, sb = (tuple(to_xy(lo, la) for la, lo in e) for e in pair)
            reach = max(2.0 * step, 3.0)
            ta, tb = _top_at(slab, sa, reach, top), _top_at(slab, sb, reach, top)
            db = DeckBridge(str(d.id), str(d.path), tuple(str(q.id) for q in frame),
                            tuple(piece.exterior.coords[:-1]), sa, sb, ta, tb,
                            float(bottom), float(d.deck_top_z) - top + 0.5 * (ta + tb))
            r, n = _road_dir(db), _across_dir(db)
            mine.append(_dc.replace(db, walls=wall_faces(cache, frame, float(bottom),
                                                         0.5 * (ta + tb), r, n)))
        # ONE zero per object (30a (1)): every piece plans from one estimate
        z = _deck_z(airport, [p for db in mine for p in db.seats_a + db.seats_b], None)
        out.extend(db if z is None else _dc.replace(db, deck_z=z) for db in mine)
    return tuple(out), notes


def _deck_z(airport, seats, rendered: "float | None") -> "float | None":
    """The pre-solve estimate of the deck top: the ground at its end lines,
    where the design solve will grade the taxiway it is flush with (the
    rendered top stands on the DEM at the anchor, under the road), else the
    rendered top."""
    dem = getattr(airport, "dem", None)
    zs = [float(dem.z(x, y)) for x, y in seats] if dem is not None else []
    zs = [z for z in zs if math.isfinite(z)]
    return sum(zs) / len(zs) if zs else rendered


def deck_under(mouth, decks: _t.Sequence[DeckBridge], reach: float) -> "DeckBridge | None":
    """The hard-deck bridge a mouth's BORE runs under: its line crosses the
    deck's ring and the mapped end stands within ``reach`` of it — the
    nearest such."""
    best = None
    pt = Point(mouth.xy)
    for db in decks:
        poly = db.polygon
        if mouth.bore.line.intersection(poly).length <= 1.0:
            continue
        d = 0.0 if poly.contains(pt) else poly.exterior.distance(pt)
        if d <= reach and (best is None or d < best[0]):
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


def _across_dir(db: DeckBridge) -> XY:
    """The unit direction from end A to end B — across the road."""
    rx, ry = _road_dir(db)
    return (ry, -rx)


def _across(ring, r: XY) -> tuple[float, float]:
    vals = [q[0] * r[0] + q[1] * r[1] for q in ring]
    return min(vals), max(vals)


def _mid_line(db: DeckBridge) -> tuple[XY, float]:
    """``(normal, offset)`` of the deck's MIDLINE: the line between its end
    lines' directions halfway across the deck along the road — one line,
    whichever mouth reads it."""
    r = _road_dir(db)
    lo, hi = _across(db.ring, r)
    return r, 0.5 * (lo + hi)


def _gap_line(db: DeckBridge, other: DeckBridge) -> tuple[XY, float]:
    """``(normal, offset)`` of the line halfway across the open stretch
    between two decks over one road — the same line from either side."""
    a, b = sorted((db, other), key=lambda d: d.ring)
    ca, cb = a.polygon.centroid, b.polygon.centroid
    n = math.hypot(cb.x - ca.x, cb.y - ca.y) or 1.0
    r = ((cb.x - ca.x) / n, (cb.y - ca.y) / n)
    return r, 0.5 * (_across(a.ring, r)[1] + _across(b.ring, r)[0])


def deck_mouth(axis: LineString, inward: XY, db: DeckBridge) -> tuple[LineString, float]:
    """``(axis, metres moved)``: the mouth of a bore under ``db`` stands at
    the deck's MIDLINE (:func:`_mid_line`) — the two mouths of one bore
    each cut half the deck, flat at its floor, and climb beyond its edge."""
    from .structure_mouth import _moved_in
    m = axis.coords[0]
    r, off = _mid_line(db)
    dot = inward[0] * r[0] + inward[1] * r[1]
    if abs(dot) <= 1e-6:
        return axis, 0.0
    return _moved_in(axis, inward, (off - (m[0] * r[0] + m[1] * r[1])) / dot)


def deck_far(db: DeckBridge, axis: LineString, decks: _t.Sequence[DeckBridge]
             ) -> "tuple[float, float, DeckBridge] | None":
    """``(own far edge s, the stop s, the other deck)``: where ``axis``
    (from ``db``'s midline outward) runs into ANOTHER deck's ring beyond its
    own — the open stretch between two bridges over one road: the trench
    stays at the floors to the midpoint between the two (the other deck's
    mouth cuts the rest), and never climbs (Q271 b)."""
    s_own = max((axis.project(Point(q)) for q in db.ring), default=0.0)
    best = None
    for o in decks:
        if o is db or o.ring == db.ring:
            continue
        x = axis.intersection(o.polygon)
        if x.is_empty:
            continue
        s0 = min(axis.project(Point(q)) for g in getattr(x, "geoms", [x])
                 for q in g.coords)
        if s0 >= s_own - 1e-6 and (best is None or s0 < best[0]):
            best = (s0, o)
    if best is None:
        return None
    return float(s_own), float(0.5 * (s_own + best[0])), best[1]


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
             other: "DeckBridge | None" = None):
    """``(ramp, outer)`` of a corridor under ``db`` (module doc): clipped to
    its own side of the deck's midline (the mouth line — the bore's other
    mouth cuts the rest, so no end cap stands across the trench) and,
    toward ``other`` deck over the same road, to its own side of the line
    halfway across the open stretch; the footprint takes in the deck ring
    ``inset`` inside its edge — the bank from the road edge up to the deck
    (Q-A as ruled) — or, under a WALLED deck, the floor runs to the walls'
    inner faces and the rim stands ``inset`` behind them
    (:func:`_walled_trench`, RULINGS 2026-10-30f (3))."""
    big = 10.0 * (axis.length + 1000.0)
    ahead = axis.interpolate(min(axis.length, 1.0))
    keep = _half_plane(_mid_line(db), (ahead.x, ahead.y), big)
    if other is not None:
        c = db.polygon.centroid
        keep = keep.intersection(_half_plane(_gap_line(db, other), (c.x, c.y), big))
    walled = _walled_trench(db, inset, other)
    if walled is not None:
        # 30f (3): the floor runs to the walls' inner faces, the rim stands
        # ``inset`` behind them — no bank climbs the walls
        floor, rim = walled
        ramp = unary_union([ramp, floor])
        outer = unary_union([outer, rim, floor])
    else:
        bank = db.polygon.buffer(-inset, join_style="mitre")
        if not bank.is_empty:
            outer = unary_union([outer, bank])

    def one(g, fallback):
        g = g.intersection(keep)
        parts = [q for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and q.area > 0]
        return max(parts, key=lambda q: q.area) if parts else fallback
    return one(ramp, ramp), one(outer, outer)


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
    u_lo, u_hi = _across(db.ring, n)
    s_lo, s_hi = _across(db.ring, r)
    ua, ub = inner_faces(faces, s_lo, s_hi, 0.5 * (u_lo + u_hi))
    if ua is None or ub is None:
        return None
    floors = [wall_strip(r, n, ua, ub, s_lo, s_hi)]
    rims = [wall_strip(r, n, ua - inset, ub + inset, s_lo, s_hi).intersection(db.polygon)]
    if other is not None:
        o_lo, o_hi = _across(other.ring, r)
        g0, g1 = (s_hi, o_lo) if o_lo >= s_hi else (o_hi, s_lo)
        if g1 > g0:
            va, vb = inner_faces(faces, g0, g1, 0.5 * (u_lo + u_hi))
            if va is not None and vb is not None:
                floors.append(wall_strip(r, n, va, vb, g0, g1))
                rims.append(wall_strip(r, n, va - inset, vb + inset, g0, g1))
    return unary_union(floors), unary_union(rims)


def deck_ground(classification, tunnels, law) -> tuple:
    """``(classification with the deck-ground cells, notes)`` (module doc,
    THE GROUND THE DECK RESTS ON): for each hard deck a corridor was cut
    under, the part of its reach (``model/structures.deck_reach``: the ring,
    and the open stretch to the next deck over the same road) no cell owns
    becomes a ``graded_strip``
    cell ``deck_ground:<object>`` — ground, never pavement; its level is the
    deck span's (``constraints/edge_deck``), so it carries no zone class.
    A piece narrower than the identity spacing is a seam of the overlay,
    not ground, and is dropped."""
    rings: dict[tuple, Polygon] = {}
    for t in tunnels:
        reach = deck_reach(t)
        if reach is not None and reach.geom_type == "Polygon":
            rings.setdefault((t.deck_bridge, tuple(reach.exterior.coords)), reach)
    if not rings:
        return classification, []
    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells if len(c.ring) >= 3]
    taken = canonical_union([p if p.is_valid else p.buffer(0.0) for p in polys])
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    out: list = []
    notes: list[str] = []
    for (oid, _ring), deck in sorted(rings.items(), key=lambda kv: kv[0]):
        free = [q for q in polygon_parts_with_area(fixed_difference(deck, taken))
                if not is_hairline(q, spacing)]
        for k, part in enumerate(free):
            out.append(Cell(0, "graded_strip", f"{DECK_GROUND_REF}:{oid}" + (f"#{k}" if k else ""),
                            tuple(part.exterior.coords)[:-1],
                            tuple(tuple(h.coords)[:-1] for h in part.interiors),
                            None, None, role_side(law, "graded_strip"), "structure",
                            {"deck_ground": 1.0, "area_m2": part.area}))
        if free:
            taken = canonical_union([taken, *free])
            notes.append(f"{oid}: the ground the deck rests on, {len(free)} face(s) "
                         f"{sum(q.area for q in free):.0f} m2 no cell owned under its ring, "
                         f"held flush (RULINGS 2026-10-30b / 30f (4))")
    if not out:
        return classification, notes
    merged = [_dc.replace(c, id=i) for i, c in enumerate(cells + out)]
    return _dc.replace(classification, cells=tuple(merged)), notes


def deck_pin(db: DeckBridge, mouth):
    """The deck bridge as the ``airport/portal_objects.Portal`` the
    structure pass pins ``mouth`` with: never slid, its depth the deck's."""
    from ..airport.portal_objects import Portal
    return Portal(db.object_id, db.resource, tuple(mouth.xy),
                  int(mouth.ways[0]) if mouth.ways else 0, db.depth_m, 0.0,
                  tuple(mouth.xy), False, db.ring, ())


def deck_seats(db: DeckBridge, axis: LineString, decks: _t.Sequence[DeckBridge],
               gap: float) -> tuple[float, "float | None", tuple, tuple, "DeckBridge | None"]:
    """``(climb_from, level_to, floor stretch, seats, other deck)`` of a corridor under
    ``db`` (``Tunnel.edge_floor_s`` / ``edge_seats``): the floor is level
    under the whole deck and climbs ``gap`` beyond its far edge — or, running
    into another deck, stays at the floors to the midpoint between them
    (``level_to``), linear from this deck's floor at its edge to the other's
    at its own (Q271 b).  Each deck states two seats, end A then end B, as
    ``(object id, the end's stations, the depth there)``."""
    def two(d: DeckBridge) -> tuple:
        return ((d.object_id, d.seats_a, d.depth_a), (d.object_id, d.seats_b, d.depth_b))
    s_own = max((axis.project(Point(q)) for q in db.ring), default=0.0)
    far = deck_far(db, axis, decks)
    if far is None:
        return s_own + gap, None, (), two(db), None
    s_own, _stop, other = far
    x = axis.intersection(other.polygon)
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
