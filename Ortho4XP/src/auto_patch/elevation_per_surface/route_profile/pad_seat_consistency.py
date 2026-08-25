"""PAD-SEAT CONSISTENCY INTERVAL — the seat defers to the SOLVED corridor.

Spec: ``docs/specs/pad-seat-consistency-spec.md`` (+ its "Implementation
ruling (Fable lead, 2026-08-25)").  Owner direction: *"pads seated at the
elevation that enables the 1 % cap"*; creation-order seniority (RULINGS
2026-08-21e) — the corridor profile is created first, so the pad seat
defers to it.

THE MEASURED GAP.  ``build_building_seats`` seats a pad anywhere inside a
FEASIBILITY interval 7-34 m wide (the reach band); the chord law then
judges the pad's frontage against the SOLVED corridor with a budget of
0.13-1.06 m.  The seat is chosen from an interval up to ~75x wider than
the constraint applied afterwards, with no reference to where the corridor
actually solved (findings ``docs/findings/apron-membrane-findings-
20260824.md`` §3-4).

THE LAW.  The pad's seating interval becomes

    band ∩ ⋂ᵢ [ corridor_value(anchorᵢ) ± budgetᵢ ]

over the pad's own FRONTAGE band records — the ones
``anchors._frontage_band_records`` captured from ``band.attachment_at`` at
seat time (never a replay).  The band still guarantees feasibility, the
corridor term guarantees consistency, and the band-chosen DEM-biased seat
stays the authority: only the interval narrows and the seat CLAMPS into it
(the v4 lesson — a scaffold-derived seat source was catastrophic, 22/22
CYXY pads down mean 9.07 m).

── THE BUDGET IS ALREADY CAP-WEIGHTED (measured, 2026-08-25) ───────────
The spec writes the consistency half-width as ``cap × route_distance``.
The band's own ``attachment_at`` quantity ``leg_m`` — exported as
``route_m`` — is NOT a raw distance: ``raster_reach_band._grid_edges``
weights every grid edge ``0.5·(cap_s + cap_d) · step``, so ``leg`` is the
Dijkstra cost in ELEVATION METRES already (``ceiling = sc[cid] + leg``).
Verified on the v5 HECA sidecar: ``ceiling − ceiling_at_anchor ==
route_m`` exactly on all 351 on-mask records.  Multiplying by ``cap``
again would collapse every interval to ~3 cm and reproduce the REFUTED v4
mechanism (seat := corridor value).  So the half-width used here is

    budget = route_m + APRON_MAX_GRADE × off_mask_m

which is ``cap × route_distance`` expressed in the band's own metric, with
the second term the band's own off-mask slack (``raster_reach_band.band``:
``slack = apron_cap * off``).  ``APRON_MAX_GRADE`` is the config constant —
never a literal.

Gate: ``O4_PAD_SEAT_CONSISTENCY`` (default **OFF** since the 2026-08-25
acceptance miss — HECA censused 2,249 against a ≤1,487 bar; lead ruling).
The mechanism, the provenance capture, the sidecar keys and the report are
all intact behind the flag: ``O4_PAD_SEAT_CONSISTENCY=1`` enables capture
AND narrowing exactly as authored, and with the flag unset the build is
byte-identical to the pre-spec build.  The default awaits the
chord-origin-population design round.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

_INF = float("inf")

#: Below this the move is not reported as a move (the standing materiality
#: floor for elevation classes, owner 2026-08-02).
MATERIALITY_M = 0.01

ENV_FLAG = "O4_PAD_SEAT_CONSISTENCY"

# ── §2 — DEM IS LAST PRIORITY (owner ruling RULINGS 2026-08-25 second
# ruling; spec ``apron-chord-anchor-target-spec.md`` §2) ─────────────────
# "Where the law leaves a choice of level (a seat interval, an unanchored
# interior), ANCHOR-CONSISTENCY is preferred over DEM proximity; DEM is the
# LAST tiebreaker."
#
# THIS MODULE IS THE CHASSIS, RE-AIMED.  The interval math, the reporting
# and the post-phase-A / pre-scaffold-seed slot are the ones authored for
# the pad-seat-consistency round; what changes is the SOURCE of the
# interval.  The refuted version narrowed against the pad's FRONTAGE
# attachment records — a much narrower population than the chords the
# census prices, which is why moving seats against it regressed HECA
# 1,964 -> 2,249.  §1 replaced the population: an apron ring vertex now
# chords to its NEAREST VISIBLE ANCHOR (pad or centerline).  §2 aims the
# seat at THAT neighbourhood, read from the ONE enumeration through
# ``UnifiedGraph.anchor_chords`` — never re-derived here.
#
# The two gates are SEPARATE and mean different things (spec §2.2): the
# frontage-subset version stays OFF under its own flag and is not
# re-enabled by this one.
ENV_FLAG_DEM_LAST = "O4_DEM_LAST_SEAT_BIAS"


def dem_last_seat_bias_enabled() -> bool:
    """THE reader for :data:`ENV_FLAG_DEM_LAST` (default **ON** in-lane —
    the owner ordered §2 forward after the §1 acceptance read).

    ``O4_DEM_LAST_SEAT_BIAS=0`` ⇒ the build is byte-identical to §1-only:
    no neighbourhood is captured, no seat moves, and the DEM-biased band
    seat stays exactly where ``build_building_seats`` put it.
    """
    return os.environ.get(ENV_FLAG_DEM_LAST, "1") != "0"


def seat_provenance_wanted() -> bool:
    """Whether the per-unit seat provenance must be CAPTURED at seat time.

    ONE reader for both mechanisms: the frontage-subset version (its own
    flag, default OFF) and the §2 DEM-last bias both consume the unit's
    node set and its band box, and the capture is the only place either
    can get them.  With both gates off nothing is captured and the build
    is byte-identical to the pre-spec one.
    """
    return pad_seat_consistency_enabled() or dem_last_seat_bias_enabled()


def pad_seat_consistency_enabled() -> bool:
    """THE reader for :data:`ENV_FLAG` (default **OFF**; ``"1"`` enables).

    Flipped to OFF by the 2026-08-25 lead ruling after the acceptance miss;
    only an explicit ``O4_PAD_SEAT_CONSISTENCY=1`` turns the mechanism on.
    The truthiness convention is unchanged (``"0"`` is the only OFF value);
    the DEFAULT moved from ``"1"`` to ``"0"``.
    """
    return os.environ.get(ENV_FLAG, "0") != "0"


def record_budget_m(rec: Mapping[str, Any]) -> Optional[float]:
    """The consistency half-width for one record.

    TWO RECORD SHAPES, ONE INTERVAL MATH (the point of re-aiming a chassis
    rather than forking one):

      * a §1 ANCHOR-NEIGHBOURHOOD record carries ``budget_m`` outright —
        the chord's own ``cap x dist``, computed where the chord was
        MINTED (``UnifiedGraph.anchor_chords``).  It is read first because
        it is the law's own budget for that very chord;
      * a FRONTAGE BAND record carries ``route_m`` — the band's own
        cap-weighted route cost to the governing attachment (elevation
        metres, see the module docstring) — plus ``off_mask_m``, the
        off-pavement leg the band prices at ``APRON_MAX_GRADE``.

    ``None`` when the record carries neither.
    """
    if "budget_m" in rec:
        try:
            b = float(rec["budget_m"])
        except (TypeError, ValueError):                     # pragma: no cover
            return None
        return b if math.isfinite(b) and b >= 0.0 else None
    if "route_m" not in rec:
        return None
    from auto_patch.config import APRON_MAX_GRADE
    try:
        route = float(rec["route_m"])
        off = float(rec.get("off_mask_m") or 0.0)
    except (TypeError, ValueError):                        # pragma: no cover
        return None
    b = route + float(APRON_MAX_GRADE) * off
    return b if math.isfinite(b) and b >= 0.0 else None


def consistency_interval(
        records: Iterable[Mapping[str, Any]],
        elev: Sequence[float],
        n: int) -> Tuple[Optional[float], Optional[float], int, Dict[str, Any]]:
    """``(lo, hi, n_anchors_used, binding)`` — ⋂ over the unit's records of
    ``[elev[anchor] ± budget]``, ``elev`` read AFTER phase A.

    A record may name SEVERAL attachment nodes (coincident attachments in
    one band cell); the band itself takes the tightest interval those
    justify (``min`` ceiling / ``max`` floor), so every named anchor
    contributes its own constraint here too.

    Anchors outside ``[0, n)`` are skipped and counted in ``binding``:
    a band built on a different node list would be a second index space,
    and inventing a mapping is exactly what the canonical-identity law
    forbids.  ``(None, None, 0, …)`` ⇒ nothing to narrow with.
    """
    lo, hi = -_INF, _INF
    used = 0
    skipped = 0
    binding: Dict[str, Any] = {"floor_anchor": None, "floor_route_m": None,
                               "floor_value": None,
                               "ceil_anchor": None, "ceil_route_m": None,
                               "ceil_value": None, "skipped_anchors": 0}
    for rec in records:
        budget = record_budget_m(rec)
        if budget is None:
            continue
        for a in (rec.get("anchor_nodes") or ()):
            try:
                ai = int(a)
            except (TypeError, ValueError):                # pragma: no cover
                continue
            if not (0 <= ai < n) or ai >= len(elev):
                skipped += 1
                continue
            v = float(elev[ai])
            if not math.isfinite(v):                       # pragma: no cover
                skipped += 1
                continue
            used += 1
            if v - budget > lo:
                lo = v - budget
                binding["floor_anchor"] = ai
                binding["floor_route_m"] = budget
                binding["floor_value"] = v
            if v + budget < hi:
                hi = v + budget
                binding["ceil_anchor"] = ai
                binding["ceil_route_m"] = budget
                binding["ceil_value"] = v
    binding["skipped_anchors"] = skipped
    if not used:
        return None, None, 0, binding
    return lo, hi, used, binding


def anchor_neighborhood_records(unit_nodes: Iterable[int],
                                anchor_chords: Iterable[Sequence[Any]],
                                solved_nodes: Optional[set] = None
                                ) -> List[Dict[str, Any]]:
    """The pad unit's §1 ANCHOR NEIGHBOURHOOD, as consistency records.

    "The pads/centerlines its ring vertices now chord to under the
    nearest-anchor enumeration" (spec §2.1): every published anchor chord
    with ONE endpoint among this unit's own nodes contributes a record
    naming the OTHER endpoint as the anchor and the chord's own
    ``cap x dist`` as the budget.

    A chord with BOTH ends inside the unit is dropped: a pad is one flat
    level, so such a chord is satisfied at zero residual by construction
    and carries no information about where that level should be.

    ``solved_nodes`` — THE ANCHORS THAT CARRY A SOLVED VALUE AT THIS SLOT
    (arm-2 correction, measured; see below).  An anchor outside it is
    dropped and counted, exactly as an out-of-range anchor already is.

    WHY THE FILTER, AND WHY IT IS NOT A NEW POPULATION.  This slot runs
    after ``_solve_spine_profile`` and BEFORE the body fill, so ``elev``
    holds a solved value only at the phase-A set (the corridor) and at the
    seat nodes phase A stamped hard.  Everywhere else it still holds the
    DEM SEED.  A "residual" measured against a seeded node is therefore a
    residual against DEM — which is the exact quantity this ruling demotes
    to last, so counting it would make the mechanism pull the way the
    ruling forbids.  The module's own contract already says this in words
    ("``elev`` — read AFTER ``_solve_spine_profile`` (the SOLVED
    corridor)"); the filter is that contract enforced instead of assumed.

    Measured (HECA, arm 1, without the filter): 44 units, 37 of them with
    CONTRADICTORY anchors, worst residual left 196.6 m and seats moving up
    to 7.08 m — and the census read 1,949 airside against §1's 1,735.  The
    contradictions were between solved corridor values and un-solved seeds
    sitting metres away.

    The records are the shape :func:`consistency_interval` already
    consumes — no second interval math, and no re-derivation of the
    neighbourhood (the chords come from the ONE enumeration, minted in the
    solve's own node space).
    """
    nodes = {int(i) for i in unit_nodes}
    out: List[Dict[str, Any]] = []
    if not nodes:
        return out
    for ch in anchor_chords or ():
        try:
            a, b, budget = int(ch[0]), int(ch[1]), float(ch[2])
        except (TypeError, ValueError, IndexError):        # pragma: no cover
            continue
        kind = str(ch[3]) if len(ch) > 3 else ""
        a_in, b_in = a in nodes, b in nodes
        if a_in == b_in:
            continue                       # neither end, or a within-pad chord
        anchor = b if a_in else a
        if solved_nodes is not None and anchor not in solved_nodes:
            out.append({"anchor_nodes": [], "budget_m": budget,
                        "kind": kind, "unsolved": True})
            continue
        out.append({"anchor_nodes": [anchor],
                    "budget_m": budget, "kind": kind})
    return out


def chord_residual_m(level: float, records: Iterable[Mapping[str, Any]],
                     elev: Sequence[float], n: int) -> float:
    """Σ over the neighbourhood of ``max(0, |level - anchor| - budget)``.

    THE QUANTITY §2 MINIMISES.  Each term is exactly the excess the census
    would price on that chord if the pad sat at ``level`` — zero while the
    chord is lawful, then growing metre for metre.  The sum is convex and
    piecewise linear in ``level``, which is what makes
    :func:`dem_last_seat_level` exact rather than a search.
    """
    total = 0.0
    for rec in records or ():
        budget = record_budget_m(rec)
        if budget is None:
            continue
        for a in (rec.get("anchor_nodes") or ()):
            try:
                ai = int(a)
            except (TypeError, ValueError):                # pragma: no cover
                continue
            if not (0 <= ai < n) or ai >= len(elev):
                continue
            v = float(elev[ai])
            if not math.isfinite(v):                       # pragma: no cover
                continue
            total += max(0.0, abs(float(level) - v) - budget)
    return total


def dem_last_seat_level(seat_m: float, box_lo: float, box_hi: float,
                        records: Iterable[Mapping[str, Any]],
                        elev: Sequence[float], n: int
                        ) -> Tuple[float, float, int]:
    """``(level, residual_m, candidates)`` — the level inside the pad's own
    band box that MINIMISES :func:`chord_residual_m`, with the DEM-biased
    seat as the LAST tiebreaker (owner ruling RULINGS 2026-08-25 §2.1).

    THE BAND REMAINS THE FEASIBILITY AUTHORITY.  The search is confined to
    ``[box_lo, box_hi]`` — the interval ``build_building_seats`` chose the
    seat from, widened to hold it — so the §2 seat can never leave the
    pad's lawful band.  That is the v4 lesson made structural: the refuted
    mechanism took its level from a scaffold instead of from the band and
    put 22 of 22 CYXY pads down a mean 9.07 m.

    EXACTNESS.  The residual is convex and piecewise linear with
    breakpoints at ``anchor ± budget``, so its minimum over an interval is
    attained at a breakpoint or at an interval end.  Evaluating those
    candidates is therefore the answer, not an approximation of it.

    THE TIEBREAK IS THE RULING.  Among levels of equal residual — which is
    the whole intersection whenever the neighbourhood is consistent — the
    one NEAREST THE CURRENT SEAT wins, and that seat is the band's
    DEM-biased choice.  So anchor-consistency decides first and DEM decides
    last, which is the ruling in one comparison.  A further tie (the seat
    exactly between two candidates) breaks on the LOWER level so two
    readers cannot disagree.
    """
    lo, hi = float(box_lo), float(box_hi)
    if hi < lo:
        lo, hi = hi, lo
    seat = min(max(float(seat_m), lo), hi)
    cands = {lo, hi, seat}
    for rec in records or ():
        budget = record_budget_m(rec)
        if budget is None:
            continue
        for a in (rec.get("anchor_nodes") or ()):
            try:
                ai = int(a)
            except (TypeError, ValueError):                # pragma: no cover
                continue
            if not (0 <= ai < n) or ai >= len(elev):
                continue
            v = float(elev[ai])
            if not math.isfinite(v):                       # pragma: no cover
                continue
            for edge in (v - budget, v + budget):
                if lo <= edge <= hi:
                    cands.add(float(edge))
    best = seat
    best_r = chord_residual_m(seat, records, elev, n)
    for c in sorted(cands):
        r = chord_residual_m(c, records, elev, n)
        if (r < best_r - 1e-9
                or (abs(r - best_r) <= 1e-9
                    and (abs(c - seat) < abs(best - seat) - 1e-12
                         or (abs(abs(c - seat) - abs(best - seat)) <= 1e-12
                             and c < best)))):
            best, best_r = float(c), r
    return best, best_r, len(cands)


def narrow_seat(seat_m: float, box_lo: float, box_hi: float,
                cons_lo: float, cons_hi: float
                ) -> Tuple[float, float, float, bool, float]:
    """``(level, lo, hi, empty, residual_m)``.

    Non-empty intersection: the narrowed interval is
    ``[max(box_lo, cons_lo), min(box_hi, cons_hi)]`` and the CURRENT seat
    clamps into it — the band-chosen, DEM-biased seat stays the authority
    (spec ruling §3).

    EMPTY intersection (seat box ∩ consistency = ∅): never a silent pick
    (spec ruling §5).  The corridor is SENIOR (creation-order seniority),
    so the seat descends at cap from the corridor side — it lands on the
    consistency-interval edge nearest the seat box — and the residual (the
    distance the feasibility box was given up by) is reported.
    """
    lo = max(float(box_lo), float(cons_lo))
    hi = min(float(box_hi), float(cons_hi))
    if lo <= hi:
        return (min(max(float(seat_m), lo), hi), lo, hi, False, 0.0)
    if float(cons_hi) < float(box_lo):
        return (float(cons_hi), float(cons_lo), float(cons_hi), True,
                float(box_lo) - float(cons_hi))
    return (float(cons_lo), float(cons_lo), float(cons_hi), True,
            float(cons_lo) - float(box_hi))


def _narrow_box(store_boxes: Dict[Any, Any], key: Any,
                lo: float, hi: float, level: float) -> None:
    """Narrow ONE ``seat_boxes`` interval to the narrowed seat interval.

    Same idiom as ``build_building_seats``: the stored box is widened to
    include the level it holds (the clamp refines the yield, it is never a
    new hold), and a key shared by two pads keeps the tighter interval per
    side.  A narrowing that would invert the stored box re-widens to the
    level so no consumer is handed an empty interval.
    """
    blo = min(float(lo), float(level))
    bhi = max(float(hi), float(level))
    prev = store_boxes.get(key)
    if prev is None:
        store_boxes[key] = (blo, bhi)
        return
    nlo, nhi = max(float(prev[0]), blo), min(float(prev[1]), bhi)
    if nlo > nhi:
        nlo, nhi = min(nlo, float(level)), max(nhi, float(level))
    store_boxes[key] = (nlo, nhi)


def apply_pad_seat_consistency(layout, elev, building_seats, n, *,
                               stamped=(), yield_idx=(),
                               anchor_chords=None,
                               solved_nodes=None) -> Dict[str, Any]:
    """Bind the consistency interval in the post-phase-A / pre-phase-B slot.

    ``elev`` — the solve's elevation array, read AFTER ``_solve_spine_profile``
    (the SOLVED corridor) and written at the unit's stamped seat nodes.
    ``building_seats`` — the ``{node: level}`` map phase B and the scaffold
    seed consume; every seat node of a narrowed unit takes the SAME clamped
    level (a pad is one flat level — never per node).
    ``stamped`` — the node set whose ``elev`` currently HOLDS the seat (the
    hard-stamp loop's own condition); other seat nodes keep the value the
    seeder gave them, exactly as today.
    ``yield_idx`` — ``layout._seat_stamp_yield_idx``: seats the hard-stamp
    guard refused.  They are NOT ``base_hard`` and enter the projections
    free, so narrowing their STARTING value is consistent — they are
    counted separately in the report.
    ``anchor_chords`` — ``UnifiedGraph.anchor_chords``, THE §1 enumeration's
    own output.  Present ⇒ the DEM-LAST SEAT BIAS runs (spec §2): the
    unit's interval source is its §1 anchor neighbourhood and the level is
    the residual-minimising one inside the band box, DEM last.  ``None`` ⇒
    the frontage-subset narrowing of the earlier round, unchanged and still
    behind its own (default-OFF) flag.

    Returns the report dict (also published on ``layout``).
    """
    report: Dict[str, Any] = {
        "on": True, "units": 0, "narrowed": 0, "moved": 0, "empty": 0,
        "no_provenance": 0, "no_anchor": 0, "skipped_anchors": 0,
        "yield_units": 0, "worst_move_m": 0.0, "worst_residual_m": 0.0,
        "inconsistent": 0, "worst_inversion_m": 0.0,
        "moves": [], "empties": [], "inconsistents": [],
        "dem_last": anchor_chords is not None, "anchor_chords": 0,
        "worst_residual_left_m": 0.0, "residual_cut_m": 0.0,
        "unsolved_anchors": 0,
    }
    prov = getattr(layout, "_pad_seat_consistency_units", None) or []
    report["units"] = len(prov)
    if not prov:
        return report
    dem_last = anchor_chords is not None
    if dem_last:
        anchor_chords = list(anchor_chords)
        report["anchor_chords"] = len(anchor_chords)
    from auto_patch.elevation_per_surface.node_space import store_of
    try:
        boxes = store_of(layout).raw("seat_boxes")
    except Exception:                                      # pragma: no cover
        boxes = None
    stamped = set(stamped)
    yield_idx = set(yield_idx)

    for u in prov:
        if dem_last:
            # ── §2: THE INTERVAL SOURCE IS THE §1 NEIGHBOURHOOD ────────
            # Re-aimed, not re-derived: the chords come from the ONE
            # enumeration that also prices the census's rows, so the level
            # this pad seats at is chosen against exactly the chords it
            # will be judged on.  The frontage-attachment records the
            # earlier round narrowed against are NOT consulted (spec §2.3
            # — that version stays off under its own flag).
            recs = anchor_neighborhood_records(u.get("nodes") or (),
                                               anchor_chords, solved_nodes)
            _uns = sum(1 for r in recs if r.get("unsolved"))
            report["unsolved_anchors"] += _uns
            recs = [r for r in recs if not r.get("unsolved")]
        else:
            recs = u.get("records") or []
        if not recs:
            # AN UNANCHORED PAD KEEPS ITS DEM SOFT-SEED (spec §2.1's own
            # clause).  No anchor reaches it, so there is no consistency
            # to prefer and the band's DEM-biased seat is still the best
            # available authority — byte-identically where it was.
            report["no_provenance"] += 1
            continue
        clo, chi, used, binding = consistency_interval(recs, elev, n)
        report["skipped_anchors"] += int(binding.get("skipped_anchors") or 0)
        if not used or clo is None or chi is None:
            report["no_anchor"] += 1
            continue
        level = float(u["level"])
        # The stored box is the interval the seat was chosen from, WIDENED
        # to include the seat (``build_building_seats``' own construction).
        box_lo = min(float(u["lo"]), level)
        box_hi = max(float(u["hi"]), level)
        if dem_last:
            # ── §2: ANCHOR-CONSISTENCY FIRST, DEM LAST ────────────────
            # The level is the one INSIDE THE BAND BOX that minimises the
            # chord residual against this pad's §1 neighbourhood; among
            # equal-residual levels the DEM-biased band seat wins, which
            # is the ruling's "DEM is the LAST tiebreaker" in one
            # comparison.  The box is never left, so the band stays the
            # feasibility authority (the v4 lesson).
            #
            # AN INVERTED CONSISTENCY INTERVAL IS NOT A DEAD END HERE.
            # The frontage-subset version had to KEEP the seat when a
            # pad's own anchors contradicted each other, because its
            # interval math had no way to choose between them without a
            # silent pick.  A residual MINIMUM is not a pick: it is the
            # level that prices least against ALL of them, it is
            # well-defined when no zero-residual level exists, and it is
            # reported with the residual it could not remove.
            resid_was = chord_residual_m(level, recs, elev, n)
            new, resid_left, _ncand = dem_last_seat_level(
                level, box_lo, box_hi, recs, elev, n)
            nlo, nhi = max(box_lo, float(clo)), min(box_hi, float(chi))
            if nlo > nhi:
                # No level satisfies every anchor: the box is not narrowed
                # (there is nothing lawful to narrow it TO), only the seat
                # inside it moves.
                nlo, nhi = box_lo, box_hi
            empty, resid = False, 0.0
            report["worst_residual_left_m"] = max(
                report["worst_residual_left_m"], resid_left)
            report["residual_cut_m"] += max(0.0, resid_was - resid_left)
            if clo > chi:
                inv = float(clo) - float(chi)
                report["inconsistent"] += 1
                report["worst_inversion_m"] = max(report["worst_inversion_m"],
                                                  inv)
                report["inconsistents"].append({
                    "ref": u.get("ref", "?"), "seat_m": level,
                    "seat_now_m": float(new), "dem_last": True,
                    "consist_floor_m": float(clo),
                    "consist_ceiling_m": float(chi),
                    "inversion_m": inv,
                    "floor_anchor": binding.get("floor_anchor"),
                    "floor_value_m": binding.get("floor_value"),
                    "floor_route_m": binding.get("floor_route_m"),
                    "ceil_anchor": binding.get("ceil_anchor"),
                    "ceil_value_m": binding.get("ceil_value"),
                    "ceil_route_m": binding.get("ceil_route_m"),
                    "residual_left_m": float(resid_left),
                    "records": len(recs),
                })
        elif clo > chi:
            # THE CONSISTENCY INTERSECTION IS ITSELF EMPTY — the pad's own
            # frontage records name corridor anchors whose SOLVED values
            # differ by more than the sum of their route budgets, so NO
            # flat level is consistent with all of them.  That is not the
            # spec's "seat box ∩ consistency = ∅" case (ruling §5, which
            # presumes a consistency interval to descend onto): there is no
            # corridor side to descend from, and picking one of the two
            # contradictory anchors would be exactly the silent pick the
            # ruling forbids.  So the seat is KEPT and the contradiction
            # named — the same disposition ``build_building_seats`` gives
            # its own empty frontage∩node-band intersection (the
            # split-level-seat trigger, RULINGS 2026-08-04).
            #
            # Measured when this class was found (2026-08-25, arm 1): HECA
            # 1 unit (0.30 m inverted), SPJC 2 units (up to 2.16 m) — where
            # the unguarded code moved the seat onto the inverted FLOOR and
            # reported a negative "residual".
            inv = clo - chi
            report["inconsistent"] += 1
            report["worst_inversion_m"] = max(report["worst_inversion_m"], inv)
            report["inconsistents"].append({
                "ref": u.get("ref", "?"),
                "seat_m": level,
                "consist_floor_m": float(clo),
                "consist_ceiling_m": float(chi),
                "inversion_m": float(inv),
                "floor_anchor": binding.get("floor_anchor"),
                "floor_value_m": binding.get("floor_value"),
                "floor_route_m": binding.get("floor_route_m"),
                "ceil_anchor": binding.get("ceil_anchor"),
                "ceil_value_m": binding.get("ceil_value"),
                "ceil_route_m": binding.get("ceil_route_m"),
                "records": len(recs),
            })
            continue
        else:
            new, nlo, nhi, empty, resid = narrow_seat(level, box_lo, box_hi,
                                                      clo, chi)
        report["narrowed"] += 1
        nodes = [int(i) for i in (u.get("nodes") or ())]
        is_yield = any(i in yield_idx for i in nodes)
        if is_yield:
            report["yield_units"] += 1
        # ONE flat level for the whole unit, at every one of its seat nodes.
        for i in nodes:
            if i < n:
                building_seats[i] = float(new)
                if i in stamped and i < len(elev):
                    elev[i] = float(new)
        if boxes is not None:
            for k in (u.get("keys") or ()):
                _narrow_box(boxes, k, nlo, nhi, new)
        # The unit's own record of what it now is (consumed by the sidecar
        # export below and by tooling).
        u["consist_floor"] = float(clo)
        u["consist_ceiling"] = float(chi)
        u["narrowed_lo"] = float(nlo)
        u["narrowed_hi"] = float(nhi)
        u["seat_final_m"] = float(new)
        # THE SIDECAR EXPORT (spec twin (e)): the narrowed interval and the
        # final seat beside the raw band interval, on the very record
        # objects ``layout._frontage_band_ll`` holds.
        # ``seat_m`` on the record is the PRE-COUPLING pad target (it is
        # stamped inside the pad loop, before the rigid-unit merge and the
        # POCS coupling); ``seat_unit_m`` is the unit level this narrowing
        # actually started from, so the two effects stay separable.
        for rec in recs:
            rec["consist_floor"] = float(clo)
            rec["consist_ceiling"] = float(chi)
            rec["seat_unit_m"] = level
            rec["seat_final_m"] = float(new)
        row = {
            "ref": u.get("ref", "?"),
            "refs": list(u.get("refs") or ()),
            "seat_was_m": level,
            "seat_now_m": float(new),
            "move_m": float(new) - level,
            "consist_floor_m": float(clo),
            "consist_ceiling_m": float(chi),
            "narrowed_lo_m": float(nlo),
            "narrowed_hi_m": float(nhi),
            "box_lo_m": box_lo,
            "box_hi_m": box_hi,
            "corridor_anchor": binding.get("ceil_anchor"),
            "corridor_value_m": binding.get("ceil_value"),
            "route_m": binding.get("ceil_route_m"),
            "floor_anchor": binding.get("floor_anchor"),
            "floor_value_m": binding.get("floor_value"),
            "floor_route_m": binding.get("floor_route_m"),
            "anchors_used": int(used),
            "records": len(recs),
            "yield_hard": bool(is_yield),
            "nodes": len(nodes),
        }
        if empty:
            row["residual_m"] = float(resid)
            report["empty"] += 1
            report["empties"].append(row)
            report["worst_residual_m"] = max(report["worst_residual_m"],
                                             abs(float(resid)))
        if abs(float(new) - level) > MATERIALITY_M:
            report["moved"] += 1
            report["moves"].append(row)
            report["worst_move_m"] = max(report["worst_move_m"],
                                         abs(float(new) - level))
    report["moves"].sort(key=lambda r: -abs(r["move_m"]))
    report["empties"].sort(key=lambda r: -abs(r.get("residual_m", 0.0)))
    report["inconsistents"].sort(key=lambda r: -r["inversion_m"])
    setattr(layout, "_pad_seat_consistency_moves", report["moves"])
    setattr(layout, "_pad_seat_consistency_empty", report["empties"])
    setattr(layout, "_pad_seat_consistency_inconsistent",
            report["inconsistents"])
    setattr(layout, "_pad_seat_consistency_report",
            {k: v for k, v in report.items()
             if k not in ("moves", "empties")})
    return report


def format_report(icao: str, report: Mapping[str, Any],
                  limit: int = 20) -> str:
    """The seat-move TABLE (one line per moved pad) + the one-line summary."""
    tag = "dem-last-seat" if report.get("dem_last") else "pad-seat-consistency"
    if report.get("dem_last"):
        lines: List[str] = [
            f"  [{tag}] {icao}: {report['narrowed']} of {report['units']} pad "
            f"unit(s) aimed at their §1 anchor neighbourhood "
            f"({report.get('anchor_chords', 0)} anchor chord(s) published); "
            f"{report['moved']} moved (worst "
            f"{report['worst_move_m']:.3f} m), residual removed "
            f"{report.get('residual_cut_m', 0.0):.3f} m total, worst residual "
            f"LEFT {report.get('worst_residual_left_m', 0.0):.3f} m, "
            f"{report.get('inconsistent', 0)} unit(s) with contradictory "
            f"anchors (seated at the residual MINIMUM, worst inversion "
            f"{report.get('worst_inversion_m', 0.0):.3f} m), "
            f"{report['yield_units']} unit(s) yield-hard, "
            f"{report['no_provenance']} unanchored (DEM soft-seed kept), "
            f"{report['no_anchor']} with no usable anchor, "
            f"{report.get('unsolved_anchors', 0)} chord(s) dropped as "
            f"NOT-YET-SOLVED at this slot (their elev is still the DEM "
            f"seed, and a residual against DEM is what this ruling "
            f"demotes to last)."]
        for r in report.get("moves", ())[:limit]:
            lines.append(
                f"  [{tag}]   {r['ref']}: {r['seat_was_m']:.3f} -> "
                f"{r['seat_now_m']:.3f} ({r['move_m']:+.3f} m) against "
                f"{r['anchors_used']} anchor(s); box "
                f"[{r['box_lo_m']:.3f},{r['box_hi_m']:.3f}] -> narrowed "
                f"[{r['narrowed_lo_m']:.3f},{r['narrowed_hi_m']:.3f}]"
                f"{'  YIELD-HARD' if r['yield_hard'] else ''}")
        for r in report.get("inconsistents", ())[:limit]:
            lines.append(
                f"  [{tag}]   CONTRADICTORY {r['ref']}: anchor "
                f"{r['floor_anchor']} demands >= {r['consist_floor_m']:.3f} "
                f"while anchor {r['ceil_anchor']} admits <= "
                f"{r['consist_ceiling_m']:.3f} ({r['inversion_m']:.3f} m "
                f"inverted) — NO level satisfies both, so the seat takes the "
                f"residual MINIMUM inside its band box: "
                f"{r['seat_m']:.3f} -> {r['seat_now_m']:.3f}, residual left "
                f"{r.get('residual_left_m', 0.0):.3f} m")
        return "\n".join(lines)
    lines = [
        f"  [pad-seat-consistency] {icao}: {report['narrowed']} of "
        f"{report['units']} pad unit(s) narrowed to "
        f"band ∩ [corridor ± route budget]; {report['moved']} moved "
        f"(worst {report['worst_move_m']:.3f} m), {report['empty']} EMPTY "
        f"intersection(s) (worst residual "
        f"{report['worst_residual_m']:.3f} m), "
        f"{report['yield_units']} unit(s) yield-hard, "
        f"{report.get('inconsistent', 0)} CORRIDOR-INCONSISTENT "
        f"(seat kept; worst inversion "
        f"{report.get('worst_inversion_m', 0.0):.3f} m), "
        f"{report['no_provenance']} without frontage provenance, "
        f"{report['no_anchor']} with no usable anchor."
    ]
    for r in report.get("moves", ())[:limit]:
        lines.append(
            f"  [pad-seat-consistency]   {r['ref']}: "
            f"{r['seat_was_m']:.3f} -> {r['seat_now_m']:.3f} "
            f"({r['move_m']:+.3f} m) corridor {r['corridor_value_m']:.3f} "
            f"@node {r['corridor_anchor']} budget {r['route_m']:.3f} m; "
            f"box [{r['box_lo_m']:.3f},{r['box_hi_m']:.3f}] -> narrowed "
            f"[{r['narrowed_lo_m']:.3f},{r['narrowed_hi_m']:.3f}]"
            f"{'  YIELD-HARD' if r['yield_hard'] else ''}")
    for r in report.get("empties", ())[:limit]:
        lines.append(
            f"  [pad-seat-consistency]   EMPTY {r['ref']}: seat box "
            f"[{r['box_lo_m']:.3f},{r['box_hi_m']:.3f}] vs consistency "
            f"[{r['consist_floor_m']:.3f},{r['consist_ceiling_m']:.3f}] — "
            f"SEAT DEFECT (spec ruling §5): descended at cap from the "
            f"corridor side to {r['seat_now_m']:.3f}, residual "
            f"{r['residual_m']:.3f} m")
    for r in report.get("inconsistents", ())[:limit]:
        lines.append(
            f"  [pad-seat-consistency]   CORRIDOR-INCONSISTENT {r['ref']}: "
            f"anchor {r['floor_anchor']} at {r['floor_value_m']:.3f} "
            f"(budget {r['floor_route_m']:.3f}) demands >= "
            f"{r['consist_floor_m']:.3f} while anchor {r['ceil_anchor']} at "
            f"{r['ceil_value_m']:.3f} (budget {r['ceil_route_m']:.3f}) "
            f"admits <= {r['consist_ceiling_m']:.3f} — NO flat level is "
            f"consistent with this pad's own frontage ({r['inversion_m']:.3f} "
            f"m inverted).  Seat KEPT at {r['seat_m']:.3f}: there is no "
            f"corridor side to descend from, and picking one anchor would be "
            f"the silent pick the ruling forbids (split-level-seat trigger).")
    return "\n".join(lines)
