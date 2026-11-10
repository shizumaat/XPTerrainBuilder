"""#1949 (OMDB ``tunner_5_1``): a roofed portal whose row reads its zero off
the road its roof states (an AGL row off a DEM bump at its anchor) is moved
onto that road with its co-placed rows, and its own floor is the cut
(``airport/portal_floor``); a floorless portal or one on its road is left
alone."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport.portal_floor import read_portal_floors
from auto_patch_v2.airport.portal_objects import Portal
from test_portal_objects1343 import LAW, THICK, _box, _portal, _write


def _at(path, oid, kind="OBJECT_AGL"):
    return types.SimpleNamespace(id=oid, path=f"objects/{oid}.obj", resolved=path,
                                 xy=(0.0, 0.0), heading_deg=0.0, kind=kind, anchor_z=104.0,
                                 agl_m=-4.8, plan_bbox=None)


def _pin(oid, zero):
    return Portal(oid, f"objects/{oid}.obj", (0.0, 0.5), -756, 6.0, 280.0, (0.0, 0.0),
                  opening_m=14.0, zero_z=zero)


def _read(objs, pins, ground=100.0):
    flat = lambda xs, ys: np.full(len(np.atleast_1d(xs)), float(ground))  # noqa: E731
    return read_portal_floors(pins, objs, O.ResourceCache(THICK), LAW, flat)


def test_a_portal_off_its_road_is_seated_on_it_and_its_floor_is_the_cut(tmp_path):
    """Two walls and a roof over a road slab (y 0 .. 0.2), the row reading
    its zero 5.2 m over the road its roof states: the frame (with its
    co-placed light) seated on that road, the slab and the walls' feet the
    cut, never the roof."""
    o = _at(_write(tmp_path / "tunnel.obj", [_box(-7.0, 0.0, 0.5, 20.0, 6.0),
                                             _box(6.5, 0.0, 0.5, 20.0, 6.0),
                                             _box(-7.0, 0.0, 14.0, 20.0, 0.3, y0=5.7),
                                             _box(-6.5, 0.0, 13.0, 20.0, 0.2)]), "dsf:obj1")
    light = types.SimpleNamespace(id="dsf:obj2", path="objects/light.obj", resolved=None,
                                  xy=(0.0, 0.0), heading_deg=0.0)
    floors, notes = _read([o, light], [_pin("dsf:obj1", 99.2)])
    assert len(floors) == 1, notes
    f = floors[0]
    assert abs(f.zero_z - 94.0) < 1e-6             # ground 100 less its roof top 6.0
    assert {pid for pid, _r, _z in f.seats} == {"dsf:obj1", "dsf:obj2"}
    assert abs(f.floor_z - 94.0) < 0.05 and float(f.faces[:, :, 2].max()) < 94.5
    assert abs(f.footprint.area - 280.0) < 5.0 and "is the cut" in notes[0]


def test_a_portal_on_its_road_or_with_no_floor_is_left_alone(tmp_path):
    o = _at(_portal(tmp_path), "dsf:obj1")
    floors, notes = _read([o], [_pin("dsf:obj1", 99.2)])
    assert floors == [] and "no floor of a plate's worth" in notes[0]
    floors, notes = _read([o], [_pin("dsf:obj1", 94.5)])
    assert floors == [] and notes == []
