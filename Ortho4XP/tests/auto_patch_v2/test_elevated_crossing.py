"""The crossing read of RULINGS 2026-11-20g (``airport/elevated_crossing``):
a structure SPANNING a mapped road's carriageway over its ground is one
crossing at its least clearance; a car at the kerb, a part standing on the
road and a mapped bridge are none; the class minimum is the road's."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport.elevated_crossing import (SPAN_SHARE, carriageways, crossable,
                                                     read_crossings)
from auto_patch_v2.law import Law


@pytest.fixture(scope="module")
def law():
    return Law.load()


def _way(wid, pts, **tags):
    return types.SimpleNamespace(id=wid, points=pts, tags=tags)


def _slab(x0, x1, y0, y1, z):
    """Two horizontal faces covering ``[x0, x1] x [y0, y1]`` at ``z``."""
    a, b, c, d = (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)
    return np.array([[a, b, c], [a, c, d]], dtype=float)


def _flat(z):
    return lambda xs, ys: np.full(np.shape(xs), z, dtype=float)


def test_crossable_ways(law):
    assert crossable({"highway": "service"})
    assert crossable({"railway": "rail"})
    assert crossable({"highway": "service", "tunnel": "yes", "layer": "-1"})
    assert not crossable({"highway": "service", "bridge": "yes"})
    assert not crossable({"building": "yes"})
    assert not crossable({"highway": "footway"})
    assert not crossable({"railway": "abandoned"})
    cw = carriageways([_way("1", [(0, -50), (0, 50)], highway="service"),
                       _way("2", [(10, -50), (10, 50)], highway="primary"),
                       _way("3", [(20, -50), (20, 50)], railway="rail")],
                      lambda w: w.points, law)
    assert [c.need_m for c in cw] == [4.2, 5.0, 5.0]


def test_a_sky_bridge_over_a_road_is_one_crossing_at_its_least_clearance(law):
    # a 7 m service road along y; a 6 m wide bridge deck across it at 3.0 m,
    # dipping to 2.6 m over the road's east half; the ground at 10.0
    cw = carriageways([_way("r", [(0.0, -40.0), (0.0, 40.0)], highway="service", lanes="2")],
                      lambda w: w.points, law)
    deck = np.concatenate([_slab(-30, 0, -3, 3, 13.0), _slab(0, 30, -3, 3, 12.6)])
    out = read_crossings([("bridge", deck, None)], cw, _flat(10.0))
    assert len(out) == 1
    c = out[0]
    assert c.owner == "bridge" and c.way == "r" and c.kind == "highway=service"
    assert c.least_m == pytest.approx(2.6) and c.short_m == pytest.approx(1.6)
    assert c.cells > 0 and c.at[0] > 0.0


def test_a_car_at_the_kerb_and_a_part_on_the_road_are_no_crossing(law):
    cw = carriageways([_way("r", [(0.0, -40.0), (0.0, 40.0)], highway="service", lanes="2")],
                      lambda w: w.points, law)
    car = _slab(1.5, 3.5, -2.0, 2.5, 10.6)          # 2 m of the 7 m: no span
    wall = _slab(-30, 30, -1, 1, 10.2)               # at grade: under 0.5 m over the ground
    assert read_crossings([("car", car, None), ("wall", wall, None)], cw, _flat(10.0)) == []
    assert SPAN_SHARE > 2.0 / 7.0


def test_a_floor_counts_a_soffit_pushed_into_the_road(law):
    # the object stage passes the frame's floor: a deck authored over its
    # zero whose ground rose over it still crosses, at a negative clearance
    cw = carriageways([_way("r", [(0.0, -40.0), (0.0, 40.0)], railway="rail")],
                      lambda w: w.points, law)
    deck = _slab(-30, 30, -3, 3, 10.4)
    out = read_crossings([("d", deck, 10.0)], cw, _flat(11.0))
    assert len(out) == 1 and out[0].least_m == pytest.approx(-0.6)
    assert out[0].short_m == pytest.approx(5.6)
