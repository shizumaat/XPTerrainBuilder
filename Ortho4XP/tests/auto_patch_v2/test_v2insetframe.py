"""THE PER-AIRPORT INSET FRAME CHECK (session ruling 2026-09-17 (3)).

``frame_state`` used to test only ``os.path.isdir`` on the tile's
``_airport_insets`` directory, and it took ``icao`` without ever using it
for the inset.  So an inset MISSING for the airport being built, or one
cut for a box that no longer contains what the airport needs, read as a
warm frame: the build then graded on the base surface where the inset
should have been, or RE-CUT the inset mid-measurement.

The rule is THE RE-CUT RULE: required today not contained in the box
REQUESTED at cut time.  Not the delivered box -- judging that marks 453
of the corpus's 565 rasters stale, every battery airport among them, for
shortfalls under a metre (measured, ``tools/inset_coverage_census.py``).

Everything here runs on a tmp corpus.
"""
from __future__ import annotations

import json
import os

import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
from auto_patch_v2.airport import dem_production as DP

LAT, LON = 60, -136
STEM, BLOCK = "N60W136", "+60-140"
ICAO = "CYXY"
#: The box this airport needs today, and one that fits inside it.
REQUIRED = (-135.10, 60.65, -135.00, 60.76)
CONTAINED = (-135.06, 60.69, -135.04, 60.72)


def _corpus(tmp_path, monkeypatch, *, requested_box=REQUIRED,
            write_raster=True, index_record=True, manifest=True):
    """A tmp Elevation_data/OSM_data pair with one tile's inset cache."""
    elevation = tmp_path / "Elevation_data"
    osm = tmp_path / "OSM_data"
    block = elevation / BLOCK
    insets = block / f"{STEM}_airport_insets"
    insets.mkdir(parents=True)
    (block / f"{STEM}.hgt").write_bytes(b"\0" * 8)
    layer = osm / BLOCK / "+60-136"
    layer.mkdir(parents=True)
    (layer / "+60-136_airports.osm.bz2").write_bytes(b"\0")
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(elevation))
    if write_raster:
        (insets / f"{ICAO}_hrdem.tif").write_bytes(b"not-a-real-geotiff")
    if manifest and write_raster:
        (insets / f"{ICAO}_hrdem.json").write_text(json.dumps(
            {"provider": "HRDEM",
             "bounding_box_wgs84": list(requested_box)}))
    if index_record:
        (insets / "index.json").write_text(json.dumps(
            {ICAO: {"HRDEM": "ok", "checked": "2026-09-17"}}))
    return str(elevation), str(osm)


def _state(tmp_path, monkeypatch, required_box=REQUIRED, **kwargs):
    (elevation, osm) = _corpus(tmp_path, monkeypatch, **kwargs)
    return DP.frame_state(elevation, osm, LAT, LON, ICAO, required_box)


# =====================================================================
# What frame_state now sees
# =====================================================================
def test_a_contained_inset_is_not_a_problem(tmp_path, monkeypatch):
    (state, problems) = _state(tmp_path, monkeypatch, CONTAINED)
    assert problems == []
    assert "airport_inset_problem_kind" not in state
    assert state["airport_inset_required_box"] == list(CONTAINED)


def test_an_inset_cut_for_a_smaller_box_is_STALE(tmp_path, monkeypatch):
    bigger = (REQUIRED[0] - 0.02, REQUIRED[1], REQUIRED[2], REQUIRED[3])
    (state, problems) = _state(tmp_path, monkeypatch, bigger)
    assert state["airport_inset_problem_kind"] == "stale"
    assert len(problems) == 1
    # It names the inset, BOTH boxes and the scope that fixes it.
    assert "STALE airport elevation inset" in problems[0]
    assert f"{ICAO}_hrdem.tif" in problems[0]
    assert "-135.100000" in problems[0]          # what it was cut for
    assert "%.6f" % bigger[0] in problems[0]     # what is required now
    assert "--refresh-data dem" in problems[0]


def test_a_missing_inset_inside_a_present_directory_is_now_SEEN(
    tmp_path, monkeypatch
):
    """THE ORIGINAL GAP: the directory is there, the airport's raster is
    not, and nothing has ever asked its provider chain."""
    (state, problems) = _state(tmp_path, monkeypatch, write_raster=False,
                               index_record=False)
    assert state["airport_inset_problem_kind"] == "missing"
    assert len(problems) == 1
    assert f"NO airport elevation inset for {ICAO}" in problems[0]
    assert "--refresh-data dem" in problems[0]


def test_a_recorded_no_coverage_is_a_LAWFUL_absence(tmp_path, monkeypatch):
    """An airport every provider answered ``no-coverage`` for has no
    raster and must NOT be a cold frame -- that negative IS the cache,
    and refusing on it would refuse forever."""
    (state, problems) = _state(tmp_path, monkeypatch, write_raster=False,
                               index_record=True)
    assert problems == []


def test_an_unjudgeable_manifest_is_REUSABLE(tmp_path, monkeypatch):
    bigger = (REQUIRED[0] - 0.02, REQUIRED[1], REQUIRED[2], REQUIRED[3])
    (state, problems) = _state(tmp_path, monkeypatch, bigger, manifest=False)
    assert problems == []


def test_without_a_required_box_the_check_does_not_run(tmp_path, monkeypatch):
    """Byte-for-byte the historic behaviour, and the core is not even
    imported -- the first frame_state call happens before the engine path
    is on sys.path."""
    (elevation, osm) = _corpus(tmp_path, monkeypatch, write_raster=False,
                               index_record=False)
    (state, problems) = DP.frame_state(elevation, osm, LAT, LON, ICAO)
    assert problems == []
    assert "airport_inset_problem_kind" not in state


def test_a_whole_tile_miss_is_named_once_not_twice(tmp_path, monkeypatch):
    """No insets directory at all: the tile-wide problem is the honest
    one, and the per-airport check must not say the same cold cache in a
    second voice."""
    (elevation, osm) = _corpus(tmp_path, monkeypatch)
    import shutil
    shutil.rmtree(os.path.join(elevation, BLOCK,
                               f"{STEM}_airport_insets"))
    (state, problems) = DP.frame_state(elevation, osm, LAT, LON, ICAO,
                                       REQUIRED)
    assert len(problems) == 1
    assert "NO airport elevation insets dir" in problems[0]


# =====================================================================
# Production warms it; the harness refuses it
# =====================================================================
def _dem(core_hosted, allow_degraded=False):
    dem = DP.ProductionDem.__new__(DP.ProductionDem)
    dem.core_hosted = core_hosted
    dem.allow_degraded = allow_degraded
    dem.provenance = {}
    dem.declared_tiles = {(LAT, LON)}
    dem._out = lambda line: None
    dem._tiles = {}
    dem.icao, dem.elevation_root, dem.osm_root = ICAO, "e", "o"
    dem.xplane_root = ""
    dem._required_boxes = {}
    return dem


def _stale_then_warm(monkeypatch, calls):
    """frame_state: warm tile-wide, STALE for this airport.

    ``calls`` used to collect ``_warm_tile`` invocations; that method is
    DELETED (spec §C.6 — the silent pool-child warm is the ~3 h +38-010
    class, RULINGS 2026-09-18b), so the list now stays empty by
    construction and any fetch reached from here is an assertion failure.
    """
    tile_warm = {"tile_stem": STEM, "base_raster_present": True,
                 "airports_layer_present": True,
                 "airport_insets_present": True}
    stale = (dict(tile_warm, airport_inset_problem_kind="stale"),
             ["STALE airport elevation inset /x/CYXY_hrdem.tif"])
    seq = [(dict(tile_warm), []), stale, stale]

    def fake_state(*args, **kwargs):
        return seq.pop(0) if len(seq) > 1 else seq[0]

    monkeypatch.setattr(DP, "frame_state", fake_state)
    monkeypatch.setattr(DP.ProductionDem, "_required_inset_box",
                        lambda self, tile, dico: REQUIRED)
    monkeypatch.setattr(DP.ProductionDem, "_expects_inset",
                        lambda self, tile: True)
    import O4_Airport_Elevation_Insets as INSETS

    def explode(*a, **k):
        calls.append(("fetch", a, k))
        raise AssertionError("nothing may fetch from _compose any more")

    monkeypatch.setattr(INSETS, "ensure_insets_for_tile", explode)


def _stub_core(monkeypatch):
    """_compose's core imports, stubbed: this twin is about the frame
    decision, not about composing a raster."""
    import sys
    import types
    tile = types.SimpleNamespace(lat=LAT, lon=LON, read_from_config=lambda: None,
                                 auto_patch_xplane_root=None)
    cfg = types.SimpleNamespace(Tile=lambda lat, lon, _s: tile)
    osm = types.SimpleNamespace(OSM_layer=lambda: None,
                                OSM_queries_to_OSM_layer=lambda *a, **k: None)
    vmap = types.SimpleNamespace(
        AIRPORTS_QUERIES=[],
        build_airports_dico=lambda _t, _l: {ICAO: {}},
        compose_tile_dem_from_disk=lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("composed-stop")))
    for name, module in (("O4_Config_Utils", cfg), ("O4_OSM_Utils", osm),
                         ("O4_Vector_Map", vmap)):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(DP.ProductionDem, "_ensure_core_path",
                        lambda self: None)


def test_production_REFUSES_a_stale_inset_and_no_longer_recuts(monkeypatch):
    """REWRITTEN for spec §C.6.  The owner's 2026-09-17 (2) ruling ("the
    app may re-cut a stale inset automatically") is still honoured — but
    by ``O4_Vector_Map.ensure_tile_frame`` in the MAIN process after an
    explicit boundary choice (§D), never here in the pool child, where the
    fetch had no progress channel and cost ~3 h on tile +38-010.  On this
    build's OWN tile a stale inset is now a refusal, and ZERO fetches
    happen on the way to it."""
    calls: list = []
    _stale_then_warm(monkeypatch, calls)
    _stub_core(monkeypatch)
    dem = _dem(core_hosted=True)
    with pytest.raises(DP.ColdDemFrame, match="STALE airport elevation inset"):
        dem._compose(LAT, LON)
    assert calls == []


def test_a_stale_inset_on_an_UNDECLARED_tile_is_context_only(monkeypatch):
    """The class-M far side: recorded, never refused, never fetched."""
    calls: list = []
    _stale_then_warm(monkeypatch, calls)
    _stub_core(monkeypatch)
    dem = _dem(core_hosted=True)
    dem.declared_tiles = {(LAT + 1, LON)}          # this cell is NOT ours
    with pytest.raises(RuntimeError, match="composed-stop"):
        dem._compose(LAT, LON)
    assert calls == []
    assert dem.provenance.get(f"context_only:{STEM}")


def test_the_harness_REFUSES_a_stale_inset_and_never_recuts(monkeypatch):
    calls: list = []
    _stale_then_warm(monkeypatch, calls)
    _stub_core(monkeypatch)
    dem = _dem(core_hosted=False)
    with pytest.raises(DP.ColdDemFrame, match="STALE airport elevation inset"):
        dem._compose(LAT, LON)
    assert calls == []            # it warmed NOTHING


def test_the_frame_records_all_three_boxes_and_the_packs(monkeypatch):
    """Owner ruling 3, conditional: ADDITIVE metadata only.  It buys
    COMPARABILITY between arms — the engine consults the manifest, never
    the frame record — and the ledger-identity guard lives in
    ``tests/test_harness.py``."""
    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES
    monkeypatch.setattr(INSETS, "requested_inset_bounding_box",
                        lambda *a: (-135.1, 60.6, -135.0, 60.8))
    monkeypatch.setattr(INSETS, "delivered_inset_bounding_box",
                        lambda _p: (-135.1, 60.6, -135.0, 60.79))
    monkeypatch.setattr(INSETS, "recorded_footprint_packs",
                        lambda *a: ["Aerosoft CYXY", "Zzz Pack"])
    monkeypatch.setattr(FNAMES, "airport_inset_dem",
                        lambda *a: "/x/CYXY_hrdem.tif")
    dem = _dem(core_hosted=False)
    dem._required_boxes[(LAT, LON)] = REQUIRED
    dem._record_inset_boxes(LAT, LON, [
        {"icao": ICAO, "provider": "hrdem"},
        {"icao": "OTHER", "provider": "hrdem"},   # not this airport
    ])
    line = dem.provenance["inset:CYXY:hrdem"]
    assert isinstance(line, str), "every value in this dict is a string"
    assert "required=-135.100000,60.650000,-135.000000,60.760000" in line
    assert "requested=-135.100000,60.600000,-135.000000,60.800000" in line
    assert "delivered=-135.100000,60.600000,-135.000000,60.790000" in line
    assert "footprint_packs=Aerosoft CYXY|Zzz Pack" in line
    assert "inset:OTHER:hrdem" not in dem.provenance
    # Unknown packs and an unreadable raster read as '?', never a guess
    # and never an exception: the frame record must not fail a build.
    monkeypatch.setattr(INSETS, "recorded_footprint_packs", lambda *a: None)
    monkeypatch.setattr(INSETS, "delivered_inset_bounding_box",
                        lambda _p: None)
    dem.provenance.clear()
    dem._record_inset_boxes(LAT, LON, [{"icao": ICAO, "provider": "hrdem"}])
    assert "delivered=?" in dem.provenance["inset:CYXY:hrdem"]
    assert "footprint_packs=?" in dem.provenance["inset:CYXY:hrdem"]


def test_allow_degraded_accepts_the_stale_inset_and_still_never_recuts(
    monkeypatch
):
    calls: list = []
    _stale_then_warm(monkeypatch, calls)
    _stub_core(monkeypatch)
    dem = _dem(core_hosted=True, allow_degraded=True)
    with pytest.raises(RuntimeError, match="composed-stop"):
        dem._compose(LAT, LON)
    assert calls == []            # accepting a worse frame authorises NO write
    assert "STALE airport elevation inset" in dem.provenance["degraded"]
