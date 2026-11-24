"""O4_Mask_Water_Squares answers what the retired per-triangle loop of
``O4_Mask_Utils.record_water_tris`` answered (issue #2269): the same
squares, the same triangles, in the same order."""
import os
import sys

import numpy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Geo_Utils as GEO  # noqa: E402
import O4_Mask_Water_Squares as WATER_SQUARES  # noqa: E402


def _loop_keys(til_x, til_y, a, b):
    """The retired ``_mask_squares_for_tri``, kept here as the reference."""
    keys = [(til_x, til_y)]
    if a == 0:
        keys.append((til_x - 16, til_y))
        if b == 0:
            keys.append((til_x - 16, til_y - 16))
        elif b == 3:
            keys.append((til_x - 16, til_y + 16))
    elif a == 3:
        keys.append((til_x + 16, til_y))
        if b == 0:
            keys.append((til_x + 16, til_y - 16))
        elif b == 3:
            keys.append((til_x + 16, til_y + 16))
    if b == 0:
        keys.append((til_x, til_y - 16))
    elif b == 3:
        keys.append((til_x, til_y + 16))
    return keys


def _loop(coords, triangles, rows, zoomlevel, bounds):
    """The retired loop, one triangle at a time, as a dict of lists."""
    (til_x_min, til_y_min, til_x_max, til_y_max) = bounds
    pt_in = coords.ravel()
    found = {}
    kept = []
    for i in rows:
        (n1, n2, n3) = triangles[i]
        (lon1, lat1) = pt_in[5 * n1:5 * n1 + 2]
        (lon2, lat2) = pt_in[5 * n2:5 * n2 + 2]
        (lon3, lat3) = pt_in[5 * n3:5 * n3 + 2]
        bary_lat = (lat1 + lat2 + lat3) / 3
        bary_lon = (lon1 + lon2 + lon3) / 3
        (til_x, til_y) = GEO.wgs84_to_orthogrid(bary_lat, bary_lon, zoomlevel)
        if (til_x < til_x_min - 16 or til_x > til_x_max + 16
                or til_y < til_y_min - 16 or til_y > til_y_max + 16):
            continue
        kept.append(i)
        (til_x2, til_y2) = GEO.wgs84_to_orthogrid(
            bary_lat, bary_lon, zoomlevel + 2)
        tri = (lat1, lon1, lat2, lon2, lat3, lon3)
        for key in _loop_keys(til_x, til_y, (til_x2 // 16) % 4,
                              (til_y2 // 16) % 4):
            found.setdefault(key, []).append(tri)
    return (kept, found)


def _mesh(seed, lat=37, lon=-9, nodes=2000, tris=5000, zoomlevel=14):
    rng = numpy.random.default_rng(seed)
    coords = numpy.zeros((nodes, 5))
    coords[:, 0] = rng.uniform(lon - 0.2, lon + 1.2, nodes)
    coords[:, 1] = rng.uniform(lat - 0.2, lat + 1.2, nodes)
    # Nodes ON square boundaries at both zoom levels: the guard's case.
    for k in range(0, min(400, nodes - 1), 2):
        (b_lat, b_lon) = GEO.gtile_to_wgs84(
            GEO.wgs84_to_orthogrid(lat + 0.5, lon + 0.5, zoomlevel)[0]
            + 16 * (k % 7), GEO.wgs84_to_orthogrid(
                lat + 0.5, lon + 0.5, zoomlevel)[1] + 16 * (k % 5),
            zoomlevel)
        coords[k:k + 2, 0] = b_lon
        coords[k:k + 2, 1] = b_lat
    triangles = rng.integers(0, nodes, (tris, 3))
    # Degenerate triangles whose barycentre IS a boundary node.
    boundary = numpy.arange(0, min(300, nodes - 1), 2)[:min(150, tris)]
    triangles[:boundary.size] = boundary[:, None]
    return (coords, triangles)


def _bounds(lat, lon, zoomlevel):
    (x_min, y_min) = GEO.wgs84_to_orthogrid(lat + 1, lon, zoomlevel)
    (x_max, y_max) = GEO.wgs84_to_orthogrid(lat, lon + 1, zoomlevel)
    return (x_min, y_min, x_max, y_max)


def test_groups_match_the_loop_value_for_value_and_in_order():
    for seed in (1, 2, 3):
        (coords, triangles) = _mesh(seed)
        rows = numpy.flatnonzero(
            numpy.random.default_rng(seed + 10).random(len(triangles)) < 0.6)
        bounds = _bounds(37, -9, 14)
        (kept, groups) = WATER_SQUARES.water_tris_by_square(
            coords, triangles, rows, 14, bounds)
        (loop_kept, loop_found) = _loop(coords, triangles, rows, 14, bounds)
        assert kept.tolist() == loop_kept
        assert [key for (key, _) in groups] == list(loop_found)
        for (key, tris) in groups:
            assert tris == loop_found[key]
            assert all(type(v) is float for v in tris[0])
            assert all(type(v) is int for v in key)


def test_no_rows_and_no_kept_rows():
    (coords, triangles) = _mesh(4, nodes=50, tris=40)
    bounds = _bounds(37, -9, 14)
    (kept, groups) = WATER_SQUARES.water_tris_by_square(
        coords, triangles, [], 14, bounds)
    assert kept.size == 0 and groups == []
    far = _bounds(10, 50, 14)
    (kept, groups) = WATER_SQUARES.water_tris_by_square(
        coords, triangles, numpy.arange(40), 14, far)
    assert kept.size == 0 and groups == []
