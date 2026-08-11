"""Round 13 — border-aware inset fetching: valid data outranks a newer
date (docs/specs/round13-border-aware-inset-fetch-spec.md).

Synthetic rasters only: no network, no X-Plane install, no write outside
``tmp_path``.  The discovery API is replaced by a stub and the sources it
returns are local GeoTIFFs, so the mosaic under test is the REAL
``gdal.Warp`` assembly production runs — the whole question here is what
GDAL does with a source that is nodata over half the box.

* **R13-1** a fetch record without a valid raster is NO record: the
  sidecar is archived as ``<name>.json.invalid-<date>`` (evidence, not
  deletion) and the fetch runs again.  A record with a valid raster is
  left alone, byte for byte.
* **R13-2** every pixel takes the NEWEST source with valid data THERE —
  the Kansas-project-wins-wholesale mechanism that cut KMCI's 100 %
  nodata inset.
* **R13-3** the record names its sources per contribution
  (``sources_used`` / ``sources_empty_over_bbox`` / ``valid_fraction``),
  and a mix of vertical datums refuses loudly instead of averaging one
  into the other.
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
except Exception:
    HAS_GDAL = False

requires_gdal = pytest.mark.skipif(
    not HAS_GDAL, reason="osgeo (GDAL python bindings) not available"
)

BBOX = (0.0, 0.0, 1.0, 1.0)          # (west, south, east, north)
NODATA = -32768.0
TILE = (0, 0)
DEFINITION = {
    "code": "USGS3DEP",
    "access_strategy": "tnm_cog",
    "role": INSETS.ROLE_AIRPORT_INSET,
    "enabled": True,
    "priority": 1.0,
    "native_resolution_m": 1,
    "vertical_datum": "NAVD88",
    "license": "Public Domain (U.S. Geological Survey)",
}


# =====================================================================
# Helpers
# =====================================================================
def _write_geotiff(path, values, bounding_box=BBOX):
    """An EPSG:4326 float32 GeoTIFF over ``bounding_box`` with nodata set."""
    (west, south, east, north) = bounding_box
    (rows, columns) = values.shape
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, columns, rows, 1, gdal.GDT_Float32
    )
    dataset.SetGeoTransform(
        (west, (east - west) / columns, 0.0,
         north, 0.0, (south - north) / rows)
    )
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    dataset.SetProjection(spatial_reference.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(values.astype(numpy.float32))
    band.FlushCache()
    dataset = None
    INSETS._inset_valid_fraction_cache.clear()
    return path


def _values_of(path):
    dataset = gdal.Open(path)
    values = dataset.GetRasterBand(1).ReadAsArray()
    dataset = None
    return values


def _source(directory, name, values, publication_date, title,
            **extra):
    """One discovered source whose ``download_url`` is a local raster."""
    path = _write_geotiff(os.path.join(str(directory), name + ".tif"), values)
    source = {
        "download_url": path,
        "source_id": name,
        "title": title,
        "publication_date": publication_date,
        "bounding_box": list(BBOX),
    }
    source.update(extra)
    return source


def _local_strategy(monkeypatch, sources):
    """The production strategy with local rasters standing in for COGs.

    Only the transport is faked: ``_warp_input_for`` drops the
    ``/vsicurl/`` prefix, and discovery returns the given sources.  The
    ordering, the mosaic and the per-source probe are the shipped code.
    """
    strategy_class = INSETS.TnmCloudOptimizedGeoTiffStrategy
    monkeypatch.setattr(
        strategy_class, "discover",
        lambda self, definition, bounding_box: list(sources),
    )
    monkeypatch.setattr(
        strategy_class, "_warp_input_for",
        lambda self, source: source["download_url"],
    )
    return strategy_class()


def _half_and_half(east_value=NODATA, west_value=200.0, size=40):
    """Valid over the WEST half, ``east_value`` over the east half."""
    values = numpy.full((size, size), west_value)
    values[:, size // 2:] = east_value
    return values


# =====================================================================
# R13-1 — a fetch record without a valid raster is no record
# =====================================================================
def _record_invalidation_arm(tmp_path, monkeypatch, icao, raster_values):
    """Run one fetch pass for ``icao`` with a pre-seeded record.

    ``raster_values`` is ``None`` for the orphan-sidecar case (a json with
    no ``.tif`` beside it — KMCI's state on 2026-08-11).  Returns the
    resolutions the fetch was asked for (empty = the cache was reused).
    """
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    directory = FNAMES.airport_inset_directory(*TILE)
    os.makedirs(directory, exist_ok=True)
    destination = FNAMES.airport_inset_dem(*TILE, icao, "USGS3DEP")
    if raster_values is not None:
        _write_geotiff(destination, raster_values)
    with open(FNAMES.airport_inset_provenance(*TILE, icao, "USGS3DEP"),
              "w") as handle:
        json.dump({"provider": "USGS3DEP",
                   "project_titles": ["USGS 1 Meter KS_Statewide_2018_A18"]},
                  handle, indent=2, sort_keys=True)

    fetched = []

    def _fetch(definition, bounding_box, target_resolution_m, path,
               footprint_prefetch=None):
        fetched.append(target_resolution_m)
        _write_geotiff(path, numpy.full((40, 40), 300.0))
        return {"provider": definition["code"], "valid_fraction": 1.0}

    monkeypatch.setattr(INSETS, "fetch_inset", _fetch)
    INSETS.ensure_airport_insets(
        TILE[0], TILE[1], {icao: BBOX}, [DEFINITION], None
    )
    return (fetched, directory, destination)


@requires_gdal
def test_a_record_whose_raster_is_gone_or_empty_refetches(
    tmp_path, monkeypatch, capsys
):
    """R13-1, both void shapes: the orphan sidecar (KMCI's own state) and
    the sidecar beside a 0 %-valid raster.  Each is archived under its
    own name and the fetch RUNS — no hand-deleted json anywhere."""
    (fetched, directory, destination) = _record_invalidation_arm(
        tmp_path, monkeypatch, "KMCI", None
    )
    stamp = INSETS.datetime.date.today().isoformat()
    assert fetched == [1.0]                       # the fetch ran
    assert os.path.isfile(
        os.path.join(directory, "KMCI_usgs3dep.json.invalid-" + stamp))
    assert os.path.isfile(destination)
    printed = capsys.readouterr().out
    assert "the raster it recorded is gone" in printed

    (fetched, directory, destination) = _record_invalidation_arm(
        tmp_path, monkeypatch, "KSTJ", numpy.full((40, 40), NODATA)
    )
    assert fetched == [1.0]
    assert os.path.isfile(
        os.path.join(directory, "KSTJ_usgs3dep.json.invalid-" + stamp))
    # The refetched raster replaced the empty one.
    assert INSETS.inset_valid_fraction(destination) == 1.0
    assert "0.00 % valid pixels" in capsys.readouterr().out


@requires_gdal
def test_a_record_with_a_valid_raster_is_left_alone(tmp_path, monkeypatch):
    """The other side of the gate: a good cache is not re-fetched, its
    record is not archived, and its bytes do not move."""
    (fetched, directory, destination) = _record_invalidation_arm(
        tmp_path, monkeypatch, "KFLV", numpy.full((40, 40), 250.0)
    )
    sidecar = FNAMES.airport_inset_provenance(*TILE, "KFLV", "USGS3DEP")
    assert fetched == []
    assert [name for name in os.listdir(directory)
            if ".invalid-" in name] == []
    with open(sidecar, "r") as handle:
        assert json.load(handle)["provider"] == "USGS3DEP"
    assert numpy.all(_values_of(destination) == 250.0)


# =====================================================================
# R13-2 — every pixel takes the newest source with valid data there
# =====================================================================
@requires_gdal
def test_the_newer_source_wins_only_where_it_has_data(tmp_path, monkeypatch):
    """The border case.  The newer project is nodata over the east half of
    the box (Kansas over a Missouri airport); the older one covers
    everything.  The assembled inset is valid EVERYWHERE, west from the
    newer source and east from the older — and the record names both."""
    newer = _source(tmp_path, "newer", _half_and_half(),
                    "2023-06-12", "USGS 1 Meter 15 x34y435 KS_2018_A18")
    older = _source(tmp_path, "older", numpy.full((40, 40), 100.0),
                    "2018-01-01", "USGS 1 Meter 15 x34y435 MO_2016_B16")
    strategy = _local_strategy(monkeypatch, [newer, older])

    ordering = []
    original_warp = INSETS.warp_vsicurl_sources_to_geotiff

    def _recording_warp(inputs, *args, **kwargs):
        ordering.extend(inputs)
        return original_warp(inputs, *args, **kwargs)

    monkeypatch.setattr(
        INSETS, "warp_vsicurl_sources_to_geotiff", _recording_warp)

    destination = os.path.join(str(tmp_path), "KMCI_usgs3dep.tif")
    provenance = strategy.fetch(DEFINITION, BBOX, 3000.0, destination)

    # OLDEST first: gdal.Warp lets a later input win only where it holds
    # data, so this ordering is what makes "newest wins per pixel" true.
    assert ordering == [older["download_url"], newer["download_url"]]
    values = _values_of(destination)
    columns = values.shape[1]
    assert not numpy.any(values == NODATA)
    assert numpy.all(values[:, : columns // 2 - 1] == 200.0)   # newer
    assert numpy.all(values[:, columns // 2 + 1:] == 100.0)    # older
    assert provenance["valid_fraction"] == 1.0
    assert [entry["source_id"] for entry in provenance["sources_used"]] == [
        "newer", "older"
    ]
    assert provenance["sources_empty_over_bbox"] == []
    assert provenance["publication_date"] == "2023-06-12"


@requires_gdal
def test_a_source_empty_over_the_box_contributes_nothing_and_is_named(
    tmp_path, monkeypatch, capsys
):
    """KMCI in miniature: the NEWEST project holds no data at all here.
    It must neither win pixels nor vanish from the record."""
    newest = _source(tmp_path, "kansas", numpy.full((40, 40), NODATA),
                     "2023-06-12", "USGS 1 Meter 15 x34y435 KS_2018_A18")
    older = _source(tmp_path, "missouri", numpy.full((40, 40), 100.0),
                    "2018-01-01", "USGS 1 Meter 15 x34y435 MO_2016_B16")
    strategy = _local_strategy(monkeypatch, [newest, older])

    destination = os.path.join(str(tmp_path), "KMCI_usgs3dep.tif")
    provenance = strategy.fetch(DEFINITION, BBOX, 3000.0, destination)

    assert numpy.all(_values_of(destination) == 100.0)
    assert provenance["valid_fraction"] == 1.0
    assert [e["source_id"] for e in provenance["sources_used"]] == ["missouri"]
    assert [e["source_id"] for e in provenance["sources_empty_over_bbox"]] == [
        "kansas"
    ]
    # The flat keys name what CONTRIBUTED, so the empty project can no
    # longer pass itself off as the inset's source.
    assert provenance["project_titles"] == [older["title"]]
    assert provenance["publication_date"] == "2018-01-01"


@requires_gdal
def test_every_source_empty_lands_an_honest_record(tmp_path, monkeypatch):
    """R13-2's tail: with nothing valid anywhere the file still lands,
    carrying ``valid_fraction`` 0 and naming what was tried — R11's
    runtime refusal is the last line of defense, not this one."""
    kansas = _source(tmp_path, "kansas", numpy.full((40, 40), NODATA),
                     "2023-06-12", "USGS 1 Meter 15 x34y435 KS_2018_A18")
    nebraska = _source(tmp_path, "nebraska", numpy.full((40, 40), NODATA),
                       "2019-01-01", "USGS 1 Meter 15 x34y435 NE_2017_A17")
    strategy = _local_strategy(monkeypatch, [kansas, nebraska])

    destination = os.path.join(str(tmp_path), "KMCI_usgs3dep.tif")
    provenance = strategy.fetch(DEFINITION, BBOX, 3000.0, destination)

    assert os.path.isfile(destination)
    assert provenance["valid_fraction"] == 0.0
    assert provenance["sources_used"] == []
    assert [e["source_id"] for e in provenance["sources_empty_over_bbox"]] == [
        "kansas", "nebraska"
    ]
    # Nothing contributed, so the flat keys name what was TRIED — the
    # R11 empty-inset line still has a project to print.
    assert provenance["project_titles"] == [kansas["title"],
                                            nebraska["title"]]
    assert INSETS.inset_is_effectively_empty(destination)[0] is True


# =====================================================================
# R13-3 — the record names its sources; datums are never mixed
# =====================================================================
@requires_gdal
def test_a_multi_project_mosaic_says_so(tmp_path, monkeypatch, capsys):
    """The log line a border airport earns: N sources across M projects."""
    newer = _source(tmp_path, "kansas", _half_and_half(),
                    "2023-06-12", "USGS 1 Meter 15 x34y435 KS_2018_A18")
    older = _source(tmp_path, "missouri", numpy.full((40, 40), 100.0),
                    "2018-01-01", "USGS 1 Meter 15 x34y435 MO_2016_B16")
    strategy = _local_strategy(monkeypatch, [newer, older])

    strategy.fetch(DEFINITION, BBOX, 3000.0,
                   os.path.join(str(tmp_path), "KMCI_usgs3dep.tif"))
    printed = capsys.readouterr().out
    assert ("KMCI_usgs3dep.tif: border-aware mosaic - 2 source(s) across "
            "2 project(s), valid 100.0 %") in printed


@requires_gdal
def test_mixed_vertical_datums_refuse_the_mosaic(tmp_path, monkeypatch):
    """Heights may be mixed only inside ONE datum.  3DEP never trips this
    today — which is why it is asserted rather than assumed."""
    navd88 = _source(tmp_path, "navd88", numpy.full((40, 40), 100.0),
                     "2023-06-12", "USGS 1 Meter 15 x34y435 KS_2018_A18")
    ellipsoidal = _source(tmp_path, "ellipsoidal",
                          numpy.full((40, 40), 130.0),
                          "2018-01-01", "USGS 1 Meter 15 x34y435 MO_2016_B16",
                          vertical_datum="WGS84 ellipsoidal")
    strategy = _local_strategy(monkeypatch, [navd88, ellipsoidal])

    destination = os.path.join(str(tmp_path), "KMCI_usgs3dep.tif")
    with pytest.raises(ValueError) as raised:
        strategy.fetch(DEFINITION, BBOX, 3000.0, destination)
    message = str(raised.value)
    assert "NAVD88" in message and "WGS84 ellipsoidal" in message
    assert "REFUSING to mix heights" in message
    assert not os.path.isfile(destination)      # nothing was assembled


def test_the_project_name_is_read_off_the_product_title():
    """3DEP titles end in the project name; that is what a reader needs
    when two states meet over one airport."""
    assert INSETS._tnm_project_of(
        "USGS 1 Meter 15 x34y435 KS_Statewide_2018_A18"
    ) == "KS_Statewide_2018_A18"
    assert INSETS._tnm_project_of(None) == "?"
