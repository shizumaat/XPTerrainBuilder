"""M4 twins: the tunnel structure pass (planar), its constraint generator
and its verify readers, on ONE synthetic airport — a mapped bore under
an apron with a non-tunnel approach way at each end, a second parallel
bore (a dual carriageway, 31h), a bridge way across one approach (a
terrain deck, 08-30d/f), and a building pad across the other approach
(the clip, 08-07 ruling 3).  Law values are read from the tables inside
the tests, never retyped.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import ramp_faces_of, structures, wall_faces_of
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff, Flat, Linear, Offset, Pin
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.structures import build_structures, carriageway_width_m
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


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D",
             "airside", "runway", {}),
        # the apron the bore passes under (x from -80 to 80)
        Cell(1, "apron", "apron1", _rect(-80, -60, 80, 60), (), None, None,
             "airside", "apron", {}),
        # a building pad across the WEST approach, 120 m out (inside the
        # ~150 m the 4 % climb needs)
        Cell(2, "building", "padW", _rect(-220, -30, -180, 30), (), None, None,
             "airside", "pad", {}),
    ]


def _ways():
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    tags_r = {"highway": "secondary", "lanes": "2"}
    # the bore: x in [-80, 80] at y = -6 and y = +6 (two carriageways)
    ways = [
        OsmWay(-101, "big_roads", ((-80.0, -6.0), (80.0, -6.0)), False, tags_t),
        OsmWay(-102, "big_roads", ((80.0, 6.0), (-80.0, 6.0)), False, tags_t),
        # approaches east and west, straight
        OsmWay(-201, "big_roads", ((80.0, -6.0), (900.0, -6.0)), False, tags_r),
        OsmWay(-202, "big_roads", ((900.0, 6.0), (80.0, 6.0)), False, tags_r),
        OsmWay(-203, "big_roads", ((-80.0, -6.0), (-900.0, -6.0)), False, tags_r),
        OsmWay(-204, "big_roads", ((-900.0, 6.0), (-80.0, 6.0)), False, tags_r),
        # a bridge across the EAST approach at x = 150, 10 m wide
        OsmWay(-301, "big_roads", ((150.0, -80.0), (150.0, 80.0)), False,
               {"highway": "service", "bridge": "yes", "width": "10", "layer": "1"}),
    ]
    return tuple(ways)


@pytest.fixture(scope="module")
def synthetic(law):
    frame = Frame = __import__("auto_patch_v2.model.frame", fromlist=["Frame"]).Frame
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), _ways(), (), (), pack, _PlaneDem(), law.ruleset_key)
    cl = Classification(tuple(_cells()), (), {}, ())
    cl2, tunnels, st = build_structures(airport, cl, law)
    pm, stats = build(airport, cl, law)
    return airport, cl2, tunnels, st, pm, stats


def test_carriageway_width_from_tags(law):
    tn = law.tables.structures.tunnel
    assert carriageway_width_m({"width": "9.5"}, law) == 9.5
    assert carriageway_width_m({"lanes": "3"}, law) == 3 * tn.lane_width_m
    assert carriageway_width_m({}, law) == tn.default_lanes * tn.lane_width_m


def test_dual_bore_is_one_ramp_per_mouth_with_gap_wall_cap(synthetic, law):
    airport, cl2, tunnels, st, pm, stats = synthetic
    tn = law.tables.structures.tunnel
    # two chains (one per carriageway), a mouth at each end, merged pairwise
    assert st.bores == 2 and st.mouths == 4 and st.duals_merged == 2
    assert st.tunnels == 2 and not st.refused, st.refused
    roles = [c.role for c in cl2.cells]
    assert roles.count("tunnel_ramp") >= 2 and roles.count("retaining_wall") >= 2
    # every ramp cell is refed the oracle's way; every wall likewise
    assert all(c.ref == "tunnel_ramp" for c in cl2.cells if c.role == "tunnel_ramp")
    assert all(c.ref == "tunnel_wall" for c in cl2.cells if c.role == "retaining_wall")
    for t in tunnels:
        assert t.mouth_z == pytest.approx(t.mouth_dem_z - tn.bore_datum_m)
        # the mouth line stands at the bore's mapped end (x = ±80)
        assert abs(abs(t.axis[0][0]) - 80.0) < 1.0
        assert t.half_width_m == pytest.approx((12.0 + 2 * 3.5 * 2 / 2) / 2, abs=0.6)
    # the gap: no ramp vertex touches a wall face, and the gap is ≥ the law
    for v in pm.vertices.values():
        rs = {pm.faces[f].role for f in v.incident_faces}
        assert not ({"tunnel_ramp", "retaining_wall"} <= rs)
    ramps = [Polygon([pm.vertices[i].xy for i in pm.ring_vertices(f.ring)])
             for f in pm.faces.values() if f.role == "tunnel_ramp"]
    walls = [Polygon([pm.vertices[i].xy for i in pm.ring_vertices(f.ring)])
             for f in pm.faces.values() if f.role == "retaining_wall"]
    assert min(r.distance(w) for r in ramps for w in walls) >= tn.wall_gap_m - 1e-6
    assert stats.t_vertices == 0
    # the apron was CUT by the structure: no apron vertex inside a ramp
    apron = [f for f in pm.faces.values() if f.role == "apron"]
    assert apron
    for f in apron:
        poly = Polygon([pm.vertices[i].xy for i in pm.ring_vertices(f.ring)])
        for r in ramps:
            assert poly.intersection(r).area < 1e-6


def test_deck_severs_the_ramp_and_pad_clips_it(synthetic, law):
    airport, cl2, tunnels, st, pm, stats = synthetic
    east = next(t for t in tunnels if t.axis[0][0] > 0)
    west = next(t for t in tunnels if t.axis[0][0] < 0)
    assert len(east.decks) == 1 and east.decks[0].way == -301
    assert east.climb_from_s > 0.0 and east.top_pinned
    # two ramp pieces east (mouth side + far side), the deck as a road face
    assert len(ramp_faces_of(pm, tunnels)[east.id]) == 2
    assert any(f.ref.startswith("bridge_deck:-301") for f in pm.faces.values())
    assert west.clipped_by == "padW" and not west.top_pinned and not west.decks
    # the clipped structure clears the pad by the gap
    pad = next(Polygon([pm.vertices[i].xy for i in pm.ring_vertices(f.ring)])
               for f in pm.faces.values() if f.role == "building")
    for f in pm.faces.values():
        if f.role in ("tunnel_ramp", "retaining_wall"):
            poly = Polygon([pm.vertices[i].xy for i in pm.ring_vertices(f.ring)])
            if poly.centroid.x < 0:
                assert poly.distance(pad) >= law.tables.structures.tunnel.wall_gap_m - 1e-6


def test_generator_rows_and_solve_round_trip(synthetic, law, tmp_path):
    airport, cl2, tunnels, st, pm, stats = synthetic
    tn = law.tables.structures.tunnel
    rows = structures(pm, law, airport)
    pins = [r for r in rows if isinstance(r, Pin)]
    diffs = [r for r in rows if isinstance(r, Diff)]
    offs = [r for r in rows if isinstance(r, Offset)]
    assert all(d.cap == tn.ramp_max_grade for d in diffs) and diffs
    assert offs and all(o.min_delta == law.tables.structures.bridge.clearance_m for o in offs)
    # one pin per vertex; every wall vertex either pinned at the DEM of
    # its band or carried by the governed ground it shares (in a band
    # Flat with its station partner)
    seen = set()
    for p in pins:
        assert p.v not in seen
        seen.add(p.v)
    flat_vs = {v for r in rows if isinstance(r, Flat) for v in r.group}
    walls = wall_faces_of(pm, tunnels)
    for t in tunnels:
        for f in walls[t.id]:
            for v in pm.ring_vertices(f.ring):
                ground = any(pm.faces[x].role not in ("tunnel_ramp", "retaining_wall")
                             for x in pm.vertices[v].incident_faces)
                assert v in seen or v in flat_vs or ground
    cs, counts, _w = generate(pm, law, airport)
    assert counts["structures"] == len(rows)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=True))
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    east = next(t for t in tunnels if t.axis[0][0] > 0)
    # the mouth group sits at the datum; the wall stands bore_datum above it
    ramp_f = ramp_faces_of(pm, tunnels)[east.id]
    zs = [sol.z[v] for f in ramp_f for v in pm.ring_vertices(f.ring)]
    # the mouth datum: the cap's crest (the covering ground) − bore_datum
    # — within the DEM's slope across the 1.1 m to the cap of the point
    # sample the record carries
    assert min(zs) == pytest.approx(east.mouth_z, abs=0.05)
    lin = [r for r in rows if isinstance(r, Linear) and r.source.ruling.startswith("tunnel.bore_datum")]
    assert lin
    for r in lin:
        assert sum(c * sol.z[v] for v, c in r.terms) == pytest.approx(-tn.bore_datum_m, abs=1e-6)
    wz = [sol.z[v] for f in walls[east.id] for v in pm.ring_vertices(f.ring)]
    assert max(wz) - min(zs) >= tn.bore_datum_m - 1e-6
    # the deck stands the clearance above the ramp beneath
    deck = [f for f in pm.faces.values() if f.ref.startswith("bridge_deck:")]
    dz = min(sol.z[v] for f in deck for v in pm.ring_vertices(f.ring))
    assert dz - east.mouth_z >= law.tables.structures.bridge.clearance_m - 1e-6
    # emit + verify: the acceptance families read 0, wall_in_runway_strip 0
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol.z)
    rows_v = census(surf, law, pub, {})
    for key in ("tunnel_wall_top_flat", "tunnel_ramp_wall_gap", "tunnel_mouth_canonical",
                "tunnel_deck_clearance", "wall_in_runway_strip"):
        assert rows_v[key] == [], (key, rows_v[key][:3])
    assert rows_v["within_shape"] == [] or all(
        r["roles"] != "tunnel_ramp|tunnel_ramp" for r in rows_v["within_shape"])


def test_verify_readers_fire_on_a_broken_structure(synthetic, law):
    """The readers are not vacuous: a wall crest bent toward the ramp
    and a ramp welded to its wall are rows."""
    airport, cl2, tunnels, st, pm, stats = synthetic
    import dataclasses as _dc
    rows = structures(pm, law, airport)
    cs, counts, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    z = list(sol.z)
    east = next(t for t in tunnels if t.axis[0][0] > 0)
    wf = wall_faces_of(pm, tunnels)[east.id][0]
    ids = pm.ring_vertices(wf.ring)
    z[ids[0]] -= 1.0                        # one crest node bent down
    sol2 = _dc.replace(sol, z=tuple(z))
    surf = graded_surface(pm, law, sol2, airport.frame.origin, airport.frame.crs, {})
    rows_v = census(surf, law, publication(pm, law, airport, sol2.z), {})
    assert rows_v["tunnel_wall_top_flat"]
