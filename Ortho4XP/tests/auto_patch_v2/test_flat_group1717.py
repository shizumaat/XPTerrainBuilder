"""#1717 / owner Q370 a, O-F1 a: a flat-built terminal group's held blocks
take ONE datum at the highest level grade law allows
(``planar/flat_group``, ``constraints/platform.datum_groups`` /
``flat_group_level``)."""
from __future__ import annotations

import math
import types

from shapely.geometry import box

from auto_patch_v2.constraints.platform import datum_groups, flat_group_level
from auto_patch_v2.law import Law


def _blk(lo, hi, d, r=(-math.inf, math.inf)):
    return {"I0": (lo, hi), "reach_isect": r, "D": d}


def test_level_is_the_zero_clamped_to_the_highest_lawful():
    blocks = {"a": _blk(96.0, 106.0, 104.8), "b": _blk(95.0, 102.1, 100.3),
              "c": _blk(90.0, 110.0, 101.0)}
    d, rep = flat_group_level(blocks, "a", ["b", "c"])
    assert d == 102.1 and rep["lawful"] == [96.0, 102.1] and rep["blocks"] == 3


def test_level_inside_the_interval_is_the_zero():
    d, _ = flat_group_level({"a": _blk(96.0, 106.0, 104.8), "b": _blk(95.0, 107.0, 100.0)},
                            "a", ["b"])
    assert d == 104.8


def test_a_block_with_no_admissible_level_of_its_own_does_not_bind():
    blocks = {"a": _blk(96.0, 106.0, 104.8), "b": _blk(103.0, 99.0, 100.0)}
    d, rep = flat_group_level(blocks, "a", ["b"])
    assert d == 104.8 and rep["own_empty"] == ["b"]


def test_an_empty_group_interval_keeps_the_preferences():
    d, rep = flat_group_level({"a": _blk(104.0, 106.0, 105.0), "b": _blk(95.0, 100.0, 98.0)},
                              "a", ["b"])
    assert d is None and rep["level"] is None


def test_datum_groups_reads_the_flat_group_off_the_registry():
    held = {"b1": {"flat_group": {"lead": "b2"}}, "b2": {"flat_group": {"lead": "b2"}},
            "b3": {"flat_group": {"lead": "b2"}}, "b4": {}}
    planar = types.SimpleNamespace(registries=types.SimpleNamespace(held=held), faces={})
    got = datum_groups(planar, Law.load(), None, ["b1", "b2", "b3", "b4"])
    assert got == {"b2": ["b1", "b3"]}


def _airport(feet_y, dem_slope):
    """Two halls chained by a walkway, stand-side walls along y = 0 (a
    metric frame: lon = x, lat = y)."""
    def part(x0, x1, y):
        ring = [(0.0, x0), (0.0, x1), (10.0, x1), (10.0, x0)]          # (lat, lon)
        feet = tuple((0.0, float(x), y) for x in range(int(x0), int(x1), 2))
        return types.SimpleNamespace(line=False, scatter=False, rings=(ring,), feet=feet,
                                     height_m=8.0)
    parts = [part(0.0, 200.0, feet_y[0]), part(199.5, 201.5, 0.0), part(201.0, 400.0, feet_y[1])]
    unit = types.SimpleNamespace(members=[types.SimpleNamespace(parts=parts)])
    dem = types.SimpleNamespace(z=lambda x, y: 100.0 + dem_slope * x)
    frame = types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat)))
    return types.SimpleNamespace(partition=types.SimpleNamespace(units=[unit]), dem=dem,
                                 frame=frame, pack=None, icao="TEST")


def _run(monkeypatch, feet_y, slope):
    import auto_patch_v2.airport.flat_pack as fp
    from auto_patch_v2.planar import flat_group as fg
    from auto_patch_v2.planar import low_level
    monkeypatch.setattr(low_level, "_stands_xy",
                        lambda a, t: [(float(x), -20.0) for x in range(0, 400, 25)])
    monkeypatch.setattr(fp, "relief_floor", lambda a, law: (2.0, "lidar"))
    pads = {"west": box(0, 0, 200, 10), "east": box(201, 0, 400, 10)}
    return fg.flat_groups(pads, box(-10, -30, 410, 0.5), _airport(feet_y, slope), Law.load())


def test_a_flat_built_group_on_sloping_ground_is_read(monkeypatch):
    got = _run(monkeypatch, (0.0, 0.0), 0.02)          # 8 m of relief under one foot plane
    assert set(got) == {"west", "east"} and got["east"]["lead"] == got["west"]["lead"]


def test_flat_ground_or_two_foot_planes_read_nothing(monkeypatch):
    assert _run(monkeypatch, (0.0, 0.0), 0.0) == {}    # no relief: nothing to hold
    assert _run(monkeypatch, (0.0, -5.0), 0.02) == {}  # the pack follows the terrain
