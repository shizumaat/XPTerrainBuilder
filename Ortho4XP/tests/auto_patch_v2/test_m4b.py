"""M4b twins: the OBJ8 reader, the basin pass (planar), its constraint
rows and verify readers, and the hard-deck OBJECT bridge, on ONE
synthetic airport with synthetic OBJ8 files written to ``tmp_path`` — a
pit object (walls + floor, a thin decal quad far below), a hard-deck
bridge object over a tunnel approach, and a roof slab that covers a
second pit.  Law values are read from the tables inside the tests,
never retyped.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport import obj8
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import basins as basin_rows
from auto_patch_v2.constraints.structures import ramp_faces_of, structures
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, DsfObject, OsmWay, Runway,
                                         RunwayEnd, SceneryPack)
from auto_patch_v2.model.constraints import Band, Flat, Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.basins import build_basins, read_objects
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


# ── synthetic OBJ8 files ─────────────────────────────────────────────────

def _box_obj(path, hx, hz, depth, top=0.0, extra="", attr="", lid=False):
    """A box pit: four walls from ``top`` down to ``-depth`` around
    ``2hx × 2hz`` (authored x, z) and a floor at ``-depth`` (a lid at
    ``top`` too with ``lid``), plus ``extra`` lines appended (a decal
    quad).  Solid, welded."""
    corners = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    vt = []
    for x, z in corners:
        vt.append((x, top, z))
        vt.append((x, -depth, z))
    tris = []
    for i in range(4):
        a, b = 2 * i, 2 * ((i + 1) % 4)
        tris += [(a, a + 1, b), (a + 1, b + 1, b)]
    tris += [(1, 3, 5), (1, 5, 7)]
    if lid:
        tris += [(0, 2, 4), (0, 4, 6)]
    lines = ["A", "800", "OBJ", "", "TEXTURE none", f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    for k in range(0, len(idx), 10):
        lines.append("IDX10 " + " ".join(str(i) for i in idx[k:k + 10]) if len(idx[k:k + 10]) == 10
                     else "IDX " + " ".join(str(i) for i in idx[k:k + 10]))
    if attr:
        lines.append(attr)
    lines.append(f"TRIS 0 {len(idx)}")
    lines.append(extra)
    path.write_text("\n".join(lines) + "\n")
    return path


def _decal_lines(y, size, n_vt):
    """A flat quad at ``y`` (thickness 0) appended after ``n_vt`` VTs."""
    vt = [(-size, y, -size), (size, y, -size), (size, y, size), (-size, y, size)]
    out = [f"VT {x:.3f} {yy:.3f} {z:.3f} 0 1 0 0 0" for x, yy, z in vt]
    out.append(f"IDX10 {n_vt} {n_vt + 1} {n_vt + 2} {n_vt} {n_vt + 2} {n_vt + 3} 0 0 0 0")
    return out


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    pit = _box_obj(d / "pit.obj", 30.0, 20.0, 6.0)
    # the decal: a flat 200 m quad 50 m down, as a separate TRIS range
    text = pit.read_text().rstrip("\n").splitlines()
    n_vt = sum(1 for ln in text if ln.startswith("VT"))
    n_idx = sum(len(ln.split()) - 1 for ln in text if ln.startswith("IDX"))
    text += _decal_lines(-50.0, 100.0, n_vt)
    text.append(f"TRIS {n_idx} 6")
    pit.write_text("\n".join(text) + "\n")
    # a hard-deck bridge: a 20 × 12 slab at y = +6 with the deck attribute
    bridge = _box_obj(d / "bridge.obj", 10.0, 6.0, 0.5, top=6.0, attr="ATTR_hard_deck")
    # a low deck (an IIS case): deck top 6 m under grade — clearance
    # would need the ramp 11 m down, beyond what the apron sharing the
    # cap can absorb under its own cap (the ground rule)
    low = _box_obj(d / "low.obj", 10.0, 6.0, 6.5, top=-6.0, attr="ATTR_hard_deck")
    # a roof slab over a pit: 70 × 50 at y = +4
    roof = _box_obj(d / "roof.obj", 35.0, 25.0, 0.2, top=4.0, lid=True)
    small = _box_obj(d / "small.obj", 10.0, 10.0, 6.0)
    return {"dir": d, "pit": pit, "bridge": bridge, "low": low, "roof": roof, "small": small}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_parse_components_and_thickness_gate(objs, law):
    g = obj8.parse_obj8(str(objs["pit"]))
    assert g.vertices.shape == (12, 3) and g.solid.shape[0] == 12 and g.draped.shape[0] == 0
    comps = obj8.solid_components(g)
    assert len(comps) == 2
    box = max(comps, key=lambda c: c.tris.shape[0])
    decal = min(comps, key=lambda c: c.tris.shape[0])
    assert box.min_y == pytest.approx(-6.0) and box.max_y == pytest.approx(0.0)
    assert decal.max_y - decal.min_y == pytest.approx(0.0)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    gen = cache.genuine(str(objs["pit"]))
    assert len(gen) == 1 and gen[0].min_y == pytest.approx(-6.0)
    b = obj8.parse_obj8(str(objs["bridge"]))
    assert b.hard_deck.shape[0] == b.solid.shape[0] and (b.hardness == obj8.HARD_DECK).all()


def test_placement_affine_heading():
    """OBJ8 x east / z south, heading clockwise from north."""
    m = obj8.placement_affine((100.0, 200.0), 0.0)
    from shapely import affinity
    from shapely.geometry import Point
    p = affinity.affine_transform(Point(10.0, -5.0), m)      # x=10 (east), z=-5 (north 5)
    assert (p.x, p.y) == pytest.approx((110.0, 205.0))
    m90 = obj8.placement_affine((0.0, 0.0), 90.0)
    p = affinity.affine_transform(Point(10.0, 0.0), m90)     # +x turns to point south
    assert (p.x, p.y) == pytest.approx((0.0, -10.0), abs=1e-9)


def test_read_placed_objects_local_grade(objs, law):
    bl = law.tables.structures.basin
    dem = _PlaneDem()
    rows = [("o1", "objects/pit.obj", (0.0, 0.0), 30.0, None, "OBJECT"),
            ("o2", "objects/missing.obj", (500.0, 0.0), 0.0, None, "OBJECT"),
            ("o3", "objects/bridge.obj", (150.0, 0.0), 0.0, 2.0, "OBJECT_AGL")]
    index = {"objects/pit.obj": str(objs["pit"]), "objects/bridge.obj": str(objs["bridge"])}
    got, rep = obj8.read_placed_objects(rows, None, index, dem.z, bl.admission_depth_m,
                                        bl.min_solid_thickness_m, bl.contact_band_m)
    assert rep.resolved == 2 and rep.unresolved == 1 and rep.unresolved_paths == ["objects/missing.obj"]
    pit = got[0]
    assert pit.below_grade is not None and pit.below_grade.area == pytest.approx(60 * 40, rel=0.05)
    assert pit.solid_min_z == pytest.approx(700.0 - 6.0, abs=0.2)     # DEM(anchor) + y
    assert pit.solid_min_depth_m == pytest.approx(-6.0, abs=0.3)
    assert pit.hard_deck is None and pit.plan_bbox is not None
    br = got[2]
    assert br.hard_deck is not None and br.hard_deck.area == pytest.approx(20 * 12, rel=0.05)
    assert br.deck_top_z == pytest.approx(dem.z(150.0, 0.0) + 2.0 + 6.0)   # AGL folded in


# ── the synthetic airport ────────────────────────────────────────────────

def _airport(objs, law, placements, ways=()):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", str(objs["dir"].parent / "Earth nav data" / "apt.dat"), "0", (), ())
    dsf = tuple(DsfObject(f"dsf:obj{i}", f"objects/{name}.obj", xy, hd, None, False, None, agl,
                          str(objs[name]), "OBJECT_AGL" if agl else "OBJECT")
                for i, (name, xy, hd, agl) in enumerate(placements))
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (), (), (), (),
                   tuple(ways), (), dsf, pack, _PlaneDem(), law.ruleset_key)


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(-120, -80, 120, 80), (), None, None, "airside", "apron", {}),
        # a pad INSIDE the pit region (cut: the trench is senior, 08-26)
        Cell(2, "building", "padIn", _rect(-10, -8, 10, 8), (), None, None, "airside", "pad", {}),
        # a pad beside the pit, not touched
        Cell(3, "building", "padOut", _rect(200, -30, 240, 30), (), None, None, "airside", "pad", {}),
    ]


@pytest.fixture(scope="module")
def basin_map(objs, law):
    airport = _airport(objs, law, [("pit", (0.0, 0.0), 30.0, 0.0),
                                   ("small", (400.0, -300.0), 0.0, 0.0)])
    objects, rep = read_objects(airport, law)
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, st = build_structures(airport, cl, law, objects)
    cl3, basins, bs = build_basins(airport, cl2, law, tunnels, objects)
    pm, stats = build(airport, cl, law)
    return airport, cl3, basins, bs, pm, stats, rep


def test_basin_pass_cells_records_and_refusals(basin_map, law):
    airport, cl3, basins, bs, pm, stats, rep = basin_map
    bl = law.tables.structures.basin
    br = law.tables.structures.bridge
    assert rep.resolved == 2 and rep.below_grade_objects == 2
    assert bs.regions == 2 and bs.basins == 1
    assert len(bs.small_regions) == 1 and not bs.refused, (bs.small_regions, bs.refused)
    b = basins[0]
    # the floor law: R_est + (deepest solid − R_est) − margins == rendered deepest − margins
    assert b.floor_z == pytest.approx(b.solid_min_z - br.floor_below_object_deck_m - bl.seat_margin_m)
    assert b.floor_z == pytest.approx(b.rim_estimate_m + b.solid_min_y_m
                                      - br.floor_below_object_deck_m - bl.seat_margin_m)
    assert b.solid_min_z == pytest.approx(700.0 - 6.0, abs=0.3)
    assert b.covered_fraction == 0.0 and b.area_m2 == pytest.approx(60 * 40, rel=0.1)
    roles = [c.role for c in cl3.cells]
    assert roles.count("tunnel_trench") == 1 and roles.count("retaining_wall") == 1
    floor = next(c for c in cl3.cells if c.role == "tunnel_trench")
    wall = next(c for c in cl3.cells if c.role == "retaining_wall")
    assert floor.ref == b.floor_ref and wall.ref == b.wall_ref and len(wall.holes) == 1
    # the gap: floor and wall clear each other by the law's gap
    fp, wp = Polygon(floor.ring), Polygon(wall.ring, wall.holes)
    assert fp.distance(wp) >= law.tables.structures.tunnel.wall_gap_m - 1e-6
    # the pad inside the pit is gone, the one beside it untouched, the apron cut
    refs = [c.ref for c in cl3.cells]
    assert "padIn" not in refs and "padOut" in refs
    apron = [c for c in cl3.cells if c.role == "apron"]
    assert apron and all("basin_cut" in c.evidence for c in apron)
    assert Polygon(apron[0].ring, apron[0].holes).distance(fp) >= \
        law.tables.structures.tunnel.wall_gap_m - 1e-6
    assert len(cl3.keepouts) == 1
    # the planar map carries the record; 0 T-vertices
    assert pm.basins and pm.basins[0].id == b.id and stats.t_vertices == 0
    assert stats.basins.basins == 1


def test_covered_region_is_refused(objs, law):
    airport = _airport(objs, law, [("pit", (0.0, 0.0), 0.0, 0.0), ("roof", (0.0, 0.0), 0.0, 0.0)])
    objects, rep = read_objects(airport, law)
    cl = Classification(tuple(_cells()), (), {}, ())
    cl3, basins, bs = build_basins(airport, cl, law, (), objects)
    assert not basins and len(bs.refused) == 1 and "covered" in bs.refused[0]
    assert cl3.cells == cl.cells


def test_basin_rows_solve_emit_verify(basin_map, law):
    airport, cl3, basins, bs, pm, stats, rep = basin_map
    rows = basin_rows(pm, law, airport)
    b = pm.basins[0]
    pins = [r for r in rows if isinstance(r, Pin)]
    floor_vs = {v for f in pm.faces.values() if f.ref.startswith(b.floor_ref)
                for v in pm.ring_vertices(f.ring)}
    floor_pins = {p.v: p.z for p in pins if p.v in floor_vs}
    assert floor_pins and set(floor_pins) == floor_vs
    assert all(z == pytest.approx(b.floor_z) for z in floor_pins.values())
    # every wall vertex pinned at the DEM or carried by the apron it shares
    flat_vs = {v for r in rows if isinstance(r, Flat) for v in r.group}
    pinned = {p.v for p in pins}
    for f in pm.faces.values():
        if f.ref.startswith(b.wall_ref):
            for cyc in (f.ring, *f.holes):
                for v in pm.ring_vertices(cyc):
                    ground = any(pm.faces[x].role not in ("tunnel_trench", "retaining_wall")
                                 for x in pm.vertices[v].incident_faces)
                    assert v in pinned or v in flat_vs or ground
    cs, counts, _w = generate(pm, law, airport)
    assert counts["basins"] == len(rows)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=True))
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    assert all(sol.z[v] == pytest.approx(b.floor_z, abs=1e-6) for v in floor_vs)
    # the rim is level with the apron where shared, the DEM where bare
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol.z)
    rec = pub["basin_facilities"]
    assert len(rec) == 1 and rec[0]["floor_ref"] == b.floor_ref
    bl, br = law.tables.structures.basin, law.tables.structures.bridge
    assert rec[0]["floor_m"] == pytest.approx(
        rec[0]["rim_law_m"] + rec[0]["solid_minimum_y_m"]
        - (br.floor_below_object_deck_m + bl.seat_margin_m), abs=0.002)
    assert rec[0]["body_depth_m"] == pytest.approx(-rec[0]["solid_minimum_y_m"])
    assert rec[0]["emitted_rim_parts_m"] and rec[0]["emitted_rim_min_m"] > rec[0]["floor_m"]
    rows_v = census(surf, law, pub, {})
    for key in ("basin_floor_declaration", "basin_floor_at_declaration", "basin_wall_gap",
                "wall_in_runway_strip"):
        assert rows_v[key] == [], (key, rows_v[key][:3])
    # steps / cross-shape: nothing between the floor and the wall or the apron
    for key in ("vertex_to_edge_step", "mid_edge_step", "cross_shape"):
        assert all("tunnel_trench" not in r["roles"] for r in rows_v[key]), rows_v[key][:3]


def test_verify_readers_fire(basin_map, law):
    airport, cl3, basins, bs, pm, stats, rep = basin_map
    import dataclasses as _dc
    cs, counts, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    b = pm.basins[0]
    z = list(sol.z)
    fv = next(v for f in pm.faces.values() if f.ref.startswith(b.floor_ref)
              for v in pm.ring_vertices(f.ring))
    z[fv] += 1.0
    sol2 = _dc.replace(sol, z=tuple(z))
    surf = graded_surface(pm, law, sol2, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol2.z)
    assert census(surf, law, pub, {})["basin_floor_at_declaration"]
    # a declaration whose two instruments disagree is a family row
    pub2 = dict(pub)
    pub2["basin_facilities"] = [dict(pub["basin_facilities"][0], body_depth_m=40.0)]
    assert census(surf, law, pub2, {})["basin_floor_declaration"]


# ── the object bridge over a tunnel approach ────────────────────────────

def _tunnel_ways():
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    tags_r = {"highway": "secondary", "lanes": "2"}
    return (
        OsmWay(-101, "big_roads", ((-80.0, -6.0), (80.0, -6.0)), False, tags_t),
        OsmWay(-201, "big_roads", ((80.0, -6.0), (900.0, -6.0)), False, tags_r),
        OsmWay(-203, "big_roads", ((-80.0, -6.0), (-900.0, -6.0)), False, tags_r),
        # a mapped bridge way right where the OBJECT bridge stands
        OsmWay(-301, "big_roads", ((150.0, -80.0), (150.0, 80.0)), False,
               {"highway": "service", "bridge": "yes", "width": "10", "layer": "1"}),
    )


def _object_bridge_map(objs, law, name):
    airport = _airport(objs, law, [(name, (150.0, -6.0), 90.0, 0.0)], _tunnel_ways())
    cells = [Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside", "runway", {}),
             Cell(1, "apron", "apron1", _rect(-80, -60, 80, 60), (), None, None, "airside", "apron", {})]
    objects, rep = read_objects(airport, law)
    cl = Classification(tuple(cells), (), {}, ())
    cl2, tunnels, st = build_structures(airport, cl, law, objects)
    pm, stats = build(airport, cl, law)
    return airport, tunnels, st, pm


def test_object_bridge_governs_and_clears(objs, law):
    airport, tunnels, st, pm = _object_bridge_map(objs, law, "bridge")
    east = next(t for t in tunnels if t.axis[0][0] > 0)
    assert st.object_decks == 1 and st.decks == 0            # the object law governs
    d = east.decks[0]
    assert d.datum == "deck_top" and d.ref.startswith("object_deck:") and d.z is not None
    assert east.climb_from_s >= d.s1                          # the cut stays at datum under it
    assert not any(f.ref.startswith("bridge_deck:") for f in pm.faces.values())
    rows = structures(pm, law, airport)
    bands = [r for r in rows if isinstance(r, Band)]
    assert bands and all(b.hi == pytest.approx(d.z - law.tables.structures.bridge.clearance_m)
                         for b in bands)
    cs, counts, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=True))
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    under = [sol.z[b.v] for b in bands]
    assert max(under) <= d.z - law.tables.structures.bridge.clearance_m + 1e-6


def test_low_object_bridge_is_an_iis(objs, law):
    airport, tunnels, st, pm = _object_bridge_map(objs, law, "low")
    cs, counts, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=True))
    assert sol.status is not Status.OPTIMAL
    assert any("deck_top" in s.ruling for _r, s in sol.iis), sol.iis[:5]
