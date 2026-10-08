"""Lane v2doorramp twins (RULINGS 2026-09-08b/c; spec
``docs/specs/auto-patch-v2/othh-terminal-ramps-spec.md`` §5):

* the law register: ``[cutout.door]`` / ``[cutout.sunken_road]`` keys,
  the ``door_ramp`` role (8 %, groundside, structure, aliased for the
  oracle under ``tunnel_ramp`` at the STRUCTURE RAMP law's 10 %
  ceiling — RULINGS 2026-09-08u (2)), ``seat =
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
  o4_grade_law=structure_ramp o4_grade_law_cap=0.1`` for the oracle
  (08u (2): the pair frame reads a ramp at the ramp law's ceiling).
Law values are read from the tables inside the tests, never retyped.
"""
from __future__ import annotations

import math

import pytest
import shapely
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import frame_entry as _fe
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
from auto_patch_v2.pipeline.build import _plate_seats
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.door_ramps import door_groups, sunken_groups
from auto_patch_v2.planar.wall_corridor_ramps import OBJECT_FRAMED
from auto_patch_v2.planar.structure_geometry import rim_standoff
from auto_patch_v2.planar.structures import build_structures
from auto_patch_v2.solve import Options, Status, solve_design

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
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8", newline="")
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
    assert spec.oracle_role == "tunnel_ramp" and spec.oracle_law == "structure_ramp"
    # RULINGS 2026-10-07e (owner): "Door ramps are exempt from the cap, since
    # they only exist when framed by objects ... the object defines both the
    # length and depth and therefore the necessary grade."  So the door law
    # carries NO grade key, and neither does the wall corridor's:
    assert not hasattr(d, "ramp_grade")
    assert not hasattr(co.wall_corridor, "max_ramp_grade")
    # ...what the role row and the oracle cap still price is what the lift
    # does not take — the ramp's seams with its neighbours — at the ROAD
    # ramp law (07d), one number
    road = law.tables.structures.tunnel.ramp_max_grade
    assert spec.oracle_cap == road
    assert is_structure_role(law, "door_ramp") and role_side(law, "door_ramp") == "groundside"
    cap = role_cap(law, "door_ramp")
    assert cap is not None and cap.longitudinal == pytest.approx(road)
    assert cap.longitudinal == role_cap(law, "tunnel_ramp").longitudinal
    assert cap.longitudinal >= role_cap(law, "service_road").longitudinal
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
    assert t.source == "door"
    ground = airport.dem.z(*w.sill_mid)
    # §47 (6) LAW A INVERTED, FRAMED BY THE WELL (owner RULINGS 2026-10-07e):
    # the ramp TOPS at the ground at the well's OUTER end and descends over
    # the well's WHOLE length to the SILL at the building wall.  Length =
    # the well's, depth = the sill's, the grade what those give: this well
    # is 2.25 m long under a 1.70 m sill, so ~75 % — far over the road
    # law, admitted, with NO step at the face and no raised floor.
    top_ground = airport.dem.z(*t.axis[-1])
    road = law.tables.structures.tunnel.ramp_max_grade
    assert t.mouth_z == pytest.approx(ground - 1.7, abs=0.05)        # the SILL: no step
    assert t.climb_from_s == pytest.approx(0.0)          # the climb starts AT the face
    assert t.top_s == pytest.approx(t.wall_length_m)     # ...and tops at the well's end
    assert t.design_grade == pytest.approx((top_ground - t.mouth_z) / t.wall_length_m)
    assert t.design_grade > road
    # the exemption record: the solve and both census readers price the
    # ramp at its own grade (``publication.lifted_caps``)
    assert t.pinched == (OBJECT_FRAMED, pytest.approx(t.wall_length_m),
                         pytest.approx(t.design_grade))
    assert any(OBJECT_FRAMED in n for n in t.notes), t.notes
    assert any("§47 (6)" in n or "LAW A INVERTED" in n for n in t.notes), t.notes
    assert t.top_pinned and not t.clipped_by
    # the cells: door_ramp faces of the sill's width, the void with the rim
    ramps = [Polygon(c.ring) for c in cl2.cells if c.role == "door_ramp"]
    voids = [Polygon(c.ring, c.holes) for c in cl2.cells if c.role == "retaining_wall"]
    assert ramps and voids
    assert not [c for c in cl2.cells if c.role == "tunnel_ramp"]
    ramp_u = unary_union(ramps)
    co = law.tables.structures.cutout
    grid = law.tables.emit.identity.min_distinct_spacing_m
    # §47 (6): NOTHING is emitted beyond the well — the outward climb and
    # ``max_length_m`` retire, so a transect 12 m out cuts no ramp at all
    beyond = Point(w.sill_mid[0] + w.normal[0] * 12.0, w.sill_mid[1] + w.normal[1] * 12.0)
    across = LineString([(beyond.x - 20.0, beyond.y), (beyond.x + 20.0, beyond.y)])
    assert across.intersection(ramp_u).length == 0.0
    # ...and INSIDE the well it is the sill's width (± the grid's rounding)
    inside_p = Point(w.sill_mid[0] + w.normal[0] * 1.0, w.sill_mid[1] + w.normal[1] * 1.0)
    across_in = LineString([(inside_p.x - 20.0, inside_p.y), (inside_p.x + 20.0, inside_p.y)])
    assert across_in.intersection(ramp_u).length == pytest.approx(
        w.sill_width_m, abs=2.0 * grid + 1e-6)
    # the rim: the law's stand-off off the floor ring everywhere
    # the floor spans under the walls, so the shell reads 0 thick (the
    # thin-shell rule: the rim at overlap + spacing off the floor ring)
    # §47 (3): a zero-thickness shell's rim YIELDS to the lattice floor
    _inset, standoff = rim_standoff(0.0, co)
    assert standoff == pytest.approx(co.ring_floor_m)
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
    # RULINGS 2026-10-07e: an object-framed ramp is ONE PLANE — every ramp
    # vertex pinned on the line from the sill to the ground at its own
    # station (``framed_plane``), no descent rows and no station ties: the
    # grade is the ramp's OWN, far over the road law
    own = t[0].design_grade
    assert own > law.tables.structures.tunnel.ramp_max_grade
    assert not [r for r in rows if type(r).__name__ == "Diff"]
    pins = [r for r in rows if isinstance(r, Pin)]
    assert any(abs(r.z - t[0].mouth_z) < 1e-6 for r in pins)      # the sill
    cs, _counts, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    faces = [f for f in pm.faces.values() if f.role == "door_ramp"]
    assert faces
    # the built ramp: the sill at the mouth, never steeper than its own
    # grade (to the emitted top chord) between its vertices, the top at the ground
    built = (airport.dem.z(*t[0].axis[-1]) - t[0].mouth_z) / max(
        ln_s for ln_s in [max(LineString(t[0].axis).project(Point(pm.vertices[v].xy))
                              for f in faces for v in pm.ring_vertices(f.ring))])
    ln = LineString(t[0].axis)
    for f in faces:
        ids = list(pm.ring_vertices(f.ring))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = pm.vertices[ids[i]].xy, pm.vertices[ids[j]].xy
                d = math.hypot(a[0] - b[0], a[1] - b[1])
                if d > 1e-6:
                    assert abs(sol.z[ids[i]] - sol.z[ids[j]]) <= built * d + 0.011
        for v in ids:
            s_ = ln.project(Point(pm.vertices[v].xy))
            if s_ <= t[0].climb_from_s + 1e-6:
                assert sol.z[v] == pytest.approx(t[0].mouth_z, abs=1e-6)
    # §47 (6): the top is the well's OUTER end (``top_s``), not the end of
    # the axis line — nothing is emitted past the well
    x, y = ln.interpolate(t[0].top_s).coords[0]
    top = [sol.z[v] for f in faces for v in pm.ring_vertices(f.ring)
           if ln.project(Point(pm.vertices[v].xy)) >= t[0].top_s - 1.0]
    # the DESIGN is the DEM exactly here (mouth_z + grade x top_s = 700.00)
    # and so is the SOLVE: the plane ends at the outermost emitted vertex,
    # so the 0.055 m the station tie used to leave on this 2.35 m well (it
    # would be 0.27 m at this grade) is gone
    assert top and max(top) == pytest.approx(airport.dem.z(x, y), abs=0.01)
    assert t[0].mouth_z + t[0].design_grade * t[0].top_s == pytest.approx(
        airport.dem.z(x, y), abs=1e-6)
    # RULINGS 2026-10-07e: the exemption record reaches the publication —
    # both census readers price the door ramp's faces at its own grade
    from auto_patch_v2.pipeline.publication import lifted_caps
    caps = lifted_caps(pm)
    assert {fid for fid in caps} == {f.id for f in faces}
    assert all(g == pytest.approx(t[0].design_grade) for g in caps.values())
    # the oracle's tags
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    text, _ways, _nodes = render_patch(surf, law, {}, {})
    assert "v='tunnel_ramp'" in text and "v='door_ramp'" in text
    assert "k='o4_grade_law' v='structure_ramp'" in text and \
        "k='o4_grade_law_cap' v='0.1'" in text


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


# --- lane ``gemltopology`` 2026-09-18: the GEML free-hole abort -------------
#
# THE MINIMAL OFFENDER, verbatim from the airport frame of GEML's
# ``Objects/CartelonAprox.OBJ`` placement ``dsf:obj1484`` (capture
# 2026-09-18, ``v2_solve_replay --capture GEML``).  ``obj8._clip_component``
# produced this component's below-ground footprint VALID; the placement's
# heading affine (``obj8._witness``) rounded it into a self-touching ring
# that visits ``(-472.3430, 726.5788)`` twice, so GEOS reads a hole with
# no shell.  ``unary_union`` of this ONE polygon raises
# ``TopologyException: unable to assign free hole to a shell`` — which is
# what aborted tile +35-003 in app engine 1.50.1796.
GEML_FREE_HOLE_WKT = (
    "MULTIPOLYGON (((-472.29122386010937 726.5434285995657, -472.3470759154321 726.4618118155117, -472.34707591543827 726.4618118155028, -472.29122386010937 726.5434285995657, -472.3429637085204 726.5788367232723, -472.4173308063246 726.4583588605841, -472.3429637085204 726.5788367232723, -472.3737492563175 726.5999047881826, -472.3737492563257 726.5999047881706, -472.3737492563175 726.5999047881826, -473.12484744630154 725.5023226415454, -473.16478067780685 725.4439608764801, -473.08225528159875 725.3874846878632, -472.3220448457465 726.4983870146116, -472.29122386010937 726.5434285995657), (-473.12347190762245 725.4986138831806, -473.12347190762245 725.4986138831806, -473.12347190762245 725.4986138831806, -473.12347190762245 725.4986138831806), (-472.5632672856197 726.1458906865047, -472.56326728565364 726.1458906864551, -472.5632672856819 726.1458906864137, -472.56326728564795 726.1458906864633, -472.5632672856197 726.1458906865047)), ((-470.7288425365336 729.0036182058856, -470.76877346202895 728.9452703936807, -471.47993486651296 727.9060422058022, -471.4480877584559 727.8842476629807, -471.39740947030486 727.8495660171853, -471.3175428518894 727.9662760082008, -471.3175428518894 727.9662760082008, -471.3515285079904 727.9166123853144, -471.3175408525619 727.9662746399626, -470.6463090108902 728.947147840694, -470.7288425365336 729.0036182058856)))"
)


# RE-POINTED to §51 (lane ``frameentry``): ``door_wells._union_below`` is
# GONE.  The repair happens ONCE, where the footprint enters the frame
# (``obj8._witness`` -> ``frame_entry.enter``), and what ``door_wells``
# does is ``frame_entry.union``.  The old twin's "repairs to 0.0 m2" was
# an artefact of ``_union_below``'s one-level ``get_parts``, which threw
# away ``make_valid``'s nested MultiPolygon: the ring carries 0.2736 m2.
def test_geml_free_hole_sliver_enters_valid_and_unions():
    g = shapely.from_wkt(GEML_FREE_HOLE_WKT)
    assert not g.is_valid                      # the transform minted this
    with pytest.raises(GEOSException, match="unable to assign free hole to a shell"):
        unary_union([g])
    r = _fe.enter([g], _fe.IDENTITY, 0.001)[0]
    # polygon parts only -- NOT a buffered line (make_valid also yields lines)
    assert r is not None and r.is_valid and r.geom_type in ("Polygon", "MultiPolygon")
    assert r.area == pytest.approx(0.2736, abs=1e-3)
    assert unary_union([r]).is_valid


def test_entry_keeps_the_lawful_members_beside_an_invalid_one():
    """One invalid member must not delete its family's real footprints."""
    a = Polygon([(0, 0), (4, 0), (4, 3), (0, 3)])
    b = Polygon([(3, 0), (7, 0), (7, 3), (3, 3)])
    bad = shapely.from_wkt(GEML_FREE_HOLE_WKT)
    placed = _fe.enter([a, bad, b], _fe.IDENTITY, 0.001)
    u = _fe.union([g for g in placed if g is not None], "twin.doorramp")
    assert u is not None and u.is_valid
    assert u.area == pytest.approx(21.0 + 0.2736, abs=1e-3)
    assert _fe.enter([], _fe.IDENTITY, 0.001).size == 0
