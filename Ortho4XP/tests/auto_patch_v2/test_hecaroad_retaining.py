"""§47 ADDENDUM — A WALL ALONG A ROAD EDGE IS A RETAINING WALL: the twins
(owner RULINGS 2026-09-27a (8); issue #8 [HECA-3];
``classify/retaining_wall``).

The site: HECA 30.1122535, 31.4062746 — the pack's 3.1 m
``metal_strip_2.obj`` wall runs along the service road and on past the
end of the 1206 route; the road's graded strip extends to the wall.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from shapely.geometry import LineString, Point, box

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify import retaining_wall as rw


class _Frame:
    """(lon, lat) -> xy with the degrees read as metres: the rule is plan
    geometry, and the twin keeps it in one frame."""

    @staticmethod
    def entry():
        return lambda lon, lat: (lon, lat)


def _ring(poly):
    return tuple((y, x) for x, y in list(poly.exterior.coords)[:-1])


def _airport(*parts):
    members = [NS(resource=f"wall{i}.obj", parts=(NS(
        rings=tuple(_ring(g) for g in rings), height_m=h, comp=i),))
        for i, (rings, h) in enumerate(parts)]
    return NS(partition=NS(units=(NS(members=tuple(members)),)), frame=_Frame())


RIBBON = LineString([(0.0, 0.0), (100.0, 0.0)]).buffer(3.0, cap_style="flat")
LANE = 4.0


@pytest.fixture(scope="module")
def cfg():
    return load_rules().service


def test_the_thresholds_are_rule_values(cfg):
    assert cfg.retaining_wall_min_height_m == 2.0
    assert cfg.retaining_wall_min_length_m == 10.0


def test_a_tall_thin_wall_along_the_road_retains_it_and_the_road_reaches_it(cfg):
    """A 3.1 m wall 2 m off the ribbon's edge, running past the ribbon's
    END by 20 m: the strip between road and wall joins the road, up to the
    wall's face (never across it)."""
    wall = box(0.0, 5.0, 120.0, 5.3)
    pieces = rw.retaining_pieces(_airport(((wall,), 3.1)), RIBBON, LANE, cfg)
    assert len(pieces) == 1 and pieces[0].height_m == pytest.approx(3.1)
    ext = rw.road_extension(pieces, RIBBON, LANE)
    assert ext.area > 0.0
    assert ext.contains(Point(50.0, 4.0))            # the gap is road now
    assert not ext.intersects(Point(50.0, 6.0))      # the far side is not
    assert ext.intersection(wall).area == pytest.approx(0.0, abs=1e-6)


def test_a_short_or_low_or_thick_object_is_not_a_wall(cfg):
    low = box(0.0, 5.0, 60.0, 5.3)
    short = box(0.0, 5.0, 6.0, 5.3)
    thick = box(0.0, 5.0, 60.0, 15.0)
    ap = _airport(((low,), 1.2), ((short,), 3.0), ((thick,), 8.0))
    assert rw.retaining_pieces(ap, RIBBON, LANE, cfg) == []


def test_a_wall_beyond_one_lane_width_retains_nothing(cfg):
    far = box(0.0, 3.0 + LANE + 2.0, 60.0, 3.0 + LANE + 2.3)
    assert rw.retaining_pieces(_airport(((far,), 3.1)), RIBBON, LANE, cfg) == []
    assert rw.road_extension([], RIBBON, LANE).is_empty


def test_an_extension_piece_apart_from_the_road_is_dropped(cfg):
    """Only what JOINS the ribbon extends the road (hecaroad_close1's
    detached ``route4``)."""
    from shapely.geometry import Polygon
    ext = rw.road_extension([rw.RetainingPiece(box(0.0, 5.0, 60.0, 5.3), 3.1,
                                               "w.obj", 0, 2.0)], RIBBON, LANE)
    for g in getattr(ext, "geoms", [ext]):
        assert isinstance(g, Polygon) and g.distance(RIBBON) < 1e-6
