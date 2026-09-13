"""THE RE-SEAT PLAN (RULINGS 2026-09-04i 04f-1; 06g): the anchor families,
their members' welded PARTS and the pack-wide ε-CONTACT GRAPH
(``airport/contact.py``), from the loader's AUTHORED reading of the
objects (``airport/pack.py`` restore-before-read).  Runs at PATCH time
inside the pipeline; the plan is the tile build's
``o4_v2_rebake_<ICAO>.json`` sidecar, seated after the mesh by
``emit/rebake.py`` / ``emit/clusters.py``.  Law: ``structures.toml
[rebake]``.  No environment is read here.

**THE READING MOVED OUT** (owner RULINGS 2026-09-11j; spec §11a (3)).
Objects to members, parts, feet, contacts, abutments and the deck /
skirt / line verdicts are ``airport/pack_partition.partition_pack`` and
run ONCE at LOAD, because the pad law needs the pack's bodies before
``classify``.  What is left here is the SCREEN — the planar and solved
facts about which members and components leave the seat — and the
attachment of the deck ring, the deck datum and the plate stations.
``plan()`` therefore FILTERS a partition; passing none re-reads the pack
in the OLD order (filter, then partition), which is the control arm of
the round's order twin and nothing the shipped pipeline uses.
"""
from __future__ import annotations


import dataclasses as _dc
import math as _math
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from ..model.rebake import FlatDatum, Member, RebakePlan, Unit
from . import deck_signature as _deck
from . import obj8 as _obj8
from .pack_partition import (PackPartition, Screen, extend_partition,
                             partition_pack)

__all__ = ["plan", "screen_of", "DeckDatum", "ring_ends", "end_line_stations"]

#: ``deck_datum(ring_xy) -> z | None``: the SOLVED surface's value at a
#: deck ring (``emit.rebake.deck_datum_from_surface`` bound to the emitted
#: surface by the pipeline); ``None`` = read the mesh at the ring instead.
DeckDatum = _t.Callable[[_t.Sequence[XY]], "float | None"]


# ── §16e (2): THE DECK'S END LINES (owner RULINGS 2026-09-13k) ───────────

def ring_ends(ring: _t.Sequence[tuple[float, float]]
              ) -> "tuple[tuple[tuple[float, float], tuple[float, float]], tuple[tuple[float, float], tuple[float, float]]] | None":
    """A deck ring's two END LINES — ``((a, b), (c, d))`` in ``(lat, lon)``,
    the shape ``Member.deck_ends`` already carries for a SIGNATURE deck.

    R12 read the deck top at the abutments and a SIGNATURE deck's plate
    hands its ends over (``deck_plate.ends``).  A FLAG deck — an
    ``ATTR_hard_deck`` ring, which is every bridge OTHH's pack authors —
    has no plate and stamped ``deck_ends = None``, so §16e (2)'s datum
    had nothing to read: the ends are derived HERE, from the ring.

    The ring's PRINCIPAL AXIS is the span (a bridge is long); the ends
    are its two extreme cross-sections.  Every point within a BAND of
    each extreme (5 % of the span, at least a metre — an end is a
    chamfered edge, not one vertex) is taken, and the end line joins the
    two of them furthest apart ACROSS the axis: the deck's own width
    there.  Plan geometry only — no surface is read, and "on land" is
    the DATUM's reading, not this one (:func:`anchor_rule._datum_anchor`
    discards a station on water).

    ``None`` for a ring of fewer than three points or one with no
    extent."""
    if len(ring) < 3:
        return None
    lat0 = sum(p[0] for p in ring) / len(ring)
    lon0 = sum(p[1] for p in ring) / len(ring)
    m_lat, m_lon = _mpd(lat0)
    pts = [((p[0] - lat0) * m_lat, (p[1] - lon0) * m_lon) for p in ring]
    n = float(len(pts))
    mx = sum(q[0] for q in pts) / n
    my = sum(q[1] for q in pts) / n
    a = sum((q[0] - mx) ** 2 for q in pts) / n
    b = sum((q[0] - mx) * (q[1] - my) for q in pts) / n
    c = sum((q[1] - my) ** 2 for q in pts) / n
    th = 0.5 * _math.atan2(2.0 * b, a - c)
    ux, uy = _math.cos(th), _math.sin(th)
    proj = [((q[0] - mx) * ux + (q[1] - my) * uy,
             -(q[0] - mx) * uy + (q[1] - my) * ux) for q in pts]
    lo_s = min(q[0] for q in proj)
    hi_s = max(q[0] for q in proj)
    span = hi_s - lo_s
    if span <= 0.0:
        return None
    band = max(1.0, 0.05 * span)
    out = []
    for keep in (lambda s: s <= lo_s + band, lambda s: s >= hi_s - band):
        ix = [i for i, q in enumerate(proj) if keep(q[0])]
        i1 = min(ix, key=lambda i: (proj[i][1], i))
        i2 = max(ix, key=lambda i: (proj[i][1], -i))
        out.append((tuple(ring[i1]), tuple(ring[i2])))
    return (out[0], out[1])


def end_line_stations(ends, step_m: float) -> tuple[tuple[float, float], ...]:
    """Both end lines sampled every ``step_m`` (``[bridge]
    abutment_sample_step_m``, the step R12's own abutment reading used),
    endpoints included — the STATIONS §16e (2)'s datum reads the ground
    at."""
    out: list[tuple[float, float]] = []
    for a, b in (ends or ()):
        m_lat, m_lon = _mpd(0.5 * (a[0] + b[0]))
        length = _math.hypot((b[0] - a[0]) * m_lat, (b[1] - a[1]) * m_lon)
        k = max(2, int(_math.ceil(length / step_m))) if step_m > 0.0 else 2
        out.extend((a[0] + (b[0] - a[0]) * i / k,
                    a[1] + (b[1] - a[1]) * i / k) for i in range(k + 1))
    return tuple(out)


def _mpd(lat: float) -> tuple[float, float]:
    r = _math.radians(lat)
    return (111_132.954 - 559.822 * _math.cos(2 * r) + 1.175 * _math.cos(4 * r),
            111_412.84 * _math.cos(r) - 93.5 * _math.cos(3 * r))


def screen_of(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
              law: Law, exclude: _t.Collection[str] = (),
              below_grade: _t.Sequence[tuple[object, _t.Collection[str]]] = (),
              plates: _t.Mapping[str, object] | None = None) -> tuple[Screen, list]:
    """The PLANAR half of the old ``plan()``: which members and which
    components leave the seat.  Returns ``(screen, objects)`` — the
    objects with the below-grade deck PROMOTION applied (04k), which is
    a planar fact and so belongs here and not at load."""
    rb = law.tables.structures.rebake
    plate_ids = frozenset(plates or ())
    # the basin records name their members by resource PATH
    # (``planar.basins``); the ids here match either spelling
    ex = set(exclude)
    excluded = {o.id for o in objects if o.id in ex or o.path in ex}
    basin_members: set[str] = set()
    objs = list(objects)
    if below_grade:
        owners = {oid for _r, ids in below_grade for oid in ids}
        basin_members = {o.id for o in objs if o.id in owners or o.path in owners}
        foreign = [o for o in objs if o.id not in owners and o.path not in owners]
        keep = {o.id for o in foreign}
        promoted, _n = _deck.promote(foreign, [r for r, _ids in below_grade])
        by_id = {o.id: o for o in promoted}
        objs = [by_id.get(o.id, o) if o.id in keep else o for o in objs]
    fam_of = {o.id: _deck.family_key(o) for o in objs if o.resolved is not None}
    deck_keys = {fam_of[o.id] for o in objs
                 if o.resolved is not None and o.deck_kind in ("flag", "signature")}
    deck_family = {o.id for o in objs if fam_of.get(o.id) in deck_keys}
    #: RULINGS 2026-09-09w (1): THE BELOW-GRADE TEST IS PER COMPONENT.
    #: 10ax (2): a basin facility is never demoted by it — the pit IS its
    #: members' below-grade geometry.
    below_comps: dict[str, frozenset[int]] = {}
    facility: set[str] = set()
    for o in objs:
        if o.resolved is None or o.id in excluded:
            continue
        exempt = ((o.id in deck_family and rb.deck_family_seats_rigid)
                  or o.id in plate_ids or o.id in basin_members)
        deep = frozenset() if exempt else frozenset(o.below_grade_comps)
        if not deep:
            continue
        below_comps[o.id] = deep
        genuine_ix = [i for i, c in enumerate(cache.components(o.resolved))
                      if c.max_y - c.min_y >= cache.thickness_m]
        if genuine_ix and deep.issuperset(genuine_ix):
            facility.add(o.id)
    #: 14.1 rule 4: a member whose elevation a STRUCTURE seat governs is
    #: never a line object (10bb rule 2)
    structure_seated = {o.id for o in objs
                        if o.id in deck_family or o.id in plate_ids
                        or o.id in basin_members or o.hard_deck is not None}
    plate_paths = plate_ids | {o.path for o in objs if o.id in plate_ids}
    return Screen(frozenset(excluded), frozenset(basin_members), frozenset(plate_paths),
                  frozenset(deck_family), below_comps, frozenset(facility),
                  frozenset(structure_seated)), objs


def plan(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
         cache: _obj8.ResourceCache, law: Law, deck_datum: DeckDatum | None = None,
         exclude: _t.Collection[str] = (),
         below_grade: _t.Sequence[tuple[object, _t.Collection[str]]] = (),
         tunnel_objects: _t.Mapping[str, tuple] | None = None,
         partition: PackPartition | None = None) -> RebakePlan:
    """The units and witnesses for ``airport``'s pack (see module doc).

    ``objects`` are the planar pass's placed objects (read from the
    AUTHORED files, the deck signature applied); ``deck_datum`` the
    solved surface's reading at a flagged deck ring; ``exclude`` the
    placement ids the TERRAIN adapted to (the basin facilities, RULINGS
    2026-08-26 / v1 ruling R4) — THAT MEMBER only is never re-seated
    (RULINGS 2026-09-09q (1): the anchor-family expansion is deleted —
    Aerosoft anchors LEMD's whole terminal pack at two points, so one
    wall-corridor member excluded 300 placements over 32 m of relief);
    every other member of the family seats per body (09d);
    ``below_grade`` the emitted below-grade regions ``(frame polygon,
    owner ids)`` — a CANDIDATE plate of a foreign family over one is a
    deck (``deck_signature.promote``).  THE BELOW-GRADE SKIP IS PER
    COMPONENT (RULINGS 2026-09-09w (1)).  ``tunnel_objects`` the tunnel
    wall objects by placement id → ``(plate height, wall-band stations
    in frame xy, the plate's clearance above the ground they read — 0 for a
    tunnel wall, ``[basin] floor_clearance_m`` for a basin, 11t §24 (2))``: RE-SEATED so the plate sits on the ground at the
    band (RULINGS 2026-09-05n-4, ``tunnel.object.reseat``) — THAT OBJECT
    only (RULINGS 2026-09-09s (1)).

    ``partition`` is the LOAD-time reading of the pack
    (``pack_partition.partition_pack``, spec §11a (3)); when it is given
    this call FILTERS it.  ``None`` re-reads the pack in the OLD order —
    the twin's control arm.
    """
    # TUNNEL WALL OBJECTS (RULINGS 2026-09-05n-4): plate-seated, by id
    plates: dict[str, tuple] = dict(tunnel_objects or {})
    if not law.tables.structures.tunnel.object.reseat:
        plates = {}
    screen, objs = screen_of(objects, cache, law, exclude, below_grade, plates)
    if partition is None:
        part = partition_pack(airport, objs, cache, law, screen)
    else:
        # THE SECOND PHASE (owner RULINGS 2026-09-11l (1)): the load
        # partition ran on the SCREENED set, so the PLATE-exempt
        # multi-anchor placements — a planar fact — are partitioned back
        # in INCREMENTALLY here, against the existing part set only.
        part = extend_partition(partition, airport, cache, law,
                                screen.plate_paths).filtered(screen, law)
    _to_xy, to_ll = airport.frame.transformers()
    by_id = {o.id: o for o in objs}
    counts = dict(part.counts)
    counts["plate_objects"] = len(plates)
    counts["plate_members"] = 0
    counts["deck_members"] = 0
    units: list[Unit] = []
    for ui, u in enumerate(part.units):
        members: list[Member] = []
        for mi, m in enumerate(u.members):
            oid, _opath = part.member_object.get((ui, mi), (m.id, m.resource))
            o = by_id.get(oid)
            members.append(m if o is None
                           else _with_deck(m, o, to_ll, deck_datum, plates, counts,
                                           law))
        units.append(_dc.replace(u, id=f"unit:{ui}", members=tuple(members)))
    flat = _flat_datum(airport, to_ll)
    if flat is not None:
        counts["flat_site"] = int(flat.substitutes)
    return RebakePlan(airport.icao, airport.pack.name, part.pack_root, tuple(units),
                      part.skipped, counts, part.contacts, flat, part.abutments)


def _with_deck(m: Member, o: _obj8.PlacedObject, to_ll, deck_datum, plates,
               counts: dict[str, int], law: Law | None = None) -> Member:
    """``m`` with the PLANAR and SOLVED fields attached: the hard-deck
    ring and its datum (or the signature plate's ends / profile /
    stations) and the tunnel-wall plate's height and band stations.
    These are the only member fields the load-time partition cannot
    carry — every one of them reads a planar product or the solve."""
    deck_ring = deck_top_y = deck_datum_z = deck_ends = None
    deck_end_stations: tuple[tuple[float, float], ...] = ()
    deck_profile: tuple[tuple[float, float], ...] = ()
    deck_stations: tuple[tuple[float, float, float], ...] = ()
    if o.hard_deck is not None and o.deck_top_z is not None:
        poly = o.hard_deck
        if poly.geom_type != "Polygon":
            poly = max(poly.geoms, key=lambda g: g.area)
        ring_xy = [(float(x), float(y)) for x, y in poly.exterior.coords[:-1]]
        deck_ring = tuple(to_ll(x, y) for x, y in ring_xy)
        deck_top_y = float(o.deck_top_z - o.anchor_z - o.agl_m)
        if o.deck_kind == "signature" and o.deck_plate is not None:
            # THE ABUTMENTS (R12): the deck top lands at the ground at the
            # deck's END LINES, on land — read after the mesh by
            # ``emit/rebake.py``; the solved surface is not consulted (a
            # bridge over a canal stands outside every graded face)
            pl = o.deck_plate
            if pl.ends is not None:
                deck_ends = tuple(tuple(to_ll(x, y) for x, y in e) for e in pl.ends)
            deck_profile = tuple(pl.profile)
            deck_stations = tuple((*to_ll(sx, sy), float(y)) for (sx, sy), y in pl.stations)
        else:
            deck_datum_z = deck_datum(ring_xy) if deck_datum is not None else None
            if deck_datum_z is None and law is not None:
                # §16e (2): A FLAG DECK OVER NO GRADED FACE GETS ITS END
                # LINES FROM ITS RING.  R12's abutment reading needs the
                # deck's ends and only a SIGNATURE deck's plate hands
                # them over; OTHH's bridges are all flag decks, and three
                # of them (Bridge_01/04/05) stand over the canal, where
                # the solved surface has no face at all and the datum the
                # seat era read is exactly this one.
                deck_ends = ring_ends(deck_ring)
                deck_end_stations = end_line_stations(
                    deck_ends,
                    law.tables.structures.bridge.abutment_sample_step_m)
                if deck_end_stations:
                    counts["deck_end_lines"] = counts.get("deck_end_lines", 0) + 1
        counts["deck_members"] += 1
    plate_y = None
    plate_clearance = 0.0
    plate_stations: tuple[tuple[float, float], ...] = ()
    if o.id in plates:
        # a 2-entry value is a pre-11t caller: clearance 0.0, the old law
        plate_y, st_xy, *rest = plates[o.id]
        plate_clearance = float(rest[0]) if rest else 0.0
        plate_stations = tuple(to_ll(x, y) for x, y in st_xy)
        counts["plate_members"] += 1
    return _dc.replace(m, deck_ring=deck_ring, deck_top_y=deck_top_y,
                       deck_datum_z=deck_datum_z, deck_kind=o.deck_kind,
                       deck_ends=deck_ends, deck_profile=deck_profile,
                       deck_evidence=tuple(o.deck_evidence),
                       deck_stations=deck_stations,
                       deck_end_stations=deck_end_stations, plate_y=plate_y,
                       plate_stations=plate_stations,
                       plate_clearance_m=plate_clearance)


def _flat_datum(airport: Airport, to_ll) -> FlatDatum | None:
    """THE FLAT-SITE DATUM (RULINGS 2026-09-08d; spec
    othh-seat-artefacts-spec.md §2): the verdict, Z0 and the datum region
    in lat/lon travel with the plan — the post-mesh seat founds anchors
    and ground on Z0 inside it."""
    fv = airport.flat_site
    if fv is None:
        return None
    return FlatDatum(fv.verdict, fv.z0_m, fv.source,
                     tuple((tuple(to_ll(x, y) for x, y in outer),
                            tuple(tuple(to_ll(x, y) for x, y in h) for h in holes))
                           for outer, holes in fv.region))
