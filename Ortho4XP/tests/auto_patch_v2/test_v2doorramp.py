"""Lane v2doorramp twins (RULINGS 2026-09-08b/c; spec
``docs/specs/auto-patch-v2/othh-terminal-ramps-spec.md`` §5):

* the law register: ``[cutout.door]`` / ``[cutout.sunken_road]`` keys,
  the ``door_ramp`` role (8 %, groundside, structure, aliased for the
  oracle under ``tunnel_ramp`` at ``service_road``'s law), ``seat =
  "none"`` the only generated value, the door grade under the role cap;
* Law A: a box with a 1.7 m well reaching its face → ONE door ramp of the
  sill's width, climbing at 8 % to the ground within 25 m, the well floor
  at the sill, the rim standing the law's stand-off off the floor ring,
  the anchor family NOT plate-seated; the same well under the roof →
  a basement, nothing;
* Law B: a roofed descending plate reaching grade → a sunken-road trench
  from the 4 m cut to the top, the floor pinned at the plate per station,
  never plate-seated; a level roofed plate → nothing (the basin pass's);
  an unroofed one → nothing (an open ramp);
* the emitted product: ``role=tunnel_ramp class=door_ramp
  o4_grade_law=service_road o4_grade_law_cap=0.08`` for the oracle.
Law values are read from the tables inside the tests, never retyped.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.door_wells import read_door_wells
from auto_patch_v2.airport.rebake_plan import plan as rebake_plan
from auto_patch_v2.airport.sunken_roads import read_sunken_roads
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import structures as structure_rows
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import render_patch
from auto_patch_v2.law import Law
from auto_patch_v2.law.cutout_schema import SEAT_NONE
from auto_patch_v2.law.tables import is_structure_role, role_cap, role_side
from auto_patch_v2.model.constraints import Pin
from auto_patch_v2.model.structures import profile_z
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, _plate_seats
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.door_ramps import door_groups, sunken_groups
from auto_patch_v2.planar.structure_geometry import rim_standoff
from auto_patch_v2.planar.structures import build_structures
from auto_patch_v2.solve import Options, Status, solve

from test_tunnel_objects import _airport, _cells, _prism, _slab, _write


# ── synthetic OBJ8 ───────────────────────────────────────────────────────

def _building(vt, tris, hx=15.0, hz=10.0, top=8.0):
    """A building: four walls and a roof from the seat to ``top`` over
    ``2hx × 2hz`` (its above-band footprint is the body)."""
    _slab(vt, tris, -hx, hx, -hz, hz, 0.0, top)


def _well(vt, tris, cx, z_face, width=3.7, out=1.5, depth=1.7, thick=0.25, lid=False):
    """A basement access well outside the face ``z = z_face`` (authored z
    south): two side walls and an outer wall from ``-depth`` to the seat,
    a floor at ``-depth`` welded to them; ``lid`` closes it at the seat."""
    hw = width / 2.0
    _slab(vt, tris, cx - hw - thick, cx - hw, z_face, z_face + out + thick, -depth, 0.0)
    _slab(vt, tris, cx + hw, cx + hw + thick, z_face, z_face + out + thick, -depth, 0.0)
    _slab(vt, tris, cx - hw, cx + hw, z_face + out, z_face + out + thick, -depth, 0.0)
    b = len(vt)
    vt += [(cx - hw - thick, -depth, z_face), (cx + hw + thick, -depth, z_face),
           (cx + hw + thick, -depth, z_face + out + thick), (cx - hw - thick, -depth, z_face + out + thick)]
    tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    if lid:
        b = len(vt)
        vt += [(cx - hw - thick, 0.0, z_face), (cx + hw + thick, 0.0, z_face),
               (cx + hw + thick, 0.0, z_face + out + thick), (cx - hw - thick, 0.0, z_face + out + thick)]
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]


def _door_obj(path):
    """A 30 × 20 building with a 3.7 m well at its south face (z = +10)."""
    vt: list = []
    tris: list = []
    _building(vt, tris)
    _well(vt, tris, 0.0, 10.0)
    return _write(path, vt, tris)


def _wide_well_obj(path):
    """The same building with a 12 m WIDE well at its south face — a
    sunken yard, not a door (RULINGS 2026-09-08j ``sill_max_width_m``)."""
    vt: list = []
    tris: list = []
    _building(vt, tris)
    _well(vt, tris, 0.0, 10.0, width=12.0)
    return _write(path, vt, tris)


def _roofed_well_obj(path):
    """The same well INSIDE the building (under its roof)."""
    vt: list = []
    tris: list = []
    _building(vt, tris)
    _well(vt, tris, 0.0, 2.0)
    return _write(path, vt, tris)


def _sloped_slab(vt, tris, x0, x1, z0, z1, y_z0, y_z1, thick):
    """A slab whose top descends from ``y_z0`` at ``z0`` to ``y_z1`` at
    ``z1`` (along authored z), ``thick`` thick: top, bottom, four sides,
    and two KERBS welded to its long edges rising to the seat (the
    component reaches grade like a real carriageway's walls do)."""
    b = len(vt)
    top = [(x0, y_z0, z0), (x1, y_z0, z0), (x1, y_z1, z1), (x0, y_z1, z1)]
    vt += top + [(x, y - thick, z) for x, y, z in top]
    tris += [(b, b + 1, b + 2), (b, b + 2, b + 3), (b + 4, b + 6, b + 5), (b + 4, b + 7, b + 6)]
    for i in range(4):
        j = (i + 1) % 4
        tris += [(b + i, b + 4 + i, b + 4 + j), (b + i, b + 4 + j, b + j)]
    k = len(vt)
    vt += [(x0, 0.0, z0), (x0, 0.0, z1), (x1, 0.0, z0), (x1, 0.0, z1)]
    tris += [(b, b + 3, k + 1), (b, k + 1, k), (b + 1, k + 2, k + 3), (b + 1, k + 3, b + 2)]


def _road_obj(path, length=300.0, width=20.0, drop=6.0, roof=True, level=False):
    """A sunken road: a 20 m carriageway slab descending ``drop`` over
    ``length`` (or LEVEL at ``-drop/2``), side walls up to the seat, and a
    roof deck at +5 over it (``roof``)."""
    vt: list = []
    tris: list = []
    hx, hz = width / 2.0, length / 2.0
    if level:
        _sloped_slab(vt, tris, -hx, hx, -hz, hz, -drop / 2.0, -drop / 2.0, 0.3)
    else:
        _sloped_slab(vt, tris, -hx, hx, -hz, hz, 0.0, -drop, 0.3)
    _slab(vt, tris, -hx - 1.0, -hx, -hz, hz, -drop - 0.3, 0.0)
    _slab(vt, tris, hx, hx + 1.0, -hz, hz, -drop - 0.3, 0.0)
    if roof:
        _slab(vt, tris, -hx - 1.0, hx + 1.0, -hz, hz, 5.0, 5.5)
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
    return {"dir": d,
            "door": _door_obj(d / "door.obj"),
            "roofed": _roofed_well_obj(d / "roofed.obj"),
            "wide": _wide_well_obj(d / "wide.obj"),
            "road": _road_obj(d / "road.obj"),
            "road_level": _road_obj(d / "road_level.obj", level=True),
            "road_open": _road_obj(d / "road_open.obj", roof=False)}


def _read(objs, law, placements):
    airport = _airport(objs, law, placements)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    return airport, cache, objects


# ── the law register ─────────────────────────────────────────────────────

def test_law_register(law):
    co = law.tables.structures.cutout
    d, r = co.door, co.sunken_road
    assert d.seat == SEAT_NONE and r.seat == SEAT_NONE
    assert 0.0 < d.sill_min_depth_m < law.tables.structures.basin.admission_depth_m
    assert d.sill_min_width_m > 0.0 and d.max_length_m > 0.0 and d.station_m > 0.0
    assert 0.0 < d.exit_max_fraction < 1.0
    assert r.max_depth_m > r.min_descent_m > 0.0 and r.top_depth_m > 0.0 and r.min_plate_m2 > 0.0
    assert 0.0 < r.roof_min_fraction <= 1.0
    spec = law.tables.precedence.roles["door_ramp"]
    assert spec.side == "groundside" and spec.structure and spec.value and spec.family == "common"
    assert spec.oracle_role == "tunnel_ramp" and spec.oracle_law == "service_road"
    assert is_structure_role(law, "door_ramp") and role_side(law, "door_ramp") == "groundside"
    cap = role_cap(law, "door_ramp")
    assert cap is not None and d.ramp_grade <= cap.longitudinal
    assert cap.longitudinal > role_cap(law, "tunnel_ramp").longitudinal
    assert cap.longitudinal == role_cap(law, "service_road").longitudinal
    assert "door_ramp" not in law.tables.precedence.order


# ── Law A ────────────────────────────────────────────────────────────────

def test_door_well_read_and_ramp_built(objs, law):
    airport, cache, objects = _read(objs, law, [("door", (0.0, 0.0), 0.0, 0.0, "OBJECT")])
    wells, ds = read_door_wells(airport, objects, cache, law)
    assert ds.wells == 1 and len(wells) == 1, ds.refused
    w = wells[0]
    dl = law.tables.structures.cutout.door
    assert w.depth_m == pytest.approx(1.7, abs=0.05)
    # the synthetic floor spans under the walls: 3.7 + 2 × 0.25 along the
    # face, 1.5 + 0.25 out
    assert w.sill_width_m == pytest.approx(4.2, abs=0.1)
    assert w.plate_out_m == pytest.approx(1.75, abs=0.1)
    # the face is the building's side (z = +10 authored = south, y = -10):
    # the normal points away from the building
    assert w.normal[1] < -0.99
    assert w.plate_cover < law.tables.structures.basin.basement_cover_min
    groups = door_groups(wells, law)
    assert len(groups) == 1 and groups[0].kind == "door" and groups[0].stop_at_pavement
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, (), groups)
    assert not sst.refused, sst.refused
    assert sst.door_ramps == 1 and len(tunnels) == 1
    t = tunnels[0]
    assert t.source == "door" and t.design_grade == pytest.approx(dl.ramp_grade)
    ground = airport.dem.z(*w.sill_mid)
    assert t.mouth_z == pytest.approx(ground - 1.7, abs=0.05)
    # the climb: from the well's outer edge, (depth / grade) plus at most
    # two stations, within max_length_m
    climb = t.top_s - t.climb_from_s
    assert 1.7 / dl.ramp_grade <= climb <= 1.7 / dl.ramp_grade + 2.0 * dl.station_m + 1e-6
    assert climb <= dl.max_length_m + dl.station_m
    assert t.climb_from_s == pytest.approx(t.wall_length_m)
    assert t.top_pinned and not t.clipped_by
    # the cells: door_ramp faces of the sill's width, the void with the rim
    ramps = [Polygon(c.ring) for c in cl2.cells if c.role == "door_ramp"]
    voids = [Polygon(c.ring, c.holes) for c in cl2.cells if c.role == "retaining_wall"]
    assert ramps and voids
    assert not [c for c in cl2.cells if c.role == "tunnel_ramp"]
    ramp_u = unary_union(ramps)
    co = law.tables.structures.cutout
    grid = law.tables.emit.identity.min_distinct_spacing_m
    # width beyond the well = the sill width (± the grid's rounding)
    beyond = Point(w.sill_mid[0] + w.normal[0] * 12.0, w.sill_mid[1] + w.normal[1] * 12.0)
    across = LineString([(beyond.x - 20.0, beyond.y), (beyond.x + 20.0, beyond.y)])
    assert across.intersection(ramp_u).length == pytest.approx(w.sill_width_m, abs=2.0 * grid + 1e-6)
    # the rim: the law's stand-off off the floor ring everywhere
    # the floor spans under the walls, so the shell reads 0 thick (the
    # thin-shell rule: the rim at overlap + spacing off the floor ring)
    _inset, standoff = rim_standoff(0.0, co, grid)
    assert standoff == pytest.approx(grid)
    for v in voids:
        for p in v.exterior.coords:
            d = ramp_u.exterior.distance(Point(p))
            if d > 1e-6:
                assert d >= standoff - 1e-6, (p, d)
    # the trench floor stays inside the well's plate (05n-2 assertion)
    assert t.trench_outside_max_m <= grid * math.sqrt(2.0) + 1e-6
    # seat = "none": the door family is not plate-seated
    class _PM:
        structures = tuple(tunnels)
        basins = ()
    assert _plate_seats(_PM(), law) == {}
    # ...and its family is EXCLUDED from the re-seat (the rebake plan's
    # "terrain adapted to it" skip), never a cluster seat into the ramp
    excluded = {oid for tn in tunnels if tn.source in ("door", "sunken_road") for oid in tn.objects}
    assert excluded == set(w.objects)
    plan = rebake_plan(airport, objects, cache, law, exclude=excluded)
    assert plan.counts["terrain_adapted"] >= 1
    assert not any(any(m.id in excluded for m in u.members) for u in plan.units)


def test_door_ramp_rows_solve_and_verify(objs, law, tmp_path):
    airport, cache, objects = _read(objs, law, [("door", (0.0, 0.0), 0.0, 0.0, "OBJECT")])
    cl = Classification(tuple(_cells()), (), {}, ())
    pm, stats = build(airport, cl, law)
    t = [x for x in pm.structures if x.source == "door"]
    assert len(t) == 1, stats.structures.refused
    rows = structure_rows(pm, law, airport)
    dl = law.tables.structures.cutout.door
    diffs = [r for r in rows if type(r).__name__ == "Diff"]
    assert diffs and all(r.cap == pytest.approx(dl.ramp_grade) for r in diffs)
    pins = [r for r in rows if isinstance(r, Pin)]
    assert any(abs(r.z - t[0].mouth_z) < 1e-6 for r in pins)      # the sill
    cs, _counts, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=True))
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    faces = [f for f in pm.faces.values() if f.role == "door_ramp"]
    assert faces
    # the built ramp: the sill at the mouth, never steeper than the door
    # law between its vertices, the top at the ground
    ln = LineString(t[0].axis)
    for f in faces:
        ids = list(pm.ring_vertices(f.ring))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = pm.vertices[ids[i]].xy, pm.vertices[ids[j]].xy
                d = math.hypot(a[0] - b[0], a[1] - b[1])
                if d > 1e-6:
                    assert abs(sol.z[ids[i]] - sol.z[ids[j]]) <= dl.ramp_grade * d + 0.011
        for v in ids:
            s_ = ln.project(Point(pm.vertices[v].xy))
            if s_ <= t[0].climb_from_s + 1e-6:
                assert sol.z[v] == pytest.approx(t[0].mouth_z, abs=1e-6)
    x, y = t[0].axis[-1]
    top = [sol.z[v] for f in faces for v in pm.ring_vertices(f.ring)
           if ln.project(Point(pm.vertices[v].xy)) >= t[0].top_s - 1.0]
    assert top and max(top) == pytest.approx(airport.dem.z(x, y), abs=0.05)
    # the oracle's tags
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    text, _ways, _nodes = render_patch(surf, law, {}, {})
    assert "v='tunnel_ramp'" in text and "v='door_ramp'" in text
    assert "k='o4_grade_law' v='service_road'" in text and "k='o4_grade_law_cap' v='0.08'" in text


def test_a_wide_well_is_a_yard_not_a_door(objs, law):
    """RULINGS 2026-09-08j: a sill wider than ``sill_max_width_m`` is a
    service yard or a parking pit — refused loudly, no ramp."""
    airport, cache, objects = _read(objs, law, [("wide", (0.0, 0.0), 0.0, 0.0, "OBJECT")])
    wells, ds = read_door_wells(airport, objects, cache, law)
    assert ds.wells == 0 and not wells
    assert any("sill_max_width_m" in r for r in ds.refused), ds.refused


def test_well_under_the_roof_is_a_basement(objs, law):
    airport, cache, objects = _read(objs, law, [("roofed", (0.0, 0.0), 0.0, 0.0, "OBJECT")])
    wells, ds = read_door_wells(airport, objects, cache, law)
    assert not wells
    assert any("BASEMENT" in r for r in ds.refused), ds.refused


# ── Law B ────────────────────────────────────────────────────────────────

def test_sunken_road_read_profile_and_pins(objs, law):
    airport, cache, objects = _read(objs, law, [("road", (0.0, 0.0), 0.0, 0.0, "OBJECT")])
    roads, rs = read_sunken_roads(airport, objects, cache, law)
    assert rs.roads == 1 and len(roads) == 1, rs.refused
    r = roads[0]
    sr = law.tables.structures.cutout.sunken_road
    # the cut where the plate reaches max_depth_m, the top where it comes
    # within top_depth_m of the ground; the profile follows the 2 % plate
    assert r.depth_m == pytest.approx(sr.max_depth_m, abs=0.05)
    assert r.top_ground_z - r.top_z == pytest.approx(sr.top_depth_m, abs=0.05)
    assert r.length_m == pytest.approx((sr.max_depth_m - sr.top_depth_m) / 0.02, rel=0.05)
    assert r.cover >= sr.roof_min_fraction
    for a, b in zip(r.stations[:-1], r.stations[1:]):
        assert (b.z - a.z) / (b.s - a.s) == pytest.approx(0.02, abs=0.003)
    groups = sunken_groups(roads, law)
    assert len(groups) == 1 and groups[0].kind == "sunken_road" and groups[0].profile
    cl = Classification(tuple(_cells()), (), {}, ())
    pm, stats = build(airport, cl, law)
    t = [x for x in pm.structures if x.source == "sunken_road"]
    assert len(t) == 1, stats.structures.refused
    assert t[0].profile and t[0].top_s == pytest.approx(t[0].wall_length_m)
    rows = structure_rows(pm, law, airport)
    pins = {r.v: r.z for r in rows if isinstance(r, Pin)}
    faces = [f for f in pm.faces.values() if f.role == "tunnel_ramp"]
    assert faces
    axis = LineString(t[0].axis)
    n = 0
    for f in faces:
        for v in pm.ring_vertices(f.ring):
            assert v in pins
            s = axis.project(Point(pm.vertices[v].xy))
            assert pins[v] == pytest.approx(profile_z(t[0].profile, min(s, t[0].top_s)), abs=0.06)
            n += 1
    assert n > 10
    class _PM:
        structures = tuple(pm.structures)
        basins = ()
    assert _plate_seats(_PM(), law) == {}


def test_level_or_open_plate_is_not_a_sunken_road(objs, law):
    airport, cache, objects = _read(objs, law, [("road_level", (0.0, 0.0), 0.0, 0.0, "OBJECT")])
    roads, rs = read_sunken_roads(airport, objects, cache, law)
    assert not roads and any("LEVEL" in r for r in rs.refused), rs.refused
    airport, cache, objects = _read(objs, law, [("road_open", (0.0, 0.0), 0.0, 0.0, "OBJECT")])
    roads, rs = read_sunken_roads(airport, objects, cache, law)
    assert not roads and any("roofed" in r for r in rs.refused), rs.refused
