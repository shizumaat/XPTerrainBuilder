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


# ══════════════════════════════════════════════════════════════════════
# S1 — the taut-chord constructor (docs/specs/s1-taut-chord-constructor
# -spec.md §6 acceptance).  Headless, synthetic, no layout required.
# ══════════════════════════════════════════════════════════════════════

from auto_patch.elevation_per_surface.route_profile.taut_string import (  # noqa: E402
    construct_taut_strings, substrate_fingerprint)
from auto_patch.elevation_per_surface.node_space import store_of as _store_of  # noqa: E402

CAP = 0.015          # config TAXI_MAX_GRADE class; never a call-site rule


# ── §6.1 wide tube, equal ends -> ONE chord, zero bends ───────────────
def _chord1_fixture():
    import json
    import pathlib
    p = (pathlib.Path(__file__).parent / "fixtures"
         / "heca_chord1_authorship.json")
    return json.loads(p.read_text())


class _Pts:
    def __init__(self):
        self.d = {}

    def get_or_add(self, x, y):
        return self.d.setdefault((round(x, 6), round(y, 6)), len(self.d))


class _Layout:
    def __init__(self, apt=(), osm=(), runway_union=None):
        self.canonical_points = _Pts()
        self.shapes = []
        # The owner's clip reads the pipeline's own object.  An EMPTY
        # polygon is the lawful "no runway contact" case: the callee
        # returns every string's identical tuple, so an airport whose
        # strings never meet a runway is byte-identical.
        from shapely.geometry import Polygon as _Poly
        self.runway_union = _Poly() if runway_union is None else runway_union
        if apt or osm:
            self.carry(apt, osm)

    def carry(self, apt, osm=()):
        """Write the carriage field exactly as phase 1 does (ruling 4):
        both tiers in ONE metre frame, fingerprinted with the SHARED
        function."""
        apt, osm = list(apt), list(osm)
        self.string_substrate_src = {
            "apt": apt, "osm": osm,
            "fingerprint": substrate_fingerprint(apt, osm)}


class _G:
    def __init__(self, pos, chains=None, service=()):
        self.pos = pos
        self.service_spine_pairs = set()


def _straight_case(n=12, service=()):
    """The SAME 110 m taxiway, now delivered the way production delivers
    it: two apt.dat pieces in the carried substrate.  The graph vertices
    attach by DECORATION at the registry's identity."""
    pos = {i: (10.0 * i, 0.0) for i in range(n)}
    apt = [([pos[i] for i in range(0, 6)], False),
           ([pos[i] for i in range(5, n)], False)]
    if service:
        pos[100], pos[101] = (0.0, 50.0), (10.0, 50.0)
        apt.append(([pos[100], pos[101]], True))
    g = _G(pos)
    jadj = {i: [(j, 0.15) for j in (i - 1, i + 1) if 0 <= j < n]
            for i in range(n)}
    return _Layout(apt), g, jadj, n


def _pin(n, pins, wide=500.0):
    """A band that PINS the named vertices (ruling 43(d): where an anchor
    pins the band, the band's CENTRE IS the anchor value -- the law
    arrives through the band, never through a policy).  Everything else
    is wide open, which under the chord model is simply unconstrained."""
    band = [(-wide, wide)] * n
    for v, z in pins.items():
        band[v] = (z, z)
    return band


def _run(layout, g, jadj, n, elev, hard, band=None):
    b2i = {f"k{i}": i for i in range(n)}
    node_band = band if band is not None else [(-500.0, 500.0)] * n
    return construct_taut_strings(
        layout, g, elev=elev, bucket_to_idx=b2i, n=n, node_band=node_band,
        hard=hard, corridor_pieces=[], junction_adj=jadj,
        cap_of_segment=lambda a, b: CAP)


def test_wiring_assembles_from_authorship_and_holds_the_chord():
    """Two authored fragments sharing a node assemble into one string and
    are strung as a single straight chord between the two anchors."""
    layout, g, jadj, n = _straight_case()
    elev = [100.0] * n
    elev[0], elev[n - 1] = 100.0, 101.65      # 1.5 % over 110 m
    out = _run(layout, g, jadj, n, elev, hard={0, n - 1},
               band=_pin(n, {0: 100.0, n - 1: 101.65}))
    assert out, "expected a rewrite map"
    assert 0 not in out and n - 1 not in out, "anchors must not be rewritten"
    span = 10.0 * (n - 1)
    for i, z in out.items():
        want = 100.0 + 1.65 * (10.0 * i) / span
        assert abs(z - want) < 1e-6, (i, z, want)
    inv = _store_of(layout).raw("string_domains")["__summary__"]
    assert inv["source"] == "string_substrate_src"
    assert inv["n_strings"] == 1, inv
    assert inv["substrate_station_m"] == 5.0        # conformed: the
    assert inv["substrate_intern_m"] > 0.0         # assembly-era window
    assert inv["decoration_identity_m"] == 0.5     # is not a domain input


def test_wiring_end_policy_does_not_inherit_post_harmonic_values():
    """THE end-policy test: a free (non-anchor) terminal's incoming value
    has ZERO influence.  A string that inherited it would move."""
    layout, g, jadj, n = _straight_case()
    band = _pin(n, {0: 100.0, n - 1: 100.0})
    base_elev = [100.0] * n
    a = _run(layout, g, jadj, n, list(base_elev), hard={0}, band=band)
    moved = list(base_elev)
    moved[n - 1] = 88.0                        # free terminal, dragged low
    layout2, g2, jadj2, _ = _straight_case()
    b = _run(layout2, g2, jadj2, n, moved, hard={0}, band=band)
    assert a == b, "a free terminal's inherited value leaked into the string"
    assert all(abs(z - 100.0) < 1e-9 for z in a.values()), a


def test_wiring_no_band_anywhere_emits_geometry_only_and_is_counted():
    """CONVERTED from the ``no_datum`` fixture, which retired with the
    fallback classes.  The property SURVIVES in its chord form (ruling
    43(c)): a string with no banded station anywhere emits GEOMETRY ONLY
    -- inert, declared, counted -- never a guessed height."""
    layout, g, jadj, n = _straight_case()
    out = _run(layout, g, jadj, n, [100.0] * n, hard=set(),
               band=[None] * n)
    assert out == {}, out
    inv = _store_of(layout).raw("string_domains")["__summary__"]
    assert inv["n_geometry_only_strings"] >= 1
    assert any(d["kind"] == "geometry_only" for d in inv["defects"])
    assert inv["endpoint_read_modes"].get("none", 0) >= 2


def test_wiring_excludes_service_authored_chains():
    layout, g, jadj, n = _straight_case(service=(2,))
    out = _run(layout, g, jadj, n, [100.0] * n, hard={0, n - 1})
    assert 100 not in out and 101 not in out, "service chain was strung"


# ── spine walk (Fable ruling 2): open-terrain crossing is
# unrepresentable by construction ────────────────────────────────────
from auto_patch.elevation_per_surface.route_profile.taut_string import (  # noqa: E402
    walk_spine_runs)


def _line(n, dx=10.0, dy=0.0, x0=0.0, y0=0.0, start=0):
    return ({start + i: (x0 + dx * i, y0 + dy * i) for i in range(n)},
            list(range(start, start + n)))


def _chain_adj(ids, pos):
    """SYMMETRIC spine adjacency along a node chain.

    ★ Must be symmetric: direction-symmetry consensus grows the walk from
    BOTH ends, so a one-directional adjacency makes every backward step
    read as a spine gap and the walk returns nothing.  (A dict
    comprehension of the form ``{v: [w] for v in ids for w in (...)}``
    silently keeps only the LAST neighbour per key -- that bug produced
    exactly that symptom.)
    """
    adj = {v: [] for v in ids}
    for v in ids:
        for w in (v - 1, v + 1):
            if w in pos and w in adj:
                adj[v].append(w)
    return adj


def _perp_from_chord(p, a, b):
    """Perpendicular distance of ``p`` from the chord ``a``->``b``.

    This is the measurement the VALIDATION BOUND is stated in: an emitted
    string's chord is exactly ``(pos[seg[0]], pos[seg[-1]])``, and every
    node it claims must lie within ``bound_m`` of it.
    """
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1e-12:
        return 0.0
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    return abs(-(p[0] - a[0]) * uy + (p[1] - a[1]) * ux)


def _assert_validation_bound(strings, pos, bound_m):
    """THE ruled invariant: every strung node is within ``bound_m`` of its
    OWN string's chord (Fable, fixture-premise ruling (a)(ii)).

    ★ Not implied by the walk's segmentation test.  ``_walk_segments``
    bounds each FORWARD segment against that segment's chord, but the
    direction-symmetry consensus then keeps a maximal covered SUB-RUN of
    it, and a sub-run is measured against its OWN (re-tilted) chord --
    which can differ from the parent's by up to the bound on each side.
    This assertion is the guard on exactly that, so it must never be
    weakened to whatever the constructor happens to emit.
    """
    for a, b, nodes, _ln, _ci in strings:
        for v in nodes:
            off = _perp_from_chord(pos[v], a, b)
            assert off <= bound_m, (
                f"strung node {v} is {off:.3f} m off its own string's "
                f"chord (bound {bound_m} m)")


def test_walk_straight_route_is_one_string():
    pos, ids = _line(30)
    adj = _chain_adj(ids, pos)
    st, sub = walk_spine_runs({0: ids}, pos, adj, bound_m=5.0, min_len_m=100.0)
    assert len(st) == 1 and not sub
    assert abs(st[0][3] - 290.0) < 1e-9


def test_walk_stops_at_a_spine_gap_and_never_bridges():
    """P7's holes end a segment; the walk cannot cross one."""
    pos, ids = _line(30)
    adj = _chain_adj(ids, pos)
    adj[14] = [13]                       # sever 14-15
    adj[15] = [16]
    st, sub = walk_spine_runs({0: ids}, pos, adj, bound_m=5.0, min_len_m=100.0)
    assert len(st) == 2, [s[3] for s in st]
    # the two strings are on OPPOSITE sides of the hole; neither spans it
    assert max(s[2][-1] for s in st) >= 29
    assert all(14 not in s[2] or 15 not in s[2] for s in st)


def test_walk_leaves_a_curve_with_no_string():
    """THE curve-exit fixture, under the FIXTURE-PREMISE RULING (Fable,
    2026-07-31).

    ★ This asserts the RULED CRITERION, never "arc nodes are excluded" as
    a class.  That premise -- aggressive arc-node exclusion -- was
    REJECTED BY NAME: it is the straightening test resurrected under a
    new job title.  A curve that never leaves ``bound_m`` IS straight at
    the owner's resolution, so a strung node merely being "on the arc"
    proves nothing and must not be asserted about.  (The rejected
    version of this fixture failed for exactly that reason: two
    sub-bound arc nodes joined the leading straight, 1.686 m off its
    chord -- lawful under the bound, illegal only under the premise.)

    CONSTRUCTION OBLIGATION -- ruling (a)(i).  "Sustained" needs no
    detector because the fixture author places the region beyond the
    criterion BY CONSTRUCTION:

    * the curve is an ``R = 100`` m arc sampled every ``dphi = 22.5``
      deg, so every arc-INTERIOR node sits ``R * (1 - cos dphi)`` =
      **7.612 m** off the chord joining its own two neighbours, versus
      ``2 * bound_m`` = 6.0 m.  That figure is also the exhaustive
      MINIMUM over every chord that spans such a node -- the offset only
      grows as the spanning arms grow -- so no candidate chord anywhere
      in the walk can bring one within bound.  Asserted below, not
      assumed.
    * the arc step is ``2 * R * sin(dphi / 2)`` = 39.018 m and the region
      spans four of them = **156.07 m >= min_len_m**, so the >=100 m
      emission rule ALONE cannot discard this curve -- the competition
      the fixture exists to preserve.  What discards it is the ruled
      two-step mechanism, in this order: bound-departure segmentation
      kills each successive curve segment SHORT (measured survivors here
      39.0 m and 58.8 m), and only then does the >=100 m rule send them
      to the inventory.  No curve detector, no straightening test, no
      new constant.
    * both flanking straights are 220 m >= ``min_len_m``, so each is free
      to emit a full string.

    Nothing is asserted about the two TANGENT nodes (arc phi=0 / phi=90).
    They are sub-bound entry nodes and ruling (a)(iii) leaves their
    membership explicitly free: the owner's strings are idealized
    two-node objects, and node-level membership at a transition is our
    construction detail inside his tolerance.
    """
    bound_m, min_len_m = 3.0, 100.0
    radius, dphi, n_arc, leg_h, leg_n = 100.0, 22.5, 4, 20.0, 12

    pos = {}
    for i in range(leg_n):                      # leg 1: 220 m along +x
        pos[i] = (leg_h * i, 0.0)
    x0 = leg_h * (leg_n - 1)                    # arc phi=0, tangent to leg 1
    for k in range(1, n_arc + 1):               # the curve: 90 deg of arc
        a = math.radians(dphi * k)
        pos[leg_n - 1 + k] = (x0 + radius * math.sin(a),
                              radius - radius * math.cos(a))
    exit_id = leg_n - 1 + n_arc                 # arc phi=90, tangent to leg 2
    ex, ey = pos[exit_id]
    for i in range(1, leg_n):                   # leg 2: 220 m along +y
        pos[exit_id + i] = (ex, ey + leg_h * i)
    ids = sorted(pos)
    adj = _chain_adj(ids, pos)

    # the CONSTRUCTED beyond-bound region: the arc's interior nodes.
    beyond = set(range(leg_n, exit_id))
    for v in sorted(beyond):
        worst = min(_perp_from_chord(pos[v], pos[a], pos[b])
                    for a in ids if a < v for b in ids if b > v)
        assert worst >= 2.0 * bound_m, (
            f"fixture construction failed: node {v} is only {worst:.3f} m "
            f"off some chord that spans it (needs >= {2.0 * bound_m})")

    st, sub = walk_spine_runs({0: ids}, pos, adj, bound_m=bound_m,
                              min_len_m=min_len_m)

    # ── the ruled invariants, and nothing else ────────────────────────
    assert len(st) == 2, [round(s[3], 1) for s in st]
    _assert_validation_bound(st, pos, bound_m)
    for _a, _b, nodes, _ln, _ci in st:
        assert not (set(nodes) & beyond), (
            f"beyond-bound curve node(s) strung: "
            f"{sorted(set(nodes) & beyond)}")
    # ... and the two strings are the two FLANKS, one each -- the owner's
    # "leave the curve with no string" read as an emission, not as a
    # membership rule.
    flank1, flank2 = set(range(leg_n - 1)), set(range(exit_id + 1, len(ids)))
    sides = sorted((bool(set(n) & flank1), bool(set(n) & flank2))
                   for _a, _b, n, _ln, _ci in st)
    assert sides == [(False, True), (True, False)], sides
    # the curve's own material survives as MEASUREMENT (selection
    # layering), never silently dropped.
    assert any(set(nodes) & beyond for _a, _b, nodes, _ln, _ci in sub)


def test_walk_cannot_cross_open_terrain():
    """THE acceptance property: two disjoint taxiways with no spine
    between them can never produce one string spanning both."""
    pos, ids = _line(12)                                   # taxiway A
    pos2, ids2 = _line(12, x0=800.0, start=100)            # taxiway B
    pos.update(pos2)
    adj = _chain_adj(ids, pos)
    adj.update(_chain_adj(ids2, pos))
    st, sub = walk_spine_runs({0: ids, 1: ids2}, pos, adj,
                              bound_m=5.0, min_len_m=100.0)
    for a, b, nodes, ln, ci in st + sub:
        assert not (set(nodes) & set(ids) and set(nodes) & set(ids2)), \
            "string crossed open terrain between two taxiways"


def test_walk_sub_min_segments_are_measurement_not_strings():
    pos, ids = _line(6)                       # 50 m only
    adj = _chain_adj(ids, pos)
    st, sub = walk_spine_runs({0: ids}, pos, adj, bound_m=5.0, min_len_m=100.0)
    assert st == [] and len(sub) == 1 and abs(sub[0][3] - 50.0) < 1e-9


# ── S1-06: the owner's ~45 deg two-string turn cut ────────────────────
# His verdict, verbatim (2026-07-31): S1-06 "cuts through open terrain...
# two straight segments with an almost 45 degree bend at the middle,
# needs two strings".
#
# The EXTENTS ARE KEYED TO HIS MAP, `/Users/noah/heca_strings.osm` --
# way ids, node ids and lat/lon verbatim.  This corner is the ONLY ~45
# deg bend in the 46-way map: every other endpoint-adjacent pair of his
# ways bends <= 25 deg or >= 88 deg (measured over all 46).  Headings
# below are atan2(north, east), CCW from east -- not compass bearings.
#
#   way -39338  621.4 m  heading 107.70 deg  (-291316 -291320 -291321
#                                             -291317)
#   way -39408   98.2 m  heading  59.66 deg  (-291317 -> -291392)  the
#                                             corner chamfer
#   way -39407  638.3 m  heading 107.91 deg  (-291392 -> -291393)
#
# Bend at J1 (-291317) = 48.05 deg, at J2 (-291392) = 48.25 deg: his
# "almost 45 degree bend at the middle".  -39407 runs 71-73 m off
# -39338's line, so any single run covering both segments must cut
# across open ground -- the defect he named.
#
# ★ The SITE is an inference, the assertions are not.  "S1-06" indexes
# OUR run inventory, which needs a build to reproduce; the corner above
# is the unique place in his map matching every clause of his sentence
# (two straight segments, both >= min_len_m, ~45 deg bend at the middle,
# open ground between them).  If the coordinator re-keys the site, only
# _S1_06_LATLON / _S1_06_WAYS move -- the assertion shape below is the
# ruled one and stands unchanged.
_S1_06_LATLON = {
    0: (30.11603651227, 31.41603724009),      # -291316, -39338 head
    1: (30.11711686818, 31.41563859543),      # -291320
    2: (30.11740108429, 31.41553372072),      # -291321
    3: (30.12135454626, 31.41407487631),      # -291317  J1
    4: (30.12211550839, 31.41458986044),      # -291392  J2
    5: (30.12757199187, 31.41255138159),      # -291393, -39407 tail
}
_S1_06_WAYS = {"-39338": (0, 1, 2, 3), "-39408": (3, 4), "-39407": (4, 5)}


def _s1_06_local_xy():
    """His lat/lon -> local metres, equirectangular about his first node."""
    lat0, lon0 = _S1_06_LATLON[0]
    per_deg = 111320.0
    east = per_deg * math.cos(math.radians(lat0))
    return {k: ((lon - lon0) * east, (lat - lat0) * per_deg)
            for k, (lat, lon) in _S1_06_LATLON.items()}


def _resample(points, step_m):
    """Sample a polyline at ~``step_m``, keeping every original vertex.

    ★ The vertices must survive: rounding his bend away would hand the
    walk a smoothed corner and the fixture would pass on geometry he
    never drew.
    """
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        n = max(1, round(math.dist(a, b) / step_m))
        for k in range(1, n + 1):
            t = k / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def test_walk_s1_06_forty_five_degree_bend_needs_two_strings():
    """S1-06 under the fixture-premise ruling's assertion shape: TWO
    strings whose extents key to his two straight segments, each strung
    node within ``bound_m`` of its own string's chord, the constructed
    beyond-bound neighbourhood at the bend UNSTRUNG, transition
    membership left free.

    CONSTRUCTION OBLIGATION.  The beyond-bound neighbourhood here is not
    a corner node -- his chamfer is locally straight -- it is the stretch
    of chamfer that lies ``>= 2 * bound_m`` from BOTH of his segment
    lines, so no string keyed to either segment can reach it.  It is
    also, at 98.2 m, below his own ``min_len_m``, so it can never emit a
    string of its own: the neighbourhood is beyond-bound by geometry and
    inventory-bound by his emission rule, both by construction.
    """
    bound_m = 8.0            # owner's TAUT_STRING_SPINE_TOLERANCE_M
    min_len_m = 100.0        # owner's TAUT_STRING_MIN_STRING_M
    step_m = 12.0            # SPINE_STEP_M -- the spine's own sampling

    xy = _s1_06_local_xy()
    walked = []
    for wid in ("-39338", "-39408", "-39407"):
        piece = _resample([xy[k] for k in _S1_06_WAYS[wid]], step_m)
        walked.extend(piece if not walked else piece[1:])
    pos = dict(enumerate(walked))
    ids = sorted(pos)
    adj = _chain_adj(ids, pos)

    seg_a = (xy[0], xy[3])                    # his -39338, 621.4 m
    seg_b = (xy[4], xy[5])                    # his -39407, 638.3 m
    beyond = {v for v in ids
              if _perp_from_chord(pos[v], *seg_a) >= 2.0 * bound_m
              and _perp_from_chord(pos[v], *seg_b) >= 2.0 * bound_m}
    assert beyond, "fixture construction failed: no beyond-bound region"

    st, sub = walk_spine_runs({0: ids}, pos, adj, bound_m=bound_m,
                              min_len_m=min_len_m)

    # ── the ruled invariants ──────────────────────────────────────────
    assert len(st) == 2, [round(s[3], 1) for s in st]
    _assert_validation_bound(st, pos, bound_m)
    for _a, _b, nodes, _ln, _ci in st:
        assert not (set(nodes) & beyond), (
            f"the bend's beyond-bound neighbourhood was strung: "
            f"{sorted(set(nodes) & beyond)}")

    # ── extents keyed to HIS segments: one string each, lying within
    # his tolerance of the segment it reproduces, covering the majority
    # of it (his acceptance is coverage, never inventory equality).
    matched = {}
    for chord, name in ((seg_a, "-39338"), (seg_b, "-39407")):
        owner_len = math.dist(*chord)
        for a, b, nodes, ln, _ci in st:
            if max(_perp_from_chord(pos[v], *chord) for v in nodes) <= bound_m:
                assert name not in matched, f"two strings claim {name}"
                matched[name] = ln / owner_len
    assert set(matched) == {"-39338", "-39407"}, matched
    for name, covered in matched.items():
        assert 0.90 <= covered <= 1.05, (name, covered)

    # his chamfer is the bend, not a string: it stays in the inventory.
    assert any(set(nodes) & beyond for _a, _b, nodes, _ln, _ci in sub)


# ══════════════════════════════════════════════════════════════════════
# WIRING — the spine walk as the driver's Stage-0 domain source
# ══════════════════════════════════════════════════════════════════════
# ★ The ``test_wiring_*`` fixtures above are Fable's pre-registered ones.
# They now run ON THE SUBSTRATE PATH -- the same 110 m taxiway delivered
# as carried apt.dat pieces, graph vertices attached by DECORATION -- and
# every behavioural assertion in them is unchanged: the rewrite map, the
# untouched anchors, the exact chord values, the string count, the
# ``no_datum`` fall-back.  Two labels conformed with the domain source
# (ruling 8): ``source``, and the assembly-era ``heading_window_m`` which
# is no longer a domain input.  The processed-tier domain and its seam are
# DELETED -- there is no flag choosing between paths at any point in time.
from auto_patch.config import (TAUT_STRING_MIN_STRING_M,  # noqa: E402
                               TAUT_STRING_SPINE_TOLERANCE_M)
from auto_patch.elevation_per_surface.route_profile.taut_string import (  # noqa: E402
    compass_ends, compose_through_paths, decorate_nodes_onto_strings,
    filter_pins_by_grade_law, strings_with_tenure, substrate_from_carriage,
    through_path_chains, write_string_sidecar)
import pytest  # noqa: E402


def _walk_case(chain_lens, step=10.0, service_len=0, gap_x=None):
    """Authored chains laid end-to-end along +x, one spine edge per step.

    ``chain_lens`` are NODE COUNTS per chain; consecutive chains share
    their meeting node (the authored fragmentation the walk sees).
    ``gap_x`` starts the second chain that far away with NO spine edge
    between the two -- open terrain.
    """
    pos, chains, nid = {}, {}, 0
    for ci, k in enumerate(chain_lens):
        start = nid - 1 if (nid and gap_x is None) else nid
        ids = list(range(start, start + k))
        x0 = (gap_x if (gap_x is not None and ci) else 0.0)
        for t, v in enumerate(ids):
            pos[v] = (x0 + step * (t if (gap_x is not None and ci) else v), 0.0)
        chains[ci] = ids
        nid = ids[-1] + 1
    n = max(pos) + 1
    adj = {}
    for ids in chains.values():                 # edges only WITHIN a chain
        for a, b in zip(ids, ids[1:]):
            adj.setdefault(a, []).append((b, CAP * step))
            adj.setdefault(b, []).append((a, CAP * step))
    apt = [([pos[v] for v in ids], False) for ids in chains.values()]
    if service_len:
        sids = list(range(1000, 1000 + service_len))
        for t, v in enumerate(sids):
            pos[v] = (step * t, 500.0)
        for a, b in zip(sids, sids[1:]):
            adj.setdefault(a, []).append((b, CAP * step))
            adj.setdefault(b, []).append((a, CAP * step))
        apt.append(([pos[v] for v in sids], True))
        return _Layout(apt), _G(pos), adj, max(n, 1000 + service_len)
    return _Layout(apt), _G(pos), adj, n


def _drive(layout, g, adj, n, elev, hard, cap=None, band=None):
    b2i = {f"k{i}": i for i in range(max(n, max(g.pos) + 1))}
    node_band = band if band is not None else [(-500.0, 500.0)] * n
    out = construct_taut_strings(
        layout, g, elev=elev, bucket_to_idx=b2i, n=n, node_band=node_band,
        hard=hard, corridor_pieces=[], junction_adj=adj,
        cap_of_segment=cap or (lambda a, b: CAP))
    raw = _store_of(layout).raw("string_domains")
    return out, raw["__summary__"], [v for k, v in raw.items()
                                     if k != "__summary__"]


def test_wiring_stage0_source_is_the_spine_walk():
    """The domain source is the WALK, at the owner's two constants."""
    layout, g, adj, n = _walk_case((21,))
    elev = [100.0] * n
    elev[n - 1] = 100.0 + CAP * 10.0 * (n - 1)
    _out, inv, rows = _drive(layout, g, adj, n, elev, hard={0, n - 1})
    assert inv["stage0_source"] == "walk_spine_runs", inv["stage0_source"]
    assert inv["source"] == "string_substrate_src"
    assert inv["spine_tolerance_m"] == TAUT_STRING_SPINE_TOLERANCE_M
    assert inv["min_string_m"] == TAUT_STRING_MIN_STRING_M
    assert inv["n_strings"] == 1 and len(rows) == 1
    assert rows[0]["n_vertices"] == n


def test_wiring_walk_string_is_the_straight_chord():
    """A straight 200 m authored chain between two anchors is strung as
    the exact chord, and neither anchor is rewritten."""
    layout, g, adj, n = _walk_case((21,))
    span = 10.0 * (n - 1)
    elev = [100.0] * n
    out, _inv, _rows = _drive(layout, g, adj, n, elev, hard={0, n - 1},
                              band=_pin(n, {0: 100.0,
                                            n - 1: 100.0 + CAP * span}))
    assert out, "expected a rewrite map"
    assert 0 not in out and n - 1 not in out
    for i, z in out.items():
        assert abs(z - (100.0 + CAP * 10.0 * i)) < 1e-9, (i, z)


def test_wiring_targets_are_linear_in_chord_station():
    """CONVERTED from the polyline-arc-length fixture.

    The gate-currency ruling governed the retired TUBE: stations and cap
    budgets read polyline arc length because the funnel walked the path.
    A chord has no path -- it is a straight line through space -- so the
    surviving property is the one the owner stated: z is LINEAR IN THE
    ALONG-STATION ON THE CHORD.  The zig-zag geometry is kept precisely
    because polyline arc length (466.5 m) and chord extent (400.0 m)
    differ by 16 %: interpolating on the wrong axis is visible here.
    """
    # ★ The wiggle is on ONE HALF only: a uniform zig-zag has arc length
    # proportional to x, so it could not separate the two axes at all.
    step, amp, k = 10.0, 3.0, 41
    pos = {i: (step * i, (amp if i % 2 else -amp) if i < 20 else -amp)
           for i in range(k)}
    adj = {}
    for a_, b_ in zip(range(k), range(1, k)):
        adj.setdefault(a_, []).append((b_, 1.0))
        adj.setdefault(b_, []).append((a_, 1.0))
    layout, g = _Layout([([pos[i] for i in range(k)], False)]), _G(pos)
    poly = sum(math.dist(pos[i], pos[i + 1]) for i in range(k - 1))
    straight = math.dist(pos[0], pos[k - 1])
    assert poly > straight + 30.0 and abs(straight - 400.0) < 1e-9
    out, inv, rows = _drive(layout, g, adj, k, [100.0] * k, hard=set(),
                            band=_pin(k, {0: 100.0, k - 1: 106.0}))
    assert inv["n_geometry_only_strings"] == 0
    assert abs(rows[0]["length_m"] - straight) < 1e-6      # the CHORD
    assert rows[0]["polyline_excess_m"] == 0.0             # a chord is it
    # every target is the linear value at that vertex's CHORD station
    for v, z in out.items():
        want = 100.0 + 6.0 * (pos[v][0] - pos[0][0]) / straight
        assert abs(z - want) < 1e-9, (v, z, want)
    # ... and NOT the polyline-arc-length value: the half-wiggle makes
    # the two axes disagree, and the worst disagreement is material
    worst = 0.0
    for v in out:
        arc = sum(math.dist(pos[i], pos[i + 1]) for i in range(v))
        worst = max(worst, abs(out[v] - (100.0 + 6.0 * arc / poly)))
    assert worst > 0.05, worst


def test_wiring_sub_min_runs_are_recorded_but_never_strung():
    """Selection layering, through the driver: the walk mints runs
    UNFILTERED, sub-100 m ones are inventory MEASUREMENT and get no
    string duty (no hook rewrite), exactly like an unclaimed node."""
    # ★ The short run must be a SEPARATE taxiway, not a short fragment of
    # this one: under ruling 2 an adjoining collinear fragment composes
    # into the trunk (that is the ruling), so a shared-endpoint stub would
    # test composition, not selection layering.
    layout, g, adj, n = _walk_case((21, 6), gap_x=800.0)
    elev = [100.0] * n
    elev[20] = 100.0 + CAP * 200.0
    out, inv, rows = _drive(layout, g, adj, n, elev, hard={0, 20})
    assert inv["n_strings"] == 1 and len(rows) == 1
    assert inv["n_sub_min"] == 1
    assert abs(inv["sub_min_total_m"] - 50.0) < 1e-9
    assert inv["sub_min"][0]["n_nodes"] == 6
    assert not [v for v in out if v > 20], sorted(out)


def test_wiring_free_terminal_value_never_leaks_at_string_scale():
    """§3 end policy at string scale: a free terminal's incoming
    (post-harmonic) value has ZERO influence on the string."""
    layout, g, adj, n = _walk_case((21,))
    a_out, _i, _r = _drive(layout, g, adj, n, [100.0] * n, hard={0})
    layout2, g2, adj2, _ = _walk_case((21,))
    moved = [100.0] * n
    moved[n - 1] = 88.0
    b_out, _i2, _r2 = _drive(layout2, g2, adj2, n, moved, hard={0})
    assert a_out == b_out, "a free terminal's value leaked into the string"


def test_wiring_service_chain_is_never_strung_at_string_scale():
    layout, g, adj, n = _walk_case((21,), service_len=21)
    elev = [100.0] * n
    elev[n - 1] = 100.0 + CAP * 10.0 * (n - 1)
    out, inv, _rows = _drive(layout, g, adj, n, elev, hard={0, n - 1})
    assert inv["n_strings"] == 1
    assert not [v for v in out if v >= 1000], sorted(out)


def test_wiring_open_terrain_is_unrepresentable_in_the_driver():
    """The acceptance property, through the driver: two taxiways with no
    spine between them can never share a string."""
    layout, g, adj, n = _walk_case((21, 21), gap_x=800.0)
    _out, inv, rows = _drive(layout, g, adj, n, [100.0] * n, hard=set())
    assert inv["n_strings"] == 2, rows
    left, right = set(range(21)), set(range(21, 42))
    for row in rows:
        ends = {row["first_vertex"], row["last_vertex"]}
        assert ends <= left or ends <= right, row


def test_wiring_is_deterministic_under_substrate_piece_order():
    """§3 ordering is a TOTAL order: the walk can emit several segments
    per through-path, so the stable id is (path, first vertex).  Same
    substrate, different apt-piece order ⇒ identical output."""
    layout, g, adj, n = _walk_case((11, 11), gap_x=800.0)
    elev = [100.0] * n
    elev[10] = 100.0 + CAP * 100.0
    elev[21] = 100.0 + CAP * 100.0
    hard = {0, 10, 11, 21}
    a_out, a_inv, a_rows = _drive(layout, g, adj, n, list(elev), hard=hard)
    layout2, g2, adj2, _ = _walk_case((11, 11), gap_x=800.0)
    layout2.carry(list(reversed(layout2.string_substrate_src["apt"])))
    b_out, b_inv, b_rows = _drive(layout2, g2, adj2, n, list(elev), hard=hard)
    assert a_out == b_out and a_out
    assert [r["chain_id"] for r in a_rows] == [r["chain_id"] for r in b_rows]
    assert a_inv["n_strings"] == b_inv["n_strings"] == 2


# ── RULING 2: authoring boundaries are not chain boundaries ───────────
def test_wiring_authoring_boundaries_are_not_chain_boundaries():
    """★ THE ruling, at string scale: three authored fragments tiling one
    straight taxiway are ONE string, and the inventory says so.

    This is restoration of committed law -- "a JUNCTION is not a turn, an
    AUTHORED GEOMETRY BREAK is not a turn" -- so the assertion is on the
    composed extent, never on a merge threshold (there is none).
    """
    layout, g, adj, n = _walk_case((8, 8, 8))          # 70 + 70 + 70 m
    span = 10.0 * (n - 1)
    elev = [100.0] * n
    out, inv, rows = _drive(layout, g, adj, n, elev, hard={0, n - 1},
                            band=_pin(n, {0: 100.0,
                                          n - 1: 100.0 + CAP * span}))
    assert inv["chain_domain"] == "through_paths"
    assert inv["n_chains_in"] == 3 and inv["n_chains_walked"] == 1
    assert inv["n_strings"] == 1 and inv["n_sub_min"] == 0
    assert rows[0]["n_source_chains"] == 3
    assert abs(rows[0]["length_m"] - span) < 1e-9
    # every fragment boundary is now an ordinary station on one chord
    for i, z in out.items():
        assert abs(z - (100.0 + CAP * 10.0 * i)) < 1e-9, (i, z)


def test_wiring_junction_pairing_is_global_best_collinear():
    """At a 4-way crossing the straight-through partners pair with each
    other -- parameter-free, no threshold -- so the trunk composes
    through the junction and the crosser stays its own path."""
    step, k = 10.0, 21
    pos, chains, adj = {}, {}, {}

    def _edge(a, b):
        adj.setdefault(a, []).append((b, CAP * step))
        adj.setdefault(b, []).append((a, CAP * step))

    for i in range(k):                                 # trunk along +x
        pos[i] = (step * i, 0.0)
    j = k // 2                                         # the shared node
    for i in range(k - 1):
        _edge(i, i + 1)
    chains[0], chains[1] = list(range(0, j + 1)), list(range(j, k))
    _apt_runs = [chains[0], chains[1]]
    cross = []
    for t in range(1, 11):                             # crosser along +y
        for sgn, base in ((1, 100), (-1, 200)):
            v = base + t
            pos[v] = (step * j, sgn * step * t)
            cross.append(v)
            _edge(v, (base + t - 1) if t > 1 else j)
    chains[2] = list(range(200 + 10, 200, -1)) + [j] + list(range(101, 111))
    _apt_runs.append(chains[2])
    n = max(pos) + 1
    layout = _Layout([([pos[v] for v in run], False) for run in _apt_runs])
    g = _G(pos)
    out, inv, rows = _drive(layout, g, adj, n, [100.0] * n, hard=set())
    assert inv["n_strings"] == 2, rows
    axes = sorted(round(abs(pos[r["first_vertex"]][0]
                            - pos[r["last_vertex"]][0]), 3) for r in rows)
    assert axes == [0.0, 200.0], axes        # one pure +x, one pure +y
    for row in rows:                          # each stays on its own axis
        assert row["n_vertices"] in (21, 21), row
    assert not (set(range(0, k)) & set(cross))


def test_compose_through_paths_partitions_edges_and_stays_linear():
    """Pure unit on the composer: every substrate edge lands in exactly
    one path, and NO path repeats a node.

    ★ Linearity is the acceptance property of the whole design -- it is
    what makes open-terrain crossing unrepresentable -- so a cycle must
    come back as a path plus a leftover, never as a closed walk.
    """
    pos = {i: (10.0 * i, 0.0) for i in range(6)}          # straight
    pos.update({10 + i: (10.0 * i, 40.0) for i in range(4)})   # a square
    pos[13] = (30.0, 40.0)
    square = [10, 11, 12, 13, 10]
    items = [(0, [0, 1, 2]), (1, [2, 3, 4, 5]), (2, square)]
    paths, stats = compose_through_paths(items, pos)
    seen = {}
    for pid, nodes in paths:
        assert len(set(nodes)) == len(nodes), (pid, nodes)   # LINEAR
        for a, b in zip(nodes, nodes[1:]):
            key = (min(a, b), max(a, b))
            assert key not in seen, ("edge used twice", key)
            seen[key] = pid
    assert len(seen) == stats["n_edges"] == 5 + 4
    straight = [p for _i, p in paths if 0 in p][0]
    assert straight == [0, 1, 2, 3, 4, 5]                    # one trunk
    assert stats["path_source_chains"][0] == 2               # spans 2 chains


# ── the PURE chaining entry point (one construction, three consumers) ──
def test_through_path_chains_composes_substrate_polylines():
    """``through_path_chains`` is what ARM-ACCEPT and the solve both use:
    substrate polylines in, maximal through-paths out."""
    a = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    b = [(20.0, 0.0), (30.0, 0.0), (40.0, 0.0)]      # shares an endpoint
    c = [(20.0, 0.0), (20.0, 10.0), (20.0, 20.0)]    # crosser at the join
    res = through_path_chains([("apt:0", a), ("apt:1", b), ("osm:x#0", c)])
    assert res.stats["n_polylines_in"] == 3
    lengths = sorted(round(sum(math.dist(p, q) for p, q in zip(ch, ch[1:])), 3)
                     for _pid, ch in res.chains)
    assert lengths == [20.0, 40.0], lengths     # trunk composed, crosser own
    trunk = [ch for _pid, ch in res.chains if len(ch) == 5][0]
    assert trunk[0] == (0.0, 0.0) and trunk[-1] == (40.0, 0.0)


def test_through_path_chains_never_bridges_a_near_miss():
    """★ Interning is EXACT-coordinate identity, never a tolerance.

    A 0.86 m endpoint near-miss -- the measured class, and a substrate
    seam joint is the same shape at <= 8 m -- is RECOGNITION ONLY: it
    licenses no geometric extension and no value transport.  Composition
    must leave the two runs separate, however collinear they are.
    """
    a = [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0)]
    b = [(200.86, 0.0), (300.0, 0.0), (400.0, 0.0)]
    res = through_path_chains([("apt:0", a), ("osm:y#0", b)])
    assert len(res.chains) == 2, res.chains
    assert res.stats["n_interned_nodes"] == 6      # nothing was merged
    for _pid, ch in res.chains:
        assert len({round(p[0], 6) for p in ch}) == len(ch)


# ══════════════════════════════════════════════════════════════════════
# RULING 3 — string tenure (exclusivity charged at STRUNG coverage)
# ══════════════════════════════════════════════════════════════════════
def _tenure_case(specs):
    """``specs`` = [(start_xy, dir_xy, n_nodes)] laid at 10 m spacing."""
    pos, items, nid = {}, [], 0
    for cid, ((x0, y0), (dx, dy), k) in enumerate(specs):
        ids = []
        for t in range(k):
            pos[nid] = (x0 + dx * 10.0 * t, y0 + dy * 10.0 * t)
            ids.append(nid)
            nid += 1
        items.append((cid, ids))
    adj = {}
    for _cid, ids in items:
        for a, b in zip(ids, ids[1:]):
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    return items, pos, adj


def test_tenure_emitted_strings_partition_the_ground():
    """★ WHAT STANDS: no metre of pavement carries two string
    authorities.  Overlapping strings are the emit-consensus minting
    mechanism and nothing downstream arbitrates two rods on one station.
    """
    items, pos, adj = _tenure_case([((0.0, 0.0), (1.0, 0.0), 40),
                                    ((0.0, 50.0), (1.0, 0.0), 40)])
    res = strings_with_tenure(items, pos, adj, bound_m=8.0, min_len_m=100.0)
    owner = {}
    for _a, _b, nodes, _ln, ci in res.strings:
        for u, w in zip(nodes, nodes[1:]):
            key = (min(u, w), max(u, w))
            assert key not in owner, ("two authorities over one edge", key)
            owner[key] = ci
    assert len(res.strings) == 2


def test_tenure_returns_unstrung_edges_and_reaches_a_fixpoint():
    """An edge is SPENT only when an emitted string covers it; the rest
    RETURN.  Termination is arithmetic, never a round cap."""
    # one 300 m straight + a 60 m spur the walk cannot fold into it
    items, pos, adj = _tenure_case([((0.0, 0.0), (1.0, 0.0), 31),
                                    ((500.0, 0.0), (0.0, 1.0), 7)])
    res = strings_with_tenure(items, pos, adj, bound_m=8.0, min_len_m=100.0)
    assert [r.n_strings for r in res.rounds] == [1, 0]
    assert res.stats["n_edges_returned"] == 6, res.stats     # the spur
    assert res.stats["n_edges_spent"] == 30
    # arithmetic termination: every emitting round strictly shrank the pool
    pools = [r.pool_before for r in res.rounds]
    assert pools == sorted(pools, reverse=True) and pools[0] > pools[-1]
    # the returned edges are the sub-min run's, still available to a later
    # round -- they were never charged to the emitted string
    assert res.sub_min and len(res.sub_min[0][2]) == 7


def test_tenure_never_relaxes_min_len_in_any_round():
    items, pos, adj = _tenure_case([((0.0, 0.0), (1.0, 0.0), 31),
                                    ((500.0, 0.0), (0.0, 1.0), 7)])
    res = strings_with_tenure(items, pos, adj, bound_m=8.0, min_len_m=100.0)
    for _a, _b, _nodes, ln, _ci in res.strings:
        assert ln >= 100.0
    assert all(s[3] < 100.0 for s in res.sub_min)


def test_tenure_is_deterministic_across_rounds():
    items, pos, adj = _tenure_case([((0.0, 0.0), (1.0, 0.0), 31),
                                    ((300.0, 0.0), (0.6, 0.8), 21),
                                    ((500.0, 0.0), (0.0, 1.0), 7)])
    a = strings_with_tenure(items, pos, adj, bound_m=8.0, min_len_m=100.0)
    b = strings_with_tenure(items, pos, adj, bound_m=8.0, min_len_m=100.0)
    assert [s[2] for s in a.strings] == [s[2] for s in b.strings]
    assert a.stats["rounds"] == b.stats["rounds"]


# ── RULING 5 — exclusion is a WALL, not a skip ────────────────────────
def test_service_pieces_cover_but_are_never_strung():
    """RULING 5 at the tier the substrate speaks: a SERVICE apt piece
    COUNTS for membership and coverage (apt.dat presence is presence --
    the committed sentence is locative) but is EXCLUDED FROM THE STRUNG
    DOMAIN, before composition, never after it."""
    layout, g, adj, n = _walk_case((21,), service_len=21)
    elev = [100.0] * n
    elev[20] = 100.0 + CAP * 200.0
    out, inv, rows = _drive(layout, g, adj, n, elev, hard={0, 20})
    assert inv["n_apt_pieces"] == 2          # the builder SAW both pieces
    assert inv["n_apt_service_excluded"] == 1
    assert inv["n_substrate_polylines"] == 1  # only one may be strung
    assert inv["n_strings"] == 1
    assert not [v for v in out if v >= 1000], sorted(out)


# ══════════════════════════════════════════════════════════════════════
# RULING 4 — hook side: fingerprint, carriage read, node decoration
# ══════════════════════════════════════════════════════════════════════
_APT = [([(0.0, 0.0), (100.0, 0.0)], False),
        ([(0.0, 40.0), (60.0, 40.0)], True)]
_OSM = [("-1234", [(0.0, 80.0), (120.0, 80.0)])]


def test_substrate_fingerprint_is_content_only_and_catches_drift():
    """One implementation, both ends.  Content only, so it survives a
    round-trip through the carried container and fails on any edit."""
    a = substrate_fingerprint(_APT, _OSM)
    assert a == substrate_fingerprint(
        [(tuple(map(tuple, c)), s) for c, s in _APT],      # tuples vs lists
        [(w, tuple(map(tuple, c))) for w, c in _OSM])
    moved = [([(0.0, 0.0), (100.001, 0.0)], False), _APT[1]]
    assert substrate_fingerprint(moved, _OSM) != a          # 1 mm moves it
    assert substrate_fingerprint(_APT, []) != a             # tier loss moves it


def test_substrate_from_carriage_asserts_the_fingerprint():
    class _L:
        pass

    lay = _L()
    log = []
    assert substrate_from_carriage(lay, station_m=5.0, log=log.append) is None
    assert log and "no string_substrate_src" in log[0]
    lay.string_substrate_src = {
        "apt": _APT, "osm": _OSM,
        "fingerprint": substrate_fingerprint(_APT, _OSM)}
    log.clear()
    sub = substrate_from_carriage(lay, station_m=5.0, log=log.append)
    assert sub is not None and sub.stats["apt_pieces"] == 2
    assert any("apt 2 pieces" in m for m in log), log       # denominator line
    lay.string_substrate_src = dict(lay.string_substrate_src,
                                    fingerprint="deadbeef")
    with pytest.raises(AssertionError):
        substrate_from_carriage(lay, station_m=5.0)


def test_decoration_uses_the_registry_identity_and_never_moves_anything():
    """A vertex is ON a string iff within the REGISTRY's identity of its
    polyline.  Unmapped vertices are simply undecorated -- off-net under
    the existing §10(v) law -- never snapped, never bridged."""
    string = [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0)]
    nodes = {1: (50.0, 0.2),        # on it
             2: (150.0, -0.49),     # on it, just inside 0.5 m
             3: (150.0, 0.86),      # the 0.86 m near-miss class: NOT on it
             4: (500.0, 0.0)}       # far away
    dec = decorate_nodes_onto_strings([string], nodes, identity_m=0.5)
    assert set(dec) == {1, 2}, dec
    assert dec[1][0][0] == 0 and abs(dec[1][0][1] - 50.0) < 1e-9
    assert abs(dec[2][0][1] - 150.0) < 1e-9 and dec[2][0][2] < 0.5
    # round-trip: every decorated vertex really is within identity
    for v, rows in dec.items():
        for _si, _st, off in rows:
            assert off <= 0.5
    # a vertex on TWO crossing strings is reported on both -- the §3
    # shared-vertex case, not a merge and not a pick
    cross = [(150.0, -60.0), (150.0, 60.0)]
    both = decorate_nodes_onto_strings([string, cross], {9: (150.0, 0.0)},
                                       identity_m=0.5)
    assert sorted(r[0] for r in both[9]) == [0, 1], both


# ══════════════════════════════════════════════════════════════════════
# THE OWNER'S RUNWAY CLIP — Fable's four regression pins
# ══════════════════════════════════════════════════════════════════════
# "Use the runway outline to clip any strings, discarding anything inside
#  the runway, and if the remainder is less than 50m just drop it, the
#  taxiway's grade will be smooth enough without it"   (owner 2026-07-31)
from auto_patch.config import (  # noqa: E402
    TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M as _CLIP_MIN)
from auto_patch.elevation_per_surface.route_profile.string_substrate import (  # noqa: E402
    clip_strings_to_runways)


def _rwy(x0, x1, half=37.8, y0=0.0):
    """A runway outline as the ruled SHOULDER-ABSORBED union (75.6 m at
    HECA) — the region where runway elevation authority ends."""
    from shapely.geometry import box
    return box(x0, y0 - half, x1, y0 + half)


def _string(x0, x1, y=0.0, step=10.0, cid=0, start=0):
    pos = {}
    k = int(round((x1 - x0) / step)) + 1
    nodes = [start + i for i in range(k)]
    for i, v in enumerate(nodes):
        pos[v] = (x0 + step * i, y)
    return (pos[nodes[0]], pos[nodes[-1]], nodes,
            math.dist(pos[nodes[0]], pos[nodes[-1]]), cid), pos


def test_clip_pin1_crossing_survives_collinear_with_its_anchor_intact():
    """A taxiway CROSSING a runway keeps both remainders ON THE SAME
    STRAIGHT LINE -- the string is an idealized elevation target, so the
    two pieces stay one line rather than two independently-solving ones."""
    s, pos = _string(-500.0, 500.0)              # 1,000 m across a runway
    res = clip_strings_to_runways([s], pos, _rwy(-100.0, 100.0),
                                  min_remainder_m=_CLIP_MIN)
    assert len(res.strings) == 2, res.stats
    assert res.stats["split_in_two"] == 1.0 and res.stats["dropped"] == 0.0
    for a, b, nodes, ln, _cid in res.strings:
        assert abs(a[1]) < 1e-9 and abs(b[1]) < 1e-9      # still the line
        assert all(abs(pos[v][1]) < 1e-9 for v in nodes)
        assert all(abs(pos[v][0]) >= 100.0 - 1e-6 for v in nodes)
    # nodes are partitioned, never duplicated across the remainders
    claimed = [v for _a, _b, nodes, _l, _c in res.strings for v in nodes]
    assert len(claimed) == len(set(claimed))


def test_clip_pin2_an_along_runway_string_drops_via_the_floor():
    """A string running ALONG a runway is inside the outline: its
    remainders fall under the 50 m floor and it is dropped entirely --
    the class that was pulling the corridor toward the 05L descent."""
    s, pos = _string(0.0, 300.0, y=10.0)         # inside the outline
    res = clip_strings_to_runways([s], pos, _rwy(-20.0, 320.0),
                                  min_remainder_m=_CLIP_MIN)
    assert res.strings == (), res.strings
    assert res.stats["dropped_m"] < _CLIP_MIN * 2


def test_clip_pin3_on20_class_keeps_its_off_runway_majority():
    """A string with a runway bite in it keeps the off-runway majority --
    the clip discards what is INSIDE, never the string."""
    s, pos = _string(0.0, 1000.0)
    res = clip_strings_to_runways([s], pos, _rwy(900.0, 1100.0),
                                  min_remainder_m=_CLIP_MIN)
    assert len(res.strings) == 1
    kept = res.strings[0][3]
    assert kept > 0.5 * s[3] and abs(kept - 900.0) < 1e-6
    assert res.stats["dropped"] == 0.0


def test_clip_pin4_no_angle_machinery_is_reintroduced():
    """The 0-29 deg / 74-90 deg discriminator is RETIRED to measurement
    history: the owner's rule subsumes it.  Scan what the code CALLS
    (``co_names``), never its prose -- an earlier version of this pin
    tripped on the words in its own docstring."""
    banned = {"atan2", "acos", "asin", "degrees", "radians", "cos", "sin",
              "angle", "bearing", "heading", "deg"}
    for fn in (clip_strings_to_runways, construct_taut_strings):
        names = {n.lower() for n in fn.__code__.co_names}
        assert not (names & banned), (fn.__name__, sorted(names & banned))


def test_clip_is_required_explicit_and_the_guard_is_not_defeated():
    s, pos = _string(0.0, 300.0)
    with pytest.raises(ValueError):
        clip_strings_to_runways([s], pos, None, min_remainder_m=_CLIP_MIN)


def test_clip_telemetry_reaches_the_inventory():
    """The census travels to S1-CP2: clipped / dropped / split / the
    [50,100) band, which SURVIVES (100 is construction-existence law
    pre-clip, 50 is emission-remainder law post-clip)."""
    layout, g, adj, n = _walk_case((21,))
    layout.runway_union = _rwy(60.0, 90.0)       # a bite out of the middle
    elev = [100.0] * n
    elev[n - 1] = 100.0 + CAP * 10.0 * (n - 1)
    _out, inv, _rows = _drive(layout, g, adj, n, elev, hard={0, n - 1})
    assert inv["clip_min_remainder_m"] == _CLIP_MIN
    assert inv["n_strings_pre_clip"] == 1
    assert inv["n_strings_clipped"] == 1
    assert inv["n_crossings_split_in_two"] == 1
    # 200 m string, 30 m bite -> 60 m and 110 m: the 60 m remainder is in
    # the [50, 100) band and SURVIVES, labelled.
    assert inv["n_remainders_in_duty_band"] == 1
    assert inv["remainders_in_duty_band"][0]["remainder_m"] == 60.0
    assert inv["n_remainders_dropped"] == 0
    assert inv["n_strings"] == 2


# ── compass labels: geography is COMPUTED, never inferred from order ──
def test_compass_ends_are_computed_not_walk_order():
    """★ REGRESSION PIN.  A string's endpoint order is WALK ORDER and
    carries no geography.  Reading "start" as "north" transposed chord
    1's two endpoint values and cost a round of investigation -- the
    chord appeared to fall north->south against the owner's expectation.
    The label must come from the COORDINATES, in either traversal order.
    """
    south, north = (0.0, -875.1), (0.0, 1732.4)
    assert compass_ends(south, north) == ("south", "north")
    assert compass_ends(north, south) == ("north", "south")   # order-proof
    # ★ north/south is PREFERRED even when the chord is more east-west:
    # chord 1 runs SW->NE and a dominant-axis rule would have called its
    # ends "east" and "west" -- true, and useless to everyone who names
    # this taxiway by its north and south ends.
    sw, ne = (-3713.2, -875.1), (-710.6, 1732.4)
    assert compass_ends(sw, ne) == ("south", "north")
    assert compass_ends(sw, ne, axis="ew") == ("west", "east")
    # east/west is the fallback only when the ends share a latitude
    assert compass_ends((0.0, 5.0), (500.0, 5.0)) == ("west", "east")


def test_endpoint_witness_ships_the_compass_label():
    """The build's own artifact must carry the labelling, so the swap
    cannot reappear downstream."""
    layout, g, adj, n = _walk_case((21,))
    # lay the string south -> north so walk order and geography differ
    for v in list(g.pos):
        g.pos[v] = (0.0, g.pos[v][0])
    layout.carry([([g.pos[v] for v in range(n)], False)])
    band = _pin(n, {0: 100.0, n - 1: 102.0})
    _out, inv, rows = _drive(layout, g, adj, n, [100.0] * n,
                             hard={0, n - 1}, band=band)
    labels = {w["end_label"] for w in inv["endpoint_witness"]}
    assert labels == {"south", "north"}, inv["endpoint_witness"]
    row = rows[0]
    assert {row["label_start"], row["label_end"]} == {"south", "north"}
    # the value keyed BY COMPASS agrees with the value keyed by order
    for w in inv["endpoint_witness"]:
        assert row[f"z_{w['end_label']}"] == w["value"]
    assert row["z_south"] == 100.0 and row["z_north"] == 102.0


# ══════════════════════════════════════════════════════════════════════
# RULING 52 — the chord is never bent by law; the GRIP is
# ══════════════════════════════════════════════════════════════════════
def _pin_chain(zs, budget=0.15, step=10.0):
    """A straight pinned chain; ``budget`` is each pair's cap allowance."""
    pins = {i: z for i, z in enumerate(zs)}
    adj = {}
    for i in range(len(zs) - 1):
        adj.setdefault(i, []).append((i + 1, budget))
        adj.setdefault(i + 1, []).append((i, budget))
    return pins, adj


def test_grip_filter_releases_only_over_cap_pairs():
    """A pin joins ``anchors``, so a both-pinned pair the projection can
    no longer flatten must not stay both-pinned.  Lawful pairs are
    untouched -- releasing them would hand the solver stations the chord
    could have held."""
    pins, adj = _pin_chain([100.0, 100.1, 100.2, 100.3])      # all lawful
    kept, rel = filter_pins_by_grade_law(pins, adj)
    assert kept == pins and rel == []
    pins, adj = _pin_chain([100.0, 100.1, 101.0, 101.1])      # 2-3 over cap
    kept, rel = filter_pins_by_grade_law(pins, adj)
    assert len(kept) == 3 and len(rel) == 1
    w = rel[0]
    assert w["pair"] == [1, 2] and w["rule"] == "grade_law_over_cap"
    assert abs(w["excess_m"] - (0.9 - 0.15)) < 1e-9
    # COMPLETENESS: no both-pinned over-cap pair survives
    for i, lst in adj.items():
        for (j, b) in lst:
            if i < j and i in kept and j in kept:
                assert abs(kept[i] - kept[j]) <= b + 1e-9


def test_grip_filter_is_endpoint_protective_and_minimal():
    """Gate (A) reads ENDPOINTS, so a run of consecutive over-cap pairs
    releases its INTERIOR pins first; and no release may be unnecessary."""
    pins, adj = _pin_chain([100.0, 101.0, 102.0, 103.0])   # every pair over
    depth = {0: 0.0, 1: 10.0, 2: 10.0, 3: 0.0}             # 1,2 interior
    kept, rel = filter_pins_by_grade_law(pins, adj, endpoint_depth=depth)
    assert 0 in kept and 3 in kept, kept          # endpoints protected
    assert set(kept) == {0, 3}, kept              # both interiors released
    # MINIMALITY: re-admitting any released pin re-creates an over-cap pair
    for v in (1, 2):
        trial = dict(kept)
        trial[v] = pins[v]
        assert any(abs(trial[i] - trial[j]) > b + 1e-9
                   for i, lst in adj.items() for (j, b) in lst
                   if i < j and i in trial and j in trial), v


def test_grip_filter_never_releases_a_law_anchor():
    """A pair whose BOTH ends are law anchors and over cap is the
    projection's pre-existing genuine-step contract, not ours."""
    pins, adj = _pin_chain([100.0, 101.0])
    kept, rel = filter_pins_by_grade_law(pins, adj, hard={0, 1})
    assert kept == pins and rel == []
    # one law anchor, one string pin -> the STRING side yields
    kept, rel = filter_pins_by_grade_law(pins, adj, hard={0})
    assert set(kept) == {0} and rel and rel[0]["released"] == 1


def test_grip_filter_is_deterministic():
    zs = [100.0, 101.0, 101.05, 102.0, 102.05, 103.0]
    pins, adj = _pin_chain(zs)
    depth = {i: min(i, len(zs) - 1 - i) * 10.0 for i in range(len(zs))}
    a = filter_pins_by_grade_law(pins, adj, endpoint_depth=depth)
    b = filter_pins_by_grade_law(dict(reversed(list(pins.items()))), adj,
                                 endpoint_depth=depth)
    assert a[0] == b[0]
    assert [w["released"] for w in a[1]] == [w["released"] for w in b[1]]


def test_pin_ledger_counts_only_actual_targets():
    """★ The ledger is the ONLY record of what production pinned -- the
    offline re-walk has failed to reproduce it three times -- so its
    population must equal the rewrite map exactly.  A row minted before
    the plural-claim and hard skips would make "released" mean two
    different things (never offered vs grip-released).
    """
    layout, g, adj, n = _walk_case((21,))
    span = 10.0 * (n - 1)
    out, inv, _rows = _drive(layout, g, adj, n, [100.0] * n,
                             hard={0, n - 1},
                             band=_pin(n, {0: 100.0, n - 1: 100.0 + CAP * span}))
    rows = inv["pins"]
    assert inv["n_targets"] == len(rows) == len(out)
    assert {r["vertex"] for r in rows} == set(out)
    assert 0 not in {r["vertex"] for r in rows}          # hard, never a pin
    for r in rows:
        assert r["z"] == out[r["vertex"]]
        assert set(r) == {"vertex", "string", "station_m", "z", "depth_m",
                          "grip"}
        assert r["grip"] == "offered"      # the call site stamps the rest


def test_sidecar_is_written_after_the_grip_filter_stamps_it(tmp_path):
    """★ REGRESSION PIN.  The sidecar used to be written INSIDE the
    constructor, so the grip filter -- which runs at the call site, after
    it returns -- could stamp the store but never the file: the log line
    proved the treatment ran while the sidecar could not.  The writer is
    separate and idempotent, and the LAST call wins."""
    import json
    layout, g, adj, n = _walk_case((21,))
    _out, inv, _rows = _drive(layout, g, adj, n, [100.0] * n, hard=set(),
                              band=_pin(n, {0: 100.0, n - 1: 101.0}))
    dump = tmp_path / "w.csv"
    inv["n_over_cap_pairs"] = 7                       # a call-site stamp
    for r in inv["pins"]:
        r["grip"] = "kept"
    assert write_string_sidecar(layout, str(dump)) == str(dump)
    side = json.loads((tmp_path / "w.csv.domains.json").read_text())
    assert side["n_over_cap_pairs"] == 7
    assert side["pins"] and all(r["grip"] == "kept" for r in side["pins"])
    assert (tmp_path / "w.csv").exists()              # endpoint witness CSV
