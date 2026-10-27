"""#1395 (RULINGS 2026-10-26f): inland water gets its own shallow bed.

X-Plane 12 draws the bed of a ``terrain_Water`` vertex at its depth ratio
times the height of the mesh's water surface over the DSF ``sea_level``
raster.  Inland water must never read the sea's depth: its bed is the
#1336 shore ramp scaled to ``INLAND_BED_DEPTH_M``.  The engine sets the
raster to the surface less that depth under inland water and scales the
ratio wherever the raster cannot hold it.  These twins run the real
pipeline functions (recut, shore ramp, raster, ratio) on synthetic water
over a real-size 1201-post raster and read the drawn depth the way the
sim does.
"""
import os
import sys
import types

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Bathymetry as BATHY  # noqa: E402
import O4_DSF_Utils as DSF  # noqa: E402

LAT, LON = -42.0, 174.0
POSTS = DSF.DSF_RASTER_POSTS
DEG_M = 111319.49
CAP = BATHY.INLAND_BED_DEPTH_M
# The tile's south-west corner sits on a post; start the water a few
# posts in so every bilinear neighbour exists.
X0_M, Y0_M = 1000.0, 1000.0


def grid_mesh(n, cell_m, water, surface=lambda i, j: 7.1):
    """An n x n vertex grid, two triangles per cell, classed by
    ``water(i, j)`` (0 land / 1 inland / 2 sea), vertex z ``surface``."""
    coslat = numpy.cos(numpy.radians(LAT))
    coords = []
    for j in range(n):
        for i in range(n):
            coords += [LON + (X0_M + i * cell_m) / (DEG_M * coslat),
                       LAT + (Y0_M + j * cell_m) / DEG_M,
                       surface(i, j), 0.0, 0.0]
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


def raster_at(raster, lon, lat):
    """The sim's bilinear read of a post-centric raster (row 0 south)."""
    x = (lon - LON) * (POSTS - 1)
    y = (lat - LAT) * (POSTS - 1)
    (i, j) = (int(x), int(y))
    (fx, fy) = (x - i, y - j)
    r = raster.astype(float)
    return ((r[j, i] * (1 - fx) + r[j, i + 1] * fx) * (1 - fy)
            + (r[j + 1, i] * (1 - fx) + r[j + 1, i + 1] * fx) * fy)


def build(mesh, raster_bed=0.0):
    """Run the DSF stage's water steps; return per water vertex
    ``(class set, distance ramp ratio, drawn depth, drawn depth before)``
    and the raster before and after."""
    (coords, tris, classes) = mesh
    tile = types.SimpleNamespace(lat=LAT, lon=LON, mask_zl=14,
                                 ratio_bathy=1.0)
    (nbr, coords, _types, is_coast, _n, tris,
     classes) = BATHY.recut_water_tris(coords, tris, classes)
    bathy = 255 * numpy.ones(nbr, dtype=numpy.uint8)
    BATHY.inland_depth_from_shore(bathy, coords, tris, classes, LAT)
    before = numpy.full((POSTS, POSTS), raster_bed, dtype=numpy.int16)
    after = before.copy()
    BATHY.set_inland_bed(after, coords, tris, classes, LAT, LON)
    scale = BATHY.inland_depth_scale(after, coords, tris, classes, LAT, LON)
    t3 = numpy.asarray(tris).reshape(-1, 3)
    xyz = coords.reshape(-1, 5)
    out = {}
    for cls in (1, 2):
        for n in set(t3[classes == cls].ravel()):
            out.setdefault(n, set()).add(cls)
    rows = {}
    for n, cls in out.items():
        (lon, lat, z) = xyz[n, :3]
        old = BATHY.set_depth_ratio(n, is_coast, bathy, tile)
        new = BATHY.set_depth_ratio(n, is_coast, bathy, tile, scale)
        rows[n] = (cls, old, new * (z - raster_at(after, lon, lat)),
                   old * (z - raster_at(before, lon, lat)))
    return rows, before, after


def pond(i, j):
    """A 60 m square pond in land, the size of the owner's pond."""
    return 1 if 3 <= i <= 8 and 3 <= j <= 8 else 0


def lake(i, j):
    """A 1.1 km square lake."""
    return 1 if 1 <= i <= 22 and 1 <= j <= 22 else 0


def test_pond_is_never_deeper_than_the_cap():
    rows, _before, after = build(grid_mesh(13, 10.0, pond))
    depths = [d for (_c, _r, d, _old) in rows.values()]
    assert max(depths) <= CAP + 1e-9
    assert min(depths) >= 0.0
    # Before #1395 the same pond drew up to 7.1 m x ramp.
    assert max(old for (*_x, old) in rows.values()) > CAP
    # The raster under the pond is its own surface less the cap.
    assert (after == numpy.floor(7.1 - CAP)).any()


def test_pond_bed_is_the_shore_ramp_times_the_cap():
    rows, _b, _a = build(grid_mesh(13, 10.0, pond))
    for (_c, ramp, depth, _old) in rows.values():
        assert depth == pytest.approx(ramp * CAP, abs=1e-6)


def test_one_km_lake_is_capped_and_reaches_the_cap():
    rows, _b, _a = build(grid_mesh(25, 50.0, lake))
    depths = [d for (_c, _r, d, _o) in rows.values()]
    assert max(depths) == pytest.approx(CAP, abs=1e-6)
    assert max(depths) <= CAP + 1e-9


def test_alpine_lake_ignores_a_deep_raster():
    """A lake 1,500 m up over a 0 m raster bed is still 3 m deep."""
    mesh = grid_mesh(25, 50.0, lake, surface=lambda i, j: 1500.0)
    rows, _b, _a = build(mesh)
    assert max(d for (_c, _r, d, _o) in rows.values()) <= CAP + 1e-9


def test_two_levels_on_one_post_stay_capped():
    """A river stepping 5 m inside one raster cell: the post takes the
    lower surface, the ratio caps the upper one."""
    def river(i, j):
        return 1 if 3 <= j <= 8 else 0
    mesh = grid_mesh(13, 10.0, river,
                     surface=lambda i, j: 12.0 if i < 6 else 7.0)
    rows, _b, _a = build(mesh)
    assert max(d for (_c, _r, d, _o) in rows.values()) <= CAP + 1e-9


def test_sea_is_untouched():
    """Sea vertices keep their ratio and every post the sea reaches
    keeps the sea's raster; the pond beside it is still capped."""
    def sea_and_pond(i, j):
        if i >= 30:
            return 2
        return pond(i, j)
    rows, before, after = build(grid_mesh(60, 10.0, sea_and_pond))
    for (cls, _ramp, depth, old) in rows.values():
        if 2 in cls:
            assert depth == pytest.approx(old, abs=1e-9)
        else:
            assert depth <= CAP + 1e-9
    # Posts within one post of a sea triangle are unchanged.
    coslat = numpy.cos(numpy.radians(LAT))
    sea_x0 = (LON + (X0_M + 30 * 10.0) / (DEG_M * coslat) - LON) * (POSTS - 1)
    first_sea_col = int(numpy.floor(sea_x0)) - 1
    assert (after[:, first_sea_col:] == before[:, first_sea_col:]).all()
    assert (after != before).any()


def test_dsf_blob_edit_keeps_the_other_rasters():
    elevation = numpy.full((POSTS, POSTS), 9, dtype=numpy.int16)
    sea_level = numpy.zeros((POSTS, POSTS), dtype=numpy.int16)
    blob = (DSF._raster_sub_atoms(elevation)
            + DSF._raster_sub_atoms(sea_level))
    (coords, tris, classes) = grid_mesh(13, 10.0, pond)
    tile = types.SimpleNamespace(lat=LAT, lon=LON)
    (edited, scale) = DSF.inland_bed(blob, coords, tris, classes, tile)
    assert len(edited) == len(blob)
    half = len(DSF._raster_sub_atoms(elevation))
    assert edited[:half] == blob[:half]
    assert edited != blob
    assert scale is not None and scale.shape == (len(coords) // 5,)
    # No raster in the blob: nothing to edit, no scale.
    assert DSF.inland_bed(b"", coords, tris, classes, tile) == (b"", None)


def test_dsf_build_sets_the_bed_before_the_ratios():
    import inspect
    source = inspect.getsource(DSF._build_dsf_body)
    bed = source.index("inland_bed(")
    assert source.index("set_depth_ratio", bed) > bed
    assert source.count("node_bathy, tile, node_scale") == 4


def test_dsf_build_keeps_the_rasters_it_read_early():
    """The rasters are read before the ratios; nothing may reset them
    before they are written (the first closing build wrote none)."""
    import inspect
    import re
    source = inspect.getsource(DSF._build_dsf_body)
    read = source.index("= elevation_and_bathymetry_data(tile)")
    assert not re.search(r"\bbDEM[NS]\s*=\s*b\"\"", source[read:])
