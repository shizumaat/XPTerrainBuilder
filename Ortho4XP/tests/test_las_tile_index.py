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
            if c[0] == "GET" and c[1].endswith("2016-T1.las")]
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


# ---------------------------------------------------------------------
# ROUND 2 (spec §2/§3/§4/§11, owner 30ay): surgical discovery, progress,
# fill bound, two-layer assembly
# ---------------------------------------------------------------------
def _square(west, south, size):
    return {"rings": [[[west, south], [west + size, south],
                       [west + size, south + size], [west, south + size],
                       [west, south]]]}


def test_surgical_discovery_keeps_footprint_tiles_only(fake_http):
    """A 4 x 4 grid of tile footprints; a diagonal (runway-like) boundary
    polygon: only the tiles its BUFFERED polygon touches are listed, not
    every tile its envelope touches, and the query box is the buffered
    footprint's envelope."""
    from shapely.geometry import LineString

    size = 0.01
    fake_http["index"] = {"features": [
        {"attributes": {"name": "T%d%d" % (i, j)},
         "geometry": _square(-106.90 + i * size, 39.20 + j * size, size)}
        for i in range(4) for j in range(4)]}
    boundary = LineString([(-106.895, 39.205), (-106.865, 39.235)]).buffer(
        0.0005)
    definition = _definition(footprint_buffer_m="100")
    definition[INSETS.LAS_FOOTPRINT_KEY] = INSETS._polygon_mapping(boundary)
    names = [s["source_id"] for s in INSETS.LasTileIndexStrategy().discover(
        definition, (-106.95, 39.15, -106.80, 39.30))]
    # the diagonal and its corner-touching neighbours; never the far
    # corners the envelope (all 16) would buy
    assert names == ["T00", "T01", "T10", "T11", "T12", "T21", "T22",
                     "T23", "T32", "T33"]
    url = fake_http["calls"][0][1]
    west = float(url.split("bbox=")[1].split(",")[0])
    assert west > -106.95                     # the core's envelope, not the box
    # a surgical listing that lost its geometry is no answer
    fake_http["index"] = {"features": [{"attributes": {"name": "T00"}}]}
    with pytest.raises(INSETS.TransientFetchError):
        INSETS.LasTileIndexStrategy().discover(
            definition, (-106.95, 39.15, -106.80, 39.30))


def test_surgical_cap_wording_names_the_core(fake_http, tmp_path,
                                            monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    from shapely.geometry import box as _box

    names = ["T%02d" % n for n in range(14)]
    fake_http["index"] = {"features": [
        {"attributes": {"name": n}, "geometry": _square(-106.9, 39.2, 0.1)}
        for n in names]}
    fake_http["head_sizes"] = {n: int(1.3e9 / 14) for n in names}
    definition = _definition(code="PITKIN1M", max_tiles_per_airport="12",
                             max_bytes_per_airport="1200000000")
    definition[INSETS.LAS_FOOTPRINT_KEY] = INSETS._polygon_mapping(
        _box(-106.88, 39.21, -106.86, 39.23))
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        INSETS.LasTileIndexStrategy().fetch(
            definition, _box_of_tile(), 1.0,
            str(tmp_path / "KASE_usgs3dep.tif.rung1"))
    assert str(caught.value) == (
        "PITKIN1M: KASE core needs 14 tiles / 1.3 GB, cap 12 / 1.2 GB "
        "(max_tiles_per_airport / max_bytes_per_airport in PITKIN1M.elv) "
        "— SKIPPED, recorded unavailable, not no-coverage")


def test_fill_within_the_density_bound_and_progress_is_heard(
        fake_http, tmp_path, monkeypatch):
    """§3 re-registered: ``filled_fraction <= 2 e^-lambda + 0.05`` with
    ``poisson_empty_rate`` and the density in the record; §2: a streaming
    tile prints progress and a completion line (the #136 heartbeat)."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    monkeypatch.setattr(INSETS, "LAS_PROGRESS_INTERVAL_S", 0.0)
    lines = []
    monkeypatch.setattr(INSETS.UI, "vprint",
                        lambda level, *parts: lines.append(" ".join(
                            str(p) for p in parts)))
    source = _write_las(tmp_path / "src.las")
    with open(source, "rb") as handle:
        fake_http["tiles"]["T1"] = handle.read()
    provenance = INSETS.LasTileIndexStrategy().fetch(
        _definition(), _box_of_tile(), 1.0,
        str(tmp_path / "out" / "KASE_x.tif"))
    lam = provenance["ground_density_per_m2"]
    assert provenance["poisson_empty_rate"] == pytest.approx(
        math.exp(-lam), abs=1e-6)
    assert provenance["filled_fraction"] <= 2 * math.exp(-lam) + 0.05
    assert any("[inset] KASE PITKINTEST tile 1/1 2016-T1.las" in line
               and " done (" in line for line in lines)


def _write_flat(path, box, value, size, hole=None):
    from osgeo import osr as _osr

    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(str(path), size, size, 1, gdal.GDT_Float32)
    (west, south, east, north) = box
    dataset.SetGeoTransform((west, (east - west) / size, 0.0, north, 0.0,
                             -(north - south) / size))
    srs = _osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    values = numpy.full((size, size), value, dtype=numpy.float32)
    if hole is not None:
        values[hole] = -32768.0
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values)
    dataset = None


def test_two_layer_assembly_feathers_the_core_edge(tmp_path):
    """A flat probe: core 101 m, surround 100 m.  Inside the region the
    core, outside the surround, a 60 m ramp inside the region's edge
    with no step over 0.05 m per cell, a core hole deep inside left
    NoData (§9), and the seam's median offset recorded."""
    from shapely.geometry import box as _box

    box = (-106.90, 39.20, -106.88, 39.22)     # ~1.7 x 2.2 km
    size = 800
    core = tmp_path / "core.tif"
    surround = tmp_path / "surround.tif"
    hole = (slice(395, 405), slice(395, 405))
    _write_flat(core, box, 101.0, size, hole=hole)
    _write_flat(surround, box, 100.0, size)
    boundary = _box(-106.895, 39.205, -106.885, 39.215)
    seam = INSETS.assemble_two_layer_inset(
        str(core), str(surround), str(tmp_path / "out.tif"), boundary,
        0.0, 60.0)
    values, transform = _read(tmp_path / "out.tif")
    assert seam["seam_median_offset_m"] == pytest.approx(1.0, abs=1e-3)
    assert seam["core_holes_left_nodata"] == 100
    assert values[400, 400] == INSETS.LAS_DTM_NODATA     # hole stays NoData
    assert values[5, 5] == pytest.approx(100.0)          # surround outside
    row = 300                                            # a transect W -> E
    transect = values[row, :]
    assert numpy.nanmax(numpy.abs(numpy.diff(transect))) <= 0.05
    assert transect.max() == pytest.approx(101.0, abs=1e-4)
    assert INSETS.feather_weight(numpy.array([-1.0, 0.0, 30.0, 60.0, 90.0]),
                                 60.0).tolist() == [0.0, 0.0, 0.5, 1.0, 1.0]


def test_wkt_epsg_is_read_without_gdal():
    """The header CRS is judged even when osr cannot reach a PROJ
    database: the code is read out of the WKT text (WKT1 and WKT2)."""
    wkt1 = pyproj.CRS.from_epsg(6428).to_wkt(version="WKT1_GDAL")
    wkt2 = pyproj.CRS.from_epsg(6428).to_wkt()
    assert INSETS._wkt_horizontal_epsg(wkt1) == 6428
    assert INSETS._wkt_horizontal_epsg(wkt2) == 6428
    compound = pyproj.CRS.from_user_input("EPSG:6428+6360").to_wkt(
        version="WKT1_GDAL")
    assert INSETS._wkt_horizontal_epsg(compound) == 6428


# ---------------------------------------------------------------------
# #153: the USGS Lidar Point Cloud rung -- LAZ tiles behind a TNM
# listing, each tile's CRS and height unit read from its own header.
# ---------------------------------------------------------------------
def _lpc_definition(**overrides):
    definition = _definition(
        code="USGSLPCTEST",
        index_format="tnm",
        index_url_template="https://tnm.test/p?bbox={west},{south},"
                           "{east},{north}",
        source_crs="from_header",
        vertical_unit="from_header",
        point_compression="laz",
        point_formats="0,1,2,3,6,7,8",
        publication_date="",
    )
    definition.pop("tile_url_template", None)
    definition.update(overrides)
    return definition


requires_laz = pytest.mark.skipif(not INSETS.laz_reader_available(),
                                  reason="no LAZ backend (lazrs)")


@requires_laz
def test_laz_tile_feet_without_vertical_crs_grids_in_metres(tmp_path):
    """A State Plane foot CRS and no vertical CRS: heights are in that
    foot (the raster rule) and come out in metres."""
    laz = _write_las(tmp_path / "t.laz", hole=False)
    with open(laz, "rb") as handle:
        assert handle.read(4) == b"LASF"
    dtm = tmp_path / "t_dtm.tif"
    record = INSETS.grid_las_tile(laz, str(dtm), _lpc_definition())
    values, transform = _read(dtm)
    assert values.shape == (N_CELLS, N_CELLS)
    cx = (I0 + 10 + 0.5) * CELL_FT
    cy = (J0 + N_CELLS - 10 - 0.5) * CELL_FT
    assert abs(values[10, 10] - _plane_ft(cx, cy) * FTUS) < 0.01
    assert record["tile_crs"] == "EPSG:6428"
    assert record["tile_vertical_unit_rule"] == "horizontal-crs"
    assert record["source_crs"] == "from_header"
    assert INSETS._las_dtm_record_if_current(
        str(dtm), _lpc_definition()) is not None
    dataset = gdal.Open(str(dtm))
    assert osr.SpatialReference(dataset.GetProjection()).GetAuthorityCode(
        None) == "6428"
    dataset = None


@requires_laz
def test_laz_tile_compound_crs_takes_the_vertical_unit(tmp_path):
    """NAD83(2011) CO Central ftUS + NAVD88 height (ftUS): the vertical
    CRS decides the height unit."""
    las = tmp_path / "c.laz"
    _write_las(las, hole=False)
    # rewrite with a compound CRS
    data = laspy.read(str(las))
    header = laspy.LasHeader(point_format=6, version="1.4")
    header.scales = data.header.scales
    header.offsets = data.header.offsets
    header.add_crs(pyproj.CRS("EPSG:6428+6360"))
    out = laspy.LasData(header)
    out.points = data.points
    out.write(str(tmp_path / "compound.laz"))
    record = INSETS.grid_las_tile(str(tmp_path / "compound.laz"),
                                  str(tmp_path / "c_dtm.tif"),
                                  _lpc_definition())
    assert record["tile_vertical_unit_rule"] == "vertical-crs"
    values, _transform = _read(tmp_path / "c_dtm.tif")
    cx = (I0 + 10 + 0.5) * CELL_FT
    cy = (J0 + N_CELLS - 10 - 0.5) * CELL_FT
    assert abs(values[10, 10] - _plane_ft(cx, cy) * FTUS) < 0.01


@requires_laz
def test_laz_validation_and_the_backend_door(tmp_path, monkeypatch):
    laz = _write_las(tmp_path / "t.laz")
    summary = INSETS.validate_las_tile(laz, _lpc_definition())
    assert summary["crs"] == "EPSG:6428"
    # PITKIN1M's contract still refuses LAZ outright
    with pytest.raises(INSETS.ProviderUnavailable,
                       match="LAZ needs a backend"):
        INSETS.validate_las_tile(laz, _definition())
    monkeypatch.setattr(INSETS, "laz_reader_available", lambda: False)
    with pytest.raises(INSETS.ProviderUnavailable, match="lazrs missing"):
        INSETS.validate_las_tile(laz, _lpc_definition())


def test_missing_laz_backend_is_unavailable_never_no_coverage(
        tmp_path, monkeypatch):
    monkeypatch.setattr(INSETS, "laz_reader_available", lambda: False)
    with pytest.raises(INSETS.ProviderUnavailable,
                       match=r"LAZ backend \(lazrs\) missing"):
        INSETS.LasTileIndexStrategy().fetch(
            _lpc_definition(), _box_of_tile(), 1.0, str(tmp_path / "a.tif"))
    definition = _lpc_definition()
    assert INSETS.provider_required_capabilities(definition) == [
        INSETS.CAPABILITY_LAS, INSETS.CAPABILITY_LAZ]
    assert INSETS.run_capability_record(definition)["capabilities"] == [
        INSETS.CAPABILITY_LAS]


def _tnm_item(name, box, date, size=1000):
    return {"downloadURL": "https://rockyweb.test/LPC/%s.laz" % name,
            "title": "USGS Lidar Point Cloud %s" % name,
            "sourceId": "sid-" + name, "publicationDate": date,
            "sizeInBytes": size,
            "boundingBox": {"minX": box[0], "minY": box[1],
                            "maxX": box[2], "maxY": box[3]}}


@pytest.fixture
def fake_tnm_lpc(monkeypatch):
    import requests

    state = {"items": [], "tiles": {}, "calls": [], "short": set()}

    def _get(url, **kwargs):
        state["calls"].append(("GET", url))
        if url.startswith("https://tnm.test/"):
            offset = int(url.rsplit("&offset=", 1)[1]) if "&offset=" in \
                url else 0
            return _Response(200, {"total": len(state["items"]),
                                   "items": state["items"][offset:
                                                           offset + 50]})
        name = url.rsplit("/", 1)[-1][:-4]
        body = state["tiles"].get(name)
        if body is None:
            return _Response(404)
        length = len(body) + (100 if name in state["short"] else 0)
        return _Response(200, body=body,
                         headers={"Content-Length": str(length)})

    def _head(url, **kwargs):
        state["calls"].append(("HEAD", url))
        return _Response(200, headers={"Content-Length": "1"})

    monkeypatch.setattr(requests, "get", _get)
    monkeypatch.setattr(requests, "head", _head)
    return state


def test_tnm_index_cuts_to_the_core_and_orders_oldest_first(fake_tnm_lpc):
    from shapely.geometry import box as shapely_box

    tile = _box_of_tile()
    far = (tile[0] + 0.5, tile[1], tile[2] + 0.5, tile[3])
    fake_tnm_lpc["items"] = (
        [_tnm_item("NEW_%02d" % n, tile, "2022-05-01") for n in range(30)]
        + [_tnm_item("OLD_%02d" % n, tile, "2015-05-01") for n in range(30)]
        + [_tnm_item("FAR", far, "2023-01-01")])
    footprint = INSETS._polygon_mapping(shapely_box(*tile))
    definition = _lpc_definition(**{INSETS.LAS_FOOTPRINT_KEY: footprint})
    strategy = INSETS.LasTileIndexStrategy()
    listing = strategy.discover(definition, tile)
    names = [source["source_id"] for source in listing]
    assert "FAR" not in names                         # outside the core
    assert names[:30] == ["OLD_%02d" % n for n in range(30)]
    assert names[30:] == ["NEW_%02d" % n for n in range(30)]
    assert listing[0]["size_bytes"] == 1000
    assert listing[0]["download_url"].endswith("OLD_00.laz")
    assert strategy.last_listing == listing
    # two pages were read (61 items)
    assert sum(1 for c in fake_tnm_lpc["calls"] if "tnm.test" in c[1]) == 2


@requires_laz
def test_lpc_fetch_end_to_end(fake_tnm_lpc, tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    laz = _write_las(tmp_path / "src.laz")
    with open(laz, "rb") as handle:
        body = handle.read()
    tile = _box_of_tile()
    fake_tnm_lpc["items"] = [_tnm_item("USGS_LPC_T1", tile, "2022-05-01",
                                       size=len(body))]
    fake_tnm_lpc["tiles"]["USGS_LPC_T1"] = body
    destination = str(tmp_path / "out" / "KGEG_usgs3dep.tif.rung3")
    os.makedirs(os.path.dirname(destination))
    provenance = INSETS.LasTileIndexStrategy().fetch(
        _lpc_definition(), tile, 1.0, destination)
    cached = os.path.join(INSETS.las_tile_cache_directory("USGSLPCTEST"),
                          "USGS_LPC_T1.laz")
    assert os.path.isfile(cached)
    assert os.path.isfile(cached[:-4] + "_dtm.tif")
    assert not any(call[0] == "HEAD" for call in fake_tnm_lpc["calls"])
    assert provenance["source_crs"] == ["EPSG:6428"]
    assert provenance["vertical_unit_source"] == [
        "US survey foot (horizontal-crs)"]
    assert provenance["point_density_per_m2"] == pytest.approx(4.0,
                                                               rel=1e-3)
    values, _transform = _read(destination)
    good = values[values != -32768.0]
    assert 7800 * FTUS - 1 < good.min() < good.max() < 7803 * FTUS + 1


@requires_laz
def test_short_laz_download_is_transient(fake_tnm_lpc, tmp_path,
                                         monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    laz = _write_las(tmp_path / "src.laz")
    with open(laz, "rb") as handle:
        body = handle.read()
    tile = _box_of_tile()
    fake_tnm_lpc["items"] = [_tnm_item("T1", tile, "2022-05-01")]
    fake_tnm_lpc["tiles"]["T1"] = body
    fake_tnm_lpc["short"].add("T1")
    with pytest.raises(INSETS.TransientFetchError, match="stopped at"):
        INSETS.LasTileIndexStrategy().fetch(
            _lpc_definition(), tile, 1.0, str(tmp_path / "a.tif"))
    assert not os.path.isfile(os.path.join(
        INSETS.las_tile_cache_directory("USGSLPCTEST"), "T1.laz"))
