"""M1 planar-map twins: the CYXY fixture builds a map that passes
I1-I7 with zero T-vertices, every edge once with both faces, faces
covering the classified pavement, a DEM sample on every vertex, chords
at the law's cap and vertices on the identity grid; the T-vertex
detector fires on an injected one; the CLI writes its products under
the 5 s target."""
from __future__ import annotations

import dataclasses as _dc
import importlib
import json
import time
from pathlib import Path

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport.load import load
from auto_patch_v2.classify import classify
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import chord_cap_m
from auto_patch_v2.model.planar import (Edge, EdgeKind, Face, PlanarError,
                                        PlanarMap, Vertex, validate)
from auto_patch_v2.planar import PlanarIndex, build, face_polygon, to_geojson
from auto_patch_v2.planar.build import _t_vertices
from auto_patch_v2.planar.chords import densify, stations

from test_airport_load import FIX, fixture_inputs

SRC = Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2"


@pytest.fixture(scope="module")
def cyxy_map():
    law = Law.for_airport("CYXY")
    a = load("CYXY", fixture_inputs(), law)
    cl = classify(a, law)
    t0 = time.perf_counter()
    pm, stats = build(a, cl, law)
    return a, law, cl, pm, stats, time.perf_counter() - t0


def test_import_and_budget():
    assert importlib.import_module("auto_patch_v2.planar")
    for py in (SRC / "planar").glob("*.py"):
        assert len(py.read_text().splitlines()) <= 1000, py


def test_invariants_and_counts(cyxy_map):
    a, law, cl, pm, stats, wall = cyxy_map
    validate(pm)                                    # I1..I7
    assert stats.t_vertices == 0
    assert stats.vertices == len(pm.vertices) and stats.vertices <= 6660
    assert stats.faces >= 200 and stats.edges > stats.faces
    assert all(v.dem_z is not None for v in pm.vertices.values())
    pairs = {e.length_key for e in pm.edges.values()}
    assert len(pairs) == len(pm.edges)               # every edge exactly once
    assert all(len(pm.faces_of_edge(e)) >= 1 for e in pm.edges)
    # both faces recorded: an edge between two pavement faces names both
    two = [e for e in pm.edges.values() if e.left_face is not None and e.right_face is not None]
    assert len(two) > stats.edges // 2
    assert stats.min_vertex_spacing_m >= law.tables.emit.identity.min_distinct_spacing_m - 1e-9
    assert stats.max_chord_m <= law.tables.emit.chords.pavement_max_chord_m + 1e-6
    assert wall < 5.0


def test_faces_cover_the_classified_pavement(cyxy_map):
    a, law, cl, pm, stats, wall = cyxy_map
    cells = unary_union([Polygon(c.ring, c.holes) for c in cl.cells])
    faces = unary_union([face_polygon(pm, f) for f, face in pm.faces.items()
                         if face.role != "graded_strip"])
    assert faces.area == pytest.approx(cells.area, rel=0.01)
    assert cells.difference(faces).area < 0.01 * cells.area
    assert faces.difference(cells).area < 0.01 * cells.area
    roles = {f.role for f in pm.faces.values()}
    assert {"runway", "runway_crossing", "apron", "building", "graded_strip"} <= roles
    for f in pm.faces.values():
        assert f.role in law.tables.precedence.roles
        assert f.side == law.tables.precedence.roles[f.role].side
    strips = [f for f in pm.faces.values() if f.role == "graded_strip"]
    assert strips and all(f.ref.startswith("adjacent_ground:") for f in strips)
    assert any(f.code_number == 4 for f in strips) and any(f.code_letter for f in strips)


def test_breaklines_and_edge_kinds(cyxy_map):
    a, law, cl, pm, stats, wall = cyxy_map
    kinds = {b.kind for b in pm.breaklines.values()}
    assert {"runway_profile", "taxi_centerline", "road_centerline"} <= kinds
    for b in pm.breaklines.values():
        vs = b.vertices(pm)
        assert len(vs) == len(b.edges) + 1
        for eid in b.edges:
            assert pm.edges[eid].kind in (EdgeKind.BREAKLINE, EdgeKind.CENTERLINE)
    prof = [b for b in pm.breaklines.values() if b.kind == "runway_profile"]
    assert {b.ref for b in prof} == {"02/20", "14L/32R", "14R/32L"}
    spacing = law.tables.emit.chords.station_spacing_m
    for b in prof:
        for eid in b.edges:
            e = pm.edges[eid]
            (ax, ay), (bx, by) = pm.vertices[e.a].xy, pm.vertices[e.b].xy
            assert ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 <= spacing + 1.0
    assert any(e.kind == EdgeKind.ZONE for e in pm.edges.values())


def test_t_vertex_detector_fires():
    """A vertex on an edge's interior that is not its endpoint: the
    builder cannot produce one; the detector and I5 both catch it."""
    pts = {0: (0, 0), 1: (10, 0), 2: (10, 10), 3: (0, 10), 4: (20, 0), 5: (20, 10),
           6: (10, 5)}
    inc = {0: (0,), 1: (0, 1), 2: (0, 1), 3: (0,), 4: (1,), 5: (1,), 6: (1,)}
    verts = {i: Vertex(i, tuple(map(float, p)), (float(p[1]), float(p[0])), 1.0, inc[i])
             for i, p in pts.items()}
    E = EdgeKind.BOUNDARY
    edges = {0: Edge(0, 0, 1, 0, None, E), 1: Edge(1, 1, 2, 0, None, E),
             2: Edge(2, 2, 3, 0, None, E), 3: Edge(3, 3, 0, 0, None, E),
             4: Edge(4, 1, 4, None, 1, E), 5: Edge(5, 4, 5, None, 1, E),
             6: Edge(6, 5, 2, None, 1, E), 7: Edge(7, 2, 6, None, 1, E),
             8: Edge(8, 6, 1, None, 1, E)}
    faces = {0: Face(0, "apron", "p", (0, 1, 2, 3), ()),
             1: Face(1, "stub", "t", (4, 5, 6, 7, 8), ())}
    pm = PlanarMap("T", verts, edges, faces, {})
    assert _t_vertices(pm) == 1          # vertex 6 lies on edge 1 (1-2)
    validate(pm)                         # the dataclass invariants alone accept it...
    # ...and a map where the shared edge is one record cannot express it:
    inc2 = dict(inc)
    inc2[6] = (0, 1)
    verts2 = {i: _dc.replace(v, incident_faces=inc2[i]) for i, v in verts.items()}
    with pytest.raises(PlanarError, match="I5"):
        validate(PlanarMap("T", verts2, edges, faces, {}))


def test_chords():
    pts = densify([(0.0, 0.0), (100.0, 0.0)], 30.0)
    assert len(pts) == 5 and pts[-1] == (100.0, 0.0)
    assert all(abs(b[0] - a[0]) <= 30.0 + 1e-9 for a, b in zip(pts, pts[1:]))
    ring = densify([(0.0, 0.0), (50.0, 0.0), (50.0, 50.0)], 60.0, closed=True)
    assert ring[0] == ring[-1] and len(ring) == 5
    assert len(stations([(0.0, 0.0), (0.0, 25.0)], 12.0)) == 4


def test_index_and_geojson(cyxy_map, tmp_path):
    a, law, cl, pm, stats, wall = cyxy_map
    idx = PlanarIndex(pm)
    fid = next(iter(pm.faces))
    p = face_polygon(pm, fid).representative_point()
    assert fid in idx.faces_at(p.x, p.y)
    faces, lines = to_geojson(pm, a.frame)
    assert len(faces["features"]) == len(pm.faces)
    assert len(lines["features"]) == len(pm.breaklines)
    g = faces["features"][0]["geometry"]["coordinates"][0]
    assert g[0] == g[-1] and abs(g[0][1] - 60.71) < 0.05


def test_cli_writes_products(tmp_path):
    from auto_patch_v2.planar.__main__ import main
    out = tmp_path / "planar"
    t0 = time.perf_counter()
    rc = main(["CYXY", "--out", str(out), "--xplane-root", str(FIX),
               "--cifp-dir", str(FIX / "CIFP"), "--data-root", str(FIX),
               "--dem-frame", "authored"])
    assert rc == 0 and time.perf_counter() - t0 < 5.0
    rep = json.loads((out / "report.json").read_text())
    assert rep["planar"]["t_vertices"] == 0 and rep["planar"]["faces"] > 0
    assert (out / "faces.geojson").stat().st_size > 1000
    assert (out / "breaklines.geojson").stat().st_size > 100
    assert rep["load"]["pack_name"] == "CYXY Fixture"
    assert rep["wall_s"]["total"] < 5.0
