"""#1934 R3 (spec ``docs/specs/1934-R3.md`` §2) as RULINGS 2026-11-20m
reads it: a retaining wall standing on its ground is plate-seated by its
FOOTING on the lowest ground beside its LOW face -- one plate entry,
stations a grid step outside its low face at its lowest level -- and the
object stage reads that plate as its datum.  A wall retaining nothing, one
too low to be two levels, one another rule seats and one whose face reaches
no stated height get none."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import retaining_seat as R
from auto_patch_v2.airport.wall_class import WallComponent
from shapely.geometry import box

# a 40 m x 0.5 m wall along x; the ground north of it (y > 0.5) is 3 m up
WALL = box(0.0, 0.0, 40.0, 0.5)


class _Dem:
    def z(self, x, y):
        if y > 0.25:
            return 35.0
        return 32.0 if x < 30.0 else 32.6          # the road climbs at its east end

    def z_many(self, xs, ys):
        import numpy as np
        return np.array([self.z(x, y) for x, y in zip(xs, ys, strict=True)], dtype=float)


def _airport():
    return types.SimpleNamespace(dem=_Dem(), partition=types.SimpleNamespace(units=[]),
                                 walled_plates=())


def _comp(oid="w", retains=True, retained=2.84, kept=0.0):
    m = types.SimpleNamespace(id=oid)
    return WallComponent((WALL,), 8.0, "Misc/Fence_Terminal_1.obj", 0, retains,
                         retained, 3.8, 35.0, (0.0, 0.0), m, kept, "dem" if retains else "")


CFG = types.SimpleNamespace(retaining_wall_clear_step_m=2.0)


def _run(comps, taken=frozenset()):
    return R.retaining_seats(_airport(), CFG, 0.5, 5.0, taken, comps=comps)


def test_a_wall_between_apron_and_road_is_seated_by_its_footing_on_the_road():
    """20m (KLAX ``Fence_Terminal_1``): the footing y -4.2 (top 3.8 less its
    8 m) on the stations outside the LOW (south) face, at its lowest level
    (the road's 32.0 part; the 32.6 end is within the clear step too)"""
    got = _run([_comp()])
    assert len(got) == 1
    w = got[0]
    assert w.oid == "w" and w.y == pytest.approx(-4.2)
    assert all(y == pytest.approx(-0.5) for _x, y in w.stations)
    xs = sorted(x for x, _y in w.stations)
    assert xs[0] == pytest.approx(0.0) and xs[-1] == pytest.approx(40.0)
    assert len(xs) == 9


@pytest.mark.parametrize("comp,taken", [
    (_comp(retains=False, retained=0.0), ()),       # retains nothing
    (_comp(retained=1.5), ()),                     # under the clear step: one level
    (_comp(kept=None), ()),                        # its face reaches no stated height
    (_comp(), ("w",)),                             # another rule seats it
])
def test_no_seat(comp, taken):
    assert _run([comp], frozenset(taken)) == ()


def test_object_stage_reads_the_plate_as_the_datum():
    """the member's datum is the plate (its y on the median station's
    ground), never its footing: the generic rule would stand y -4.2 on the
    surface under its plan"""
    m = types.SimpleNamespace(plate_y=0.0, plate_kind=R.RETAINING_PLATE,
                              plate_stations=((1.0, 0.0), (2.0, 0.0), (3.0, 0.0)))
    d = AR.datum_of(m)
    assert d is not None and d.y == 0.0 and len(d.stations) == 3

    def surface(la, lo):
        return 35.0 + 0.1 * la

    geom = AR.BodyGeometry(((0.0, 0.0, -4.2, ((0.0, 0.0, -4.2), (0.0, 1.0, -4.2))),),
                           0.0, 0.0)
    a = AR.anchor_for(AR.PLATE_ONLY, geom, surface, datum=d)
    assert a.y_zero == 0.0 and a.lat == 2.0
    assert a.surface_z == pytest.approx(35.2)


def test_the_retaining_plate_leads_its_unit_and_group():
    """the §16g unit and the connected group ride the wall's plate datum
    (``open_frame_seat.LEAD_PLATES``), as a walled plate's: the median of
    the surface at its stations less its y -- not its footing's ground"""
    from auto_patch_v2.airport import open_frame_seat as OF
    m = types.SimpleNamespace(plate_y=0.0, plate_kind=R.RETAINING_PLATE,
                              plate_stations=((1.0, 0.0), (2.0, 0.0), (3.0, 0.0)))

    def surface(la, lo):
        return 35.0 + 0.1 * la
    assert OF.walled_unit_zero([m], surface) == pytest.approx(35.2)
    body = types.SimpleNamespace(anchor=types.SimpleNamespace(surface_z=34.5, y_zero=-4.2,
                                                              datum=False))
    rec = types.SimpleNamespace(bodies=[body])
    assert OF.walled_lead(rec, m, surface) == pytest.approx(35.2)
    assert OF.walled_lead(rec, m) is None
    other = types.SimpleNamespace(plate_y=0.0, plate_kind="edge", plate_stations=m.plate_stations)
    assert OF.walled_lead(rec, other, surface) is None


def test_the_footing_stands_at_the_lowest_level_within_the_ground_bar():
    """20m "at the lowest road level": with the 0.5 m ground bar only the
    stations on the road's 32.0 part remain (its 32.6 end is another level)"""
    (w,) = R.retaining_seats(_airport(), CFG, 0.5, 5.0, comps=[_comp()], level_m=0.5)
    assert w.stations and all(x < 30.0 for x, _y in w.stations)
