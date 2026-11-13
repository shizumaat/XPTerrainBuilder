"""§9a THE ISOLATED SEAT: an object standing apart stands on its lowest
contact feet (#2063 round 3; owner RULINGS 2026-11-13y (4)/(5), 2026-10-22o,
2026-11-13r; spec ``docs/specs/2063-round3-isolated-seat-spec.md``).

THE DEFECT (KRNT, the owner's sim read 2026-11-13).  A parked aircraft
stands on its wheels, and the generic anchor (``anchor_rule._generic_anchor``)
seats every body at the MEDIAN of ``surface - y`` over every foot of every
part: the gear legs, the belly and the wheels all vote, each at its own
height.  On a sloping apron the median buried 25 of KRNT's 29 footed aircraft
bodies' wheels more than 5 cm.  13y (5): "a free-standing object (>= 2 m plan
gap from anything else, 22o) is seated on its lowest contact feet".

THE ISOLATED CLUSTER (:func:`clusters`).  The plan's solid parts joined
wherever their plan outlines (``Part.rings``, else ``Part.box``) come within
``[placement] rigid_reach_m``.  A LINE part neither links nor blocks (10bb);
a part of a sibling plan of the airport (``foreign``) blocks but never
joins.  A SHARE is the cluster's parts within one plan ``Unit`` (one anchor
frame).

THE CERTAIN WITNESS (13r: any doubt keeps today's seat).  A share is seated
here only when ALL hold, and each refusal is counted by reason:

* I1 ``not_isolated``: no foreign outline within the reach;
* I2 ``structure``: no member of the CLUSTER is skirted, a deck, a plate, a
  datum, a basin, a connector, an authored seat, an adapted frame, or
  carries a welded base plane (a part of such a member within the reach of
  a candidate refuses it the same way: the closure would hold it);
* I3 ``span``: the cluster's plan diagonal is within ``span_max_m``;
* I4 ``no_feet`` / ``off_author_ground``: the share has feet and its
  lowest authored ``y`` is within ``split_tol_m`` of ``-Unit.agl_m``;
* I5 ``no_surface`` / ``water`` / ``pad`` / ``deck`` / ``rim``: every
  lowest contact foot reads the design surface, on land, off every object
  pad (``pad_majority``), deck face and rim ring;
* I6 ``spread``: ``surface - y`` over the lowest contact feet spreads no
  more than ``split_tol_m`` (one terrain; the object stays level).

THE SEAT (:func:`seat`).  The lowest contact feet ``L`` are the feet within
``motion_step_m`` of the share's lowest (``placement_motion.
lowest_contact_feet``); over them ``r = surface - y`` and the zero is
``Z = max(median(r), max(r) - motion_step_m)``: no contact foot is buried
more than the motion step, and the apron's fall across the gear shows as
float.  ONE frame per share: every body of every member of it is written at
that anchor.

NO LAW CONSTANT LIVES HERE.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics
import typing as _t

from . import anchor_rule as _ar
from . import placement_contact as _pcon
from .placement_motion import lowest_contact_feet

__all__ = ["Share", "REFUSALS", "ISO_PREFIX", "outlines", "clusters",
           "shares", "seat", "keep_isolated", "without"]

#: every refusal reason, in the order the witness asks them
REFUSALS = ("not_isolated", "structure", "span", "no_feet",
            "off_author_ground", "no_surface", "water", "pad", "deck", "rim",
            "spread")

#: the share id's prefix (``Anchor.isolated``)
ISO_PREFIX = "iso:"

#: the deck verdicts I2 refuses (``Member.deck_kind``)
_DECK_KINDS = frozenset({"flag", "signature", "family"})


@_dc.dataclass(frozen=True)
class Share:
    """One seated share: its id, plan unit index, part ids and anchor."""

    id: str
    unit: int
    pids: frozenset
    anchor: _ar.Anchor


def outlines(plan: _t.Any) -> tuple:
    """Every non-line part's plan outline ``(box, rings)`` — what a sibling
    plan of the same airport passes as ``foreign`` (I1)."""
    return tuple((p.box, p.rings) for u in plan.units for m in u.members
                 for p in m.parts if not p.line)


def _structure(m: _t.Any, rims: _t.Sequence[_ar.RimRing], seats: frozenset,
               adapted: frozenset, conn: frozenset) -> bool:
    """I2: does this member carry a structure verdict another law seats?
    A DECK is the plan's deck verdict (``flag`` / ``signature`` and their
    ``family``, the kinds §6 classes ``deck`` and seats with it) — a
    ``candidate`` plate has no spanning evidence and is no deck (an
    aircraft's wing reads as one)."""
    planes = (getattr(m, "base_profile", None) or {}).get("planes") or ()
    planes = planes if isinstance(planes, (int, float)) else len(planes)
    return bool(m.skirted or m.deck_kind in _DECK_KINDS or m.elevated_deck
                or m.plate_y is not None or m.anchor_zero is not None
                or m.deck_datum_z is not None or planes >= 1
                or str(m.id) in seats or _ar.datum_of(m) is not None
                or any(p.pid in adapted or p.pid in conn for p in m.parts)
                or (rims and any(p.base_y < 0.0 and _ar.ring_of_part(
                    rims, p.lat, p.lon, p.feet) is not None for p in m.parts)))


def clusters(parts: _t.Sequence[_t.Any], reach_m: float,
             blockers: _t.Sequence[tuple] = (), ref_lat: float = 0.0
             ) -> tuple[list[list[int]], dict[int, set[int]]]:
    """``(clusters, blocked)``: the indices of ``parts`` grouped where their
    outlines come within ``reach_m`` (singletons included), and per
    cluster the indices of the ``blockers`` outlines ``(box, rings)`` within
    the reach of it — a blocker never joins two clusters."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(parts)
    if not n:
        return [], set()
    pairs, near = _pcon.gap_pairs([(p.box, p.rings) for p in parts], reach_m,
                                  ref_lat, blockers)
    if pairs:
        a = [q[0] for q in pairs]
        b = [q[1] for q in pairs]
        g = coo_matrix(([1] * len(a), (a, b)), shape=(n, n))
        _k, lab = connected_components(g, directed=False)
        lab = [int(q) for q in lab]
    else:
        lab = list(range(n))
    by: dict[int, list[int]] = {}
    for i, q in enumerate(lab):
        by.setdefault(q, []).append(i)
    out = [by[k] for k in sorted(by, key=lambda k: by[k][0])]
    idx = {i: c for c, grp in enumerate(out) for i in grp}
    blocked: dict[int, set[int]] = {}
    for i, k in near:
        blocked.setdefault(idx[i], set()).add(k)
    return out, blocked


def _span_m(parts: _t.Sequence[_t.Any]) -> float:
    lat0 = min(p.box[0] for p in parts)
    lat1 = max(p.box[2] for p in parts)
    ml, mo = _pcon.m_per_deg_exact(0.5 * (lat0 + lat1))
    return math.hypot((lat1 - lat0) * ml,
                      (max(p.box[3] for p in parts) - min(p.box[1] for p in parts)) * mo)


def _surface(surface: _ar.Surface, pts: _t.Sequence[tuple]) -> list:
    many = getattr(surface, "many", None)
    if many is not None:
        return [None if z is None or z != z else float(z)
                for z in many([p[0] for p in pts], [p[1] for p in pts])]
    return [None if (z := surface(p[0], p[1])) is None else float(z) for p in pts]


def seat(readings: _t.Sequence[tuple[float, float, float, float]],
         step_m: float) -> "tuple[tuple[float, float, float, float], float, float]":
    """THE SEAT of one share over its lowest contact feet ``(lat, lon, y,
    surface z)``: ``(anchor foot, Z, median)``.  ``Z = max(median(r), max(r)
    - step_m)`` with ``r = z - y``; the anchor is the foot whose ``r`` is
    nearest ``Z`` (the highest-``r`` foot when the burial cap binds), ties
    to the lowest ``|y|`` then south-west — deterministic over a pack."""
    rs = [z - y for _la, _lo, y, z in readings]
    med = float(statistics.median(rs))
    zero = max(med, max(rs) - float(step_m))
    best = min(readings, key=lambda f: (round(abs(f[3] - f[2] - zero), 9),
                                        round(abs(f[2]), 6), f[0], f[1]))
    return best, zero, med


def _refuse(counts: dict, why: str, n: int = 1) -> None:
    counts[f"isolated_refused_{why}"] = counts.get(f"isolated_refused_{why}", 0) + n


def shares(plan: _t.Any, surface: _ar.Surface,
           pads: _t.Sequence[_ar.PadRing] = (), rims: _t.Sequence[_ar.RimRing] = (),
           decks: _t.Sequence[_ar.DeckFace] = (), *, reach_m: float,
           span_max_m: float, split_tol_m: float, step_m: float,
           foreign: _t.Sequence[tuple] = (), counts: "dict | None" = None,
           refused: "dict | None" = None) -> dict[int, Share]:
    """Every seated share of ``plan`` (module doc), keyed by part id.  Any
    of ``reach_m``, ``split_tol_m`` or ``step_m`` at 0 disarms (``{}``).
    ``refused``, when given, is filled ``share id -> reason`` for every
    share refused (the report's ISOLATED block)."""
    counts = counts if counts is not None else {}
    if reach_m <= 0.0 or split_tol_m <= 0.0 or step_m <= 0.0:
        return {}
    from .footprint_connector import verdicts_of
    seats = frozenset(str(r.get("id")) for r in getattr(plan, "authored_seats", ()) or ()
                      if hasattr(r, "get"))
    adapted = frozenset(getattr(plan, "adapted_frame_pids", ()) or ())
    conn = frozenset(q for v in (verdicts_of(plan) or ()) for q in v.pids)
    cand: list[tuple[_t.Any, int, _t.Any]] = []
    blockers: list[tuple] = []
    for ui, u in enumerate(plan.units):
        for m in u.members:
            solid = [p for p in m.parts if not p.line]
            if _structure(m, rims, seats, adapted, conn):
                blockers.extend((p.box, p.rings) for p in solid)
            else:
                cand.extend((p, ui, m) for p in solid)
    parts = [c[0] for c in cand]
    if not parts:
        return {}
    n_struct = len(blockers)
    groups, blocked = clusters(parts, reach_m, blockers + list(foreign),
                               parts[0].lat)
    out: dict[int, Share] = {}
    counts["isolated_clusters"] = counts.get("isolated_clusters", 0) + len(groups)
    for ci, grp in enumerate(groups):
        by_unit: dict[int, list[int]] = {}
        for i in grp:
            by_unit.setdefault(cand[i][1], []).append(i)
        # a structure of THIS plan within the reach is in the closure (I2);
        # a sibling plan's part only blocks (I1)
        near = blocked.get(ci, ())
        why = ("structure" if any(k < n_struct for k in near) else
               "not_isolated" if near else
               "span" if span_max_m > 0.0 and _span_m([parts[i] for i in grp]) > span_max_m
               else None)
        for ui, idx in sorted(by_unit.items()):
            s, why2 = ((None, why) if why else
                       _share(plan, ui, [parts[i] for i in idx], surface, pads,
                              rims, decks, split_tol_m, step_m))
            if s is None:
                _refuse(counts, why2)
                if refused is not None:
                    refused[f"{ISO_PREFIX}{min(parts[i].pid for i in idx)}@{ui}"] = why2
                continue
            counts["isolated_shares"] = counts.get("isolated_shares", 0) + 1
            out.update((q, s) for q in s.pids)
    return out


def _share(plan, ui: int, sp: list, surface, pads, rims, decks,
           split_tol_m: float, step_m: float) -> "tuple[Share | None, str]":
    """One share's witness I4-I6 and seat, or ``(None, reason)``."""
    u = plan.units[ui]
    feet = [f for p in sp for f in p.feet]
    if not feet:
        return None, "no_feet"
    if abs(min(p.base_y for p in sp) + float(u.agl_m or 0.0)) > split_tol_m:
        return None, "off_author_ground"
    low = lowest_contact_feet(feet, step_m)
    zs = _surface(surface, low)
    if any(z is None for z in zs):
        return None, "no_surface"
    water = getattr(surface, "water", None)
    if water is not None and any(water(f[0], f[1]) for f in low):
        return None, "water"
    rd = [(float(f[0]), float(f[1]), float(f[2]), z) for f, z in zip(low, zs, strict=True)]
    if _ar.pad_majority(rd, pads) is not None:
        return None, "pad"
    if decks and any(_ar.deck_of(decks, f[0], f[1]) is not None for f in low):
        return None, "deck"
    if rims and any(_ar.rim_of(rims, f[0], f[1]) is not None for f in low):
        return None, "rim"
    rs = [z - y for _la, _lo, y, z in rd]
    spread = max(rs) - min(rs)
    if spread > split_tol_m:
        return None, "spread"
    best, zero, med = seat(rd, step_m)
    sid = f"{ISO_PREFIX}{min(p.pid for p in sp)}@{ui}"
    cap = " (burial cap binds)" if zero > med + 1e-9 else ""
    a = _ar.Anchor(_ar.OTHER, best[0], best[1], best[3] - zero,
                   f"isolated {sid}: its lowest contact feet ({len(rd)} within "
                   f"{step_m:g} m), zero {zero:.3f}{cap}, spread {spread:.2f} m "
                   "(RULINGS 2026-11-13y (5), §9a)", best[3], isolated=sid)
    return Share(sid, ui, frozenset(p.pid for p in sp), a), ""


def without(plan: _t.Any, iso: _t.Mapping[int, Share]) -> _t.Any:
    """``plan`` less every isolated part — what the plan-wide group seats
    (§16g units, 22o/22q zeros) are derived from, so no isolated share is
    in a unit or lends its ground to one (13y (4))."""
    if not iso:
        return plan
    units = tuple(_dc.replace(u, members=tuple(
        _dc.replace(m, parts=tuple(p for p in m.parts if p.pid not in iso))
        if any(p.pid in iso for p in m.parts) else m for m in u.members))
        for u in plan.units)
    return _dc.replace(plan, units=units)


def keep_isolated(record: _t.Any, pre: _t.Any) -> _t.Any:
    """``record`` with every isolated body of ``pre`` restored: the group
    seats of pass 4 (22o/22q, the open frames, the airside deck) never
    move an isolated share (13y (4))."""
    was = {b.body_id: b for b in pre.bodies if getattr(b.anchor, "isolated", "")}
    if not was or record is pre:
        return record
    out = tuple(was.get(b.body_id, b) for b in record.bodies)
    return _dc.replace(record, bodies=out)
