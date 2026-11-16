"""#2118: a unit whose walls are not its ground — a basin takes its rim, a
structure on piles its zero-level contacts (``airport/zero_level_seat``)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as ar
from auto_patch_v2.airport import zero_level_seat as zl

M = 1.0 / 111_000.0          # ~ one metre in degrees at the equator


def _part(pid, lat, lon, base_y, feet, h=5.0, box=None):
    box = box or (lat - 5 * M, lon - 5 * M, lat + 5 * M, lon + 5 * M)
    return types.SimpleNamespace(pid=pid, lat=lat, lon=lon, base_y=base_y,
                                 feet=tuple(feet), height_m=h, line=False, box=box)


def test_a_basin_unit_takes_its_rim_not_its_floor():
    """OTHH Dewatering_02: the floor read -9.68 and the walls -9.37; the rim
    the patch cut stands at 3.96 and is the object's zero."""
    ring = ar.RimRing("basin_wall:6", ((-20 * M, -20 * M), (-20 * M, 20 * M),
                                       (20 * M, 20 * M), (20 * M, -20 * M)))

    def surface(la, lo):
        inside = abs(la) < 20 * M and abs(lo) < 20 * M
        return -9.68 if inside else 3.96
    floor = _part(1, 0.0, 0.0, -13.2, [(0.0, 0.0, -9.37)])
    out = zl.rim_unit_zero([1], {1: floor}, {1: (0.0, 25 * M)}, [ring], surface)
    assert out is not None and abs(out[0] - 3.96) < 1e-9 and out[1] == "basin_wall:6"
    assert zl.rim_unit_zero([1], {1: floor}, {1: (0.0, 25 * M)}, [], surface) is None


COLUMN = types.SimpleNamespace(min_h_m=2.0, max_w_m=2.0, aspect=3.0, min_count=3)


def _pier(wall_y=-8.93, w=0.9):
    piles = [_part(i, i * 10 * M, 0.0, wall_y, [(i * 10 * M, 0.0, wall_y)], h=10.9,
                   box=(i * 10 * M, 0.0, i * 10 * M + w * M, w * M)) for i in range(1, 6)]
    end = _part(9, 0.0, 0.0, -0.15, [(0.0, 0.0, -0.15)], h=1.9,
                box=(0.0, 0.0, 10 * M, M))       # the land end, touching pile 1
    member = types.SimpleNamespace(parts=tuple(piles) + (end,))
    parts = {p.pid: p for p in member.parts}
    unit = types.SimpleNamespace(pids=frozenset(p.pid for p in piles),
                                 boxes=tuple(p.box for p in piles))
    return unit, parts, {q: member for q in parts}


def _shore(la, lo):
    return 3.96 if la < 5 * M else 0.1


def test_a_pier_on_piles_seats_on_its_land_end():
    """OTHH 34R approach-light pier: every pile foot at y -8.93 on sea-level
    ground, the land end (in no unit) at y -0.15 on 3.96 — the unit takes
    4.11 and the piles bury, where the walls' base put it at 8.93."""
    unit, parts, member_of = _pier()
    out = zl.unit_zero(unit, unit.pids, parts, member_of, {}, (), _shore,
                       2.0, 3.0, 1.0, COLUMN)
    assert out is not None and abs(out[0] - 4.11) < 1e-9 and out[2] == zl.PILE_SRC


def test_walls_that_are_not_columns_or_reach_the_zero_keep_the_walls_rule():
    """A building's walls (wide), piles that reach the zero level, or no
    column law: the walls' reading stands."""
    unit, parts, member_of = _pier(w=6.0)
    assert zl.unit_zero(unit, unit.pids, parts, member_of, {}, (), _shore,
                        2.0, 3.0, 1.0, COLUMN) is None
    unit, parts, member_of = _pier(wall_y=-2.0)
    assert zl.unit_zero(unit, unit.pids, parts, member_of, {}, (), _shore,
                        2.0, 3.0, 1.0, COLUMN) is None
    unit, parts, member_of = _pier()
    assert zl.unit_zero(unit, unit.pids, parts, member_of, {}, (), _shore,
                        2.0, 3.0, 1.0, None) is None


def test_a_tunnel_ring_is_no_rim():
    """Only a basin ring (``basin_wall:``) is the object's rim."""
    ring = ar.RimRing("tunnel_wall@1", ((-20 * M, -20 * M), (-20 * M, 20 * M),
                                        (20 * M, 20 * M), (20 * M, -20 * M)))
    floor = _part(1, 0.0, 0.0, -13.2, [(0.0, 0.0, -9.37)])
    assert zl.rim_unit_zero([1], {1: floor}, {1: (0.0, 25 * M)}, [ring],
                            lambda la, lo: 1.0) is None
