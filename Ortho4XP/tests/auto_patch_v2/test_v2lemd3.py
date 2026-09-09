"""Lane v2lemd3 twins (RULINGS 2026-09-06c; spec
``docs/specs/auto-patch-v2/lemd-read-20260906-spec.md``):

* §1 the BASEMENT test is a FRACTION (``[basin] basement_cover_min``):
  a region under its own object's above-grade solids for less than the
  fraction is a PIT (covered or open) and is cut — the pad yields
  inside it (``cuts_pads``); at or above the fraction it is a basement
  and the pad governs.  The 04i erosion test that fired at 38 % is gone.
* §2 the EDGE WALL (``[tunnel.object] edge_wall_max_plate_m``): a wall
  object with a real skirt and a low crest gives the ramp its PLAN
  (straight or curved, the width between the walls) with the crest
  flush at grade (the seat reads the crest), and its DEPTH from the bore
  law (``tunnel.bore_datum_m`` at the mouth); the bore mouth inside it
  is the object's; an edge wall with no bore mouth is refused by name.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import LineString, Point, Polygon

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.tunnel_objects import read_corridors, signature
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.pipeline.build import _plate_seats
from auto_patch_v2.planar.basins import build_basins, read_objects
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.structures import build_structures

from test_m4b import _airport as _basin_airport, _cells as _basin_cells, _rect, _two_box_obj
from test_tunnel_objects import _airport as _wall_airport, _arc_wall_obj, _bore, _cells as _wall_cells, _wall_obj


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── §1: the basement fraction ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def basin_objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    # a pit shell 60 × 40 (walls 0 → −5, floor) and, in the SAME object,
    # a roofed box over PART of it: 'half' covers ~half the region (a
    # covered pit), 'whole' covers all of it (a basement)
    half = _two_box_obj(d / "half.obj", dict(hx=30.0, hz=20.0, depth=5.0),
                        dict(hx=14.0, hz=22.0, depth=-0.5, top=8.0, lid=True))
    whole = _two_box_obj(d / "whole.obj", dict(hx=30.0, hz=20.0, depth=5.0),
                         dict(hx=32.0, hz=22.0, depth=-0.5, top=8.0, lid=True))
    return {"dir": d, "half": half, "whole": whole}


def _basins_of(objs, law, placements, cells):
    airport = _basin_airport(objs, law, placements)
    objects, rep = read_objects(airport, law)
    cl = Classification(tuple(cells), (), {}, ())
    cl3, basins, bs = build_basins(airport, cl, law, (), objects, report=rep)
    return cl, cl3, basins, bs, rep


def test_a_partly_covered_region_is_a_pit_the_pad_yields_inside(basin_objs, law):
    """2026-09-06c (1): own cover under basement_cover_min → a PIT, cut
    to its floor plate; the pad cell over it is cut back (cuts_pads)."""
    bl = law.tables.structures.basin
    assert 0.5 < bl.basement_cover_min < 1.0 and bl.cuts_pads
    cells = _basin_cells() + [Cell(4, "building", "padHalf", _rect(-30, -20, 30, 20), (),
                                   None, None, "airside", "pad", {})]
    cl, cl3, basins, bs, rep = _basins_of(basin_objs, law, [("half", (0.0, 0.0), 0.0, 0.0)], cells)
    assert rep.below_grade_objects == 1
    assert not [r for r in bs.refused if "BASEMENT" in r], bs.refused
    assert len(basins) == 1
    b = basins[0]
    assert b.kind == "covered pit"
    # the own cover is reported (about half) and lies under the fraction
    note = next(n for n in b.notes if "(own " in n)
    own = float(note.split("own ")[1].split("%")[0]) / 100.0
    assert 0.3 < own < bl.basement_cover_min
    # the pit is cut to the floor plate: a tunnel_trench face at the
    # rendered floor (the plate at −5 on the 700 + 0.005 x plane)
    floors = [c for c in cl3.cells if c.role == "tunnel_trench"]
    assert len(floors) == 1 and b.floor_z == pytest.approx(b.solid_min_z)
    assert Polygon(floors[0].ring).area > 0.8 * 60.0 * 40.0
    # the pad yielded inside: its cell no longer covers the floor
    pad = [Polygon(c.ring, c.holes) for c in cl3.cells if c.ref.startswith("padHalf")]
    floor = Polygon(floors[0].ring)
    assert all(p.intersection(floor).area < 1e-6 for p in pad)
    assert bs.cells_cut >= 1


def test_a_wholly_covered_region_is_a_basement_the_pad_governs(basin_objs, law):
    """...and at/above the fraction it is a basement: refused naming the
    pad, no cell cut."""
    cells = _basin_cells() + [Cell(4, "building", "padWhole", _rect(-30, -20, 30, 20), (),
                                   None, None, "airside", "pad", {})]
    cl, cl3, basins, bs, rep = _basins_of(basin_objs, law, [("whole", (0.0, 0.0), 0.0, 0.0)], cells)
    assert not basins
    ref = [r for r in bs.refused if "BASEMENT" in r]
    assert len(ref) == 1 and "padWhole" in ref[0] and "basement_cover_min" in ref[0]
    assert cl3.cells == cl.cells


# ── §2: the edge wall ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def wall_objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    return {
        "dir": d,
        # LEMD85's numbers: crest 1.18 m over a 4.03 m skirt, a 160 m U
        "edge": _wall_obj(d / "edge.obj", length=160.0, top=1.18, depth=4.03, end_a=True),
        # the same crest and skirt on CURVED walls
        "edge_arc": _arc_wall_obj(d / "edge_arc.obj", top=1.18, depth=4.03),
        # a full wall for the control (plate 5 m = the depth)
        "full": _wall_obj(d / "full.obj", length=160.0, end_a=True),
    }


def _sig(objs, law, name):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    path = str(objs[name])
    return signature(cache.geometry(path), cache.genuine(path), law)


def test_the_edge_wall_signature(wall_objs, law):
    ob = law.tables.structures.tunnel.object
    assert 0.0 < ob.edge_wall_max_plate_m <= ob.plate_min_height_m
    sig = _sig(wall_objs, law, "edge")
    assert not isinstance(sig, str), sig
    assert sig.edge_wall and sig.plate_y == pytest.approx(1.18) and sig.skirt_depth_m == pytest.approx(4.03)
    full = _sig(wall_objs, law, "full")
    assert not full.edge_wall and full.plate_y == pytest.approx(5.0)


def _corridors(objs, law, placements, ways):
    airport = _wall_airport(objs, law, placements, ways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, rep = read_objects(airport, law, cache)
    cs, st = read_corridors(airport, objects, cache, law)
    return airport, objects, cache, cs, st


def test_edge_wall_plan_from_the_walls_depth_from_the_bore_law(wall_objs, law):
    """The ramp's width is the walls' inner width (not lanes × lane
    width), its depth at the mouth tunnel.bore_datum_m (not the crest),
    the crest is the seat's plate, the bore mouth inside is the object's."""
    tn = law.tables.structures.tunnel
    co = law.tables.structures.cutout
    # placed with its crest at the ground (a plain OBJECT): the seat gate
    # does not apply to an edge wall; the bore ends inside the closed end
    airport, objects, cache, cs, st = _corridors(
        wall_objs, law, [("edge", (0.0, 0.0), 180.0, None, "OBJECT")], _bore(y_in=-70.0, y_open=80.0))
    assert st.corridors == 1, st.refused
    c = cs[0]
    assert c.edge_wall and c.mouth_kind == "bore"
    assert c.depth_m == pytest.approx(tn.bore_datum_m) and c.plate_y == pytest.approx(1.18)
    assert c.floor_z == pytest.approx(airport.dem.z(*c.axis[0]) - tn.bore_datum_m)
    assert any("edge wall" in n for n in c.notes)
    cl = Classification(tuple(_wall_cells(-200, -300, 200, 200)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not [r for r in sst.refused if "edge.obj" in r], sst.refused
    t = [t for t in tunnels if t.source == "object"][0]
    assert t.edge_wall and t.depth_m == pytest.approx(tn.bore_datum_m)
    assert t.plate_y_m == pytest.approx(1.18)
    assert t.mouth_z == pytest.approx(c.floor_z)
    assert -101 in t.replaced_ways            # the bore mouth inside is the object's
    # the ramp inside the walls is as wide as the walls (16 m between the
    # inner faces + the floor overlap each side), never the lanes width
    near = c.footprint.buffer(1.0)
    ramps = [Polygon(x.ring) for x in cl2.cells if x.role == "tunnel_ramp"
             and near.contains(Polygon(x.ring).centroid)]
    assert ramps
    xs = [abs(x) for r in ramps for x, y in r.exterior.coords]
    grid = law.tables.emit.identity.min_distinct_spacing_m
    assert max(xs) == pytest.approx(8.0 + co.floor_overlap_m, abs=2 * grid)
    assert max(xs) > tn.lane_width_m * 2 / 2.0 + 1.0
    # 5.1 m over 160 m fits inside the walls at 3.2 %: the ramp tops at the wall end
    assert t.top_s == pytest.approx(t.wall_length_m) and t.design_grade == pytest.approx(
        tn.bore_datum_m / t.wall_length_m)
    # the seat reads the CREST: plate 1.18 for the placement
    pm, stats = build(airport, cl, law)
    seats = _plate_seats(pm, law)
    assert seats["dsf:obj0"][0] == pytest.approx(1.18)


def test_edge_wall_follows_its_curve(wall_objs, law):
    """The PLAN is the walls': a curved edge wall bends the ramp — no
    chord, no vertex outside the inner faces ⊕ floor_overlap_m."""
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2"}
    bore = (OsmWay(-501, "big_roads", ((150.0, -5.0), (150.0, 400.0)), False, tags_t),)
    airport, objects, cache, cs, st = _corridors(
        wall_objs, law, [("edge_arc", (0.0, 0.0), 0.0, None, "OBJECT")], bore)
    assert st.corridors == 1, st.refused
    c = cs[0]
    assert c.edge_wall and c.mouth_kind == "bore"
    a, b = c.axis[0], c.axis[-1]
    mid = c.axis[len(c.axis) // 2]
    assert LineString([a, b]).distance(Point(mid)) > 5.0
    cl = Classification(tuple(_wall_cells(-400, -400, 400, 400)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not [r for r in sst.refused if "edge_arc.obj" in r], sst.refused
    t = [t for t in tunnels if t.source == "object"][0]
    assert t.trench_outside_max_m == 0.0 and t.edge_wall
    grid = law.tables.emit.identity.min_distinct_spacing_m
    co = law.tables.structures.cutout
    region = c.trench.buffer(co.floor_overlap_m + grid * math.sqrt(2.0) + 1e-6,
                             join_style="mitre", mitre_limit=2.0)
    near = c.footprint.buffer(5.0)
    ramps = [Polygon(x.ring) for x in cl2.cells if x.role == "tunnel_ramp"
             and near.contains(Polygon(x.ring).centroid)]
    assert ramps
    for r in ramps:
        for p in r.exterior.coords:
            assert region.contains(Point(p)), p


def test_edge_wall_without_a_bore_is_refused_by_name(wall_objs, law):
    """RULINGS 2026-09-08l/08o: the bore law's depth applies to EVERY mouth
    kind, so an edge wall with no bore is no longer refused for want of a
    depth — but its closed-end fallback with NO mapped road through the
    trench is refused by name (a wall around nothing)."""
    airport, objects, cache, cs, st = _corridors(
        wall_objs, law, [("edge", (0.0, 0.0), 180.0, None, "OBJECT")], ())
    assert st.corridors == 0
    assert any("closed-end fallback" in r and "no mapped road" in r for r in st.refused), st.refused
