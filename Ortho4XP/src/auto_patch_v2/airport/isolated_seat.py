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
  datum, a basin, a connector, an authored seat, an adapted frame, a member
  of an OPEN STRUCTURE's frame (every member a deck or deck candidate,
  which 22c moves as one rigid group), or carries a welded base plane (a
  part of such a member within the reach of a candidate refuses it the
  same way: the closure would hold it);
* I3 ``span``: the cluster's plan diagonal is within ``span_max_m``;
* I7 ``building_file`` (amendment A1): no part of the cluster belongs to a
  BUILDING FILE — a member one of whose own clusters (its solid non-line
  parts joined within the reach, the parts the structure closure took
  included) is WALLED-BASE (:func:`building_files`);
* I8 ``walled`` (A1): the cluster itself is not WALLED-BASE — at least
  ``[placement] chain_min_height_m`` tall AND its feet spread over at least
  ``[placement] isolated_base_min_fraction`` of its plan diagonal
  (:func:`base_spread`): a wall stands on a line of feet as long as itself,
  an aircraft on three wheels well inside its span (KRNT B737 0.32-0.37,
  the lowest wall refused 0.52);
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

THE FROZEN ELECTION (A1 §3.4).  The election is held WITH the isolated
present: no non-isolated body's anchor, zero, senior or carrier may differ
because a share exists.  So today's raws are made from the full groups
(``placement_body._raw_bodies``) and every pass runs on them unchanged; the
share's own raws are made beside them (``placement_body.isolated_raws``) and
read by no pass.  A share one of today's raws WELDS — a raw holding its
parts and a part not its own — is refused ``welded`` (:func:`welded`).  Last,
before the cut, :func:`vacate` drops every today raw all of whose parts are
one share's, hands its components (and the orphans riding with it) to the
share's body, and re-forms what is left of a body around its FROZEN anchor.

NO LAW CONSTANT LIVES HERE.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics
import typing as _t

import numpy as _np

from ..geom.diameter import plan_diameter
from . import anchor_rule as _ar
from . import placement_contact as _pcon
from .placement_motion import lowest_contact_feet

__all__ = ["REFUSALS", "ISO_PREFIX", "outlines", "shares", "welded", "vacate"]

#: every refusal reason, in the order the witness asks them
REFUSALS = ("not_isolated", "structure", "span", "building_file", "walled",
            "welded", "no_feet",
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


def _height_m(parts: _t.Sequence[_t.Any]) -> float:
    """A1: the parts' solid height — their highest top over their lowest
    base (``Part.base_y`` + ``Part.height_m``)."""
    return (max(p.base_y + p.height_m for p in parts)
            - min(p.base_y for p in parts))


def base_spread(parts: _t.Sequence[_t.Any]) -> float:
    """A1: how far the parts' feet spread — the greatest plan distance
    between any two of their feet (every ``Part.feet``) over the parts'
    plan diagonal; 0 with fewer than two feet."""
    feet = [f for p in parts for f in p.feet]
    span = _span_m(parts) if len(feet) >= 2 else 0.0
    if span <= 0.0:
        return 0.0
    la0, lo0 = feet[0][0], feet[0][1]
    ml, mo = _pcon.m_per_deg_exact(la0)
    xy = _np.array([((f[1] - lo0) * mo, (f[0] - la0) * ml) for f in feet])
    return plan_diameter(xy) / span


def _walled_base(parts: _t.Sequence[_t.Any], min_h_m: float,
                min_fraction: float) -> bool:
    """A1's WALLED-BASE: at least ``min_h_m`` tall and the feet spread over
    at least ``min_fraction`` of the plan diagonal (height asked first: it
    is the cheap half)."""
    return bool(parts) and (_height_m(parts) >= min_h_m
                            and base_spread(parts) >= min_fraction)


def building_files(members: _t.Iterable[_t.Any], reach_m: float,
                   min_h_m: float, min_fraction: float) -> frozenset:
    """A1 I7: the ids of the BUILDING FILES among ``members`` — a member
    one of whose own clusters (:func:`clusters` over its solid non-line
    parts at ``reach_m``) is WALLED-BASE (:func:`_walled_base`)."""
    out = set()
    for m in members:
        solid = [p for p in m.parts if not p.line]
        if not solid:
            continue
        groups, _b = clusters(solid, reach_m, (), solid[0].lat)
        if any(_walled_base([solid[i] for i in g], min_h_m, min_fraction)
               for g in groups):
            out.add(m.id)
    return frozenset(out)


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
           refused: "dict | None" = None, wall_min_h_m: float = 0.0,
           base_min_fraction: float = 0.0) -> dict[int, Share]:
    """Every seated share of ``plan`` (module doc), keyed by part id.  Any
    of ``reach_m``, ``split_tol_m`` or ``step_m`` at 0 disarms (``{}``);
    ``wall_min_h_m`` or ``base_min_fraction`` at 0 disarms I7 and I8 both.
    A plan whose parts carry no solid height (``Part.height_m`` all 0, an
    older plan) cannot ask I8 and is disarmed whole, counted
    ``isolated_disarmed_no_height``.  ``refused``, when given, is filled
    ``share id -> reason`` for every share refused (the report's ISOLATED
    block)."""
    counts = counts if counts is not None else {}
    if reach_m <= 0.0 or split_tol_m <= 0.0 or step_m <= 0.0:
        return {}
    walls = wall_min_h_m > 0.0 and base_min_fraction > 0.0
    if walls and not any(p.height_m > 0.0 for u in plan.units
                         for m in u.members for p in m.parts):
        counts["isolated_disarmed_no_height"] = 1
        return {}
    from .footprint_connector import verdicts_of
    seats = frozenset(str(r.get("id")) for r in getattr(plan, "authored_seats", ()) or ()
                      if hasattr(r, "get"))
    adapted = frozenset(getattr(plan, "adapted_frame_pids", ()) or ())
    conn = frozenset(q for v in (verdicts_of(plan) or ()) for q in v.pids)
    cand: list[tuple[_t.Any, int, _t.Any]] = []
    blockers: list[tuple] = []
    member_of: dict[int, _t.Any] = {}
    from .open_frame_seat import OPEN_KINDS
    for ui, u in enumerate(plan.units):
        # an OPEN STRUCTURE's frame (every member a deck or deck candidate)
        # moves as ONE rigid group (RULINGS 2026-10-22c): all structure
        open_frame = bool(u.members) and all(
            str(getattr(x, "deck_kind", "") or "") in OPEN_KINDS for x in u.members)
        for m in u.members:
            member_of.update((p.pid, m) for p in m.parts)
            solid = [p for p in m.parts if not p.line]
            if open_frame or _structure(m, rims, seats, adapted, conn):
                blockers.extend((p.box, p.rings) for p in solid)
            else:
                cand.extend((p, ui, m) for p in solid)
    if not cand:
        return {}
    ref = cand[0][0].lat
    # I2 BY CLOSURE, cheapest first: a candidate within the reach of a
    # structure part is in that structure's cluster, and so is whatever it
    # reaches — it stands in as a blocker for the rest (same verdict as the
    # whole closure, without pairing the clutter round every building)
    # — twice: the parts a structure reaches, then the parts THEY reach
    n_cand = len(cand)
    for _step in range(2):
        near_s = _pcon.near_any([(c[0].box, c[0].rings) for c in cand], blockers,
                                reach_m, ref)
        blockers = [(c[0].box, c[0].rings)
                    for c, d in zip(cand, near_s, strict=True) if d]
        cand = [c for c, d in zip(cand, near_s, strict=True) if not d]
    counts["isolated_parts_by_structure"] = (
        counts.get("isolated_parts_by_structure", 0) + n_cand - len(cand))
    doomed = blockers
    parts = [c[0] for c in cand]
    if not parts:
        return {}
    groups, _b = clusters(parts, reach_m, (), ref)
    outl = [(p.box, p.rings) for p in parts]
    by_struct = _pcon.near_any(outl, doomed, reach_m, ref)
    by_foreign = _pcon.near_any(outl, foreign, reach_m, ref)
    out: dict[int, Share] = {}
    files: dict[str, bool] = {}     # I7, member id -> building file (lazy)
    counts["isolated_clusters"] = counts.get("isolated_clusters", 0) + len(groups)
    for ci, grp in enumerate(groups):
        by_unit: dict[int, list[int]] = {}
        for i in grp:
            by_unit.setdefault(cand[i][1], []).append(i)
        # a structure of THIS plan within the reach is in the closure (I2);
        # a sibling plan's part only blocks (I1)
        why = ("structure" if any(by_struct[i] for i in grp) else
               "not_isolated" if any(by_foreign[i] for i in grp) else
               "span" if span_max_m > 0.0 and _span_m([parts[i] for i in grp]) > span_max_m
               else None)
        if why is None and walls:
            why = _walls(grp, parts, member_of, files, reach_m, wall_min_h_m,
                         base_min_fraction)
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


def _walls(grp: _t.Sequence[int], parts: _t.Sequence[_t.Any],
           member_of: _t.Mapping[int, _t.Any], files: dict, reach_m: float,
           min_h_m: float, min_fraction: float) -> "str | None":
    """A1 I8 / I7 for one plan cluster surviving I1-I3: ``walled`` when the
    cluster itself is WALLED-BASE, else ``building_file`` when a part of it
    belongs to a building file (``files`` caches the member verdicts), else
    ``None``.  The cluster is asked first: a lone wall is ``walled``, and a
    cluster no wall of its own refuses is named by the file that does."""
    if _walled_base([parts[i] for i in grp], min_h_m, min_fraction):
        return "walled"
    for i in grp:
        m = member_of[parts[i].pid]
        if m.id not in files:
            files[m.id] = bool(building_files((m,), reach_m, min_h_m,
                                              min_fraction))
        if files[m.id]:
            return "building_file"
    return None


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


def welded(iso: _t.Mapping[int, Share], raws: _t.Iterable[tuple],
           counts: "dict | None" = None) -> frozenset:
    """A1 §3.4 (4): the ids of the shares a today raw WELDS — a raw (its
    parts first) holding both isolated and non-isolated parts.  Each is
    refused ``welded`` and its seat count taken back.  A raw all of whose
    parts are isolated welds nothing, whatever shares they are of: it is
    vacated whole (:func:`vacate`)."""
    out: set[str] = set()
    for r in raws:
        ids = {iso[p.pid].id if p.pid in iso else None for p in r[0]}
        if None in ids and len(ids) > 1:
            out |= {i for i in ids if i}
    if out and counts is not None:
        _refuse(counts, "welded", len(out))
        counts["isolated_shares"] = counts.get("isolated_shares", 0) - len(out)
    return frozenset(out)


def vacate(record: _t.Any, st: _t.Any, u: _t.Any, iso_raws: "dict | None",
           grp_of: _t.Mapping[int, _t.Sequence[int]],
           carrier_of: _t.Mapping[int, tuple], *, step_m: float, reach_m: float,
           counts: dict, by_class: dict) -> "tuple[_t.Any, bool]":
    """A1 §3.4 (3): ``(record, vacated?)`` — one member's record, every
    anchor already elected, with its isolated shares swapped in.

    Every today raw of ``st`` all of whose parts are isolated (each part a
    share's: a key of ``iso_raws``, ``share id -> placement_body.
    isolated_raws`` raw) is dropped from its body.  A body left with no
    part raw vanishes and its orphan raws (no parts: §16d (1)'s loose
    components) go to the LEAD share of its senior raw (:func:`_lead`); an
    orphan-only body CARRIED on a vanished body of this member goes with
    that body.  A body that keeps a part raw is re-formed
    over what is left — parts, components, feet, boxes — on its FROZEN
    anchor, name and seat.  The share's body is its isolated raw (the parts
    a dropped raw held) and the orphans handed to it, one body per share;
    a member's shares join one file where their zeros agree within half the
    motion step and they lie within ``reach_m`` (§3.3).  ``grp_of`` is
    ``body id -> raw indices`` and ``carrier_of`` ``body id -> (member,
    group)`` for a carried body, both as pass 4 formed the record."""
    if not iso_raws:
        return record, False
    from . import placement_carrier as _pc
    raw = st.raw
    share_of_pid = {p.pid: sid for sid, r in iso_raws.items() for p in r[0]}

    drop = {i for i in range(len(raw))
            if raw[i][0] and all(p.pid in share_of_pid for p in raw[i][0])}
    if not drop:
        return record, False
    hand: dict[str, list[int]] = {}
    gone: dict[int, str] = {}         # vanished body id -> its share
    rest: dict[int, list[int]] = {}   # re-formed body id -> raws kept
    for b in record.bodies:
        g = list(grp_of.get(b.body_id, ()))
        prt = [i for i in g if raw[i][0]]
        if not any(i in drop for i in prt):
            continue
        kept = [i for i in g if i not in drop]
        if any(raw[i][0] for i in kept):
            rest[b.body_id] = kept
        else:
            gone[b.body_id] = _lead(raw[_pc.senior_of(raw, prt)][0], share_of_pid)
            hand.setdefault(gone[b.body_id], []).extend(kept)
    for b in record.bodies:           # an orphan-only body rides its carrier
        g = grp_of.get(b.body_id, ())
        c = carrier_of.get(b.body_id)
        if (g and b.body_id not in gone and not any(raw[i][0] for i in g)
                and c is not None and c[0] == st.mi and c[1] in gone):
            gone[b.body_id] = gone[c[1]]
            hand.setdefault(gone[c[1]], []).extend(g)
    dropped = {p.pid for i in drop for p in raw[i][0]}
    bodies = [_reformed(b, st, u, rest[b.body_id]) if b.body_id in rest else b
              for b in record.bodies if b.body_id not in gone]
    news = _share_bodies(st, u, iso_raws, dropped, hand, step_m, reach_m,
                         1 + max((b.body_id for b in record.bodies), default=-1),
                         counts, by_class)
    counts["isolated_raws_vacated"] = counts.get("isolated_raws_vacated", 0) + len(drop)
    counts["isolated_bodies_vacated"] = counts.get("isolated_bodies_vacated", 0) + len(gone)
    counts["isolated_bodies_reformed"] = counts.get("isolated_bodies_reformed", 0) + len(rest)
    counts["isolated_bodies"] = counts.get("isolated_bodies", 0) + len(news)
    return _dc.replace(record, bodies=tuple(bodies) + tuple(news)), True


def _lead(parts: _t.Sequence[_t.Any], share_of_pid: _t.Mapping[int, str]) -> str:
    """The share holding most of ``parts``' feet (ties to the lowest id) —
    where the orphans of a vanished body go."""
    n: dict[str, int] = {}
    for p in parts:
        q = share_of_pid[p.pid]
        n[q] = n.get(q, 0) + len(p.feet)
    return min(n, key=lambda q: (-n[q], q))


def _reformed(b: _t.Any, st: _t.Any, u: _t.Any, kept: list[int]) -> _t.Any:
    """``b`` over the raws ``kept`` — what it holds and covers re-read
    (``placement_file._group_bodies``' own derivation), its anchor, name,
    seat and carrier frozen."""
    from .placement_file import _group_bodies
    f = _group_bodies(st.raw, [kept], st.m, u, {}, {}, st.part_boxes, (),
                      st.bridge, st.geom_boxes)[0]
    return _dc.replace(b, components=f.components, pids=f.pids,
                       cut_components=f.cut_components, tris=f.tris,
                       feet=f.feet if b.feet else (), plan_box=f.plan_box,
                       geom_box=f.geom_box, foot_boxes=f.foot_boxes,
                       fill=f.fill, geom_pts=f.geom_pts,
                       elevated_members=f.elevated_members,
                       bridge_of=f.bridge_of)


def _share_bodies(st: _t.Any, u: _t.Any, iso_raws: dict, dropped: set,
                  hand: dict, step_m: float, reach_m: float, first_id: int,
                  counts: dict, by_class: dict) -> list:
    """The member's share bodies (:func:`vacate`), numbered from
    ``first_id``: each share's raw over the parts a dropped raw held, the
    shares joined at half ``step_m`` within ``reach_m`` (§3.3), each group
    with the orphans handed to its shares."""
    from . import obj8_split as _split
    from . import placement_carrier as _pc
    from .placement_file import _group_bodies
    sids = [q for q in sorted(iso_raws)
            if any(p.pid in dropped for p in iso_raws[q][0])]
    if not sids:
        return []
    raws = []
    for q in sids:
        r = iso_raws[q]
        parts = [p for p in r[0] if p.pid in dropped]
        raws.append((parts, r[1], r[2], tuple(f for p in parts for f in p.feet))
                    + tuple(r[4:]))
    boxes = [_pc.box_of(r[3], r[0]) for r in raws]
    keys = [(k, r[2], len(r[3])) for k, r in enumerate(raws)]
    groups = _pc.coarsen(keys, 0.5 * step_m, frozenset(), boxes,
                         attach_elevated=False, reach_m=reach_m)
    n0 = len(st.raw)
    ext = list(st.raw) + raws
    # the per-raw lists a later append (an orphan, a carrier piece) may have
    # left short are padded, so the share raws read their own entries
    pboxes = (list(st.part_boxes) + [[]] * (n0 - len(st.part_boxes))
              + [[p.box for p in r[0]] for r in raws])
    gboxes = list(st.geom_boxes) + [None] * (n0 - len(st.geom_boxes) + len(raws))
    bridge = list(st.bridge) + [""] * (n0 - len(st.bridge) + len(raws))
    grps = [[n0 + k for k in g] + [i for k in g for i in hand.get(sids[k], ())]
            for g in groups]
    out = []
    for j, b in enumerate(_group_bodies(ext, grps, st.m, u, counts, by_class,
                                        pboxes, (), bridge, gboxes)):
        bid = first_id + j
        out.append(_dc.replace(b, body_id=bid, new_resource=_split.body_resource_name(
            st.m.resource, bid, b.anchor.offset)))
    return out
