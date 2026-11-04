"""Owner RULINGS 2026-10-28s (2), Q250 a (#507, HECA ``metal_strip_2.obj``
comp 12): across a declared pack wall with airside pavement on both sides,
the lower side is bounded to no more than the wall's height below the
upper side, in the geometry.

Synthetic: two aprons either side of a 1 m thick, 3 m wall along x = 0.
``airport/wall_air`` names the pairs across it (the census's own pairing);
``solve/wall_floor`` floors the lower end of a pair the solve stood over
the wall, and ``solve/flex.stage_one`` re-solves stage 1 ONCE with them —
never where no pair is over (one solve, the problem untouched)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Band, ConstraintSet
from shapely.geometry import box

WALL = box(-0.5, -20.0, 0.5, 20.0)
#: west apron vertices 0-3 (x -10..-2), east apron 4-7 (x 2..10)
XY = [(-10.0, -10.0), (-2.0, -10.0), (-2.0, 10.0), (-10.0, 10.0),
      (2.0, -10.0), (10.0, -10.0), (10.0, 10.0), (2.0, 10.0)]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _pm(wall_air=None):
    verts = {i: NS(xy=xy, key=(xy[1] * 1e-5, xy[0] * 1e-5)) for i, xy in enumerate(XY)}
    faces = {0: NS(role="apron", ring=(0, 1, 2, 3), holes=()),
             1: NS(role="apron", ring=(4, 5, 6, 7), holes=())}
    terr = {} if wall_air is None else {"wall_air": wall_air}
    return NS(vertices=verts, faces=faces, ring_vertices=lambda r: tuple(r),
              road_terrace=terr)


def test_the_pairs_across_a_wall_are_the_census_pairing(law):
    from auto_patch_v2.airport.wall_air import wall_air_pairs
    w = NS(poly=WALL, height_m=3.0, label="wall.obj#comp0", mouth=False)
    got = wall_air_pairs(_pm(), law, [w])
    assert list(got) == [0]
    # within the 5 m pair window and across the wall: 1-4, 2-7 (4 m)
    assert sorted((a, b) for a, b, _d in got[0]["pairs"]) == [(1, 4), (2, 7)]
    assert got[0]["height_m"] == 3.0 and got[0]["label"] == "wall.obj#comp0"
    # a walled tunnel mouth declares only the step it carries: no pairs
    assert wall_air_pairs(_pm(), law, [NS(poly=WALL, height_m=3.0, label="m",
                                          mouth=True)]) == {}


def _air():
    return {0: {"line": [], "height_m": 3.0, "label": "wall.obj#comp0",
                "pairs": [(1, 4, 4.0), (2, 7, 4.0)]}}


def test_the_lower_end_is_floored_at_the_wall_height_below_the_upper(law):
    from auto_patch_v2.solve.wall_floor import WALL_FLOOR_RULING, wall_floor_rows
    z = [100.0, 100.0, 100.0, 100.0, 95.8, 95.8, 95.8, 97.5]
    rows = wall_floor_rows(_pm(_air()), law, z)
    # 1-4 steps 4.2 m over a 3 m wall: 4 floored at 97.0; 2-7 steps 2.5 m
    assert [(r.v, r.lo, r.hi) for r in rows] == [(4, 97.0, None)]
    assert rows[0].source.ruling.startswith(WALL_FLOOR_RULING + " (")
    assert wall_floor_rows(_pm(_air()), law, [100.0] * 8) == []


def _solve1(calls):
    def solve1(_pm_x, cs_x):
        z = [100.0, 100.0, 100.0, 100.0, 95.8, 95.8, 95.8, 97.5]
        for b in cs_x.bands:
            z[b.v] = max(z[b.v], b.lo)
        calls.append(len(cs_x.bands))
        return (NS(z=tuple(z)), NS(wall_floor=None), frozenset(), {}, {}, {})
    return solve1


def test_stage_one_solves_once_more_with_the_floors(law):
    from auto_patch_v2.solve.flex import stage_one
    calls: list[int] = []
    _pm1, cs, got, rec, _y = stage_one(_pm(_air()), ConstraintSet.from_rows([]),
                                       law, None, _solve1(calls))
    assert calls == [0, 1] and rec is None
    assert [b.v for b in cs.bands if isinstance(b, Band)] == [4]
    assert got[0].z[4] == pytest.approx(97.0)
    assert got[1].wall_floor["rows"] == 1 and got[1].wall_floor["unmet"] == []
    assert got[1].wall_floor["worst_lift_m"] == pytest.approx(1.2)


def test_no_pair_over_its_wall_is_one_solve_and_the_same_problem(law):
    from auto_patch_v2.solve.flex import stage_one
    calls: list[int] = []
    cs0 = ConstraintSet.from_rows([])
    _pm1, cs, got, _rec, _y = stage_one(_pm(), cs0, law, None, _solve1(calls))
    assert calls == [0] and cs is cs0 and got[1].wall_floor is None
