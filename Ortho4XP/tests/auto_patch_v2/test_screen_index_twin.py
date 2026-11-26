"""The coarsening's contiguity / terrain screens and ``body_root``'s nearest
root read an index (a group's hull and ground range; a root's hull) instead
of every member (MMUN's scatter pieces: 34.6 M pairs, 3.35 M root reads).
Same answer: each new reading is twinned here against the loop it replaced,
on random fields with empty boxes, missing boxes and missing grounds."""
from __future__ import annotations

import random
import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import open_frame_seat as OFS
from auto_patch_v2.airport import placement_carrier as PC
from auto_patch_v2.airport.placement_boxes import box_gap_m


def _old_coarsen(bodies, tol_m, boxes, reach_m, grounds):
    """``coarsen``'s grouping loop as it was (no elevated bodies)."""
    order = sorted(range(len(bodies)), key=lambda i: (-bodies[i][2], bodies[i][0]))
    groups, zeros = [], []

    def contiguous(gi, i):
        if i >= len(boxes) or boxes[i] is None:
            return True
        return any(j < len(boxes) and boxes[j] is not None
                   and box_gap_m(boxes[i], boxes[j]) <= reach_m for j in groups[gi])

    def same(gi, i):
        if i >= len(grounds) or grounds[i] is None:
            return True
        return all(j >= len(grounds) or grounds[j] is None
                   or abs(float(grounds[i]) - float(grounds[j])) <= tol_m
                   for j in groups[gi])

    for i in order:
        a = bodies[i][1]
        z = None if a.surface_z is None else float(a.surface_z) - float(a.y_zero)
        for gi, g0 in enumerate(zeros):
            if (z is None) == (g0 is None) and (z is None or abs(z - g0) <= tol_m) \
                    and contiguous(gi, i) and same(gi, i):
                groups[gi].append(i)
                break
        else:
            groups.append([i])
            zeros.append(z)
    return [sorted(g) for g in sorted(groups, key=min)]


def _anchor(z):
    return AR.Anchor("other", 21.0, -86.9, 0.0, "t", surface_z=z)


def _box(rng):
    la, lo = 21.0 + rng.random() * 2e-4, -86.9 + rng.random() * 2e-4
    return (la, lo, la + rng.random() * 2e-5, lo + rng.random() * 2e-5)


def test_coarsen_groups_as_the_pairwise_loop_did():
    for seed in range(40):
        rng = random.Random(seed)
        n = rng.randint(1, 60)
        bodies = [(k, _anchor(None if rng.random() < 0.1 else rng.choice((1.0, 1.02, 1.3, 2.0))),
                   rng.randint(0, 5)) for k in range(n)]
        boxes = [None if rng.random() < 0.1 else () if rng.random() < 0.05 else _box(rng)
                 for _ in range(n - rng.randint(0, 2))]
        grounds = [None if rng.random() < 0.1 else rng.choice((1.0, 1.03, 1.06, 1.5))
                   for _ in range(n - rng.randint(0, 2))]
        reach = rng.choice((1.0, 3.0, 8.0))
        got = PC.coarsen(bodies, 0.05, frozenset(), boxes, reach_m=reach, grounds=grounds)
        assert got == _old_coarsen(bodies, 0.05, boxes, reach, grounds), seed


def _old_body_root_box(box, root_boxes):
    best = None
    for r in sorted(root_boxes):
        g = OFS._gap_m(tuple(box), root_boxes[r])
        if g is not None and g <= OFS.TOUCH_M and (best is None or g < best[0]):
            best = (g, r)
    return None if best is None else best[1]


def test_body_root_finds_the_root_the_loop_found():
    for seed in range(40):
        rng = random.Random(seed)
        roots = {f"fu:{k}": [_box(rng) for _ in range(rng.randint(0, 6))]
                 for k in range(rng.randint(1, 12))}
        index = OFS.RootIndex(roots)
        assert dict(index) == roots
        for _ in range(30):
            box = _box(rng)
            b = types.SimpleNamespace(anchor=None, pids=(), merged_into="", plan_box=box)
            want = _old_body_root_box(box, roots)
            assert OFS.body_root(b, {}, None, index) == want
            assert OFS.body_root(b, {}, None, roots) == want
