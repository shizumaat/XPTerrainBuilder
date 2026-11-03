"""#1726 (owner KBWI sim read 2026-11-03T05:25:51Z, option A): a building's
slender SUPPORT members (poles, piers under it) found no storey -- a lower
storey is read on the unit's other walls, and its plane is that of all the
walled feet, the supports standing on it included (``planar/low_level.
feet_levels``, ``geom/foot_planes.is_support``)."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.geom import foot_planes as SM
from auto_patch_v2.law import Law
from auto_patch_v2.planar import low_level as LL

LAW = Law.load()
XY = lambda lon, lat: (lon, lat)  # noqa: E731


def _part(w_m: float, h_m: float, y: float, n: int = 4, lat=39.18, lon=-76.67):
    d = w_m / 111_320.0
    return types.SimpleNamespace(line=False, height_m=h_m, box=(lat, lon, lat + d, lon + d * 1.3),
                                 feet=((lat, lon, y),) * n, base_y=y)


def test_a_pole_is_a_support_and_a_wall_is_not():
    assert SM.is_support(_part(0.3, 11.0, -6.15), LAW)
    assert SM.is_support(_part(1.9, 9.2, -3.46), LAW)
    assert not SM.is_support(_part(20.0, 9.0, -6.15), LAW)
    assert not SM.is_support(_part(0.3, 1.0, -6.15), LAW)      # not walled


def test_walled_feet_without_the_supports():
    parts = [(_part(0.3, 11.0, -6.15), (0, 0)), (_part(20.0, 9.0, -0.4), (0, 0))]
    assert sorted(LL.walled_feet(parts, LAW, XY)[1]) == [-6.15] * 4 + [-0.4] * 4
    assert LL.walled_feet(parts, LAW, XY, supports=False)[1] == [-0.4] * 4


def _levels(monkeypatch, parts):
    Y = np.asarray(LL.walled_feet(parts, LAW, XY)[1])
    monkeypatch.setattr(LL, "stand_floor", lambda *a: (0.0, None, Y, None))
    return LL.feet_levels(parts, None, [], LAW, XY)


def test_poles_alone_found_no_lower_storey(monkeypatch):
    """KBWI ``BWI_Terminal_new``: walls at the apron, poles 6.15 m down."""
    parts = [(_part(30.0, 9.0, 0.0, 200), (0, 0)), (_part(0.3, 11.0, -6.15, 120), (0, 0))]
    assert _levels(monkeypatch, parts) == (0.0, None)


def test_walls_witness_the_storey_and_its_columns_keep_its_plane(monkeypatch):
    """KMCI ``building26/b1``: walls read the lower storey, its columns
    hold the densest plane (-8.2), which stays the storey's plane."""
    parts = [(_part(30.0, 9.0, 0.0, 200), (0, 0)), (_part(30.0, 9.0, -10.5, 60), (0, 0)),
             (_part(0.5, 6.0, -8.2, 300), (0, 0))]
    assert _levels(monkeypatch, parts) == (0.0, -8.2)
