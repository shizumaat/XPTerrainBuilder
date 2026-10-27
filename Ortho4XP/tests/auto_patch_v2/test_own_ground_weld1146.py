"""#1146 (owner RULINGS 2026-10-22o on the pieces of ONE placement; lane
lseat, ``docs/findings/seating-lseat.md`` §2): an OWN-GROUND piece moves
with the pieces its authored geometry touches within a metre.

KLAX's elevated rail: rails lying ON a beam's top face share no vertex with
it (§16c (6) binds by vertex), hold no part, and each fell to its own
ground — the rail stood in pieces up to 2.5 m apart.
"""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import placement_targets as PT
from auto_patch_v2.airport.placement_file import OWN_GROUND
from auto_patch_v2.airport.placement_record import Body, Split

_M = types.SimpleNamespace(resource="objects/rail.obj", zero_y=0.0)


class _Cutter:
    """The member's authored geometry: one quad per component."""

    def __init__(self, quads):
        v, comps = [], []
        for q in quads:
            k = len(v)
            v.extend(q)
            comps.append(types.SimpleNamespace(
                tris=np.array([[k, k + 1, k + 2], [k, k + 2, k + 3]])))
        self._geom = types.SimpleNamespace(vertices=np.asarray(v, dtype=float))
        self._comps = comps

    def _read(self):
        return True


def _quad(x0, x1, z0, z1, y):
    return [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]


def _body(i, ground, reason=OWN_GROUND + ": no carrier the law accepts"):
    a = AR.Anchor(AR.DECK, 40.0, -3.0, 0.0, reason, ground, offset=(0.0, 0.0, 0.0))
    return Body(i, AR.DECK, (i,), a, f"objects/rail__b{i}.obj")


def _split(*bodies):
    return Split(0, "dsf:obj0", "objects/rail.obj", "/x/objects/rail.obj",
                 40.0, -3.0, 0.0, tuple(bodies))


def _zeros(rec):
    return [round(float(b.anchor.surface_z) - float(b.anchor.y_zero), 2)
            for b in rec.bodies]


#: a 300 m beam whose top face is y = 19.1, with no vertex mid-span
BEAM = _quad(0.0, 300.0, -2.0, 2.0, 19.1)


def test_rails_on_a_beam_face_take_the_beam_zero():
    """Two rails lying on the beam's top face (vertex-to-face 0 m, nearest
    beam VERTEX 100 m away) are one group with it: the largest piece's
    zero, the pieces' own grounds ignored."""
    cut = _Cutter([BEAM, _quad(100.0, 110.0, -1.0, -0.5, 19.1),
                   _quad(150.0, 160.0, 0.5, 1.0, 19.1)])
    rec = _split(_body(0, 32.0), _body(1, 30.5), _body(2, 31.2))
    counts: dict = {}
    out = PT.weld_own_ground(rec, _M, cut, counts)
    assert _zeros(out) == [32.0, 32.0, 32.0]
    assert counts["own_ground_welded_bodies"] == 2


def test_a_piece_the_law_seated_wins_over_the_own_ground_pieces():
    """The beam is carried (a unit's datum): the rail touching it takes ITS
    zero, and the carried beam never moves."""
    cut = _Cutter([BEAM, _quad(100.0, 110.0, -1.0, -0.5, 19.1)])
    rec = _split(_body(0, 33.0, reason="footless_carried_by_unit: fu:1"),
                 _body(1, 30.5))
    out = PT.weld_own_ground(rec, _M, cut, {})
    assert _zeros(out) == [33.0, 33.0]
    assert out.bodies[0] is rec.bodies[0]


def test_pieces_two_metres_apart_keep_their_own_ground():
    """22o splits what is clearly a couple of metres apart: a rail 2 m
    above the beam's face is not welded."""
    cut = _Cutter([BEAM, _quad(100.0, 110.0, -1.0, -0.5, 21.1)])
    rec = _split(_body(0, 32.0), _body(1, 30.5))
    out = PT.weld_own_ground(rec, _M, cut, {})
    assert _zeros(out) == [32.0, 30.5]


def test_a_carried_piece_is_never_moved():
    """Two carried pieces (a material file's trim on two buildings) touch:
    neither is own ground, so nothing moves."""
    cut = _Cutter([BEAM, _quad(100.0, 110.0, -1.0, -0.5, 19.1)])
    rec = _split(_body(0, 33.0, reason="carried by a"),
                 _body(1, 30.5, reason="carried by b"))
    assert PT.weld_own_ground(rec, _M, cut, {}) is rec


def test_pieces_touch_reads_the_face_not_the_vertex():
    ix = [[0, 1, 2], [0, 2, 3]]
    t_beam = np.asarray(BEAM, dtype=float)[ix]
    t_rail = np.asarray(_quad(100.0, 110.0, -1.0, -0.5, 19.6), dtype=float)[ix]
    assert PT.pieces_touch(t_beam, t_rail, 1.0)
    assert not PT.pieces_touch(t_beam, t_rail, 0.4)
