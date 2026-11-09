"""Issues #1950 / #1952 twins — A PIT NEEDS A FLOOR YOU COULD STAND ON
(``planar/basin_floor_width.py``).

KMCI is where it was found: the border retaining wall
(``Airport/Border/KCMO-Trimsheet-16.obj``) is modelled down to its
footing, a strip about a metre wide 12 m under the wall's top along its
whole length.  04i rule 1 read that strip as a floor plate, the region
pass took the wall's own plan as a pit and cut a slot 13-20 m deep beside
a wall whose visible foot is 6 m down.

The fixtures: the same footing shape (a long box ``2 * FOOT_HZ`` wide)
and a box pit, both on a flat DEM.  With the rule the footing is refused
and named; the pit stays a basin.  Law values are read from the tables.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.basin_witness import read_objects
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basin_floor_width import floor_share
from auto_patch_v2.planar.basins import build_basins
from shapely.geometry import box
from test_m4b import _box_obj
from test_v2basinfix import _airport, _cells, _FlatDem

FOOT_HZ = 0.5          # a 1 m wide footing, as KMCI's border wall


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("basin1952_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text(
        "I\n1000 Version\n", encoding="utf-8", newline="")
    dd = law.tables.structures.basin.admission_depth_m
    return {"dir": d,
            "footing": _box_obj(d / "footing.obj", hx=60.0, hz=FOOT_HZ, depth=4.0 * dd),
            "pit": _box_obj(d / "pit.obj", hx=30.0, hz=20.0, depth=2.0 * dd)}


def _basins(objs, law, name):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    a = _airport(objs, law, name, _FlatDem(), hx=10.0, hz=10.0)
    objects, rep = read_objects(a, law, cache)
    _cl, basins, stats = build_basins(a, Classification(tuple(_cells()), (), {}, ()),
                                      law, (), objects, cache=cache, report=rep)
    return objects, basins, stats


def test_a_wall_footing_is_not_a_pit(objs, law):
    objects, basins, stats = _basins(objs, law, "footing")
    # rule 1 still WITNESSES it (every other reader sees the same reading)...
    assert [o.id for o in objects if o.witnesses] == ["dsf:obj0"]
    # ...but no pit is cut, and the refusal names the object and the law
    assert basins == ()
    bl = law.tables.structures.basin
    line = next(r for r in stats.refused if "WALL'S FOOTING" in r)
    assert "dsf:obj0 footing.obj#0" in line
    assert f"footprint_close_m {bl.footprint_close_m:g} m wide" in line


def test_a_pit_with_a_floor_stays_a_basin(objs, law):
    _objects, basins, stats = _basins(objs, law, "pit")
    assert len(basins) == 1, stats.refused
    assert not any("WALL'S FOOTING" in r for r in stats.refused)


def test_floor_share_reads_width_not_area(law):
    w = law.tables.structures.basin.footprint_close_m
    assert floor_share(box(0, 0, 400, 0.5 * w), w) == 0.0     # a long strip: no floor
    assert floor_share(box(0, 0, 20, 20), w) == pytest.approx(1.0)
    assert floor_share(box(0, 0, 0, 0), w) == 0.0
