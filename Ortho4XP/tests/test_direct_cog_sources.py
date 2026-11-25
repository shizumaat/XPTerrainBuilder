"""Footprinted ``cog_source`` lines of the direct_cog strategy (#1926).

A publisher of a few dozen regional rasters (the Norwegian Polar
Institute's S0 terrain-model zips, NPOLARS0) cannot list them in
``cog_urls``: every airport would open every block remotely.  Each
``cog_source=W,S,E,N|path`` line carries its block's footprint and only
the blocks touching the airport box are warped, in file order (the warp
lets later inputs win, so newer blocks are listed last).  Offline.
"""
import os

import O4_Airport_Elevation_Insets as INSETS
import pytest
from elevation_access import registry
from elevation_access.definitions import DEM_CLASS_KEY, provider_serves_country
from elevation_access.stac_assets import _stac_asset_href_to_vsicurl
from elevation_access.strategies.direct_cog import (
    COG_SOURCE_KEY,
    _assign_source_srs,
    cog_sources,
)
from elevation_access.warp import _vsicurl_allowed_extensions

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROVIDERS = os.path.normpath(
    os.path.join(_HERE, "..", "Providers", "Elevation"))

#: Longyearbyen (ENSB) airport box, the closing case of #1926.
ENSB_BOX = (15.3837, 78.2379, 15.5429, 78.2544)
FAR_BOX = (10.0, 59.9, 10.1, 60.0)


def _definition(lines):
    return {"code": "TESTBLOCKS", "access_strategy": "direct_cog",
            COG_SOURCE_KEY: ";".join(lines)}


def test_cog_sources_parse_and_skip_a_malformed_line():
    pairs = cog_sources(_definition([
        "15.0,78.0,16.0,78.5|https://example.test/a.zip/a/a.tif",
        "not,a,box|https://example.test/bad.tif",
        "15.0,78.0,16.0,78.5|",
        "1,2,3,4|/vsizip//vsicurl/https://example.test/b.zip/b.tif",
    ]))
    assert pairs == [
        ((15.0, 78.0, 16.0, 78.5),
         "/vsicurl/https://example.test/a.zip/a/a.tif"),
        ((1.0, 2.0, 3.0, 4.0),
         "/vsizip//vsicurl/https://example.test/b.zip/b.tif"),
    ]


def test_only_the_blocks_touching_the_box_are_read_in_file_order():
    strategy = registry.ACCESS_STRATEGIES["direct_cog"]()
    definition = _definition([
        "15.0,78.0,16.0,78.5|https://example.test/old.tif",
        "20.0,79.0,21.0,79.5|https://example.test/elsewhere.tif",
        "15.4,78.2,15.6,78.3|https://example.test/new.tif",
        # A second island of the old raster: read once, where first touched.
        "15.3,78.24,15.5,78.26|https://example.test/old.tif",
    ])
    assert strategy.discover(definition, ENSB_BOX) == [
        {"source": "/vsicurl/https://example.test/old.tif"},
        {"source": "/vsicurl/https://example.test/new.tif"},
    ]
    assert strategy.discover(definition, FAR_BOX) is None


def test_the_reader_joins_repeated_cog_source_lines(tmp_path):
    (tmp_path / "TESTBLOCKS.elv").write_text(
        "access_strategy=direct_cog\n"
        "cog_source=1,2,3,4|https://example.test/a.tif\n"
        "cog_source=5,6,7,8|https://example.test/b.tif\n",
        encoding="utf-8", newline="\n")
    try:
        INSETS.initialize_elevation_providers_dict(str(tmp_path))
        definition = INSETS.elevation_providers_dict["TESTBLOCKS"]
        assert [path for (_box, path) in cog_sources(definition)] == [
            "/vsicurl/https://example.test/a.tif",
            "/vsicurl/https://example.test/b.tif",
        ]
    finally:
        INSETS.initialize_elevation_providers_dict(_PROVIDERS)


@pytest.fixture
def shipped():
    INSETS.initialize_elevation_providers_dict(_PROVIDERS)
    return INSETS.elevation_providers_dict


def test_npolars0_ranks_ahead_of_arcticdem_in_svalbard(shipped):
    npi = shipped["NPOLARS0"]
    arctic = shipped["ARCTICDEM2M"]
    assert npi["enabled"] and npi["role"] == "airport_inset"
    assert npi["priority"] > arctic["priority"]
    assert "SJM" in npi["country"].split(",")
    assert npi[DEM_CLASS_KEY] == "fine"
    # Heights are orthometric (mean sea level): no ellipsoid reduction.
    assert "geoid_shift" not in npi
    assert npi["license"].startswith("Creative Commons Attribution 4.0")
    strategy = registry.ACCESS_STRATEGIES["direct_cog"]()
    sources = strategy.discover(npi, ENSB_BOX)
    assert sources and all(
        entry["source"].startswith("/vsizip//vsicurl/https://"
                                   "public.data.npolar.no/")
        for entry in sources)
    assert strategy.discover(npi, FAR_BOX) is None


#: Saba (TNCS) airport box, the closing case of the Dutch Caribbean lidar.
SABA_BOX = (-63.226, 17.640, -63.218, 17.648)


def test_a_third_field_assigns_the_source_crs():
    """``W,S,E,N|url|EPSG:n``: the CRS travels with its source as a
    ``vrt://`` wrapper; a CRS field that is not ``EPSG:<digits>`` drops
    the line instead of warping it to the wrong place."""
    pairs = cog_sources(_definition([
        "1,2,3,4|https://example.test/a.tif|epsg:10641",
        "1,2,3,4|https://example.test/b.tif|+proj=tmerc",
        "1,2,3,4|https://example.test/c.tif|EPSG:",
        "1,2,3,4|https://example.test/d.tif|EPSG:1|extra",
        "1,2,3,4|/vsicurl/https://example.test/e.tif|EPSG:10759",
    ]))
    assert pairs == [
        ((1.0, 2.0, 3.0, 4.0),
         "vrt:///vsicurl/https://example.test/a.tif?a_srs=EPSG:10641"),
        ((1.0, 2.0, 3.0, 4.0),
         "vrt:///vsicurl/https://example.test/e.tif?a_srs=EPSG:10759"),
    ]
    assert _assign_source_srs("/vsicurl/x.tif", "EPSG:4326") == (
        "vrt:///vsicurl/x.tif?a_srs=EPSG:4326")


def test_a_vrt_wrapper_is_already_virtual_and_keeps_the_curl_fence():
    wrapped = "vrt:///vsicurl/https://example.test/a.TIF?a_srs=EPSG:10641"
    assert _stac_asset_href_to_vsicurl(wrapped) == wrapped
    # The extension fence reads through the wrapper to the curl path.
    assert _vsicurl_allowed_extensions([wrapped]) == ".tif,.tiff,.vrt"


def test_dutch_caribbean_lidar_serves_the_bes_islands_only(shipped):
    bes = shipped["DUTCHCARIBBEAN50CM"]
    assert bes["enabled"] and bes["role"] == "airport_inset"
    assert len(bes["coverage_bboxes"]) == 3
    # apt.dat's TNCS/TNCE/TNCB country rows read NLD.
    assert provider_serves_country(bes, "NLD")
    assert provider_serves_country(bes, "BES")
    assert not provider_serves_country(bes, "SXM")
    assert "geoid_shift" not in bes  # local MSL, passed through
    strategy = registry.ACCESS_STRATEGIES["direct_cog"]()
    assert strategy.discover(bes, SABA_BOX) == [{
        "source": "vrt:///vsicurl/https://basisdata.nl/hwh-ortho/"
                  "Caribisch_NL/LiDAR/caribisch/Saba/02a_DTM_50cm/"
                  "M_SABA2023.TIF?a_srs=EPSG:10641"}]
    # Sint Maarten (TNCM) lies between the islands' boxes: not claimed.
    assert strategy.discover(bes, (-63.115, 18.035, -63.100, 18.045)) is None
    # Every source names its island's engineering CRS.
    assert all("?a_srs=EPSG:10" in path for (_box, path) in cog_sources(bes))
