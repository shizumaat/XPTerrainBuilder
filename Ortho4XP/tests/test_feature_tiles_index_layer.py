"""THE INDEX-LAYER FORM of ``arcgis_feature_tiles`` and the #154 holder
``.elv`` files (spec us-holder-providers §3.2/§4, RULINGS 2026-09-30bm,
issue #154, lane tx154).

Texas publishes its lidar as ONE statewide tile-index layer whose features
name a tile of a collection; the TxGIO resources API resolves a collection's
per-quad DEM zip, and the one member per tile is read out of that zip.
These twins pin, with no network:

* the index is paged to the end (``exceededTransferLimit``) and the
  resources listing followed through ``next``; a listing that never ends is
  TRANSIENT, never a truncated whole;
* a tile the resolver cannot place, or a member its archive does not hold,
  is ``unavailable`` -- never a partial mosaic delivered as the whole;
* the cap counts MEMBERS and refuses as ``unavailable``;
* the surgical core (``footprint_buffer_m`` + the ladder's footprint) keeps
  only tiles meeting the buffered boundary and carries a ``core`` block;
* ``.img`` members warp like ``.tif``, and a member with NO CRS takes the
  definition's ``source_srs``;
* every shipped holder ``.elv`` parses, declares its vertical unit, joins
  the ladder, and its coverage box keeps the five controls out.
"""

import json
import os
import types
import zipfile

import numpy
import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES

try:
    from osgeo import gdal, osr

    gdal.UseExceptions()
    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

BOX = (-97.84, 31.06, -97.82, 31.08)          # KGRK-sized
LAYER = "https://index.test/FeatureServer/0"
RESOURCES = "https://api.test/resources/?collection_id={collid}"
COLLECTION = "c0ffee"
# Three 0.01-degree tiles side by side across the box (west to east).
TILES = {
    "3197581a1": (-97.84, 31.06, -97.83, 31.07),
    "3197581a2": (-97.83, 31.06, -97.82, 31.07),
    "3197581b1": (-97.84, 31.07, -97.83, 31.08),
}


def _tile_raster(path, box, value, with_crs=True, driver="GTiff",
                 nodata=-9999.0, size=20):
    dataset = gdal.GetDriverByName(driver).Create(
        str(path), size, size, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((box[0], (box[2] - box[0]) / size, 0.0,
                             box[3], 0.0, -(box[3] - box[1]) / size))
    if with_crs:
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.WriteArray(numpy.full((size, size), value, dtype=numpy.float32))
    dataset = None


def _quad_zip(tmp_path, members):
    """One per-quad zip ``{prefix}_{key}_dem.zip`` holding ``members``
    (``{name: (box, value, with_crs, driver)}``) plus a .tfw companion."""
    path = tmp_path / "proj20-50cm-test_3197581_dem.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for (name, (box, value, with_crs, driver)) in members.items():
            local = tmp_path / name
            _tile_raster(local, box, value, with_crs=with_crs, driver=driver)
            archive.write(local, name)
            archive.writestr(os.path.splitext(name)[0] + ".xml", "<x/>")
    return str(path)


def _ring(box):
    (w, s, e, n) = box
    return {"rings": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def _definition(tmp_path, **extra):
    definition = {
        "code": "TXTEST",
        "access_strategy": "arcgis_feature_tiles",
        "index_layer_url": LAYER,
        "index_where": "bestavail='Yes'",
        "tile_id_field": "tileid",
        "collection_field": "collid",
        "archive_resolver": "tnris_resources",
        "archive_resolver_url": RESOURCES,
        # A LOCAL archive path stands in for the S3 origin.
        "archive_url_template": str(tmp_path) + "/{prefix}_{tileid7}_dem.zip",
        "archive_access": "remote_member",
        "member_filter_template": "-1m_{tileid}",
        "max_archives_per_airport": "16",
        "vertical_unit": "m",
        "native_resolution_m": "1",
    }
    definition.update(extra)
    return definition


class _FakeServer:
    """The index layer (two pages) and the resources API (two pages)."""

    def __init__(self, tiles=TILES, resource_keys=("3197581",),
                 index_status=200, endless_index=False):
        self.tiles = tiles
        self.resource_keys = list(resource_keys)
        self.index_status = index_status
        self.endless_index = endless_index
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if url == LAYER + "/query":
            if self.index_status != 200:
                return types.SimpleNamespace(
                    status_code=self.index_status, json=lambda: {})
            offset = int(params["resultOffset"])
            names = sorted(self.tiles)
            # The server's maxRecordCount is 2, below what is asked for.
            count = min(int(params["resultRecordCount"]), 2)
            page = names[offset:offset + count] if not self.endless_index \
                else names[:1]
            features = [
                {"attributes": {"tileid": name, "collid": COLLECTION},
                 "geometry": _ring(self.tiles[name])}
                for name in page
            ]
            payload = {"features": features,
                       "exceededTransferLimit": self.endless_index
                       or offset + len(page) < len(names)}
            return types.SimpleNamespace(status_code=200,
                                         json=lambda: payload)
        if url.startswith("https://api.test/resources/"):
            page2 = url.endswith("&page=2")
            results = [] if page2 else [
                {"resource": "https://cdn.test/%s/resources/"
                             "proj20-50cm-test_%s_dem.zip" % (COLLECTION, key)}
                for key in self.resource_keys]
            if page2:
                results = [{"resource": "https://cdn.test/x/resources/"
                                        "proj20-50cm-test_9999999_dem.zip"}]
            payload = {"count": len(self.resource_keys) + 1,
                       "results": results,
                       "next": None if page2 else url + "&page=2"}
            return types.SimpleNamespace(status_code=200,
                                         json=lambda: payload)
        raise AssertionError("unexpected GET " + url)


@pytest.fixture
def server(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "elev"))
    fake = _FakeServer()
    monkeypatch.setattr(requests, "get", fake.get)
    return fake


pytestmark = pytest.mark.skipif(not HAS_GDAL, reason="no osgeo")


def _strategy():
    return INSETS.ACCESS_STRATEGIES["arcgis_feature_tiles"]()


def test_index_layer_pages_resolves_and_reads_one_member_per_tile(
        tmp_path, server):
    _quad_zip(tmp_path, {
        "proj20-1m_3197581a1.tif": (TILES["3197581a1"], 300.0, True, "GTiff"),
        "proj20-1m_3197581a2.tif": (TILES["3197581a2"], 310.0, True, "GTiff"),
        "proj20-1m_3197581b1.tif": (TILES["3197581b1"], 320.0, True, "GTiff"),
        # A member no feature names: never read.
        "proj20-1m_3197581z9.tif": (TILES["3197581b1"], 999.0, True, "GTiff"),
    })
    destination = str(tmp_path / "KGRK_txtest.tif")
    provenance = INSETS.fetch_inset(_definition(tmp_path), BOX, 50.0,
                                    destination)
    assert provenance is not None
    assert provenance["source_ids"] == sorted(TILES)
    assert provenance["archive_members"] == 3
    assert provenance["vertical_unit_applied"] == "m"
    result = gdal.Open(destination)
    values = result.GetRasterBand(1).ReadAsArray()
    valid = values[values > -32768]
    assert valid.size and 299.5 < float(valid.min()) \
        and float(valid.max()) < 320.5
    # Both index pages were read; the where clause rode every query.
    queries = [p for (u, p) in server.calls if u == LAYER + "/query"]
    # The server answered 2 of the 1,000 asked for: the next page starts
    # at what ARRIVED, not at the page size asked for.
    assert [q["resultOffset"] for q in queries] == ["0", "2"]
    assert all(q["where"] == "bestavail='Yes'" for q in queries)
    # The resources listing was followed through ``next`` and memoised.
    with open(_strategy().resources_path(_definition(tmp_path)),
              encoding="utf-8") as handle:
        memo = json.load(handle)
    assert set(memo[COLLECTION]) == {"3197581", "9999999"}
    assert memo[COLLECTION]["3197581"] == (
        str(tmp_path) + "/proj20-50cm-test_3197581_dem.zip")
    # Scratch members were removed.
    assert not os.path.exists(destination + ".members")


def test_index_layer_page_size_is_asked_for(tmp_path, server, monkeypatch):
    strategy_class = INSETS.ACCESS_STRATEGIES["arcgis_feature_tiles"]
    monkeypatch.setattr(strategy_class, "INDEX_PAGE_SIZE", 1)
    entries = strategy_class().discover(_definition(tmp_path), BOX)
    assert [e["source_id"] for e in entries] == sorted(TILES)
    offsets = [p["resultOffset"] for (u, p) in server.calls
               if u == LAYER + "/query"]
    assert offsets == ["0", "1", "2"]


def test_index_layer_listing_that_never_ends_is_transient(tmp_path,
                                                          monkeypatch):
    import requests

    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "elev"))
    monkeypatch.setattr(requests, "get",
                        _FakeServer(endless_index=True).get)
    with pytest.raises(INSETS.TransientFetchError):
        _strategy().discover(_definition(tmp_path), BOX)


def test_index_layer_5xx_is_transient_never_no_coverage(tmp_path,
                                                        monkeypatch):
    import requests

    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "elev"))
    monkeypatch.setattr(requests, "get",
                        _FakeServer(index_status=503).get)
    with pytest.raises(INSETS.TransientFetchError):
        _strategy().discover(_definition(tmp_path), BOX)


def test_discovery_lists_tiles_without_resolving_or_writing(
        tmp_path, server):
    """Asking "is there coverage" (the ladder re-check, the census) lists
    the index tiles only: no resources-API call, no memo write."""
    entries = _strategy().discover(_definition(tmp_path), BOX)
    assert [e["source_id"] for e in entries] == sorted(TILES)
    assert not [u for (u, _p) in server.calls
                if u.startswith("https://api.test/")]
    assert not os.path.exists(_strategy().resources_path(
        _definition(tmp_path)))


def test_tile_without_a_resource_is_unavailable_after_one_refresh(
        tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "elev"))
    fake = _FakeServer(resource_keys=("3097000",))
    monkeypatch.setattr(requests, "get", fake.get)
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        _strategy().discover(_definition(tmp_path), BOX, resolve=True)
    assert "has no archive in collection" in str(caught.value)
    # The memo was consulted, then the listing refetched ONCE.
    listings = [u for (u, _p) in fake.calls
                if u.startswith("https://api.test/") and "page=2" not in u]
    assert len(listings) == 2


def test_member_missing_from_its_archive_is_unavailable(tmp_path, server):
    _quad_zip(tmp_path, {
        "proj20-1m_3197581a1.tif": (TILES["3197581a1"], 300.0, True, "GTiff"),
    })
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        _strategy().fetch(_definition(tmp_path), BOX, 50.0,
                          str(tmp_path / "KGRK_txtest.tif"))
    assert "holds no member" in str(caught.value)
    assert not os.path.exists(str(tmp_path / "KGRK_txtest.tif"))


def test_member_cap_is_unavailable_in_members(tmp_path, server):
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        _strategy().fetch(
            _definition(tmp_path, max_archives_per_airport="2"), BOX, 50.0,
            str(tmp_path / "KGRK_txtest.tif"))
    assert ("TXTEST: KGRK needs 3 archive members, cap 2 "
            "(max_archives_per_airport in TXTEST.elv)") in str(caught.value)


def test_surgical_core_keeps_only_tiles_meeting_the_boundary(
        tmp_path, server):
    from shapely.geometry import box as shapely_box

    _quad_zip(tmp_path, {
        "proj20-1m_3197581a1.tif": (TILES["3197581a1"], 300.0, True, "GTiff"),
        "proj20-1m_3197581a2.tif": (TILES["3197581a2"], 310.0, True, "GTiff"),
        "proj20-1m_3197581b1.tif": (TILES["3197581b1"], 320.0, True, "GTiff"),
    })
    # A boundary inside the south-west tile, buffered 50 m: it meets a1
    # only (the tiles are ~950 m wide).
    boundary = shapely_box(-97.838, 31.062, -97.834, 31.066)
    definition = _definition(tmp_path, footprint_buffer_m="50",
                             core_feather_m="20")
    definition[INSETS.LAS_FOOTPRINT_KEY] = INSETS._polygon_mapping(boundary)
    provenance = _strategy().fetch(definition, BOX, 50.0,
                                   str(tmp_path / "KGRK_txtest.tif"))
    assert provenance["source_ids"] == ["3197581a1"]
    core = provenance["core"]
    assert core["tile_names"] == ["3197581a1"]
    assert core["footprint_buffer_m"] == 50.0
    assert core["feather_m"] == 20.0
    # The index was asked over the CORE's envelope, with geometry.
    query = [p for (u, p) in server.calls if u == LAYER + "/query"][0]
    assert query["returnGeometry"] == "true"
    # Without the opt-in key the footprint is ignored: the whole box.
    del definition["footprint_buffer_m"]
    assert len(_strategy().discover(definition, BOX)) == 3


def test_img_member_and_source_srs_fallback(tmp_path, server):
    _quad_zip(tmp_path, {
        "proj20-1m_3197581a1.tif": (TILES["3197581a1"], 300.0, True, "GTiff"),
        # Erdas IMAGINE member WITHOUT any CRS: declared by source_srs.
        "proj20-1m_3197581a2.img": (TILES["3197581a2"], 310.0, False, "HFA"),
        "proj20-1m_3197581b1.tif": (TILES["3197581b1"], 320.0, True, "GTiff"),
    })
    destination = str(tmp_path / "KGRK_txtest.tif")
    provenance = _strategy().fetch(
        _definition(tmp_path, source_srs="EPSG:4326"), BOX, 50.0,
        destination)
    assert provenance is not None
    result = gdal.Open(destination)
    values = result.GetRasterBand(1).ReadAsArray()
    assert numpy.any(numpy.abs(values - 310.0) < 0.5)


def test_url_form_provenance_keys_unchanged():
    """The Ireland (URL) form gains NO provenance key: the additive keys
    belong to the index-layer form only."""
    import inspect

    source = inspect.getsource(
        INSETS.ACCESS_STRATEGIES["arcgis_feature_tiles"].fetch)
    assert 'if definition.get("index_layer_url"):' in source


# ---------------------------------------------------------------------
# The shipped #154 holder files
# ---------------------------------------------------------------------
HOLDER_FILES = {
    # code: (unit, witness airport lat/lon)
    "TEXAS1M": ("m", (31.06911, -97.8297)),          # KGRK
    "NCPHASE3": ("ftUS", (35.87804, -78.7868)),      # KRDU
    "NOAATXJLC1M": ("m", (30.06925, -94.2119)),      # KBMT
    "NOAAKETCHIKAN": ("m", (55.35534, -131.70909)),  # PAKT
    "NOAAAKCOASTAL": ("m", (59.04338, -158.51005)),  # PADL
    "NOAACOLUMBIARIVER": ("m", (46.15666, -123.88084)),  # KAST
}
CONTROLS = {"HECA": (30.1219, 31.4056), "KCLT": (35.2140, -80.9431),
            "SPJC": (-12.0219, -77.1143), "CYXY": (60.7096, -135.0674),
            "KASE": (39.2232, -106.8688)}


def _point_box(lat, lon, half=0.02):
    return (lon - half, lat - half, lon + half, lat + half)


@pytest.mark.parametrize("code", sorted(HOLDER_FILES))
def test_holder_elv_parses_declares_unit_and_joins_the_ladder(code):
    INSETS.initialize_elevation_providers_dict()
    definition = INSETS.elevation_providers_dict[code]
    (unit, (lat, lon)) = HOLDER_FILES[code]
    assert definition["role"] == "airport_inset"
    assert definition["enabled"] in (True, "True")
    assert str(definition["ladder_member"]) == "True"
    assert float(definition["priority"]) == 90.0
    assert INSETS._raster_vertical_unit(definition) == unit
    assert definition.get("vertical_datum") == "NAVD88"
    assert definition.get("license") and definition.get("license_note")
    assert definition.get("attribution")
    assert INSETS._coverage_bbox_intersects(definition,
                                            _point_box(lat, lon))
    for (icao, (clat, clon)) in CONTROLS.items():
        assert not INSETS._coverage_bbox_intersects(
            definition, _point_box(clat, clon)), (code, icao)


def test_holder_elv_transport_is_never_the_bot_refusing_host():
    INSETS.initialize_elevation_providers_dict()
    texas = INSETS.elevation_providers_dict["TEXAS1M"]
    assert texas["archive_url_template"].startswith(
        "https://s3.amazonaws.com/data.tnris.org/")
    assert "data.geographic.texas.gov" not in texas["archive_url_template"]
    assert int(float(texas["max_archives_per_airport"])) == 16
    nc = INSETS.elevation_providers_dict["NCPHASE3"]
    assert [url.rsplit("/", 1)[-1] for url in nc["cog_urls"].split(",")] == [
        "NC_phase3_2024_m15636_EPSG-6543.vrt",
        "NC_phase3_2024_m15636_EPSG-6543_1.vrt"]
