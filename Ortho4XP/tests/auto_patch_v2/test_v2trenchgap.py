"""Lane v2trenchgap twins (RULINGS 2026-09-08a; spec
``docs/specs/auto-patch-v2/othh-read-20260906-spec.md`` §1a): the
at-grade rim moves INSIDE the wall object's footprint.

* the law: ``rim_standoff(t)`` — a 1 m wall's rim stands 0.5 m inside its
  outer face and the identity spacing off the floor ring; a 0.4 m shell
  (half its thickness under the spacing) has the spacing bind: its rim
  stands at ``floor_overlap_m + spacing`` outside the inner face — at or
  outside the outer face; the floor ring is untouched;
* the mesh wall band width (rim → floor ring) before (§1: the wall's
  thickness − overlap + gap = its thickness) and after (§1a: the
  stand-off) for OTHH's 1.0 m tunnel walls and a 0.75 m drainage shell;
* the corridor product: a 1 m wall object's emitted rim vertices stand
  inside the walls' footprint and exactly the stand-off off the ramp;
  the ramp edges (inner face ⊕ overlap) do not move;
* the basin product: the pit's rim clears its floor by the stand-off and
  ``shell_thickness_m`` reads a 0.75 m shell.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import shell_thickness_m
from auto_patch_v2.planar.structure_geometry import rim_standoff
from auto_patch_v2.planar.structures import build_structures

from test_m4b import _basins_of
from test_m4b import objs as basin_objs  # noqa: F401  (fixture)
from test_tunnel_objects import _cells, _corridors, _wall_obj


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    return {"dir": d,
            "wall1": _wall_obj(d / "wall1.obj", thick=1.0, end_a=True)}   # U, 1 m walls


def _section_1_band(t: float, co) -> float:
    """§1 (2026-09-06b) as it stood: the rim = outer face ⊕ 0.3 m, the
    floor ring = inner face ⊕ overlap — band = t − overlap + 0.3."""
    return max(t - co.floor_overlap_m, 0.0) + 0.3


def test_the_rule(law):
    co = law.tables.structures.cutout
    sp = law.tables.emit.identity.min_distinct_spacing_m
    assert co.rim_inset_fraction == 0.5 and co.floor_overlap_m == 0.3 and sp == 0.5
    # a 1 m wall: the rim 0.5 m inside its outer face; the stand-off from
    # the floor ring (inner face + 0.3) is 1.0 − 0.3 − 0.5 = 0.2, floored
    # at the identity spacing
    inset, standoff = rim_standoff(1.0, co, sp)
    assert inset == pytest.approx(0.5) and standoff == pytest.approx(sp)
    rim_from_inner = co.floor_overlap_m + standoff
    assert 1.0 - rim_from_inner == pytest.approx(0.2)         # inside the outer face
    # a 0.4 m shell: half its thickness (0.2) is under the spacing — the
    # spacing binds and the rim stands at overlap + spacing = 0.8 m off
    # the inner face: 0.4 m OUTSIDE the outer face (the law's thin-shell
    # rule; the outer face itself is reached at t = 0.8)
    inset, standoff = rim_standoff(0.4, co, sp)
    assert inset == pytest.approx(0.2) and standoff == pytest.approx(sp)
    assert co.floor_overlap_m + standoff - 0.4 == pytest.approx(0.4)
    inset, standoff = rim_standoff(0.8, co, sp)
    assert co.floor_overlap_m + standoff == pytest.approx(0.8)  # at the outer face
    # OTHH's end walls (2.0-2.5 m): the rim at half, the band 0.7-0.95
    for t in (2.0, 2.5):
        inset, standoff = rim_standoff(t, co, sp)
        assert inset == pytest.approx(t / 2.0)
        assert standoff == pytest.approx(t - co.floor_overlap_m - t / 2.0)
        assert standoff > sp
    # the floor ring is not the rule's to move: only the overlap names it
    assert co.floor_overlap_m == 0.3


def test_band_width_before_after(law):
    """The mesh wall band (rim → floor ring), OTHH: the 1.0 m tunnel side
    walls 1.00 → 0.50 m; a 0.75 m drainage shell 0.75 → 0.50 m (the
    spacing binds: its rim 0.05 m outside the outer face)."""
    co = law.tables.structures.cutout
    sp = law.tables.emit.identity.min_distinct_spacing_m
    assert _section_1_band(1.0, co) == pytest.approx(1.0)
    assert rim_standoff(1.0, co, sp)[1] == pytest.approx(0.5)
    assert _section_1_band(0.75, co) == pytest.approx(0.75)
    inset, standoff = rim_standoff(0.75, co, sp)
    assert inset == pytest.approx(0.375) and standoff == pytest.approx(0.5)
    assert co.floor_overlap_m + standoff - 0.75 == pytest.approx(0.05)


def test_corridor_rim_inside_the_wall_floor_untouched(objs, law):
    """A 1 m wall object: every side rim vertex stands inside the walls'
    footprint (⊕ the grid's rounding) and ≥ the stand-off off the ramp,
    the nearest at exactly the stand-off; the ramp's edges are the inner
    faces ⊕ floor_overlap_m as before."""
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    bore = (OsmWay(-101, "big_roads", ((0.0, -40.0), (0.0, -400.0)), False, tags_t),
            OsmWay(-201, "big_roads", ((0.0, -400.0), (0.0, -1300.0)), False,
                   {"highway": "secondary", "lanes": "2"}))
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall1", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")], bore)
    assert st.corridors == 1, st.refused
    c = cs[0]
    co = law.tables.structures.cutout
    grid = law.tables.emit.identity.min_distinct_spacing_m
    t_l = c.stations[len(c.stations) // 2].thick_l
    assert t_l == pytest.approx(1.0, abs=0.05)
    inset, standoff = rim_standoff(t_l, co, grid)
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not [r for r in sst.refused if "wall1.obj" in r], sst.refused
    t = [x for x in tunnels if x.source == "object"][0]
    assert t.trench_outside_max_m == 0.0                       # the floor ring: inner ⊕ overlap
    near = c.footprint.buffer(5.0)
    # the object's own pieces: the ones INTERSECTING the footprint (a void's
    # centroid drifts with the ramp beyond the walls — 2026-09-08l moved the
    # depth to bore_datum_m and the climb 2.5 m further out)
    ramps = [Polygon(x.ring) for x in cl2.cells if x.role == "tunnel_ramp"
             and near.intersects(Polygon(x.ring))]
    walls = [Polygon(x.ring, x.holes) for x in cl2.cells if x.role == "retaining_wall"
             and near.intersects(Polygon(x.ring, x.holes))]
    assert ramps and walls
    ramp_u = unary_union(ramps)
    # the floor overlaps the inner faces by the overlap (and the grid's outward snap)
    assert ramp_u.contains(c.trench)
    assert c.trench.exterior.distance(ramp_u.exterior) <= co.floor_overlap_m + grid + 1e-6
    # the rim: inside the walls' plan footprint (⊕ one grid rounding),
    # never under the stand-off off the ramp, and touching it somewhere
    inside = c.walls.buffer(grid + 1e-6)
    dists = []
    for w in walls:
        for p in w.exterior.coords:
            d = ramp_u.exterior.distance(Point(p))
            if d < 1e-6:
                continue                     # the U void's exterior runs along the ramp
            if not c.walls.buffer(3.0 * t_l).contains(Point(p)):
                continue                     # the climb beyond the walls (OSM law)
            dists.append(d)
            assert inside.contains(Point(p)), p
            assert d >= standoff - 1e-6, (p, d)
    # §34 (7) (RULINGS 2026-09-14p): a straight constant-thickness corridor
    # emits its END CHORDS and nothing between, so this rim is a handful of
    # points, not one per 2 m station — what is measured is the STAND-OFF
    assert len(dists) >= 8
    assert min(dists) == pytest.approx(standoff, abs=1e-6)
    # §1 put this rim 1.0 m off the ramp (outside the wall): it is 0.5 now
    assert max(dists) < _section_1_band(t_l, co) - 1e-6


def test_basin_rim_stand_off_and_shell_thickness(basin_objs, law):  # noqa: F811
    """The m4b pit (zero-thickness authored walls): the rim clears the
    floor by the stand-off (the spacing binds); ``shell_thickness_m``
    reads a 0.75 m band between a 60 × 40 footprint and its plate."""
    co = law.tables.structures.cutout
    grid = law.tables.emit.identity.min_distinct_spacing_m
    cl, cl3, basins, bs, rep = _basins_of(basin_objs, law, [("pit", (0.0, 0.0), 0.0, 0.0)])
    assert len(basins) == 1 and not bs.refused, bs.refused
    b = basins[0]
    floor = next(c for c in cl3.cells if c.ref == b.floor_ref)
    wall = next(c for c in cl3.cells if c.ref == b.wall_ref)
    fp, wp = Polygon(floor.ring), Polygon(wall.ring, wall.holes)
    _inset, standoff = rim_standoff(0.0, co, grid)
    assert standoff == grid
    assert wp.exterior.distance(fp) >= standoff - 1e-6
    assert any("stand-off" in n for n in b.notes)
    region = Polygon([(-30, -20), (30, -20), (30, 20), (-30, 20)])
    plate = region.buffer(-0.75, join_style="mitre")
    assert shell_thickness_m(region, plate) == pytest.approx(0.75, abs=0.02)
    assert shell_thickness_m(region, region) == 0.0
