"""Twins for the OBJECT PAD FRAME — the mesh-free, pristine-keyed frame
the emission-time pad design and the y-bake fallback both read
(RULINGS "OBJECT PADS: EMISSION-TIME RELATIVE" + Fable's R3 "one frame,
single pass", 2026-08-14).

The two claims that make R3 work are pinned here: the frame is the SAME
whether it comes fresh or out of its sidecar, and it is built without a
mesh at all — ``_measure_structure_parts(sampler=None)`` must reproduce
every pack-data column the sampled call produces.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from auto_patch import obj8_partition, object_anchor, object_frame  # noqa: E402
from test_object_anchor import (  # noqa: E402
    PIT_CENTRE_LATITUDE,
    PIT_CENTRE_LONGITUDE,
    box_vertices_and_triangles,
    make_geometry,
    make_placement,
    pit_sampler,  # noqa: F401  (a pytest fixture, used by name below)
)


def _box_geometry(size: float = 10.0, base_y: float = 0.0):
    """A shed the partition sees as ONE structure, standing on the
    ground: the shared box builder every object twin already uses."""
    vertices, triangles = box_vertices_and_triangles(
        0.0, size, base_y, base_y + 4.0, 0.0, size)
    return make_geometry(vertices, triangles)


def _pool(resource="shed.obj", latitude=30.0, longitude=31.0, agl=0.0):
    placement = make_placement(resource, latitude, longitude)
    placement = placement._replace(above_ground_level_metres=agl)
    return object_anchor.ObjectPool(
        placements=[placement],
        resolved_paths={resource: "/nowhere/" + resource},
    )


class _CountingSampler:
    def __init__(self):
        self.calls = 0

    def elevation_at_or_none(self, latitude, longitude):
        self.calls += 1
        return 100.0


def _frame_and_parts(pool, geometry_by_resource, sampler):
    frame = object_anchor._build_pool_frame(pool, geometry_by_resource)
    structures = object_anchor.partition_structures(pool, geometry_by_resource, epsilon_metres=0.05)
    shared = []
    for structure in structures:
        for resource_path, triangles in structure.triangles_by_resource.items():
            offset = frame.base_offset_by_resource.get(resource_path)
            if offset is None:
                continue
            shared.extend(tuple(offset + i for i in t) for t in triangles)
    return frame, object_anchor._measure_structure_parts(
        frame, sampler, shared, 0.0, 1.0, for_clustering=True)


def test_the_mesh_free_reading_asks_no_mesh_and_matches_the_pack_columns():
    """``sampler=None`` must reproduce every PACK column and consult no
    sampler — that equality is what lets the frame move pre-solve."""
    pool = _pool()
    geometry = {"shed.obj": _box_geometry()}
    sampler = _CountingSampler()
    _f1, sampled = _frame_and_parts(pool, geometry, sampler)
    assert sampler.calls > 0
    _f2, meshfree = _frame_and_parts(pool, geometry, None)

    assert len(meshfree) == len(sampled)
    for a, b in zip(sampled, meshfree):
        assert (a.key, a.base_y, a.base_resource, a.is_ground) == (
            b.key, b.base_y, b.base_resource, b.is_ground)
        assert a.plan_box == b.plan_box
        assert a.area_square_metres == pytest.approx(b.area_square_metres)
        assert a.centroid_x == pytest.approx(b.centroid_x)
        assert a.centroid_z == pytest.approx(b.centroid_z)
        if a.is_ground:
            assert a.latitude == pytest.approx(b.latitude)
            assert a.longitude == pytest.approx(b.longitude)
    # ... and the ground columns are the ONLY difference.
    assert all(p.ground_metres is None for p in meshfree if p.is_ground)
    assert all(p.ground_measured is False for p in meshfree if p.is_ground)


def test_a_built_frame_carries_the_anchor_datum_and_the_contact_geometry():
    pool = _pool(agl=1.25)
    geometry = {"shed.obj": _box_geometry()}
    structures = object_anchor.partition_structures(pool, geometry, epsilon_metres=0.05)
    frame = object_frame.build_pad_frame(pool, geometry, structures)

    assert frame.parts, "a ground-touching shed must raise a pad part"
    part = frame.parts[0]
    assert part.base_resource == "shed.obj"
    assert part.contact_parts_lonlat, "the ring law's input must be present"
    for group in part.contact_parts_lonlat:
        assert len(group) == 3, "one group per contact TRIANGLE (§2.5 v2b)"

    anchor = frame.anchor_by_resource["shed.obj"]
    assert anchor.above_ground_level_metres == pytest.approx(1.25)
    assert anchor.latitude == pytest.approx(30.0)
    assert anchor.longitude == pytest.approx(31.0)


def test_the_frame_groups_its_parts_by_structure():
    pool = _pool()
    geometry = {"shed.obj": _box_geometry()}
    structures = object_anchor.partition_structures(pool, geometry, epsilon_metres=0.05)
    frame = object_frame.build_pad_frame(pool, geometry, structures)
    grouped = frame.parts_by_structure()
    assert sum(len(v) for v in grouped.values()) == len(frame.parts)


def test_the_rendered_base_is_the_seated_false_formula():
    part = object_frame.PadPart(
        structure_index=0, part_key=0, base_resource="a.obj", base_y=-0.5,
        latitude=1.0, longitude=2.0, contact_parts_lonlat=(),
    )
    assert object_frame.rendered_base_metres(part, 100.0) == pytest.approx(99.5)


def test_a_part_whose_anchor_has_no_ground_renders_nothing():
    """Invariant I-13: never guessed, never nearest-vertex sampled."""
    part = object_frame.PadPart(
        structure_index=0, part_key=0, base_resource="a.obj", base_y=0.0,
        latitude=1.0, longitude=2.0, contact_parts_lonlat=(),
    )
    assert object_frame.rendered_base_metres(part, None) is None


class TestTheCircularityFallback:
    """A pad covering its own render datum can close nothing: raising the
    ground raises the object with it and ``AGL + base_y`` is invariant.
    Measured at HECA, 1 of 1883 requests."""

    anchor = object_frame.PadAnchor(latitude=30.0, longitude=31.0,
                                    above_ground_level_metres=0.0)

    def test_a_ring_around_its_own_datum_is_detected(self):
        # (lon, lat) — the ring contract everywhere in the pad family.
        ring = [(lon, lat) for lat, lon in
                [(29.999, 30.999), (29.999, 31.001),
                 (30.001, 31.001), (30.001, 30.999)]]
        assert object_frame.ring_covers_its_own_datum([ring], self.anchor)

    def test_a_ring_elsewhere_is_padable(self):
        ring = [(40.0, 10.0), (40.001, 10.0), (40.001, 10.001)]
        assert not object_frame.ring_covers_its_own_datum([ring], self.anchor)

    def test_no_ring_at_all_is_not_self_covering(self):
        assert not object_frame.ring_covers_its_own_datum([], self.anchor)

    def test_a_degenerate_ring_is_skipped_not_crashed(self):
        assert not object_frame.ring_covers_its_own_datum(
            [[(31.0, 30.0), (31.0, 30.0)]], self.anchor)


class TestTheCacheIsTheSameFrame:
    """Fable's R3 step (1) acceptance: FRAME-FROM-CACHE == FRAME-FRESH.

    The whole point of the sidecar is that a warm build pays ~0 for the
    frame; if what comes back differed from a fresh build in any field,
    every downstream pad would silently depend on cache warmth — the
    warm-vs-cold class that has already moved terrain 12 m in this repo.
    """

    @staticmethod
    def _wire(monkeypatch, tmp_path):
        from auto_patch import dsf_reader, object_rebake, post_mesh

        monkeypatch.setattr(dsf_reader, "airport_mod_cache_dir",
                            lambda pack_root: str(tmp_path))
        monkeypatch.setattr(object_rebake,
                            "pristine_object_fingerprint_entries",
                            lambda pack_root: ["shed.obj:deadbeef"])
        return post_mesh

    def test_the_second_read_comes_from_disk_and_is_identical(
            self, monkeypatch, tmp_path):
        post_mesh = self._wire(monkeypatch, tmp_path)
        pool = _pool(agl=1.25)
        geometry = {"shed.obj": _box_geometry()}
        structures = object_anchor.partition_structures(
            pool, geometry, epsilon_metres=0.05)

        fresh = post_mesh.cached_pad_frame(
            pool, geometry, structures, "/nowhere/pack")
        assert list(tmp_path.glob("o4_object_pad_frame_*.cache")), \
            "the frame must have been written to its sidecar"

        # Second read: make a fresh build IMPOSSIBLE, so anything
        # returned can only have come off the disk.
        from auto_patch import object_frame as _of
        monkeypatch.setattr(_of, "build_pad_frame", _boom)
        warm = post_mesh.cached_pad_frame(
            pool, geometry, structures, "/nowhere/pack")

        assert warm == fresh

    def test_a_law_scalar_change_re_keys_the_cache(
            self, monkeypatch, tmp_path):
        """The key carries the scalars that SHAPE the frame, so moving
        the contact band cannot be served a stale frame."""
        post_mesh = self._wire(monkeypatch, tmp_path)
        from auto_patch import config

        pool = _pool()
        first = post_mesh.pad_frame_cache_key(pool, "/nowhere/pack")
        monkeypatch.setattr(config, "DSF_OBJECT_FOOT_BAND_M",
                            config.DSF_OBJECT_FOOT_BAND_M + 1.0)
        assert post_mesh.pad_frame_cache_key(pool, "/nowhere/pack") != first

    def test_the_disk_half_can_be_switched_off_without_changing_the_answer(
            self, monkeypatch, tmp_path):
        post_mesh = self._wire(monkeypatch, tmp_path)
        monkeypatch.setenv("O4_OBJECT_PAD_FRAME_CACHE", "0")
        pool = _pool()
        geometry = {"shed.obj": _box_geometry()}
        structures = object_anchor.partition_structures(
            pool, geometry, epsilon_metres=0.05)
        frame = post_mesh.cached_pad_frame(
            pool, geometry, structures, "/nowhere/pack")
        assert frame == object_frame.build_pad_frame(
            pool, geometry, structures)
        assert not list(tmp_path.glob("o4_object_pad_frame_*.cache"))


def _boom(*args, **kwargs):
    raise AssertionError("a warm read must not rebuild the frame")


# ---------------------------------------------------------------------------
# R3 STEP (2): the y-bake CONSUMES the frame instead of rebuilding it.
# ---------------------------------------------------------------------------


def _pit_pool_and_geometry():
    """A two-object pool over the PIT mesh: a shed and a lean-to sharing a
    contact edge, so the partition welds several parts and the decision
    exercises grounds, spans and pad requests rather than a trivial box."""
    shed_vertices, shed_triangles = box_vertices_and_triangles(
        0.0, 30.0, 0.0, 8.0, 0.0, 30.0)
    # 0.02 m clear of the shed: WELDING is by exact position, so this is
    # a second PART, while the 0.05 m contact epsilon still binds the two
    # into ONE structure — the multi-part case the welding exists for.
    lean_vertices, lean_triangles = box_vertices_and_triangles(
        30.02, 45.0, 0.0, 4.0, 0.0, 15.0)
    geometry = {
        "shed.obj": make_geometry(shed_vertices, shed_triangles),
        "lean.obj": make_geometry(lean_vertices, lean_triangles),
    }
    placements = [
        make_placement("shed.obj", PIT_CENTRE_LATITUDE, PIT_CENTRE_LONGITUDE),
        make_placement("lean.obj", PIT_CENTRE_LATITUDE, PIT_CENTRE_LONGITUDE),
    ]
    pool = object_anchor.ObjectPool(
        placements=placements,
        resolved_paths={
            "shed.obj": "/nowhere/shed.obj",
            "lean.obj": "/nowhere/lean.obj",
        },
    )
    return pool, geometry


def _pit_case():
    pool, geometry = _pit_pool_and_geometry()
    structures = object_anchor.partition_structures(
        pool, geometry, epsilon_metres=0.05)
    frame = object_frame.build_pad_frame(pool, geometry, structures)
    return pool, geometry, structures, frame


def _shared_triangles(pool_frame, structure):
    shared = []
    for resource_path, triangles in structure.triangles_by_resource.items():
        offset = pool_frame.base_offset_by_resource.get(resource_path)
        if offset is None:
            continue
        shared.extend(tuple(offset + i for i in t) for t in triangles)
    return shared


def test_the_frame_carries_the_welding_and_its_pool_frame_signature():
    """Step (2)'s payload: one label per shared triangle, stamped with
    the index space those triangles belong to."""
    pool, geometry, structures, frame = _pit_case()
    pool_frame = object_anchor._build_pool_frame(pool, geometry)

    assert frame.pool_frame_signature == (
        object_anchor.pool_frame_signature(pool_frame))
    assert frame.welded_labels_by_structure, "the welding must be carried"
    for structure_index, labels in frame.welded_labels_by_structure.items():
        shared = _shared_triangles(pool_frame, structures[structure_index])
        assert len(labels) == len(shared)
        assert len(set(labels)) > 1, (
            "this fixture must exercise a MULTI-part structure, or the "
            "regroup twin below proves nothing")


def test_the_labels_regroup_into_exactly_what_weld_parts_returned():
    """The identity R3 step (2) rests on: a CONSUMED welding and a
    PERFORMED one are the same object, part order and triangle order
    included — otherwise the parts, their keys and every seat drift."""
    pool, geometry, structures, frame = _pit_case()
    pool_frame = object_anchor._build_pool_frame(pool, geometry)
    for structure_index, labels in frame.welded_labels_by_structure.items():
        shared = _shared_triangles(pool_frame, structures[structure_index])
        assert object_frame.regroup_welded_parts(shared, labels) == (
            obj8_partition.weld_parts(pool_frame.shared_vertices, shared))


def test_the_frame_consuming_rebake_decides_exactly_what_the_old_one_did(
        pit_sampler):  # noqa: F811
    """THE STEP (2) ACCEPTANCE TWIN: same mesh in, same decision out.

    The frame supplies the welding and nothing else, so every downstream
    number — deltas, grounds, spans, skips, pad requests, cluster seats —
    must be identical to the build that welded for itself.  If it is
    not, the frame is not the same frame and R3's whole premise fails.
    """
    pool, geometry, structures, frame = _pit_case()

    without = object_anchor.structure_deltas(
        pool, geometry, structures, pit_sampler)
    with_frame = object_anchor.structure_deltas(
        pool, geometry, structures, pit_sampler, pad_frame=frame)

    assert with_frame == without


def test_a_supplied_welding_means_the_rebake_never_welds(
        monkeypatch, pit_sampler):  # noqa: F811
    """The COST claim, not just the value claim (acceptance (c)): with the
    frame in hand the rebake must not call ``weld_parts`` at all — that
    call measured 783.6 s, 57.8 % of a +30+031 build, in the 2026-07-26
    profile.  Proved by making it raise."""
    pool, geometry, structures, frame = _pit_case()

    def _no_welding(*args, **kwargs):
        raise AssertionError("the frame's welding must be consumed, not redone")

    monkeypatch.setattr(obj8_partition, "weld_parts", _no_welding)
    decision = object_anchor.structure_deltas(
        pool, geometry, structures, pit_sampler, pad_frame=frame)
    assert decision.structures


class TestTheFrameIsRefusedRatherThanMisread:
    """A welded part is a list of pool-frame vertex INDICES.  Read against
    the wrong frame it would name real vertices at wrong positions — a
    silent, plausible wrong answer, which is the one outcome this repo's
    never-silent posture forbids."""

    def test_a_foreign_signature_is_refused_and_the_decision_still_right(
            self, pit_sampler):  # noqa: F811
        pool, geometry, structures, frame = _pit_case()
        import dataclasses

        foreign = dataclasses.replace(
            frame, pool_frame_signature=("some other pool", 1, 2))
        assert object_anchor.structure_deltas(
            pool, geometry, structures, pit_sampler, pad_frame=foreign,
        ) == object_anchor.structure_deltas(
            pool, geometry, structures, pit_sampler)

    def test_a_welding_that_does_not_partition_the_structure_is_refused(
            self, pit_sampler):  # noqa: F811
        """The signature matches but the partition does not — the
        partition-cache skew the pristine key cannot see."""
        pool, geometry, structures, frame = _pit_case()
        import dataclasses

        truncated = dataclasses.replace(
            frame,
            welded_labels_by_structure={
                index: labels[:1]
                for index, labels in frame.welded_labels_by_structure.items()
            },
        )
        assert object_anchor.structure_deltas(
            pool, geometry, structures, pit_sampler, pad_frame=truncated,
        ) == object_anchor.structure_deltas(
            pool, geometry, structures, pit_sampler)
