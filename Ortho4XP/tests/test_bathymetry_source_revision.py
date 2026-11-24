"""#2265: a failed bathymetry fetch is transient; a dead source's recorded
negatives heal once.  Headless: tmp_path, stubbed fetches, no network."""
import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

osgeo = pytest.importorskip("osgeo")
from osgeo import gdal, osr  # noqa: E402

import numpy  # noqa: E402
from shapely.geometry import MultiLineString  # noqa: E402

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_Bathymetry_Band as BATHYBAND  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Step_Reuse as REUSE  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from elevation_access import warp as WARP  # noqa: E402
from elevation_access.base import TransientFetchError  # noqa: E402
from elevation_access.failures import warp_failure_is_transient  # noqa: E402

CODE = "REVBATHY"
COASTLINE = MultiLineString([[(0.15, 0.05), (0.15, 0.35)]])
FOUR_CELLS = 4


def _definition(revision=1, resolution=450.0):
    out = {"code": CODE, "role": "bathymetry", "enabled": True,
           "priority": 10.0, "native_resolution_m": resolution}
    if revision:
        out["source_revision"] = str(revision)
    return out


def _tile(masks="True"):
    return SimpleNamespace(lat=0, lon=0, bathymetry_band_km=0.1,
                           masks_use_DEM_too=masks)


def _stem(column, row):
    path = FNAMES.bathymetry_band_cell(
        0, 0, column, row, CODE, BATHYBAND.BATHYMETRY_CELL_RESOLUTION_M)
    return os.path.splitext(os.path.basename(path))[0]


def _write_cell(path, box):
    (west, south, east, north) = box
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, 4, 4, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((west, (east - west) / 4, 0, north, 0,
                             (south - north) / 4))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(numpy.full((4, 4), -6.0, dtype=numpy.float32))
    dataset = None


def _fetch_ok(calls):
    def fetch(definition, box, resolution, path):
        calls.append(box)
        _write_cell(path, box)
        return {"provider": definition["code"]}
    return fetch


def _stamp_path():
    return FNAMES.bathymetry_band_index(0, 0)


def _stamp():
    with open(_stamp_path(), encoding="utf-8") as handle:
        return json.load(handle)


def _write_dead_link_stamp():
    os.makedirs(os.path.dirname(_stamp_path()), exist_ok=True)
    cells = {_stem(1, row): "no_coverage" for row in range(FOUR_CELLS)}
    key = "[false, true, 0.1]"
    with open(_stamp_path(), "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"provider": CODE, "cells": cells, "checked": "2026-11-23",
                   "gating": [False, True, 0.1],
                   "gatings": {key: {"provider": CODE, "reached": [CODE],
                                     "mosaic": []}}}, handle)


@pytest.fixture(autouse=True)
def _environment(monkeypatch, tmp_path):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(INSETS, "select_bathymetry_definitions",
                        lambda lat, lon: [_definition()])
    monkeypatch.setattr(BATHYBAND, "_band_geometry",
                        lambda tile: (COASTLINE, None))
    monkeypatch.setattr(UI, "red_flag", False)
    BATHYBAND._prefetch_futures.clear()
    yield
    BATHYBAND._prefetch_futures.clear()


def _run():
    return BATHYBAND.ensure_bathymetry_band(
        _tile(), fine_nearshore_only=False, intertidal_ok=True)


def test_a_404_warp_raises_only_inside_the_band_scope(monkeypatch, tmp_path):
    def dead(*args, **kwargs):
        raise RuntimeError("HTTP response code: 404")
    monkeypatch.setattr(WARP.gdal, "Warp", dead)
    box = (0.1, 0.0, 0.2, 0.1)
    out = str(tmp_path / "cell.tif")
    assert WARP.warp_vsicurl_sources_to_geotiff(
        ["/vsicurl/x.tif"], box, 10.0, out) is False
    with warp_failure_is_transient():
        with pytest.raises(TransientFetchError):
            WARP.warp_vsicurl_sources_to_geotiff(
                ["/vsicurl/x.tif"], box, 10.0, out)


def test_failed_fetch_records_no_negative_and_retries(monkeypatch):
    def failing(*args):
        raise TransientFetchError("HTTP response code: 404")
    monkeypatch.setattr(INSETS, "fetch_inset", failing)
    assert _run() is None
    stamp = _stamp()
    assert "no_coverage" not in stamp["cells"].values()
    assert stamp["refetch"] == [CODE]
    assert not BATHYBAND.is_cached(_tile(), False, True)
    calls = []
    monkeypatch.setattr(INSETS, "fetch_inset", _fetch_ok(calls))
    assert _run() is not None
    assert len(calls) == FOUR_CELLS
    assert "refetch" not in _stamp()


def test_a_real_empty_answer_is_durable(monkeypatch):
    calls = []

    def empty(definition, box, resolution, path):
        calls.append(box)
        return None
    monkeypatch.setattr(INSETS, "fetch_inset", empty)
    assert _run() is None
    assert set(_stamp()["cells"].values()) == {"no_coverage"}
    assert _stamp()["source_revisions"] == {CODE: 1}
    count = len(calls)
    assert _run() is None
    assert len(calls) == count
    assert BATHYBAND.is_cached(_tile(), False, True)


def test_old_negatives_heal_once(monkeypatch):
    _write_dead_link_stamp()
    assert not BATHYBAND.is_cached(_tile(), False, True)
    calls = []
    monkeypatch.setattr(INSETS, "fetch_inset", _fetch_ok(calls))
    assert _run() is not None
    assert len(calls) == FOUR_CELLS
    assert set(_stamp()["cells"].values()) == {"ok"}
    assert _run() is not None
    assert len(calls) == FOUR_CELLS


def test_a_provider_without_a_revision_keeps_its_negatives(monkeypatch):
    monkeypatch.setattr(INSETS, "select_bathymetry_definitions",
                        lambda lat, lon: [_definition(revision=0)])
    _write_dead_link_stamp()
    calls = []
    monkeypatch.setattr(INSETS, "fetch_inset", _fetch_ok(calls))
    assert _run() is None
    assert calls == []


def test_masks_key_sees_only_a_revised_provider_the_masks_walk(monkeypatch):
    _write_dead_link_stamp()
    # Auto admits fine sources only: a coarse revised source changes nothing.
    assert BATHYBAND.masks_source_state(_tile("auto")) is None
    assert BATHYBAND.masks_source_state(_tile("True")) == "pending"
    monkeypatch.setattr(INSETS, "fetch_inset", _fetch_ok([]))
    assert _run() is not None
    state = BATHYBAND.masks_source_state(_tile("True"))
    assert state not in (None, "pending")


def test_pending_band_makes_the_masks_step_stale(monkeypatch):
    monkeypatch.setattr(REUSE, "_read", lambda tile: {
        "committed": {"masks": {"inputs": {"band_source": "pending"}}}})
    monkeypatch.setattr(REUSE, "_previous_digest", lambda doc, step: "")
    monkeypatch.setattr(REUSE, "live_settings", lambda tile, step: {})
    monkeypatch.setattr(REUSE, "code_identity", lambda step: {})
    monkeypatch.setattr(BATHYBAND, "masks_source_state", lambda t: "pending")
    assert "band" in REUSE.stale_reason(_tile(), "masks")


# ---------------------------------------------------------------------
# wcs_subset (EMODnet)
# ---------------------------------------------------------------------
def _wcs_definition():
    return {"code": "SUBSETBATHY", "role": "bathymetry",
            "access_strategy": "wcs_subset", "native_resolution_m": 115,
            "wcs_service_url": "https://wcs.test/wcs", "wcs_version": "2.0.1",
            "wcs_coverage": "c__mean", "wcs_lon_axis": "Long",
            "wcs_lat_axis": "Lat", "coverage_bbox": "-36,15,43,90",
            "value_floor_m": -11100.0}


def test_wcs_subset_names_each_axis_by_its_label():
    from elevation_access.strategies.wcs_subset import request_url
    url = request_url(_wcs_definition(), (-9.5, 38.5, -9.4, 38.6))
    assert "subset=Long(-9.502" in url and "subset=Lat(38.497" in url


@pytest.mark.parametrize("status,body", [(404, b"<xml/>"), (200, b"<xml/>")])
def test_wcs_subset_refusal_is_transient(monkeypatch, tmp_path, status, body):
    import requests
    from elevation_access.strategies.wcs_subset import WcsSubsetStrategy
    monkeypatch.setattr(requests, "get", lambda *a, **k: SimpleNamespace(
        status_code=status, content=body))
    with pytest.raises(TransientFetchError):
        WcsSubsetStrategy().fetch(_wcs_definition(), (-9.5, 38.5, -9.4, 38.6),
                                  10.0, str(tmp_path / "cell.tif"))
    assert os.listdir(tmp_path) == []
