"""Twins for ``auto_patch.patch_ground`` — the patch's own ground at a
point, which is what the emission-time pad target reads (RULINGS
"OBJECT PADS: EMISSION-TIME RELATIVE", owner 2026-08-14).

The premise these pin is measured, not assumed: at HECA's 2,112 hosted
anchor datums the field reproduced the BUILT mesh to p50 0.029 m /
p90 0.602 m against the 0.75 m ``DSF_OBJECT_FOOT_PAD_RESIDUAL_M`` cap,
and exactly (1e-6 m) at the three datums carrying all 1,874 hosted pad
requests.  These twins hold the RULE that produced those numbers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from auto_patch.patch_ground import (  # noqa: E402
    PatchGroundField,
    _open_ring,
    field_from_layout,
    shapes_from_layout,
)

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_a_flat_ring_carries_its_value_everywhere_inside():
    field = PatchGroundField([("apron", SQUARE, [7.5] * 4)])
    for point in ((1.0, 1.0), (5.0, 5.0), (9.0, 2.0)):
        value, role = field.value_at(*point)
        assert role == "apron"
        assert value == pytest.approx(7.5, abs=1e-9)


def test_a_sloped_ring_interpolates_linearly():
    # z = x: the plane is reproduced exactly, whichever way the ring's
    # Delaunay splits the square.
    field = PatchGroundField([("apron", SQUARE, [0.0, 10.0, 10.0, 0.0])])
    for x in (0.5, 2.0, 5.0, 9.5):
        value, _role = field.value_at(x, 4.0)
        assert value == pytest.approx(x, abs=1e-9)


def test_a_point_outside_every_shape_is_unhosted():
    field = PatchGroundField([("apron", SQUARE, [1.0] * 4)])
    assert field.value_at(50.0, 50.0) == (None, None)


def test_a_pad_role_never_hosts():
    """A pad is what the caller is about to place; reading one would
    make the target self-referential."""
    field = PatchGroundField([
        ("object_pad", SQUARE, [99.0] * 4),
        ("object_pad_blend", SQUARE, [98.0] * 4),
    ])
    assert len(field) == 0
    assert field.value_at(5.0, 5.0) == (None, None)


def test_the_innermost_covering_shape_decides():
    inner = [(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)]
    field = PatchGroundField([
        ("graded_strip", SQUARE, [1.0] * 4),
        ("building", inner, [2.0] * 4),
    ])
    assert field.value_at(5.0, 5.0) == (2.0, "building")
    assert field.value_at(1.0, 1.0) == (1.0, "graded_strip")


def test_a_closed_ring_and_its_open_form_agree():
    closed = SQUARE + [SQUARE[0]]
    open_field = PatchGroundField([("apron", SQUARE, [0.0, 10.0, 10.0, 0.0])])
    closed_field = PatchGroundField(
        [("apron", closed, [0.0, 10.0, 10.0, 0.0, 0.0])])
    assert (closed_field.value_at(3.0, 3.0)
            == open_field.value_at(3.0, 3.0))


def test_the_closing_repeat_is_trimmed_once():
    coords, alts = _open_ring(SQUARE + [SQUARE[0]], [1, 2, 3, 4, 1])
    assert coords == SQUARE
    assert alts == [1, 2, 3, 4]


def test_a_ring_without_altitudes_is_dropped_not_defaulted():
    field = PatchGroundField([("apron", SQUARE, [])])
    assert len(field) == 0


def test_a_ring_with_too_few_vertices_is_dropped():
    field = PatchGroundField([("apron", [(0.0, 0.0), (1.0, 1.0)], [1.0, 2.0])])
    assert len(field) == 0


class _FakeShape:
    def __init__(self, polygon, role, **values):
        self.polygon = polygon
        self.role = role
        self.altitude = values.get("altitude")
        self.altitude_high = values.get("altitude_high")
        self.altitude_low = values.get("altitude_low")
        self.node_altitudes = values.get("node_altitudes")


class _FakeLayout:
    def __init__(self, shapes):
        self.shapes = shapes


def test_a_layout_field_reads_the_flat_altitude_form():
    from shapely.geometry import Polygon

    layout = _FakeLayout([_FakeShape(Polygon(SQUARE), "apron",
                                     altitude=12.25)])
    assert len(shapes_from_layout(layout)) == 1
    field = field_from_layout(layout)
    value, role = field.value_at(5.0, 5.0)
    assert role == "apron"
    assert value == pytest.approx(12.25, abs=1e-9)


def test_a_layout_shape_with_no_altitude_authors_nothing():
    from shapely.geometry import Polygon

    layout = _FakeLayout([_FakeShape(Polygon(SQUARE), "apron")])
    assert shapes_from_layout(layout) == []
    assert len(field_from_layout(layout)) == 0


def test_a_layout_pad_shape_is_dropped_from_the_field():
    from shapely.geometry import Polygon

    layout = _FakeLayout([
        _FakeShape(Polygon(SQUARE), "object_pad", altitude=3.0),
        _FakeShape(Polygon(SQUARE), "apron", altitude=4.0),
    ])
    assert len(field_from_layout(layout)) == 1
    assert field_from_layout(layout).value_at(5.0, 5.0) == (4.0, "apron")
