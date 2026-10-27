"""#1466: a provider reaches a box when its declared box does AND its real
footprint (a cached catalogue, else a probed cell map) overlaps it.
Synthetic footprints, a fake strategy registry, no network."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import O4_Elevation_Level as RINGS  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
from elevation_access import footprints as FP  # noqa: E402
from elevation_access import registry as REGISTRY  # noqa: E402
from elevation_access.base import TransientFetchError  # noqa: E402
from elevation_access.strategies import stac as STAC  # noqa: E402
from elevation_access.strategies import wcs as WCS  # noqa: E402

LAT, LON = 47, 7
TILE = (LON, LAT, LON + 1, LAT + 1)


@pytest.fixture(autouse=True)
def _elevation_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "Elevation"))


def _cell(column, row):
    return FP.tile_cell_boxes(LAT, LON)[(column, row)]


def _definition(code="PROV", strategy=None, box=TILE):
    definition = {"code": code, "coverage_bbox": box}
    if strategy:
        definition["access_strategy"] = strategy
    return definition


def _write_map(code, covered):
    path = FP.footprint_path(code, LAT, LON)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"covered": covered}, handle)


def test_the_cell_is_the_ring_cell():
    assert FP.FOOTPRINT_CELL_DEGREES == RINGS.COASTLINE_CELL_DEGREES
    assert _cell(3, 4) == RINGS.approach_ring_cell_box(LAT, LON, 3, 4)


def test_an_unknown_footprint_is_the_box_alone():
    definition = _definition()
    assert FP.footprint_answer(definition, _cell(5, 5)) is None
    assert FP.covers_box(definition, _cell(5, 5))
    assert not FP.covers_box(definition, (20, 20, 20.1, 20.1))


def test_a_probed_map_answers_per_cell_and_edges_do_not_count():
    definition = _definition()
    _write_map("PROV", [[2, 2]])
    assert FP.covers_box(definition, _cell(2, 2))
    # the neighbour shares only an edge with the covered cell
    assert not FP.covers_box(definition, _cell(3, 2))
    # a box straddling the covered cell reaches it
    (west, south, east, north) = _cell(2, 2)
    assert FP.covers_box(definition, (west - 0.05, south, west + 0.01, north))


def test_a_box_over_an_unprobed_tile_stays_unknown():
    definition = _definition(box=(6, 46, 9, 49))
    _write_map("PROV", [])
    assert FP.footprint_answer(definition, _cell(5, 5)) is False
    assert FP.footprint_answer(definition, (7.9, 47.5, 8.1, 47.6)) is None


class _CatalogueStrategy:
    boxes = None

    def cached_source_boxes(self, definition):
        return self.boxes


class _ProbingStrategy:
    answers = None
    calls = 0

    def probe_cell_coverage(self, definition, cell_boxes):
        type(self).calls += 1
        if self.answers is TransientFetchError:
            raise TransientFetchError("down")
        return [self.answers(box) for box in cell_boxes]


@pytest.fixture
def strategies(monkeypatch):
    registry = dict(REGISTRY.ACCESS_STRATEGIES)
    registry["test_catalogue"] = _CatalogueStrategy
    registry["test_probe"] = _ProbingStrategy
    monkeypatch.setattr(REGISTRY, "ACCESS_STRATEGIES", registry)
    monkeypatch.setattr(_CatalogueStrategy, "boxes", None)
    monkeypatch.setattr(_ProbingStrategy, "calls", 0)


def test_a_cached_catalogue_is_the_footprint(strategies, monkeypatch):
    definition = _definition(strategy="test_catalogue")
    assert FP.footprint_answer(definition, _cell(0, 0)) is None
    monkeypatch.setattr(_CatalogueStrategy, "boxes",
                        [[7.0, 47.0, 7.05, 47.05]])
    assert FP.covers_box(definition, _cell(0, 0))
    assert not FP.covers_box(definition, _cell(9, 9))


def test_the_probe_writes_a_map_once_and_refresh_asks_again(
        strategies, monkeypatch):
    definition = _definition(strategy="test_probe")
    monkeypatch.setattr(_ProbingStrategy, "answers",
                        staticmethod(lambda box: box[0] < LON + 0.5))
    assert FP.ensure_tile_footprints([definition], LAT, LON) == ["PROV"]
    assert FP.covers_box(definition, _cell(4, 7))
    assert not FP.covers_box(definition, _cell(5, 7))
    assert FP.ensure_tile_footprints([definition], LAT, LON) == []
    assert _ProbingStrategy.calls == 1
    assert FP.ensure_tile_footprints([definition], LAT, LON,
                                     refresh=True) == ["PROV"]


def test_only_cells_inside_the_box_are_probed(strategies, monkeypatch):
    asked = []
    definition = _definition(strategy="test_probe",
                             box=(7.0, 47.0, 7.25, 47.15))
    monkeypatch.setattr(_ProbingStrategy, "answers",
                        staticmethod(lambda box: asked.append(box) or True))
    FP.ensure_tile_footprints([definition], LAT, LON)
    # the 0.1-degree cells reaching the box: columns 0-2 x rows 0-1
    assert len(asked) == 3 * 2


def test_a_transient_probe_writes_nothing(strategies, monkeypatch):
    definition = _definition(strategy="test_probe")
    monkeypatch.setattr(_ProbingStrategy, "answers", TransientFetchError)
    assert FP.ensure_tile_footprints([definition], LAT, LON) == []
    assert not os.path.exists(FP.footprint_path("PROV", LAT, LON))
    assert FP.covers_box(definition, _cell(5, 5))


def test_forget_drops_the_tile_maps():
    _write_map("PROV", [[1, 1]])
    FP.forget_tile_footprints(LAT, LON)
    assert not os.path.exists(FP.footprint_path("PROV", LAT, LON))


def test_wcs_cells_holding_data_reject_nodata_and_a_constant_fill(tmp_path):
    gdal = pytest.importorskip("osgeo.gdal")

    pixels = 40
    values = numpy.full((pixels, pixels), -32768.0, dtype="float32")
    # western half real (a ramp), south-east a constant 0 fill
    values[:, :20] = 400.0 + numpy.arange(pixels * 20).reshape(pixels, 20)
    values[20:, 20:] = 0.0
    path = str(tmp_path / "probe.tif")
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, pixels, pixels, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((7.0, 0.01, 0.0, 47.4, 0.0, -0.01))
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values)
    dataset = None
    boxes = [(7.0, 47.0, 7.1, 47.1),   # real data
             (7.3, 47.0, 7.4, 47.1),   # constant 0
             (7.3, 47.3, 7.4, 47.4)]   # nodata
    assert WCS._cells_holding_data(path, boxes) == [True, False, False]


class _Response:
    def __init__(self, status, features):
        self.status_code = status
        self._features = features

    def json(self):
        return {"features": self._features}


def test_stac_probe_is_one_limit_one_search_per_cell(monkeypatch):
    import requests

    bodies = []

    def _post(url, json=None, timeout=None):
        bodies.append(json)
        hit = json["bbox"][0] < LON + 0.5
        return _Response(200, [{"id": "x"}] if hit else [])

    monkeypatch.setattr(requests, "post", _post)
    definition = {"code": "STACPROBE", "discovery_url_template": "https://x/s",
                  "collections": "c"}
    strategy = STAC.StacCloudOptimizedGeoTiffStrategy()
    answers = strategy.probe_cell_coverage(
        definition, [_cell(1, 1), _cell(8, 1)])
    assert answers == [True, False]
    assert all(body["limit"] == 1 for body in bodies)

    monkeypatch.setattr(requests, "post",
                        lambda url, json=None, timeout=None: _Response(503, []))
    with pytest.raises(TransientFetchError):
        strategy.probe_cell_coverage(definition, [_cell(1, 1)])
