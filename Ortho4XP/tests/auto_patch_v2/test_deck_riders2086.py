"""#2086: a bridge authored as a deck file and the structure file riding it
seats as ONE free-standing bridge (``airport/deck_riders``).  Headless,
synthetic: no pack, no mesh, no network."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import bridge_family as BF
from auto_patch_v2.airport import deck_riders as DR
from auto_patch_v2.airport import placement_body as PB

LA, LO = 36.68, -4.47
_D = 1e-3          # ~111 m of latitude


def _print(unit: int, member: int) -> BF.DeckPrint:
    """A square deck footprint ~111 m x 90 m north-east of (LA, LO)."""
    a, b, c, d = (LA, LO), (LA + _D, LO), (LA + _D, LO + _D), (LA, LO + _D)
    p = BF.DeckPrint(key=f"d{unit}.{member}", unit=unit, member=member, under_y=0.0,
                     box=(LA, LO, LA + _D, LO + _D), tris=((a, b, c), (a, c, d)))
    p.index()
    return p


def _part(lat: float, lon: float):
    return types.SimpleNamespace(lat=lat, lon=lon)


def _m(kind: str, *parts):
    return types.SimpleNamespace(deck_kind=kind, parts=tuple(parts))


def _plan(*units):
    return types.SimpleNamespace(units=tuple(types.SimpleNamespace(members=ms) for ms in units))


IN = _part(LA + 0.5 * _D, LO + 0.5 * _D)
EDGE = _part(LA + 0.5 * _D, LO + _D + 2e-6)      # ~0.2 m off the print: within CONTACT_M
OUT = _part(LA + 0.5 * _D, LO + 2 * _D)          # ~90 m off


def test_a_structure_riding_its_deck_makes_the_frame_one_bridge():
    plan = _plan((_m("signature", IN), _m("family", IN, EDGE)))
    assert DR.riding_frames(plan, [_print(0, 0)]) == {(0, 0): 0, (0, 1): 0}


def test_one_family_part_off_every_deck_leaves_the_frame_as_it_was():
    plan = _plan((_m("signature", IN), _m("family", IN, OUT)))
    assert DR.riding_frames(plan, [_print(0, 0)]) == {}


def test_a_frame_with_a_building_member_is_not_a_bridge():
    plan = _plan((_m("signature", IN), _m("family", IN), _m("", IN)))
    assert DR.riding_frames(plan, [_print(0, 0)]) == {}


def test_frames_without_a_family_member_or_without_a_deck_are_not_listed():
    plan = _plan((_m("signature", IN), _m("flag", IN)), (_m("family", IN),))
    assert DR.riding_frames(plan, [_print(0, 0), _print(1, 0)]) == {}


def test_a_rider_is_read_against_its_own_frames_decks_only():
    # unit 1's deck print covers the rider, unit 0's frame has a deck with no print
    plan = _plan((_m("signature", OUT), _m("family", IN)), (_m("signature", IN),))
    assert DR.riding_frames(plan, [_print(1, 0)]) == {}


def test_a_partless_rider_does_not_ride():
    plan = _plan((_m("signature", IN), _m("family")))
    assert DR.riding_frames(plan, [_print(0, 0)]) == {}


def _obj(tmp_path, rows):
    p = tmp_path / "deck.obj"
    vt = "\n".join(f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in rows)
    p.write_text(f"I\n800\nOBJ\n\nPOINT_COUNTS {len(rows)} 0 0 3\n{vt}\nIDX10 0 1 2\nTRIS 0 3\n",
                 encoding="utf-8", newline="\n")
    return str(p)


def test_end_tops_read_the_deck_where_each_end_line_is(tmp_path):
    # a deck on a grade along north (OBJ z is south): y -0.25 at its south end,
    # +1.28 at the crown, -1.53 at its north end; heading 0
    path = _obj(tmp_path, [(0.0, -0.25, 50.0), (0.0, 1.28, 0.0), (0.0, -1.53, -50.0)])
    deck = types.SimpleNamespace(authored_path=path, heading_deg=0.0)
    mdeg = 1.0 / 111_000.0
    south = ((LA - 52 * mdeg, LO - 1e-4), (LA - 52 * mdeg, LO + 1e-4))
    north = ((LA + 52 * mdeg, LO - 1e-4), (LA + 52 * mdeg, LO + 1e-4))
    assert DR.end_tops(deck, (south, north), (LA, LO)) == pytest.approx((-0.25, -1.53))
    assert DR.end_tops(types.SimpleNamespace(authored_path=str(tmp_path / "x.obj")),
                       (south, north), (LA, LO)) is None


def test_a_rider_takes_its_bridges_datum_and_others_keep_their_own():
    datum = object()
    u = types.SimpleNamespace(members=())
    m = types.SimpleNamespace(deck_kind="family", plate_y=None, deck_top_y=None)
    assert PB._member_datum(m, u, datum, 2.0, 30.0, 0.3) is datum
    assert PB._member_datum(m, u, None, 2.0, 30.0, 0.3) is None
