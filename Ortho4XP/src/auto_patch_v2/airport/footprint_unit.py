"""§16g THE FOOTPRINT UNIT (owner RULINGS 2026-09-13bo, interviewed;
spec ``object-placement-spec.md`` §16g).

Owner: *"Regarding bridge family, we can't rely on naming conventions
across all airports.  We always want to keep objects covering the same
footprint together when changing their seat.  Objects separated by
lateral space, e.g. separate buildings, can move vertically independent
of other buildings.  Only time we allow actually cutting objects apart is
for things like very long connecting pieces like the elevated rail at
HECA which would require two buildings kilometers apart to be at the same
elevation."*

ONE rule replaces every family derivation of 2026-09-13: §16e (3)'s row /
ring / footprint-contact / NAME attempts, §16f (1)'s shared-authored-datum
condition (overlap alone binds) and §16f (4)'s partition by pad (a unit
spanning two pads takes ONE datum by the priority rule).  §16f (7) — a
large terminal cluster is one unit on one pad, the apron flattened around
it (design ``§30 (4)``) — is this law's design-surface side and stands.

The derivation itself is ``placement_family._clusters``, asked at
``[placement] footprint_touch_m`` (0.5 m) instead of the millimetres of
``contact_eps_m``, with ``min_members=1`` so two bodies of ONE member bind
as readily as a deck and its piers.  ONE derivation, three readers: this
module, ``planar/cluster.plan_clusters`` (the design surface's cluster,
read off the pack partition before the object stage exists) and §16f's own
census.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from . import anchor_rule as _ar
from . import placement_boxes as _pb
from .placement_contact import _polys_touch, m_per_deg_exact, ring_metres
from .footprint_connector import (CONNECTOR_BOXES_MAX, ClusterTopology,
                                  PlanConnector, _is_connector,
                                  _near_index, _span_m,
                                  authored_unit_census, authored_units,
                                  cluster_topology, connectors_of_cluster,
                                  contact_graph)
from .placement_family import (FAMILY_CONTACTS_MAX, Family, _all_on_pavement,
                               _clusters, _contacts_of, _median,
                               bodies_of_plan, cluster_plane, pad_plurality,
                               union_area_m2)

__all__ = ["UNIT_REASON", "bind_footprint_units", "PlanConnector",
           "ClusterTopology"]


#: §16g's own counts key prefix, so the census can tell a §16g unit from
#: a §16f family in a plan written by either tree.
UNIT_REASON = "§16g unit"


def _is_deck_member(st: _t.Any) -> bool:
    """§16e (2): does this staged member carry a DECK?  The same test
    ``bridge_family.deck_prints`` uses (``deck_kind`` flag / signature),
    widened by ``deck_ring`` for a member the signature pass named
    without re-parsing."""
    m = getattr(st, "m", None)
    if m is None:
        return False
    return bool(getattr(m, "deck_ring", None)
                or getattr(m, "deck_kind", "") in ("flag", "signature"))


def bind_footprint_units(cands: list, staged: _t.Sequence[_t.Any],
                         surface: _ar.Surface,
                         pads: _t.Sequence[_ar.PadRing], counts: dict, *,
                         unit_id: str = "", touch_m: float = 0.0,
                         visual_m: float = 0.0, cluster_min_m2: float = 0.0,
                         connector_span_m: float = 0.0,
                         plan_wide: "_t.Mapping[int, tuple[str, float, str, str]] | None" = None
                         ) -> list[Family]:
    """§16g THE FOOTPRINT UNIT (owner RULINGS 2026-09-13bo, interviewed;
    spec §16g) — the ONE rule that replaces every family derivation of
    2026-09-13: §16e (3)'s row / ring / footprint / NAME attempts, §16f
    (1)'s shared-authored-datum condition and §16f (4)'s partition by pad.

    (1) THE UNIT: bodies whose plan footprints overlap or come within
    ``touch_m`` are one unit, chained transitively — :func:`_clusters`
    with ``min_members=1``, so two bodies of ONE member bind as readily
    as a deck and its piers, which is what "covering the same footprint"
    means.  A body touching nothing is its own unit and is not here.

    (2) ONE ZERO PER UNIT, the datum by PRIORITY: a DECK member's own
    zero (§16e (2)/(6)); else the plane of the emitted ``building`` pad
    most of the unit's contacts stand on — the CLUSTER pad (§30 (4)) where
    the unit's footprint union passes ``cluster_min_m2``; else the median
    ground under the unit's contacts.  A member further than ``visual_m``
    off the plane is REPORTED and seated anyway.  PAVEMENT IS KING only
    for a unit standing ENTIRELY on rolled-on pavement — inside a mixed
    unit the datum rule wins (13bo, superseding §16f (5)).

    (3) AS AMENDED BY §16g (6) (owner RULINGS 2026-09-13cn): a CONNECTOR
    (:func:`_is_connector`) is a body that CONNECTS TWO UNITS, and it is
    no longer left out of anything — it is seated on the datum of the unit
    its HIGH end touches and records both ends in ``connector_of`` until
    §10's station cut is written for it.  A body whose every contact
    chains into ONE unit is that unit's MEMBER however long it is.  The
    topology can only be read from the plan-wide partition, so the
    per-``Unit`` path below never names a connector at all.

    Mutates ``cands`` and the staged members' ``raw`` / ``ground_off`` in
    place, the shape :func:`bind_families` and
    ``placement_atom.bind_unit`` both take.  Returns the units, for the
    census."""
    if touch_m <= 0.0 or not cands:
        return []
    from . import placement_carrier as _pc
    by_mi = {st.mi: st for st in staged}
    if plan_wide:
        return _bind_plan_wide(cands, by_mi, surface, counts, plan_wide,
                               visual_m=visual_m,
                               connector_span_m=connector_span_m)
    clusters, _adj = _clusters(cands, touch_m, min_members=1)
    units: list[Family] = []
    bound_ci: set[int] = set()
    counts.setdefault("unit_connectors_cut", 0)
    for cl in clusters:
        per: dict[int, list] = {}
        for ci in cl:
            c = cands[ci]
            st = by_mi.get(c.member)
            if st is None:
                continue
            cc = _contacts_of(c, st, surface)
            if not cc:
                continue
            # §16g (6): NO connector test here.  This path sees ONE
            # cluster and nothing outside it, so it can never witness the
            # "two DIFFERENT units" the law requires — and a body whose
            # every contact chains into one unit is that unit's member
            # however long it is (13cn).  The topology is asked only where
            # the plan-wide partition exists (:func:`_bind_plan_wide`).
            per[ci] = cc
        if len(per) < 2:
            continue
        # §16g (2): PAVEMENT IS KING only for a unit standing ENTIRELY on
        # rolled-on pavement — an object never moves the aircraft, but a
        # terminal wall with one foot on apron is not "on pavement".
        if all(_all_on_pavement(cc, surface) for cc in per.values()):
            counts["unit_all_on_pavement"] = \
                counts.get("unit_all_on_pavement", 0) + 1
            continue
        boxes = [b for ci in cl for b in (cands[ci].part_boxes or
                                          ([cands[ci].box] if cands[ci].box else []))]
        area = union_area_m2(boxes)
        # ── the datum, by priority ───────────────────────────────────
        zero: float | None = None
        where = ""
        src = ""
        deck = [ci for ci in per if _is_deck_member(by_mi[cands[ci].member])]
        for ci in sorted(deck):
            a = cands[ci].anchor
            if a.surface_z is not None:
                zero = float(a.surface_z) - float(a.y_zero)
                where = by_mi[cands[ci].member].m.resource.rsplit("/", 1)[-1]
                src = "deck"
                break
        if zero is None:
            # §16g (2): THE PAD MOST OF THE UNIT'S CONTACTS STAND ON, and
            # its OWN plane (``median(pad.z)``, 13aq's reading).  This IS
            # the §30 (4) CLUSTER PAD for a large unit and needs no second
            # branch to say so: where the unit's footprint union passes
            # ``cluster_pad_min_m2`` the design surface has already priced
            # every pad the union stands on as ONE plane
            # (``constraints.pads._plane_groups``), so the pad the
            # plurality names carries that plane's level.  A branch that
            # took the MEDIAN OVER SEVERAL PADS instead was written and
            # DELETED: at KCLT it fired on ``unit:3``'s hangars, whose
            # 5,000 m2 union the design surface does NOT fuse, and
            # averaged two planes that are not one.
            allc = [q for cc in per.values() for q in cc]
            step = max(1, len(allc) // FAMILY_CONTACTS_MAX)
            p = pad_plurality(allc[::step], pads)
            if p is not None and p.z:
                zero, where, src = _median(p.z), p.ref, "pad"
                if cluster_min_m2 > 0.0 and area >= cluster_min_m2:
                    src = "cluster_pad"
        if zero is None:
            zero = _median([q[3] - q[2] for cc in per.values() for q in cc])
            where, src = "", "ground"
        fid = f"{unit_id or 'unit'}#{cl[0]}@{src}"
        mems = sorted({cands[ci].member for ci in per})
        gz = [cands[ci].anchor.surface_z - cands[ci].anchor.y_zero
              for ci in per if cands[ci].anchor.surface_z is not None]
        moved = 0
        n_off = 0
        n_contacts = 0
        for ci, cc in sorted(per.items()):
            c = cands[ci]
            st = by_mi[c.member]
            n_contacts += len(cc)
            _st = max(1, len(cc) // _pb.GROUND_OFF_FEET_MAX)
            if (visual_m > 0.0
                    and abs(_median([q[3] - q[2] for q in cc[::_st]]) - zero)
                    > visual_m):
                n_off += 1
            best = min(cc, key=lambda q: (round(abs(q[3] - q[2] - zero), 6),
                                          round(abs(q[2]), 6), q[0], q[1]))
            own = best[3] - best[2]
            a = _ar.Anchor(
                c.anchor.body_class, best[0], best[1], best[3] - zero,
                f"{UNIT_REASON} {fid} of {len(mems)} member(s) on "
                + (f"pad {where}" if src in ("pad", "cluster_pad")
                   else (f"deck {where}" if src == "deck"
                         else "its median ground"))
                + f" at {zero:.2f} (own ground {own - zero:+.2f} m)",
                best[3], family=fid)
            grp0 = (st.groups[c.group] if 0 <= c.group < len(st.groups) else ())
            if not grp0:
                continue
            k0 = _pc.senior_of(st.raw, grp0)
            r0 = st.raw[k0]
            st.raw[k0] = (r0[0], r0[1], a) + tuple(r0[3:])
            _off = _pb.anchor_ground_off(
                a, tuple(f for j in grp0 for f in st.raw[j][3]), surface)
            if c.group < len(st.ground_off):
                st.ground_off[c.group] = _off
            cands[ci] = _dc.replace(c, anchor=a, ground_off=_off)
            bound_ci.add(ci)
            moved += 1
        if not moved:
            continue
        counts["bodies_bound_to_unit"] = \
            counts.get("bodies_bound_to_unit", 0) + moved
        counts["footprint_units"] = counts.get("footprint_units", 0) + 1
        counts[f"unit_datum_{src}"] = counts.get(f"unit_datum_{src}", 0) + 1
        if n_off:
            counts["unit_members_off_the_plane"] = \
                counts.get("unit_members_off_the_plane", 0) + n_off
        units.append(Family(
            id=fid, unit=unit_id or "",
            members=tuple(by_mi[m].m.resource for m in mems if m in by_mi),
            bodies=moved, contacts=n_contacts, zero_z=zero, pad=where,
            spread_before_m=((max(gz) - min(gz)) if gz else 0.0),
            spread_after_m=0.0, apart=()))
    return units


def cluster_zero_allowed(forced: _t.Sequence[int], st: _t.Any,
                         box: _t.Any, cands: _t.Sequence[_t.Any],
                         reach_m: float, counts: dict) -> list[int]:
    """§16g (4) (owner RULINGS 2026-09-13bu item 4): MAY THIS BODY TAKE
    §16c (7)'s CLUSTER ZERO without asking the carrier search?

    Not if it is FOOTLESS, and not from a cluster member standing more
    than ``coarsen_reach_m`` away in plan.  KCLT's
    ``Charlotte_Airport_001_ALB`` is a pure roof resource (authored
    y 2.10 … 33.64, nothing at ground) spread over the whole 1.7 km
    hangar district; the short-circuit handed each of its 28 footless
    bodies a zero from anywhere in its rigid cluster — ``__b16`` rode
    ``007_ALB__b11`` at 221.20 over a hangar standing at 216.03.  A body
    with FEET has its own ground to check the cluster against (§16c (7)'s
    ``bind_ground_m``); a footless one has none, so it must ask what it
    actually stands over.

    THE TEST AS BUILT IS THE DISTANCE ALONE, applied to every member —
    a DEVIATION from 13bu item 4's parenthetical ("the short-circuit does
    not apply to footless members"), reported not decided.  Withdrawing
    it from every footless member outright was measured and REFUTED: it
    costs nothing at the owner's sites (KCLT's `001_ALB` comes out 78
    bodies either way against 27 before) and it breaks §14 (1)'s rigid
    span — a footless deck ABUTTING its footed building, zero metres
    away, stopped riding that building's anchor and was cut in two by
    §16a (1) (`test_a_footless_deck_abutting_a_footed_building_rides_its
    _anchor`).  The defect 13bu names is a zero chosen 1.7 km away, and
    the distance is what names it."""
    out = list(forced)
    if not out or reach_m <= 0.0 or box is None:
        return out
    keep = [q for q in out if _pb.box_gap_m(box, cands[q].box) <= reach_m]
    if not keep:
        counts["cluster_zero_refused_footless_or_far"] = \
            counts.get("cluster_zero_refused_footless_or_far", 0) + 1
    return keep


# ── §16g (1) PLAN-WIDE (owner RULINGS 2026-09-13bw) ──────────────────────

@_dc.dataclass(frozen=True)
class PlanUnit:
    """One FOOTPRINT UNIT of the WHOLE plan (§16g (1) as ruled in 13bw).

    Round 1 derived the unit inside the per-``Unit`` loop, because that is
    where PASS 1's staged bodies exist — and 13bw ruled that a
    CONSTRUCTION ARTEFACT, not the law: OTHH's `Bridge_02` / `Bridge_03`
    came out at 1.52 / 1.93 m of spread precisely because their deck,
    piers and clutter are authored on rows that fall in different plan
    ``Unit``s and each pass could only see its own.

    So the relation is derived from the PLAN, before any unit is staged:
    the bodies are ``placement_family.bodies_of_plan``'s (§9's own body
    law, the ONE derivation) and the chaining is
    ``placement_family._clusters``'s, asked over every body of every unit
    at once.  What each pass then does is LOOK UP the datum this unit was
    given — one zero across plan units by construction."""

    id: str
    #: ``(unit, member, body)`` keys of its bodies
    bodies: tuple[tuple[int, int, int], ...]
    #: every PART id it holds — the join a staged candidate is mapped by
    pids: frozenset[int]
    members: tuple[str, ...]
    boxes: tuple[tuple[float, float, float, float], ...]
    area_m2: float
    #: §16g (7) (2) THE DECK GUARD (owner RULINGS 2026-09-14c item 1): the
    #: PART IDS of the bodies whose FOOTPRINT POLYGONS touch a deck
    #: member's ring in this unit — the only bodies a deck lends its datum
    #: to.  Empty where the unit holds no deck.  Before the guard a deck
    #: reached by a BOX chain handed 96.20 to 1,509 HECA bodies, six
    #: buildings among them 4.0-5.3 m off their own pads (14g).
    deck_pids: frozenset[int] = frozenset()
    #: the deck member's own datum and name, or ``None``
    deck: "tuple[float, str] | None" = None


class _PShim:
    """A plan body dressed as the candidate :func:`_clusters` reads."""

    __slots__ = ("member", "part_boxes", "box", "body_class", "key", "pids",
                 "resource", "rings", "walled")

    def __init__(self, seq, key, boxes, pids, resource, rings=(), walled=True):
        self.member = seq            # a UNIQUE id per body: the chaining
        self.key = key               # is plan-wide, so "member" may not
        self.pids = pids             # collapse two bodies of one member
        self.resource = resource
        self.part_boxes = boxes
        #: §16g (7) (1): this body's component FOOTPRINT POLYGONS
        self.rings = tuple(rings)
        self.box = _pb.hull_of(boxes)
        self.body_class = ""
        #: §16g (10) (4): this body has WALLS and may LINK a unit
        self.walled = bool(walled)


def plan_units(plan: _t.Any, touch_m: float) -> list[PlanUnit]:
    """§16g (1) PLAN-WIDE: every footprint unit of ``plan``, chained
    across placement ``Unit``s.  A body touching nothing is its own unit
    and is NOT returned — it seats alone (§16c)."""
    return plan_units_and_connectors(plan, touch_m, 0.0)[0]


def _deck_lending(cl: _t.Sequence[int], shims: _t.Sequence[_PShim],
                  plan: _t.Any, touch_m: float, connector_span_m: float,
                  counts: "dict | None"
                  ) -> "tuple[frozenset[int], tuple[float, str] | None]":
    """§16g (7) THE DECK GUARD (owner RULINGS 2026-09-14c item 1): WHICH
    bodies of this unit may take a deck member's datum?

    Only those whose FOOTPRINT POLYGONS touch the deck's own footprint.
    §16g (2) gave a deck's zero to its whole unit, and with the unit
    chained on PART BOXES that unit was `fu:38:20` — 978 bodies over
    2,471 m standing on 136 pads that span 34.8 m — so `T3_road.obj`'s
    rail deck handed 96.20 to 1,509 HECA bodies: six buildings 4.0-5.3 m
    above their own pads and the terminal at 30.1279552, 31.403143
    +23.70 m (14g).  §16g (7) (1)'s polygon chain breaks most of that
    hop; the guard is what makes the rest impossible AND VISIBLE, and it
    is counted (``deck_datum_lent_to``) so a census can see whom a deck
    reached.

    A CONNECTOR NEVER LENDS (§16g (7) (2)): a body long enough to be the
    rail is its own body, and neither unit takes its deck."""
    decks = []
    for i in cl:
        ui, mi, _gi = shims[i].key
        m = plan.units[ui].members[mi]
        dz = getattr(m, "deck_datum_z", None)
        if dz is None:
            continue
        if (connector_span_m > 0.0
                and _span_m(shims[i].part_boxes) >= connector_span_m):
            if counts is not None:
                counts["deck_lender_refused_connector"] = \
                    counts.get("deck_lender_refused_connector", 0) + 1
            continue
        decks.append((i, float(dz), m.resource.rsplit("/", 1)[-1],
                      getattr(m, "deck_ring", None)))
    if not decks:
        return frozenset(), None
    i0, dz, name, ring = sorted(decks)[0]
    ml, mo = m_per_deg_exact(shims[i0].box[0])
    theirs = [ring_metres(ring, ml, mo)] if ring and len(ring) >= 3 else []
    theirs += [ring_metres(r, ml, mo) for r in (shims[i0].rings or ())
               if len(r) >= 3]
    lent: set[int] = set(shims[i0].pids)
    n = 1
    for i in cl:
        if i == i0:
            continue
        mine = [ring_metres(r, ml, mo) for r in (shims[i].rings or ())
                if len(r) >= 3]
        if not theirs or not mine or _polys_touch(mine, theirs, touch_m):
            lent.update(shims[i].pids)
            n += 1
    if counts is not None:
        counts["deck_datum_lent_to"] = counts.get("deck_datum_lent_to", 0) + n
        counts["deck_units"] = counts.get("deck_units", 0) + 1
        counts["deck_unit_bodies"] = counts.get("deck_unit_bodies", 0) + len(cl)
    return frozenset(lent), (dz, name)


def plan_units_and_connectors(plan: _t.Any, touch_m: float,
                              connector_span_m: float,
                              counts: "dict | None" = None,
                              chain_min_height_m: float = 0.0
                              ) -> "tuple[list[PlanUnit], list[PlanConnector]]":
    """§16g (1) PLAN-WIDE with §16g (6)'s CONNECTOR reading.

    THE PARTITION IS UNCHANGED — the units are exactly the ones §16g (1)
    already derived, and an identified connector STAYS IN ITS UNIT for the
    census (§16g (6) (2): "still chained for the purpose of the unit
    census").  What the connector reading adds is a question asked of each
    LONG body inside its own unit: **is this body the link?**  Remove it
    and see what its unit falls into.

    * The remainder breaks into two or more COMPONENTS and the body's two
      hull ends touch two DIFFERENT ones — it CONNECTS them.  "Two
      different units" can only ever mean this: a body that chains two
      groups makes them one unit by existing, so the partition WITH it in
      can never witness the split.
    * The remainder stays connected and the body touches it at ONE end
      only, with nothing within ``connector_span_m`` of the other — it
      connects that unit to open ground (the HECA elevated rail running
      off the terminal).
    * Anything else — every contact into one component, or a free end with
      a unit inside the reach — is a MEMBER however long it is.  That is
      13cn's correction and the SPJC viaduct.

    Held to the LONG bodies (``connector_span_m``), so the cost is one
    sub-clustering per long body and nothing at all when the law is
    disarmed.

    §16g (10) (4) ONLY A WALLED BODY LINKS A UNIT (owner RULINGS
    2026-09-14ah).  The same rule the design surface's ``plan_clusters``
    applies to its clusters, applied to the UNIT — they are one relation
    (§16g (9) ONE POPULATION) and a leaf rule that held on one side only
    would be two populations again.  MEASURED at HECA: with the design
    cluster resolved but the unit still chaining through slabs, the T3
    terminal stayed in ``fu:38:23@cluster_pad`` — 52 members on one datum
    — and its body sat 7.50 m above its own ground.  A body whose tallest
    component's ``Part.height_m`` is under ``chain_min_height_m``, or
    whose member the plan already calls a DECK, is its own unit.  0
    disarms; a plan carrying no height at all does not apply it and the
    count says so (``unit_chain_no_height``)."""
    if touch_m <= 0.0 or not getattr(plan, "units", ()):
        return [], []
    bodies, _of_pid = bodies_of_plan(plan)
    parts_of = {p.pid: p for u in plan.units for m in u.members
                for p in m.parts}
    any_height = any(float(getattr(q, "height_m", 0.0)) > 0.0
                     for q in parts_of.values())
    shims: list[_PShim] = []
    for key, pids in sorted(bodies.items()):
        ui, mi, _gi = key
        live = [parts_of[q] for q in pids
                if q in parts_of and not parts_of[q].line]
        bx = [q.box for q in live]
        if bx:
            tall = max((float(getattr(q, "height_m", 0.0)) for q in live),
                       default=0.0)
            walled = (chain_min_height_m <= 0.0 or not any_height
                      or (tall >= chain_min_height_m
                          and not str(getattr(plan.units[ui].members[mi],
                                              "deck_kind", "") or "")))
            shims.append(_PShim(len(shims), key, bx, frozenset(pids),
                                plan.units[ui].members[mi].resource,
                                tuple(r for q in live
                                      for r in getattr(q, "rings", ())
                                      if len(r) >= 3), walled))
    if len(shims) < 2:
        return [], []
    # §16g (10) (4): the chain runs over the WALLED bodies alone; a LEAF
    # is its own unit, seated on its own ground or its carrier
    walled_ix = [i for i, q in enumerate(shims) if q.walled]
    leaves = [i for i, q in enumerate(shims) if not q.walled]
    if walled_ix:
        sub = [shims[i] for i in walled_ix]
        clusters, _adj = _clusters(sub, touch_m, min_members=1, counts=counts)
        clusters = [[walled_ix[k] for k in cl] for cl in clusters]
    else:
        clusters, _adj = [], {}
    # NO BACKFILL: a body that chains with nothing has never been a
    # PlanUnit here (``_clusters`` drops the singletons) and is seated on
    # its own ground by the default path — which is exactly what §16g
    # (10) (4) says a LEAF must be.  Adding singleton units would be a
    # second change riding on this one.
    if counts is not None:
        counts["unit_leaf_bodies"] = len(leaves)
        counts["unit_chain_no_height"] = 0 if any_height else 1
    # every body that is IN a unit: the "nothing at the other end" test is
    # about the whole plan, not about the connector's own unit (a rail
    # ending 50 m short of the NEXT building connects two things).  The
    # index is built ONCE (RULINGS 2026-09-14e).
    index = (_near_index([i for cl in clusters for i in cl], shims)
             if connector_span_m > 0.0 else None)
    out: list[PlanUnit] = []
    conns: list[PlanConnector] = []
    conn_keys: set = set()
    for cl in clusters:
        boxes = [b for i in cl for b in shims[i].part_boxes]
        uid = f"fu:{shims[cl[0]].key[0]}:{cl[0]}"
        deck_pids, deck = _deck_lending(cl, shims, plan, touch_m,
                                        connector_span_m, counts)
        out.append(PlanUnit(
            id=uid,
            bodies=tuple(shims[i].key for i in cl),
            pids=frozenset().union(*(shims[i].pids for i in cl)),
            members=tuple(sorted({shims[i].resource for i in cl})),
            boxes=tuple(boxes), area_m2=union_area_m2(boxes),
            deck_pids=deck_pids, deck=deck))
        if connector_span_m <= 0.0:
            continue
        conns.extend(connectors_of_cluster(cl, uid, shims, touch_m,
                                           connector_span_m, index))
    return out, conns


def _centres(boxes: _t.Sequence[tuple[float, float, float, float]],
             cap: int) -> list[tuple[float, float]]:
    step = max(1, len(boxes) // cap)
    return [(0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3])) for b in boxes[::step]]


def plan_unit_datums(units: _t.Sequence[PlanUnit], plan: _t.Any,
                     surface: _ar.Surface, pads: _t.Sequence[_ar.PadRing],
                     cluster_min_m2: float
                     ) -> dict[str, tuple[float, str, str]]:
    """§16g (2)'s PRIORITY DATUM, read PLAN-WIDE: ``unit id -> (zero,
    where, source)``.

    DECK first — the plan itself carries a deck member's own datum
    (``Member.deck_datum_z``, §16e (2)/(6)), so the piers and clutter
    chained to it take the deck's plane without any bridge-specific law,
    which is 13bo's own test.  Then the PAD most of the unit's footprint
    stands on (its OWN plane, ``median(pad.z)`` — the §30 (4) cluster pad
    for a unit over ``cluster_pad_min_m2``).  Then the median ground under
    its part centres.

    The ground is sampled at the PART CENTRES rather than at the feet: the
    feet belong to a staged body and this pass runs before any staging.  A
    unit whose every centre falls off the surface takes no datum and its
    bodies keep whatever the per-unit passes give them."""
    by_key: dict[tuple[int, int], _t.Any] = {}
    for ui, u in enumerate(plan.units):
        for mi, m in enumerate(u.members):
            by_key[(ui, mi)] = m
    out: dict[str, tuple[float, str, str]] = {}
    for un in units:
        zero: float | None = None
        where = src = ""
        # §16g (7): THE DECK IS NO LONGER THE UNIT'S DATUM.  It is lent,
        # per body, to the bodies whose footprint polygons touch it
        # (``PlanUnit.deck_pids``, overlaid by :func:`plan_wide_seats`);
        # what this function computes is the datum for everything ELSE.
        # A plan with no ring field publishes no ``deck_pids`` and the
        # whole unit takes the deck, which is the pre-(7) reading.
        pts = _centres(un.boxes, FAMILY_CONTACTS_MAX)
        if zero is None:
            cc = [(la, lo, 0.0, surface(la, lo)) for la, lo in pts]
            cc = [q for q in cc if q[3] is not None]
            if not cc:
                continue
            p = pad_plurality(cc, pads)
            if p is not None and p.z:
                zero, where, src = _median(list(p.z)), p.ref, "pad"
                if cluster_min_m2 > 0.0 and un.area_m2 >= cluster_min_m2:
                    src = "cluster_pad"
            else:
                zero, where, src = _median([q[3] for q in cc]), "", "ground"
        out[un.id] = (zero, where, src)
    return out


def _bind_plan_wide(cands: list, by_mi: _t.Mapping[int, _t.Any],
                    surface: _ar.Surface, counts: dict,
                    plan_wide: _t.Mapping[int, tuple],
                    *, visual_m: float, connector_span_m: float
                    ) -> list[Family]:
    """§16g (1)/(2) PLAN-WIDE (owner RULINGS 2026-09-13bw): seat every
    candidate of this pass at the datum ITS PLAN-WIDE UNIT was given.

    ``plan_wide`` maps a PART ID to ``(unit id, zero, where, source,
    connector ends, the HIGH end's own seat)`` — the join is the pid,
    because the plan's body keys and a staged candidate's ground groups
    are different partitions of the same triangles and the part is what
    both are made of.  A candidate whose pids name no unit (a body
    touching nothing) is left alone: it seats by §16c as it always did.

    §16g (6) (owner RULINGS 2026-09-13cn): an identified CONNECTOR is NOT
    dropped out of the bind.  It is moved onto the seat of the unit its
    HIGH end touches, with both ends recorded in ``connector_of``; when
    §10's station cut is written for it, each piece keeps its own end's
    datum and grades between.  It never reaches §16c's low-side foot,
    which is what put SPJC's viaduct 7.81 m above the terminal (13cn).

    THE HIGH-END SEAT IS TAKEN ONLY BY A BODY THAT PASSES ALL THREE
    TESTS.  The plan names the TOPOLOGY (span + two ends); the GROUND STEP
    is a staged reading and lives here, so a long body whose ends stand at
    the same height is an ordinary MEMBER of its whole unit and keeps the
    unit's datum — moving it onto one end's component would be the same
    expulsion under a new name."""
    counts.setdefault("unit_connectors_cut", 0)
    counts.setdefault("unit_connectors_seated", 0)
    per_uid: dict[str, dict[int, list]] = {}
    info: dict[str, tuple[float, str, str]] = {}
    conn: dict[int, tuple[str, str]] = {}
    for ci, c in enumerate(cands):
        if c.body_class in (_ar.LINE_SEGMENT, _ar.BASIN):
            continue
        hit: dict[str, int] = {}
        for q in c.pids:
            got = plan_wide.get(q)
            if got is not None:
                hit[got[0]] = hit.get(got[0], 0) + 1
        if not hit:
            continue
        uid = max(sorted(hit), key=lambda k: hit[k])
        row = plan_wide[next(q for q in sorted(c.pids)
                             if plan_wide.get(q, ("",))[0] == uid)]
        z, where, src = row[1], row[2], row[3]
        st = by_mi.get(c.member)
        if st is None:
            continue
        cc = _contacts_of(c, st, surface)
        if not cc:
            continue
        pair = row[4] if len(row) > 4 else ("", "")
        high = row[5] if len(row) > 5 else None
        if (high is not None and pair and pair[0] != pair[1]
                and _is_connector(c, cc, connector_span_m, visual_m,
                                  ends=pair)):
            conn[ci] = pair
            uid, z, where, src = high
            counts["unit_connectors_seated"] = \
                counts.get("unit_connectors_seated", 0) + 1
        per_uid.setdefault(uid, {})[ci] = cc
        info[uid] = (z, where, src)
    out: list[Family] = []
    for uid, per in sorted(per_uid.items()):
        zero, where, src = info[uid]
        if len(per) < 2 and not any(ci in conn for ci in per):
            continue
        # §16g (2): PAVEMENT IS KING only for a unit standing ENTIRELY on
        # rolled-on pavement.  Read over the candidates THIS pass holds —
        # a plan-wide unit split across passes is judged per pass, which
        # is the one place the plan-wide reading cannot reach.
        if all(_all_on_pavement(cc, surface) for cc in per.values()):
            counts["unit_all_on_pavement"] = \
                counts.get("unit_all_on_pavement", 0) + 1
            continue
        out.extend(_seat(cands, by_mi, surface, counts, per, zero, where,
                         src, uid, visual_m,
                         conn={ci: conn[ci] for ci in per if ci in conn}))
    return out


def _seat(cands: list, by_mi: _t.Mapping[int, _t.Any], surface: _ar.Surface,
          counts: dict, per: _t.Mapping[int, list], zero: float, where: str,
          src: str, uid: str, visual_m: float,
          conn: "_t.Mapping[int, tuple[str, str]] | None" = None
          ) -> list[Family]:
    """Put every candidate of ``per`` on ``zero`` — the one anchor rewrite
    §16f (2) and §16g (2) both take, factored so the per-unit and the
    plan-wide readings cannot drift apart."""
    from . import placement_carrier as _pc
    fid = f"{uid}@{src}"
    mems = sorted({cands[ci].member for ci in per})
    gz = [cands[ci].anchor.surface_z - cands[ci].anchor.y_zero
          for ci in per if cands[ci].anchor.surface_z is not None]
    moved = n_off = n_contacts = 0
    for ci, cc in sorted(per.items()):
        c = cands[ci]
        st = by_mi[c.member]
        n_contacts += len(cc)
        _st = max(1, len(cc) // _pb.GROUND_OFF_FEET_MAX)
        if (visual_m > 0.0
                and abs(_median([q[3] - q[2] for q in cc[::_st]]) - zero)
                > visual_m):
            n_off += 1
        best = min(cc, key=lambda q: (round(abs(q[3] - q[2] - zero), 6),
                                      round(abs(q[2]), 6), q[0], q[1]))
        own = best[3] - best[2]
        pair = (conn or {}).get(ci)
        a = _ar.Anchor(
            c.anchor.body_class, best[0], best[1], best[3] - zero,
            f"{UNIT_REASON} {fid} of {len(mems)} member(s) on "
            + (f"pad {where}" if src in ("pad", "cluster_pad")
               else (f"deck {where}" if src == "deck"
                     else "its median ground"))
            + f" at {zero:.2f} (own ground {own - zero:+.2f} m)"
            + ("" if pair is None else
               f" — §16g (6)/(7) CONNECTOR between "
               f"{pair[0] or 'open ground'} and {pair[1] or 'open ground'}, "
               f"seated on its LOW end's contact (no station cut written)"),
            best[3], family=fid,
            connector_of=("" if pair is None else f"{pair[0]}|{pair[1]}"))
        grp0 = (st.groups[c.group] if 0 <= c.group < len(st.groups) else ())
        if not grp0:
            continue
        k0 = _pc.senior_of(st.raw, grp0)
        r0 = st.raw[k0]
        st.raw[k0] = (r0[0], r0[1], a) + tuple(r0[3:])
        _off = _pb.anchor_ground_off(
            a, tuple(f for j in grp0 for f in st.raw[j][3]), surface)
        if c.group < len(st.ground_off):
            st.ground_off[c.group] = _off
        cands[ci] = _dc.replace(c, anchor=a, ground_off=_off)
        moved += 1
    if not moved:
        return []
    counts["bodies_bound_to_unit"] = \
        counts.get("bodies_bound_to_unit", 0) + moved
    counts["footprint_units"] = counts.get("footprint_units", 0) + 1
    counts[f"unit_datum_{src}"] = counts.get(f"unit_datum_{src}", 0) + 1
    if n_off:
        counts["unit_members_off_the_plane"] = \
            counts.get("unit_members_off_the_plane", 0) + n_off
    return [Family(
        id=fid, unit=uid,
        members=tuple(by_mi[m].m.resource for m in mems if m in by_mi),
        bodies=moved, contacts=n_contacts, zero_z=zero, pad=where,
        spread_before_m=((max(gz) - min(gz)) if gz else 0.0),
        spread_after_m=0.0, apart=())]


def _end_probe(cn: _t.Any, own: _t.Sequence[tuple], feet_of
               ) -> tuple:
    """§16g (7) (2) as clarified (owner RULINGS 2026-09-14j): WHERE the
    connector's end contact is read.

    At the connector's OWN GROUND FEET in that end, as degenerate boxes,
    so ``plan_unit_datums`` samples the terrain exactly where the piece
    touches it — its pad if it stands on one, the design surface
    otherwise.  Round 3 sampled the end's BOX CENTRES and HECA's
    1,149 m rail read OFF-SHEET at both ends (measured: 0 of 7 and 0 of
    8 centres on any graded face), so only one end ever produced a datum
    and the ``min`` of the two had nothing to choose from — the rail came
    out at 93.16, its south end, when its north end stands at ~73.4.  A
    foot is a real contact point and is on the sheet wherever the patch
    covers the piece at all.  With no foot in the end, the box centres
    stand as they did."""
    lo = min(b[0] for b in own)
    hi = max(b[2] for b in own)
    lo2 = min(b[1] for b in own)
    hi2 = max(b[3] for b in own)
    feet = [f for f in feet_of(cn.pids)
            if lo <= f[0] <= hi and lo2 <= f[1] <= hi2]
    if feet:
        return tuple((f[0], f[1], f[0], f[1]) for f in feet)
    return tuple(own)


def plan_wide_seats(plan: _t.Any, surface: _ar.Surface,
                    pads: _t.Sequence[_ar.PadRing], touch_m: float,
                    cluster_min_m2: float, counts: dict,
                    connector_span_m: float = 0.0,
                    chain_min_height_m: float = 0.0
                    ) -> "tuple[dict[int, tuple], list[tuple[float, float, float, float, float, str]]]":
    """§16g (1)/(2) PLAN-WIDE, as one call: ``(part id -> (unit id, zero,
    where, source, connector ends, the HIGH end's own seat), the units'
    plan boxes with their zero)``.

    ``connector ends`` is ``("", "")`` for an ordinary member and the two
    end units of a §16g (6) CONNECTOR; the sixth field is then that
    connector's HIGH end's ``(unit, zero, where, source)``, which
    :func:`_bind_plan_wide` takes ONLY when the staged ground-step test
    fires too.  The first four fields stay the body's own UNIT's seat, so
    a long body that turns out not to step is an ordinary member.

    The PART is the join for a staged candidate, because the plan's
    bodies and a candidate's ground groups are different partitions of
    the same triangles.  The BOXES are the join for §16g (5)'s dropped
    multi-anchor placement, which has no part of its own in the plan at
    all — the pack dropped it before the plan was written — and can only
    be placed by WHERE IT STANDS."""
    if touch_m <= 0.0:
        return {}, []
    units, conns = plan_units_and_connectors(plan, touch_m,
                                             connector_span_m, counts,
                                             chain_min_height_m)
    _parts = {p.pid: p for u in plan.units for m in u.members for p in m.parts}

    def _feet_of(pids):
        out = []
        for q in pids:
            p = _parts.get(q)
            if p is not None:
                out.extend(p.feet)
        return out
    dat = plan_unit_datums(units, plan, surface, pads, cluster_min_m2)
    out: dict[int, tuple] = {}
    seats: list[tuple[float, float, float, float, float, str]] = []
    for un in units:
        d = dat.get(un.id)
        if d is None:
            continue
        for q in un.pids:
            out[q] = (un.id, d[0], d[1], d[2], ("", ""), None)
        # §16g (7) THE DECK GUARD: the deck's datum is LENT, per body, to
        # the bodies whose footprint polygons touch it — never to the unit
        if un.deck is not None and un.deck_pids:
            dz, name = un.deck
            for q in un.deck_pids:
                if q in out:
                    out[q] = (un.id, dz, name, "deck", ("", ""), None)
        h = _pb.hull_of(un.boxes)
        if h is not None:
            seats.append((h[0], h[1], h[2], h[3], d[0], d[2]))
    # §16g (6) (2): THE HIGH END KEEPS THE CONNECTOR.  Between the two end
    # units the datum SOURCE ranks first — DECK over PAD over GROUND, the
    # deck-side unit being the one the piece arrives at in the air — and
    # the higher zero breaks the tie.  An end on open ground names no unit
    # and can never win; a connector neither of whose ends has a datum is
    # left to §16c.
    # §16g (7) (2) (owner RULINGS 2026-09-14c item 1): THE CONNECTOR IS
    # SEATED LOW.  13df seated it on its HIGH end so the piece met the
    # deck it arrived at; at HECA that reading lifted the T3 terminal
    # complex onto `T3_road.obj`'s deck, and the owner withdrew it.  The
    # piece now takes its LOW end's contact — ground or pad — so it
    # disappears INTO the ground at the high end instead of standing the
    # airport up to meet it, and §10's station cut, when it is written,
    # grades it between its two end contacts.  Between the two ends the
    # LOWER zero wins outright; the source ranks only a tie.
    rank = {"ground": 0, "pad": 1, "cluster_pad": 1, "deck": 2}
    n_open = 0
    for cn in conns:
        # §16g (7) (2): each end's contact is read under the CONNECTOR'S
        # OWN geometry at that end, never over the end unit — a rail's end
        # component is a whole district and its median ground is not the
        # ground the abutment stands on.
        ends = [(u, _end_probe(cn, own, _feet_of), ky)
                for u, own, bx, ky in
                ((cn.end_a, cn.own_a, cn.boxes_a, cn.keys_a),
                 (cn.end_b, cn.own_b, cn.boxes_b, cn.keys_b))
                if u and bx and own]
        ends = [e for e in ends if e[1]]
        if not ends:
            continue
        ed = plan_unit_datums(
            [PlanUnit(id=u, bodies=(), pids=frozenset(), members=(),
                      boxes=tuple(own), area_m2=union_area_m2(list(own)))
             for u, own, ky in ends], plan, surface, pads, cluster_min_m2)
        cand = [(round(ed[u][0], 6), rank.get(ed[u][2], 3), u)
                for u, _own, _ky in ends if u in ed]
        if not cand:
            continue
        _z, _r, u = min(cand)
        d = ed[u]
        if not (cn.end_a and cn.end_b):
            n_open += 1
        # the body keeps its UNIT's seat unless the staged ground-step
        # test also fires (``_bind_plan_wide``); the HIGH end's seat rides
        # beside it as the alternative, never as the default.
        base = out.get(next(iter(cn.pids)))
        for q in cn.pids:
            row = out.get(q) or base
            if row is None:
                continue
            out[q] = (row[0], row[1], row[2], row[3],
                      (cn.end_a, cn.end_b), (u, d[0], d[1], d[2]))
    counts["plan_wide_units"] = len(units)
    counts["plan_wide_units_seated"] = len(dat)
    counts["plan_wide_connectors"] = len(conns)
    counts["plan_wide_connectors_to_open_ground"] = n_open
    counts.update(authored_unit_census(plan, out))
    return out, seats


# ── §16g (5) PER-PLACEMENT ELEVATION (owner RULINGS 2026-09-13bw) ────────

def msl_seats_for_dump(dump: _t.Any, plan: _t.Any,
                       unit_seats: _t.Sequence[tuple[float, float, float,
                                                     float, float, str]],
                       surface: _ar.Surface, pack_root: str,
                       split_idx: _t.AbstractSet[int], *,
                       tol_m: float = 0.02,
                       authored_ground: "float | None" = None) -> tuple:
    """§16g (5): the placements to seat by their DSF ROW —
    ``OBJECT_MSL lat lon heading elevation``.

    THE POPULATION is the MULTI-ANCHOR resources the plan DROPPED: a
    pack-authored resource placed at two or more rows that the rebake plan
    holds no member for.  One file cannot carry a per-placement offset, so
    the plan drops it and it keeps whatever the terrain does — which is
    the owner's item 1 at KCLT (13bj): "passengers and seat objects ...
    sitting on the ground under the building instead of on the floor".
    The offset therefore goes on the ROW, which is exactly the owner's own
    2026-09-11a/b instruction.

    THE FAMILY RELATION IS THE INVARIANT (owner RULINGS 2026-09-13cb,
    correcting 13by).  A placement standing in a footprint unit is seated
    at THE UNIT'S DATUM PLUS ITS AUTHORED OFFSET, wherever its anchor
    happens to fall — so a second-floor passenger floats where the author
    put them and never drops to the actual ground.

    "ON GROUND" is only the case where the terrain at the anchor ALREADY
    equals the unit's datum within ``tol_m`` (``[emit] hard_tol_m``,
    0.02 m) — the cluster pad under the terminal — and there the row is
    left exactly as it is and X-Plane's own drape does the work.
    Everywhere else (an anchor over apron, a road, a sunken pier area, a
    deck, a terraced pad) the row is written ``OBJECT_MSL`` at
    ``unit datum + authored offset``.

    THE AUTHORED OFFSET: an ``OBJECT_AGL`` row's elevation column IS the
    offset; an ``OBJECT_MSL`` row's is an ABSOLUTE against the ground the
    pack was authored on, so the offset is that absolute minus the pack's
    authored ground (never kept as an absolute — the 11b conversion); a
    plain ``OBJECT`` row's offset is 0.  ``authored_ground`` is the
    caller's reading of the datum the pack was built on (the plan's flat
    datum ``z0_m`` where it has one); where none is known an
    ``OBJECT_MSL`` row's offset cannot be recovered and the row is left
    alone rather than guessed at, which the census counts.

    A placement whose row the SPLIT already replaces is never here — the
    two edits would collide, and ``dsf_write.edit_dump`` refuses it."""
    from ..model.placement import MslSeat
    from . import obj8 as _obj8
    have = {m.resource for u in getattr(plan, "units", ()) for m in u.members}
    rows = list(getattr(dump, "placements", ()) or ())
    if not rows:
        return ()
    n_of: dict[str, int] = {}
    for p in rows:
        n_of[p.def_path] = n_of.get(p.def_path, 0) + 1
    # the smallest unit box containing the point wins: a concourse inside
    # a terminal is the seat a body standing in it takes
    boxes = sorted(unit_seats, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    out: list[MslSeat] = []
    for i, p in enumerate(rows):
        if i in split_idx or n_of.get(p.def_path, 0) < 2:
            continue
        if p.def_path in have or _obj8.is_stock_library_resource(p.def_path):
            continue
        seat = None
        for la0, lo0, la1, lo1, zero, src in boxes:
            if la0 <= p.lat <= la1 and lo0 <= p.lon <= lo1:
                seat = (zero, src)
                break
        if seat is None:
            continue                      # in no unit: §16c seats it
        zero, src = seat
        off = authored_offset(p, authored_ground)
        if off is None:
            continue                      # an MSL row with no known ground
        z = surface(p.lat, p.lon)
        if z is not None and abs(float(z) - zero) <= tol_m and off == 0.0:
            continue                      # the terrain IS the datum: leave it
        out.append(MslSeat(i, p.def_path, float(p.lon), float(p.lat),
                           float(p.heading_deg), float(zero) + off, src))
    return tuple(out)


def authored_offset(p: _t.Any, authored_ground: "float | None"
                    ) -> "float | None":
    """§16g (5) (owner RULINGS 2026-09-13cb): the height THIS placement's
    row asks for above the ground it stands on.

    ``OBJECT_AGL``'s elevation column already is it.  ``OBJECT_MSL``'s is
    an absolute against the ground the pack was AUTHORED on, so the
    offset is that absolute minus ``authored_ground``; with no authored
    ground known the offset cannot be recovered and the caller is told so
    (``None``) rather than handed a guess.  A plain ``OBJECT`` row asks
    for 0 — whatever height its geometry carries is inside the file and
    rides with it."""
    kind = getattr(p, "kind", "OBJECT")
    if kind == "OBJECT_AGL":
        return float(getattr(p, "elevation", 0.0) or 0.0)
    if kind == "OBJECT_MSL":
        if authored_ground is None:
            return None
        return float(getattr(p, "elevation", 0.0) or 0.0) - float(authored_ground)
    return 0.0


def multi_anchor_census(dump: _t.Any, plan: _t.Any,
                        msl: _t.Sequence[_t.Any],
                        split_idx: _t.AbstractSet[int],
                        unit_seats: _t.Sequence[tuple] = ()) -> dict[str, int]:
    """§16g (5) as amended (owner RULINGS 2026-09-13by): how the
    MULTI-ANCHOR placements the plan holds no member for are seated.

    ``multi_anchor_on_ground`` — left alone, the design surface seats
    them (the default and the better one: under a terminal cluster the
    mesh terrain IS the cluster pad, i.e. the floor).
    ``multi_anchor_object_msl`` — written with an elevation because their
    unit's datum is a DECK and on-ground would put them on the road under
    it.  ``multi_anchor_converted_from_msl`` — rows the pack authored as
    ``OBJECT_MSL`` / ``OBJECT_AGL`` for pieces standing on the ground,
    which the conversions pass turns into on-ground rows (the other half
    of the owner's 11b: "remove all hard-coded elevations").

    NONE of them is DROPPED any more, which is the number the ruling
    asks for: KCLT's 205 were dropped only because the plan wanted to
    write one offset into one shared file and could not."""
    from . import obj8 as _obj8
    have = {m.resource for u in getattr(plan, "units", ()) for m in u.members}
    rows = list(getattr(dump, "placements", ()) or ())
    n_of: dict[str, int] = {}
    for p in rows:
        n_of[p.def_path] = n_of.get(p.def_path, 0) + 1
    seated = {m.index for m in msl}
    out = {"multi_anchor_rows": 0, "multi_anchor_in_a_unit": 0,
           "multi_anchor_on_ground": 0, "multi_anchor_object_msl": 0,
           "multi_anchor_converted_from_msl": 0, "multi_anchor_dropped": 0}
    for i, p in enumerate(rows):
        if i in split_idx or n_of.get(p.def_path, 0) < 2:
            continue
        if p.def_path in have or _obj8.is_stock_library_resource(p.def_path):
            continue
        out["multi_anchor_rows"] += 1
        if i in seated:
            out["multi_anchor_object_msl"] += 1
        elif p.kind in ("OBJECT_MSL", "OBJECT_AGL"):
            out["multi_anchor_converted_from_msl"] += 1
        else:
            out["multi_anchor_on_ground"] += 1
        if any(la0 <= p.lat <= la1 and lo0 <= p.lon <= lo1
               for la0, lo0, la1, lo1, _z, _s in unit_seats):
            out["multi_anchor_in_a_unit"] += 1
    return out
