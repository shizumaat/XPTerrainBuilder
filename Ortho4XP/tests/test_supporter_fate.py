"""Supporter FATE: an inheritor shares its supporter's outcome.

Defect (HECA, Tai Models pack, 2026-07-26 — the owner's "a ton of
floating objects").  Structure 0 of that pack is a 1237 x 2480 m,
16,868-part mega-structure whose ground-contact terrain spans 25.79 m,
so the rigid-seat span limit SKIPS it and it stays at its authored
elevations.  It nevertheless kept acting as an elevation SUPPORTER:
every elevated structure whose centroid landed in its bounding box
inherited its ground (invariant I-8) and then baked, because an
inheritor has no ground-touching part and therefore a ground span of 0
that no skip can catch.  8,102 structures — 554 k triangles of signage,
roof clutter and fittings — were baked -2.00 .. -2.45 m relative to a
parent that had not moved.

The rule these tests pin (``DSF_OBJECT_SUPPORTER_FATE``, default on):
a structure that inherits a SKIPPED supporter's ground is skipped too,
with a counted reason quoting the parent's; a structure that inherits a
BAKED supporter's ground bakes exactly as before; and with the gate off
the whole thing is the pre-fix behaviour.

Hermetic: synthetic geometry against the hand-written plane mesh from
:mod:`test_object_anchor`, plus a fake pack directory for the
stale-bake reversion — no network, no X-Plane install.
"""

from __future__ import annotations

import pytest

from auto_patch import config, object_anchor, object_rebake
from auto_patch.object_anchor import (
    ObjectPool,
    RebakeDecision,
    Structure,
    partition_structures,
    structure_deltas,
)

from test_object_anchor import (  # noqa: F401 (plane_sampler is a fixture)
    CONTACT_EPSILON_METRES,
    PLANE_ANCHOR_LATITUDE,
    PLANE_ANCHOR_LONGITUDE,
    compound_geometry,
    make_placement,
    plane_sampler,
)

SUPPORTER_FATE_PHRASE = object_anchor.SUPPORTER_FATE_SKIP_REASON_PHRASE
GROUND_SPAN_SKIP_PHRASE = object_anchor.GROUND_SPAN_SKIP_REASON_PHRASE

# A ground-touching CHAIN of two slabs bridged by an elevated beam, plus
# a detached box floating well above it.  The box touches nothing (4 m of
# clear air to the beam, far past the 0.25 m contact epsilon), so it is
# its own structure; its centroid lies inside the chain's horizontal
# bounding box, so pass 2 makes the chain its supporter.
_CLUTTER_BOX = (20.0, 22.0, 5.0, 6.0, 3.0, 5.0)
# Slabs 50 m apart across the plane's slope: ~14 m of ground span, far
# past the 3.0 m rigid-seat limit, so the chain is SKIPPED.
_WIDE_CHAIN = (
    (0.0, 10.0, 0.0, 1.0, 0.0, 10.0),
    (10.1, 49.9, 0.6, 1.0, 0.0, 10.0),
    (50.0, 60.0, 0.0, 1.0, 0.0, 10.0),
)
# The same shape 6 m across: ~1.7 m of span, comfortably under the
# limit, so the chain BAKES.
_NARROW_CHAIN = (
    (0.0, 2.0, 0.0, 1.0, 0.0, 4.0),
    (2.05, 5.95, 0.6, 1.0, 0.0, 4.0),
    (6.0, 8.0, 0.0, 1.0, 0.0, 4.0),
)
_NARROW_CLUTTER_BOX = (3.0, 4.0, 5.0, 6.0, 1.0, 3.0)


def _decision(boxes, sampler, resource="chain.obj"):
    """Partition one resource's boxes and solve the seating decision."""
    placement = make_placement(
        resource, PLANE_ANCHOR_LATITUDE, PLANE_ANCHOR_LONGITUDE
    )
    geometry_by_resource = {resource: compound_geometry(*boxes)}
    pool = ObjectPool(
        placements=[placement],
        resolved_paths={resource: f"/nonexistent/{resource}"},
    )
    structures = partition_structures(
        pool, geometry_by_resource, epsilon_metres=CONTACT_EPSILON_METRES
    )
    decision = structure_deltas(
        pool, geometry_by_resource, structures, sampler
    )
    return decision


def _split(decision):
    """``(supporter, inheritor)`` — the ground-touching chain and the
    elevated box, whichever order the partition produced them in."""
    ground = [
        (index, structure)
        for index, structure in enumerate(decision.structures)
        if structure.is_ground_touching
    ]
    elevated = [
        (index, structure)
        for index, structure in enumerate(decision.structures)
        if not structure.is_ground_touching
    ]
    assert len(ground) == 1 and len(elevated) == 1
    return ground[0], elevated[0]


class TestSkippedSupporterTakesItsInheritorsWithIt:
    def test_inheritor_of_a_skipped_supporter_is_skipped_and_counted(
        self, plane_sampler
    ):
        decision = _decision(
            _WIDE_CHAIN + (_CLUTTER_BOX,), plane_sampler
        )
        (supporter_index, supporter), (_index, inheritor) = _split(decision)

        # The supporter is the span-limit skip this fix is about.
        assert supporter.skip_reason is not None
        assert GROUND_SPAN_SKIP_PHRASE in supporter.skip_reason

        # The inheritor shares its fate: skipped, with a reason that
        # opens with the stable phrase post_mesh counts on and quotes
        # the parent's own reason.
        assert inheritor.skip_reason is not None
        assert inheritor.skip_reason.startswith(SUPPORTER_FATE_PHRASE)
        assert supporter.skip_reason in inheritor.skip_reason
        # The audit trail still names the supporter it inherited from.
        assert (
            inheritor.inherited_from_structure_index == supporter_index
        )

        # Nothing baked: no structure carried a delta, so the whole
        # resource is reported unbaked and the byte-idempotent rewrite
        # (and the reversion pass) leave every vertex authored.
        assert decision.delta_by_resource_and_vertex == {}
        assert [resource for resource, _reason in decision.skipped] == [
            "chain.obj"
        ]

    def test_the_gate_off_restores_the_pre_fix_split(
        self, plane_sampler, monkeypatch
    ):
        # O4_SUPPORTER_FATE=0: the inheritor bakes while its supporter
        # stays put — exactly the HECA tear, kept available as an escape
        # hatch and proving the gate, not some incidental property, is
        # what changed.
        monkeypatch.setattr(config, "DSF_OBJECT_SUPPORTER_FATE", False)
        decision = _decision(
            _WIDE_CHAIN + (_CLUTTER_BOX,), plane_sampler
        )
        (_supporter_index, supporter), (_index, inheritor) = _split(decision)

        assert GROUND_SPAN_SKIP_PHRASE in supporter.skip_reason
        assert inheritor.skip_reason is None
        assert "chain.obj" in decision.delta_by_resource_and_vertex

    def test_a_foot_candidate_over_a_skipped_supporter_still_skips(
        self, plane_sampler
    ):
        # The clutter box in its OWN resource is a foot candidate: its
        # lowest vertex IS that resource's lowest vertex, the
        # author-baked-offset signature.  Pass 2 nonetheless routes it
        # into inheritance because a supporter's box covers its feet —
        # and it must keep doing so even though that supporter is
        # skipped.  Measured 2026-07-26: re-routing such candidates to
        # the per-foot path seats them on TERRAIN, which at HECA drops
        # 80 structures by 4.3 m to 25.7 m (roof clutter falling to the
        # apron).  A skipped supporter is still physically there.
        chain_resource, clutter_resource = "chain.obj", "clutter.obj"

        # Precondition: on its own the box IS foot-anchored, so the
        # assertion below really is about the supporter and not about a
        # box the foot detector never looked at.
        alone = _decision(
            (_CLUTTER_BOX,), plane_sampler, resource=clutter_resource
        )
        assert alone.foot_clusters_by_structure_index

        placements = [
            make_placement(
                chain_resource, PLANE_ANCHOR_LATITUDE, PLANE_ANCHOR_LONGITUDE
            ),
            make_placement(
                clutter_resource,
                PLANE_ANCHOR_LATITUDE,
                PLANE_ANCHOR_LONGITUDE,
            ),
        ]
        geometry_by_resource = {
            chain_resource: compound_geometry(*_WIDE_CHAIN),
            clutter_resource: compound_geometry(_CLUTTER_BOX),
        }
        pool = ObjectPool(
            placements=placements,
            resolved_paths={
                resource: f"/nonexistent/{resource}"
                for resource in geometry_by_resource
            },
        )
        structures = partition_structures(
            pool, geometry_by_resource, epsilon_metres=CONTACT_EPSILON_METRES
        )
        decision = structure_deltas(
            pool, geometry_by_resource, structures, plane_sampler
        )
        (_supporter_index, supporter), (index, inheritor) = _split(decision)

        assert GROUND_SPAN_SKIP_PHRASE in supporter.skip_reason
        assert inheritor.skip_reason.startswith(SUPPORTER_FATE_PHRASE)
        # NOT re-routed to the per-foot path.
        assert index not in decision.foot_clusters_by_structure_index
        assert decision.delta_by_resource_and_vertex == {}


class TestBakedSupporterStillCarriesItsInheritors:
    @pytest.mark.parametrize("supporter_fate", [True, False])
    def test_inheritor_of_a_baked_supporter_bakes_unchanged(
        self, plane_sampler, monkeypatch, supporter_fate
    ):
        # The only structures the fix may touch are those whose supporter
        # was skipped: with a baked supporter the decision is identical
        # with the gate on and off, down to the offset.
        monkeypatch.setattr(
            config, "DSF_OBJECT_SUPPORTER_FATE", supporter_fate
        )
        decision = _decision(
            _NARROW_CHAIN + (_NARROW_CLUTTER_BOX,), plane_sampler
        )
        (supporter_index, supporter), (_index, inheritor) = _split(decision)

        assert supporter.skip_reason is None
        assert inheritor.skip_reason is None
        assert inheritor.inherited_from_structure_index == supporter_index
        # Every vertex of all four boxes carries an offset.
        assert set(decision.delta_by_resource_and_vertex["chain.obj"]) == set(
            range(32)
        )
        assert decision.skipped == []

    def test_structures_are_returned_in_the_callers_order(
        self, plane_sampler
    ):
        # Pass 3 evaluates supporters before inheritors; the returned
        # list must still line up positionally with the input.
        boxes = _WIDE_CHAIN + (_CLUTTER_BOX,)
        placement = make_placement(
            "chain.obj", PLANE_ANCHOR_LATITUDE, PLANE_ANCHOR_LONGITUDE
        )
        geometry_by_resource = {"chain.obj": compound_geometry(*boxes)}
        pool = ObjectPool(
            placements=[placement],
            resolved_paths={"chain.obj": "/nonexistent/chain.obj"},
        )
        structures = partition_structures(
            pool, geometry_by_resource, epsilon_metres=CONTACT_EPSILON_METRES
        )
        decision = structure_deltas(
            pool, geometry_by_resource, structures, plane_sampler
        )

        assert len(decision.structures) == len(structures)
        for original, updated in zip(structures, decision.structures):
            assert (
                updated.triangles_by_resource
                == original.triangles_by_resource
            )
            assert updated.is_ground_touching == original.is_ground_touching


class TestStaleInheritorBakeIsRestored:
    """Packs on disk already carry the -2.45 m inheritor bake.  The first
    run under the fix must UN-bake them: the resource carries no delta,
    lands in ``decision.skipped``, and ``object_rebake.apply``'s reversion
    pass copies the ``.anchor_bak`` original back byte for byte."""

    def _supporter_fate_decision(self, resource):
        reason = (
            f"{SUPPORTER_FATE_PHRASE} (ground span 25.8 m "
            f"{GROUND_SPAN_SKIP_PHRASE} — left at authored elevations) — "
            "this structure inherits that supporter's ground (invariant "
            "I-8) and must share its fate; left at authored elevations"
        )
        skipped_structure = Structure(
            triangles_by_resource={resource: [(0, 1, 2)]},
            surface_area_square_metres=12.0,
            centroid_latitude=30.1273,
            centroid_longitude=31.4008,
            minimum_base_y_by_resource={resource: 19.7},
            is_ground_touching=False,
            ground_span_metres=0.0,
            needs_pad=False,
            skip_reason=reason,
            inherited_from_structure_index=0,
        )
        return RebakeDecision(
            structures=[skipped_structure],
            delta_by_resource_and_vertex={},
            anchor_ground_by_resource={},
            skipped=[(resource, reason)],
        )

    def test_the_transition_run_unbakes_the_inheritor(self, tmp_path):
        resource = "Airport/T23/red.obj"
        pack_root = tmp_path / "pack"
        live_path = pack_root / resource
        live_path.parent.mkdir(parents=True)
        authored = b"AUTHORED inheritor bytes\n"
        stale_bake = b"inheritor bytes baked -2.445 m by an earlier run\n"
        live_path.write_bytes(stale_bake)
        backup_path = live_path.with_name(live_path.name + ".anchor_bak")
        backup_path.write_bytes(authored)
        mesh_path = tmp_path / "Data+30+031.mesh"
        mesh_path.write_text("MeshVersionFormatted 2\nEnd\n")

        report = object_rebake.apply(
            self._supporter_fate_decision(resource),
            str(pack_root),
            str(mesh_path),
        )

        assert resource in report.objects_reverted
        assert live_path.read_bytes() == authored
        assert report.reversions_missing_backup == []

    def test_a_second_run_leaves_the_restored_file_alone(self, tmp_path):
        # Idempotence: once un-baked, live equals the backup and the
        # reversion pass has nothing to do.
        resource = "Airport/T23/red.obj"
        pack_root = tmp_path / "pack"
        live_path = pack_root / resource
        live_path.parent.mkdir(parents=True)
        authored = b"AUTHORED inheritor bytes\n"
        live_path.write_bytes(authored)
        backup_path = live_path.with_name(live_path.name + ".anchor_bak")
        backup_path.write_bytes(authored)
        mesh_path = tmp_path / "Data+30+031.mesh"
        mesh_path.write_text("MeshVersionFormatted 2\nEnd\n")

        report = object_rebake.apply(
            self._supporter_fate_decision(resource),
            str(pack_root),
            str(mesh_path),
        )

        assert resource not in report.objects_reverted
        assert live_path.read_bytes() == authored


class TestTheGateIsInTheShortCircuitFingerprint:
    def test_flipping_the_gate_changes_the_run_fingerprint(
        self, monkeypatch
    ):
        # A recorded run fingerprint must never let a build short-circuit
        # past a changed decision: the gate is part of the digested set.
        monkeypatch.setattr(config, "DSF_OBJECT_SUPPORTER_FATE", True)
        digest_on = object_rebake._gate_digest(0.25)
        monkeypatch.setattr(config, "DSF_OBJECT_SUPPORTER_FATE", False)
        digest_off = object_rebake._gate_digest(0.25)
        assert digest_on != digest_off
        assert "DSF_OBJECT_SUPPORTER_FATE" in object_rebake._GATE_NAMES
