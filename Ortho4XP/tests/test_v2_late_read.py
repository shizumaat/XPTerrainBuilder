"""Twin of ``tools/v2_late_read.py``'s part-aware bars (spec §55 (7), (14)):
a missed follow row is DECLARED when the stage refused that ring's bound on
that vertex (its own ``late_declared`` record) and OWN-GROUP otherwise; a
stepping pair at a merged station's ring is named a merged-sliver step."""
from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import v2_late_read as lr                                      # noqa: E402

from auto_patch_v2.constraints.gap_follow import GEN, RULING     # noqa: E402
from auto_patch_v2.law import Law                               # noqa: E402
from auto_patch_v2.model.constraints import Linear, Source      # noqa: E402

LAW = Law.for_airport("HECA")
PAD, ROAD = "building:building6", "service_road:route3"
#: vertex -> (level, faces): 1 across a knife from the pad's group, 2 on its
#: own road 0.5 m off, 3 a ribbon vertex 1.5 m off its road, 4 met
Z = {1: 99.0, 2: 96.5, 3: 97.5, 4: 96.0}
FACES = {1: ["groundside_pavement:gap:5/s2"], 2: ["groundside_pavement:gap:5/s2"],
         3: ["service_road:small_roads:-7"], 4: ["groundside_pavement:gap:5/s2"]}


def _row(v, lo, hi, ring):
    return Linear(((v, 1.0),), lo, hi, Source(GEN, RULING, (ring, ring)))


def _late(declared):
    rows = [_row(1, 91.9, 92.1, PAD), _row(2, 95.9, 96.0, ROAD),
            _row(3, 95.9, 96.0, ROAD), _row(4, 95.9, 96.1, ROAD)]
    merged = {"ring": PAD, "cls": "pad", "z": 92.0, "xy": (0.5, 0.0), "group": 1,
              "into_group": 0}
    return types.SimpleNamespace(
        icao="TEST", law=LAW, rows=rows, lot_rows=[], declared=declared, za=Z,
        grep={"conflicts": []},
        cut={"pieces": [{"ref": "gap:5", "conflicts_merged": [merged]}]},
        pa=types.SimpleNamespace(vertices={v: types.SimpleNamespace(xy=(float(v), 0.0))
                                           for v in Z}),
        names=lambda v: FACES[v], ll=lambda v: f"v{v}")


def test_a_miss_is_declared_by_the_stages_own_record_or_it_is_own_group():
    lines: list = []
    res = lr.read_follow(_late({(1, PAD)}), out=lines.append)
    assert (res["missed"], res["missed_declared"], res["missed_own_group"]) == (3, 1, 2)
    assert res["own_group_where"] == {"part <= floor": 1, "ribbon > floor": 1}
    assert res["own_group_worst_m"] == 1.5
    assert any("declared 6.90 m at v1" in x and "merged station" in x for x in lines)
    # the stage's record is the ONLY witness: without that bound refused,
    # the same miss beside the same merged station is the part's own
    assert lr.read_follow(_late(set()), out=lines.append)["missed_own_group"] == 3
    # an arm that predates the record: classed by the merged station near it
    assert lr.read_follow(_late(None), out=lines.append)["missed_declared"] == 1


def test_a_stepping_pair_at_a_merged_stations_ring_is_named(monkeypatch):
    L = _late(set())
    worst = {("gap:5/s2", PAD): (8.35, 1.45, "30.1,31.4", 100.4, 92.0),
             ("gap:5/s2", ROAD): (0.5, 1.45, "30.1,31.4", 96.6, 96.0),
             ("gap:5/s3", ROAD): (0.05, 1.45, "30.1,31.4", 96.0, 96.0)}
    monkeypatch.setattr(lr, "standoff_pairs", lambda _L: {
        "worst": worst, "area": {"gap:5/s2": 800.0, "gap:5/s3": 300.0},
        "stand": 1.45, "cap": 0.08, "step": 0.116})
    lines: list = []
    res = lr.read_standoff(L, 10, out=lines.append)
    assert res == {"pairs": 3, "stepping": 2, "stepping_big": 2,
                   "stepping_merged_sliver": 1}
    assert sum("MERGED-SLIVER" in x for x in lines[1:]) == 1
