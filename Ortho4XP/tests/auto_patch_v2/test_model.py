"""M0 model twins: frame identity, planar-map invariants, constraint
rows, graded-surface JSON round trip, and the package import/dependency
direction."""
from __future__ import annotations

import dataclasses as _dc
import importlib
import re
from pathlib import Path

import pytest

from auto_patch_v2.emit.surface import (SCHEMA, GradedSurface, SurfaceBreakline,
                                        SurfaceFace, SurfaceVertex)
from auto_patch_v2.model.constraints import (Band, ConstraintSet, Diff, Flat,
                                             Offset, Pin, Source)
from auto_patch_v2.model.frame import Frame, identity_key
from auto_patch_v2.model.planar import (Breakline, Edge, EdgeKind, Face,
                                        PlanarError, PlanarMap, Vertex,
                                        validate)

SRC = Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2"


# ── frame ────────────────────────────────────────────────────────────────

def test_identity_key_is_rounding_not_proximity():
    a = identity_key(60.709599999999, -135.067100000001, 11)
    b = identity_key(60.7096, -135.0671, 11)
    assert a == b
    assert identity_key(60.7096, -135.0671, 11) != \
        identity_key(60.70960000001, -135.0671, 11)


def test_frame_round_trip_cyxy():
    fr = Frame(icao="CYXY", origin=(60.7096, -135.0671), identity_dp=11)
    to_xy, to_ll = fr.transformers()
    x, y = to_xy(-135.0671, 60.7096)
    assert abs(x) < 1e-6 and abs(y) < 1e-6
    x, y = to_xy(-135.05, 60.72)
    lat, lon = to_ll(x, y)
    assert abs(lat - 60.72) < 1e-9 and abs(lon + 135.05) < 1e-9
    assert 900 < x < 1000 and 1100 < y < 1200
    assert fr.key(60.72, -135.05) == (60.72, -135.05)


# ── planar map ───────────────────────────────────────────────────────────

def _square_map(dem=100.0) -> PlanarMap:
    """Two faces sharing one edge: 0-1-2-3 (apron) and 1-4-5-2 (stub)."""
    pts = {0: (0, 0), 1: (10, 0), 2: (10, 10), 3: (0, 10), 4: (20, 0),
           5: (20, 10)}
    inc = {0: (0,), 1: (0, 1), 2: (0, 1), 3: (0,), 4: (1,), 5: (1,)}
    vertices = {i: Vertex(i, tuple(map(float, p)), (float(p[1]), float(p[0])),
                          dem, inc[i]) for i, p in pts.items()}
    E = EdgeKind.BOUNDARY
    edges = {
        0: Edge(0, 0, 1, 0, None, E), 1: Edge(1, 1, 2, 0, 1, E),
        2: Edge(2, 2, 3, 0, None, E), 3: Edge(3, 3, 0, 0, None, E),
        4: Edge(4, 1, 4, None, 1, E), 5: Edge(5, 4, 5, None, 1, E),
        6: Edge(6, 5, 2, None, 1, E),
    }
    faces = {0: Face(0, "apron", "p1", (0, 1, 2, 3), ()),
             1: Face(1, "stub", "t1", (4, 5, 6, 1), (), code_letter="C")}
    bl = {0: Breakline(0, "taxi_centerline", "t1", (4, 5))}
    return PlanarMap("TEST", vertices, edges, faces, bl)


def test_valid_map_passes_and_derives():
    pm = _square_map()
    validate(pm)
    assert pm.faces_of_edge(1) == (0, 1)
    assert pm.edges_of_vertex()[1] == (0, 1, 4)
    assert pm.breaklines[0].vertices(pm) == (1, 4, 5)


def test_invariants_are_enforced():
    pm = _square_map()
    # I7 no DEM
    v = dict(pm.vertices)
    v[3] = _dc.replace(v[3], dem_z=None)
    with pytest.raises(PlanarError, match="I7"):
        validate(_dc.replace(pm, vertices=v))
    # I1 duplicate key (two vertices, one coordinate)
    v = dict(pm.vertices)
    v[3] = _dc.replace(v[3], key=v[0].key)
    with pytest.raises(PlanarError, match="I1"):
        validate(_dc.replace(pm, vertices=v))
    # I2 an edge twice
    e = dict(pm.edges)
    e[7] = Edge(7, 2, 1, 0, 1, EdgeKind.BOUNDARY)
    with pytest.raises(PlanarError, match="I2"):
        validate(_dc.replace(pm, edges=e))
    # I3 no face either side
    e = dict(pm.edges)
    e[0] = _dc.replace(e[0], left_face=None)
    with pytest.raises(PlanarError, match="I3"):
        validate(_dc.replace(pm, edges=e))
    # I4 ring does not close
    f = dict(pm.faces)
    f[0] = _dc.replace(f[0], ring=(0, 1, 2))
    with pytest.raises(PlanarError, match="I4"):
        validate(_dc.replace(pm, faces=f))
    # I5 incident faces incomplete (the T-vertex class)
    v = dict(pm.vertices)
    v[1] = _dc.replace(v[1], incident_faces=(0,))
    with pytest.raises(PlanarError, match="I5"):
        validate(_dc.replace(pm, vertices=v))
    # I6 breakline edges not adjacent
    b = {0: Breakline(0, "x", "x", (0, 6))}
    with pytest.raises(PlanarError, match="I6"):
        validate(_dc.replace(pm, breaklines=b))


# ── constraints ──────────────────────────────────────────────────────────

def test_constraint_set_counts_and_sources():
    s = Source("runway_profile", "2026-08-05", ("rwy:14L/32R",))
    cs = ConstraintSet(
        pins=(Pin(0, 700.0, s),),
        diffs=(Diff(0, 1, 0.015, 100.0, s), Diff(1, 2, 0.015, 50.0, s)),
        flats=(Flat((3, 4, 5), Source("pads", "2026-09-01g")),),
        bands=(Band(6, None, 705.0, Source("zones", "2026-08-01")),),
        offsets=(Offset(7, 8, 5.1, Source("tunnels", "2026-09-03b")),))
    assert cs.counts() == {"pins": 1, "diffs": 2, "flats": 1, "bands": 1,
                           "offsets": 1, "linears": 0}
    assert cs.vertices() == frozenset(range(9))
    assert cs.by_generator() == {"runway_profile": 3, "pads": 1, "zones": 1,
                                 "tunnels": 1}
    assert cs.diffs[0].bound_m == pytest.approx(1.5)
    assert cs.merged(cs).counts()["diffs"] == 4
    assert cs.rows()[0] is cs.pins[0]
    with pytest.raises(NotImplementedError):
        cs.to_sparse()


# ── graded surface ───────────────────────────────────────────────────────

def test_graded_surface_json_round_trip():
    gs = GradedSurface(
        icao="CYXY", ruleset="icao", origin=(60.7096, -135.0671), crs="+proj=tmerc",
        identity_dp=11,
        vertices=(SurfaceVertex(0, (60.70960000001, -135.0671), 703.123456),
                  SurfaceVertex(1, (60.7097, -135.0671), 703.2),
                  SurfaceVertex(2, (60.7097, -135.0670), 703.3)),
        faces=(SurfaceFace(0, "apron", "p1", (0, 1, 2), (), "airside"),),
        breaklines=(SurfaceBreakline(0, "taxi_centerline", "t", (0, 1)),),
        provenance={"law_sha256": "x"})
    text = gs.to_json()
    back = GradedSurface.from_json(text)
    assert back.to_json() == text
    assert back.vertices[0].z == 703.12       # ONE quantisation, 2 dp
    assert back.vertices[0].ll == (60.70960000001, -135.0671)
    assert back.faces[0].ring == (0, 1, 2)
    d = gs.to_dict()
    assert set(d) == set(SCHEMA["required"])
    with pytest.raises(ValueError):
        GradedSurface.from_dict({"schema": "other"})


# ── package hygiene ──────────────────────────────────────────────────────

def test_package_imports_and_stubs():
    assert importlib.import_module("auto_patch_v2")
    api = importlib.import_module("auto_patch_v2.solve.api")
    assert callable(api.solve)                      # M2: implemented (highs.solve)
    osm = importlib.import_module("auto_patch_v2.emit.osm_adapter")
    assert callable(osm.write_patch)                # M2: implemented
    s2 = importlib.import_module("auto_patch_v2.emit.s2_adapter")
    with pytest.raises(NotImplementedError):
        s2.rasterise(None, (), 1.0)


def test_no_v1_import_no_env_gate_no_geometry_in_model():
    for py in SRC.rglob("*.py"):
        text = py.read_text()
        assert "from auto_patch " not in text and "import auto_patch\n" \
            not in text and "auto_patch." not in text.replace(
                "auto_patch_v2", ""), py
        assert "os.environ" not in text and "getenv" not in text, py
        assert len(text.splitlines()) <= 1000, py
        if py.parent.name in ("model", "law"):
            assert not re.search(r"^\s*(import|from)\s+(shapely|numpy)",
                                 text, re.M), py


def test_dependency_direction():
    """law <- model <- solve <- emit; the M1 producers airport <-
    classify <- planar import law + model and each other in that order;
    nothing imports upward (M0 §1)."""
    order = ["law", "model", "solve", "emit"]
    producers = {"airport": {"law", "model"},
                 "classify": {"law", "model", "airport"},
                 "planar": {"law", "model", "airport", "classify"},
                 # M2: constraints import law + model (+ nothing of v2 above);
                 # verify reads law/model/emit and the constraints' pure
                 # geometry; pipeline is the orchestrator and reads everything
                 "constraints": {"law", "model"},
                 "verify": {"law", "model", "emit", "constraints"},
                 "pipeline": {"law", "model", "airport", "classify", "planar",
                              "constraints", "solve", "emit", "verify"}}
    for py in SRC.rglob("*.py"):
        pkg = py.parent.name if py.parent != SRC else None
        imports = re.findall(r"from \.\.(\w+)", py.read_text())
        if pkg in producers:
            for m in imports:
                assert m in producers[pkg], (py, m)
            continue
        if pkg not in order:
            continue
        for m in imports:
            assert order.index(m) < order.index(pkg), (py, m)
    for pkg in ("airport", "classify", "planar"):
        assert (SRC / pkg / "__init__.py").is_file()
