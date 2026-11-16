"""#1934 R3 (spec ``docs/specs/1934-R3.md`` §3; RULINGS 2026-11-16d,
2026-11-13x (1)): a mapped-road ribbon standing within the rim band of the
airside is grown to the rim and welded at its nodes (30aa rule 9) -- but
never across a retaining wall's footprint and the grid step past it:
there it stands where it is, the step drawn inside the wall's slot.  The
weld beside no wall is unchanged."""
from __future__ import annotations

from auto_patch_v2.law import Law
from auto_patch_v2.model.wall_reach import wall_slot
from auto_patch_v2.planar.overlay import Region, airside_clip, build_rim
from shapely.geometry import Polygon, box


def _clip(keep_out=None):
    law = Law.for_airport("ZZZZ")
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    apron = box(0.0, 0.0, 200.0, 100.0)
    nodes = [(float(x), 100.0) for x in range(0, 201, 5)] + [(0.0, 0.0), (200.0, 0.0)]
    rim = build_rim(apron, law, nodes)
    road = Region("service_road", "big_roads:-1", box(20.0, 100.0 + 0.6 * rim.band, 180.0, 110.0),
                  None, None, "groundside", "cell")
    out, _c = airside_clip([road], law, air=apron, nodes=nodes, rim=rim,
                           select=lambda r: True, near_m=rim.band, keep_out=keep_out)
    return out[0].polygon, grid, rim


def test_ribbon_beside_no_wall_is_welded_to_the_rim():
    got, _grid, _rim = _clip()
    assert got.bounds[1] == 100.0


def test_ribbon_never_grows_across_a_retaining_wall():
    wall = Polygon([(0.0, 100.0), (200.0, 100.0), (200.0, 100.5), (0.0, 100.5)])
    _g, grid, _rim = _clip()
    slot = wall_slot(wall, grid)
    assert slot.bounds[3] == 100.5 + grid
    got, _grid, rim = _clip(keep_out=slot)
    assert got.bounds[1] > 100.5
    assert got.intersection(wall).area == 0.0


def test_no_walls_no_slot():
    assert wall_slot(None, 0.5) is None and wall_slot(Polygon(), 0.5) is None


def test_a_zone_sliver_in_a_wall_slot_never_joins_the_road():
    """the 1 m zone sliver between an apron rim and a road with a 0.5 m
    retaining wall in it: no groundside host takes it (the DEM owns it, the
    step stands in the slot); without the wall the road takes it as before"""
    from auto_patch_v2.planar.overlay import dissolve_sliver_zones
    apron = Region("apron", "pav5", box(0.0, 0.0, 100.0, 100.0), None, None,
                   "airside", "cell")
    sliver = Region("graded_strip", "adjacent_ground:taxi:F:zone2#1", box(0.0, 100.0, 40.0, 101.0),
                    None, None, "airside", "zone")
    road = Region("service_road", "big_roads:-1", box(0.0, 101.0, 40.0, 110.0), None, None,
                  "groundside", "cell")
    faces = [(r.polygon, r) for r in (apron, sliver, road)]
    wall = box(0.0, 100.0, 40.0, 100.5)
    # the airside host refuses the sliver as a THAWED one (its nodes are new)
    kw = dict(host_roles=("apron",), air_nodes=set())
    out, n, dropped, _a, rows = dissolve_sliver_zones(
        list(faces), 50.0, 2.0, slot=wall_slot(wall, 0.5), **kw)
    assert n == 0 and dropped == 1
    assert {r.ref for _p, r in out} == {"pav5", "big_roads:-1"}
    assert [p for p, r in out if r.ref == "big_roads:-1"][0].bounds[1] == 101.0
    out, n, dropped, _a, rows = dissolve_sliver_zones(list(faces), 50.0, 2.0, **kw)
    assert n == 1 and rows[0][3] == "service_road:big_roads:-1"
