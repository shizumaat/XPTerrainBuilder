"""#2241: a slab falling along its end line is welded station by station --
the anchor's level at a station, the deck-end census's reading and the
end line's seat depths all take that station's own top."""
from __future__ import annotations

import sys
import types
from pathlib import Path

from auto_patch_v2.constraints.deck_anchor import _level_at as level_at
from auto_patch_v2.constraints.deck_anchor import _station_top as station_top
from auto_patch_v2.constraints.deck_lines import _vertex_depths
from auto_patch_v2.model.structures import DeckAnchor

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from check_grade_lib.families.deck_end_flush import check_deck_end_flush  # noqa: E402


def _anchor(**kw):
    base = dict(object_id="d", end="A", v=2, stations=(1, 2, 3), z_m=163.5, top_y=7.5,
                rise_m=0.0, family="taxi", ref="", profile_z_m=163.5)
    base.update(kw)
    return DeckAnchor(**base)


def test_the_anchor_reads_each_station_at_its_own_top():
    a = _anchor(station_tops=(7.0, 7.5, 8.0))
    assert station_top(a, 1) == 7.0 and station_top(a, 3) == 8.0
    assert level_at(a, 3) == 164.0 and level_at(a, 1) == 163.0
    flat = _anchor()
    assert station_top(flat, 3) == 7.5 and level_at(flat, 3) == 163.5


def test_seat_depths_are_the_mean_of_each_vertex_stations():
    db = types.SimpleNamespace(station_tops=((7.0, 7.5, 8.0), (7.0, 7.0, 7.0)),
                               seats_a=((0, 0), (5, 0), (10, 0)),
                               seats_b=((0, 9), (5, 9), (10, 9)), bottom_y=0.0)
    got = dict(_vertex_depths(db, 0, [(0, 11), (1, 11), (2, 12)]))
    assert got == {11: 7.25, 12: 8.0}
    # one level along the line: no per-vertex reading
    assert _vertex_depths(db, 1, [(0, 21), (1, 22), (2, 23)]) == ()


def test_the_census_reads_a_falling_line_off_its_station_tops():
    nodes = {1: (43.0, -79.0), 2: (43.0, -79.0001), 3: (43.0, -79.0002)}
    way = types.SimpleNamespace(nids=[1, 2, 3], elevs=[163.0, 163.5, 164.0])
    rec = {"object": "d", "plate": 0, "top_y": 7.5,
           "stations": [[43.0, -79.0], [43.0, -79.0001], [43.0, -79.0002]]}
    # read at one top the falling surface is 0.5 m off at both ends ...
    assert len(check_deck_end_flush([rec], nodes, [way])) == 2
    # ... and flush read station by station
    rec["station_tops"] = [7.0, 7.5, 8.0]
    assert check_deck_end_flush([rec], nodes, [way]) == []
