"""Twins for the tunnel wall OBJECTS as the tunnel authority (RULINGS
2026-09-05k-1; spec ``docs/specs/auto-patch-v2/tunnel-wall-objects-spec.md``
§4): the wall signature over synthetic OBJ8 text, its refusals, the
two-placement merge, the seat / plate datums, an OSM bore under the hull
replaced, the SAME ``Tunnel`` product through the generator, the solve
and the verify readers, the re-bake exclusion, and the law register.
Law values are read from the tables inside the tests, never retyped.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.rebake_plan import plan as rebake_plan
from auto_patch_v2.airport.tunnel_objects import read_corridors, signature
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import ramp_faces_of, structures, wall_faces_of
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, DsfObject, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Flat, Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.structures import build_structures
from auto_patch_v2.solve import Options, Status, solve
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


def _slab(vt, tris, x0, x1, z0, z1, y0, y1, bottom=False):
    """A box slab (five faces, open-bottomed unless ``bottom``)."""
    base = len(vt)
    for x in (x0, x1):
        for z in (z0, z1):
            vt.append((x, y0, z))
            vt.append((x, y1, z))
    # corners: (x0,z0)=0,1 (x0,z1)=2,3 (x1,z0)=4,5 (x1,z1)=6,7  (even = y0, odd = y1)
    b = base
    faces = [(b + 1, b + 3, b + 7), (b + 1, b + 7, b + 5),          # top
             (b, b + 1, b + 5), (b, b + 5, b + 4),                  # z0 side
             (b + 2, b + 3, b + 7), (b + 2, b + 7, b + 6),          # z1 side
             (b, b + 1, b + 3), (b, b + 3, b + 2),                  # x0 side
             (b + 4, b + 5, b + 7), (b + 4, b + 7, b + 6)]          # x1 side
    if bottom:
        faces += [(b, b + 2, b + 6), (b, b + 6, b + 4)]
    tris.extend(faces)


def _wall_obj(path, length=100.0, width=20.0, thick=2.0, depth=12.0, top=5.0,
              end_a=False, end_b=False, floor=False, bottom=False):
    """Two parallel wall slabs along z (authored), ``top`` above the
    seat, ``depth`` below it; an end wall across z = −L/2 (``end_a``) /
    +L/2 (``end_b``); a floor plate at −depth (``floor``)."""
    vt: list = []
    tris: list = []
    hx, hz = width / 2.0, length / 2.0
    _slab(vt, tris, -hx, -hx + thick, -hz, hz, -depth, top, bottom)
    _slab(vt, tris, hx - thick, hx, -hz, hz, -depth, top, bottom)
    if end_a:
        _slab(vt, tris, -hx + thick, hx - thick, -hz, -hz + thick, -depth, top, bottom)
    if end_b:
        _slab(vt, tris, -hx + thick, hx - thick, hz - thick, hz, -depth, top, bottom)
    if floor:
        b = len(vt)
        vt += [(-hx, -depth, -hz), (hx, -depth, -hz), (hx, -depth, hz), (-hx, -depth, hz)]
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
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
        "wall": _wall_obj(d / "wall.obj", end_a=True),                     # closed/open
        "wall_open": _wall_obj(d / "wall_open.obj"),                       # open/open
        "wall_box": _wall_obj(d / "wall_box.obj", end_a=True, end_b=True),  # closed/closed
        "wall_bottom": _wall_obj(d / "wall_bottom.obj", end_a=True, bottom=True),
        "floored": _wall_obj(d / "floored.obj", end_a=True, floor=True),
        "kerb": _wall_obj(d / "kerb.obj", depth=12.0, top=0.3),
        "shallow": _wall_obj(d / "shallow.obj", depth=1.0, top=5.0),
        "stub": _wall_obj(d / "stub.obj", length=6.0, width=8.0, thick=3.0),
    }


def _sig(objs, law, name):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    path = str(objs[name])
    return signature(cache.geometry(path), cache.genuine(path), law)


# ── §4: the signature ────────────────────────────────────────────────────

def test_two_slabs_with_a_crest_plate_are_a_wall_skirt(objs, law):
    ob = law.tables.structures.tunnel.object
    sig = _sig(objs, law, "wall")
    assert not isinstance(sig, str), sig
    assert sig.plate_y == pytest.approx(5.0)
    assert sig.plate_area_m2 == pytest.approx(2 * 100.0 * 2.0 + 16.0 * 2.0, rel=0.02)
    assert sig.plate_area_m2 >= ob.plate_min_area_m2
    assert sig.skirt_depth_m == pytest.approx(12.0)
    assert sig.length_m == pytest.approx(100.0) and sig.width_m == pytest.approx(20.0)
    # the end wall closes a; b is a mouth (the two slabs leave the centre bare)
    assert (sig.open_a, sig.open_b) == (False, True)
    # a slab's own underside at the flank is not a floor plate
    sig2 = _sig(objs, law, "wall_bottom")
    assert not isinstance(sig2, str), sig2
    assert _sig(objs, law, "wall_open").open_a and _sig(objs, law, "wall_open").open_b
    box = _sig(objs, law, "wall_box")
    assert not box.open_a and not box.open_b


def test_refusals_name_their_reason(objs, law):
    assert "floor plate below the seat" in _sig(objs, law, "floored")
    assert "kerb" in _sig(objs, law, "kerb")
    assert "no wall skirt" in _sig(objs, law, "shallow")
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


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(-200, -120, 200, 120), (), None, None,
             "airside", "apron", {}),
    ]


def _bore():
    """A mapped bore along the corridor's axis (y in the frame), under the apron."""
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    tags_r = {"highway": "secondary", "lanes": "2"}
    return (OsmWay(-101, "big_roads", ((0.0, -60.0), (0.0, 60.0)), False, tags_t),
            OsmWay(-201, "big_roads", ((0.0, 60.0), (0.0, 900.0)), False, tags_r),
            OsmWay(-202, "big_roads", ((0.0, -60.0), (0.0, -900.0)), False, tags_r))


def _corridors(objs, law, placements, ways=()):
    airport = _airport(objs, law, placements, ways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, rep = read_objects(airport, law, cache)
    cs, st = read_corridors(airport, objects, cache, law)
    return airport, objects, cache, cs, st


def test_datums_seat_and_plate(objs, law):
    """§3.3: floor = the seat (DEM(placement) + AGL; MSL absolute),
    crest = floor + the plate height, depth = the plate height."""
    dem = _PlaneDem()
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL"),
                    ("wall", (400.0, 0.0), 90.0, 650.0, "OBJECT_MSL"),
                    ("wall", (800.0, 0.0), 0.0, 0.0, "OBJECT")])
    # the plain OBJECT seats AT grade: a fence, not a tunnel floor (the
    # basin family's admission depth) — refused by placement, named
    assert st.corridors == 2 and len(st.refused) == 1 and "not 2.5 m" in st.refused[0].replace(
        f"not {law.tables.structures.basin.admission_depth_m:.1f} m", "not 2.5 m"), st.refused
    by_x = sorted(cs, key=lambda c: c.rect.centroid.x)
    assert by_x[0].floor_z == pytest.approx(dem.z(0.0, 0.0) - 3.0)
    assert by_x[0].crest_z == pytest.approx(dem.z(0.0, 0.0) - 3.0 + 5.0)
    assert by_x[0].depth_m == pytest.approx(5.0)
    assert by_x[1].floor_z == pytest.approx(650.0)
    # the hull under its placement: 100 × 20, the long axis along the
    # frame's y at heading 0 and along x at heading 90
    assert by_x[0].rect.area == pytest.approx(2000.0, rel=0.01)
    assert abs(by_x[0].b[1] - by_x[0].a[1]) == pytest.approx(100.0, abs=0.01)
    assert abs(by_x[1].b[0] - by_x[1].a[0]) == pytest.approx(100.0, abs=0.01)
    assert by_x[0].ends == "closed/open"


def test_two_placements_merge_at_their_open_ends(objs, law):
    """§3.2: two hulls whose open ends face within merge_gap_m are ONE
    corridor (tunnel1 × 2); two the gap apart stay two."""
    gap = law.tables.structures.tunnel.object.merge_gap_m
    # wall: closed at −z (authored), open at +z; heading 0 → +z is frame −y.
    # A: open end at y = −50; B (heading 180): open end at y = +50 → placed
    # at y = −100 − gap/2 its open end stands gap/2 short of A's
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL"),
                    ("wall", (0.0, -100.0 - gap / 2.0), 180.0, -3.0, "OBJECT_AGL")])
    assert st.merged == 1 and st.corridors == 1, (st.merged, st.corridors, st.refused)
    c = cs[0]
    assert c.ends == "closed/closed" and len(c.objects) == 2
    assert c.length_m == pytest.approx(200.0 + gap / 2.0, abs=0.5)
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL"),
                    ("wall", (0.0, -100.0 - 3 * gap), 180.0, -3.0, "OBJECT_AGL")])
    assert st.merged == 0 and st.corridors == 2


# ── the SAME Tunnel product ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def corridor_map(objs, law):
    """A closed/open wall object over a mapped bore under the apron: the
    corridor replaces the bore and climbs out of its open end (the
    frame's −y, along the bore's approach way)."""
    airport = _airport(objs, law, [("wall", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL")], _bore())
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, rep = read_objects(airport, law, cache)
    cs, ts = read_corridors(airport, objects, cache, law)
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, st = build_structures(airport, cl, law, objects, cs)
    pm, stats = build(airport, cl, law)
    return airport, cl2, tunnels, st, pm, stats, cs


def test_bore_under_the_hull_is_replaced(corridor_map, law):
    airport, cl2, tunnels, st, pm, stats, cs = corridor_map
    tn = law.tables.structures.tunnel
    assert st.bores == 1 and st.bores_replaced_by_object == 1 and st.object_corridors == 1
    assert st.tunnels == 1 and not st.refused, st.refused
    t = tunnels[0]
    assert t.source == "object" and t.crest == tn.object.crest and t.replaced_ways == (-101,)
    assert t.mouth_z == pytest.approx(cs[0].floor_z) and t.crest_z == pytest.approx(cs[0].crest_z)
    assert t.depth_m == pytest.approx(5.0) and t.ends == "closed/open" and t.capped
    # the cap stands at the closed end (+y), the climb starts at the hull's far end
    assert t.axis[0][1] == pytest.approx(50.0, abs=0.01) and t.climb_from_s == pytest.approx(100.0)
    assert t.top_s > t.climb_from_s and t.top_pinned
    # the ramp runs down the approach way (x = 0) beyond the open end
    assert all(abs(x) < 0.5 for x, y in t.axis)
    roles = [c.role for c in cl2.cells]
    assert roles.count("tunnel_ramp") >= 1 and roles.count("retaining_wall") >= 1
    assert all(c.ref == "tunnel_ramp" for c in cl2.cells if c.role == "tunnel_ramp")
    assert all(c.ref == "tunnel_wall" for c in cl2.cells if c.role == "retaining_wall")
    # the same map through the pipeline's planar build
    assert len(pm.structures) == 1 and pm.structures[0].source == "object"
    assert stats.structures.bores_replaced_by_object == 1
    assert stats.tunnel_objects.corridors == 1


def test_generator_rows_solve_and_verify(corridor_map, law):
    airport, cl2, tunnels, st, pm, stats, cs = corridor_map
    tn = law.tables.structures.tunnel
    t = pm.structures[0]
    rows = structures(pm, law, airport)
    pins = {r.v: r for r in rows if isinstance(r, Pin)}
    walls = wall_faces_of(pm, pm.structures)[t.id]
    ramps = ramp_faces_of(pm, pm.structures)[t.id]
    assert walls and ramps
    # every BARE wall vertex is pinned at the plate crest; the datum
    # group at the seat is a Flat and its representative pinned at the floor
    bare = 0
    for f in walls:
        for v in pm.ring_vertices(f.ring):
            ground = any(pm.faces[x].role not in ("tunnel_ramp", "retaining_wall")
                         for x in pm.vertices[v].incident_faces)
            if v in pins and not ground:
                bare += 1
                assert pins[v].z == pytest.approx(t.crest_z)
                assert "plate" in pins[v].source.ruling
    assert bare > 0
    seat_pins = [p for p in pins.values() if "floor_datum" in p.source.ruling]
    assert len(seat_pins) == 1 and seat_pins[0].z == pytest.approx(t.mouth_z)
    assert not any(r.source.ruling.startswith("tunnel.bore_datum") for r in rows)
    cs_all, counts, _w = generate(pm, law, airport)
    sol = solve(pm, cs_all, DEFAULT_WEIGHTS, Options(diagnose_iis=True))
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    zs = [sol.z[v] for f in ramps for v in pm.ring_vertices(f.ring)]
    assert min(zs) == pytest.approx(t.mouth_z, abs=1e-6)
    # the trench is flat at the floor over the hull; the ramp climbs beyond
    axis = t.axis
    from shapely.geometry import LineString, Point
    ln = LineString(axis)
    for f in ramps:
        for v in pm.ring_vertices(f.ring):
            s = ln.project(Point(pm.vertices[v].xy))
            if s <= t.climb_from_s + 1.0:
                assert sol.z[v] == pytest.approx(t.mouth_z, abs=1e-6)
            else:
                assert sol.z[v] <= t.mouth_z + tn.ramp_max_grade * (s - t.climb_from_s) + 1e-6
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol.z)
    assert pub["tunnel_objects"] and pub["tunnel_objects"][0]["depth_m"] == pytest.approx(5.0)
    rows_v = census(surf, law, pub, {})
    for key in ("tunnel_wall_top_flat", "tunnel_ramp_wall_gap", "tunnel_mouth_canonical",
                "wall_in_runway_strip"):
        assert rows_v[key] == [], (key, rows_v[key][:3])


def test_open_open_and_closed_closed_corridors(objs, law):
    """An open+open corridor is two capless halves (a ramp from each
    mouth); a closed+closed one is a capped, far-capped trench with no
    climb — both the same ramp / wall faces."""
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall_open", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL"),
                    ("wall_box", (300.0, 0.0), 0.0, -3.0, "OBJECT_AGL")])
    cl = Classification(tuple(_cells()) + (
        Cell(2, "apron", "apron2", _rect(200, -120, 400, 120), (), None, None,
             "airside", "apron", {}),), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not sst.refused, sst.refused
    halves = [t for t in tunnels if t.ends == "open/open"]
    box = [t for t in tunnels if t.ends == "closed/closed"]
    assert len(halves) == 2 and len(box) == 1
    for h in halves:
        assert not h.capped and h.cap_centre is None and h.climb_from_s == pytest.approx(50.0)
        assert h.top_pinned and h.top_s > 50.0
    b = box[0]
    assert b.capped and b.far_capped and not b.top_pinned
    assert b.top_s == pytest.approx(100.0) and b.climb_from_s == pytest.approx(100.0)
    assert b.wall_path[0] == b.wall_path[-1]           # the O: a closed centreline
    # the box's band is ONE ring with the trench in its hole
    box_walls = [Polygon(c.ring, c.holes) for c in cl2.cells
                 if c.role == "retaining_wall" and Polygon(c.ring).centroid.x > 200]
    assert len(box_walls) == 1 and len(box_walls[0].interiors) == 1
    # the two halves' ramps meet at the midpoint: their rings share the mid-line
    pm, stats = build(airport, cl, law)
    from shapely.geometry import Polygon as _P
    ramps = [_P([pm.vertices[i].xy for i in pm.ring_vertices(f.ring)])
             for f in pm.faces.values() if f.role == "tunnel_ramp"
             and _P([pm.vertices[i].xy for i in pm.ring_vertices(f.ring)]).centroid.x < 100]
    assert len(ramps) == 2 and ramps[0].touches(ramps[1])
    assert stats.t_vertices == 0
    rows = structures(pm, law, airport)
    cs_all, counts, _w = generate(pm, law, airport)
    sol = solve(pm, cs_all, DEFAULT_WEIGHTS, Options(diagnose_iis=True))
    assert sol.status is Status.OPTIMAL, sol.iis[:5]


def test_rebake_excludes_the_tunnel_object_family(objs, law):
    """§3.6: a tunnel wall object (and its anchor family) is never
    re-seated; the plan lists it under ``tunnel_object``."""
    airport, objects, cache, cs, st = _corridors(
        objs, law, [("wall", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL"),
                    ("shallow", (0.0, 0.0), 0.0, -3.0, "OBJECT_AGL"),
                    ("shallow", (500.0, 0.0), 0.0, 0.0, "OBJECT")])
    pl = rebake_plan(airport, objects, cache, law, None,
                     tunnel_objects={oid for c in cs for oid in c.objects})
    resources = [m.resource for u in pl.units for m in u.members]
    assert "objects/wall.obj" not in resources
    assert pl.counts["terrain_adapted"] == 2          # the wall and its family's sibling
    assert dict(pl.skipped)["objects/wall.obj"].startswith("tunnel_object")
    assert "objects/shallow.obj" in resources         # the far sibling still seats


def test_law_register(law):
    """§2: every key read through the model, no literal in Python."""
    ob = law.tables.structures.tunnel.object
    assert ob.source_precedence == ("object", "osm")
    assert ob.floor_datum == "seat" and ob.crest == "plate"
    assert ob.plate_normal_y_min == law.tables.structures.bridge.deck_plate_normal_y_min
    assert ob.plate_bin_m == law.tables.structures.bridge.deck_plane_bin_m
    assert ob.floor_plate_max_m2 == 0.0
    for key in ("skirt_min_depth_m", "plate_min_area_m2", "plate_min_height_m",
                "hull_min_length_m", "end_cap_open_m", "merge_gap_m"):
        assert getattr(ob, key) > 0.0, key
    assert law.tables.structures.rebake.structure_family_excluded is True
