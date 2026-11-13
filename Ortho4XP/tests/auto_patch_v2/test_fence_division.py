"""RULINGS 2026-11-13s (#1338, #1854): A MAPPED CAR PARK IS NOT AIRSIDE BY
EDGE; A FENCE NEVER HAS AIRSIDE ON BOTH SIDES.

Owner 18:02Z: "Yes to car park mapping, and fence lines are another clear
indicator of a division, a fence cannot cross airside, so a fence can be
airside on one side and groundside on the other, or groundside on both,
but never airside on both sides of a fence."  Twins of
``classify/airside_edge`` (the §27 flip, both exemptions) and
``classify/fence_division`` (the fences, the band, the defect check)."""
from __future__ import annotations

import types

from auto_patch_v2.classify.airside_edge import airside_edge_flip, mapped_car_park
from auto_patch_v2.classify.fence_division import (
    FENCE_BARRIER_TAGS,
    airside_both_sides,
    fence_band,
    fence_lines,
)
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import EdgeLine, OsmWay
from shapely.geometry import LineString, box

LAW = Law.for_airport("SYNT")
RULES = load_rules()


def _flip(lot_evid, fences=None):
    final = [["apron", "pav1", box(0, 0, 100, 100), None, {}, "apron"],
             ["parking_lot", "pav2", box(100, 0, 200, 100), None,
              dict({"kind": "lot"}, **lot_evid), "lot"]]
    n, _r = airside_edge_flip(final, [], LAW, RULES, fences=fences)
    return n, final[1][0]


def test_a_mapped_car_park_is_not_flipped_by_its_apron_edge():
    """(1): a LOT by OSM car-park cover keeps its verdict along 100 m of
    apron; a lot by any other rung (12c's own LEMD shape 81) still flips."""
    frac = RULES.lot.parking_cover_fraction
    park = {"source_class": "lot", "source_parking_cover": frac}
    assert mapped_car_park(park, RULES)
    assert _flip(park) == (0, "parking_lot")
    assert _flip({"source_class": "lot", "source_parking_cover": frac - 0.01}) == (1, "apron")
    assert _flip({"source_class": "lot", "source_parking_cover": 0.0}) == (1, "apron")


def test_the_source_record_publishes_its_parking_cover():
    import dataclasses as dc

    from auto_patch_v2.classify.sources import SourceRecord
    f = {x.name: 0 for x in dc.fields(SourceRecord)}
    f.update(id="s", description="", cls="lot", reason="", taxi_name="",
             taxi_designator="", parking_cover=0.8)
    ev = SourceRecord(**f).as_evidence()
    assert ev["source_parking_cover"] == 0.8 and ev["source_class"] == "lot"


def test_airside_never_propagates_across_a_fence():
    """(2): a lot whose only airside contact is an edge a fence runs along
    stays groundside; a fence within ``[edge_lines] host_reach_m`` runs
    along it, one beyond does not."""
    reach = RULES.edge_lines.host_reach_m
    on = [("f", LineString([(100.0 + reach - 1.0, -5), (100.0 + reach - 1.0, 105)]))]
    off = [("f", LineString([(100.0 + reach + 5.0, -5), (100.0 + reach + 5.0, 105)]))]
    assert _flip({}, fence_band(on, RULES)) == (0, "parking_lot")
    assert _flip({}, fence_band(off, RULES)) == (1, "apron")
    assert fence_band([], RULES) is None
    # a fence along only part of the edge leaves the rest a contact
    short = [("f", LineString([(100.0, -5), (100.0, 50)]))]
    assert _flip({}, fence_band(short, RULES)) == (1, "apron")


def _cell(role, g):
    return types.SimpleNamespace(role=role, ring=tuple(g.exterior.coords)[:-1], holes=())


def test_airside_on_both_sides_of_a_fence_is_a_defect():
    fence = [("f", LineString([(100.0, 0), (100.0, 100)]))]
    both = [_cell("apron", box(0, 0, 100, 100)), _cell("apron", box(100, 0, 200, 100))]
    got = airside_both_sides(both, fence, LAW, RULES)
    assert got["fence_airside_both"] == 1 and got["fence_airside_both_m"] >= 90.0
    assert got["fence_airside_both_sites"][0][0] == "f"
    one = [_cell("apron", box(0, 0, 100, 100)), _cell("parking_lot", box(100, 0, 200, 100))]
    got = airside_both_sides(one, fence, LAW, RULES)
    assert got["fence_airside_both"] == 0 and got["fence_lines"] == 1


def test_the_fences_are_on_top_line_objects_and_osm_barriers():
    def el(base, solid_top):
        return EdgeLine("dsf:line0", "x.fac", ((0.0, 0.0), (50.0, 0.0)), False,
                        base, 2.0, solid_top, 0.5, 0.1)
    ways = [OsmWay(k, "fences", ((0.0, 10.0), (50.0, 10.0)), False, {"barrier": b})
            for k, b in enumerate(FENCE_BARRIER_TAGS + ("gate",))]
    ap = types.SimpleNamespace(edge_lines=(el(0.0, 0.2), el(-3.0, 2.0)), osm_ways=ways)
    ids = [i for i, _l in fence_lines(ap, RULES)]
    # the wire fence stands on its zero; the buried wall retains, it divides nothing
    assert ids == ["dsf:line0", "osm:0", "osm:1"]


def test_the_fence_feed_twins_the_engine_feed():
    import O4_Vector_Map as VM
    from auto_patch_v2.airport import osm as _osm
    assert _osm.FENCE_FEED in _osm.FEEDS and VM.FENCE_SUFFIX == _osm.FENCE_FEED
    assert VM.FENCE_CACHE_TAG_SCHEMA == _osm.FENCE_CACHE_TAG_SCHEMA
    assert set(VM.FENCE_TAGS_OF_INTEREST) == set(_osm.FENCE_TAGS_OF_INTEREST)
    assert "fences" in VM.TILE_BUILD_FEEDS and "fences" in VM.TILE_FEEDS
    assert {q.split('"')[3] for q in VM.FENCE_QUERIES[0]} == set(FENCE_BARRIER_TAGS)
    import sys
    from pathlib import Path
    harness = str(Path(__file__).resolve().parents[2] / "tools" / "harness")
    if harness not in sys.path:
        sys.path.insert(0, harness)
    import shared_repo_guard as G
    assert G.scope_of("OSM_data/-50+170/-42+174/-42+174_fences.osm.bz2") == "fences"


def test_a_lot_a_fence_crosses_flips_only_on_the_apron_side():
    """KCRW ``dsf:pol45``: one lot page with fences THROUGH it flipped
    whole.  The face is cut along the fence; the piece against the apron
    flips, the piece beyond the fence stays a lot; a fence across a lot
    nothing flips leaves it whole."""
    from auto_patch_v2.classify.airside_edge import EDGE_CANDIDATES
    from auto_patch_v2.classify.fence_division import rejoin_unsplit, split_at_fences
    fence = [("f", LineString([(150.0, -5), (150.0, 105)]))]
    final = [["apron", "pav1", box(0, 0, 100, 100), None, {}, "apron"],
             ["parking_lot", "pav2", box(100, 0, 200, 100), None, {"kind": "lot"}, "lot"],
             ["parking_lot", "pav3", box(500, 0, 600, 100), None, {"kind": "lot"}, "lot"]]
    fence.append(("g", LineString([(550.0, -5), (550.0, 105)])))
    cut = split_at_fences(final, fence, EDGE_CANDIDATES, RULES)
    assert sorted(cut) == [1, 2] and len(final) == 5
    airside_edge_flip(final, [], LAW, RULES, fences=fence_band(fence, RULES))
    assert rejoin_unsplit(final, cut) == 1
    roles = sorted((f[1].split("#")[0], f[0], round(f[2].centroid.x), round(f[2].area))
                   for f in final)
    assert roles == [("pav1", "apron", 50, 10000), ("pav2", "apron", 125, 5000),
                     ("pav2", "parking_lot", 175, 5000), ("pav3", "parking_lot", 550, 10000)]
    cells = [_cell(f[0], f[2]) for f in final]
    assert airside_both_sides(cells, fence, LAW, RULES)["fence_airside_both"] == 0


def test_a_fence_crossing_an_edge_runs_along_none_of_it():
    """A fence that meets the apron edge end-on (perpendicular) is no
    division of that edge: the lot still flips on it."""
    cross = [("f", LineString([(80.0, 50), (160.0, 50)]))]
    assert _flip({}, fence_band(cross, RULES)) == (1, "apron")
