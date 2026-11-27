"""#2239: a shell under its own pack deck hangs its floor from that deck's
end lines (``constraints/edge_floor._own_deck_seat``; owner 2026-11-26: "the
ground under the bridge must meet the bottom of the bridge object")."""
from __future__ import annotations

import types

from auto_patch_v2.constraints.edge_floor import _own_deck_seat


def _line(deck, terms, depth):
    return types.SimpleNamespace(deck=deck, terms=terms, depth=depth)


def test_the_shell_floor_is_its_deck_seat_less_the_deck_depth():
    deck = types.SimpleNamespace(object_id="dsf:obj1", members=("dsf:obj1",))
    planar = types.SimpleNamespace(decks=(deck,))
    lines = {"dsf:obj1": [_line(deck, ((1, 0.5), (2, 0.5)), 7.55),
                          _line(deck, ((3, 1.0),), 7.47)]}
    tn = types.SimpleNamespace(source="object", objects=("dsf:obj1",))
    (terms, depth), = _own_deck_seat(planar, tn, lines)
    assert dict(terms) == {1: 0.25, 2: 0.25, 3: 0.5}
    assert abs(depth - 7.51) < 1e-9


def test_a_shell_under_no_deck_of_its_own_keeps_its_authored_floor():
    deck = types.SimpleNamespace(object_id="dsf:obj9", members=("dsf:obj9",))
    planar = types.SimpleNamespace(decks=(deck,))
    lines = {"dsf:obj9": [_line(deck, ((1, 1.0),), 7.0)]}
    assert _own_deck_seat(planar, types.SimpleNamespace(source="object", objects=("dsf:obj1",)),
                         lines) == ()
    assert _own_deck_seat(planar, types.SimpleNamespace(source="osm", objects=("dsf:obj9",)),
                         lines) == ()
