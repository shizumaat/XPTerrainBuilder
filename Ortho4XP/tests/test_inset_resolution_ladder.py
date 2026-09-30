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

    @INSETS.register_access_strategy(STRATEGY)
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
        INSETS.ACCESS_STRATEGIES.pop(STRATEGY, None)


def _definition():
    return {
        "code": "FAKE3DEP",
        "access_strategy": STRATEGY,
        "role": INSETS.ROLE_AIRPORT_INSET,
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
    assert INSETS.inset_valid_fraction(destination) == 1.0
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
    plan.update({1.0: 0.0, 3.0: INSETS.TransientFetchError("outage")})
    destination = str(tmp_path / "a.tif")
    with pytest.raises(INSETS.TransientFetchError):
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
    # 30aw (2): USGS 1 m -> PITKIN1M 1 m -> USGS 3 m -> USGS 10 m.
    assert [r["native_resolution_m"] for r in rungs] == [1.0, 3.0, 10.0]
    assert rungs[0]["provider"] == "PITKIN1M"
    assert "discovery_url_template" not in rungs[0]
    assert all("{west}" in r["discovery_url_template"] for r in rungs[1:])
    assert "1/3 arc-second" in rungs[-1]["discovery_url_template"]
    assert usgs["native_resolution_m"] == 1.0          # rung 0 untouched
    resolved = INSETS._ladder_rung_definitions(usgs)
    assert [(d["code"], d["access_strategy"]) for _l, d in resolved] == [
        ("USGS3DEP", "tnm_cog"), ("PITKIN1M", "las_tile_index"),
        ("USGS3DEP", "tnm_cog"), ("USGS3DEP", "tnm_cog")]


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
                raise INSETS.TransientFetchError("index outage")
            listing = plan.get(key, {}).get("listing") or []
            return [{"source_id": i} for i in listing] or None

        def fetch(self, definition, bounding_box_wgs84,
                  target_resolution_m, destination_path):
            key = _key(definition)
            calls["fetch"].append(key)
            entry = plan.get(key) or {}
            if entry.get("unavailable"):
                raise INSETS.ProviderUnavailable(entry["unavailable"])
            if entry.get("valid") is None:
                return None
            _write_raster(destination_path, entry["valid"])
            return {
                "provider": definition["code"],
                "native_resolution_m": definition["native_resolution_m"],
                "resolution_m": target_resolution_m,
                "source_ids": list(entry.get("listing") or []),
                "sources_used": [{"source_id": i}
                                 for i in entry.get("listing") or []],
            }

    INSETS.register_access_strategy(STRATEGY)(type("_A", (_Base,), {}))
    INSETS.register_access_strategy(OTHER_STRATEGY)(type("_B", (_Base,), {}))
    chain = {
        "code": "FAKE3DEP",
        "access_strategy": STRATEGY,
        "role": INSETS.ROLE_AIRPORT_INSET,
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
        "role": INSETS.ROLE_AIRPORT_INSET,
        "enabled": True,
        "priority": 0.5,
        "native_resolution_m": 1.0,
        "coverage_bbox": "-107.4,38.95,-106.3,39.55",
    }
    other["coverage_bboxes"] = INSETS._parse_bounding_boxes(
        other["coverage_bbox"])
    monkeypatch.setattr(INSETS, "elevation_providers_dict",
                        {"FAKE3DEP": chain, "FAKEPIT": other})
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    try:
        yield plan, calls, chain, other, discover_raise
    finally:
        INSETS.ACCESS_STRATEGIES.pop(STRATEGY, None)
        INSETS.ACCESS_STRATEGIES.pop(OTHER_STRATEGY, None)


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
