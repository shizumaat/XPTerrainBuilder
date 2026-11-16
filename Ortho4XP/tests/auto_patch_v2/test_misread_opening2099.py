"""Twin for #2099 Part F (owner RULINGS 2026-11-16a, 2026-11-15j, 2026-10-19p;
spec ``docs/specs/2099-F.md``): an entrance opening read under one road lane
is a MISREAD -- the face is re-read off its walls, jamb to jamb from the bore
line, seated on the ground its walls retain (``trench_objects._misread_face``)
-- and a trench object so misread whose walls stand on both sides of an open
floor is cut to its walls as an object floor (``airport/walled_trench``).
Synthetic OBJ8 and ways; law values read from the tables."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.trench_objects import _ground_max, mouth_portals, read_trench_objects
from auto_patch_v2.airport.walled_trench import walled_trench_floors
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import read_objects
from test_tunnel_objects import _airport, _slab, _write

_T = {"highway": "primary", "lanes": "2", "tunnel": "yes", "layer": "-1"}


def _headwall(vt, tris, half: float) -> None:
    """A full-height face across the bore at z = 0 (y -6 .. +1), authored in
    three pieces whose seams stand 0.2 m either side of the bore line: its
    foot breaks there, so the gap reader reads 0.4 m."""
    for x0, x1 in ((-half, -0.2), (-0.2, 0.2), (0.2, half)):
        _slab(vt, tris, x0, x1, -0.5, 0.5, -6.0, 1.0)


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
    out = {"dir": d}
    vt: list = []
    tris: list = []
    _headwall(vt, tris, 15.0)
    out["face"] = _write(d / "face.obj", vt, tris)
    vt, tris = [], []
    _headwall(vt, tris, 1.0)
    out["narrow"] = _write(d / "narrow.obj", vt, tris)
    # a trench: the face and two walls running 60 m out along the approach
    vt, tris = [], []
    _headwall(vt, tris, 8.0)
    _slab(vt, tris, -8.0, -7.0, 0.5, 60.0, -6.0, -0.1)
    _slab(vt, tris, 7.0, 8.0, 0.5, 60.0, -6.0, -0.1)
    out["trench"] = _write(d / "trench.obj", vt, tris)
    # a retaining wall turned 90 degrees out along the approach at one jamb only
    vt, tris = [], []
    _headwall(vt, tris, 8.0)
    _slab(vt, tris, 8.0, 9.0, 0.5, 60.0, -6.0, -0.1)
    out["bent"] = _write(d / "bent.obj", vt, tris)
    return out


def _pins(objs, law, name):
    tunnel = OsmWay(-7, "big_roads", ((0.0, 0.6), (0.0, 300.0)), False, _T)
    airport = _airport(objs, law, [(name, (0.0, 0.0), 0.0, 0.0, "OBJECT")], (tunnel,))
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    trenches, _notes = read_trench_objects(objects, cache, law, [tunnel])
    pins = mouth_portals(trenches, objects, cache, law, [tunnel], airport.dem.z)
    return airport, cache, objects, trenches, pins


def test_a_sub_lane_opening_is_read_jamb_to_jamb(objs, law):
    airport, _c, _o, _t, pins = _pins(objs, law, "face")
    assert len(pins) == 1
    p = pins[0]
    lane = float(law.tables.structures.tunnel.lane_width_m)
    assert p.opening_misread
    # the face stands full height from -15 to +15: jamb to jamb, never 0.4 m
    assert p.opening_m >= lane
    assert p.opening_m == pytest.approx(30.0, abs=1.0)
    # walled, its zero on the ground its walls retain, its floor that less 6
    tol = float(law.tables.structures.tunnel.object.bore_end_tolerance_m)
    ground = _ground_max(airport.dem.z, p.end_xy, 2.0 * tol)
    assert p.bottom_y == pytest.approx(-6.0, abs=0.01)
    assert p.floor_z == pytest.approx(ground - 6.0, abs=0.01)


def test_no_sub_lane_slot_ever(objs, law):
    _a, _c, _o, _t, pins = _pins(objs, law, "narrow")
    # a face 2 m wide reads under a lane jamb to jamb too: no opening at all
    assert len(pins) == 1 and pins[0].opening_misread
    assert pins[0].opening_m == 0.0 and pins[0].opening_xy == ()


def test_a_misread_walled_trench_is_cut_to_its_walls(objs, law):
    airport, cache, objects, trenches, pins = _pins(objs, law, "trench")
    misread = {p.object_id for p in pins if p.opening_misread}
    assert misread == {"dsf:obj0"}
    floors, notes = walled_trench_floors(trenches, objects, cache, law, misread, airport.dem.z)
    assert len(floors) == 1, notes
    f = floors[0]
    # the floor between the walls, at the walls' feet
    assert 14.0 * 50.0 < f.footprint.area < 14.0 * 61.0
    assert f.floor_z == pytest.approx(f.zero_z - 6.0, abs=0.01)
    assert f.clearance_m == 0.0 and f.seats[0][0] == "dsf:obj0"
    # not misread: not read here (the mapped-mouth readers own it)
    assert walled_trench_floors(trenches, objects, cache, law, set(), airport.dem.z)[0] == []


def test_a_single_retaining_wall_is_no_trench(objs, law):
    airport, cache, objects, trenches, pins = _pins(objs, law, "bent")
    misread = {p.object_id for p in pins if p.opening_misread}
    floors, _notes = walled_trench_floors(trenches, objects, cache, law, misread, airport.dem.z)
    assert floors == []
