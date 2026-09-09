"""Lane v2lemd4 twins (RULINGS 2026-09-06f; the LEMD 970 / 1088 sites
attributed by v2lemd3):

* §1 THE RIM IS THE SHELL'S GROUND-CONTACT RING (``[basin]
  rim_protrusion_max_fraction``): solids of the same component standing
  above the contact band — a control tower, a vent WELDED to the pit's
  shell — are cover or protrusions up to that share of the component's
  face area (each triangle clipped at the band plane); more is a shell
  through the ground (rule 1, refused by resource).  LEMD85: 3.4 %.
* §2 THE EDGE WALL'S CREST IS ITS TOP BAND WHEREVER IT LIES (``[tunnel.
  object] edge_wall_min_skirt_m``): the seat is the author's handle —
  Bridge4.obj is authored y 0 … 2.02 (and was baked to −2.88 … −0.86);
  either reading is an edge wall whose skirt is measured below its own
  crest, the seat reads that crest, the depth is the bore law's.
* §3 the ramp inside the walls reaches the walls' ground at the far end
  (the rise, not the mouth depth, on sloped ground; the design line is
  the target inside the walls; the fit priced over the corners' direct
  distance), the mouth ground read at the mouth WALL (the median along
  its faces), and a U whose end is several wall segments or whose side
  jogs still reads.
* §4 THE PAVEMENT DECK (``[bridge] pavement_deck_families``): a taxi-
  family cell spanning an object corridor is a DECK over the ramp —
  the cell keeps its role and surface (never cut through), the ramp is
  severed under it at the mouth datum, the climb resumes beyond it, the
  deck rows solve.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.tunnel_objects import read_corridors, signature
from auto_patch_v2.airport.tunnel_walls import read_wall_lines
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.build import _plate_seats
from auto_patch_v2.planar.basins import build_basins, read_objects
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.structures import build_structures
from auto_patch_v2.solve import Options, Status, solve_design

from test_m4b import _airport as _basin_airport, _cells as _basin_cells, _rect
from test_tunnel_objects import (_PlaneDem, _airport as _wall_airport, _bore, _cells as _wall_cells,
                                 _prism, _slab, _wall_obj, _write)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── §1: the rim protrusion ────────────────────────────────────────────────

def _pit_with_tower(path, hx=30.0, hz=20.0, depth=5.0, tower=4.0, height=8.0):
    """A pit shell (four walls 0 → −depth, a floor) with a TOWER welded to
    its corner: a ``tower × tower`` prism from the rim (y = 0) up to
    ``height`` sharing the shell's corner vertex — ONE solid component
    (``solid_components`` welds by position)."""
    corners = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    vt: list = []
    for x, z in corners:
        vt.append((x, 0.0, z))
        vt.append((x, -depth, z))
    tris: list = []
    for i in range(4):
        a, b = 2 * i, 2 * ((i + 1) % 4)
        tris += [(a, a + 1, b), (a + 1, b + 1, b)]
    tris += [(1, 3, 5), (1, 5, 7)]
    _prism(vt, tris, [(-hx, -hz), (-hx + tower, -hz), (-hx + tower, -hz + tower), (-hx, -hz + tower)],
           0.0, height)
    return _write(path, vt, tris)


@pytest.fixture(scope="module")
def pit_objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    # shell face area 3,400 m2 (walls 1,000 + floor 2,400): an 8 m tower
    # adds 144 m2 above the band (4.1 %), a 24 m tower 400 m2 (10.5 %)
    return {"dir": d,
            "tower": _pit_with_tower(d / "tower.obj", height=8.0),
            "tall": _pit_with_tower(d / "tall.obj", height=24.0)}


def test_area_fraction_above_clips_each_face(law):
    """The measure: a vertical right triangle of area 1 (feet at y 0,
    apex at y 2) keeps 1/4 above y = 1 (the similar apex triangle)."""
    v = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
    c = obj8.Component(np.array([[0, 1, 2]]), 0.0, 2.0, 0.0, 0.0, False)
    assert obj8.area_fraction_above(v, c, -1.0) == pytest.approx(1.0)
    assert obj8.area_fraction_above(v, c, 1.0) == pytest.approx(0.25)
    assert obj8.area_fraction_above(v, c, 1.5) == pytest.approx(0.0625)
    assert obj8.area_fraction_above(v, c, 2.0) == pytest.approx(0.0)
    # two apexes above, one foot below: the complement
    v2 = np.array([[0.0, 2.0, 0.0], [1.0, 2.0, 0.0], [0.0, 0.0, 0.0]])
    assert obj8.area_fraction_above(v2, c, 1.0) == pytest.approx(0.75)


def test_a_tower_in_the_pit_is_cover_not_the_rim(pit_objs, law):
    """2026-09-06f (970): the shell's ground-contact ring is the rim; the
    welded tower (4.1 % of the face area above the band) does not refuse
    the pit — admitted, the protrusion noted, the pad inside cut."""
    bl = law.tables.structures.basin
    assert 0.0 < bl.rim_protrusion_max_fraction < bl.basement_cover_min
    cells = _basin_cells() + [Cell(4, "building", "padTower", _rect(-30, -20, 30, 20), (),
                                   None, None, "airside", "pad", {})]
    airport = _basin_airport(pit_objs, law, [("tower", (0.0, 0.0), 0.0, 0.0)])
    objects, rep = read_objects(airport, law)
    assert rep.below_grade_objects == 1 and not rep.through_grade
    (n, frac, top), = rep.rim_protrusions.values()
    assert n == 1 and 0.03 < frac < bl.rim_protrusion_max_fraction and top == pytest.approx(8.0, abs=0.3)
    w = objects[0].witnesses[0]
    assert w.protrusion_fraction == pytest.approx(frac) and w.protrusion_top_m == pytest.approx(top)
    cl = Classification(tuple(cells), (), {}, ())
    cl3, basins, bs = build_basins(airport, cl, law, (), objects, report=rep)
    assert not bs.refused, bs.refused
    assert len(basins) == 1
    b = basins[0]
    assert b.floor_z == pytest.approx(b.solid_min_z)
    assert any("rim protrusion" in n and "cover, not the rim" in n for n in b.notes), b.notes
    # the pad yielded inside (cuts_pads)
    floor = Polygon(b.ring)
    pad = [Polygon(c.ring, c.holes) for c in cl3.cells if c.ref.startswith("padTower")]
    assert all(p.intersection(floor).area < 1e-6 for p in pad)


def test_a_shell_through_the_ground_is_still_refused(pit_objs, law):
    """...and a shell whose solids above the band exceed the fraction (a
    24 m tower: 10.5 %) is a building through the ground (rule 1),
    refused by resource naming the fraction."""
    airport = _basin_airport(pit_objs, law, [("tall", (0.0, 0.0), 0.0, 0.0)])
    objects, rep = read_objects(airport, law)
    assert rep.below_grade_objects == 0 and not rep.rim_protrusions
    assert len(rep.through_grade) == 1
    cl = Classification(tuple(_basin_cells()), (), {}, ())
    cl3, basins, bs = build_basins(airport, cl, law, (), objects, report=rep)
    assert not basins
    assert len(bs.refused) == 1 and "rim_protrusion_max_fraction" in bs.refused[0] \
        and "tall.obj" in bs.refused[0], bs.refused


# ── §2: the edge wall's crest is its top band ─────────────────────────────

@pytest.fixture(scope="module")
def wall_objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    return {
        "dir": d,
        # Bridge4.obj as AUTHORED: standing on its seat, crest 2.016 up
        "standing": _wall_obj(d / "standing.obj", length=160.0, top=2.016, depth=0.0, end_a=True),
        # ...and as v1 had baked it: wholly below the seat
        "sunk": _wall_obj(d / "sunk.obj", length=160.0, top=-0.859, depth=2.875, end_a=True),
        # too low a wall for an edge wall (skirt 1.0 < edge_wall_min_skirt_m)
        "kerb": _wall_obj(d / "kerb.obj", length=160.0, top=1.0, depth=0.0, end_a=True),
        # a long standing wall for the pavement deck (§4)
        "long": _wall_obj(d / "long.obj", length=300.0, top=2.0, depth=0.0, end_a=True),
        # a full wall with a JOG in one side and a three-segment far end
        "jogged": _jogged_wall(d / "jogged.obj"),
    }


def _band(vt, tris, path, thick, y0, y1):
    """A wall band of plan thickness ``thick`` centred on the polyline
    ``path`` (authored x, z): one prism per segment, each extended by
    ``thick / 2`` at both ends so consecutive prisms overlap at the
    joints (one welded crest ring)."""
    h = thick / 2.0
    for a, b in zip(path[:-1], path[1:]):
        dx, dz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dz) or 1.0
        ux, uz = dx / L, dz / L
        nx, nz = -uz, ux
        a2 = (a[0] - ux * h, a[1] - uz * h)
        b2 = (b[0] + ux * h, b[1] + uz * h)
        _prism(vt, tris, [(a2[0] + nx * h, a2[1] + nz * h), (b2[0] + nx * h, b2[1] + nz * h),
                          (b2[0] - nx * h, b2[1] - nz * h), (a2[0] - nx * h, a2[1] - nz * h)],
               y0, y1)


def _jogged_wall(path, length=120.0, width=20.0, thick=2.0, depth=12.0, top=5.0):
    """A U whose left wall JOGS 1.5 m sideways at mid-length and whose
    closed end (authored −z) is THREE segments — an end wall, a 60°
    oblique wall, a return — before the right wall: Bridge4's plan
    features on the synthetic twin."""
    vt: list = []
    tris: list = []
    hx, hz, j, h = width / 2.0, length / 2.0, 1.5, thick / 2.0
    xl, xr = -hx - h, hx + h                     # the walls' centrelines
    _band(vt, tris, [(xl, hz), (xl, 0.0), (xl - j, 0.0), (xl - j, -hz)], thick, -depth, top)
    _band(vt, tris, [(xl - j, -hz), (xl + 8.0, -hz), (xl + 12.0, -hz + 6.9), (xr, -hz + 6.9),
                     (xr, hz)], thick, -depth, top)
    return _write(path, vt, tris)


def _sig(objs, law, name):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    path = str(objs[name])
    return signature(cache.geometry(path), cache.genuine(path), law)


def _corridors(objs, law, placements, ways):
    airport = _wall_airport(objs, law, placements, ways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, rep = read_objects(airport, law, cache)
    cs, st = read_corridors(airport, objects, cache, law)
    return airport, objects, cache, cs, st


def test_the_crest_is_the_top_band_wherever_it_lies(wall_objs, law):
    """2026-09-06f: standing on the seat or sunk below it, the same wall
    reads the same — an edge wall, its crest the top band, its skirt
    (2.02 m) below that crest; a 1 m wall is refused by name."""
    ob = law.tables.structures.tunnel.object
    assert 0.0 < ob.edge_wall_min_skirt_m < ob.skirt_min_depth_m
    for name, crest in (("standing", 2.016), ("sunk", -0.859)):
        sig = _sig(wall_objs, law, name)
        assert not isinstance(sig, str), (name, sig)
        assert sig.edge_wall and sig.plate_y == pytest.approx(crest, abs=1e-3)
        assert sig.skirt_depth_m == pytest.approx(2.016, abs=2e-3)
    kerb = _sig(wall_objs, law, "kerb")
    assert isinstance(kerb, str) and "edge_wall_min_skirt_m" in kerb and "skirt_min_depth_m" in kerb


@pytest.mark.parametrize("name,crest", [("standing", 2.016), ("sunk", -0.859)])
def test_edge_wall_below_or_on_the_seat_builds_its_corridor(wall_objs, law, name, crest):
    """Both readings build the corridor: depth = tunnel.bore_datum_m at
    the mouth, the trench between the walls, the seat reading the crest
    (the re-seat's delta = ground − (base + crest) puts it flush)."""
    tn = law.tables.structures.tunnel
    airport, objects, cache, cs, st = _corridors(
        wall_objs, law, [(name, (0.0, 0.0), 180.0, None, "OBJECT")], _bore(y_in=-70.0, y_open=80.0))
    assert st.corridors == 1, st.refused
    c = cs[0]
    assert c.edge_wall and c.mouth_kind == "bore"
    assert c.depth_m == pytest.approx(tn.bore_datum_m) and c.plate_y == pytest.approx(crest, abs=1e-3)
    cl = Classification(tuple(_wall_cells(-200, -300, 200, 200)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    assert not [r for r in sst.refused if name in r], sst.refused
    t = [t for t in tunnels if t.source == "object"][0]
    assert t.edge_wall and t.plate_y_m == pytest.approx(crest, abs=1e-3)
    assert t.top_s == pytest.approx(t.wall_length_m)
    assert t.trench_outside_max_m == 0.0
    pm, stats = build(airport, cl, law)
    seats = _plate_seats(pm, law)
    assert seats["dsf:obj0"][0] == pytest.approx(crest, abs=1e-3)


# ── §3: the ramp reaches the walls' ground; the plan reads ────────────────

def test_ramp_reaches_the_far_ground_on_sloped_terrain(wall_objs, law):
    """Heading 90 puts the axis along x, where the plane DEM rises 0.5 %:
    the rise at the wall end is the depth PLUS the ground's rise; the
    design grade is that rise over the walls (not depth / length), the
    top at the wall end, and the mouth ground is the median along the
    mouth wall's faces."""
    tn = law.tables.structures.tunnel
    bore = (_bore(y_in=-70.0, y_open=80.0)[0],)
    # the closed end (authored −z) faces −x under heading 90... place the
    # bore along x accordingly: its end inside the closed end
    from auto_patch_v2.model.airport import OsmWay
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    bore = (OsmWay(-101, "big_roads", ((-70.0, 0.0), (-400.0, 0.0)), False, tags_t),)
    airport, objects, cache, cs, st = _corridors(
        wall_objs, law, [("standing", (0.0, 0.0), 90.0, None, "OBJECT")], bore)
    assert st.corridors == 1, st.refused
    c = cs[0]
    dem = _PlaneDem()
    # the mouth ground = the median DEM along the mouth wall's faces
    assert c.mouth_dem_z == pytest.approx(dem.z(*c.axis[0]), abs=0.05)
    cl = Classification(tuple(_wall_cells(-300, -200, 300, 200)), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    t = [t for t in tunnels if t.source == "object"][0]
    far = dem.z(*t.axis[-1])
    rise = far - t.mouth_z
    assert rise > tn.bore_datum_m + 0.5          # the ground rose along the walls
    assert t.top_s == pytest.approx(t.wall_length_m)
    assert t.design_grade == pytest.approx(rise / t.wall_length_m, rel=1e-3)
    assert t.design_grade < tn.ramp_max_grade


def test_jogged_wall_with_a_three_segment_end_reads_as_a_u(wall_objs, law):
    """A side wall's 1.5 m jog is not a corner pair; the far end's three
    segments are ONE end wall; the trench closes along them."""
    sig = _sig(wall_objs, law, "jogged")
    assert not isinstance(sig, str), sig
    walls = read_wall_lines(sig.plate, law)
    assert not isinstance(walls, str), walls
    assert walls.kind == "U" and walls.closed == (True, False)
    assert len(walls.end_walls[0]) >= 4 and not walls.end_walls[1]
    # the trench closed along the end walls never covers the wall band;
    # the chord between the side walls' ends would run through the
    # oblique wall
    ring = Polygon(walls.trench_ring())
    chord = Polygon(list(walls.inner_a) + list(reversed(walls.inner_b)))
    assert ring.is_valid and ring.intersection(walls.plate).area < 1.0
    assert chord.intersection(walls.plate).area > 5.0


# ── §4: the pavement deck ─────────────────────────────────────────────────

def test_taxiway_spanning_the_corridor_is_a_deck_never_a_cut(wall_objs, law):
    """2026-09-06f (1088): a taxi-family cell across the walls is a DECK
    over the ramp — kept whole in plan (its pieces + the deck piece = the
    cell), the deck piece keeping its role under ``bridge_deck:<ref>``,
    the ramp severed under it, the climb resuming beyond it, the deck
    rows solving."""
    tn = law.tables.structures.tunnel
    br = law.tables.structures.bridge
    assert "taxi" in br.pavement_deck_families
    # the 300 m wall's closed end at −150 (heading 180); the taxiway
    # crosses at y −20..0 (s ≈ 130..150 from the mouth)
    airport, objects, cache, cs, st = _corridors(
        wall_objs, law, [("long", (0.0, 0.0), 180.0, None, "OBJECT")],
        _bore(y_in=-140.0, y_open=170.0))
    assert st.corridors == 1, st.refused
    twy = Cell(9, "cross_connector", "twyD", _rect(-80, -20, 80, 0), (), 3, "D", "airside",
               "taxiway", {})
    cells = _wall_cells(-200, -300, 200, -170) + [twy]
    cl = Classification(tuple(cells), (), {}, ())
    cl2, tunnels, sst = build_structures(airport, cl, law, objects, cs)
    t = [t for t in tunnels if t.source == "object"][0]
    assert sst.pavement_decks == 1 and sst.decks == 0
    assert len(t.decks) == 1
    d = t.decks[0]
    assert d.ref == "bridge_deck:twyD" and d.datum == "dem" and d.way == 0
    assert 120.0 < d.s0 < d.s1 < 160.0
    assert t.climb_from_s == pytest.approx(d.s1 + tn.wall_gap_m)
    assert t.top_s == pytest.approx(t.wall_length_m)
    assert t.design_grade == pytest.approx(tn.bore_datum_m / (t.wall_length_m - t.climb_from_s), rel=1e-2)
    # the cell is whole in plan: its pieces plus the deck piece cover it
    rect = Polygon(_rect(-80, -20, 80, 0))
    pieces = [Polygon(c.ring, c.holes) for c in cl2.cells if c.ref.startswith("twyD")]
    deck_cells = [c for c in cl2.cells if c.ref.startswith("bridge_deck:twyD")]
    assert len(deck_cells) == 1
    dc = deck_cells[0]
    assert dc.role == "cross_connector" and dc.kind == "taxiway" and dc.code_letter == "D"
    assert dc.evidence.get("pavement_deck") == 1.0
    covered = unary_union(pieces + [Polygon(dc.ring, dc.holes)])
    assert rect.difference(covered).area < 1.0
    # the ramp is severed under the deck: no ramp face touches it
    dpoly = Polygon(dc.ring)
    for c in cl2.cells:
        if c.role == "tunnel_ramp":
            assert Polygon(c.ring).distance(dpoly) >= tn.wall_gap_m - 1e-6
    # the deck rows solve: OPTIMAL, every deck vertex clears the ramp
    pm, stats = build(airport, cl, law)
    tt = [x for x in pm.structures if x.source == "object"][0]
    assert len(tt.decks) == 1
    cs_all, counts, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs_all, law)[0]
    assert sol.status is Status.OPTIMAL, sol.message
    deck_faces = [f for f in pm.faces.values() if f.ref.startswith("bridge_deck:twyD")]
    assert deck_faces
    deck_z = [sol.z[v] for f in deck_faces for v in pm.ring_vertices(f.ring)]
    # the object's own ramp faces (the bore's far mouth keeps its OSM ramp)
    inside = cs[0].footprint.buffer(1.0)
    ramps = [f for f in pm.faces.values() if f.role == "tunnel_ramp"
             and inside.contains(Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)])
                                 .representative_point())]
    assert len(ramps) == 2                       # severed at the deck
    ramp_near = [sol.z[v] for f in ramps for v in pm.ring_vertices(f.ring)
                 if dpoly.distance(Point(pm.vertices[v].xy)) <= tn.wall_gap_m + 1.0]
    # 08t: the deck clearance is a TARGET of the one solve — held to the
    # census's own elevation materiality, not to the LP's exact offset
    assert ramp_near and min(deck_z) >= (max(ramp_near) + br.clearance_m
                                         - 2.0 * law.tables.emit.materiality.elevation_m)
    # ...the ramp under the deck sits at the mouth datum (flat) and the
    # piece beyond climbs to the ground at the wall end
    ax = LineString(tt.axis)
    under = [sol.z[v] for f in ramps for v in pm.ring_vertices(f.ring)
             if ax.project(Point(pm.vertices[v].xy)) <= d.s0 + 1.0]
    assert under and max(under) <= tt.mouth_z + 1e-3
    top = [sol.z[v] for f in ramps for v in pm.ring_vertices(f.ring)
           if ax.project(Point(pm.vertices[v].xy)) >= tt.top_s - 1.0]
    assert top and max(top) == pytest.approx(_PlaneDem().z(*tt.axis[-1]), abs=0.05)


def test_structures_stage_records(wall_objs, law):
    """``python -m auto_patch_v2.planar ICAO --stage structures``: the
    structure stages alone as records (the lane's site replay, promoted
    on its second use) — the corridor, its tunnel, the refusals."""
    from auto_patch_v2.planar.__main__ import structure_records
    airport = _wall_airport(wall_objs, law, [("standing", (0.0, 0.0), 180.0, None, "OBJECT")],
                            _bore(y_in=-70.0, y_open=80.0))
    cl = Classification(tuple(_wall_cells(-200, -300, 200, 200)), (), {}, ())
    rec = structure_records(airport, cl, law)
    assert rec["icao"] == "ZZZZ" and rec["objects"]["placements"] == 1
    assert len(rec["corridors"]) == 1 and rec["corridors"][0]["edge_wall"]
    assert rec["corridors"][0]["mouth_ll"] != rec["corridors"][0]["far_ll"]
    t = [t for t in rec["tunnels"] if t["source"] == "object"]
    assert len(t) == 1 and t[0]["top_s"] == pytest.approx(t[0]["wall_length_m"])
    assert isinstance(rec["corridor_refused"], list) and isinstance(rec["basin_refused"], list)
    import json
    json.dumps(rec, default=str)


def test_law_register(law):
    """Every key read through the model, no literal in Python."""
    bl = law.tables.structures.basin
    ob = law.tables.structures.tunnel.object
    br = law.tables.structures.bridge
    assert 0.0 < bl.rim_protrusion_max_fraction < 1.0
    assert 0.0 < ob.edge_wall_min_skirt_m <= ob.skirt_min_depth_m
    assert br.pavement_deck_families and all(isinstance(f, str) for f in br.pavement_deck_families)
