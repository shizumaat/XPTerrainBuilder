"""Twins for the tunnel wall OBJECTS as the tunnel authority — round 2
(RULINGS 2026-09-05n; spec ``docs/specs/auto-patch-v2/tunnel-wall-
objects-round2-spec.md`` §4): the wall lines read from the crest plate's
plan ring (a U, an O, two bands; a CURVED pair of walls), the trench
between the inner faces with no vertex outside the walls and the band =
the wall footprint, the mouth chosen by the bore, the floor at the mouth
= ground − plate height, the ramp inside the walls (and beyond only at
``ramp_max_grade`` when the walls are too short), a bore covered at one
end keeping its OSM ramp at the other, a box on the bore flat at the
mouth depth, the plate re-seat (delta = ground − rendered plate, exempt
from the 1 m threshold, one file one delta), the SAME ``Tunnel`` product
through the generator / solve / verify readers, and the law register.
Law values are read from the tables inside the tests, never retyped.
"""
from __future__ import annotations

import json
import math

import pytest
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.rebake_plan import plan as rebake_plan
from auto_patch_v2.airport.tunnel_objects import read_corridors, signature
from auto_patch_v2.airport.tunnel_walls import read_wall_lines
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import ramp_faces_of, structures, wall_faces_of
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.rebake import DATUM_PLATE, seat
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, DsfObject, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.structures import build_structures
from auto_patch_v2.solve import Options, Status, solve_design
from auto_patch_v2.verify import census


class _PlaneDem:
    provenance = {"synthetic": "plane 0.5 % up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.005 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


# ── synthetic OBJ8 text ──────────────────────────────────────────────────

def _write(path, vt, tris):
    lines = ["A", "800", "OBJ", "", "TEXTURE none", f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    lines += ["IDX " + " ".join(str(i) for i in idx[k:k + 10]) for k in range(0, len(idx), 10)]
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return path


def _prism(vt, tris, quad, y0, y1):
    """A vertical prism over the plan quad ``quad`` (4 × (x, z), in
    order): four sides and a top, no bottom."""
    b = len(vt)
    for x, z in quad:
        vt.append((x, y0, z))
        vt.append((x, y1, z))
    for k in range(4):
        i, j = b + 2 * k, b + 2 * ((k + 1) % 4)
        tris += [(i, i + 1, j + 1), (i, j + 1, j)]
    tris += [(b + 1, b + 3, b + 5), (b + 1, b + 5, b + 7)]


def _slab(vt, tris, x0, x1, z0, z1, y0, y1):
    _prism(vt, tris, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y0, y1)


def _wall_obj(path, length=100.0, width=20.0, thick=2.0, depth=12.0, top=5.0,
              end_a=False, end_b=False, floor=False):
    """Two parallel wall slabs along z (authored), ``top`` above the seat,
    ``depth`` below it; an end wall across z = −L/2 (``end_a``) / +L/2
    (``end_b``); a floor plate at −depth (``floor``)."""
    vt: list = []
    tris: list = []
    hx, hz = width / 2.0, length / 2.0
    _slab(vt, tris, -hx, -hx + thick, -hz, hz, -depth, top)
    _slab(vt, tris, hx - thick, hx, -hz, hz, -depth, top)
    if end_a:
        _slab(vt, tris, -hx + thick, hx - thick, -hz, -hz + thick, -depth, top)
    if end_b:
        _slab(vt, tris, -hx + thick, hx - thick, hz - thick, hz, -depth, top)
    if floor:
        b = len(vt)
        vt += [(-hx, -depth, -hz), (hx, -depth, -hz), (hx, -depth, hz), (-hx, -depth, hz)]
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    return _write(path, vt, tris)


def _arc_wall_obj(path, radius=150.0, sweep_deg=60.0, width=20.0, thick=1.0, depth=12.0,
                  top=5.0, step_deg=3.0):
    """Two CURVED walls (arcs about the authored origin, ``width`` apart
    between their inner faces) joined by an end wall at the arc's start —
    a U whose side walls bend ``sweep_deg``."""
    vt: list = []
    tris: list = []
    n = int(round(sweep_deg / step_deg))
    angs = [math.radians(k * step_deg) for k in range(n + 1)]

    def pt(r, a):
        return (r * math.cos(a), r * math.sin(a))
    for r_in, r_out in ((radius - width / 2.0 - thick, radius - width / 2.0),
                        (radius + width / 2.0, radius + width / 2.0 + thick)):
        for a0, a1 in zip(angs[:-1], angs[1:]):
            _prism(vt, tris, [pt(r_in, a0), pt(r_out, a0), pt(r_out, a1), pt(r_in, a1)], -depth, top)
    # the end wall across the start (angle 0 .. thick/r): overlapping the
    # side walls' bands, so the plate is ONE welded ring (a U)
    a0, a1 = angs[0], math.radians(math.degrees(thick / radius))
    ri, ro = radius - width / 2.0 - thick / 2.0, radius + width / 2.0 + thick / 2.0
    _prism(vt, tris, [pt(ri, a0), pt(ro, a0), pt(ro, a1), pt(ri, a1)], -depth, top)
    return _write(path, vt, tris)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    return {
        "dir": d,
        "wall": _wall_obj(d / "wall.obj", end_a=True),                        # U, 100 m
        "wall_long": _wall_obj(d / "wall_long.obj", length=160.0, end_a=True),  # U, 160 m
        "wall_open": _wall_obj(d / "wall_open.obj"),                          # two bands
        "wall_box": _wall_obj(d / "wall_box.obj", end_a=True, end_b=True),     # O
        "arc": _arc_wall_obj(d / "arc.obj"),                                  # curved U
        "floored": _wall_obj(d / "floored.obj", end_a=True, floor=True),
        "kerb": _wall_obj(d / "kerb.obj", depth=12.0, top=0.3),
        "shallow": _wall_obj(d / "shallow.obj", depth=1.0, top=5.0),
        "stub": _wall_obj(d / "stub.obj", length=6.0, width=8.0, thick=3.0),
    }


def _sig(objs, law, name):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    path = str(objs[name])
    return signature(cache.geometry(path), cache.genuine(path), law)


# ── the signature and the wall lines ─────────────────────────────────────

def test_signature_and_wall_lines(objs, law):
    ob = law.tables.structures.tunnel.object
    sig = _sig(objs, law, "wall")
    assert not isinstance(sig, str), sig
    assert sig.plate_y == pytest.approx(5.0)
    assert sig.plate_area_m2 >= ob.plate_min_area_m2 and sig.skirt_depth_m == pytest.approx(12.0)
    # the plate's plan ring is the walls: a U (one end wall), 2 m bands,
    # the inner faces 16 m apart
    w = read_wall_lines(sig.plate, law)
    assert not isinstance(w, str), w
    assert w.kind == "U" and w.closed == (True, False)
    assert w.thickness_m == pytest.approx(2.0, abs=0.05)
    assert w.end_thickness_m[0] == pytest.approx(2.0, abs=0.05)
    assert LineString(w.inner_a).distance(LineString(w.inner_b)) == pytest.approx(16.0, abs=0.01)
    box = read_wall_lines(_sig(objs, law, "wall_box").plate, law)
    assert box.kind == "O" and box.closed == (True, True)
    two = read_wall_lines(_sig(objs, law, "wall_open").plate, law)
    assert two.kind == "II" and two.closed == (False, False)
    arc = read_wall_lines(_sig(objs, law, "arc").plate, law)
    assert arc.kind == "U" and arc.closed == (True, False)
    assert arc.thickness_m == pytest.approx(1.0, abs=0.05)


def test_refusals_name_their_reason(objs, law):
    # RULINGS 2026-09-08l: a floor slab is DEPTH EVIDENCE, never a refusal
    # (the basin pass still owns a floor it witnessed, by witness)
    floored = _sig(objs, law, "floored")
    assert not isinstance(floored, str), floored
    assert floored.floor_y == pytest.approx(-12.0) and floored.plate_y == pytest.approx(5.0)
    # RULINGS 2026-09-06c (2): a low crest over a real (12 m) skirt is an
    # EDGE WALL signature, not a kerb refusal (test_v2lemd3 reads it);
    # the kerb refusal stays for a crest between the two keys
    kerb = _sig(objs, law, "kerb")
    assert not isinstance(kerb, str) and kerb.edge_wall and kerb.plate_y == pytest.approx(0.3)
    # RULINGS 2026-09-06f: a wall whose skirt below the SEAT is shallow
    # (1 m) reads its crest as its top band — an EDGE WALL signature
    # (skirt 6 m below the crest); it builds only around a bore mouth
    # (test_v2lemd4).  Round 2's "no wall skirt" refusal is now for a
    # wall too low for either reading (edge_wall_min_skirt_m).
    shallow = _sig(objs, law, "shallow")
    assert not isinstance(shallow, str) and shallow.edge_wall
    assert shallow.plate_y == pytest.approx(5.0) and shallow.skirt_depth_m == pytest.approx(6.0)
    assert "stub" in _sig(objs, law, "stub")


# ── the synthetic airport ────────────────────────────────────────────────

def _airport(objs, law, placements, ways=()):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", str(objs["dir"].parent / "Earth nav data" / "apt.dat"), "0", (), ())
    dsf = tuple(DsfObject(f"dsf:obj{i}", f"objects/{name}.obj", xy, hd, None, False, None, elev,
                          str(objs[name]), kind)
                for i, (name, xy, hd, elev, kind) in enumerate(placements))
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (), (), (), (),
                   tuple(ways), (), dsf, pack, _PlaneDem(), law.ruleset_key)


def _cells(x0=-200, y0=-120, x1=200, y1=120):
    return [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(x0, y0, x1, y1), (), None, None,
             "airside", "apron", {}),
    ]


def _bore(y_in=-40.0, y_far=-400.0, y_open=50.0):
    """A mapped bore ending at ``y_in`` (inside a wall object placed at the
    origin, heading 180: its closed end is at −y) and running on under
    the ground to ``y_far``; the approach way beyond the far mouth, and a
    mapped road leaving the object's open end (``y_open``) toward +y."""
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    tags_r = {"highway": "secondary", "lanes": "2"}
    return (OsmWay(-101, "big_roads", ((0.0, y_in), (0.0, y_far)), False, tags_t),
            OsmWay(-201, "big_roads", ((0.0, y_far), (0.0, y_far - 900.0)), False, tags_r),
            OsmWay(-202, "big_roads", ((0.0, y_open), (0.0, 300.0)), False, tags_r))


def _corridors(objs, law, placements, ways=()):
    airport = _airport(objs, law, placements, ways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, rep = read_objects(airport, law, cache)
    cs, st = read_corridors(airport, objects, cache, law)
    return airport, objects, cache, cs, st


# ── §4: the curved walls ─────────────────────────────────────────────────

def test_curved_walls_trench_between_inner_faces(objs, law):
    """05n-2: the trench follows the walls' curves and never leaves them;
    the wall band is the wall footprint; no rectangle anywhere."""
    # the arc's end wall stands at authored (150, 0) = frame (150, 0); the
    # bore ends just inside it and runs away to +y
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2"}
    bore = (OsmWay(-501, "big_roads", ((150.0, -5.0), (150.0, 400.0)), False, tags_t),)
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("arc", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL")], bore)
    assert st.corridors == 1, st.refused
    c = cs[0]
    assert c.mouth_kind == "bore" and c.mouth_closed
    # the axis bends: its middle stands off the chord by the sagitta
    a, b = c.axis[0], c.axis[-1]
    mid = c.axis[len(c.axis) // 2]
    chord = LineString([a, b])
    assert chord.distance(Point(mid)) > 5.0
    cl = Classification(tuple(_cells(-400, -400, 400, 400)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    # (the bore's far OSM mouth climbs toward the runway and is refused
    # on its own account; the object corridor is what this twin reads)
    assert not [r for r in sst.refused if "arc.obj" in r], sst.refused
    t = [t for t in tunnels if t.source == "object"][0]
    assert t.trench_outside_max_m == 0.0
    near = c.footprint.buffer(5.0)
    ramps = [Polygon(x.ring) for x in cl2.cells if x.role == "tunnel_ramp"
             and near.contains(Polygon(x.ring).centroid)]
    walls = [Polygon(x.ring, x.holes) for x in cl2.cells if x.role == "retaining_wall"
             and near.contains(Polygon(x.ring).centroid)]
    assert ramps and walls
    # 05n-2 as 2026-09-06b (1) amends it: no trench vertex outside the
    # inner lines ⊕ floor_overlap_m (0.0 above); and none further than one
    # identity-grid step past that either (the snapped end-line vertices)
    grid = law.tables.emit.identity.min_distinct_spacing_m
    co = law.tables.structures.cutout
    region = c.trench.buffer(co.floor_overlap_m + grid * math.sqrt(2.0) + 1e-6,
                             join_style="mitre", mitre_limit=2.0)
    for r in ramps:
        for p in r.exterior.coords:
            assert region.contains(Point(p)), p
    # the floor OVERLAPS the inner faces: the ramp is wider than the trench
    assert max(r.area for r in ramps) > c.trench.area
    # every RIM vertex (the void's exterior) stands INSIDE the walls'
    # footprint (09-08a: rim_standoff of the 1 m wall = the identity
    # spacing off the ramp), rounded AWAY from the ramp in grid steps —
    # never more (a hull rectangle would be tens of metres); the void's
    # holes are the ramp itself (shared vertices, no band between)
    from auto_patch_v2.planar.structure_geometry import rim_standoff
    _inset, standoff = rim_standoff(c.stations[0].thick_l, co, grid)
    plate = c.walls.buffer(4 * grid + 1e-6)
    ramp_u = unary_union(ramps)
    n_rim = 0
    for w in walls:
        for p in w.exterior.coords:
            if ramp_u.exterior.distance(Point(p)) < 1e-6:
                continue                  # the U void's exterior runs along the ramp too
            n_rim += 1
            assert plate.contains(Point(p)), p
            assert ramp_u.exterior.distance(Point(p)) >= standoff - 1e-6
    assert n_rim > 10
    assert sum(w.area for w in walls) < 1.5 * c.walls.area


# ── §4: the mouth, the floor, the ramp inside / beyond the walls ─────────

def test_mouth_by_bore_floor_ground_minus_plate_ramp_inside_walls(objs, law):
    """05n-1: mouth = the bore end (the closed end); floor = ground(mouth)
    − plate; a 160 m wall holds the 5 m at 3.2 % — the ramp tops AT the
    wall end at the design grade."""
    tn = law.tables.structures.tunnel
    dem = _PlaneDem()
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall_long", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")], _bore(y_in=-70.0, y_open=80.0))
    assert st.corridors == 1, st.refused
    c = cs[0]
    assert c.mouth_kind == "bore" and c.mouth_closed and not c.far_closed and not c.flat
    assert c.axis[0][1] < c.axis[-1][1]          # the mouth is the −y (closed) end
    # RULINGS 2026-09-08l: no floor slab -> the bore law's depth, never the crest
    assert c.depth_m == pytest.approx(law.tables.structures.tunnel.bore_datum_m)
    assert c.floor_z == pytest.approx(dem.z(*c.axis[0]) - law.tables.structures.tunnel.bore_datum_m)
    assert c.plate_y == pytest.approx(5.0)
    cl = Classification(tuple(_cells(-200, -300, 200, 200)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not sst.refused, sst.refused
    t = [t for t in tunnels if t.source == "object"][0]
    assert t.mouth_z == pytest.approx(c.floor_z) and t.climb_from_s == 0.0
    assert t.top_s == pytest.approx(t.wall_length_m) and t.top_pinned
    assert 0.0 < t.design_grade < tn.ramp_max_grade
    assert t.design_grade == pytest.approx(tn.bore_datum_m / t.wall_length_m)   # 2026-09-08l
    assert t.mouth_kind == "bore" and t.ground_kind == "open"


def test_wall_too_short_ramp_beyond_at_ramp_max_grade(objs, law):
    """A 100 m wall cannot hold 5 m at 4 %: the ramp continues beyond the
    wall end at exactly ``ramp_max_grade`` along the approach."""
    tn = law.tables.structures.tunnel
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")], _bore(y_in=-40.0))
    assert st.corridors == 1, st.refused
    cl = Classification(tuple(_cells(-200, -300, 200, 200)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not sst.refused, sst.refused
    t = [t for t in tunnels if t.source == "object"][0]
    assert t.top_s > t.wall_length_m and t.design_grade == pytest.approx(tn.ramp_max_grade)
    # the climb beyond: the existing ramp machinery — the depth at
    # ramp_max_grade over the DIRECT distance from the mouth (the census
    # prices ring pairs over the chord: 2 × half off the axis), plus one
    # station of slack
    half = t.half_width_m
    need = 5.0 / tn.ramp_max_grade + 2.0 * half
    spacing = law.tables.emit.chords.station_spacing_m
    assert need <= t.top_s <= need + 2.0 * spacing
    # the ramp beyond the walls runs down the approach way (x = 0)
    assert all(abs(x) < 0.5 for x, y in t.axis)


# ── §4: precedence per mouth ─────────────────────────────────────────────

def test_bore_covered_at_one_end_keeps_its_osm_ramp_at_the_other(objs, law):
    """05n-3: the bore's mouth inside the object is the object's; its far
    mouth (under the apron, outside every object) keeps its OSM ramp."""
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall_long", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")],
        _bore(y_in=-70.0, y_far=-400.0, y_open=80.0))
    cl = Classification(tuple(_cells(-200, -600, 200, 200)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not sst.refused, sst.refused
    assert sst.mouths_replaced_by_object == 1 and sst.bores_replaced_by_object == 0
    assert sst.mouths == 1 and sst.tunnels == 2
    kinds = sorted(t.source for t in tunnels)
    assert kinds == ["object", "osm"]
    osm = [t for t in tunnels if t.source == "osm"][0]
    assert osm.axis[0][1] == pytest.approx(-400.0, abs=1.0)
    assert any("one mouth inside" in r for r in sst.bore_precedence)
    obj = [t for t in tunnels if t.source == "object"][0]
    assert obj.replaced_ways == (-101,)


def test_box_on_the_bore_is_flat_at_the_mouth_depth(objs, law):
    """A box the bore passes through (OTHH tunnel west 1) has two bore
    mouths: no ground end, the trench flat at ground − plate."""
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2"}
    bore = (OsmWay(-301, "big_roads", ((0.0, 300.0), (0.0, -300.0)), False, tags_t),)
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall_box", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL")], bore)
    assert st.corridors == 1, st.refused
    c = cs[0]
    assert c.flat and c.mouth_kind == "bore" and c.ground_kind == "bore"
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    # (the bore's own mouths at ±300 stand outside the box: OSM ramps,
    # 05n-3 — the +y one climbs toward the runway and is refused on its
    # own account)
    assert not [r for r in sst.refused if "wall_box" in r], sst.refused
    t = [t for t in tunnels if t.source == "object"][0]
    assert t.capped and t.far_capped and not t.top_pinned
    assert t.climb_from_s == pytest.approx(t.top_s) and t.design_grade == 0.0


# ── the SAME Tunnel product through the readers ──────────────────────────

@pytest.fixture(scope="module")
def corridor_map(objs, law):
    # the apron covers the mouth end only: the walls' far stations stand
    # on BARE ground (their crest the DEM), the near ones share the apron
    airport = _airport(objs, law, [("wall_long", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL")],
                       _bore(y_in=-70.0, y_open=80.0))
    cl = Classification(tuple(_cells(-200, -300, 200, -60)), (), {}, ())
    pm, stats = build(airport, cl, law)
    return airport, pm, stats


def test_generator_rows_solve_and_verify(corridor_map, law, tmp_path):
    airport, pm, stats = corridor_map
    tn = law.tables.structures.tunnel
    objs_t = [t for t in pm.structures if t.source == "object"]
    assert len(objs_t) == 1
    t = objs_t[0]
    rows = structures(pm, law, airport)
    pins = {r.v: r for r in rows if isinstance(r, Pin)}
    walls = wall_faces_of(pm, pm.structures)[t.id]
    ramps = ramp_faces_of(pm, pm.structures)[t.id]
    assert walls and ramps
    dem = _PlaneDem()
    bare = 0
    for f in walls:
        for v in pm.ring_vertices(f.ring):
            ground = any(pm.faces[x].role not in ("tunnel_ramp", "retaining_wall")
                         for x in pm.vertices[v].incident_faces)
            if v in pins and not ground and "plate_datum = ground" in pins[v].source.ruling:
                bare += 1
                x, y = pm.vertices[v].xy
                assert abs(pins[v].z - dem.z(x, y)) < 0.05
    assert bare > 0
    mouth_pins = [p for p in pins.values() if "mouth_depth = floor_slab" in p.source.ruling]
    assert len(mouth_pins) == 1 and mouth_pins[0].z == pytest.approx(t.mouth_z)
    # no 5.1 m mouth relation on the OBJECT's rows (the OSM far mouth keeps its own)
    assert not any(r.source.ruling.startswith("tunnel.bore_datum") for r in rows
                   if r.source.inputs and r.source.inputs[0] == t.id)
    cs_all, counts, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs_all, law)[0]
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    ln = LineString(t.axis)
    zs = []
    for f in ramps:
        for v in pm.ring_vertices(f.ring):
            s = ln.project(Point(pm.vertices[v].xy))
            z = sol.z[v]
            zs.append((s, z))
            assert z <= t.mouth_z + tn.ramp_max_grade * s + 1e-6
    smin = min(zs, key=lambda q: q[0])
    smax = max(zs, key=lambda q: q[0])
    assert smin[1] == pytest.approx(t.mouth_z, abs=1e-6)
    # the top reaches the ground at the wall end
    x, y = t.axis[-1]
    assert smax[1] == pytest.approx(dem.z(x, y), abs=0.05)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol.z)
    rec = pub["tunnel_objects"][0]
    assert rec["depth_m"] == pytest.approx(law.tables.structures.tunnel.bore_datum_m)
    assert rec["mouth"] == "bore"
    assert rec["ramp_beyond_walls_m"] == 0.0 and rec["trench_outside_max_m"] == 0.0
    from auto_patch_v2.emit.osm_adapter import write_patch
    paths = write_patch(surf, law, tmp_path, pub, {"tag": "twin"})
    assert json.loads(paths.sidecar.read_text())["tunnel_objects"][0]["ground_end"] == "open"
    rows_v = census(surf, law, pub, {})
    for key in ("structure_rim_gap", "tunnel_mouth_canonical", "wall_in_runway_strip"):
        assert rows_v[key] == [], (key, rows_v[key][:3])


# ── §4: the re-seat ──────────────────────────────────────────────────────

def test_reseat_plate_to_ground(corridor_map, objs, law):
    """05n-4: the wall object is planned with its plate and band
    stations; the seat's delta = ground − (mesh(anchor) + agl + plate),
    exempt from the 1 m threshold, datum ``plate``."""
    from auto_patch_v2.pipeline.build import _plate_seats
    airport, pm, stats = corridor_map
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, rep = read_objects(airport, law, cache)
    seats = _plate_seats(pm, law)
    assert set(seats) == {"dsf:obj0"} and seats["dsf:obj0"][0] == pytest.approx(5.0)
    pl = rebake_plan(airport, objects, cache, law, None, tunnel_objects=seats)
    members = [m for u in pl.units for m in u.members]
    assert len(members) == 1 and members[0].plate_y == pytest.approx(5.0)
    assert len(members[0].plate_stations) > 10
    assert pl.counts["plate_members"] == 1 and pl.counts["terrain_adapted"] == 0
    assert "objects/wall_long.obj" not in dict(pl.skipped)
    # the round trip carries the plate
    from auto_patch_v2.model.rebake import RebakePlan
    pl2 = RebakePlan.from_json(pl.to_json())
    assert pl2.units[0].members[0].plate_stations == members[0].plate_stations
    # a mesh: the anchor sits in the cut trench 2.0 m under the ground,
    # the wall band stations on the ground
    unit = pl2.units[0]
    ground = 700.0

    def sampler(lat, lon):
        if (round(lat, 7), round(lon, 7)) == (round(unit.anchor[0], 7), round(unit.anchor[1], 7)):
            return ground - 3.5, False
        return ground, False
    res = seat(pl2, sampler, law)
    us = res.units[0]
    assert us.datum == DATUM_PLATE and us.bakes
    # rendered plate = (ground − 3.5) + agl(−3.0) + 5.0 = ground − 1.5: the cut
    # under the anchor is what the delta compensates (+1.5); a plate seat
    # under min_delta_m would STAY (RULINGS 2026-09-08d d)
    expect = ground - ((ground - 3.5) + unit.agl_m + 5.0)
    assert us.delta_m == pytest.approx(expect)
    assert us.skip_reason is None
    assert res.counts()["plate_units"] == 1


def test_one_file_one_delta_for_two_placements(objs, law):
    """A plate-seated resource placed at two anchors (OTHH tunnel1 × 2)
    is planned per anchor and bakes only when the seats agree."""
    from auto_patch_v2.pipeline.build import _plate_seats
    airport = _airport(objs, law, [("wall_long", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL"),
                                   ("wall_long", (600.0, 0.0), 180.0, -3.0, "OBJECT_AGL")],
                       _bore(y_in=-70.0, y_open=80.0)
                       + (OsmWay(-401, "big_roads", ((600.0, -70.0), (600.0, -400.0)),
                                 False, {"highway": "secondary", "tunnel": "yes"}),))
    cl = Classification(tuple(_cells(-200, -300, 800, 200)), (), {}, ())
    pm, stats = build(airport, cl, law)
    assert len([t for t in pm.structures if t.source == "object"]) == 2, stats.structures.refused
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, rep = read_objects(airport, law, cache)
    pl = rebake_plan(airport, objects, cache, law, None, tunnel_objects=_plate_seats(pm, law))
    assert len(pl.units) == 2 and pl.counts["multi_anchor"] == 0
    rb = law.tables.structures.rebake
    res = seat(pl, lambda la, lo: (700.0, False), law)
    assert all(u.bakes and u.datum == DATUM_PLATE for u in res.units)
    # disagreeing seats: the second anchor's ground 1 m lower → held, both
    anchors = {u.anchor for u in pl.units}
    low = sorted(anchors)[0]

    def sampler(lat, lon):
        return (699.0 if (lat, lon) == low else 700.0), False
    res2 = seat(pl, sampler, law)
    assert all(u.held and "one file" in (u.skip_reason or "") for u in res2.units)
    assert rb.agreement_window_m < 1.0


def test_law_register(law):
    """§2: every key read through the model, no literal in Python."""
    ob = law.tables.structures.tunnel.object
    assert ob.source_precedence == ("object", "osm")
    assert ob.plate_datum == "ground" and ob.mouth_depth == "floor_slab"    # 2026-09-08l
    assert ob.ramp_end == "wall_end" and ob.trench == "inner_walls" and ob.mouth_end == "bore"
    assert ob.reseat is True
    assert ob.wall_face_max_thickness_m > 0.0 and ob.wall_sample_m > 0.0
    assert ob.plate_normal_y_min == law.tables.structures.bridge.deck_plate_normal_y_min
    assert ob.plate_bin_m == law.tables.structures.bridge.deck_plane_bin_m
    # THE CUTOUT (RULINGS 2026-09-06b (1), 2026-09-08a): the overlap ≤
    # half the thinnest wall the identity grid can express (OTHH: 0.75 m
    # drainage shells, 1.0 m tunnel walls); the rim inside the outer face
    # by a fraction of the thickness; no band is ever emitted
    co = law.tables.structures.cutout
    thinnest = 2.0 * law.tables.emit.identity.min_distinct_spacing_m * 0.75
    assert 0.0 < co.floor_overlap_m <= thinnest / 2.0
    assert 0.0 < co.rim_inset_fraction <= 1.0
    assert co.emit_wall_band is False
    assert law.tables.structures.basin.seat == "floor_plate"
    # RULINGS 2026-09-08o: a bore end within this of the plate is the mouth
    assert ob.bore_end_tolerance_m > ob.end_cap_open_m > 0.0
    for key in ("skirt_min_depth_m", "plate_min_area_m2", "plate_min_height_m",
                "hull_min_length_m", "end_cap_open_m", "merge_gap_m"):
        assert getattr(ob, key) > 0.0, key
    assert law.tables.structures.rebake.structure_seat_threshold_exempt is False   # 08d (d)
