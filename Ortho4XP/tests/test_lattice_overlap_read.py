"""LATTICE / SPINE-STATION OVERLAP READ — twins for
``tools/lattice_overlap_read.py`` (promoted 2026-08-27 from the
round3spine lane's scratchpad on its ~8th use, RULINGS ``7e90032``).

The tool answers a CONTAINMENT question no other instrument asks: does
an emitted apron-membrane segment leave the apron it belongs to?  A
census cannot — a breakline through a carved building breaks no grade
law and prices zero rows, which is how the defect the owner saw in the
sim (RULINGS 2026-08-26b item 1) shipped invisibly.

These twins pin what makes it trustworthy:
  * it PRICES NOTHING and registers no law family;
  * the footprint, the metre frame and the roles come from the harness
    library (``check_grade``), never re-spelled;
  * the FEATURE ways are parsed directly, because
    ``check_grade._parse_osm`` drops a way with fewer than three nodes
    before its open-feature route — the measured reason 13 of 18 HECA
    station crossings were invisible through that parser alone;
  * a segment inside its apron is not reported, one that leaves is, and
    what it passes through is named;
  * a patch with no sidecar is REFUSED (no anchor, no metre frame);
  * this index row exists.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lattice_overlap_read as LOR                        # noqa: E402

ANCHOR = (30.12, 31.40)


def _ll(x, y):
    """Metres east/north of ANCHOR -> (lat, lon), the frame
    ``check_grade._ll_to_m_factory`` inverts."""
    lat = ANCHOR[0] + y / 111320.0
    lon = ANCHOR[1] + x / (111320.0 * math.cos(math.radians(ANCHOR[0])))
    return lat, lon


def _patch(tmp_path, name, *, apron, membrane, other=None,
           feature="apron_lattice"):
    """One emitted patch: an ``apron`` ring, an optional other-role ring,
    and one membrane feature way.  Coordinates are in metres."""
    out = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    nid = [-1]
    ways = []

    def _way(pts, tags, close):
        nids = []
        for (x, y) in pts:
            lat, lon = _ll(x, y)
            out.append(f"  <node id='{nid[0]}' lat='{lat:.11f}' "
                       f"lon='{lon:.11f}'>\n"
                       f"    <tag k='alt_abs' v='100.00' />\n  </node>\n")
            nids.append(nid[0])
            nid[0] -= 1
        if close:
            nids.append(nids[0])
        ways.append((nids, tags))

    _way(apron, {"role": "apron", "aeroway": "apron"}, True)
    if other:
        _way(other[1], {"role": other[0]}, True)
    _way(membrane, {"o4_feature": feature}, False)
    wid = -900
    for nids, tags in ways:
        out.append(f"  <way id='{wid}'>\n")
        for n in nids:
            out.append(f"    <nd ref='{n}' />\n")
        for k, v in sorted(tags.items()):
            out.append(f"    <tag k='{k}' v='{v}' />\n")
        out.append("  </way>\n")
        wid -= 1
    out.append("</osm>\n")
    p = tmp_path / name
    p.write_text("".join(out))
    (tmp_path / (name + ".axes.json")).write_text(json.dumps(
        {"anchor": list(ANCHOR), "ruleset": "icao"}))
    return p


_SQUARE = [(-200, -200), (200, -200), (200, 200), (-200, 200)]
#: An L: the notch is the +x/+y quadrant.
_L = [(-200, -200), (200, -200), (200, -60), (-60, -60), (-60, 200),
      (-200, 200)]


def test_a_segment_inside_its_apron_is_not_reported(tmp_path):
    p = _patch(tmp_path, "ok.osm", apron=_SQUARE,
               membrane=[(-100, 0), (0, 0), (100, 0)])
    r = LOR.read(p)
    assert r["apron_lattice"]["ways"] == 1
    assert r["apron_lattice"]["segments"] == 2
    assert r["apron_lattice"]["outside"] == []
    assert r["apron_lattice"]["outside_total_m"] == 0.0


def test_a_segment_that_leaves_its_apron_is_reported_with_its_length(
        tmp_path):
    """The measured HECA class: two lawful endpoints, a chord across
    ground the apron does not own."""
    p = _patch(tmp_path, "notch.osm", apron=_L,
               membrane=[(100, -100), (100, 100)])
    r = LOR.read(p)["apron_lattice"]
    assert len(r["outside"]) == 1
    # the arm above ends at y = -60, so ~160 m of the 200 m chord is out
    assert 150.0 < r["outside"][0]["outside_m"] < 165.0
    assert r["outside_total_m"] == r["outside"][0]["outside_m"]


def test_what_the_segment_passes_through_is_named(tmp_path):
    """The attribution the fix is written against — role and way id."""
    hole = [(20, -40), (80, -40), (80, 40), (20, 40)]
    p = _patch(tmp_path, "through.osm", apron=_SQUARE,
               membrane=[(-150, 0), (150, 0)],
               other=("building", hole))
    r = LOR.read(p)["apron_lattice"]
    # The apron ring itself has no hole here, so the chord stays inside
    # the footprint: nothing is reported, and that is correct — the tool
    # judges CONTAINMENT IN THE APRON, not overlap with a neighbour.
    assert r["outside"] == []
    # ... but when the apron really is notched around that building the
    # same chord is an excursion, and the building is named.
    p2 = _patch(tmp_path, "through2.osm", apron=_L,
                membrane=[(100, -100), (100, 100)],
                other=("building", [(60, 0), (140, 0), (140, 80),
                                    (60, 80)]))
    hit = LOR.read(p2)["apron_lattice"]["outside"][0]
    assert any(role == "building" for (role, _wid, _m) in hit["through"])


def test_a_two_node_way_is_SEEN_here_and_not_by_the_census_parser(
        tmp_path):
    """THE reason this tool parses features itself.  Measured: 13 of 18
    HECA station crossings emitted as two-node ways, and
    ``check_grade._parse_osm`` drops those before its open-feature
    route — the tool then reported an apron as stationless while the
    patch carried stations on it."""
    import check_grade as CG
    p = _patch(tmp_path, "two.osm", apron=_L,
               membrane=[(100, -100), (100, 100)],
               feature="apron_spine_station")
    feats: dict = {}
    CG._parse_osm(p, feature_out=feats)
    assert feats.get("apron_spine_station", []) == [], \
        "the library parser is expected to drop the 2-node way"
    r = LOR.read(p)["apron_spine_station"]
    assert r["ways"] == 1 and r["segments"] == 1
    assert len(r["outside"]) == 1


def test_both_membrane_classes_are_swept_by_default():
    assert LOR.DEFAULT_FEATURES == ("apron_lattice", "apron_spine_station")


def test_the_tolerance_is_emit_rounding_not_a_law_threshold(tmp_path):
    p = _patch(tmp_path, "tol.osm", apron=_L,
               membrane=[(100, -100), (100, 100)])
    assert LOR.read(p, tolerance_m=1e6)["apron_lattice"]["outside"] == []
    assert LOR.read(p, tolerance_m=0.0)["apron_lattice"]["outside"]


def test_it_prices_no_law_and_registers_no_family():
    """A measurement, not a census.  A private row count here would be
    the census-wrapper defect."""
    import inspect
    src = inspect.getsource(LOR)
    for forbidden in ("LAW_FAMILIES", "run_checks", "Violation",
                      "adjudication", "_fam("):
        assert forbidden not in src, forbidden


def test_the_footprint_and_frame_come_from_the_harness_library():
    """Imported, never re-spelled."""
    import inspect
    src = inspect.getsource(LOR.read)
    assert "check_grade" in src
    assert "_parse_osm" in src and "_ll_to_m_factory" in src


def test_a_patch_with_no_sidecar_is_refused(tmp_path):
    p = _patch(tmp_path, "nos.osm", apron=_SQUARE,
               membrane=[(-100, 0), (100, 0)])
    (tmp_path / "nos.osm.axes.json").unlink()
    with pytest.raises(SystemExit) as e:
        LOR.main([str(p)])
    assert "axes.json" in str(e.value)


def test_the_cli_json_IS_the_library_result(tmp_path, capsys):
    p = _patch(tmp_path, "cli.osm", apron=_L,
               membrane=[(100, -100), (100, 100)])
    out = tmp_path / "r.json"
    assert LOR.main([str(p), "--json", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload[str(p)] == LOR.read(p)
    assert "leaving the apron footprint" in capsys.readouterr().out


def test_the_tool_is_in_the_index():
    """RULINGS ``7e90032``: a tool absent from the index is treated as
    absent, and every new tool lands WITH its index entry."""
    for cand in (_ROOT.parent / "tools" / "INDEX.md",
                 _ROOT / "tools" / "INDEX.md"):
        if cand.exists():
            text = cand.read_text()
            break
    else:                                                 # pragma: no cover
        pytest.skip("no tools/INDEX.md reachable from this checkout")
    assert "lattice_overlap_read.py" in text
    assert "_parse_osm" in text, \
        "the row must state why the tool parses features itself"


# ═════════════════════════════════════════════════════════════════════
# ``--on-edge`` — UNWELDED T-VERTICES, and the mesh needles they force
# (promoted 2026-08-28 from the lane/lemd123 scratch sweep, RULINGS
# ``7e90032``; spec docs/specs/lemd-rim-and-stations-spec.md §D)
# ═════════════════════════════════════════════════════════════════════

def test_a_node_ON_a_ring_edge_is_reported_as_unwelded(tmp_path):
    """The measured class: a station 2 cm inside the apron boundary, on
    an edge whose endpoints are 200 m away — a T-vertex with a value of
    its own against the ring's lerp."""
    p = _patch(tmp_path, "onedge.osm", apron=_SQUARE,
               membrane=[(-100, -199.98), (0, -199.98), (100, -199.98)],
               feature="apron_spine_station")
    r = LOR.read_on_edge(p)
    d = r["apron_spine_station"]
    assert d["nodes"] == 3
    assert d["shared_with_a_ring"] == 0
    assert d["on_edge_unwelded"] == 3
    row = d["rows"][0]
    assert row["host_role"] == "apron"
    assert row["perp_m"] == pytest.approx(0.02, abs=0.01)


def test_a_WELDED_node_is_not_reported(tmp_path):
    """The §A outcome: the station coordinate IS a ring vertex, so the
    node id is shared and there is one geometry, not two."""
    apron = [(-200, -200), (-100, -200), (0, -200), (100, -200),
             (200, -200), (200, 200), (-200, 200)]
    p = _patch(tmp_path, "welded.osm", apron=apron,
               membrane=[(-100, -200), (0, -200), (100, -200)],
               feature="apron_spine_station")
    r = LOR.read_on_edge(p)
    d = r["apron_spine_station"]
    assert d["on_edge_unwelded"] == 0, d["rows"]


def test_a_node_AT_an_edge_endpoint_is_that_endpoint_not_a_T_vertex(
        tmp_path):
    """``--vertex-tol`` is what makes an endpoint an endpoint: a node
    within it of a ring CORNER is the corner, not a T-vertex on the edge
    beside it."""
    p = _patch(tmp_path, "corner.osm", apron=_SQUARE,
               membrane=[(-199.9, -199.98), (0, 500), (100, 500)],
               feature="apron_spine_station")
    r = LOR.read_on_edge(p)
    assert r["apron_spine_station"]["on_edge_unwelded"] == 0


def test_a_node_well_INSIDE_the_apron_is_not_reported(tmp_path):
    p = _patch(tmp_path, "inside.osm", apron=_SQUARE,
               membrane=[(-100, 0), (0, 0), (100, 0)],
               feature="apron_spine_station")
    r = LOR.read_on_edge(p)
    assert r["apron_spine_station"]["on_edge_unwelded"] == 0


def test_the_value_TEAR_is_reported_against_the_hosts_own_lerp(tmp_path):
    """What the node costs: the station carries its own value where the
    ring says something else.  Worst measured at CYXY: 0.907 m."""
    p = _patch(tmp_path, "tear.osm", apron=_SQUARE,
               membrane=[(-100, -199.98), (0, -199.98), (100, -199.98)],
               feature="apron_spine_station")
    r = LOR.read_on_edge(p)
    row = r["apron_spine_station"]["rows"][0]
    # the fixture writes every node at 100.00, so the tear is zero — the
    # point is that it is COMPUTED against the host's lerp, per host.
    assert row["tears"], "no host lerp was priced at all"
    assert row["worst_tear_m"] == pytest.approx(0.0, abs=1e-6)


# ── the needle read (owner sim load-time regression, 2026-08-28b) ────

def test_an_unwelded_run_reports_NEAR_PARALLEL_pairs(tmp_path):
    """The mesh cost of the same defect: two constrained segments ~2 cm
    apart and parallel force a needle fan along the whole collinear run.
    Measured on the owner's +30+031 tile: aspect p99 43,275 against a
    ~23 baseline, and the worst cell's 8 of 12 near-parallel pairs were
    apron ring x apron_spine_station."""
    p = _patch(tmp_path, "needles.osm", apron=_SQUARE,
               membrane=[(-100, -199.98), (0, -199.98), (100, -199.98)],
               feature="apron_spine_station")
    np_ = LOR.read_on_edge(p)["near_parallel_pairs"]
    assert np_["feature_x_ring"], "the needle source went unreported"
    assert np_["by_class_and_role"].get(
        "apron_spine_station x apron") == len(np_["feature_x_ring"])
    assert np_["feature_x_ring"][0]["gap_m"] == pytest.approx(0.02,
                                                              abs=0.01)


def test_a_WELDED_run_reports_NO_near_parallel_pair(tmp_path):
    """The acceptance: welding removes the needle source, not just the
    value tear."""
    apron = [(-200, -200), (-100, -200), (0, -200), (100, -200),
             (200, -200), (200, 200), (-200, 200)]
    p = _patch(tmp_path, "nofan.osm", apron=apron,
               membrane=[(-100, -200), (0, -200), (100, -200)],
               feature="apron_spine_station")
    np_ = LOR.read_on_edge(p)["near_parallel_pairs"]
    assert np_["feature_x_ring"] == [], np_["feature_x_ring"]


def test_END_TO_END_collinear_segments_are_a_weld_not_a_needle():
    """All three conditions are needed.  Two segments laid end to end
    are at zero distance and perfectly parallel and are not a needle
    source; only a shared RUN is."""
    a = ((0.0, 0.0), (10.0, 0.0))
    end_to_end = ((10.0, 0.0), (20.0, 0.0))
    side_by_side = ((2.0, 0.02), (8.0, 0.02))
    assert LOR._near_parallel(a, end_to_end) is None
    assert LOR._near_parallel(a, side_by_side) is not None
    # ...and a crossing pair is not one either
    assert LOR._near_parallel(a, ((5.0, -5.0), (5.0, 5.0))) is None


def test_apron_x_apron_pairs_are_reported_SEPARATELY(tmp_path):
    """A SECOND, older needle source, named and never conflated with the
    station class: two apron rings tracing one boundary with
    non-identical spellings."""
    p = _patch(tmp_path, "twin_rings.osm", apron=_SQUARE,
               membrane=[(-100, 0), (0, 0), (100, 0)],
               other=("apron", [(-200, -200.05), (200, -200.05),
                                (200, -400), (-200, -400)]))
    np_ = LOR.read_on_edge(p)["near_parallel_pairs"]
    assert np_["apron_x_apron"], "the twin-ring boundary went unreported"
    assert np_["feature_x_ring"] == []


def test_the_CLI_on_edge_JSON_is_the_library_result(tmp_path, capsys):
    p = _patch(tmp_path, "cli.osm", apron=_SQUARE,
               membrane=[(-100, -199.98), (0, -199.98), (100, -199.98)],
               feature="apron_spine_station")
    out = tmp_path / "out.json"
    assert LOR.main([str(p), "--on-edge", "--json", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload[str(p)] == json.loads(json.dumps(LOR.read_on_edge(p)))
    assert "sit ON a ring edge" in capsys.readouterr().out


def test_the_on_edge_read_still_REFUSES_without_a_sidecar(tmp_path):
    p = _patch(tmp_path, "nosidecar.osm", apron=_SQUARE,
               membrane=[(-100, 0), (0, 0), (100, 0)])
    (tmp_path / "nosidecar.osm.axes.json").unlink()
    with pytest.raises(SystemExit):
        LOR.main([str(p), "--on-edge"])


def test_the_index_row_documents_the_on_edge_subcommand():
    index = (_ROOT.parent / "tools" / "INDEX.md").read_text()
    row = [ln for ln in index.splitlines()
           if "lattice_overlap_read.py" in ln]
    assert row, "the tool has no INDEX.md row"
    assert "--on-edge" in row[0]
    assert "144" in row[0], "the measured basis is not in the row"
