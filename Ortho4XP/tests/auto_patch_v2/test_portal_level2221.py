"""#2221 (KBUF ``Road_Tunnel.obj``, owner RULINGS 2026-11-21d): a floorless
roofed portal whose row stands off the road its roof states is seated on
its mouth's floor, and the floor stays level under it to its footprint's
outer end (``planar/portal_level``)."""
from __future__ import annotations

from auto_patch_v2.airport.portal_objects import Portal
from auto_patch_v2.planar.portal_level import level_to_s, off_road
from shapely.geometry import LineString, box
from test_portal_objects1343 import LAW


def _pin(zero, floor_z=None, opening=14.0, foot=None, at_grade=True):
    return Portal("dsf:obj1", "objects/t.obj", (0.0, 0.0), -1, 6.64, 219.0, (0.0, 0.0),
                  floor_z=floor_z, opening_m=opening, zero_z=zero, footprint=foot,
                  at_grade=at_grade)


def test_a_row_off_its_road_is_seated_and_one_on_it_is_not():
    assert off_road(_pin(218.36), 211.94, LAW)              # AGL 0 on the uncut DEM
    assert not off_road(_pin(212.10), 211.94, LAW)          # on its road (cover_flush_m)
    assert not off_road(_pin(218.36, floor_z=211.0), 211.94, LAW)   # a stated floor
    assert not off_road(_pin(218.36, opening=0.0), 211.94, LAW)     # no opening read
    assert not off_road(None, 211.94, LAW)
    # #2225: a floorless portal under the author's ground is seated alike
    # (RJTT ``tunnel6.obj``: its walls stand on the road its roof states)
    assert off_road(_pin(218.36, at_grade=False), 211.94, LAW)
    assert not off_road(_pin(212.10, at_grade=False), 211.94, LAW)


def test_an_at_grade_mouth_states_no_floor_of_its_own(tmp_path):
    """Its row reads the uncut ground and the faces under its roof are its
    arch's soffit: ``airport/portal_floor`` reads no floor from it."""
    import dataclasses

    from test_portal_floor1949 import _at, _box, _read, _write
    from test_portal_floor1949 import _pin as _floor_pin
    o = _at(_write(tmp_path / "tunnel.obj", [_box(-7.0, 0.0, 0.5, 20.0, 6.0),
                                             _box(6.5, 0.0, 0.5, 20.0, 6.0),
                                             _box(-7.0, 0.0, 14.0, 20.0, 0.3, y0=5.7),
                                             _box(-6.5, 0.0, 13.0, 20.0, 0.2)]), "dsf:obj1")
    assert len(_read([o], [_floor_pin("dsf:obj1", 99.2)])[0]) == 1
    pin = dataclasses.replace(_floor_pin("dsf:obj1", 99.2), at_grade=True)
    assert _read([o], [pin]) == ([], [])


def test_the_floor_stays_level_to_the_footprint_s_outer_end():
    axis = LineString([(0.0, 0.0), (0.0, 100.0)])           # mouth outward along +y
    assert abs(level_to_s(_pin(218.36, foot=box(-7.0, -18.0, 7.0, 19.6)), axis) - 19.6) < 1e-9
    assert level_to_s(_pin(218.36), axis) == 0.0
