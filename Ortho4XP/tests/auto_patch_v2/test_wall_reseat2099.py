"""T5 / T6 (#2099 F2 P4, spec ``docs/specs/2099-F2.md`` §5): a retaining
wall the entrance re-read seats has ONE seat -- the wall class reads the
entrance's zero (``Airport.wall_reseats``, ``wall_class._seat_z``), its top
rows are a seat pair to the entrance's airside seat (``constraints/
road_ramp``), and only ``planar/wall_slope`` reads its RETAINED band; no
re-seat, nothing changes."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import wall_class
from auto_patch_v2.airport.wall_reseat import _reseats as wall_reseats
from auto_patch_v2.airport.wall_reseat import attach_wall_reseats
from auto_patch_v2.constraints import road_ramp as rr
from auto_patch_v2.constraints.edge_floor import seat_pair
from auto_patch_v2.constraints.wall_zone import RetainingLine
from auto_patch_v2.model.constraints import Source
from auto_patch_v2.planar.wall_slope import wall_slopes
from shapely.geometry import LineString, box


def _pin(oid, reseat, floor=165.0, bottom=-7.0):
    return types.SimpleNamespace(object_id=oid, wall_reseat=reseat, floor_z=floor, bottom_y=bottom)


def test_only_a_pin_the_re_read_walls_reseats_its_wall():
    got = wall_reseats([_pin("a", True), _pin("b", False), _pin("a", True, floor=164.0)])
    assert got == {"a": pytest.approx(171.0)}
    ap = types.SimpleNamespace(wall_reseats={})
    import dataclasses as dc

    @dc.dataclass(frozen=True)
    class _Ap:
        wall_reseats: dict = dc.field(default_factory=dict)
    assert attach_wall_reseats(_Ap(), [_pin("a", True)]).wall_reseats == {"a": 172.0}
    # the wall class reads it as the member's seat; no entry, the DEM's
    member = types.SimpleNamespace(id="a", zero_y=0.0)
    seated = types.SimpleNamespace(wall_reseats={"a": 176.0}, dem=None)
    assert wall_class._seat_z(seated, None, member, None) == 176.0
    assert wall_class._seat_z(ap, None, member, None) is None      # no DEM: unread


def test_a_reseated_walls_top_rows_are_a_seat_pair():
    face = LineString([(0.0, 0.0), (100.0, 0.0)])
    poly = box(0.0, -1.0, 100.0, 0.0)
    line = RetainingLine(poly, 20.0, 3.0, {}, face, ((0.0, 176.5), (100.0, 176.5)),
                         placement="a", reseat_z=176.0)
    plain = line._replace(placement="b", reseat_z=None)
    terms = ((7, 0.5), (8, 0.5))
    assert rr._seated_top([line], {"a": terms}, (50.0, 0.2)) == (terms, 176.0)
    assert rr._seated_top([plain], {"b": terms}, (50.0, 0.2)) is None
    assert rr._seated_top([line], {}, (50.0, 0.2)) is None          # no airside seat: Band
    # z[v] = the airside seat less (zero - level): level - zero over the seat
    rows = seat_pair(1, (terms, 176.0 - 176.5), Source("wall_terrace", "r", ()))
    z = {7: 170.0, 8: 171.0}
    zv = 0.5 * (z[7] + z[8]) + 0.5
    for r in rows:
        lhs = sum(c * (zv if k == 1 else z[k]) for k, c in r.terms)
        assert (r.lo is None or lhs >= r.lo - 1e-9) and (r.hi is None or lhs <= r.hi + 1e-9)


def test_only_the_wall_slope_reads_the_retained_band():
    poly = box(0.0, -1.0, 100.0, 0.0)
    w = types.SimpleNamespace(poly=poly, upper=box(0.0, 0.0, 100.0, 3.0),
                              lower=box(0.0, -4.0, 100.0, -1.0), resource="w.obj",
                              top_profile=((0.0, 176.5), (100.0, 176.5)), foot_profile=None,
                              upper_face=None, lower_face=None, retained=None)
    near = sum(g.area for _r, g in wall_slopes([w], (), (), 0.5, 0.05))
    far = sum(g.area for _r, g in wall_slopes(
        [types.SimpleNamespace(**dict(vars(w), retained=box(0.0, 0.0, 100.0, 20.0)))],
        (), (), 0.5, 0.05))
    assert near == pytest.approx(300.0, rel=0.01)
    assert far == pytest.approx(2000.0, rel=0.01)
