"""Twins of the #2181 / #2183 generated-bridge rules (``planar/deck_gen_cover``,
``planar/deck_gen_pairs``, ``planar/deck_pack_cover.overhead_decks``,
``pipeline/road_deck``): the cover ends where OSM maps the road open; a
road read from two extracts is one road; the deck carries the taxiway over
the pack's hole; two decks side by side within their banks' runs are one
cut; a road bridge within 2 x edge_margin rides the deck, farther off it is
its own narrow deck; a pack deck high over the crossing refuses nothing."""
from __future__ import annotations

import types

import pytest

from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.structures import DeckBridge
from auto_patch_v2.pipeline.road_deck import road_deck_records
from auto_patch_v2.planar.deck_gen_cover import bridge_ribbons, covered_state, distinct_ways
from auto_patch_v2.planar.deck_gen_pairs import (
    _pair_gap_m,
    _rider_gap_m,
    one_bridge,
    one_cut,
    riders,
)
from auto_patch_v2.planar.deck_pack_cover import overhead_decks
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

LAW = load_default()


def _way(wid, pts, **tags):
    return types.SimpleNamespace(id=wid, points=tuple(pts), tags=dict(tags), closed=False)


def test_covered_state_reads_tunnel_covered_and_layer():
    assert covered_state({"tunnel": "building_passage"})
    assert covered_state({"covered": "yes"})
    assert covered_state({"layer": "-1"})
    assert not covered_state({"highway": "primary"})
    assert not covered_state({"covered": "no", "tunnel": "no"})


def test_a_way_from_two_extracts_is_counted_once():
    a = _way(-1, [(0, 0), (65, 0)], tunnel="yes")
    b = _way(-2, [(65, 0), (0, 0)], tunnel="yes")          # the twin, reversed
    c = _way(-3, [(80, 0), (140, 0)], tunnel="yes")
    assert [w.id for w in distinct_ways([a, b, c])] == [-1, -3]


def _airport(ways):
    return types.SimpleNamespace(osm_ways=tuple(ways))


def test_the_deck_carries_the_taxiway_over_the_packs_hole():
    # taxiway pavement both sides of a 40 m hole the pack left under its
    # bridge object; the mapped bridge stops 4 m short of the north edge
    P = unary_union([box(-10, -100, 10, -20), box(-10, 20, 10, 100)])
    bridge = _way(-9, [(0, -24), (0, 16)], aeroway="taxiway", bridge="yes", layer="1")
    ribbons, notes = bridge_ribbons(P, _airport([bridge]), LAW)
    assert len(ribbons) == 1 and "hole" in notes[0]
    r = ribbons[0]
    assert r.contains(box(-9, -20, 9, 20))             # pavement to pavement
    assert abs(r.bounds[2] - r.bounds[0] - 20.0) < 0.5  # at the taxiway's width


def test_a_bridge_paved_across_gives_no_ribbon():
    P = box(-10, -100, 10, 100)
    bridge = _way(-9, [(0, -20), (0, 20)], aeroway="taxiway", bridge="yes", layer="1")
    assert bridge_ribbons(P, _airport([bridge]), LAW) == ([], [])


def _deck(oid, ring, covered=(), floor=6.0):
    return DeckBridge(oid, f"{oid}.obj", (), tuple(ring), ((0, 0),), ((0, 1),), 0.0, 0.0,
                      -floor, 0.0, floor_min_m=floor, witness="generated",
                      covered=tuple(covered))


def _ring(x0, x1, y0=0.0, y1=150.0):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def test_two_decks_side_by_side_are_one_cut():
    road_w = [(-1, (("highway", "primary"),), ((0.0, 75.0), (90.0, 75.0)))]
    road_e = [(-2, (("highway", "primary"),), ((106.0, 75.0), (200.0, 75.0)))]
    a = _deck("a", _ring(0, 98), road_w)
    b = _deck("b", _ring(106, 200), road_e)
    gap_road = _way(-3, [(90.0, 75.0), (106.0, 75.0)], highway="primary")
    out, notes = one_cut([a, b], [gap_road], LAW, lambda _t: 20.0)
    assert notes and "ONE cut" in notes[0]
    gap = unary_union([Polygon(q) for q in out[0].approach])
    assert gap.contains(box(98.5, 60, 105.5, 90))       # the strip between them leaves


def test_decks_farther_apart_than_their_banks_stay_two_cuts():
    a = _deck("a", _ring(0, 98), [(-1, (), ((0.0, 75.0), (98.0, 75.0)))])
    b = _deck("b", _ring(98 + _pair_gap_m(_deck("x", _ring(0, 1)), _deck("y", _ring(0, 1)), LAW)
                         + 1.0, 250), [(-2, (), ((140.0, 75.0), (250.0, 75.0)))])
    road = _way(-3, [(0.0, 75.0), (250.0, 75.0)], highway="primary")
    out, notes = one_cut([a, b], [road], LAW, lambda _t: 20.0)
    assert notes == [] and out[0].approach == ()


def test_a_road_beside_the_taxiway_is_no_reason_to_join_two_decks():
    a = _deck("a", _ring(0, 98, 0, 40), [(-1, (), ((0.0, 20.0), (98.0, 20.0)))])
    b = _deck("b", _ring(0, 98, 50, 90), [(-2, (), ((0.0, 70.0), (98.0, 70.0)))])
    along = _way(-3, [(50.0, -20.0), (50.0, 120.0)], highway="service")   # across both
    out, notes = one_cut([a, b], [along], LAW, lambda _t: 20.0)
    assert notes == []


def test_one_mapped_bridge_is_one_deck():
    R = unary_union([box(0, 0, 60, 30), box(0, 50, 60, 80)])
    merged = one_bridge(R, [LineString([(30, -5), (30, 85)])])
    assert merged.geom_type == "Polygon" and merged.contains(box(1, 31, 59, 49))
    assert one_bridge(R, [LineString([(100, -5), (100, 85)])]).equals(R)


def test_a_road_bridge_rides_the_deck_within_two_edge_margins():
    piece = box(0, 0, 60, 150)
    carried = box(10, 0, 60, 150)
    near = {"id": "-1818", "over": ["-1"], "axis_xy": [[7.0, 0.0], [7.0, 150.0]], "half_m": 2.5}
    far = {"id": "-1318", "over": ["-1"], "axis_xy": [[-40.0, 0.0], [-40.0, 150.0]],
           "half_m": 2.5}
    grown, ids, notes = riders(piece, carried, {"-1"}, [near, far], LAW)
    assert ids == ("-1818",)
    assert _rider_gap_m(LAW) == 2.0 * float(LAW.tables.structures.deck_gen.edge_margin_m)
    assert any("own deck" in n for n in notes)
    assert grown.contains(box(4.5, 1, 9.5, 149))


def _plate_obj(oid, ys):
    """A placed object of flat up-facing 10 m plates at heights ``ys``."""
    import numpy as np
    from auto_patch_v2.airport.obj8 import ObjGeometry
    vs, ts = [], []
    for k, y in enumerate(ys):
        x0 = 10.0 * k - 5.0
        n = len(vs)
        vs += [(x0, y, -5.0), (x0 + 10, y, -5.0), (x0 + 10, y, 5.0), (x0, y, 5.0)]
        ts += [(n, n + 2, n + 1), (n, n + 3, n + 2)]
    tris = np.asarray(ts, dtype=np.int64)
    g = ObjGeometry("x.obj", np.asarray(vs, dtype=float), tris, np.zeros(len(ts), dtype=np.int8),
                    np.zeros((0, 3), dtype=np.int64), np.zeros(len(ts), dtype=bool),
                    np.zeros(len(ts), dtype=bool))
    o = types.SimpleNamespace(id=oid, path=f"{oid}.obj", resolved=oid, xy=(0.0, 0.0),
                              heading_deg=0.0, hard_deck=box(-5, -5, 10 * len(ys) - 5, 5),
                              deck_top_z=100.0 + max(ys), anchor_z=100.0, agl_m=0.0)
    return o, g


def test_a_pack_deck_high_over_the_crossing_refuses_nothing():
    sky, gs = _plate_obj("sky", [30.0])
    twy, gt = _plate_obj("twy", [0.5, 12.0])       # at grade here, a tall top beside
    geoms = {"sky": gs, "twy": gt}
    cache = types.SimpleNamespace(geometry=lambda r: geoms.get(r))
    region = box(-4, -4, 4, 4)
    assert overhead_decks([sky, twy], cache, region, 100.0, LAW) == frozenset({"sky"})


def test_a_road_bridge_is_published_as_a_narrow_flat_deck():
    frame = types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (y * 1e-5, x * 1e-5)))
    airport = types.SimpleNamespace(frame=frame)
    b = {"id": "-301", "axis_xy": [[0.0, 0.0], [30.0, 0.0]], "half_m": 3.0,
         "levels": [344.1, 345.3], "ground": [], "junctions": [[0, 0, 0]], "subtype": 50,
         "net": "x", "span_wkt": "POLYGON EMPTY"}
    rider = dict(b, id="-1818")
    decks, kept = road_deck_records([b, rider], {"-1818"}, LAW, airport)
    assert [d["road_bridge"] for d in decks] == ["-301"]
    d = decks[0]
    assert d["family"] == "road" and d["zero_m"] == 344.1 and abs(d["top_b"] - 1.2) < 1e-6
    w = 3.0 + float(LAW.tables.structures.deck_gen.edge_margin_m)
    lats = [p[1] for p in d["ring"]]
    assert abs((max(lats) - min(lats)) * 1e5 - 2 * w) < 1e-6
    assert all("junctions" not in k for k in kept)     # no X-Plane chain is written


def test_the_object_stage_writes_a_road_deck_and_no_chain():
    from auto_patch_v2.airport.generated_pack import recipe
    frame = types.SimpleNamespace(
        transformers=lambda: (None, lambda x, y: (40.0 + y * 1e-5, -80.0 + x * 1e-5)))
    b = {"id": "-301", "axis_xy": [[0.0, 0.0], [30.0, 0.0]], "half_m": 3.0,
         "levels": [344.1, 345.3], "ground": [], "junctions": [[0, 0, 0]], "subtype": 50,
         "net": "x", "span_wkt": box(-80.0, 40.0, -79.9997, 40.00005).wkt}
    decks, kept = road_deck_records([b], set(), LAW, types.SimpleNamespace(frame=frame))
    rec = recipe({"decks": decks, "road_bridges": kept}, "", "TEST", LAW, xplane_root="")
    assert rec["chains"] == []
    assert rec["decks"] and all(r["resource"].endswith(".obj") for r in rec["decks"])
    assert abs(rec["decks"][0]["msl"] - 344.1) < 1e-6


def test_a_road_deck_spans_the_whole_cut_of_the_taxiway_deck_it_runs_along():
    """RULINGS 2026-11-19s (8) (d) (KPHX 1.0.566 ``-301`` / ``-302``): a road
    bridge over a generated deck's cut runs on to the deck's end lines, and
    each end stands at the solved ground there -- no floating end."""
    from auto_patch_v2.model.deck_carve import CarvePath, DeckCarve
    from auto_patch_v2.model.structures import GENERATED_WITNESS
    frame = types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (y * 1e-5, x * 1e-5)))
    airport = types.SimpleNamespace(frame=frame)
    # a taxiway deck along y (its route), its ends at y = -25 / +25 over a
    # road along x; its cut runs along the road far past the deck
    ring = ((-20.0, -25.0), (20.0, -25.0), (20.0, 25.0), (-20.0, 25.0))
    path = CarvePath("-1002", "road", 4.0, 5.0, 0.05, 1.0, ((-200.0, 0.0), (200.0, 0.0)),
                     (), ())
    db = DeckBridge("o4gen_t", "objects/o4_generated/deck_t.obj", (), ring,
                    ((-20.0, -25.0), (20.0, -25.0)), ((-20.0, 25.0), (20.0, 25.0)), 0.0, 0.0,
                    -6.0, 100.0, witness=GENERATED_WITNESS, floor_min_m=6.0,
                    route=((0.0, -100.0), (0.0, 100.0)),
                    carve=DeckCarve(("OSM road -1002",), "along OSM road -1002", (path,)))
    # the service road bridge 60 m east, mapped 30 m long across the road
    b = {"id": "-301", "axis_xy": [[60.0, -15.0], [60.0, 15.0]], "half_m": 3.0,
         "levels": [344.1, 345.3], "ground": [], "junctions": [[0, 0, 0]], "subtype": 50,
         "net": "x", "span_wkt": "POLYGON EMPTY"}
    decks, _kept = road_deck_records([b], set(), LAW, airport, [db],
                                     lambda xy: 340.0 + 0.01 * xy[1])
    d, = decks
    lats = [p[1] * 1e5 for p in d["route"]]
    assert min(lats) == pytest.approx(-25.0)
    assert max(lats) == pytest.approx(25.0)
    assert d["spans_cut"] == "o4gen_t"
    assert d["zero_m"] == pytest.approx(339.75)
    assert d["top_b"] == pytest.approx(0.5)
    # a bridge whose axis crosses no cut keeps its mapped ends
    far, _k = road_deck_records([dict(b, axis_xy=[[60.0, 30.0], [60.0, 60.0]])], set(), LAW,
                                airport, [db], lambda xy: 340.0)
    assert "spans_cut" not in far[0] and far[0]["zero_m"] == 344.1
