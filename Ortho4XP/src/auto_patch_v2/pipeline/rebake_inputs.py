"""THE PLANAR AND SOLVED FACTS THE REBAKE PLAN READS beyond the pack
partition (owner RULINGS 2026-10-04x (1); 04f-1): the plate seats of the
tunnel walls and basins, the excluded and authored placements, the
below-grade regions and the solved deck datum — ONE assembly
(:func:`_rebake_inputs`) for the build's emit stage and any instrument
that replays its rebake section."""
from __future__ import annotations

import typing as _t

from ..emit.rebake import deck_datum_from_surface
from . import authored_seats as _authored_seats

__all__ = ["plate_stations"]


def _plate_seats(pm, law, seats=None) -> dict[str, tuple[float, list, float]]:
    """Placement id -> ``(plate y, stations in frame xy)`` for every
    PLATE-seated structure member: a tunnel wall object (RULINGS
    2026-09-05n-4: plate height above its seat; the stations stand at the
    walls' OUTER FACE + ``emit.identity.min_distinct_spacing_m`` outward,
    every ``bridge.abutment_sample_step_m`` along the object's own
    footprint — RULINGS 2026-09-08d (c): never on the rim ring, whose
    vertices sample the trench drop (OTHH tunnels middle-west/-east
    −2.30 / −2.09), and whichever side of the outer face the rim stands
    on) and a basin member (RULINGS 2026-09-06b (3), ``basin.seat =
    "floor_plate"``: the family's floor-plate y — NEGATIVE, under the
    rendered y = 0 plane — and points ON the trench floor face, so the
    seat's delta = floor − (mesh(anchor) + agl + plate y) lands the plate
    on the floor — and, 2026-09-09ac (2), ONLY for the basin's own
    witness resource ``Basin.witness_id``, never for every member).  ``emit/rebake._plate_reading`` reads both alike.

    AUTHORED TO THE CUT (object-placement spec §18 (3); owner RULINGS
    2026-10-07c (3)-(5)): a member whose authored seat already works over
    the cut (``seats``, ``authored_seats.seat_records``) is NOT entered —
    it is never re-seated; a wall that is re-seated carries the pack's
    median proud height as the plate's clearance over the ground its
    stations read (0.0 = flush, 05n-4)."""
    seats = _authored_seats.seat_records(pm, law) if seats is None else seats
    kept = _authored_seats.kept_ids(seats)
    from shapely.geometry import LineString as _LS
    from shapely.geometry import Point as _Pt
    from shapely.geometry import Polygon as _Poly
    grid = law.tables.emit.identity.min_distinct_spacing_m
    step = law.tables.structures.bridge.abutment_sample_step_m
    rim_off = law.tables.structures.tunnel.wall_gap_m + law.tables.structures.tunnel.wall_band_width_m
    tol = law.tables.structures.tunnel.wall_band_width_m + 2.0 * grid
    out: dict[str, tuple[float, list]] = {}
    for tn in pm.structures:
        if tn.source != "object" or not tn.objects:
            continue
        # RULINGS 2026-09-08o: the stations stand OUTSIDE the EMITTED rim
        # ring (``wall_path``) on at-grade ground, never on the mesh wall
        # face (57 of unit:8's 70 stations lay inside the rim ring, pushed
        # outside the outer face by the arrangement's snap) and never in
        # the ramp beyond the wall end
        beyond = None
        if tn.top_s > tn.wall_length_m + 1e-6 and len(tn.axis) >= 2:
            ax = _LS(tn.axis)
            s0, s1 = min(tn.wall_length_m, ax.length), min(tn.top_s, ax.length)
            if s1 - s0 > 1e-6:
                seg = [ax.interpolate(s0)] + [_Pt(q) for q in tn.axis
                                                if s0 < ax.project(_Pt(q)) < s1] + [ax.interpolate(s1)]
                beyond = _LS([(q.x, q.y) for q in seg]).buffer(tn.half_width_m + rim_off + grid)
        pts = plate_stations(tn.footprint, grid, step, tn.wall_path, beyond)
        if not pts:
            # no footprint recorded: the rim ring inside the walls (pre-08d)
            pts = list(tn.wall_path)
            if tn.wall_length_m > 0.0 and tn.top_s > tn.wall_length_m + 1e-6:
                ax = _LS(tn.axis)
                pts = [p for p in pts if ax.project(_Pt(p)) <= tn.wall_length_m + tol]
        for oid in tn.objects:
            if oid in kept:
                continue
            # the seat reads the CREST (plate_y_m): an edge wall's depth
            # is the bore law's, its crest still goes flush (2026-09-06c)
            out[oid] = (float(tn.plate_y_m or tn.depth_m), pts,
                        float((seats.get(oid) or {}).get("proud_m") or 0.0))
    out.update(_edge_seat_plates(pm, kept, law))
    if law.tables.structures.basin.seat != "floor_plate":
        return out
    for b in pm.basins:
        floor = _Poly(b.ring)
        inner = floor.buffer(-2.0 * grid)
        pts = list((inner if not inner.is_empty and inner.geom_type == "Polygon"
                    else floor).exterior.coords)[:-1]
        if not pts:
            continue
        # RULINGS 2026-09-09ac (2): the plate seat is the BASIN'S OWN
        # WITNESS RESOURCE's — the object whose floor plate the basin cut
        # (``Basin.witness_id``, the deepest genuine solid, the one
        # ``plate_y_m`` is measured from).  Another member whose plate
        # merely SHARES that plate y is not plate-seated: it seats by its
        # feet like any other resource (measured at LEMD: 12 of the 13
        # "plate" members were terminal slabs the basin half claimed at
        # the T4S basin's own −7.048 / +5.206 / … plate y, standing them
        # 12–17 m off their own feet — spec §11.4).
        # A SPLIT-LEVEL BUILDING (``planar/split_level_pit``) is one frame:
        # every member seats its lower floor on the floor, as one
        seated = (b.member_ids if b.kind == "split_level" else (b.witness_id,)) \
            if b.witness_id else ()
        for oid in seated:
            if oid in kept:
                continue
            # ... and the plate stands ``floor_clearance_m`` ABOVE the
            # trench floor its stations read (11t §24 (2)): the floor row
            # dropped the terrain by that much so the plate renders, and a
            # seat without it would chase the object straight back down.
            # ... and a split-level building's lower floor is a DATUM: it
            # meets the floor at its stations at any authored height (a
            # lower floor authored under the zero, KLAX's terminals at y -4,
            # otherwise kept its zero on the pit floor and sank a storey)
            clear = b.clearance(law.tables.structures.basin.floor_clearance_m)
            out.setdefault(oid, (float(b.plate_y_m), pts, clear, SPLIT_PLATE)
                           if b.kind == "split_level" else (float(b.plate_y_m), pts, clear))
    return out


#: the plate kind of an EDGE BRIDGE's seat (``anchor_rule.datum_of``)
EDGE_PLATE = "edge"
#: the plate kind of a SPLIT-LEVEL building's lower floor (``planar/split_level_pit``)
SPLIT_PLATE = "split_level"
def _edge_seat_plates(pm, kept, law=None) -> dict[str, tuple]:
    """Placement id -> ``(0.0, [seat], 0.0, EDGE_PLATE)`` for every edge
    bridge an edge trench meets (``Tunnel.edge_seats``,
    ``planar/bridge_span``): its ZERO — the deck its top is — sits on the
    solved surface at its seat, the airside pavement it edges (owner
    RULINGS 2026-10-27r "the top of the objects flush with the airside
    surface"; sim read 2026-10-28T14:26Z point 2: a single-placement edge
    object re-cut as a BASIN body took its zero from the trench's rim, 8-10
    m under the taxiway).  The anchor reads it FIRST (§16e's datum,
    ``anchor_rule.datum_of``), ahead of the basin rim."""
    out: dict[str, tuple] = {}
    for ov in getattr(pm, "overpasses", ()) or ():
        # a ROAD OVERPASS (``planar/overpass_deck``, RULINGS 2026-10-30f
        # (5)): its zero on the road beneath, every deck piece's stations
        if ov.object_id not in kept:
            y, st, *rest = out.get(ov.object_id, (0.0, [], 0.0, OVERPASS_PLATE))
            out[ov.object_id] = (y, st + [tuple(p) for p in ov.stations
                                          if tuple(p) not in st], *rest)
    tops: dict[str, dict] = {}
    if law is not None and getattr(pm, "decks", ()):
        from ..constraints.deck_lines import end_lines
        for oid, es in sorted(end_lines(pm, law).items()):
            _deck_plate(out, oid, es, kept, pm, tops)
    for tn in pm.structures:
        if getattr(tn, "deck_bridge", ""):
            continue
        for oid, seat, _depth in getattr(tn, "edge_seats", ()) or ():
            if oid not in kept:
                out.setdefault(oid, (0.0, [tuple(seat)], 0.0, EDGE_PLATE))
    for oid, by_pt in tops.items():
        # the deck's y is the stations' own mean top, each station once —
        # the reference ``constraints/edge_deck._station_rows`` holds every
        # station flush from (RULINGS 2026-10-30a (1))
        y, st, *rest = out[oid]
        out[oid] = (sum(by_pt.values()) / len(by_pt), st, *rest)
    _unit_members(out, pm, kept)
    return out


def _unit_members(out: dict, pm, kept) -> None:
    """ONE ZERO PER UNIT (owner 2026-11-03T23:21Z): every placement
    co-placed with a pack deck (``DeckBridge.members``, its frame — EDDF's
    ``Bridge_4_hard`` with its ``_asph`` / ``_asph_dark`` layers, one anchor)
    takes the deck's own plate, so the frame seats at one zero; read each on
    its own ring they stood at 104.92 / 103.67 / 106.22 (#1663)."""
    for db in getattr(pm, "decks", ()) or ():
        plate = out.get(db.object_id)
        if plate is None or plate[3] != DECK_PLATE:
            continue
        for m in db.members:
            if m != db.object_id and m not in kept:
                out.setdefault(m, plate)


#: the plate kind of a HARD-DECK BRIDGE's end lines (``airside_deck_seat``)
DECK_PLATE = "deck"
#: the plate kind of a ROAD OVERPASS's road beneath (``airside_deck_seat``):
#: its y is the zero's own, 0.0
OVERPASS_PLATE = "overpass"


def _deck_plate(out: dict, oid: str, es, kept, pm, tops: dict) -> None:
    """A PACK DECK's deck member (owner RULINGS 2026-10-30a (1),
    ``planar/deck_bridge``; deck redesign §1: read off ``PlanarMap.decks``
    whether or not a corridor runs under it): ``(deck top y, every end
    line's stations, 0.0, DECK_PLATE[, anchor zero])`` — its zero is the
    solved surface at its end lines less its top, ONE zero for the whole
    frame (``airside_deck_seat.airside_zero`` reads it first); ``es`` its
    end lines (``constraints/deck_lines``), every deck piece of the object.

    #1692: the stations are the SEAT VERTICES the design solve held flush
    (the pavement the end lines name) — never the raw ring points: a
    facing contact that wraps the deck's corner stands its last stations
    on the side edge beside the trench, and KBNA's walled cut read them
    166.6-171.6 m, the zero 0.53 m under the taxiway."""
    if oid in kept or not es:
        return
    deck = es[0].deck
    bottom = float(deck.bottom_y)
    y, st, *rest = out.get(oid, (0.5 * (deck.top_a + deck.top_b), [], 0.0, DECK_PLATE))
    # deck-end-anchors spec §3: the zero the anchors state — the anchor's
    # level less its end line's top, less the frame's bottom
    held = [a for a in getattr(pm, "deck_anchors", ()) or () if a.object_id == oid]
    if held and len(rest) < 3:
        rest = [*rest, held[0].z_m - held[0].top_y - bottom]
    by_pt = tops.setdefault(oid, {})
    for e in es:
        pts = [tuple(pm.vertices[v].xy) for v, _w in e.terms]
        for p in pts:
            by_pt.setdefault(p, bottom + float(e.depth))
        st = st + [p for p in pts if p not in st]
    out[oid] = (y, st, *rest)


def plate_stations(footprint, standoff_m: float, step_m: float, rim_path=(),
                   exclude=None) -> list:
    """RULINGS 2026-09-08d (c) / 2026-09-08o: the plate seat's stations for
    a wall object of plan ``footprint`` (its walls' outer faces, a ring in
    frame xy): the footprint UNITED with the emitted rim ring (``rim_path``
    — the trench's at-grade rim as built, which the arrangement's outward
    snap can push OUTSIDE the outer face, 08e deviation 2) where that ring
    lies against the footprint, grown by ``standoff_m`` (mitred, so the
    corners stay corners) and sampled every ``step_m`` along the exterior
    — points OUTSIDE both the wall and the rim ring, on the at-grade
    ground, never on the mesh wall face; a station inside ``exclude`` (the
    ramp beyond the wall end) is dropped.  ``[]`` without a footprint."""
    import math as _m

    from shapely.geometry import Point as _Pt
    from shapely.geometry import Polygon as _Poly
    from shapely.ops import unary_union as _uu
    if not footprint or len(footprint) < 3:
        return []
    poly = _Poly(footprint)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.geom_type != "Polygon":
        return []
    region = poly
    rim = None
    if rim_path and len(rim_path) >= 3:
        rim = _Poly(rim_path)
        if not rim.is_valid:
            rim = rim.buffer(0)
        if not rim.is_empty:
            # only the rim's extent AGAINST the object: the rim beyond the
            # walls (an OSM stand-off along the climb) is the ramp's
            near = rim.intersection(poly.buffer(standoff_m * 2.0, join_style="mitre"))
            poke = near.difference(poly) if not near.is_empty else near
            if not poke.is_empty and poke.area > 1e-9:
                # the rim stands outside the wall somewhere: the region grows
                # by it (a rim wholly inside the wall leaves the footprint as
                # it is — the ring keeps its own vertex order)
                region = _uu([poly, near])
                if region.geom_type != "Polygon":
                    region = max((g for g in region.geoms if g.geom_type == "Polygon"),
                                 key=lambda g: g.area, default=poly)
    ring = region.buffer(standoff_m, join_style="mitre").exterior
    n = max(4, int(_m.ceil(ring.length / step_m)))
    pts = [tuple(ring.interpolate(k * ring.length / n).coords[0]) for k in range(n)]
    keep = []
    for q in pts:
        pq = _Pt(q)
        if rim is not None and not rim.is_empty and rim.contains(pq):
            continue
        if exclude is not None and not exclude.is_empty and exclude.contains(pq):
            continue
        keep.append(q)
    return keep


def _basin_polygon(b):
    """A basin's admitted region as a frame polygon (the deck signature's
    below-grade spanning evidence, 04k), ``None`` when degenerate."""
    from shapely.geometry import Polygon
    try:
        p = Polygon(b.region or b.ring)
        return p if p.is_valid and not p.is_empty else p.buffer(0)
    except (ValueError, TypeError):
        return None


def _stamp_cut_rings(seats: dict, pm, airport) -> None:
    """Owner RULINGS 2026-10-26d (#1331): each pack OBJECT cut's footprint
    ring, ``[[lat, lon], ...]``, on the seat record of every placement it
    was read from (``airport/cut_deck_seat.CUT_RING``) — the witness the
    object stage reads to seat a pack deck over the pack's own cut."""
    from ..airport.cut_deck_seat import CUT_FRAME_Z, CUT_RING
    to_ll = airport.frame.transformers()[1]
    for tn in getattr(pm, "structures", ()):
        if getattr(tn, "source", "") != "object":
            continue
        ring = tuple(getattr(tn, "footprint", ()) or ()) or tuple(tn.wall_path or ())
        if len(ring) < 3:
            continue
        ll = [[round(q[0], 9), round(q[1], 9)] for q in (to_ll(x, y) for x, y in ring)]
        for oid in tn.objects:
            if oid in seats:
                seats[oid][CUT_RING] = ll
                if getattr(tn, "cut_frame", ()):
                    # owner 2026-11-05 §0.5: the frame zero its floor was read at
                    seats[oid][CUT_FRAME_Z] = round(float(tn.cut_frame[1]), 3)


def _rebake_inputs(pm, law, surf, airport) -> dict[str, _t.Any]:
    """THE PLANAR AND SOLVED FACTS the rebake plan reads beyond the pack
    partition — ``tunnel_objects`` (the plate seats) / ``exclude`` /
    ``below_grade`` / ``deck_datum``, the keywords ``rebake_screen.take``
    and ``rebake_plan.plan`` share.  ONE assembly: the build and any
    instrument that replays its rebake section call this."""
    _to_xy = airport.frame.transformers()[0]
    # a basin family is PLATE-seated onto its floor (2026-09-06b (3)),
    # never excluded; ``exclude`` stays for any other caller
    excluded = set() if law.tables.structures.basin.seat == "floor_plate" \
        else {oid for b in pm.basins for oid in b.objects}
    # seat = "none" (RULINGS 2026-09-08b/c, spec §2 / §3): a door
    # ramp's or a sunken road's family is NEVER re-seated by its
    # trench — the cluster law would sink the well's neighbours into
    # the ramp (measured OTHH: 8 Parking-Left/Right objects written)
    excluded |= {oid for tn in pm.structures
                 if tn.source in ("door", "sunken_road", "wall_corridor")
                 for oid in tn.objects}
    # AUTHORED TO THE CUT (object-placement spec §18 (3) (b)): a wall or a
    # pit whose authored seat already works over the cut is the author's —
    # no plate seat and no other seat either
    seats = _authored_seats.seat_records(pm, law)
    excluded |= _authored_seats.kept_ids(seats)
    _stamp_cut_rings(seats, pm, airport)
    # issue #1730: a terrain-shaped hard deck's row is seated at its DEM fit
    from ..airport import object_floor as _of
    from ..airport import terrain_shaped as _ts
    floors = tuple(getattr(pm, "object_floors", ()) or ())
    # #1903: a trench object's floor and its frame are written whole at
    # their read zero — no other seat moves them (a deck of the frame the
    # pavement drives across is planned: ``ObjectFloor.decks``, B2)
    excluded |= {pid for f in floors for pid, _r, _z in f.seats}
    return {
        "tunnel_objects": _plate_seats(pm, law, seats),
        "authored_seats": (tuple(seats[k] for k in sorted(seats))
                           + tuple(_ts.seat_records(airport))
                           + tuple(_ts.portal_seat_records(pm.structures,
                                                           airport.frame.transformers()[1]))
                           + tuple(_of.seat_records(floors, airport.frame.transformers()[1]))),
        "exclude": excluded,
        "below_grade": [(_basin_polygon(b), tuple(b.objects)) for b in pm.basins],
        # the SOLVED surface's value at every hard deck — ``emit/rebake.py``
        "deck_datum": lambda ring, _s=surf: deck_datum_from_surface(_s, ring, _to_xy)}
