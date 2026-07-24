"""Filter local OSM extracts into Overpass-equivalent XML
(docs/specs/osm-regional-extracts-spec.md section 5).

Headless: hand-written ``.osm`` XML fixtures under ``tmp_path`` (pyosmium
reads XML natively), no network, no pbf, no X-Plane install.  The final
round-trip test proves the emitted bytes feed ``OSM_layer.update_dicosm``
exactly like an Overpass response.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_OSM_Extract_Filter as FILTER  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers: build tiny .osm XML documents on disk.
# ---------------------------------------------------------------------------


def _osm_doc(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<osm version="0.6" generator="test-fixture">\n'
        + body
        + "</osm>\n"
    )


def _node(node_id, lat, lon, tags=None):
    tags = tags or {}
    head = '  <node id="%d" lat="%s" lon="%s" version="1"' % (node_id, lat, lon)
    if not tags:
        return head + "/>\n"
    out = head + ">\n"
    for k, v in tags.items():
        out += '    <tag k="%s" v="%s"/>\n' % (k, v)
    out += "  </node>\n"
    return out


def _way(way_id, refs, tags=None):
    tags = tags or {}
    out = '  <way id="%d" version="1">\n' % way_id
    for ref in refs:
        out += '    <nd ref="%d"/>\n' % ref
    for k, v in tags.items():
        out += '    <tag k="%s" v="%s"/>\n' % (k, v)
    out += "  </way>\n"
    return out


def _relation(rel_id, members, tags=None):
    """members: list of (type, ref, role) with type in {'way','node'}."""
    tags = tags or {}
    out = '  <relation id="%d" version="1">\n' % rel_id
    for mtype, ref, role in members:
        out += '    <member type="%s" ref="%d" role="%s"/>\n' % (mtype, ref, role)
    for k, v in tags.items():
        out += '    <tag k="%s" v="%s"/>\n' % (k, v)
    out += "  </relation>\n"
    return out


def _write(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(_osm_doc(body))
    return str(path)


# The bbox used by most tests: a 1x1 square around (0,0)..(1,1).
BBOX = (0.0, 0.0, 1.0, 1.0)


def _parse_ids(xml_bytes):
    """Cheap structural read of the emitted XML: returns (node_ids, way_ids,
    rel_ids) as ordered lists of the raw fixture ids, using the same
    line/quote conventions as the consumer."""
    nodes, ways, rels = [], [], []
    for line in xml_bytes.decode("utf-8").splitlines():
        items = line.split('"')
        if "<node id=" in items[0]:
            nodes.append(int(items[1]))
        elif "<way id=" in items[0]:
            ways.append(int(items[1]))
        elif "<relation id=" in items[0]:
            rels.append(int(items[1]))
    return nodes, ways, rels


# ---------------------------------------------------------------------------
# 1. tag + bbox match returns the way with all nodes; a same-tag way wholly
#    outside the bbox is not returned.
# ---------------------------------------------------------------------------


def test_matched_way_returned_with_nodes_outside_way_excluded(tmp_path):
    body = (
        _node(1, "0.5", "0.5")
        + _node(2, "0.6", "0.6")
        + _node(3, "5.0", "5.0")
        + _node(4, "5.1", "5.1")
        + _way(10, [1, 2], {"natural": "water"})
        + _way(20, [3, 4], {"natural": "water"})
    )
    path = _write(tmp_path, "a.osm", body)

    xml = FILTER.filter_extracts_to_osm_xml(
        [path], ['way["natural"="water"]'], BBOX
    )
    nodes, ways, rels = _parse_ids(xml)

    assert 10 in ways
    assert 20 not in ways  # wholly outside the bbox
    assert {1, 2} <= set(nodes)  # way 10's nodes came along
    assert 3 not in nodes and 4 not in nodes


# ---------------------------------------------------------------------------
# 2. a way with a DIFFERENT tag inside the bbox is not returned.
# ---------------------------------------------------------------------------


def test_wrong_tag_way_inside_bbox_excluded(tmp_path):
    body = (
        _node(1, "0.5", "0.5")
        + _node(2, "0.6", "0.6")
        + _way(10, [1, 2], {"highway": "residential"})
    )
    path = _write(tmp_path, "a.osm", body)

    xml = FILTER.filter_extracts_to_osm_xml(
        [path], ['way["natural"="water"]'], BBOX
    )
    _, ways, _ = _parse_ids(xml)
    assert ways == []


# ---------------------------------------------------------------------------
# 3. key-only statements match any value.
# ---------------------------------------------------------------------------


def test_key_only_statement_matches_any_value(tmp_path):
    body = (
        _node(1, "0.5", "0.5", {"aeroway": "gate"})
        + _node(2, "0.6", "0.6", {"aeroway": "helipad"})
        + _node(3, "0.7", "0.7", {"amenity": "bench"})
    )
    path = _write(tmp_path, "a.osm", body)

    xml = FILTER.filter_extracts_to_osm_xml([path], ['node["aeroway"]'], BBOX)
    nodes, _, _ = _parse_ids(xml)
    assert 1 in nodes and 2 in nodes
    assert 3 not in nodes  # no aeroway tag


# ---------------------------------------------------------------------------
# 4. a selected relation pulls in member ways/nodes lying OUTSIDE the bbox,
#    and the member ways' nodes come along (downward closure).
# ---------------------------------------------------------------------------


def test_relation_closure_pulls_outside_members(tmp_path):
    body = (
        # A node inside the bbox that anchors the relation.
        _node(1, "0.5", "0.5")
        # An outer way entirely OUTSIDE the bbox.
        + _node(2, "9.0", "9.0")
        + _node(3, "9.1", "9.1")
        + _way(50, [2, 3])
        # A member way that touches the bbox (node 1) so the relation is
        # selected even though its tag would otherwise need geometry proof.
        + _node(4, "0.4", "0.4")
        + _way(51, [1, 4])
        + _relation(
            100,
            [("way", 50, "outer"), ("way", 51, "outer")],
            {"waterway": "riverbank"},
        )
    )
    path = _write(tmp_path, "a.osm", body)

    xml = FILTER.filter_extracts_to_osm_xml(
        [path], ['rel["waterway"="riverbank"]'], BBOX
    )
    nodes, ways, rels = _parse_ids(xml)

    assert 100 in rels
    # Both member ways present, including the one fully outside the bbox.
    assert 50 in ways and 51 in ways
    # And the outside way's nodes came with it.
    assert 2 in nodes and 3 in nodes
    assert 1 in nodes and 4 in nodes


# ---------------------------------------------------------------------------
# 5. dedup across two extract files carrying the same element id.
# ---------------------------------------------------------------------------


def test_dedup_across_files_first_wins(tmp_path):
    body_a = (
        _node(1, "0.5", "0.5")
        + _node(2, "0.6", "0.6")
        + _way(10, [1, 2], {"natural": "water"})
    )
    body_b = (
        # Same ids, different coordinates: first file must win.
        _node(1, "0.9", "0.9")
        + _node(2, "0.8", "0.8")
        + _way(10, [1, 2], {"natural": "water"})
    )
    path_a = _write(tmp_path, "a.osm", body_a)
    path_b = _write(tmp_path, "b.osm", body_b)

    xml = FILTER.filter_extracts_to_osm_xml(
        [path_a, path_b], ['way["natural"="water"]'], BBOX
    )
    nodes, ways, _ = _parse_ids(xml)

    assert ways.count(10) == 1
    assert nodes.count(1) == 1 and nodes.count(2) == 1
    # First file's coordinates survived.
    assert 'lat="0.5000000"' in xml.decode("utf-8")
    assert 'lat="0.9000000"' not in xml.decode("utf-8")


# ---------------------------------------------------------------------------
# 6. round-trip through OSM_layer.update_dicosm.
# ---------------------------------------------------------------------------


def test_roundtrip_through_update_dicosm(tmp_path):
    import O4_OSM_Utils as OSM

    body = (
        _node(1, "0.5", "0.25")
        + _node(2, "0.6", "0.35")
        + _way(10, [1, 2], {"natural": "water"})
    )
    path = _write(tmp_path, "a.osm", body)

    xml = FILTER.filter_extracts_to_osm_xml(
        [path], ['way["natural"="water"]'], BBOX
    )

    layer = OSM.OSM_layer()
    # input_tags/target_tags None -> every way becomes a "first" catch, all
    # tags kept, mirroring a direct Overpass download.
    ret = layer.update_dicosm(xml, None, None)
    assert ret == 1

    assert len(layer.dicosmfirst["w"]) == 1
    wayid = next(iter(layer.dicosmfirst["w"]))
    assert layer.dicosmtags["w"][wayid]["natural"] == "water"
    assert len(layer.dicosmw[wayid]) == 2

    # Node coordinates are stored as (lon, lat); confirm they match the
    # fixture regardless of the parser's internal id remapping.
    coords = set(layer.dicosmn.values())
    assert (0.25, 0.5) in coords
    assert (0.35, 0.6) in coords


# ---------------------------------------------------------------------------
# 7. missing extract file raises ExtractFilterError.
# ---------------------------------------------------------------------------


def test_missing_extract_raises(tmp_path):
    missing = str(tmp_path / "does_not_exist.osm")
    with pytest.raises(FILTER.ExtractFilterError):
        FILTER.filter_extracts_to_osm_xml(
            [missing], ['way["natural"="water"]'], BBOX
        )


# ---------------------------------------------------------------------------
# 8. multi-box: one filtering pass selects elements inside ANY of the given
#    boxes and nothing between them (a bounding rectangle would leak those).
# ---------------------------------------------------------------------------


def test_multi_box_selects_all_boxes_and_nothing_between(tmp_path):
    body = (
        _node(1, "0.2", "0.2")
        + _node(2, "0.3", "0.3")  # in box A
        + _node(3, "2.2", "2.2")
        + _node(4, "2.3", "2.3")  # in box B
        + _node(5, "1.5", "1.5")
        + _node(6, "1.6", "1.6")  # between the boxes
        + _way(10, [1, 2], {"building": "yes"})
        + _way(20, [3, 4], {"building": "yes"})
        + _way(30, [5, 6], {"building": "yes"})
    )
    path = _write(tmp_path, "a.osm", body)

    boxes = [(0.0, 0.0, 1.0, 1.0), (2.0, 2.0, 3.0, 3.0)]
    xml = FILTER.filter_extracts_to_osm_xml([path], ['way["building"]'], boxes)
    nodes, ways, rels = _parse_ids(xml)

    assert 10 in ways and 20 in ways
    # Inside the boxes' bounding RECTANGLE but outside every box: excluded.
    assert 30 not in ways
    assert {1, 2, 3, 4} <= set(nodes)
    assert 5 not in nodes and 6 not in nodes


def test_single_box_tuple_and_one_element_list_are_equivalent(tmp_path):
    body = (
        _node(1, "0.5", "0.5")
        + _node(2, "0.6", "0.6")
        + _way(10, [1, 2], {"building": "yes"})
    )
    path = _write(tmp_path, "a.osm", body)

    as_tuple = FILTER.filter_extracts_to_osm_xml(
        [path], ['way["building"]'], BBOX
    )
    as_list = FILTER.filter_extracts_to_osm_xml(
        [path], ['way["building"]'], [BBOX]
    )
    assert as_tuple == as_list


# ---------------------------------------------------------------------------
# Clip cache: filtering a clip must be byte-identical to filtering the
# original extracts, for any statements and any bbox inside the clip box.
# ---------------------------------------------------------------------------


def _mixed_fixture(tmp_path):
    body = (
        _node(1, "0.5", "0.5", {"aeroway": "aerodrome"})
        + _node(2, "0.6", "0.6")
        + _node(3, "9.0", "9.0")          # far outside any query bbox
        + _node(4, "9.1", "9.1")
        + _way(50, [3, 4])                # entirely outside
        + _node(5, "0.4", "0.4")
        + _way(51, [2, 5], {"natural": "water"})
        + _way(52, [1, 2], {"highway": "primary"})
        + _relation(
            100,
            [("way", 50, "outer"), ("way", 51, "outer")],
            {"waterway": "riverbank"},
        )
    )
    return _write(tmp_path, "mixed.osm", body)


def test_clip_serves_identical_results(tmp_path):
    source = _mixed_fixture(tmp_path)
    clip = str(tmp_path / "clip.osm.pbf")
    # Clip box encloses the query bbox with margin, like production.
    FILTER.clip_extracts_to_pbf([source], (-0.05, -0.05, 1.05, 1.05), clip)

    for statements in (
        ['way["natural"="water"]'],
        ['rel["waterway"="riverbank"]'],
        ['node["aeroway"]', 'way["highway"]'],
    ):
        direct = FILTER.filter_extracts_to_osm_xml([source], statements, BBOX)
        via_clip = FILTER.filter_extracts_to_osm_xml([clip], statements, BBOX)
        assert via_clip == direct, statements


def test_clip_write_failure_raises_and_cleans_up(tmp_path):
    source = _mixed_fixture(tmp_path)
    target_dir = tmp_path / "missing-dir"
    with pytest.raises(FILTER.ExtractFilterError):
        FILTER.clip_extracts_to_pbf(
            [source], (-0.05, -0.05, 1.05, 1.05),
            str(target_dir / "clip.osm.pbf"))
    assert not target_dir.exists()


def test_concurrent_clips_of_same_target_both_succeed(tmp_path):
    """Two threads cutting the SAME clip path must not share a temp file.

    The 2026-07-23 field failure: concurrent query rounds cut the same
    clip, both writers used the pid-keyed temp name, and the loser's
    atomic rename died with ENOENT after minutes of work.  The temp name
    is now thread-unique, so even unserialized cutters both complete.
    """
    import threading

    source = _mixed_fixture(tmp_path)
    clip = str(tmp_path / "clip.osm.pbf")
    box = (-0.05, -0.05, 1.05, 1.05)
    errors = []

    def cut():
        try:
            FILTER.clip_extracts_to_pbf([source], box, clip)
        except Exception as error:   # noqa: BLE001 - the assertion target
            errors.append(error)

    threads = [threading.Thread(target=cut) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert os.path.isfile(clip)
    # No orphaned temp files either way.
    leftovers = [
        name for name in os.listdir(tmp_path) if ".tmp-" in name]
    assert leftovers == []


# ---------------------------------------------------------------------------
# osmium-tool clip cutting: cut_clip_with_osmium must uphold the exact
# clip contract — filtering the osmium-cut clip is BYTE-IDENTICAL to
# filtering the original extracts, for any statements and any bbox
# inside the clip box.  The relation-heavy fixtures below exercise the
# closure cases where the wrong strategy (plain complete_ways, which
# does not complete relation members) would diverge.
# ---------------------------------------------------------------------------

import shutil  # noqa: E402

_OSMIUM = shutil.which("osmium")
requires_osmium = pytest.mark.skipif(
    _OSMIUM is None, reason="osmium-tool binary not on PATH"
)

# The padded area box the clips are cut for, and the query bbox inside it.
CLIP_BOX = (-0.05, -0.05, 1.05, 1.05)


def _relation_heavy_fixture(tmp_path, name="rich.osm"):
    """An ORDERED extract (nodes, ways, relations, ids ascending — the
    layout osmium extract assumes) covering every relation-closure case:

    * rel 100: touches via member way 51; member way 50 lies entirely
      outside the clip box and member way 999 does not exist (dangling).
    * rel 101: type=route (NOT multipolygon — the case ``-S types=any``
      exists for); touches via way 52, drags in outside way 53.
    * rel 102: touches ONLY via member node 2; drags outside way 54.
    * rel 103: nested — carries rel 100 as a member (consumers ignore
      relation-in-relation, but the member line must survive verbatim).
    * rel 104: entirely outside the query bbox and the clip box; never
      selected, with or without it in the clip.
    """
    body = (
        _node(1, "0.5", "0.5", {"aeroway": "aerodrome"})
        + _node(2, "0.6", "0.6")
        + _node(3, "9.0", "9.0")
        + _node(4, "9.1", "9.1")
        + _node(5, "0.4", "0.4")
        + _node(6, "8.0", "8.0")
        + _node(7, "8.1", "8.1")
        + _node(8, "7.0", "7.0")
        + _node(9, "7.1", "7.1")
        + _way(50, [3, 4])
        + _way(51, [2, 5], {"natural": "water"})
        + _way(52, [1, 2], {"highway": "primary"})
        + _way(53, [6, 7], {"highway": "primary"})
        + _way(54, [8, 9])
        + _way(55, [1, 5], {"leisure": "park"})
        + '  <relation id="100" version="1">\n'
        + '    <member type="way" ref="50" role="outer"/>\n'
        + '    <member type="way" ref="51" role="outer"/>\n'
        + '    <member type="way" ref="999" role="outer"/>\n'
        + '    <tag k="type" v="multipolygon"/>\n'
        + '    <tag k="waterway" v="riverbank"/>\n'
        + "  </relation>\n"
        + _relation(
            101,
            [("way", 52, ""), ("way", 53, "")],
            {"type": "route", "route": "road"},
        )
        + _relation(
            102,
            [("node", 2, "admin_centre"), ("way", 54, "outer")],
            {"type": "boundary", "boundary": "administrative"},
        )
        + '  <relation id="103" version="1">\n'
        + '    <member type="relation" ref="100" role="inner"/>\n'
        + '    <member type="way" ref="55" role="outer"/>\n'
        + '    <tag k="waterway" v="riverbank"/>\n'
        + "  </relation>\n"
        + _relation(104, [("way", 50, "outer")], {"waterway": "riverbank"})
    )
    return _write(tmp_path, name, body)


_QUERY_SETS = (
    ['rel["waterway"="riverbank"]'],
    ['rel["route"]'],
    ['rel["boundary"="administrative"]'],
    ['node["aeroway"]', 'way["highway"]'],
    ['way["natural"="water"]', 'rel["waterway"="riverbank"]'],
)


@requires_osmium
def test_osmium_clip_filtering_is_byte_identical(tmp_path):
    source = _relation_heavy_fixture(tmp_path)
    osmium_clip = str(tmp_path / "osmium_clip.osm.pbf")
    FILTER.cut_clip_with_osmium([source], CLIP_BOX, osmium_clip, _OSMIUM)
    python_clip = str(tmp_path / "python_clip.osm.pbf")
    FILTER.clip_extracts_to_pbf([source], CLIP_BOX, python_clip)

    for statements in _QUERY_SETS:
        direct = FILTER.filter_extracts_to_osm_xml(
            [source], statements, BBOX)
        via_osmium = FILTER.filter_extracts_to_osm_xml(
            [osmium_clip], statements, BBOX)
        via_python = FILTER.filter_extracts_to_osm_xml(
            [python_clip], statements, BBOX)
        assert via_osmium == direct, statements
        assert via_python == direct, statements


@requires_osmium
def test_osmium_clip_relation_closure_content(tmp_path):
    """Spot-check the closure the strategy choice is load-bearing for:
    a selected relation's member way OUTSIDE the box arrives with its
    nodes (plain complete_ways would leave way 50 / nodes 3, 4 out)."""
    source = _relation_heavy_fixture(tmp_path)
    clip = str(tmp_path / "clip.osm.pbf")
    FILTER.cut_clip_with_osmium([source], CLIP_BOX, clip, _OSMIUM)

    xml = FILTER.filter_extracts_to_osm_xml(
        [clip], ['rel["waterway"="riverbank"]'], BBOX)
    nodes, ways, rels = _parse_ids(xml)
    assert 100 in rels and 103 in rels
    assert 104 not in rels
    assert 50 in ways and 51 in ways and 55 in ways
    assert {2, 3, 4, 5} <= set(nodes)


@requires_osmium
def test_osmium_clip_multiple_extracts_first_file_wins(tmp_path):
    """Two 'regions' carrying the same way id with DIFFERENT node
    coordinates (adjacent Geofabrik snapshots from different days): the
    per-region-cut-then-pyosmium-merge path must keep the first file's
    data, byte-identical to filtering the originals.  (A single
    ``osmium merge`` here would keep both versions — the reason the
    multi-extract path avoids it.)"""
    body_a = (
        _node(1, "0.5", "0.5")
        + _node(2, "0.6", "0.6")
        + _way(10, [1, 2], {"natural": "water"})
        + _way(11, [1, 2], {"highway": "primary"})
    )
    body_b = (
        _node(1, "0.9", "0.9")
        + _node(2, "0.8", "0.8")
        + _node(3, "0.7", "0.7")
        + _way(10, [1, 2], {"natural": "water"})
        + _way(12, [2, 3], {"natural": "water"})
    )
    path_a = _write(tmp_path, "region_a.osm", body_a)
    path_b = _write(tmp_path, "region_b.osm", body_b)
    clip = str(tmp_path / "clip.osm.pbf")
    FILTER.cut_clip_with_osmium([path_a, path_b], CLIP_BOX, clip, _OSMIUM)

    for statements in (
        ['way["natural"="water"]'],
        ['way["highway"]'],
    ):
        direct = FILTER.filter_extracts_to_osm_xml(
            [path_a, path_b], statements, BBOX)
        via_clip = FILTER.filter_extracts_to_osm_xml(
            [clip], statements, BBOX)
        assert via_clip == direct, statements
    # And the tie really went to the first file.
    xml = FILTER.filter_extracts_to_osm_xml(
        [clip], ['way["natural"="water"]'], BBOX).decode("utf-8")
    assert 'lat="0.5000000"' in xml
    assert 'lat="0.9000000"' not in xml


@requires_osmium
def test_osmium_clip_no_leftover_temporaries(tmp_path):
    source = _relation_heavy_fixture(tmp_path)
    clip = str(tmp_path / "clip.osm.pbf")
    FILTER.cut_clip_with_osmium([source], CLIP_BOX, clip, _OSMIUM)
    assert os.path.isfile(clip)
    leftovers = [n for n in os.listdir(tmp_path) if ".tmp-" in n]
    assert leftovers == []


def test_osmium_cut_stop_request_raises_before_spawn(tmp_path):
    source = _mixed_fixture(tmp_path)
    clip = str(tmp_path / "clip.osm.pbf")
    with pytest.raises(FILTER.ExtractFilterError):
        FILTER.cut_clip_with_osmium(
            [source], CLIP_BOX, clip, _OSMIUM or "osmium",
            should_stop=lambda: True)
    assert not os.path.exists(clip)
    leftovers = [n for n in os.listdir(tmp_path) if ".tmp-" in n]
    assert leftovers == []


def test_osmium_cut_failing_binary_raises_and_cleans_up(tmp_path):
    source = _mixed_fixture(tmp_path)
    clip = str(tmp_path / "clip.osm.pbf")
    # sys.executable balks at the osmium arguments and exits non-zero on
    # every platform — a stand-in for a broken or wrong-arch binary.
    with pytest.raises(FILTER.ExtractFilterError):
        FILTER.cut_clip_with_osmium([source], CLIP_BOX, clip, sys.executable)
    assert not os.path.exists(clip)
    leftovers = [n for n in os.listdir(tmp_path) if ".tmp-" in n]
    assert leftovers == []


def test_osmium_cut_rejects_multiple_boxes(tmp_path):
    source = _mixed_fixture(tmp_path)
    with pytest.raises(FILTER.ExtractFilterError):
        FILTER.cut_clip_with_osmium(
            [source], [CLIP_BOX, (2.0, 2.0, 3.0, 3.0)],
            str(tmp_path / "clip.osm.pbf"), _OSMIUM or "osmium")
