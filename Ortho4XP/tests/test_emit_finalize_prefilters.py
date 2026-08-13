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
import math
import random
from collections import defaultdict

from shapely.geometry import LineString, Point, Polygon

from auto_patch.conformance import (
    _crossing_candidate_pairs,
    _edge_linestrings,
    _points_near_edge,
    _tjunctions_on_edge,
)
from auto_patch.pavement.vertices import (
    _project_means_onto_runway_boundaries,
)


# ── the reference scans (pre-optimisation code, verbatim) ───────────

def _reference_points_near_edge(grid, cell, ax, ay, bx, by, tol):
    """The BOUNDING-BOX cell scan the band walk replaces."""
    minx, maxx = (ax, bx) if ax <= bx else (bx, ax)
    miny, maxy = (ay, by) if ay <= by else (by, ay)
    i0 = int((minx - tol) / cell)
    i1 = int((maxx + tol) / cell)
    j0 = int((miny - tol) / cell)
    j1 = int((maxy + tol) / cell)
    seen = set()
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            for pt in grid.get((i, j), ()):
                if pt not in seen:
                    seen.add(pt)
                    yield pt


def _reference_project_onto_runway_boundary(px, py, runway_boundaries, tol):
    """The per-cluster projection scan the batch replaces."""
    best = None
    for (min_x, min_y, max_x, max_y), exterior in runway_boundaries:
        if not (min_x <= px <= max_x and min_y <= py <= max_y):
            continue
        point = Point(px, py)
        distance = exterior.distance(point)
        if distance <= tol and (best is None or distance < best[0]):
            projected = exterior.interpolate(exterior.project(point))
            best = (distance, (projected.x, projected.y))
    return None if best is None else best[1]


# ── fixtures ────────────────────────────────────────────────────────

def _random_vertex_grid(rng, cell, n=1500, span=1500.0):
    grid = defaultdict(list)
    for _ in range(n):
        x = rng.uniform(-span, span)
        y = rng.uniform(-span, span)
        grid[(int(x / cell), int(y / cell))].append((x, y))
    return grid


def _runway_boundary(x0, y0, angle, length, width, tol):
    dx, dy = math.cos(angle), math.sin(angle)
    nx, ny = -dy, dx
    ring = [
        (x0 + dx * length / 2 + nx * width / 2,
         y0 + dy * length / 2 + ny * width / 2),
        (x0 + dx * length / 2 - nx * width / 2,
         y0 + dy * length / 2 - ny * width / 2),
        (x0 - dx * length / 2 - nx * width / 2,
         y0 - dy * length / 2 - ny * width / 2),
        (x0 - dx * length / 2 + nx * width / 2,
         y0 - dy * length / 2 + ny * width / 2),
    ]
    exterior = LineString(Polygon(ring).exterior.coords)
    b = exterior.bounds
    return ((b[0] - tol, b[1] - tol, b[2] + tol, b[3] + tol), exterior)


# ── twins ───────────────────────────────────────────────────────────

class TestPointsNearEdgeBandWalk:
    """The band walk yields a different SUPERSET than the box scan; what
    must not change is what the callers keep from it."""

    def test_matches_box_scan_after_the_callers_exact_filter(self):
        rng = random.Random(7)
        cell, tol = 5.0, 0.5
        for _ in range(120):
            grid = _random_vertex_grid(rng, cell)
            ax, ay = rng.uniform(-1200, 1200), rng.uniform(-1200, 1200)
            bx, by = rng.uniform(-1200, 1200), rng.uniform(-1200, 1200)
            # Seed vertices ON the segment: the only ones that survive.
            for _k in range(6):
                t = rng.uniform(0.05, 0.95)
                x = ax + (bx - ax) * t + rng.uniform(-tol, tol) * 0.4
                y = ay + (by - ay) * t + rng.uniform(-tol, tol) * 0.4
                grid[(int(x / cell), int(y / cell))].append((x, y))
            reference = _tjunctions_on_edge(
                ax, ay, bx, by,
                list(_reference_points_near_edge(
                    grid, cell, ax, ay, bx, by, tol)), tol)
            fast = _tjunctions_on_edge(
                ax, ay, bx, by,
                list(_points_near_edge(
                    grid, cell, ax, ay, bx, by, tol)), tol)
            assert fast == reference

    def test_short_and_degenerate_edges_match(self):
        rng = random.Random(11)
        cell, tol = 5.0, 0.5
        grid = _random_vertex_grid(rng, cell, n=400, span=60.0)
        cases = [
            (0.0, 0.0, 0.0, 0.0),          # degenerate
            (0.0, 0.0, 0.3, 0.0),          # sub-cell
            (-3.0, -3.0, 3.0, 3.0),        # across the sign-flip cell
            (-40.0, 1.0, 40.0, 1.0),       # axis-aligned, long
            (1.0, -40.0, 1.0, 40.0),       # axis-aligned, vertical
        ]
        for ax, ay, bx, by in cases:
            reference = _tjunctions_on_edge(
                ax, ay, bx, by,
                list(_reference_points_near_edge(
                    grid, cell, ax, ay, bx, by, tol)), tol)
            fast = _tjunctions_on_edge(
                ax, ay, bx, by,
                list(_points_near_edge(
                    grid, cell, ax, ay, bx, by, tol)), tol)
            assert fast == reference

    def test_every_true_positive_is_yielded(self):
        """The contract is a SUPERSET of the points within tol — proved
        against brute force, not against the other scan."""
        rng = random.Random(13)
        cell, tol = 5.0, 0.5
        grid = _random_vertex_grid(rng, cell, n=800, span=400.0)
        every = [pt for bucket in grid.values() for pt in bucket]
        for _ in range(40):
            ax, ay = rng.uniform(-300, 300), rng.uniform(-300, 300)
            bx, by = rng.uniform(-300, 300), rng.uniform(-300, 300)
            segment = LineString([(ax, ay), (bx, by)])
            truth = {pt for pt in every
                     if segment.distance(Point(pt)) <= tol}
            got = set(_points_near_edge(grid, cell, ax, ay, bx, by, tol))
            assert truth <= got


class TestCrossingCandidatePairs:
    """The bulk STRtree query + vectorised endpoint-share filter must
    enumerate the SAME pair set as the per-line loop it replaces (the
    crossing resolver sorts what it collects per edge, so only the set
    can reach an output)."""

    @staticmethod
    def _reference_pairs(tree, lines, edges):
        out = set()
        for ei, ln in enumerate(lines):
            for ej in tree.query(ln):
                if ej <= ei:
                    continue
                a0, a1 = edges[ei]
                b0, b1 = edges[ej]
                if {a0, a1} & {b0, b1}:
                    continue
                out.add((ei, int(ej)))
        return out

    def test_matches_the_per_line_loop(self):
        from shapely.strtree import STRtree
        rng = random.Random(31)
        for _ in range(20):
            edges = []
            # Rings, so shared endpoints (the filtered case) are common.
            for _r in range(25):
                cx, cy = rng.uniform(-200, 200), rng.uniform(-200, 200)
                ring = [(cx + rng.uniform(-30, 30), cy + rng.uniform(-30, 30))
                        for _k in range(6)]
                for k in range(len(ring)):
                    a, b = ring[k], ring[(k + 1) % len(ring)]
                    if a != b:
                        edges.append((a, b))
            lines = _edge_linestrings(edges)
            tree = STRtree(lines)
            reference = self._reference_pairs(tree, lines, edges)
            fast = {(int(i), int(j))
                    for i, j in _crossing_candidate_pairs(tree, lines, edges)}
            assert fast == reference

    def test_edge_linestrings_match_one_by_one_construction(self):
        rng = random.Random(37)
        edges = [((rng.uniform(-50, 50), rng.uniform(-50, 50)),
                  (rng.uniform(-50, 50), rng.uniform(-50, 50)))
                 for _ in range(500)]
        built = _edge_linestrings(edges)
        for line, (a, b) in zip(built, edges):
            assert list(line.coords) == list(LineString([a, b]).coords)


class TestRunwayProjectionBatch:
    def test_matches_the_per_cluster_scan(self):
        rng = random.Random(17)
        tol = 1.5
        for _ in range(12):
            boundaries = [
                _runway_boundary(rng.uniform(-500, 500),
                                 rng.uniform(-500, 500),
                                 rng.uniform(0.0, math.pi),
                                 rng.uniform(200.0, 3000.0),
                                 rng.uniform(20.0, 60.0), tol)
                for _k in range(rng.randint(1, 5))]
            # A DUPLICATE boundary forces exact-tie distances, where the
            # scan's "first strictly-smaller wins" rule is observable.
            boundaries.append(boundaries[0])
            means = [(rng.uniform(-700, 700), rng.uniform(-700, 700))
                     for _k in range(400)]
            for _k in range(120):
                _b, exterior = boundaries[rng.randrange(len(boundaries))]
                on = exterior.interpolate(rng.uniform(0.0, exterior.length))
                means.append((on.x + rng.uniform(-tol, tol) * 0.5,
                              on.y + rng.uniform(-tol, tol) * 0.5))
            reference = [
                _reference_project_onto_runway_boundary(px, py,
                                                        boundaries, tol)
                for px, py in means]
            assert _project_means_onto_runway_boundaries(
                means, boundaries, tol) == reference

    def test_empty_inputs(self):
        assert _project_means_onto_runway_boundaries([], [], 1.5) == []
        assert _project_means_onto_runway_boundaries(
            [(0.0, 0.0)], [], 1.5) == [None]


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
