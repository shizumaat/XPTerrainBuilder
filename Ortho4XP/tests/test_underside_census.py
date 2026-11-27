"""``tools/underside_census.py``: today's seat read off a placement plan,
the S3 table, and its ``tools/INDEX.md`` row."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import underside_census as uc  # noqa: E402


def test_today_reads_each_body_zero_and_its_pad(tmp_path):
    plan = tmp_path / "o4_v2_placement_TEST.json"
    plan.write_text(json.dumps({"splits": [{"placement": {"index": 7}, "bodies": [
        {"surface_z": 366.70, "y_zero": 0.36,
         "anchor_reason": "§16g unit fu:1:2 of 4 member(s) on pad building21 at 366.34"},
        {"surface_z": 374.0, "y_zero": 0.0, "anchor_reason": "own ground"}]}]}),
        encoding="utf-8", newline="\n")
    got = uc.today_of(str(plan))
    assert got["dsf:obj7"][0] == (366.70 - 0.36, 366.34)
    assert got["dsf:obj7"][1] == (374.0, None)
    assert uc.today_of(None) == {}


def test_the_table_counts_verdicts_no_pad_and_gaps():
    rows = [{"verdict": "coherent", "D": 1.0, "stations": 4, "air_off": 0},
            {"verdict": "exception", "D": None, "stations": 6, "air_off": 0, "no_pad_gaps": 3},
            {"verdict": "composite", "D": 2.0, "stations": 9, "air_off": 2}]
    head, line = uc.table([{"icao": "TEST", "rows": rows, "seconds": 0.5}])
    assert head.split()[:3] == ["ICAO", "units", "coherent"]
    assert line.split() == ["TEST", "3", "1", "0", "1", "0", "1", "1", "1", "1", "0.50"]


def test_the_index_row():
    index = (ROOT.parent / "tools" / "INDEX.md").read_text(encoding="utf-8")
    assert "`Ortho4XP/tools/underside_census.py`" in index


def test_the_perimeter_report_counts_free_and_in_patch_overs():
    res = {"icao": "TEST", "path": "x.pkl", "seconds": 1.0, "grade": {"raised": 3},
           "perimeters": [{"unit": "u1", "res": "a.obj", "why": "coherent", "z0": 10.0,
                           "stations": 9, "far": 1},
                          {"unit": "u2", "res": "b.obj", "why": "no pad", "z0": 5.0,
                           "stations": 4, "far": 0}],
           "in_patch": [{"by_role": {"parking_lot": [5, 2, -0.7]}, "groundside": 5,
                         "groundside_over": 2},
                        {"by_role": {}, "groundside": 0, "groundside_over": 0}],
           "free_before": [{"over": 3}, {"over": 0}],
           "free_after": [{"free": 4, "over": 1, "boundary": 2, "patch": 3},
                          {"free": 4, "over": 0, "boundary": 0, "patch": 0}]}
    lines = uc.perimeter_lines(res)
    assert len(lines) == 3 and "a.obj" in lines[1] and "parking_lot 2/5" in lines[1]
    assert lines[-1].split("TOTAL ")[1].startswith("free stations 8: over 0.5 m 3 -> 1")
    assert "in-patch groundside 5: over 2" in lines[-1]
    assert "perimeter_judge" in (ROOT.parent / "tools" / "INDEX.md").read_text(encoding="utf-8")
