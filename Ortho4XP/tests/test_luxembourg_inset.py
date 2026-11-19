"""The Luxembourg national lidar inset (#2185).

ELLX built on FABDEM: no provider served country LUX, and the
neighbouring Rhineland-Palatinate DGM1 (whose box covers ELLX) serves DEU
only.  LUXEMBOURG50CM is the ACT BD-L-Lidar2024 terrain model, one
country-wide Cloud-Optimized GeoTIFF read windowed through /vsicurl.
No network: ``discover`` only builds the virtual path.
"""

import os

import pytest

import O4_Airport_Elevation_Insets as INSETS
from elevation_access import registry as ea_registry
from elevation_access.definitions import provider_serves_country

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROVIDERS = os.path.normpath(os.path.join(_HERE, "..", "Providers", "Elevation"))

#: The ELLX inset box of the 1.0.562 build (its FABDEM provenance).
ELLX_BOX = (6.1746, 49.6099, 6.2483, 49.6428)
COG = ("https://download.data.public.lu/resources/"
       "bd-l-lidar2024-releve-3d-du-territoire-luxembourgeois/"
       "20241223-093912/MNT_Lidar2024.tif")


@pytest.fixture()
def registry():
    INSETS.initialize_elevation_providers_dict(_PROVIDERS)
    return INSETS.elevation_providers_dict


def test_definition_is_an_enabled_national_cog_inset(registry):
    lux = registry["LUXEMBOURG50CM"]
    assert lux["role"] == "airport_inset"
    assert lux["access_strategy"] == "direct_cog"
    assert lux["enabled"] is True
    assert float(lux["native_resolution_m"]) == 0.5
    assert lux["cog_urls"] == COG
    # Orthometric national heights: no ellipsoid reduction.
    assert "geoid_shift" not in lux
    assert lux["priority"] > registry["FABDEM"]["priority"]


def test_country_rule_gives_ellx_the_luxembourg_source(registry):
    assert provider_serves_country(registry["LUXEMBOURG50CM"], "LUX")
    assert not provider_serves_country(registry["LUXEMBOURG50CM"], "DEU")
    # The cause of #2185: the German state covering ELLX's box is DEU-only.
    assert not provider_serves_country(registry["RHINELANDPALATINATE1M"], "LUX")


def test_discover_reads_the_cog_for_ellx_only(registry):
    lux = dict(registry["LUXEMBOURG50CM"])
    strategy = ea_registry.ACCESS_STRATEGIES["direct_cog"]()
    assert strategy.discover(lux, ELLX_BOX) == [{"source": "/vsicurl/" + COG}]
    # Hahn (EDFH, Rhineland-Palatinate) lies outside the Grand Duchy box.
    assert strategy.discover(lux, (7.24, 49.93, 7.29, 49.96)) is None
