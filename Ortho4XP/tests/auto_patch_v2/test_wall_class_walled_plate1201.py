"""#1201 (owner sim read 2026-11-04, KSEA 16C): a RUNWAY-END WALLED PLATE's
own wall components carry no "as it sits" seat (``wall_class._seat_z``):
the plate's top is seated on the solved safety area (RULINGS 2026-10-27u)
and its bottom sinks, so the wall-top / wall-foot readings
(``airport/wall_top``) read nothing off its origin and no wall slope holds
the safety area's end up to a top read on the runway."""
from __future__ import annotations

import types

import numpy as np

from auto_patch_v2.airport import dem as dem_mod
from auto_patch_v2.airport import wall_class
from auto_patch_v2.airport.wall_top import top_profile


def _airport(plates=()):
    return types.SimpleNamespace(dem=object(), walled_plates=tuple(plates))


def _member(mid):
    return types.SimpleNamespace(id=mid, zero_y=0.0, origin=(47.0, -122.0))


def _unit():
    return types.SimpleNamespace(agl_m=0.0, anchor=None)


def _flat_dem(monkeypatch, z=131.1):
    monkeypatch.setattr(dem_mod, "dem_z_many", lambda _d, xs, _ys: np.full(len(xs), z))


def test_an_ordinary_wall_sits_on_the_dem_at_its_origin(monkeypatch):
    _flat_dem(monkeypatch)
    z = wall_class._seat_z(_airport(), _unit(), _member("dsf:obj1"), lambda lo, la: (0.0, 0.0))
    assert z == 131.1


def test_a_walled_plate_member_has_no_seat_as_it_sits(monkeypatch):
    _flat_dem(monkeypatch)
    plate = types.SimpleNamespace(ids=("dsf:obj1", "dsf:obj2"))
    ap = _airport([plate])
    to_xy = lambda lo, la: (0.0, 0.0)                       # noqa: E731
    assert wall_class._seat_z(ap, _unit(), _member("dsf:obj2"), to_xy) is None
    # another placement beside it keeps its seat
    assert wall_class._seat_z(ap, _unit(), _member("dsf:obj9"), to_xy) == 131.1


def test_no_seat_reads_no_top_so_no_slope_holds_the_safety_area():
    comp = types.SimpleNamespace(seat_z=None, member=object(), origin=(0.0, 0.0))
    from shapely.geometry import LineString, Polygon
    piece = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    assert top_profile(comp, piece, LineString([(0, 1), (10, 1)]), lambda lo, la: (lo, la)) is None
