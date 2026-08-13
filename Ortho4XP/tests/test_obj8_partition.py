"""Workstream W2 acceptance tests for ``auto_patch.obj8_partition``.

The theory is ``docs/obj8_structure_partition.md``: structures are the
connected components of the epsilon-contact graph (invariant I-6), the
narrow phase prunes 3D bounding-box over-merges, and a pair that cannot
be proved apart keeps its edge (invariant I-20).  The trap test — a wall
abutting a roof WITHOUT shared vertices is ONE structure — encodes the
partition document's headline finding: vertex connectivity is not
contact (4,453 torn abutments at KCLT).
"""

from __future__ import annotations

import pytest

from auto_patch import obj8_partition
from auto_patch.obj8_partition import (
    connected_structures,
    contact_graph,
    weld_parts,
)


def box_geometry(
    minimum_x: float,
    minimum_y: float,
    minimum_z: float,
    size: float,
    vertices: list[tuple[float, float, float]],
) -> list[tuple[int, int, int]]:
    """Append one closed box to ``vertices`` and return its triangles."""
    base = len(vertices)
    for bit_z in (0, 1):
        for bit_y in (0, 1):
            for bit_x in (0, 1):
                vertices.append(
                    (
                        minimum_x + bit_x * size,
                        minimum_y + bit_y * size,
                        minimum_z + bit_z * size,
                    )
                )
    corner_triangles = [
        (0, 1, 3), (0, 3, 2),
        (4, 7, 5), (4, 6, 7),
        (0, 5, 1), (0, 4, 5),
        (2, 3, 7), (2, 7, 6),
        (0, 2, 6), (0, 6, 4),
        (1, 5, 7), (1, 7, 3),
    ]
    return [tuple(base + index for index in triangle) for triangle in corner_triangles]


def quad_triangles(
    corner_a: tuple[float, float, float],
    corner_b: tuple[float, float, float],
    corner_c: tuple[float, float, float],
    corner_d: tuple[float, float, float],
    vertices: list[tuple[float, float, float]],
) -> list[tuple[int, int, int]]:
    """Append one quad (two triangles, four fresh vertices)."""
    base = len(vertices)
    vertices.extend([corner_a, corner_b, corner_c, corner_d])
    return [(base, base + 1, base + 2), (base, base + 2, base + 3)]


def structures_of(
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    epsilon_metres: float,
) -> list[list[int]]:
    parts = weld_parts(vertices, triangles)
    edges = contact_graph(vertices, parts, epsilon_metres)
    return connected_structures(len(parts), edges)


# ---------------------------------------------------------------------------
# weld_parts — level 1 of the hierarchy
# ---------------------------------------------------------------------------

def test_weld_parts_merges_duplicated_seam_positions():
    """Exporters duplicate a position once per texture seam; without the
    positional weld one wall shatters into two parts."""
    vertices: list[tuple[float, float, float]] = []
    # Two triangles forming one quad, sharing an edge only by POSITION:
    # six vertex entries, four unique positions.
    left = quad_triangles(
        (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 3.0, 0.0), (0.0, 3.0, 0.0),
        vertices,
    )[:1]
    right_base = len(vertices)
    vertices.extend(
        [(4.0, 0.0, 0.0), (4.0, 3.0, 0.0), (0.0, 3.0, 0.0)]
    )
    right = [(right_base, right_base + 1, right_base + 2)]
    parts = weld_parts(vertices, left + right)
    assert len(parts) == 1
    assert sorted(len(part) for part in parts) == [2]


def test_weld_parts_keeps_disjoint_boxes_apart():
    vertices: list[tuple[float, float, float]] = []
    first = box_geometry(0.0, 0.0, 0.0, 10.0, vertices)
    second = box_geometry(13.0, 0.0, 0.0, 10.0, vertices)
    parts = weld_parts(vertices, first + second)
    assert len(parts) == 2
    assert sorted(len(part) for part in parts) == [12, 12]


# ---------------------------------------------------------------------------
# contact graph — the trap test and the separations
# ---------------------------------------------------------------------------

def test_wall_abutting_roof_without_shared_vertices_is_one_structure():
    """THE trap (partition document section 1): triangle soup abuts
    without sharing vertices.  The wall's top edge sits 0.1 m beneath the
    roof plane, with no coincident vertex positions — vertex
    connectivity says two parts, contact says one structure."""
    vertices: list[tuple[float, float, float]] = []
    # Vertical wall: x 0..4, y 0..3, z = 0.
    wall = quad_triangles(
        (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 3.0, 0.0), (0.0, 3.0, 0.0),
        vertices,
    )
    # Horizontal roof slab 0.1 m above the wall top, overhanging it on
    # every side so the wall's top vertices project into the roof's
    # interior.  No vertex is shared, no positions coincide.
    roof = quad_triangles(
        (-1.0, 3.1, -1.0), (5.0, 3.1, -1.0), (5.0, 3.1, 1.0), (-1.0, 3.1, 1.0),
        vertices,
    )
    parts = weld_parts(vertices, wall + roof)
    assert len(parts) == 2  # vertex connectivity alone would tear here
    structures = structures_of(vertices, wall + roof, epsilon_metres=0.25)
    assert len(structures) == 1


def test_two_boxes_three_metres_apart_are_two_structures():
    vertices: list[tuple[float, float, float]] = []
    triangles = box_geometry(0.0, 0.0, 0.0, 10.0, vertices)
    triangles += box_geometry(13.0, 0.0, 0.0, 10.0, vertices)
    structures = structures_of(vertices, triangles, epsilon_metres=0.25)
    assert len(structures) == 2


def test_two_boxes_within_epsilon_merge():
    vertices: list[tuple[float, float, float]] = []
    triangles = box_geometry(0.0, 0.0, 0.0, 10.0, vertices)
    triangles += box_geometry(10.2, 0.0, 0.0, 10.0, vertices)
    structures = structures_of(vertices, triangles, epsilon_metres=0.25)
    assert len(structures) == 1


def test_jetbridge_above_shed_stays_separate_in_three_dimensions():
    """The 2D bounding box (the prototype's) merges a slab at y = 6 m
    with the shed beneath it; the 3D box must not."""
    vertices: list[tuple[float, float, float]] = []
    shed = box_geometry(0.0, 0.0, 0.0, 4.0, vertices)
    elevated_slab = quad_triangles(
        (0.0, 6.0, 0.0), (4.0, 6.0, 0.0), (4.0, 6.0, 4.0), (0.0, 6.0, 4.0),
        vertices,
    )
    structures = structures_of(
        vertices, shed + elevated_slab, epsilon_metres=0.25
    )
    assert len(structures) == 2


def test_interlocking_parts_with_overlapping_boxes_stay_separate():
    """Narrow-phase acceptance: two parts whose 3D bounding boxes overlap
    while their surfaces stay well apart (an interlocking L arrangement)
    must remain separate structures — the broad phase alone would fuse
    them."""
    vertices: list[tuple[float, float, float]] = []
    # An L: one arm along x (z 0..1), one arm along z (x 0..1).
    arm_along_x = box_geometry(0.0, 0.0, 0.0, 1.0, vertices)
    arm_along_x += box_geometry(1.0, 0.0, 0.0, 1.0, vertices)
    arm_along_x += box_geometry(2.0, 0.0, 0.0, 1.0, vertices)
    arm_along_z = box_geometry(0.0, 0.0, 1.0, 1.0, vertices)
    arm_along_z += box_geometry(0.0, 0.0, 2.0, 1.0, vertices)
    l_shape = arm_along_x + arm_along_z
    # A box nested in the L's notch corner: its 3D bounding box overlaps
    # the L's (which spans x 0..3, z 0..3), but its surfaces stay 1 m
    # from both arms.
    nested_box = box_geometry(2.0, 0.0, 2.0, 1.0, vertices)

    parts = weld_parts(vertices, l_shape + nested_box)
    assert len(parts) == 2

    # The L's bounding box contains the nested box's entirely.
    edges = contact_graph(vertices, parts, epsilon_metres=0.25)
    assert edges == set()
    structures = connected_structures(len(parts), edges)
    assert len(structures) == 2


def _diagonal_triangle_and_distant_speck() -> tuple[
    list[tuple[float, float, float]], list[tuple[int, int, int]]
]:
    """A large diagonal triangle plus a small triangle floating deep
    inside its bounding box but ~2 m from its surface.  The box
    restriction cannot empty the candidate sets here (the speck sits
    inside the big triangle's inflated bounding box), so the narrow
    phase must actually spend point-times-triangle work to prove the
    pair apart."""
    vertices: list[tuple[float, float, float]] = [
        (0.0, 0.0, 0.0),
        (4.0, 4.0, 0.0),
        (4.0, 0.0, 4.0),
        (3.5, 3.5, 3.5),
        (3.6, 3.5, 3.5),
        (3.5, 3.6, 3.5),
    ]
    triangles = [(0, 1, 2), (3, 4, 5)]
    return vertices, triangles


def test_distant_speck_inside_bounding_box_is_proved_apart():
    vertices, triangles = _diagonal_triangle_and_distant_speck()
    structures = structures_of(vertices, triangles, epsilon_metres=0.25)
    assert len(structures) == 2


def test_budget_exhaustion_keeps_the_edge(monkeypatch):
    """Invariant I-20: a pair the narrow phase cannot afford to test is
    kept, never pruned — over-merging costs centimetres, tearing is
    unrecoverable.  With the budget forced to zero, the same pair the
    previous test proved apart must now merge on doubt."""
    monkeypatch.setattr(
        obj8_partition, "NARROW_PHASE_POINT_TRIANGLE_BUDGET", 0
    )
    vertices, triangles = _diagonal_triangle_and_distant_speck()
    structures = structures_of(vertices, triangles, epsilon_metres=0.25)
    assert len(structures) == 1


# ---------------------------------------------------------------------------
# connected_structures
# ---------------------------------------------------------------------------

def test_connected_structures_groups_and_isolates():
    structures = connected_structures(5, {(0, 1), (2, 3)})
    assert structures == [[0, 1], [2, 3], [4]]


def test_connected_structures_transitive_chain():
    structures = connected_structures(4, {(0, 1), (1, 2), (2, 3)})
    assert structures == [[0, 1, 2, 3]]


def test_connected_structures_no_edges():
    assert connected_structures(3, set()) == [[0], [1], [2]]


def test_degenerate_edge_not_a_number_is_contact_not_separation():
    """Found live at HECA: a triangle with a duplicated corner makes the
    edge branches of the point-triangle test divide 0/0, and the
    resulting not-a-number used to poison ``ndarray.min()`` for the whole
    pair — flipping genuine contact to "proved apart" (the tear
    invariant I-20 forbids).  A degenerate sliver whose spine passes
    through a neighbouring part's vertex must merge with it."""
    from auto_patch.obj8_partition import contact_graph, weld_parts

    vertices = [
        # Part 1: degenerate sliver — corners 0 and 1 are the SAME
        # position, so edge_ab has zero length.
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        # Part 2: a real triangle with one vertex exactly on the
        # sliver's spine midpoint (true distance 0).
        (1.0, 0.0, 0.0),
        (1.0, 5.0, 0.0),
        (1.0, 0.0, 5.0),
    ]
    triangles = [(0, 1, 2), (3, 4, 5)]
    parts = weld_parts(vertices, triangles)
    assert len(parts) == 2
    edges = contact_graph(vertices, parts, epsilon_metres=0.25)
    assert edges, (
        "degenerate-edge not-a-number separated two parts in true contact"
    )


# ---------------------------------------------------------------------------
# split_oversized_components_with_edges — the re-derived contact edges
# per-cluster seating consumes (per-cluster seating spec section 3.1)
# ---------------------------------------------------------------------------

def _oversized_chain():
    """Two two-box buildings 900 m apart, joined by a long thin fence,
    with a short trim plate on the first building.

    Everything is 0.1 m apart — inside the contact epsilon, outside the
    weld tolerance — so the parts CONTACT without sharing vertices,
    which is how a payware bake is actually assembled.  The component
    spans 940 m, so the connector split re-partitions it: the fence is
    the connector (too long to reattach), the trim is building-internal
    and must come back.
    """
    vertices: list[tuple[float, float, float]] = []
    triangles = box_geometry(0.0, 0.0, 0.0, 20.0, vertices)        # A1
    triangles += box_geometry(20.1, 0.0, 0.0, 20.0, vertices)      # A2
    triangles += box_geometry(900.0, 0.0, 0.0, 20.0, vertices)     # B1
    triangles += box_geometry(920.1, 0.0, 0.0, 20.0, vertices)     # B2
    triangles += quad_triangles(                                   # fence
        (40.2, 0.0, 0.0), (899.9, 0.0, 0.0),
        (899.9, 1.0, 0.0), (40.2, 1.0, 0.0), vertices)
    triangles += quad_triangles(                                   # trim
        (0.0, 20.1, 0.0), (10.0, 20.1, 0.0),
        (10.0, 20.1, 10.0), (0.0, 20.1, 10.0), vertices)
    return vertices, triangles


def test_split_returns_spanning_edges_for_every_group_it_builds():
    vertices, triangles = _oversized_chain()
    parts = weld_parts(vertices, triangles)
    assert len(parts) == 6
    edges = contact_graph(vertices, parts, epsilon_metres=0.25)
    groups = connected_structures(len(parts), edges)
    assert len(groups) == 1, "the fence chains everything into one"

    split_groups, split_count, edges_by_group = (
        obj8_partition.split_oversized_components_with_edges(
            vertices, parts, groups, epsilon_metres=0.25))
    assert split_count == 1
    # Two buildings plus the fence as its own singleton; the trim came
    # back to the building it belongs to.
    assert sorted(len(group) for group in split_groups) == [1, 2, 3]
    assert len(edges_by_group) == len(split_groups)

    for group, group_edges in zip(split_groups, edges_by_group):
        # Every group here was BUILT by the split, so none may report
        # "use the caller's edges" — and each edge set must SPAN its
        # group, which is exactly what seating verifies before it cuts.
        assert group_edges is not None
        assert len(group_edges) == len(group) - 1
        members = set(group)
        assert all(
            left in members and right in members
            for left, right in group_edges)
        reached = {group[0]}
        for _pass in range(len(group)):
            for left, right in group_edges:
                if left in reached or right in reached:
                    reached.update((left, right))
        assert reached == members


def test_split_leaves_untouched_groups_edgeless_for_the_caller():
    """A group the split did not build reports ``None`` — the caller's
    own contact edges still describe it, and re-deriving them would be
    work for nothing."""
    vertices: list[tuple[float, float, float]] = []
    triangles = box_geometry(0.0, 0.0, 0.0, 20.0, vertices)
    parts = weld_parts(vertices, triangles)
    edges = contact_graph(vertices, parts, epsilon_metres=0.25)
    groups = connected_structures(len(parts), edges)
    split_groups, split_count, edges_by_group = (
        obj8_partition.split_oversized_components_with_edges(
            vertices, parts, groups, epsilon_metres=0.25))
    assert split_count == 0
    assert split_groups == groups
    assert edges_by_group == [None]


def test_the_plain_split_wrapper_still_returns_two_values():
    """``split_oversized_components`` keeps its shape for callers that
    do not need the edges."""
    vertices, triangles = _oversized_chain()
    parts = weld_parts(vertices, triangles)
    edges = contact_graph(vertices, parts, epsilon_metres=0.25)
    groups = connected_structures(len(parts), edges)
    plain = obj8_partition.split_oversized_components(
        vertices, parts, groups, epsilon_metres=0.25)
    with_edges = obj8_partition.split_oversized_components_with_edges(
        vertices, parts, groups, epsilon_metres=0.25)
    assert plain == with_edges[:2]


# ---------------------------------------------------------------------------
# perf P3 lane G — the prefilter and the shared-geometry layers, twinned
# against the machinery they replace (a cache or a prefilter that cannot
# be shown equal to the full scan is a second answer, not a speed-up)
# ---------------------------------------------------------------------------

def test_far_degenerate_triangle_still_claims_contact():
    """THE PREFILTER'S EXEMPTION, twinned.

    A triangle with a zero-length edge answers 0.0 — contact — for a
    point ARBITRARILY far away: the edge branch divides 0/0 and the
    kernel sanitises the not-a-number to 0.0 (invariant I-20, numerical
    doubt merges).  That answer is not a function of distance, so the
    per-pair box prefilter must never drop such a pair; the magnet
    triangles bypass the filter and see every point.

    The specimen is the 0/0 case exactly, in the only configuration
    where it can still be reached: the candidate set is filtered against
    the WHOLE point cloud's box, so the sliver survives that filter here
    (the cloud straddles it in y) while NEITHER point is within epsilon
    of the sliver's own box.  The per-pair prefilter would drop both —
    and with them a contact the historical kernel reports.
    """
    from auto_patch.obj8_partition import (
        _PartGeometry,
        _point_triangle_minimum_distances,
        _vertex_to_triangle_proof,
    )
    import numpy

    vertex_array = numpy.array(
        [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        dtype=numpy.float64,
    )
    sliver = _PartGeometry(vertex_array, [(0, 1, 2)])
    assert sliver.degenerate_triangles.all()

    straddling_points = numpy.array([[0.5, 10.0, 0.0],
                                     [0.5, -10.0, 0.0]])
    # What the unfiltered kernel says — the behaviour being preserved.
    with numpy.errstate(invalid="ignore", divide="ignore"):
        historical = _point_triangle_minimum_distances(
            straddling_points,
            sliver.corner_a, sliver.corner_b, sliver.corner_c)
    assert historical.min() == 0.0, (
        "specimen no longer reaches the 0/0 edge branch")

    contact, proved = _vertex_to_triangle_proof(
        straddling_points, sliver, 0.25)
    assert proved
    assert contact, (
        "a degenerate triangle's merge-on-doubt claim was prefiltered "
        "away — the prefilter is only exact for proper triangles"
    )


def test_prefilter_agrees_with_the_full_grid_on_proper_triangles():
    """The prefilter is a lossless restriction, not an approximation:
    for a proper (non-degenerate) part its verdict must equal the one
    the unfiltered kernel gives over the whole point x triangle grid, at
    a separation either side of epsilon."""
    from auto_patch.obj8_partition import (
        _PartGeometry,
        _point_triangle_minimum_distances,
        _vertex_to_triangle_proof,
    )
    import numpy

    vertices: list[tuple[float, float, float]] = []
    triangles = box_geometry(0.0, 0.0, 0.0, 4.0, vertices)
    vertex_array = numpy.asarray(vertices, dtype=numpy.float64)
    box = _PartGeometry(vertex_array, triangles)
    assert not box.degenerate_triangles.any()

    for offset in (0.1, 0.2, 0.24, 0.26, 1.0, 25.0):
        points = numpy.array([[2.0, 4.0 + offset, 2.0],
                              [50.0, 50.0, 50.0]])
        contact, proved = _vertex_to_triangle_proof(points, box, 0.25)
        assert proved
        with numpy.errstate(invalid="ignore", divide="ignore"):
            full = _point_triangle_minimum_distances(
                points, box.corner_a, box.corner_b, box.corner_c)
        assert contact == bool(full.min() <= 0.25), offset


def test_shared_part_geometries_give_the_same_partition():
    """THE SHARED-GEOMETRY LAYER, twinned.  ``contact_graph`` and
    ``split_oversized_components_with_edges`` accept a caller's vertex
    array and part geometries so a partition builds them once instead of
    three times; they are pure derived data, so both spellings must
    produce identical results."""
    import numpy

    vertices, triangles = _oversized_chain()
    parts = weld_parts(vertices, triangles)
    vertex_array = numpy.asarray(vertices, dtype=numpy.float64)
    geometries = [
        obj8_partition._PartGeometry(vertex_array, part) for part in parts
    ]

    own_edges = contact_graph(vertices, parts, epsilon_metres=0.25)
    shared_edges = contact_graph(
        vertices, parts, epsilon_metres=0.25,
        vertex_array=vertex_array, part_geometries=geometries)
    assert own_edges == shared_edges

    groups = connected_structures(len(parts), own_edges)
    own_split = obj8_partition.split_oversized_components_with_edges(
        vertices, parts, groups, epsilon_metres=0.25)
    shared_split = obj8_partition.split_oversized_components_with_edges(
        vertices, parts, groups, epsilon_metres=0.25,
        vertex_array=vertex_array, part_geometries=geometries)
    assert own_split == shared_split

    # And a SECOND pass over the same geometry objects — whose lazy
    # caches (k-d tree, cell indexes) are now warm — must still agree:
    # a warmed cache that changed an answer would be the whole point of
    # the twin.
    assert contact_graph(
        vertices, parts, epsilon_metres=0.25,
        vertex_array=vertex_array, part_geometries=geometries) == own_edges


def test_measured_plan_extents_are_the_measurement_they_replace():
    """The connector split measures each part's plan extents once and
    hands them to the glue and linear-connector tests; passing them in
    must not change either verdict."""
    import numpy

    vertices, triangles = _oversized_chain()
    parts = weld_parts(vertices, triangles)
    vertex_array = numpy.asarray(vertices, dtype=numpy.float64)
    for part in parts:
        extents = obj8_partition.part_plan_extents(vertex_array, part)
        assert (
            obj8_partition.part_is_chain_glue(vertex_array, part, extents)
            == obj8_partition.part_is_chain_glue(vertex_array, part)
        )
        assert (
            obj8_partition.part_is_linear_connector(
                vertex_array, part, extents)
            == obj8_partition.part_is_linear_connector(vertex_array, part)
        )


def test_weld_parts_ignores_repeat_sightings_of_one_vertex_index():
    """The weld pass now visits each distinct vertex INDEX once.  A fan
    of triangles sharing one apex — the index seen many times — must
    weld exactly as it did when every sighting was re-rounded."""
    vertices = [
        (0.0, 0.0, 0.0),          # apex, shared by every triangle
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
        # a duplicate POSITION of the apex under a different index
        (0.0, 0.0, 0.0004),
        (5.0, 5.0, 5.0),
        (6.0, 5.0, 5.0),
    ]
    triangles = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
                 (5, 6, 7)]
    parts = weld_parts(vertices, triangles)
    assert len(parts) == 1, (
        "the fan and the position-duplicate apex are one welded part")
    assert parts[0] == triangles
