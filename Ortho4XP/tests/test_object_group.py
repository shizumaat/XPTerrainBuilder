"""An object group moves as one (issue #1970): a placement the plan cut
into parts is selected and re-heighted with its group — every row cut
into bodies of the same structure units, read from the placement plan —
and the pack DSF's write lifts every body of the group by one offset.

Synthetic plan beside a ``tmp_path`` patch; no network, no build."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace as NS

import O4_File_Names as FNAMES
import pytest
from auto_patch_v2.airport import user_seats as US
from auto_patch_v2.model import placement as P
from o4_engine import object_group as OG
from o4_engine import object_seat as OS
from o4_engine import object_seat_edit as OSE

TILE = "+45-123"


def _body(bid, unit, z, box, res):
    """One plan body; ``box`` is ``(s, w)``, a 20 m square from there."""
    box = [box[0], box[1], box[0] + 0.0002, box[1] + 0.0002]
    return {"body_id": bid, "class": "other", "new_resource": res,
            "anchor": {"lat": box[0], "lon": box[1], "heading": 0.0},
            "unit_of": unit, "surface_z": z, "y_zero": 0.5, "geom_box": box}


def _split(index, res, lat, lon, bodies):
    return {"placement": {"index": index, "resource": res, "lat": lat, "lon": lon,
                          "heading": 0.0}, "bodies": bodies}


#: A hangar authored as material layers (the KBZN shape): rows 1, 2 and 4
#: are cut into bodies of units u1 / u2 (one group); row 3 stands apart;
#: row 0 was not cut; row 5 was kept whole (its seat landed on the authored
#: one) but seated in unit u2 — it stays and moves with the group (owner
#: RULINGS 2026-11-09a (15); LFMN's Terminal2/3/4 in the T1 unit).
PLAN = {
    "version": 2, "icao": "ZZZZ", "dsf_path": "",
    "splits": [
        _split(1, "objects/walls.obj", 45.1, -122.9,
               [_body("b0", "u1", 100.5, (45.1, -122.9), "objects/walls__b0.obj"),
                _body("b1", "u2", 50.5, (45.1004, -122.9), "objects/walls__b1.obj")]),
        _split(2, "objects/roof.obj", 45.1, -122.9,
               [_body("b0", "u1", 101.0, (45.1, -122.9), "objects/roof__b0.obj")]),
        _split(3, "objects/far.obj", 45.2, -122.8,
               [_body("b0", "u3", 70.5, (45.2, -122.8), "objects/far__b0.obj")]),
        _split(4, "objects/fence.obj", 45.1, -122.9,
               [_body("b0", None, 60.5, (45.1008, -122.9), "objects/fence__b0.obj"),
                _body("b1", "u2", 50.5, (45.1004, -122.9), "objects/fence__b1.obj")]),
    ],
    "kept": [{"index": 0, "resource": "objects/a.obj", "reason": "stock"},
             {"index": 5, "resource": "objects/wing.obj", "reason": "authored_seat_lands",
              "units": ["u2"], "lat": 45.1012, "lon": -122.9, "zero_m": 49.8}],
}


@pytest.fixture
def plan(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    path = OS._plan_path(TILE, "ZZZZ")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(PLAN, fh)
    return OS._entries(path)


def test_the_group_is_the_component_of_rows_and_units(plan):
    assert OG.group_rows(plan, 2) == OG.group_rows(plan, 4) == (1, 2, 4, 5)
    assert OG.group_rows(plan, 5) == (1, 2, 4, 5)       # kept whole, in u2
    assert OG.group_rows(plan, 3) == (3,)
    assert OG.group_rows(plan, 0) == (0,)               # not cut, no unit: alone
    assert not OG.in_group(plan, 0) and OG.in_group(plan, 5) and OG.in_group(plan, 3)
    assert OG._source_names(plan, (1, 2, 4, 5)) == ["fence.obj", "roof.obj", "walls.obj",
                                                    "wing.obj"]
    assert len(OG._group_ring(OG._group_bodies(plan, (1, 2, 4)))) >= 3


def test_clicking_any_part_answers_for_its_whole_group(plan):
    rec = OS.object_seat(TILE, "ZZZZ", 2, 45.1, -122.9)
    assert rec["seat"] == "group" and rec["group"]["rows"] == [1, 2, 4, 5]
    assert rec["group"]["parts"] == 6 and rec["bottom_m"] == 49.8
    assert rec["lines"][0] == ("Group of 4 objects, 6 parts: fence.obj, roof.obj, "
                               "walls.obj, …")
    assert OS.object_seat(TILE, "ZZZZ", 1, 45.1, -122.9)["group"] == rec["group"]
    assert OS.object_seat(TILE, "ZZZZ", 5, 45.1012, -122.9)["group"] == rec["group"]
    ring = rec["group"]["ring"]
    assert max(p[0] for p in ring) >= 45.1012, "the outline takes in the kept row"
    assert OS.object_seat(TILE, "ZZZZ", 0, 45.1, -122.9)["seat"] == "kept"


def test_a_height_change_moves_every_row_of_the_group_by_one_offset(plan):
    r = OSE.object_seat_set(TILE, "ZZZZ", 2, "objects/roof.obj", 45.1, -122.9, bottom_m=51.8)
    assert (r["offset_m"], r["previous_offset_m"], r["rows"]) == (2.0, None, [1, 2, 4, 5])
    seats = US.read(OSE._patch_dir(TILE), "ZZZZ")
    assert sorted(seats) == [1, 2, 4, 5]
    assert {s.offset_m for s in seats.values()} == {2.0}
    assert {s.zero_m for s in seats.values()} == {None}
    assert (seats[5].model, seats[5].lat) == ("objects/wing.obj", 45.1012)
    rec = OS.object_seat(TILE, "ZZZZ", 4, 45.1, -122.9)
    assert rec["user_offset_m"] == 2.0 and rec["bottom_m"] == 51.8
    # the kept row is a handle on the same group: moving it moves them all
    r2 = OSE.object_seat_set(TILE, "ZZZZ", 5, "objects/wing.obj", 45.1012, -122.9,
                             bottom_m=52.8)
    assert r2["rows"] == [1, 2, 4, 5] and r2["offset_m"] == 3.0
    assert {s.offset_m for s in US.read(OSE._patch_dir(TILE), "ZZZZ").values()} == {3.0}
    assert "rebuild the tile" in rec["why"]
    # the Undo sends the previous offset back (none): the whole group clears
    r = OSE.object_seat_set(TILE, "ZZZZ", 2, "objects/roof.obj", 45.1, -122.9,
                            offset_m=r["previous_offset_m"])
    assert r["offset_m"] is None and US.read(OSE._patch_dir(TILE), "ZZZZ") == {}


def test_the_write_lifts_every_body_of_a_group_row(plan):
    rows = [NS(def_path=p, lat=45.1, lon=-122.9, heading_deg=0.0)
            for p in ("objects/a.obj", "objects/walls.obj", "objects/roof.obj",
                      "objects/far.obj", "objects/fence.obj", "objects/wing.obj")]
    pp = P.PlacementPlan(
        icao="ZZZZ", pack_name="p", pack_root="/p", dsf_path="/p/x.dsf",
        dsf_backup_path="/p/x.dsf.anchor_bak", provenance=P.Provenance("", "", ""),
        splits=tuple(P.Split.from_dict(s) for s in PLAN["splits"]),
        kept=tuple(P.Kept.from_dict(k) for k in PLAN["kept"]))
    assert [k.to_dict() for k in pp.kept] == PLAN["kept"], "the plan round-trips"
    seats = {i: US.UserSeat(i, rows[i].def_path, 45.1, -122.9, None, 2.0)
             for i in (1, 2, 4, 5)}
    out, seated, refused = US.apply(pp, seats, rows)
    assert seated == (1, 2, 4, 5) and refused == ()
    # the kept row moves WHOLE by the group's offset, on its DSF row
    assert [k.index for k in out.kept] == [0]
    assert [(m.index, m.elevation, m.why) for m in out.msl_seats] == [(5, 51.8, US.WHY)]
    lifted = {(s.placement.index, b.body_id): b.msl_z for s in out.splits for b in s.bodies}
    assert lifted == {(1, "b0"): 102.0, (1, "b1"): 52.0, (2, "b0"): 102.5,
                      (3, "b0"): None, (4, "b0"): 62.0, (4, "b1"): 52.0}
    assert len(out.splits) == 4, "a group row stays cut into its parts"


def test_a_seat_file_round_trips_offsets_and_refuses_neither():
    s = US.UserSeat(2, "m", 1.0, 2.0, None, 1.5)
    assert US.UserSeat.from_dict(s.to_dict()) == s
    with pytest.raises(ValueError):
        US.UserSeat.from_dict({"index": 1, "lat": 0, "lon": 0})
