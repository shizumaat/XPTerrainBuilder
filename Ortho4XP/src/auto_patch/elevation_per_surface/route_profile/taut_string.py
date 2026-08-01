"""Exact taut string through a vertical tube (spine longitudinal profile).

The taut-string objective (docs/specs/taut-string-spine-profile-spec.md,
approved 2026-07-28) replaces the min-curvature harmonic as the taxi-spine
longitudinal profile: per corridor, the profile is the *shortest path* in
the ``(station, elevation)`` plane through the feasible tube
``[floor[i], ceiling[i]]``, pinned at genuinely-pinned points.  It is
symmetric (no up/down preference), deviates from the chord only where a
wall or a peg forces it, and every bend has a witnessed wall contact.

This module is deliberately dependency-free — pure stdlib + :mod:`math`,
no ``auto_patch`` imports, no numpy/shapely, no randomness — so it can be
unit-tested in isolation and reused by any caller.  Output is a
deterministic function of the inputs (bit-identical across runs).

Algorithm: the greedy funnel.  Walking right from the last fixed point
``(s_a, z_a)`` the feasible slope window ``[g_lo, g_hi]`` is tightened by
each visited station (``g_hi`` from the ceilings, ``g_lo`` from the
floors, both remembering the station that set them).  While the window is
non-empty the string can still reach every visited station in a straight
line.  When a new station inverts the window the string must bend at the
binding wall contact: a floor that pushes ``g_lo`` past ``g_hi`` bends the
string down onto the ceiling of the station that set ``g_hi`` (symmetric
for a ceiling that pushes ``g_hi`` below ``g_lo``).  The bend point
becomes the new fixed point and the funnel restarts there; stations
between two fixed points take the straight tangent between them.  At the
last station the same rule is applied to the closing slope required by
``z_end``.

Complexity: each bend permanently retires every station up to the bend,
so the scan is O(k) on the corridors this solver sees (station counts are
in the hundreds; a whole HECA spine is ~7 k nodes across all corridors).

Correctness oracle (used by ``tests/test_taut_string.py``): the taut
string is exactly the fixpoint of the clamped-Laplacian obstacle-problem
relaxation ``z_i <- clamp(lerp(z_{i-1}, z_{i+1}), floor_i, ceiling_i)``
with the endpoints held — a strictly convex problem, hence a unique
fixpoint.

S1 — THE TAUT-CHORD CONSTRUCTOR (2026-07-31)
--------------------------------------------
``docs/specs/s1-taut-chord-constructor-spec.md`` adds a second layer on
top of the funnel above: it is not enough to string a corridor well if
the corridor DECOMPOSITION already forbids the answer.  Measured (S1
spec §1a, interventional): ``_build_spine_corridors`` cuts HECA's single
3,980 m parallel-taxiway chord into 62 pieces carrying ZERO hard
anchors, and the 59 interior piece ENDPOINTS — 8 % of the chord's spine
nodes — carry 100 % of the movable sag, because each is pegged at its
inherited draped value.  So "the longest possible straight chord between
its anchors" (model spec §4.3.1) was never attempted.

Stage 0 (:func:`assemble_maximal_strings`) therefore assembles its OWN
maximal string domains by following through junctions onto the adjoining
piece whose heading deviates least.  Interior piece endpoints then
DISSOLVE into ordinary stations — they carry no value and no boundary
role — which is a stronger statement than seeding them well, and is what
:func:`taut_chain_profile` then strings.  ``_build_spine_corridors`` is
deliberately NOT modified (it keeps its other consumers); S1's assembly
is a read-only overlay.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import (Dict, List, NamedTuple, Optional,
                    Sequence, Set, Tuple)

__all__ = [
    "taut_string", "string_with_pegs",
    # S1 — the CHORD MODEL (rulings 42/43/49).  The tube, the funnel, the
    # bends and the fragment-assembly family retired with ruling 45's
    # protocol; ``taut_string``/``string_with_pegs`` STAY — they are the
    # §10 rod sweep's, not string construction's.
    "StringDomain", "StringDefect", "walk_spine_runs",
    "compose_through_paths", "substrate_fingerprint",
    "substrate_from_carriage", "decorate_nodes_onto_strings",
    "ThroughPathChains", "through_path_chains", "domains_from_walk",
    "TenureRound", "TenureResult", "strings_with_tenure",
    "EndpointRead", "read_endpoint_band_centre", "chord_station",
    "chord_targets", "compass_ends", "filter_pins_by_grade_law",
    "construct_taut_strings", "write_string_sidecar",
]

INF = float("inf")

#: ★ RULING 9 — the substrate's sampling resolution.  OURS, not the
#: owner's: a sampling resolution prices no intent, so asking him would
#: invert the intent-question law.  Grounds: every measured arm and every
#: prediction on this line is seated on 5.0 m, with 1.6x margin against
#: the 8 m corridor law and 20x against the 100 m emission law.  FORM IS
#: BINDING: it stays REQUIRED-EXPLICIT at the builder, it is named ONCE
#: here for the one production call site, it is NEVER config- or
#: env-tunable (deliberately unlike the owner's constants), it is logged
#: in every denominator line, and it moves only by ruling WITH a
#: re-baseline.
SUBSTRATE_STATION_M = 5.0

#: ★ RULING 10 — CONSTRUCTION-side interning: float-noise hygiene, and
#: nothing else.  The registry's 0.5 m binds at DECORATION ONLY; interning
#: the substrate at 0.5 m is FORBIDDEN (it would mint identity the
#: registry never granted).  Pinned here and logged like the station.
SUBSTRATE_INTERN_M = 1e-6

#: Endpoint / peg values are clamped into their own walls.  Violations
#: below this size are pure floating-point noise; larger ones are clamped
#: too (spec §4: the raw value is owned elsewhere and is never changed,
#: the mismatch stays reported by the cap projection).
ENDPOINT_CLAMP_TOL = 1e-9


def _clamp(value: float, low: float, high: float) -> float:
    """Return ``value`` clamped into ``[low, high]`` (``±inf`` allowed)."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def _check_tube(stations: list[float], floor: list[float],
                ceiling: list[float]) -> int:
    """Assert the shared tube preconditions and return the length."""
    k = len(stations)
    assert k >= 2, "taut string needs at least two stations"
    assert len(floor) == k, "floor length must match stations"
    assert len(ceiling) == k, "ceiling length must match stations"
    for i in range(1, k):
        assert stations[i] > stations[i - 1], (
            f"stations must strictly increase (index {i}: "
            f"{stations[i - 1]!r} -> {stations[i]!r})")
    for i in range(k):
        assert floor[i] <= ceiling[i], (
            f"inverted tube at index {i}: floor {floor[i]!r} > "
            f"ceiling {ceiling[i]!r}")
    return k


def _emit(out: list[float], stations: list[float],
          a: int, z_a: float, b: int, z_b: float) -> None:
    """Write the straight segment ``(s_a, z_a) -> (s_b, z_b)`` into
    ``out``, interpolating the stations strictly between them."""
    s_a = stations[a]
    grade = (z_b - z_a) / (stations[b] - s_a)
    for m in range(a + 1, b):
        out[m] = z_a + grade * (stations[m] - s_a)
    out[b] = z_b


def taut_string(stations: list[float], floor: list[float],
                ceiling: list[float],
                z_start: float, z_end: float) -> list[float]:
    """Exact taut string (shortest path in ``(s, z)``) through the tube
    ``[floor[i], ceiling[i]]`` at strictly-increasing ``stations``, from
    ``(stations[0], z_start)`` to ``(stations[-1], z_end)``.

    Walls may be ``float('-inf')`` / ``float('inf')`` (unbounded), which
    is how off-network nodes with no reach band are expressed.

    Preconditions (asserted): equal lengths >= 2, strictly increasing
    stations, ``floor[i] <= ceiling[i]``.  The endpoint values are
    clamped into their own walls (see :data:`ENDPOINT_CLAMP_TOL`).

    Returns a ``list[float]`` of the same length; ``out[0]`` and
    ``out[-1]`` are the clamped endpoint values.
    """
    k = _check_tube(stations, floor, ceiling)

    z_a = _clamp(float(z_start), floor[0], ceiling[0])
    z_target = _clamp(float(z_end), floor[k - 1], ceiling[k - 1])
    assert math.isfinite(z_a), f"start value not finite: {z_start!r}"
    assert math.isfinite(z_target), f"end value not finite: {z_end!r}"

    out = [0.0] * k
    out[0] = z_a
    a = 0
    while a < k - 1:
        s_a = stations[a]
        g_hi, i_hi = INF, -1     # tightest ceiling bound and its witness
        g_lo, i_lo = -INF, -1    # tightest floor bound and its witness
        bend, bend_value = -1, 0.0
        j = a + 1
        while j < k:
            ds = stations[j] - s_a
            top, bot = ceiling[j], floor[j]
            g_top = INF if top == INF else (top - z_a) / ds
            g_bot = -INF if bot == -INF else (bot - z_a) / ds
            if g_bot > g_hi:
                # This floor cannot be cleared without breaching the
                # ceiling that set g_hi: bend down onto that ceiling.
                bend, bend_value = i_hi, ceiling[i_hi]
                break
            if g_top < g_lo:
                # Symmetric: bend up onto the floor that set g_lo.
                bend, bend_value = i_lo, floor[i_lo]
                break
            if g_top <= g_hi:    # ties keep the furthest witness
                g_hi, i_hi = g_top, j
            if g_bot >= g_lo:
                g_lo, i_lo = g_bot, j
            j += 1

        if bend < 0:
            # Every station is reachable in a straight line; aim at the
            # far endpoint, bending first if its slope is out of window.
            g_req = (z_target - z_a) / (stations[k - 1] - s_a)
            if g_req > g_hi:
                bend, bend_value = i_hi, ceiling[i_hi]
            elif g_req < g_lo:
                bend, bend_value = i_lo, floor[i_lo]
            else:
                bend, bend_value = k - 1, z_target

        assert bend > a, "taut string funnel failed to advance"
        assert math.isfinite(bend_value), "bend onto an unbounded wall"
        _emit(out, stations, a, z_a, bend, bend_value)
        a, z_a = bend, bend_value

    return out


def string_with_pegs(stations: list[float], floor: list[float],
                     ceiling: list[float],
                     pegs: dict[int, float]) -> list[float] | None:
    """Taut string with pass-through pegs.

    ``pegs`` maps station index -> value (hard nodes: runway joins, seam
    pins, ``seat_on_spine`` seats, settled corridor endpoints).  The
    corridor is split at the peg indices and every span between two
    consecutive pegs is strung independently with :func:`taut_string`, so
    a peg is an exact pass-through point.  A peg value is clamped into
    its OWN walls for the string; the input dict is never mutated (the
    raw peg value is owned elsewhere).

    If index 0 (resp. the last index) is not a peg, that free end
    CONTINUES THE TANGENT of the adjacent strung span, clamped into the
    walls at each station — the fewest-grade-changes rule.

    Fewer than 2 pegs total: returns ``None`` (the caller falls back to
    its current behaviour).
    """
    k = _check_tube(stations, floor, ceiling)
    for index, value in pegs.items():
        assert isinstance(index, int) and not isinstance(index, bool), (
            f"peg index must be an int, got {index!r}")
        assert 0 <= index < k, f"peg index {index} out of range (k={k})"
        assert math.isfinite(value), (
            f"peg value at index {index} not finite: {value!r}")

    indices = sorted(pegs)
    if len(indices) < 2:
        return None

    out = [0.0] * k
    for p, q in zip(indices, indices[1:]):
        out[p:q + 1] = taut_string(stations[p:q + 1], floor[p:q + 1],
                                   ceiling[p:q + 1], pegs[p], pegs[q])

    first, last = indices[0], indices[-1]
    if first > 0:
        # Tangent of the first strung segment, extended backwards.
        grade = ((out[first + 1] - out[first])
                 / (stations[first + 1] - stations[first]))
        s_p, z_p = stations[first], out[first]
        for m in range(first):
            out[m] = _clamp(z_p + grade * (stations[m] - s_p),
                            floor[m], ceiling[m])
    if last < k - 1:
        # Tangent of the last strung segment, extended forwards.
        grade = ((out[last] - out[last - 1])
                 / (stations[last] - stations[last - 1]))
        s_q, z_q = stations[last], out[last]
        for m in range(last + 1, k):
            out[m] = _clamp(z_q + grade * (stations[m] - s_q),
                            floor[m], ceiling[m])
    return out


# ══════════════════════════════════════════════════════════════════════
# S1 — Stage 0: maximal-string domain assembly (spec §2)
# ══════════════════════════════════════════════════════════════════════

#: Two positions closer than this are the same point (degenerate step).
_DEGENERATE_STEP_M = 1e-9

#: Slope-audit and wall-contact tolerance.
_SLOPE_TOL = 1e-9
_CONTACT_TOL = 1e-7


@dataclass(frozen=True)
class StringDomain:
    """A maximal string domain — the output of Stage 0 (spec §4)."""

    vertices: List[int]
    stations: List[float]
    pieces: List[int]
    priority_class: int


@dataclass(frozen=True)
class StringDefect:
    """An infeasible station or a slope-audit failure (spec §2.2/§2.4).

    Both carry BOTH binding authors, so the report names what propagated
    each side rather than merely that the chain failed.
    """

    kind: str            # "infeasible_station" | "slope_audit"
    chain_id: int
    station: float
    vertex: int
    lo: float
    hi: float
    author_lo: str
    author_hi: str
    detail: str



def _stations_of(points: Sequence[Tuple[float, float]]) -> List[float]:
    """Cumulative straight-line chord stations along ``points``."""
    out = [0.0] * len(points)
    acc = 0.0
    for t in range(1, len(points)):
        acc += math.hypot(points[t][0] - points[t - 1][0],
                          points[t][1] - points[t - 1][1])
        out[t] = acc
    return out


def _walk_segments(walk, pos, adj, bound_m, stops_out=None):
    """Bound-departure segmentation along ONE walk direction.

    ``stops_out`` (out-parameter, ``None`` in every production call that
    does not want it) collects ``(end_node, reason)`` for each boundary
    this direction creates: ``gap`` when the spine edge is absent (P7's
    holes) and ``turn`` when the chord departs beyond ``bound_m``.  The
    distinction is not cosmetic — a turn is the owner's +/-8 m tolerance
    doing its job and his to rule on, a gap is substrate and ours.
    """
    def _dev(pts):
        a, b = pts[0], pts[-1]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-9:
            return 0.0
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        return max(abs(-(p[0] - a[0]) * uy + (p[1] - a[1]) * ux) for p in pts)

    segs, seg = [], [walk[0]]
    for k in range(1, len(walk)):
        prev, cur = walk[k - 1], walk[k]
        _gap = cur not in adj.get(prev, ())
        if not _gap:                                  # (b) no spine gap
            cand = seg + [cur]
            if _dev([pos[v] for v in cand]) <= bound_m:
                seg = cand
                continue
        if stops_out is not None:
            stops_out.append((prev, "gap" if _gap else "turn"))
        if len(seg) >= 2:
            segs.append(seg)
        seg = [cur]
    if stops_out is not None and len(seg) >= 2:
        stops_out.append((seg[-1], "route_end"))
    if len(seg) >= 2:
        segs.append(seg)
    return segs


def walk_spine_runs(chains, pos, spine_adj, *, bound_m, min_len_m=None,
                    service=(), stops_out=None):
    """The SPINE WALK with DIRECTION SYMMETRY (Fable rulings, 2026-07-31).

    The chord-growing core is unchanged — the DOMAIN changes.  Candidates
    are "the next nodes along the walked spine path", never "spine within
    margin of a chord in the plane".  That alone makes open-terrain
    crossing UNREPRESENTABLE BY CONSTRUCTION: a string can only be a
    stretch of walked spine, so it can never cut between two taxiways
    across unpaved ground — the defect the owner named in ~all 32
    unmatched runs.  The walk ends a segment at (a) a turn (departure
    beyond ``bound_m``), (b) a spine gap (P7's holes), (c) route end.

    ★ DIRECTION SYMMETRY — the curve-exit answer, and it needs NO new
    constant: an emitted string must be reproducible growing from EITHER
    end.  Forward-only growth absorbs a curve's tail into the following
    segment; that tail cannot be reproduced growing backward, so the
    consensus of the two directions drops it.  "Sustained departure" and
    "straightens" are therefore EMERGENT, never parameters — sub-bound
    curvature IS straight at the owner's resolution, and curve segments
    are discarded by his own >=100 m emission rule rather than by any
    straightening test.  Do not reintroduce one.

    ``bound_m`` is a VALIDATION BOUND and is REQUIRED-EXPLICIT.
    ``min_len_m`` defaults to the owner's landed 100 m.

    Returns ``(strings, sub_min)``; sub-threshold segments are kept as
    measurement, preserving the selection layering.
    """
    if min_len_m is None:
        from auto_patch.config import TAUT_STRING_MIN_STRING_M as _MIN
        min_len_m = _MIN
    adj = {}
    for i, lst in (spine_adj or {}).items():
        adj[i] = {(e[0] if isinstance(e, (tuple, list)) else e) for e in lst}
    strings, sub_min = [], []
    for ci, chain in chains.items():
        if ci in service:
            continue
        walk = [v for v in chain if v in pos]
        if len(walk) < 2:
            continue
        _fstops = [] if stops_out is not None else None
        fwd = _walk_segments(walk, pos, adj, bound_m, _fstops)
        bwd = [list(reversed(sg)) for sg in
               _walk_segments(list(reversed(walk)), pos, adj, bound_m)]
        # CONSENSUS: a node is strung only where BOTH directions agree.
        # Per forward segment, keep its maximal contiguous runs whose
        # nodes are also covered by some backward segment.  (Pairing every
        # forward against every backward segment instead would manufacture
        # spurious fragments from cross-pairs.)
        bcov = set()
        for b in bwd:
            bcov |= set(b)
        consensus = []
        for f in fwd:
            run = []
            for v in f:
                if v in bcov:
                    run.append(v)
                else:
                    if len(run) >= 2:
                        consensus.append(run)
                    run = []
            if len(run) >= 2:
                consensus.append(run)
        if stops_out is not None:
            # the forward pass's own boundaries, plus the ones DIRECTION
            # SYMMETRY created: a node the backward pass did not cover
            # ends its run by consensus, which is a different author from
            # a turn and must not be reported as one.
            _fwdset = {v for f in fwd for v in f}
            for _v, _why in _fstops:
                stops_out.append({"chain": ci, "node": _v, "reason": _why,
                                  "x": pos[_v][0], "y": pos[_v][1]})
            for _run in consensus:
                for _end in (_run[0], _run[-1]):
                    if _end in _fwdset and not any(
                            _s["node"] == _end and _s["chain"] == ci
                            for _s in stops_out):
                        stops_out.append({"chain": ci, "node": _end,
                                          "reason": "consensus",
                                          "x": pos[_end][0],
                                          "y": pos[_end][1]})
        for seg in consensus:
            a, b = pos[seg[0]], pos[seg[-1]]
            ln = math.hypot(b[0] - a[0], b[1] - a[1])
            if ln < min_len_m and stops_out is not None:
                for _end in (seg[0], seg[-1]):
                    stops_out.append({"chain": ci, "node": _end,
                                      "reason": "tenure", "x": pos[_end][0],
                                      "y": pos[_end][1]})
            (strings if ln >= min_len_m else sub_min).append(
                (a, b, list(seg), ln, ci))
    return strings, sub_min


def compose_through_paths(items, pos):
    """MAXIMAL THROUGH-PATHS partitioning the substrate EDGES (ruling 2).

    ★ RESTORATION OF COMMITTED LAW, not new intent: the model spec
    already rules that "a JUNCTION is not a turn — chord 1 runs straight
    through 33" and "an AUTHORED GEOMETRY BREAK is not a turn".  Piece
    ids, route ids, junctions, dedup seams and tier boundaries are
    therefore NOT chain boundaries; the only boundaries left are the ones
    the geometry itself imposes, and the WALK (not this function) finds
    those with the owner's 8.0 m bound.

    Mechanics, all of them:
      * the input's consecutive node pairs are EDGES; the output
        partitions them (every edge appears in exactly one path);
      * junction composition is **global best-collinear pairing —
        permissive and PARAMETER-FREE**.  Every (junction, edge-pair)
        candidate is scored by straight-through-ness and accepted in one
        global descending pass while both ends are free.  There is no
        threshold and none may be added: ``TAUT_STRING_TURN_DEG`` stays
        retired;
      * a degree-2 node (a seam joint, an authored geometry break) has
        exactly one candidate, so seam joints compose END-TO-END by the
        same rule with no special case;
      * ``min_len`` is NOT applied here — it applies to WALK OUTPUT.

    ★ THE SAFETY SENTENCE, in its CORRECTED form (Fable 2026-07-31, ruling
    3; the original was measured TRUE in geometry and FALSE in tenure):
    a bad pairing costs nothing ANYWHERE — the walk cuts its geometry AND
    its tenure lapses.  Under emission-charged tenure
    (:func:`strings_with_tenure`) a composed path only SPENDS the edges an
    emitted string actually covers; a cut-off tail returns to the pool and
    another round may string it.  Do not read this as a licence to pair
    loosely: it is why no threshold is needed here.

    ★ PATHS STAY LINEAR.  A free graph walk is REJECTED (unmeasured
    machinery): linear chains are precisely what keeps OPEN-TERRAIN
    CROSSING UNREPRESENTABLE BY CONSTRUCTION — the acceptance property of
    the whole design.  Traversal therefore never revisits a node inside
    one path; a cycle or figure-eight ends the path and the remaining
    edges start their own.

    Pure, deterministic (every iteration is over sorted keys) and
    O(E log E + sum deg^2).  Returns ``(items, stats)``.
    """
    # ── edges (deduped, positioned) ───────────────────────────────────
    edges: List[Tuple[int, int]] = []
    edge_id: Dict[Tuple[int, int], int] = {}
    src_chains: Dict[int, Set[int]] = {}
    n_no_pos = 0
    for cid, chain in items:
        for a, b in zip(chain, chain[1:]):
            if a == b:
                continue
            if a not in pos or b not in pos:
                n_no_pos += 1
                continue
            key = (a, b) if a < b else (b, a)
            eid = edge_id.get(key)
            if eid is None:
                eid = edge_id[key] = len(edges)
                edges.append(key)
            src_chains.setdefault(eid, set()).add(cid)
    incident: Dict[int, List[int]] = {}
    for eid, (a, b) in enumerate(edges):
        incident.setdefault(a, []).append(eid)
        incident.setdefault(b, []).append(eid)

    def _other(eid, v):
        a, b = edges[eid]
        return b if a == v else a

    def _dir(v, eid):
        px, py = pos[v]
        qx, qy = pos[_other(eid, v)]
        d = math.hypot(qx - px, qy - py)
        return None if d < 1e-12 else ((qx - px) / d, (qy - py) / d)

    # ── global best-collinear pairing (no threshold) ──────────────────
    cands = []
    for v in sorted(incident):
        inc = sorted(incident[v])
        dirs = {e: _dir(v, e) for e in inc}
        for i, e1 in enumerate(inc):
            d1 = dirs[e1]
            if d1 is None:
                continue
            for e2 in inc[i + 1:]:
                d2 = dirs[e2]
                if d2 is None:
                    continue
                # +1 = dead straight through v, -1 = hairpin.
                cands.append((-(d1[0] * d2[0] + d1[1] * d2[1]), v, e1, e2))
    cands.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
    pair: Dict[Tuple[int, int], int] = {}
    for _score, v, e1, e2 in cands:
        if (v, e1) in pair or (v, e2) in pair:
            continue
        pair[(v, e1)] = e2
        pair[(v, e2)] = e1

    # ── traversal into maximal LINEAR paths ───────────────────────────
    used: Set[int] = set()
    out: List[Tuple[int, List[int]]] = []
    path_chains: Dict[int, int] = {}
    for e0 in range(len(edges)):
        if e0 in used:
            continue
        used.add(e0)
        a0, b0 = edges[e0]
        nodes = [a0, b0]
        seen_nodes = {a0, b0}
        chains_here = set(src_chains.get(e0, ()))
        for end, append in ((b0, True), (a0, False)):
            e, v = e0, end
            while True:
                nxt = pair.get((v, e))
                if nxt is None or nxt in used:
                    break
                w = _other(nxt, v)
                if w in seen_nodes:          # cycle / figure-eight: STOP
                    break                    # (the edge starts its own path)
                used.add(nxt)
                seen_nodes.add(w)
                chains_here |= src_chains.get(nxt, set())
                if append:
                    nodes.append(w)
                else:
                    nodes.insert(0, w)
                e, v = nxt, w
        path_chains[len(out)] = len(chains_here)
        out.append((len(out), nodes))
    stats = {
        "n_edges": len(edges),
        "n_edges_dropped_no_pos": n_no_pos,
        "n_paths": len(out),
        "path_source_chains": path_chains,
        "max_source_chains_per_path": max(path_chains.values(), default=0),
        "max_path_nodes": max((len(p) for _i, p in out), default=0),
    }
    return out, stats


class ThroughPathChains(NamedTuple):
    """``through_path_chains``' result.

    ``chains`` are the composed through-paths as coordinates (the chain
    equality control); ``items``/``pos`` are the SAME data interned into
    the node domain :func:`strings_with_tenure` consumes, so an offline
    arm never interns twice or re-composes to run the emission.
    """

    chains: List[Tuple[int, List[Tuple[float, float]]]]
    stats: Dict[str, object]
    items: List[Tuple[int, List[int]]] = []
    pos: Dict[int, Tuple[float, float]] = {}


class TenureRound(NamedTuple):
    """One round of :func:`strings_with_tenure` (ruling 3 telemetry)."""

    index: int
    n_paths: int
    n_strings: int
    metres: float
    pool_before: int
    edges_spent: int


class TenureResult(NamedTuple):
    """Emitted strings after tenure converges, plus the round census."""

    strings: List[tuple]
    sub_min: List[tuple]
    rounds: List[TenureRound]
    stats: Dict[str, object]


def through_path_chains(polylines, *, intern_m: float = SUBSTRATE_INTERN_M
                        ) -> ThroughPathChains:
    """THE PRODUCTION CHAINING over SUBSTRATE POLYLINES — one construction,
    three consumers (the solve, ARM-ACCEPT, the tests).

    ``polylines`` is ``[(key, coords), ...]`` — exactly
    ``string_substrate.StringSubstrate.polylines()``.  Coordinates are
    interned into node identities and :func:`compose_through_paths` (the
    same core the solve runs) does the rest, so an offline acceptance arm
    never needs a copy of the chaining.

    ★ INTERNING IS EXACT-COORDINATE IDENTITY, NOT A TOLERANCE.
    ``intern_m`` (``SUBSTRATE_INTERN_M``, 1 um) is FLOAT-NOISE HYGIENE and
    nothing else; the registry's 0.5 m binds at DECORATION ONLY and
    interning at 0.5 m here is FORBIDDEN (ruling 10).  Endpoints that are
    merely NEAR stay DISTINCT — the 0.86 m near-miss class and the
    substrate's own seam joints are RECOGNITION ONLY: they license no
    geometric extension and no value transport, so composition must never
    join across one.  Identity != membership != bridging.

    Pure and deterministic.  Returns :class:`ThroughPathChains`.
    """
    precision = max(0, int(round(-math.log10(max(intern_m, 1e-12)))))
    ids: Dict[Tuple[float, float], int] = {}
    pos: Dict[int, Tuple[float, float]] = {}
    items: List[Tuple[int, List[int]]] = []
    for ordinal, (_key, coords) in enumerate(polylines):
        nodes: List[int] = []
        for (x, y) in coords:
            k = (round(float(x), precision), round(float(y), precision))
            nid = ids.get(k)
            if nid is None:
                nid = ids[k] = len(ids)
                pos[nid] = (float(x), float(y))
            if not nodes or nodes[-1] != nid:
                nodes.append(nid)
        if len(nodes) >= 2:
            items.append((ordinal, nodes))
    paths, stats = compose_through_paths(items, pos)
    stats["n_polylines_in"] = len(items)
    stats["n_interned_nodes"] = len(ids)
    return ThroughPathChains([(pid, [pos[v] for v in nodes])
                              for pid, nodes in paths], stats,
                             items, pos)


def strings_with_tenure(items, pos, spine_adj, *, bound_m, min_len_m,
                        stops_out=None):
    """★ RULING 3 — EXCLUSIVITY IS AN EMISSION INVARIANT, CHARGED AT
    STRUNG COVERAGE, never at composition time.

    What STANDS: emitted strings PARTITION the substrate they cover — no
    metre of pavement carries two string authorities.  A non-exclusive
    cover is REJECTED as a construction: two authorities over one ground
    is the emit-consensus minting mechanism, and nothing downstream has a
    law for arbitrating two rods on one station.

    What CHANGES: an edge is SPENT only when an EMITTED string actually
    covers it.  Edges of a composed path that the walk cut off, and edges
    ``min_len_m`` then deleted, RETURN to the pool; the identical
    constructor — identical composition, identical walk, identical
    exclusion set — re-runs on the residual subgraph until a round emits
    nothing.  Measured cost of the old composition-time spend: +2,533 m
    of substrate-present owner pavement barred from every string.

    Invariants, all of them binding:
      * TERMINATION IS ARITHMETIC — an emitting round spends >= 1 edge
        from a finite pool and the pool strictly shrinks; a round that
        emits nothing is the fixpoint.  There is no round cap and none
        may be added;
      * DETERMINISM IS INHERITED — the residual is a set difference
        walked in the substrate's OWN stable (first-seen) edge order, so
        every round's composition and walk are the ruled ones;
      * ``min_len_m`` IS NEVER RELAXED, in any round — a residual round
        that re-composes the same sub-min domain emits nothing and stops,
        which is why delete-not-split holds every round;
      * the exclusion set is applied BEFORE this function (ruling 5) and
        is therefore uniform across rounds by construction.

    Pure.  ``items`` is the UNCOMPOSED domain ``[(author_id, [nodes])]``.
    """
    ordered: List[Tuple[Tuple[int, int], int]] = []
    seen: Set[Tuple[int, int]] = set()
    for author, chain in items:
        for a, b in zip(chain, chain[1:]):
            if a == b or a not in pos or b not in pos:
                continue
            key = (a, b) if a < b else (b, a)
            if key not in seen:
                seen.add(key)
                ordered.append((key, author))
    pool = set(seen)
    strings: List[tuple] = []
    sub_min: List[tuple] = []
    rounds: List[TenureRound] = []
    src_counts: Dict[int, int] = {}
    base = 0                 # path ids stay UNIQUE ACROSS ROUNDS (round 1
    while True:              # keeps its ids, so round-1 output is identical)
        round_items = [(author, [key[0], key[1]])
                       for key, author in ordered if key in pool]
        paths, cstats = compose_through_paths(round_items, pos)
        for pid, n_src in (cstats.get("path_source_chains") or {}).items():
            src_counts[base + pid] = n_src
        _rstops = [] if stops_out is not None else None
        got, sub = walk_spine_runs({base + pid: nodes for pid, nodes in paths},
                                   pos, spine_adj, bound_m=bound_m,
                                   min_len_m=min_len_m, stops_out=_rstops)
        if stops_out is not None:
            _emitted_ends = {v for (_a, _b, nd, _l, _c) in got
                             for v in (nd[0], nd[-1])}
            for _row in _rstops:
                _row["round"] = len(rounds)
                # ★ population, stated not implied: a boundary is either an
                # END OF AN EMITTED STRING or a boundary of something the
                # walk discarded.  Conflating them is how this class of
                # instrument lies.
                _row["is_emitted_end"] = _row["node"] in _emitted_ends
                stops_out.append(_row)
        base += len(paths)
        if not got:
            sub_min = sub                    # the converged unstrung mass
            rounds.append(TenureRound(len(rounds), len(paths), 0, 0.0,
                                      len(pool), 0))
            break
        spent: Set[Tuple[int, int]] = set()
        metres = 0.0
        for (_a, _b, nodes, ln, _ci) in got:
            metres += float(ln)
            for u, w in zip(nodes, nodes[1:]):
                spent.add((u, w) if u < w else (w, u))
        rounds.append(TenureRound(len(rounds), len(paths), len(got), metres,
                                  len(pool), len(spent & pool)))
        strings.extend(got)
        before = len(pool)
        pool -= spent
        # arithmetic termination: an emitting round MUST shrink the pool.
        assert len(pool) < before, "tenure round emitted without spending"
    stats = {
        "path_source_chains": src_counts,
        "n_rounds": len(rounds),
        "n_edges_total": len(ordered),
        "n_edges_spent": len(ordered) - len(pool),
        "n_edges_returned": len(pool),
        "rounds": [r._asdict() for r in rounds],
    }
    return TenureResult(strings, sub_min, rounds, stats)


def substrate_fingerprint(apt_tier, osm_tier) -> str:
    """★ RULING 4 — THE ONE FINGERPRINT.  Computed at CAPTURE (phase 1)
    and RECOMPUTED at the hook, which asserts equality.

    Both ends must import THIS function: two implementations of "the same
    hash" is exactly the drift the fingerprint exists to catch.  Content
    only — per-tier counts, metre totals and the canonically-serialised
    coordinates at 1 mm — so it is invariant to container types and
    reproducible across processes.

    ``apt_tier`` is ``[(coords, is_service), ...]``; ``osm_tier`` is
    ``[(way_id, coords), ...]``.  Both in the layout's own metre frame —
    ONE projection; a second ``to_m`` anywhere on this data is the
    measured 0.4 % mixed-projection defect.
    """
    import hashlib as _hashlib
    h = _hashlib.sha256()
    apt = list(apt_tier)
    osm = list(osm_tier)
    h.update(f"apt:{len(apt)}|osm:{len(osm)}".encode())
    total = 0.0
    for coords, is_service in apt:
        pts = [(round(float(x), 3), round(float(y), 3)) for x, y in coords]
        total += math.fsum(math.dist(pts[i], pts[i + 1])
                           for i in range(len(pts) - 1))
        h.update(f"|A{int(bool(is_service))}:{pts}".encode())
    for way_id, coords in osm:
        pts = [(round(float(x), 3), round(float(y), 3)) for x, y in coords]
        total += math.fsum(math.dist(pts[i], pts[i + 1])
                           for i in range(len(pts) - 1))
        h.update(f"|O{way_id}:{pts}".encode())
    h.update(f"|m:{total:.3f}".encode())
    return h.hexdigest()


def substrate_from_carriage(layout, *, station_m, log=None):
    """★ RULING 4, HOOK SIDE — build the substrate ONCE, from the CARRIED
    field ONLY, with the same pure builder every test and instrument uses.

    Reads ``layout.string_substrate_src`` and nothing else: reaching for
    ``layout.apt_taxi_centerlines`` here, or re-reading OSM, are the two
    MEASURED proxies (recognition reassigns the former; the latter does
    not exist in phase 2) and are spec violations.

    Recomputes the carried fingerprint and ASSERTS it, then logs the
    denominator line (pieces / ways / metres / fingerprint prefix) exactly
    as the acceptance arms log theirs — drift shows in the log, not in a
    gate three steps later.  Returns ``None`` when no field was captured
    (gate OFF at phase 1), which is lawful and logged, never silent.

    ``station_m`` is REQUIRED-EXPLICIT, mirroring ``build_string_substrate``
    (0 < station_m <= tol_m; a resolution coarser than the corridor cannot
    resolve it).
    """
    from auto_patch.config import TAUT_STRING_SPINE_TOLERANCE_M
    from .string_substrate import build_string_substrate

    src = getattr(layout, "string_substrate_src", None)
    _say = log if log is not None else (lambda _m: None)
    if not src:
        _say("[S1 substrate] no string_substrate_src carried "
             "(phase-1 capture did not run) — no substrate built")
        return None
    apt = list(src["apt"])
    osm = list(src["osm"])
    want = src.get("fingerprint")
    got = substrate_fingerprint(apt, osm)
    if want != got:
        raise AssertionError(
            f"string_substrate_src fingerprint mismatch: captured {want!r} "
            f"vs recomputed {got!r} — the carried object is not the one "
            f"phase 1 measured")
    sub = build_string_substrate(
        [c for c, _svc in apt], osm,
        tol_m=TAUT_STRING_SPINE_TOLERANCE_M, station_m=station_m)
    st = sub.stats
    _say(f"[S1 substrate] apt {int(st['apt_pieces'])} pieces / "
         f"{st['apt_m']:.1f} m; osm {int(st['osm_ways'])} ways / "
         f"{st['osm_m']:.1f} m; standing {int(st['standing_runs'])} / "
         f"{st['standing_m']:.1f} m; seams {int(st['seams'])}; "
         f"substrate {st['substrate_m']:.1f} m; fp {got[:12]}")
    if not osm:
        _say("[S1 substrate] OSM tier EMPTY — lawful degradation "
             "(no OSM data present), recorded")
    return sub


def decorate_nodes_onto_strings(strings, node_xy, *, identity_m):
    """★ RULING 4 — NODE DECORATION, the hook-side space bridge.

    A graph vertex lies ON an emitted string iff its canonical coordinate
    sits within the REGISTRY'S identity (``layout.canonical_points.tol_m``,
    the pipeline's ONE identity) of that string's polyline; its station is
    the arc-length projection.  Pass that value in — the substrate's 1 um
    interning is float hygiene BELOW this and the 8.0 m bound is
    membership law, never an identity radius.

    DECORATE, NEVER RE-DERIVE: chain topology is frozen at construction.
    Nothing here merges, splits or re-orders a string, no node is moved,
    and an UNMAPPED station is simply not decorated — it is an OFF-NET
    station under the EXISTING §10(v) law (> 20 % of a trunk => report), no
    new constant, nothing snapped, nothing bridged.

    Returns ``{vertex: [(string_index, station_m, offset_m), ...]}`` — ALL
    strings within identity, nearest-first with a deterministic tie-break.

    ★ MULTI-VALUED ON PURPOSE — DO NOT "SIMPLIFY" THIS TO THE NEAREST
    STRING.  Keeping one owner per vertex is the obvious implementation and
    it is WRONG: a vertex on two crossing strings is the §3 SHARED-VERTEX
    case, already ruled, and under ruling 42 a plural-claimed vertex is
    NEVER rewritten — the solve joins the approaching chords under grade
    law.  Dropping the second entry does not fail here; it silently makes a
    plural claim look single and comes back as a wrong ELEVATION several
    steps downstream, with nothing pointing at decoration.  Canonical
    identity is authoritative: reporting both is neither a merge nor
    bridging.
    """
    # ★ THE INDEX WALKS EACH SEGMENT, ONE CELL PER STEP, AND REGISTERS THE
    # 3x3 NEIGHBOURHOOD — NEVER ITS BOUNDING BOX.  The obvious bbox fill is
    # a BUILD-TIME LANDMINE: a 4 km diagonal string spans ~64 M cells at
    # this resolution, which would not have shown up at HECA (short apt
    # pieces) and would have surfaced as an OOM on some other airport.
    # Correctness of the walk: a query point within ``identity_m <= cell``
    # of a segment is within ``cell`` of some step point, hence in that
    # step's cell or one of its 8 neighbours.
    cell = max(float(identity_m), 1.0)
    grid: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    polys = [list(nodes) for nodes in strings]
    for si, coords in enumerate(polys):
        for k in range(len(coords) - 1):
            (x1, y1), (x2, y2) = coords[k], coords[k + 1]
            seg = math.hypot(x2 - x1, y2 - y1)
            steps = int(seg / cell) + 1
            for t in range(steps + 1):
                f = t / steps
                cx = int((x1 + (x2 - x1) * f) // cell)
                cy = int((y1 + (y2 - y1) * f) // cell)
                for ox in (-1, 0, 1):
                    for oy in (-1, 0, 1):
                        bucket = grid.setdefault((cx + ox, cy + oy), [])
                        if not bucket or bucket[-1] != (si, k):
                            bucket.append((si, k))
    out: Dict[int, List[Tuple[int, float, float]]] = {}
    for v, (px, py) in node_xy.items():
        best: Dict[int, Tuple[float, float]] = {}
        for (si, k) in grid.get((int(px // cell), int(py // cell)), ()):
            coords = polys[si]
            (x1, y1), (x2, y2) = coords[k], coords[k + 1]
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 < 1e-18 else max(0.0, min(
                1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
            qx, qy = x1 + t * dx, y1 + t * dy
            d = math.hypot(px - qx, py - qy)
            if d > identity_m:
                continue
            s = math.fsum(math.dist(coords[i], coords[i + 1])
                          for i in range(k)) + t * math.sqrt(L2)
            if si not in best or (d, s) < best[si]:
                best[si] = (d, s)
        if best:
            out[v] = sorted(((si, st, d) for si, (d, st) in best.items()),
                            key=lambda r: (r[2], r[0]))
    return out


def domains_from_walk(strings, pos, priority_of=None) -> List[StringDomain]:
    """Adapt ``walk_spine_runs``' ``(a, b, nodes, ln, chain_id)`` tuples to
    the frozen :class:`StringDomain` (offline arms and fixtures; the
    production driver builds its domains from DECORATION).

    ``stations`` are POLYLINE arc-length along the walked path.
    ``priority_class`` is the strongest (lowest) class among the string's
    own nodes, from ``_scan_roles``' role map.  Pure; order-preserving.
    """
    priority_of = priority_of or {}
    out: List[StringDomain] = []
    for (_a, _b, nodes, _ln, chain_id) in strings:
        verts = list(nodes)
        out.append(StringDomain(
            vertices=verts,
            stations=_stations_of([pos[v] for v in verts]),
            pieces=[chain_id],
            priority_class=min((priority_of.get(v, 3) for v in verts),
                               default=3)))
    return out

# ══════════════════════════════════════════════════════════════════════
# THE CHORD MODEL (rulings 42/43/49) — a string is a STRAIGHT CHORD
# ══════════════════════════════════════════════════════════════════════
# The owner, verbatim: "The string is always a straight chord through
# space, only the end points sit in the middle of the band."
#
# ★ THE WHOLE ELEVATION CONTENT OF A STRING IS TWO NUMBERS.  Between its
# endpoints the chord runs above or below the band FREELY; the solver
# pulls the surface to its cap toward the chord where the chord is
# unreachable — reconciliation is entirely solve-side.  THE STRING NEVER
# BENDS, so a straight line measured against a straight line differs
# LINEARLY and its extremum sits at an END: THE MID-SPAN SAG IS
# UNREPRESENTABLE, exactly as open-terrain crossing is unrepresentable
# under the walk.  Do not reintroduce a tube, a funnel, or a bend.


class EndpointRead(NamedTuple):
    """One endpoint's band read (ruling 49) — value plus its provenance.

    ``mode`` is the READ LAW that fired: ``direct`` (the endpoint is a
    graph node), ``interpolated`` (inside graph coverage, the band field
    read at the true location between two bracketing nodes),
    ``clamped`` (beyond the outermost banded station — the chord extends
    over the tail by its own linearity), or ``none`` (no banded station
    anywhere on the string: GEOMETRY ONLY, never a guessed height).
    """

    value: Optional[float]
    mode: str
    offset_m: float
    lo: float
    hi: float
    bracket: Tuple[int, ...]


def read_endpoint_band_centre(station, banded, *, identity_m):
    """RULING 49 — read the law AT THE TRUE LOCATION.  No snap.

    ``banded`` is this string's own banded stations, ascending:
    ``[(along_station, node, lo, hi), ...]``.  ``station`` is the
    endpoint's along-station on the same axis.

    ★ SNAPPING THE ENDPOINT TO A GRAPH NODE IS REJECTED: it moves
    geometry the chord model froze as RETAINED, it needs a radius
    constant (the shipped-constant trap), and for the far mode a snap IS
    the clamp wearing a different name while also mutating plan geometry
    mid-acceptance.  Interpolating is a READ of a law field at a point —
    nothing crosses a gap, no identity is minted, no geometry moves.

    Mode 2 measured EMPTY at HECA (108 direct / 0 interpolated / 62
    clamped).  That is a HECA fact, not a general one — the mode is
    implemented and tested regardless.
    """
    if not banded:
        return EndpointRead(None, "none", 0.0, -INF, INF, ())
    # (1) DIRECT — the endpoint IS a banded node.
    best = min(banded, key=lambda r: abs(r[0] - station))
    if abs(best[0] - station) <= identity_m:
        return EndpointRead(0.5 * (best[2] + best[3]), "direct", 0.0,
                            best[2], best[3], (best[1],))
    # (3) BEYOND-GRAPH — clamp to the outermost banded station; the chord
    # extends over the tail by its own linearity (two points define it
    # everywhere, extension adds no information) and the tail is
    # DELIVERY-MOOT: no nodes exist there, so the hook rewrites nothing.
    if station < banded[0][0]:
        r = banded[0]
        return EndpointRead(0.5 * (r[2] + r[3]), "clamped",
                            banded[0][0] - station, r[2], r[3], (r[1],))
    if station > banded[-1][0]:
        r = banded[-1]
        return EndpointRead(0.5 * (r[2] + r[3]), "clamped",
                            station - banded[-1][0], r[2], r[3], (r[1],))
    # (2) BETWEEN-NODE — interpolate [lo, hi] to the true along-station.
    for k in range(len(banded) - 1):
        s0, v0, lo0, hi0 = banded[k]
        s1, v1, lo1, hi1 = banded[k + 1]
        if s0 <= station <= s1:
            t = 0.0 if s1 - s0 < 1e-9 else (station - s0) / (s1 - s0)
            lo = lo0 + (lo1 - lo0) * t
            hi = hi0 + (hi1 - hi0) * t
            return EndpointRead(0.5 * (lo + hi), "interpolated", 0.0,
                                lo, hi, (v0, v1))
    r = banded[-1]
    return EndpointRead(0.5 * (r[2] + r[3]), "clamped", 0.0, r[2], r[3],
                        (r[1],))


def filter_pins_by_grade_law(pins, spine_adj, *, hard=(), endpoint_depth=None,
                             eps: float = 1e-9):
    """★ RULING 52 — THE CHORD IS NEVER BENT BY LAW; THE GRIP IS.

    Chord targets become Dirichlet pins, and pins join the solve's
    ``anchors`` set — which means fairing and the exact cap projection can
    no longer drive a both-pinned pair to its cap.  So the pin SET is
    law-filtered first: **no pair remains both-pinned where the chord
    grade between the pinned values exceeds that pair's cap budget**
    (strict ``>`` at the existing 1e-9 audit epsilon — no new constant).

    The chord itself is NEVER modified and never clipped: it stays gate
    (A)'s object, a pure straight ideal.  43(f) reads: telemetry for the
    CHORD, law for the GRIP.  Releasing a pin does not move a value — it
    hands that station back to the solver, which then rides its cap toward
    the chord, which is the owner's own sentence (grade law overrules the
    string when needed) applied exactly where "when needed" is true.

    Release policy, all of it:
      * MINIMAL — no released pin can be re-pinned without re-creating an
        over-cap pair (verified by a re-admission pass, not merely by a
        greedy stopping rule);
      * DETERMINISTIC — same input, same output;
      * ENDPOINT-PROTECTIVE — release the member FARTHER from its string's
        nearer endpoint (gate (A) reads endpoints), so within a run of
        consecutive over-cap pairs the INTERIOR pins go first;
      * ties break on stable node id;
      * a pair whose BOTH ends are law anchors is NEVER released — that is
        the projection's pre-existing genuine-step contract, not ours.

    Returns ``(kept_pins, releases)``; each release is a GRIP-YIELD
    WITNESS naming the pair, cap, chord grade, excess, released end and
    the rule that fired.
    """
    hard = set(hard)
    depth = endpoint_depth or {}
    # over-cap pairs among BOTH-pinned vertices
    over: List[tuple] = []
    seen: Set[Tuple[int, int]] = set()
    for i, lst in (spine_adj or {}).items():
        if i not in pins:
            continue
        for e in lst:
            j = e[0] if isinstance(e, (tuple, list)) else e
            budget = float(e[1]) if isinstance(e, (tuple, list)) and len(e) > 1 \
                else 0.0
            if j not in pins:
                continue
            key = (i, j) if i < j else (j, i)
            if key in seen:
                continue
            seen.add(key)
            dz = abs(pins[key[0]] - pins[key[1]])
            if dz > budget + eps:
                if key[0] in hard and key[1] in hard:
                    continue          # pre-existing genuine step: not ours
                over.append((key, budget, dz))
    if not over:
        return dict(pins), []

    incident: Dict[int, Set[Tuple[int, int]]] = {}
    info: Dict[Tuple[int, int], tuple] = {}
    for key, budget, dz in over:
        info[key] = (budget, dz)
        for v in key:
            if v not in hard:         # a law anchor is never a candidate
                incident.setdefault(v, set()).add(key)

    def _rank(v):
        # most pairs covered first; then MOST INTERIOR (farthest from its
        # string's nearer endpoint); then stable id.
        return (-len(incident.get(v, ())), -float(depth.get(v, 0.0)), v)

    remaining = set(info)
    released: List[int] = []
    while remaining:
        cands = sorted({v for k in remaining for v in k if v in incident},
                       key=_rank)
        if not cands:
            break                     # only law-anchor pairs left: not ours
        v = cands[0]
        released.append(v)
        remaining -= incident[v]
    # MINIMALITY: re-admit any release that is no longer necessary (the
    # greedy may over-release when a later pick covered the same pair).
    kept_released = list(released)
    for v in sorted(released, key=lambda x: (float(depth.get(x, 0.0)), x)):
        trial = set(kept_released) - {v}
        if all(k[0] in trial or k[1] in trial for k in info):
            kept_released = sorted(trial)
    releases = []
    for v in kept_released:
        for key in sorted(incident.get(v, ())):
            budget, dz = info[key]
            releases.append({
                "pair": list(key), "released": v, "cap_budget_m": budget,
                "chord_dz_m": dz, "excess_m": dz - budget,
                "rule": "grade_law_over_cap"})
    kept = {v: z for v, z in pins.items() if v not in set(kept_released)}
    return kept, releases


def compass_ends(a, b, *, axis: str = "auto"):
    """★ COMPASS LABELS FOR A CHORD'S TWO ENDS — emitted, never inferred.

    A string's endpoint order is WALK ORDER: it follows the composed
    path's traversal, which is seeded by edge id and carries no
    geographic meaning whatsoever.  Reading "start" as "north" transposed
    chord 1's two endpoint values in a report and cost a round of
    investigation (the chord appeared to fall north->south, contradicting
    the owner's expectation; corrected, band centre rises +2.11 m
    north->south against his +2.00 and the runway's +1.57).  So the
    labels are COMPUTED FROM THE COORDINATES and shipped in the artifact:
    no consumer should ever have to infer geography from our iteration
    order again.

    The layout's metre frame is anchor-relative equirectangular — x is
    EASTING, y is NORTHING — so the comparison is direct.

    ``axis="ns"`` labels north/south, ``"ew"`` east/west, and ``"auto"``
    PREFERS NORTH/SOUTH — that is how every taxiway on this line is named
    (chord 1 runs SW->NE, and a dominant-axis rule would have called its
    ends "east" and "west", which is true and useless).  East/west is the
    fallback for a chord whose ends share a latitude.  ``None`` when the
    requested axis is degenerate.  Returns ``(label_of_a, label_of_b)``.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    ns = (("south", "north") if dy >= 0 else ("north", "south")) \
        if abs(dy) > 1e-6 else None
    ew = (("west", "east") if dx >= 0 else ("east", "west")) \
        if abs(dx) > 1e-6 else None
    if axis == "ns":
        return ns
    if axis == "ew":
        return ew
    return ns or ew or ("a", "b")


def chord_station(point, a, u):
    """Along-station of ``point`` on the chord ``a`` with unit dir ``u``."""
    return (point[0] - a[0]) * u[0] + (point[1] - a[1]) * u[1]


def chord_targets(a, b, z_a, z_b, vertices, pos):
    """The hook's value law: z LINEAR IN ALONG-STATION between the two
    endpoint values.  Two numbers give every node on the route a target.

    Returns ``{vertex: z}``.  A degenerate chord yields the mean.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return {v: 0.5 * (z_a + z_b) for v in vertices if v in pos}
    u = (dx / L, dy / L)
    return {v: z_a + (z_b - z_a) * (chord_station(pos[v], a, u) / L)
            for v in vertices if v in pos}


# ══════════════════════════════════════════════════════════════════════
# S1 — the per-string constructor (spec §2 steps 1-5)
# ══════════════════════════════════════════════════════════════════════


#: Pavement role -> class.  §3's ORDERING retired with its value
#: machinery (ruling 42); the class survives as inventory telemetry only.
_PRIORITY_BY_ROLE: Dict[str, int] = {}


def _priority_role_map() -> Dict[str, int]:
    """Role -> §3 priority class, built once from the layout role names
    (never from literals at a call site: renaming a ``ROLE_*`` value must
    not silently change classing)."""
    global _PRIORITY_BY_ROLE
    if not _PRIORITY_BY_ROLE:
        from auto_patch.layout import (ROLE_CROSS_CONNECTOR,
                                       ROLE_PRIMARY_PARALLEL,
                                       ROLE_SECONDARY_PARALLEL, ROLE_STUB)
        _PRIORITY_BY_ROLE = {
            ROLE_PRIMARY_PARALLEL: 1,
            ROLE_SECONDARY_PARALLEL: 1,
            ROLE_CROSS_CONNECTOR: 2,
            ROLE_STUB: 2,
        }
    return _PRIORITY_BY_ROLE


def _scan_roles(layout, bucket_to_idx, n: int):
    """One pass over the shapes of interest.

    Returns ``(priority_of_node, service_nodes)``.  Only the roles that
    change an answer are scanned — junction/apron shapes (the bulk of a
    global-slice layout) are skipped, so this stays cheap.
    """
    from auto_patch.layout import ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD
    priority_by_role = _priority_role_map()
    service_roles = (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
    wanted = set(priority_by_role) | set(service_roles)
    priority_of: Dict[int, int] = {}
    service_nodes: Set[int] = set()
    cps = layout.canonical_points
    for shape in getattr(layout, "shapes", ()):
        role = getattr(shape, "role", None)
        if role not in wanted:
            continue
        poly = getattr(shape, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        is_service = role in service_roles
        rank = priority_by_role.get(role, 3)
        for (x, y) in poly.exterior.coords:
            idx = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if idx is None or idx >= n:
                continue
            if is_service:
                service_nodes.add(idx)
            elif rank < priority_of.get(idx, 3):
                priority_of[idx] = rank
    return priority_of, service_nodes


def write_string_sidecar(layout, path=None) -> Optional[str]:
    """Serialise the ``string_domains`` summary to the witness sidecar.

    Idempotent and safe to call more than once: the LAST call wins, which
    is the point — the grip filter stamps its disposition onto the summary
    after the constructor returns, so the file must be written after that,
    not during construction.  ``None`` when ``O4_STRING_WITNESS_DUMP`` is
    unset (no file, no cost).
    """
    import json as _json
    import os as _os

    dump = path or _os.environ.get("O4_STRING_WITNESS_DUMP")
    if not dump:
        return None
    from ..node_space import store_of
    summary = (store_of(layout).raw("string_domains") or {}).get("__summary__")
    if summary is None:
        return None
    with open(str(dump) + ".domains.json", "w") as fh:
        _json.dump(summary, fh, indent=1, default=str)
    import csv as _csv
    # THE ENDPOINT WITNESS (ruling 46) — the bend CSV retired with the
    # bends; a chord's two reads ARE its whole elevation content.
    with open(dump, "w", newline="") as fh:
        writer = _csv.writer(fh)
        writer.writerow(["string", "which", "end_label", "mode", "value",
                         "lo", "hi", "offset_m", "bracket",
                         "n_banded_stations"])
        for w in summary.get("endpoint_witness", ()):
            writer.writerow([w["string"], w["which"], w["end_label"],
                             w["mode"], w["value"], w["lo"], w["hi"],
                             w["offset_m"],
                             " ".join(str(x) for x in w["bracket"]),
                             w["n_banded_stations"]])
    return str(dump)


def construct_taut_strings(layout, G, *, elev, bucket_to_idx, n, node_band,
                           hard, corridor_pieces, junction_adj,
                           cap_of_segment,
                           hard_cat=None,
                           have_initial=None) -> Dict[int, float]:
    """S1 — Stage 0 assembly, §3 ordering, and the per-string constructor.

    PURE with respect to the solve: ``elev`` and the layout geometry are
    READ, never written.  The return value is the full rewrite map
    ``vertex -> taut z`` (uncrowned, the space ``solve_route_profile``
    works in); an empty map means there is nothing to apply.  Applying it
    is the caller's single gated statement.

    ``hard`` is the clause-1 anchor set — the values the string may not
    move (runway/CIFP, tile-seam pins, runway joins, building spine
    seats).  NOTE for callers: at the rod-mint point ``base_hard`` has
    already absorbed the whole phase-A spine freeze, so passing that set
    would make every strung vertex an anchor and the hook a no-op; pass
    the TRUTH set instead.

    ``corridor_pieces`` is ``_build_spine_corridors``' output verbatim
    (node-index lists) — read-only; ``junction_adj`` is the spine
    adjacency ``{i: [(j, budget), ...]}``, used for junction degree in the
    inventory; ``cap_of_segment(a, b) -> float`` gives the per-segment
    longitudinal law cap.

    Mints ``string_bends`` (bend witnesses) and ``string_domains`` (the
    Stage-0 assembly inventory) into the node-space store, and dumps the
    witnesses as CSV when ``O4_STRING_WITNESS_DUMP`` names a path.

    ``hard_cat`` / ``have_initial`` — PROBE B (docs/specs/taut-string-probe-
    spec.md §2): pure passengers.  Neither is read by any code path here;
    both are written verbatim into the ``O4_STRING_STATE_DUMP`` pickle so
    the hook-entry band violations can be attributed OFFLINE to the writer
    that made them.  ``hard_cat`` is the solve's ``_hard_cat`` (a COPY,
    made by the caller) — it names the stamp category of every hard node;
    ``have_initial`` is ``_seed_elevations``' third return.
    ⚠ MEASURED 2026-08-01: ``have_initial`` is NOT a layout-warm-start vs
    DEM-sample discriminator (the probe spec §2.2 assumed it was).  Every
    seeding branch in ``_seed_elevations`` sets it — warm start, DEM
    sample AND the nearest-hard backfill (solver_primitives.py:3021,
    :3040) — so it is a COVERAGE flag and comes out ``True`` for every
    node (131,753 of 131,753 at HECA).  It ships as the spec asks; do not
    read a P0 sub-class out of it without re-deriving one.
    ``None`` (the default) ⇒ the key is absent from the pickle.
    """
    import os as _os

    from auto_patch.config import (TAUT_STRING_MIN_STRING_M,
                                    TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M,
                                    TAUT_STRING_SPINE_TOLERANCE_M)
    from .string_substrate import clip_strings_to_runways
    from ..node_space import store_of

    pos = getattr(G, "pos", None) or {}
    priority_of, service_nodes = _scan_roles(layout, bucket_to_idx, n)
    hard_set = set(hard)

    # ══ STAGE 0 — THE CARRIED SUBSTRATE (ruling 8: the processed-tier
    # domain is DELETED; there is no selection flag between paths at any
    # point in time, and an empty carried field is a lawful, logged no-op,
    # NEVER a fallback) ═══════════════════════════════════════════════
    _log = []
    _sub = substrate_from_carriage(layout, station_m=SUBSTRATE_STATION_M,
                                   log=_log.append)
    if _os.environ.get("O4_STEP_DEBUG") == "1":
        for _m in _log:
            print("    " + _m)
    if _sub is None:
        return {}
    # RULING 5 at the tier: service apt pieces COUNT for membership and
    # coverage (apt.dat presence is presence — the committed sentence is
    # locative) but are EXCLUDED FROM THE STRUNG DOMAIN.  Exclusion
    # restricts what may be STRUNG, never what COVERS, and it precedes
    # composition — never after it.
    _svc_apt = {i for i, (_c, _is_svc)
                in enumerate(layout.string_substrate_src["apt"]) if _is_svc}
    _domain_polys = [(k, c) for k, c in _sub.polylines()
                     if not (k.startswith("apt:") and int(k[4:]) in _svc_apt)]
    _tp = through_path_chains(_domain_polys)
    # The substrate is its own connectivity: a composed path's consecutive
    # nodes ARE substrate edges, so this adjacency is the walk's spine-gap
    # test in substrate space (P7's holes are absences of edges here).
    _sadj: Dict[int, List[int]] = {}
    for _pid, _ids in _tp.items:
        for _a, _b in zip(_ids, _ids[1:]):
            _sadj.setdefault(_a, []).append(_b)
            _sadj.setdefault(_b, []).append(_a)
    # ★ RULING 3: tenure — compose, walk, emit; edges the walk cut or
    # ``min_len`` deleted RETURN to the pool and the identical constructor
    # re-runs on the residual until a round emits nothing.
    # ★ ONE margin, the owner's ``TAUT_STRING_SPINE_TOLERANCE_M`` (8.0).
    _boundaries: List[dict] = []
    _tenure = strings_with_tenure(
        _tp.items, _tp.pos, _sadj, bound_m=TAUT_STRING_SPINE_TOLERANCE_M,
        min_len_m=TAUT_STRING_MIN_STRING_M, stops_out=_boundaries)
    walk_sub_min = _tenure.sub_min
    # ── THE OWNER'S RUNWAY CLIP (2026-07-31, verbatim: "Use the runway
    # outline to clip any strings, discarding anything inside the runway,
    # and if the remainder is less than 50m just drop it, the taxiway's
    # grade will be smooth enough without it").
    # ★ THE EMITTED STRINGS ARE CLIPPED, NOT THE SUBSTRATE — Fable's bind
    # point, required by committed design: §2 step 1 seats runway-crossing
    # values as clause-1 anchors ON THE CHAIN, so the chain must SPAN the
    # crossing.  Clipping the substrate would sever every crossing into two
    # independently-solving strings exactly where continuity is hardest
    # law.  Do not "simplify" this back into the substrate stage.
    # ★ THE OUTLINE IS THE PIPELINE'S OWN OBJECT, never one we pick:
    # ``layout.runway_union`` IS the ruled shoulder-absorbed union (built
    # in phase 2, long before the solve).  The callee keeps the polygon
    # REQUIRED-EXPLICIT and raises on None — that guard is deliberate and
    # is not defeated here.
    # ★ Clipped ONE STRING AT A TIME so every remainder keeps the identity
    # of its PRE-CLIP chord: ruling 43(e) — clip remainders inherit THE ONE
    # chord defined by the pre-clip endpoints, which is ruling 18's
    # collinearity now true by definition.  The census is accumulated, so
    # the telemetry is identical to the batch call.
    _clip_strings: List[tuple] = []
    _chord_of_string: Dict[int, tuple] = {}
    _clip_dropped: List[tuple] = []
    _clip_band: List[tuple] = []
    _clip_stats = {"clipped": 0.0, "dropped": 0.0, "dropped_m": 0.0,
                   "in_duty_band": 0.0, "split_in_two": 0.0}
    for _s in _tenure.strings:
        _one = clip_strings_to_runways(
            [_s], _tp.pos, layout.runway_union,
            min_remainder_m=TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M)
        if len(_one.strings) != 1 or _one.strings[0][2] != _s[2]:
            # the clip created boundaries of its own: a remainder end that
            # is not the pre-clip string's end was authored by the RUNWAY
            # OUTLINE, not by the walk.
            for _t in _one.strings:
                for _end in (_t[2][0], _t[2][-1]) if _t[2] else ():
                    if _end not in (_s[2][0], _s[2][-1]):
                        _boundaries.append({
                            "chain": _s[4], "node": _end, "reason": "clip",
                            "x": _tp.pos[_end][0], "y": _tp.pos[_end][1],
                            "round": -1, "is_emitted_end": True})
        for _t in _one.strings:
            _chord_of_string[len(_clip_strings)] = (_s[0], _s[1])
            _clip_strings.append(_t)
        _clip_dropped.extend(_one.dropped)
        _clip_band.extend(_one.in_duty_band)
        for _k in _clip_stats:
            _clip_stats[_k] += float(_one.stats.get(_k, 0.0))
    _string_polys = [[_tp.pos[v] for v in nodes]
                     for (_a, _b, nodes, _ln, _ci) in _clip_strings]

    # ── DECORATION (ruling 4/10): the substrate stays coordinate-space;
    # graph vertices attach to it at the REGISTRY'S 0.5 m — the pipeline's
    # ONE identity, and the only place it binds.  The substrate's 1 um
    # interning is float hygiene BELOW it; the 8.0 m bound is membership
    # law, never an identity radius.  DECORATE, NEVER RE-DERIVE.
    _identity_m = float(getattr(layout.canonical_points, "tol_m", 0.5))
    _eligible = {v: xy for v, xy in pos.items()
                 if v < n and v not in service_nodes}
    _dec = decorate_nodes_onto_strings(_string_polys, _eligible,
                                       identity_m=_identity_m)
    _n_multi = sum(1 for _r in _dec.values() if len(_r) > 1)
    _by_string: Dict[int, List[Tuple[float, int, float]]] = {}
    for _v, _rows_v in _dec.items():
        for (_si, _st, _off) in _rows_v:
            _by_string.setdefault(_si, []).append((_st, _v, _off))
    domains: List[StringDomain] = []
    _dec_offsets: List[float] = []
    for _si in sorted(_by_string):
        _rows = sorted(_by_string[_si])
        _verts = [r[1] for r in _rows]
        _stations = [r[0] for r in _rows]
        _dec_offsets.extend(r[2] for r in _rows)
        if len(_verts) < 2:
            continue
        # STATIONS ARE POLYLINE ARC-LENGTH along the string the vertex was
        # decorated onto (the gate-currency ruling) — the projection's own
        # arc length, not a re-measure through the graph.
        domains.append(StringDomain(
            vertices=_verts, stations=_stations, pieces=[_si],
            priority_class=min((priority_of.get(v, 3) for v in _verts),
                               default=3)))
    _path_chains = _tenure.stats["path_source_chains"]

    # ══ THE CHORD MODEL (rulings 42/43/49) ═══════════════════════════
    # Per string: read the band centre at each END, then give every
    # claimed vertex the LINEAR value between them.  No tube, no
    # propagation, no funnel, no bend, no fallback class — a chord is
    # always constructible, so infeasibility can never again be a
    # string-construction defect; it is a solve-side law question.
    rewrites: Dict[int, float] = {}
    all_defects: List[StringDefect] = []
    inventory: List[dict] = []
    endpoint_witness: List[dict] = []
    _claims: Dict[int, int] = {}
    for _v, _rows_v in _dec.items():
        _claims[_v] = len(_rows_v)
    n_geometry_only = 0
    n_plural_skipped = 0
    _plural_ledger: List[int] = []
    _mode_census: Dict[str, int] = {}
    _pin_depth: Dict[int, float] = {}
    _pin_rows: List[dict] = []
    _departures: List[dict] = []

    for dom in domains:
        _si = dom.pieces[0]
        # ★ RULING 43(e): clip remainders inherit THE ONE chord, defined
        # by the PRE-CLIP endpoints — collinearity now true by definition.
        _a, _b = _chord_of_string.get(_si, (None, None))
        if _a is None:
            continue
        _dx, _dy = _b[0] - _a[0], _b[1] - _a[1]
        _L = math.hypot(_dx, _dy)
        _u = (_dx / _L, _dy / _L) if _L > 1e-9 else (1.0, 0.0)
        # this string's own banded stations, ascending
        _banded = []
        for _v in dom.vertices:
            _band = (node_band[_v] if (node_band is not None
                                       and _v < len(node_band)) else None)
            if _band is None:
                continue
            _lo, _hi = float(_band[0]), float(_band[1])
            if _lo > _hi:                 # quarantine signal: not a read
                continue
            _banded.append((chord_station(pos[_v], _a, _u), _v, _lo, _hi))
        _banded.sort()
        # ── DEPARTURE LEDGER (smooth bow vs localized excursion) ───────
        # Perpendicular offset of every strung vertex from its own
        # string's chord.  Already computed geometry, emitted rather than
        # inferred: the offline walk has diverged from production three
        # times, so a 25 m wander must be attributable to substrate pieces
        # from the BUILD, not reconstructed.
        for _v in dom.vertices:
            _dev_s = chord_station(pos[_v], _a, _u)
            _departures.append({
                "string": _si, "vertex": _v,
                "along_station_m": round(_dev_s, 3),
                "perp_offset_m": round(
                    abs(-(pos[_v][0] - _a[0]) * _u[1]
                        + (pos[_v][1] - _a[1]) * _u[0]), 4)})
        _r0 = read_endpoint_band_centre(chord_station(_a, _a, _u), _banded,
                                        identity_m=_identity_m)
        _r1 = read_endpoint_band_centre(chord_station(_b, _a, _u), _banded,
                                        identity_m=_identity_m)
        # ★ Endpoint order is WALK ORDER and carries NO geography; the
        # compass label is computed and SHIPPED so no consumer infers it.
        _lab0, _lab1 = compass_ends(_a, _b)
        _ew = compass_ends(_a, _b, axis="ew")
        for _r, _which, _lab in ((_r0, "start", _lab0), (_r1, "end", _lab1)):
            _mode_census[_r.mode] = _mode_census.get(_r.mode, 0) + 1
            endpoint_witness.append({
                "string": _si, "which": _which, "end_label": _lab,
                "mode": _r.mode,
                "value": _r.value, "lo": _r.lo, "hi": _r.hi,
                "offset_m": round(_r.offset_m, 3),
                "bracket": list(_r.bracket),
                "n_banded_stations": len(_banded)})
        if _r0.value is None or _r1.value is None:
            # RULING 43(c): no banded station anywhere ⇒ GEOMETRY ONLY,
            # inert and DECLARED — never a guessed height.
            n_geometry_only += 1
            all_defects.append(StringDefect(
                kind="geometry_only", chain_id=_si, station=0.0,
                vertex=dom.vertices[0] if dom.vertices else -1,
                lo=0.0, hi=0.0, author_lo="band=none", author_hi="band=none",
                detail=("string has no banded station: geometry emitted, "
                        "no elevation content (census-1 extraction class)")))
            _chord_grade = 0.0
        else:
            _targets = chord_targets(_a, _b, _r0.value, _r1.value,
                                     dom.vertices, pos)
            for _v in _targets:
                _st = chord_station(pos[_v], _a, _u)
                # distance from the NEARER endpoint: gate (A) reads
                # endpoints, so the grip filter releases interior pins
                # first (ruling 52, endpoint-protective).
                _pin_depth[_v] = min(abs(_st), abs(_L - _st))
                # ★ THE PIN LEDGER.  Production is the ONLY place that
                # knows which vertices were pinned and to what; an offline
                # re-walk of the substrate has now failed to reproduce it
                # three times (89 strings vs production's 71).  So the
                # instrument ships FROM THE BUILD: with these rows,
                # ``max |emitted - chord|`` at kept pins is a one-line
                # check on the next build instead of a reconstruction.

            for _v, _z in _targets.items():
                # ★ RULING 42, unconditional: the hook rewrites only
                # vertices claimed by exactly ONE string.  A plural-claimed
                # vertex is NEVER rewritten — the solve joins the
                # approaching chords under grade law.  This replaces §3's
                # whole value machinery (one-value policy, hard-anchor
                # promotion, trunk-first ordering).
                if _claims.get(_v, 1) > 1:
                    n_plural_skipped += 1
                    _plural_ledger.append(_v)
                    continue
                if _v in hard_set:
                    continue              # anchors are never rewritten
                rewrites[_v] = _z
                # ★ ONE ROW PER ACTUAL TARGET, recorded HERE and not at
                # evaluation: a row minted before the plural-claim and
                # hard skips would make "released" mean two different
                # things (never offered vs grip-released) and the
                # disposition column would be quietly wrong.
                _pin_rows.append({
                    "vertex": _v, "string": _si,
                    "station_m": round(chord_station(pos[_v], _a, _u), 4),
                    "z": _z,
                    "depth_m": round(_pin_depth.get(_v, 0.0), 4),
                    "grip": "offered"})
            _chord_grade = (abs(_r1.value - _r0.value) / _L
                            if _L > 1e-9 else 0.0)

        _len_m = _L
        inventory.append({
            "chain_id": _si,
            "priority_class": dom.priority_class,
            "n_pieces": len(dom.pieces),
            "pieces": list(dom.pieces),
            "n_vertices": len(dom.vertices),
            "n_source_chains": _path_chains.get(_si, 0),
            "length_m": _len_m,
            "chord_extent_m": _len_m,
            # the chord IS the straight line, so polyline excess is zero
            # by construction; the field stays for schema continuity.
            "polyline_excess_m": 0.0,
            "polyline_excess_pct": 0.0,
            "first_vertex": dom.vertices[0] if dom.vertices else -1,
            "last_vertex": dom.vertices[-1] if dom.vertices else -1,
            "z_start": _r0.value,
            "z_end": _r1.value,
            # geography, computed from the coordinates -- never from the
            # traversal order that produced z_start / z_end
            "label_start": _lab0,
            "label_end": _lab1,
            f"z_{_lab0}": _r0.value,
            f"z_{_lab1}": _r1.value,
            # both axes when both are defined: a SW->NE trunk has a real
            # north end AND a real east end, and no reader should have to
            # pick which one our dominant-axis rule happened to choose.
            **({f"z_{_ew[0]}": _r0.value, f"z_{_ew[1]}": _r1.value}
               if _ew and _ew[0] not in (_lab0, _lab1) else {}),
            "read_mode_start": _r0.mode,
            "read_mode_end": _r1.mode,
            "endpoint_offset_start_m": round(_r0.offset_m, 3),
            "endpoint_offset_end_m": round(_r1.offset_m, 3),
            "n_banded_stations": len(_banded),
            # ★ RULING 43(f): chord grade vs cap is TELEMETRY, NOT LAW.
            # A steeper-than-cap chord is a lawful preference; the surface
            # rides its cap toward it.  Never gate on this.
            "chord_grade": _chord_grade,
            "n_offnet": len(dom.vertices) - len(_banded),
            "start_degree": len(junction_adj.get(dom.vertices[0], ()))
                            if dom.vertices else 0,
            "end_degree": len(junction_adj.get(dom.vertices[-1], ()))
                          if dom.vertices else 0,
        })

    # ── artifacts (spec §2.5 / §4) ────────────────────────────────────
    _tot_poly = sum(float(r["length_m"]) for r in inventory)
    _tot_along = _tot_poly
    _longest = max((float(r["length_m"]) for r in inventory), default=0.0)
    key_of = {i: k for k, i in bucket_to_idx.items()}
    store = store_of(layout)
    # ★ BEND WITNESSES RETIRE WITH THE BENDS (ruling 44): a chord cannot
    # bend, so there is nothing to witness.  The ENDPOINT WITNESS replaces
    # them — per string, the two reads that ARE its elevation content.
    ep_payload: Dict[object, list] = {}
    for _w in endpoint_witness:
        _bk = _w.get("bracket") or []
        _key = key_of.get(_bk[0]) if _bk else None
        if _key is None:
            continue
        ep_payload.setdefault(_key, []).append(_w)
    store.mint("string_endpoints", "keyset", ep_payload, replace=True)

    domains_payload: Dict[object, object] = {
        "__summary__": {
            "n_corridor_pieces_in": len(corridor_pieces),
            # ── the chord model (rulings 42/43/49) ────────────────────
            "value_model": "straight_chord",
            "endpoint_read_modes": dict(_mode_census),
            "n_geometry_only_strings": n_geometry_only,
            "n_plural_claim_skipped": n_plural_skipped,
            "plural_claim_ledger": sorted(set(_plural_ledger))[:400],
            "endpoint_witness": endpoint_witness[:400],
            # per-pin distance from its string's nearer endpoint — the
            # grip filter's endpoint-protective ordering (ruling 52).
            "pin_depth": _pin_depth,
            # THE PIN LEDGER, complete and unclipped: vertex, string,
            # along-station, chord target, and the grip disposition the
            # caller stamps after the law filter runs.
            "pins": _pin_rows,
            "n_targets": len(_pin_rows),
            # one row per STRUNG vertex; max is the headline the arm reads
            # every boundary the WALK + CLIP created, with its author:
            # turn / gap / route_end / consensus / tenure / clip.  The
            # turn-vs-tenure distinction decides whose defect a split is.
            "walk_boundaries": _boundaries,
            "n_walk_boundaries": len(_boundaries),
            "boundary_reasons": {_r: sum(1 for _b in _boundaries
                                         if _b["reason"] == _r)
                                 for _r in sorted({_b["reason"] for _b
                                                   in _boundaries})},
            "departures": _departures,
            "n_departure_rows": len(_departures),
            "max_departure_m": max((r["perp_offset_m"] for r in _departures),
                                   default=0.0),
            # ── the DENOMINATOR LINE, in the artifact as well as the log
            # (ruling 4): which substrate, at which resolution, under
            # which identities.  Mixed-definition tables are forbidden
            # unlabelled (ruling 10), so every identity is named here.
            "source": "string_substrate_src",
            "stage0_source": "walk_spine_runs",
            "substrate_fingerprint": layout.string_substrate_src.get(
                "fingerprint"),
            "substrate_station_m": SUBSTRATE_STATION_M,
            "substrate_intern_m": SUBSTRATE_INTERN_M,
            "decoration_identity_m": _identity_m,
            "substrate_stats": dict(_sub.stats),
            "n_apt_pieces": int(_sub.stats.get("apt_pieces", 0)),
            "n_apt_service_excluded": len(_svc_apt),
            "n_substrate_polylines": len(_domain_polys),
            "spine_tolerance_m": TAUT_STRING_SPINE_TOLERANCE_M,
            "min_string_m": TAUT_STRING_MIN_STRING_M,
            "n_strings": len(domains),
            "n_chains_walked": (_tenure.rounds[0].n_paths
                                if _tenure.rounds else 0),
            "n_domain_runs": len(_tp.items),
            # ── ruling 3 tenure telemetry ─────────────────────────────
            "n_tenure_rounds": _tenure.stats["n_rounds"],
            "n_edges_total": _tenure.stats["n_edges_total"],
            "n_edges_spent": _tenure.stats["n_edges_spent"],
            "n_edges_returned": _tenure.stats["n_edges_returned"],
            "tenure_rounds": _tenure.stats["rounds"],
            # ── ruling 2: the chain domain is maximal through-paths ────
            "chain_domain": "through_paths",
            "n_chains_in": len(_domain_polys),
            # ── the owner's runway clip ───────────────────────────────
            "clip_min_remainder_m": TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M,
            "n_strings_pre_clip": len(_tenure.strings),
            "n_strings_clipped": int(_clip_stats["clipped"]),
            "n_remainders_dropped": int(_clip_stats["dropped"]),
            "remainders_dropped_m": _clip_stats["dropped_m"],
            "n_crossings_split_in_two": int(_clip_stats["split_in_two"]),
            # [50, 100) SURVIVES — the two owner constants govern different
            # moments (100 = construction existence, pre-clip; 50 =
            # emission remainder, post-clip).  Labelled telemetry for the
            # owner, never a gate and never our decision.
            "n_remainders_in_duty_band": int(_clip_stats["in_duty_band"]),
            "remainders_in_duty_band": [
                {"chain": _s[4], "remainder_m": round(float(_L), 2),
                 "original_m": round(float(_s[3]), 2)}
                for _s, _L in _clip_band],
            "remainders_dropped": [
                {"chain": _s[4], "remainder_m": round(float(_L), 2),
                 "original_m": round(float(_s[3]), 2)}
                for _s, _L in _clip_dropped],
            # ── decoration census (ruling 4 audit) ────────────────────
            "n_nodes_eligible": len(_eligible),
            "n_nodes_decorated": len(_dec),
            "decorated_fraction": (len(_dec) / len(_eligible)
                                   if _eligible else 0.0),
            "n_nodes_on_two_strings": _n_multi,
            "decoration_max_offset_m": max(_dec_offsets, default=0.0),
            "decoration_mean_offset_m": (
                math.fsum(_dec_offsets) / len(_dec_offsets)
                if _dec_offsets else 0.0),
            "total_polyline_m": _tot_poly,
            "total_along_m": _tot_along,
            "polyline_excess_m": _tot_poly - _tot_along,
            "polyline_excess_pct": (100.0 * (_tot_poly - _tot_along)
                                    / _tot_along if _tot_along > 1e-9
                                    else 0.0),
            "longest_string_m": _longest,
            # SELECTION LAYERING: minted, recorded, given no string duty.
            "n_sub_min": len(walk_sub_min),
            "sub_min_total_m": sum(float(s[3]) for s in walk_sub_min),
            "sub_min_max_m": max((float(s[3]) for s in walk_sub_min),
                                 default=0.0),
            "sub_min": [{"chain": s[4], "n_nodes": len(s[2]),
                         "along_m": round(float(s[3]), 2),
                         "first_vertex": s[2][0], "last_vertex": s[2][-1]}
                        for s in walk_sub_min[:400]],
            "n_defects": len(all_defects),
            "n_rewritten": len(rewrites),
            "defects": [d.__dict__ if hasattr(d, "__dict__") else d
                        for d in all_defects],
            "n_endpoint_reads": len(endpoint_witness),
        }}
    # ★ ONE PAYLOAD ROW PER STRING.  Keying by first vertex alone made
    # strings that SHARE a first vertex overwrite each other: 8 of 64 at
    # HECA vanished from the keyed view while the summary still said 64 —
    # a per-string reading over a 56-string population reported as 64.
    # Third defect of this class tonight; all three were the population
    # not being what the key claimed.
    _seen_keys: Dict[object, int] = {}
    for row in inventory:
        key = key_of.get(row["first_vertex"])
        if key is None:
            continue
        if key in _seen_keys:
            key = (key, row["chain_id"])      # collision: disambiguate
        _seen_keys[key] = row["chain_id"]
        domains_payload[key] = row
    domains_payload["__summary__"]["n_inventory_rows"] = len(_seen_keys)
    store.mint("string_domains", "keyset", domains_payload, replace=True)

    # ★ S1 INPUT STATE CAPTURE (do not drop): the §3 stage-1 acceptance
    # is "construction re-run OFFLINE on the arm graph".  That is
    # impossible unless the arm captures S1's own inputs — arm 2 did not,
    # which cost a whole sequencing round.  Written under the same env
    # var so it always rides an instrumented arm.
    _st_dump = _os.environ.get("O4_STRING_STATE_DUMP")
    if _st_dump:
        import pickle as _pkl
        # PROBE B (spec §2): the two attribution fields ride the SAME
        # pickle.  Absent when the caller supplied nothing, so an offline
        # reader can tell "not carried" from "carried and empty".
        _probe_b = {}
        if hard_cat is not None:
            _probe_b["hard_cat"] = dict(hard_cat)
        if have_initial is not None:
            _probe_b["have_initial"] = list(have_initial)
        with open(_st_dump, "wb") as _sf:
            _pkl.dump({**_probe_b,
                       "elev": list(elev), "hard": set(hard_set),
                       "node_band": list(node_band) if node_band else None,
                       "pos": dict(pos), "spine_adj": {k: list(v) for k, v
                                                       in (junction_adj or {}).items()},
                       "substrate_polylines": [(k, list(c)) for k, c
                                               in _domain_polys],
                       "substrate_fingerprint":
                           layout.string_substrate_src.get("fingerprint"),
                       "decoration": dict(_dec),
                       "edges": [(e[0], e[1], bool(e[3])) for e
                                 in (getattr(G, "edges", ()) or ())
                                 if len(e) >= 4],
                       "bucket_to_idx": dict(bucket_to_idx), "n": n}, _sf)
    domains_payload["__summary__"]["strings"] = inventory
    # ★ The sidecar is written by ``write_string_sidecar`` — NOT here.
    # Writing it at this point is what made the grip-filter counts
    # unobservable: the filter runs at the CALL SITE, after this function
    # returns, so anything it stamps onto the summary reached the store
    # but never the file.  The caller writes the sidecar once, last.
    write_string_sidecar(layout)
    return rewrites
