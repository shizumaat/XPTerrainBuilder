"""``auto_patch.obj8_broad_phase`` (issue #1865): the vectorised broad
phase returns the SAME set, in the same iteration order, as the per-pair
loop it replaced.  ``contact_graph`` skips pairs already joined while it
walks that order, so the order decides which contact edges it returns.
"""

from __future__ import annotations

import numpy
import pytest

from auto_patch import obj8_broad_phase
from auto_patch.obj8_broad_phase import broad_phase_pairs


def _loop_reference(minimums, maximums, epsilon, cell):
    """The historical loop, verbatim in behaviour: first-touch buckets,
    upper-triangle visits, first passing occurrence added."""
    buckets: dict[tuple[int, int], list[int]] = {}
    for index, (low, high) in enumerate(zip(minimums, maximums, strict=True)):
        for cell_x in range(int((low[0] - epsilon) // cell),
                            int((high[0] + epsilon) // cell) + 1):
            for cell_z in range(int((low[2] - epsilon) // cell),
                                int((high[2] + epsilon) // cell) + 1):
                buckets.setdefault((cell_x, cell_z), []).append(index)
    pairs: set[tuple[int, int]] = set()
    for bucket in buckets.values():
        for position, left in enumerate(bucket):
            for right in bucket[position + 1:]:
                if (left, right) in pairs:
                    continue
                if ((minimums[left] - epsilon <= maximums[right]).all()
                        and (minimums[right] - epsilon
                             <= maximums[left]).all()):
                    pairs.add((left, right))
    return pairs


def _boxes(count, seed, spread, size):
    generator = numpy.random.default_rng(seed)
    minimums = generator.uniform(-spread, spread, (count, 3))
    minimums[:, 1] = generator.uniform(0.0, 4.0, count)
    maximums = minimums + generator.uniform(0.05, size, (count, 3))
    return minimums, maximums


@pytest.mark.parametrize("seed, count, spread, size, epsilon", [
    (1, 400, 30.0, 4.0, 0.25),     # dense: most cells shared
    (2, 300, 200.0, 20.0, 0.0),    # spanning boxes, many cells each
    (3, 250, 15.0, 1.0, 3.5),      # epsilon larger than most boxes
])
def test_same_set_same_order_as_the_loop(seed, count, spread, size,
                                         epsilon, monkeypatch):
    # A small batch forces several batches, so the batch seams are
    # exercised as well as the single-batch path.
    monkeypatch.setattr(obj8_broad_phase, "_CANDIDATE_BATCH", 97)
    minimums, maximums = _boxes(count, seed, spread, size)
    cell = max(6.0, 2.0 * epsilon)
    expected = _loop_reference(minimums, maximums, epsilon, cell)
    got = broad_phase_pairs(minimums, maximums, epsilon, cell)
    assert expected
    assert list(got) == list(expected)


def test_no_pairs_for_fewer_than_two_parts_or_disjoint_boxes():
    empty = numpy.zeros((0, 3))
    assert broad_phase_pairs(empty, empty, 0.25, 6.0) == set()
    one = numpy.zeros((1, 3))
    assert broad_phase_pairs(one, one + 1.0, 0.25, 6.0) == set()
    far = numpy.array([[0.0, 0.0, 0.0], [100.0, 0.0, 100.0]])
    assert broad_phase_pairs(far, far + 1.0, 0.25, 6.0) == set()
