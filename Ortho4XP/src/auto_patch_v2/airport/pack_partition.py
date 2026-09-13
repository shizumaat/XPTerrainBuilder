"""THE PACK PARTITION AT LOAD (owner RULINGS 2026-09-11j; spec
``object-placement-spec.md`` §11a (3)).

``rebake_plan.plan()`` used to do two different jobs in one pass: it READ
THE PACK — objects to members, members to welded parts and ground feet,
parts to the ε-contact graph and the authored-frame abutments, plus the
deck / skirt / line verdicts — and it FILTERED that reading by what the
planar pass and the solve had since decided (the basin facilities the
terrain adapted to, the below-grade components, the tunnel-wall plates,
the solved surface's value at a hard deck).  The first job reads nothing
but the pack, the law and the DEM under each anchor; the second cannot
run before ``planar``.  Round 1 of lane ``v2canopy`` measured the
consequence: the pad law needs the pack's BODIES and ABUTMENTS, the pads
are minted in ``classify``, and ``classify`` runs long before ``plan()``
— pad ← group ← abutments ← planar ← classify ← pad, a cycle.

So the first job moves here and runs ONCE at LOAD.  :func:`partition_pack`
is the reading; :class:`Screen` is everything the planar products know
about which members and which components leave the seat; and
:meth:`PackPartition.filtered` applies a screen to a reading that already
exists.  ``rebake_plan.plan()`` is then a thin consumer: build the screen,
filter the load-time partition, attach the planar / solved deck and plate
fields, and emit the ``RebakePlan``.

**THE TWO ORDERS ARE NOT IDENTICAL, AND THE DIFFERENCE IS THE POINT.**
Partition-then-filter is not filter-then-partition:

* the ε-contact edge set is a CONNECTIVITY-EQUIVALENT SPANNING subset
  (``contact.partition``: a pair already joined transitively is never
  tested), so removing a screened part's edges afterwards can leave two
  parts unjoined that the old order would have joined directly;
* a member the screen drops entirely (a basin facility, a stock resource
  at a second anchor) still contributes PARTS to the load partition, so
  ``pools`` / ``structures`` and the pid numbering differ;
* the LINE verdict (10bb) is planar-independent, but the STRUCTURE-SEAT
  exemptions that override it (14.1 rule 4: a deck, a plate, a basin
  member is never a line object) are not — so a structure-seated member
  is partitioned here with DRAPE STATIONS where the old order gave it
  ground feet.

``filtered`` therefore RE-STATES the line verdict for the screened set and
drops the screened parts and every contact / abutment that touches one.
The round's first twin (``tests/auto_patch_v2/test_v2canopy2.py``)
compares ``contacts`` / ``abutments`` / ``parts`` of the two orders on the
LEMD and OTHH DSFTool dumps already in the mod cache and reports the
difference.

Pure reading: the pack, the law, and the DEM the loader already sampled
at every anchor.  No planar product, no solved surface, no environment.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import typing as _t

import numpy as np

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from ..model.rebake import Member, Part, Unit
from . import contact as _contact
from . import deck_signature as _deck
from . import line_object as _line
from . import obj8 as _obj8
from . import skirt as _skirt
from .pack import live_path_of

__all__ = ["Screen", "PackPartition", "partition_pack", "extend_partition",
           "counts_zero"]


def counts_zero() -> dict[str, int]:
    return {"placements": 0, "unresolved": 0, "stock": 0,
            "outside_pack": 0, "msl": 0, "multi_anchor": 0,
            "units": 0, "members": 0, "deck_members": 0,
            "parts": 0, "no_parts": 0, "contacts": 0, "pools": 0,
            "structures": 0, "pairs_tested": 0, "pairs_unproved": 0,
            "skirted_members": 0, "elevated_decks": 0,
            "terrain_adapted": 0, "line_objects": 0,
            "below_grade": 0, "below_grade_parts": 0,
            "deck_families": 0, "plate_members": 0, "plate_objects": 0,
            "signature_decks": 0}


@_dc.dataclass(frozen=True)
class Screen:
    """What the PLANAR products say about the pack — the half of the old
    ``plan()`` that cannot run at load.

    ``excluded`` the placement ids the terrain adapted to (that MEMBER
    only, 09q (1)); ``basin_members`` the admitted basins' own members
    (10ax (2): never demoted by the below-grade skip); ``plate_paths``
    the tunnel-wall / basin-floor plate-seated placements (09s (1), which
    are also exempt from the multi-anchor drop); ``deck_family`` the
    placement ids whose anchor family carries a deck (R12-2);
    ``below_comps`` per placement the component indices standing under
    their own ground (09w (1)); ``facility`` the placements whose EVERY
    genuine component is one, which leave the seat whole.

    An EMPTY screen is the identity: nothing is filtered, which is what
    the load-time partition is."""

    excluded: frozenset[str] = frozenset()
    basin_members: frozenset[str] = frozenset()
    plate_paths: frozenset[str] = frozenset()
    deck_family: frozenset[str] = frozenset()
    below_comps: _t.Mapping[str, frozenset[int]] = _dc.field(default_factory=dict)
    facility: frozenset[str] = frozenset()
    #: placements whose ELEVATION another law governs, so 10bb's line
    #: class must not reach them (14.1 rule 4)
    structure_seated: frozenset[str] = frozenset()

    def is_empty(self) -> bool:
        return not (self.excluded or self.basin_members or self.plate_paths
                    or self.below_comps or self.facility or self.structure_seated)


@_dc.dataclass(frozen=True)
class PackPartition:
    """The pack read once: units of members with their welded parts, the
    contact graph and the abutments, plus the index a filter needs."""

    icao: str
    pack_name: str
    pack_root: str
    units: tuple[Unit, ...]
    skipped: tuple[tuple[str, str], ...]
    counts: _t.Mapping[str, int]
    contacts: tuple[tuple[int, int], ...] = ()
    abutments: tuple[tuple[int, int], ...] = ()
    #: ``(unit index, member index) -> (placement id, DSF resource path)``
    #: — the join back to the ``PlacedObject`` the screen and the deck
    #: fields are read from.  BOTH halves are needed: a screen names a
    #: basin member by either spelling, and the multi-anchor drop is by
    #: resource path, which is not ``Member.resource`` (a pack-relative
    #: LIVE path).
    member_object: _t.Mapping[tuple[int, int], tuple[str, str]] = \
        _dc.field(default_factory=dict)
    #: unused since the two-phase order (11l (1)): the multi-anchor drop
    #: is applied AT LOAD, so nothing is left for :meth:`filtered` to drop
    multi_anchor: frozenset[str] = frozenset()
    #: how many anchors each multi-anchor resource is placed at
    anchor_count: _t.Mapping[str, int] = _dc.field(default_factory=dict)
    #: THE SECOND PHASE (owner RULINGS 2026-09-11l (1)): the multi-anchor
    #: placements dropped at load, kept so the PLATE exemption — a planar
    #: product — can be partitioned back in INCREMENTALLY by
    #: :func:`extend_partition`.  Load partition only.
    deferred: tuple[tuple[tuple[float, float, float], _obj8.PlacedObject], ...] = ()
    #: the geometry index the incremental phase queries (``_LoadGeom``);
    #: ``None`` on a filtered or already-extended reading
    geom: _t.Any = None

    def member_at(self, key: tuple[int, int]) -> Member:
        return self.units[key[0]].members[key[1]]

    # ── the filter ──────────────────────────────────────────────────────

    def filtered(self, screen: Screen, law: Law) -> "PackPartition":
        """This reading with ``screen``'s members and components removed,
        the line verdict re-stated for the structure-seated, and every
        contact / abutment touching a removed part dropped (module doc)."""
        rb = law.tables.structures.rebake
        counts = dict(self.counts)
        skipped = dict(self.skipped)
        keep_pids: set[int] = set()
        units: list[Unit] = []
        member_object: dict[tuple[int, int], str] = {}
        counts["terrain_adapted"] = 0
        counts["below_grade"] = 0
        counts["below_grade_parts"] = 0
        # the drop already ran at LOAD (11l (1)); ``self.multi_anchor`` is
        # empty and the count is carried through untouched
        counts["multi_anchor"] = int(self.counts.get("multi_anchor", 0))
        dropped_multi: set[str] = set()
        for ui, u in enumerate(self.units):
            members: list[Member] = []
            for mi, m in enumerate(u.members):
                oid, opath = self.member_object.get((ui, mi), (m.id, m.resource))
                if opath in self.multi_anchor and opath not in screen.plate_paths:
                    dropped_multi.add(opath)
                    continue
                if oid in screen.excluded:
                    counts["terrain_adapted"] += 1
                    skipped.setdefault(opath,
                                       "basin facility / structure member: the terrain "
                                       "adapted to THIS member (08-26; v1 R4; 09q (1): "
                                       "never its anchor family) — never re-seated")
                    continue
                if oid in screen.facility:
                    counts["below_grade"] += 1
                    skipped.setdefault(opath,
                                       "below-grade solids: the terrain adapts to it "
                                       "(08-26), never re-seated by its feet")
                    continue
                deep = set(screen.below_comps.get(oid, ()))
                counts["below_grade_parts"] += len(deep)
                parts = tuple(p for p in m.parts if p.comp not in deep)
                if screen.structure_seated and oid in screen.structure_seated:
                    # 14.1 rule 4: the line class must not reach a member
                    # whose elevation a structure seat governs
                    parts = tuple(_dc.replace(p, line=False) for p in parts)
                if not parts and not (oid in screen.deck_family and rb.deck_family_seats_rigid):
                    counts["no_parts"] += 1
                    skipped.setdefault(opath,
                                       "no genuine solid component: nothing to seat")
                    continue
                keep_pids.update(p.pid for p in parts)
                members.append(_dc.replace(m, parts=parts))
                member_object[(len(units), len(members) - 1)] = (oid, opath)
            if members:
                units.append(_dc.replace(u, members=tuple(members)))
        counts["multi_anchor"] += len(dropped_multi)
        for r in sorted(dropped_multi):
            skipped[r] = (f"placed at {self.anchor_count.get(r, 0)} anchors — one "
                          "file cannot carry per-placement offsets (I-4)")
        contacts = tuple((a, b) for a, b in self.contacts
                         if a in keep_pids and b in keep_pids)
        abutments = tuple((a, b) for a, b in self.abutments
                          if a in keep_pids and b in keep_pids)
        counts["units"] = len(units)
        counts["members"] = sum(len(u.members) for u in units)
        counts["parts"] = sum(len(m.parts) for u in units for m in u.members)
        counts["contacts"] = len(contacts)
        counts["abutments"] = len(abutments)
        counts["line_objects"] = sum(1 for u in units for m in u.members
                                     if m.parts and all(p.line for p in m.parts))
        return _dc.replace(self, units=tuple(units), skipped=tuple(sorted(skipped.items())),
                           counts=counts, contacts=contacts, abutments=abutments,
                           member_object=member_object, multi_anchor=frozenset(),
                           deferred=(), geom=None)


@_dc.dataclass(frozen=True)
class _LoadGeom:
    """What the incremental second phase queries (11l (1)): the load
    partition's part boxes and component ids, the member geometry it was
    read from (references into the one ``ResourceCache``, so holding it
    costs nothing), and the anchor-plane numbering it must extend."""

    index: _contact.BaseIndex
    members: tuple
    member_ref: tuple
    anchor_of_member: tuple[int, ...]
    anchor_ix: _t.Mapping[tuple[float, float, float], int]
    deck_family_ids: frozenset[str]


def _build_member(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, law: Law,
                  sc: Screen, deck_family_ids: _t.Collection[str], pack_root: str,
                  counts: dict[str, int], skipped: dict[str, str],
                  no_solid: set[str] | None = None):
    """One placement as a :class:`Member` plus the geometry the contact
    pass places, or ``None`` when nothing about it can be seated.  ONE
    implementation: the load loop and :func:`extend_partition` build a
    member identically, so an incrementally added plate is the member the
    whole pass would have built."""
    rb = law.tables.structures.rebake
    sk = law.tables.structures.skirt
    geom = cache.geometry(o.resolved)
    if geom is None:
        skipped.setdefault(o.path, "unreadable OBJ8")
        return None
    deep = set(sc.below_comps.get(o.id, ()))
    all_comps = list(enumerate(cache.components(o.resolved)))
    comps = [(i, c) for i, c in all_comps
             if c.max_y - c.min_y >= cache.thickness_m and i not in deep]
    counts["below_grade_parts"] += len(deep)
    in_deck_family = o.id in sc.deck_family or o.id in deck_family_ids
    if not comps and not (in_deck_family and rb.deck_family_seats_rigid) \
            and o.id not in sc.plate_paths and o.path not in sc.plate_paths \
            and o.hard_deck is None:
        # NO THICKNESS GATE (owner RULINGS 2026-09-11ai; spec §16 (1);
        # unconditional since the seat's retirement, 2026-09-12s).  The
        # skip was the SEAT's (08-26 §2.1: a resource with no genuine
        # solid has nothing to re-seat per vertex) and the placement
        # stage — the only object stage — has no such question: it
        # asks where a body's ZERO goes, and a resource of nothing but
        # thin panels has one like any other.  Skipped, the resource
        # never enters the plan population and stays on the pack's
        # shared-datum row: LEMD's garage roof-top pavilions
        # (``Terminal4_green-TEJ1``) rendered 15.8 m UNDER the slab they
        # stand on, and 25 resources / 25 rows were outside the plan.
        # The member is admitted with its thin components as its parts;
        # with no ground contact at all it becomes a FOOTLESS body (§14)
        # and is CARRIED by §15/§16's rule.
        if all_comps:
            comps = [(i, c) for i, c in all_comps if i not in deep]
        if not comps:
            counts["no_parts"] += 1
            skipped.setdefault(o.path, "no genuine solid component: nothing to seat")
            return None
        counts["no_solid_admitted"] = counts.get("no_solid_admitted", 0) + 1
        # §16 (1)'s own sentence: such a resource is a FOOTLESS body.  Its
        # thin panels are not ground contacts — read as feet they make a
        # two-triangle VOR marker spanning a terminal apron into a footed
        # body with three feet 50 m down, which the carrier search would
        # then offer as ground and the census would read as something to
        # stand over.  The feet are stripped where the parts are attached.
        if no_solid is not None:
            no_solid.add(o.path)
    rel = os.path.relpath(live_path_of(o.resolved), pack_root) if pack_root \
        else live_path_of(o.resolved)
    # THE FOUNDATION SKIRT (owner RULINGS 2026-09-10ag; spec §22.3)
    skirted = bool(sk.seat_low_side and _skirt.is_skirt(cache, o.resolved, law))
    counts["skirted_members"] += int(skirted)
    # THE ELEVATED DECK (owner RULINGS 2026-09-11a; spec §17.5): the
    # GATE on the cross-placement abutment group, read off the cache
    deck_body = bool(_deck.elevated_deck(cache, o.resolved, law).deck)
    counts["elevated_decks"] += int(deck_body)
    # THE LINE OBJECT (owner RULINGS 2026-09-10bb; spec §16).  The
    # STRUCTURE-SEAT exemptions of 14.1 rule 4 are a screen fact and
    # are applied by :meth:`PackPartition.filtered`.
    is_line = (o.id not in sc.structure_seated
               and _line.is_line_object(cache, o.resolved, rb))
    if is_line:
        counts["line_objects"] += 1
    # EVERY OPTIONAL FIELD IS PASSED BY NAME.  Twice now a field inserted
    # into ``model.rebake.Member`` has silently shifted this call's
    # positional tail: ``plate_clearance_m`` in 2026-09-11t (the viaduct's
    # ``elevated_deck`` read False and every member's ``skirted`` read the
    # clearance), and ``deck_end_stations`` in 5fc707eb / §16e (2), which
    # slid ``plate_y`` onto the ``()`` meant for ``plate_stations`` —
    # ``plate_y is not None`` is ``planar.group._eligible``'s first test, so
    # EVERY body at LEMD came out ineligible and the pad group law derived
    # 0 groups, 0 relief bodies (measured 2026-09-13, lane ``v2settle``).
    # Naming the tail is not a style choice: it is the only spelling a
    # future insertion cannot break.  ``tests/auto_patch_v2/test_v2settle
    # .py`` twins it.
    member = Member(id=o.id, resource=rel, authored_path=o.resolved,
                    live_path=live_path_of(o.resolved),
                    heading_deg=o.heading_deg, parts=(),
                    deck_ring=None, deck_top_y=None, deck_datum_z=None,
                    deck_kind=o.deck_kind, deck_ends=None,
                    deck_end_stations=(), deck_profile=(), deck_evidence=(),
                    deck_stations=(), plate_y=None, plate_stations=(),
                    skirted=skirted, elevated_deck=deck_body)
    return member, (o, geom, list(comps)), bool(is_line)


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) \
            == os.path.abspath(root)
    except ValueError:
        return False


def _batch_to_ll(frame):
    """``(xs, ys) -> (lats, lons)`` over arrays, the frame's own CRS."""
    from pyproj import Transformer
    inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)

    def f(xs, ys):
        lons, lats = inv.transform(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))
        return np.asarray(lats, dtype=float), np.asarray(lons, dtype=float)
    return f


def partition_pack(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                   cache: _obj8.ResourceCache, law: Law,
                   screen: Screen | None = None) -> PackPartition:
    """Read ``airport``'s pack into units, members, parts, feet, contacts
    and abutments (module doc).

    ``screen`` is normally ``None`` — the LOAD reading, unfiltered, which
    is what ``planar/group.py`` and ``classify/evidence._pads`` consume
    and what ``plan()`` filters.  A screen given here reproduces the OLD
    order (filter, then partition) and exists so the round's twin can
    measure the two against each other; nothing in the shipped pipeline
    passes one.
    """
    sc = screen or Screen()
    rb = law.tables.structures.rebake
    sk = law.tables.structures.skirt
    counts = counts_zero()
    counts["signature_decks"] = sum(1 for o in objects if o.deck_kind == "signature")
    # THE DECK FAMILIES readable at LOAD (R12-2 completeness): a
    # FLAG deck is ``ATTR_hard_deck`` in the authored file, so its family
    # is a load fact.  A SIGNATURE deck is promoted by the planar pass and
    # is a screen fact — but the screen only ever REMOVES members, so the
    # load partition must keep every member a deck family might claim or
    # the filter has nothing to restore: a deck-family member with no
    # genuine solid (Bridge_01_LOD0_004, a two-triangle sheet) still seats
    # WITH its deck and must not be dropped here.
    _fam = {o.id: _deck.family_key(o) for o in objects if o.resolved is not None}
    _deck_keys = {_fam[o.id] for o in objects
                  if o.resolved is not None and o.deck_kind in ("flag", "signature")}
    deck_family_ids = {o.id for o in objects if _fam.get(o.id) in _deck_keys}
    counts["deck_families"] = len(_deck_keys)
    counts["plate_objects"] = len(sc.plate_paths)
    skipped: dict[str, str] = {}
    #: §16 (1): the resources admitted with no genuine solid — footless by
    #: construction, so their parts carry no feet
    no_solid: set[str] = set()
    _to_xy, to_ll = airport.frame.transformers()
    to_ll_batch = _batch_to_ll(airport.frame)
    apt = airport.pack.apt_dat_path
    pack_root = os.path.dirname(os.path.dirname(apt)) if apt else ""

    anchors_by_resource: dict[str, set[tuple[float, float, float]]] = {}
    keyed: list[tuple[tuple[float, float, float], _obj8.PlacedObject]] = []
    for o in objects:
        counts["placements"] += 1
        if o.resolved is None:
            counts["unresolved"] += 1
            continue
        if o.id in sc.excluded:
            counts["terrain_adapted"] += 1
            skipped.setdefault(o.path, "basin facility / structure member: the terrain "
                                       "adapted to THIS member (08-26; v1 R4; 09q (1): "
                                       "never its anchor family) — never re-seated")
            continue
        if o.id in sc.facility:
            counts["below_grade"] += 1
            skipped.setdefault(o.path, "below-grade solids: the terrain adapts to it "
                                       "(08-26), never re-seated by its feet")
            continue
        if _obj8.is_stock_library_resource(o.path):
            counts["stock"] += 1
            skipped.setdefault(o.path, "stock library resource (shared, never baked)")
            continue
        live = live_path_of(o.resolved)
        if pack_root and not _inside(live, pack_root):
            counts["outside_pack"] += 1
            skipped.setdefault(o.path, "resolves outside the pack (a shared library "
                                       "object never carries one airport's offsets)")
            continue
        if o.kind == "OBJECT_MSL":
            counts["msl"] += 1
            skipped.setdefault(o.path, "OBJECT_MSL: not terrain-draped")
            continue
        lat, lon = to_ll(o.xy[0], o.xy[1])
        key = (round(lat, 9), round(lon, 9), round(o.agl_m, 3))
        anchors_by_resource.setdefault(o.path, set()).add(key)
        keyed.append((key, o))

    multi = {r for r, ks in anchors_by_resource.items() if len(ks) > 1}
    # THE MULTI-ANCHOR DROP RUNS AT LOAD (owner RULINGS 2026-09-11l (1)).
    # Round 2 deferred it to ``filtered`` because a PLATE-seated resource
    # is exempt and the plate set is a planar fact — and paid 2,493
    # members instead of 1,187 at LEMD for it (+37 s; OTHH +263 s).  So
    # the drop is applied HERE, on the screened set, and the exempted
    # plates come back INCREMENTALLY in :func:`extend_partition`.
    drop_now = multi - set(sc.plate_paths)
    counts["multi_anchor"] = len(drop_now)
    for r in sorted(drop_now):
        skipped[r] = (f"placed at {len(anchors_by_resource[r])} anchors — one "
                      "file cannot carry per-placement offsets (I-4)")
    deferred = tuple((key, o) for key, o in keyed
                     if o.path in drop_now) if sc.is_empty() else ()

    units_by_key: dict[tuple[float, float, float], dict[str, Member]] = {}
    placed: list[tuple[_obj8.PlacedObject, _obj8.ObjGeometry,
                       list[tuple[int, _obj8.Component]]]] = []
    line_members: set[int] = set()
    member_ref: list[tuple[tuple[float, float, float], str, str]] = []
    for key, o in keyed:
        if o.path in drop_now:
            continue
        members = units_by_key.setdefault(key, {})
        if o.path in members:
            continue        # the same resource at the same anchor twice: one bake
        built = _build_member(o, cache, law, sc, deck_family_ids, pack_root,
                              counts, skipped, no_solid)
        if built is None:
            continue
        member, mgeom, is_line = built
        if is_line:
            line_members.add(len(placed))
        members[o.path] = member
        placed.append(mgeom)
        member_ref.append((key, o.path, o.id))

    # THE ANCHOR PLANE per member (owner RULINGS 2026-09-10ay; spec §17)
    anchor_ix: dict[tuple[float, float, float], int] = {}
    anchor_of_member = [anchor_ix.setdefault(key, len(anchor_ix))
                        for key, _path, _oid in member_ref]
    part = _contact.partition(placed, rb.contact_epsilon_m, rb.contact_weld_m,
                              rb.contact_narrow_budget, rb.pool_overlap_m,
                              rb.contact_batch_rows,
                              law.tables.structures.basin.contact_band_m,
                              rb.foot_samples_max,
                              rb.elevated_base_m,
                              line_members, rb.body_feet_span_m,
                              rb.line_object_stations_max,
                              anchor_of_member, rb.plate_gap_max_m,
                              rb.abutment_extent_min_m,
                              law.tables.emit.identity.min_distinct_spacing_m)
    parts_by_member = _parts_by_member(part, to_ll_batch)
    for mi, (key, path, _oid) in enumerate(member_ref):
        m = units_by_key[key][path]
        ps = tuple(parts_by_member.get(mi, ()))
        if path in no_solid:
            ps = tuple(_dc.replace(p, feet=()) for p in ps)
        units_by_key[key][path] = _dc.replace(m, parts=ps)
        counts["parts"] += len(ps)

    units: list[Unit] = []
    member_object: dict[tuple[int, int], tuple[str, str]] = {}
    oid_of = {(key, path): oid for key, path, oid in member_ref}
    for i, (key, members) in enumerate(sorted(units_by_key.items())):
        if not members:
            continue
        names = sorted(members)
        ms = tuple(members[k] for k in names)
        for mi, nm in enumerate(names):
            member_object[(len(units), mi)] = (oid_of.get((key, nm), ms[mi].id), nm)
        units.append(Unit(f"unit:{len(units)}", (key[0], key[1]), key[2], ms))
        counts["members"] += len(ms)
    counts["units"] = len(units)
    counts["contacts"] = len(part.contacts)
    counts["abutments"] = len(part.abutments)
    counts["pools"] = part.pools
    counts["structures"] = part.structures
    counts["pairs_tested"] = part.pairs_tested
    counts["pairs_unproved"] = part.pairs_unproved
    geom = _LoadGeom(_contact.base_index(part), tuple(placed), tuple(member_ref),
                     tuple(anchor_of_member), dict(anchor_ix),
                     frozenset(deck_family_ids)) if sc.is_empty() else None
    return PackPartition(airport.icao, airport.pack.name, pack_root, tuple(units),
                         tuple(sorted(skipped.items())), counts,
                         part.contacts, part.abutments, member_object,
                         frozenset(),
                         {r: len(ks) for r, ks in anchors_by_resource.items()},
                         deferred, geom)


def _parts_by_member(part: _contact.Partition, to_ll_batch) -> dict[int, list[Part]]:
    """The placed parts as plan rows, in one batched transform."""
    out: dict[int, list[Part]] = {}
    if not part.parts:
        return out
    xs = np.array([p.centroid[0] for p in part.parts])
    ys = np.array([p.centroid[1] for p in part.parts])
    lats, lons = to_ll_batch(xs, ys)
    bx = np.array([p.plan_box for p in part.parts])
    la0, lo0 = to_ll_batch(bx[:, 0], bx[:, 1])
    la1, lo1 = to_ll_batch(bx[:, 2], bx[:, 3])
    # THE FEET (09s (2)) in one batched transform: their world y is the
    # AUTHORED y, so the seat reads mesh(foot) − y
    nf = np.array([0 if p.feet is None else p.feet.shape[0] for p in part.parts])
    if nf.sum():
        fxy = np.concatenate([p.feet for p in part.parts
                              if p.feet is not None and p.feet.shape[0]])
        fla, flo = to_ll_batch(fxy[:, 0], fxy[:, 1])
    else:
        fxy = np.zeros((0, 3))
        fla = flo = np.zeros(0)
    at = 0
    # nf is POSITIONAL over ``part.parts`` -- index it by position, never by
    # ``p.pid`` (a GLOBAL load-numbering id: ``extend_partition``'s fake
    # Partition holds only the new parts, whose pids continue the numbering,
    # so pid-indexing was an IndexError -- RULINGS 2026-09-12as (2))
    for i, (p, la, lo, a0, o0, a1, o1) in enumerate(
            zip(part.parts, lats, lons, la0, lo0, la1, lo1)):
        k = int(nf[i])
        feet = tuple((round(float(fla[at + j]), 8), round(float(flo[at + j]), 8),
                      round(float(fxy[at + j, 2]), 3)) for j in range(k))
        at += k
        # rounded to the millimetre (8 dp of a degree, 3 dp of a metre): the
        # plan is a witness set, and OTHH's 152 k parts are 26 MB unrounded
        out.setdefault(p.member, []).append(
            Part(p.pid, p.comp, round(float(la), 8), round(float(lo), 8),
                 round(p.base_y, 3), round(p.area_m2, 3),
                 (round(float(min(a0, a1)), 8), round(float(min(o0, o1)), 8),
                  round(float(max(a0, a1)), 8), round(float(max(o0, o1)), 8)),
                 feet, bool(p.line)))
    return out


def frame_xy(airport: Airport) -> _t.Callable[[float, float], XY]:
    """``(lat, lon) -> frame xy`` — the plan's coordinates are degrees and
    every geometric consumer works in the frame."""
    to_xy, _to_ll = airport.frame.transformers()

    def f(lat: float, lon: float) -> XY:
        return to_xy(lon, lat)
    return f


def extend_partition(part: PackPartition, airport: Airport,
                     cache: _obj8.ResourceCache, law: Law,
                     plate_paths: _t.Collection[str]) -> PackPartition:
    """THE SECOND PHASE (owner RULINGS 2026-09-11l (1); spec §11a).

    The load partition ran on the SCREENED object set, so every
    multi-anchor resource was dropped — including the tunnel-wall PLATE
    placements, whose exemption (09s (1)) is a PLANAR product and cannot
    be known at load.  This adds those back: their members are built by
    the same :func:`_build_member`, their parts and feet by the same
    ``contact.placed_parts``, and their ε-contacts and abutments are
    sought by SPATIAL QUERY against the existing part boxes
    (``contact.extend``) — the whole pack is never repartitioned.

    Returns ``part`` unchanged when nothing is exempt, which is the usual
    case; the caller then filters exactly as before.
    """
    geom: _LoadGeom | None = part.geom
    if geom is None or not part.deferred:
        return part
    pp = set(plate_paths)
    add = [(key, o) for key, o in part.deferred if o.path in pp or o.id in pp]
    if not add:
        return part
    rb = law.tables.structures.rebake
    counts = dict(part.counts)
    skipped = dict(part.skipped)
    sc = Screen()
    new_members: list = []
    new_ref: list[tuple[tuple[float, float, float], str, str]] = []
    new_member_rows: list[Member] = []
    line_members: set[int] = set()
    seen: set[tuple[tuple[float, float, float], str]] = set()
    readded: set[str] = set()
    for key, o in add:
        if (key, o.path) in seen:
            continue
        seen.add((key, o.path))
        built = _build_member(o, cache, law, sc, geom.deck_family_ids,
                              part.pack_root, counts, skipped)
        if built is None:
            continue
        member, mgeom, is_line = built
        if is_line:
            line_members.add(len(new_members))
        new_members.append(mgeom)
        new_member_rows.append(member)
        new_ref.append((key, o.path, o.id))
        readded.add(o.path)
        skipped.pop(o.path, None)
    if not new_members:
        return part
    anchor_ix = dict(geom.anchor_ix)
    anchor_of = list(geom.anchor_of_member) + \
        [anchor_ix.setdefault(k, len(anchor_ix)) for k, _p, _o in new_ref]
    ext = _contact.extend(geom.index, geom.members, new_members,
                          rb.contact_epsilon_m, rb.contact_weld_m,
                          rb.contact_narrow_budget, rb.contact_batch_rows,
                          law.tables.structures.basin.contact_band_m,
                          rb.foot_samples_max, rb.elevated_base_m,
                          line_members, rb.body_feet_span_m,
                          rb.line_object_stations_max, anchor_of,
                          rb.plate_gap_max_m, rb.abutment_extent_min_m,
                          law.tables.emit.identity.min_distinct_spacing_m)
    to_ll_batch = _batch_to_ll(airport.frame)
    fake = _contact.Partition(ext.parts, (), 0, 0, 0, 0, ())
    rows = _parts_by_member(fake, to_ll_batch)
    base_n = len(geom.members)
    # ── merge: rebuild the units from the load reading plus the added ──
    by_key: dict[tuple[float, float, float], dict[str, Member]] = {}
    for ui, u in enumerate(part.units):
        for mi, m in enumerate(u.members):
            oid, opath = part.member_object.get((ui, mi), (m.id, m.resource))
            by_key.setdefault((u.anchor[0], u.anchor[1], u.agl_m), {})[opath] = m
    for i, (key, opath, _oid) in enumerate(new_ref):
        by_key.setdefault(key, {})[opath] = _dc.replace(
            new_member_rows[i], parts=tuple(rows.get(base_n + i, ())))
    units: list[Unit] = []
    member_object: dict[tuple[int, int], tuple[str, str]] = {}
    oid_of = {(k, p): o for k, p, o in list(geom.member_ref) + new_ref}
    for key, members in sorted(by_key.items()):
        if not members:
            continue
        names = sorted(members)
        ms = tuple(members[n] for n in names)
        for mi, nm in enumerate(names):
            member_object[(len(units), mi)] = (oid_of.get((key, nm), ms[mi].id), nm)
        units.append(Unit(f"unit:{len(units)}", (key[0], key[1]), key[2], ms))
    counts["units"] = len(units)
    counts["members"] = sum(len(u.members) for u in units)
    counts["parts"] = sum(len(m.parts) for u in units for m in u.members)
    counts["multi_anchor"] = max(0, int(counts.get("multi_anchor", 0)) - len(readded))
    contacts = tuple(sorted(set(part.contacts) | set(ext.contacts)))
    abutments = tuple(sorted(set(part.abutments) | set(ext.abutments)))
    counts["contacts"] = len(contacts)
    counts["abutments"] = len(abutments)
    counts["structures"] = ext.structures
    counts["pairs_tested"] = int(counts.get("pairs_tested", 0)) + ext.pairs_tested
    counts["pairs_unproved"] = int(counts.get("pairs_unproved", 0)) + ext.pairs_unproved
    counts["line_objects"] = sum(1 for u in units for m in u.members
                                 if m.parts and all(p.line for p in m.parts))
    counts["plate_readded"] = len(readded)
    counts["plate_neighbours"] = ext.neighbours
    return _dc.replace(part, units=tuple(units), skipped=tuple(sorted(skipped.items())),
                       counts=counts, contacts=contacts, abutments=abutments,
                       member_object=member_object, deferred=(), geom=None)
