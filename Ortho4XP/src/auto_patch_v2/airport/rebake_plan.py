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
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from ..model.rebake import FlatDatum, Member, RebakePlan, Unit
from . import deck_signature as _deck
from . import obj8 as _obj8
from .pack_partition import PackPartition, Screen, partition_pack

__all__ = ["plan", "screen_of", "DeckDatum"]

#: ``deck_datum(ring_xy) -> z | None``: the SOLVED surface's value at a
#: deck ring (``emit.rebake.deck_datum_from_surface`` bound to the emitted
#: surface by the pipeline); ``None`` = read the mesh at the ring instead.
DeckDatum = _t.Callable[[_t.Sequence[XY]], "float | None"]


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
         tunnel_objects: _t.Mapping[str, tuple[float, _t.Sequence[XY]]] | None = None,
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
    in frame xy)``: RE-SEATED so the plate sits on the ground at the
    band (RULINGS 2026-09-05n-4, ``tunnel.object.reseat``) — THAT OBJECT
    only (RULINGS 2026-09-09s (1)).

    ``partition`` is the LOAD-time reading of the pack
    (``pack_partition.partition_pack``, spec §11a (3)); when it is given
    this call FILTERS it.  ``None`` re-reads the pack in the OLD order —
    the twin's control arm.
    """
    # TUNNEL WALL OBJECTS (RULINGS 2026-09-05n-4): plate-seated, by id
    plates: dict[str, tuple[float, _t.Sequence[XY]]] = dict(tunnel_objects or {})
    if not law.tables.structures.tunnel.object.reseat:
        plates = {}
    screen, objs = screen_of(objects, cache, law, exclude, below_grade, plates)
    if partition is None:
        part = partition_pack(airport, objs, cache, law, screen)
    else:
        part = partition.filtered(screen, law)
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
                           else _with_deck(m, o, to_ll, deck_datum, plates, counts))
        units.append(_dc.replace(u, id=f"unit:{ui}", members=tuple(members)))
    flat = _flat_datum(airport, to_ll)
    if flat is not None:
        counts["flat_site"] = int(flat.substitutes)
    return RebakePlan(airport.icao, airport.pack.name, part.pack_root, tuple(units),
                      part.skipped, counts, part.contacts, flat, part.abutments)


def _with_deck(m: Member, o: _obj8.PlacedObject, to_ll, deck_datum, plates,
               counts: dict[str, int]) -> Member:
    """``m`` with the PLANAR and SOLVED fields attached: the hard-deck
    ring and its datum (or the signature plate's ends / profile /
    stations) and the tunnel-wall plate's height and band stations.
    These are the only member fields the load-time partition cannot
    carry — every one of them reads a planar product or the solve."""
    deck_ring = deck_top_y = deck_datum_z = deck_ends = None
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
        counts["deck_members"] += 1
    plate_y = None
    plate_stations: tuple[tuple[float, float], ...] = ()
    if o.id in plates:
        plate_y, st_xy = plates[o.id]
        plate_stations = tuple(to_ll(x, y) for x, y in st_xy)
        counts["plate_members"] += 1
    return _dc.replace(m, deck_ring=deck_ring, deck_top_y=deck_top_y,
                       deck_datum_z=deck_datum_z, deck_kind=o.deck_kind,
                       deck_ends=deck_ends, deck_profile=deck_profile,
                       deck_evidence=tuple(o.deck_evidence),
                       deck_stations=deck_stations, plate_y=plate_y,
                       plate_stations=plate_stations)


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
