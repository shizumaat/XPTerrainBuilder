"""T7 (#2099 F2 P5, spec ``docs/specs/2099-F2.md`` §6/§9): a hung wedge wall
with stage-1 airside behind its upper face gets ONE plate entry at its top
y on those airside stations; a level-foot hung wall, a wall with airside
on both faces, and a row another rule seats get none."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import hung_wall_seat as H
from auto_patch_v2.airport import wall_class, wall_sheets, wall_top
from shapely.geometry import box

# frame: the wall is a 40 m x 0.8 m strip along x at y in [0, 0.8]
WALL = box(0.0, 0.0, 40.0, 0.8)


def _ring_ll(poly):
    # frame entry is identity (to_xy(lon, lat) = (lon, lat)): rings are (lat, lon)
    return [(y, x) for x, y in list(poly.exterior.coords)[:-1]]


def _airport(member_ids=("w",)):
    part = types.SimpleNamespace(rings=[_ring_ll(WALL)], base_y=-7.4, height_m=7.5,
                                 line=False, feet=[(0, 0)], comp=0)
    members = [types.SimpleNamespace(id=i, parts=[part], resource="wall.obj",
                                     origin=(0.0, 0.0)) for i in member_ids]
    unit = types.SimpleNamespace(members=members, anchor=(0.0, 0.0))
    frame = types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat)))
    return types.SimpleNamespace(partition=types.SimpleNamespace(units=[unit]),
                                 frame=frame, retaining_walls=())


LAW = types.SimpleNamespace(tables=types.SimpleNamespace(structures=types.SimpleNamespace(
    tunnel=types.SimpleNamespace(object=types.SimpleNamespace(
        wall_face_max_thickness_m=2.0, wall_sample_m=2.0, entrance_airside_reach_m=1.5,
        plate_bin_m=0.5, shell_floor_min_m=2.0)))))


CFG = types.SimpleNamespace(retaining_wall_min_height_m=2.0, retaining_wall_min_length_m=10.0)


@pytest.fixture
def wedge(monkeypatch):
    """Stubs: gate G passes; the top level at +0.03..+0.1; the foot
    ``state["foot"]`` (a wedge by default); airside where
    ``state["airside"]`` lies."""
    state = {"foot": (-7.4, -0.5), "airside": box(0.0, 0.8, 40.0, 30.0)}
    monkeypatch.setattr(wall_sheets, "hung_wall", lambda *a, **k: True)
    monkeypatch.setattr(wall_class, "_seat_z", lambda *a, **k: 170.0)
    monkeypatch.setattr(wall_top, "top_profile",
                        lambda comp, g, f, to_xy, cache=None:
                        ((0.0, 0.08), (20.0, 0.1), (40.0, 0.03)))
    monkeypatch.setattr(wall_top, "foot_profile",
                        lambda comp, g, f, to_xy, cache=None: ((0.0, state["foot"][0]),
                                                               (40.0, state["foot"][1])))

    return state


def _run(state, ap=None, taken=frozenset()):
    return H.hung_wedge_plates(ap or _airport(), [state["airside"]], LAW, CFG, None, set(taken))


def test_wedge_with_airside_behind_upper_face_gets_one_plate(wedge):
    got = _run(wedge)
    assert len(got) == 1
    w = got[0]
    assert w.oid == "w" and w.top_y == pytest.approx(0.1)
    assert w.share == pytest.approx(1.0) and w.other == 0.0
    assert w.foot_range == pytest.approx(6.9)
    # the stations stand entrance_airside_reach_m behind the upper face
    assert all(y == pytest.approx(0.8 + 1.5) for _x, y in w.stations)
    assert len(w.stations) == 20


def test_level_foot_hung_wall_gets_none(wedge):
    wedge["foot"] = (-7.4, -7.0)
    assert _run(wedge) == []


def test_airside_on_both_faces_gets_none(wedge):
    wedge["airside"] = box(0.0, -30.0, 40.0, 30.0)
    assert _run(wedge) == []


def test_row_seated_elsewhere_gets_none(wedge):
    assert _run(wedge, taken={"w"}) == []


def test_retaining_wall_of_record_gets_none(wedge):
    ap = _airport()
    ap.retaining_walls = (types.SimpleNamespace(poly=WALL),)
    assert _run(wedge, ap) == []
