"""``object_seat`` (protocol 1.24, #1702): the object inspector's seat is
READ from the last build's placement plan, keyed by the DSF row, and the
ground under a draped row is ``cursor_elevation``'s."""
from __future__ import annotations

import json
import os

import O4_File_Names as FNAMES
import pytest
from o4_engine import elevation_commands as EC
from o4_engine import object_seat as OS

TILE = "+45-123"

PLAN = {
    "splits": [{"placement": {"index": 4, "resource": "objects/bridge.obj"},
                "bodies": [{"body_id": "b0", "surface_z": 100.0, "y_zero": 0.5},
                           {"body_id": "b1", "surface_z": 103.0, "y_zero": 0.0,
                            "lift_m": 1.0}]}],
    "msl_seats": [{"index": 7, "elevation": 250.25, "why": "unit"}],
    "riders": [{"index": 8, "seat_z": 90.0, "seat_why": "msl_written"},
               {"index": 9, "seat_z": None, "seat_why": "on_ground"}],
    "conversions": [{"index": 10, "kind_before": "OBJECT_AGL", "z_before": 3.0}],
    # a row the stage did not split may still be seated on its row
    "kept": [{"index": 7, "reason": "one_body"}, {"index": 11, "reason": "anim"}],
}


def test_each_row_under_its_strongest_section():
    e = OS._plan_entries(PLAN)
    assert {r: k for r, (k, _) in e.items()} == {
        4: "split", 7: "row", 8: "rider", 9: "rider", 10: "converted", 11: "kept"}


def test_split_reads_the_plan_body_zeros():
    entry = OS._plan_entries(PLAN)[4]
    rec = OS._seat_record(entry, agl_m=0.0, ground_m=None, y_min=-0.5, y_max=6.0)
    assert (rec["zero_m"], rec["zero_max_m"]) == (99.5, 104.0)
    assert (rec["bottom_m"], rec["top_m"], rec["height_m"]) == (99.0, 110.0, 6.5)
    assert rec["lines"][:3] == ["Height 6.5 m", "Top 110.0 m MSL", "Bottom 99.0 m MSL"]
    assert "2 bodies" in rec["lines"][-1] and not OS._needs_ground(entry)


@pytest.mark.parametrize("row, ground, want_zero", [
    (7, None, 250.25),        # a row seat: its elevation
    (8, None, 90.0),          # a written rider
    (9, 50.0, 50.0),          # a rider on the ground
    (10, 50.0, 50.0),         # converted: on the ground, the lift dropped
    (11, 50.0, 52.0),         # kept: as the pack places it, its lift kept
    (99, 50.0, 52.0),         # not in the plan: likewise
])
def test_row_seats(row, ground, want_zero):
    entry = OS._plan_entries(PLAN).get(row)
    assert OS._needs_ground(entry) == (ground is not None)
    rec = OS._seat_record(entry, agl_m=2.0, ground_m=ground, y_min=0.0, y_max=4.0)
    assert rec["zero_m"] == want_zero and rec["top_m"] == want_zero + 4.0


def test_command_reads_the_plan_beside_the_patch(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    path = OS._plan_path(TILE, "zzzz")
    os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(PLAN, fh)
    calls = []

    def ground(lat, lon, build_dir=None):
        calls.append((lat, lon))
        return {"elevation_m": 40.0, "source": "mesh", "pending": len(calls) == 1}
    monkeypatch.setattr(EC, "cursor_elevation", ground)
    rec = OS.object_seat(TILE, "ZZZZ", 7, 45.2, -122.9, y_min=0, y_max=3)
    assert rec["plan"] == "o4_v2_placement_ZZZZ.json" and rec["top_m"] == 253.25
    assert calls == []                                 # a row seat needs no ground
    first = OS.object_seat(TILE, "ZZZZ", 11, 45.2, -122.9, agl_m=1.0, y_min=0, y_max=3)
    assert first["pending"] and first["zero_m"] == 41.0
    again = OS.object_seat(TILE, "ZZZZ", 11, 45.2, -122.9, agl_m=1.0, y_min=0, y_max=3)
    assert not again["pending"] and again["bottom_m"] == 41.0


def test_no_plan_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    monkeypatch.setattr(EC, "cursor_elevation",
                        lambda lat, lon, build_dir=None: {"elevation_m": None, "pending": False})
    rec = OS.object_seat(TILE, "ZZZZ", 3, 45.2, -122.9, y_min=0, y_max=3)
    assert rec["plan"] is None and rec["top_m"] is None
    assert rec["lines"][-1].startswith("No placement plan from the last build")
    with pytest.raises(ValueError):
        OS.object_seat(TILE, "ZZZZ", "x", 45.2, -122.9)
