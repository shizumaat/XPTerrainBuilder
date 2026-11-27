"""Twin for #2302 (LEMD: almost no building pads).  A single PLANE authored
deep under its zero over the whole airport (LEMD's one-quad region sheets
50 m down, 2.0-2.6 km2 each) is no trench object: it pins no tunnel mouth
and casts no entrance shade, so the cluster pads it covers stand.  A thin
floor slab with a thickness keeps its trench reading
(``test_entrance_object1747``).  Synthetic OBJ8 and ways; law values read
from the tables."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.entrance_shade import entrance_shade
from auto_patch_v2.airport.trench_objects import mouth_portals, read_trench_objects
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import read_objects
from test_tunnel_objects import _airport, _slab, _write

_T = {"highway": "primary", "lanes": "2", "tunnel": "yes", "layer": "-1"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    # one quad 50 m under its zero, 400 m across (two triangles, no extent)
    plane = _write(d / "plane.obj",
                   [(-200.0, -50.0, -200.0), (200.0, -50.0, -200.0),
                    (200.0, -50.0, 200.0), (-200.0, -50.0, 200.0)],
                   [(0, 1, 2), (0, 2, 3)])
    vt: list = []
    tris: list = []
    _slab(vt, tris, -6.0, 6.0, -6.0, 6.0, -5.2, -5.0)
    return {"dir": d, "plane": plane, "sheet": _write(d / "sheet.obj", vt, tris)}


def _read(objs, law, name, tunnel):
    airport = _airport(objs, law, [(name, (0.0, 0.0), 0.0, 0.0, "OBJECT")], (tunnel,))
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    trenches, _notes = read_trench_objects(objects, cache, law, [tunnel])
    return airport, cache, objects, trenches


def test_a_buried_plane_is_no_trench_and_shades_no_pad(objs, law):
    tunnel = OsmWay(-7, "big_roads", ((0.0, 3.0), (0.0, 300.0)), False, _T)
    airport, cache, objects, trenches = _read(objs, law, "plane", tunnel)
    assert objects and trenches == []
    assert mouth_portals(trenches, objects, cache, law, [tunnel], airport.dem.z) == []
    assert entrance_shade(airport, objects, cache, law) is None


def test_a_thin_floor_slab_keeps_its_trench_reading(objs, law):
    tunnel = OsmWay(-7, "big_roads", ((0.0, 3.0), (0.0, 300.0)), False, _T)
    airport, cache, objects, trenches = _read(objs, law, "sheet", tunnel)
    assert [t.object_id for t in trenches] == ["dsf:obj0"]
    assert mouth_portals(trenches, objects, cache, law, [tunnel], airport.dem.z)
