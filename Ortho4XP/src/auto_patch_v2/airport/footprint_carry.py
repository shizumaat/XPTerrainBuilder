"""§16g (3)/(11) THE UNIT CARRY AND THE UNIT'S CONTENTS — the carry
machinery split out of ``footprint_unit`` (issue #303: that file passed
the 1,500-line split point again, after the ``footprint_seats`` split of
issue #104 / RULINGS 2026-09-13bz).

No behaviour of its own.  Three questions, all asked of a plan ALREADY
seated by ``footprint_unit.plan_unit_datums`` /
``footprint_seats.plan_wide_seats``, so nothing here reads this module's
siblings back and the split needs no lazy import:

* :func:`unit_carry_index` — the per-plan ``unit id -> (hull, boxes,
  zero, where, source)`` index both answers below read.
* :func:`unit_carry` (issue #31) — WHICH §16g unit carries a FOOTLESS
  piece, by part id then by plan box.
* :func:`contents_seat` (issue #10 [HECA-5], #289, #290) — a UNIT'S
  CONTENTS RIDE THE UNIT: whether a carried piece keeps the carrier the
  search chose, takes another member of its own rigid cluster, or rides
  its unit's datum itself.

:func:`is_connector_length` is the owner's railway carve-out (09-18s)
both of them apply, and :data:`UNIT_CARRY` / :data:`CONTENTS_SEAT` are
the counts keys their instruments read.  ``footprint_unit`` re-exports
every name, so every caller still reads ``footprint_unit.unit_carry``.
"""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import typing as _t

from . import placement_boxes as _pb
from .placement_contact import m_per_deg_exact

__all__ = ["UNIT_CARRY", "UNIT_CARRY_BOXES_MAX", "CONTENTS_SEAT",
           "UnitCarry", "contents_seat", "is_connector_length",
           "unit_by_pid", "unit_carry", "unit_carry_index"]


#: issue #31 (§16g (11), the owner's SPJC read of 2026-09-30y: "the
#: terminal ... separating from its jetways"): the reason a FOOTLESS
#: placement carried by its own FOOTPRINT UNIT records, and the counts
#: key both instruments read.  §16 (3)'s ``footless_own_ground`` keeps
#: only the footless pieces no unit of the plan admits.
UNIT_CARRY = "footless_carried_by_unit"

#: issue #31: the unit's own part boxes are read at this stride cap when
#: the frontage question is asked of one — the same bound
#: ``FAMILY_CONTACTS_MAX`` puts on a unit's contacts, for the same
#: reason (a 1,000 m terminal publishes tens of thousands of parts and
#: the answer does not depend on reading every one of them).
UNIT_CARRY_BOXES_MAX = 4000


@_dc.dataclass(frozen=True)
class UnitCarry:
    """issue #31: one footless piece's CARRIER, where the carrier is its
    §16g FOOTPRINT UNIT rather than a footed body of it.

    ``zero_z`` is the unit's DATUM — the one zero §16g (2) gives every
    member, which after #174/#182 is the composed unit's origin plane
    ``p0``: a pad plane, a deck's abutment datum, or the median ground
    under the unit's contacts.  ``why`` is the sentence the anchor's
    reason carries, so the record names the carrier the law chose."""

    unit: str
    zero_z: float
    where: str
    source: str
    why: str


def unit_carry_index(plan: _t.Any, plan_wide: _t.Mapping[int, tuple]
                     ) -> dict[str, tuple]:
    """issue #31: ``unit id -> (plan hull, part boxes, zero, where,
    source)`` for every §16g unit of ``plan`` that has a datum.

    The FOOTPRINT is the unit's own part boxes (§16g (1)'s own reading,
    the one its derivation chains at ``footprint_touch_m``); the hull is
    kept beside them only as the cheap pre-filter :func:`unit_carry`
    tests first, because a unit's hull overstates its footprint wherever
    the unit is L-shaped.  LINE parts are left out: a fence's
    axis-aligned box says nothing about where a unit stands (§16 (3)'s
    own sentence, read on this side).

    Built ONCE per plan and only where a footless piece actually asks —
    a plan whose every footless piece found a footed carrier pays
    nothing."""
    boxes: dict[str, list[tuple[float, float, float, float]]] = {}
    info: dict[str, tuple[float, str, str]] = {}
    for u in getattr(plan, "units", ()) or ():
        for m in u.members:
            for p in m.parts:
                if getattr(p, "line", False) or not p.box:
                    continue
                row = plan_wide.get(p.pid)
                if row is None or row[1] is None:
                    continue
                uid = str(row[0])
                if uid not in info:
                    info[uid] = (float(row[1]), str(row[2] or ""),
                                 str(row[3] or ""))
                boxes.setdefault(uid, []).append(tuple(p.box))
    out: dict[str, tuple] = {}
    for uid, bx in boxes.items():
        h = _pb.hull_of(bx)
        if h is None:
            continue
        step = max(1, len(bx) // UNIT_CARRY_BOXES_MAX)
        z, where, src = info[uid]
        out[uid] = (h, tuple(bx[::step]), z, where, src)
    return out


def is_connector_length(box: "tuple[float, float, float, float] | None",
             span_max_m: float) -> bool:
    """The owner's railway carve-out (09-18s), read on a plan box: a
    piece whose plan diagonal reaches ``span_max_m`` is the CONNECTOR
    class, never bound rigidly to one unit's datum.  0 disarms."""
    if span_max_m <= 0.0 or box is None:
        return False
    ml, mo = m_per_deg_exact(0.5 * (box[0] + box[2]))
    return _math.hypot((box[2] - box[0]) * ml,
                       (box[3] - box[1]) * mo) >= span_max_m


def unit_by_pid(pids: _t.AbstractSet[int], plan_wide: _t.Mapping[int, tuple],
                index: _t.Mapping[str, tuple]) -> "UnitCarry | None":
    """THE PART-ID JOIN (:func:`unit_carry`'s first join, factored so the
    contents seat below reads the same answer): the §16g unit holding the
    most of ``pids`` (the unit id breaks a tie), or ``None``."""
    hit: dict[str, int] = {}
    for q in pids:
        row = plan_wide.get(q)
        if row is not None and str(row[0]) in index:
            hit[str(row[0])] = hit.get(str(row[0]), 0) + 1
    if not hit:
        return None
    uid = max(sorted(hit), key=lambda k: hit[k])
    _h, _bx, z, where, src = index[uid]
    return UnitCarry(uid, z, where, src,
                     f"{UNIT_CARRY}: within its own §16g unit {uid}"
                     f" (§16g (1): its parts are the unit's)")


def _is_connector_row(row: "tuple | None") -> bool:
    """Does a plan-wide row (``footprint_seats.plan_wide_seats``) name a
    §16g (6) CONNECTOR — two distinct ends, or the plan's ``cut``
    verdict?"""
    if not row:
        return False
    if len(row) > 6 and row[6] == "cut":
        return True
    pair = row[4] if len(row) > 4 else None
    return bool(pair) and len(pair) == 2 and pair[0] != pair[1]


#: the count of carried bodies :func:`contents_seat` moved off a carrier
#: standing at another level onto their own unit's datum
CONTENTS_SEAT = "contents_rerouted_to_unit"


def contents_seat(over: _t.Sequence[tuple], pids: _t.AbstractSet[int],
                  box: "tuple[float, float, float, float] | None",
                  plan_wide: _t.Mapping[int, tuple],
                  index: _t.Mapping[str, tuple], *,
                  alternatives: _t.Sequence[_t.Any] = (),
                  tol_m: float = 0.0, span_max_m: float = 0.0,
                  counts: "dict | None" = None,
                  piece_boxes: "_t.Sequence[tuple] | None" = None,
                  deck_rider: "_t.Callable[[_t.Any], bool] | None" = None
                  ) -> "tuple[list, UnitCarry | None]":
    """Issue #10 [HECA-5] (lane ``interiors10``): A UNIT'S CONTENTS RIDE
    THE UNIT.  ``(carriers, None)`` to keep — or replace — the carriers
    the search chose; ``([], unit)`` to seat the piece on its own unit's
    datum instead.

    MEASURED (HECA, main 0bc1a0ce): of the 2,491 written bodies whose part
    ids the plan-wide map (§16g (1) chain, S6 contents, 27a sheets) puts
    in a footprint unit, 180 stand more than 0.5 m off that unit's datum,
    140 of them CARRIED — 118 through §16c (7)'s contact cluster, whose
    senior footed body is a kerb, a sidewalk or a NEIGHBOUR's wall (66 in
    another unit, 62 in none), and 20 through §15's "rests on it".  The
    windows, doors and glass of a terminal then render at the sidewalk's
    level (T3 ``Plastic`` -7.24 m, the T23 hangar's doors +10.58 m) — the
    owner's "missing interiors / levels separated".

    THE RULE.  A piece whose own parts name unit U (the part-id join,
    :func:`unit_by_pid`) keeps the carrier only where that carrier's zero
    IS U's (within ``tol_m``, ``[placement] split_tol_m``).  Otherwise a
    member of ``alternatives`` (the other candidates of the same rigid
    cluster) standing at U's zero takes it; failing that the piece rides
    U ITSELF (the issue #31 unit carry — its authored y kept over U's
    datum).  A CONNECTOR-length piece (``span_max_m``) is left alone: the
    owner's railway carve-out, as in :func:`unit_carry`.

    ISSUE #289 (lane ``hecaobjects``): the carve-out is read on the
    piece's own PARTS (``piece_boxes``, one plan box per solid
    component), never on the hull of the whole piece.  A carried piece
    is often a scatter of small components of one material — T3's
    ``T3_6``/``360_room``/``T2_glass`` panes chained 240-331 m across the
    terminal by §16c (7) — whose hull reads connector-length while no
    one of them is a railway; the carve-out kept them on a carrier
    standing on ANOTHER block (2.64-3.27 m off their own, HECA control
    ``hecaobjects_ctl``).  A part reaching connector length is the
    carve-out only where the PLAN calls its piece a connector (its
    plan-wide row carries two connector ends, §16g (6)): T3's 240-331 m
    floor and roof slabs (8,108-13,148 m2) are members of the terminal's
    unit, not railways.

    ISSUE #290: a piece RIDING A DECK stays on its deck.  ``deck_rider``
    says, for a DECK carrier, whether the piece is that deck's own edge
    furniture (its parts stand on the deck's authored surface —
    ``bridge_family.DeckPrint.top_at``); such a carrier is kept whatever
    its zero, because a deck and what stands on it are one rigid
    assembly (§16e (3)).  HECA's ``T23/T3_road`` viaduct had its
    railings, lamp posts and signs moved by this rule onto the terminal's
    datum 6.17 m above the road surface they stand on."""
    if not over or not plan_wide or not index:
        return list(over), None
    if piece_boxes:
        if (any(is_connector_length(b, span_max_m) for b in piece_boxes)
                and any(_is_connector_row(plan_wide.get(q)) for q in pids)):
            return list(over), None
    elif is_connector_length(box, span_max_m):
        return list(over), None
    if deck_rider is not None:
        on_deck = [t for t in over
                   if getattr(t[0], "body_class", "") == "deck"
                   and deck_rider(t[0])]
        if on_deck:
            # the deck ALONE carries it: a sidewalk or kerb beside the
            # deck that the search also named is seated by its own rule
            # and is not the deck's datum
            if counts is not None:
                counts[CONTENTS_SEAT + "_kept_deck_rider"] = \
                    counts.get(CONTENTS_SEAT + "_kept_deck_rider", 0) + 1
            return on_deck, None
    uc = unit_by_pid(pids, plan_wide, index)
    if uc is None:
        return list(over), None

    def _zero(c: _t.Any) -> "float | None":
        a = c.anchor
        return (None if a.surface_z is None
                else float(a.surface_z) - float(a.y_zero))

    def _at(c: _t.Any) -> bool:
        z = _zero(c)
        return z is not None and abs(z - float(uc.zero_z)) <= tol_m

    if all(_at(c) for c, *_r in over):
        return list(over), None
    for alt in alternatives:
        if _at(alt):
            if counts is not None:
                counts[CONTENTS_SEAT + "_alt_carrier"] = \
                    counts.get(CONTENTS_SEAT + "_alt_carrier", 0) + 1
            return [(alt, f"issue #10: its parts are unit {uc.unit}'s "
                     "contents — the member of its rigid cluster at the "
                     "unit's zero")], None
    c0 = next((c for c, *_r in over if not _at(c)), over[0][0])
    z0 = _zero(c0)
    if counts is not None:
        counts[CONTENTS_SEAT] = counts.get(CONTENTS_SEAT, 0) + 1
        if z0 is not None:
            counts[CONTENTS_SEAT + "_worst_m"] = max(
                counts.get(CONTENTS_SEAT + "_worst_m", 0.0),
                round(abs(z0 - float(uc.zero_z)), 3))
    return [], _dc.replace(
        uc, why=(f"{UNIT_CARRY}: issue #10, its parts are unit {uc.unit}'s "
                 f"contents and the carrier "
                 f"{str(getattr(c0, 'resource', '?')).rsplit('/', 1)[-1]} "
                 + ("stands off-sheet" if z0 is None else
                    f"stands {z0 - float(uc.zero_z):+.2f} m off its datum")))


def unit_carry(pids: _t.AbstractSet[int],
               box: "tuple[float, float, float, float] | None",
               plan_wide: _t.Mapping[int, tuple],
               index: _t.Mapping[str, tuple],
               *, frontage_m: float = 0.0, span_max_m: float = 0.0,
               counts: "dict | None" = None) -> "UnitCarry | None":
    """issue #31 (§16 (3) NARROWED): WHICH UNIT CARRIES THIS FOOTLESS
    PIECE?  ``None`` where no unit of the plan admits it, and only then
    does §16 (3)'s own-ground path still apply.

    The owner's law is 2026-09-18s read on the object stage: *"Anything
    that intersects the building (and doesn't extend of hundreds of
    metres like a railway) is just treated as part of that building and
    moves with it ... the flat terminal area should include the
    jetways."*  A jetway's ``.obj`` has no foot below the contact band —
    its tunnel hangs off the terminal and its rotunda stands on the
    terminal's own floor — so it is a FOOTLESS body, and §16 (3) wrote it
    at the ground under its own footprint whenever the carrier search
    refused every footed body of its unit.  A terminal seated on a pad is
    exactly that case: §16a (2) refuses its walls as a carrier (their
    zero is the pad's and the ground under their own feet is the DEM
    metres below), the fallbacks are refused by the carried-side test for
    the same reason, and the jetway is left on the terrain while the
    terminal rides the pad.  That is the separation the owner read at
    SPJC (RULINGS 2026-09-30y).

    TWO JOINS, in order:

    1. **THE PART ID.**  A piece whose own parts already name a unit in
       ``plan_wide`` is a member of it by §16g (1)'s own derivation —
       the chain, S6's CONTENTS or 27a's spanning sheet put it there.
       Where its parts name more than one, the unit holding the most of
       them wins (the unit id breaks a tie, so the answer never depends
       on iteration order).
    2. **THE PLAN BOX.**  Otherwise the piece's plan box is asked against
       each unit's own footprint: the unit it OVERLAPS most, else — a
       jetway bay set down against the frontage and overlapping nothing
       — the nearest unit within ``frontage_m``.  ``frontage_m`` is
       ``[placement] footprint_touch_m``, the same tolerance §16g (1)
       chains two footprints at; 0 disarms the box join entirely.

    THE RAILWAY CARVE-OUT IS THE OWNER'S OWN (09-18s: "doesn't extend of
    hundreds of metres like a railway").  A piece whose own plan diagonal
    reaches ``span_max_m`` (``[placement] connector_span_m``) is the
    CONNECTOR class §16g (3)/(6) governs — cut at §10's stations and
    seated per end, never bound rigidly to one unit's datum — so it is
    refused here and keeps whatever §16 (3) gave it.  0 disarms the test.

    The piece takes that unit's DATUM and nothing else: no ground read
    of its own, no height guessed from its neighbours."""
    if not index:
        return None
    if is_connector_length(box, span_max_m):
        if counts is not None:
            counts["footless_unit_carry_refused_connector"] = \
                counts.get("footless_unit_carry_refused_connector", 0) + 1
        return None
    by_pid = unit_by_pid(pids, plan_wide, index)
    if by_pid is not None:
        if counts is not None:
            counts["footless_unit_carry_by_pid"] = \
                counts.get("footless_unit_carry_by_pid", 0) + 1
        return by_pid
    if box is None or frontage_m <= 0.0:
        return None
    best_over: tuple[float, str] | None = None
    best_gap: tuple[float, str] | None = None
    for uid in sorted(index):
        h, bx, _z, _w, _s = index[uid]
        if _pb.box_gap_m(box, h) > frontage_m:
            continue
        over = max((_pb.overlap_m2(box, b) for b in bx), default=0.0)
        if over > 0.0:
            if best_over is None or over > best_over[0]:
                best_over = (over, uid)
            continue
        gap = min((_pb.box_gap_m(box, b) for b in bx), default=None)
        if gap is not None and gap <= frontage_m:
            if best_gap is None or gap < best_gap[0]:
                best_gap = (gap, uid)
    if best_over is not None:
        uid = best_over[1]
        _h, _bx, z, where, src = index[uid]
        if counts is not None:
            counts["footless_unit_carry_within"] = \
                counts.get("footless_unit_carry_within", 0) + 1
        return UnitCarry(uid, z, where, src,
                         f"{UNIT_CARRY}: its plan box lies within unit "
                         f"{uid}'s footprint ({best_over[0]:.1f} m2)")
    if best_gap is not None:
        uid = best_gap[1]
        _h, _bx, z, where, src = index[uid]
        if counts is not None:
            counts["footless_unit_carry_frontage"] = \
                counts.get("footless_unit_carry_frontage", 0) + 1
        return UnitCarry(uid, z, where, src,
                         f"{UNIT_CARRY}: it touches unit {uid}'s frontage "
                         f"({best_gap[0]:.2f} m)")
    return None

