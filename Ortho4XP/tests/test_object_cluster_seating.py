"""Per-cluster object seating — the seat-disagreement cut, bake-and-pad,
and the bridge rule.

Design: ``docs/specs/per-cluster-object-seating-spec.md`` sections 3.2,
4.2, 4.3 and 5.1.  Origin (owner, 2026-07-26, HECA "a ton of floating
objects"): a heavy payware pack welds its whole terminal complex into
ONE km-scale contact component.  On flat ground (KCLT 0.022 m / KBNA
0.005 m of ground-contact relief) one rigid seat serves it perfectly; at
HECA the same topology sits on 26 m of REAL relief, the rigid-seat span
limit refuses the lot, and — with supporter fate — the refusal cascades
to 6,339 inheritors.  Correct, and useless.

What these tests pin, all hermetic (synthetic geometry against
hand-written meshes in ``tmp_path``, no network, no X-Plane install):

* THE CUT (section 3.2).  Two four-object groups on a 24 m terrain step,
  chained into one structure by a single ground-to-ground contact: with
  the gate ON the contact is cut and both halves seat on their own
  plateau; with the gate OFF the whole structure is refused, exactly as
  it is today.  Byte-for-byte legacy behaviour when the gate is off is
  the primary regression guarantee, and a structure whose relief is
  small at the T scale must produce IDENTICAL deltas with the gate on
  (the KCLT/KBNA degeneracy guarantee, section 2).
* BAKE-AND-PAD (section 4.3).  A cluster that no single offset can seat
  — a long building climbing a gentle slope, every contact edge under T
  — is no longer refused: it seats at its median and raises
  ``ClusterPadRequest``s for the residual groups terrain must close.
* THE BRIDGE RULE (section 4.2a).  An elevated component contacting two
  clusters joins its majority-contact side and the residual toward the
  other is REPORTED, never averaged across.
* THE PAD LAW's clip (section 5.1 clause 2, owner ruling R2): pavement
  wins absolutely — a pad footprint is differenced against the airside
  polygons before it can be emitted, and a pad wholly inside pavement is
  inadmissible rather than shrunken.
"""

from __future__ import annotations

import math
import os

import pytest

from auto_patch import (
    config,
    obj8_reader,
    object_anchor,
    object_clusters,
    object_footprints,
    object_rebake,
)
from auto_patch.mesh_sampler import MeshElevationSampler
from auto_patch.object_anchor import (
    discover_object_pools,
    partition_structures,
    structure_deltas,
)

from test_object_anchor import (
    CONTACT_EPSILON_METRES,
    box_vertices_and_triangles,
    make_geometry,
    make_placement,
    metres_per_degree_longitude_at,
    write_mesh_file,
)

GROUND_SPAN_SKIP_PHRASE = object_anchor.GROUND_SPAN_SKIP_REASON_PHRASE

BASE_LATITUDE = 50.0
BASE_LONGITUDE = 10.0
METRES_PER_DEGREE_LONGITUDE = metres_per_degree_longitude_at(BASE_LATITUDE)
METRES_PER_DEGREE_LATITUDE = obj8_reader.METRES_PER_DEGREE_LATITUDE

# Terrain of the step mesh: 70 m west of the step, 94 m east of it —
# HECA's Private Hall (~72.6-81.5 m) and T23 (~93.7-99.5 m) zones,
# abstracted to two plateaus and the 24 m that separates them.
LOW_GROUND_METRES = 70.0
HIGH_GROUND_METRES = 94.0
STEP_EAST_METRES = 40.0
STEP_WIDTH_METRES = 0.2


# ── mesh construction ─────────────────────────────────────────────────


def _longitude_of(east_metres: float) -> float:
    return BASE_LONGITUDE + east_metres / METRES_PER_DEGREE_LONGITUDE


def _write_profile_mesh(path, east_metres_columns, elevation_of_east):
    """A mesh whose elevation is a function of EAST only, sampled at the
    given columns and constant across a wide latitude band.

    Piecewise-linear in longitude between columns, constant in latitude,
    so barycentric interpolation reproduces the intended profile exactly
    at every sample point (the ``test_object_anchor`` plane-mesh idiom).
    """
    latitudes = [BASE_LATITUDE - 0.002, BASE_LATITUDE + 0.002]
    longitudes = [_longitude_of(east) for east in east_metres_columns]
    vertices = [
        (longitude, latitude, elevation_of_east(east))
        for latitude in latitudes
        for east, longitude in zip(east_metres_columns, longitudes)
    ]
    column_count = len(longitudes)
    triangles = []
    for column in range(column_count - 1):
        south_west = column + 1
        south_east = column + 2
        north_west = column_count + column + 1
        north_east = column_count + column + 2
        triangles.append((south_west, south_east, north_east))
        triangles.append((south_west, north_east, north_west))
    write_mesh_file(path, vertices, triangles)
    return MeshElevationSampler(
        path,
        (
            longitudes[0],
            latitudes[0],
            longitudes[-1],
            latitudes[-1],
        ),
        # A hair of margin: the mesh writer rounds coordinates to nine
        # decimals, so the outermost columns fall a nanodegree outside
        # their own exact bounds and would be filtered out.
        margin_degrees=1.0e-6,
    )


@pytest.fixture()
def step_sampler(tmp_path):
    """Two plateaus 24 m apart, joined by a 0.2 m-wide ramp — the relief
    transition the cut law exists to find."""

    def elevation_of_east(east_metres: float) -> float:
        if east_metres <= STEP_EAST_METRES:
            return LOW_GROUND_METRES
        return HIGH_GROUND_METRES

    return _write_profile_mesh(
        os.path.join(tmp_path, "cluster_step.mesh"),
        [
            -40.0,
            STEP_EAST_METRES,
            STEP_EAST_METRES + STEP_WIDTH_METRES,
            140.0,
        ],
        elevation_of_east,
    )


RAMP_GRADE = 0.08  # metres of rise per metre east


@pytest.fixture()
def ramp_sampler(tmp_path):
    """A uniform 8 % slope: every contact edge stays under T, and the
    span still accumulates past the rigid-seat limit — the ramp case the
    span gate must survive for (spec section 4.3)."""
    return _write_profile_mesh(
        os.path.join(tmp_path, "cluster_ramp.mesh"),
        [-40.0, 140.0],
        lambda east_metres: LOW_GROUND_METRES + RAMP_GRADE * east_metres,
    )


@pytest.fixture()
def gentle_sampler(tmp_path):
    """A 0.2 m rise across the whole model: relief far below T, so
    nothing may be cut and the machinery must reduce to per-structure
    seating (the KCLT/KBNA degeneracy guarantee)."""
    return _write_profile_mesh(
        os.path.join(tmp_path, "cluster_gentle.mesh"),
        [-40.0, 140.0],
        lambda east_metres: LOW_GROUND_METRES + 0.001 * east_metres,
    )


# ── pool construction ─────────────────────────────────────────────────


def _one_box_geometry(minimum_x, maximum_x, minimum_y, maximum_y,
                      minimum_z, maximum_z):
    vertices, triangles = box_vertices_and_triangles(
        minimum_x, maximum_x, minimum_y, maximum_y, minimum_z, maximum_z
    )
    return make_geometry(vertices, triangles)


def _shared_anchor_pool(boxes_by_resource):
    """One object per box, ALL sharing a single anchor — the payware
    topology this spec is about (385 HECA objects on one DSF anchor)."""
    geometry_by_resource = {
        resource: _one_box_geometry(*box)
        for resource, box in boxes_by_resource.items()
    }
    placements = [
        make_placement(
            resource,
            BASE_LATITUDE,
            BASE_LONGITUDE,
            definition_index=index,
        )
        for index, resource in enumerate(boxes_by_resource)
    ]
    resolved_paths = {
        resource: f"/nonexistent/{resource}" for resource in boxes_by_resource
    }
    pools = discover_object_pools(
        placements,
        resolved_paths,
        geometry_by_resource,
        epsilon_metres=CONTACT_EPSILON_METRES,
    )
    assert len(pools) == 1, "the test model must pool as one"
    return pools[0], geometry_by_resource


def _decide(pool, geometry_by_resource, sampler):
    structures = partition_structures(
        pool, geometry_by_resource, epsilon_metres=CONTACT_EPSILON_METRES
    )
    decision = structure_deltas(
        pool, geometry_by_resource, structures, sampler
    )
    return structures, decision


@pytest.fixture()
def cluster_gate_on(monkeypatch):
    """The gate as it ships once the owner's in-sim verdict lands: on,
    T = 0.5 m (spec section 3.3)."""
    monkeypatch.setattr(config, "DSF_OBJECT_CLUSTER_SEATING", True)
    monkeypatch.setattr(config, "DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M", 0.5)


# Two four-box groups, chained across the step: every box is 9.9 m wide
# with a 0.1 m modelling gap to its neighbour (inside the 0.25 m contact
# epsilon, so they CONTACT — but they share no vertex position, so they
# weld into eight separate parts, which is the payware topology: triangle
# soup that abuts without sharing vertices).  The A4/B1 gap is 0.2 m, so
# all eight are one structure whose ground span is 24 m.
_STEPPED_CHAIN = {
    "a1.obj": (0.0, 9.9, 0.0, 5.0, 0.0, 10.0),
    "a2.obj": (10.0, 19.9, 0.0, 5.0, 0.0, 10.0),
    "a3.obj": (20.0, 29.9, 0.0, 5.0, 0.0, 10.0),
    "a4.obj": (30.0, 39.9, 0.0, 5.0, 0.0, 10.0),
    "b1.obj": (40.1, 50.0, 0.0, 5.0, 0.0, 10.0),
    "b2.obj": (50.1, 60.0, 0.0, 5.0, 0.0, 10.0),
    "b3.obj": (60.1, 70.0, 0.0, 5.0, 0.0, 10.0),
    "b4.obj": (70.1, 80.0, 0.0, 5.0, 0.0, 10.0),
}
_LOW_RESOURCES = ("a1.obj", "a2.obj", "a3.obj", "a4.obj")
_HIGH_RESOURCES = ("b1.obj", "b2.obj", "b3.obj", "b4.obj")


class TestSeatDisagreementCut:
    """Spec section 3.2: cut a ground-to-ground contact whose two ends
    want seats more than T apart, and seat each side on its own
    plateau."""

    def test_gate_off_refuses_the_whole_chain(self, step_sampler,
                                              monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_CLUSTER_SEATING", False)
        _structures, decision = _decide(
            *_shared_anchor_pool(_STEPPED_CHAIN), step_sampler
        )
        assert len(decision.structures) == 1
        structure = decision.structures[0]
        assert structure.skip_reason is not None
        assert GROUND_SPAN_SKIP_PHRASE in structure.skip_reason
        assert structure.ground_span_metres == pytest.approx(
            HIGH_GROUND_METRES - LOW_GROUND_METRES, abs=1e-6
        )
        # Nothing baked, nothing clustered: every object stays authored.
        assert decision.delta_by_resource_and_vertex == {}
        assert decision.cluster_counts == {}
        assert decision.cluster_seams == []

    def test_gate_on_cuts_the_step_and_seats_both_plateaus(
        self, step_sampler, cluster_gate_on
    ):
        _structures, decision = _decide(
            *_shared_anchor_pool(_STEPPED_CHAIN), step_sampler
        )
        assert len(decision.structures) == 1
        structure = decision.structures[0]

        # The structure is no longer refused — its two halves are.
        assert structure.skip_reason is None
        assert decision.cluster_counts["clusters"] == 2
        assert decision.cluster_counts["clusters_baked"] == 2
        assert decision.cluster_counts["clusters_refused"] == 0
        assert decision.cluster_counts["cut_edges"] == 1

        # Every object shares one anchor at ground 70, so the low group
        # needs no correction and the high group needs the full 24 m.
        for resource in _LOW_RESOURCES:
            deltas = decision.delta_by_resource_and_vertex[resource]
            assert set(deltas) == set(range(8)), resource
            for delta in deltas.values():
                assert delta == pytest.approx(0.0, abs=1e-6), resource
        for resource in _HIGH_RESOURCES:
            deltas = decision.delta_by_resource_and_vertex[resource]
            assert set(deltas) == set(range(8)), resource
            for delta in deltas.values():
                assert delta == pytest.approx(
                    HIGH_GROUND_METRES - LOW_GROUND_METRES, abs=1e-6
                ), resource

        # Invariant I-21 in its rendered form: after the bake every
        # object's base plane sits on the ground under it.
        for resource in _LOW_RESOURCES + _HIGH_RESOURCES:
            anchor_ground = decision.anchor_ground_by_resource[resource]
            delta = next(
                iter(decision.delta_by_resource_and_vertex[resource].values())
            )
            expected = (
                LOW_GROUND_METRES
                if resource in _LOW_RESOURCES
                else HIGH_GROUND_METRES
            )
            assert anchor_ground + delta == pytest.approx(expected, abs=1e-6)

    def test_the_cut_seam_is_reported_with_its_measured_ground_step(
        self, step_sampler, cluster_gate_on
    ):
        _structures, decision = _decide(
            *_shared_anchor_pool(_STEPPED_CHAIN), step_sampler
        )
        cut_seams = [
            seam for seam in decision.cluster_seams if seam.kind == "cut"
        ]
        assert len(cut_seams) == 1
        seam = cut_seams[0]
        step = HIGH_GROUND_METRES - LOW_GROUND_METRES
        # Tear audit (spec section 4.5): the cut is justified by the
        # measured ground step, and the rendered seam is EXPLAINED by it
        # (u(e) = |seam − g| is zero here, both sides seating exactly).
        assert seam.ground_step_metres == pytest.approx(step, abs=1e-6)
        assert seam.seam_metres == pytest.approx(step, abs=1e-6)
        assert (
            seam.ground_step_metres
            > config.DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M
        )

    def test_no_pad_requests_when_every_cluster_seats_exactly(
        self, step_sampler, cluster_gate_on
    ):
        _structures, decision = _decide(
            *_shared_anchor_pool(_STEPPED_CHAIN), step_sampler
        )
        assert decision.cluster_pad_requests == []
        assert decision.structures[0].needs_pad is False


class TestDegeneracyIsByteForByteLegacy:
    """Spec section 2: on ground that is flat at the T scale, zero edges
    are cut, every structure has exactly one cluster, and the machinery
    reduces to today's behaviour.  This is the KCLT/KBNA regression
    gate in miniature."""

    _COMPACT_CHAIN = {
        "left.obj": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0),
        "right.obj": (1.1, 2.1, 0.0, 1.0, 0.0, 1.0),
    }

    def test_gate_on_and_off_agree_exactly(
        self, gentle_sampler, monkeypatch
    ):
        _structures, gate_off = _decide(
            *_shared_anchor_pool(self._COMPACT_CHAIN), gentle_sampler
        )
        monkeypatch.setattr(config, "DSF_OBJECT_CLUSTER_SEATING", True)
        monkeypatch.setattr(
            config, "DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M", 0.5
        )
        _structures, gate_on = _decide(
            *_shared_anchor_pool(self._COMPACT_CHAIN), gentle_sampler
        )

        assert gate_on.cluster_counts["clusters"] == 1
        assert gate_on.cluster_counts["cut_edges"] == 0
        assert gate_on.cluster_seams == []
        assert gate_on.cluster_pad_requests == []
        assert (
            gate_on.delta_by_resource_and_vertex
            == gate_off.delta_by_resource_and_vertex
        )
        assert gate_on.skipped == gate_off.skipped
        for baked, legacy in zip(gate_on.structures, gate_off.structures):
            assert baked.skip_reason == legacy.skip_reason
            assert baked.needs_pad == legacy.needs_pad
            assert baked.ground_span_metres == pytest.approx(
                legacy.ground_span_metres, abs=1e-12
            )

    def test_tolerance_zero_disables_the_cut(
        self, step_sampler, monkeypatch
    ):
        """``DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M = 0`` is the documented
        disable (spec section 3.3), and must reproduce the refusal even
        with the gate itself on."""
        monkeypatch.setattr(config, "DSF_OBJECT_CLUSTER_SEATING", True)
        monkeypatch.setattr(
            config, "DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M", 0.0
        )
        _structures, decision = _decide(
            *_shared_anchor_pool(_STEPPED_CHAIN), step_sampler
        )
        assert decision.cluster_counts == {}
        assert decision.structures[0].skip_reason is not None
        assert GROUND_SPAN_SKIP_PHRASE in decision.structures[0].skip_reason


# A ten-box building climbing a uniform 8 % slope: consecutive part
# centroids are 5 m apart, so every contact edge sees 0.4 m of ground
# step — under T, nothing cut — while the ends accumulate 3.6 m of span,
# past the 3.0 m rigid-seat limit.  This is the accumulation case the
# span gate must survive for, and the case bake-and-pad exists to serve.
_RAMP_CHAIN = {
    f"ramp{index}.obj": (
        index * 5.0,
        index * 5.0 + 4.9,
        0.0,
        4.0,
        0.0,
        10.0,
    )
    for index in range(10)
}
_RAMP_PART_CENTROID_EAST = [index * 5.0 + 2.45 for index in range(10)]


class TestOverSpanClusterBakesAndPads:
    """Spec section 4.3: where the structure-level gate refuses
    outright, a span-gated CLUSTER is seated at its median AND issued
    pad requests."""

    def test_gate_off_refuses_the_ramp(self, ramp_sampler, monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_CLUSTER_SEATING", False)
        _structures, decision = _decide(
            *_shared_anchor_pool(_RAMP_CHAIN), ramp_sampler
        )
        structure = decision.structures[0]
        assert structure.skip_reason is not None
        assert GROUND_SPAN_SKIP_PHRASE in structure.skip_reason
        assert decision.delta_by_resource_and_vertex == {}

    def test_gate_on_seats_the_ramp_at_its_median_and_pads_the_ends(
        self, ramp_sampler, cluster_gate_on
    ):
        _structures, decision = _decide(
            *_shared_anchor_pool(_RAMP_CHAIN), ramp_sampler
        )
        structure = decision.structures[0]

        # One cluster (no edge exceeds T), seated, flagged for pads.
        assert decision.cluster_counts["clusters"] == 1
        assert decision.cluster_counts["clusters_baked"] == 1
        assert decision.cluster_counts["cut_edges"] == 0
        assert structure.skip_reason is None
        assert structure.needs_pad is True

        # Seated at the MEDIAN of the ten part grounds (amendment A19
        # per cluster): centroids at 2.5, 7.5 … 47.5 m east.
        grounds = [
            LOW_GROUND_METRES + RAMP_GRADE * east
            for east in _RAMP_PART_CENTROID_EAST
        ]
        expected_seat = (sorted(grounds)[4] + sorted(grounds)[5]) / 2.0
        anchor_ground = decision.anchor_ground_by_resource["ramp0.obj"]
        delta = next(
            iter(decision.delta_by_resource_and_vertex["ramp0.obj"].values())
        )
        assert anchor_ground + delta == pytest.approx(
            expected_seat, abs=1e-6
        )

        # Two coherent pads — the low end and the high end — not ten
        # confetti rings (spec section 5.3 grouping).
        requests = decision.cluster_pad_requests
        assert len(requests) == 2
        assert {request.part_count for request in requests} == {3}
        for request in requests:
            assert request.cluster_id == 0
            assert abs(request.residual_metres) > (
                config.DSF_OBJECT_FOOT_PAD_RESIDUAL_M
            )
            assert request.over_relief_cap is False
            # The pad target is the terrain elevation that would meet
            # the seated building base (spec section 5.1 clause 1).
            assert request.target_ground_metres == pytest.approx(
                expected_seat, abs=1e-6
            )
            assert len(request.contact_points_lonlat) == 4 * 3
        # One pad must be raised (building above terrain) and one cut.
        assert {
            request.residual_metres > 0.0 for request in requests
        } == {True, False}

    def test_a_pad_needing_more_relief_than_the_cap_is_flagged(
        self, ramp_sampler, cluster_gate_on, monkeypatch
    ):
        """Spec section 5.1 clause 1: an over-cap pad is still RECORDED,
        carrying its measured numbers — the cluster keeps its seat and
        the residual is a finding, never a silent loss."""
        monkeypatch.setattr(config, "DSF_OBJECT_PAD_MAX_RELIEF_M", 1.0)
        _structures, decision = _decide(
            *_shared_anchor_pool(_RAMP_CHAIN), ramp_sampler
        )
        assert decision.structures[0].skip_reason is None
        requests = decision.cluster_pad_requests
        assert requests
        assert all(request.over_relief_cap for request in requests)


# The bridge specimen: two ground groups on the two plateaus with NO
# ground contact between them, joined only by a two-part ELEVATED
# connector resting on the top of each side — HECA's road_train rail
# link between T23 and the Private Hall, abstracted.
_BRIDGED_GROUPS = {
    "a1.obj": (0.0, 9.9, 0.0, 5.0, 0.0, 10.0),
    "a2.obj": (10.0, 19.9, 0.0, 5.0, 0.0, 10.0),
    "a3.obj": (20.0, 29.9, 0.0, 5.0, 0.0, 10.0),
    "a4.obj": (30.0, 39.9, 0.0, 5.0, 0.0, 10.0),
    "b1.obj": (45.0, 54.9, 0.0, 5.0, 0.0, 10.0),
    "b2.obj": (55.0, 64.9, 0.0, 5.0, 0.0, 10.0),
    "b3.obj": (65.0, 74.9, 0.0, 5.0, 0.0, 10.0),
    "b4.obj": (75.0, 84.9, 0.0, 5.0, 0.0, 10.0),
    "link_west.obj": (38.0, 42.9, 5.0, 6.0, 0.0, 10.0),
    "link_east.obj": (43.0, 47.9, 5.0, 6.0, 0.0, 10.0),
}


class TestBridgeRule:
    """Spec section 4.2a: an elevated component contacting two clusters
    joins its majority-contact cluster; the residual toward the other is
    reported, never averaged across.  No pack modification, no DSF
    write, and the clusters themselves never merge."""

    def test_the_connector_joins_one_cluster_and_the_seam_is_reported(
        self, step_sampler, cluster_gate_on
    ):
        _structures, decision = _decide(
            *_shared_anchor_pool(_BRIDGED_GROUPS), step_sampler
        )
        assert len(decision.structures) == 1, "one contact component"
        assert decision.cluster_counts["clusters"] == 2
        assert decision.cluster_counts["clusters_baked"] == 2

        # Both plateaus seated on their own ground.
        for resource in _LOW_RESOURCES:
            delta = next(
                iter(decision.delta_by_resource_and_vertex[resource].values())
            )
            assert delta == pytest.approx(0.0, abs=1e-6)
        for resource in _HIGH_RESOURCES:
            delta = next(
                iter(decision.delta_by_resource_and_vertex[resource].values())
            )
            assert delta == pytest.approx(
                HIGH_GROUND_METRES - LOW_GROUND_METRES, abs=1e-6
            )

        # The connector is rigid: BOTH its parts carry ONE offset — it
        # followed one cluster, it did not stretch between the two.
        link_deltas = set()
        for resource in ("link_west.obj", "link_east.obj"):
            link_deltas.update(
                decision.delta_by_resource_and_vertex[resource].values()
            )
        assert len(link_deltas) == 1

        # And the residual toward the cluster it left is reported.
        bridge_seams = [
            seam for seam in decision.cluster_seams if seam.kind == "bridge"
        ]
        assert len(bridge_seams) == 1
        seam = bridge_seams[0]
        assert seam.part_count == 2
        assert seam.cluster_id != seam.other_cluster_id
        assert seam.seam_metres == pytest.approx(
            HIGH_GROUND_METRES - LOW_GROUND_METRES, abs=1e-6
        )
        assert decision.cluster_counts["bridge_seams"] == 1

    def test_majority_contact_wins(self):
        """The assignment rule itself, on a hand-built graph: the
        elevated component joins the side it touches most, and never
        merges the two clusters."""
        parts = [
            object_clusters.ClusterPart(
                key=0, is_ground=True, base_y=0.0, ground_metres=70.0
            ),
            object_clusters.ClusterPart(
                key=1, is_ground=True, base_y=0.0, ground_metres=70.0
            ),
            object_clusters.ClusterPart(
                key=2, is_ground=True, base_y=0.0, ground_metres=94.0
            ),
            object_clusters.ClusterPart(key=3, is_ground=False, base_y=6.0),
        ]
        partition = object_clusters.form_clusters(
            parts,
            [(0, 1), (1, 2), (0, 3), (1, 3), (2, 3)],
            0.5,
        )
        assert partition.cluster_count == 2
        low_cluster = partition.cluster_id_by_part_key[0]
        high_cluster = partition.cluster_id_by_part_key[2]
        assert partition.cluster_id_by_part_key[1] == low_cluster
        # Two contacts to the low cluster, one to the high one.
        assert partition.cluster_id_by_part_key[3] == low_cluster
        assert len(partition.bridge_seams) == 1
        assert partition.bridge_seams[0].cluster_id == low_cluster
        assert partition.bridge_seams[0].other_cluster_id == high_cluster
        assert partition.bridge_seams[0].contact_count == 2
        assert partition.bridge_seams[0].other_contact_count == 1

    def test_a_tie_goes_to_the_lower_cluster_id(self):
        parts = [
            object_clusters.ClusterPart(
                key=0, is_ground=True, base_y=0.0, ground_metres=70.0
            ),
            object_clusters.ClusterPart(
                key=1, is_ground=True, base_y=0.0, ground_metres=94.0
            ),
            object_clusters.ClusterPart(key=2, is_ground=False, base_y=6.0),
        ]
        partition = object_clusters.form_clusters(
            parts, [(0, 1), (0, 2), (1, 2)], 0.5
        )
        assert partition.cluster_count == 2
        assert partition.cluster_id_by_part_key[2] == 0


class TestCutLawEdgeCases:
    """Spec section 3.2's "everything else keeps its edge" clauses and
    invariant I-20' (merge on doubt survives for UNMEASURED ground)."""

    def test_an_unmeasured_ground_keeps_its_edge(self):
        parts = [
            object_clusters.ClusterPart(
                key=0, is_ground=True, base_y=0.0, ground_metres=70.0
            ),
            object_clusters.ClusterPart(
                key=1,
                is_ground=True,
                base_y=0.0,
                ground_metres=94.0,
                ground_measured=False,
            ),
        ]
        partition = object_clusters.form_clusters(parts, [(0, 1)], 0.5)
        assert partition.cut_edges == ()
        assert partition.cluster_count == 1

    def test_seat_targets_not_raw_ground_decide_the_cut(self):
        """A step in the BUILDING over a step in the ground wants ONE
        rigid offset — cutting it would tear a correctly assembled
        facade (spec section 3.2, "why seat difference")."""
        parts = [
            object_clusters.ClusterPart(
                key=0, is_ground=True, base_y=0.0, ground_metres=70.0
            ),
            object_clusters.ClusterPart(
                key=1, is_ground=True, base_y=-2.0, ground_metres=68.0
            ),
        ]
        partition = object_clusters.form_clusters(parts, [(0, 1)], 0.5)
        assert partition.cut_edges == ()
        assert partition.cluster_count == 1

    def test_an_elevated_end_never_votes(self):
        parts = [
            object_clusters.ClusterPart(
                key=0, is_ground=True, base_y=0.0, ground_metres=70.0
            ),
            object_clusters.ClusterPart(key=1, is_ground=False, base_y=9.0),
        ]
        partition = object_clusters.form_clusters(parts, [(0, 1)], 0.5)
        assert partition.cut_edges == ()
        assert partition.cluster_id_by_part_key[1] == 0

    def test_a_component_touching_no_cluster_is_reported_unassigned(self):
        parts = [
            object_clusters.ClusterPart(
                key=0, is_ground=True, base_y=0.0, ground_metres=70.0
            ),
            object_clusters.ClusterPart(key=1, is_ground=False, base_y=9.0),
        ]
        partition = object_clusters.form_clusters(parts, [], 0.5)
        assert partition.unassigned_elevated_components == ((1,),)
        assert 1 not in partition.cluster_id_by_part_key

    def test_residual_groups_follow_kept_edges(self):
        groups = object_clusters.residual_part_groups(
            [0, 1, 2, 3, 4],
            [(0, 1), (1, 2), (2, 3), (3, 4)],
            {0, 1, 4},
        )
        assert groups == [(0, 1), (4,)]


class TestContactEdgeThreading:
    """Spec section 3.1: the partition computes the contact graph once
    and must hand it to seating — recomputing the narrow phase there is
    the one way this phase could breach the build-time budget."""

    def test_partition_threads_a_spanning_edge_set(self, step_sampler):
        pool, geometry_by_resource = _shared_anchor_pool(_STEPPED_CHAIN)
        structures = partition_structures(
            pool, geometry_by_resource, epsilon_metres=CONTACT_EPSILON_METRES
        )
        assert len(structures) == 1
        # Eight welded parts chained: the contact graph's spanning subset
        # is exactly seven edges.
        assert len(structures[0].contact_edges) == 7
        keys = {
            key for edge in structures[0].contact_edges for key in edge
        }
        assert len(keys) == 8

    def test_a_structure_without_threaded_edges_keeps_the_rigid_seat(
        self, step_sampler, cluster_gate_on
    ):
        """A hand-built structure, a pre-clustering partition cache or a
        connector-split group carries no verified edges — merge on doubt
        (invariant I-20' keeps its unmeasured half) and the per-STRUCTURE
        seat stands."""
        from dataclasses import replace

        pool, geometry_by_resource = _shared_anchor_pool(_STEPPED_CHAIN)
        structures = partition_structures(
            pool, geometry_by_resource, epsilon_metres=CONTACT_EPSILON_METRES
        )
        stripped = [
            replace(structure, contact_edges=()) for structure in structures
        ]
        decision = structure_deltas(
            pool, geometry_by_resource, stripped, step_sampler
        )
        assert decision.cluster_counts["structures_unthreaded"] == 1
        assert decision.cluster_counts["clusters"] == 0
        assert decision.structures[0].skip_reason is not None
        assert GROUND_SPAN_SKIP_PHRASE in decision.structures[0].skip_reason


class TestPadLawClip:
    """Spec section 5.1 clause 2 / owner ruling R2: pavement wins
    absolutely.  A pad footprint is differenced against the airside
    polygons before it can be emitted; at HECA the Private Hall's north
    face is INSIDE an apron polygon, and a pad that ignored the apron
    would grade the apron."""

    # A 20 m pad ring and an apron covering everything north of its
    # midline, in lon/lat degrees around the test origin.
    _PAD_SIZE_DEGREES = 20.0 / METRES_PER_DEGREE_LATITUDE

    def _pad_ring(self):
        half = self._PAD_SIZE_DEGREES / 2.0
        return [
            (BASE_LONGITUDE - half, BASE_LATITUDE - half),
            (BASE_LONGITUDE + half, BASE_LATITUDE - half),
            (BASE_LONGITUDE + half, BASE_LATITUDE + half),
            (BASE_LONGITUDE - half, BASE_LATITUDE + half),
        ]

    def _apron_ring(self, southern_latitude):
        half = self._PAD_SIZE_DEGREES
        return [
            (BASE_LONGITUDE - half, southern_latitude),
            (BASE_LONGITUDE + half, southern_latitude),
            (BASE_LONGITUDE + half, BASE_LATITUDE + half),
            (BASE_LONGITUDE - half, BASE_LATITUDE + half),
        ]

    def test_the_pad_is_clipped_at_the_apron_edge(self):
        pieces = object_footprints.clip_pad_ring_against_pavement(
            self._pad_ring(), [self._apron_ring(BASE_LATITUDE)]
        )
        assert len(pieces) == 1
        latitudes = [latitude for _longitude, latitude in pieces[0]]
        # Nothing survives north of the apron's southern edge: the pad
        # stops exactly AT the apron, it does not reach under it.
        assert max(latitudes) == pytest.approx(BASE_LATITUDE, abs=1e-12)
        assert min(latitudes) == pytest.approx(
            BASE_LATITUDE - self._PAD_SIZE_DEGREES / 2.0, abs=1e-12
        )

    def test_a_pad_wholly_inside_pavement_is_inadmissible(self):
        pieces = object_footprints.clip_pad_ring_against_pavement(
            self._pad_ring(),
            [self._apron_ring(BASE_LATITUDE - self._PAD_SIZE_DEGREES)],
        )
        assert pieces == []

    def test_no_pavement_leaves_the_ring_alone(self):
        pieces = object_footprints.clip_pad_ring_against_pavement(
            self._pad_ring(), []
        )
        assert len(pieces) == 1
        assert len(pieces[0]) == 4

    def test_clip_slivers_are_dropped(self):
        """A pavement edge grazing the pad leaves a sliver, not a pad."""
        sliver_edge = (
            BASE_LATITUDE - self._PAD_SIZE_DEGREES / 2.0 + 1e-9
        )
        pieces = object_footprints.clip_pad_ring_against_pavement(
            self._pad_ring(), [self._apron_ring(sliver_edge)]
        )
        assert pieces == []


class TestClusterPadRequestProvenance:
    """The run record carries the cluster pad requests so a
    short-circuited run still writes a correct per-tile sidecar (the
    FootPadRequest pattern, spec section 3.5)."""

    def test_requests_round_trip_through_the_run_record(self, tmp_path):
        request = object_anchor.ClusterPadRequest(
            structure_index=3,
            cluster_id=1,
            resource_path="terminal.obj",
            latitude=BASE_LATITUDE,
            longitude=BASE_LONGITUDE,
            base_y=0.25,
            residual_metres=-1.75,
            target_ground_metres=71.5,
            contact_points_lonlat=((10.0, 50.0), (10.001, 50.0)),
            part_count=4,
            over_relief_cap=True,
        )
        record = object_rebake.build_run_record(
            str(tmp_path),
            str(tmp_path / "airport.dsf"),
            str(tmp_path / "Data.mesh"),
            epsilon_metres=0.25,
            excluded_resources=None,
            referenced_resources=[],
            resolve_resource=lambda resource_path: None,
            structures_baked=1,
            structures_needing_pad=1,
            foot_pad_requests=[],
            cluster_pad_requests=[request],
            cluster_seams=[],
            cluster_counts={"clusters": 2},
        )
        assert record["cluster_counts"] == {"clusters": 2}
        restored = object_rebake.run_record_cluster_pad_requests(record)
        assert restored == [request]


def test_the_tolerance_guard_holds():
    """Spec section 3.3: T must exceed the contact epsilon it partitions
    across (config asserts this at import; pin it here so a future edit
    to either number is caught by the suite, not by a build)."""
    assert (
        config.DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M
        > config.DSF_OBJECT_CONTACT_EPSILON_M
    )
    assert math.isfinite(config.DSF_OBJECT_PAD_MAX_RELIEF_M)
