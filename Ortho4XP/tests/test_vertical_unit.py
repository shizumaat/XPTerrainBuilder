"""THE VERTICAL-UNIT KEY and the CAP CLASS (spec us-holder-providers §2/§3,
RULINGS 2026-09-30bm, issue #154, lane vunit154).

A feet raster used to bake at 3.28x (the shared warp never rescaled Z) and
its sanitizer voided every cell above 12,000 -- 3,658 m real.  The key
``vertical_unit=m|ft|ftUS`` is applied at ONE site, the warp's post-warp
array pass, BEFORE the garbage test; a compound CRS that contradicts it
refuses as ``ProviderUnavailable``; the delivered raster is stamped and the
stamp rides into the provenance; the two-layer assembler refuses a unit
mismatch; a pre-key record of a unit-bearing raster provider is void.
Without the key the warp is a strict no-op (no CRS probe, no scale, no
stamp).  A per-airport cap exceeded is ``unavailable``, never ``None`` and
never a silent truncation.  No network.
"""

import json
import os

import numpy
import pytest

import O4_Airport_Elevation_Insets as INSETS
from tests.inset_code import patch_inset_code
from elevation_access import base as ea_base
from elevation_access import capabilities as ea_capabilities
from elevation_access import registry as ea_registry
from elevation_access.strategies import las_tile_index as ea_las_tile_index
from elevation_access import vertical_units as ea_vertical_units
from elevation_access import warp as ea_warp

try:
    from osgeo import gdal, osr

    gdal.UseExceptions()
    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

pytestmark = pytest.mark.skipif(not HAS_GDAL, reason="no osgeo")

BOX = (-78.80, 35.86, -78.77, 35.89)          # KRDU-sized, NC Phase 3 land
SIZE = 40
SOURCE_NODATA = -999999.0                     # NC Phase 3's fill


def _plane(size=SIZE):
    rows, cols = numpy.mgrid[0:size, 0:size]
    return (400.0 + 3.0 * rows + 2.0 * cols).astype(numpy.float32)


def _write_source(path, values, srs_text="EPSG:4326", nodata=SOURCE_NODATA,
                  box=BOX):
    size = values.shape[0]
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), size, size, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform(
        (box[0], (box[2] - box[0]) / size, 0.0, box[3], 0.0,
         -(box[3] - box[1]) / size))
    srs = osr.SpatialReference()
    srs.SetFromUserInput(srs_text)
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.WriteArray(values)
    dataset = None
    return str(path)


def _feet_source_with_holes(path, srs_text="EPSG:4326"):
    values = _plane()
    values[5:9, 5:9] = SOURCE_NODATA
    values[30:33, 12:20] = SOURCE_NODATA
    return _write_source(path, values, srs_text)


def _warp(sources, destination, vertical_unit=None, **kwargs):
    kwargs.setdefault("provider_code", "NCTEST")
    return ea_warp.warp_vsicurl_sources_to_geotiff(
        sources, BOX, 20.0, str(destination), vertical_unit=vertical_unit,
        **kwargs)


def _read(path):
    dataset = gdal.Open(str(path))
    values = dataset.GetRasterBand(1).ReadAsArray().astype(numpy.float64)
    metadata = dataset.GetMetadata() or {}
    dataset = None
    return values, metadata


# ---------------------------------------------------------------- the table
def test_unit_factors_are_exact_and_shared():
    assert ea_vertical_units.VERTICAL_UNIT_TO_M["ftUS"] == 1200.0 / 3937.0
    assert ea_vertical_units.VERTICAL_UNIT_TO_M["ft"] == 0.3048
    assert ea_vertical_units.VERTICAL_UNIT_TO_M["m"] == 1.0
    # ONE table: the LAS gridder reads the same object.
    assert ea_las_tile_index.LAS_UNIT_TO_M is ea_vertical_units.VERTICAL_UNIT_TO_M


# ------------------------------------------------------------ the warp site
@pytest.mark.parametrize("unit", ["ftUS", "ft"])
def test_feet_raster_bakes_at_the_unit_factor_with_holes_kept(tmp_path, unit):
    source = _feet_source_with_holes(tmp_path / "src.tif")
    assert _warp([source], tmp_path / "raw.tif")
    assert _warp([source], tmp_path / "metres.tif", vertical_unit=unit)
    (raw, raw_meta) = _read(tmp_path / "raw.tif")
    (metres, meta) = _read(tmp_path / "metres.tif")
    raw_valid = raw != -32768.0
    # The holes stay -32768, cell for cell.
    assert numpy.array_equal(raw_valid, metres != -32768.0)
    assert (~raw_valid).any()
    factor = ea_vertical_units.VERTICAL_UNIT_TO_M[unit]
    assert numpy.max(numpy.abs(metres[raw_valid] - raw[raw_valid] * factor)) \
        < 1e-3
    assert meta[ea_vertical_units.VERTICAL_UNIT_STAMP_DECLARED] == unit
    assert meta[ea_vertical_units.VERTICAL_UNIT_STAMP_SOURCE] == "elv"
    assert meta[ea_vertical_units.VERTICAL_UNIT_STAMP_APPLIED] == "m"
    assert not any(key.startswith("O4_VERTICAL_UNIT") for key in raw_meta)


def test_ceiling_is_judged_in_metres(tmp_path):
    # 13,000 ftUS = 3,962 m: a real summit the pre-key sanitizer voided.
    values = numpy.full((SIZE, SIZE), 13000.0, dtype=numpy.float32)
    source = _write_source(tmp_path / "high.tif", values)
    assert _warp([source], tmp_path / "old.tif")
    assert _warp([source], tmp_path / "new.tif", vertical_unit="ftUS")
    (old, _meta) = _read(tmp_path / "old.tif")
    (new, _meta) = _read(tmp_path / "new.tif")
    assert (old == -32768.0).all()
    assert numpy.allclose(new, 13000.0 * 1200.0 / 3937.0, atol=1e-2)


def test_no_key_is_a_strict_no_op(tmp_path, monkeypatch):
    def _probe_called(*_args, **_kwargs):
        raise AssertionError("the source CRS was probed without a key")

    patch_inset_code(monkeypatch, "resolve_warp_vertical_unit", _probe_called)
    source = _feet_source_with_holes(tmp_path / "src.tif")
    assert ea_warp.warp_vsicurl_sources_to_geotiff(
        [source], BOX, 20.0, str(tmp_path / "a.tif"))
    assert _warp([source], tmp_path / "b.tif", vertical_unit=None)
    with open(tmp_path / "a.tif", "rb") as a, open(tmp_path / "b.tif",
                                                   "rb") as b:
        assert a.read() == b.read()
    assert INSETS.raster_vertical_unit_stamp(str(tmp_path / "a.tif")) is None
    assert INSETS.raster_vertical_unit_held(str(tmp_path / "a.tif")) == "m"


# --------------------------------------------------------------- refusals
def test_declared_metre_compound_crs_refuses_a_feet_key(tmp_path):
    source = _feet_source_with_holes(tmp_path / "m.tif",
                                     srs_text="EPSG:6318+5703")
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        _warp([source], tmp_path / "out.tif", vertical_unit="ftUS")
    assert str(caught.value) == (
        "NCTEST: .elv vertical_unit=ftUS but %s declares metre" % source)
    # Refused BEFORE the warp: nothing was written.
    assert not os.path.exists(tmp_path / "out.tif")


def test_metre_key_on_a_feet_compound_crs_refuses(tmp_path):
    source = _feet_source_with_holes(tmp_path / "ft.tif",
                                     srs_text="EPSG:6318+6360")
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="vertical_unit=m but .* declares US survey foot"):
        _warp([source], tmp_path / "out.tif", vertical_unit="m")


def test_agreeing_compound_crs_is_recorded_as_elv_eq_crs(tmp_path):
    source = _feet_source_with_holes(tmp_path / "ft.tif",
                                     srs_text="EPSG:6318+6360")
    assert _warp([source], tmp_path / "out.tif", vertical_unit="ftUS")
    stamp = INSETS.raster_vertical_unit_stamp(str(tmp_path / "out.tif"))
    assert stamp == {"declared": "ftUS", "source": "elv=crs",
                     "applied": "m"}


def test_mixed_declared_units_across_one_mosaic_refuse(tmp_path):
    a = _feet_source_with_holes(tmp_path / "a.tif", srs_text="EPSG:6318+6360")
    b = _feet_source_with_holes(tmp_path / "b.tif", srs_text="EPSG:6318+5703")
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="declare different vertical units"):
        _warp([a, b], tmp_path / "out.tif", vertical_unit="ftUS")


def test_unknown_unit_is_unavailable_not_a_guess():
    with pytest.raises(ea_base.ProviderUnavailable, match="furlong"):
        ea_vertical_units._raster_vertical_unit({"code": "X", "vertical_unit": "furlong"})
    assert ea_vertical_units._raster_vertical_unit({"code": "X"}) is None


# -------------------------------------------------------------- provenance
def test_fetch_inset_lifts_the_stamp_into_the_provenance(tmp_path,
                                                         monkeypatch):
    source = _feet_source_with_holes(tmp_path / "src.tif")

    class _Feet:
        def discover(self, definition, box):
            return [{"source_id": "s"}]

        def fetch(self, definition, box, resolution, destination):
            assert ea_warp.warp_vsicurl_sources_to_geotiff(
                [source], box, resolution, destination,
                vertical_unit=ea_vertical_units._raster_vertical_unit(definition),
                provider_code=definition.get("code"))
            return {"provider": definition["code"]}

    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "vunit_fake", _Feet)
    feet = INSETS.fetch_inset(
        {"code": "NCTEST", "access_strategy": "vunit_fake",
         "vertical_unit": "ftUS"}, BOX, 20.0, str(tmp_path / "f.tif"))
    assert feet["vertical_unit_source"] == "elv"
    assert feet["vertical_unit_applied"] == "m"
    metres = INSETS.fetch_inset(
        {"code": "MTEST", "access_strategy": "vunit_fake"}, BOX, 20.0,
        str(tmp_path / "m.tif"))
    assert "vertical_unit_source" not in metres
    assert "vertical_unit_applied" not in metres


# ---------------------------------------------------------- two-layer gate
def _stamp(path, **items):
    dataset = gdal.Open(str(path), gdal.GA_Update)
    for (key, value) in items.items():
        dataset.SetMetadataItem(key, value)
    dataset = None


def test_two_layer_assembler_refuses_a_unit_mismatch(tmp_path):
    core = _write_source(tmp_path / "core.tif", _plane(), nodata=-32768.0)
    surround = _write_source(tmp_path / "surround.tif", _plane(),
                             nodata=-32768.0)
    # A core that DECLARES feet and was never applied: the KASE class.
    _stamp(core, **{ea_vertical_units.VERTICAL_UNIT_STAMP_DECLARED: "ftUS"})
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="core holds ftUS"):
        INSETS.assemble_ladder_inset(core, [(surround, {"label": "s"})],
                                     str(tmp_path / "out.tif"), None,
                                     0.0, 30.0)
    assert not os.path.exists(tmp_path / "out.tif")


def test_ladder_assembler_refuses_a_feet_fill(tmp_path):
    core = _write_source(tmp_path / "core.tif", _plane(), nodata=-32768.0)
    surround = _write_source(tmp_path / "surround.tif", _plane(),
                             nodata=-32768.0)
    _stamp(surround, **{ea_vertical_units.VERTICAL_UNIT_STAMP_DECLARED: "ftUS"})
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="fill 's' holds ftUS"):
        INSETS.assemble_ladder_inset(core, [(surround, {"label": "s"})],
                                     str(tmp_path / "out.tif"), None,
                                     0.0, 30.0)
    assert not os.path.exists(tmp_path / "out.tif")


def test_two_layer_assembler_carries_the_core_stamp(tmp_path):
    core = _write_source(tmp_path / "core.tif", _plane(), nodata=-32768.0)
    surround = _write_source(tmp_path / "surround.tif", _plane(),
                             nodata=-32768.0)
    _stamp(core, **{ea_vertical_units.VERTICAL_UNIT_STAMP_DECLARED: "ftUS",
                    ea_vertical_units.VERTICAL_UNIT_STAMP_SOURCE: "elv",
                    ea_vertical_units.VERTICAL_UNIT_STAMP_APPLIED: "m"})
    out = str(tmp_path / "out.tif")
    INSETS.assemble_ladder_inset(core, [(surround, {"label": "s"})], out,
                                 None, 0.0, 30.0)
    assert INSETS.raster_vertical_unit_stamp(out) == {
        "declared": "ftUS", "source": "elv", "applied": "m"}


# ------------------------------------------------------- pre-key sidecars
def _cached_inset(tmp_path, record):
    inset = _write_source(tmp_path / "KRDU_NCTEST.tif", _plane(),
                          nodata=-32768.0)
    with open(tmp_path / "KRDU_NCTEST.json", "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump(record, handle)
    return inset


def test_pre_key_sidecar_of_a_feet_raster_provider_is_void(tmp_path):
    inset = _cached_inset(tmp_path, {"provider": "NCTEST"})
    feet = {"code": "NCTEST", "access_strategy": "direct_cog",
            "vertical_unit": "ftUS"}
    reason = INSETS._void_inset_record_reason(inset, feet)
    assert reason is not None and "vertical_unit_applied" in reason
    # Without the definition (or for a metre provider) nothing changes.
    assert INSETS._void_inset_record_reason(inset) is None
    assert INSETS._void_inset_record_reason(
        inset, {"code": "NCTEST", "access_strategy": "direct_cog"}) is None
    # The point-cloud key is the POINT unit, applied while gridding.
    assert INSETS._void_inset_record_reason(
        inset, dict(feet, access_strategy="las_tile_index")) is None


def test_post_key_sidecar_stands(tmp_path):
    inset = _cached_inset(tmp_path, {"provider": "NCTEST",
                                     "vertical_unit_source": "elv",
                                     "vertical_unit_applied": "m"})
    assert INSETS._void_inset_record_reason(
        inset, {"code": "NCTEST", "access_strategy": "direct_cog",
                "vertical_unit": "ftUS"}) is None


# --------------------------------------------------------- the cap class
def test_lerc_tile_cap_is_unavailable_not_no_coverage(tmp_path, monkeypatch):
    patch_inset_code(monkeypatch, "lerc_decode_available", lambda: True)
    definition = {"code": "HILLSTEST", "access_strategy": "arcgis_lerc_tiles",
                  "tile_url_template": "https://example.invalid/{z}/{y}/{x}",
                  "tile_level": 17}
    destination = str(tmp_path / "KTPA_HILLSTEST.tif")
    big_box = (-82.60, 27.90, -82.45, 28.05)       # > 1,024 tiles at L17
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        ea_registry.ACCESS_STRATEGIES["arcgis_lerc_tiles"]().fetch(
            definition, big_box, 1.0, destination)
    text = str(caught.value)
    assert text.startswith("HILLSTEST: KTPA needs ")
    assert "cap 1024 tiles (max_tiles_per_airport in HILLSTEST.elv)" in text
    assert "recorded unavailable, not no-coverage" in text


def test_feature_archive_cap_is_unavailable_never_a_silent_slice(
        tmp_path, monkeypatch):
    strategy_class = ea_registry.ACCESS_STRATEGIES["arcgis_feature_tiles"]
    listing = [{"url": "https://example.invalid/%d.zip" % n}
               for n in range(9)]
    monkeypatch.setattr(strategy_class, "discover",
                        lambda self, definition, box: list(listing))
    definition = {"code": "TXTEST", "access_strategy": "arcgis_feature_tiles"}
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        strategy_class().fetch(definition, BOX, 1.0,
                               str(tmp_path / "KGRK_TXTEST.tif"))
    assert ("TXTEST: KGRK needs 9 archives, cap 8 "
            "(max_archives_per_airport in TXTEST.elv)") in str(caught.value)
    # The key raises the cap: 9 archives under max_archives_per_airport=16
    # pass the gate.  A listed archive that then fails to download is a
    # TRANSIENT raise (lane tx154, spec §7): skipping it would deliver a
    # partial mosaic as the whole, and returning None would record a
    # durable no-coverage for a network failure.
    import requests

    def _refused(*_args, **_kwargs):
        raise requests.ConnectionError("no network in the suite")

    monkeypatch.setattr(requests, "get", _refused)
    with pytest.raises(ea_base.TransientFetchError):
        strategy_class().fetch(
            dict(definition, max_archives_per_airport="16"), BOX, 1.0,
            str(tmp_path / "KGRK_TXTEST.tif"))


def test_tile_grid_cap_is_unavailable(tmp_path):
    definition = {"code": "GRIDTEST", "access_strategy": "tile_grid_http",
                  "source_epsg": 25832, "tile_size_km": 1,
                  "tile_url_template": "https://example.invalid/{e}_{n}.tif"}
    wide_box = (9.0, 50.0, 9.3, 50.2)               # ~21 x 22 km of 1 km tiles
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="cap 120 tiles \\(max_tiles_per_airport"):
        ea_registry.ACCESS_STRATEGIES["tile_grid_http"]().discover(
            definition, wide_box)


def test_truncated_wfs_listing_is_unavailable(monkeypatch):
    import requests

    class _Response:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        text = "{}"

        def json(self):
            return {"numberMatched": 300, "numberReturned": 120,
                    "features": [{"properties": {"url": "u%d" % n}}
                                 for n in range(120)]}

    monkeypatch.setattr(requests, "get", lambda *a, **k: _Response())
    definition = {"code": "WFSTEST", "access_strategy": "wfs_tile_index",
                  "wfs_service_url": "https://example.invalid/wfs",
                  "wfs_type_name": "t"}
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="needs 300 tiles \\(the WFS returned 120\\)"):
        ea_registry.ACCESS_STRATEGIES["wfs_tile_index"]().discover(definition, BOX)
