"""THE TRIM RULE (#1725 item 2, ``elevation_access.inset_trim``): a cached
inset cut for a larger box than the build now reads is cut down to it in
place -- the kept pixels copied, never resampled -- and its sidecar then
records the new box as the requested one.  Synthetic rasters in
``tmp_path`` only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy  # noqa: E402
import pytest  # noqa: E402
from elevation_access import inset_trim as TRIM  # noqa: E402
from elevation_access.gdal_support import gdal, has_gdal  # noqa: E402

pytestmark = pytest.mark.skipif(not has_gdal, reason="needs GDAL")

# 200 x 100 pixels of 0.001 deg from (10.0, 50.1) down to (10.2, 50.0)
GEOTRANSFORM = (10.0, 0.001, 0.0, 50.1, 0.0, -0.001)


@pytest.fixture
def inset(tmp_path, monkeypatch):
    monkeypatch.setenv("O4_INSET_SCRATCH_DIR", str(tmp_path / "scratch"))
    path = str(tmp_path / "KXXX_usgs3dep.tif")
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, 200, 100, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform(GEOTRANSFORM)
    pixels = numpy.arange(200 * 100, dtype=numpy.float32).reshape(100, 200)
    dataset.GetRasterBand(1).WriteArray(pixels)
    dataset = None
    sidecar = path[:-4] + ".json"
    with open(sidecar, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"requested_bounding_box_wgs84": [10.0, 50.0, 10.2, 50.1],
                   "provider": "USGS3DEP"}, handle)
    return path, sidecar, pixels


def test_an_oversized_inset_is_cut_to_the_box_with_its_pixels(inset):
    path, sidecar, pixels = inset
    box = (10.0505, 50.0205, 10.1495, 50.0795)
    assert TRIM.trim_cached_inset(path, sidecar, box) > 0
    dataset = gdal.Open(path)
    (x0, _dx, _a, y0, _b, _dy) = dataset.GetGeoTransform()
    assert (dataset.RasterXSize, dataset.RasterYSize) == (100, 60)
    assert (round(x0, 6), round(y0, 6)) == (10.05, 50.08)
    kept = dataset.GetRasterBand(1).ReadAsArray()
    assert numpy.array_equal(kept, pixels[20:80, 50:150])     # copied, not resampled
    with open(sidecar, encoding="utf-8") as handle:
        meta = json.load(handle)
    assert meta["requested_bounding_box_wgs84"] == list(box)
    assert meta["trimmed_from_bounding_box_wgs84"] == [10.0, 50.0, 10.2, 50.1]
    assert TRIM.trim_cached_inset(path, sidecar, box) == 0     # settled


def test_an_inset_the_box_mostly_keeps_is_left_alone(inset):
    path, sidecar, _pixels = inset
    before = os.path.getsize(path)
    assert TRIM.trim_cached_inset(path, sidecar, (10.0, 50.0, 10.19, 50.1)) == 0
    assert os.path.getsize(path) == before


def test_a_guarded_write_is_never_trimmed(inset, monkeypatch):
    path, sidecar, _pixels = inset
    monkeypatch.setattr(TRIM, "_write_refused_by_armed_guard", lambda p: True)
    assert TRIM.trim_cached_inset(path, sidecar, (10.05, 50.02, 10.1, 50.05)) == 0
    assert gdal.Open(path).RasterXSize == 200


def test_kept_fraction():
    assert TRIM.kept_fraction(GEOTRANSFORM, 200, 100,
                              (10.0, 50.0, 10.1, 50.1)) == pytest.approx(0.5)
    assert TRIM.kept_fraction(GEOTRANSFORM, 200, 100, (11, 51, 12, 52)) == 1.0
