"""Tests for the per-subsystem ``is_cached(tile)`` fetch predicates
(docs/specs/apron-string-and-scheduling-spec.md §A.2).

Each fetch subsystem answers for ITSELF whether a step would issue a
remote request; the scheduler never re-derives what a step reads.  The
contract every predicate must honour, and what these tests pin:

* cheap — filesystem/manifest only, never a network probe;
* conservative — anything it cannot decide reads as NOT cached;
* never raises — a predicate that blows up must read as not cached too.

Headless, no network, ``tmp_path``-based.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import parallel


# ---------------------------------------------------------------------
# The registry the scheduler asks through
# ---------------------------------------------------------------------
def test_every_named_subsystem_publishes_a_predicate():
    """The whole of the scheduler's knowledge is STEP_FETCH_SUBSYSTEMS;
    a name in it that publishes no ``is_cached`` would silently pin its
    step to "never cached" forever."""
    parallel.preload_cache_predicates()
    for step_key, module_names in parallel.STEP_FETCH_SUBSYSTEMS.items():
        for module_name in module_names:
            predicate = parallel._subsystem_is_cached(module_name)
            assert callable(predicate), (
                "%s (fetched by the %s step) publishes no is_cached"
                % (module_name, step_key))


def test_a_step_without_fetch_subsystems_is_trivially_cached():
    for step_key in ("mesh", "masks", "overlays"):
        assert parallel.tile_inputs_are_cached(object(), step_key) is True


def test_predicates_are_registered_for_both_fetch_steps():
    assert set(parallel.STEP_FETCH_SUBSYSTEMS) == {"vector", "imagery"}


# ---------------------------------------------------------------------
# Vector / OpenStreetMap extract
# ---------------------------------------------------------------------
def _write_osm_cache(path, schema=""):
    import bz2

    os.makedirs(os.path.dirname(path), exist_ok=True)
    root = '<osm version="0.6"'
    if schema:
        root += ' o4_tag_schema="%s"' % schema
    root += ">\n"
    with bz2.open(path, "wt") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        handle.write(root)
        handle.write("</osm>\n")


def test_vector_predicate_requires_every_layer_and_its_schema(
    monkeypatch, tmp_path
):
    import O4_File_Names as FNAMES
    import O4_Vector_Map as VMAP

    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    tile = SimpleNamespace(lat=10, lon=20)
    monkeypatch.setattr(
        VMAP, "osm_layer_warm_specifications",
        lambda t: [("airports", ["q"], ["all"], [], ""),
                   ("big_roads", ["q"], [], [], "2026-07-16")])
    # Nothing on disk, and no local extracts: not cached.
    monkeypatch.setattr(
        "O4_OSM_Extracts.local_extracts_cover", lambda bbox: False)
    assert VMAP.is_cached(tile) is False
    _write_osm_cache(FNAMES.osm_cached(10, 20, "airports"))
    assert VMAP.is_cached(tile) is False, "one layer still missing"
    # Present but stamped with the WRONG schema is not a hit.
    _write_osm_cache(FNAMES.osm_cached(10, 20, "big_roads"), "1999-01-01")
    assert VMAP.is_cached(tile) is False
    _write_osm_cache(FNAMES.osm_cached(10, 20, "big_roads"), "2026-07-16")
    assert VMAP.is_cached(tile) is True


def test_vector_predicate_accepts_local_extract_coverage(
    monkeypatch, tmp_path
):
    """A tile its build filters from stored regional extracts never
    reaches Overpass, so it holds no fetch token."""
    import O4_File_Names as FNAMES
    import O4_Vector_Map as VMAP

    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    monkeypatch.setattr(
        VMAP, "osm_layer_warm_specifications",
        lambda t: [("airports", ["q"], ["all"], [], "")])
    monkeypatch.setattr(
        "O4_OSM_Extracts.local_extracts_cover", lambda bbox: True)
    assert VMAP.is_cached(SimpleNamespace(lat=10, lon=20)) is True


def test_vector_predicate_never_raises(monkeypatch):
    import O4_Vector_Map as VMAP

    def exploding(tile):
        raise RuntimeError("config is a mess")

    monkeypatch.setattr(VMAP, "osm_layer_warm_specifications", exploding)
    assert VMAP.is_cached(SimpleNamespace(lat=10, lon=20)) is False


# ---------------------------------------------------------------------
# Airport packs (auto_patch's only remote traffic is these OSM layers)
# ---------------------------------------------------------------------
def test_airport_pack_predicate_follows_the_road_level(
    monkeypatch, tmp_path
):
    import O4_File_Names as FNAMES
    import O4_Vector_Map as VMAP
    from auto_patch import osm_load

    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    tile = SimpleNamespace(lat=30, lon=31)
    monkeypatch.setattr(VMAP, "resolved_road_level", lambda t: (2, False))
    assert osm_load.is_cached(tile) is False
    _write_osm_cache(FNAMES.osm_cached(30, 31, "airports"))
    assert osm_load.is_cached(tile) is False, "big_roads still missing"
    _write_osm_cache(FNAMES.osm_cached(30, 31, "big_roads"))
    assert osm_load.is_cached(tile) is False, "small_roads still missing"
    _write_osm_cache(FNAMES.osm_cached(30, 31, "small_roads"))
    assert osm_load.is_cached(tile) is True
    # A tile that wants no roads needs only the airports layer.
    monkeypatch.setattr(VMAP, "resolved_road_level", lambda t: (0, False))
    other = SimpleNamespace(lat=31, lon=31)
    _write_osm_cache(FNAMES.osm_cached(31, 31, "airports"))
    assert osm_load.is_cached(other) is True


# ---------------------------------------------------------------------
# Elevation: base tiles over the 3x3 neighbourhood, and airport insets
# ---------------------------------------------------------------------
def test_elevation_predicate_accepts_a_pinned_custom_dem(tmp_path):
    import O4_DEM_Utils as DEM

    pinned = tmp_path / "pinned.tif"
    tile = SimpleNamespace(lat=10, lon=20, custom_dem=str(pinned),
                           elevation_level="auto")
    assert DEM.is_cached(tile) is False
    pinned.write_bytes(b"x")
    assert DEM.is_cached(tile) is True


def test_elevation_predicate_needs_the_whole_neighbourhood(monkeypatch):
    """``build_combined_raster`` assembles nine tiles, so eight of nine
    on disk is NOT cached — one missing neighbour is a download."""
    import O4_Airport_Elevation_Insets as INSETS
    import O4_DEM_Utils as DEM

    present = set()

    def fake_cached(source, lat, lon, prefer_coarse=False):
        return (lat, lon) in present

    monkeypatch.setattr(INSETS, "base_tile_is_cached", fake_cached)
    monkeypatch.setattr(DEM, "_world_tiles", lambda: None)  # all land
    monkeypatch.setattr(
        DEM, "resolve_default_base_source", lambda lat, lon, level: "View")
    tile = SimpleNamespace(lat=10, lon=20, custom_dem="",
                           elevation_level="auto")
    neighbourhood = {
        (lat, lon)
        for lat in (9, 10, 11) for lon in (19, 20, 21)
    }
    present.update(neighbourhood)
    assert DEM.is_cached(tile) is True
    present.discard((11, 21))
    assert DEM.is_cached(tile) is False


def test_elevation_predicate_skips_ocean_only_neighbours(monkeypatch):
    import numpy

    import O4_Airport_Elevation_Insets as INSETS
    import O4_DEM_Utils as DEM

    monkeypatch.setattr(
        INSETS, "base_tile_is_cached",
        lambda source, lat, lon, prefer_coarse=False: (lat, lon) == (10, 20))
    ocean = numpy.zeros((180, 360), dtype=numpy.uint8)
    ocean[89 - 10, 180 + 20] = 1          # only the tile itself is land
    monkeypatch.setattr(DEM, "_world_tiles", lambda: ocean)
    monkeypatch.setattr(
        DEM, "resolve_default_base_source", lambda lat, lon, level: "View")
    tile = SimpleNamespace(lat=10, lon=20, custom_dem="",
                           elevation_level="auto")
    assert DEM.is_cached(tile) is True


def test_inset_predicate_is_true_when_insets_are_disabled():
    import O4_Airport_Elevation_Insets as INSETS

    tile = SimpleNamespace(lat=10, lon=20, airport_elevation_insets=False)
    assert INSETS.is_cached(tile) is True


def _inset_tile(**overrides):
    values = {
        "lat": 30, "lon": 31,
        "airport_elevation_insets": True,
        "airport_elevation_inset_margin_m": 2000.0,
        "airport_elevation_providers": "auto",
        "airport_elevation_level": "auto",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_inset_predicate_needs_a_stamp_matching_the_configuration(
    monkeypatch, tmp_path
):
    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES

    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    monkeypatch.setattr(
        FNAMES, "Elevation_dir", str(tmp_path / "Elevation_data"))
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda t: True)
    tile = _inset_tile()
    # No airports layer at all: the airport SET is unknowable.
    assert INSETS.is_cached(tile) is False
    _write_osm_cache(FNAMES.osm_cached(30, 31, "airports"))
    assert INSETS.is_cached(tile) is False, "no stamp yet"

    monkeypatch.setattr(
        INSETS, "list_cached_inset_dems",
        lambda lat, lon, provider_codes=None: [
            os.path.join(FNAMES.airport_inset_directory(lat, lon),
                         "HECA_srtm.tif")])
    inset_dir = FNAMES.airport_inset_directory(30, 31)
    os.makedirs(inset_dir, exist_ok=True)
    with open(os.path.join(inset_dir, "HECA_srtm.tif"), "wb") as handle:
        handle.write(b"raster")
    INSETS._write_inset_completion_stamp(tile)
    assert INSETS.is_cached(tile) is True

    # A wider margin wants a bigger box: the stamp no longer applies.
    assert INSETS.is_cached(
        _inset_tile(airport_elevation_inset_margin_m=4000.0)) is False
    # A different provider selection likewise.
    assert INSETS.is_cached(
        _inset_tile(airport_elevation_providers="SRTM")) is False
    # A refreshed airports layer changes the airport set.
    _write_osm_cache(FNAMES.osm_cached(30, 31, "airports"), "changed")
    assert INSETS.is_cached(tile) is False


def test_inset_predicate_notices_a_deleted_inset(monkeypatch, tmp_path):
    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES

    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    monkeypatch.setattr(
        FNAMES, "Elevation_dir", str(tmp_path / "Elevation_data"))
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda t: True)
    tile = _inset_tile()
    _write_osm_cache(FNAMES.osm_cached(30, 31, "airports"))
    inset_dir = FNAMES.airport_inset_directory(30, 31)
    os.makedirs(inset_dir, exist_ok=True)
    inset_path = os.path.join(inset_dir, "HECA_srtm.tif")
    with open(inset_path, "wb") as handle:
        handle.write(b"raster")
    monkeypatch.setattr(
        INSETS, "list_cached_inset_dems",
        lambda lat, lon, provider_codes=None: [inset_path])
    INSETS._write_inset_completion_stamp(tile)
    assert INSETS.is_cached(tile) is True
    os.remove(inset_path)
    assert INSETS.is_cached(tile) is False


def test_the_completion_stamp_is_not_rewritten_when_nothing_changed(
    monkeypatch, tmp_path
):
    """A settled warm pass stamps the SAME content every time, and the
    stamp lives in the shared data repo — so an identical rewrite is a
    build side effect on everyone's corpus (owner ruling e9daef5), not
    bookkeeping.  Measured 2026-08-08: two mesh-only tile runs rewrote
    two of these (plus two inset indexes and a band index) while every
    guarded build reported the repo unchanged.
    """
    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES

    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    monkeypatch.setattr(
        FNAMES, "Elevation_dir", str(tmp_path / "Elevation_data"))
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda t: True)
    tile = _inset_tile()
    _write_osm_cache(FNAMES.osm_cached(30, 31, "airports"))
    inset_dir = FNAMES.airport_inset_directory(30, 31)
    os.makedirs(inset_dir, exist_ok=True)
    inset_path = os.path.join(inset_dir, "HECA_srtm.tif")
    with open(inset_path, "wb") as handle:
        handle.write(b"raster")
    monkeypatch.setattr(
        INSETS, "list_cached_inset_dems",
        lambda lat, lon, provider_codes=None: [inset_path])

    INSETS._write_inset_completion_stamp(tile)
    path = INSETS.inset_completion_stamp_path(30, 31)
    os.utime(path, ns=(1, 1))

    INSETS._write_inset_completion_stamp(tile)     # the settled warm pass
    assert os.stat(path).st_mtime_ns == 1
    assert INSETS.is_cached(tile) is True

    # A configuration change IS content, and still lands.
    INSETS._write_inset_completion_stamp(
        _inset_tile(airport_elevation_inset_margin_m=4000.0))
    assert os.stat(path).st_mtime_ns != 1
    with open(path) as handle:
        assert json.load(handle)["margin_m"] == 4000.0


# ---------------------------------------------------------------------
# Bathymetry band
# ---------------------------------------------------------------------
def _bathymetry_tile(**overrides):
    values = {"lat": 21, "lon": -160, "masks_use_DEM_too": "auto",
              "bathymetry_band_km": 5.0}
    values.update(overrides)
    return SimpleNamespace(**values)


def test_bathymetry_predicate_is_true_when_the_band_is_not_wanted():
    import O4_Bathymetry_Band as BAND

    assert BAND.is_cached(_bathymetry_tile(masks_use_DEM_too="False")) is True


def test_bathymetry_predicate_is_true_without_a_covering_provider(
    monkeypatch
):
    import O4_Bathymetry_Band as BAND

    monkeypatch.setattr(BAND, "has_gdal", True)
    monkeypatch.setattr(
        "O4_Airport_Elevation_Insets.select_bathymetry_definitions",
        lambda lat, lon: [])
    assert BAND.is_cached(_bathymetry_tile()) is True


def test_bathymetry_predicate_needs_settled_cells_and_a_mosaic(
    monkeypatch, tmp_path
):
    import O4_Bathymetry_Band as BAND
    import O4_File_Names as FNAMES

    monkeypatch.setattr(BAND, "has_gdal", True)
    monkeypatch.setattr(
        FNAMES, "Elevation_dir", str(tmp_path / "Elevation_data"))
    monkeypatch.setattr(
        "O4_Airport_Elevation_Insets.select_bathymetry_definitions",
        lambda lat, lon: [{"code": "CUDEM"}])
    tile = _bathymetry_tile()
    assert BAND.is_cached(tile) is False, "no stamp"

    directory = FNAMES.bathymetry_band_directory(21, -160)
    os.makedirs(directory, exist_ok=True)
    cell_name = "cell_03_07_cudem_10.0m"
    with open(os.path.join(directory, cell_name + ".tif"), "wb") as handle:
        handle.write(b"raster")
    stamp = {
        "provider": "CUDEM",
        "cells": {cell_name: "ok", "cell_04_07_cudem_10.0m": "no_coverage"},
        "gating": BAND._band_gating_key(tile, True, False),
    }
    BAND._write_band_stamp(FNAMES.bathymetry_band_index(21, -160), stamp)
    assert BAND.is_cached(tile) is False, "the mosaic is still missing"
    with open(FNAMES.bathymetry_band_vrt(21, -160, "CUDEM"), "w") as handle:
        handle.write("<VRTDataset/>")
    assert BAND.is_cached(tile) is True

    # A wider band wants cells nobody fetched.
    assert BAND.is_cached(
        _bathymetry_tile(bathymetry_band_km=12.0)) is False
    # A stamp from before the gating key existed cannot be judged.
    stamp.pop("gating")
    BAND._write_band_stamp(FNAMES.bathymetry_band_index(21, -160), stamp)
    assert BAND.is_cached(tile) is False


# ---------------------------------------------------------------------
# Imagery: the step-completion manifest (the needed set is mesh-derived
# and cannot be enumerated up front — spec §A.2)
# ---------------------------------------------------------------------
def _imagery_tile(tmp_path, **overrides):
    build_dir = tmp_path / "zOrtho4XP_+10+020"
    os.makedirs(build_dir / "textures", exist_ok=True)
    values = {
        "lat": 10, "lon": 20, "build_dir": str(build_dir),
        "default_website": "BI", "default_zl": 16,
        "texture_mode": "full_ortho",
        "textures_total_last_build": 12,
        "textures_missing_last_build": 12,
        "grouped": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _write_mesh(tile):
    import O4_File_Names as FNAMES

    path = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write("mesh")
    return path


def test_imagery_predicate_needs_a_manifest(tmp_path):
    import O4_Tile_Utils as TILE

    tile = _imagery_tile(tmp_path)
    _write_mesh(tile)
    assert TILE.is_cached(tile) is False, "no manifest"
    TILE._write_imagery_manifest(tile, {"done": 12, "failed": 0},
                                 {"done": 12})
    assert TILE.is_cached(tile) is True


def test_imagery_manifest_is_invalidated_by_its_own_inputs(tmp_path):
    import O4_Tile_Utils as TILE

    tile = _imagery_tile(tmp_path)
    mesh_path = _write_mesh(tile)
    TILE._write_imagery_manifest(tile, {"done": 12, "failed": 0},
                                 {"done": 12})
    assert TILE.is_cached(tile) is True
    # A different imagery source or zoom wants different textures.
    assert TILE.is_cached(
        _imagery_tile(tmp_path, default_website="EOX")) is False
    assert TILE.is_cached(_imagery_tile(tmp_path, default_zl=17)) is False
    assert TILE.is_cached(
        _imagery_tile(tmp_path, texture_mode="default_xplane")) is False
    # The needed set is MESH-derived: a rebuilt mesh invalidates it.
    with open(mesh_path, "w") as handle:
        handle.write("a different mesh")
    assert TILE.is_cached(tile) is False


def test_imagery_manifest_records_failed_downloads_as_incomplete(tmp_path):
    """``build_tile`` returns 1 and activates the DSF as long as ANY
    texture landed, so the failure count is the only thing separating a
    complete step from one that dropped textures."""
    import O4_Tile_Utils as TILE

    tile = _imagery_tile(tmp_path)
    _write_mesh(tile)
    TILE._write_imagery_manifest(tile, {"done": 8, "failed": 4},
                                 {"done": 8})
    assert TILE.is_cached(tile) is False


def test_imagery_manifest_notices_deleted_textures(tmp_path):
    import O4_Tile_Utils as TILE

    tile = _imagery_tile(tmp_path)
    _write_mesh(tile)
    textures = os.path.join(tile.build_dir, "textures")
    for index in range(3):
        with open(os.path.join(textures, "t%d.dds" % index), "wb") as f:
            f.write(b"dds")
    TILE._write_imagery_manifest(tile, {"done": 3, "failed": 0},
                                 {"done": 3})
    assert TILE.is_cached(tile) is True
    os.remove(os.path.join(textures, "t0.dds"))
    assert TILE.is_cached(tile) is False


def test_imagery_manifest_rejects_a_foreign_schema(tmp_path):
    import O4_Tile_Utils as TILE

    tile = _imagery_tile(tmp_path)
    _write_mesh(tile)
    TILE._write_imagery_manifest(tile, {"done": 1, "failed": 0},
                                 {"done": 1})
    path = TILE.imagery_manifest_path(tile)
    with open(path) as handle:
        manifest = json.load(handle)
    manifest["schema"] = "1999-01-01"
    with open(path, "w") as handle:
        json.dump(manifest, handle)
    assert TILE.is_cached(tile) is False
    # And an unreadable one.
    with open(path, "w") as handle:
        handle.write("{not json")
    assert TILE.is_cached(tile) is False


def test_imagery_manifest_is_tile_scoped_in_a_grouped_directory(tmp_path):
    """A "grouped" build directory is shared by every tile that writes
    into it, so the manifest must not be a single shared file."""
    import O4_Tile_Utils as TILE

    first = _imagery_tile(tmp_path)
    second = _imagery_tile(tmp_path, lat=11, lon=21)
    second.build_dir = first.build_dir
    assert (TILE.imagery_manifest_path(first)
            != TILE.imagery_manifest_path(second))


def test_imagery_manifest_write_never_raises(tmp_path):
    import O4_Tile_Utils as TILE

    tile = _imagery_tile(tmp_path, build_dir="/nonexistent/nowhere")
    TILE._write_imagery_manifest(tile, {"done": 1}, {"done": 1})
    assert TILE.is_cached(tile) is False


# ---------------------------------------------------------------------
# Gate-off byte identity (spec Acceptance: proven by sha256)
# ---------------------------------------------------------------------
def test_manifest_writing_does_not_touch_the_emitted_artefacts(tmp_path):
    """The manifest lands beside the tile config, never inside the
    directories X-Plane reads: hashing the emitted tree before and after
    a manifest write gives the same digest."""
    import O4_Tile_Utils as TILE

    tile = _imagery_tile(tmp_path)
    _write_mesh(tile)
    emitted = os.path.join(tile.build_dir, "Earth nav data")
    os.makedirs(emitted, exist_ok=True)
    with open(os.path.join(emitted, "+10+020.dsf"), "wb") as handle:
        handle.write(b"a dsf")
    textures = os.path.join(tile.build_dir, "textures")
    with open(os.path.join(textures, "t.dds"), "wb") as handle:
        handle.write(b"a texture")

    def digest():
        hasher = hashlib.sha256()
        for root in (emitted, textures):
            for name in sorted(os.listdir(root)):
                hasher.update(name.encode())
                with open(os.path.join(root, name), "rb") as handle:
                    hasher.update(handle.read())
        return hasher.hexdigest()

    before = digest()
    TILE._write_imagery_manifest(tile, {"done": 1, "failed": 0},
                                 {"done": 1})
    assert digest() == before
    assert os.path.isfile(TILE.imagery_manifest_path(tile))


def test_gate_off_restores_the_pre_change_scheduler(monkeypatch):
    """The gate-off arm in one place: caps, compute rule and bypass all
    return to their pre-2026-07-30 values."""
    monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", "0")
    monkeypatch.delenv("O4_OSM_CLASS_LIMIT", raising=False)
    monkeypatch.delenv("O4_IMAGERY_CLASS_LIMIT", raising=False)
    assert parallel.cache_aware_admission_enabled() is False
    assert parallel.class_limits(6) == {
        "osm": 2, "imagery": 2, "compute": 6}
    for value in ("0", "false", "FALSE", "no", "off"):
        monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", value)
        assert parallel.cache_aware_admission_enabled() is False
    for value in ("1", "true", "yes", "anything-else"):
        monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", value)
        assert parallel.cache_aware_admission_enabled() is True
    monkeypatch.delenv("O4_CACHE_AWARE_ADMISSION")
    assert parallel.cache_aware_admission_enabled() is True


# ---------------------------------------------------------------------
# The predicates must be CHEAP (spec §A.2) — no network, no build
# ---------------------------------------------------------------------
def test_no_predicate_opens_a_socket(monkeypatch, tmp_path):
    """A predicate that probed the network would defeat its own purpose
    (and hang a dispatch).  Poison the socket module and ask them all."""
    import socket

    parallel.preload_cache_predicates()

    def refuse(*args, **kwargs):
        raise AssertionError("a cache predicate touched the network")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    tile = SimpleNamespace(
        lat=10, lon=20, build_dir=str(tmp_path), custom_dem="",
        elevation_level="auto", airport_elevation_insets=False,
        masks_use_DEM_too="False", default_website="BI", default_zl=16,
        texture_mode="full_ortho", road_level=1, grouped=False)
    for step_key in ("vector", "imagery"):
        # The verdict itself does not matter here; not raising does.
        parallel.tile_inputs_are_cached(tile, step_key)
