"""#2266 (part 2): A BUILDING IS NEVER A CHANNEL'S FLOOR.

The structure knife never cuts a building, so a channel corridor drawn
over one left the building's cell inside the floor: the two shared
vertices and the floor's pin (``channel.floor``) seated the building pad,
and through its frontage the apron around it, at the cut depth.  The
corridor now stands out of a building exactly as it stands out of a deck
(§45 (17)): the floor the wall band back from it, the bank stopping at its
outline.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.planar.channel import identify_channels
from auto_patch_v2.planar.channel_claims import channel_cells
from auto_patch_v2.planar.structures import build_structures
from shapely.geometry import Polygon
from test_v2channel import _airport, _cells, _pavement_with_corridor, _rect, _road


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


#: a building standing on the corridor floor between the two necks
_BUILDING = _rect(-4.0, 40.0, 60.0, 90.0)


def _channel(law):
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    cl = Classification(tuple(_cells()), (), {}, ())
    chans, st = identify_channels(ap, cl, law)
    assert len(chans) == 1, (st.refused, st.notes)
    return ap, cl, chans


def test_the_floor_stands_the_wall_band_back_from_a_building(law):
    _ap, _cl, chans = _channel(law)
    b = Polygon(_BUILDING)
    cells, _knives = channel_cells(chans, law, [b])
    floor = [p for r, _ref, p, _c in cells if r == "tunnel_trench"]
    bank = [p for r, _ref, p, _c in cells if r == "retaining_wall"]
    band = chans[0].wall_band_m
    assert floor and bank
    for f in floor:
        assert f.distance(b) >= band - 1e-6
    for q in floor + bank:
        assert q.intersection(b).area < 1e-6
    # without the building the corridor ran under it
    bare, _k = channel_cells(chans, law)
    assert any(p.intersection(b).area > 1.0 for _r, _ref, p, _c in bare)


def test_a_building_far_from_the_corridor_changes_nothing(law):
    _ap, _cl, chans = _channel(law)
    far = Polygon(_rect(300.0, 300.0, 340.0, 340.0))
    a, ka = channel_cells(chans, law)
    b, kb = channel_cells(chans, law, [far])
    assert [(r, ref, p.wkb) for r, ref, p, _c in a] == [(r, ref, p.wkb) for r, ref, p, _c in b]
    assert [k.wkb for k in ka] == [k.wkb for k in kb]


def test_build_structures_keeps_the_floor_off_a_building_cell(law):
    ap, _cl, chans = _channel(law)
    cells = [*_cells(), Cell(9, "building", "building0", _BUILDING, (), None, None,
                             "airside", "building", {})]
    cl = Classification(tuple(cells), (), {}, ())
    out, _tunnels, _st = build_structures(ap, cl, law, channels=chans)
    b = Polygon(_BUILDING)
    floors = [Polygon(c.ring, c.holes) for c in out.cells if c.role == "tunnel_trench"]
    assert floors
    assert all(f.intersection(b).area < 1e-6 and f.distance(b) > 0.0 for f in floors)
    assert any(c.role == "building" for c in out.cells)


# ── §45 (23) PROPOSED: a neck never infers a cut under a building ────────

def _with_building(ring):
    return [*_cells(), Cell(9, "building", "building0", ring, (), None, None,
                            "airside", "building", {})]


def test_23_a_building_on_a_neck_only_floor_refuses_the_channel(law):
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, st = identify_channels(ap, Classification(tuple(_with_building(_BUILDING)), (), {},
                                                     ()), law)
    assert chans == []
    assert any("§45 (23)" in r and "building0" in r for r in st.refused), st.refused
    assert st.datum_clearance == 0


def test_23_a_building_beside_the_floor_keeps_the_channel(law):
    _ap, _cl, base = _channel(law)
    half = max(h for _s, h in base[0].widths)
    beside = _rect(half, 40.0, half + 40.0, 90.0)     # touches the floor's edge only
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, st = identify_channels(ap, Classification(tuple(_with_building(beside)), (), {},
                                                     ()), law)
    assert [c.id for c in chans] == [c.id for c in base], st.refused
    assert not any("§45 (23)" in r for r in st.refused)
