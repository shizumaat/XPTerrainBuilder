"""OWNER RULINGS 2026-10-04p (A, issue #8): THE WALL GATE AND THE ROAD
LEADS — both at the one trim, ``airport/road_ramp.wall_keyed``.

HECA ``route3`` shares its kerb with apron ``dsf:objpav433`` along the
wall ``metal_strip_2.obj`` (3.10 m) in three witness spans; the 57.4 m
gate between two of them dropped the terrace and eight ``meet`` anchors
held the road at its DEM, 3.08 m under the apron at the worst."""
from __future__ import annotations

from auto_patch_v2.airport.road_ramp import gate_merged, wall_keyed

CAP = 0.08            # any road cap: the rule reads it, never types it
H = 3.1


def _terr(walls, meet=()):
    st = {v: (5, float(s)) for v, s in
          ((1, 0.0), (2, 100.0), (3, 130.0), (4, 160.0), (5, 260.0),
           (6, 300.0), (7, 400.0))}
    st[50] = (9, 130.0)                          # a ribbon on another route
    own = {v: True for v in range(1, 8)}
    foot = {v: (100, 101, 0.5, "apron") for v in st}
    return {"foot": foot, "pad": {}, "station": st, "kerb": {},
            "meet": {v: True for v in meet}, "walled": {}, "own": own,
            "wall": walls}


def test_a_gap_no_longer_than_the_there_and_back_ramp_is_a_gate():
    gate = 2.0 * H / CAP                          # 77.5 m
    assert gate_merged([(0.0, 100.0, H), (100.0 + gate, 300.0, H)], CAP) \
        == [(0.0, 300.0, H)]
    assert gate_merged([(0.0, 100.0, H), (100.5 + gate, 300.0, H)], CAP) \
        == [(0.0, 100.0, H), (100.5 + gate, 300.0, H)]


def test_the_gate_reads_the_lower_wall_and_chains():
    # the second wall is 1 m: its ramp is 25 m, the 60 m gap is no gate
    assert len(gate_merged([(0.0, 100.0, H), (160.0, 260.0, 1.0)], CAP)) == 2
    # three spans chain; the merged span carries the lower height on
    got = gate_merged([(160.0, 260.0, H), (0.0, 100.0, H),
                       (300.0, 400.0, 2.0)], CAP)
    assert got == [(0.0, 400.0, 2.0)]


def test_no_cap_no_gate():
    spans = [(0.0, 100.0, H), (110.0, 200.0, H)]
    assert gate_merged(spans, None) == spans


def test_the_terrace_runs_through_the_gate():
    walls = {0: {"upper": [1, 2], "height_m": H},
             1: {"upper": [4, 5], "height_m": H}}
    out, left = wall_keyed(_terr(walls), CAP)
    # 100 -> 160 is a 60 m gate (<= 77.5): v3 at s 130 stays; 6, 7 leave
    assert left == 2 and {1, 2, 3, 4, 5} <= set(out["station"])
    assert 6 not in out["station"] and 7 not in out["foot"]
    # without the cap (10-03l alone) the gate drops the terrace
    out, left = wall_keyed(_terr(walls))
    assert left == 3 and 3 not in out["station"]


def test_inside_a_keyed_span_the_road_leads():
    walls = {0: {"upper": [1, 5], "height_m": H}}
    out, _left = wall_keyed(_terr(walls, meet=(3, 6, 50)), CAP)
    # the keyed own vertex loses its meet, the one that left the terrace
    # loses it with everything else, a ribbon's meet is untouched (10-03b)
    assert out["meet"] == {50: True}
    assert 3 in out["foot"] and 50 in out["foot"]
