"""The uniform-grid index of ``auto_patch.mesh_sampler`` (RULINGS
2026-09-12g).

The grid replaced a per-query LINEAR SCAN over every retained triangle's
bounding box.  It is an ACCELERATOR, not a new answer: these twins pin
that down against a reference implementation of the scan that was
deleted, on the points where an accelerator is most likely to diverge —
SHARED EDGES and SHARED VERTICES, where two or three triangles all
contain the point and the answer is decided by visit order.

Three twins:

* ``test_grid_matches_linear_scan`` — the deleted scan, re-implemented
  here, against :meth:`MeshElevationSampler.sample_at`, bit for bit
  (elevation, terrain type, ``OutsideMeshError``).
* ``test_sample_many_matches_sample_at`` — the batch form against the
  point form, bit for bit.
* ``test_engine_surface_carries_many`` — the engine's ``_surface``
  closure carries the ``.many`` attribute ``placement_geom.surface_many``
  batches through (RULINGS 2026-09-12g (2)); without it the shipped path
  silently takes the per-point fallback.
"""

from __future__ import annotations

import os
import random

import numpy
import pytest

from auto_patch.mesh_sampler import (
    MeshElevationSampler,
    MeshSample,
    OutsideMeshError,
    WATER_BIT_MASK,
)


# ----------------------------------------------------------------------
# A synthetic mesh with DELIBERATELY UNEVEN triangle sizes: a fine block
# (an airport's own triangles) inside a coarse one (the countryside), so
# the grid's bucket spans are not uniform and the cell-count ladder has
# something to choose between.
# ----------------------------------------------------------------------

def _write_mesh(path: str, vertices, triangles) -> None:
    with open(path, "w") as handle:
        handle.write("MeshVersionFormatted 2\nDimension 3\n\nVertices\n")
        handle.write("%d\n" % len(vertices))
        for longitude, latitude, elevation in vertices:
            handle.write("%.12f %.12f %.12f 0\n"
                         % (longitude, latitude, elevation / 100000.0))
        handle.write("\nNormals\n0\n\nTriangles\n")
        handle.write("%d\n" % len(triangles))
        for a, b, c, attribute in triangles:
            handle.write("%d %d %d %d\n" % (a + 1, b + 1, c + 1, attribute))


def _block(vertices, triangles, x0, y0, x1, y1, steps, seed):
    """Triangulate a rectangle into ``steps`` x ``steps`` split quads."""
    rng = random.Random(seed)
    base = len(vertices)
    for row in range(steps + 1):
        for column in range(steps + 1):
            longitude = x0 + (x1 - x0) * column / steps
            latitude = y0 + (y1 - y0) * row / steps
            vertices.append(
                (longitude, latitude, 100.0 + 40.0 * rng.random()))
    width = steps + 1
    for row in range(steps):
        for column in range(steps):
            sw = base + row * width + column
            se = sw + 1
            nw = sw + width
            ne = nw + 1
            # Water bits on a scattering of triangles so is_water is a
            # real discriminator and not a constant.
            triangles.append((sw, se, ne, 1 if rng.random() < 0.2 else 0))
            triangles.append((sw, ne, nw, 4 if rng.random() < 0.2 else 0))


@pytest.fixture(scope="module")
def uneven_mesh(tmp_path_factory) -> str:
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int, int]] = []
    _block(vertices, triangles, 10.0, 50.0, 10.02, 50.02, 12, 1)   # coarse
    _block(vertices, triangles, 10.008, 50.008, 10.012, 50.012, 40, 2)  # fine
    path = str(tmp_path_factory.mktemp("mesh") / "uneven.mesh")
    _write_mesh(path, vertices, triangles)
    return path


@pytest.fixture(scope="module")
def uneven_sampler(uneven_mesh) -> MeshElevationSampler:
    return MeshElevationSampler(uneven_mesh, (10.0, 50.0, 10.02, 50.02),
                                margin_degrees=0.0)


def _linear_scan(sampler: MeshElevationSampler, latitude: float,
                 longitude: float) -> "MeshSample | None":
    """The prefilter the grid replaced, verbatim (RULINGS 2026-09-12g).

    This is the reference the grid is an accelerator OF; it exists only
    here, and only so the equivalence has something to be asserted
    against.
    """
    candidate_indices = numpy.nonzero(
        (sampler._triangle_minimum[:, 0] <= longitude)
        & (sampler._triangle_maximum[:, 0] >= longitude)
        & (sampler._triangle_minimum[:, 1] <= latitude)
        & (sampler._triangle_maximum[:, 1] >= latitude)
    )[0]
    for candidate_index in candidate_indices:
        corner_a = sampler._corner_a[candidate_index]
        corner_b = sampler._corner_b[candidate_index]
        corner_c = sampler._corner_c[candidate_index]
        denominator = (corner_b[1] - corner_c[1]) * (
            corner_a[0] - corner_c[0]
        ) + (corner_c[0] - corner_b[0]) * (corner_a[1] - corner_c[1])
        if abs(denominator) < 1e-18:
            continue
        weight_a = (
            (corner_b[1] - corner_c[1]) * (longitude - corner_c[0])
            + (corner_c[0] - corner_b[0]) * (latitude - corner_c[1])
        ) / denominator
        weight_b = (
            (corner_c[1] - corner_a[1]) * (longitude - corner_c[0])
            + (corner_a[0] - corner_c[0]) * (latitude - corner_c[1])
        ) / denominator
        weight_c = 1.0 - weight_a - weight_b
        if weight_a >= -1e-9 and weight_b >= -1e-9 and weight_c >= -1e-9:
            attribute = int(sampler._triangle_attributes[candidate_index])
            return MeshSample(
                elevation_metres=float(
                    weight_a * corner_a[2]
                    + weight_b * corner_b[2]
                    + weight_c * corner_c[2]
                ),
                terrain_type=attribute,
                is_water=bool(attribute & WATER_BIT_MASK),
            )
    return None


def _query_points(sampler: MeshElevationSampler) -> list[tuple[float, float]]:
    """Vertices, edge midpoints, triangle centroids, off-mesh points and
    a random scatter — the shared-edge and shared-vertex cases first."""
    points: list[tuple[float, float]] = []
    corners = (sampler._corner_a, sampler._corner_b, sampler._corner_c)
    count = len(sampler._triangles)
    step = max(1, count // 400)
    for index in range(0, count, step):
        a = corners[0][index]
        b = corners[1][index]
        c = corners[2][index]
        for corner in (a, b, c):                      # SHARED VERTICES
            points.append((float(corner[1]), float(corner[0])))
        for first, second in ((a, b), (b, c), (c, a)):  # SHARED EDGES
            points.append((float((first[1] + second[1]) / 2.0),
                           float((first[0] + second[0]) / 2.0)))
        points.append((float((a[1] + b[1] + c[1]) / 3.0),
                       float((a[0] + b[0] + c[0]) / 3.0)))
    rng = random.Random(7)
    for _ in range(2000):                              # interior scatter
        points.append((50.0 + 0.02 * rng.random(),
                       10.0 + 0.02 * rng.random()))
    for _ in range(200):                               # OFF the mesh
        points.append((50.0 + 0.05 * rng.random() + 0.03,
                       10.0 + 0.05 * rng.random() + 0.03))
    return points


def test_grid_picks_a_ladder_cell_count(uneven_sampler):
    assert uneven_sampler._grid_cells in MeshElevationSampler._GRID_LADDER
    entries = int(uneven_sampler._grid_start[-1])
    assert entries == len(uneven_sampler._grid_triangles)
    assert entries <= (
        MeshElevationSampler._GRID_MAX_ENTRIES_PER_TRIANGLE
        * len(uneven_sampler._triangles)
    )


def test_grid_buckets_are_index_sorted(uneven_sampler):
    """The tie-break at a shared edge IS this ordering."""
    starts = uneven_sampler._grid_start
    for cell in range(0, len(starts) - 1):
        bucket = uneven_sampler._grid_triangles[starts[cell]:starts[cell + 1]]
        if len(bucket) > 1:
            assert numpy.all(numpy.diff(bucket) > 0)


def test_grid_matches_linear_scan(uneven_sampler):
    points = _query_points(uneven_sampler)
    assert len(points) > 3000
    inside = 0
    for latitude, longitude in points:
        expected = _linear_scan(uneven_sampler, latitude, longitude)
        try:
            got = uneven_sampler.sample_at(latitude, longitude)
        except OutsideMeshError:
            got = None
        assert (got is None) == (expected is None), (latitude, longitude)
        if got is not None:
            inside += 1
            # BIT-identical, not approximately equal.
            assert got.elevation_metres == expected.elevation_metres
            assert got.terrain_type == expected.terrain_type
            assert got.is_water == expected.is_water
    assert inside > 2000          # the oracle must not be all-misses
    assert inside < len(points)   # ... nor all-hits


def test_sample_many_matches_sample_at(uneven_sampler):
    points = _query_points(uneven_sampler)
    latitudes = [p[0] for p in points]
    longitudes = [p[1] for p in points]
    batch = uneven_sampler.sample_many(latitudes, longitudes)
    assert len(batch) == len(points)
    for index, (latitude, longitude) in enumerate(points):
        try:
            one = uneven_sampler.sample_at(latitude, longitude)
        except OutsideMeshError:
            one = None
        many = batch[index]
        assert (one is None) == (many is None), (latitude, longitude)
        if one is not None:
            assert many.elevation_metres == one.elevation_metres
            assert many.terrain_type == one.terrain_type
            assert many.is_water == one.is_water


def test_sample_many_edges():
    """Empty input, length mismatch."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "mesh",
                        "synthetic_fan_three_triangles.mesh")
    sampler = MeshElevationSampler(path, (10.0, 50.0, 10.001, 50.001))
    assert sampler.sample_many([], []) == []
    with pytest.raises(ValueError):
        sampler.sample_many([50.0, 50.0], [10.0])


def test_engine_surface_carries_many(monkeypatch):
    """``_surface`` must satisfy ``placement_geom.surface_many``'s
    ``.many`` protocol, and the memo must not change an answer."""
    from auto_patch import engine_v2
    from auto_patch_v2.airport import placement_geom

    calls = {"point": 0, "batch": 0}

    def sample(latitude, longitude):
        calls["point"] += 1
        return (round(latitude + longitude, 6), False)

    def sample_many(latitudes, longitudes):
        calls["batch"] += 1
        return [(round(a + o, 6), False)
                for a, o in zip(latitudes, longitudes)]

    sample.many = sample_many
    surface = engine_v2._placement_surface(sample)
    assert callable(getattr(surface, "many", None))

    points = [(1.0, 2.0, 0.0), (3.0, 4.0, 0.0), (1.0, 2.0, 0.0)]
    batched = placement_geom.surface_many(surface, points)
    assert batched == [3.0, 7.0, 3.0]
    assert calls["batch"] == 1
    # the memo: a repeat costs no sampler call
    before = calls["point"]
    assert surface(1.0, 2.0) == 3.0
    assert surface(1.0, 2.0) == 3.0
    assert calls["point"] == before      # both served by the batch's memo
    assert surface(9.0, 9.0) == 18.0
    assert calls["point"] == before + 1


def test_engine_surface_many_without_batch_sampler():
    """A sampler with no ``.many`` still yields a working ``.many``."""
    from auto_patch import engine_v2
    from auto_patch_v2.airport import placement_geom

    def sample(latitude, longitude):
        if latitude < 0:
            return None
        return (latitude * 10.0, False)

    surface = engine_v2._placement_surface(sample)
    assert callable(getattr(surface, "many", None))
    assert placement_geom.surface_many(
        surface, [(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    ) == [10.0, 20.0]
