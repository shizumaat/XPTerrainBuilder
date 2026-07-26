"""Bake resampling (O1), ballot error model (O2), seam harmonization (O3).

Headless: every raster is a synthetic temporary GeoTIFF, no network, no
X-Plane install.  Tests needing GDAL skip cleanly without the bindings.

Covered:
  * O1 -- resample-mode selection (coarse inset -> bilinear, fine inset ->
    area average, gate off -> nearest), the gate-off path being the
    historic nearest stamp EXACTLY, the staircase disappearing from a
    bilinear bake, and the box filter suppressing an alias a point sample
    would fold down;
  * O1 -- ``DEM.alt_vec_bilinear_strict`` semantics (exact at posts,
    nodata outside the extent, renormalising over nodata corners);
  * O2 -- the ideal-bake error model scores the BILINEAR chain the mesher
    renders, asserted against a hand-computed cell;
  * O3 -- two neighbour tiles sharing a seam-straddling inset ballot
    identically, a non-straddling neighbour is not merged, and the gate
    restores the per-tile ballot.
"""

import os

import numpy
import pytest

import O4_File_Names as FNAMES
import O4_DEM_Utils as DEM
import O4_Airport_Elevation_Insets as INSETS

try:
    from osgeo import gdal, osr

    HAS_GDAL = True
except Exception:
    HAS_GDAL = False

requires_gdal = pytest.mark.skipif(
    not HAS_GDAL, reason="osgeo (GDAL python bindings) not available"
)


# =====================================================================
# Helpers
# =====================================================================
def _write_geotiff(path, west, south, east, north, array):
    """Write ``array`` as an EPSG:4326 float32 GeoTIFF over the box."""
    rows, columns = array.shape
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform(
        (west, (east - west) / columns, 0, north, 0, (south - north) / rows)
    )
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    dataset.SetProjection(spatial_reference.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(array.astype(numpy.float32))
    band.FlushCache()
    dataset = None
    return path


class _FakeTile:
    """The subset of a ``CFG.Tile`` the inset code reads."""

    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon
        self.dem = None
        self.custom_dem = ""
        self.airport_elevation_insets = True
        self.airport_elevation_providers = "auto"
        self.airport_elevation_level = "auto"
        self.airport_elevation_inset_margin_m = 1000.0
        self.airport_elevation_inset_feather_m = 60.0
        self.working_grid_arc_seconds = "auto"


class _SyntheticDem:
    """A minimal DEM-like object with the readers under test bound in."""

    def __init__(self, array, x0, y0, x1, y1, nodata=-32768.0):
        self.alt_dem = numpy.asarray(array, dtype=numpy.float32)
        (self.nydem, self.nxdem) = self.alt_dem.shape
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.nodata = nodata

    alt_vec_strict = DEM.DEM.alt_vec_strict
    alt_vec_bilinear_strict = DEM.DEM.alt_vec_bilinear_strict


# =====================================================================
# O1 -- the strict bilinear reader
# =====================================================================
def test_bilinear_strict_is_exact_at_posts_and_nodata_outside():
    # 3x3 posts over [0, 2] x [0, 2] (post spacing 1 degree).
    values = numpy.array(
        [[10.0, 20.0, 30.0],      # north row
         [40.0, 50.0, 60.0],
         [70.0, 80.0, 90.0]],     # south row
    )
    dem = _SyntheticDem(values, 0.0, 0.0, 2.0, 2.0)
    posts = numpy.array(
        [[0.0, 2.0], [1.0, 2.0], [2.0, 2.0],
         [0.0, 1.0], [1.0, 1.0], [2.0, 1.0],
         [0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]
    )
    # Every native post reproduces EXACTLY -- the bake preserves content.
    assert dem.alt_vec_bilinear_strict(posts) == pytest.approx(
        values.ravel()
    )
    # Halfway along the top edge -> the mean of its two posts.
    assert dem.alt_vec_bilinear_strict(
        numpy.array([[0.5, 2.0]])
    )[0] == pytest.approx(15.0)
    # Cell centre -> the mean of its four posts (nearest would give one).
    assert dem.alt_vec_bilinear_strict(
        numpy.array([[0.5, 1.5]])
    )[0] == pytest.approx(30.0)
    # Outside the extent -> the nodata sentinel, exactly as alt_vec_strict.
    outside = numpy.array([[-0.1, 1.0], [2.1, 1.0], [1.0, -0.1]])
    assert list(dem.alt_vec_bilinear_strict(outside)) == [
        dem.nodata, dem.nodata, dem.nodata
    ]


def test_bilinear_strict_renormalises_over_nodata_corners():
    """A node keeps a value while ANY of its four posts has one.

    Propagating nodata instead would erode the inset's data footprint by a
    post all round every hole -- a coverage change the bake must not make.
    """
    values = numpy.array(
        [[10.0, -32768.0],
         [30.0, 50.0]],
    )
    dem = _SyntheticDem(values, 0.0, 0.0, 1.0, 1.0)
    # Cell centre: the valid corners carry weight 0.25 each -> mean of 3.
    assert dem.alt_vec_bilinear_strict(
        numpy.array([[0.5, 0.5]])
    )[0] == pytest.approx((10.0 + 30.0 + 50.0) / 3.0)
    # All four corners nodata -> nodata.
    holed = _SyntheticDem(numpy.full((2, 2), -32768.0), 0.0, 0.0, 1.0, 1.0)
    assert holed.alt_vec_bilinear_strict(
        numpy.array([[0.5, 0.5]])
    )[0] == holed.nodata


# =====================================================================
# O1 -- resample-mode selection
# =====================================================================
def _inset_dem(pixel_degrees, size=8):
    span = pixel_degrees * (size - 1)
    return _SyntheticDem(
        numpy.zeros((size, size)), 0.0, 0.0, span, span
    )


def test_resample_mode_picks_bilinear_for_a_coarser_inset(monkeypatch):
    monkeypatch.delenv("O4_INSET_BAKE_INTERP", raising=False)
    working = 1.0 / 10800.0                     # 1/3 arc-second
    coarse = _inset_dem(1.0 / 3600.0)           # 30 m inset, 3x coarser
    assert INSETS.inset_bake_resample_mode(coarse, working, working) == (
        "bilinear"
    )


def test_resample_mode_picks_area_average_for_a_finer_inset(monkeypatch):
    monkeypatch.delenv("O4_INSET_BAKE_INTERP", raising=False)
    working = 1.0 / 7200.0                      # 1/2 arc-second
    fine = _inset_dem(1.0 / 36000.0)            # ~3 m lidar
    assert INSETS.inset_bake_resample_mode(fine, working, working) == "area"


def test_resample_mode_matched_resolution_stays_bilinear(monkeypatch):
    """Equal postings are not "finer": no box filter, just interpolation."""
    monkeypatch.delenv("O4_INSET_BAKE_INTERP", raising=False)
    working = 1.0 / 3600.0
    same = _inset_dem(1.0 / 3600.0)
    assert INSETS.inset_bake_resample_mode(same, working, working) == (
        "bilinear"
    )


def test_resample_mode_is_nearest_when_the_gate_is_off(monkeypatch):
    monkeypatch.setenv("O4_INSET_BAKE_INTERP", "0")
    working = 1.0 / 10800.0
    for pixel in (1.0 / 3600.0, 1.0 / 36000.0):
        assert INSETS.inset_bake_resample_mode(
            _inset_dem(pixel), working, working
        ) == "nearest"


# =====================================================================
# O1 -- the bake itself
# =====================================================================
def _bake_window(inset, x_coordinates, y_coordinates, step=None):
    """Run the bake's sampler over a destination node grid."""
    x_step = step if step is not None else x_coordinates[1] - x_coordinates[0]
    y_step = step if step is not None else y_coordinates[0] - y_coordinates[1]
    mesh_x, mesh_y = numpy.meshgrid(x_coordinates, y_coordinates)
    query = numpy.column_stack((mesh_x.ravel(), mesh_y.ravel()))
    return INSETS.sample_inset_onto_working_grid(
        inset, query, mesh_x.shape, x_coordinates, y_coordinates,
        x_step, y_step,
    )


def _ramp_inset(posts=9, pixel=3.0 / 3600.0):
    """A COARSE inset carrying a linear ramp: 0, 30, 60 ... metres."""
    span = pixel * (posts - 1)
    values = numpy.tile(
        numpy.arange(posts, dtype=numpy.float32) * 30.0, (posts, 1)
    )
    return _SyntheticDem(values, 0.0, 0.0, span, span)


def test_gate_off_bake_is_the_historic_nearest_stamp(monkeypatch):
    monkeypatch.setenv("O4_INSET_BAKE_INTERP", "0")
    inset = _ramp_inset()
    step = (inset.x1 - inset.x0) / 24.0          # 3x finer than the inset
    xs = inset.x0 + numpy.arange(25) * step
    ys = inset.y1 - numpy.arange(25) * step
    mesh_x, mesh_y = numpy.meshgrid(xs, ys)
    query = numpy.column_stack((mesh_x.ravel(), mesh_y.ravel()))
    baked = _bake_window(inset, xs, ys)
    historic = inset.alt_vec_strict(query).reshape(mesh_x.shape)
    # Byte-identical to the pre-O1 path -- the gate is a true off switch.
    assert numpy.array_equal(baked, historic)


def test_bilinear_bake_removes_the_staircase(monkeypatch):
    """A 30 m inset on a 3x finer grid: nearest steps, bilinear ramps."""
    inset = _ramp_inset()
    step = (inset.x1 - inset.x0) / 24.0
    xs = inset.x0 + numpy.arange(25) * step
    ys = inset.y1 - numpy.arange(25) * step

    monkeypatch.setenv("O4_INSET_BAKE_INTERP", "0")
    nearest = _bake_window(inset, xs, ys)[12]
    monkeypatch.setenv("O4_INSET_BAKE_INTERP", "1")
    bilinear = _bake_window(inset, xs, ys)[12]

    nearest_steps = numpy.diff(nearest)
    bilinear_steps = numpy.diff(bilinear)
    # Nearest: two thirds of the node-to-node steps are dead flat and the
    # rest are a full 30 m riser -- the literal staircase.
    assert (numpy.abs(nearest_steps) < 1e-6).sum() >= 15
    assert numpy.abs(nearest_steps).max() == pytest.approx(30.0)
    # Bilinear: a constant 10 m rise per node, no flat run anywhere.
    assert (numpy.abs(bilinear_steps) < 1e-6).sum() == 0
    assert bilinear_steps == pytest.approx(numpy.full(24, 10.0))
    # ...and every native inset post is still carried EXACTLY.
    assert bilinear[::3] == pytest.approx(numpy.arange(9) * 30.0)


def test_area_average_bake_suppresses_the_alias(monkeypatch):
    """A FINE inset with detail above the grid's Nyquist limit.

    Point-sampling a +/-10 m checkerboard at every third post reads only
    the crests -- a mirror-image artefact that looks like a 10 m plateau.
    The box filter returns the cell mean instead.
    """
    monkeypatch.setenv("O4_INSET_BAKE_INTERP", "1")
    posts = 61
    pixel = 1.0 / 36000.0
    span = pixel * (posts - 1)
    row = numpy.where(numpy.arange(posts) % 3 == 0, 110.0, 95.0)
    values = numpy.tile(row.astype(numpy.float32), (posts, 1))
    inset = _SyntheticDem(values, 0.0, 0.0, span, span)

    step = 3 * pixel                              # 3x coarser than the inset
    xs = inset.x0 + numpy.arange(1, 20) * step
    ys = inset.y1 - numpy.arange(1, 20) * step
    assert INSETS.inset_bake_resample_mode(inset, step, step) == "area"
    averaged = _bake_window(inset, xs, ys)[9]

    monkeypatch.setenv("O4_INSET_BAKE_INTERP", "0")
    aliased = _bake_window(inset, xs, ys)[9]

    # Nearest lands on a crest every time: a phantom flat 110 m surface.
    assert aliased == pytest.approx(numpy.full(aliased.shape, 110.0))
    # The box filter reads the cell's mean -- 1 crest + 2 troughs.
    assert averaged == pytest.approx(
        numpy.full(averaged.shape, (110.0 + 95.0 + 95.0) / 3.0)
    )


def test_area_average_keeps_the_inset_extent(monkeypatch):
    """Outside the inset, the box filter must still say nodata."""
    monkeypatch.setenv("O4_INSET_BAKE_INTERP", "1")
    posts = 21
    pixel = 1.0 / 36000.0
    span = pixel * (posts - 1)
    inset = _SyntheticDem(
        numpy.full((posts, posts), 42.0), 0.5, 0.5, 0.5 + span, 0.5 + span
    )
    step = 3 * pixel
    xs = numpy.array([0.5 - 5 * step, 0.5 + 5 * step, 0.5 + span + 5 * step])
    ys = numpy.array([0.5 + span / 2.0])
    assert INSETS.inset_bake_resample_mode(inset, step, step) == "area"
    baked = _bake_window(inset, xs, ys, step=step)[0]
    assert baked[0] == inset.nodata
    assert baked[1] == pytest.approx(42.0)
    assert baked[2] == inset.nodata


@requires_gdal
def test_bake_into_a_tile_dem_is_gate_switchable(tmp_path, monkeypatch):
    """End to end through ``bake_airport_insets_into_alt_dem``."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "has_gdal", True)
    INSETS.initialize_elevation_providers_dict()

    base_path = str(tmp_path / "base.tif")
    _write_geotiff(base_path, 0.0, 0.0, 1.0, 1.0,
                   numpy.zeros((301, 301), dtype=numpy.float32))

    inset_directory = FNAMES.airport_inset_directory(0, 0)
    os.makedirs(inset_directory, exist_ok=True)
    inset_path = FNAMES.airport_inset_dem(0, 0, "TEST", "USGS3DEP")
    # A 20-post ramp over an inner window: coarse against the 301-post base.
    ramp = numpy.tile(
        numpy.linspace(100.0, 200.0, 20, dtype=numpy.float32), (20, 1)
    )
    _write_geotiff(inset_path, 0.30, 0.30, 0.70, 0.70, ramp)

    baked = {}
    for gate in ("0", "1"):
        monkeypatch.setenv("O4_INSET_BAKE_INTERP", gate)
        dem = DEM.DEM(0, 0, base_path, fill_nodata=False)
        tile = _FakeTile(0, 0)
        tile.dem = dem
        tile.airport_elevation_inset_feather_m = 1.0
        INSETS.bake_airport_insets_into_alt_dem(tile)
        baked[gate] = dem.alt_dem.copy()

    row = 150
    interior = slice(110, 190)
    nearest_steps = numpy.abs(numpy.diff(baked["0"][row, interior]))
    interp_steps = numpy.abs(numpy.diff(baked["1"][row, interior]))
    # The nearest bake is mostly dead-flat treads; the interpolating bake
    # steps at every single node.
    assert (nearest_steps < 1e-6).sum() > 0.4 * nearest_steps.size
    assert (interp_steps < 1e-6).sum() == 0
    # Same terrain either way: no datum shift, just no staircase.
    assert baked["1"][row, interior].mean() == pytest.approx(
        baked["0"][row, interior].mean(), abs=1.0
    )


# =====================================================================
# O2 -- the ballot's error model is the bilinear chain
# =====================================================================
@requires_gdal
def test_ideal_bake_error_models_the_bilinear_chain(tmp_path):
    """Hand-computed cell: the model must score BILINEAR, not the split.

    The probe sits at the exact centre of one working-grid cell of the
    ``factor = 1`` grid over the 3601-post base geometry, and the inset is
    built so its posts land exactly on the four surrounding working-grid
    nodes and on the probe itself:

        NW = 100, NE = 140, SW = 160, SE = 100, truth at the centre = 120

    TRUE BILINEAR (Triangle4XP.altitude, rx = ry = 0.5)
        = (100 + 140 + 160 + 100) / 4 = 125   ->  |125 - 120| = 5
    The retired two-triangle split (rx >= ry -> (1-rx)*NW + ry*SE)
        = 0.5 * (100 + 100)          = 100   ->  |100 - 120| = 20

    so the two models are 15 m apart on this cell and the assertion can
    only pass for one of them.
    """
    geometry = (0.0, 1.0, 0.0, 1.0, 3601, 3601)   # x0, x1, y0, y1, nx, ny
    node = 1.0 / 3600.0                            # working-grid spacing
    half = node / 2.0
    probe_lon = 0.5 + half
    probe_lat = 0.5 + half

    # Inset posting = half the working spacing, phased so pixel centres
    # land on 0.5, 0.5 + half, 0.5 + node ... on both axes.
    pixel = half
    size = 9
    west = 0.5 - 3.5 * pixel
    north = 0.5 + node + 3.5 * pixel
    values = numpy.full((size, size), 100.0, dtype=numpy.float32)
    values[3, 3] = 100.0        # NW node (row 3 == lat 0.5 + node)
    values[3, 5] = 140.0        # NE node
    values[5, 3] = 160.0        # SW node (row 5 == lat 0.5)
    values[5, 5] = 100.0        # SE node
    values[4, 4] = 120.0        # the probe itself
    path = _write_geotiff(
        str(tmp_path / "cell.tif"),
        west, north - size * pixel, west + size * pixel, north, values,
    )

    probes = [(probe_lon, probe_lat, probe_lon, probe_lat)]
    errors = INSETS.ideal_bake_errors_per_probe(path, probes, 1, geometry)
    assert len(errors) == 1
    assert errors[0] == pytest.approx(5.0, abs=1e-3)     # bilinear chain
    assert errors[0] != pytest.approx(20.0, abs=1e-1)    # not the split


@requires_gdal
def test_ideal_bake_error_is_zero_on_a_planar_inset(tmp_path):
    """Bilinear reproduces any plane exactly, so a planar inset costs 0.

    The retired triangle split does too, so this is a sanity anchor rather
    than a discriminator -- it pins that the rewrite did not introduce a
    constant bias.
    """
    geometry = (0.0, 1.0, 0.0, 1.0, 3601, 3601)
    size = 40
    pixel = 1.0 / 36000.0
    west = south = 0.5
    columns = numpy.arange(size, dtype=numpy.float32)
    values = numpy.tile(columns * 2.0, (size, 1)) + numpy.arange(
        size, dtype=numpy.float32
    )[:, None] * 3.0
    path = _write_geotiff(
        str(tmp_path / "plane.tif"),
        west, south, west + size * pixel, south + size * pixel, values,
    )
    probe_lon = west + 17.3 * pixel
    probe_lat = south + 11.7 * pixel
    errors = INSETS.ideal_bake_errors_per_probe(
        path, [(probe_lon, probe_lat, probe_lon, probe_lat)], 1, geometry
    )
    assert errors[0] == pytest.approx(0.0, abs=1e-2)


# =====================================================================
# O3 -- seam factor harmonization
# =====================================================================
def _cache_inset(lat, lon, icao, west, south, east, north, values):
    directory = FNAMES.airport_inset_directory(lat, lon)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, icao + "_copernicusglo30.tif")
    return _write_geotiff(path, west, south, east, north, values)


def _scarp(size=64, low=100.0, high=180.0):
    values = numpy.full((size, size), low, dtype=numpy.float32)
    values[:, size // 2:] = high
    return values


@requires_gdal
def test_seam_straddling_inset_makes_both_tiles_ballot_identically(
    tmp_path, monkeypatch
):
    """The O3 rule, on two synthetic neighbour states.

    A straddling inset is cached under BOTH tiles (as the footprint-driven
    fetch produces).  Each tile also owns a private inset of its own, so
    balloted alone the two tiles see different evidence.  Harmonized, both
    must assemble the same merged set and return the same factor.
    """
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "has_gdal", True)
    monkeypatch.setenv("O4_INSET_SEAM_HARMONIZE", "1")
    INSETS.initialize_elevation_providers_dict()

    # Tiles (0, 0) and (0, -1) share the lon = 0 seam.
    straddle = (-0.02, 0.40, 0.02, 0.44)          # crosses lon = 0
    for tile_lon in (0, -1):
        _cache_inset(0, tile_lon, "SEAM", *straddle, _scarp())
    # Private, wholly-interior insets: different terrain on each side.
    _cache_inset(0, 0, "EAST", 0.30, 0.30, 0.34, 0.34,
                 numpy.full((64, 64), 12.0, dtype=numpy.float32))
    _cache_inset(0, -1, "WEST", -0.70, 0.30, -0.66, 0.34,
                 _scarp(low=0.0, high=250.0))

    east = INSETS.seam_harmonized_ballot_insets(0, 0, None)
    west = INSETS.seam_harmonized_ballot_insets(0, -1, None)
    # Same ballot, named the same way, in the same order, from both sides.
    assert [os.path.basename(p) for (p, _la, _lo) in east] == [
        os.path.basename(p) for (p, _la, _lo) in west
    ]
    assert [os.path.basename(p) for (p, _la, _lo) in east] == [
        "EAST_copernicusglo30.tif",
        "SEAM_copernicusglo30.tif",
        "WEST_copernicusglo30.tif",
    ]
    # And the SAME physical file is chosen for the shared basename, from
    # the lexicographically first tile of the component.
    assert [p for (p, _la, _lo) in east] == [p for (p, _la, _lo) in west]

    class _Geometry:
        x0 = y0 = -0.01
        x1 = y1 = 1.01
        nxdem = nydem = 3673
        alt_dem = None

    factor_east = INSETS._historic_working_grid_factor(
        _FakeTile(0, 0), _Geometry()
    )
    factor_west = INSETS._historic_working_grid_factor(
        _FakeTile(0, -1), _Geometry()
    )
    assert factor_east == factor_west


@requires_gdal
def test_non_straddling_neighbour_is_never_merged(tmp_path, monkeypatch):
    """An inset that stops short of the seam pulls in nothing."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "has_gdal", True)
    monkeypatch.setenv("O4_INSET_SEAM_HARMONIZE", "1")
    INSETS.initialize_elevation_providers_dict()

    # Both tiles have insets, neither crosses the lon = 0 seam.
    _cache_inset(0, 0, "EAST", 0.30, 0.30, 0.34, 0.34, _scarp())
    _cache_inset(0, -1, "WEST", -0.70, 0.30, -0.66, 0.34, _scarp())
    east = INSETS.seam_harmonized_ballot_insets(0, 0, None)
    west = INSETS.seam_harmonized_ballot_insets(0, -1, None)
    assert [os.path.basename(p) for (p, _la, _lo) in east] == [
        "EAST_copernicusglo30.tif"
    ]
    assert [os.path.basename(p) for (p, _la, _lo) in west] == [
        "WEST_copernicusglo30.tif"
    ]
    # Ownership is the tile itself, so its own index carries the probes.
    assert east[0][1:] == (0, 0)
    assert west[0][1:] == (0, -1)


@requires_gdal
def test_seam_harmonization_gate_off_restores_the_per_tile_ballot(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "has_gdal", True)
    monkeypatch.setenv("O4_INSET_SEAM_HARMONIZE", "0")
    INSETS.initialize_elevation_providers_dict()

    straddle = (-0.02, 0.40, 0.02, 0.44)
    for tile_lon in (0, -1):
        _cache_inset(0, tile_lon, "SEAM", *straddle, _scarp())
    _cache_inset(0, 0, "EAST", 0.30, 0.30, 0.34, 0.34, _scarp())
    east = INSETS.seam_harmonized_ballot_insets(0, 0, None)
    assert [os.path.basename(p) for (p, _la, _lo) in east] == [
        "EAST_copernicusglo30.tif",
        "SEAM_copernicusglo30.tif",
    ]


@requires_gdal
def test_seam_harmonization_is_transitive_through_straddling_insets(
    tmp_path, monkeypatch
):
    """A -- B -- C chained by two different straddling insets.

    A and C share no seam at all, but both must still land on the same
    ballot: the rule is the transitive closure of the straddle relation.
    """
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "has_gdal", True)
    monkeypatch.setenv("O4_INSET_SEAM_HARMONIZE", "1")
    INSETS.initialize_elevation_providers_dict()

    # Tiles (0, -2), (0, -1), (0, 0).  One inset crosses lon = -1, another
    # crosses lon = 0; no single inset spans both seams.
    for tile_lon in (-2, -1):
        _cache_inset(0, tile_lon, "AB", -1.02, 0.40, -0.98, 0.44, _scarp())
    for tile_lon in (-1, 0):
        _cache_inset(0, tile_lon, "BC", -0.02, 0.40, 0.02, 0.44, _scarp())

    names = {
        tile_lon: [
            os.path.basename(p)
            for (p, _la, _lo) in INSETS.seam_harmonized_ballot_insets(
                0, tile_lon, None
            )
        ]
        for tile_lon in (-2, -1, 0)
    }
    assert names[-2] == names[-1] == names[0] == [
        "AB_copernicusglo30.tif",
        "BC_copernicusglo30.tif",
    ]


@requires_gdal
def test_seam_harmonization_walks_latitude_seams_too(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "has_gdal", True)
    monkeypatch.setenv("O4_INSET_SEAM_HARMONIZE", "1")
    INSETS.initialize_elevation_providers_dict()

    # Tiles (0, 0) and (1, 0) share the lat = 1 seam.
    for tile_lat in (0, 1):
        _cache_inset(tile_lat, 0, "NS", 0.40, 0.98, 0.44, 1.02, _scarp())
    _cache_inset(0, 0, "SOUTHONLY", 0.30, 0.30, 0.34, 0.34, _scarp())

    south = [
        os.path.basename(p)
        for (p, _la, _lo) in INSETS.seam_harmonized_ballot_insets(0, 0, None)
    ]
    north = [
        os.path.basename(p)
        for (p, _la, _lo) in INSETS.seam_harmonized_ballot_insets(1, 0, None)
    ]
    assert south == north == [
        "NS_copernicusglo30.tif",
        "SOUTHONLY_copernicusglo30.tif",
    ]


@requires_gdal
def test_seam_harmonization_terminates_on_a_long_chain(tmp_path, monkeypatch):
    """Termination is by disk state, not by a recursion guard.

    Ten tiles chained end to end by straddling insets: every member must
    return the SAME full ballot, and the walk must stop.
    """
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "has_gdal", True)
    monkeypatch.setenv("O4_INSET_SEAM_HARMONIZE", "1")
    INSETS.initialize_elevation_providers_dict()

    chain = list(range(-10, 0))
    for index, tile_lon in enumerate(chain[:-1]):
        seam = tile_lon + 1
        for owner in (tile_lon, seam):
            _cache_inset(0, owner, "S%02d" % index,
                         seam - 0.02, 0.40, seam + 0.02, 0.44, _scarp())
    expected = sorted("S%02d_copernicusglo30.tif" % i for i in range(9))
    for tile_lon in chain:
        assert [
            os.path.basename(p)
            for (p, _la, _lo) in INSETS.seam_harmonized_ballot_insets(
                0, tile_lon, None
            )
        ] == expected


def test_seam_harmonization_is_a_noop_without_insets(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    assert INSETS.seam_harmonized_ballot_insets(0, 0, None) == []


@requires_gdal
def test_inset_footprint_degrees_reads_the_header(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    path = _cache_inset(0, 0, "FP", 0.10, 0.20, 0.30, 0.44, _scarp())
    footprint = INSETS._inset_footprint_degrees(path)
    assert footprint == pytest.approx((0.10, 0.20, 0.30, 0.44), abs=1e-9)
    assert INSETS._inset_footprint_degrees(str(tmp_path / "absent.tif")) is (
        None
    )


def test_bake_gate_and_seam_gate_default_on(monkeypatch):
    monkeypatch.delenv("O4_INSET_BAKE_INTERP", raising=False)
    monkeypatch.delenv("O4_INSET_SEAM_HARMONIZE", raising=False)
    assert INSETS.inset_bake_interpolation_enabled() is True
    assert INSETS.seam_harmonization_enabled() is True
    monkeypatch.setenv("O4_INSET_BAKE_INTERP", "0")
    monkeypatch.setenv("O4_INSET_SEAM_HARMONIZE", "0")
    assert INSETS.inset_bake_interpolation_enabled() is False
    assert INSETS.seam_harmonization_enabled() is False
