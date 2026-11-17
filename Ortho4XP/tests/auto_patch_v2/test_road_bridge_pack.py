"""Twins of ``planar/road_bridge_pack`` (spec 2123 B1 (c), "the pack always
wins"): a generated road bridge is refused where the pack draws its own
bridge -- an elevated top over the span, a hard deck, or a road segment of
its own along the axis at any level -- and stands where the pack only drapes
pavement there, lays an at-grade object, or has a road crossing under it."""
from __future__ import annotations

import types

from auto_patch_v2.law.tables import load_default
from auto_patch_v2.planar.road_bridge_pack import pack_provides
from shapely.geometry import LineString, box
from test_deck_pack_cover import _geom, _obj, _quad  # noqa: E402  (sibling twin)

LAW = load_default()
LINE = LineString([(-40, 0), (40, 0)])
SPAN = LINE.buffer(4.0, cap_style="flat")


def _roads(*segs):
    return types.SimpleNamespace(segments=lambda: list(segs))


def _why(*placed, roads=()) -> str:
    geoms = {o.resolved: g for o, g in placed}
    cache = types.SimpleNamespace(geometry=lambda r: geoms.get(r))
    return pack_provides(SPAN, LINE, [o for o, _g in placed], cache, _roads(*roads), LAW)


def test_the_packs_bridge_object_over_the_span_refuses_it():
    why = _why(_obj("brg", _geom([_quad(6.0, 50.0)])))
    assert "brg" in why and "top over 100 %" in why


def test_a_bridge_the_pack_models_in_pieces_is_the_packs():
    """Two elevated pieces, each over 40 % of the axis, together 80 %."""
    a, b = _obj("a", _geom([_quad(6.0, 16.0)])), _obj("b", _geom([_quad(6.0, 16.0)]))
    a[0].xy, b[0].xy = (-22.0, 0.0), (22.0, 0.0)
    why = _why(a, b)
    assert "top over 80 %" in why and "a (" in why and "b (" in why


def test_a_pack_hard_deck_over_the_span_refuses_it():
    assert "hard deck hd" in _why(_obj("hd", _geom([_quad(0.0, 5.0)]),
                                       hard_deck=box(-30, -30, 30, 30)))


def test_draped_pavement_and_an_at_grade_object_leave_it_ours():
    assert _why(_obj("page", _geom([_quad(0.0, 50.0)], draped=True)),
                _obj("lot", _geom([_quad(0.5, 50.0)]))) == ""


def test_the_packs_own_road_along_the_axis_refuses_it_at_any_level():
    for level in (0, 1):
        why = _why(roads=[("roads.net", 50, level, LineString([(-45, 2.0), (45, 2.5)]))])
        assert f"level {level}" in why and "road network" in why


def test_a_pack_road_crossing_under_the_span_is_not_the_bridge():
    assert _why(roads=[("roads.net", 30, 0, LineString([(0, -60), (0, 60)])),
                       ("roads.net", 30, 0, LineString([(-45, 30), (45, 30)]))]) == ""
