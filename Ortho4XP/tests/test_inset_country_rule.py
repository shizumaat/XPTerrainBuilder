"""THE COUNTRY RULE for elevation insets (owner RULINGS 2026-10-20bc, #1205).

A national provider serves only airports of its own country, whatever
coverage it reports; with none of the airport's country the ranking falls
to the global source.  Precedents: a Canadian airport took USGS 3DEP; a
Moroccan airport asked the Spanish 5 m model.  Synthetic definitions and a
recording strategy only -- no network, no GDAL.
"""
import os

import O4_Airport_Apt_Identity as ID
import O4_Airport_Elevation_Insets as INSETS
import O4_Airport_Index as AIRPORT_INDEX
import O4_File_Names as FNAMES
import pytest
from elevation_access import definitions as ea_definitions
from elevation_access import registry as ea_registry

BOX = (-123.45, 48.62, -123.40, 48.66)


def _definition(code, country, priority):
    return {"code": code, "access_strategy": "country_rule_recorder",
            "role": ea_definitions.ROLE_AIRPORT_INSET, "enabled": True,
            "priority": priority, "country": country}


def _run(tmp_path, monkeypatch, definitions, icao, country):
    """Run the fetch loop for one airport; return (asked codes, record)."""
    pytest.importorskip("osgeo.gdal")  # the fetch loop needs GDAL; CI's mac/linux legs drop it
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    asked = []

    @ea_registry.register_access_strategy("country_rule_recorder")
    class _Recorder:
        def discover(self, definition, bounding_box_wgs84):
            asked.append(definition["code"])
            return None

        def fetch(self, definition, bbox, resolution_m, destination_path):
            asked.append(definition["code"])
            return None

    try:
        index = INSETS.ensure_airport_insets(
            48, -124, {icao: BOX}, definitions, 3.0,
            airport_countries={icao: country} if country else None)
    finally:
        ea_registry.ACCESS_STRATEGIES.pop("country_rule_recorder", None)
    return sorted(set(asked)), index[icao]


def test_a_canadian_airport_never_asks_a_us_provider(tmp_path, monkeypatch):
    us, globe = _definition("USFAKE", "USA", 100), _definition(
        "GLOBEFAKE", "GLOBAL", 1)
    # An inset the US provider delivered before the rule: set aside.
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    stale = FNAMES.airport_inset_dem(48, -124, "CYYZ", "USFAKE")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "wb") as handle:
        handle.write(b"raster")
    asked, record = _run(tmp_path, monkeypatch, [us, globe], "CYYZ", "CAN")
    assert asked == ["GLOBEFAKE"]
    assert record["USFAKE"] == INSETS.NO_COVERAGE
    assert not os.path.exists(stale)
    assert not INSETS.list_cached_inset_dems(48, -124)
    assert any(name.startswith("CYYZ_usfake.tif.out-of-country-")
               for name in os.listdir(os.path.dirname(stale)))


def test_a_moroccan_airport_never_asks_a_spanish_provider(
        tmp_path, monkeypatch):
    spain, globe = _definition("ESFAKE", "ESP", 100), _definition(
        "GLOBEFAKE", "GLOBAL", 1)
    asked, record = _run(tmp_path, monkeypatch, [spain, globe], "GMZZ", "MAR")
    assert asked == ["GLOBEFAKE"] and record["ESFAKE"] == INSETS.NO_COVERAGE


def test_own_country_and_unknown_country_still_ask(tmp_path, monkeypatch):
    spain = _definition("ESFAKE", "ESP", 100)
    assert _run(tmp_path, monkeypatch, [spain], "LEZZ", "ESP")[0] == [
        "ESFAKE"]
    assert _run(tmp_path / "u", monkeypatch, [spain], "XZZZ", None)[0] == [
        "ESFAKE"]


def test_the_predicates():
    serves = ea_definitions.provider_serves_country
    assert not serves({"country": "USA,PRI"}, "CAN")
    assert serves({"country": "USA,PRI"}, "pri")
    assert serves({"country": "GLOBAL"}, "MAR") and serves({}, "MAR")
    share = ea_definitions.providers_share_country
    assert share({"country": "USA"}, {"country": "USA,PRI"})
    assert not share({"country": "USA"}, {"country": "CAN"})
    assert not share({"country": "USA"}, {"country": "GLOBAL"})
    assert share({"country": "GLOBAL"}, {"country": "CAN"})


def test_a_national_ladder_member_joins_only_its_countrys_ladder(
        monkeypatch):
    member = dict(_definition("USMEMBER", "USA", 90), ladder_member=True,
                  coverage_bbox=(-124.0, 48.0, -123.0, 49.0),
                  native_resolution_m=1.0)
    monkeypatch.setattr(INSETS, "elevation_providers_dict",
                        {"USMEMBER": member})
    for (root_country, joins) in (("CAN", False), ("USA", True),
                                  ("GLOBAL", False)):
        root = dict(_definition("ROOT", root_country, 100),
                    native_resolution_m=1.0)
        codes = [rung.get("code")
                 for (_label, rung) in INSETS._ladder_rung_definitions(
                     root, BOX)]
        assert ("USMEMBER" in codes) is joins, root_country


def test_every_shipped_inset_provider_declares_its_country():
    INSETS.initialize_elevation_providers_dict()
    insets = {code: definition for (code, definition)
              in INSETS.elevation_providers_dict.items()
              if definition.get("role", ea_definitions.ROLE_AIRPORT_INSET)
              == ea_definitions.ROLE_AIRPORT_INSET}
    assert insets
    undeclared = sorted(code for (code, d) in insets.items()
                        if not str(d.get("country") or "").strip())
    assert undeclared == []
    serves = ea_definitions.provider_serves_country
    assert not serves(insets["USGS3DEP"], "CAN")      # the CYYJ precedent
    assert not serves(insets["SPAIN5M"], "MAR")       # the GMTT precedent
    assert serves(insets["HRDEM"], "CAN")
    assert ea_definitions.provider_countries(
        insets["COPERNICUSGLO30"]) is None
    # An explicit cross-provider rung shares its root's country.
    for (code, root) in insets.items():
        for rung in root.get("resolution_ladder_rungs") or ():
            other = rung.get("provider")
            if other and other in insets:
                assert ea_definitions.providers_share_country(
                    insets[other], root), (code, other)


def test_apt_dat_country_is_stamped_on_the_airport_record():
    assert ID.iso_country("USA United States") == "USA"
    assert ID.iso_country("CAN") == "CAN"
    assert ID.iso_country("") == "" and ID.iso_country("Perú") == ""
    entry = AIRPORT_INDEX.AirportEntry(
        code="ZZZZ", name="Synthetic", city="", country="MAR Morocco",
        lat=33.94, lon=-118.41, category="icao_airport",
        extent=(33.93, -118.44, 33.95, -118.38), runway_m=3000)
    dico = {}
    ID.adopt_apt_dat_identities(dico, [entry])
    assert dico["ZZZZ"][ID.COUNTRY_KEY] == "MAR"
    assert INSETS._airport_countries(dico) == {"ZZZZ": "MAR"}
