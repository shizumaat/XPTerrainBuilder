"""Broad phase of the OBJ8 contact graph: the part pairs whose 3D
axis-aligned bounding boxes come within epsilon (issue #1865).

Split out of ``obj8_partition`` when it was vectorised.  The loop it
replaces tested every pair sharing a horizontal grid cell in Python, one
small ``ndarray.all()`` per pair: PAKT's pack-ground pool (307 k riprap
stone parts) made 17.5 M such tests, about 50 s per call, and a
partition calls the contact graph twice (the pool, then the connector
split's re-derivation).

The result is the SAME SET, built by the same insertion sequence, so its
iteration order is unchanged too.  ``contact_graph`` walks that order
and skips pairs already joined, so the order decides which edges it
returns, and seating reads those edges.  The loop visited buckets in
first-touch order and, inside a bucket, pairs ``(i, j)`` with ``i``
before ``j`` in member order, adding a pair the first time it passed the
box test.  The box test is symmetric in its two parts, so a pair that
fails once fails in every bucket.  This module tests the same candidates
in the same order with the same float64 comparisons, keeps the first
occurrence of each passing pair, and inserts them in that order.
"""

from __future__ import annotations

import numpy

# Candidate pairs tested per numpy batch: bounds peak memory (about
# 250 bytes per candidate across the index, gather and mask arrays).
_CANDIDATE_BATCH = 2_000_000


def broad_phase_pairs(
    box_minimums: numpy.ndarray,
    box_maximums: numpy.ndarray,
    epsilon_metres: float,
    cell_size: float,
) -> set[tuple[int, int]]:
    """All index pairs ``(low, high)`` whose boxes come within
    ``epsilon_metres`` on every axis.  ``box_minimums`` /
    ``box_maximums`` are ``(N, 3)`` float64 arrays, one row per part;
    ``cell_size`` is the horizontal (x, z) bucket size."""
    part_count = len(box_minimums)
    if part_count < 2:
        return set()
    passing_left: list[numpy.ndarray] = []
    passing_right: list[numpy.ndarray] = []
    members = _bucket_members(box_minimums, box_maximums, epsilon_metres,
                              cell_size)
    for left, right in _candidate_batches(members):
        passes = (
            (box_minimums[left] - epsilon_metres <= box_maximums[right])
            .all(axis=1)
            & (box_minimums[right] - epsilon_metres <= box_maximums[left])
            .all(axis=1)
        )
        passing_left.append(left[passes])
        passing_right.append(right[passes])
    if not passing_left:
        return set()
    low = numpy.concatenate(passing_left)
    high = numpy.concatenate(passing_right)
    _unique, first = numpy.unique(low * part_count + high, return_index=True)
    first.sort()
    return set(zip(low[first].tolist(), high[first].tolist()))


def _bucket_members(
    box_minimums: numpy.ndarray,
    box_maximums: numpy.ndarray,
    epsilon_metres: float,
    cell_size: float,
) -> list[list[int]]:
    """Each grid cell's parts (index order), cells in first-touch order
    — the buckets the loop built; single-part cells hold no pair."""
    first_x = _cells(box_minimums[:, 0] - epsilon_metres, cell_size)
    last_x = _cells(box_maximums[:, 0] + epsilon_metres, cell_size)
    first_z = _cells(box_minimums[:, 2] - epsilon_metres, cell_size)
    last_z = _cells(box_maximums[:, 2] + epsilon_metres, cell_size)
    buckets: dict[tuple[int, int], list[int]] = {}
    for part_index, (x_low, x_high, z_low, z_high) in enumerate(
            zip(first_x, last_x, first_z, last_z)):
        for cell_x in range(x_low, x_high + 1):
            for cell_z in range(z_low, z_high + 1):
                buckets.setdefault((cell_x, cell_z), []).append(part_index)
    return [bucket for bucket in buckets.values() if len(bucket) > 1]


def _cells(values: numpy.ndarray, cell_size: float) -> list[int]:
    """``int(value // cell_size)`` per value, as the loop computed it
    (numpy's float64 ``//`` is Python's floor division)."""
    return (values // cell_size).astype(numpy.int64).tolist()


def _candidate_batches(members: list[list[int]]):
    """``(left, right)`` index arrays of every within-bucket pair in the
    loop's visiting order (row-major upper triangle per bucket), cut
    into batches of about ``_CANDIDATE_BATCH`` pairs."""
    upper_by_size: dict[int, tuple[numpy.ndarray, numpy.ndarray]] = {}
    lefts: list[numpy.ndarray] = []
    rights: list[numpy.ndarray] = []
    pending = 0
    for bucket in members:
        upper = upper_by_size.get(len(bucket))
        if upper is None:
            upper = numpy.triu_indices(len(bucket), 1)
            upper_by_size[len(bucket)] = upper
        bucket_array = numpy.asarray(bucket, dtype=numpy.int64)
        lefts.append(bucket_array[upper[0]])
        rights.append(bucket_array[upper[1]])
        pending += len(upper[0])
        if pending >= _CANDIDATE_BATCH:
            yield numpy.concatenate(lefts), numpy.concatenate(rights)
            lefts, rights, pending = [], [], 0
    if lefts:
        yield numpy.concatenate(lefts), numpy.concatenate(rights)
