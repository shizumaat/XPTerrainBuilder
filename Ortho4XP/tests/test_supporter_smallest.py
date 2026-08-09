"""Supporter SELECTION: the smallest containing structure wins.

Defect B (HECA, Tai Models pack, 2026-07-26).  Invariant I-8 seats an
elevated structure on a SUPPORTER — a ground-touching structure whose
plan bounding box contains the inheritor's centroid.  The original code
took the FIRST such candidate in structure-index order, which is
arbitrary whenever boxes nest, and systematically wrong for a co-baked
payware pack: the kilometre-scale terminal web is partitioned early, so
at HECA structure 0 (1237 x 2480 m) claimed 8,102 inheritors even though
1,761 of them had a SMALLER containing ground-touching structure — the
building they physically sit on — available.

``DSF_OBJECT_SUPPORTER_SMALLEST`` (default on) picks the smallest
containing plan box instead, ties by lowest structure index.  With
``DSF_OBJECT_SUPPORTER_FATE`` also on, that re-homing changes OUTCOMES:
an inheritor stranded on a span-skipped mega-structure moves onto a
smaller supporter that actually bakes, and bakes with it (measured at
HECA: 1,736 structures flipped from a supporter-fate skip to baked).

Hermetic: synthetic geometry against the hand-written plane mesh from
:mod:`test_object_anchor` — no network, no X-Plane install.
"""

from __future__ import annotations

import pytest

from auto_patch import config, object_anchor, object_rebake
from auto_patch.object_anchor import (
    ObjectPool,
    partition_structures,
    structure_deltas,
)

from test_object_anchor import (  # noqa: F401 (fixtures used by name)
    CONTACT_EPSILON_METRES,
    PLANE_ANCHOR_LATITUDE,
    PLANE_ANCHOR_LONGITUDE,
    compound_geometry,
    make_placement,
    plane_sampler,
    reseat_threshold_off,
)

SUPPORTER_FATE_PHRASE = object_anchor.SUPPORTER_FATE_SKIP_REASON_PHRASE
GROUND_SPAN_SKIP_PHRASE = object_anchor.GROUND_SPAN_SKIP_REASON_PHRASE

# A wide, ground-touching L of three welded bars: plan box x 0..8 by
# z 0..80 (640 m2), all of it within the rigid-seat span limit, so it
# BAKES.  Listed first, so it is structure 0 — the index-order winner the
# pre-fix code would pick.
_WIDE_L = (
    (0.0, 2.0, 0.0, 1.0, 0.0, 80.0),
    (2.0, 3.0, 0.0, 1.0, 0.0, 2.0),
    (3.0, 8.0, 0.0, 1.0, 0.0, 2.0),
)
# A small, separate ground-touching slab well inside the L's plan box
# (4 m2), and an elevated box whose centroid sits over BOTH.
_SMALL_SLAB = (3.0, 5.0, 0.0, 1.0, 40.0, 42.0)
_CLUTTER_OVER_SMALL_SLAB = (3.5, 4.5, 5.0, 6.0, 40.5, 41.5)

# The HECA shape in miniature: a CHAINED mega-structure (three bars
# 0.1 m apart — inside the contact epsilon, so one structure, but three
# welded parts, so a real ground span) covering 50 m of the sloped plane.
# Its span is ~14 m, far past the 3.0 m rigid-seat limit, so it is
# SKIPPED and hands that fate to whatever inherits from it.
_MEGA_CHAIN = (
    (0.0, 10.0, 0.0, 1.0, 0.0, 80.0),
    (10.1, 49.9, 0.6, 1.0, 0.0, 2.0),
    (50.0, 60.0, 0.0, 1.0, 0.0, 2.0),
)
_INNER_SLAB = (20.0, 24.0, 0.0, 1.0, 40.0, 44.0)
_CLUTTER_OVER_INNER_SLAB = (21.0, 23.0, 5.0, 6.0, 41.0, 43.0)

_RESOURCE = "pack.obj"


def _decision(boxes, sampler):
    placement = make_placement(
        _RESOURCE, PLANE_ANCHOR_LATITUDE, PLANE_ANCHOR_LONGITUDE
    )
    geometry_by_resource = {_RESOURCE: compound_geometry(*boxes)}
    pool = ObjectPool(
        placements=[placement],
        resolved_paths={_RESOURCE: f"/nonexistent/{_RESOURCE}"},
    )
    structures = partition_structures(
        pool, geometry_by_resource, epsilon_metres=CONTACT_EPSILON_METRES
    )
    return structure_deltas(
        pool, geometry_by_resource, structures, sampler
    )


def _only_elevated(decision):
    elevated = [
        (index, structure)
        for index, structure in enumerate(decision.structures)
        if not structure.is_ground_touching
    ]
    assert len(elevated) == 1
    return elevated[0]


class TestTheSmallestContainingSupporterIsChosen:
    def test_a_nested_slab_beats_the_wide_structure_that_encloses_it(
        self, plane_sampler
    ):
        decision = _decision(
            _WIDE_L + (_SMALL_SLAB, _CLUTTER_OVER_SMALL_SLAB), plane_sampler
        )
        structures = decision.structures
        # Preconditions: the WIDE structure really is the lower index (so
        # this test is about the size rule and not about ordering luck),
        # and both candidates really do contain the clutter centroid.
        assert structures[0].is_ground_touching
        assert structures[1].is_ground_touching
        assert structures[0].surface_area_square_metres > (
            structures[1].surface_area_square_metres
        )

        _index, inheritor = _only_elevated(decision)
        assert inheritor.inherited_from_structure_index == 1

    def test_the_gate_off_restores_first_containing_in_index_order(
        self, plane_sampler, monkeypatch
    ):
        monkeypatch.setattr(config, "DSF_OBJECT_SUPPORTER_SMALLEST", False)
        decision = _decision(
            _WIDE_L + (_SMALL_SLAB, _CLUTTER_OVER_SMALL_SLAB), plane_sampler
        )
        _index, inheritor = _only_elevated(decision)
        assert inheritor.inherited_from_structure_index == 0

    def test_the_two_choices_really_do_seat_the_inheritor_differently(
        self, plane_sampler, monkeypatch, reseat_threshold_off
    ):
        # Guard against a vacuous test: the supporters' grounds differ,
        # so the re-homing moves the object, it does not merely relabel
        # its parent.
        boxes = _WIDE_L + (_SMALL_SLAB, _CLUTTER_OVER_SMALL_SLAB)
        clutter_vertex = len(compound_geometry(*boxes).vertices) - 1

        decision_on = _decision(boxes, plane_sampler)
        monkeypatch.setattr(config, "DSF_OBJECT_SUPPORTER_SMALLEST", False)
        decision_off = _decision(boxes, plane_sampler)

        delta_on = decision_on.delta_by_resource_and_vertex[_RESOURCE][
            clutter_vertex
        ]
        delta_off = decision_off.delta_by_resource_and_vertex[_RESOURCE][
            clutter_vertex
        ]
        assert abs(delta_on - delta_off) > 0.1


class TestReHomingChangesTheInheritorsFate:
    """The HECA outcome: an inheritor stranded on a span-skipped
    mega-structure moves to the small supporter it actually rests on and
    bakes with it (``DSF_OBJECT_SUPPORTER_FATE`` decides the fate; this
    gate decides WHOSE).

    PRECONDITION RE-PINNED 2026-08-04 (landing commit 66a0a67, "Object
    seating: per-cluster law default ON").  Both tests here need a
    span-SKIPPED mega-structure; 66a0a67 made the rigid-seat span limit
    bake-and-pad per cluster instead of refusing the structure
    (``object_anchor._seat_clustered_structure``, spec section 4.3), so
    ``_MEGA_CHAIN`` no longer skips under the default gate and both died
    on ``skip_reason is None``.  The SELECTION law under test
    (``DSF_OBJECT_SUPPORTER_SMALLEST``) is unchanged — the sibling class
    ``TestTheSmallestContainingSupporterIsChosen`` exercises it on the
    default gate and stayed green throughout.  The fixture below pins the
    OFF arm of a live gate; see the same-dated note in
    ``test_supporter_fate.py`` for the coverage gap this leaves open.
    """

    @pytest.fixture(autouse=True)
    def _pre_cluster_span_skip(self, monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_CLUSTER_SEATING", False)

    def test_the_inheritor_bakes_with_its_new_smaller_supporter(
        self, plane_sampler
    ):
        decision = _decision(
            _MEGA_CHAIN + (_INNER_SLAB, _CLUTTER_OVER_INNER_SLAB),
            plane_sampler,
        )
        mega, inner = decision.structures[0], decision.structures[1]
        assert GROUND_SPAN_SKIP_PHRASE in (mega.skip_reason or "")
        assert inner.skip_reason is None

        _index, inheritor = _only_elevated(decision)
        assert inheritor.inherited_from_structure_index == 1
        assert inheritor.skip_reason is None
        assert _RESOURCE in decision.delta_by_resource_and_vertex

    def test_the_gate_off_leaves_it_stranded_on_the_skipped_mega(
        self, plane_sampler, monkeypatch
    ):
        monkeypatch.setattr(config, "DSF_OBJECT_SUPPORTER_SMALLEST", False)
        decision = _decision(
            _MEGA_CHAIN + (_INNER_SLAB, _CLUTTER_OVER_INNER_SLAB),
            plane_sampler,
        )
        _index, inheritor = _only_elevated(decision)
        assert inheritor.inherited_from_structure_index == 0
        assert (inheritor.skip_reason or "").startswith(
            SUPPORTER_FATE_PHRASE
        )


class TestTheSelectionRuleItself:
    """Direct tests of the grid index, where the tie-break and the
    oversized-box path can be stated exactly."""

    @staticmethod
    def _pick(boxes, point_x, point_z):
        index = object_anchor._build_supporter_index(
            list(range(len(boxes))), boxes
        )
        return object_anchor._smallest_containing_supporter_index(
            index, boxes, point_x, point_z
        )

    def test_the_smallest_containing_box_wins_whatever_its_index(self):
        boxes = [
            (0.0, 100.0, 0.0, 100.0),  # 10,000 m2, index 0
            (10.0, 30.0, 10.0, 30.0),  # 400 m2
            (18.0, 22.0, 18.0, 22.0),  # 16 m2 — the winner
        ]
        assert self._pick(boxes, 20.0, 20.0) == 2

    def test_equal_areas_tie_break_on_the_lowest_index(self):
        # Two boxes of exactly 400 m2 both contain the point; the rule is
        # lowest structure index, so the answer must not depend on the
        # order the grid happened to bucket them in.
        boxes = [
            (0.0, 100.0, 0.0, 100.0),
            (10.0, 30.0, 10.0, 30.0),
            (11.0, 31.0, 9.0, 29.0),
        ]
        assert self._pick(boxes, 20.0, 20.0) == 1
        reversed_boxes = [boxes[0], boxes[2], boxes[1]]
        assert self._pick(reversed_boxes, 20.0, 20.0) == 1

    def test_a_point_no_box_contains_has_no_supporter(self):
        boxes = [(0.0, 10.0, 0.0, 10.0), (20.0, 30.0, 20.0, 30.0)]
        assert self._pick(boxes, 15.0, 15.0) is None

    def test_an_oversized_box_still_wins_when_it_is_the_only_container(
        self,
    ):
        # A kilometre-scale box covers far more grid cells than
        # ``_SUPPORTER_GRID_OVERSIZED_CELLS`` and is held aside rather
        # than written into every cell; it must still be found.
        boxes = [
            (0.0, 2000.0, 0.0, 2000.0),
            (1900.0, 1910.0, 10.0, 20.0),
        ]
        assert self._pick(boxes, 500.0, 500.0) == 0
        assert self._pick(boxes, 1905.0, 15.0) == 1

    def test_a_structure_with_no_box_is_never_a_supporter(self):
        boxes = [None, (0.0, 10.0, 0.0, 10.0)]
        assert self._pick(boxes, 5.0, 5.0) == 1


class TestTheGateIsInTheShortCircuitFingerprint:
    def test_flipping_the_gate_changes_the_run_fingerprint(
        self, monkeypatch
    ):
        monkeypatch.setattr(config, "DSF_OBJECT_SUPPORTER_SMALLEST", True)
        digest_on = object_rebake._gate_digest(0.25)
        monkeypatch.setattr(config, "DSF_OBJECT_SUPPORTER_SMALLEST", False)
        digest_off = object_rebake._gate_digest(0.25)
        assert digest_on != digest_off
        assert (
            "DSF_OBJECT_SUPPORTER_SMALLEST" in object_rebake._GATE_NAMES
        )

    def test_the_record_version_was_bumped(self):
        # A pack baked by the pre-defect-B code must never short-circuit
        # past the new seating.
        assert object_rebake.RUN_RECORD_VERSION >= 3
