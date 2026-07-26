"""``weld_parts`` local-index-space equivalence (2026-07-26 performance fix).

``object_anchor.structure_deltas`` re-welds each structure's triangles
against the POOL-WIDE vertex array (8.09 M vertices at +30+031) while
only the triangles are per-structure.  The old implementation opened
with ``parent = list(range(len(vertices)))``, making the call
Θ(pool vertices) instead of Θ(structure triangles) — 783.6 s, 57.8 % of
the tile build.

The fix relabels the touched vertices into a local index space.  That is
pure bookkeeping, so this module pins the ONLY acceptable outcome:
byte-identical output — same parts, same order, same triangle order —
against a verbatim copy of the pre-fix implementation, on synthetic
multi-part / shared-vertex / degenerate cases and on randomised soups.
"""

from __future__ import annotations

import random
from collections import defaultdict

from auto_patch.obj8_partition import VERTEX_WELD_DECIMALS, weld_parts


def weld_parts_pre_fix(vertices, triangles):
    """Verbatim pre-2026-07-26 ``weld_parts`` (commit 5eecc3f)."""
    parent = list(range(len(vertices)))

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root

    position_to_vertex = {}
    for triangle in triangles:
        for index in triangle:
            vertex = vertices[index]
            key = (
                round(vertex[0], VERTEX_WELD_DECIMALS),
                round(vertex[1], VERTEX_WELD_DECIMALS),
                round(vertex[2], VERTEX_WELD_DECIMALS),
            )
            if key in position_to_vertex:
                union(index, position_to_vertex[key])
            else:
                position_to_vertex[key] = index

    for first, second, third in triangles:
        union(first, second)
        union(second, third)

    grouped = defaultdict(list)
    for triangle in triangles:
        grouped[find(triangle[0])].append(triangle)
    return list(grouped.values())


def assert_identical(vertices, triangles):
    """Both implementations must agree down to list order."""
    expected = weld_parts_pre_fix(vertices, triangles)
    actual = weld_parts(vertices, triangles)
    assert actual == expected


# ---------------------------------------------------------------------------
# synthetic cases
# ---------------------------------------------------------------------------

def test_empty_triangle_soup_matches():
    assert_identical([(0.0, 0.0, 0.0)] * 4, [])
    assert weld_parts([(0.0, 0.0, 0.0)] * 4, []) == []


def test_single_triangle_matches():
    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
    assert_identical(vertices, [(0, 1, 2)])


def test_two_disjoint_parts_keep_their_order():
    vertices = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
        (50.0, 0.0, 0.0), (51.0, 0.0, 0.0), (50.0, 0.0, 1.0),
    ]
    triangles = [(3, 4, 5), (0, 1, 2)]
    assert_identical(vertices, triangles)
    assert [len(part) for part in weld_parts(vertices, triangles)] == [1, 1]


def test_shared_position_welds_across_parts():
    """Duplicated positions (texture seam) merge two index-disjoint fans."""
    vertices = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
        # same three positions again, different indices
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
    ]
    triangles = [(0, 1, 2), (3, 4, 5)]
    assert_identical(vertices, triangles)
    assert len(weld_parts(vertices, triangles)) == 1


def test_weld_only_below_the_rounding_threshold():
    epsilon = 10.0 ** -(VERTEX_WELD_DECIMALS + 3)
    vertices = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
        (epsilon, 0.0, 0.0), (5.0, 0.0, 0.0), (5.0, 0.0, 1.0),
        (0.5, 0.0, 0.0), (9.0, 0.0, 0.0), (9.0, 0.0, 1.0),
    ]
    triangles = [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    assert_identical(vertices, triangles)
    parts = weld_parts(vertices, triangles)
    # the epsilon-offset fan welds onto the first; the 0.5 m one does not
    assert len(parts) == 2


def test_degenerate_triangles_match():
    """Repeated indices and zero-area triangles take the same path."""
    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    triangles = [(0, 0, 0), (1, 1, 2), (2, 2, 2), (0, 1, 2)]
    assert_identical(vertices, triangles)


def test_unreferenced_vertices_never_form_parts():
    """A huge trailing vertex array (the pool-wide case) changes nothing."""
    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
    vertices += [(float(index), 7.0, 0.0) for index in range(5000)]
    triangles = [(0, 1, 2)]
    assert_identical(vertices, triangles)
    assert weld_parts(vertices, triangles) == [[(0, 1, 2)]]


def test_high_index_triangles_in_a_sparse_pool_match():
    """Only the tail of a big pool array is touched — the structure_deltas
    shape: pool-wide vertices, a handful of per-structure triangles."""
    vertices = [(float(index), 0.0, 0.0) for index in range(20000)]
    triangles = [(19997, 19998, 19999), (19000, 19001, 19002)]
    assert_identical(vertices, triangles)


# ---------------------------------------------------------------------------
# randomised soups — the real defence
# ---------------------------------------------------------------------------

def test_randomised_soups_match_the_pre_fix_implementation():
    generator = random.Random(20260726)
    for _case in range(60):
        vertex_count = generator.randint(6, 200)
        # a coarse coordinate grid so duplicate positions (and hence
        # cross-part welds) are common
        vertices = [
            (
                float(generator.randint(0, 6)),
                float(generator.randint(0, 3)),
                float(generator.randint(0, 6)),
            )
            for _index in range(vertex_count)
        ]
        triangles = [
            (
                generator.randrange(vertex_count),
                generator.randrange(vertex_count),
                generator.randrange(vertex_count),
            )
            for _index in range(generator.randint(0, 120))
        ]
        assert_identical(vertices, triangles)


def test_randomised_sparse_pool_slices_match():
    """Pool-wide array, per-structure triangle slices — old vs new."""
    generator = random.Random(31415)
    vertices = [
        (
            float(generator.randint(0, 400)),
            float(generator.randint(0, 20)),
            float(generator.randint(0, 400)),
        )
        for _index in range(4000)
    ]
    for _case in range(30):
        base = generator.randrange(0, 3900)
        triangles = [
            (
                base + generator.randrange(0, 100),
                base + generator.randrange(0, 100),
                base + generator.randrange(0, 100),
            )
            for _index in range(generator.randint(1, 80))
        ]
        assert_identical(vertices, triangles)
