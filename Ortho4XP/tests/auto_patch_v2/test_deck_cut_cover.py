"""Twin of ``tools/deck_cut_cover`` (``deck_probe --cut-cover``; owner
2026-11-17 "Be sure the cut goes all the way under anywhere we add a
bridge"): a generated deck whose floor and banks are cut passes; a vertex
left at deck level under the ring fails; an edge from the crest across the
floor fails though its vertices pass; a road bridge's lower road with its
clearance passes, one standing in it fails."""
from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import numpy as np
from auto_patch_v2.law.tables import load_default

_SPEC = importlib.util.spec_from_file_location(
    "deck_cut_cover", Path(__file__).resolve().parents[2] / "tools" / "deck_cut_cover.py")
C = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(C)

LAW = load_default()
#: the bank under a generated deck (``deck_generated.generated_bank_slope``)
SLOPE = float(LAW.tables.zones.adjacent_ground.old_dem_fill_slope)
# a deck 40 m along x (end lines x = 0 and x = 40), 20 m wide, 6 m deep
DECK = types.SimpleNamespace(object_id="o4gen_t", witness="generated",
                             ring=((0, -10), (40, -10), (40, 10), (0, 10)),
                             seats_a=((0, -10), (0, 10)), seats_b=((40, -10), (40, 10)),
                             depth_a=6.0, depth_b=6.0)


def _pm(points, edges=()):
    vs = {i: types.SimpleNamespace(xy=p) for i, (p, _z) in enumerate(points)}
    es = {k: types.SimpleNamespace(id=k, a=a, b=b) for k, (a, b) in enumerate(edges)}
    anchors = (types.SimpleNamespace(object_id="o4gen_t", end="a", stations=(0,)),
               types.SimpleNamespace(object_id="o4gen_t", end="b", stations=(1,)))
    pm = types.SimpleNamespace(vertices=vs, edges=es, decks=(DECK,), deck_anchors=anchors)
    return pm, np.array([zz for _p, zz in points], float)


ENDS = [((0.0, 0.0), 10.0), ((40.0, 0.0), 10.0)]


def test_a_cut_floor_and_banks_pass():
    pm, z = _pm(ENDS + [((20.0, 0.0), 4.0), ((4.0, 5.0), 10.0 - SLOPE * 4.0)])
    (q,) = C.cut_cover(pm, z, None, LAW, 0.5)
    assert q["over"] == 0 and q["samples"] == 2


def test_ground_left_under_the_deck_fails():
    pm, z = _pm(ENDS + [((20.0, 0.0), 10.0)])
    (q,) = C.cut_cover(pm, z, None, LAW, 0.5)
    assert q["over"] == 1 and q["worst_m"] == 6.0


def test_an_edge_from_the_crest_across_the_floor_fails():
    """Vertices outside the ring at crest level and one on the floor: the
    edge between them stands over the bank inside the ring."""
    pts = ENDS + [((20.0, -30.0), 10.0), ((20.0, 30.0), 10.0)]
    pm, z = _pm(pts, edges=[(2, 3)])
    (q,) = C.cut_cover(pm, z, None, LAW, 0.5)
    assert q["over"] > 0 and q["worst_at"][2].startswith("e0")


def _bridge_airport(lower_z: float):
    road = types.SimpleNamespace(id="-9", tags={"highway": "service"},
                                 points=((20.0, -30.0), (20.0, 30.0)))
    b = {"id": "-1", "axis_xy": [[0, 0], [40, 0]], "levels": [10.0, 10.0],
         "span_xy": [[0, -4], [40, -4], [40, 4], [0, 4]], "over": ["-9"]}
    ap = types.SimpleNamespace(osm_ways=(road,), road_bridges=(b,), frame=None)
    pm = types.SimpleNamespace(vertices={0: types.SimpleNamespace(xy=(20.0, 0.0))},
                               edges={}, decks=(), deck_anchors=())
    return pm, np.array([lower_z]), ap


def test_a_road_bridge_with_its_clearance_passes_and_without_fails():
    pm, z, ap = _bridge_airport(5.5)
    (q,) = C.cut_cover(pm, z, ap, LAW, 0.5)
    assert q["over"] == 0 and q["lower"] == "-9"
    pm, z, ap = _bridge_airport(8.0)
    (q,) = C.cut_cover(pm, z, ap, LAW, 0.5)
    assert q["over"] == 1
