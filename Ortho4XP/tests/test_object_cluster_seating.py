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

from test_object_anchor import (  # noqa: F401 (fixtures used by name)
    CONTACT_EPSILON_METRES,
    box_vertices_and_triangles,
    make_geometry,
    make_placement,
    metres_per_degree_longitude_at,
    reseat_threshold_off,
    write_mesh_file,
)

GROUND_SPAN_SKIP_PHRASE = object_anchor.GROUND_SPAN_SKIP_REASON_PHRASE
BELOW_THRESHOLD_PHRASE = (
    object_anchor.BELOW_BAKE_THRESHOLD_SKIP_REASON_PHRASE
)

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
        self, step_sampler, cluster_gate_on, reseat_threshold_off
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
        self, gentle_sampler, monkeypatch, reseat_threshold_off
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
        self, step_sampler, cluster_gate_on, reseat_threshold_off
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


# A residual group shaped like a C: a five-metre-wide arm climbing the
# ramp from the west, then a courtyard wall — bottom leg, right column,
# top leg — around 4.9 x 4.9 m of OPEN GROUND.  This is the OTHH
# topology, abstracted: the parts are contact-connected all the way
# round, so the retired law hulled them into one rectangle and the pad
# flattened the courtyard with them (owner in-sim, build 1.0.226:
# "large rectangles ... spanning water and parking lots").
_COURTYARD_CHAIN = {
    **{
        f"w{index + 1}.obj": (
            5.0 * index, 5.0 * index + 4.9, 0.0, 5.0, 0.0, 4.9
        )
        for index in range(8)
    },
    "link.obj": (40.0, 44.9, 0.0, 5.0, 0.0, 4.9),
    "bottom.obj": (45.0, 49.9, 0.0, 5.0, 0.0, 4.9),
    "right_s.obj": (50.0, 54.9, 0.0, 5.0, 0.0, 4.9),
    "right_m.obj": (50.0, 54.9, 0.0, 5.0, 5.0, 9.9),
    "right_n.obj": (50.0, 54.9, 0.0, 5.0, 10.0, 14.9),
    "top.obj": (45.0, 49.9, 0.0, 5.0, 10.0, 14.9),
}
_COURTYARD_RESOURCES = (
    "bottom.obj", "right_s.obj", "right_m.obj", "right_n.obj", "top.obj",
)


class TestFootprintHuggingRequestRings:
    """object-reseat-threshold-spec §2.5, on the PRODUCER: a request's
    rings are the union of its parts' dilated contact hulls, so the ring
    hugs the objects instead of hulling the ground between them.
    Residual accounting is unchanged — the group is still one request."""

    def _courtyard_request(self, decision):
        # The courtyard sits EAST of the cluster's median seat, so its
        # residual is the negative one; the west arm's is positive.
        requests = [
            request for request in decision.cluster_pad_requests
            if request.residual_metres < 0.0
        ]
        assert len(requests) == 1, [
            (request.part_count, request.residual_metres)
            for request in decision.cluster_pad_requests
        ]
        return requests[0]

    def _local(self, longitude, latitude):
        return (
            (longitude - BASE_LONGITUDE) * METRES_PER_DEGREE_LONGITUDE,
            (latitude - BASE_LATITUDE) * METRES_PER_DEGREE_LATITUDE,
        )

    def test_the_group_records_its_contact_band_triangles(
        self, ramp_sampler, cluster_gate_on
    ):
        """§2.5 v2b: one request per residual group (accounting
        unchanged) whose ring input is the group's GROUND-CONTACT
        GEOMETRY — one group per contact-band triangle.  The five boxes
        contribute their bottom faces (two triangles each) and nothing
        above the band; the flat point list still carries the plan-box
        corners as the audit trail."""
        _structures, decision = _decide(
            *_shared_anchor_pool(_COURTYARD_CHAIN), ramp_sampler
        )
        request = self._courtyard_request(decision)
        assert request.part_count == 5
        assert all(len(part) == 3 for part in request.contact_parts_lonlat)
        assert len(request.contact_parts_lonlat) == 10
        # The plan-box audit trail is untouched: four corners per part.
        assert len(request.contact_points_lonlat) == 4 * 5

    def test_the_ring_hugs_the_courtyard_instead_of_filling_it(
        self, ramp_sampler, cluster_gate_on
    ):
        """THE DEFECT, measured: the retired hull covers the courtyard,
        the hugging ring does not — and the ring is a third of its
        area."""
        from shapely.geometry import Point, Polygon

        _structures, decision = _decide(
            *_shared_anchor_pool(_COURTYARD_CHAIN), ramp_sampler
        )
        request = self._courtyard_request(decision)
        margin = config.DSF_OBJECT_FOOT_PAD_MARGIN_M

        rings = object_footprints.foot_pad_rings(
            [list(part) for part in request.contact_parts_lonlat], margin
        )
        assert len(rings) == 1, "the C is contact-connected: one component"
        hugging = Polygon([self._local(*point) for point in rings[0]])
        hull = Polygon([
            self._local(*point) for point in object_footprints.foot_pad_ring(
                list(request.contact_points_lonlat), margin)
        ])

        # The courtyard centre is 2.55 m from every part — outside the
        # margin, inside the hull.  (The pool frame's z runs SOUTH, so a
        # part at z = +7.45 lands at −7.45 m north of the anchor.)
        courtyard = Point(47.45, -7.45)
        assert hull.contains(courtyard)
        assert not hugging.intersects(courtyard)
        # Every square metre the hugging ring drops is open ground the
        # retired law graded; the courtyard is inside that difference.
        # (Its scale here is the specimen's — one 4.9 m courtyard — not
        # the field's: at OTHH the same mechanism bridged water and
        # parking lots.)
        assert hugging.within(hull.buffer(1e-6))
        assert hull.area - hugging.area > 5.0
        assert hull.difference(hugging).contains(courtyard)

    def test_every_ring_vertex_stays_within_the_margin_of_a_hull(
        self, ramp_sampler, cluster_gate_on
    ):
        """§2.5's structural assertion on the producer's own output."""
        from shapely.geometry import MultiPoint, Point
        from shapely.ops import unary_union

        _structures, decision = _decide(
            *_shared_anchor_pool(_COURTYARD_CHAIN), ramp_sampler
        )
        margin = config.DSF_OBJECT_FOOT_PAD_MARGIN_M
        for request in decision.cluster_pad_requests:
            hulls = unary_union([
                MultiPoint([self._local(*point) for point in part]).convex_hull
                for part in request.contact_parts_lonlat
            ])
            rings = object_footprints.foot_pad_rings(
                [list(part) for part in request.contact_parts_lonlat], margin
            )
            assert rings
            for ring in rings:
                for point in ring:
                    assert hulls.distance(
                        Point(*self._local(*point))) <= margin + 0.01


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


# ── the reseat threshold, per CLUSTER ─────────────────────────────────


SHELF_RAMP_GRADE = 0.1  # metres of rise per metre east, west of the shelf


@pytest.fixture()
def shelf_sampler(tmp_path):
    """A flat shelf east of the origin, approached by a gentle ramp to
    its west.

    The cluster's parts stand on the shelf, so they share one ground and
    the cut law leaves them one rigid body; an object's ANCHOR is placed
    on the ramp, which is what sets that member's correction (invariant
    I-3: ``delta(C, O) = cluster_ground − ground(anchor(O))``).  That is
    the only way a cluster gets members with DIFFERENT corrections, and
    the mixed-rigidity witness below needs exactly that.
    """
    return _write_profile_mesh(
        os.path.join(tmp_path, "cluster_shelf.mesh"),
        [-60.0, 0.0, 140.0],
        lambda east_metres: LOW_GROUND_METRES + (
            SHELF_RAMP_GRADE * east_metres if east_metres < 0.0 else 0.0
        ),
    )


# Four boxes standing on the shelf in WORLD space, 0.1 m apart — inside
# the contact epsilon, welded into no shared vertex, so they are four
# parts of one structure exactly like the stepped chain above.
_SHELF_CHAIN = {
    f"shelf{index}.obj": (
        index * 10.0,
        index * 10.0 + 9.9,
        0.0,
        5.0,
        0.0,
        10.0,
    )
    for index in range(4)
}


def _anchor_east_for_correction(correction_metres: float) -> float:
    """Where an object's anchor must stand for its member correction to
    be ``correction_metres`` (the shelf is at ``LOW_GROUND_METRES``)."""
    return -correction_metres / SHELF_RAMP_GRADE


def _pool_with_own_anchors(world_boxes_by_resource, anchor_east_by_resource):
    """One object per WORLD-space box, each carrying its own anchor.

    Geometry is authored relative to its own anchor, so the local box is
    the world box shifted back by that anchor's east offset — the two
    descriptions place the same object.
    """
    geometry_by_resource = {}
    placements = []
    for index, (resource, box) in enumerate(world_boxes_by_resource.items()):
        anchor_east = anchor_east_by_resource[resource]
        minimum_x, maximum_x, minimum_y, maximum_y, minimum_z, maximum_z = (
            box
        )
        geometry_by_resource[resource] = _one_box_geometry(
            minimum_x - anchor_east,
            maximum_x - anchor_east,
            minimum_y,
            maximum_y,
            minimum_z,
            maximum_z,
        )
        placements.append(
            make_placement(
                resource,
                BASE_LATITUDE,
                _longitude_of(anchor_east),
                definition_index=index,
            )
        )
    pools = discover_object_pools(
        placements,
        {
            resource: f"/nonexistent/{resource}"
            for resource in world_boxes_by_resource
        },
        geometry_by_resource,
        epsilon_metres=CONTACT_EPSILON_METRES,
    )
    assert len(pools) == 1, "the test model must pool as one"
    return pools[0], geometry_by_resource


def _shelf_decision(correction_by_resource, sampler):
    return _decide(
        *_pool_with_own_anchors(
            _SHELF_CHAIN,
            {
                resource: _anchor_east_for_correction(correction)
                for resource, correction in correction_by_resource.items()
            },
        ),
        sampler,
    )


class TestReseatThreshold:
    """docs/specs/object-reseat-threshold-spec.md sections 2.1 and 2.2,
    on the default (clustered) path.

    A cluster is ONE RIGID BODY, so the MAX correction over its members
    decides for all of them: baking some members and not others would
    tear it.  Under the threshold the pack is untouched and the cluster's
    ground contacts are routed to the pad system instead."""

    def test_a_below_threshold_cluster_pads_instead_of_reseating(
        self, shelf_sampler, cluster_gate_on
    ):
        # Every member 0.30 m out: nothing is written to the pack, and
        # the 0.30 m the objects keep is asked of the terrain instead
        # (0.30 > the 0.15 m no-bake floor).
        _structures, decision = _shelf_decision(
            {resource: 0.30 for resource in _SHELF_CHAIN}, shelf_sampler
        )
        assert decision.delta_by_resource_and_vertex == {}
        assert decision.cluster_counts["clusters"] == 1
        assert decision.cluster_counts["clusters_baked"] == 0
        assert decision.cluster_counts["clusters_refused"] == 0
        assert decision.cluster_counts["clusters_below_threshold"] == 1

        structure = decision.structures[0]
        assert BELOW_THRESHOLD_PHRASE in structure.skip_reason
        assert "0.300" in structure.skip_reason

        # One request for the whole connected group, never four
        # confetti rings; the target is the ground that meets the
        # UNBAKED, as-draped base.
        assert len(decision.cluster_pad_requests) == 1
        request = decision.cluster_pad_requests[0]
        assert request.part_count == 4
        assert request.residual_metres == pytest.approx(-0.30, abs=1e-2)
        assert request.target_ground_metres == pytest.approx(
            LOW_GROUND_METRES - 0.30, abs=1e-2
        )
        assert request.over_relief_cap is False
        assert request.contact_points_lonlat

    def test_a_sub_floor_residual_asks_terrain_for_nothing(
        self, shelf_sampler, cluster_gate_on
    ):
        """Spec section 2.2's materiality floor: a 0.1 m float is under
        the visible-seam scale and the mesh quantum, so adapting terrain
        to it would be churn."""
        _structures, decision = _shelf_decision(
            {resource: 0.10 for resource in _SHELF_CHAIN}, shelf_sampler
        )
        assert decision.delta_by_resource_and_vertex == {}
        assert decision.cluster_counts["clusters_below_threshold"] == 1
        assert decision.cluster_pad_requests == []

    def test_one_member_over_the_threshold_reseats_the_whole_cluster(
        self, shelf_sampler, cluster_gate_on
    ):
        """Spec section 2.1, the MAX not the mean: one member needing
        1.2 m reseats every member, including the three that only needed
        0.1 m — a cluster is one rigid body and baking part of it would
        tear it."""
        corrections = {resource: 0.10 for resource in _SHELF_CHAIN}
        corrections["shelf2.obj"] = 1.20
        _structures, decision = _shelf_decision(corrections, shelf_sampler)

        assert decision.cluster_counts["clusters_baked"] == 1
        assert decision.cluster_counts["clusters_below_threshold"] == 0
        assert decision.structures[0].skip_reason is None
        assert set(decision.delta_by_resource_and_vertex) == set(_SHELF_CHAIN)
        for resource, correction in corrections.items():
            deltas = set(
                decision.delta_by_resource_and_vertex[resource].values()
            )
            assert len(deltas) == 1, resource
            assert next(iter(deltas)) == pytest.approx(
                correction, abs=1e-2
            ), resource
        # Every part is seated exactly on the shelf: the rigid body is
        # whole, which is what "the max decides" buys.
        for resource in _SHELF_CHAIN:
            anchor_ground = decision.anchor_ground_by_resource[resource]
            delta = next(
                iter(decision.delta_by_resource_and_vertex[resource].values())
            )
            assert anchor_ground + delta == pytest.approx(
                LOW_GROUND_METRES, abs=1e-2
            )
        # A baked cluster keeps the 0.75 m residual floor: its parts sit
        # exactly on the shelf, so it asks terrain for nothing.
        assert decision.cluster_pad_requests == []

    def test_measure_only_routes_every_cluster_below_the_threshold(
        self, shelf_sampler, cluster_gate_on
    ):
        """Spec section 2.3: the pass runs, the pack is not modified, and
        the requests are still raised — even for a correction the default
        law would happily bake."""
        pool, geometry_by_resource = _pool_with_own_anchors(
            _SHELF_CHAIN,
            {
                resource: _anchor_east_for_correction(2.0)
                for resource in _SHELF_CHAIN
            },
        )
        structures = partition_structures(
            pool, geometry_by_resource, epsilon_metres=CONTACT_EPSILON_METRES
        )
        decision = structure_deltas(
            pool,
            geometry_by_resource,
            structures,
            shelf_sampler,
            measure_only=True,
        )
        assert decision.delta_by_resource_and_vertex == {}
        assert decision.cluster_counts["clusters_below_threshold"] == 1
        assert "measure-only" in decision.structures[0].skip_reason
        assert len(decision.cluster_pad_requests) == 1
        assert decision.cluster_pad_requests[0].target_ground_metres == (
            pytest.approx(LOW_GROUND_METRES - 2.0, abs=1e-2)
        )


class TestThresholdZeroIsHead:
    """Spec section 5 acceptance 2, the DEGENERACY GATE:
    ``O4_DSF_OBJECT_BAKE_MIN_DELTA_M=0`` must reproduce the
    pre-2026-08-09 behaviour exactly — every non-zero delta bakes, no
    unit is routed to the terrain side, and nothing new appears in the
    decision.  Any diff is a bug in the threshold, not a policy choice.

    The fixture is deliberately the population the default threshold
    CHANGES (four sub-metre members): if the disabled threshold leaked
    anywhere, this is where it would show.
    """

    def _legacy_decision_shape(self, decision, corrections):
        # The pre-change law, restated from first principles: each
        # member's delta is its own anchor-to-cluster-ground offset
        # (invariant I-3), every member bakes, and the only pad requests
        # are the baked path's (> DSF_OBJECT_FOOT_PAD_RESIDUAL_M).
        assert set(decision.delta_by_resource_and_vertex) == set(
            _SHELF_CHAIN
        )
        for resource, correction in corrections.items():
            deltas = set(
                decision.delta_by_resource_and_vertex[resource].values()
            )
            assert len(deltas) == 1, resource
            assert next(iter(deltas)) == pytest.approx(
                correction, abs=1e-2
            ), resource
            assert set(
                decision.delta_by_resource_and_vertex[resource]
            ) == set(range(8)), resource
        assert decision.structures[0].skip_reason is None
        assert decision.skipped == []
        assert decision.cluster_pad_requests == []
        assert decision.foot_pad_requests == []

    def test_disabled_threshold_bakes_every_sub_metre_member(
        self, shelf_sampler, cluster_gate_on, reseat_threshold_off
    ):
        corrections = {
            resource: 0.10 + 0.05 * index
            for index, resource in enumerate(_SHELF_CHAIN)
        }
        _structures, decision = _shelf_decision(corrections, shelf_sampler)
        self._legacy_decision_shape(decision, corrections)
        # And none of the new machinery fired: no below-threshold count,
        # no below-threshold reason anywhere in the decision.
        assert decision.cluster_counts["clusters_below_threshold"] == 0
        assert decision.cluster_counts["clusters_baked"] == 1
        assert not any(
            structure.skip_reason
            and BELOW_THRESHOLD_PHRASE in structure.skip_reason
            for structure in decision.structures
        )

    def test_the_disabled_threshold_changes_nothing_else(
        self, shelf_sampler, cluster_gate_on, monkeypatch
    ):
        """The same pool decided twice — threshold disabled versus a
        threshold no member can reach — differs ONLY in the threshold's
        own outputs: same clusters, same cut edges, same seams, same
        grounds.  (This is the in-suite form of "byte-identical to
        HEAD": the arithmetic that produces bytes is untouched.)"""
        corrections = {resource: 0.30 for resource in _SHELF_CHAIN}
        monkeypatch.setattr(config, "DSF_OBJECT_BAKE_MIN_DELTA_M", 0.0)
        _structures, baked = _shelf_decision(corrections, shelf_sampler)
        monkeypatch.setattr(config, "DSF_OBJECT_BAKE_MIN_DELTA_M", 1.0)
        _structures, held = _shelf_decision(corrections, shelf_sampler)

        assert held.anchor_ground_by_resource == (
            baked.anchor_ground_by_resource
        )
        assert held.cluster_seams == baked.cluster_seams
        for name in ("clusters", "cut_edges", "structures_clustered"):
            assert held.cluster_counts[name] == baked.cluster_counts[name]
        assert (
            held.structures[0].ground_span_metres
            == baked.structures[0].ground_span_metres
        )
        assert held.structures[0].needs_pad == baked.structures[0].needs_pad
        # The difference is exactly the threshold's own doing.
        assert baked.delta_by_resource_and_vertex
        assert held.delta_by_resource_and_vertex == {}
        assert baked.cluster_counts["clusters_baked"] == 1
        assert held.cluster_counts["clusters_below_threshold"] == 1


def test_the_tolerance_guard_holds():
    """Spec section 3.3: T must exceed the contact epsilon it partitions
    across (config asserts this at import; pin it here so a future edit
    to either number is caught by the suite, not by a build)."""
    assert (
        config.DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M
        > config.DSF_OBJECT_CONTACT_EPSILON_M
    )
    assert math.isfinite(config.DSF_OBJECT_PAD_MAX_RELIEF_M)
