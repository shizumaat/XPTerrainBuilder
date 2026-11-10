"""#1977: a pack plate that CONTINUES a runway's paved end (an overrun deck on
a retaining structure) is a runway-end walled plate read at the paved end —
seated flush with the pavement at its near edge, its safety area and
under-plate ground starting where it leaves the pavement.  Synthetic: one
runway along +y, its north end at (0, 0) with a 50 m blast pad; a plate from
s0 past the end, its top rising 1 % outward, a 30 m wall down its side."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import pavement_end_plate as PE
from auto_patch_v2.airport import walled_plate as W
from auto_patch_v2.airport.obj8 import ObjGeometry, PlacedObject
from auto_patch_v2.law import Law
from shapely.geometry import Polygon


@pytest.fixture(scope="module")
def law():
    return Law.load()


def _runway(pad=50.0):
    def end(n, xy, over):
        return types.SimpleNamespace(name=n, xy=xy, approach="visual", overrun_m=over)
    return types.SimpleNamespace(id="16/34",
                                 ends=(end("16", (0.0, 0.0), pad), end("34", (0.0, -3000.0), 0.0)),
                                 code_number=4, code_letter="E", instrument=False, width_m=45.0)


class _Dem:
    def z_many(self, xs, ys):
        return np.array([100.0 if y < 120.0 else 70.0 for y in ys])


def _deck(s0=40.0, s1=140.0, half=30.0, wall=True, rise=0.01) -> ObjGeometry:
    """Authored x east, z south (frame s = -z), the top at y = rise * (s - s0)."""
    def y(s):
        return rise * (s - s0)
    v = [(-half, y(s0), -s0), (half, y(s0), -s0), (half, y(s1), -s1), (-half, y(s1), -s1)]
    tris = [(0, 1, 2), (0, 2, 3)]
    if wall:
        v += [(-half, -30.0, -s0), (-half, -30.0, -s1)]
        tris += [(0, 3, 5), (0, 5, 4)]
    t = np.array(tris, dtype=np.int64)
    return ObjGeometry("d.obj", np.array(v, dtype=float), t, np.zeros(len(t), dtype=np.int64),
                       np.zeros((0, 3), dtype=np.int64))


def _placed() -> PlacedObject:
    box = Polygon([(-30, 30), (30, 30), (30, 150), (-30, 150)])
    return PlacedObject("dsf:7", "objects/d.obj", "/pack/objects/d.obj", (0.0, 0.0), 0.0, 0.0,
                        "OBJECT_MSL", 100.0, None, box, None, None, None, None,
                        origin_built=True, deck_kind="candidate")


class _Cache:
    def __init__(self, g):
        self.g = g

    def geometry(self, path):
        return self.g


def _mark(law, g, pad=50.0):
    ap = types.SimpleNamespace(runways=(_runway(pad),), dem=_Dem(), walled_plates=())
    return W.mark(ap, [_placed()], _Cache(g), law)[0]


def test_a_deck_at_the_paved_end_is_seated_flush_there(law):
    o = _mark(law, _deck())
    p = o.walled_plate
    assert p is not None and p.end_name == "16" and p.end == 0
    # its top AT the near edge (s 40 + 1 m into the plate), not the plate's mean
    assert p.plate_y == pytest.approx(0.01, abs=0.005)
    # the seat stands on the pavement just inside the near edge
    assert all(s[1] == pytest.approx(38.0, abs=0.5) for s in p.stations)
    # the safety area and the hidden ground start where it leaves the pavement
    assert p.inner_s == pytest.approx(50.0)
    assert min(y for _x, y in p.footprint) == pytest.approx(50.0, abs=0.5)
    assert p.height_m == pytest.approx(30.0, abs=0.5)
    # out of the MSL guard and the deck verdict (one rigid origin set)
    assert o.origin_built is False and o.deck_kind == ""


@pytest.mark.parametrize("why, g, pad", [
    ("no structure under it: a ground decal", _deck(wall=False), 50.0),
    ("too narrow to continue the runway", _deck(half=10.0), 50.0),
    ("its near edge far past the paved end", _deck(s0=120.0, s1=220.0), 50.0),
    ("its near edge far past a runway end with no pad", _deck(s0=40.0), 0.0),
])
def test_refused(law, why, g, pad):
    o = _mark(law, g, pad)
    assert o.walled_plate is None, why
    assert o.origin_built is True


def test_the_reader_alone_matches_the_record(law):
    e = W._ends(types.SimpleNamespace(runways=(_runway(),)), law)[0]
    o = types.SimpleNamespace(xy=(0.0, 0.0), heading_deg=0.0, id="x")
    r = PE.read(o, _deck(), e, _Dem(), law)
    assert r is not None and r.step_m == pytest.approx(30.0)


def test_a_unit_holding_a_walled_plate_rides_its_datum():
    """KCRW 05: the overrun's §16g unit took its wall's foot (46 m under the
    deck) as its datum; a unit holding a walled plate takes the plate's."""
    from auto_patch_v2.airport.open_frame_seat import walled_unit_zero
    plate = types.SimpleNamespace(plate_kind="walled", plate_y=0.12,
                                  plate_stations=((1.0, 1.0), (2.0, 2.0), (3.0, 3.0)))
    other = types.SimpleNamespace(plate_kind="", plate_y=None, plate_stations=())
    def surface(la, lo):
        return {1.0: 288.5, 2.0: 288.6, 3.0: None}[la]
    assert walled_unit_zero([other, plate], surface) == pytest.approx(288.55 - 0.12)
    assert walled_unit_zero([other], surface) is None
