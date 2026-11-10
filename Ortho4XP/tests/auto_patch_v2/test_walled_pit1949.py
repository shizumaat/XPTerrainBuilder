"""#1949 (owner 2026-11-10T14:33Z, OMDB): a pack that hangs a whole sunken
area off one shared datum authors the floor AT the zero and the ground at the
top of its retaining walls.  The walls' rim is the pit's ground: the floor is
cut ``rim - floor`` under it, and a frame whose rim stands off the ground
around it is moved so the rim lands there (``airport/walled_pit``)."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import object_floor as OF
from test_hanging_objects1298 import LAW, THICK, _box, _write


def _flat(z):
    return lambda xs, ys: np.full(len(np.atleast_1d(xs)), float(z))


def _at(path, oid, zero=100.0):
    return types.SimpleNamespace(id=oid, path=f"objects/{oid}.obj", resolved=path, xy=(0.0, 0.0),
                                 heading_deg=0.0, kind="OBJECT", anchor_z=zero, agl_m=0.0,
                                 plan_bbox=None)


def _pit(tmp_path, wall_h=12.0, roof=False):
    """A 60 x 40 m floor plate at y 0 .. 0.2 and, co-placed, four walls
    standing on its edges from y 0 to ``wall_h`` (and a roof over it)."""
    floor = _write(tmp_path / "floor.obj", [_box(0.0, 0.0, 60.0, 40.0, 0.2)])
    walls = [_box(-0.5, 0.0, 0.5, 40.0, wall_h), _box(60.0, 0.0, 0.5, 40.0, wall_h),
             _box(0.0, -0.5, 60.0, 0.5, wall_h), _box(0.0, 40.0, 60.0, 0.5, wall_h)]
    if roof:
        walls.append(_box(-0.5, -0.5, 61.0, 41.0, 0.3, y0=wall_h))
    return [_at(_write(tmp_path / "walls.obj", walls), "dsf:obj1"),
            _at(floor, "dsf:obj2")]


def _read(objs, ground):
    return OF.read_object_floors(objs, O.ResourceCache(THICK), LAW, {}, ground=_flat(ground))


def test_a_frame_standing_proud_of_the_ground_lands_its_rim_on_it(tmp_path):
    """OMDB: the walls' rim 12 m over the zero, the ground 10 m UNDER the
    zero — the frame moves 22 m down and the floor is cut 12 m under the
    ground."""
    floors, notes = _read(_pit(tmp_path), 90.0)
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes
    f = floors[0]
    assert abs(f.lift + 22.0) < 0.05 and f.covers == ("dsf:obj1",)
    assert abs(f.floor_z - 78.0) < 0.05 and abs(f.rim_z - 90.0) < 0.05
    assert {pid: round(z, 2) for pid, _r, z in f.seats} == {"dsf:obj2": 78.0, "dsf:obj1": 78.0}
    recs = OF.seat_records(floors)
    assert {r["id"]: r["elevation"] for r in recs} == {"dsf:obj2": 78.0, "dsf:obj1": 78.0}
    assert abs(f.footprint.area - 2400.0) < 5.0


def test_a_rim_at_the_ground_keeps_the_authored_seat(tmp_path):
    """The rim 1 m over the ground (within ``authored_crest_max_m``): no
    lift, the floor cut at its authored level 11 m under the ground."""
    floors, notes = _read(_pit(tmp_path), 111.0)
    assert len(floors) == 1 and floors[0].lift == 0.0, notes
    assert abs(floors[0].floor_z - 100.0) < 0.05


def test_low_walls_round_a_plate_are_no_pit(tmp_path):
    """A kerb or a fence 1.5 m high round a plate is no retaining wall."""
    floors, notes = _read(_pit(tmp_path, wall_h=1.5), 90.0)
    assert floors == [], notes


def test_a_floor_under_its_own_roof_is_a_building(tmp_path):
    """Walls round a floor with a roof over it: a building's (the basin
    basement test), never a pit."""
    floors, notes = _read(_pit(tmp_path, roof=True), 90.0)
    assert floors == [] and any("a building, not a pit" in n for n in notes), notes


def test_the_frames_placements_in_the_pit_move_with_it_and_the_rest_keep_their_seats(tmp_path):
    """The pit's lamps (a lights-only object over it) move with the frame;
    a co-placed building far from it keeps its own seat."""
    lamps = tmp_path / "lamps.obj"
    lamps.write_text("I\n800\nOBJ\n\nPOINT_COUNTS 0 0 0 0\n\n"
                     "LIGHT_PARAM full_custom_halo_night 10.0 9.0 10.0 1 1 1 1 100 0 -1 0 1\n"
                     "LIGHT_PARAM full_custom_halo_night 50.0 9.0 30.0 1 1 1 1 100 0 -1 0 1\n",
                     encoding="utf-8", newline="\n")
    far = _write(tmp_path / "far.obj", [_box(500.0, 500.0, 30.0, 30.0, 8.0)])
    objs = _pit(tmp_path) + [_at(str(lamps), "dsf:obj3"), _at(far, "dsf:obj4")]
    floors, notes = _read(objs, 90.0)
    assert len(floors) == 1, notes
    assert {pid for pid, _r, _z in floors[0].seats} == {"dsf:obj1", "dsf:obj2", "dsf:obj3"}


def test_a_pit_floor_is_no_author_ground_for_the_floors_read_after_it():
    """#1949 (5): the pit's floor plate stands under its rim — dropped from
    the author's ground (``AuthorGround.without``), it is never the ground
    another floor (OMDB ``duong_ray_FACE``) is read against."""
    from auto_patch_v2.geom.author_ground import AuthorGround
    tri = np.array([[[0.0, 0.0, 1.0], [10.0, 0.0, 1.0], [0.0, 10.0, 1.0]]])
    ag = AuthorGround(np.concatenate([tri, tri + [0.0, 0.0, 5.0]]), ["pit", "plate"])
    assert abs(ag.at([1.0], [1.0])[0] - 1.0) < 1e-9
    rest = ag.without({"pit"})
    assert abs(rest.at([1.0], [1.0])[0] - 6.0) < 1e-9 and list(rest.owners) == ["plate"]
    assert ag.without(set()) is ag
