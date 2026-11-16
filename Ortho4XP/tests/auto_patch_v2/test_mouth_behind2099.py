"""#2099 F2 P1b / P1c (twin T3): a taxiway a pinned ENTRANCE mouth's ring
meets only BEHIND the mouth line is no clause-1 hit -- no yield, it stays a
stop, and the cap is held short of it; a taxiway at the opening still
yields, and so does one too close for a cap of ``wall_gap_m``."""
from __future__ import annotations

import types

from auto_patch_v2.law import Law
from auto_patch_v2.planar import mouth_behind as MB
from auto_patch_v2.planar import structure_mouth as SM
from shapely.geometry import LineString, box

LAW = Law.for_airport("")
GAP = LAW.tables.structures.tunnel.wall_gap_m
AXIS = LineString([(0.0, 0.0), (0.0, -120.0)])         # the ramp runs south
GROUP = types.SimpleNamespace(mouth=(0.0, 0.0), inward=(0.0, 1.0))   # the bore north
RING = box(-5.0, -6.0, 5.0, 1.6)                       # cap 1.6 m behind the mouth line


def _pin(face, entrance=True):
    cells = [types.SimpleNamespace(kind="governed", role="stub", ref="pav1")]
    return SM._pinned(GROUP, AXIS, cells, [face], [], LAW, (), 3.5, 1.6, (), 0.5, (), RING,
                      entrance=entrance)


def test_a_taxiway_behind_the_mouth_line_is_no_yield_and_bounds_the_cap():
    got = _pin(box(-30.0, 1.3, 30.0, 40.0))
    assert isinstance(got, tuple) and len(got) == 8
    assert "pav1" in [r for _p, r in got[2]]              # it stays a stop
    behind = got[7]
    assert abs(behind.d - 1.3) < 1e-9 and behind.refs == ("pav1",)
    cap = MB.cap_bound(behind, LAW, GAP)
    assert cap is not None and GAP <= cap < 1.3


def test_the_ring_less_the_taxiway_keeps_its_area():
    face = box(-30.0, 1.3, 30.0, 40.0)
    behind = _pin(face)[7]
    cut = MB.clear_of(RING, behind.faces)
    assert cut.intersection(face).area == 0.0 and abs(face.area - face.difference(cut).area) < 1e-9


def test_a_taxiway_at_the_opening_yields_as_today():
    assert _pin(box(-30.0, -4.0, 30.0, 40.0)) == "pav1"


def test_a_taxiway_too_close_for_the_gap_leaves_the_yield():
    behind = _pin(box(-30.0, 0.8, 30.0, 40.0))[7]
    assert MB.cap_bound(behind, LAW, GAP) is None


def test_a_portal_that_is_no_entrance_face_yields_as_today():
    assert _pin(box(-30.0, 1.3, 30.0, 40.0), entrance=False) == "pav1"
