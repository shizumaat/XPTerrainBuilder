"""#1139 twin: a pack retaining wall splits the adjacent ground
(``constraints/wall_zone``) and a one-wall object retains its depth under
its zero (``airport/wall_class``)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import wall_class
from auto_patch_v2.constraints import wall_zone as wz
from auto_patch_v2.model.constraints import Linear, Source
from shapely.geometry import Polygon, box

SRC = Source("zones", "zones.adjacent_ground (2026-08-01)", ())
# a 5 m wall along x = -2 .. 0 (reach 20 m, smear 5 m); upper side west
WALL = wz.RetainingLine(box(-2.0, 0.0, 0.0, 100.0), 20.0, 5.0,
                        {100: "upper", 101: "lower"})
XY = {100: (-12.0, 50.0), 101: (25.0, 50.0)}


def _row(g, feet, lo=-0.6, hi=-0.2):
    return Linear(((g, 1.0), *((v, -w) for v, w in feet)), lo, hi, SRC, follows=g)


def _split(r, xy, pave=None, refs=None):
    refs = refs or {}
    return wz.split(r, {**XY, **xy}, [WALL], lambda v: refs.get(v, frozenset()),
                    lambda _r: pave)


def test_an_overhanging_edge_releases_its_zone():
    # the pavement runs 3 m past the wall's face; the zone beyond is below
    pave = box(-30.0, 0.0, 3.0, 100.0)
    side, _ = _split(_row(1, [(2, 1.0)]), {1: (10.0, 50.0), 2: (3.0, 50.0)}, pave)
    assert side == "beyond"


def test_a_wall_under_the_far_edge_keeps_the_upper_zone():
    # the same pavement's WEST zone stands on the upper side: kept as it is
    pave = box(-5.0, 0.0, 10.0, 100.0)
    r = _row(1, [(2, 1.0)])
    side, kept = _split(r, {1: (-10.0, 50.0), 2: (-5.0, 50.0)}, pave)
    assert side is None and kept is r


def test_ground_between_the_pavement_and_the_wall_is_flat():
    # the wall AT the pavement edge (4 m out, within BEHIND_SHARE x reach)
    pave = box(-16.0, 0.0, -6.0, 100.0)
    side, kept = _split(_row(1, [(2, 1.0)]), {1: (-4.0, 50.0), 2: (-6.0, 50.0)}, pave)
    assert side == "before" and kept.lo == 0.0 and kept.hi == 0.0


def test_a_wall_far_from_the_pavement_keeps_the_band_law():
    # #1633 round 3 spec §3 (2): 28 m out the wall is met by the band's own
    # law (the band stops short of it in ``planar/zones``), never a plane
    pave = box(-40.0, 0.0, -30.0, 100.0)
    r = _row(1, [(2, 1.0)])
    side, kept = _split(r, {1: (-10.0, 50.0), 2: (-30.0, 50.0)}, pave)
    assert side is None and kept is r


def test_a_floor_only_row_never_becomes_the_plane():
    pave = box(-40.0, 0.0, -30.0, 100.0)
    r = _row(1, [(2, 1.0)], lo=None, hi=-0.2)
    side, kept = _split(r, {1: (-10.0, 50.0), 2: (-30.0, 50.0)}, pave)
    assert side is None and kept is r


def test_a_blended_foot_below_the_wall_is_dropped():
    # feet: a taxiway edge west (same side) and a pad rim east, below the wall
    xy = {1: (-4.0, 50.0), 2: (-6.0, 50.0), 3: (8.0, 50.0)}
    r = _row(1, [(2, 0.5), (3, 0.5)])
    side, kept = _split(r, xy, box(-16.0, 0.0, -6.0, 100.0),
                        {2: frozenset({"pav14"}), 3: frozenset()})
    assert side == "before"
    assert [v for v, _c in kept.terms] == [1, 2]
    assert abs(sum(c for _v, c in kept.terms)) < 1e-9


def test_a_pavement_straddling_the_wall_releases_the_ground_past_it():
    xy = {1: (10.0, 50.0), 2: (5.0, 50.0), 3: (-6.0, 50.0)}
    r = _row(1, [(2, 0.5), (3, 0.5)])
    side, _ = _split(r, xy, box(-30.0, 0.0, 5.0, 100.0),
                     {2: frozenset({"pav14"}), 3: frozenset({"pav14"})})
    assert side == "beyond"


def test_the_lower_level_runs_flat_to_the_foot():
    # the DEM smears the step 2 m out; the level there is the ground past it
    xy = {1: (2.0, 50.0), 2: (9.0, 50.0), 3: (-4.0, 50.0)}
    out = wz.foot_ground({1: 298.0, 2: 290.0, 3: 301.0}, xy, [WALL])
    assert out[1] == 290.0 and out[2] == 290.0
    assert out[3] == 301.0          # nothing past the smear on its side


def test_a_one_wall_object_retains_its_depth_under_its_zero():
    part = types.SimpleNamespace(base_y=-10.52)
    assert wall_class._depth_under_zero(part) == 10.52
    assert wall_class._depth_under_zero(types.SimpleNamespace(base_y=0.4)) is None
    cfg = types.SimpleNamespace(retaining_wall_thick_width_per_height=0.5,
                                retaining_wall_step_min_fraction=0.75,
                                retaining_wall_step_max_fraction=1.25,
                                retaining_wall_step_ring_m=3.0)
    ap = types.SimpleNamespace(dem=object())
    whole = Polygon([(0, 0), (137, 0), (137, 1.46), (0, 1.46)])
    orig = wall_class._step_across
    wall_class._step_across = lambda *_a: 11.08      # KATL muro_ladrillo
    try:
        assert not wall_class._retains_its_height(ap, whole, 1.46, 16.64, cfg)
        assert wall_class._retains_its_height(ap, whole, 1.46, 16.64, cfg, 10.52)
    finally:
        wall_class._step_across = orig
