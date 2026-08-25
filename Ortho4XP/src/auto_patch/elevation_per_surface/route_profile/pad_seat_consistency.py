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

Gate: ``O4_PAD_SEAT_CONSISTENCY`` (default ON; "0" disables capture AND
narrowing, byte-identical to the pre-spec build).
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


def pad_seat_consistency_enabled() -> bool:
    """THE reader for :data:`ENV_FLAG` (default ON; ``"0"`` disables)."""
    return os.environ.get(ENV_FLAG, "1") != "0"


def record_budget_m(rec: Mapping[str, Any]) -> Optional[float]:
    """The consistency half-width for one frontage band record.

    ``route_m`` is the band's own cap-weighted route cost to the governing
    attachment (elevation metres, see the module docstring);
    ``off_mask_m`` is the off-pavement leg the band prices at
    ``APRON_MAX_GRADE``.  ``None`` when the record carries no provenance.
    """
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
                               stamped=(), yield_idx=()) -> Dict[str, Any]:
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

    Returns the report dict (also published on ``layout``).
    """
    report: Dict[str, Any] = {
        "on": True, "units": 0, "narrowed": 0, "moved": 0, "empty": 0,
        "no_provenance": 0, "no_anchor": 0, "skipped_anchors": 0,
        "yield_units": 0, "worst_move_m": 0.0, "worst_residual_m": 0.0,
        "inconsistent": 0, "worst_inversion_m": 0.0,
        "moves": [], "empties": [], "inconsistents": [],
    }
    prov = getattr(layout, "_pad_seat_consistency_units", None) or []
    report["units"] = len(prov)
    if not prov:
        return report
    from auto_patch.elevation_per_surface.node_space import store_of
    try:
        boxes = store_of(layout).raw("seat_boxes")
    except Exception:                                      # pragma: no cover
        boxes = None
    stamped = set(stamped)
    yield_idx = set(yield_idx)

    for u in prov:
        recs = u.get("records") or []
        if not recs:
            report["no_provenance"] += 1
            continue
        clo, chi, used, binding = consistency_interval(recs, elev, n)
        report["skipped_anchors"] += int(binding.get("skipped_anchors") or 0)
        if not used or clo is None or chi is None:
            report["no_anchor"] += 1
            continue
        level = float(u["level"])
        if clo > chi:
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
        # The stored box is the interval the seat was chosen from, WIDENED
        # to include the seat (``build_building_seats``' own construction).
        box_lo = min(float(u["lo"]), level)
        box_hi = max(float(u["hi"]), level)
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
    lines: List[str] = [
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
