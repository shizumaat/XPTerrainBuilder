"""Twin for #1737 (owner 2026-11-02 ENGM: the tunnel-mouth object "is
floating, not seated with top flush to apron area"; ``constraints/
airside_top``): an ENTRANCE face whose top plan airside pavement abuts is
seated on that pavement's SOLVED level -- the floor that level less the
face's height, the zero that level less its top y -- never on the DEM max
over its top.  Synthetic stubs; law values read from the tables."""
from __future__ import annotations

import dataclasses as _dc
import types

import pytest
from auto_patch_v2.airport import terrain_shaped as TS
from auto_patch_v2.airport.portal_objects import Portal
from auto_patch_v2.constraints import airside_top as AT
from auto_patch_v2.law import Law
from auto_patch_v2.planar.entrance_skirt import entrance_top
from shapely.geometry import box


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


#: a lid's top plan, 40 x 20 m; the face 0.4 m over its zero, 8.5 m under it
_PLAN = box(0.0, 0.0, 40.0, 20.0)


def _pin(cover: float = 211.6) -> Portal:
    top, bottom = 0.4, -8.5
    zero = cover - top
    return Portal("dsf:obj7", "objects/portal.obj", (10.0, 0.0), -9, 8.9, 0.0, (10.0, 0.0),
                  floor_z=zero + bottom, bottom_y=bottom, face_top_z=cover, top_plan=_PLAN)


def test_the_top_is_read_back_from_the_seat_its_cover_set():
    rings, top_y, height = entrance_top(_pin())
    assert top_y == pytest.approx(0.4) and height == pytest.approx(8.9)
    assert len(rings) == 1 and len(rings[0]) == 5
    assert entrance_top(_dc.replace(_pin(), top_plan=None)) == ()


def _planar(xys, tops):
    verts = [types.SimpleNamespace(xy=xy) for xy in xys]
    structures = [types.SimpleNamespace(id=f"tunnel:{k}", entrance_top=t)
                  for k, t in enumerate(tops)]
    return types.SimpleNamespace(vertices=verts, structures=structures)


def test_the_seat_is_the_airside_abutting_the_top(monkeypatch, law):
    """Airside vertices within the reach of the top plan are the seat (their
    mean); one farther out, and every groundside vertex, is not; a face no
    airside reaches has no seat."""
    reach = float(law.tables.structures.tunnel.object.entrance_airside_reach_m)
    xys = [(5.0, -0.3), (20.0, -0.5), (35.0, -reach + 0.1), (20.0, -reach - 2.0), (20.0, 25.0)]
    pm = _planar(xys, [entrance_top(_pin()), ()])
    monkeypatch.setattr("auto_patch_v2.model.platform.stage_air_vertices",
                        lambda planar, law: {0, 1, 2, 3})
    seats = AT.top_seats(pm, law)
    assert set(seats) == {"tunnel:0"}
    terms, height, top_y = seats["tunnel:0"]
    assert [v for v, _w in terms] == [0, 1, 2]
    assert sum(w for _v, w in terms) == pytest.approx(1.0)
    assert (height, top_y) == (pytest.approx(8.9), pytest.approx(0.4))
    assert AT.top_seat(seats, pm.structures[0]) == (terms, height)
    assert AT.top_seat(seats, pm.structures[1]) is None
    monkeypatch.setattr("auto_patch_v2.model.platform.stage_air_vertices",
                        lambda planar, law: {3, 4})
    assert AT.top_seats(pm, law) == {}


def test_the_zero_is_the_solved_airside_less_the_top(monkeypatch, law):
    """MEASURED ENGM (Ham3): the apron at the lid's edge solved 2.3-3.2 m
    under the DEM max the top was seated on -- the zero follows the apron."""
    xys = [(5.0, -0.3), (20.0, -0.5)]
    pm = _planar(xys, [entrance_top(_pin())])
    monkeypatch.setattr("auto_patch_v2.model.platform.stage_air_vertices",
                        lambda planar, law: {0, 1})
    seat = AT.top_seats(pm, law)["tunnel:0"]
    solved = {(5.0, -0.3): 208.5, (20.0, -0.5): 209.1}
    zero = AT._solved_zero(seat, pm, lambda x, y: solved.get((x, y)))
    assert zero == pytest.approx(208.8 - 0.4)
    assert AT._solved_zero(seat, pm, lambda x, y: None) is None


def test_the_surface_reader_finds_the_vertex_at_a_point():
    sv = [types.SimpleNamespace(ll=(60.0, 11.0), z=208.5),
          types.SimpleNamespace(ll=(60.1, 11.1), z=7.0)]
    z_at = AT._surface_z_at(types.SimpleNamespace(vertices=sv),
                           lambda lon, lat: (lon * 1000.0, lat * 1000.0))
    assert z_at(11000.0, 60000.0) == pytest.approx(208.5)
    assert z_at(11000.5, 60000.0) is None


def test_the_entrance_record_carries_the_solved_zero():
    tn = types.SimpleNamespace(id="tunnel:0", portal="dsf:obj7",
                               portal_seat=("objects/portal.obj", 211.2, (10.0, 0.0), 10.0))

    def to_ll(x, y):
        return (60.0, 11.0)
    base = TS.portal_seat_records([tn], to_ll)
    moved = TS.portal_seat_records([tn], to_ll, zeros={"tunnel:0": 208.4})
    assert base[0]["elevation"] == pytest.approx(211.2)
    assert moved[0]["elevation"] == pytest.approx(208.4)
    assert moved[0]["seat"] == base[0]["seat"] == TS.ENTRANCE_SEAT


def test_a_group_of_bores_opens_across_every_members_opening():
    """The second half of #1737: the ramp of four rail bores one face fronts
    grades to the face's full width -- the hull of the members' openings
    across the axis -- never to the first member's 1.2 m slot."""
    from auto_patch_v2.planar.mouth_opening import group_opening, opening_halves
    from shapely.geometry import LineString
    axis = LineString([(0.0, 0.0), (0.0, 100.0)])     # into the bore: north
    wide = _dc.replace(_pin(), opening_m=28.0, opening_xy=((-20.0, 0.0), (8.0, 0.0)))
    slot = _dc.replace(_pin(), opening_m=1.2, opening_xy=((8.2, 0.5), (9.4, 0.5)))
    width, edges = group_opening([slot, wide], axis)
    assert width == pytest.approx(29.4)
    assert opening_halves(axis, edges) == (pytest.approx(20.0), pytest.approx(9.4))
    assert group_opening([slot], LineString([(0.0, 0.0), (0.0, 1.0)]))[0] == pytest.approx(1.2)
    assert group_opening([], axis) == (0.0, ())
