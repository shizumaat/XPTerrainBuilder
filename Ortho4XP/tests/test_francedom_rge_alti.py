"""RGE ALTI 1 m for overseas France (#2272).

FRANCE1M asks the Geoplateforme WMS in Lambert-93 and its box stops at
metropolitan France; FRANCEDOM1M asks the SAME layer in EPSG:4326 over one
box per overseas territory, and FRANCEDOMTIDAL hands its Litto3D seabed to
the depth masks.  No network: ``requests.get`` is stubbed.
"""

import os
import re
import types

import numpy
import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_Geo_Utils as GEO
from elevation_access import definitions as ea_definitions
from elevation_access.strategies.wcs_kvp import WcsKvpStrategy

_PROVIDERS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "Providers", "Elevation")

#: An airport-sized box on Saint-Barthelemy (lon/lat; a fixture point,
#: not code).
_ISLAND_BOX = (-62.858, 17.895, -62.828, 17.912)


@pytest.fixture(scope="module")
def shipped():
    return INSETS.initialize_elevation_providers_dict(_PROVIDERS)


def _numbers(url, key):
    return [float(v) for v in
            re.search(key + r"=([^&]+)", url).group(1).split(",")]


def test_overseas_boxes_and_countries(shipped):
    dom, tidal, metro = (shipped["FRANCEDOM1M"], shipped["FRANCEDOMTIDAL"],
                         shipped["FRANCE1M"])
    assert dom["role"] == ea_definitions.ROLE_AIRPORT_INSET
    assert tidal["role"] == ea_definitions.ROLE_BATHYMETRY
    assert len(dom["coverage_bboxes"]) == 7
    assert tidal["coverage_bboxes"] == dom["coverage_bboxes"]
    assert ea_definitions._coverage_bbox_intersects(dom, _ISLAND_BOX)
    assert not ea_definitions._coverage_bbox_intersects(metro, _ISLAND_BOX)
    # Between the territories (the open Atlantic) nothing is claimed.
    assert not ea_definitions._coverage_bbox_intersects(
        dom, (-40.0, 20.0, -39.9, 20.1))
    for country in ("BLM", "MAF", "GLP", "MTQ", "GUF", "REU", "MYT",
                    "SPM", "FRA"):
        assert ea_definitions.provider_serves_country(dom, country)
    # Sint Maarten shares the island's box but is not France.
    assert not ea_definitions.provider_serves_country(dom, "SXM")
    # The same service and request as the inset; seabed kept, blends not.
    assert (tidal["wcs_getcoverage_template"]
            == dom["wcs_getcoverage_template"])
    assert float(tidal["value_floor_m"]) == -150.0
    assert float(dom["value_floor_m"]) == -150.0  # the smeared sentinel
    assert "geoid_shift" not in dom  # local MSL datums, not ellipsoidal


def test_geographic_request_is_lat_first_one_metre(shipped):
    dom = shipped["FRANCEDOM1M"]
    urls = WcsKvpStrategy()._request_urls(dom, _ISLAND_BOX, 1.0)
    assert len(urls) == 1 and "CRS=EPSG:4326" in urls[0]
    (south, west, north, east) = _numbers(urls[0], "BBOX")
    (width,) = _numbers(urls[0], "WIDTH")
    (height,) = _numbers(urls[0], "HEIGHT")
    # WMS 1.3.0 EPSG:4326 axis order: latitude first.
    assert 17.0 < south < north < 18.0 and -63.0 < west < east < -62.0
    # Padded by the strategy's 60 m on every side, in degrees.
    lon_m = GEO.lon_to_m((_ISLAND_BOX[1] + _ISLAND_BOX[3]) / 2.0)
    assert abs((_ISLAND_BOX[0] - west) * lon_m - 60.0) < 0.5
    assert abs((_ISLAND_BOX[1] - south) * GEO.lat_to_m - 60.0) < 0.5
    # Pixels are 1 m on the ground along both axes.
    assert abs((east - west) * lon_m / width - 1.0) < 1e-3
    assert abs((north - south) * GEO.lat_to_m / height - 1.0) < 1e-3


def test_geographic_request_tiles_within_max_width(shipped):
    dom = shipped["FRANCEDOM1M"]
    box = (-61.56, 16.24, -61.48, 16.29)  # ~8.5 x 5.5 km
    urls = WcsKvpStrategy()._request_urls(dom, box, 1.0)
    assert len(urls) == 4  # 2 x 2: both axes exceed 5010 px
    for url in urls:
        assert 0 < _numbers(url, "WIDTH")[0] <= 5010
        assert 0 < _numbers(url, "HEIGHT")[0] <= 5010
    # The tiles abut: the second starts where the first ends.
    assert _numbers(urls[0], "BBOX")[3] == pytest.approx(
        _numbers(urls[1], "BBOX")[1], abs=1e-6)


def test_fetch_keeps_seabed_and_drops_nodata(shipped, tmp_path,
                                              monkeypatch):
    gdal = pytest.importorskip("osgeo.gdal")
    osr = pytest.importorskip("osgeo.osr")
    import requests

    (west, south, east, north) = (-62.86, 17.89, -62.82, 17.92)
    columns, rows = 80, 60
    values = numpy.full((rows, columns), 12.0, dtype=numpy.float32)
    values[:, :20] = -7.5            # Litto3D seabed
    values[:, 55:] = -99999.0        # beyond the survey
    payload_path = str(tmp_path / "answer.tif")
    dataset = gdal.GetDriverByName("GTiff").Create(
        payload_path, columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((west, (east - west) / columns, 0, north, 0,
                             (south - north) / rows))
    reference = osr.SpatialReference()
    reference.ImportFromEPSG(4326)
    dataset.SetProjection(reference.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-99999.0)
    band.WriteArray(values)
    dataset = band = None
    with open(payload_path, "rb") as handle:
        payload = handle.read()
    asked = []

    def _fake_get(url, timeout=None, headers=None):
        asked.append(url)
        return types.SimpleNamespace(status_code=200, content=payload)

    monkeypatch.setattr(requests, "get", _fake_get)
    destination = str(tmp_path / "inset.tif")
    record = WcsKvpStrategy().fetch(shipped["FRANCEDOM1M"], _ISLAND_BOX,
                                    10.0, destination)
    assert record and record["provider"] == "FRANCEDOM1M" and len(asked) == 1
    out = gdal.Open(destination)
    data = out.GetRasterBand(1).ReadAsArray()
    nodata = out.GetRasterBand(1).GetNoDataValue()
    valid = data[data != nodata]
    assert valid.size
    assert valid.min() >= -7.5 - 1e-3 and valid.max() <= 12.0 + 1e-3
    assert (valid < -7.0).any()          # the seabed survives
    assert (data == nodata).any()        # -99999 is no coverage, not ground
