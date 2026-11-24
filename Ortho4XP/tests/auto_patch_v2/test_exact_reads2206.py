"""Twins of the #2206 step-4 exact speedups: each served reading equals the
one it replaces, bit for bit.

* ``airport/dem_production._BakedTile.sample_one`` -- the point read in
  plain floats -- equals :meth:`sample` at every point;
* ``planar/low_level.unit_share`` -- the bounding-box pre-selection over
  the held part centres (``low_level._part_points``) -- equals the full loop;
* ``airport/wall_class.wall_class_components`` -- read once per airport --
  is served only while its census fields are the same objects."""
from __future__ import annotations

import numpy as np
from shapely.geometry import Point, Polygon

from auto_patch_v2.airport import wall_class
from auto_patch_v2.airport.dem_production import _BakedTile
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar import low_level as _ll
from auto_patch_v2.planar.low_level import unit_share

FRAME = Frame("TEST", (33.64, -84.42), 16)


def test_the_point_read_is_bit_equal_to_the_array_read():
    rng = np.random.default_rng(7)
    for shape, frame in (((1201, 1201), (0.0, 1.0, 0.0, 1.0)),
                         ((361, 241), (-0.0004, 1.0004, -0.0002, 1.0002)),
                         ((10, 7), (0.1, 0.9, 0.05, 0.95))):
        t = _BakedTile(33, -85, rng.normal(300.0, 20.0, shape), *frame)
        lat = 33.0 + rng.uniform(-0.1, 1.1, 4000)
        lon = -85.0 + rng.uniform(-0.1, 1.1, 4000)
        lat[:4], lon[:4] = [33.0, 34.0, 33.5, 34.0], [-85.0, -84.0, -84.5, -85.0]
        want = t.sample(lat, lon)
        got = np.array([t.sample_one(a, b) for a, b in zip(lat, lon, strict=True)])
        assert np.array_equal(want.view(np.int64), got.view(np.int64))


class _Obj:
    """A weakly referable record (the real partition is a dataclass)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _airport(seed: int):
    rng = np.random.default_rng(seed)
    units = []
    for _u in range(12):
        members = []
        for _m in range(3):
            parts = [_Obj(lat=33.64 + rng.uniform(-0.01, 0.01),
                          lon=-84.42 + rng.uniform(-0.01, 0.01),
                          line=bool(rng.random() < 0.1)) for _p in range(20)]
            members.append(_Obj(parts=parts))
        units.append(_Obj(members=members))
    return _Obj(partition=_Obj(units=units), frame=FRAME)


def _full_loop(P, airport, to_xy):
    """The loop ``unit_share`` ran before #2206."""
    by: dict[int, list] = {}
    for ui, u in enumerate(airport.partition.units):
        for m in u.members:
            for p in m.parts:
                if getattr(p, "line", False):
                    continue
                xy = to_xy(p.lon, p.lat)
                if P.contains(Point(xy)):
                    by.setdefault(ui, []).append((p, xy))
    if not by:
        return None, []
    return max(by.items(), key=lambda kv: (len(kv[1]), -kv[0]))


def test_unit_share_pre_selection_equals_the_full_loop():
    ap = _airport(3)
    rng = np.random.default_rng(11)
    for _k in range(15):
        to_xy = ap.frame.entry()          # a fresh projection per call, as the callers do
        cx, cy = rng.uniform(-900.0, 900.0, 2)
        r = rng.uniform(20.0, 700.0)
        P = Point(cx, cy).buffer(r, 3) if _k % 3 else Polygon()
        assert unit_share(P, ap, to_xy) == _full_loop(P, ap, to_xy)
    assert id(ap.partition) in _ll._HELD


def test_part_points_refuse_another_projection():
    ap = _airport(5)
    pts, _xy = _ll._part_points(ap.partition, ap.frame, ap.frame.entry())

    def shifted(lon, lat):
        x, y = ap.frame.entry()(lon, lat)
        return x + 1.0, y

    got, _xy2 = _ll._part_points(ap.partition, ap.frame, shifted)
    assert [q[2] for q in got] == [(x + 1.0, y) for _u, _p, (x, y) in pts]


def test_the_wall_class_reading_is_held_per_census(monkeypatch):
    calls = []
    monkeypatch.setattr(wall_class, "_derive", lambda ap, cfg: calls.append(ap) or ["w"])
    part = _Obj(units=[])
    ap = _Obj(partition=part, frame=FRAME, dem=object(), osm_ways=(), wall_reseats={},
              pavements=())
    cfg = ("service", 1)
    assert wall_class.wall_class_components(ap, cfg) == ["w"]
    # the same census objects under another airport record: served
    twin = _Obj(**{**ap.__dict__, "wall_shade": "x"})
    assert wall_class.wall_class_components(twin, ("service", 1)) == ["w"]
    assert len(calls) == 1
    # a census field replaced, or another cfg: read afresh
    wall_class.wall_class_components(_Obj(**{**ap.__dict__, "dem": object()}), cfg)
    wall_class.wall_class_components(ap, ("service", 2))
    assert len(calls) == 3


def test_floor_pads_pre_selection_equals_on():
    from shapely.strtree import STRtree

    from auto_patch_v2.airport.unit_storey import _on
    from auto_patch_v2.classify.floor_yard import _on_near
    rng = np.random.default_rng(13)
    parts = [(_Obj(base_y=float(k)),
              Point(*rng.uniform(0.0, 500.0, 2)).buffer(rng.uniform(2, 40), 2))
             for k in range(80)]
    ur = _Obj(parts=tuple(parts))
    tree = STRtree([g for _p, g in parts])
    for _k in range(30):
        P = Point(*rng.uniform(0.0, 500.0, 2)).buffer(rng.uniform(10.0, 150.0), 3)
        assert _on_near(ur, tree, P) == _on(ur, P)
