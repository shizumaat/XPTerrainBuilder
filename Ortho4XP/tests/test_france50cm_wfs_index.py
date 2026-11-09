"""FRANCE50CM's tile index answers again (#1944).

The Geoplateforme withdrew ``IGNF_MNT-LIDAR-HD:dalle`` from its WFS: the
query answered HTTP 400 "Unknown namespace [IGNF_MNT-LIDAR-HD]" and every
French airport fell back to FRANCE1M.  The LiDAR HD tile index is now
``IGNF_LIDAR-HD_METADONNEE:metadata`` (one feature per 1 km tile; the
terrain GeoTIFF URL is ``url_mnt``).  The fixture is a live answer at the
LFKC inset box, trimmed to two tiles.  No network: ``requests.get`` is
stubbed and answers only the recorded request.
"""

import json
import os
import types

import pytest

import O4_Airport_Elevation_Insets as INSETS
from elevation_access import registry as ea_registry

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROVIDERS = os.path.normpath(
    os.path.join(_HERE, "..", "Providers", "Elevation"))
with open(os.path.join(_HERE, "fixtures", "france50cm_wfs_lfkc.json"),
          encoding="utf-8") as _handle:
    _FIXTURE = json.load(_handle)
_WITHDRAWN_NAMESPACE = "IGNF_MNT-LIDAR-HD"


@pytest.fixture
def shipped():
    INSETS.initialize_elevation_providers_dict(_PROVIDERS)
    return INSETS.elevation_providers_dict


@pytest.fixture
def recorded_wfs(monkeypatch):
    import requests

    seen = []

    def _get(url, timeout=None, **_kwargs):
        seen.append(url)
        if url != _FIXTURE["request_url"]:
            return types.SimpleNamespace(status_code=400, url=url,
                                         json=lambda: {})
        return types.SimpleNamespace(
            status_code=200, url=url, json=lambda: _FIXTURE["response"])

    monkeypatch.setattr(requests, "get", _get)
    return seen


@pytest.mark.parametrize("code", ["FRANCE50CM", "FRANCETIDAL"])
def test_no_lidar_provider_names_the_withdrawn_layer(shipped, code):
    definition = shipped[code]
    assert definition["access_strategy"] == "wfs_tile_index"
    assert _WITHDRAWN_NAMESPACE + ":" not in definition["wfs_type_name"]
    assert definition["wfs_type_name"] == "IGNF_LIDAR-HD_METADONNEE:metadata"
    assert definition["url_property"] == "url_mnt"


def test_the_lfkc_query_matches_the_recorded_request(shipped):
    strategy = ea_registry.ACCESS_STRATEGIES["wfs_tile_index"]()
    url = strategy._feature_query_url(
        shipped["FRANCE50CM"], tuple(_FIXTURE["bounding_box_wgs84"]))
    assert url == _FIXTURE["request_url"]


def test_the_lfkc_index_resolves_to_terrain_tiles(shipped, recorded_wfs):
    strategy = ea_registry.ACCESS_STRATEGIES["wfs_tile_index"]()
    sources = strategy.discover(
        shipped["FRANCE50CM"], tuple(_FIXTURE["bounding_box_wgs84"]))
    assert recorded_wfs == [_FIXTURE["request_url"]]
    assert sources and len(sources) == len(_FIXTURE["response"]["features"])
    for source in sources:
        # The bare-earth model, never the surface (MNS) or height (MNH)
        # rasters the same feature also carries.
        assert "IGNF_LIDAR-HD_MNT_ELEVATION" in source["url"]
        assert "_MNT_" in source["url"]
