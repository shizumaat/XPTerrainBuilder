"""RULINGS 2026-11-20o (#2194): the stretch of a mapped bore between two
mouths one pack entrance object pins is kept off the zones
(``planar/pinned_span``)."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.planar.pinned_span import pinned_spans


def _t(cap, portal="dsf:obj1", floor=True, ways=(-1, -2), half=18.0):
    return types.SimpleNamespace(portal=portal, portal_floor=floor, cap_centre=cap,
                                 ways=ways, half_width_m=half)


def test_both_mouths_pinned_by_one_object_keep_the_span_off_the_zones():
    got = pinned_spans([_t((0.0, 0.0)), _t((84.0, 0.0), half=19.0)])
    assert len(got) == 1 and got[0].area == pytest.approx(84.0 * 38.0)


def test_one_pinned_mouth_or_two_objects_is_no_span():
    assert pinned_spans([_t((0.0, 0.0))]) == []
    assert pinned_spans([_t((0.0, 0.0)), _t((84.0, 0.0), portal="dsf:obj2")]) == []
    assert pinned_spans([_t((0.0, 0.0)), _t((84.0, 0.0), floor=False)]) == []
