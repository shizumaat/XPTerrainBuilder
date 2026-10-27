"""#1201 (owner RULINGS 2026-10-27t / 2026-10-27u): a runway-end WALLED PLATE
is recognised by geometry and position, the safety area ends at its inner
edge, its top is the seat's datum, and the ground under it never rises
through it.  Synthetic: one runway along +y, its north end at (0, 0); a plate
290-310 m past the end, a 20 m wall at its outer edge, the DEM stepping 15 m."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import walled_plate as W
from auto_patch_v2.airport.anchor_rule import datum_of
from auto_patch_v2.airport.obj8 import ObjGeometry, PlacedObject
from auto_patch_v2.constraints.walled_plate import RULING, under_plate_rows
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Band
from auto_patch_v2.model.end_area import end_area_lengths
from auto_patch_v2.model.walled_plate import WalledPlate
from shapely.geometry import Polygon


@pytest.fixture(scope="module")
def law():
    return Law.load()


def _runway():
    def end(n, xy):
        return types.SimpleNamespace(name=n, xy=xy, approach="visual")
    return types.SimpleNamespace(id="16/34",
                                 ends=(end("16", (0.0, 0.0)), end("34", (0.0, -3000.0))),
                                 code_number=4, code_letter="E", instrument=False, width_m=45.0)


class _Dem:
    """Upper ground falling 3 % past the end, ``step`` m lower past s = 318."""

    def __init__(self, step=15.0):
        self.step = step

    def z(self, x, y):
        return 100.0 - 0.03 * max(y, 0.0) - (self.step if y > 314.0 else 0.0)

    def z_many(self, xs, ys):
        return np.array([self.z(x, y) for x, y in zip(xs, ys, strict=True)])


def _plate_geometry(wall=True, half=100.0, s0=290.0, s1=310.0, h=20.0) -> ObjGeometry:
    """An OBJ8 placed at the origin (0, 0) heading 0: authored x east,
    z south, so the frame's north s is -z."""
    v = [(-half, 0.0, -s0), (half, 0.0, -s0), (half, 0.0, -s1), (-half, 0.0, -s1)]
    tris = [(0, 1, 2), (0, 2, 3)]
    if wall:
        v += [(-half, -h, -s1), (half, -h, -s1)]
        tris += [(3, 2, 5), (3, 5, 4)]
    vv = np.array(v, dtype=float)
    t = np.array(tris, dtype=np.int64)
    return ObjGeometry("p.obj", vv, t, np.zeros(len(t), dtype=np.int64),
                       np.zeros((0, 3), dtype=np.int64))


def _placed(xy=(0.0, 0.0), extent=None) -> PlacedObject:
    box = Polygon(extent or [(-100, 280), (100, 280), (100, 320), (-100, 320)])
    return PlacedObject("dsf:1", "objects/p.obj", "/pack/objects/p.obj", xy, 0.0, 0.0, "OBJECT",
                        100.0, None, box, None, None, None, None, origin_built=True,
                        deck_kind="candidate")


def _airport(dem=None, plates=()):
    return types.SimpleNamespace(runways=(_runway(),), dem=dem or _Dem(), walled_plates=plates)


class _Cache:
    def __init__(self, g):
        self.g = g

    def geometry(self, path):
        return self.g


def test_recognised_by_all_four_witnesses(law):
    out = W.mark(_airport(), [_placed()], _Cache(_plate_geometry()), law)
    p = out[0].walled_plate
    assert p is not None and p.end_name == "16" and p.end == 0
    assert p.inner_s == pytest.approx(290.0, abs=1.0)
    assert p.height_m == pytest.approx(20.0, abs=0.5)
    assert p.plate_y == pytest.approx(0.0)
    # out of the readings another law owns (27u replaces the 20s guard)
    assert out[0].origin_built is False and out[0].deck_kind == ""
    assert all(s[1] == pytest.approx(288.0, abs=1.0) for s in p.stations)


@pytest.mark.parametrize("why, kw", [
    ("no outer wall", dict(geometry=_plate_geometry(wall=False))),
    ("no lower ground at the foot", dict(dem=_Dem(step=0.0))),
    ("a step deeper than the wall: its foot would float", dict(dem=_Dem(step=30.0))),
    ("too narrow for the safety area", dict(geometry=_plate_geometry(half=30.0))),
])
def test_refused(law, why, kw):
    g = kw.get("geometry", _plate_geometry())
    out = W.mark(_airport(kw.get("dem")), [_placed()], _Cache(g), law)
    assert out[0].walled_plate is None, why
    assert out[0].origin_built is True


def test_off_the_axis_is_not_read(law):
    far = [(900, 280), (1100, 280), (1100, 320), (900, 320)]
    out = W.mark(_airport(), [_placed(xy=(1000.0, 0.0), extent=far)], _Cache(_plate_geometry()),
                 law)
    assert out[0].walled_plate is None


def _record(**kw) -> WalledPlate:
    base = dict(ids=("dsf:1",), runway="16/34", end=0, plate_y=-9.9, inner_s=290.0,
                stations=((0.0, 288.0),), inner=((-100.0, 290.0), (100.0, 290.0)),
                outer=((-100.0, 310.0), (100.0, 310.0)),
                footprint=((-100.0, 290.0), (100.0, 290.0), (100.0, 310.0), (-100.0, 310.0),
                           (-100.0, 290.0)),
                height_m=20.0, step_m=15.0, end_name="16")
    base.update(kw)
    return WalledPlate(**base)


def test_the_safety_area_ends_at_the_inner_edge(law):
    ap = types.SimpleNamespace(runways=(_runway(),), dem=None, walled_plates=(_record(),))
    lens = end_area_lengths(ap, law)["16/34"]
    assert lens[0] == pytest.approx(290.0)
    assert lens[1] > 290.0                  # the uncapped end keeps its length


def test_the_plate_is_the_seat_datum_at_any_height():
    m = types.SimpleNamespace(plate_y=-9.9, plate_kind="walled", plate_stations=((47.0, -122.0),),
                              deck_top_y=None, deck_kind="")
    d = datum_of(m)
    assert d is not None and d.y == pytest.approx(-9.9) and d.stations == ((47.0, -122.0),)
    # without the kind, a negative plate is a floor plate and reads no datum
    m.plate_kind = ""
    assert datum_of(m) is None


def _planar(points):
    """``points``: id -> (xy, roles); one face per role."""
    roles = sorted({r for _xy, rs in points.values() for r in rs})
    fid = {r: i for i, r in enumerate(roles)}
    faces = {i: types.SimpleNamespace(id=i, role=r) for r, i in fid.items()}
    verts = {k: types.SimpleNamespace(id=k, xy=xy, incident_faces=tuple(fid[r] for r in rs))
             for k, (xy, rs) in points.items()}
    return types.SimpleNamespace(vertices=verts, faces=faces)


def test_the_ground_under_the_plate_stays_below_it(law):
    pm = _planar({1: ((0.0, 300.0), ["graded_strip"]), 2: ((5.0, 300.0), ["service_road"]),
                  3: ((5.0, 330.0), ["service_road"]), 4: ((0.0, 290.5), ["service_road"])})
    rows = under_plate_rows(pm, law, _airport(plates=(_record(),)))
    # the road under the plate only: never the safety area's own vertex, never
    # a vertex on the inner edge or past the outer one
    assert [r.v for r in rows] == [2]
    r = rows[0]
    assert isinstance(r, Band) and r.lo is None and r.source.ruling == RULING
    assert r.hi == pytest.approx(_Dem().z(0.0, 288.0) - 0.05)


def test_the_wall_at_the_plate_is_declared_lawful_to_the_census():
    """27t: a terrace joint at the plate carries the emitter's flag, and the
    census's runway-strip wall ban (2026-08-01) exempts exactly it."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import check_grade
    at = {"points": [[290.0, -50.0], [290.0, 50.0]]}         # (lat, lon) = (y, x) here
    away = {"points": [[100.0, -50.0], [100.0, 50.0]]}
    wing = {"points": [[200.0, 90.0], [280.0, 90.0]], "shapes": ["objects/p.obj#comp1"]}
    rows = W.declare_joints([at, away, wing], (_record(),), lambda lon, lat: (lon, lat),
                            ("objects/p.obj",))
    assert rows[0].get(W.JOINT_KEY) is True and W.JOINT_KEY not in rows[1]
    assert rows[2].get(W.JOINT_KEY) is True          # the plate object's own wall
    assert check_grade._terrace_joint_strip_exempt(rows) == [True, False, True]
