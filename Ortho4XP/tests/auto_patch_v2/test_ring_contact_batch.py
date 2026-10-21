"""Twin of ``airport/ring_contact_batch.py`` and ``placement_contact.
_any_within`` (issue #412): the batched footprint-polygon contact answers
every pair exactly as ``_polys_touch`` does, and the inlined box product
exactly as ``box_gap_m`` over the product — on random rings built near
the tolerance, rings nested inside rings, and bodies with no ring."""
from __future__ import annotations

import random

import numpy as np
from auto_patch_v2.airport import placement_boxes as _pb
from auto_patch_v2.airport.placement_contact import _any_within, _polys_touch, ring_metres
from auto_patch_v2.airport.ring_contact_batch import polys_touch_many

EPS = 0.5
ML, MO = 110_770.0, 100_950.0


def _ring(rng: random.Random, cx: float, cy: float, r: float) -> list:
    n = rng.randint(3, 16)
    angs = sorted(rng.uniform(0.0, 2 * np.pi) for _ in range(n))
    return [((cx + r * rng.uniform(0.4, 1.0) * np.cos(a)) / ML,
             (cy + r * rng.uniform(0.4, 1.0) * np.sin(a)) / MO) for a in angs]


def _bodies(seed: int, n: int) -> list:
    rng = random.Random(seed)
    out: list = []
    for _ in range(n):
        k = rng.choice([0, 1, 1, 2, 3])
        cx, cy = 2_770_000.0 + rng.uniform(0, 60), 5_200_000.0 + rng.uniform(0, 60)
        rings = [_ring(rng, cx + rng.uniform(-8, 8), cy + rng.uniform(-8, 8),
                       rng.choice([0.3, 2.0, 6.0, 25.0])) for _ in range(k)]
        out.append([ring_metres(r, ML, MO) for r in rings])
    return out


def test_batch_matches_pairwise():
    for seed in range(6):
        bodies = _bodies(seed, 60)
        pairs = [(a, b) for a in range(len(bodies)) for b in range(a + 1, len(bodies))]
        got = polys_touch_many(bodies, pairs, EPS).tolist()
        want = [_polys_touch(bodies[a], bodies[b], EPS) for a, b in pairs]
        assert got == want
        assert any(want) and not all(want)


def test_nested_ring_and_no_ring():
    outer = ring_metres([(0.0, 0.0), (0.0, 1e-3), (1e-3, 1e-3), (1e-3, 0.0)], ML, MO)
    inner = ring_metres([(4e-4, 4e-4), (4e-4, 5e-4), (5e-4, 5e-4)], ML, MO)
    bodies = [[outer], [inner], [], None]
    pairs = [(0, 1), (1, 0), (0, 2), (3, 1)]
    assert polys_touch_many(bodies, pairs, EPS).tolist() == [True, True, True, True]
    assert polys_touch_many(bodies, [], EPS).tolist() == []


def test_any_within_matches_product():
    rng = random.Random(7)
    for _ in range(300):
        def box() -> tuple:
            la, lo = 25.25 + rng.uniform(0, 1e-4), 51.6 + rng.uniform(0, 1e-4)
            return (la, lo, la + rng.uniform(0, 2e-5), lo + rng.uniform(0, 2e-5))
        xs = [box() for _ in range(rng.randint(1, 6))]
        ys = [box() for _ in range(rng.randint(1, 6))]
        eps = rng.choice([0.0, 0.5, 3.0])
        want = any(_pb.box_gap_m(x, y) <= eps for x in xs for y in ys)
        assert _any_within(xs, ys, eps) == want
