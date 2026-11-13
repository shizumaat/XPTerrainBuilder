"""The tile pane's "Elevation" row (#2033): the elevation a tile was built
with -- the base the build read and its airport insets' sources -- from the
tile's own records (``O4_Unpatched_Airports``' sidecar), never a guess at
what a build would use now.

No network, no build: the DEM is a stand-in carrying the fields a load
sets.
"""
from __future__ import annotations

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_DEM_Utils as DEM  # noqa: E402
import O4_Tile_Info as TINFO  # noqa: E402
import O4_Unpatched_Airports as UNPATCHED  # noqa: E402


def _dem(**fields):
    base = {"lat": 30, "lon": 31, "base_keyword": None, "base_file": None,
            "base_substitutions": []}
    return types.SimpleNamespace(**{**base, **fields})


def test_the_base_label_names_the_source_the_load_read():
    assert DEM.base_source_label(_dem(base_keyword="View")) == "Viewfinderpanoramas"
    assert DEM.base_source_label(_dem(base_file="/x/my_dem.tif")) == "my_dem.tif"
    # The tile's own cell came from a fallback: the fallback is named.
    fallback = _dem(base_keyword="View", base_substitutions=[
        {"cell": "+30+031", "fallback": "Copernicus GLO-30"}])
    assert DEM.base_source_label(fallback) == "Copernicus GLO-30"
    # A neighbour's fallback is not the tile's base.
    neighbour = _dem(base_keyword="View", base_substitutions=[
        {"cell": "+31+031", "fallback": "Copernicus GLO-30"}])
    assert DEM.base_source_label(neighbour) == "Viewfinderpanoramas"
    assert DEM.base_source_label(_dem()) == ""


def test_the_row_reads_the_base_and_the_insets_from_the_records(tmp_path):
    tile = types.SimpleNamespace(build_dir=str(tmp_path))
    assert TINFO._elevation_text(str(tmp_path)) == ""
    UNPATCHED.record_base_source(tile, "Copernicus GLO-30")
    assert TINFO._elevation_text(str(tmp_path)) == "Copernicus GLO-30"
    UNPATCHED.record_inset_sources(tile, [
        {"icao": "KAAA", "provider": "USGS3DEP", "native_resolution_m": 1.0},
        {"icao": "KBBB", "provider": "USGS3DEP", "native_resolution_m": 1.0}])
    assert TINFO._elevation_text(str(tmp_path)) == (
        "Copernicus GLO-30 + USGS3DEP 1 m inset")
    UNPATCHED.record_inset_sources(tile, [
        {"icao": "KAAA", "provider": "USGS3DEP", "native_resolution_m": 1.0},
        {"icao": "KCCC", "provider": "COPERNICUSGLO30",
         "native_resolution_m": 30.0}])
    assert TINFO._elevation_text(str(tmp_path)) == (
        "Copernicus GLO-30 + USGS3DEP 1 m, COPERNICUSGLO30 30 m insets")
    # Each record is read from disk, not from this process's tile object.
    assert UNPATCHED.read_base_source(
        types.SimpleNamespace(build_dir=str(tmp_path))) == "Copernicus GLO-30"


def test_a_tile_built_before_the_record_names_its_pinned_file(tmp_path):
    assert TINFO._elevation_text(str(tmp_path), "/dem/N30E031.tif;/dem/a.tif") == (
        "N30E031.tif")


def test_the_tile_info_carries_the_row(tmp_path):
    names = {field.name for field in TINFO.TileInfo.__dataclass_fields__.values()}
    assert "elevation" in names
