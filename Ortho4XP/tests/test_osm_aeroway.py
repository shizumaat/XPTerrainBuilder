"""``auto_patch.osm_aeroway`` — the three extractors ``O4_Vector_Map``
calls in the tile build's vector phase (taxiway centrelines, building
footprints, big roads near the airport).

Production reaches all three on every tile build (measured: the OTHH
tile build of lane ``objtests``, 2026-10-04) and no test executed any of
them after the v1 cut (RULINGS 2026-10-04j "coverage owed").  Inputs are
what ``O4_Vector_Map`` hands over today: an ``OSM_layer``'s dicts and the
``dico_airports`` entries (tile-relative shapely geometry).
"""
from __future__ import annotations

from shapely.geometry import MultiPolygon, Polygon

from auto_patch import osm_aeroway as OA

from object_stage_support import OsmLayer, square, tile

TILE = tile(25, 51)
LON, LAT = 51.6, 25.3


def _rel(coords):
    """Absolute (lon, lat) -> the tile-relative frame ``dico_airports``
    geometry lives in."""
    return [(x - TILE.lon, y - TILE.lat) for x, y in coords]


def _boundary(half_deg: float = 0.02) -> MultiPolygon:
    return MultiPolygon([Polygon(_rel(square(LON, LAT, half_deg)))])


# ── taxiways ────────────────────────────────────────────────────────────


def test_taxiway_centrelines_are_absolute_and_carry_the_ref():
    layer = OsmLayer()
    named = layer.way([(LON, LAT), (LON + 0.001, LAT)], {"ref": "A1"})
    bare = layer.way([(LON, LAT), (LON, LAT + 0.001)])
    airports = {"OTHH": {"taxiway": (MultiPolygon(), [named, bare])}}
    out = OA.extract_taxiway_info(layer, airports, TILE)
    assert list(out) == ["OTHH"]
    assert out["OTHH"] == [
        {"centerline": [(LON, LAT), (LON + 0.001, LAT)],
         "wayid": named, "name": "A1"},
        {"centerline": [(LON, LAT), (LON, LAT + 0.001)],
         "wayid": bare, "name": ""},
    ]


def test_taxiway_extraction_skips_what_it_cannot_read():
    layer = OsmLayer()
    good = layer.way([(LON, LAT), (LON + 0.001, LAT)])
    one_node = layer.way([(LON, LAT)])
    layer.dicosmw[one_node].append(999_999)      # a node the layer lacks
    airports = {
        "PRE": {"taxiway": [good]},              # before build_taxiway_areas
        "NONE": {},                              # no taxiway key at all
        "EMPTY": {"taxiway": (MultiPolygon(), [])},
        "GONE": {"taxiway": (MultiPolygon(), [424242])},   # way not in layer
        "SHORT": {"taxiway": (MultiPolygon(), [one_node])},
        "OK": {"taxiway": (MultiPolygon(), [good, 424242, one_node])},
    }
    out = OA.extract_taxiway_info(layer, airports, TILE)
    assert list(out) == ["OK"]
    assert [t["wayid"] for t in out["OK"]] == [good]


def test_taxiway_extraction_reads_a_layer_with_no_tag_table():
    layer = OsmLayer()
    way = layer.way([(LON, LAT), (LON + 0.001, LAT)])
    del layer.dicosmtags
    out = OA.extract_taxiway_info(
        layer, {"X": {"taxiway": (MultiPolygon(), [way])}}, TILE)
    assert out["X"][0]["name"] == ""


# ── buildings ───────────────────────────────────────────────────────────


def test_hangars_come_back_in_absolute_coordinates():
    hangar_abs = square(LON, LAT, 0.0005)
    airports = {"OTHH": {"hangar": MultiPolygon([Polygon(_rel(hangar_abs))])}}
    out = OA.extract_building_info(OsmLayer(), airports, TILE)
    (building,) = out["OTHH"]
    assert building["source"] == "hangar"
    ring = building["footprint"]
    assert ring[0] == ring[-1] and len(ring) == 5
    for (x, y), (ex, ey) in zip(ring, hangar_abs):
        assert abs(x - ex) < 1e-9 and abs(y - ey) < 1e-9


def test_a_hangar_wayid_list_is_not_a_footprint():
    """Before ``build_hangar_areas`` the entry is a list of way ids; the
    extractor reads only the built MultiPolygon."""
    out = OA.extract_building_info(
        OsmLayer(), {"X": {"hangar": [1, 2, 3]}}, TILE)
    assert out == {}


def test_terminals_are_read_from_ways_and_relations_inside_the_boundary():
    layer = OsmLayer()
    inside = square(LON, LAT, 0.001)
    layer.way(inside, {"aeroway": "terminal"}, closed=True)
    layer.relation([square(LON + 0.005, LAT, 0.001)], {"aeroway": "terminal"})
    # outside the boundary, an OPEN way, a non-terminal: none is a terminal
    layer.way(square(LON + 0.5, LAT, 0.001), {"aeroway": "terminal"},
              closed=True)
    layer.way(inside, {"aeroway": "terminal"})
    layer.way(inside, {"aeroway": "apron"}, closed=True)
    layer.relation([square(LON, LAT, 0.001)], {"aeroway": "apron"})
    out = OA.extract_building_info(layer, {"OTHH": {"boundary": _boundary()}},
                                   TILE)
    assert [b["source"] for b in out["OTHH"]] == ["terminal", "terminal"]
    assert out["OTHH"][0]["footprint"][:4] == inside


def test_no_boundary_means_no_terminal_and_no_general_building():
    layer = OsmLayer()
    layer.way(square(LON, LAT, 0.001), {"aeroway": "terminal"}, closed=True)
    buildings = OsmLayer()
    buildings.way(square(LON, LAT, 0.001), {"building": "yes"}, closed=True)
    assert OA.extract_building_info(layer, {"X": {}}, TILE,
                                    building_layer=buildings) == {}


def test_general_buildings_join_unless_a_terminal_already_covers_them():
    layer = OsmLayer()
    terminal = square(LON, LAT, 0.001)
    layer.way(terminal, {"aeroway": "terminal"}, closed=True)
    buildings = OsmLayer()
    buildings.way(square(LON, LAT, 0.0009), {"building": "yes"},
                  closed=True)                              # the terminal again
    separate = square(LON + 0.01, LAT, 0.0005)
    buildings.way(separate, {"building": "hangar"}, closed=True)
    buildings.way(square(LON + 0.5, LAT, 0.0005), {"building": "yes"},
                  closed=True)                              # off the airport
    buildings.way(separate, {"highway": "service"}, closed=True)   # no building
    buildings.way(separate, {"building": "yes"})                   # open ring
    untagged = buildings.way(separate, closed=True)
    assert untagged not in buildings.dicosmtags["w"]
    out = OA.extract_building_info(
        layer, {"OTHH": {"boundary": _boundary()}}, TILE,
        building_layer=buildings)
    assert [b["source"] for b in out["OTHH"]] == ["terminal", "building"]
    assert out["OTHH"][1]["footprint"][:4] == separate


# ── roads ───────────────────────────────────────────────────────────────


def test_no_road_layer_is_an_empty_answer():
    assert OA.extract_road_info({"X": {"boundary": _boundary()}}, TILE) == {}


def test_big_roads_near_the_boundary_carry_type_tunnel_and_bridge():
    roads = OsmLayer()
    edge = LON + 0.02                                  # the boundary's east edge
    near = [(edge + 0.0002, LAT - 0.01), (edge + 0.0002, LAT + 0.01)]
    roads.way(near, {"highway": "motorway", "tunnel": "yes"})
    roads.way(near, {"highway": "trunk_link", "bridge": "yes"})
    roads.way(near, {"highway": "primary", "tunnel": "building_passage"})
    roads.way(near, {"highway": "residential"})        # not a big road
    roads.way(near, {"aeroway": "taxiway"})            # not a road
    roads.way([(edge + 0.2, LAT), (edge + 0.2, LAT + 0.01)],
              {"highway": "motorway"})                 # far from the airport
    lone = roads.way([(edge, LAT)], {"highway": "motorway"})
    assert len(roads.dicosmw[lone]) == 1               # under two nodes
    airports = {"OTHH": {"boundary": _boundary()}, "NOB": {}}
    out = OA.extract_road_info(airports, TILE, road_layer=roads)
    assert list(out) == ["OTHH"]
    assert [(r["highway_type"], r["tunnel"], r["bridge"])
            for r in out["OTHH"]] == [("motorway", True, False),
                                      ("trunk_link", False, True),
                                      ("primary", True, False)]
    assert all(r["centerline"] == near for r in out["OTHH"])


def test_the_road_reach_is_the_fifty_metre_influence_band():
    """A road is "near" inside ``ROAD_TERRAIN_INFLUENCE`` of the boundary
    and not beyond it — the constant, not a literal typed here."""
    reach_deg = OA.ROAD_TERRAIN_INFLUENCE / OA.DEG_TO_M
    edge = LON + 0.02
    roads = OsmLayer()
    for factor, kind in ((0.5, "primary"), (2.0, "secondary")):
        x = edge + factor * reach_deg
        roads.way([(x, LAT - 0.001), (x, LAT + 0.001)], {"highway": kind})
    out = OA.extract_road_info({"X": {"boundary": _boundary()}}, TILE,
                               road_layer=roads)
    assert [r["highway_type"] for r in out["X"]] == ["primary"]
