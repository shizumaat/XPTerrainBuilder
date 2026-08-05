"""LAW-AWARE EMIT SNAP — the per-pair quantization guard (seed-fix round
§1b + the LEAD AMENDMENT, ``docs/specs/seed-fix-round-spec.md``).

WHY THIS EXISTS.  ``layout.to_osm`` emits every elevation rounded to the
0.01 m grid, so each endpoint moves up to ±0.005 m and a pair's ``|Δz|``
can grow by one full grid step between the solved field and the emitted
file.  A pair solved exactly AT its budget then reads over the law in the
patch.

The historical guarantee was bought in the SOLVER: every edge swept to
``budget − 0.01`` (``one_solve._margined_budget``).  That is correct per
pair and WRONG per path — the reach envelope, the break detection and the
stall adjudication are all path quantities, so the margin compounds
``N × 0.01`` along an N-hop route.  Measured at HEAZ: a 69-hop witness
route loses 0.63 m of envelope, 593 of 2032 nodes read INFEASIBLE that are
lawful, and the phase-A projection burns 3983 sweeps chasing a deficit the
law never imposed.

So the guarantee MOVES here, to emit, where the quantization actually
happens:

  * the correction is per NODE and bounded by ONE grid step — a node is
    only ever snapped to a grid point ADJACENT to its solved value, never
    further — so it CANNOT compound along a path (the property the margin
    lacked);
  * the rounding DIRECTION is chosen per PAIR against that pair's own raw
    cap (the LEAD AMENDMENT).  A naive nearest-grid snap of a pair sitting
    at exactly cap rounds the endpoints apart by a full step and re-mints
    an over-cap census row — the emit side has minted violations before
    (the HECA emit-consensus 1,497-row case), and that debate is not
    reopened here.

THE ALGORITHM.  Each node has exactly two candidate emitted values: the
grid points below and above its solved value (equal when it already sits
on the grid).  Start every node at its NEAREST grid point (today's
behaviour, so a field with slack is byte-identical).  Then, for each pair
still over its raw cap, flip whichever endpoint's flip fixes the pair
without breaking an already-lawful pair; iterate to a fixed point with a
small bounded pass cap.  Every reachable state keeps each node within one
grid step of its solved value, so the guard is bounded whether or not it
converges, and the residual is REPORTED rather than hidden.

The pair set is the emitted patch's own law pairs (the same
``(i, j, cap·length)`` budgets the validator reads), so this is a guard on
the law, not a second grading authority: it never moves a value off its
own grid neighbourhood and never changes which pairs exist.
"""
from __future__ import annotations

import os as _os
from typing import Dict, Iterable, List, Sequence, Tuple

__all__ = ["snap_grid_m", "emit_snap_enabled", "law_aware_snap",
           "snap_pairs_from_axes_ll"]

#: The emitted elevation grid (``to_osm`` writes ``f"{v:.2f}"``).
_SNAP_GRID_M = 0.01

#: Bounded repair passes.  Each pass is O(pairs); the fixed point is
#: normally reached in one or two.  A residual after the cap is REPORTED,
#: never iterated on (convergence guards: 2-attempt cap, materiality
#: floor).
_MAX_PASSES = 4


def snap_grid_m() -> float:
    """The emitted elevation grid step in metres."""
    return _SNAP_GRID_M


def emit_snap_enabled() -> bool:
    """The guard rides the SAME gate as the raw-law sweeps: the margin and
    the snap are two halves of ONE guarantee and must never be off (or on)
    together.  ``O4_EMIT_SNAP_GUARD`` overrides for the twins."""
    explicit = _os.environ.get("O4_EMIT_SNAP_GUARD")
    if explicit is not None:
        return explicit == "1"
    return _os.environ.get("O4_RAW_LAW_SWEEPS", "0") == "1"


def _grid_neighbours(value: float) -> Tuple[float, float]:
    """``(below, above)`` grid points bracketing ``value`` (equal when it
    already sits on the grid, to within half a micron)."""
    q = value / _SNAP_GRID_M
    lo = _round_half_even_floor(q)
    below = lo * _SNAP_GRID_M
    if abs(value - below) < 1e-9:
        return below, below
    return below, below + _SNAP_GRID_M


def _round_half_even_floor(q: float) -> float:
    import math
    return math.floor(q + 1e-9)


def _nearest(value: float) -> float:
    below, above = _grid_neighbours(value)
    if below == above:
        return below
    return below if (value - below) <= (above - value) else above


def law_aware_snap(
        values: Dict[int, float],
        pairs: Sequence[Tuple[int, int, float]],
        *,
        max_passes: int = _MAX_PASSES,
) -> Tuple[Dict[int, float], dict]:
    """Snap ``values`` (``{node: solved_elev}``) to the emit grid so that no
    pair in ``pairs`` (``(i, j, raw_cap)``) exceeds its RAW cap because of
    the snap.

    Returns ``(snapped, report)``.  ``report`` carries
    ``over_cap_before`` / ``over_cap_after`` (pairs over cap purely from
    the snap — a pair already over cap on the SOLVED field is excluded:
    the snap is not asked to repair the solver), ``flips`` and
    ``worst_residual_m``.

    Guarantees, both by construction and both asserted by the twins:
      * every returned value is a grid point ADJACENT to the node's solved
        value (``|snapped − solved| ≤ one grid step``);
      * a pair lawful on the solved field and repairable by direction
        choice comes out lawful.
    """
    snapped: Dict[int, float] = {k: _nearest(v) for k, v in values.items()}
    below: Dict[int, float] = {}
    above: Dict[int, float] = {}
    for k, v in values.items():
        below[k], above[k] = _grid_neighbours(v)

    def _solved_lawful(i: int, j: int, cap: float) -> bool:
        return abs(values[i] - values[j]) - cap <= 1e-12

    live: List[Tuple[int, int, float]] = [
        (i, j, cap) for (i, j, cap) in pairs
        if i in values and j in values and cap is not None and cap >= 0.0]

    over_before = sum(
        1 for (i, j, cap) in live
        if _solved_lawful(i, j, cap)
        and abs(snapped[i] - snapped[j]) - cap > 1e-12)

    flips = 0
    for _ in range(max(0, int(max_passes))):
        moved = False
        for (i, j, cap) in live:
            if not _solved_lawful(i, j, cap):
                continue                    # the SOLVER owns this one
            if abs(snapped[i] - snapped[j]) - cap <= 1e-12:
                continue
            # The pair is over cap ONLY because of the snap.  Flipping the
            # HIGHER endpoint down (or the LOWER one up) is the only
            # direction that helps; take whichever flip is available and
            # does not break an already-lawful incident pair.
            hi, lo = (i, j) if snapped[i] > snapped[j] else (j, i)
            for node, target in ((hi, below[hi]), (lo, above[lo])):
                if target == snapped[node]:
                    continue                # already at that neighbour
                prev = snapped[node]
                snapped[node] = target
                if _breaks_a_lawful_pair(node, snapped, values, live):
                    snapped[node] = prev
                    continue
                flips += 1
                moved = True
                break
        if not moved:
            break

    over_after = 0
    worst = 0.0
    for (i, j, cap) in live:
        if not _solved_lawful(i, j, cap):
            continue
        excess = abs(snapped[i] - snapped[j]) - cap
        if excess > 1e-12:
            over_after += 1
            worst = max(worst, excess)
    return snapped, {
        "pairs": len(live),
        "over_cap_before": int(over_before),
        "over_cap_after": int(over_after),
        "flips": int(flips),
        "worst_residual_m": float(worst),
    }


def _breaks_a_lawful_pair(node: int, snapped, values, live) -> bool:
    """True when ``node``'s current snap puts an incident pair over cap
    that the SOLVED field satisfied.  Linear in ``live`` — the pair lists
    this guard runs on are the emitted patch's law pairs, and the repair
    loop only reaches here for pairs the nearest-snap actually broke (a
    handful per airport), so the cost is a scan of the tight set, not a
    quadratic sweep."""
    for (i, j, cap) in live:
        if node != i and node != j:
            continue
        if abs(values[i] - values[j]) - cap > 1e-12:
            continue                        # never satisfied — not ours
        if abs(snapped[i] - snapped[j]) - cap > 1e-12:
            return True
    return False


def snap_pairs_from_axes_ll(pair_caps_ll: Iterable, node_id_to_ll: dict,
                            referenced_nids) -> List[Tuple[int, int, float]]:
    """Adapt the sidecar's ``pair_caps`` rows —
    ``[[lat_a, lon_a], [lat_b, lon_b], budget_m]``, lat/lon rounded to 7
    decimals — into node-id pairs against the emitter's own
    ``node_id_to_ll``.

    ONE pair set, ONE key: the 7-decimal lat/lon rounding is exactly the
    key ``verification.lockstep_pair_caps_ll`` wrote and ``check_grade``
    reads, so the guard and the validator judge the same pairs (the
    lockstep requirement).  A pair whose endpoint is not emitted (weld,
    decimation) simply drops — the guard never invents a constraint."""
    ll_to_nid: dict = {}
    for nid, (lat, lon) in (node_id_to_ll or {}).items():
        if referenced_nids is not None and nid not in referenced_nids:
            continue
        ll_to_nid.setdefault((round(float(lat), 7), round(float(lon), 7)),
                             nid)
    out: List[Tuple[int, int, float]] = []
    for row in (pair_caps_ll or ()):
        try:
            (lat_a, lon_a), (lat_b, lon_b), cap = row[0], row[1], float(row[2])
        except (TypeError, ValueError, IndexError):
            continue
        nid_a = ll_to_nid.get((round(float(lat_a), 7), round(float(lon_a), 7)))
        nid_b = ll_to_nid.get((round(float(lat_b), 7), round(float(lon_b), 7)))
        if nid_a is None or nid_b is None or nid_a == nid_b:
            continue
        out.append((nid_a, nid_b, cap))
    return out
