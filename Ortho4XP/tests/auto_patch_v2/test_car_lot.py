"""Twins of the parked-car lot (owner RULINGS 2026-11-16p, #2114): three or
more parked cars within ``link_m`` on ground no cell holds mark a
``parking_lot`` under them (+ the margin); cars on an apron, along a road,
on a deck or inside a building count for nothing; the lot is a LATE cell."""
from __future__ import annotations

import types

from auto_patch_v2.airport.facade import is_parked_car
from auto_patch_v2.classify import car_lot as cl
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model import planar as mp
from auto_patch_v2.model.airport import Building, DsfObject
from shapely.geometry import Point, Polygon

CAR = "lib/cars/car_static.obj"


def _car(i, x, y, kind="OBJECT", y_off=0.0, path=CAR):
    return DsfObject(f"dsf:obj{i}", path, (x, y), 0.0, None, False, None, y_off, None, kind)


def _cell(i, role, ring, side="groundside"):
    return Cell(i, role, f"{role}{i}", tuple(ring), (), None, None, side, role, {})


def _box(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _row(i0, x0, y, n, step=4.0, **kw):
    return [_car(i0 + k, x0 + k * step, y, **kw) for k in range(n)]


class _Flat:
    provenance = {}

    def z(self, x, y):
        return 100.0


def _plan(objects, cells, buildings=()):
    """``([(part, cars)], stats)`` through the mint's own constructor hook."""
    ap = types.SimpleNamespace(dsf_objects=tuple(objects), buildings=tuple(buildings), dem=_Flat())
    out = []
    stats = cl.mint_car_lots(ap, list(cells), Law.for_airport("KBNA"), load_rules(),
                             lambda role, ref, poly, kind, cn=None, cl_=None, evidence=None:
                             out.append((poly, evidence[cl.CARS_KEY])))
    return out, stats


def test_a_parked_car_is_a_vehicle_by_library_or_by_the_packs_vehicle_folder():
    assert is_parked_car(CAR)
    assert is_parked_car("Objects/X Objects Static/X Vehicles/X Pickup Trucks/Dodge.obj")
    assert not is_parked_car("Objects/X Parking Itens/carStop_1x.obj")       # a wheel stop
    assert not is_parked_car("Objects/X Car Container/cont_dolly_P6P_1.obj")
    assert not is_parked_car("Objects/cargo/hall.obj")


def test_three_linked_cars_on_free_ground_mark_one_lot_and_two_do_not():
    plan, stats = _plan(_row(0, 0.0, 0.0, 4) + _row(10, 200.0, 0.0, 2), [])
    assert stats["car_groups"] == 1 and len(plan) == 1
    part, n = plan[0]
    assert n == 4
    reach = load_rules().car_lots.car_half_m + load_rules().car_lots.margin_m
    assert part.contains(Point(-reach + 0.5, 0.0)) and not part.contains(Point(-reach - 0.5, 0.0))
    assert not part.intersects(Polygon(_box(190.0, -10.0, 210.0, 10.0)))


def test_cars_on_an_apron_along_a_road_raised_or_in_a_building_count_for_nothing():
    apron = _cell(0, "apron", _box(-10.0, -10.0, 40.0, 10.0), side="airside")
    road = _cell(1, "service_road", _box(-10.0, 98.0, 40.0, 104.0))
    on_apron = _row(0, 0.0, 0.0, 4)
    by_road = _row(10, 0.0, 106.0, 4)                           # 2 m off the road edge
    raised = _row(20, 0.0, 200.0, 4, kind="OBJECT_AGL", y_off=6.0)
    garage = Building("osm:1", _box(-10.0, 290.0, 40.0, 310.0), (), "osm", None, None)
    inside = _row(30, 0.0, 300.0, 4)
    msl_deck = _row(40, 0.0, 400.0, 4, kind="OBJECT_MSL", y_off=108.0)
    plan, stats = _plan(on_apron + by_road + raised + inside + msl_deck, [apron, road], [garage])
    assert plan == []
    assert stats["cars_held"] == 8 and stats["cars_along_road"] == 4 and stats["cars_raised"] == 8


def test_the_lot_takes_only_free_ground_and_stands_off_what_stands():
    pad = _cell(0, "building", _box(-20.0, 4.0, 40.0, 30.0), side="airside")
    road = _cell(1, "service_road", _box(-20.0, -14.0, 40.0, -4.5))
    plan, _s = _plan(_row(0, 0.0, 0.0, 5), [pad, road])
    part, _n = plan[0]
    assert part.intersection(Polygon(pad.ring)).area < 1e-6
    assert part.distance(Polygon(pad.ring)) > 0.5               # the pad's set-back
    assert part.distance(Polygon(road.ring)) > 0.5              # the stand-off


def test_the_mint_spells_a_late_lot():
    out = []
    ap = types.SimpleNamespace(dsf_objects=tuple(_row(0, 0.0, 0.0, 3)), buildings=(), dem=_Flat())
    stats = cl.mint_car_lots(ap, [], Law.for_airport("KBNA"), load_rules(),
                             lambda role, ref, poly, kind, cn=None, cl_=None, evidence=None:
                             out.append((role, ref, kind, dict(evidence or {}))))
    assert out == [("parking_lot", "carlot:0", "parking_lot", {cl.CARS_KEY: 3})]
    assert stats["car_lots"] == 1
    assert mp.is_late_ref("carlot:0") and mp.is_late_ref("carlot:3#1")
