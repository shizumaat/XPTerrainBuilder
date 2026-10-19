"""Twins for :mod:`O4_Airport_Apt_Identity`: a tile's airports take their
code and extent from apt.dat (the offline airport index), OSM aerodromes
the fallback.  Synthetic index entries and dictionaries only."""
from shapely import geometry

import O4_Airport_Apt_Identity as ID
import O4_Airport_Index as AIRPORT_INDEX


def _entry(code, lat, lon, extent, category="icao_airport", runway_m=3000,
           name="Synthetic"):
    return AIRPORT_INDEX.AirportEntry(
        code=code, name=name, city="", country="", lat=lat, lon=lon,
        category=category, extent=extent, runway_m=runway_m)


def _osm(key_type, name, boundary=None, repr_node=(0.0, 0.0)):
    return {"key_type": key_type, "name": name, "repr_node": repr_node,
            "boundary": boundary, "runway": [], "runway_as_rel": [],
            "taxiway": [], "apron": [], "hangar": []}


BIG = _entry("ZZZZ", 33.94, -118.41, (33.93, -118.44, 33.95, -118.38))


def test_airport_without_aerodrome_is_seeded_under_its_code():
    dico = {}
    assert ID.adopt_apt_dat_identities(dico, [BIG]) == 1
    seed = dico["ZZZZ"]
    assert seed["key_type"] == "icao" and seed[ID.SEED_FLAG]
    assert seed["boundary"].bounds == (-118.44, 33.93, -118.38, 33.95)
    assert seed["repr_node"] == (-118.41, 33.94)


def test_seed_kept_only_when_a_surface_attached():
    dico = {}
    ID.adopt_apt_dat_identities(dico, [BIG])
    assert ID.drop_unclaimed_seeds(dico) == [] and dico == {}
    ID.adopt_apt_dat_identities(dico, [BIG])
    dico["ZZZZ"]["runway"].append(-7)
    assert ID.drop_unclaimed_seeds(dico) == ["ZZZZ"]
    assert ID.SEED_FLAG not in dico["ZZZZ"]


def test_uncoded_aerodrome_takes_the_apt_dat_code_it_overlaps_most():
    small = _entry("YYYY", 33.94, -118.43, (33.939, -118.431, 33.941, -118.429))
    dico = {"Some Airfield": _osm(
        "name", "Some Airfield",
        geometry.box(-118.44, 33.93, -118.38, 33.95), (-118.41, 33.94))}
    assert ID.adopt_apt_dat_identities(dico, [small, BIG]) == 1
    assert dico["ZZZZ"]["name"] == "Some Airfield"
    assert dico["ZZZZ"]["key_type"] == "icao"
    assert "YYYY" in dico and dico["YYYY"][ID.SEED_FLAG]


def test_osm_icao_tag_is_kept_and_claims_the_overlapped_airport():
    dico = {"QQQQ": _osm("icao", "Tagged",
                         geometry.box(-118.44, 33.93, -118.38, 33.95))}
    assert ID.adopt_apt_dat_identities(dico, [BIG]) == 0
    assert set(dico) == {"QQQQ"}


def test_osm_code_known_to_apt_dat_keeps_its_key():
    dico = {"ZZZZ": _osm("icao", "Same",
                         geometry.box(-118.44, 33.93, -118.38, 33.95))}
    assert ID.adopt_apt_dat_identities(dico, [BIG]) == 0
    assert set(dico) == {"ZZZZ"} and dico["ZZZZ"]["key_type"] == "icao"


def test_implausible_extent_is_the_datum_only():
    # A stray boundary node half a world away (a real Global Airports row).
    stray = _entry("WT01", 33.86, -118.28, (0.74, -118.28, 33.86, 110.1),
                   category="airport", runway_m=450)
    dico = {"Blimp Base": _osm(
        "name", "Blimp Base", geometry.box(-118.29, 33.85, -118.27, 33.87),
        (-118.28, 33.86))}
    assert ID.adopt_apt_dat_identities(dico, [stray]) == 0
    # The datum lies inside the aerodrome: it is that airport, by point.
    assert set(dico) == {"WT01"} and dico["WT01"]["key_type"] == "local_ref"


def test_tile_selection_and_missing_index(tmp_path):
    cache = tmp_path / "index.tsv"
    assert ID.tile_apt_dat_airports(33, -119, str(cache), xplane_root="") == []
    cache.write_text(
        "O4AIRPORTIDX 6 3\n"
        "ZZZZ\tBig\t\t\t33.94\t-118.41\ticao_airport\t33.93\t-118.44\t33.95\t-118.38\t3000\t0\n"
        "HHHH\tPad\t\t\t33.5\t-118.5\theliport\t33.5\t-118.5\t33.5\t-118.5\t0\t9\n"
        "FARR\tFar\t\t\t40.0\t-100.0\ticao_airport\t39.9\t-100.1\t40.1\t-99.9\t2000\t2\n",
        encoding="utf-8")
    codes = [e.code for e in
             ID.tile_apt_dat_airports(33, -119, str(cache), xplane_root="")]
    assert codes == ["ZZZZ"]
