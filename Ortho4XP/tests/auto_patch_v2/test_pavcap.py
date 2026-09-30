"""THE UNIVERSAL PAVEMENT CAP — the engine's hard row family
(``constraints/pavement_cap.py``; owner RULINGS 2026-09-29ac, issue #105).

The road cap (``[common] road_max_grade``) is the HARD fallback over every
pavement pair no row already caps at or under it: a pavement pair at 9 %
is refused, at 7 % passes; a runway pair keeps its own 1.5 %; the
platform collar (a 1:3 bank) and two pins mint nothing.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.constraints import pavement_cap
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.constraints import Diff, Pin, Source


@pytest.fixture(scope="module")
def law():
    return T.load_default()


@_dc.dataclass
class _V:
    xy: tuple


@_dc.dataclass
class _F:
    id: int
    role: str
    ref: str
    ring: tuple
    holes: tuple = ()


class _Planar:
    """The two things the family reads off a ``PlanarMap``: faces (ring
    as a cycle of vertex ids here) and vertex coordinates."""

    def __init__(self, verts, faces):
        self.vertices = {v: _V(xy) for v, xy in verts.items()}
        self.faces = {f.id: f for f in faces}

    @staticmethod
    def ring_vertices(cycle):
        return tuple(cycle)

    def roles_at(self, v):
        """RULINGS 2026-09-30aa: the pair law reads the vertex's roles."""
        return tuple(f.role for f in self.faces.values()
                     if v in (*f.ring, *(q for h in f.holes for q in h)))


def _rect(v0, x0, length=10.0, width=8.0):
    ids = (v0, v0 + 1, v0 + 2, v0 + 3)
    xy = {ids[0]: (x0, 0.0), ids[1]: (x0 + length, 0.0),
          ids[2]: (x0 + length, width), ids[3]: (x0, width)}
    return ids, xy


def _holds(row, z):
    return abs(z[row.a] - z[row.b]) <= row.cap * row.d + 1e-9


def test_the_fallback_is_the_road_cap(law):
    assert T.pavement_fallback_cap(law) == law.tables.common.road_max_grade
    assert pavement_cap.RULING.split(" (")[0] in {
        h.split(" (")[0] for h in law.tables.emit.design.hard_rulings}


def test_a_pavement_pair_at_9_percent_is_refused_at_7_passes(law):
    ids, xy = _rect(0, 0.0)
    pm = _Planar(xy, [_F(1, "groundside_pavement", "lot", ids)])
    rows = pavement_cap.pavement_road_cap([], pm, law)
    assert len(rows) == 4 and all(isinstance(r, Diff) for r in rows)
    assert all(r.cap == pytest.approx(0.08) for r in rows)
    edge = next(r for r in rows if {r.a, r.b} == {0, 1})
    assert edge.d == pytest.approx(10.0)
    assert not _holds(edge, {0: 0.0, 1: 0.9})       # 9 %: refused
    assert _holds(edge, {0: 0.0, 1: 0.7})           # 7 %: passes


def test_a_runway_pair_keeps_its_own_lower_cap(law):
    """A pair already capped at or under the fallback by a hard Diff (the
    runway's 1.5 %) mints no fallback row — its own cap is the law."""
    ids, xy = _rect(0, 0.0)
    pm = _Planar(xy, [_F(1, "runway", "09/27", ids)])
    src = Source("runway_profile", "rulesets.runway.longitudinal", ())
    own = [Diff(0, 1, 0.015, 10.0, src), Diff(2, 3, 0.015, 10.0, src)]
    rows = pavement_cap.pavement_road_cap(own, pm, law)
    got = {frozenset((r.a, r.b)) for r in rows}
    assert frozenset((0, 1)) not in got and frozenset((2, 3)) not in got
    assert frozenset((1, 2)) in got                  # the unpriced ring edge


def test_welded_neighbours_of_two_faces_are_one_capped_pair(law):
    a, xya = _rect(0, 0.0)
    b, xyb = _rect(10, 10.8)                         # 0.8 m gap
    pm = _Planar({**xya, **xyb}, [_F(1, "apron", "pav1", a),
                                  _F(2, "service_road", "r1", b)])
    rows = pavement_cap.pavement_road_cap([], pm, law)
    cross = [r for r in rows if (r.a < 10) != (r.b < 10)]
    assert {frozenset((r.a, r.b)) for r in cross} == {
        frozenset((1, 10)), frozenset((2, 13))}
    assert all(r.d == pytest.approx(0.8) for r in cross)


def test_collar_and_two_pins_mint_nothing(law):
    ids, xy = _rect(0, 0.0)
    pm = _Planar(xy, [_F(1, "building", "b1#collar", ids)])
    assert pavement_cap.pavement_road_cap([], pm, law) == []
    pm2 = _Planar(xy, [_F(1, "apron", "pav1", ids)])
    src = Source("seam_pins", "seam", ())
    pins = [Pin(0, 0.0, src), Pin(1, 5.0, src)]
    got = {frozenset((r.a, r.b))
           for r in pavement_cap.pavement_road_cap(pins, pm2, law)}
    assert frozenset((0, 1)) not in got and len(got) == 3


def test_structure_ramps_are_not_pavement(law):
    ids, xy = _rect(0, 0.0)
    for role in ("door_ramp", "wall_corridor_ramp", "garage_ramp"):
        pm = _Planar(xy, [_F(1, role, "r", ids)])
        assert pavement_cap.pavement_road_cap([], pm, law) == []


def test_pad_pad_weld_is_a_step_not_a_grade(law):
    """RULINGS 2026-09-30l (2), issue #123: two different BUILDING pads
    within the weld radius hold the ``building_to_building`` step
    exemption — no fallback row between them (the HECA cargo pads were
    dragged 6.4 m onto the lower pad across their declared terrace).  Each
    pad's own ring edges stay capped, and a pad|apron weld stays priced."""
    a, xya = _rect(0, 0.0)
    b, xyb = _rect(10, 10.8)                         # 0.8 m gap
    pm = _Planar({**xya, **xyb}, [_F(1, "building", "building51", a),
                                  _F(2, "building", "building129", b)])
    rows = pavement_cap.pavement_road_cap([], pm, law)
    assert not [r for r in rows if (r.a < 10) != (r.b < 10)]
    assert len(rows) == 8                            # both rings' edges
    pm2 = _Planar({**xya, **xyb}, [_F(1, "building", "building51", a),
                                   _F(2, "apron", "pav37", b)])
    rows2 = pavement_cap.pavement_road_cap([], pm2, law)
    assert {frozenset((r.a, r.b)) for r in rows2
            if (r.a < 10) != (r.b < 10)} == {
        frozenset((1, 10)), frozenset((2, 13))}


def test_a_groundside_pair_on_the_airside_mints_no_row_and_one_foot_follows(law):
    """RULINGS 2026-09-30aa rules 3-4 (#100): a road ring's pair with BOTH
    feet on the apron rim is the apron's, never the road's; a pair with
    ONE foot there is one-way, the road foot following — and every row
    names its minting face (rule 1's filter reads it)."""
    apron = (0, 1, 2, 3)
    road = (1, 4, 5, 2)                   # shares the apron edge 1-2
    xy = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (10.0, 8.0), 3: (0.0, 8.0),
          4: (30.0, 0.0), 5: (30.0, 8.0)}
    pm = _Planar(xy, [_F(1, "apron", "pav1", apron),
                      _F(2, "service_road", "small_roads:-3", road)])
    rows = pavement_cap.pavement_road_cap([], pm, law)
    by = {frozenset((r.a, r.b)): r for r in rows}
    # the shared edge 1-2 is minted ONCE, by the apron (no follower)
    assert by[frozenset((1, 2))].follows is None
    assert by[frozenset((1, 2))].source.inputs == ("face:1",)
    # the road's own contact edges follow the ROAD vertex
    assert by[frozenset((1, 4))].follows == (4,)
    assert by[frozenset((2, 5))].follows == (5,)
    assert by[frozenset((4, 5))].follows is None
    assert by[frozenset((4, 5))].source.inputs == ("face:2",)
