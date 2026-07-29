"""Unit tests for the taut-string core module (spec §8.1).

Everything here is pure arithmetic: no layout, no DEM, no network, no
X-Plane install.  Two independent references are used to check the
funnel implementation in
``auto_patch.elevation_per_surface.route_profile.taut_string``:

* ``_relax_oracle`` — the slow-but-sure clamped-Laplacian (obstacle
  problem) relaxation the spec names as the correctness oracle.  Its
  fixpoint is unique (strictly convex energy, box constraints) and equals
  the taut string.  Gauss-Seidel converges at a rate ~1-O(1/k^2), so it
  is only run on the small corridors (``k <= _RELAX_MAX_K``) where it
  reaches full accuracy in a sane number of sweeps.
* ``_dp_oracle`` — an exact shortest-path DP over the tube's wall
  vertices (Euclidean length, visibility by an incremental slope
  window).  Completely different logic from the funnel, O(k^2), fast
  enough for every case including the k=200 corridors.

In addition ``_assert_fixpoint`` checks the KKT/fixpoint condition
directly on the funnel output, which is a full optimality certificate.
"""
from __future__ import annotations

import math
import random

from auto_patch.elevation_per_surface.route_profile.taut_string import (
    string_with_pegs, taut_string)

INF = float("inf")

#: Above this station count the Gauss-Seidel relaxation is too slow to
#: reach 1e-10 max-move; the exact DP oracle covers those cases.
_RELAX_MAX_K = 25


# --------------------------------------------------------------------------
# references
# --------------------------------------------------------------------------
def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else (high if value > high else value)


def _relax_oracle(stations: list[float], floor: list[float],
                  ceiling: list[float], z_start: float, z_end: float,
                  tol: float = 1e-10,
                  max_sweeps: int = 200_000) -> tuple[list[float], bool]:
    """Clamped-Laplacian obstacle relaxation with the endpoints held.

    Returns ``(profile, converged)``.
    """
    k = len(stations)
    z = [0.0] * k
    z[0] = _clamp(z_start, floor[0], ceiling[0])
    z[k - 1] = _clamp(z_end, floor[k - 1], ceiling[k - 1])
    span = stations[k - 1] - stations[0]
    for i in range(1, k - 1):
        t = (stations[i] - stations[0]) / span
        z[i] = _clamp(z[0] + t * (z[k - 1] - z[0]), floor[i], ceiling[i])
    converged = False
    for _ in range(max_sweeps):
        move = 0.0
        for i in range(1, k - 1):
            h0 = stations[i] - stations[i - 1]
            h1 = stations[i + 1] - stations[i]
            target = (h1 * z[i - 1] + h0 * z[i + 1]) / (h0 + h1)
            new = _clamp(target, floor[i], ceiling[i])
            delta = abs(new - z[i])
            if delta > move:
                move = delta
            z[i] = new
        if move < tol:
            converged = True
            break
    return z, converged


def _dp_oracle(stations: list[float], floor: list[float],
               ceiling: list[float], z_start: float,
               z_end: float) -> list[float]:
    """Exact shortest path through the tube by DP over wall vertices."""
    k = len(stations)
    cand: list[list[float]] = [[] for _ in range(k)]
    cand[0].append(_clamp(z_start, floor[0], ceiling[0]))
    for i in range(1, k - 1):
        if math.isfinite(floor[i]):
            cand[i].append(floor[i])
        if math.isfinite(ceiling[i]) and ceiling[i] != floor[i]:
            cand[i].append(ceiling[i])
    cand[k - 1].append(_clamp(z_end, floor[k - 1], ceiling[k - 1]))

    nodes: list[tuple[int, float]] = []
    node_at: list[list[int]] = [[] for _ in range(k)]
    for i in range(k):
        for value in cand[i]:
            node_at[i].append(len(nodes))
            nodes.append((i, value))

    n = len(nodes)
    dist = [INF] * n
    prev = [-1] * n
    dist[0] = 0.0
    for t in range(n):
        base = dist[t]
        if base == INF:
            continue
        i, z_u = nodes[t]
        g_lo, g_hi = -INF, INF
        for j in range(i + 1, k):
            ds = stations[j] - stations[i]
            for t2 in node_at[j]:
                z_v = nodes[t2][1]
                grade = (z_v - z_u) / ds
                if grade < g_lo - 1e-12 or grade > g_hi + 1e-12:
                    continue
                cost = base + math.hypot(ds, z_v - z_u)
                if cost < dist[t2]:
                    dist[t2] = cost
                    prev[t2] = t
            top = ceiling[j]
            bot = floor[j]
            if top != INF:
                g_top = (top - z_u) / ds
                if g_top < g_hi:
                    g_hi = g_top
            if bot != -INF:
                g_bot = (bot - z_u) / ds
                if g_bot > g_lo:
                    g_lo = g_bot
            if g_lo > g_hi:
                break

    assert dist[n - 1] < INF, "DP oracle found no feasible path"
    chain = [n - 1]
    while prev[chain[-1]] >= 0:
        chain.append(prev[chain[-1]])
    chain.reverse()

    out = [0.0] * k
    out[0] = nodes[chain[0]][1]
    for u, v in zip(chain, chain[1:]):
        i, z_u = nodes[u]
        j, z_v = nodes[v]
        grade = (z_v - z_u) / (stations[j] - stations[i])
        for m in range(i + 1, j):
            out[m] = z_u + grade * (stations[m] - stations[i])
        out[j] = z_v
    return out


def _assert_fixpoint(stations: list[float], floor: list[float],
                     ceiling: list[float], z: list[float],
                     tol: float = 1e-8) -> None:
    """Assert ``z`` is a fixpoint of the clamped-Laplacian (optimality)."""
    for i in range(1, len(stations) - 1):
        h0 = stations[i] - stations[i - 1]
        h1 = stations[i + 1] - stations[i]
        target = (h1 * z[i - 1] + h0 * z[i + 1]) / (h0 + h1)
        want = _clamp(target, floor[i], ceiling[i])
        assert abs(want - z[i]) <= tol * max(1.0, abs(z[i])), (
            f"not a fixpoint at {i}: {z[i]!r} != {want!r}")


def _assert_feasible(floor: list[float], ceiling: list[float],
                     z: list[float], tol: float = 1e-9) -> None:
    for i, value in enumerate(z):
        assert value >= floor[i] - tol, f"below floor at {i}"
        assert value <= ceiling[i] + tol, f"above ceiling at {i}"


def _check_against_oracles(stations: list[float], floor: list[float],
                           ceiling: list[float], z_start: float,
                           z_end: float) -> list[float]:
    """Run the funnel and cross-check it against every reference."""
    got = taut_string(stations, floor, ceiling, z_start, z_end)
    assert len(got) == len(stations)
    _assert_feasible(floor, ceiling, got)
    _assert_fixpoint(stations, floor, ceiling, got)

    want_dp = _dp_oracle(stations, floor, ceiling, z_start, z_end)
    for i, (a, b) in enumerate(zip(got, want_dp)):
        assert abs(a - b) <= 1e-6, f"DP oracle mismatch at {i}: {a!r} vs {b!r}"

    if len(stations) <= _RELAX_MAX_K:
        want_relax, converged = _relax_oracle(stations, floor, ceiling,
                                              z_start, z_end)
        assert converged, "relaxation oracle did not converge"
        for i, (a, b) in enumerate(zip(got, want_relax)):
            assert abs(a - b) <= 1e-6, (
                f"relaxation oracle mismatch at {i}: {a!r} vs {b!r}")
    return got


def _grades(stations: list[float], z: list[float]) -> list[float]:
    return [(z[i + 1] - z[i]) / (stations[i + 1] - stations[i])
            for i in range(len(stations) - 1)]


# --------------------------------------------------------------------------
# tube generators (seeded, never touching global random state)
# --------------------------------------------------------------------------
def _cap_tube(rng: random.Random, k: int, cap: float
              ) -> tuple[list[float], list[float], list[float], float, float]:
    """A cap-Lipschitz tube plus cap-compatible endpoint values."""
    stations = [0.0]
    for _ in range(k - 1):
        stations.append(stations[-1] + rng.uniform(4.0, 45.0))
    top = [rng.uniform(100.0, 120.0)]
    bot = [top[0] - rng.uniform(0.2, 9.0)]
    for i in range(1, k):
        step = stations[i] - stations[i - 1]
        top.append(top[-1] + rng.uniform(-cap, cap) * step)
        bot.append(bot[-1] + rng.uniform(-cap, cap) * step)
    ceiling = top
    floor = [min(bot[i], ceiling[i]) for i in range(k)]  # still cap-Lipschitz
    z_start = rng.uniform(floor[0], ceiling[0])
    total = stations[-1] - stations[0]
    z_end = _clamp(z_start + rng.uniform(-cap, cap) * total,
                   floor[-1], ceiling[-1])
    return stations, floor, ceiling, z_start, z_end


def _random_tube(rng: random.Random, k: int
                 ) -> tuple[list[float], list[float], list[float],
                            float, float]:
    """A wilder tube: steep walls, unbounded stretches, pinch points."""
    stations = [0.0]
    for _ in range(k - 1):
        stations.append(stations[-1] + rng.uniform(1.0, 60.0))
    base = [rng.uniform(-50.0, 50.0)]
    for _ in range(k - 1):
        base.append(base[-1] + rng.uniform(-6.0, 6.0))
    floor: list[float] = []
    ceiling: list[float] = []
    for i in range(k):
        width = rng.choice([0.0, 0.5, 3.0, 20.0])
        lo = base[i] - width * rng.random()
        hi = base[i] + width * rng.random()
        roll = rng.random()
        if roll < 0.18:
            lo = -INF          # off-net node: unbounded below
        elif roll < 0.30:
            hi = INF           # unbounded above
        elif roll < 0.36:
            lo = hi = base[i]  # forced pass-through
        floor.append(lo)
        ceiling.append(hi)
    z_start = rng.uniform(-60.0, 60.0)
    z_end = rng.uniform(-60.0, 60.0)
    return stations, floor, ceiling, z_start, z_end


# --------------------------------------------------------------------------
# 1-7: taut_string
# --------------------------------------------------------------------------
def test_chord_in_tube_is_the_exact_chord():
    """1. The chord fits the tube -> the string IS the chord."""
    stations = [0.0, 30.0, 55.0, 100.0, 160.0]
    floor = [90.0] * 5
    ceiling = [130.0] * 5
    got = _check_against_oracles(stations, floor, ceiling, 100.0, 108.0)
    grade = 8.0 / 160.0
    for i, s in enumerate(stations):
        assert abs(got[i] - (100.0 + grade * s)) <= 1e-9


def test_ceiling_pinch_bends_at_the_witness():
    """2. A ceiling pinch mid-span: one bend, exactly on the ceiling."""
    stations = [0.0, 25.0, 50.0, 75.0, 100.0]
    floor = [-INF] * 5
    ceiling = [200.0, 200.0, 101.0, 200.0, 200.0]
    got = _check_against_oracles(stations, floor, ceiling, 100.0, 106.0)
    assert abs(got[2] - 101.0) <= 1e-12          # touches the pinch exactly
    left = _grades(stations, got)[:2]
    right = _grades(stations, got)[2:]
    assert abs(left[0] - left[1]) <= 1e-12       # straight tangent, left
    assert abs(right[0] - right[1]) <= 1e-12     # straight tangent, right
    assert left[0] < right[0]                    # bent down onto the ceiling


def test_floor_pinch_is_symmetric():
    """3. Floor pinch: the mirror image of the ceiling case."""
    stations = [0.0, 25.0, 50.0, 75.0, 100.0]
    floor = [-200.0, -200.0, 99.0, -200.0, -200.0]
    ceiling = [INF] * 5
    got = _check_against_oracles(stations, floor, ceiling, 100.0, 94.0)
    assert abs(got[2] - 99.0) <= 1e-12
    grades = _grades(stations, got)
    assert abs(grades[0] - grades[1]) <= 1e-12
    assert abs(grades[2] - grades[3]) <= 1e-12
    assert grades[0] > grades[2]                 # bent up off the floor

    # ... and it is the exact mirror of the ceiling-pinch case.
    mirror = taut_string(stations, [-INF] * 5,
                         [200.0, 200.0, 101.0, 200.0, 200.0], 100.0, 106.0)
    for a, b in zip(got, mirror):
        assert abs((a - 100.0) + (b - 100.0)) <= 1e-9


def test_unbounded_walls_give_the_chord():
    """4. Both walls infinite -> pure chord."""
    stations = [0.0, 12.0, 44.0, 91.0]
    floor = [-INF] * 4
    ceiling = [INF] * 4
    got = _check_against_oracles(stations, floor, ceiling, 5.0, -13.0)
    grade = -18.0 / 91.0
    for i, s in enumerate(stations):
        assert abs(got[i] - (5.0 + grade * s)) <= 1e-9


def test_mixed_finite_and_infinite_walls():
    """5. One wall finite, one infinite."""
    stations = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    ceiling = [INF] * 6
    floor = [100.0, 101.0, 108.0, 104.0, 101.0, 100.0]
    got = _check_against_oracles(stations, floor, ceiling, 100.0, 100.0)
    assert abs(got[2] - 108.0) <= 1e-12          # rides the floor bulge
    assert got[1] > floor[1] and got[3] > floor[3]

    # unbounded floor, finite ceiling
    ceiling2 = [110.0, 109.0, 102.0, 106.0, 109.0, 110.0]
    floor2 = [-INF] * 6
    got2 = _check_against_oracles(stations, floor2, ceiling2, 110.0, 110.0)
    assert abs(got2[2] - 102.0) <= 1e-12


def test_cap_lipschitz_tubes_keep_grades_under_cap():
    """6. Cap-Lipschitz tube -> every emitted grade obeys the cap."""
    cap = 0.015
    for seed in (1, 2, 3, 5, 8, 13, 21, 34):
        rng = random.Random(seed)
        k = rng.choice([3, 4, 7, 12, 20, 25])
        stations, floor, ceiling, z_start, z_end = _cap_tube(rng, k, cap)
        # the generator's contract, re-verified here
        for i in range(1, k):
            step = stations[i] - stations[i - 1]
            assert abs(ceiling[i] - ceiling[i - 1]) <= cap * step + 1e-12
            assert abs(floor[i] - floor[i - 1]) <= cap * step + 1e-12
        got = _check_against_oracles(stations, floor, ceiling, z_start, z_end)
        for i, grade in enumerate(_grades(stations, got)):
            assert abs(grade) <= cap + 1e-9, (
                f"seed {seed} edge {i}: grade {grade!r} over cap {cap}")


def test_degenerate_corridors():
    """7. Two stations; and a zero-width tube (forced pass-through)."""
    got = _check_against_oracles([0.0, 42.0], [-INF, -INF], [INF, INF],
                                 10.0, 13.0)
    assert got == [10.0, 13.0]

    # endpoints outside their own walls are clamped in
    got = taut_string([0.0, 42.0], [0.0, 5.0], [3.0, 9.0], -100.0, 100.0)
    assert got == [0.0, 9.0]      # clamp(-100, 0, 3), clamp(100, 5, 9)

    # floor == ceiling at an interior station: exact pass-through
    stations = [0.0, 10.0, 30.0, 60.0]
    floor = [-INF, -INF, 55.0, -INF]
    ceiling = [INF, INF, 55.0, INF]
    got = _check_against_oracles(stations, floor, ceiling, 50.0, 50.0)
    assert abs(got[2] - 55.0) <= 1e-12
    assert abs(got[1] - (50.0 + (5.0 / 30.0) * 10.0)) <= 1e-9


# --------------------------------------------------------------------------
# 8-10: string_with_pegs
# --------------------------------------------------------------------------
def test_pegs_are_hit_and_spans_are_independent():
    """8. Interior pegs are exact; a distant wall cannot move a span."""
    stations = [float(10 * i) for i in range(9)]
    floor = [-INF] * 9
    ceiling = [INF] * 9
    pegs = {0: 100.0, 4: 104.0, 8: 102.0}
    got = string_with_pegs(stations, floor, ceiling, pegs)
    assert got is not None
    for index, value in pegs.items():
        assert abs(got[index] - value) <= 1e-12
    # each span is its own straight chord
    for i in range(1, 4):
        assert abs(got[i] - (100.0 + i * 1.0)) <= 1e-9
    for i in range(5, 9):
        assert abs(got[i] - (104.0 - (i - 4) * 0.5)) <= 1e-9

    # move a wall inside the SECOND span only
    ceiling2 = list(ceiling)
    ceiling2[6] = 101.0
    got2 = string_with_pegs(stations, floor, ceiling2, pegs)
    assert got2 is not None
    assert got2[:5] == got[:5], "an unrelated span moved"
    assert abs(got2[6] - 101.0) <= 1e-12
    assert got2[5] != got[5]


def test_free_ends_continue_the_tangent_clamped():
    """9. Free head/tail continue the adjacent tangent, clamped."""
    stations = [float(10 * i) for i in range(9)]
    floor = [-INF] * 9
    ceiling = [INF] * 9
    floor[0] = 95.0        # clamps the head extension up
    ceiling[1] = 95.0      # clamps the head extension down
    ceiling[7] = 107.0     # clamps the tail extension down
    pegs = {3: 100.0, 6: 106.0}
    got = string_with_pegs(stations, floor, ceiling, pegs)
    assert got is not None
    assert abs(got[3] - 100.0) <= 1e-12
    assert abs(got[6] - 106.0) <= 1e-12
    for i in (4, 5):       # strung span: straight, grade 0.2
        assert abs(got[i] - (100.0 + 0.2 * (stations[i] - 30.0))) <= 1e-9
    # head: tangent 0.2 backwards from (30, 100), clamped at 0 and 1
    assert abs(got[2] - 98.0) <= 1e-9      # free, on the tangent
    assert abs(got[1] - 95.0) <= 1e-12     # tangent would be 96.0 -> ceiling
    assert abs(got[0] - 95.0) <= 1e-12     # tangent would be 94.0 -> floor
    # tail: tangent 0.2 forwards from (60, 106)
    assert abs(got[7] - 107.0) <= 1e-12    # tangent would be 108.0 -> ceiling
    assert abs(got[8] - 110.0) <= 1e-9     # free, on the tangent
    _assert_feasible(floor, ceiling, got)


def test_peg_edge_cases():
    """10. <2 pegs -> None; dict untouched; peg values clamped."""
    stations = [0.0, 10.0, 20.0, 30.0]
    floor = [-INF, -INF, -INF, -INF]
    ceiling = [INF, INF, INF, 150.0]

    assert string_with_pegs(stations, floor, ceiling, {}) is None
    assert string_with_pegs(stations, floor, ceiling, {2: 100.0}) is None

    pegs = {0: 100.0, 3: 200.0}
    snapshot = dict(pegs)
    got = string_with_pegs(stations, floor, ceiling, pegs)
    assert pegs == snapshot, "the pegs dict was mutated"
    assert got is not None
    assert abs(got[3] - 150.0) <= 1e-12     # clamp(200, -inf, 150)
    assert abs(got[0] - 100.0) <= 1e-12

    # a peg below its own floor is clamped up
    floor2 = [-INF, 120.0, -INF, -INF]
    ceiling2 = [INF] * 4
    pegs2 = {1: 90.0, 3: 130.0}
    got2 = string_with_pegs(stations, floor2, ceiling2, pegs2)
    assert got2 is not None
    assert abs(got2[1] - 120.0) <= 1e-12


# --------------------------------------------------------------------------
# 11-12: determinism and oracle agreement at scale
# --------------------------------------------------------------------------
def test_determinism():
    """11. Same input -> bit-identical output, both entry points."""
    rng = random.Random(4242)
    stations, floor, ceiling, z_start, z_end = _random_tube(rng, 60)
    first = taut_string(stations, floor, ceiling, z_start, z_end)
    second = taut_string(stations, floor, ceiling, z_start, z_end)
    assert first == second

    pegs = {0: first[0], 17: first[17], 41: first[41], 59: first[59]}
    a = string_with_pegs(stations, floor, ceiling, pegs)
    b = string_with_pegs(stations, floor, ceiling,
                         dict(reversed(list(pegs.items()))))
    assert a is not None and a == b, "peg iteration order leaked into output"


def test_oracle_agreement_on_seeded_tubes():
    """12. Seeded random tubes, k in [3, 200], including free regions."""
    sizes = [3, 4, 5, 9, 16, 25, 37, 64, 111, 200]
    for seed, k in enumerate(sizes, start=101):
        rng = random.Random(seed)
        stations, floor, ceiling, z_start, z_end = _random_tube(rng, k)
        _check_against_oracles(stations, floor, ceiling, z_start, z_end)


def test_pegged_spans_match_taut_string_per_span():
    """string_with_pegs == taut_string on each span (seeded tubes)."""
    for seed in (7, 77, 777):
        rng = random.Random(seed)
        k = 48
        stations, floor, ceiling, _, _ = _random_tube(rng, k)
        indices = sorted(rng.sample(range(k), 5))
        pegs = {i: rng.uniform(-60.0, 60.0) for i in indices}
        got = string_with_pegs(stations, floor, ceiling, pegs)
        assert got is not None
        for p, q in zip(indices, indices[1:]):
            span = taut_string(stations[p:q + 1], floor[p:q + 1],
                               ceiling[p:q + 1], pegs[p], pegs[q])
            for offset, value in enumerate(span):
                assert abs(got[p + offset] - value) <= 1e-12
        _assert_feasible(floor, ceiling, got)
