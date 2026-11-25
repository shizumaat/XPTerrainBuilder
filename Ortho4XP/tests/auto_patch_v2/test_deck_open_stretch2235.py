"""#2235 (KMCO 28.422975,-81.306380, owner 1.0.572: "spiky bumps in the
ground between the bridges"): a banked deck's own ground PAST the bank's
run-on -- the open stretch between two decks over the same roads -- stands
under the bank's blend as a one-sided CEILING (``constraints/edge_deck.
_span_rows``), never filled toward the deck, and so takes the ground's datum
(``solve/design_ground._deck_ground_vertices``).  Held two-sided, the blend
daylit (drop 0) and the rows tied the stretch flush with the deck 6 m over
the at-grade roads: the rows the roads could not bear were relaxed and the
rest stood lone vertices 4-6 m over the ground.  Synthetic, no capture."""
from __future__ import annotations

import types

from auto_patch_v2.constraints import edge_deck as ED
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.deck_bank import bank_past_m, banked, deck_bank_slope
from auto_patch_v2.model.structures import DECK_GROUND_REF
from auto_patch_v2.solve import design_ground as DG

LAW = load_default()
# a deck 40 m along x over a road along y, end lines (seats) at x = 0 and x = 40
RING = ((0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0))
#: a frame's walls on both sides of the road (``test_cut_goes_under``)
BOTH_WALLS = ((0.0, 1.0), (1.0, 0.0), ((5.0, 0.0, 20.0), (35.0, 0.0, 20.0)))
OWN = f"{DECK_GROUND_REF}:o4gen_d"
SEAT_Z, GROUND_Z = 31.5, 25.5


def _pm(xy_of, faces, walls=()):
    vx = {v: types.SimpleNamespace(xy=xy, dem_z=GROUND_Z, incident_faces=tuple(
        fid for fid, (_r, _ref, ring) in faces.items() if v in ring))
        for v, xy in xy_of.items()}
    fs = {fid: types.SimpleNamespace(id=fid, role=role, ref=ref, ring=tuple(ring), holes=())
          for fid, (role, ref, ring) in faces.items()}
    deck = types.SimpleNamespace(object_id="o4gen_d", ring=RING, walls=walls)
    return types.SimpleNamespace(
        decks=(deck,), vertices=vx, faces=fs, edges={},
        ring_vertices=lambda ring: tuple(ring), roles_at=lambda v: ("graded_strip",))


# seats 1, 2 on the end lines; 7 on the bank's run-on beside the ring; 8, 9
# the open stretch 6 m / 14 m past it -- every face the deck's own ground
XY = {1: (0.0, 10.0), 2: (40.0, 10.0), 7: (20.0, 20.5), 8: (20.0, 27.0), 9: (12.0, 35.0)}
FACES = {20: ("graded_strip", OWN, (7, 8, 9)), 21: ("graded_strip", OWN + "#1", (7, 9, 1)),
         22: ("graded_strip", OWN + "#2", (7, 8, 2))}


def _rows(walls=()):
    pm = _pm(XY, FACES, walls)
    deck = pm.decks[0]
    es = [types.SimpleNamespace(terms=((1, 1.0),), deck=deck, depth=6.0,
                                line=[(0.0, 0.0), (0.0, 20.0)]),
          types.SimpleNamespace(terms=((2, 1.0),), deck=deck, depth=6.0,
                                line=[(40.0, 0.0), (40.0, 20.0)])]
    ends = [(e.terms, 0.0) for e in es]
    bank = ED._bank_slope(LAW, es)
    rows = ED._span_rows(pm, "o4gen_d", es, (), set(), ends, 0.04, bank=bank,
                         past=bank_past_m(LAW))
    by: dict[int, list] = {}
    for r in rows:
        by.setdefault(r.terms[0][0], []).append(r)
    return bank, by


def _holds(row, z):
    s = sum(c * z[v] for v, c in row.terms)
    return (row.lo is None or s >= row.lo - 1e-9) and (row.hi is None or s <= row.hi + 1e-9)


def test_the_open_stretch_past_the_run_on_takes_a_ceiling_only():
    bank, by = _rows()
    assert bank == deck_bank_slope(LAW)
    # on the run-on the bank is the deck's ground: held both ways
    assert len(by[7]) == 2
    # past it the blend is a ceiling (z[v] - z[seat] <= -drop), never a floor
    for v in (8, 9):
        assert len(by[v]) == 1 and by[v][0].lo is None and by[v][0].terms[0][1] > 0.0
    # the at-grade ground 6 m under the deck violates nothing there
    z = {1: SEAT_Z, 2: SEAT_Z, 8: GROUND_Z, 9: GROUND_Z}
    assert all(_holds(r, z) for v in (8, 9) for r in by[v])


def test_a_walled_decks_open_stretch_stays_flush():
    """30f (3): the fill behind a walled deck's walls is flush with it."""
    bank, by = _rows(BOTH_WALLS)
    assert bank is None
    assert all(len(by[v]) == 2 for v in (7, 8, 9))


def test_the_open_stretch_past_the_run_on_takes_the_grounds_datum():
    ground = {20, 21, 22}
    pm = _pm(XY, FACES)
    assert banked(pm.decks[0])
    decked = DG._deck_ground_vertices(pm, ground, LAW)
    # under the ring and on its run-on the ground follows the deck; past it
    # (8, 9) the ceiling alone holds it, so the datum levels it
    assert 7 in decked and 1 in decked and not {8, 9} & decked
    walled = _pm(XY, FACES, BOTH_WALLS)
    assert not banked(walled.decks[0])
    assert {7, 8, 9} <= DG._deck_ground_vertices(walled, ground, LAW)
