"""#153 -- the USGS Original Product Resolution (OPR) ladder rung.

USGS publishes QL1/QL2 lidar over 51 US airports (all of Alaska's, KGEG,
KGTF, KPUB, KGPT ...) with no 1 m product; TNM lists the same flights as
OPR DEM tiles: ~1 km GeoTIFFs at 0.5-1.5 m, each in its own CRS and HEIGHT
UNIT (metres; NAVD88-in-feet compound CRSs; State Plane foot CRSs with no
vertical CRS at all).  The ``tnm_cog`` strategy with
``source_units=from_source`` reads every header, converts feet to metres
through a scaling VRT, leaves products coarser than
``max_source_resolution_m`` (the 5 m Alaska IFSAR) out of the mosaic, and
records the native resolution the FILES carry.  The TNM listing is PAGED
(50 a page; KGEG's box lists 97 OPR tiles).  No network: ``requests`` is
faked and the warp reads local GeoTIFFs.
"""

import os

import numpy
import pytest

import O4_Airport_Elevation_Insets as INSETS
from tests.inset_code import patch_inset_code
from elevation_access import base as ea_base
from elevation_access import discovery as ea_discovery
from elevation_access.strategies import tnm_cog as ea_tnm_cog
from elevation_access import warp as ea_warp

gdal = pytest.importorskip("osgeo.gdal")
from osgeo import osr  # noqa: E402

FTUS = 1200.0 / 3937.0
#: KGEG-ish: NAD83(2011) / UTM 11N
UTM = 6340
#: Washington North (ftUS), NAD83(2011) -- a State Plane foot CRS.
SPFT = 6597
BOX = (-117.5480, 47.6120, -117.5320, 47.6260)


def _srs(epsg, vertical=None):
    srs = osr.SpatialReference()
    if vertical is None:
        srs.ImportFromEPSG(epsg)
    else:
        horizontal = osr.SpatialReference()
        horizontal.ImportFromEPSG(epsg)
        height = osr.SpatialReference()
        height.ImportFromEPSG(vertical)
        srs.SetCompoundCS("test", horizontal, height)
    return srs


def _corner(epsg, lon, lat):
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target = osr.SpatialReference()
    target.ImportFromEPSG(epsg)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    (x, y, _z) = osr.CoordinateTransformation(source, target).TransformPoint(
        lon, lat)
    return x, y


def _write_tile(path, epsg, value, pixel, vertical=None, unit_type=None,
                box=BOX):
    """A tile over ``box`` in ``epsg`` holding ``value`` everywhere, at
    ``pixel`` CRS units a pixel."""
    (x0, y1) = _corner(epsg, box[0], box[3])
    (x1, y0) = _corner(epsg, box[2], box[1])
    width = max(4, int((x1 - x0) / pixel))
    height = max(4, int((y1 - y0) / pixel))
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), width, height, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((x0, pixel, 0.0, y1, 0.0, -pixel))
    dataset.SetProjection(_srs(epsg, vertical).ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-999999.0)
    values = numpy.full((height, width), value, dtype=numpy.float32)
    values[:2, :2] = -999999.0
    band.WriteArray(values)
    if unit_type:
        band.SetUnitType(unit_type)
    dataset = None
    return str(path)


def test_height_unit_rules(tmp_path):
    cases = [
        # a NAVD88-height-in-feet compound CRS (Montana DNRC)
        (dict(epsg=UTM, vertical=6360), 1200.0 / 3937.0, "vertical-crs"),
        # metres declared by a compound CRS (WA NorthEast B22)
        (dict(epsg=UTM, vertical=5703), 1.0, "vertical-crs"),
        # a State Plane foot CRS with no vertical CRS (Fairbanks FB17)
        (dict(epsg=SPFT), FTUS, "horizontal-crs"),
        # the band says metres (Salton Sea)
        (dict(epsg=UTM, unit_type="metre"), 1.0, "band-unit"),
        # nothing said, a metre CRS
        (dict(epsg=UTM), 1.0, "horizontal-crs"),
    ]
    for number, (kwargs, factor, rule) in enumerate(cases):
        pixel = 1.0 if kwargs["epsg"] == UTM else 3.0
        path = _write_tile(tmp_path / ("t%d.tif" % number), value=100.0,
                           pixel=pixel, **kwargs)
        dataset = gdal.Open(path)
        (got, _name, got_rule) = ea_tnm_cog.raster_height_unit(dataset)
        assert got == pytest.approx(factor, rel=1e-9), kwargs
        assert got_rule == rule, kwargs
        assert ea_tnm_cog.raster_native_resolution_m(dataset) == pytest.approx(
            pixel * (FTUS if kwargs["epsg"] == SPFT else 1.0), rel=1e-6)
        dataset = None


def test_metre_scaled_vrt_keeps_nodata(tmp_path):
    tile = _write_tile(tmp_path / "ft.tif", SPFT, 1000.0, 3.0)
    vrt = ea_tnm_cog._metre_scaled_vrt(tile, FTUS, str(tmp_path / "ft.vrt"))
    dataset = gdal.Open(vrt)
    band = dataset.GetRasterBand(1)
    values = band.ReadAsArray()
    assert band.GetNoDataValue() == -999999.0
    assert values[0, 0] == -999999.0                 # NoData unscaled
    assert values[5, 5] == pytest.approx(1000.0 * FTUS, abs=1e-3)


class _Response:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload
        self.headers = {}

    def json(self):
        return self._payload


def _item(name, date):
    return {"downloadURL": "https://prd-tnm.test/OPR/%s.tif" % name,
            "sourceId": name, "title": "USGS OPR %s" % name,
            "publicationDate": date,
            "boundingBox": {"minX": BOX[0], "minY": BOX[1],
                            "maxX": BOX[2], "maxY": BOX[3]}}


@pytest.fixture
def fake_tnm(monkeypatch):
    import requests

    state = {"items": [], "page": 50, "calls": [], "drop_page": None}

    def _get(url, **kwargs):
        state["calls"].append(url)
        offset = 0
        if "&offset=" in url:
            offset = int(url.rsplit("&offset=", 1)[1])
        page = state["items"][offset:offset + state["page"]]
        if state["drop_page"] is not None and offset == state["drop_page"]:
            page = []
        return _Response({"total": len(state["items"]), "items": page})

    monkeypatch.setattr(requests, "get", _get)
    return state


def test_listing_is_paged(fake_tnm):
    fake_tnm["items"] = [_item("T%03d" % n, "2023-01-01") for n in range(97)]
    items = ea_discovery.tnm_listing_items("https://tnm.test/p?x=1", "TNM")
    assert [item["sourceId"] for item in items] == [
        "T%03d" % n for n in range(97)]
    assert fake_tnm["calls"] == ["https://tnm.test/p?x=1",
                                 "https://tnm.test/p?x=1&offset=50"]


def test_one_page_listing_asks_once(fake_tnm):
    """A 1 m listing (a handful of 10 km tiles) makes exactly the request
    discovery always made -- the controls' listing is unchanged."""
    fake_tnm["items"] = [_item("T1", "2020-01-01")]
    ea_discovery.tnm_listing_items("https://tnm.test/p", "TNM")
    assert fake_tnm["calls"] == ["https://tnm.test/p"]


def test_a_listing_that_stops_short_is_transient(fake_tnm):
    fake_tnm["items"] = [_item("T%03d" % n, "2023") for n in range(97)]
    fake_tnm["drop_page"] = 50
    with pytest.raises(ea_base.TransientFetchError, match="97 product"):
        ea_discovery.tnm_listing_items("https://tnm.test/p", "TNM")


def _opr_definition(**overrides):
    definition = {
        "code": "USGSOPRTEST",
        "access_strategy": "tnm_cog",
        "discovery_url_template": "https://tnm.test/p?bbox={west},{south},"
                                  "{east},{north}",
        "native_resolution_m": 1.0,
        "source_units": "from_source",
        "max_source_resolution_m": "2",
        "ladder_judge": "airport_cover",
        "vertical_datum": "NAVD88",
    }
    definition.update(overrides)
    return definition


def test_fetch_reads_units_and_resolution_from_the_files(tmp_path, fake_tnm,
                                                        monkeypatch):
    """Three products over one box: an OLD State Plane foot tile (3 ftUS),
    a NEWER metre tile covering only the east half, and a 5 m IFSAR DTM.
    The mosaic is in METRES everywhere (the foot tile converted), the
    newer tile wins where it has data, the IFSAR stays out, and the record
    carries the resolution and units the files declare."""
    east = (BOX[0] + 0.5 * (BOX[2] - BOX[0]), BOX[1], BOX[2], BOX[3])
    paths = {
        "OLDFT": _write_tile(tmp_path / "oldft.tif", SPFT, 1000.0, 3.0),
        "NEWM": _write_tile(tmp_path / "newm.tif", UTM, 400.0, 0.5,
                            vertical=5703, box=east),
        "IFSAR": _write_tile(tmp_path / "ifsar.tif", UTM, -50.0, 5.0),
    }
    fake_tnm["items"] = [_item("OLDFT", "2017-01-01"),
                         _item("NEWM", "2023-01-01"),
                         _item("IFSAR", "2010-01-01")]
    monkeypatch.setattr(
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy, "_warp_input_for",
        lambda self, source: paths[source["source_id"]])
    destination = str(tmp_path / "out" / "KGEG_usgs3dep.tif.rung2")
    strategy = ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy()
    provenance = strategy.fetch(_opr_definition(), BOX, 1.0, destination)
    dataset = gdal.Open(destination)
    values = dataset.GetRasterBand(1).ReadAsArray()
    dataset = None
    valid = values[values != -32768.0]
    assert valid.size > 0.9 * values.size
    west_half = values[:, : values.shape[1] // 3]
    east_half = values[:, -values.shape[1] // 3:]
    assert numpy.median(west_half) == pytest.approx(1000.0 * FTUS, abs=0.01)
    assert numpy.median(east_half) == pytest.approx(400.0, abs=0.01)
    assert not numpy.any(numpy.isclose(values, -50.0))      # IFSAR out
    assert provenance["native_resolution_from"] == "source files"
    assert provenance["native_resolution_m"] == pytest.approx(
        3.0 * FTUS, abs=1e-3)
    assert provenance["native_resolution_range_m"][0] == pytest.approx(0.5)
    assert provenance["heights_converted_to_m"] == ["US survey foot"]
    assert [entry["source_id"] for entry in
            provenance["sources_excluded_too_coarse"]] == ["IFSAR"]
    assert provenance["sources_excluded_too_coarse"][0][
        "native_resolution_m"] == pytest.approx(5.0)
    assert sorted(entry["source_id"] for entry in
                  provenance["sources_used"]) == ["NEWM", "OLDFT"]
    # the listing the ladder records names every listed product
    assert INSETS._provenance_listing_ids(provenance) == [
        "IFSAR", "NEWM", "OLDFT"]
    # no scaling VRT survives the fetch
    assert sorted(os.listdir(tmp_path / "out")) == [
        "KGEG_usgs3dep.tif.rung2"]


def test_only_coarse_products_is_no_coverage_with_the_listing_kept(
        tmp_path, fake_tnm, monkeypatch):
    paths = {"IFSAR": _write_tile(tmp_path / "ifsar.tif", UTM, -50.0, 5.0)}
    fake_tnm["items"] = [_item("IFSAR", "2010-01-01")]
    monkeypatch.setattr(
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy, "_warp_input_for",
        lambda self, source: paths[source["source_id"]])
    strategy = ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy()
    assert strategy.fetch(_opr_definition(), BOX, 1.0,
                          str(tmp_path / "a.tif")) is None
    assert INSETS._listing_ids(strategy.last_listing) == ["IFSAR"]


def test_unreadable_header_is_transient(tmp_path, fake_tnm, monkeypatch):
    fake_tnm["items"] = [_item("GONE", "2023-01-01")]
    monkeypatch.setattr(
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy, "_warp_input_for",
        lambda self, source: str(tmp_path / "missing.tif"))
    with pytest.raises(ea_base.TransientFetchError, match="header of GONE"):
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
            _opr_definition(), BOX, 1.0, str(tmp_path / "a.tif"))


def test_usgs3dep_rung_zero_is_untouched_by_source_units(
        tmp_path, fake_tnm, monkeypatch):
    """Without ``source_units`` (USGS 1 m) no header is pre-read and no
    VRT is built: the warp inputs are the listing's, as before."""
    paths = {"M": _write_tile(tmp_path / "m.tif", UTM, 400.0, 1.0)}
    fake_tnm["items"] = [_item("M", "2020-01-01")]
    monkeypatch.setattr(
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy, "_warp_input_for",
        lambda self, source: paths[source["source_id"]])
    seen = []
    real = ea_warp.warp_vsicurl_sources_to_geotiff

    def _spy(inputs, *args, **kwargs):
        seen.append((list(inputs), kwargs.get("gdal_configuration_options")))
        return real(inputs, *args, **kwargs)

    patch_inset_code(monkeypatch, "warp_vsicurl_sources_to_geotiff", _spy)
    patch_inset_code(monkeypatch, "_inspect_raster_source",
                        lambda *a: pytest.fail("header read"))
    provenance = ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
        {"code": "USGS3DEPTEST", "access_strategy": "tnm_cog",
         "discovery_url_template": "https://tnm.test/p",
         "native_resolution_m": 1.0}, BOX, 1.0, str(tmp_path / "b.tif"))
    assert seen == [([paths["M"]], None)]
    assert "native_resolution_from" not in provenance
    assert provenance["native_resolution_m"] == 1.0


def test_opr_is_never_a_whole_tile_overlay():
    """``supports_wide_area=false`` in USGSOPR.elv: the elevation_level
    overlay never reads thousands of OPR tiles for a 1 x 1 degree tile,
    even pinned; USGS3DEP still serves the US tile."""
    import O4_Elevation_Level as LEVEL

    INSETS.initialize_elevation_providers_dict()
    codes = [d["code"] for d in LEVEL._wide_area_candidate_definitions(
        47, -118, "auto")]
    assert "USGS3DEP" in codes
    assert "USGSOPR" not in codes and "USGSLPC" not in codes
    assert LEVEL._wide_area_candidate_definitions(
        47, -118, "USGSOPR") == []


def test_opr_and_lpc_are_ladder_only():
    """#153: the OPR / LPC providers are RUNGS of USGS3DEP's ladder -- never
    ranked on their own in ``auto`` (so an airport USGS3DEP answered never
    lists them as unanswered covering providers), still pinnable."""
    INSETS.initialize_elevation_providers_dict()
    auto = [d["code"] for d in INSETS.select_provider_definitions("auto")]
    assert "USGS3DEP" in auto
    assert "USGSOPR" not in auto and "USGSLPC" not in auto
    assert [d["code"] for d in INSETS.select_provider_definitions(
        "USGSOPR")] == ["USGSOPR"]
