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
from .placement_family import (FAMILY_CONTACTS_MAX, Family, _all_on_pavement,
                               _clusters, _contacts_of, _median,
                               cluster_plane, pad_plurality, union_area_m2)

__all__ = ["UNIT_REASON", "bind_footprint_units"]


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


def _span_m(boxes: _t.Sequence[tuple[float, float, float, float]]) -> float:
    """The plan DIAGONAL of a body's footprint, metres (§16g (3))."""
    h = _pb.hull_of(boxes)
    if h is None:
        return 0.0
    ml, mo = _ar._m_per_deg(0.5 * (h[0] + h[2]))
    return (((h[2] - h[0]) * ml) ** 2 + ((h[3] - h[1]) * mo) ** 2) ** 0.5


def _is_connector(c: _t.Any, cc: _t.Sequence[tuple[float, float, float, float]],
                  span_m: float, visual_m: float) -> bool:
    """§16g (3) THE ONLY CUT — the HECA elevated-rail class: a footprint
    span of at least ``span_m`` AND two ends whose GROUND differs by at
    least ``visual_m``.  "Very long connecting pieces ... which would
    require two buildings kilometers apart to be at the same elevation"
    (owner 13bo); everything shorter stays rigid however steep.

    The ends are the two contacts furthest apart in plan, read on the
    hull's long axis — the cheap reading of "its two ends", and the one
    the span itself is measured on."""
    if span_m <= 0.0 or visual_m <= 0.0 or len(cc) < 2:
        return False
    boxes = list(c.part_boxes) or ([c.box] if c.box else [])
    if _span_m(boxes) < span_m:
        return False
    h = _pb.hull_of(boxes)
    if h is None:
        return False
    along_lat = (h[2] - h[0]) >= (h[3] - h[1])
    key = (lambda q: q[0]) if along_lat else (lambda q: q[1])
    lo = min(cc, key=key)
    hi = max(cc, key=key)
    return abs((lo[3] - lo[2]) - (hi[3] - hi[2])) >= visual_m


def bind_footprint_units(cands: list, staged: _t.Sequence[_t.Any],
                         surface: _ar.Surface,
                         pads: _t.Sequence[_ar.PadRing], counts: dict, *,
                         unit_id: str = "", touch_m: float = 0.0,
                         visual_m: float = 0.0, cluster_min_m2: float = 0.0,
                         connector_span_m: float = 0.0) -> list[Family]:
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

    (3) THE ONLY CUT: a CONNECTOR (:func:`_is_connector`) is left out of
    the unit's rigid bind and named, so §10's line stations and §16b's
    own terrain cut divide it as they already do.

    Mutates ``cands`` and the staged members' ``raw`` / ``ground_off`` in
    place, the shape :func:`bind_families` and
    ``placement_atom.bind_unit`` both take.  Returns the units, for the
    census."""
    if touch_m <= 0.0 or not cands:
        return []
    from . import placement_carrier as _pc
    by_mi = {st.mi: st for st in staged}
    clusters, _adj = _clusters(cands, touch_m, min_members=1)
    units: list[Family] = []
    bound_ci: set[int] = set()
    for cl in clusters:
        per: dict[int, list] = {}
        n_conn = 0
        for ci in cl:
            c = cands[ci]
            st = by_mi.get(c.member)
            if st is None:
                continue
            cc = _contacts_of(c, st, surface)
            if not cc:
                continue
            if _is_connector(c, cc, connector_span_m, visual_m):
                n_conn += 1
                counts["unit_connectors_cut"] = \
                    counts.get("unit_connectors_cut", 0) + 1
                continue
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
