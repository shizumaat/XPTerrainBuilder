"""Flat-pad spec §2 as ruled 2026-09-30r (issue #111, Q-111b option (1)):
the terminal OBJECT is cut into flat blocks at its narrowest necks.  Twins
for the band, the neck cut, the jetway-bay floor, the per-block terrace
declaration (the strip the mint leaves between two blocks' floors), the
more-than-``frontage_blocks_max`` STOP, the block ref grammar and the
object-stage cut (``airport/pad_block_seat``)."""
from __future__ import annotations

import types

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box

from auto_patch_v2.model.planar import block_of, block_ref, unit_ref_of
from auto_patch_v2.planar.pad_blocks import (arc_distance, band, bisect_blocks,
                                             hold_mask, reach)

A = 0.015            # the apron hard cap
MARGIN = 0.3
BAY = 40.0


def _frontage(P: Polygon, z_of, step: float = 2.0):
    """Every ring sample of ``P`` as a contact with ground ``z_of(x, y)``
    and its ring position."""
    ring = P.exterior
    n = int(ring.length // step)
    C = np.asarray([ring.interpolate(i * ring.length / n).coords[0] for i in range(n)])
    S = np.arange(n) * ring.length / n
    z = np.asarray([z_of(x, y) for x, y in C])
    return C, S, z, float(ring.length)


def _dumbbell() -> Polygon:
    """Two 200 x 100 m halls joined by a 20 m wide, 60 m long neck."""
    return (box(0, 0, 200, 100).union(box(260, 0, 460, 100))
            .union(box(200, 40, 260, 60)))


def test_reach_is_never_negative_and_band_is_closed_along_the_ring():
    C = np.array([[0.0, 0.0], [10.0, 0.0]])
    Q = np.array([[0.0, 5.0]])
    r = reach(C, Q, np.array([-MARGIN]), A)
    assert r.min() >= 0.0                      # a*5 - 0.3 < 0 -> clamped
    z = np.array([10.0, 20.0])
    S = np.array([0.0, 10.0])
    L, U = band(z, np.array([1.0, 1.0]), S, 1000.0, A)
    # each contact is bounded by the other within a * 10 m along the ring
    assert L[0] >= 19.0 - A * 10.0 - 1e-9 and U[1] <= 11.0 + A * 10.0 + 1e-9
    assert arc_distance(np.array([1.0]), np.array([99.0]), 100.0)[0, 0] == 2.0


def test_the_cut_is_at_the_neck():
    P = _dumbbell()
    C, S, z, per = _frontage(P, lambda x, y: 100.0 + (3.0 if x > 230.0 else 0.0))
    r = np.full(len(C), 0.5)
    L, U = band(z, r, S, per, A)
    pieces, cuts, necks, ok = bisect_blocks(
        P, C, L, U, z, margin=MARGIN, bay_m=BAY, max_blocks=5,
        neck=lambda s: s.length, seeds=400, dirs=8)
    assert ok and len(pieces) == 2 and len(cuts) == 1
    # the chord crosses the 20 m neck, not a 100 m hall
    assert cuts[0].length <= 20.0 + 1e-6
    assert 200.0 - 1e-6 <= cuts[0].centroid.x <= 260.0 + 1e-6


def test_one_level_is_one_block():
    P = _dumbbell()
    C, S, z, per = _frontage(P, lambda x, y: 100.0)
    L, U = band(z, np.full(len(C), 0.5), S, per, A)
    pieces, cuts, _n, ok = bisect_blocks(P, C, L, U, z, margin=MARGIN, bay_m=BAY,
                                         max_blocks=5, neck=lambda s: s.length,
                                         seeds=200, dirs=6)
    assert ok and len(pieces) == 1 and not cuts


def test_no_block_smaller_than_a_jetway_bay():
    # a 30 m stub at another level: splitting it off would leave a block
    # under a bay, so the unit cannot split there
    P = box(0, 0, 300, 100).union(box(300, 40, 330, 60))
    C, S, z, per = _frontage(P, lambda x, y: 100.0 + (3.0 if x > 300.0 else 0.0))
    L, U = band(z, np.full(len(C), 0.2), S, per, A)
    pieces, _c, _n, ok = bisect_blocks(P, C, L, U, z, margin=MARGIN, bay_m=BAY,
                                       max_blocks=5, neck=lambda s: s.length,
                                       seeds=300, dirs=8)
    assert all(g.area >= BAY * BAY for g in pieces)
    assert all(g.exterior.length >= BAY for g in pieces)


def test_more_than_the_cap_is_a_stop():
    # a 1,200 m bar rising 12 m with no reach: it needs more blocks than 3
    P = box(0, 0, 1200, 30).segmentize(20.0)   # a real ring has vertices to cut at
    C, S, z, per = _frontage(P, lambda x, y: 100.0 + 0.01 * x)
    L, U = band(z, np.zeros(len(C)), S, per, A)
    pieces, cuts, _n, ok = bisect_blocks(P, C, L, U, z, margin=MARGIN, bay_m=BAY,
                                         max_blocks=3, neck=lambda s: s.length,
                                         seeds=300, dirs=4)
    assert not ok and len(pieces) == 3 and len(cuts) == 2


def test_ramp_contacts_between_two_blocks():
    # two blocks 3 m apart: contacts within |dD| / (2a) = 100 m of the
    # other block's frontage are the ramp, never held
    S = np.arange(0.0, 400.0, 2.0)
    own = (S >= 200.0).astype(int)
    D = np.array([100.0, 103.0])
    L = np.full(len(S), -np.inf)
    U = np.full(len(S), np.inf)
    held, ramp = hold_mask(D, own, S, 10_000.0, L, U, A)
    # block 0's last contact is at 198 m, block 1's first at 200 m
    gap = (S > 100.0) & (S < 298.0)
    assert not held[gap].any() and held[~gap].all()
    assert (ramp == gap).all()


def test_block_ref_grammar():
    assert block_ref("building4", 2) == "building4/b2"
    assert block_of("building4/b2#collar") == ("building4", 2)
    assert block_of("building4") is None and block_of("a/bx") is None
    assert unit_ref_of("building4/b0#collar") == "building4"
    assert unit_ref_of("building4#collar") == "building4"


def _pad(ref, x0, x1, z):
    ring = ((0.0, x0), (0.0, x1), (1.0, x1), (1.0, x0))
    return types.SimpleNamespace(ref=ref, ring=ring, z=(z,) * 4)


def _part(pid, lat, lon, y=0.0):
    return types.SimpleNamespace(pid=pid, lat=lat, lon=lon, feet=((lat, lon, y),),
                                 box=(lat, lon, lat, lon), line=False)


def test_object_stage_cuts_the_contact_graph_at_the_block_boundary():
    import dataclasses

    from auto_patch_v2.airport import pad_block_seat as pbs

    @dataclasses.dataclass(frozen=True)
    class _Plan:
        units: tuple
        contacts: tuple
        abutments: tuple = ()

    parts = (_part(0, 0.5, 0.1), _part(1, 0.5, 0.4), _part(2, 0.5, 0.6), _part(3, 0.5, 0.9))
    member = types.SimpleNamespace(parts=parts, resource="t.obj")
    plan = _Plan(units=(types.SimpleNamespace(members=(member,)),),
                 contacts=((0, 1), (1, 2), (2, 3)))
    pads = [_pad("t/b0", 0.0, 0.5, 10.0), _pad("t/b1", 0.5, 1.0, 12.0),
            _pad("other", 5.0, 6.0, 0.0)]
    cut, abu, counts = pbs.sever(plan, pads, ((1, 2),))
    assert cut.contacts == ((0, 1), (2, 3)) and abu == ()
    assert counts["block_contacts_cut"] == 1


def test_each_block_is_its_own_platform_with_a_declared_terrace_between():
    """§2 (5): the mint gives every block its own platform + collar refs
    and leaves a STRIP of collar between two blocks' floors wide enough for
    the 1:3 bank of the predicted step — never one platform vertex at two
    floors — and registers each block as HELD."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.platform import HELD, PLATFORMS
    from auto_patch_v2.planar.pad_blocks import Block, BlockPlan
    from auto_patch_v2.planar.platform import _mint_blocks

    law = Law.for_airport("HECA")
    bank = float(law.tables.emit.design.bank_slope)
    P = _dumbbell()
    chord = LineString([(230.0, 40.0), (230.0, 60.0)])
    left = Polygon([(0, 0), (200, 0), (200, 40), (230, 40), (230, 60), (200, 60),
                    (200, 100), (0, 100)])
    right = P.difference(left)
    plan = BlockPlan("t", "split", 0, 0,
                     [Block(0, 10, 100.0, polygon=left), Block(1, 10, 103.0, polygon=right)],
                     cuts=[chord], steps=[(0, 1, -3.0)])
    import dataclasses
    reg = dataclasses.make_dataclass("R", ["ref", "polygon"])("t", P)
    PLATFORMS.clear()
    HELD.clear()
    inner = P.buffer(-5.0, join_style=2)
    got = _mint_blocks(reg, P, [inner], plan, law, 0.0, 10.0, 5.0, 100, None)
    assert got is not None
    plats, cols = got
    assert {r.ref for r in plats} == {"t/b0", "t/b1"}
    assert {r.ref for r in cols} == {"t/b0#collar", "t/b1#collar"}
    assert set(HELD) == {"t/b0", "t/b1"} and HELD["t/b1"]["unit"] == "t"
    a = [r.polygon for r in plats if r.ref == "t/b0"]
    b = [r.polygon for r in plats if r.ref == "t/b1"]
    gap = min(p.distance(q) for p in a for q in b)
    assert gap >= 3.0 / bank - 1e-6            # the whole 1:3 bank fits
    PLATFORMS.clear()
    HELD.clear()


def test_no_cut_through_more_than_a_bay_of_building():
    """RULINGS 2026-09-30u (i): the neck is chosen narrowest-first, and a
    chord crossing more than a jetway bay of footed parts is no neck — a
    100 m-wide hall rising 3 m stays ONE block (its miss reported)."""
    P = box(0, 0, 400, 100).segmentize(20.0)
    C, S, z, per = _frontage(P, lambda x, y: 100.0 + (3.0 if x > 200.0 else 0.0))
    L, U = band(z, np.full(len(C), 0.2), S, per, A)
    pieces, cuts, _n, ok = bisect_blocks(P, C, L, U, z, margin=MARGIN, bay_m=BAY,
                                         max_blocks=5, neck=lambda s: s.length,
                                         seeds=300, dirs=8)
    assert not ok and len(pieces) == 1 and not cuts


def test_the_clearest_neck_wins_over_the_smaller_miss():
    """Two admissible cuts that both fix the miss: the one crossing no
    building (a 20 m courtyard gap in the neck measure) wins."""
    P = _dumbbell()
    C, S, z, per = _frontage(P, lambda x, y: 100.0 + (3.0 if x > 230.0 else 0.0))
    L, U = band(z, np.full(len(C), 0.5), S, per, A)
    hall = box(0, 0, 200, 100)          # footed parts: the left hall only
    pieces, cuts, necks, ok = bisect_blocks(
        P, C, L, U, z, margin=MARGIN, bay_m=BAY, max_blocks=5,
        neck=lambda s: s.intersection(hall).length, seeds=400, dirs=8)
    assert ok and len(cuts) == 1 and necks[0] == 0.0
