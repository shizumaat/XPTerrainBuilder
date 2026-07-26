"""Stage-1 tests: the DEM query reads the surface the mesher renders.

The grading law measures the surface the mesher renders -- one surface,
two readers.  ``O4_DEM_Utils.DEM.alt_baked`` / ``alt_vec_baked`` are a
Python transcription of ``Triangle4XP.altitude()``
(``Utils/src/Triangle4XP.c:3571``) over the baked working raster, and
``bake_airport_insets_into_alt_dem`` re-points ``dem.alt``/``dem.alt_vec``
at them once that raster is final.

Everything here is headless: pure numpy for the interpolation identity,
and synthetic in-memory GeoTIFFs (skipped without GDAL) for the bake.
"""

import os

import numpy
import pytest

import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
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
def triangle4xp_altitude(raster, x0, y0, x1, y1, x, y):
    """``altitude()`` from ``Utils/src/Triangle4XP.c``, transcribed here
    INDEPENDENTLY of the implementation under test (deliberately written
    from the C source, index arithmetic and all, so the assertion is a
    real cross-check rather than a tautology)."""
    nx_max = raster.shape[1] - 1
    ny_max = raster.shape[0] - 1
    px = (x - x0) / (x1 - x0) * nx_max
    py = (y1 - y) / (y1 - y0) * ny_max
    nx = int(numpy.floor(px))
    ny = int(numpy.floor(py))
    nxp = nx + 1 if (nx + 1) < nx_max else nx_max
    nyp = ny + 1 if (ny + 1) < ny_max else ny_max
    rx = px - nx
    ry = py - ny
    return (
        raster[ny][nx] * (1 - rx) * (1 - ry)
        + raster[ny][nxp] * rx * (1 - ry)
        + raster[nyp][nx] * (1 - rx) * ry
        + raster[nyp][nxp] * rx * ry
    )


def make_dem(raster, x0=0.0, y0=0.0, x1=1.0, y1=1.0):
    """A bare ``DEM`` carrying ``raster`` -- no file, no download."""
    dem = DEM.DEM.__new__(DEM.DEM)
    dem.lat = 0
    dem.lon = 0
    dem.alt_dem = raster
    dem.nxdem = raster.shape[1]
    dem.nydem = raster.shape[0]
    dem.x0, dem.y0, dem.x1, dem.y1 = x0, y0, x1, y1
    dem.nodata = -32768
    dem.subdems = tuple()
    dem.source_path = ""
    dem.baked_query_active = False
    dem.alt = dem.alt_nostrict
    dem.alt_vec = dem.alt_vec_nostrict
    return dem


def rough_raster(side=41, seed=7):
    generator = numpy.random.default_rng(seed)
    return (generator.random((side, side)) * 60.0).astype(numpy.float32)


def _write_geotiff(path, west, south, east, north, values):
    rows, columns = values.shape
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform(
        (west, (east - west) / columns, 0, north, 0, (south - north) / rows)
    )
    reference = osr.SpatialReference()
    reference.ImportFromEPSG(4326)
    dataset.SetProjection(reference.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values.astype(numpy.float32))
    band.FlushCache()
    dataset = None
    return path


class _FakeTile:
    def __init__(self, lat, lon, custom_dem=""):
        self.lat = lat
        self.lon = lon
        self.dem = None
        self.custom_dem = custom_dem
        self.airport_elevation_insets = True
        self.airport_elevation_providers = "auto"
        self.airport_elevation_level = "auto"
        self.airport_elevation_inset_margin_m = 1000.0
        # Feather 0 -> the inset lands unblended over its whole footprint,
        # so "inside the footprint" is unambiguous for these assertions.
        self.airport_elevation_inset_feather_m = 0.0
        self.working_grid_arc_seconds = "auto"


# =====================================================================
# The interpolation identity
# =====================================================================
def test_alt_baked_is_triangle4xp_bilinear():
    """The scalar query reproduces the mesher's interpolant exactly."""
    raster = rough_raster()
    dem = make_dem(raster)
    generator = numpy.random.default_rng(11)
    for _ in range(400):
        x, y = generator.random(), generator.random()
        assert dem.alt_baked((x, y)) == pytest.approx(
            triangle4xp_altitude(raster, 0.0, 0.0, 1.0, 1.0, x, y), abs=1e-9
        )


def test_alt_vec_baked_matches_the_scalar_query():
    raster = rough_raster()
    dem = make_dem(raster)
    generator = numpy.random.default_rng(13)
    way = generator.random((256, 2))
    vectorized = dem.alt_vec_baked(way)
    for index, (x, y) in enumerate(way):
        assert vectorized[index] == pytest.approx(
            dem.alt_baked((x, y)), abs=1e-9
        )


def test_alt_baked_clamps_outside_the_extent():
    """Out-of-extent nodes clamp (``alt_nostrict``'s convention) rather
    than index out of bounds -- Triangle4XP assumes in-range callers."""
    raster = rough_raster()
    dem = make_dem(raster)
    assert dem.alt_baked((-5.0, 0.5)) == pytest.approx(dem.alt_baked((0.0, 0.5)))
    assert dem.alt_baked((0.5, 9.0)) == pytest.approx(dem.alt_baked((0.5, 1.0)))
    # The far corner post is reachable and finite.
    assert dem.alt_baked((1.0, 1.0)) == pytest.approx(float(raster[0][-1]))


def test_alt_nostrict_is_not_the_mesher_surface():
    """Why ``alt_nostrict`` was NOT reused: it is a triangle-split
    interpolant, which meets bilinear on the cell edges and departs from
    it inside the cell.  This is the justification for a new reader."""
    raster = rough_raster()
    dem = make_dem(raster)
    step = 1.0 / (raster.shape[0] - 1)
    # Cell centre: the two schemes disagree by (t1+t2-t3-t4)/4.
    centre = (step * 3.5, step * 5.5)
    assert abs(dem.alt_nostrict(centre) - dem.alt_baked(centre)) > 1e-3
    # On a grid line they agree.
    on_line = (step * 3.0, step * 5.5)
    assert dem.alt_nostrict(on_line) == pytest.approx(
        dem.alt_baked(on_line), abs=1e-6
    )


# =====================================================================
# enable_baked_query: the gate and the safety refusals
# =====================================================================
def test_enable_baked_query_refuses_without_subdems(monkeypatch):
    monkeypatch.setenv("O4_DEM_QUERY_BAKED", "1")
    dem = make_dem(rough_raster())
    assert dem.enable_baked_query([]) is False
    assert dem.baked_query_active is False


def test_enable_baked_query_refuses_an_unbaked_subdem(monkeypatch):
    """A sub-DEM that never baked lives only in the query path (the
    legacy ``custom_dem = "base;local"`` feature); bypassing the
    composite would silently drop it, so the switch is refused."""
    monkeypatch.setenv("O4_DEM_QUERY_BAKED", "1")
    dem = make_dem(rough_raster())
    baked = make_dem(rough_raster(seed=2))
    baked.source_path = "/cache/BAKED.tif"
    unbaked = make_dem(rough_raster(seed=3))
    unbaked.source_path = "/user/local.tif"
    dem.subdems = (baked, unbaked)
    assert dem.enable_baked_query(["/cache/BAKED.tif"]) is False
    assert dem.alt == dem.alt_nostrict
    # Every sub-DEM baked -> the switch is made.
    assert dem.enable_baked_query(["/cache/BAKED.tif", "/user/local.tif"])
    assert dem.alt == dem.alt_baked
    assert dem.alt_vec == dem.alt_vec_baked
    assert dem.baked_query_active is True


def test_enable_baked_query_respects_the_gate(monkeypatch):
    monkeypatch.setenv("O4_DEM_QUERY_BAKED", "0")
    dem = make_dem(rough_raster())
    subdem = make_dem(rough_raster(seed=5))
    subdem.source_path = "/cache/BAKED.tif"
    dem.subdems = (subdem,)
    assert dem.enable_baked_query(["/cache/BAKED.tif"]) is False
    assert dem.alt == dem.alt_nostrict


# =====================================================================
# End to end over the real bake
# =====================================================================
def _bake_fixture(tmp_path, monkeypatch):
    """A composite DEM (flat base + ramped coarse inset) after the real
    ``bake_airport_insets_into_alt_dem``.  Returns (tile, dem, window)."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "has_gdal", True)
    INSETS.initialize_elevation_providers_dict()

    base = numpy.zeros((301, 301), dtype=numpy.float32)
    base_path = _write_geotiff(str(tmp_path / "base.tif"), 0.0, 0.0, 1.0, 1.0,
                               base)

    # A COARSE inset (24 posts over 0.30 deg) carrying a steep ramp: its
    # nearest-neighbour staircase and the bilinear ramp of the baked
    # working raster differ by metres, which is the whole point.
    columns = 24
    ramp = numpy.tile(
        numpy.linspace(0.0, 240.0, columns, dtype=numpy.float32), (columns, 1)
    )
    inset_directory = FNAMES.airport_inset_directory(0, 0)
    os.makedirs(inset_directory, exist_ok=True)
    inset_path = FNAMES.airport_inset_dem(0, 0, "TEST", "USGS3DEP")
    _write_geotiff(inset_path, 0.35, 0.35, 0.65, 0.65, ramp)

    dem = DEM.DEM(0, 0, base_path + ";" + inset_path, fill_nodata=False)
    assert dem.alt == dem.alt_composite  # composite before the bake
    tile = _FakeTile(0, 0)
    tile.dem = dem
    INSETS.bake_airport_insets_into_alt_dem(tile)
    return tile, dem


@requires_gdal
def test_query_reads_the_bake_inside_the_footprint(tmp_path, monkeypatch):
    monkeypatch.setenv("O4_DEM_QUERY_BAKED", "1")
    _tile, dem = _bake_fixture(tmp_path, monkeypatch)
    assert dem.baked_query_active is True

    generator = numpy.random.default_rng(17)
    inside = 0
    for _ in range(300):
        x = float(generator.uniform(0.40, 0.60))
        y = float(generator.uniform(0.40, 0.60))
        assert dem.alt((x, y)) == pytest.approx(
            triangle4xp_altitude(dem.alt_dem, dem.x0, dem.y0, dem.x1, dem.y1,
                                 x, y),
            abs=1e-9,
        )
        inside += 1
    assert inside == 300

    # ... and it is a REAL change: the old composite read (nearest
    # neighbour on the inset's own coarse posting) disagrees.
    worst = max(
        abs(dem.alt((x, 0.5)) - dem.alt_composite((x, 0.5)))
        for x in numpy.linspace(0.40, 0.60, 201)
    )
    assert worst > 1.0


@requires_gdal
def test_query_outside_the_footprint_stays_on_the_base(tmp_path, monkeypatch):
    """No inset leakage: outside the inset extent the query still returns
    the base surface (flat 0 m here), read from the same baked raster."""
    monkeypatch.setenv("O4_DEM_QUERY_BAKED", "1")
    _tile, dem = _bake_fixture(tmp_path, monkeypatch)
    for x, y in ((0.10, 0.10), (0.90, 0.10), (0.10, 0.90), (0.90, 0.90),
                 (0.20, 0.50), (0.50, 0.80)):
        assert dem.alt((x, y)) == pytest.approx(0.0, abs=1e-9)
        assert dem.alt((x, y)) == pytest.approx(
            dem.alt_composite((x, y)), abs=1e-9
        )


@requires_gdal
def test_gate_off_keeps_the_nearest_neighbour_composite(tmp_path, monkeypatch):
    monkeypatch.setenv("O4_DEM_QUERY_BAKED", "0")
    _tile, dem = _bake_fixture(tmp_path, monkeypatch)
    assert dem.baked_query_active is False
    assert dem.alt == dem.alt_composite
    assert dem.alt_vec == dem.alt_vec_composite
    generator = numpy.random.default_rng(19)
    for _ in range(200):
        x = float(generator.uniform(0.40, 0.60))
        y = float(generator.uniform(0.40, 0.60))
        node = (x, y)
        # Byte-identical to the pre-change reader: the inset's own strict
        # (nearest) value wins.
        subdem = dem.subdems[-1]
        assert dem.alt(node) == pytest.approx(subdem.alt_strict(node))


@requires_gdal
def test_vector_query_follows_the_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("O4_DEM_QUERY_BAKED", "1")
    _tile, dem = _bake_fixture(tmp_path, monkeypatch)
    way = numpy.array([[x, 0.5] for x in numpy.linspace(0.40, 0.60, 64)])
    vectorized = dem.alt_vec(way)
    for index, (x, y) in enumerate(way):
        assert vectorized[index] == pytest.approx(dem.alt((x, y)), abs=1e-9)
