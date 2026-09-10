"""A COLD production DEM frame is WARMED by the production host (the app's
driver, ``core_hosted=True``) and REFUSED by the harness (RULINGS
2026-09-10f).  Precedent: SPJC spans S13W078 + S12W078; the app's build
of 1.0.302 refused the cold neighbour tile instead of fetching its
airports layer and baking its insets."""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import dem_production as DP


class _Frame:
    origin = (-12.5, -77.5)


def _dem(core_hosted: bool, allow_degraded: bool = False) -> DP.ProductionDem:
    d = DP.ProductionDem.__new__(DP.ProductionDem)
    d.core_hosted = core_hosted
    d.allow_degraded = allow_degraded
    d.provenance = {}
    d._warm_notes = {}
    d._out = lambda line: None
    d._tiles = {}
    return d


def _cold_then_warm(monkeypatch, calls):
    cold = ({"tile_stem": "S12W078", "base_raster_present": True,
             "airports_layer_present": False, "airport_insets_present": False},
            ["NO cached airports OSM layer", "NO airport elevation insets dir"])
    warm = (dict(cold[0], airports_layer_present=True, airport_insets_present=True), [])
    seq = [cold, warm]

    def fake_state(*a, **k):
        return seq.pop(0) if len(seq) > 1 else seq[0]
    monkeypatch.setattr(DP, "frame_state", fake_state)
    def fake_warm(self, lat, lon, state):
        calls.append((lat, lon))
        raise RuntimeError("warmed-stop")   # composition after the warm is not under test
    monkeypatch.setattr(DP.ProductionDem, "_warm_tile", fake_warm)


def test_production_host_warms_the_cold_neighbour_tile(monkeypatch):
    calls: list = []
    _cold_then_warm(monkeypatch, calls)
    d = _dem(core_hosted=True)
    d.icao, d.elevation_root, d.osm_root = "SPJC", "e", "o"
    with pytest.raises(RuntimeError, match="warmed-stop"):
        d._compose(-12, -78)
    assert calls == [(-12, -78)]


def test_harness_still_refuses_a_cold_frame(monkeypatch):
    calls: list = []
    _cold_then_warm(monkeypatch, calls)
    d = _dem(core_hosted=False)
    d.icao, d.elevation_root, d.osm_root = "SPJC", "e", "o"
    with pytest.raises(DP.ColdDemFrame, match="COLD"):
        d._compose(-12, -78)
    assert calls == []


def test_may_warm_needs_the_base_raster_and_no_degraded_flag():
    d = _dem(core_hosted=True)
    assert d._may_warm({"base_raster_present": True})
    assert not d._may_warm({"base_raster_present": False})
    d.allow_degraded = True
    assert not d._may_warm({"base_raster_present": True})
    d = _dem(core_hosted=False)
    assert not d._may_warm({"base_raster_present": True})


def test_a_failed_warm_names_itself_in_the_refusal(monkeypatch):
    cold = ({"tile_stem": "S12W078", "base_raster_present": True,
             "airports_layer_present": False, "airport_insets_present": True},
            ["NO cached airports OSM layer"])
    monkeypatch.setattr(DP, "frame_state", lambda *a, **k: cold)

    def fake_warm(self, lat, lon, state):
        self._warm_notes[state["tile_stem"]] = "warmed airports_layer_present: airports layer NOT written"
    monkeypatch.setattr(DP.ProductionDem, "_warm_tile", fake_warm)
    d = _dem(core_hosted=True)
    d.icao, d.elevation_root, d.osm_root = "SPJC", "e", "o"
    with pytest.raises(DP.ColdDemFrame, match="TRIED to warm"):
        d._compose(-12, -78)
