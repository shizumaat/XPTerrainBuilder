"""FABDEM's cells inside 10-degree zips (``degree_zipped_cog``, #1942).

The names are computed, never read from the portal's tile GeoJSON (which
names both zips and members wrongly); an absent archive or member is a
durable absent; a directory that cannot be read on an archive the server
says exists is transient.  No network: the HEAD probe and the zip listing
are faked.
"""

import O4_Airport_Elevation_Insets as INSETS
import pytest
from elevation_access.base import TransientFetchError
from elevation_access.gdal_support import has_gdal
from elevation_access.strategies import degree_zipped_cog as zipped

PORTAL = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn/"


@pytest.fixture
def registry():
    saved = INSETS.elevation_providers_dict
    yield INSETS.initialize_elevation_providers_dict()
    INSETS.elevation_providers_dict = saved


@pytest.fixture
def fabdem(registry):
    return registry["FABDEM"]


@pytest.fixture
def strategy(monkeypatch):
    monkeypatch.setattr(zipped.DegreeZippedCogStrategy,
                        "_members_by_archive", {})
    return zipped.DegreeZippedCogStrategy()


@pytest.mark.parametrize("cell, tokens", [
    ((54, -5), ("N50", "W010", "N60", "E000")),
    ((5, 3), ("N00", "E000", "N10", "E010")),
    ((-1, 175), ("S10", "E170", "N00", "W180")),
    ((-59, -71), ("S60", "W080", "S50", "W070")),
    ((79, -180), ("N70", "W180", "N80", "W170")),
])
def test_block_tokens_follow_the_portal_grammar(cell, tokens):
    assert zipped.DegreeZippedCogStrategy.block_tokens(*cell) == tokens


def test_the_shipped_definition_names_archive_and_member(fabdem, strategy):
    assert fabdem["access_strategy"] == "degree_zipped_cog"
    assert fabdem["role"] == "airport_inset"
    assert strategy._cell_url(fabdem, 54, -5) == (
        PORTAL + "N50W010-N60E000_FABDEM_V1-2.zip")
    assert strategy._member_name(fabdem, 54, -5) == "N54W005_FABDEM_V1-2.tif"
    assert strategy._cell_url(fabdem, -34, 151) == (
        PORTAL + "S40E150-S30E160_FABDEM_V1-2.zip")
    assert strategy._member_name(fabdem, -34, 151) == "S34E151_FABDEM_V1-2.tif"


def test_fabdem_ranks_just_above_copernicus_and_masks_nothing(fabdem,
                                                             registry):
    copernicus = registry["COPERNICUSGLO30"]
    assert int(fabdem["priority"]) == int(copernicus["priority"]) + 1
    national = [d for d in registry.values()
                if d.get("role") == "airport_inset" and d.get("enabled")
                and d["code"] not in ("FABDEM", "COPERNICUSGLO30")]
    assert all(int(d["priority"]) > int(fabdem["priority"])
               for d in national)
    assert not fabdem.get(INSETS.SURFACE_MODEL_BUILDING_MASKING)
    assert fabdem.get(INSETS.FALLBACK_QUALITY) is True
    assert "CC BY-NC-SA 4.0" in fabdem["license"]
    assert "Hawker" in fabdem["attribution"]


@pytest.mark.skipif(not has_gdal, reason="needs GDAL")
def test_a_listed_member_is_read_in_place(fabdem, strategy, monkeypatch):
    heads, listings = [], []
    monkeypatch.setattr(zipped.DegreeZippedCogStrategy, "_url_exists",
                        lambda self, url: heads.append(url) or True)

    def _read_dir(path):
        listings.append(path)
        return ["N54W005_FABDEM_V1-2.tif", "N54W004_FABDEM_V1-2.tif"]

    monkeypatch.setattr(zipped.gdal, "ReadDir", _read_dir)
    archive = PORTAL + "N50W010-N60E000_FABDEM_V1-2.zip"
    assert strategy.cell_source(fabdem, 54, -5) == (
        "/vsizip//vsicurl/" + archive + "/N54W005_FABDEM_V1-2.tif")
    # Open sea inside a published block: not a member, a durable absent.
    assert strategy.cell_source(fabdem, 54, -9) is None
    assert listings == ["/vsizip//vsicurl/" + archive]   # listed once
    sources = strategy.discover(fabdem, (-4.7, 54.0, -4.5, 54.2))
    assert [s["cell"] for s in sources] == [[54, -5]]


def test_an_absent_archive_is_absent(fabdem, strategy, monkeypatch):
    monkeypatch.setattr(zipped.DegreeZippedCogStrategy, "_url_exists",
                        lambda self, url: False)
    assert strategy.cell_source(fabdem, 30, -40) is None


@pytest.mark.skipif(not has_gdal, reason="needs GDAL")
def test_an_unreadable_directory_is_transient(fabdem, strategy, monkeypatch):
    monkeypatch.setattr(zipped.DegreeZippedCogStrategy, "_url_exists",
                        lambda self, url: True)
    monkeypatch.setattr(zipped.gdal, "ReadDir", lambda path: None)
    with pytest.raises(TransientFetchError):
        strategy.cell_source(fabdem, 54, -5)
    assert zipped.DegreeZippedCogStrategy._members_by_archive == {}
