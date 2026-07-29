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
"""
from __future__ import annotations

import math

__all__ = ["taut_string", "string_with_pegs"]

INF = float("inf")

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
