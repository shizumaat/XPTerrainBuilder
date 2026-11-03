"""Twins for the sea cell (issue #1721).

The owner's tiles +40-074, +40-075 and +41-072 were refused because
their neighbour cells +39-074 / +40-072 are open Atlantic that the coarse
``Utils/world_tiles.png`` marks as land: Viewfinderpanoramas had no
member, and Copernicus GLO-30 / GLO-90 had no tile.  The rule these
twins hold: every source LOOKING and finding no tile, a land-complete
source among them, is sea (``0``, zero-filled) -- and a transient
failure, or a cached OSM coastline in the cell, keeps the refusal.

No network: the strategies are fakes.
"""

import bz2
import os

import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_UI_Utils as UI
import pytest
from elevation_access import base_fallback, sea_cell
from elevation_access import registry as ea_registry

CELL = (39, -74)
ABSENT_TEXT = "no elevation for the LAND cell +39-074 (no archive member)"


class _Configured:
    def covers(self, definition, lat, lon):
        return True

    def download_url(self, definition, lat, lon):
        return "https://configured.invalid/%d/%d.zip" % (lat, lon)

    def tile_cache_path(self, definition, lat, lon):
        return FNAMES.elevation_data("View", lat, lon)

    def ensure_tile(self, definition, lat, lon, verbose=True):
        raise DEM.ElevationAbsentRefused(ABSENT_TEXT)


class _NoTile:
    """A fallback that looked and has no tile; ``transient`` codes raise
    as an unreachable bucket does."""

    transient = set()

    def covers(self, definition, lat, lon):
        return True

    def tile_cache_path(self, definition, lat, lon):
        return "%s_%s.tif" % (FNAMES.base_file_name(lat, lon),
                              definition["code"])

    def ensure_tile(self, definition, lat, lon, verbose=True):
        if definition["code"] in _NoTile.transient:
            raise RuntimeError("existence probe died on the transport")
        return 0


CONFIGURED = {"code": "PRIMARY", "role": "base", "access_strategy": "_primary",
              "display_name": "Primary source"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "elev"))
    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "osm"))
    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "_primary", _Configured)
    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "_notile", _NoTile)
    monkeypatch.setattr(UI, "red_flag", False)
    _NoTile.transient = set()
    base_fallback.forget_unreachable_sources()
    yield {
        "PRIMARY": CONFIGURED,
        "GLOBAL1": {"code": "GLOBAL1", "role": "base", "fallback_rank": "1",
                    "land_complete": "True", "access_strategy": "_notile",
                    "display_name": "Global one"},
        "GLOBAL2": {"code": "GLOBAL2", "role": "base", "fallback_rank": "2",
                    "land_complete": "True", "access_strategy": "_notile",
                    "display_name": "Global two"},
    }
    base_fallback.forget_unreachable_sources()


def _ensure(providers):
    return base_fallback.ensure_tile_or_fallback(
        _Configured(), CONFIGURED, CELL[0], CELL[1], False, providers)


def _write_coastline(lat, lon):
    path = FNAMES.osm_cached(lat, lon, "coastline")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    (y, x) = (lat + 0.5, lon + 0.5)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n'
           '<node id="1" lat="%.7f" lon="%.7f"/>\n'
           '<node id="2" lat="%.7f" lon="%.7f"/>\n'
           '<way id="10">\n<nd ref="1"/>\n<nd ref="2"/>\n'
           '<tag k="natural" v="coastline"/>\n</way>\n</osm>\n'
           % (y, x, y + 0.1, x + 0.1))
    with bz2.open(path, "wt") as handle:
        handle.write(xml)
    return path


def test_every_source_with_no_tile_is_a_sea_cell(world, capsys):
    assert _ensure(world) == 0
    said = capsys.readouterr().out
    assert "Elevation cell +39-074 is taken as SEA and zero-filled" in said
    assert "Global one and Global two" in said
    assert ABSENT_TEXT in said


def test_a_transient_fallback_failure_keeps_the_refusal(world):
    _NoTile.transient = {"GLOBAL2"}
    with pytest.raises(DEM.ElevationAbsentRefused) as caught:
        _ensure(world)
    assert "Global two: RuntimeError" in str(caught.value)


def test_a_configured_transport_failure_is_never_sea(world, monkeypatch):
    def unreachable(self, definition, lat, lon, verbose=True):
        raise DEM.ElevationTransportRefused("ReadTimeout six times")
    monkeypatch.setattr(_Configured, "ensure_tile", unreachable)
    with pytest.raises(DEM.ElevationTransportRefused):
        _ensure(world)


def test_no_land_complete_witness_keeps_the_refusal(world):
    for code in ("GLOBAL1", "GLOBAL2"):
        del world[code]["land_complete"]
    with pytest.raises(DEM.ElevationAbsentRefused):
        _ensure(world)


def test_a_cached_osm_coastline_witnesses_land(world, capsys):
    land = _write_coastline(*CELL)
    assert sea_cell.osm_land_witness(*CELL) == land
    with pytest.raises(DEM.ElevationAbsentRefused):
        _ensure(world)
    assert "shows land, so it is not taken as sea" in capsys.readouterr().out


def test_no_cached_osm_layer_is_no_land_witness(world):
    assert sea_cell.osm_land_witness(*CELL) is None


def test_the_shipped_copernicus_fallbacks_are_land_complete():
    import O4_Airport_Elevation_Insets as INSETS
    here = os.path.dirname(os.path.abspath(__file__))
    shipped = INSETS.initialize_elevation_providers_dict(
        os.path.join(here, "..", "Providers", "Elevation"))
    try:
        fallbacks = base_fallback.fallback_definitions(shipped)
        assert fallbacks and all(sea_cell.is_land_complete(d)
                                 for d in fallbacks)
    finally:
        INSETS.initialize_elevation_providers_dict(
            os.path.join(here, "..", "Providers", "Elevation"))
