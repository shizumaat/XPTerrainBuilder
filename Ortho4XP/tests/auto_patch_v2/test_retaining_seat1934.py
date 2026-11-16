"""#1934 R3 (spec ``docs/specs/1934-R3.md`` §2; RULINGS 2026-11-16d): a
retaining wall whose retained face reaches its zero is plate-seated on its
UPPER ground -- one plate entry, stations a grid step outside its upper
face -- and the object stage reads that plate as its datum (never its
footing).  A wall retaining nothing, one too low to be two levels, one
another rule seats and one whose face reaches no stated height get none."""
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
        return 35.0 if y > 0.25 else 32.0


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


def test_buried_wall_is_seated_on_its_upper_ground():
    got = _run([_comp()])
    assert len(got) == 1
    w = got[0]
    assert w.oid == "w" and w.top_y == 0.0
    # every station a grid step outside the UPPER (north) face, 5 m apart
    assert all(y == pytest.approx(1.0) for _x, y in w.stations)
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
