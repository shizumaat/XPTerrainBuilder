"""#1726 EXPERIMENT (owner 2026-11-02T22:33Z-22:37Z, awaiting his sim read):
a building group's slender SUPPORT members (poles, piers under it) found no
storey and, with ``[building_pad] support_lift`` on, the group is lifted so
their densest foot plane stands at grade (``geom/foot_planes``).  The
knob is OFF by default; off, the storey readers are unchanged."""
from __future__ import annotations

import dataclasses as _dc
import types

from auto_patch_v2.geom import foot_planes as SM
from auto_patch_v2.law import Law
from auto_patch_v2.planar import low_level as LL

LAW = Law.load()


def _law(on: bool):
    st = LAW.tables.structures
    bp = _dc.replace(st.building_pad, support_lift=on)
    return types.SimpleNamespace(tables=types.SimpleNamespace(
        structures=types.SimpleNamespace(building_pad=bp, placement=st.placement)))


def _part(w_m: float, h_m: float, y: float, lat=39.18, lon=-76.67):
    d = w_m / 111_320.0
    return types.SimpleNamespace(line=False, height_m=h_m, box=(lat, lon, lat + d, lon + d * 1.3),
                                 feet=((lat, lon, y),) * 4, base_y=y)


def test_the_knob_is_off_by_default():
    assert SM.support_lift_on(LAW) is False


def test_a_pole_is_a_support_and_a_wall_is_not():
    law = _law(True)
    assert SM.is_support(_part(0.3, 11.0, -6.15), law)
    assert SM.is_support(_part(1.9, 9.2, -3.46), law)
    assert not SM.is_support(_part(20.0, 9.0, -6.15), law)
    assert not SM.is_support(_part(0.3, 1.0, -6.15), law)      # not walled


def test_supports_found_no_storey_only_with_the_knob_on():
    parts = [(_part(0.3, 11.0, -6.15), (0, 0)), (_part(20.0, 9.0, -0.4), (0, 0))]
    xy = lambda lon, lat: (lon, lat)  # noqa: E731
    assert sorted(LL.walled_feet(parts, _law(False), xy)[1]) == [-6.15] * 4 + [-0.4] * 4
    assert LL.walled_feet(parts, _law(True), xy)[1] == [-0.4] * 4


def test_the_support_plane_is_the_densest_not_the_deepest():
    zs = [72.2] * 30 + [48.6] * 80 + [46.0] * 50
    z, n = SM.support_plane(zs, 1.0)
    assert (z, n) == (48.6, 80)
