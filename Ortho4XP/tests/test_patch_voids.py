"""AN UNCOVERED HOLE IS CONSTRAINED, NEVER COVERED (owner KDEN 1.0.557).

39.843615,-104.691320: the void of hole ring -12289 (448,092 m2 inside
``adjacent_ground:taxi:F:zone1#32``; inner faces 65,308 m2) was taken as
patch coverage — the host's closed way is its ring with the hole FILLED and
the hole's own closed way was added as a filled polygon too — so it took an
INTERP_ALT seed and the R18-1b fill laid a plane over a drainage valley.

Pinned here, headless: the host covers its ring minus the hole, a face
inside the hole stays covered, the void takes no INTERP_ALT seed and no
coverage in either step, and the hole ring stays a ``PATCH_RING_MARKER``
edge (``O4_Patch_Voids``).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy
import pytest
from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Mesh_Utils as MESH  # noqa: E402
import O4_Patch_Voids as VOIDS  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402

LAT, LON = 30, 30
HOST = [(0.0010, 0.0010), (0.0090, 0.0010), (0.0090, 0.0090), (0.0010, 0.0090)]
HOLE = [(0.0030, 0.0030), (0.0070, 0.0030), (0.0070, 0.0070), (0.0030, 0.0070)]
INNER = [(0.0030, 0.0030), (0.0045, 0.0030), (0.0045, 0.0045), (0.0030, 0.0045)]
P_HOST = (0.0020, 0.0020)       # the host's annulus: covered
P_VOID = (0.0060, 0.0060)       # in the hole, outside the inner face: void
P_INNER = (0.0037, 0.0037)      # the face inside the hole: covered


class _DEM:
    def alt_vec(self, way):
        return numpy.zeros((len(way), 1))


class _Tile:
    lat, lon = LAT, LON
    auto_patch = "All"

    def __init__(self):
        self.dem = _DEM()


def _write_patch(patch_dir):
    lines = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<osm version='0.6' upload='false' generator='test'>"]
    node_ids = {}
    for ring in (HOST, HOLE, INNER):
        for (x, y) in ring:
            if (x, y) not in node_ids:
                node_ids[(x, y)] = -(len(node_ids) + 1)
                lines.append(
                    f"  <node id='{node_ids[(x, y)]}' lat='{LAT + y:.10f}' "
                    f"lon='{LON + x:.10f}'><tag k='alt_abs' v='75' /></node>")
    for (way_id, ring, tags) in (
            (-100, HOST, (("role", "graded_strip"), ("shapeID", "7"))),
            (-101, HOLE, (("o4_feature", "gap_interior_ring"),
                          ("shapeID", "7"))),
            (-102, INNER, (("role", "graded_strip"), ("shapeID", "8")))):
        lines.append(f"  <way id='{way_id}'>")
        for point in ring + [ring[0]]:
            lines.append(f"    <nd ref='{node_ids[point]}' />")
        for (k, v) in tags:
            lines.append(f"    <tag k='{k}' v='{v}' />")
        lines.append("  </way>")
    lines.append("</osm>")
    (patch_dir / "TEST.patch.osm").write_text("\n".join(lines),
                                             encoding="utf-8")


@pytest.fixture
def included(tmp_path, monkeypatch):
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    _write_patch(patch_dir)
    monkeypatch.setattr(VMAP.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    vector_map = VECT.Vector_Map()
    (area, _list, graded) = VMAP.include_patches(vector_map, _Tile())
    return (vector_map, area, graded)


def _point(xy):
    return geometry.Point(*xy)


def test_the_host_covers_its_ring_minus_the_hole(included):
    (_vm, area, graded) = included
    assert area.covers(_point(P_HOST))
    assert area.covers(_point(P_INNER))
    assert not area.covers(_point(P_VOID))
    assert not graded.covers(_point(P_VOID))


def test_the_void_takes_no_interp_alt_seed(included):
    (vector_map, _area, _graded) = included
    seeds = [geometry.Point(s) for s in vector_map.seeds["INTERP_ALT"]]
    void = geometry.Polygon(HOLE).difference(geometry.Polygon(INNER))
    assert not any(void.contains(s) for s in seeds)
    assert any(geometry.Polygon(INNER).contains(s) for s in seeds)
    annulus = geometry.Polygon(HOST).difference(geometry.Polygon(HOLE))
    assert any(annulus.contains(s) for s in seeds)


def test_the_hole_ring_stays_a_patch_ring_edge(included):
    (vector_map, _area, _graded) = included
    # the hole's east side (x = 0.007) is no other ring's edge
    east = [
        vector_map.data_edges[eid]
        for (eid, (i0, i1)) in vector_map.edges_dico.items()
        if all(abs(vector_map.nodes_dico[i][0] - 0.0070) < 1e-9
               for i in (i0, i1))]
    assert east and set(east) == {VMAP.PATCH_RING_MARKER}


def test_the_voids_are_recorded_for_the_mesh_step(included):
    (vector_map, _area, _graded) = included
    voids = vector_map.patch_voids
    assert voids.covers(_point(P_VOID))
    assert not voids.covers(_point(P_INNER))
    assert voids.area == pytest.approx(0.004 ** 2 - 0.0015 ** 2, rel=1e-6)


def _write_poly(tmp_path):
    points, segments = [], []
    for ring in (HOST, HOLE):
        base = len(points)
        points += ring
        segments += [(base + i, base + (i + 1) % 4) for i in range(4)]
    base = len(points)
    points += [INNER[1], INNER[2], INNER[3]]   # INNER[0] is HOLE[0]
    ids = [0 + 4, base, base + 1, base + 2]
    segments += [(ids[i], ids[(i + 1) % 4]) for i in range(4)]
    node = tmp_path / "Data+30+030.node"
    poly = tmp_path / "Data+30+030.poly"
    node.write_text(f"{len(points)} 2 1 0\n" + "".join(
        f"{i + 1} {x:.9f} {y:.9f} 0.0\n" for i, (x, y) in enumerate(points)))
    poly.write_text(f"0 2 1 0\n\n{len(segments)} 1\n" + "".join(
        f"{k + 1} {a + 1} {b + 1} {VMAP.PATCH_RING_MARKER}\n"
        for k, (a, b) in enumerate(segments)) + "\n0\n\n0\n")
    return (str(node), str(poly))


def test_the_mesh_coverage_leaves_the_void_out(included, tmp_path,
                                               monkeypatch):
    (vector_map, _area, _graded) = included
    (node, poly) = _write_poly(tmp_path)
    monkeypatch.setattr(MESH.FNAMES, "input_node_file", lambda t: node)
    monkeypatch.setattr(MESH.FNAMES, "input_poly_file", lambda t: poly)
    VOIDS.write(poly, vector_map.patch_voids)
    (_coverage, covered) = MESH.patch_coverage_polygon(_Tile())
    assert covered.covers(_point(P_HOST))
    assert covered.covers(_point(P_INNER))
    assert not covered.covers(_point(P_VOID))


def test_no_sidecar_is_the_filled_coverage_of_a_pre_void_poly(
        tmp_path, monkeypatch):
    (node, poly) = _write_poly(tmp_path)
    monkeypatch.setattr(MESH.FNAMES, "input_node_file", lambda t: node)
    monkeypatch.setattr(MESH.FNAMES, "input_poly_file", lambda t: poly)
    (_coverage, covered) = MESH.patch_coverage_polygon(_Tile())
    assert covered.covers(_point(P_VOID))


def test_an_empty_void_removes_a_stale_sidecar(tmp_path):
    poly = str(tmp_path / "x.poly")
    VOIDS.write(poly, geometry.box(0, 0, 1, 1))
    assert VOIDS.read(poly).area == pytest.approx(1.0)
    VOIDS.write(poly, geometry.Polygon())
    assert VOIDS.read(poly) is None
