"""#130 -- the ``las_tile_index`` strategy (PITKIN1M, KASE / Aspen).

Spec ``docs/specs/las-tile-lidar-provider-spec.md`` §3 / §8.4.  A
synthetic 50 x 50 m LAS 1.4 point-format-6 tile (EPSG 6428, US survey
feet) carrying ground on an analytic plane, class-6 roofs and WITHHELD
ground spikes grids to the plane within 1 cm; an empty block fills to
radius 3 and stays NoData beyond; a LAZ / a CRS mismatch / a short file
refuse with :class:`ProviderUnavailable`; an ArcGIS ``{"error": ...}``
inside a 200 is transient; the size-cap wording is exact.  No network:
``requests`` is faked.
"""

import json
import math
import os

import numpy
import pytest

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS

laspy = pytest.importorskip("laspy")
pyproj = pytest.importorskip("pyproj")
gdal = pytest.importorskip("osgeo.gdal")
from osgeo import osr  # noqa: E402

FTUS = 1200.0 / 3937.0
CELL_FT = 1.0 / FTUS                 # a 1 m cell in the source CRS
N_CELLS = 50                         # 50 x 50 m
I0 = int(math.floor(2611000.0 / CELL_FT))
J0 = int(math.floor(1510000.0 / CELL_FT))
HOLE = (19, 31)                      # empty block: cells [19, 31) both axes


def _plane_ft(x, y):
    return 7800.0 + 0.02 * (x - I0 * CELL_FT) + 0.01 * (y - J0 * CELL_FT)


def _definition(**overrides):
    definition = {
        "code": "PITKINTEST",
        "access_strategy": "las_tile_index",
        "role": INSETS.ROLE_AIRPORT_INSET,
        "enabled": True,
        "index_url_template": "https://index.test/q?bbox={west},{south},"
                              "{east},{north}",
        "index_name_field": "name",
        "tile_url_template": "https://tiles.test/2016-{name}.las",
        "source_crs": "6428",
        "vertical_unit": "ftUS",
        "vertical_datum": "NAVD88",
        "ground_classes": "2",
        "grid_resolution_m": "1",
        "native_resolution_m": 1.0,
        "min_points_per_cell": "1",
        "fill_radius_cells": "3",
        "max_tiles_per_airport": "64",
        "max_bytes_per_airport": "8000000000",
        "keep_raw_las": "true",
        "rmse_z_m": "0.045",
        "publication_date": "2016-08",
        "license": "test licence",
        "license_note": "test note",
        "attribution": "test attribution",
    }
    definition.update(overrides)
    return definition


def _write_las(path, epsg=6428, hole=True):
    """Four symmetric ground points per cell (so a cell mean IS the plane
    at the cell centre), a class-6 roof 100 ft up in every cell, and a
    WITHHELD ground spike 500 ft up in every fifth cell -- the hole too."""
    xs, ys, zs, cls, withheld = [], [], [], [], []
    offsets = (-0.25, 0.25)
    for i in range(N_CELLS):
        for j in range(N_CELLS):
            cx = (I0 + i + 0.5) * CELL_FT
            cy = (J0 + j + 0.5) * CELL_FT
            in_hole = hole and HOLE[0] <= i < HOLE[1] and \
                HOLE[0] <= j < HOLE[1]
            if not in_hole:
                for dx in offsets:
                    for dy in offsets:
                        x = cx + dx * CELL_FT
                        y = cy + dy * CELL_FT
                        xs.append(x), ys.append(y)
                        zs.append(_plane_ft(x, y))
                        cls.append(2), withheld.append(False)
            xs.append(cx), ys.append(cy)
            zs.append(_plane_ft(cx, cy) + 100.0)
            cls.append(6), withheld.append(False)
            if (i * N_CELLS + j) % 5 == 0:
                xs.append(cx), ys.append(cy)
                zs.append(_plane_ft(cx, cy) + 500.0)
                cls.append(2), withheld.append(True)
    header = laspy.LasHeader(point_format=6, version="1.4")
    header.scales = numpy.array([0.001, 0.001, 0.001])
    header.offsets = numpy.array([2611000.0, 1510000.0, 7800.0])
    header.add_crs(pyproj.CRS.from_epsg(epsg))
    data = laspy.LasData(header)
    data.x = numpy.array(xs)
    data.y = numpy.array(ys)
    data.z = numpy.array(zs)
    data.classification = numpy.array(cls, dtype=numpy.uint8)
    data.withheld = numpy.array(withheld, dtype=bool)
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    data.write(str(path))
    return str(path)


def _read(path):
    dataset = gdal.Open(str(path))
    values = dataset.GetRasterBand(1).ReadAsArray().astype(numpy.float64)
    transform = dataset.GetGeoTransform()
    dataset = None
    return values, transform


def test_ground_grids_to_the_analytic_plane_in_metres(tmp_path):
    las = _write_las(tmp_path / "t.las", hole=False)
    dtm = tmp_path / "t_dtm.tif"
    record = INSETS.grid_las_tile(las, str(dtm), _definition())
    values, transform = _read(dtm)
    assert values.shape == (N_CELLS, N_CELLS)
    # Anchored on the CRS-origin lattice: adjacent tiles share cell edges.
    assert transform[0] == pytest.approx(I0 * CELL_FT, abs=1e-6)
    assert transform[1] == pytest.approx(CELL_FT, abs=1e-9)
    for row in range(N_CELLS):
        for col in range(N_CELLS):
            cx = (I0 + col + 0.5) * CELL_FT
            cy = (J0 + N_CELLS - row - 0.5) * CELL_FT
            # ftUS -> m; the roofs (class 6) and the WITHHELD spikes are out.
            assert abs(values[row, col] - _plane_ft(cx, cy) * FTUS) < 0.01
    assert record["points_ground"] == 4 * N_CELLS * N_CELLS
    assert record["cells_valid"] == N_CELLS * N_CELLS
    assert record["cells_filled"] == 0
    assert record["ground_density_per_m2"] == pytest.approx(4.0, rel=1e-3)
    assert record["grid_rule_version"] == INSETS.LAS_GRID_RULE_VERSION
    with open(str(dtm)[:-4] + ".json", encoding="utf-8") as handle:
        assert json.load(handle) == record


def test_empty_block_fills_to_radius_three_and_nodata_beyond(tmp_path):
    las = _write_las(tmp_path / "t.las", hole=True)
    dtm = tmp_path / "t_dtm.tif"
    record = INSETS.grid_las_tile(las, str(dtm), _definition())
    values, _transform = _read(dtm)
    nodata = values == INSETS.LAS_DTM_NODATA
    side = HOLE[1] - HOLE[0]                    # 12 cells
    inner = side - 2 * 3                        # 6 cells stay empty
    assert int(nodata.sum()) == inner * inner
    assert record["cells_filled"] == side * side - inner * inner
    # the NoData block is the hole's centre, in raster rows (north up)
    rows = sorted({r for r, _c in zip(*numpy.nonzero(nodata))})
    cols = sorted({c for _r, c in zip(*numpy.nonzero(nodata))})
    assert cols == list(range(HOLE[0] + 3, HOLE[1] - 3))
    assert rows == list(range(N_CELLS - HOLE[1] + 3, N_CELLS - HOLE[0] - 3))
    # a filled cell is a neighbour mean of the plane: close, never a spike
    filled = (~nodata)
    assert values[filled].max() < (_plane_ft((I0 + 50) * CELL_FT,
                                             (J0 + 50) * CELL_FT)
                                   * FTUS + 0.05)


def test_grid_is_deterministic(tmp_path):
    las = _write_las(tmp_path / "t.las")
    a = INSETS.grid_las_tile(las, str(tmp_path / "a_dtm.tif"), _definition())
    b = INSETS.grid_las_tile(las, str(tmp_path / "b_dtm.tif"), _definition())
    assert a == b
    assert numpy.array_equal(_read(tmp_path / "a_dtm.tif")[0],
                             _read(tmp_path / "b_dtm.tif")[0])


def test_valid_tile_passes_validation(tmp_path):
    las = _write_las(tmp_path / "t.las")
    summary = INSETS.validate_las_tile(las, _definition())
    assert summary["epsg"] == 6428


def test_crs_mismatch_refuses(tmp_path):
    las = _write_las(tmp_path / "t.las", epsg=2232)   # CO Central ftUS NAD83
    with pytest.raises(INSETS.ProviderUnavailable, match="EPSG:2232"):
        INSETS.validate_las_tile(las, _definition())


def test_short_file_refuses(tmp_path):
    las = _write_las(tmp_path / "t.las")
    with open(las, "r+b") as handle:
        handle.truncate(os.path.getsize(las) - 17)
    with pytest.raises(INSETS.ProviderUnavailable, match="short or damaged"):
        INSETS.validate_las_tile(las, _definition())


def test_laz_refuses(tmp_path):
    las = _write_las(tmp_path / "t.las")
    laz = las[:-4] + ".laz"
    os.rename(las, laz)
    with pytest.raises(INSETS.ProviderUnavailable, match="LAZ needs a backend"):
        INSETS.validate_las_tile(laz, _definition())
    # a compressed point-format bit in an otherwise LAS-named file
    las = _write_las(tmp_path / "u.las")
    with open(las, "r+b") as handle:
        handle.seek(104)
        handle.write(bytes([6 | 0x80]))
    with pytest.raises(INSETS.ProviderUnavailable, match="LAZ needs a backend"):
        INSETS.validate_las_tile(las, _definition())


# ---------------------------------------------------------------------
# discovery + fetch, with ``requests`` faked
# ---------------------------------------------------------------------
class _Response:
    def __init__(self, status=200, payload=None, body=b"", headers=None):
        self.status_code = status
        self._payload = payload
        self._body = body
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def iter_content(self, size):
        for start in range(0, len(self._body), size):
            yield self._body[start:start + size]

    def close(self):
        pass


def _box_of_tile():
    source = osr.SpatialReference()
    source.ImportFromEPSG(6428)
    target = osr.SpatialReference()
    target.ImportFromEPSG(4326)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, target)
    corners = [transform.TransformPoint((I0 + a) * CELL_FT,
                                        (J0 + b) * CELL_FT)
               for a in (8, N_CELLS - 8) for b in (8, N_CELLS - 8)]
    lons = [c[0] for c in corners]
    lats = [c[1] for c in corners]
    return (min(lons), min(lats), max(lons), max(lats))


@pytest.fixture
def fake_http(monkeypatch):
    import requests

    state = {"index": {"features": [{"attributes": {"name": "T1"}}]},
             "tiles": {}, "calls": []}

    def _get(url, **kwargs):
        state["calls"].append(("GET", url, dict(kwargs.get("headers")
                                                or {})))
        if url.startswith("https://index.test/"):
            payload = state["index"]
            if isinstance(payload, _Response):
                return payload
            return _Response(200, payload)
        name = url.rsplit("2016-", 1)[-1][:-4]
        body = state["tiles"].get(name)
        if body is None:
            return _Response(404)
        rng = (kwargs.get("headers") or {}).get("Range")
        if rng:
            start = int(rng.split("=")[1].rstrip("-"))
            return _Response(206, body=body[start:])
        return _Response(200, body=body)

    def _head(url, **kwargs):
        state["calls"].append(("HEAD", url, {}))
        name = url.rsplit("2016-", 1)[-1][:-4]
        size = state.get("head_sizes", {}).get(
            name, len(state["tiles"].get(name, b"")))
        return _Response(200, headers={"Content-Length": str(size)})

    monkeypatch.setattr(requests, "get", _get)
    monkeypatch.setattr(requests, "head", _head)
    return state


def test_index_error_body_is_transient(fake_http):
    fake_http["index"] = {"error": {"code": 400, "message": "boom"}}
    strategy = INSETS.LasTileIndexStrategy()
    with pytest.raises(INSETS.TransientFetchError):
        strategy.discover(_definition(), _box_of_tile())
    fake_http["index"] = {"features": [], "error": {"code": 500}}
    with pytest.raises(INSETS.TransientFetchError):
        strategy.discover(_definition(), _box_of_tile())


def test_truncated_index_is_transient_and_empty_is_durable(fake_http):
    strategy = INSETS.LasTileIndexStrategy()
    fake_http["index"] = {"features": [{"attributes": {"name": "T1"}}],
                          "exceededTransferLimit": True}
    with pytest.raises(INSETS.TransientFetchError):
        strategy.discover(_definition(), _box_of_tile())
    fake_http["index"] = _Response(503)
    with pytest.raises(INSETS.TransientFetchError):
        strategy.discover(_definition(), _box_of_tile())
    fake_http["index"] = {"features": []}
    assert strategy.discover(_definition(), _box_of_tile()) is None


def test_out_of_coverage_makes_no_call(fake_http):
    strategy = INSETS.LasTileIndexStrategy()
    definition = _definition(coverage_bbox="10,10,11,11")
    assert strategy.discover(definition, _box_of_tile()) is None
    assert fake_http["calls"] == []


def test_cap_wording_is_exact(fake_http, tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    names = ["T%02d" % n for n in range(71)]
    fake_http["index"] = {"features": [{"attributes": {"name": n}}
                                       for n in names]}
    fake_http["head_sizes"] = {n: int(7.9e9 / 71) for n in names}
    definition = _definition(code="PITKIN1M")
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        INSETS.LasTileIndexStrategy().fetch(
            definition, _box_of_tile(), 1.0,
            str(tmp_path / "KASE_usgs3dep.tif.rung1"))
    assert str(caught.value) == (
        "PITKIN1M: KASE needs 71 tiles / 7.9 GB, cap 64 / 8.0 GB "
        "(max_tiles_per_airport / max_bytes_per_airport in PITKIN1M.elv) "
        "— SKIPPED, recorded unavailable, not no-coverage")
    assert not any(call[0] == "GET" and "tiles.test" in call[1]
                   for call in fake_http["calls"])


def test_missing_laspy_is_unavailable_never_no_coverage(tmp_path,
                                                       monkeypatch):
    monkeypatch.setattr(INSETS, "las_reader_available", lambda: False)
    with pytest.raises(INSETS.ProviderUnavailable, match="laspy missing"):
        INSETS.LasTileIndexStrategy().fetch(
            _definition(), _box_of_tile(), 1.0, str(tmp_path / "a.tif"))
    definition = _definition()
    assert INSETS.provider_required_capabilities(definition) == [
        INSETS.CAPABILITY_LAS]
    assert INSETS.run_capability_record(definition)["capabilities"] == []


def test_fetch_downloads_resumes_grids_and_records(fake_http, tmp_path,
                                                   monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    source = _write_las(tmp_path / "src.las")
    with open(source, "rb") as handle:
        body = handle.read()
    fake_http["tiles"]["T1"] = body
    fake_http["index"] = {"features": [{"attributes": {"name": "T1"}},
                                       {"attributes": {"name": "T2"}}]}
    destination = str(tmp_path / "out" / "KASE_pitkintest.tif")
    os.makedirs(os.path.dirname(destination))
    # A half-finished download from an earlier run resumes by Range.
    with open(destination + ".las0.part", "wb") as handle:
        handle.write(body[:1000])
    provenance = INSETS.LasTileIndexStrategy().fetch(
        _definition(), _box_of_tile(), 1.0, destination)
    gets = [c for c in fake_http["calls"]
            if c[0] == "GET" and "tiles.test" in c[1]]
    assert gets[0][2].get("Range") == "bytes=1000-"
    cached = os.path.join(INSETS.las_tile_cache_directory("PITKINTEST"),
                          "T1.las")
    with open(cached, "rb") as handle:
        assert handle.read() == body           # appended, byte-exact
    assert os.path.isfile(cached[:-4] + "_dtm.tif")
    assert not os.path.exists(destination + ".las0.part")
    assert provenance["provider"] == "PITKINTEST"
    assert provenance["source_ids"] == ["T1", "T2"]
    assert provenance["tiles_missing"] == ["T2"]        # listed, 404
    assert [s["source_id"] for s in provenance["sources_used"]] == ["T1"]
    assert provenance["sources_used"][0]["publication_date"] == "2016-08"
    assert provenance["valid_fraction"] >= 0.95
    assert provenance["filled_fraction"] == pytest.approx(
        108.0 / (N_CELLS * N_CELLS - 144 + 108), abs=1e-5)
    assert provenance["point_density_per_m2"] == pytest.approx(4.0, rel=1e-3)
    assert provenance["rmse_z_m"] == 0.045
    assert provenance["license_note"] == "test note"
    assert provenance["vertical_unit_source"] == "ftUS"
    assert provenance["source_crs"] == "EPSG:6428"
    assert provenance["native_resolution_m"] == 1.0
    # the inset carries the plane in METRES (NAVD88, never shifted)
    values, _transform = _read(destination)
    good = values[values != -32768.0]
    assert 7800 * FTUS - 1 < good.min() < good.max() < 7803 * FTUS + 1

    # A second fetch re-uses the cached tile and its DTM: no tile GET.
    fake_http["calls"].clear()
    INSETS.LasTileIndexStrategy().fetch(
        _definition(), _box_of_tile(), 1.0, destination + ".again")
    assert [c for c in fake_http["calls"]
            if c[0] == "GET" and c[1].endswith("T1.las")] == []


def test_every_listed_tile_missing_is_unavailable(fake_http, tmp_path,
                                                  monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    with pytest.raises(INSETS.ProviderUnavailable,
                       match="index lists 1 tiles, server has none"):
        INSETS.LasTileIndexStrategy().fetch(
            _definition(), _box_of_tile(), 1.0,
            str(tmp_path / "KASE_x.tif"))


def test_shipped_pitkin1m_definition():
    providers = INSETS.initialize_elevation_providers_dict()
    pitkin = providers["PITKIN1M"]
    assert pitkin["access_strategy"] == "las_tile_index"
    assert pitkin["enabled"] is True
    assert "requires_license_ack" not in pitkin
    assert pitkin["priority"] < providers["USGS3DEP"]["priority"]
    assert pitkin["native_resolution_m"] == 1.0
    assert "https://pitkincounty.com/478/Disclaimer" in pitkin["license_note"]
    assert "2026-09-30aw" in pitkin["license_note"]
    assert not INSETS.ACCESS_STRATEGIES["las_tile_index"].supports_wide_area
    # KASE sits inside the county box; Madrid does not.
    assert INSETS._coverage_bbox_intersects(
        pitkin, (-106.8994, 39.1893, -106.8378, 39.2532))
    assert not INSETS._coverage_bbox_intersects(
        pitkin, (-3.6, 40.4, -3.5, 40.5))
