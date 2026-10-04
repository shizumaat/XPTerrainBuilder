"""#157 -- zipped IMG products on the ``tnm_cog`` strategy (KGRK).

TNM lists the NED 1/9 arc-second (3 m) products over much of the US as
ERDAS IMAGINE ``.img`` files INSIDE a zip
(``…/Elevation/19/IMG/ned19_n31x25_w098x00_tx_bellburnetmclennancos_2011.zip``
over KGRK, measured 2026-09-30).  The rung handed that zip to the warp as
``/vsicurl/…zip`` (not a raster), the warp failed, and the failure was
recorded as a DURABLE no-coverage -- KGRK took 10 m although a 3 m product
lists over it.  Two laws:

1. a zipped product is downloaded whole to scratch beside the
   destination, its raster member (``.img``, else ``.tif``) is warped
   through ``/vsizip/``, and the scratch is removed;
2. a listed product the engine cannot decode is ``unavailable`` with the
   reason (RULINGS 2026-09-13b) -- the ladder climbs and the re-check asks
   again -- never no-coverage; a well-formed EMPTY listing stays the
   durable no-coverage.

No network: ``requests.get`` is a fake TNM (listing JSON + zip bodies).
"""

import io
import os
import zipfile

import numpy
import pytest

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS
from elevation_access import base as ea_base
from elevation_access import definitions as ea_definitions
from elevation_access.strategies import tnm_cog as ea_tnm_cog
from elevation_access import warp as ea_warp

gdal = pytest.importorskip("osgeo.gdal")
from osgeo import osr  # noqa: E402

#: KGRK's inset box (lane tx154, #157).
BOX = (-97.8607, 31.0328, -97.7982, 31.1027)
LISTING_FINE = "https://tnm.test/products?datasets=19"
LISTING_COARSE = "https://tnm.test/products?datasets=13"
LISTING_ONE_M = "https://tnm.test/products?datasets=1m"
ZIP_URL = "https://prd-tnm.test/Elevation/19/IMG/ned19_kgrk.zip"
COARSE_ZIP_URL = "https://prd-tnm.test/Elevation/13/TIFF/usgs13_kgrk.zip"
FIELD_M = 305.5


def _raster_bytes(tmp_path, name, driver, value):
    """A raster over BOX (+ margin) in EPSG:4326 NAD83-ish, as bytes per
    file the driver wrote (HFA may write one file)."""
    path = str(tmp_path / name)
    size = 64
    dataset = gdal.GetDriverByName(driver).Create(
        path, size, size, 1, gdal.GDT_Float32)
    west, south, east, north = (BOX[0] - 0.01, BOX[1] - 0.01,
                                BOX[2] + 0.01, BOX[3] + 0.01)
    dataset.SetGeoTransform((west, (east - west) / size, 0.0, north, 0.0,
                             -(north - south) / size))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4269)
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-3.4028234663852886e38)
    band.WriteArray(numpy.full((size, size), value, dtype=numpy.float32))
    dataset = None
    with open(path, "rb") as handle:
        return handle.read()


def _zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for (name, data) in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class _Response:
    def __init__(self, payload=None, body=None, status=200,
                 content_type="application/json"):
        self.status_code = status
        self._payload = payload
        self._body = body or b""
        self.headers = {"Content-Type": content_type,
                        "Content-Length": str(len(self._body))}

    def json(self):
        return self._payload

    def iter_content(self, size):
        for start in range(0, len(self._body), size):
            yield self._body[start:start + size]

    def close(self):
        pass


def _item(url, source_id):
    return {"downloadURL": url, "sourceId": source_id,
            "title": "USGS NED %s" % source_id,
            "publicationDate": "2011-01-01",
            "boundingBox": {"minX": BOX[0], "minY": BOX[1],
                            "maxX": BOX[2], "maxY": BOX[3]}}


@pytest.fixture
def fake_tnm(monkeypatch):
    """``listings[prefix]`` = items; ``bodies[url]`` = zip bytes (absent:
    a 404)."""
    import requests

    state = {"listings": {}, "bodies": {}, "gets": []}

    def _get(url, **kwargs):
        state["gets"].append(url)
        for (prefix, items) in state["listings"].items():
            if url.startswith(prefix):
                return _Response({"total": len(items), "items": items})
        if url in state["bodies"]:
            return _Response(body=state["bodies"][url],
                             content_type="application/zip")
        return _Response(status=404, content_type="text/plain")

    monkeypatch.setattr(requests, "get", _get)
    return state


def _definition(listing=LISTING_FINE, native=3.0, code="USGS3DEPZIPTEST"):
    return {"code": code, "access_strategy": "tnm_cog",
            "discovery_url_template": listing + "&bbox={west},{south},"
                                                "{east},{north}",
            "native_resolution_m": native}


def _values(path):
    dataset = gdal.Open(path)
    values = dataset.GetRasterBand(1).ReadAsArray()
    dataset = None
    return values


def test_a_zipped_img_product_warps_and_leaves_no_scratch(tmp_path,
                                                         fake_tnm):
    img = _raster_bytes(tmp_path, "src.img", "HFA", FIELD_M)
    fake_tnm["listings"][LISTING_FINE] = [_item(ZIP_URL, "ned19_kgrk")]
    fake_tnm["bodies"][ZIP_URL] = _zip({
        "ned19_kgrk.shp": b"not a raster",
        "readme.pdf": b"%PDF",
        "ned19_kgrk.img": img,
    })
    out = tmp_path / "out"
    destination = str(out / "KGRK_usgs3dep.tif.rung4")
    provenance = ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
        _definition(), BOX, 3.0, destination)
    values = _values(destination)
    assert numpy.all(values == pytest.approx(FIELD_M))
    assert provenance["source_urls"] == [ZIP_URL]
    assert [entry["source_id"] for entry in provenance["sources_used"]] == [
        "ned19_kgrk"]
    assert provenance["valid_fraction"] == 1.0
    assert sorted(os.listdir(out)) == ["KGRK_usgs3dep.tif.rung4"]


def test_a_zip_without_img_takes_its_geotiff_member(tmp_path, fake_tnm):
    tif = _raster_bytes(tmp_path, "src.tif", "GTiff", 300.0)
    fake_tnm["listings"][LISTING_FINE] = [_item(ZIP_URL, "z")]
    fake_tnm["bodies"][ZIP_URL] = _zip({"inner/z.tif": tif})
    destination = str(tmp_path / "a.tif")
    ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
        _definition(), BOX, 3.0, destination)
    assert numpy.all(_values(destination) == pytest.approx(300.0))


def test_an_undecodable_product_is_unavailable_never_no_coverage(
        tmp_path, fake_tnm):
    fake_tnm["listings"][LISTING_FINE] = [_item(ZIP_URL, "ned19_kgrk")]
    fake_tnm["bodies"][ZIP_URL] = _zip({"ned19_kgrk.img": b"\0garbage" * 64})
    out = tmp_path / "out"
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="1 listed product.*could not be read"):
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
            _definition(), BOX, 3.0, str(out / "KGRK.tif"))
    assert not out.exists() or os.listdir(out) == []


def test_an_unreadable_listed_raster_is_unavailable(tmp_path, fake_tnm,
                                                    monkeypatch):
    """The same law for a plain (unzipped) product: the 1 m and 1/3
    arc-second rungs list GeoTIFFs, and one the engine cannot read is
    ``unavailable`` too."""
    bad = tmp_path / "bad.tif"
    bad.write_bytes(b"II*\0garbage")
    fake_tnm["listings"][LISTING_ONE_M] = [
        _item("https://prd-tnm.test/1m/x.tif", "x")]
    monkeypatch.setattr(ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy,
                        "_warp_input_for", lambda self, source: str(bad))
    with pytest.raises(ea_base.ProviderUnavailable, match="could not be read"):
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
            _definition(LISTING_ONE_M, 1.0), BOX, 1.0,
            str(tmp_path / "b.tif"))


def test_a_zip_with_no_raster_member_is_unavailable(tmp_path, fake_tnm):
    fake_tnm["listings"][LISTING_FINE] = [_item(ZIP_URL, "z")]
    fake_tnm["bodies"][ZIP_URL] = _zip({"z.shp": b"x", "readme.pdf": b"y"})
    with pytest.raises(ea_base.ProviderUnavailable, match="no raster member"):
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
            _definition(), BOX, 3.0, str(tmp_path / "c.tif"))
    assert not any(name.endswith(".zip") for name in os.listdir(tmp_path))


def test_a_listed_archive_missing_from_the_server_is_unavailable(
        tmp_path, fake_tnm):
    fake_tnm["listings"][LISTING_FINE] = [_item(ZIP_URL, "z")]
    with pytest.raises(ea_base.ProviderUnavailable, match="HTTP 404"):
        ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
            _definition(), BOX, 3.0, str(tmp_path / "d.tif"))


def test_a_well_formed_empty_listing_is_still_no_coverage(tmp_path,
                                                         fake_tnm):
    fake_tnm["listings"][LISTING_FINE] = []
    assert ea_tnm_cog.TnmCloudOptimizedGeoTiffStrategy().fetch(
        _definition(), BOX, 3.0, str(tmp_path / "e.tif")) is None
    assert fake_tnm["gets"] == [
        _definition()["discovery_url_template"].format(
            west=repr(BOX[0]), south=repr(BOX[1]), east=repr(BOX[2]),
            north=repr(BOX[3]))]


def test_the_ladder_records_unavailable_and_climbs(tmp_path, fake_tnm,
                                                   monkeypatch):
    """KGRK in miniature, through the ladder: 1 m lists nothing, the 1/9
    arc-second zip holds an undecodable IMG -> ``unavailable`` with the
    reason (no listing recorded, so the re-check asks it again), and the
    1/3 arc-second rung (a zipped GeoTIFF) delivers."""
    tif = _raster_bytes(tmp_path, "coarse.tif", "GTiff", 299.0)
    fake_tnm["listings"][LISTING_ONE_M] = []
    fake_tnm["listings"][LISTING_FINE] = [_item(ZIP_URL, "ned19_kgrk")]
    fake_tnm["listings"][LISTING_COARSE] = [_item(COARSE_ZIP_URL, "u13")]
    fake_tnm["bodies"][ZIP_URL] = _zip({"ned19_kgrk.img": b"\0bad" * 64})
    fake_tnm["bodies"][COARSE_ZIP_URL] = _zip({"u13.tif": tif})
    chain = dict(_definition(LISTING_ONE_M, 1.0, code="USGS3DEPZIPCHAIN"),
                 role=ea_definitions.ROLE_AIRPORT_INSET, enabled=True, priority=1.0,
                 ladder_label="1 meter")
    chain["resolution_ladder_rungs"] = INSETS._parse_resolution_ladder(
        "3|1/9 arc-second|%s&bbox={west},{south},{east},{north};"
        "10|1/3 arc-second|%s&bbox={west},{south},{east},{north}"
        % (LISTING_FINE, LISTING_COARSE))
    monkeypatch.setattr(INSETS, "elevation_providers_dict",
                        {chain["code"]: chain})
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    out = tmp_path / "insets"
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(out / "KGRK_usgs3depzipchain.tif"),
                                    resolution_ladder=True)
    tried = provenance["ladder"]["rungs_tried"]
    assert [r["outcome"] for r in tried] == [
        "no-coverage", "unavailable", "delivered"]
    assert "could not be read" in tried[1]["unavailable_reason"]
    assert "listing_ids" not in tried[1]
    assert INSETS._stored_rung_listing(tried[1]) is None   # re-asked
    assert provenance["ladder"]["delivered_label"] == "1/3 arc-second"
    assert not any(name.endswith(".zip") for name in os.listdir(out))


def test_a_local_archive_member_keeps_the_curl_extension_fence():
    fence = ea_warp._vsicurl_allowed_extensions(
        ["/vsizip//tmp/x.tif.tnm0.zip/a.img",
         "/vsicurl/https://prd-tnm.test/a.tif"])
    assert fence == ".tif,.tiff,.vrt"
    assert ea_warp._vsicurl_allowed_extensions(
        ["/vsizip//vsicurl/https://h.test/a.zip/a.img"]) is None
