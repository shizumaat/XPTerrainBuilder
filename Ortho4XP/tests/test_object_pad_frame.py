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

from auto_patch import object_anchor, object_frame  # noqa: E402
from test_object_anchor import (  # noqa: E402
    box_vertices_and_triangles,
    make_geometry,
    make_placement,
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
