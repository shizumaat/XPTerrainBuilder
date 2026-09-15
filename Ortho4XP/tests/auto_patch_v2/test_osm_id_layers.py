"""ONE ID NAMESPACE ACROSS THE FEEDS (RULINGS 2026-09-15ap).

The cached layers under ``OSM_data/<10°>/<tile>/`` — ``airports``,
``airport_small_roads``, ``big_roads`` — are separate Overpass exports and
each MINTS ITS OWN NEGATIVE WAY IDS.  Measured at LEMD, 8 of 11 bridge-
deck ids carried two ways, five with an ``aeroway=taxiway`` first copy: a
first-copy read presented way ``-6288`` (``bridge=yes highway=service
lanes=4``) as ``highway=secondary`` and five ``bridge=yes`` decks as
tagless roads.  The loader (``airport/load.load_osm_ways``) now keys every
way by ``airport/osm.qualified_id`` — ``<feed>:<tile>:<raw>`` — at the ONE
loading site, so a consumer dict keyed on ``OsmWay.id`` cannot keep one
copy and silently drop the other.

These twins build a two-layer (then three-layer) fixture in ``tmp_path``
where the SAME negative id is a taxiway in one layer and a bridge in the
other, and read it through the real loading site.
"""
from __future__ import annotations

from pathlib import Path

from auto_patch_v2.airport import osm as O
from auto_patch_v2.airport.deck_signature import bridge_lines, is_bridge_way
from auto_patch_v2.airport.load import load_osm_ways
from auto_patch_v2.model.airport import OsmWay

#: the site: tile +40-004, the box centre inside it
LAT, LON = 40.47, -3.56
_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n'


def _way(wid: int, nodes: list[tuple[int, float, float]], tags: dict) -> str:
    body = "".join(f'  <node id="{n}" lat="{la}" lon="{lo}"/>\n' for n, la, lo in nodes)
    body += f'  <way id="{wid}">\n'
    body += "".join(f'    <nd ref="{n}"/>\n' for n, _la, _lo in nodes)
    body += "".join(f'    <tag k="{k}" v="{v}"/>\n' for k, v in tags.items())
    body += "  </way>\n"
    return body


def _feed(root: Path, feed: str, ways: str) -> Path:
    p = Path(O.feed_path(str(root), 40, -4, feed))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_HEAD + ways + "</osm>\n")
    return p


def _to_xy(lon: float, lat: float) -> tuple[float, float]:
    return ((lon - LON) * 85_000.0, (lat - LAT) * 111_000.0)


def _two_layer_root(tmp_path: Path) -> Path:
    """``-6288`` is an ``aeroway=taxiway`` in ``airports`` and a
    ``bridge=yes`` service road in ``big_roads`` — LEMD's own collision."""
    root = tmp_path / "OSM_data"
    _feed(root, "airports", _way(-6288, [(-1, 40.470, -3.560), (-2, 40.471, -3.560)],
                                  {"aeroway": "taxiway"}))
    _feed(root, "big_roads", _way(-6288, [(-1, 40.472, -3.565), (-2, 40.472, -3.563)],
                                   {"bridge": "yes", "highway": "service", "lanes": "4"}))
    return root


def test_the_same_negative_id_in_two_layers_arrives_as_two_keys(tmp_path):
    ways, _b, sources, _rep = load_osm_ways(str(_two_layer_root(tmp_path)),
                                            LAT, LON, 0.05, _to_xy)
    assert len(sources) == 2 and len(ways) == 2
    ids = {w.id for w in ways}
    assert ids == {"airports:+40-004:-6288", "big_roads:+40-004:-6288"}
    by_id = {w.id: w for w in ways}          # the consumer shape that collided
    assert len(by_id) == 2
    assert by_id["airports:+40-004:-6288"].tags == {"aeroway": "taxiway"}
    assert by_id["big_roads:+40-004:-6288"].tags["bridge"] == "yes"
    assert all(w.id.startswith(w.kind + ":") for w in ways)
    assert {O.raw_id(w.id) for w in ways} == {"-6288"}


def test_the_bridge_reader_names_the_ROAD_layers_copy(tmp_path):
    """The structure pass selects by tag and was right (15ap); its id now
    says which layer it read, so a witness joined by id cannot land on
    the taxiway."""
    ways, *_ = load_osm_ways(str(_two_layer_root(tmp_path)), LAT, LON, 0.05, _to_xy)
    decks = bridge_lines(ways)
    assert [wid for wid, _ln in decks] == ["big_roads:+40-004:-6288"]
    assert not any(is_bridge_way(w.tags) for w in ways if w.kind == "airports")


def test_two_ROAD_layers_minting_one_tunnel_id_keep_both_bores(tmp_path):
    """``structure_road`` keys its bore ends by way id across BOTH road
    feeds; small-roads ``-5`` and big-roads ``-5`` are two different
    bores and must be two dict entries."""
    root = _two_layer_root(tmp_path)
    tunnel = {"tunnel": "yes", "highway": "service", "layer": "-1"}
    _feed(root, "airport_small_roads",
          _way(-5, [(-1, 40.468, -3.560), (-2, 40.468, -3.558)], tunnel))
    _feed(root, "big_roads",
          _way(-6288, [(-1, 40.472, -3.565), (-2, 40.472, -3.563)],
               {"bridge": "yes", "highway": "service", "lanes": "4"})
          + _way(-5, [(-3, 40.475, -3.560), (-4, 40.475, -3.558)], tunnel))
    ways, *_ = load_osm_ways(str(root), LAT, LON, 0.05, _to_xy)
    bore_ends = {w.id: (w.points[0], w.points[-1]) for w in ways
                 if w.tags.get("tunnel") == "yes"}
    assert set(bore_ends) == {"airport_small_roads:+40-004:-5", "big_roads:+40-004:-5"}
    assert bore_ends["airport_small_roads:+40-004:-5"] != bore_ends["big_roads:+40-004:-5"]


def test_a_way_outside_the_box_is_not_loaded_and_a_missing_root_is_empty(tmp_path):
    root = _two_layer_root(tmp_path)
    _feed(root, "airport_small_roads",
          _way(-9, [(-1, 40.9, -3.9), (-2, 40.9, -3.89)], {"highway": "service"}))
    ways, *_ = load_osm_ways(str(root), LAT, LON, 0.05, _to_xy)
    assert {O.raw_id(w.id) for w in ways} == {"-6288"}
    assert load_osm_ways("", LAT, LON, 0.05, _to_xy) == ([], [], [], O.RelationReport())


def test_qualified_id_keeps_the_tile_and_a_stitched_ring_suffix_verbatim():
    """Nothing folded or hashed: a §25 stitched ring (``-2#0``) and a
    neighbouring tile's copy of the same raw id are distinct, readable
    keys, and ``raw_id`` gives the export's own id back."""
    assert O.qualified_id("airports", "+40-004:-2#0") == "airports:+40-004:-2#0"
    assert O.qualified_id("big_roads", "+40-004:-6288") != \
        O.qualified_id("big_roads", "+40-005:-6288")
    assert O.raw_id("big_roads:+40-004:-6288") == "-6288"
    assert O.raw_id("+40-004:-6288") == "-6288" and O.raw_id(-6288) == "-6288"
    assert O.raw_id("airports:+40-004:-2#0") == "-2#0"


def test_an_osm_building_id_carries_the_feed(tmp_path):
    root = _two_layer_root(tmp_path)
    ring = [(-11, 40.470, -3.550), (-12, 40.470, -3.549), (-13, 40.4705, -3.549),
            (-14, 40.4705, -3.550), (-11, 40.470, -3.550)]
    _feed(root, "airports", _way(-6288, [(-1, 40.470, -3.560), (-2, 40.471, -3.560)],
                                  {"aeroway": "taxiway"})
          + _way(-7, ring, {"building": "yes", "aeroway": "terminal"}))
    _ways, buildings, *_ = load_osm_ways(str(root), LAT, LON, 0.05, _to_xy)
    assert [b.id for b in buildings] == ["osm:airports:+40-004:-7"]


def test_a_synthetic_fixture_way_still_reads_as_one_key():
    """Fixtures pass a bare int; no consumer casts the id — it is a key."""
    w = OsmWay(-101, "big_roads", ((0.0, 0.0), (1.0, 0.0)), False, {"bridge": "yes"})
    assert {w.id: w}[-101] is w and O.raw_id(w.id) == "-101"
