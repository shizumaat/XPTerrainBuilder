"""#2099 P5b twin: A WALL-TOP PLATE IS SEATED BY ITS PLATE, NEVER BY A UNIT.

A hung wedge wall (``airport/hung_wall_seat``) carries its top as a plate of
kind ``WALL_TOP_PLATE`` (``pipeline/rebake_inputs._hung_wedges``).  Its §16e
datum (``anchor_rule.datum_of``) stands at any sign of its top y, and the
plan-wide partition (``footprint_unit.plan_units_and_connectors``) leaves it
out of every §16g unit: chained to a building cluster on a pad 0.9 m over the
airside, it took the pad's zero and drew 0.88 m proud (T7b)."""
from __future__ import annotations

import dataclasses as _dc
import statistics

import pytest
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport.hung_wall_seat import WALL_TOP_PLATE
from auto_patch_v2.model.frame import m_per_deg_exact
from auto_patch_v2.model.rebake import Member, Part, Unit

LAT0, LON0 = 43.68, -79.62
ML, MO = m_per_deg_exact(LAT0)
AIRSIDE, PAD = 169.0, 169.9          # the pad stands 0.9 m over the airside


def _ll(x, z):
    return LAT0 - z / ML, LON0 + x / MO


def _part(pid, x0, x1, z0, z1, height):
    ring = (_ll(x0, z0), _ll(x1, z0), _ll(x1, z1), _ll(x0, z1))
    la, lo = [p[0] for p in ring], [p[1] for p in ring]
    return Part(pid=pid, comp=0, lat=sum(la) / 4, lon=sum(lo) / 4, base_y=0.0,
                area_m2=(x1 - x0) * (z1 - z0), box=(min(la), min(lo), max(la), max(lo)),
                feet=tuple((*_ll(x, z), 0.0) for x, z in ((x0, z0), (x1, z1))),
                rings=(ring,), height_m=height)


def _member(mid, part, **kw):
    return Member(id=mid, resource=mid + ".obj", authored_path="", live_path="",
                  heading_deg=0.0, parts=(part,), origin=(LAT0, LON0), **kw)


#: the wall's top stations, on the airside behind its upper face
STATIONS = tuple(_ll(x, -12.0) for x in (0.0, 4.0, 8.0))


def _plan(kind=WALL_TOP_PLATE, top_y=1.2):
    a = _member("bldg_a", _part(0, 0.0, 10.0, 0.0, 10.0, 6.0))
    b = _member("bldg_b", _part(1, 10.0, 20.0, 0.0, 10.0, 6.0))
    wall = _member("wall", _part(2, 0.0, 10.0, -11.0, 0.0, 3.0), plate_y=top_y,
                   plate_stations=STATIONS, plate_kind=kind)
    units = tuple(Unit(f"unit:{k}", (LAT0, LON0), 0.0, (m,)) for k, m in enumerate((a, b, wall)))
    return _plan_ns(units)


def _plan_ns(units):
    import types
    return types.SimpleNamespace(units=units, contacts=(), connectors=None,
                                 adapted_frame_pids=(), authored_seats=())


def _surface(la, _lo):
    return AIRSIDE if la > _ll(0.0, -10.5)[0] else PAD


def _units(plan, counts=None):
    units, _c = FU.plan_units_and_connectors(plan, 0.5, 200.0, counts if counts is not None
                                             else {}, 2.5)
    z = FU.plan_unit_datums(units, plan, _surface, (), 0.0, 0.0, 2.5)
    return {b: (u.id, z[u.id][0]) for u in units for b in u.bodies if u.id in z}


def test_t7b_a_wedge_wall_touching_a_pad_cluster_keeps_its_plate_datum():
    counts = {}
    seats = _units(_plan(), counts)
    assert (2, 0, 0) not in seats                       # the wall: no §16g unit
    assert counts["unit_members_left_wall_top"] == 1
    wall = _plan().units[2].members[0]
    d = AR.datum_of(wall)
    assert d is not None and "wall-top plate" in d.label
    zero = statistics.mean(_surface(*s) for s in d.stations) - d.y
    assert zero == pytest.approx(AIRSIDE - 1.2)         # airside mean - top y
    # the cluster's zero is the one it had with no wall in the plan
    alone = _plan_ns(_plan().units[:2])
    assert {k: v[1] for k, v in seats.items()} == {k: v[1] for k, v in _units(alone).items()}


def test_without_the_kind_the_wall_still_chains_as_before():
    seats = _units(_plan(kind=""))
    assert (2, 0, 0) in seats and seats[(2, 0, 0)][0] == seats[(0, 0, 0)][0]


@pytest.mark.parametrize("top_y", [0.0, -0.05])
def test_a_wall_top_at_or_under_its_zero_is_still_seated(top_y):
    wall = _dc.replace(_plan().units[2].members[0], plate_y=top_y)
    d = AR.datum_of(wall)
    assert d is not None and d.y == pytest.approx(top_y) and d.stations == STATIONS
    # an unkinded plate at the same y stays the crest-plate rule's (y > 0 only)
    assert AR.datum_of(_dc.replace(wall, plate_kind="")) is None
