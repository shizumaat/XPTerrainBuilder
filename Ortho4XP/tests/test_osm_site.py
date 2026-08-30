"""Twins for ``tools/osm_site.py`` — the promoted site reader.

The tool it replaces existed twice (the round-20 lane's ``kclt_site.py``
for emitted patches and ``osmfeed.py`` for bz2 road feeds), and the two
copies had DRIFTED: one could read ``alt_abs``, the other could read
bz2, and neither could read the other's quoting dialect.  These twins pin
exactly that — one reader, both dialects, both containers — plus the
selection, ordering and filtering the callers rely on, and the fact that
the CLI prints what the library returns.

Headless: everything is built in ``tmp_path``; no network, no X-Plane
install, no corpus file is read.
"""
from __future__ import annotations

import bz2
import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import osm_site  # noqa: E402


PROBE = (35.2136411, -80.9422253)


def _patch_dialect() -> str:
    """The emitted-patch dialect: single quotes, per-node ``alt_abs``."""
    return (
        "<?xml version='1.0'?>\n<osm version='0.6'>\n"
        "  <node id='-1' action='modify' visible='true' "
        "lat='35.21364110' lon='-80.94222530'>\n"
        "    <tag k='alt_abs' v='206.36' />\n  </node>\n"
        "  <node id='-2' action='modify' visible='true' "
        "lat='35.21365000' lon='-80.94212000'>\n"
        "    <tag k='alt_abs' v='207.08' />\n  </node>\n"
        "  <node id='-3' action='modify' visible='true' "
        "lat='35.30000000' lon='-80.90000000' />\n"
        "  <way id='-100' action='modify' visible='true'>\n"
        "    <nd ref='-1' />\n    <nd ref='-2' />\n"
        "    <tag k='role' v='tunnel_ramp' />\n"
        "    <tag k='ref' v='tunnel_ramp' />\n  </way>\n"
        "  <way id='-200' action='modify' visible='true'>\n"
        "    <nd ref='-3' />\n"
        "    <tag k='role' v='apron' />\n  </way>\n"
        "</osm>\n"
    )


def _feed_dialect() -> str:
    """The road-feed dialect: double quotes, no altitudes."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<osm version="0.6" generator="Ortho4XP">\n'
        '  <node id="-75941" lat="35.2136411" lon="-80.9422253" '
        'version="1"/>\n'
        '  <node id="-75940" lat="35.2137920" lon="-80.9414489" '
        'version="1"/>\n'
        '  <way id="-9696" version="1">\n'
        '    <nd ref="-75941"/>\n    <nd ref="-75940"/>\n'
        '    <tag k="highway" v="service"/>\n  </way>\n'
        "</osm>\n"
    )


@pytest.fixture()
def patch_file(tmp_path: Path) -> Path:
    path = tmp_path / "arm.osm"
    path.write_text(_patch_dialect())
    return path


@pytest.fixture()
def feed_file(tmp_path: Path) -> Path:
    path = tmp_path / "feed.osm.bz2"
    with bz2.open(path, "wt") as handle:
        handle.write(_feed_dialect())
    return path


class TestBothDialects:
    """One reader, both quoting styles, plain and bz2 — the drift the
    two scratchpad copies had."""

    def test_reads_the_single_quoted_patch(self, patch_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(patch_file))
        assert set(nodes) == {"-1", "-2", "-3"}
        assert [w[0] for w in ways] == ["-100", "-200"]

    def test_reads_the_double_quoted_bz2_feed(self, feed_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(feed_file))
        assert set(nodes) == {"-75941", "-75940"}
        assert ways[0][0] == "-9696"
        assert ways[0][1] == ["-75941", "-75940"]

    def test_reads_an_uncompressed_feed(self, tmp_path: Path) -> None:
        path = tmp_path / "feed.osm"
        path.write_text(_feed_dialect())
        nodes, _ways = osm_site.read_osm(str(path))
        assert len(nodes) == 2

    def test_alt_abs_is_read_and_absence_is_none(
        self, patch_file: Path
    ) -> None:
        nodes, _ways = osm_site.read_osm(str(patch_file))
        assert nodes["-1"][2] == pytest.approx(206.36)
        # A vertex no authority claimed carries NO altitude — never a 0.0.
        assert nodes["-3"][2] is None

    def test_way_tags_survive_both_dialects(
        self, patch_file: Path, feed_file: Path
    ) -> None:
        _n, ways = osm_site.read_osm(str(patch_file))
        assert ways[0][2]["role"] == "tunnel_ramp"
        _n2, ways2 = osm_site.read_osm(str(feed_file))
        assert ways2[0][2]["highway"] == "service"


class TestSelection:
    def test_radius_excludes_the_far_way(self, patch_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(patch_file))
        near = osm_site.ways_near(nodes, ways, PROBE, 60.0)
        assert [row["way"] for row in near] == ["-100"]

    def test_a_wide_radius_admits_it(self, patch_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(patch_file))
        near = osm_site.ways_near(nodes, ways, PROBE, 20000.0)
        assert {row["way"] for row in near} == {"-100", "-200"}

    def test_rows_are_nearest_first(self, patch_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(patch_file))
        near = osm_site.ways_near(nodes, ways, PROBE, 20000.0)
        assert near == sorted(near, key=lambda r: r["distance_m"])

    def test_role_filter(self, patch_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(patch_file))
        near = osm_site.ways_near(nodes, ways, PROBE, 20000.0,
                                  role="apron")
        assert [row["way"] for row in near] == ["-200"]

    def test_alt_range_is_the_ways_own(self, patch_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(patch_file))
        row = osm_site.ways_near(nodes, ways, PROBE, 60.0)[0]
        assert row["alt_min"] == pytest.approx(206.36)
        assert row["alt_max"] == pytest.approx(207.08)
        assert row["nodes"] == 2

    def test_a_way_with_no_altitudes_reports_none(
        self, feed_file: Path
    ) -> None:
        nodes, ways = osm_site.read_osm(str(feed_file))
        row = osm_site.ways_near(nodes, ways, PROBE, 200.0)[0]
        assert row["alt_min"] is None and row["alt_max"] is None

    def test_distance_is_the_nearest_node_not_the_first(
        self, patch_file: Path
    ) -> None:
        nodes, ways = osm_site.read_osm(str(patch_file))
        row = osm_site.ways_near(nodes, ways, PROBE, 60.0)[0]
        assert row["distance_m"] == pytest.approx(0.0, abs=0.01)


class TestDump:
    def test_dump_keeps_way_order(self, feed_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(feed_file))
        rows = osm_site.dump_way(nodes, ways, "-9696", PROBE)
        assert [r["node"] for r in rows] == ["-75941", "-75940"]
        assert [r["i"] for r in rows] == [0, 1]
        assert rows[0]["distance_m"] == pytest.approx(0.0, abs=0.01)
        assert rows[1]["distance_m"] > 50.0

    def test_dump_of_an_unknown_way_is_empty(self, feed_file: Path) -> None:
        nodes, ways = osm_site.read_osm(str(feed_file))
        assert osm_site.dump_way(nodes, ways, "-1", PROBE) == []

    def test_a_dangling_nd_ref_is_reported_not_dropped(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "dangling.osm"
        path.write_text(
            "<osm version='0.6'>\n"
            "  <node id='-1' lat='35.2136411' lon='-80.9422253' />\n"
            "  <way id='-100'>\n    <nd ref='-1' />\n"
            "    <nd ref='-999' />\n  </way>\n</osm>\n")
        nodes, ways = osm_site.read_osm(str(path))
        rows = osm_site.dump_way(nodes, ways, "-100", PROBE)
        assert len(rows) == 2
        assert rows[1]["missing"] is True


class TestCli:
    """The CLI prints and dumps what the library returns — one code
    path, so a report and a caller's own read cannot disagree."""

    def test_json_matches_the_library(self, patch_file: Path,
                                      tmp_path: Path, capsys) -> None:
        out = tmp_path / "site.json"
        rc = osm_site.main([str(patch_file), "--at",
                            f"{PROBE[0]},{PROBE[1]}", "--radius", "60",
                            "--json", str(out)])
        assert rc == 0
        report = json.loads(out.read_text())
        nodes, ways = osm_site.read_osm(str(patch_file))
        assert report["files"][0]["near"] == osm_site.ways_near(
            nodes, ways, PROBE, 60.0)

    def test_several_files_are_reported_separately(
        self, patch_file: Path, feed_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "two.json"
        osm_site.main([str(patch_file), str(feed_file), "--at",
                       f"{PROBE[0]},{PROBE[1]}", "--radius", "200",
                       "--json", str(out)])
        report = json.loads(out.read_text())
        assert [entry["path"] for entry in report["files"]] == [
            str(patch_file), str(feed_file)]

    def test_tag_keys_filters_the_report_only(
        self, patch_file: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "keys.json"
        osm_site.main([str(patch_file), "--at",
                       f"{PROBE[0]},{PROBE[1]}", "--radius", "60",
                       "--tag-keys", "role", "--json", str(out)])
        report = json.loads(out.read_text())
        assert report["files"][0]["near"][0]["tags"] == {
            "role": "tunnel_ramp"}

    def test_dump_without_a_probe_is_allowed(self, feed_file: Path,
                                             tmp_path: Path) -> None:
        out = tmp_path / "dump.json"
        assert osm_site.main([str(feed_file), "--dump", "-9696",
                              "--json", str(out)]) == 0
        rows = json.loads(out.read_text())["files"][0]["dump"]
        assert "distance_m" not in rows[0]

    def test_a_bare_read_without_at_or_dump_is_refused(
        self, feed_file: Path
    ) -> None:
        with pytest.raises(SystemExit):
            osm_site.main([str(feed_file)])


class TestDsfRoadNetworkSource:
    """THE THIRD ROAD SOURCE (2026-08-28, LEMD ramp/road fidelity round).

    At LEMD the tile carries no small-roads extract and ``big_roads`` is
    empty at both tunnel sites: the corridors derive from the X-Plane DSF
    VECTOR ROAD NETWORK sidecar, which neither OSM dialect can read.  The
    sidecar's record types are the ENGINE's own
    (``auto_patch.dsf_road_network``) — these twins pin that this reader
    unpickles them rather than growing a second road parser.
    """

    @pytest.fixture()
    def sidecar(self, tmp_path: Path) -> Path:
        import pickle

        src = Path(__file__).resolve().parent.parent / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        from auto_patch.dsf_road_network import (
            RoadNetwork, RoadSegment, RoadShapePoint,
        )

        def _point(lon, lat, level=0.0):
            return RoadShapePoint(lon, lat, level, abs(level) < 0.5)

        network = RoadNetwork(
            network_definitions=["lib/g10/roads_EU.net"],
            segments=[
                # A long chain whose SHAPE POINTS straddle the probe: the
                # nearest node is far, the line passes right over it.
                RoadSegment(0, "lib/g10/roads_EU.net", 50, 18, 19, [
                    _point(-80.9422253, 35.2100000),
                    _point(-80.9422253, 35.2180000),
                ]),
                # An ELEVATED segment beside it (level 1 = a bridge).
                RoadSegment(0, "lib/g10/roads_EU.net", 60, 20, 21, [
                    _point(-80.9400000, 35.2130000, 1.0),
                    _point(-80.9400000, 35.2140000, 1.0),
                ]),
            ],
            skipped_line_count=0,
        )
        path = tmp_path / "o4_dsf_road_network_+35-081.cache"
        with open(path, "wb") as handle:
            pickle.dump({"fingerprint": "x", "result": network}, handle)
        return path

    def test_segments_read_as_ways_with_their_subtype(
        self, sidecar: Path
    ) -> None:
        nodes, ways = osm_site.read_site_file(str(sidecar))
        assert len(ways) == 2
        assert len(nodes) == 4
        tags = dict(ways[0][2])
        assert tags["source"] == "dsf-road-network"
        assert tags["road_subtype"] == "50"
        assert tags["draped"] == "all"
        assert tags["net_def"] == "lib/g10/roads_EU.net"
        assert dict(ways[1][2])["draped"] == "none"

    def test_the_level_flag_is_never_reported_as_an_altitude(
        self, sidecar: Path
    ) -> None:
        """The network's third column is a DRAPING LEVEL, not metres —
        reporting it as ``alt_abs`` would invent an elevation."""
        nodes, _ways = osm_site.read_site_file(str(sidecar))
        for _lat, _lon, alt, tags in nodes.values():
            assert alt is None
            assert "level" in tags and "draped" in tags

    def test_the_polyline_frame_finds_what_the_node_frame_misses(
        self, sidecar: Path
    ) -> None:
        """A DSF segment's shape points stand tens of metres apart while
        the road passes right over the probe — the whole reason the
        ``.cache`` container selects by POLYLINE."""
        nodes, ways = osm_site.read_site_file(str(sidecar))
        by_node = osm_site.ways_near(nodes, ways, PROBE, 60.0,
                                     by_line=False)
        by_line = osm_site.ways_near(nodes, ways, PROBE, 60.0,
                                     by_line=True)
        assert by_node == []
        assert [row["way"] for row in by_line] == ["seg0"]
        assert by_line[0]["line_distance_m"] == pytest.approx(0.0, abs=0.5)
        assert by_line[0]["distance_m"] > 60.0
        assert by_line[0]["selected_by"] == "line"

    def test_the_cli_declares_which_frame_it_selected(
        self, sidecar: Path, tmp_path: Path, capsys
    ) -> None:
        out = tmp_path / "site.json"
        osm_site.main([str(sidecar), "--at", f"{PROBE[0]},{PROBE[1]}",
                       "--json", str(out)])
        printed = capsys.readouterr().out
        assert "selected by polyline" in printed
        entry = json.loads(out.read_text())["files"][0]
        assert entry["selection_frame"] == "line"
        assert entry["near"][0]["way"] == "seg0"

    def test_by_node_forces_the_osm_frame_on_a_sidecar(
        self, sidecar: Path, capsys
    ) -> None:
        osm_site.main([str(sidecar), "--at", f"{PROBE[0]},{PROBE[1]}",
                       "--by-node"])
        assert "selected by nearest node" in capsys.readouterr().out

    def test_a_pickle_that_is_not_a_sidecar_is_refused(
        self, tmp_path: Path
    ) -> None:
        import pickle

        path = tmp_path / "not_a_network.cache"
        with open(path, "wb") as handle:
            pickle.dump({"fingerprint": "x", "result": 42}, handle)
        with pytest.raises(SystemExit):
            osm_site.read_site_file(str(path))


def test_tool_is_in_the_index() -> None:
    """RULINGS 7e90032 rule 1: a tool absent from the index is treated as
    absent, and every new tool lands WITH its index entry."""
    index = (Path(__file__).resolve().parents[2] / "tools" / "INDEX.md")
    assert index.exists(), index
    text = index.read_text()
    assert "Ortho4XP/tools/osm_site.py" in text
    # The 2026-08-28 extensions land WITH their index prose: a capability
    # absent from the index is treated as absent.
    assert "o4_dsf_road_network" in text


# ── CONTAINMENT (--contains / --line) ────────────────────────────────
#
# The SECOND question, and the reason it exists: ``--at`` reports the
# distance to a way's nearest NODE, so a point deep inside a big ring
# reads tens of metres away and never 0.00 m.  A lane read "1.20 m /
# 11.60 m outside" off exactly that, and a containment read then showed
# both owner probes 9.87 m and 3.88 m INSIDE the pad (spec
# ``lemd-basin-trench-ramp-extension`` Amendment 2).

_CENTRE = (40.4923132, -3.5697896)


def _square(latitude, longitude, half_metres):
    """A closed square ring about a point, as (lat, lon) corners."""
    import math
    lat_step = half_metres / 111320.0
    lon_step = half_metres / (111320.0 * math.cos(math.radians(latitude)))
    return [
        (latitude - lat_step, longitude - lon_step),
        (latitude - lat_step, longitude + lon_step),
        (latitude + lat_step, longitude + lon_step),
        (latitude + lat_step, longitude - lon_step),
        (latitude - lat_step, longitude - lon_step),
    ]


def _ring_patch(rings) -> str:
    """An emitted-dialect patch of closed rings.

    ``rings`` is ``[(way_id, role, ref, [(lat, lon), ...]), ...]``.
    """
    lines = ["<?xml version='1.0'?>", "<osm version='0.6'>"]
    node_id = -1
    way_lines = []
    for way_id, role, ref, points in rings:
        refs = []
        for latitude, longitude in points[:-1]:
            lines.append(
                f"  <node id='{node_id}' action='modify' visible='true' "
                f"lat='{latitude:.9f}' lon='{longitude:.9f}'>"
                "<tag k='alt_abs' v='100.0' /></node>")
            refs.append(node_id)
            node_id -= 1
        way_lines.append(
            f"  <way id='{way_id}' action='modify' visible='true'>"
            + "".join(f"<nd ref='{r}' />" for r in refs)
            + f"<nd ref='{refs[0]}' />"
            + f"<tag k='role' v='{role}' /><tag k='ref' v='{ref}' />"
            + "<tag k='altitude' v='100.0' /></way>")
    lines.extend(way_lines)
    lines.append("</osm>")
    return "\n".join(lines) + "\n"


def _big_ring_file(tmp_path) -> Path:
    path = tmp_path / "rings.osm"
    path.write_text(_ring_patch([
        ("-10008", "building", "building8",
         _square(*_CENTRE, 60.0)),
        ("-11774", "tunnel_trench", "object_basin_trench",
         _square(_CENTRE[0], _CENTRE[1] - 0.002, 20.0)),
    ]))
    return path


class TestContainment:
    def test_the_nearest_node_read_is_not_the_containment_read(
            self, tmp_path):
        """THE TRAP, pinned: the probe is at the ring's CENTRE, so
        ``--at`` reports ~60 m to the nearest node while containment
        says INSIDE.  Two questions, two answers, and quoting the first
        as the second is what had to be corrected."""
        path = _big_ring_file(tmp_path)
        nodes, ways = osm_site.read_osm(str(path))
        near = osm_site.ways_near(nodes, ways, _CENTRE, 200.0, "building")
        assert near and near[0]["distance_m"] > 50.0

        rings = osm_site._library_rings(str(path), _CENTRE)
        groups = osm_site.contains_at(rings, (0.0, 0.0))
        inside = {(g["role"], g["ref"]) for g in groups if g["inside"]}
        assert ("building", "building8") in inside

    def test_a_point_outside_every_ring_is_inside_nothing(self, tmp_path):
        path = _big_ring_file(tmp_path)
        far = (_CENTRE[0] + 0.01, _CENTRE[1])
        rings = osm_site._library_rings(str(path), far)
        assert not [g for g in osm_site.contains_at(rings, (0.0, 0.0))
                    if g["inside"]]

    def test_a_hole_ring_puts_the_point_OUTSIDE_its_own_group(
            self, tmp_path):
        """EVEN-ODD is what a hole IS.  The emitter ships an interior
        ring as its own closed way under the same ``ref``; counting
        "any ring covers it" would report a pad as covering ground it
        deliberately does not."""
        path = tmp_path / "holed.osm"
        path.write_text(_ring_patch([
            ("-1", "building", "b", _square(*_CENTRE, 60.0)),
            ("-2", "building", "b", _square(*_CENTRE, 10.0)),
        ]))
        rings = osm_site._library_rings(str(path), _CENTRE)
        groups = osm_site.contains_at(rings, (0.0, 0.0))
        assert len(groups) == 1
        assert groups[0]["covering_rings"] == 2
        assert groups[0]["inside"] is False

    def test_the_role_filter_scopes_the_containment(self, tmp_path):
        path = _big_ring_file(tmp_path)
        rings = osm_site._library_rings(str(path), _CENTRE)
        groups = osm_site.contains_at(rings, (0.0, 0.0), "tunnel_trench")
        assert groups == []

    def test_the_stations_cover_both_ends_of_the_line(self):
        start, end = (40.0, -3.0), (40.0, -3.0 + 0.0001)
        length = osm_site.metres_between(start, end)
        stations = osm_site.line_stations(start, end, 2.0)
        assert stations[0][2] == pytest.approx(0.0)
        assert stations[-1][2] == pytest.approx(length, abs=1e-6)
        gaps = [b[2] - a[2] for a, b in zip(stations, stations[1:])]
        assert all(gap <= 2.0 + 1e-9 for gap in gaps), gaps

    def test_a_degenerate_line_is_one_station_not_a_crash(self):
        assert len(osm_site.line_stations((40.0, -3.0), (40.0, -3.0),
                                          2.0)) == 1

    def test_the_cli_json_IS_the_library_result(self, tmp_path):
        """The CLI prints what the library returns — no second read."""
        path = _big_ring_file(tmp_path)
        out = tmp_path / "report.json"
        assert osm_site.main([
            str(path), "--at", f"{_CENTRE[0]},{_CENTRE[1]}",
            "--contains", "--json", str(out)]) == 0
        report = json.loads(out.read_text())
        groups = report["files"][0]["contains"]
        rings = osm_site._library_rings(str(path), _CENTRE)
        assert groups == osm_site.contains_at(rings, (0.0, 0.0))

    def test_the_line_sweep_reports_every_station(self, tmp_path):
        path = _big_ring_file(tmp_path)
        out = tmp_path / "line.json"
        assert osm_site.main([
            str(path),
            "--line", f"{_CENTRE[0]},{_CENTRE[1]}:"
                      f"{_CENTRE[0] + 0.001},{_CENTRE[1]}",
            "--step", "2", "--json", str(out)]) == 0
        rows = json.loads(out.read_text())["files"][0]["line"]
        assert len(rows) > 10
        assert rows[0]["inside"], "the first station is inside the pad"
        assert not rows[-1]["inside"], "the last station left every ring"

    def test_the_line_needs_two_points(self):
        with pytest.raises(SystemExit):
            osm_site.main(["x.osm", "--line", "40.0,-3.0"])

    def test_the_index_row_exists(self):
        """Tool discipline (RULINGS ``7e90032``): a tool — and a
        question a tool newly answers — lands with its index entry."""
        index = (Path(__file__).resolve().parent.parent.parent
                 / "tools" / "INDEX.md").read_text()
        assert "tools/osm_site.py" in index
        assert "--contains" in index


# ══════════════════════════════════════════════════════════════════
# --relate — the DUPLICATION question
# (spec ``docs/specs/othh-tunnel-mouth-canonical-spec.md``)
# ══════════════════════════════════════════════════════════════════
def _tiling_pair_file(tmp_path) -> Path:
    """Two rings that TILE — 0 m² overlap, a long shared edge.

    OTHH item 1 in miniature: service_road -10051 and tunnel_road
    -12306 carry ONE corridor, and `--at` reports them as two ordinary
    neighbours.  Only the shared-boundary length tells them apart from
    a genuine pair of adjacent surfaces.
    """
    import math
    lat, lon = _CENTRE
    lat_step = 40.0 / 111320.0
    lon_step = 40.0 / (111320.0 * math.cos(math.radians(lat)))
    left = [(lat - lat_step, lon - lon_step), (lat - lat_step, lon),
            (lat + lat_step, lon), (lat + lat_step, lon - lon_step),
            (lat - lat_step, lon - lon_step)]
    right = [(lat - lat_step, lon), (lat - lat_step, lon + lon_step),
             (lat + lat_step, lon + lon_step), (lat + lat_step, lon),
             (lat - lat_step, lon)]
    path = tmp_path / "tiling.osm"
    path.write_text(_ring_patch([
        ("-10051", "service_road", "", left),
        ("-12306", "service_road", "tunnel_road", right),
    ]))
    return path


class TestRelate:
    def test_a_tiling_pair_reads_as_zero_overlap_and_a_long_edge(
            self, tmp_path):
        path = _tiling_pair_file(tmp_path)
        nodes, ways = osm_site.read_osm(str(path))
        rings = osm_site._library_rings(str(path), _CENTRE)
        pairs = osm_site.relate_rings(rings, ["-10051", "-12306"])
        assert len(pairs) == 1
        row = pairs[0]
        assert row["overlap_m2"] == pytest.approx(0.0, abs=0.5)
        assert row["shared_edge_m"] > 70.0, (
            "the shared boundary is what says these are ONE surface")
        assert not row["a_inside_b"] and not row["b_inside_a"]
        assert len(nodes) == 8 and len(ways) == 2

    def test_an_overlapping_pair_reads_as_overlap(self, tmp_path):
        path = tmp_path / "nested.osm"
        path.write_text(_ring_patch([
            ("-1", "retaining_wall", "tunnel_wall",
             _square(*_CENTRE, 30.0)),
            ("-2", "retaining_wall", "tunnel_wall",
             _square(*_CENTRE, 10.0)),
        ]))
        rings = osm_site._library_rings(str(path), _CENTRE)
        row = osm_site.relate_rings(rings, ["-1", "-2"])[0]
        assert row["overlap_m2"] > 350.0
        assert row["b_inside_a"], "a nested ring must read as nested"

    def test_the_cli_prints_and_json_matches_the_library(self, tmp_path):
        path = _tiling_pair_file(tmp_path)
        out = tmp_path / "relate.json"
        osm_site.main([str(path), "--at", f"{_CENTRE[0]},{_CENTRE[1]}",
                       "--radius", "200", "--relate", "--json", str(out)])
        rows = json.loads(out.read_text())["files"][0]["relate"]
        rings = osm_site._library_rings(str(path), _CENTRE)
        assert rows == osm_site.relate_rings(rings, ["-10051", "-12306"])

    def test_the_index_row_names_relate(self):
        index = (Path(__file__).resolve().parent.parent.parent
                 / "tools" / "INDEX.md").read_text()
        assert "--relate" in index
