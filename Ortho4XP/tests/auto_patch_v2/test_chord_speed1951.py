"""#1951 part 2 — the chord-cover predicate and the road ring's pair walk,
made cheap, read EXACTLY as before: ``chords_covered`` is held to GEOS's
plain ``covered_by`` and ``roads.ring_pairs`` to the double loop it
replaced, on random notched faces with holes (the same answers, never
"close")."""
from __future__ import annotations

import math
import random

import numpy as np
import shapely
from auto_patch_v2.constraints.geometry import chords_covered, face_cover, rows_outside
from auto_patch_v2.constraints.roads import ring_pairs
from auto_patch_v2.geom import exact


def _face(rng: random.Random) -> tuple[list, list]:
    """A star-shaped ring with notches (chords leave it) and one square hole."""
    n = rng.randint(12, 60)
    ring = []
    for k in range(n):
        t = 2 * math.pi * k / n
        r = 40.0 + (25.0 if k % 5 == 0 else 0.0) + rng.uniform(-6.0, 6.0)
        ring.append((round(r * math.cos(t), 3), round(r * math.sin(t), 3)))
    cx, cy, h = rng.uniform(-8, 8), rng.uniform(-8, 8), rng.uniform(2, 6)
    hole = [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]
    return ring, [hole]


def _plain(poly, seg) -> list[bool]:
    shapely.prepare(poly)
    return [bool(b) for b in shapely.covered_by(shapely.linestrings(np.asarray(seg, float)), poly)]


def test_chords_covered_is_covered_by():
    rng = random.Random(1951)
    seen = covered = 0
    for _ in range(40):
        ring, holes = _face(rng)
        poly = face_cover(ring, holes, 0.05)
        pts = ring + holes[0]
        seg = [(pts[i], pts[j]) for i in range(len(pts)) for j in range(i + 1, len(pts))]
        # chords along the boundary and touching it from inside
        seg += [(ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))]
        seg += [((0.0, 0.0), p) for p in pts]
        want = _plain(poly, seg)
        assert chords_covered(poly, seg) == want
        seen += len(seg)
        covered += sum(want)
    assert 0 < covered < seen          # both answers exercised


def test_chords_covered_degenerate():
    assert chords_covered(None, [((0, 0), (1, 1))]) == [True]
    assert chords_covered(face_cover([(0, 0), (1, 0), (0, 1)], [], 0.05), []) == []


def _reference_pairs(xy, min_d, outside):
    out, n_out = [], 0
    n = len(xy)
    for i in range(n):
        for j in range(i + 1, n):
            (ax, ay), (bx, by) = xy[i], xy[j]
            d = exact.hypot(ax - bx, ay - by)
            if d < min_d:
                continue
            if (i, j) in outside:
                n_out += 1
                continue
            out.append((i, j, d))
    return out, n_out


def test_ring_pairs_is_the_double_loop():
    rng = random.Random(7)
    for _ in range(30):
        ring, holes = _face(rng)
        # near-duplicate vertices so the spacing floor bites
        ring = ring + [(ring[0][0] + 0.01, ring[0][1])]
        outside = set(rows_outside(face_cover(ring, holes, 0.05), ring, 0.2, 0, len(ring)))
        for out in (outside, set()):
            got = ring_pairs(ring, 0.2, out)
            want = _reference_pairs(ring, 0.2, out)
            assert got == want
            assert all(isinstance(i, int) and isinstance(d, float) for i, _j, d in got[0])
    assert ring_pairs([(0.0, 0.0)], 0.2) == ([], 0)
