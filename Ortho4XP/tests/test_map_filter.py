"""#2097: the map's Filter menu logic (``O4_Map_Filter``; Mac twin
``MapFilter`` in MapFilter.swift)."""
import O4_Map_Filter as MAPFILTER


def test_stored_form_round_trips_in_menu_order():
    hidden = MAPFILTER.parse_hidden(["drape", "icao", "nonsense"])
    assert hidden == {"drape", "icao"}
    assert MAPFILTER.dump_hidden(hidden) == ["icao", "drape"]
    assert MAPFILTER.parse_hidden("small,full") == {"small", "full"}
    assert MAPFILTER.parse_hidden(None) == frozenset()
    assert not MAPFILTER.is_filtering(frozenset())


def test_an_airport_needs_its_kind_and_its_source():
    shows = MAPFILTER.shows_airport
    assert shows(frozenset(), True, False)
    assert not shows({"icao"}, True, True)
    assert shows({"icao"}, False, True)
    assert not shows({"global"}, False, False)
    assert shows({"global"}, True, True)


def test_a_tile_needs_any_of_its_items():
    shows = MAPFILTER.shows_tile
    assert shows(frozenset(), None)               # built, not in World
    assert not shows({"full"}, "full")
    assert shows({"full"}, "full", pinned=True)   # a Favorite
    assert not shows({"full", "favorites"}, "full", pinned=True)
    assert shows({"full"}, "drape")
    assert not shows({"drape"}, "drape")
    assert not shows(frozenset(), "nothing")
    assert not MAPFILTER.shows_other_ortho({"full"})
    assert MAPFILTER.shows_any_tile({"favorites", "full", "drape"})
    assert not MAPFILTER.shows_any_tile({"favorites", "full", "drape", "off"})
    assert MAPFILTER.shows_tile(frozenset(), "off")          # #2100
    assert not MAPFILTER.shows_tile({"off"}, "off")
    assert MAPFILTER.shows_tile({"full"}, "off")


def test_the_airport_patch_is_its_own_section():
    """#2214: "Airport patch" hides the zoomed-in airport's patch layer and
    touches no airport mark or tile."""
    assert MAPFILTER.SECTIONS[-1] == ("Patch", (("patch", "Airport patch"),))
    assert MAPFILTER.shows_patch(frozenset())
    assert not MAPFILTER.shows_patch({"patch"})
    assert MAPFILTER.dump_hidden({"patch", "icao"}) == ["icao", "patch"]
    assert MAPFILTER.shows_any_tile({"patch"})
    assert MAPFILTER.shows_airport({"patch"}, True, True)
