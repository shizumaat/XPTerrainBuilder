"""Unit tests for the NEAR-MISS building-frontage recognition (2026-07-08).

A DSF building-pad outline and the apt.dat apron edge it fronts can be offset
by a sub-metre source mismatch (SPJC building29 vs its SW apron: 0.68 m),
leaving a thin unpaved sliver that defeats every exact-identity reconciler
(they all key off ``SHARED_VERTEX_TOL_M`` = 0.5 m, the one canonical
identity).  ``anchors._near_miss_frontage_contacts`` recognizes such pairs
per-EDGE and its two consumers emit raise-biased soft floors
(``near_miss_building_frontage_floors``) and joint-projection law edges
(``near_miss_building_frontage_edges``) toward the pad's ALREADY-CHOSEN seat.

These tests pin the recognition contract:

* a pad + apron at a 0.7 m offset (inside ``BUILDING_FRONTAGE_NEAR_MISS_M``)
  gets the raise anchors — floors ``seat − APRON_MAX_GRADE·d`` and edges with
  budget ``APRON_MAX_GRADE·d``;
* the same pair at a 1.5 m offset (outside the radius) gets nothing;
* the pad seat is UNCHANGED in both cases (raise-biased: the near-miss edge
  never feeds the pad's seat);
* a genuinely SHARED (vertex-welded) frontage is not a near miss — identity
  already reconciles it, so no anchors are emitted;
* the ``O4_BUILDING_FRONTAGE_NEAR_MISS=0`` gate disables recognition.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.config import APRON_MAX_GRADE
from auto_patch.layout import ROLE_APRON, ROLE_BUILDING
from auto_patch.elevation_per_surface.route_profile.anchors import (
    BUILDING_FRONTAGE_NEAR_MISS_M,
    near_miss_building_frontage_edges,
    near_miss_building_frontage_floors,
)

PAD_SEAT = 25.56


class _Shape:
    def __init__(self, role, polygon, ref=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref


class _Layout:
    def __init__(self, shapes):
        self.shapes = shapes
        self.canonical_points = CanonicalPointRegistry()


def _open_ring(polygon):
    coords = list(polygon.exterior.coords)
    return coords[:-1] if coords[0] == coords[-1] else coords


def _build_fixture(gap_m):
    """A 10x10 flat pad and a 20x10 apron across ``gap_m`` of unpaved
    sliver (no shared vertices), the SPJC building29 shape class."""
    pad = _Shape(ROLE_BUILDING, Polygon(
        [(0, 0), (10, 0), (10, 10), (0, 10)]), ref="pad")
    apron = _Shape(ROLE_APRON, Polygon(
        [(10 + gap_m, 0), (30 + gap_m, 0), (30 + gap_m, 10),
         (10 + gap_m, 10)]))
    layout = _Layout([pad, apron])
    bucket_to_idx = {}
    for shape in layout.shapes:
        for (x, y) in _open_ring(shape.polygon):
            key = layout.canonical_points.get_or_add(float(x), float(y))
            if key not in bucket_to_idx:
                bucket_to_idx[key] = len(bucket_to_idx)
    pad_nodes = {bucket_to_idx[layout.canonical_points.get_or_add(
        float(x), float(y))] for (x, y) in _open_ring(pad.polygon)}
    apron_nodes = {bucket_to_idx[layout.canonical_points.get_or_add(
        float(x), float(y))] for (x, y) in _open_ring(apron.polygon)}
    building_seats = {i: PAD_SEAT for i in pad_nodes}
    return layout, bucket_to_idx, building_seats, pad_nodes, apron_nodes


def _wide_band(_x, _y):
    return (0.0, 1000.0)


def test_near_miss_pair_gets_raise_anchors():
    """0.7 m offset (inside the radius): floors + edges on the apron's
    near-miss edge endpoints, seat − cap·d, pad seat untouched."""
    gap = 0.7
    assert gap < BUILDING_FRONTAGE_NEAR_MISS_M
    (layout, bucket_to_idx, building_seats,
     pad_nodes, apron_nodes) = _build_fixture(gap)
    seats_before = dict(building_seats)

    floors = near_miss_building_frontage_floors(
        layout, bucket_to_idx, _wide_band, building_seats)
    edges = near_miss_building_frontage_edges(
        layout, bucket_to_idx, building_seats)

    assert floors, "near-miss pair must be recognized"
    assert edges, "near-miss pair must emit law edges"
    # Anchors live on APRON nodes only — never on the pad.
    assert set(floors) <= apron_nodes
    assert not (set(floors) & pad_nodes)
    # The apron's frontage corners (10.7, 0) / (10.7, 10) sit exactly
    # ``gap`` from the pad: floor = seat − cap·gap, raise-biased (≤ seat).
    near_corner = bucket_to_idx[layout.canonical_points.get_or_add(
        10.0 + gap, 0.0)]
    assert near_corner in floors
    assert floors[near_corner] == pytest.approx(
        PAD_SEAT - APRON_MAX_GRADE * gap, abs=1e-6)
    for level in floors.values():
        assert level <= PAD_SEAT + 1e-9
    # Law edges pair each floored endpoint with a PAD node at the
    # apron-law budget cap·d.
    for (apron_node, pad_node, budget) in edges:
        assert apron_node in apron_nodes
        assert pad_node in pad_nodes
        assert budget >= APRON_MAX_GRADE * gap - 1e-9
    near_edge = [e for e in edges if e[0] == near_corner]
    assert near_edge and near_edge[0][2] == pytest.approx(
        APRON_MAX_GRADE * gap, abs=1e-6)
    # Pad seat UNCHANGED (the near-miss edge never feeds the seat).
    assert building_seats == seats_before


def test_beyond_radius_pair_is_not_recognized():
    """1.5 m offset (outside the radius): a real setback, no anchors."""
    gap = 1.5
    assert gap > BUILDING_FRONTAGE_NEAR_MISS_M
    (layout, bucket_to_idx, building_seats,
     _pad_nodes, _apron_nodes) = _build_fixture(gap)
    seats_before = dict(building_seats)

    floors = near_miss_building_frontage_floors(
        layout, bucket_to_idx, _wide_band, building_seats)
    edges = near_miss_building_frontage_edges(
        layout, bucket_to_idx, building_seats)

    assert floors == {}
    assert edges == []
    assert building_seats == seats_before


def test_shared_frontage_is_not_a_near_miss():
    """A vertex-welded (gap 0) frontage is reconciled by IDENTITY — the
    recognition must not re-anchor it."""
    (layout, bucket_to_idx, building_seats,
     _pad_nodes, _apron_nodes) = _build_fixture(0.0)

    floors = near_miss_building_frontage_floors(
        layout, bucket_to_idx, _wide_band, building_seats)
    edges = near_miss_building_frontage_edges(
        layout, bucket_to_idx, building_seats)

    assert floors == {}
    assert edges == []


# ── PAD ROD COUPLING contact map (docs/specs/pad-rod-coupling-spec.md) ───

def test_weld_refs_out_carries_the_pad_seat():
    """``weld_refs_out`` fills the SAME contact set with the pad's seat —
    the §7 reference of a pad-face-welded fabric vertex IS the seat."""
    gap = 0.7
    (layout, bucket_to_idx, building_seats,
     pad_nodes, apron_nodes) = _build_fixture(gap)

    weld_refs = {}
    edges = near_miss_building_frontage_edges(
        layout, bucket_to_idx, building_seats, weld_refs_out=weld_refs)

    assert weld_refs, "the pad-face contacts must carry a reference"
    # Same contact set as the law edges — one reference per contact node.
    assert set(weld_refs) == {a for (a, _p, _b) in edges}
    # Apron side only; never the pad (the pad's own rod is its seat).
    assert set(weld_refs) <= apron_nodes
    assert not (set(weld_refs) & pad_nodes)
    for (level, pad_node) in weld_refs.values():
        assert level == pytest.approx(PAD_SEAT, abs=1e-9)
        # The PAD NODE rides along: the call site resolves the pad's own
        # rod through it (the seat scalar is pre-merge and can be stale).
        assert pad_node in pad_nodes


def test_weld_refs_out_is_optional_and_leaves_edges_identical():
    """Omitting the out-param is the pre-coupling behavior exactly."""
    (layout, bucket_to_idx, building_seats,
     _pad_nodes, _apron_nodes) = _build_fixture(0.7)
    without = near_miss_building_frontage_edges(
        layout, bucket_to_idx, building_seats)
    (layout2, b2i2, seats2, _pn2, _an2) = _build_fixture(0.7)
    weld_refs = {}
    with_out = near_miss_building_frontage_edges(
        layout2, b2i2, seats2, weld_refs_out=weld_refs)
    assert with_out == without
    assert weld_refs


def test_weld_refs_out_takes_the_nearer_pad():
    """A fabric vertex facing TWO pads references the NEARER contact
    (spec §2 — pads may legitimately differ; the inter-pad step
    exemption stays)."""
    near_seat, far_seat = 25.56, 31.0
    near_pad = _Shape(ROLE_BUILDING, Polygon(
        [(0, 0), (10, 0), (10, 10), (0, 10)]), ref="near")
    # Gaps 0.7 m / 0.95 m: both inside the near-miss radius and both wider
    # than the canonical merge radius (0.5 m — a narrower gap would make
    # the corner a SHARED vertex and identity would own it).
    apron = _Shape(ROLE_APRON, Polygon(
        [(10.7, 0), (20.0, 0), (20.0, 10), (10.7, 10)]))
    far_pad = _Shape(ROLE_BUILDING, Polygon(
        [(20.95, 0), (30, 0), (30, 10), (20.95, 10)]), ref="far")
    layout = _Layout([near_pad, apron, far_pad])
    bucket_to_idx = {}
    for shape in layout.shapes:
        for (x, y) in _open_ring(shape.polygon):
            key = layout.canonical_points.get_or_add(float(x), float(y))
            bucket_to_idx.setdefault(key, len(bucket_to_idx))

    def _idx(x, y):
        return bucket_to_idx[layout.canonical_points.get_or_add(
            float(x), float(y))]

    building_seats = {}
    for (x, y) in _open_ring(near_pad.polygon):
        building_seats[_idx(x, y)] = near_seat
    for (x, y) in _open_ring(far_pad.polygon):
        building_seats[_idx(x, y)] = far_seat

    weld_refs = {}
    near_miss_building_frontage_edges(
        layout, bucket_to_idx, building_seats, weld_refs_out=weld_refs)

    # The apron's west corners are 0.4 m from the near pad and 0.9 m from
    # the far one: both contacts fire, the NEARER seat wins.
    west = _idx(10.7, 0.0)
    east = _idx(20.0, 0.0)
    assert weld_refs[west][0] == pytest.approx(near_seat, abs=1e-9)
    assert weld_refs[east][0] == pytest.approx(far_seat, abs=1e-9)
    assert weld_refs[west][1] in {_idx(x, y)
                                 for (x, y) in _open_ring(near_pad.polygon)}
    assert weld_refs[east][1] in {_idx(x, y)
                                 for (x, y) in _open_ring(far_pad.polygon)}


def test_weld_refs_out_empty_when_recognition_is_off(monkeypatch):
    monkeypatch.setenv("O4_BUILDING_FRONTAGE_NEAR_MISS", "0")
    (layout, bucket_to_idx, building_seats,
     _pad_nodes, _apron_nodes) = _build_fixture(0.7)
    weld_refs = {}
    assert near_miss_building_frontage_edges(
        layout, bucket_to_idx, building_seats,
        weld_refs_out=weld_refs) == []
    assert weld_refs == {}


def test_gate_off_disables_recognition(monkeypatch):
    monkeypatch.setenv("O4_BUILDING_FRONTAGE_NEAR_MISS", "0")
    (layout, bucket_to_idx, building_seats,
     _pad_nodes, _apron_nodes) = _build_fixture(0.7)

    floors = near_miss_building_frontage_floors(
        layout, bucket_to_idx, _wide_band, building_seats)
    edges = near_miss_building_frontage_edges(
        layout, bucket_to_idx, building_seats)

    assert floors == {}
    assert edges == []
