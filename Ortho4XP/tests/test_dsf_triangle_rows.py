"""The DSF builder's array helpers answer what the per-element code they
replaced answered (#850): byte-identical DSFs rest on it."""
import os
import random
import sys

import numpy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_DSF_Utils as DSF  # noqa: E402
import O4_Geo_Arrays as GEO_ARRAYS  # noqa: E402
import O4_Geo_Utils as GEO  # noqa: E402


def _boundary_points(zoomlevel, lat=37.5, lon=-8.5, count=200):
    """Points exactly on orthogrid boundaries (the guard's case)."""
    (x0, y0) = GEO.wgs84_to_orthogrid(lat, lon, zoomlevel)
    return [GEO.gtile_to_wgs84(x0 + 16 * (k % 9), y0 + 16 * (k % 7),
                               zoomlevel) for k in range(count)]


def test_orthogrid_of_arrays_is_the_scalar_one():
    rng = numpy.random.default_rng(5)
    lat = list(rng.uniform(-80, 80, 20000)) + [
        p[0] for z in (14, 16, 19) for p in _boundary_points(z)]
    lon = list(rng.uniform(-180, 179.9, 20000)) + [
        p[1] for z in (14, 16, 19) for p in _boundary_points(z)]
    for zoomlevel in (14, 16, 19):
        (til_x, til_y) = GEO_ARRAYS.wgs84_to_orthogrid(
            numpy.array(lat), numpy.array(lon), zoomlevel)
        assert list(zip(til_x.tolist(), til_y.tolist(), strict=True)) == [
            GEO.wgs84_to_orthogrid(a, b, zoomlevel)
            for (a, b) in zip(lat, lon, strict=True)]


def test_triangle_rows_are_the_per_element_reads():
    rng = numpy.random.default_rng(7)
    nodes = 3000
    coords = numpy.zeros(5 * (nodes + 50))          # resized past the end
    coords[0:5 * nodes:5] = rng.uniform(-9, -8, nodes)
    coords[1:5 * nodes:5] = rng.uniform(37, 38, nodes)
    for (k, (b_lat, b_lon)) in enumerate(_boundary_points(16, count=100)):
        coords[5 * k] = b_lon
        coords[5 * k + 1] = b_lat
    nbr_tris = 70000                                # more than one chunk
    tri_idx = rng.integers(0, nodes, 3 * (nbr_tris + 9)).astype(numpy.uint32)
    tri_idx[:300] = numpy.repeat(numpy.arange(100), 3)
    tri_types = rng.integers(0, 3, nbr_tris + 9).astype(numpy.uint8)
    rows = list(DSF._triangle_rows(coords, tri_idx, tri_types, nbr_tris, 16))
    assert len(rows) == nbr_tris
    for tri in list(range(0, nbr_tris, 37)) + list(range(100)):
        (n1, n2, n3) = tri_idx[3 * tri: 3 * tri + 3]
        bary_lon = (coords[5 * n1] + coords[5 * n2] + coords[5 * n3]) / 3
        bary_lat = (coords[5 * n1 + 1] + coords[5 * n2 + 1]
                    + coords[5 * n3 + 1]) / 3
        expected = (n1, n2, n3, tri_types[tri],
                    GEO.wgs84_to_orthogrid(bary_lat, bary_lon, 16))
        assert rows[tri] == expected
        assert all(type(v) is int for v in rows[tri][:4])


def test_remap_of_arrays_is_the_scalar_remap():
    raw = numpy.arange(0, 64, dtype=numpy.uint16).repeat(3)
    for use_masks_for_inland in (False, True):
        for has_water in (3, 7):
            got = DSF._remap_water_tri_types(
                raw, use_masks_for_inland, has_water)
            assert got.dtype == raw.dtype
            assert got.tolist() == [
                DSF.remap_water_tri_type(int(v), use_masks_for_inland,
                                         has_water) for v in raw]


def test_float2qquad_writes_the_binary_repr_digits():
    r = random.Random(11)
    values = [r.random() for _ in range(50000)] + [
        0.0, -0.0, -1e-12, -2.0 ** -32, 2.0 ** -32, 0.5, 1 - 1e-16, 1.0, 1.5]
    for x in values:
        expected = ("1" * DSF.QQUAD_BITS if x >= 1 else numpy.binary_repr(
            int((1 << DSF.QQUAD_BITS) * x)).zfill(DSF.QQUAD_BITS))
        assert DSF.float2qquad(x) == expected
