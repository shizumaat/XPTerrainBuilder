"""Twins for THE INSET-BOX MESH RULE (#233, lane meshbox233): the curv_tol
weight map covers an airport's elevation-inset box at the inset's class,
and a tile with no fine inset keeps today's map byte for byte.  Plus the
twin of the instrument that measured it (``tools/mesh_inset_error.py``)."""
import json
import os
import pickle
import sys
import types

import numpy
import pytest

import O4_Mesh_Utils as MESH

TOOLS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools")


class _Boundary:
    def __init__(self, bounds):
        self.bounds = bounds


def _tile(**overrides):
    tile = types.SimpleNamespace(
        lat=39, lon=-107, curvature_tol=2.0, apt_curv_tol=0.5,
        apt_curv_ext=0.5, coast_curv_tol=2.0, coast_curv_ext=0.5)
    tile.__dict__.update(overrides)
    return tile


def _legacy_map(tile, boundary):
    """Today's airport rectangle, spelled out (the pre-#233 map)."""
    import O4_Geo_Utils as GEO
    weights = numpy.ones((1001, 1001), dtype=numpy.float32)
    (xmin, ymin, xmax, ymax) = boundary
    x_shift = 1000 * tile.apt_curv_ext * GEO.m_to_lon(tile.lat)
    y_shift = 1000 * tile.apt_curv_ext * GEO.m_to_lat
    weights[
        max(round(((1 - ymax) - y_shift) * 1000), 0):
        min(round(((1 - ymin) + y_shift) * 1000), 1000) + 1,
        max(round((xmin - x_shift) * 1000), 0):
        min(round((xmax + x_shift) * 1000), 1000) + 1,
    ] = tile.curvature_tol / tile.apt_curv_tol
    return weights


@pytest.fixture
def built(tmp_path, monkeypatch):
    """``build(tile, boundary, inset_boxes)`` -> the weight map
    ``build_curv_tol_weight_map`` writes for one airport and those
    insets."""
    apt_file = str(tmp_path / "Data.apt")

    def build(tile, boundary, inset_boxes):
        with open(apt_file, "wb") as handle:
            pickle.dump({"KXXX": {"boundary": _Boundary(boundary)}}, handle)
        monkeypatch.setattr(MESH.FNAMES, "apt_file", lambda _tile: apt_file)
        monkeypatch.setattr(MESH.INSETS, "baked_inset_boxes",
                            lambda _tile: list(inset_boxes))
        weights = numpy.ones((1001, 1001), dtype=numpy.float32)
        MESH.build_curv_tol_weight_map(tile, weights)
        return weights

    return build


BOUNDARY = (0.130, 0.215, 0.140, 0.235)          # tile-relative degrees
# ~3 km around it: far larger than the boundary + 0.5 km rectangle.
BOX = (-107 + 0.100, 39 + 0.189, -107 + 0.162, 39 + 0.253)


def test_weight_scales_with_the_inset_class():
    assert MESH.inset_box_curv_weight(1.0) == 30.0
    assert MESH.inset_box_curv_weight(5.0) == 6.0
    assert MESH.inset_box_curv_weight(10.0) == 3.0
    assert MESH.inset_box_curv_weight(30.0) == 1.0
    assert MESH.inset_box_curv_weight(90.0) == 1.0     # never loosens


def test_one_metre_inset_box_is_covered_beyond_the_airport_rectangle(built):
    tile = _tile()
    weights = built(tile, BOUNDARY, [(BOX, 1.0, "KXXX_usgs3dep.tif")])
    rows = slice(round((1 - 0.253) * 1000), round((1 - 0.189) * 1000) + 1)
    columns = slice(100, 162 + 1)
    assert (weights[rows, columns] == 30.0).all()
    # ... the whole box, which the legacy rectangle does not reach ...
    legacy = _legacy_map(tile, BOUNDARY)
    assert (legacy[rows, columns] == 1.0).any()
    # ... and nothing outside it.
    outside = numpy.ones_like(weights, dtype=bool)
    outside[rows, columns] = False
    assert (weights[outside] == 1.0).all()


def test_no_inset_keeps_todays_map_byte_identical(built):
    tile = _tile()
    weights = built(tile, BOUNDARY, [])
    assert weights.tobytes() == _legacy_map(tile, BOUNDARY).tobytes()


def test_base_class_inset_keeps_todays_map_byte_identical(built):
    tile = _tile()
    weights = built(tile, BOUNDARY, [(BOX, 30.0, "KXXX_copernicusglo30.tif")])
    assert weights.tobytes() == _legacy_map(tile, BOUNDARY).tobytes()


def test_coarser_inset_never_loosens_the_airport_rectangle(built):
    tile = _tile()
    weights = built(tile, BOUNDARY, [(BOX, 10.0, "KXXX_x.tif")])
    legacy = _legacy_map(tile, BOUNDARY)
    assert (weights >= legacy).all()
    assert weights.max() == 4.0 and (weights == 3.0).any()


def test_airport_density_switch_turns_the_box_rule_off(built):
    tile = _tile(apt_curv_tol=2.0)                # == curvature_tol: off
    weights = built(tile, BOUNDARY, [(BOX, 1.0, "KXXX_usgs3dep.tif")])
    assert (weights == 1.0).all()


def test_box_is_clipped_to_the_tile():
    tile = _tile()
    weights = numpy.ones((1001, 1001), dtype=numpy.float32)
    raised = MESH.apply_inset_box_curv_weights(
        tile, weights, [((-107.02, 38.99, -106.99, 39.01), 1.0)])
    assert raised == 11 * 11 and (weights[-11:, :11] == 30.0).all()
    assert MESH.apply_inset_box_curv_weights(
        tile, weights, [((-105.5, 39.2, -105.4, 39.3), 1.0)]) == 0


# ── the instrument ────────────────────────────────────────────────────

def _write_mesh(path, vertices, triangles):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("MeshVersionFormatted 1\nDimension 3\n\nVertices\n")
        handle.write("%d\n" % len(vertices))
        for (lon, lat, z) in vertices:
            handle.write("%.9f %.9f %.9f 0\n" % (lon, lat, z / 100000.0))
        handle.write("\nTriangles\n%d\n" % len(triangles))
        for (a, b, c) in triangles:
            handle.write("%d %d %d 0\n" % (a + 1, b + 1, c + 1))


def test_mesh_inset_error_reads_the_facet_offset(tmp_path):
    gdal = pytest.importorskip("osgeo.gdal")
    sys.path.insert(0, TOOLS)
    import mesh_inset_error

    # A 0.02 deg inset: the plane z = 100 + 1000 * (lon - west).
    (west, north, pixel, size) = (10.0, 50.02, 0.0001, 200)
    raster = numpy.tile(
        100.0 + 1000.0 * ((numpy.arange(size) + 0.5) * pixel), (size, 1))
    inset = str(tmp_path / "KXXX_test.tif")
    dataset = gdal.GetDriverByName("GTiff").Create(
        inset, size, size, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((west, pixel, 0, north, 0, -pixel))
    dataset.GetRasterBand(1).WriteArray(raster.astype(numpy.float32))
    dataset = None

    def plane(lon, offset):
        return 100.0 + 1000.0 * (lon - west) + offset

    corners = [(10.004, 50.004), (10.016, 50.004), (10.016, 50.016),
               (10.004, 50.016)]
    graded = str(tmp_path / "KXXX.graded.json")
    with open(graded, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"vertices": [[0, 50.009, 10.009], [1, 50.009, 10.011],
                                [2, 50.011, 10.011], [3, 50.011, 10.009]],
                   "faces": [{"ring": [0, 1, 2, 3]}]}, handle)
    reports = {}
    for (name, offset) in (("on", 0.0), ("off", 2.5)):
        mesh = str(tmp_path / (name + ".mesh"))
        _write_mesh(mesh, [(lon, lat, plane(lon, offset))
                           for (lon, lat) in corners],
                    [(0, 1, 2), (0, 2, 3)])
        reports[name] = mesh_inset_error.measure(mesh, inset, [graded])
    on = reports["on"]["regions"]["box_outside_patch"]
    off = reports["off"]["regions"]["box_outside_patch"]
    assert on["triangles"] == 2
    assert on["centroid_abs_error_m"]["max"] < 0.01
    assert abs(off["centroid_abs_error_m"]["p50"] - 2.5) < 0.01
    assert abs(off["vertex_abs_error_m"]["p95"] - 2.5) < 0.01
    assert reports["on"]["patch_vertices"]["n"] == 0
    assert mesh_inset_error.format_report(reports["off"])
