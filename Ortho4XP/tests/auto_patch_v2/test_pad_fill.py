"""Issues #712 / #1003 twin (owner RULINGS 2026-10-19ap, Q33 2026-10-20;
spec ``docs/specs/pad-fill-region-spec.md``): the ground under a pad
unit's off-pad plate and pier prints is filled to the pad's level — the
fill is a ramp LANDING of the block (its level rows, 1:3 collar and lot
cut).  Hermetic: a metre frame (lon = x, lat = y)."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.geom.base_slab import FaceFacts
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import base_slab_law
from auto_patch_v2.planar import pad_fill as PF
from shapely.geometry import box

LAW = Law.for_airport("HECA")
LW = base_slab_law(LAW)
FLAT = FaceFacts(0.0, 0.0, 0.0)


def to_xy(lon, lat):
    return (lon, lat)


def _part(comp, b, base_y=0.15, h=0.0, feet=()):
    ring = tuple((y, x) for x, y in tuple(b.exterior.coords)[:-1])
    x0, y0, x1, y1 = b.bounds
    return types.SimpleNamespace(comp=comp, base_y=base_y, height_m=h,
                                 area_m2=b.area, rings=(ring,), feet=feet,
                                 box=(y0, x0, y1, x1), line=False, scatter=False)


def _partition(*parts, mid="dsf:obj1", res="Terminal/side_walk.obj", deck=""):
    m = types.SimpleNamespace(id=mid, resource=res, parts=tuple(parts),
                              deck_kind=deck, origin=(0.0, 0.0), heading_deg=0.0)
    return types.SimpleNamespace(units=(types.SimpleNamespace(id="unit:0", members=(m,)),))


BLOCK = [("b5", box(0, 0, 100, 100))]


def _faces(ff=FLAT):
    return lambda _m, _c: ff


def test_a_feetless_plate_riding_a_block_fills_its_off_block_part_at_its_y():
    """HECA ``Seasonal_Terminal/side_walk.obj``: a zero-thickness plate at
    y 0.15 with no feet, part on its terminal's block, part over the lot."""
    plate = _part(0, box(50, 0, 160, 100))
    got = PF.plate_fills(_partition(plate), to_xy, LW, _faces(), BLOCK)
    assert len(got) == 1
    f = got[0]
    assert (f.block, f.kind, f.y) == ("b5", "plate", 0.15)
    assert f.extent.area == pytest.approx(60 * 100)
    assert f.extent.bounds == pytest.approx((100, 0, 160, 100))


def test_a_plate_that_barely_touches_a_block_does_not_ride_it():
    plate = _part(0, box(99, 0, 200, 100))       # 100 m2 on the block < min_m2
    assert PF.plate_fills(_partition(plate), to_xy, LW, _faces(), BLOCK) == []


def test_a_sloped_or_kerbed_plate_is_no_fill():
    plate = _part(0, box(50, 0, 160, 100))
    sloped = FaceFacts(0.0, 2.0 * LW.level_m + 0.1, 0.0)
    kerbed = FaceFacts(LW.max_side_share + 0.1, 0.0, 0.0)
    elevated = FaceFacts(0.0, 0.0, 0.9)
    for ff in (sloped, kerbed, elevated):
        assert PF.plate_fills(_partition(plate), to_xy, LW, _faces(ff), BLOCK) == []


def test_a_storey_or_a_deck_member_is_no_plate():
    storey = _part(0, box(50, 0, 160, 100), base_y=0.0, h=LW.max_height_m + 1.0)
    high = _part(1, box(50, 0, 160, 100), base_y=LW.base_y_max_m + 0.5)
    assert PF.plate_fills(_partition(storey, high), to_xy, LW, _faces(), BLOCK) == []
    plate = _part(0, box(50, 0, 160, 100))
    assert PF.plate_fills(_partition(plate, deck="flag"), to_xy, LW, _faces(), BLOCK) == []


class _Deck:
    """A deck footprint: everything inside ``area`` is its."""

    def __init__(self, area):
        self.area, self.unit, self.member = area, 0, 99

    def contains(self, lat, lon):
        return self.area.contains(box(lon - 1e-6, lat - 1e-6, lon + 1e-6, lat + 1e-6))

    def contains_many(self, lats, lons):
        return [self.contains(la, lo) for la, lo in zip(lats, lons, strict=True)]


def _piers(xs, y=-0.29):
    return [_part(i, box(x, 110, x + 2, 140), base_y=y, h=0.7,
                  feet=((112.0, x + 1.0, y), (138.0, x + 1.0, y)))
            for i, x in enumerate(xs)]


def test_a_viaducts_ground_prints_off_its_block_are_one_fill_within_two_banks():
    """HECA #1003: the T3 viaduct's ground strips stand off its block,
    31 m apart — closer than two bank widths, so one fill (their hull)."""
    from auto_patch_v2.airport import bridge_family as BF
    part = _partition(*_piers([10, 41, 72]), res="T23/Plastic.obj")
    vias = {"T23/T3_road.obj": ("b5", 3, BF.frame_of(part.units[0].members[0]),
                                _Deck(box(0, 100, 200, 200)))}
    got = PF.pier_fills(vias, part, to_xy, BLOCK, 0.5, 2 * 15.0)
    assert len(got) == 1
    f = got[0]
    assert (f.block, f.kind, f.y, f.voters) == ("b5", "piers", -0.29, 3)
    assert f.extent.bounds == pytest.approx((10, 110, 74, 140))
    # far apart, two fills
    part2 = _partition(*_piers([10, 141]), res="T23/Plastic.obj")
    vias2 = {"d": ("b5", 2, BF.frame_of(part2.units[0].members[0]),
                   _Deck(box(0, 100, 200, 200)))}
    assert len(PF.pier_fills(vias2, part2, to_xy, BLOCK, 0.5, 30.0)) == 2


def test_a_print_below_the_band_or_outside_the_deck_is_not_the_viaducts():
    from auto_patch_v2.airport import bridge_family as BF
    part = _partition(*_piers([10], y=-2.0), res="T23/Plastic.obj")
    vias = {"d": ("b5", 1, BF.frame_of(part.units[0].members[0]),
                  _Deck(box(0, 100, 200, 200)))}
    assert PF.pier_fills(vias, part, to_xy, BLOCK, 0.5, 30.0) == []
    part = _partition(*_piers([10]), res="T23/Plastic.obj")
    vias = {"d": ("b5", 1, BF.frame_of(part.units[0].members[0]),
                  _Deck(box(500, 500, 600, 600)))}
    assert PF.pier_fills(vias, part, to_xy, BLOCK, 0.5, 30.0) == []


def test_a_plate_fill_is_a_landing_of_its_block_with_its_collar(monkeypatch):
    """The fill is minted by the ramp-landing mint (no deck needed): a
    ``<unit>/landing<k>`` held at the block's datum + y, with the landing's
    1:3 collar, never taking the airside or a bank's width of it."""
    from auto_patch_v2.airport import slab_faces as SF
    from auto_patch_v2.model.registries import Registries
    from auto_patch_v2.planar import landing as LD
    from auto_patch_v2.planar.overlay import Region
    monkeypatch.setattr(SF, "witness_faces", lambda _lw: _faces())
    plate = _part(0, box(50, 0, 160, 100))
    airport = types.SimpleNamespace(partition=_partition(plate),
                                    frame=types.SimpleNamespace(entry=lambda: to_xy))
    pad = Region("building", "b5", box(0, 0, 100, 100), None, None, "groundside", "cell")
    air = box(150, 0, 300, 100)
    reg = Registries()
    reg.held["b5"] = {"unit": "b5", "k": 0, "blocks": 1}
    counts: dict = {}
    got = LD.landing_regions([pad], {}, [air], airport, LAW, 0.0, 15.0, counts, reg=reg)
    refs = {str(r.ref) for r in got}
    assert refs == {"b5/landing0", "b5/landing0#collar"}
    rec = reg.landings["b5/landing0"]
    assert (rec["block"], rec["y"], rec["kind"]) == ("b5", 0.15, "plate")
    keep = float(LAW.tables.emit.design.bank_min_width_m)
    for r in got:
        assert r.polygon.distance(air) >= keep - 0.01   # the round buffer's chord
    assert counts["landings"] == 1

