"""Lane v2othh3 twins (RULINGS 2026-09-06b; spec
``docs/specs/auto-patch-v2/othh-read-20260906-spec.md``):

* §2 the ramp width from the pavement tracing the road — a 12 m
  pavement along one approach makes that ramp 12 m wide per station,
  the untraced approach keeps the lanes default (7 m);
* §3 the basin family's PLATE SEAT — a pit whose anchor lies INSIDE its
  own trench seats by ``floor − (mesh(anchor) + agl + plate y)`` (= the
  depth, datum ``plate``, exempt from the 1 m threshold) so the rendered
  floor plate lands ON the trench floor; a pit whose anchor lies OUTSIDE
  seats by ~0; and the rebake plan never excludes a basin family.
* §1 the trench floor and the rim as the emitted product reads them:
  the OSM ramp's rim, its emitted ``structure_rim`` way, no
  ``retaining_wall`` way.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import LineString, Point, Polygon

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.rebake_plan import plan as rebake_plan
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.structures import ramp_faces_of
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, DsfObject, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import _plate_seats
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.structures import build_structures

from test_m4b import _PlaneDem, _airport as _basin_airport, _box_obj, _cells as _basin_cells, _rect


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── §2: the ramp width from the pavement ─────────────────────────────────

def _ways():
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    tags_r = {"highway": "secondary", "lanes": "2"}
    return (OsmWay(-101, "big_roads", ((-80.0, 0.0), (80.0, 0.0)), False, tags_t),
            OsmWay(-201, "big_roads", ((80.0, 0.0), (900.0, 0.0)), False, tags_r),
            OsmWay(-203, "big_roads", ((-80.0, 0.0), (-900.0, 0.0)), False, tags_r))


def _airport(law, ways):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), tuple(ways), (), (), pack, _PlaneDem(), law.ruleset_key)


def _cells(traced: bool):
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(-80, -60, 80, 60), (), None, None, "airside", "apron", {}),
    ]
    if traced:
        # the pack traced the road through the EAST ramp: a 12 m pavement
        # along the approach axis (y = 0), the axis at its centre
        cells.append(Cell(2, "service_road", "road_e", _rect(80, -6, 400, 6), (), None, None,
                          "groundside", "road", {}))
    return cells


def test_ramp_width_from_the_pavement_tracing_the_road(law):
    """2026-09-06b (2): the east ramp is 12 m wide (the pavement's) per
    station; the west ramp keeps lanes × lane_width_m (7 m)."""
    tn = law.tables.structures.tunnel
    assert tn.ramp_width_source == ("pavement", "lanes") and tn.ramp_pavement_max_offset_m > 0.0
    airport = _airport(law, _ways())
    cl = Classification(tuple(_cells(True)), (), {}, ())
    cl2, tunnels, st = build_structures(airport, cl, law)
    assert st.tunnels == 2 and not st.refused, st.refused
    east = next(t for t in tunnels if t.axis[0][0] > 0)
    west = next(t for t in tunnels if t.axis[0][0] < 0)
    assert any("ramp width from the pavement" in n for n in east.notes)
    assert not any("ramp width from the pavement" in n for n in west.notes)
    grid = law.tables.emit.identity.min_distinct_spacing_m
    for t, want in ((east, 6.0), (west, 3.5)):
        ramps = [Polygon(c.ring) for c in cl2.cells if c.role == "tunnel_ramp"
                 and Polygon(c.ring).centroid.x * t.axis[0][0] > 0]
        assert ramps
        ys = [abs(y) for r in ramps for x, y in r.exterior.coords
              if abs(x - t.axis[0][0]) > 5.0 and abs(x - t.axis[-1][0]) > 5.0]
        assert ys and max(ys) == pytest.approx(want, abs=grid) and \
            min(ys) == pytest.approx(want, abs=grid), (t.id, min(ys), max(ys))
    # the control: no pavement traces the road — both ramps at the lanes width
    cl_c = Classification(tuple(_cells(False)), (), {}, ())
    cl2c, tunnels_c, st_c = build_structures(airport, cl_c, law)
    for t in tunnels_c:
        assert not any("ramp width from the pavement" in n for n in t.notes)
        ramps = [Polygon(c.ring) for c in cl2c.cells if c.role == "tunnel_ramp"
                 and Polygon(c.ring).centroid.x * t.axis[0][0] > 0]
        ys = [abs(y) for r in ramps for x, y in r.exterior.coords
              if abs(x - t.axis[0][0]) > 5.0 and abs(x - t.axis[-1][0]) > 5.0]
        assert max(ys) == pytest.approx(3.5, abs=grid)


def test_a_pavement_the_axis_merely_skirts_is_not_the_ramp(law):
    """The offset gate: a 12 m pavement whose centre stands 5 m off the
    axis (> ramp_pavement_max_offset_m) does not set the width."""
    airport = _airport(law, _ways())
    cells = _cells(False) + [Cell(2, "service_road", "road_off", _rect(80, -1, 400, 11), (),
                                  None, None, "groundside", "road", {})]
    cl2, tunnels, st = build_structures(airport, Classification(tuple(cells), (), {}, ()), law)
    east = next(t for t in tunnels if t.axis[0][0] > 0)
    assert not any("ramp width from the pavement" in n for n in east.notes)


# ── §3: the basin family's plate seat ────────────────────────────────────

def _offset_pit(path, x0=40.0, x1=100.0, hz=20.0, depth=6.0):
    """A box pit whose plan lies at authored x in [x0, x1] — its ANCHOR
    (the origin) stands OUTSIDE its own floor."""
    corners = [(x0, -hz), (x1, -hz), (x1, hz), (x0, hz)]
    vt = []
    for x, z in corners:
        vt.append((x, 0.0, z))
        vt.append((x, -depth, z))
    tris = []
    for i in range(4):
        a, b = 2 * i, 2 * ((i + 1) % 4)
        tris += [(a, a + 1, b), (a + 1, b + 1, b)]
    tris += [(1, 3, 5), (1, 5, 7)]
    lines = ["A", "800", "OBJ", "", "TEXTURE none", f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    lines += ["IDX " + " ".join(str(i) for i in idx[k:k + 10]) for k in range(0, len(idx), 10)]
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    return {"dir": d, "pit": _box_obj(d / "pit.obj", 30.0, 20.0, 6.0),
            "offpit": _offset_pit(d / "offpit.obj")}


def test_basin_family_plans_its_floor_plate_at_the_trench_floor(objs, law):
    """2026-09-06b (3): the pit's anchor lies INSIDE its trench — the
    seat's delta is the depth (the plate lands ON the floor, datum
    ``plate``, exempt from the 1 m threshold); the plan carries the
    family (no exclusion); the offset pit's anchor lies OUTSIDE its
    trench and its seat is ~0."""
    airport = _basin_airport(objs, law, [("pit", (0.0, 0.0), 0.0, 0.0),
                                         ("offpit", (400.0, -300.0), 0.0, 0.0)])
    cl = Classification(tuple(_basin_cells()), (), {}, ())
    objects_out: list = []
    pm, stats = build(airport, cl, law, objects_out=objects_out)
    assert len(pm.basins) == 2 and stats.basins.basins == 2, stats.basins.refused
    bl = law.tables.structures.basin
    assert bl.seat == "floor_plate"
    inside = next(b for b in pm.basins if b.anchor_inside_floor)
    outside = next(b for b in pm.basins if not b.anchor_inside_floor)
    assert inside.plate_y_m == pytest.approx(-6.0, abs=0.3)
    assert inside.seat_expect_m == pytest.approx(6.0, abs=0.3)
    assert abs(outside.seat_expect_m) < 0.05
    # the floor IS the rendered plate: R_est + plate y (no margin)
    for b in pm.basins:
        assert b.floor_z == pytest.approx(b.solid_min_z, abs=1e-6)
    seats = _plate_seats(pm, law)
    # RULINGS 2026-09-09ac (2): the plate seat is the basin's OWN WITNESS
    # resource's — the object whose floor plate the basin cut — never
    # every member of the region (at LEMD that seated 12 terminal slabs
    # onto a floor they never had, spec §11.4/§12)
    assert set(seats) == {b.witness_id for b in pm.basins}
    for b in pm.basins:
        oid = b.witness_id
        assert oid in b.member_ids
        assert seats[oid][0] == pytest.approx(b.plate_y_m)
        assert all(Polygon(b.ring).buffer(1e-6).contains(Point(q)) for q in seats[oid][1])
    objects, cache = objects_out
    pl = rebake_plan(airport, objects, cache, law, None, exclude=(), tunnel_objects=seats,
                     below_grade=[(Polygon(b.region), tuple(b.objects)) for b in pm.basins])
    assert pl.counts["terrain_adapted"] == 0 and pl.counts["below_grade"] == 0
    assert pl.counts["plate_members"] == 2 and pl.counts["units"] == 2
    # THE SEAT IS RETIRED (owner RULINGS 2026-09-12s, spec §8): the seat
    # half of this twin — the plate delta 6.0 + floor_clearance_m and the
    # off-pit's bare clearance, read out of ``emit/rebake.seat`` over a
    # mesh sampler — is DELETED with the mechanism.  What survives is the
    # PLAN half above: the witness resource, its plate y, its stations
    # inside the ring, and the two plate members the plan carries.


# ── §1: the product ───────────────────────────────────────────────────────

def test_the_product_carries_the_rim_and_no_wall_band(law, tmp_path):
    """The emitted patch: the ramp (floor) and its ``structure_rim`` ring,
    no ``retaining_wall`` way; the rim stands wall_gap_m +
    wall_band_width_m off the OSM ramp's edge (no object states a wall);
    the census reads the rim as a role-less feature."""
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.emit.osm_adapter import write_patch
    from auto_patch_v2.pipeline.publication import publication
    from auto_patch_v2.solve import Options, Status, solve_design
    from auto_patch_v2.verify import census
    airport = _airport(law, _ways())
    cl = Classification(tuple(_cells(True)), (), {}, ())
    pm, stats = build(airport, cl, law)
    cs, counts, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol.z)
    paths = write_patch(surf, law, tmp_path, pub, {"tag": "twin"})
    txt = paths.patch.read_text()
    assert "k='role' v='retaining_wall'" not in txt
    assert txt.count("k='o4_feature' v='structure_rim'") >= 2
    rows = census(surf, law, pub, {})
    assert rows["structure_rim_gap"] == [] and rows["tunnel_mouth_canonical"] == []
    # the census's own frame reads the rim off the ramp by the OSM stand-off
    tn = law.tables.structures.tunnel
    from auto_patch_v2.verify.frame import Patch
    p = Patch.of(surf, law, pub)
    rims = [sh for sh in p.features if sh.feature == "structure_rim"]
    ramps = [sh for sh in p.shapes if sh.role == "tunnel_ramp"]
    assert rims and ramps
    for r in rims:
        for k in range(1, len(r.ids) - 1):
            d = min(math.hypot(r.xy[k][0] - q[0], r.xy[k][1] - q[1]) for sh in ramps for q in sh.xy)
            assert d >= tn.wall_gap_m - 1e-6
