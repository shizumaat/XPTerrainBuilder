"""#1336: an inland pond's drawn depth ramps up from its shore, not a pit.

X-Plane 12 draws the bed of a ``terrain_Water`` vertex at its depth ratio
times the depth from the mesh's (flat) water surface down to the DSF
``sea_level`` raster.  Before #1336 every inland vertex off the shore got
ratio 1, so a small pond over a raster bed 7 m down (the owner's
-41.333237416, 174.813714740: surface 7.08-7.12 m, raster 0 m) became a
7 m pit with walls one triangle wide.  This twin is a synthetic depressed
pond on the real pipeline functions: recut, mask bounds, the inland ramp,
``set_depth_ratio``.
"""
import os
import sys
import types

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Bathymetry as BATHY  # noqa: E402

LAT, LON = -41.0, 174.0
DEG_M = 111319.49
SURFACE_M, RASTER_BED_M = 7.1, 0.0


def grid_mesh(n=13, cell_m=10.0, water=lambda i, j: False):
    """An n x n grid of vertices, two triangles per cell, each triangle
    classed 0 land / 1 inland / 2 sea by ``water(i, j)`` of its cell."""
    coslat = numpy.cos(numpy.radians(LAT))
    coords = []
    for j in range(n):
        for i in range(n):
            coords += [LON + i * cell_m / (DEG_M * coslat),
                       LAT + j * cell_m / DEG_M, SURFACE_M, 0.0, 0.0]
    tris, classes = [], []
    for j in range(n - 1):
        for i in range(n - 1):
            a, b = j * n + i, j * n + i + 1
            c, d = a + n, b + n
            tris += [a, b, d, a, d, c]
            classes += [water(i, j)] * 2
    return (numpy.array(coords, dtype=float),
            numpy.array(tris, dtype=numpy.int64),
            numpy.array(classes, dtype=numpy.int64))


def pond(i, j):
    """A 60 m square pond (cells 3..8) in land: the owner's pond's size."""
    return 1 if 3 <= i <= 8 and 3 <= j <= 8 else 0


def ratios(coords, tris, classes, ramp):
    tile = types.SimpleNamespace(lat=LAT, lon=LON, mask_zl=14,
                                 ratio_bathy=1.0)
    (nbr_nodes, coords, node_types, node_is_coast, _n, tris,
     classes) = BATHY.recut_water_tris(coords, tris, classes)
    node_bathy = 255 * numpy.ones(nbr_nodes, dtype=numpy.uint8)
    if ramp:
        BATHY.inland_depth_from_shore(node_bathy, coords, tris, classes, LAT)
    water = set(numpy.asarray(tris).reshape(-1, 3)[classes > 0].ravel())
    xy = coords.reshape(-1, 5)[:, :2]
    return {n: (xy[n], BATHY.set_depth_ratio(n, node_is_coast, node_bathy,
                                             tile))
            for n in sorted(water)}, node_is_coast


def drawn_depth(ratio):
    return ratio * (SURFACE_M - RASTER_BED_M)


def shore_distance_m(lonlat):
    """Distance to the pond's square shoreline (x, y in 30..90 m)."""
    coslat = numpy.cos(numpy.radians(LAT))
    x = (lonlat[0] - LON) * DEG_M * coslat
    y = (lonlat[1] - LAT) * DEG_M
    return min(x - 30, 90 - x, y - 30, 90 - y)


def test_unramped_pond_is_a_pit():
    """The defect, reproduced: full raster depth half an edge off shore."""
    by_node, is_coast = ratios(*grid_mesh(water=pond), ramp=False)
    interior = [r for n, (_xy, r) in by_node.items() if not is_coast[n]]
    assert interior and min(interior) == 1.0


def test_ramped_pond_deepens_with_distance_from_shore():
    by_node, is_coast = ratios(*grid_mesh(water=pond), ramp=True)
    pixel_m = BATHY.ZL16_PIXEL_EQUATOR_M * numpy.cos(numpy.radians(LAT))
    for n, (lonlat, ratio) in by_node.items():
        if is_coast[n]:
            assert ratio == 0
            continue
        d = shore_distance_m(lonlat)
        # set_depth_ratio's own ramp on the measured shore distance.
        expected = max(min(10 * round(d / pixel_m) / 255, 1), 0.1)
        assert ratio == pytest.approx(expected, abs=1e-9), (lonlat, d)
    centre = max(r for n, (_xy, r) in by_node.items() if not is_coast[n])
    # 30 m from shore: 0.65 of the raster depth, not all of it.
    assert drawn_depth(centre) < 0.7 * (SURFACE_M - RASTER_BED_M)


def test_lake_reaches_full_depth_beyond_the_ramp():
    """A 1 km lake keeps its full raster depth past ~46 m from shore."""
    def lake(i, j):
        return 1 if 1 <= i <= 22 and 1 <= j <= 22 else 0
    by_node, is_coast = ratios(*grid_mesh(n=25, cell_m=50.0, water=lake),
                               ramp=True)
    interior = [r for n, (_xy, r) in by_node.items() if not is_coast[n]]
    assert max(interior) == 1.0
    assert min(interior) < 1.0


def test_sea_vertices_keep_the_sea_rule():
    """Water touching the sea is the masks' business, never the ramp's."""
    def sea_and_pond(i, j):
        if i >= 9:
            return 2
        return pond(i, j) if i <= 8 else 0
    coords, tris, classes = grid_mesh(water=sea_and_pond)
    (nbr_nodes, coords, _types, _coast, _n, tris,
     classes) = BATHY.recut_water_tris(coords, tris, classes)
    node_bathy = 255 * numpy.ones(nbr_nodes, dtype=numpy.uint8)
    BATHY.inland_depth_from_shore(node_bathy, coords, tris, classes, LAT)
    sea_nodes = set(numpy.asarray(tris).reshape(-1, 3)[classes == 2].ravel())
    assert all(node_bathy[n] == 255 for n in sea_nodes)


def test_no_inland_water_is_a_no_op():
    coords, tris, classes = grid_mesh()
    node_bathy = 255 * numpy.ones(len(coords) // 5, dtype=numpy.uint8)
    assert BATHY.inland_depth_from_shore(
        node_bathy, coords, tris, classes, LAT) == 0
    assert (node_bathy == 255).all()


def test_dsf_build_calls_the_ramp_after_the_masks():
    import inspect

    import O4_DSF_Utils as DSF
    source = inspect.getsource(DSF._build_dsf_body)
    masks = source.index("compute_depth_ratio_bounds_from_masks")
    assert source.index("inland_depth_from_shore", masks) > masks
