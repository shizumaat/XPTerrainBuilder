"""RULINGS 2026-11-14a (2) (#1884): a LINE object (fence, wall, barrier —
``Part.line``) forms no body with what it touches and never joins two
objects into one group.  LOWS: the perimeter fence touching Terminal_42 and
Terminal_35 glued a 1.1 km group into one height."""
from __future__ import annotations

import types

from auto_patch_v2.airport.open_frame_seat import (frame_root_boxes,
                                                   merge_frame_roots,
                                                   unchained_links)


def _sq(x0, y0, s=10.0):
    d = 1e-5                                        # ~1.1 m per unit in lat
    return ((y0 * d, x0 * d), (y0 * d, (x0 + s) * d), ((y0 + s) * d, (x0 + s) * d),
            ((y0 + s) * d, x0 * d))


def _part(pid, x0, s=10.0, line=False):
    r = _sq(x0, 0.0, s)
    box = (min(q[0] for q in r), min(q[1] for q in r), max(q[0] for q in r),
           max(q[1] for q in r))
    return types.SimpleNamespace(pid=pid, rings=(r,), box=box, line=line)


def _frame(bridge_is_line):
    # two buildings 13 m apart, a thin piece 0.5 m off each, spanning the gap
    return types.SimpleNamespace(id="f", anchor=(0.0, 0.0), members=[types.SimpleNamespace(
        parts=[_part(1, 0.0), _part(2, 10.5, 12.0, line=bridge_is_line), _part(3, 23.0)])])


def test_an_unchained_deck_still_joins_two_buildings():
    """22o stands for a thin deck (not a line): the two units move as one."""
    pw = {1: ("fu:1:1", 0.0), 3: ("fu:1:3", 0.0)}
    assert len(unchained_links(_frame(False), pw)) == 1


def test_an_unchained_fence_joins_nothing():
    pw = {1: ("fu:1:1", 0.0), 3: ("fu:1:3", 0.0)}
    assert unchained_links(_frame(True), pw) == {}


def test_a_fence_unit_never_merges_two_frame_roots():
    """A fence seated as its own unit: its boxes are not a frame root's, so
    ``merge_frame_roots`` (the lifted-frame touch merge) cannot chain
    through it either."""
    u = _frame(True)
    pw = {1: ("fu:1:1", 0.0), 2: ("fu:1:2", 0.0), 3: ("fu:1:3", 0.0)}
    boxes = frame_root_boxes(u, pw)
    assert set(boxes) == {"fu:1:1", "fu:1:3"}
    got = merge_frame_roots(boxes)
    assert got["fu:1:1"] != got["fu:1:3"]
    assert unchained_links(u, pw) == {}
