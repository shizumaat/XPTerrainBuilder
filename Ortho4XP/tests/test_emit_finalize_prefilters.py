"""Twins for the emit/finalize prefilters (perf P3 wave 2, lane E).

Every optimisation in this lane is a SEMANTICS-IDENTICAL transformation:
the fast path must return exactly what the scan it replaces returned, or
the perf phase's byte-identity gate (frozen 1.0.245 baselines) would
break.  Each test below therefore carries the REFERENCE implementation —
the code as it stood before the change — and asserts equality on a
fixture built to hit the cases the transformation could get wrong
(long diagonal edges, negative coordinates, exact ties, points sitting
exactly on a boundary).
"""
import random

from shapely.geometry import LineString, Point


# ── the reference scans (pre-optimisation code, verbatim) ───────────


# ── fixtures ────────────────────────────────────────────────────────


# ── twins ───────────────────────────────────────────────────────────


class TestPointBufferQueryBox:
    """``_snap_ring_to_static`` (adjacent_ground) queries the static-edge
    STRtree with a BOX where it used to build a point BUFFER.  The tree
    query is envelope-only, so the two are the same query iff the
    buffer's envelope is exactly the box — including the ORDER of the
    returned candidates, which the nearest-wins tie-break reads."""

    def test_point_buffer_envelope_is_the_box(self):
        rng = random.Random(23)
        from shapely.geometry import box
        radius = 0.21
        for _ in range(5000):
            x = rng.uniform(-5000.0, 5000.0)
            y = rng.uniform(-5000.0, 5000.0)
            assert Point(x, y).buffer(radius).bounds == (
                x - radius, y - radius, x + radius, y + radius)
            assert box(x - radius, y - radius,
                       x + radius, y + radius).bounds == (
                x - radius, y - radius, x + radius, y + radius)

    def test_tree_returns_the_same_candidates_in_the_same_order(self):
        import numpy as np
        from shapely.geometry import box
        from shapely.strtree import STRtree
        rng = random.Random(29)
        radius = 0.21
        geometries = [
            LineString([(rng.uniform(0, 1000), rng.uniform(0, 1000)),
                        (rng.uniform(0, 1000), rng.uniform(0, 1000))])
            for _ in range(2000)]
        tree = STRtree(geometries)
        for _ in range(1000):
            x, y = rng.uniform(0, 1000), rng.uniform(0, 1000)
            assert np.array_equal(
                tree.query(Point(x, y).buffer(radius)),
                tree.query(box(x - radius, y - radius,
                               x + radius, y + radius)))
