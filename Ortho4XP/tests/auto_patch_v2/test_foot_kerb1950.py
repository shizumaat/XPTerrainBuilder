"""#1950 / #1952 KMCI round 4 (owner RULINGS 2026-11-10a (2)): a lot at a
retaining wall's foot steps down from the held pad it meets at a declared
KERB (``planar/foot_kerb``), read as a declared wall
(``airport/riser_wall``); the lot is at the foot for every wall
(``airport/road_ramp.wall_terraces``)."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import LineString, box

from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import kerb_ref
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar import foot_kerb as FK
from auto_patch_v2.planar.overlay import Region

FOOT = ((0.0, 299.8), (100.0, 299.8), (200.0, 299.8))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _wall(low_side="sheets"):
    return types.SimpleNamespace(lower_band=box(300.0, 505.15, 500.0, 508.96),
                                 lower_face=LineString([(300.0, 505.15), (500.0, 505.15)]),
                                 foot_profile=FOOT, low_side=low_side)


def _reg(level):
    reg = Registries()
    reg.held["blk"] = {"unit": "blk", "datum_pred": level}
    return reg


def _regions():
    lot = Region("parking_lot", "dsf:lot", box(320.0, 506.0, 360.0, 540.0), None, None,
                 "groundside", "cell")
    pad = Region("building", "blk", box(320.0, 540.0, 360.0, 580.0), None, None,
                 "airside", "cell")
    return [lot], [pad]


def test_a_foot_lot_steps_down_from_its_pad_at_a_declared_kerb(law, monkeypatch):
    monkeypatch.setattr(FK, "_foot_walls", lambda _a: [_wall()])
    base, pads = _regions()
    reg = _reg(305.0)
    counts: dict = {}
    b2, p2 = FK.foot_kerbs(base, pads, types.SimpleNamespace(dem=None), law, 0.5, reg, counts)
    kerbs = [r for r in p2 if r.ref == kerb_ref("blk")]
    assert len(kerbs) == 1 and kerbs[0].role == "building"
    K = kerbs[0].polygon
    assert K.bounds == pytest.approx((320.0, 539.0, 360.0, 540.0))   # one riser width
    (lot,) = b2
    assert lot.ref == "dsf:lot" and lot.polygon.bounds[3] == pytest.approx(539.0)
    assert not lot.polygon.intersects(pads[0].polygon)
    (rec,) = reg.held["blk"]["kerbs"]
    assert rec["height_m"] == pytest.approx(5.2)
    assert rec["upper"] and all(abs(y - 540.0) < 0.3 for ln in rec["upper"] for _x, y in ln)
    assert counts["foot_kerbs"] == 1
    # the front is memoised: a second pass SETS the record, never appends
    FK.foot_kerbs(*_regions(), types.SimpleNamespace(dem=None), law, 0.5, reg)
    assert len(reg.held["blk"]["kerbs"]) == 1


def test_no_kerb_without_a_step_a_held_pad_or_a_sheet_wall(law, monkeypatch):
    for walls, reg in (([_wall()], _reg(300.1)),                 # within visual_m
                       ([_wall("dem")], _reg(305.0)),            # 10-03c lot
                       ([_wall()], Registries())):               # no held pad
        monkeypatch.setattr(FK, "_foot_walls",
                            lambda _a, w=walls: [x for x in w if x.low_side == "sheets"])
        base, pads = _regions()
        b2, p2 = FK.foot_kerbs(base, pads, types.SimpleNamespace(dem=None), law, 0.5, reg)
        assert b2 == base and p2 == pads


def test_a_pads_kerb_is_read_as_a_declared_wall(law):
    """``airport/riser_wall``: the kerb's faces become one wall record --
    ``upper`` on the pad's edge, ``lower`` on the lot's -- so the readers
    that take a wall (release, cut, step floor, joint) take it."""
    from auto_patch_v2.airport.riser_wall import riser_walls
    V = {1: (320.0, 540.0), 2: (360.0, 540.0), 3: (360.0, 539.0), 4: (320.0, 539.0)}
    pm = types.SimpleNamespace(
        vertices={v: types.SimpleNamespace(xy=p) for v, p in V.items()},
        faces={0: types.SimpleNamespace(ref=kerb_ref("blk"), ring=(1, 2, 3, 4), holes=())},
        ring_vertices=lambda ring: ring,
        registries=types.SimpleNamespace(landings={}, held={"blk": {"kerbs": [{
            "ring": [(320.0, 539.0), (360.0, 539.0), (360.0, 540.0), (320.0, 540.0),
                     (320.0, 539.0)],
            "upper": [[(320.0, 540.0), (360.0, 540.0)]], "height_m": 5.2}]}}))
    (rec,) = riser_walls(pm, law)
    assert rec["upper"] == [1, 2] and rec["lower"] == [3, 4]
    assert rec["height_m"] == 5.2 and rec["retains"] and rec["label"].endswith("blk#kerb#0")


def test_the_foot_walls_are_the_retaining_walls_whose_low_side_is_the_sheets():
    """``airport/foot_lot.sheet_walls`` reads ``WallSides.low_side`` off
    ``airport.retaining_walls`` (one reading of the sides, no second
    wall-class pass): a DEM-witnessed wall is no foot wall."""
    from auto_patch_v2.airport.foot_lot import sheet_walls
    w = _wall()
    side = types.SimpleNamespace(lower=w.lower_band, lower_face=w.lower_face,
                                 foot_profile=FOOT, low_side="sheets")
    dem = types.SimpleNamespace(lower=w.lower_band, lower_face=w.lower_face,
                                foot_profile=FOOT, low_side="")
    (got,) = sheet_walls(types.SimpleNamespace(retaining_walls=(side, dem)))
    assert got.lower_band is w.lower_band and got.low_side == "sheets"
    assert sheet_walls(types.SimpleNamespace()) == []
