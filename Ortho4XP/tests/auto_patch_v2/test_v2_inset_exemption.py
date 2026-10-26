"""§A.6 patch∖inset reaches the frame check (issue #1352).

An airport that is PATCHED but outside the INSET selection solves on the
base raster: no inset directory is ever created for it, and that is not a
cold frame.  Until #1352 none of the ``frame_state`` calls passed
``expects_inset``, so on a tile whose inset mode admitted none of its
airports every one of them refused with ``airport_elevation_missing`` —
and the warning blamed the internet connection.

Headless: a stand-in corpus in ``tmp_path`` (a base raster and an
airports layer, NO ``_airport_insets`` directory), the composition
stubbed after the frame decision.
"""
from __future__ import annotations

import types

import O4_Tile_Failures as FAIL
import pytest
from auto_patch_v2.airport import dem_production as DP

LAT, LON = 43, -122
#: An FAA location identifier: never admitted by the ``ICAO`` inset mode.
LID = "S21"


@pytest.fixture
def corpus(tmp_path):
    """A base raster and an airports layer for the tile — and no inset
    directory, which is what a tile whose inset mode admits none of its
    airports has on disk."""
    elevation = tmp_path / "Elevation_data" / "+40-130"
    elevation.mkdir(parents=True)
    (elevation / "N43W122.hgt").write_bytes(b"\0\1")
    osm = tmp_path / "OSM_data" / "+40-130" / "+43-122"
    osm.mkdir(parents=True)
    (osm / "+43-122_airports.osm.bz2").write_bytes(b"osm")
    return tmp_path


def _dem(corpus, icao=LID) -> DP.ProductionDem:
    d = DP.ProductionDem.__new__(DP.ProductionDem)
    d.core_hosted = True
    d.allow_degraded = False
    d.icao = icao
    d.elevation_root = str(corpus / "Elevation_data")
    d.osm_root = str(corpus / "OSM_data")
    d.xplane_root = ""
    d.provenance = {}
    d.lines = []
    d._out = d.lines.append
    d._tiles = {}
    d._required_boxes = {}
    d.declared_tiles = {(LAT, LON)}
    return d


@pytest.fixture
def baked(monkeypatch):
    """Stop each path at the bake: what is under test is the frame
    decision before it, never the composition."""
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP

    calls = []
    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer",
                        lambda *a, **k: None)
    monkeypatch.setattr(VMAP, "build_airports_dico", lambda *a, **k: {})
    monkeypatch.setattr(VMAP, "compose_tile_dem_from_disk",
                        lambda *a, **k: "composed-dem")
    monkeypatch.setattr(DP.ProductionDem, "_bake",
                        lambda self, lat, lon, dem, stem, state, **k:
                        calls.append((dem, k["how"], state)) or "baked")
    return calls


def _mode(monkeypatch, mode: str) -> None:
    """The tile cfg's inset selection (``airport_elevation_insets``)."""
    tile = types.SimpleNamespace(lat=LAT, lon=LON,
                                 airport_elevation_insets=mode)
    monkeypatch.setattr(DP.ProductionDem, "_core_tile",
                        lambda self, lat, lon: tile)


def test_frame_state_exempts_an_airport_outside_the_inset_selection(corpus):
    root, osm = str(corpus / "Elevation_data"), str(corpus / "OSM_data")
    _state, problems = DP.frame_state(root, osm, LAT, LON, LID)
    assert any("NO airport elevation insets dir" in p for p in problems)
    state, problems = DP.frame_state(root, osm, LAT, LON, LID,
                                     expects_inset=False)
    assert problems == []
    assert state["expects_inset"] is False


def test_a_composed_tile_patches_its_outside_airport_on_the_base_dem(
        corpus, baked, monkeypatch):
    _mode(monkeypatch, "ICAO")
    d = _dem(corpus)
    assert d._compose(LAT, LON) == "baked"
    ((dem, how, state),) = baked
    assert (dem, how) == ("composed-dem", "composed")
    assert state["airport_insets_present"] is False
    assert d.provenance["inset_selection"] == "mode=ICAO admitted=False"
    assert "degraded" not in d.provenance


def test_a_host_seeded_tile_patches_its_outside_airport_on_the_base_dem(
        corpus, baked, monkeypatch):
    """The tile build's own path: the worker ADOPTS the host's raster, and
    the inset mode is resolved for that tile too."""
    _mode(monkeypatch, "ICAO")
    d = _dem(corpus)
    assert d._adopt(LAT, LON, "host-dem") == "baked"
    ((dem, how, _state),) = baked
    assert (dem, how) == ("host-dem", "host-seeded")


@pytest.mark.parametrize("path", ["_compose", "_adopt"])
def test_an_admitted_airport_with_no_inset_still_refuses_as_a_cold_cache(
        corpus, baked, monkeypatch, path):
    """The exemption is the selection's, not a blanket pass: under ``All``
    the same airport needs its inset, and the refusal names a cold cache
    — build again, never "check the internet connection"."""
    _mode(monkeypatch, "All")
    d = _dem(corpus)
    args = (LAT, LON) if path == "_compose" else (LAT, LON, "host-dem")
    with pytest.raises(DP.ColdDemFrame) as caught:
        getattr(d, path)(*args)
    assert baked == []
    assert FAIL.code_for_exception(caught.value) == DP.COLD_CACHE_CODE
    entry = FAIL.CATALOGUE[DP.COLD_CACHE_CODE]
    assert "internet" not in (entry.why + FAIL.REMEDIES[entry.remedy]).lower()


def test_a_failed_download_is_named_as_one():
    assert DP.cold_frame_code({}) == DP.COLD_CACHE_CODE
    assert DP.cold_frame_code({"airport_inset_fetch_failed": True}) == \
        DP.FETCH_FAILED_CODE
    assert DP.cold_frame_code({}, tried="a recorded warm attempt") == \
        DP.FETCH_FAILED_CODE
    assert FAIL.CATALOGUE[DP.FETCH_FAILED_CODE].remedy == "network"
    exc = DP.ColdDemFrame("x")
    exc.failure_code = DP.FETCH_FAILED_CODE
    assert FAIL.code_for_exception(exc) == DP.FETCH_FAILED_CODE
