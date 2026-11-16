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
from auto_patch_v2.airport.trench_objects import (_cover_over, _ground_max, mouth_portals,
                                                  read_trench_objects)
from auto_patch_v2.airport.walled_trench import walled_trench_floors
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import read_objects
from test_tunnel_objects import _airport, _slab, _write

_T = {"highway": "primary", "lanes": "2", "tunnel": "yes", "layer": "-1"}


def _headwall(vt, tris, half: float, top: float = 1.0, seam: float = 0.2) -> None:
    """A full-height face across the bore at z = 0 (y -6 .. ``top``), authored
    in three pieces whose seams stand ``seam`` either side of the bore line:
    its foot breaks there, so the gap reader reads ``2 * seam``."""
    for x0, x1 in ((-half, -seam), (-seam, seam), (seam, half)):
        _slab(vt, tris, x0, x1, -0.5, 0.5, -6.0, top)


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
    # #2099 F2 P0: a lid face (+0.4) its own read walls, a 1.2 m slot
    vt, tris = [], []
    _headwall(vt, tris, 15.0, top=0.4, seam=0.6)
    out["lid"] = _write(d / "lid.obj", vt, tris)
    # a face its own read does NOT wall: a floor plate in the bore (y -6.2 ..
    # -6.0, seams at the bore line) outweighs the headwall's top
    vt, tris = [], []
    _headwall(vt, tris, 15.0)
    for x0, x1 in ((-15.0, -0.2), (-0.2, 0.2), (0.2, 15.0)):
        _slab(vt, tris, x0, x1, 0.5, 9.0, -6.2, -6.0)
    out["floored"] = _write(d / "floored.obj", vt, tris)
    # T2 (#2099 F2 P1a): the same face with a parapet plate offset to its back
    for x0, x1 in ((-15.0, -0.2), (-0.2, 0.2), (0.2, 15.0)):
        _slab(vt, tris, x0, x1, -2.5, -0.5, 2.0, 2.2)
    out["parapet"] = _write(d / "parapet.obj", vt, tris)
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
    airport, _c, objects, _t, pins = _pins(objs, law, "face")
    assert len(pins) == 1
    p = pins[0]
    lane = float(law.tables.structures.tunnel.lane_width_m)
    assert p.opening_misread
    # the face stands full height from -15 to +15: jamb to jamb, never 0.4 m
    assert p.opening_m >= lane
    assert p.opening_m == pytest.approx(30.0, abs=1.0)
    # #2099 F2 P0: its own read walls it (top +1 over bottom -6): it keeps
    # that read's seat -- floor on its top's cover, never the re-read's
    assert not p.wall_reseat
    assert p.bottom_y == pytest.approx(-6.0, abs=0.01)
    cover = _cover_over(p.top_plan, airport.dem.z)
    assert p.floor_z == pytest.approx(cover - 7.0, abs=0.01)


def test_a_face_its_own_read_walls_keeps_its_seat(objs, law):
    """T1 (#2099 F2 P0): a lid face (+0.4) with a 1.2 m slot: the opening
    is re-read jamb to jamb, its floor, top and plan stay its own read's."""
    airport, _c, _o, _t, pins = _pins(objs, law, "lid")
    p = pins[0]
    assert p.opening_misread and not p.wall_reseat
    assert p.opening_m == pytest.approx(30.0, abs=1.0)
    cover = _cover_over(p.top_plan, airport.dem.z)
    assert p.face_top_z == pytest.approx(cover)
    assert p.floor_z == pytest.approx(cover - 6.4, abs=0.01)
    assert p.top_plan.area == pytest.approx(30.0, abs=1.0)


def test_a_face_its_own_read_does_not_wall_is_reseated(objs, law):
    """T1 (#2099 F2 P0): a face whose own read is a floor plate (no wall's
    height) is walled by the re-read, its zero on the ground its walls
    retain, and says so (``wall_reseat``)."""
    airport, _c, _o, _t, pins = _pins(objs, law, "floored")
    p = pins[0]
    assert p.opening_misread and p.wall_reseat
    tol = float(law.tables.structures.tunnel.object.bore_end_tolerance_m)
    ground = _ground_max(airport.dem.z, p.end_xy, 2.0 * tol)
    assert p.floor_z - p.bottom_y == pytest.approx(ground, abs=0.01)


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


def test_the_plan_of_a_reseated_face_is_its_wall(objs, law):
    """T2 (#2099 F2 P1a): a face walled by the re-read publishes its WALL as
    its plan (its solids within the face reach), never only the plates at
    its top: a parapet plate offset to its back leaves the wall's front in
    the plan, so the mouth stands at the wall's front."""
    from shapely.geometry import Point
    _a, _c, _o, _t, pins = _pins(objs, law, "parapet")
    p = pins[0]
    assert p.wall_reseat and p.face_plan is not None
    # both faces of the 1 m headwall (authored z -0.5 .. +0.5) are in it
    for y in (-0.45, 0.0, 0.45):
        assert p.face_plan.buffer(0.01).contains(Point(5.0, y))
