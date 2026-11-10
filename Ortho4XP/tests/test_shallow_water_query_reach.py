"""#1919: the shallow-water mask fallback's OSM query reaches exactly
the mask squares it draws, never a flat margin that selects a further
regional extract.

Tile +53+009 (EDDH) asked for a 0.5-degree margin, so its box ran to
52.5 N and touched the simplified polygon of a region lying south of
the tile (detmold-regbez tops out at 52.53 N): the build downloaded a
130 MB extract and cut a second 618 MB clip for a land sliver no mask
square ever draws.  Headless: synthetic Geofabrik index shaped like the
real one around the tile, no network, no pbf, no DEM.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Cfg_Vars as CFG_VARS  # noqa: E402
import O4_Land_Witness as LAND  # noqa: E402
import O4_Mask_Utils as MASK  # noqa: E402
import O4_OSM_Extracts as EXTRACTS  # noqa: E402
import O4_OSM_Utils as OSM  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402


def _leaf(region_id, lon_min, lat_min, lon_max, lat_max):
    ring = [[lon_min, lat_min], [lon_max, lat_min], [lon_max, lat_max],
            [lon_min, lat_max], [lon_min, lat_min]]
    return {"type": "Feature",
            "properties": {"id": region_id, "parent": "germany",
                           "urls": {"pbf": "https://example.invalid/x"}},
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


@pytest.fixture
def index_store(tmp_path, monkeypatch):
    directory = str(tmp_path / "extracts")
    monkeypatch.setattr(EXTRACTS, "STORE_DIRECTORY", directory)
    monkeypatch.setattr(LAND, "_land_posts", lambda lat, lon: None)
    EXTRACTS._leaf_regions.cache = None
    # The tile's own region reaches down to 52.6 N; a southern region
    # (the detmold-regbez shape) pokes up to 52.533 N under it.
    index = {"type": "FeatureCollection", "features": [
        _leaf("germany", 5, 47, 15, 55),
        _leaf("north", 8.0, 52.6, 11.5, 55.0),
        _leaf("south", 8.07, 51.44, 9.47, 52.533),
    ]}
    index["features"][0]["properties"]["parent"] = None
    os.makedirs(directory)
    with open(os.path.join(directory, "index-v1.json"), "w",
              encoding="utf-8", newline="") as index_file:
        json.dump(index, index_file)
    yield directory
    EXTRACTS._leaf_regions.cache = None


def _query_box(monkeypatch, lat, lon, margins):
    """The box OSM_queries_to_OSM_layer hands the extracts backend."""
    seen = []

    def _capture(statements, bounding_box, request_description=""):
        seen.append(tuple(bounding_box))
        return None

    monkeypatch.setattr(EXTRACTS, "osm_xml_from_local_extracts", _capture)
    monkeypatch.setattr(OSM, "get_overpass_data",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr(UI, "red_flag", False)
    OSM.OSM_queries_to_OSM_layer(['way["natural"="reef"]'],
                                 OSM.OSM_layer(), lat, lon, [],
                                 bbox_margin_degrees=margins)
    return seen[0]


def test_flat_half_degree_margin_reached_the_southern_region(
        index_store, monkeypatch):
    """The mechanism: the former flat margin's box selects it."""
    box = _query_box(monkeypatch, 53, 9, 0.5)
    assert box == (52.5, 8.5, 54.5, 10.5)
    assert "south" in [r for (r, _u) in EXTRACTS.covering_regions(box)]


def test_square_reach_stays_with_the_tiles_own_region(
        index_store, monkeypatch):
    margins = MASK._shallow_water_query_margins(53, 9)
    box = _query_box(monkeypatch, 53, 9, margins)
    assert box[0] > 52.6          # never below the north region's edge
    assert [r for (r, _u) in EXTRACTS.covering_regions(box)] == ["north"]


@pytest.mark.parametrize("lat, lon", [(53, 9), (0, 0), (-34, 18),
                                      (64, -22), (70, 25)])
def test_reach_covers_every_square_the_masks_draw(lat, lon):
    """Every square build_masks draws for the tile, at every offered
    mask_zl, lies inside the query box (one cache serves them all), and
    the reach never exceeds the former 0.5-degree box (old caches stay
    supersets under the unchanged schema)."""
    (south, west, north, east) = MASK._shallow_water_query_margins(lat, lon)
    assert max(south, west, north, east) < 0.5
    offered = CFG_VARS.cfg_vars["mask_zl"]["values"]
    assert MASK.SHALLOW_WATER_REACH_ZL == min(offered)
    import O4_Geo_Utils as GEO

    for zoomlevel in offered:
        (x_min, y_min) = GEO.wgs84_to_orthogrid(lat + 1, lon, zoomlevel)
        (x_max, y_max) = GEO.wgs84_to_orthogrid(lat, lon + 1, zoomlevel)
        for til_x in range(x_min, x_max + 1, 16):
            for til_y in range(y_min, y_max + 1, 16):
                (s, w, n, e) = MASK._shallow_water_square_box(
                    til_x, til_y, zoomlevel)
                assert s >= lat - south - 1e-9
                assert w >= lon - west - 1e-9
                assert n <= lat + 1 + north + 1e-9
                assert e <= lon + 1 + east + 1e-9
