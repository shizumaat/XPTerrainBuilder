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

THE MODULE OWNS TWO EMIT-SIDE DISCIPLINES.  The second is
:func:`shared_corner_authority_nodes` — the SHARED-CORNER AUTHORITY law
(see its docstring).  Both answer the same question: which authority owns
a value once the global solve has converged.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set, Tuple

__all__ = ["snap_grid_m", "law_aware_snap", "snap_pairs_from_axes_ll",
           "shared_corner_authority_nodes", "SHARED_CORNER_MAX_BEND_DEG"]

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


#: A ring vertex whose incident edges turn by more than this is a REAL
#: grade break on that ring, not a point on a straight run.  Same value and
#: same test as ``route_profile.solve._fair_ring_edges``' ``max_bend_deg``
#: — one number, one meaning; a second threshold here would be a second
#: instrument over one population.
SHARED_CORNER_MAX_BEND_DEG = 25.0


def shared_corner_authority_nodes(layout, bucket_to_idx,
                                  max_bend_deg: float =
                                  SHARED_CORNER_MAX_BEND_DEG) -> Set[int]:
    """THE SHARED-CORNER AUTHORITY LAW — the node indices a RING-LOCAL pass
    may read but must never write.

    THE LAW.  A vertex owned by ONE shape ring is that ring's own variable:
    a ring-local pass (edge fairing, triangle-plane repair) has full
    authority over it.  A vertex owned by TWO OR MORE rings does not belong
    to any one of them.  Where every owner agrees the vertex sits on a
    STRAIGHT run, the owners cannot disagree and a ring-local move is
    harmless.  Where even ONE owner sees a CORNER — a real grade break —
    the vertex is a break for the surface, and any other owner that fairs
    it "smooth" is exercising an authority it does not have.  Such a vertex
    keeps the value the GLOBAL projection converged to, which is the same
    discipline a weld-shared vertex follows: one node, one value, never a
    second writer.

    THE DEFECT IT CLOSES (SPJC node 10625, ``spjc16/``).  A FREE node
    (``hard_cat`` None) at the corner of apron 551 + junction 444 +
    junction 568.  Between two arms its value in SOLVE SPACE — the input to
    ``final_grade_projection`` — moved **+0.078 m** (22.101 → 22.179).  Its
    EMITTED value moved **+0.310 m** (22.490 → 22.800): a **4.0x**
    amplification at this ONE node while every neighbour within 12 m
    emitted +0.04..+0.11.  It minted a **50.67 %** grade row — rank 1 in
    the whole airport, against a both-off worst of 13.0 % — and 10 of the
    28 new census rows in that arm trace to it alone (census +16 → +7 once
    the single vertex is neutralised).  The amplifier is the ring-local
    tail of the projection: the node is the CENTRE of up to three different
    fairing triples, one per owning ring, each with different flanks and a
    length-scaled lever, all mutating one shared slot in sequence.

    NOT A CLAMP.  Nothing here changes a value; it names the nodes whose
    value is already decided.  Passing this set as a pass's ANCHOR set
    (never as ``skip_nodes``) keeps such a node READABLE as a flank — its
    neighbours still fair against it — and only removes the write.

    ``bucket_to_idx`` — the solve's canonical-key → node-index map, so the
    set is returned in the caller's own index space.  Ownership is read
    through ``canonical_points.get`` (the MEASUREMENT query, never
    ``get_or_add``: interning a new point changes which LATER points intern
    together and would move the emitted surface), so a ring vertex the
    registry has never seen is simply not counted.

    Ownership counts EVERY shape with a polygon, buildings and runways
    included: a junction that shares a vertex with a building ring is
    exactly the cross-authority case, and excluding the roles a given pass
    happens to skip would make the answer pass-specific — which is how one
    population comes to have two instruments.
    """
    import math as _math

    cps = getattr(layout, "canonical_points", None)
    if cps is None or not bucket_to_idx:
        return set()
    # ONE SCAN PER GEOMETRY STATE.  ``final_grade_projection`` runs twice
    # (MID and LATE) and the ownership relation is a pure function of the
    # ring geometry + the registry, so the answer is cached against both.
    # ``len(bucket_to_idx)`` is in the key because the set is returned in
    # the CALLER's index space — a different node list is a different
    # answer even over identical geometry.
    stamp = (len(getattr(layout, "shapes", ()) or ()), cps.size,
             len(bucket_to_idx), float(max_bend_deg))
    cached = getattr(layout, "_shared_corner_authority_cache", None)
    if cached is not None and cached[0] == stamp:
        return set(cached[1])
    cos_lim = _math.cos(_math.radians(float(max_bend_deg)))
    owners: Dict[object, int] = {}
    corner: Set[object] = set()
    for s in getattr(layout, "shapes", ()) or ():
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        try:
            ring = list(poly.exterior.coords)
        except Exception:                            # pragma: no cover
            continue
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        m = len(ring)
        if m < 3:
            continue
        keys = [cps.get(float(x), float(y)) for (x, y) in ring[:m]]
        seen_here: Set[object] = set()
        for t in range(m):
            k = keys[t]
            if k is None:
                continue
            if k not in seen_here:
                seen_here.add(k)
                owners[k] = owners.get(k, 0) + 1
            if k in corner:
                continue
            ax, ay = ring[(t - 1) % m][0], ring[(t - 1) % m][1]
            bx, by = ring[t][0], ring[t][1]
            dx, dy = ring[(t + 1) % m][0], ring[(t + 1) % m][1]
            ux, uy = bx - ax, by - ay
            vx, vy = dx - bx, dy - by
            lu = _math.hypot(ux, uy)
            lv = _math.hypot(vx, vy)
            if lu <= 1e-9 or lv <= 1e-9:
                continue        # degenerate segment: no direction to turn
            if (ux * vx + uy * vy) / (lu * lv) < cos_lim:
                corner.add(k)
    out: Set[int] = set()
    for k, n_owners in owners.items():
        if n_owners < 2 or k not in corner:
            continue
        i = bucket_to_idx.get(k)
        if i is not None:
            out.add(int(i))
    try:
        layout._shared_corner_authority_cache = (stamp, frozenset(out))
    except Exception:                                    # pragma: no cover
        pass                                             # read-only layout
    return out


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
