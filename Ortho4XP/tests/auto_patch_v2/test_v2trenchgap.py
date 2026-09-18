"""Lane v2trenchgap twins, RE-FOUNDED on §47 (lane `v2wallface`, owner
RULINGS 2026-09-17h/17j): THE TRENCH RINGS SIT ON THE WALL'S FACES.

08a moved the rim INSIDE the wall by ``rim_inset_fraction`` and floored
its stand-off at the identity spacing; §47 supersedes both for an OBJECT
WALL — the floor ring IS the inner face, the rim ring IS the outer face,
and the band between them is the wall's own measured thickness ``t``.

* the law: ``rim_standoff(t)`` returns ``(0, t)`` for every wall at or
  above the MEASURED lattice floor ``cutout.ring_floor_m``, and
  ``(t − F, F)`` — a rim YIELDED outward by ``F − t`` — below it;
* the mesh wall band (rim → floor ring) under 08a against §47, for
  OTHH's 1.0 m tunnel walls, its 0.75 m drainage shells and its 0.55 /
  0.25 m Dewatering shells;
* the corridor product: a 1 m wall object's emitted floor ring IS its
  inner faces and its rim IS the outer faces — 1.00 m apart, not 0.50;
* the basin product: a zero-thickness shell's rim yields to ``F`` and
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
from auto_patch_v2.planar.structure_geometry import rim_standoff, rim_yield_m
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


def _law_08a_band(t: float, co, spacing: float) -> float:
    """The 08a band this lane supersedes: ``max(t − overlap − 0.5·t,
    spacing)`` — a 1 m wall read 0.50 m, a 0.75 m shell 0.50 m."""
    return max(t - co.floor_overlap_m - co.rim_inset_fraction * t, spacing)


def test_the_rule(law):
    """§47 (1)/(3): the rim IS the outer face (inset 0) and the band IS
    ``t`` — floored at the MEASURED ``ring_floor_m``, where the rim yields
    outward instead and the floor never moves."""
    co = law.tables.structures.cutout
    sp = law.tables.emit.identity.min_distinct_spacing_m
    F = co.ring_floor_m
    assert F == pytest.approx(0.7071) and sp == 0.5
    # every wall at or above F: the rim ON the outer face, band = t
    for t in (0.75, 1.0, 2.0, 2.5):
        inset, standoff = rim_standoff(t, co)
        assert inset == pytest.approx(0.0)
        assert standoff == pytest.approx(t)
        assert rim_yield_m(t, co) == pytest.approx(0.0)
    # OTHH's two Dewatering shells (0.25 / 0.55 m) cannot hold two
    # distinct rings: the FLOOR stays on the inner face and the RIM
    # yields outward by F − t (§47 (3)), reported by name
    for t in (0.25, 0.55):
        inset, standoff = rim_standoff(t, co)
        assert standoff == pytest.approx(F)
        assert inset == pytest.approx(t - F)          # NEGATIVE: outside the outer face
        assert rim_yield_m(t, co) == pytest.approx(F - t)
    # neither retired key names the pair any more
    assert rim_standoff(1.0, co)[1] != _law_08a_band(1.0, co, sp)
    # ...and the identity spacing is no longer the floor: F is
    assert rim_standoff(0.0, co)[1] == pytest.approx(F) != sp


def test_band_width_before_after(law):
    """The mesh wall band (rim → floor ring), OTHH's own shells: 08a
    against §47.  1.00 m side walls 0.50 → 1.00; 0.75 m drainage shells
    0.50 → 0.75; the 0.55 / 0.25 m Dewatering shells 0.50 → 0.7071 (the
    yield), and the rim now stands OUTSIDE their outer face, not 0.4 m
    outside the INNER one as 08a left it."""
    co = law.tables.structures.cutout
    sp = law.tables.emit.identity.min_distinct_spacing_m
    F = co.ring_floor_m
    for t, before, after in ((1.00, 0.50, 1.00), (0.75, 0.50, 0.75),
                             (0.55, 0.50, F), (0.25, 0.50, F)):
        assert _law_08a_band(t, co, sp) == pytest.approx(before, abs=1e-9)
        assert rim_standoff(t, co)[1] == pytest.approx(after)
    # 08a put a 1 m wall's rim 0.2 m inside its outer face BY LAW (and
    # 0.4 m OUTSIDE it in practice, the 08e OWED deviation (2)); §47 puts
    # it ON the face, and the emit path may not leave it (§47 (2))
    assert co.floor_overlap_m + _law_08a_band(1.0, co, sp) == pytest.approx(0.8)
    assert rim_standoff(1.0, co)[1] == pytest.approx(1.0)


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
    inset, standoff = rim_standoff(t_l, co)
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
    # §47 (1): the floor ring IS the inner faces — the ramp is the trench
    # itself now, not the trench ⊕ 0.3 m (the 08a overlap is retired and
    # the outward ``snap_out`` with it, §47 (2))
    assert ramp_u.area == pytest.approx(c.trench.area, rel=0.02)
    assert c.trench.exterior.distance(ramp_u.exterior) <= grid + 1e-6
    # the rim: ON the walls' OUTER faces — inside their plan footprint ⊕
    # one grid rounding, never under the band (= the wall's own thickness)
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
    # §47 (1): the band IS the 1 m wall's thickness — where 08a's rim
    # stood 0.50 m off the ramp (0.2 m inside the outer face by law, and
    # measured 0.4 m OUTSIDE it at OTHH site 1), it now stands on the face
    assert standoff == pytest.approx(t_l)
    assert standoff > _law_08a_band(t_l, co, grid) + 1e-6
    assert max(dists) <= standoff + grid + 1e-6


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
    # §47 (3): a ZERO-thickness authored shell (the m4b pit) cannot hold
    # two rings at all — its rim yields outward to the lattice floor
    _inset, standoff = rim_standoff(0.0, co)
    assert standoff == pytest.approx(co.ring_floor_m)
    assert rim_yield_m(0.0, co) == pytest.approx(co.ring_floor_m)
    assert wp.exterior.distance(fp) >= standoff - 1e-6
    assert any("stand-off" in n for n in b.notes)
    region = Polygon([(-30, -20), (30, -20), (30, 20), (-30, 20)])
    plate = region.buffer(-0.75, join_style="mitre")
    assert shell_thickness_m(region, plate) == pytest.approx(0.75, abs=0.02)
    assert shell_thickness_m(region, region) == 0.0
