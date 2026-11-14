"""Twins for the inset threshold correction (#2089, spec
``docs/specs/2089-inset-threshold-correction-spec.md`` §7).

Headless: synthetic GeoTIFF insets in ``tmp_path``, a synthetic working
grid, synthetic airport codes and CIFP thresholds (no X-Plane install).
The bake runs through ``_plan_threshold_corrections`` and
``bake_airport_insets_into_alt_dem``, the production pair.
"""

import os

import numpy
import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
import pytest
from auto_patch import flat_site_mode as FLAT_SITE_MODE
from elevation_access import threshold_correction as TC
from tests.inset_code import patch_inset_code

try:
    from osgeo import gdal, osr

    HAS_GDAL = True
except Exception:
    HAS_GDAL = False

pytestmark = pytest.mark.skipif(not HAS_GDAL, reason="GDAL not available")

POSTS = 3601                       # the 1 arc-second working grid
STEP = 1.0 / (POSTS - 1)
INSET_PIXEL = 1.0 / 10800.0        # a 1/3 arc-second inset
BOX = (0.40, 0.40, 0.46, 0.46)     # west, south, east, north (tile-relative)
ICAO = "ZZTC"


class _Tile:
    def __init__(self, lat, lon, root):
        self.lat, self.lon = lat, lon
        self.dem = None
        self.custom_dem = ""
        self.airport_elevation_insets = True
        self.airport_elevation_providers = "auto"
        self.airport_elevation_level = "auto"
        self.airport_elevation_inset_margin_m = 1000.0
        self.airport_elevation_inset_feather_m = 60.0
        self.working_grid_arc_seconds = "auto"
        self.auto_patch_xplane_root = root


class _Dem:
    """The working grid: the attributes the plan and the bake read."""

    def __init__(self, array):
        self.alt_dem = numpy.asarray(array, dtype=numpy.float32)
        (self.nydem, self.nxdem) = self.alt_dem.shape
        self.x0, self.y0, self.x1, self.y1 = 0.0, 0.0, 1.0, 1.0
        self.nodata = -32768.0


def _grid():
    """Cell-centre tile-relative (x, y) of the working grid."""
    axis = numpy.arange(POSTS) * STEP
    return numpy.meshgrid(axis, 1.0 - axis)


def _write_inset(path, box, values_of):
    """An EPSG:4326 GeoTIFF over ``box`` (absolute degrees) whose cell
    centres hold ``values_of(lon, lat)``."""
    (west, south, east, north) = box
    columns = int(round((east - west) / INSET_PIXEL))
    rows = int(round((north - south) / INSET_PIXEL))
    lon = west + (numpy.arange(columns) + 0.5) * INSET_PIXEL
    lat = north - (numpy.arange(rows) + 0.5) * INSET_PIXEL
    (lon, lat) = numpy.meshgrid(lon, lat)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((west, INSET_PIXEL, 0, north, 0, -INSET_PIXEL))
    reference = osr.SpatialReference()
    reference.ImportFromEPSG(4326)
    dataset.SetProjection(reference.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values_of(lon, lat).astype(numpy.float32))
    dataset = None
    return path


def _threshold(lon, lat, elevation):
    """A threshold on a working-grid cell centre."""
    return {"lat": round(lat / STEP) * STEP, "lon": round(lon / STEP) * STEP,
            "elevation_m": float(elevation)}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    patch_inset_code(monkeypatch, "has_gdal", True)
    INSETS.initialize_elevation_providers_dict()
    state = {"thresholds": {}}
    monkeypatch.setattr(FLAT_SITE_MODE, "cifp_runways",
                        lambda root, icao: state["thresholds"])
    state["root"] = str(tmp_path)
    return state


def _inset_path(lat=0, lon=0):
    return FNAMES.airport_inset_dem(lat, lon, ICAO, "USGS3DEP")


def _bake(world, base, plan=True, lat=0, lon=0):
    tile = _Tile(lat, lon, world["root"])
    tile.dem = _Dem(base.copy())
    if plan:
        INSETS._plan_threshold_corrections(tile)
    INSETS.bake_airport_insets_into_alt_dem(tile)
    return tile


def _at(array, lon, lat):
    return float(array[int(round((1.0 - lat) / STEP)),
                       int(round(lon / STEP))])


def _disc(array, lon, lat, radius_m=TC.DISC_RADIUS_M):
    (x, y) = _grid()
    m = 111_320.0
    near = numpy.hypot((x - lon) * m, (y - lat) * m) <= max(radius_m, 22.0)
    return float(numpy.median(array[near]))


def _four(values, centre=0.43, half=0.015):
    """Four thresholds around ``centre``, elevations ``values``."""
    corners = [(centre - half, centre - half), (centre + half, centre - half),
               (centre - half, centre + half), (centre + half, centre + half)]
    return {f"RW{i + 1:02d}": _threshold(lon, lat, value)
            for (i, ((lon, lat), value)) in enumerate(zip(corners, values, strict=True))}


def _level(lon, lat):
    """A near-level inset (+-0.3 m: a raster with no relief at all is
    declined by the bake as a provider fill)."""
    return 10.0 + 10.0 * (lon - 0.43)


def _four_r(residuals):
    """Four thresholds whose residuals against :func:`_level` are
    ``residuals``."""
    pins = _four([0.0] * 4)
    return {k: dict(v, elevation_m=_level(v["lon"], v["lat"]) + r)
            for ((k, v), r) in zip(pins.items(), residuals, strict=True)}


# ---------------------------------------------------------------- 1
def test_within_the_bar_the_bake_is_byte_identical(world):
    _write_inset(_inset_path(), BOX, _level)
    world["thresholds"] = _four_r([1.0, 2.0, -0.5, 0.0])
    base = numpy.full((POSTS, POSTS), 10.0)
    control = _bake(world, base, plan=False)
    tile = _bake(world, base)
    assert numpy.array_equal(tile.dem.alt_dem, control.dem.alt_dem)
    assert tile.dem.inset_threshold_plans == {}
    assert all("threshold_correction" not in entry
               for entry in tile.dem.airport_inset_provenance)


# ---------------------------------------------------------------- 2
def test_a_constant_offset_is_removed_and_tapered_to_the_box_edge(world):
    def truth(lon, lat):
        return 20.0 + 1000.0 * (lon - 0.40)
    _write_inset(_inset_path(), BOX, lambda lon, lat: truth(lon, lat) - 5.0)
    world["thresholds"] = {
        k: dict(v, elevation_m=truth(v["lon"], v["lat"]))
        for (k, v) in _four([0, 0, 0, 0]).items()}
    (x, y) = _grid()
    base = truth(x, y)
    control = _bake(world, base, plan=False).dem.alt_dem
    tile = _bake(world, base)
    baked = tile.dem.alt_dem
    for pin in world["thresholds"].values():
        assert abs(_disc(baked, pin["lon"], pin["lat"])
                   - pin["elevation_m"]) <= 0.10
    record = tile.dem.inset_threshold_corrections[_inset_path()]
    assert record["status"] == "apply"
    # Zero change on and outside the inset box edge.
    outside = (x <= BOX[0]) | (x >= BOX[2]) | (y <= BOX[1]) | (y >= BOX[3])
    assert numpy.array_equal(baked[outside], control[outside])
    # The taper is monotone, 0 at the edge and full TAPER_M inside.
    tau = TC.taper(numpy.linspace(-50.0, 600.0, 400))
    assert numpy.all(numpy.diff(tau) >= 0.0)
    assert tau[0] == 0.0 and tau[-1] == 1.0


# ---------------------------------------------------------------- 3
def test_licj_pattern_residuals_are_met_exactly_and_bounded(world):
    _write_inset(_inset_path(), BOX, _level)
    world["thresholds"] = _four_r([8.0, 4.0, 2.0, -0.5])
    base = numpy.full((POSTS, POSTS), 10.0)
    control = _bake(world, base, plan=False).dem.alt_dem
    tile = _bake(world, base)
    baked = tile.dem.alt_dem
    for pin in world["thresholds"].values():
        assert _at(baked, pin["lon"], pin["lat"]) == pytest.approx(
            pin["elevation_m"], abs=0.05)
    field = baked.astype(float) - control
    assert field.min() >= -0.5 - 1e-4 and field.max() <= 8.0 + 1e-4


# ---------------------------------------------------------------- 4
def test_no_data_cells_are_never_corrected(world):
    def values(lon, lat):
        out = _level(lon, lat)
        hole = (abs(lon - 0.43) < 0.004) & (abs(lat - 0.43) < 0.004)
        return numpy.where(hole, -32768.0, out)
    _write_inset(_inset_path(), BOX, values)
    world["thresholds"] = _four_r([5.0, 5.0, 4.0, 6.0])
    base = numpy.full((POSTS, POSTS), 3.0)
    control = _bake(world, base, plan=False).dem.alt_dem
    baked = _bake(world, base).dem.alt_dem
    (x, y) = _grid()
    hole = (abs(x - 0.43) < 0.003) & (abs(y - 0.43) < 0.003)
    assert numpy.array_equal(baked[hole], control[hole])
    assert numpy.all(baked[hole] == 3.0)
    assert baked.min() >= control.min()


# ---------------------------------------------------------------- 5
def _bump(lon, lat):
    """The inset's error: ~8 m at RW01, 1-1.6 m at the other thresholds,
    and a 400 m bump that lifts mid-field to ~8 m -- a shape the
    thresholds alone cannot know (the LICJ shore strip)."""
    def gauss(lon0, lat0, sigma_m):
        d2 = ((lon - lon0) ** 2 + (lat - lat0) ** 2) * 111_320.0 ** 2
        return numpy.exp(-d2 / (2 * sigma_m ** 2))
    return 1.0 + 7.0 * gauss(0.415, 0.415, 1500.0) + 5.0 * gauss(
        0.43, 0.43, 400.0)


def test_model_b_follows_the_base_where_the_thresholds_cannot(
        world, monkeypatch):
    truth = 20.0
    _write_inset(_inset_path(), BOX, lambda lon, lat: truth - _bump(lon, lat))
    world["thresholds"] = _four([truth] * 4)
    base = numpy.full((POSTS, POSTS), truth)
    tile = _bake(world, base)
    record = tile.dem.inset_threshold_corrections[_inset_path()]
    assert record["model"] == "base_witness"
    assert abs(_at(tile.dem.alt_dem, 0.43, 0.43) - truth) <= 1.0
    monkeypatch.setattr(TC, "MODEL_B", False)
    only_thresholds = _bake(world, base)
    assert abs(_at(only_thresholds.dem.alt_dem, 0.43, 0.43) - truth) > 2.0


def test_model_b_is_refused_on_a_canopy_base(world, monkeypatch):
    truth = 20.0
    _write_inset(_inset_path(), BOX, lambda lon, lat: truth - _bump(lon, lat))
    world["thresholds"] = _four([truth] * 4)
    canopy = numpy.full((POSTS, POSTS), truth + 15.0)
    tile = _bake(world, canopy)
    assert (tile.dem.inset_threshold_corrections[_inset_path()]["model"]
            == "thresholds")
    monkeypatch.setattr(TC, "MODEL_B", False)
    assert numpy.array_equal(tile.dem.alt_dem,
                             _bake(world, canopy).dem.alt_dem)


# ---------------------------------------------------------------- 6
def test_a_straddling_inset_uses_the_thresholds_on_both_tiles(world):
    def values(lon, lat):
        return 10.0 + 100.0 * (lon - 0.97)
    west_box = (0.97, 0.40, 1.03, 0.46)
    east_box = (0.97 + INSET_PIXEL, 0.40, 1.03 + INSET_PIXEL, 0.46)
    _write_inset(_inset_path(0, 0), west_box, values)
    _write_inset(_inset_path(0, 1), east_box, values)
    world["thresholds"] = {
        "RW01": _threshold(0.985, 0.42, 16.0),
        "RW02": _threshold(1.015, 0.42, 17.5),
        "RW03": _threshold(0.985, 0.44, 15.5),
        "RW04": _threshold(1.015, 0.44, 16.0)}
    corrections = []
    for lon in (0, 1):
        base = numpy.full((POSTS, POSTS), 15.0)
        control = _bake(world, base, plan=False, lon=lon).dem.alt_dem
        tile = _bake(world, base, lon=lon)
        record = tile.dem.inset_threshold_corrections[_inset_path(0, lon)]
        assert record["model"] == "thresholds"
        corrections.append((tile.dem.alt_dem.astype(float) - control,
                            [r["residual_m"] for r in record["readings"]]))
    ((west, west_r), (east, east_r)) = corrections
    rows = slice(int((1 - 0.455) / STEP), int((1 - 0.405) / STEP))
    seam = numpy.abs(west[rows, -1] - east[rows, 0]).max()
    reading_gap = max(abs(a - b) for (a, b) in zip(west_r, east_r, strict=True))
    assert seam <= reading_gap + 0.02


# ---------------------------------------------------------------- 7
def test_one_witness_is_no_correction_and_over_the_cap_is_refused(world):
    _write_inset(_inset_path(), BOX, _level)
    base = numpy.full((POSTS, POSTS), 10.0)
    control = _bake(world, base, plan=False).dem.alt_dem
    world["thresholds"] = {"RW01": _threshold(0.42, 0.42, 16.0)}
    tile = _bake(world, base)
    assert tile.dem.inset_threshold_plans == {}
    assert numpy.array_equal(tile.dem.alt_dem, control)
    world["thresholds"] = _four_r([20.0, 2.0, 2.0, 2.0])
    tile = _bake(world, base)
    assert numpy.array_equal(tile.dem.alt_dem, control)
    (entry,) = tile.dem.airport_inset_provenance
    assert entry["threshold_correction"]["status"] == "refused"
    assert TC.verdict([{"residual_m": 4.0}])["status"] == "none"


# ---------------------------------------------------------------- 8
def test_the_ring_offset_is_measured_before_the_correction(world):
    _write_inset(_inset_path(), BOX, _level)
    world["thresholds"] = _four_r([8.0, 4.0, 2.0, -0.5])
    base = numpy.full((POSTS, POSTS), 7.0)
    offsets = []
    for plan in (False, True):
        tile = _Tile(0, 0, world["root"])
        tile.dem = _Dem(base.copy())
        if plan:
            INSETS._plan_threshold_corrections(tile)
        offsets.append(INSETS._bake_one_inset(tile, _inset_path(), 60.0))
    assert offsets[0] == offsets[1]
    assert offsets[0] == pytest.approx(3.0, abs=0.1)


# ---------------------------------------------------------------- 10
def test_the_vector_step_keys_on_the_inset_airports_cifp(world, tmp_path):
    import O4_Step_Reuse as REUSE
    cifp = tmp_path / "CIFP.dat"
    cifp.write_text("one cycle", encoding="utf-8", newline="\n")
    tile = _Tile(0, 0, world["root"])
    _write_inset(_inset_path(), BOX, _level)
    import auto_patch.build_support as BUILD_SUPPORT
    original = BUILD_SUPPORT._find_cifp_path
    BUILD_SUPPORT._find_cifp_path = lambda root, icao: str(cifp)
    try:
        assert INSETS.inset_cifp_files(tile) == [str(cifp)]
        before = REUSE._content(REUSE._inset_cifp_files(tile))
        cifp.write_text("the next cycle", encoding="utf-8", newline="\n")
        assert REUSE._content(REUSE._inset_cifp_files(tile)) != before
    finally:
        BUILD_SUPPORT._find_cifp_path = original
    assert "inset_cifp" in REUSE._KEYS_EQUAL_WHEN_ABSENT
