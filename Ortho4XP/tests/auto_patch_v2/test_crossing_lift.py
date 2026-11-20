"""RULINGS 2026-11-20g (2) / 20k: a touching group holding a component the
patch read as an elevated crossing seats at the published crossing seat,
never above its own HIGHEST vote; a group with no crossing keeps 16v's
lower seat.  Synthetic frames of ``test_touch_seat2110``."""
from __future__ import annotations

import dataclasses as dc

from test_touch_seat2110 import LAW, _World, _zero


def _law(*crossings):
    return dc.replace(LAW, crossings=tuple(crossings))


def _pair():
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("b", (20.05, 0, 40, 20), 431.6)
    return w, a, b


def test_a_crossing_group_rises_to_its_published_seat():
    w, a, b = _pair()
    out, table, counts = w.run(_law({"member": "dsf:a", "comp": 0, "zero": 431.4}))
    assert _zero(out[a]) == _zero(out[b]) == 431.4
    row = next(r for r in table["groups"] if r["class"] == "crossing")
    assert row["lift"] == 0.4 and row["crossing_zero"] == 431.4
    assert counts["touch_groups_crossing"] == 1
    assert "crossing seat" in out[a].bodies[0].anchor.reason


def test_the_lift_stops_at_the_highest_vote():
    w, a, b = _pair()
    out, _t, _c = w.run(_law({"member": "dsf:b", "comp": 0, "zero": 433.0}))
    assert _zero(out[a]) == _zero(out[b]) == 431.6


def test_no_crossing_keeps_the_lower_seat():
    w, a, b = _pair()
    out, _t, counts = w.run(_law({"member": "dsf:other", "comp": 0, "zero": 433.0}))
    assert _zero(out[a]) == _zero(out[b]) == 431.0
    assert "touch_groups_crossing" not in counts


def test_a_seat_under_the_lower_vote_lifts_nothing():
    w, a, b = _pair()
    out, _t, _c = w.run(_law({"member": "dsf:a", "comp": 0, "zero": 430.5}))
    assert _zero(out[a]) == _zero(out[b]) == 431.0
