"""#130 -- the USGS3DEP resolution ladder (KASE, Aspen).

KASE's 1 m 3DEP mosaic held 0.22 % valid pixels (the only 1 m project
there never flew the cell over the airport), the bake refused it, and the
airport was graded on the 30 m base DEM while 3DEP publishes 1/3
arc-second (~10 m) over the whole box.  The ladder: a rung below the
bake's own threshold (``INSET_MIN_VALID_FRAC``) climbs to the next,
coarser rung declared in the provider's ``.elv``; the record names every
rung tried and the one delivered; no-coverage only when no rung listed a
product.  No network: a fake strategy writes synthetic GeoTIFFs whose
valid fraction is keyed on the rung's native resolution.
"""

import json
import os

import numpy
import pytest

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS
from elevation_access import base as ea_base
from elevation_access import capabilities as ea_capabilities
from elevation_access import definitions as ea_definitions
from elevation_access import las_tiles as ea_las_tiles
from elevation_access import registry as ea_registry
from elevation_access.strategies import las_tile_index as ea_las_tile_index
from elevation_access.strategies import tnm_cog as ea_tnm_cog
from elevation_access import warp as ea_warp

try:
    from osgeo import gdal, osr

    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

requires_gdal = pytest.mark.skipif(not HAS_GDAL, reason="no osgeo")

BOX = (-106.8994, 39.1893, -106.8378, 39.2532)
STRATEGY = "ladder_fake_strategy"


def _write_raster(path, valid_fraction, size=40):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, size, size, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform(
        (BOX[0], (BOX[2] - BOX[0]) / size, 0.0, BOX[3], 0.0,
         -(BOX[3] - BOX[1]) / size))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    values = numpy.full((size, size), -32768.0, dtype=numpy.float32)
    valid_rows = int(round(valid_fraction * size))
    values[:valid_rows, :] = 2400.0
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values)
    dataset = None


@pytest.fixture
def fake_strategy():
    """``plan[native_m]`` = valid fraction to deliver, ``None`` for "no
    product listed", or an Exception instance to raise."""
    plan = {}
    calls = []

    @ea_registry.register_access_strategy(STRATEGY)
    class _Fake:
        def discover(self, definition, bounding_box_wgs84):
            return [{"note": "fake"}]

        def fetch(self, definition, bounding_box_wgs84,
                  target_resolution_m, destination_path):
            native = definition["native_resolution_m"]
            calls.append((native, target_resolution_m, destination_path))
            outcome = plan.get(native)
            if isinstance(outcome, Exception):
                _write_raster(destination_path, 0.5)     # partial file
                raise outcome
            if outcome is None:
                return None
            _write_raster(destination_path, outcome)
            return {
                "provider": definition["code"],
                "native_resolution_m": native,
                "resolution_m": target_resolution_m,
                "sources_used": [{"title": "rung %g" % native}],
            }

    try:
        yield plan, calls
    finally:
        ea_registry.ACCESS_STRATEGIES.pop(STRATEGY, None)


def _definition():
    return {
        "code": "FAKE3DEP",
        "access_strategy": STRATEGY,
        "role": ea_definitions.ROLE_AIRPORT_INSET,
        "enabled": True,
        "priority": 1.0,
        "native_resolution_m": 1.0,
        "ladder_label": "1 meter",
        "discovery_url_template": "rung0",
        "resolution_ladder_rungs": INSETS._parse_resolution_ladder(
            "10|1/3 arc-second|rung2;3|1/9 arc-second|rung1"),
    }


@requires_gdal
def test_empty_1m_climbs_to_3m(tmp_path, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 0.0, 3.0: 1.0, 10.0: 1.0})
    destination = str(tmp_path / "KASE_fake3dep.tif")
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True)
    assert [call[0] for call in calls] == [1.0, 3.0]    # 10 m never asked
    assert calls[1][1] == 3.0                           # warped at 3 m
    assert provenance["resolution_m"] == 3.0
    assert provenance["native_resolution_m"] == 3.0
    ladder = provenance["ladder"]
    assert ladder["delivered_rung"] == 1
    assert ladder["delivered_label"] == "1/9 arc-second"
    assert ladder["threshold_valid_fraction"] == INSETS.INSET_MIN_VALID_FRAC
    assert [r["outcome"] for r in ladder["rungs_tried"]] == [
        "below-threshold", "delivered"]
    # The 3 m raster IS the inset now; no rung scratch file survives.
    assert ea_warp.inset_valid_fraction(destination) == 1.0
    assert sorted(os.listdir(tmp_path)) == ["KASE_fake3dep.tif"]


@requires_gdal
def test_finest_rung_answering_stops_the_ladder(tmp_path, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 1.0, 3.0: 1.0, 10.0: 1.0})
    destination = str(tmp_path / "a.tif")
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True)
    assert [call[0] for call in calls] == [1.0]
    assert provenance["ladder"]["delivered_rung"] == 0
    assert provenance["resolution_m"] == 1.0


@requires_gdal
def test_no_product_rung_is_skipped(tmp_path, fake_strategy):
    """The KASE shape: 1 m sub-threshold, 1/9" lists nothing, 1/3" whole."""
    plan, calls = fake_strategy
    plan.update({1.0: 0.0022, 3.0: None, 10.0: 1.0})
    destination = str(tmp_path / "a.tif")
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True)
    ladder = provenance["ladder"]
    assert [r["outcome"] for r in ladder["rungs_tried"]] == [
        "below-threshold", "no-coverage", "delivered"]
    assert ladder["delivered_label"] == "1/3 arc-second"
    assert provenance["resolution_m"] == 10.0


@requires_gdal
def test_every_rung_below_threshold_keeps_the_finest(tmp_path, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 0.025, 3.0: 0.0, 10.0: None})
    destination = str(tmp_path / "a.tif")
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True)
    assert provenance["ladder"]["delivered_rung"] is None
    assert provenance["resolution_m"] == 1.0          # the finest, kept
    assert INSETS.inset_is_effectively_empty(destination)[0]
    assert sorted(os.listdir(tmp_path)) == ["a.tif"]


@requires_gdal
def test_no_coverage_only_when_every_rung_lists_nothing(tmp_path,
                                                        fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: None, 3.0: None, 10.0: None})
    destination = str(tmp_path / "a.tif")
    assert INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True) is None
    assert len(calls) == 3
    assert os.listdir(tmp_path) == []


@requires_gdal
def test_transient_rung_raises_and_leaves_no_scratch(tmp_path, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 0.0, 3.0: ea_base.TransientFetchError("outage")})
    destination = str(tmp_path / "a.tif")
    with pytest.raises(ea_base.TransientFetchError):
        INSETS.fetch_inset(
            _definition(), BOX, 1.0, destination, resolution_ladder=True)
    assert not any(name.startswith("a.tif.rung")
                   for name in os.listdir(tmp_path))


@requires_gdal
def test_ladder_is_off_unless_asked(tmp_path, fake_strategy):
    """The whole-tile overlay path never trades a sparse 1 m tile down."""
    plan, calls = fake_strategy
    plan.update({1.0: 0.0, 3.0: 1.0})
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, str(tmp_path / "a.tif"))
    assert [call[0] for call in calls] == [1.0]
    assert "ladder" not in provenance


def test_parse_orders_rungs_finest_first_and_drops_malformed():
    rungs = INSETS._parse_resolution_ladder(
        "10|coarse|u10; nonsense ;3|fine|u3;0|zero|u0")
    assert [(r["native_resolution_m"], r["label"]) for r in rungs] == [
        (3.0, "fine"), (10.0, "coarse")]


def test_shipped_usgs3dep_declares_the_ladder():
    providers = INSETS.initialize_elevation_providers_dict()
    usgs = providers["USGS3DEP"]
    rungs = usgs["resolution_ladder_rungs"]
    # 30aw (2) + 30bl (#153): USGS 1 m -> PITKIN1M 1 m -> USGS OPR ->
    # USGS LPC -> USGS 3 m -> USGS 10 m.
    assert [r["native_resolution_m"] for r in rungs] == [
        1.0, 1.0, 1.0, 3.0, 10.0]
    assert [r.get("provider") for r in rungs[:3]] == [
        "PITKIN1M", "USGSOPR", "USGSLPC"]
    assert all("discovery_url_template" not in r for r in rungs[:3])
    assert all("{west}" in r["discovery_url_template"] for r in rungs[3:])
    assert "1/3 arc-second" in rungs[-1]["discovery_url_template"]
    assert usgs["native_resolution_m"] == 1.0          # rung 0 untouched
    resolved = INSETS._ladder_rung_definitions(usgs)
    assert [(d["code"], d["access_strategy"]) for _l, d in resolved] == [
        ("USGS3DEP", "tnm_cog"), ("PITKIN1M", "las_tile_index"),
        ("USGSOPR", "tnm_cog"), ("USGSLPC", "las_tile_index"),
        ("USGS3DEP", "tnm_cog"), ("USGS3DEP", "tnm_cog")]


def test_shipped_opr_and_lpc_rungs():
    """#153: the OPR rung reads units from its files and is judged by
    airport cover; the LPC rung is a TNM-indexed LAZ point cloud gated on
    the LAZ backend; both are US-only and sit below USGS3DEP."""
    providers = INSETS.initialize_elevation_providers_dict()
    opr = providers["USGSOPR"]
    lpc = providers["USGSLPC"]
    usgs = providers["USGS3DEP"]
    assert opr["access_strategy"] == "tnm_cog"
    assert "Original Product Resolution" in opr["discovery_url_template"]
    assert ea_tnm_cog._definition_reads_source_units(opr)
    assert INSETS._rung_judged_by_airport_cover(opr)
    assert float(opr["max_source_resolution_m"]) > 1.5   # MS Coastal 4 ftUS
    assert lpc["access_strategy"] == "las_tile_index"
    assert lpc["index_format"] == "tnm"
    assert "Lidar Point Cloud" in lpc["index_url_template"]
    assert INSETS.provider_required_capabilities(lpc) == [
        ea_capabilities.CAPABILITY_LAS, ea_capabilities.CAPABILITY_LAZ]
    assert ea_las_tile_index._las_crs_from_header(lpc)
    for definition in (opr, lpc):
        assert definition["coverage_bbox"] == usgs["coverage_bbox"]
        assert definition["priority"] < providers["PITKIN1M"]["priority"]
        assert not INSETS._rung_can_be_surround(definition)


@requires_gdal
def test_airport_fetch_records_the_ladder_in_the_sidecar(
        tmp_path, monkeypatch, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 0.0, 3.0: None, 10.0: 1.0})
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    record = INSETS.ensure_airport_insets(
        39, -107, {"KASE": BOX}, [_definition()], None)
    assert record["KASE"]["FAKE3DEP"] == "ok"
    sidecar = FNAMES.airport_inset_provenance(39, -107, "KASE", "FAKE3DEP")
    with open(sidecar, encoding="utf-8") as handle:
        meta = json.load(handle)
    assert meta["ladder"]["delivered_label"] == "1/3 arc-second"
    assert meta["resolution_m"] == 10.0
    assert meta["native_resolution_m"] == 10.0



# ---------------------------------------------------------------------
# CROSS-PROVIDER RUNGS + THE BUILD-TIME RE-CHECK (RULINGS 2026-09-30aw)
# ---------------------------------------------------------------------
OTHER_STRATEGY = "ladder_fake_other_strategy"


@pytest.fixture
def two_providers(monkeypatch, tmp_path):
    """A chain FAKE3DEP (1 m, 10 m) with a cross-provider rung FAKEPIT
    (1 m, its own strategy and coverage) between them.  ``plan`` maps a
    rung key (``"FAKE3DEP:1"``, ``"FAKEPIT"``, ``"FAKE3DEP:10"``) to
    ``{"valid": fraction | None, "listing": [ids]}``; ``discover_raise``
    names keys whose discovery raises transient."""
    plan = {}
    calls = {"fetch": [], "discover": []}
    discover_raise = set()

    def _key(definition):
        if definition["code"] == "FAKEPIT":
            return "FAKEPIT"
        return "FAKE3DEP:%g" % definition["native_resolution_m"]

    class _Base:
        def discover(self, definition, bounding_box_wgs84):
            key = _key(definition)
            calls["discover"].append(key)
            if key in discover_raise:
                raise ea_base.TransientFetchError("index outage")
            listing = plan.get(key, {}).get("listing") or []
            return [{"source_id": i} for i in listing] or None

        def fetch(self, definition, bounding_box_wgs84,
                  target_resolution_m, destination_path):
            key = _key(definition)
            calls["fetch"].append(key)
            entry = plan.get(key) or {}
            if entry.get("unavailable"):
                raise ea_base.ProviderUnavailable(entry["unavailable"])
            if entry.get("transient"):
                _write_raster(destination_path, 0.5)     # partial file
                raise ea_base.TransientFetchError(entry["transient"])
            if entry.get("valid") is None:
                self.last_listing = [{"source_id": i} for i in
                                     entry.get("listing") or []]
                return None
            if entry.get("keep"):
                _write_partial(destination_path, bounding_box_wgs84,
                               2400.0, entry["keep"])
            else:
                _write_raster(destination_path, entry["valid"])
            return {
                "provider": definition["code"],
                "native_resolution_m": definition["native_resolution_m"],
                "resolution_m": target_resolution_m,
                "source_ids": list(entry.get("listing") or []),
                "sources_used": [{"source_id": i}
                                 for i in entry.get("listing") or []],
            }

    ea_registry.register_access_strategy(STRATEGY)(type("_A", (_Base,), {}))
    ea_registry.register_access_strategy(OTHER_STRATEGY)(type("_B", (_Base,), {}))
    chain = {
        "code": "FAKE3DEP",
        "access_strategy": STRATEGY,
        "role": ea_definitions.ROLE_AIRPORT_INSET,
        "enabled": True,
        "priority": 1.0,
        "native_resolution_m": 1.0,
        "ladder_label": "1 meter",
        "discovery_url_template": "rung0",
        "resolution_ladder_rungs": INSETS._parse_resolution_ladder(
            "1|county lidar|provider:FAKEPIT;10|1/3 arc-second|rung2"),
    }
    other = {
        "code": "FAKEPIT",
        "access_strategy": OTHER_STRATEGY,
        "role": ea_definitions.ROLE_AIRPORT_INSET,
        "enabled": True,
        "priority": 0.5,
        "native_resolution_m": 1.0,
        "coverage_bbox": "-107.4,38.95,-106.3,39.55",
    }
    other["coverage_bboxes"] = ea_definitions._parse_bounding_boxes(
        other["coverage_bbox"])
    monkeypatch.setattr(INSETS, "elevation_providers_dict",
                        {"FAKE3DEP": chain, "FAKEPIT": other})
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    try:
        yield plan, calls, chain, other, discover_raise
    finally:
        ea_registry.ACCESS_STRATEGIES.pop(STRATEGY, None)
        ea_registry.ACCESS_STRATEGIES.pop(OTHER_STRATEGY, None)


def _sidecar(icao="KASE"):
    path = FNAMES.airport_inset_provenance(39, -107, icao, "FAKE3DEP")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def test_parse_accepts_a_provider_rung_and_keeps_file_order_on_ties():
    rungs = INSETS._parse_resolution_ladder(
        "10|coarse|u10;1|county|provider:PIT;3|fine|u3;1|bad|provider:")
    assert [(r["native_resolution_m"], r["label"], r.get("provider"))
            for r in rungs] == [(1.0, "county", "PIT"), (3.0, "fine", None),
                                (10.0, "coarse", None)]


@requires_gdal
def test_provider_rung_resolves_its_own_strategy(tmp_path, two_providers):
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": 0.0022, "listing": ["u1"]},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1", "T2"]}})
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(tmp_path / "KASE_fake3dep.tif"),
                                    resolution_ladder=True)
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKEPIT"]
    ladder = provenance["ladder"]
    assert ladder["delivered_rung"] == 1
    assert ladder["delivered_provider"] == "FAKEPIT"
    assert provenance["provider"] == "FAKEPIT"
    assert [r["provider"] for r in ladder["rungs_tried"]] == [
        "FAKE3DEP", "FAKEPIT"]
    assert ladder["rungs_tried"][0]["listing_ids"] == ["u1"]
    assert ladder["rungs_tried"][1]["listing_ids"] == ["T1", "T2"]


@requires_gdal
def test_out_of_coverage_provider_rung_makes_no_call(tmp_path,
                                                     two_providers):
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    madrid = (-3.6, 40.4, -3.5, 40.5)
    provenance = INSETS.fetch_inset(chain, madrid, 1.0,
                                    str(tmp_path / "LEMD_fake3dep.tif"),
                                    resolution_ladder=True)
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKE3DEP:10"]
    assert "FAKEPIT" not in calls["discover"]
    outcomes = [r["outcome"] for r in provenance["ladder"]["rungs_tried"]]
    assert outcomes == ["below-threshold", "out-of-coverage", "delivered"]


@requires_gdal
def test_unavailable_provider_rung_climbs_on(tmp_path, two_providers):
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKEPIT": {"unavailable": "laspy missing"},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(tmp_path / "KASE_fake3dep.tif"),
                                    resolution_ladder=True)
    tried = provenance["ladder"]["rungs_tried"]
    assert [r["outcome"] for r in tried] == [
        "below-threshold", "unavailable", "delivered"]
    assert tried[1]["unavailable_reason"] == "laspy missing"
    assert "listing_ids" not in tried[1]


@requires_gdal
def test_recheck_new_listing_between_two_builds_refetches(two_providers):
    """The 2024 USGS Aspen unit, in miniature: build 1 finds the finer
    rung empty and delivers rung 1; before build 2 the finer rung LISTS a
    product with coverage -- build 2's re-check sees the new id, re-runs
    the ladder and delivers rung 0."""
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": None, "listing": []},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    assert _sidecar()["ladder"]["delivered_rung"] == 1
    plan["FAKE3DEP:1"] = {"valid": 1.0, "listing": ["new2024"]}
    calls["fetch"].clear()
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    assert calls["fetch"] == ["FAKE3DEP:1"]
    meta = _sidecar()
    assert meta["ladder"]["delivered_rung"] == 0
    assert meta["provider"] == "FAKE3DEP"
    recheck = INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP", BOX)
    assert recheck is None                           # rung 0: nothing finer


@requires_gdal
def test_recheck_stamps_new_listing_even_when_it_grids_empty(two_providers):
    """A finer product that LISTS but grids below the threshold (KASE's
    0.22 %) re-runs the ladder and leaves the delivered rung where it
    was; the next build is then unchanged -- no loop."""
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": None, "listing": []},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    plan["FAKE3DEP:1"] = {"valid": 0.0022, "listing": ["sparse"]}
    recheck = INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP", BOX)
    assert recheck["result"] == "new-listing"
    assert recheck["new_source_ids"] == ["sparse"]
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    meta = _sidecar()
    assert meta["ladder"]["delivered_rung"] == 1
    assert meta["ladder"]["rungs_tried"][0]["listing_ids"] == ["sparse"]
    calls["fetch"].clear()
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    assert calls["fetch"] == []
    assert _sidecar()["ladder"]["recheck"]["result"] == "unchanged"


@requires_gdal
def test_recheck_unchanged_never_fetches_and_never_rewrites(two_providers):
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    calls["fetch"].clear()
    calls["discover"].clear()
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    assert calls["fetch"] == []
    assert calls["discover"] == ["FAKE3DEP:1"]       # finer rungs only
    path = FNAMES.airport_inset_provenance(39, -107, "KASE", "FAKE3DEP")
    first = os.stat(path).st_mtime_ns
    with open(path, "rb") as handle:
        body = handle.read()
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    with open(path, "rb") as handle:
        assert handle.read() == body                 # byte-identical
    assert os.stat(path).st_mtime_ns == first
    assert json.loads(body)["ladder"]["recheck"]["result"] == "unchanged"


@requires_gdal
def test_recheck_transient_discovery_leaves_the_inset_standing(
        two_providers):
    plan, calls, chain, _other, discover_raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    discover_raise.add("FAKE3DEP:1")
    calls["fetch"].clear()
    record = INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain],
                                          None)
    assert calls["fetch"] == []
    assert record["KASE"]["FAKE3DEP"] == "ok"
    meta = _sidecar()
    assert meta["provider"] == "FAKEPIT"
    assert meta["ladder"]["recheck"]["result"] == "transient"


@requires_gdal
def test_recheck_never_runs_for_a_rung_zero_inset(two_providers):
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": 1.0, "listing": ["u1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    calls["discover"].clear()
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    assert calls["discover"] == []
    assert "recheck" not in _sidecar()["ladder"]


# ---------------------------------------------------------------------
# ROUND 2: the airport-coverage gate, the two-layer inset, the guard
# ---------------------------------------------------------------------
CORE_STRATEGY = "ladder_fake_core_strategy"


def _write_partial(path, box, value, keep):
    """A raster over ``box`` with data only inside ``keep`` (a W,S,E,N)."""
    size = 60
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, size, size, 1, gdal.GDT_Float32)
    (west, south, east, north) = box
    dx = (east - west) / size
    dy = (north - south) / size
    dataset.SetGeoTransform((west, dx, 0.0, north, 0.0, -dy))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    values = numpy.full((size, size), -32768.0, dtype=numpy.float32)
    xs = west + (numpy.arange(size) + 0.5) * dx
    ys = north - (numpy.arange(size) + 0.5) * dy
    inside = ((ys >= keep[1]) & (ys <= keep[3]))[:, None] & (
        (xs >= keep[0]) & (xs <= keep[2]))[None, :]
    values[inside] = value
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values)
    dataset = None


@pytest.fixture
def core_chain(monkeypatch, tmp_path, two_providers):
    """``two_providers``'s chain, its FAKEPIT rung answering like a
    SURGICAL LAS fetch: data only over ``plan["core_keep"]``, a ``core``
    block, and the footprint it was handed recorded."""
    plan, calls, chain, other, discover_raise = two_providers
    seen = {}

    class _Core:
        def discover(self, definition, bounding_box_wgs84):
            return [{"source_id": "T1"}]

        def fetch(self, definition, bounding_box_wgs84,
                  target_resolution_m, destination_path):
            calls["fetch"].append("FAKEPIT")
            seen["footprint"] = definition.get(ea_las_tiles.LAS_FOOTPRINT_KEY)
            _write_partial(destination_path, bounding_box_wgs84, 2400.0,
                           plan["core_keep"])
            return {"provider": "FAKEPIT", "native_resolution_m": 1.0,
                    "resolution_m": target_resolution_m,
                    "source_ids": ["T1"],
                    "core": {"provider": "FAKEPIT",
                             "boundary_polygon_wgs84": definition.get(
                                 ea_las_tiles.LAS_FOOTPRINT_KEY),
                             "footprint_buffer_m": 0.0,
                             "tile_names": ["T1"], "feather_m": 60.0}}

    ea_registry.register_access_strategy(CORE_STRATEGY)(_Core)
    other["access_strategy"] = CORE_STRATEGY
    try:
        yield plan, calls, chain, seen
    finally:
        ea_registry.ACCESS_STRATEGIES.pop(CORE_STRATEGY, None)


def _airport():
    from shapely.geometry import box as _box

    # the aerodrome: the middle of BOX
    return _box(-106.880, 39.210, -106.857, 39.232)


@requires_gdal
def test_core_delivered_over_the_airport_with_a_surround(tmp_path,
                                                        core_chain):
    plan, calls, chain, seen = core_chain
    airport = _airport()
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]},
                 "core_keep": (-106.885, 39.205, -106.852, 39.237)})
    destination = str(tmp_path / "KASE_fake3dep.tif")
    provenance = INSETS.fetch_inset(chain, BOX, 1.0, destination,
                                    resolution_ladder=True,
                                    footprint_polygon=airport)
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKEPIT", "FAKE3DEP:10"]
    assert seen["footprint"]["type"] == "Polygon"   # handed the footprint
    ladder = provenance["ladder"]
    assert ladder["delivered_rung"] == 1
    assert ladder["delivered_provider"] == "FAKEPIT"
    assert ladder[ea_las_tiles.LAS_FOOTPRINT_KEY]["type"] == "Polygon"
    assert provenance["airport_valid_fraction"] >= \
        INSETS.INSET_MIN_AIRPORT_COVER_FRAC
    assert provenance["core"]["rung"] == 1
    assert provenance["surround"]["provider"] == "FAKE3DEP"
    assert provenance["surround"]["rung"] == 2
    assert provenance["valid_fraction"] == 1.0      # box-wide, assembled
    assert provenance["native_resolution_m"] == 1.0
    assert [r.get("role") for r in ladder["rungs_tried"]] == [
        None, None, "surround"]
    assert sorted(os.listdir(tmp_path)) == ["KASE_fake3dep.tif"]


@requires_gdal
def test_core_below_the_airport_cover_rule_moves_on(tmp_path, core_chain):
    """The 80 % rule: a core covering only a corner of the aerodrome is
    NOT delivered, whatever its box-wide share; the ladder climbs."""
    plan, calls, chain, seen = core_chain
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]},
                 "core_keep": (-106.880, 39.210, -106.870, 39.220)})
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(tmp_path / "KASE_fake3dep.tif"),
                                    resolution_ladder=True,
                                    footprint_polygon=_airport())
    tried = provenance["ladder"]["rungs_tried"]
    assert tried[1]["outcome"] == "below-threshold"
    assert tried[1]["airport_valid_fraction"] < \
        INSETS.INSET_MIN_AIRPORT_COVER_FRAC
    assert provenance["ladder"]["delivered_rung"] == 2
    assert "core" not in provenance


@requires_gdal
def test_recheck_stamp_not_attempted_under_an_armed_guard(
        two_providers, monkeypatch):
    """§11 (4e): the stamp write is NEVER attempted when an armed guard
    would refuse it; the result still returns (the harness puts it in
    frame.json)."""
    import sys
    import types

    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    path = FNAMES.airport_inset_provenance(39, -107, "KASE", "FAKE3DEP")
    with open(path, "rb") as handle:
        body = handle.read()
    armed = types.ModuleType("fake_armed_guard_130")
    armed._ACTIVE_GUARDS = [object()]
    armed.active_guard_refuses = lambda p: True
    monkeypatch.setitem(sys.modules, "fake_armed_guard_130", armed)
    recheck = INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP", BOX,
                                    record=True)
    assert recheck["result"] == "unchanged"
    assert "not attempted" in recheck["stamp"]
    with open(path, "rb") as handle:
        assert handle.read() == body


# ---------------------------------------------------------------------
# #153 (owner RULINGS 2026-09-30bl): every rung failure class falls
# through; airport-cover rungs; the surround is never a lidar rung.
# ---------------------------------------------------------------------
@requires_gdal
def test_transient_provider_rung_climbs_on_and_is_rechecked(two_providers):
    """A rung that does not answer is recorded ``transient`` (no listing)
    and the ladder delivers the next rung; the next build's re-check asks
    it again, and when it answers with coverage it wins."""
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": None, "listing": []},
                 "FAKEPIT": {"transient": "index outage",
                             "listing": ["T1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    meta = _sidecar()
    tried = meta["ladder"]["rungs_tried"]
    assert [r["outcome"] for r in tried] == [
        "no-coverage", "transient", "delivered"]
    assert tried[1]["transient_reason"] == "index outage"
    assert "listing_ids" not in tried[1]
    assert meta["ladder"]["delivered_rung"] == 2
    recheck = INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP", BOX)
    assert recheck["result"] == "new-listing"
    assert recheck["new_source_ids"] == ["T1"]
    plan["FAKEPIT"] = {"valid": 1.0, "listing": ["T1"]}
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    assert _sidecar()["ladder"]["delivered_provider"] == "FAKEPIT"


@requires_gdal
def test_every_rung_transient_is_no_answer(tmp_path, two_providers):
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"transient": "a"},
                 "FAKEPIT": {"transient": "b"},
                 "FAKE3DEP:10": {"transient": "c"}})
    with pytest.raises(ea_base.TransientFetchError, match="a"):
        INSETS.fetch_inset(chain, BOX, 1.0, str(tmp_path / "K_f.tif"),
                           resolution_ladder=True)
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKEPIT", "FAKE3DEP:10"]
    assert os.listdir(tmp_path) == []


@requires_gdal
def test_no_coverage_rung_records_what_it_listed(tmp_path, two_providers):
    """A rung whose listing yields nothing usable (OPR listing only 5 m
    IFSAR) records that listing, so the re-check does not read it as new
    on every build."""
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKEPIT": {"valid": None, "listing": ["IFSAR"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    tried = _sidecar()["ladder"]["rungs_tried"]
    assert tried[1]["outcome"] == "no-coverage"
    assert tried[1]["listing_ids"] == ["IFSAR"]
    plan["FAKEPIT"]["listing"] = ["IFSAR"]
    recheck = INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP", BOX)
    assert recheck["result"] == "unchanged"


@requires_gdal
def test_airport_cover_rung_is_judged_over_the_airport(tmp_path,
                                                       two_providers):
    """``ladder_judge=airport_cover`` (the OPR rung): a raster holding
    far more than the box rule's 5 % but missing the aerodrome is NOT
    delivered; one covering the aerodrome is -- with no core, no
    surround."""
    plan, calls, chain, other, _raise = two_providers
    other["ladder_judge"] = "airport_cover"
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"],
                             # the west third of the box: 33 % box-wide,
                             # beside the aerodrome
                             "keep": (BOX[0], BOX[1], -106.8789, BOX[3])},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(tmp_path / "KASE_fake3dep.tif"),
                                    resolution_ladder=True,
                                    footprint_polygon=_airport())
    tried = provenance["ladder"]["rungs_tried"]
    assert tried[1]["valid_fraction"] > INSET_BOX_RULE_MARGIN
    assert tried[1]["airport_valid_fraction"] < \
        INSETS.INSET_MIN_AIRPORT_COVER_FRAC
    assert tried[1]["outcome"] == "below-threshold"
    assert provenance["ladder"]["delivered_rung"] == 2
    # covering the aerodrome: delivered at the rung, whole-box raster
    plan["FAKEPIT"]["keep"] = (-106.885, 39.205, -106.852, 39.237)
    calls["fetch"].clear()
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(tmp_path / "KASE_fake3dep.tif"),
                                    resolution_ladder=True,
                                    footprint_polygon=_airport())
    # The rung covers the aerodrome but not the whole box: its holes fill
    # DOWN THE LADDER from 10 m (spec §12) -- not from the base DEM.
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKEPIT", "FAKE3DEP:10"]
    assert provenance["ladder"]["delivered_provider"] == "FAKEPIT"
    assert provenance["ladder"]["delivered_rung"] == 1
    assert provenance["ladder"]["rungs_tried"][1][
        "airport_valid_fraction"] >= INSETS.INSET_MIN_AIRPORT_COVER_FRAC
    assert provenance["ladder"]["rungs_tried"][2]["role"] == "fill"
    assert [layer["label"] for layer in provenance["fills"]["layers"]] == [
        "1/3 arc-second"]
    assert provenance["valid_fraction"] == 1.0
    assert provenance["airport_filled_fraction"] == 1.0
    assert provenance["holes"] and all(
        row["filled_by"]["label"] == "1/3 arc-second"
        for row in provenance["holes"])
    assert "core" not in provenance and "surround" not in provenance


#: The box rule's threshold, with margin: the test raster is far above it.
INSET_BOX_RULE_MARGIN = 0.2


@requires_gdal
def test_surround_never_takes_a_lidar_rung(tmp_path, core_chain,
                                           monkeypatch):
    """KASE's chain after #153: PITKIN1M core, then the OPR and LPC rungs,
    then 10 m.  The surround skips the airport-cover and point-cloud
    rungs (never asked) and is the seamless 10 m layer, as before."""
    plan, calls, chain, seen = core_chain
    lidar = {"code": "FAKEOPR", "access_strategy": STRATEGY,
             "role": ea_definitions.ROLE_AIRPORT_INSET, "enabled": True,
             "priority": 0.4, "native_resolution_m": 1.0,
             "ladder_judge": "airport_cover"}
    cloud = {"code": "FAKELPC", "access_strategy": "las_tile_index",
             "role": ea_definitions.ROLE_AIRPORT_INSET, "enabled": True,
             "priority": 0.3, "native_resolution_m": 1.0}
    INSETS.elevation_providers_dict.update(
        {"FAKEOPR": lidar, "FAKELPC": cloud})
    chain["resolution_ladder_rungs"] = INSETS._parse_resolution_ladder(
        "1|county lidar|provider:FAKEPIT;1|opr|provider:FAKEOPR;"
        "1|lpc|provider:FAKELPC;10|1/3 arc-second|rung2")
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]},
                 "core_keep": (-106.885, 39.205, -106.852, 39.237)})
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(tmp_path / "KASE_fake3dep.tif"),
                                    resolution_ladder=True,
                                    footprint_polygon=_airport())
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKEPIT", "FAKE3DEP:10"]
    assert provenance["surround"]["rung"] == 4
    assert provenance["ladder"]["delivered_provider"] == "FAKEPIT"


@requires_gdal
def test_recheck_of_a_lidar_rung_inset_finds_a_later_1m_product(
        two_providers):
    """``ladder_recheck`` covers the new rungs: an inset the OPR-class
    rung delivered re-asks rung 0, and a USGS 1 m product appearing later
    still wins."""
    plan, calls, chain, other, _raise = two_providers
    other["ladder_judge"] = "airport_cover"
    plan.update({"FAKE3DEP:1": {"valid": None, "listing": []},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    assert _sidecar()["ladder"]["delivered_provider"] == "FAKEPIT"
    calls["discover"].clear()
    recheck = INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP", BOX)
    assert recheck["result"] == "unchanged"
    assert calls["discover"] == ["FAKE3DEP:1"]
    plan["FAKE3DEP:1"] = {"valid": 1.0, "listing": ["usgs1m"]}
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    meta = _sidecar()
    assert meta["ladder"]["delivered_rung"] == 0
    assert meta["provider"] == "FAKE3DEP"


@requires_gdal
def test_partial_rung_zero_yields_to_a_same_resolution_rung(tmp_path,
                                                            two_providers):
    """KGEG: USGS 1 m covers ~half the airport (box rule passes, its holes
    would fall to the 30 m base DEM); the OPR rung of the same flight
    covers all of it and is delivered.  The 10 m rung is never asked."""
    plan, calls, chain, other, _raise = two_providers
    other["ladder_judge"] = "airport_cover"
    plan.update({"FAKE3DEP:1": {"valid": 1.0, "listing": ["u1"],
                                "keep": (BOX[0], BOX[1], -106.8685,
                                         BOX[3])},
                 "FAKEPIT": {"valid": 1.0, "listing": ["T1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(tmp_path / "KGEG_fake3dep.tif"),
                                    resolution_ladder=True,
                                    footprint_polygon=_airport())
    tried = provenance["ladder"]["rungs_tried"]
    assert [r["outcome"] for r in tried] == ["partial", "delivered"]
    assert tried[0]["airport_valid_fraction"] < \
        INSETS.INSET_MIN_AIRPORT_COVER_FRAC
    assert provenance["ladder"]["delivered_provider"] == "FAKEPIT"
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKEPIT"]
    assert ea_warp.inset_valid_fraction(
        str(tmp_path / "KGEG_fake3dep.tif")) == 1.0
    assert sorted(os.listdir(tmp_path)) == ["KGEG_fake3dep.tif"]


@requires_gdal
def test_partial_rung_zero_stands_when_no_same_resolution_rung_covers(
        two_providers):
    """No 1 m-class alternative answers (an outage): rung 0 is delivered
    exactly as before -- never traded for the coarser 10 m rung -- and
    the next build's re-check asks the rung that did not answer; when it
    covers the airport, it wins."""
    plan, calls, chain, other, _raise = two_providers
    other["ladder_judge"] = "airport_cover"
    half = (BOX[0], BOX[1], -106.8685, BOX[3])
    plan.update({"FAKE3DEP:1": {"valid": 1.0, "listing": ["u1"],
                                "keep": half},
                 "FAKEPIT": {"transient": "outage", "listing": ["T1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    polygons = {"KASE": _airport()}
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None,
                                 airport_polygons=polygons)
    meta = _sidecar()
    ladder = meta["ladder"]
    assert [r["outcome"] for r in ladder["rungs_tried"]] == [
        "delivered", "transient", "delivered"]
    assert ladder["delivered_rung"] == 0
    # The 10 m rung is never DELIVERED in its place (30bu) -- it FILLS
    # the partial rung's holes (spec §12, owner RULINGS 2026-10-01d).
    assert ladder["rungs_tried"][2]["role"] == "fill"
    assert meta["airport_filled_fraction"] == 1.0
    assert meta["airport_valid_fraction"] < \
        INSETS.INSET_MIN_AIRPORT_COVER_FRAC
    recheck = INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP", BOX)
    assert recheck["result"] == "new-listing"
    assert recheck["new_source_ids"] == ["T1"]
    plan["FAKEPIT"] = {"valid": 1.0, "listing": ["T1"]}
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None,
                                 airport_polygons=polygons)
    ladder = _sidecar()["ladder"]
    assert ladder["delivered_provider"] == "FAKEPIT"
    # and from then on: rung 1 delivered over a partial rung 0, the
    # re-check asks rung 0 only and finds nothing new
    calls["discover"].clear()
    assert INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP",
                                 BOX)["result"] == "unchanged"
    assert calls["discover"] == ["FAKE3DEP:1"]


# ---------------------------------------------------------------------
# GLOBAL ASSEMBLY (spec us-holder-providers §1, RULINGS 2026-09-30bm):
# every ``ladder_member=True`` provider whose coverage box reaches the
# airport box joins the ladder; no hand ``provider:`` line.
# ---------------------------------------------------------------------
#: Airport boxes (ARP +- ~2 km) of the five controls and three holders.
CONTROL_BOXES = {
    "HECA": (31.38, 30.10, 31.43, 30.14),
    "KCLT": (-80.97, 35.19, -80.92, 35.24),
    "SPJC": (-77.13, -12.04, -77.09, -12.00),
    "CYXY": (-135.09, 60.69, -135.05, 60.73),
    "KASE": BOX,
}
KRDU_BOX = (-78.81, 35.85, -78.76, 35.90)
KGRK_BOX = (-97.84, 31.04, -97.80, 31.09)


def _codes(rungs):
    return [(label, definition["code"]) for (label, definition) in rungs]


def test_global_members_join_only_inside_their_box():
    providers = INSETS.initialize_elevation_providers_dict()
    usgs = providers["USGS3DEP"]
    chain = _codes(INSETS._ladder_rung_definitions(usgs))
    # KRDU: NCPHASE3 (0.9525 m, boxed to NC) sorts after the pinned
    # USGS 1 m and before every 1 m / 3 m rung; no other holder joins.
    krdu = _codes(INSETS._ladder_rung_definitions(usgs, KRDU_BOX))
    assert krdu == [chain[0], ("NCPHASE3", "NCPHASE3")] + chain[1:]
    # KGRK: TEXAS1M (1 m, priority 90) ties the chain's 1 m rungs and
    # sorts AFTER them ("USGS when USGS has it": the chain sorts as
    # USGS3DEP 100), before the 3 m rung.
    kgrk = _codes(INSETS._ladder_rung_definitions(usgs, KGRK_BOX))
    assert kgrk == chain[:4] + [("TEXAS1M", "TEXAS1M")] + chain[4:]
    assert [code for (_l, code) in kgrk[1:4]] == [
        "PITKIN1M", "USGSOPR", "USGSLPC"]
    # The controls: no member's box reaches them -- the rung list is the
    # chain's, unchanged (KASE: PITKIN1M stays rung 1).
    for icao, box in CONTROL_BOXES.items():
        assert _codes(INSETS._ladder_rung_definitions(usgs, box)) == chain, \
            icao
    assert chain[1] == ("Pitkin County 2016 lidar", "PITKIN1M")


def test_member_needs_the_key_a_box_and_enabled(monkeypatch):
    chain = {"code": "ROOT", "priority": 100.0, "native_resolution_m": 1.0,
             "resolution_ladder_rungs": INSETS._parse_resolution_ladder(
                 "3|three|u3;10|ten|u10")}
    def member(code, **keys):
        definition = {"code": code, "role": ea_definitions.ROLE_AIRPORT_INSET,
                      "enabled": True, "priority": 90.0,
                      "native_resolution_m": 2.0, "ladder_member": True,
                      "coverage_bboxes": [(0.0, 0.0, 1.0, 1.0)]}
        definition.update(keys)
        return definition
    registry = {
        "ROOT": chain,
        "INBOX": member("INBOX"),
        "FAR": member("FAR", coverage_bboxes=[(50.0, 50.0, 51.0, 51.0)]),
        "NOBOX": member("NOBOX", coverage_bboxes=[]),
        "OFF": member("OFF", enabled=False),
        "NOTMEMBER": member("NOTMEMBER", ladder_member=False),
        "BASE": member("BASE", role="base"),
        "FINEHIGH": member("FINEHIGH", native_resolution_m=1.0,
                           priority=200.0),
    }
    monkeypatch.setattr(INSETS, "elevation_providers_dict", registry)
    rungs = INSETS._ladder_rung_definitions(chain, (0.2, 0.2, 0.3, 0.3))
    assert [d["code"] for (_l, d) in rungs] == [
        "ROOT", "FINEHIGH", "INBOX", "ROOT", "ROOT"]
    assert [d.get("native_resolution_m") for (_l, d) in rungs] == [
        1.0, 1.0, 2.0, 3.0, 10.0]
    # Outside every member box: the chain alone, in file order.
    rungs = INSETS._ladder_rung_definitions(chain, (5.0, 5.0, 6.0, 6.0))
    assert [label for (label, _d) in rungs] == [
        "1 m", "three", "ten"]


@requires_gdal
def test_member_rung_delivers_and_out_of_box_member_is_no_row(
        tmp_path, two_providers):
    plan, calls, chain, _other, _raise = two_providers
    holder = {"code": "FAKEHOLD", "access_strategy": OTHER_STRATEGY,
              "role": ea_definitions.ROLE_AIRPORT_INSET, "enabled": True,
              "priority": 0.25, "native_resolution_m": 2.0,
              "ladder_member": True,
              "coverage_bboxes": [(-107.0, 39.0, -106.5, 39.5)]}
    INSETS.elevation_providers_dict["FAKEHOLD"] = holder
    plan.update({"FAKE3DEP:1": {"valid": 0.0, "listing": ["u1"]},
                 "FAKEPIT": {"unavailable": "laspy missing"},
                 "FAKE3DEP:2": {"valid": 1.0, "listing": ["H1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    provenance = INSETS.fetch_inset(chain, BOX, 1.0,
                                    str(tmp_path / "KASE_fake3dep.tif"),
                                    resolution_ladder=True)
    ladder = provenance["ladder"]
    assert ladder["delivered_provider"] == "FAKEHOLD"
    assert ladder["delivered_rung"] == 2
    assert [(r["provider"], r["outcome"]) for r in ladder["rungs_tried"]] \
        == [("FAKE3DEP", "below-threshold"), ("FAKEPIT", "unavailable"),
            ("FAKEHOLD", "delivered")]
    # Outside the member's box: no row and no call -- unlike the
    # explicit FAKEPIT line, which keeps its out-of-coverage row.
    calls["fetch"].clear()
    madrid = (-3.6, 40.4, -3.5, 40.5)
    provenance = INSETS.fetch_inset(chain, madrid, 1.0,
                                    str(tmp_path / "LEMD_fake3dep.tif"),
                                    resolution_ladder=True)
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKE3DEP:10"]
    assert [r["provider"] for r in provenance["ladder"]["rungs_tried"]] == [
        "FAKE3DEP", "FAKEPIT", "FAKE3DEP"]


@requires_gdal
def test_recheck_asks_a_global_member(two_providers):
    """An inset the 10 m rung delivered re-asks the finer global member's
    discovery too: a holder product listed later is a new listing."""
    plan, calls, chain, _other, _raise = two_providers
    INSETS.elevation_providers_dict["FAKEHOLD"] = {
        "code": "FAKEHOLD", "access_strategy": OTHER_STRATEGY,
        "role": ea_definitions.ROLE_AIRPORT_INSET, "enabled": True,
        "priority": 0.25, "native_resolution_m": 2.0, "ladder_member": True,
        "coverage_bboxes": [(-107.0, 39.0, -106.5, 39.5)]}
    plan.update({"FAKE3DEP:1": {"valid": None, "listing": []},
                 "FAKEPIT": {"valid": None, "listing": []},
                 "FAKE3DEP:2": {"valid": None, "listing": []},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    assert _sidecar()["ladder"]["delivered_rung"] == 3
    plan["FAKE3DEP:2"] = {"valid": 1.0, "listing": ["H2025"]}
    recheck = INSETS.ladder_recheck(39, -107, "KASE", "FAKE3DEP", BOX)
    assert recheck["result"] == "new-listing"
    assert recheck["new_source_ids"] == ["H2025"]
    assert 2 in recheck["rungs_checked"]


def test_surround_never_takes_a_polygon_post_portal():
    assert not INSETS._rung_can_be_surround(
        {"access_strategy": "aoi_zip_download"})
    assert INSETS._rung_can_be_surround({"access_strategy": "direct_cog"})


def test_rung_row_records_units_and_bytes(tmp_path):
    """Spec §1/§2: a rung row names the source unit, the unit the cells
    were converted to, and the bytes fetched; a pre-key rung gains no
    key."""
    attempt = {}
    INSETS._record_rung_units_and_bytes(
        attempt, {"vertical_unit_source": "ftUS",
                  "vertical_unit_applied": "m", "bytes_fetched": 41},
        str(tmp_path / "absent.tif"))
    assert attempt == {"vertical_unit_source": "ftUS",
                       "vertical_unit_applied": "m", "bytes_fetched": 41}
    attempt = {}
    INSETS._record_rung_units_and_bytes(
        attempt, {"vertical_unit_source": []}, str(tmp_path / "absent.tif"))
    assert attempt == {}


@requires_gdal
def test_unavailable_rung_zero_climbs(tmp_path, two_providers):
    """Spec §1 outcome table + RULINGS 2026-09-30bu (1): an undecodable
    USGS 1 m product (rung 0 ``unavailable``, #157) no longer skips the
    coarser rungs -- the ladder climbs and delivers the 10 m rung; the
    rung-0 row records the reason."""
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"unavailable": "undecodable zip member"},
                 "FAKEPIT": {"valid": None, "listing": []},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    destination = str(tmp_path / "KASE_fake3dep.tif")
    provenance = INSETS.fetch_inset(chain, BOX, 1.0, destination,
                                    resolution_ladder=True)
    tried = provenance["ladder"]["rungs_tried"]
    assert [r["outcome"] for r in tried] == [
        "unavailable", "no-coverage", "delivered"]
    assert tried[0]["unavailable_reason"] == "undecodable zip member"
    assert provenance["ladder"]["delivered_rung"] == 2
    assert os.path.isfile(destination)


@requires_gdal
def test_unavailable_rung_zero_with_nothing_else_stays_unavailable(
        tmp_path, two_providers):
    """...and when no other rung lists anything the provider's answer is
    still ``unavailable`` (13b) -- never a durable no-coverage."""
    plan, calls, chain, _other, _raise = two_providers
    plan.update({"FAKE3DEP:1": {"unavailable": "undecodable zip member"},
                 "FAKEPIT": {"valid": None, "listing": []},
                 "FAKE3DEP:10": {"valid": None, "listing": []}})
    with pytest.raises(ea_base.ProviderUnavailable):
        INSETS.fetch_inset(chain, BOX, 1.0,
                           str(tmp_path / "KASE_fake3dep.tif"),
                           resolution_ladder=True)
    assert calls["fetch"] == ["FAKE3DEP:1", "FAKEPIT", "FAKE3DEP:10"]
