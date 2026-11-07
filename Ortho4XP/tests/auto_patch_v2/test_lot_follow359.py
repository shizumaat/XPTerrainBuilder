"""Issue #359 (HECA lot ``dsf:objpav394`` around ``building8``): THE LOT
OVER A DECLARED WALL GRADES FLAT OUT FROM ITS PAD — in a follower pass
after stage 2 (``solve/follow_stage``, ``pipeline/lot_follow``), where the
pad is a constant and the coupling cannot form a loop.

Synthetic (``test_wallterrace291``'s lot arm): an apron at 100 m, a 3 m wall
along its north edge, a lot below it on ground rising 0.06 per metre and a
building on the lot.  Stage 2 alone leaves the lot on its own ground (only
the wall-foot pairs take the pad's level); the follower pass puts every
paired lot vertex at its pad's level and moves nothing else."""
from __future__ import annotations

import pytest
import test_wallterrace291 as wt
from auto_patch_v2.law import Law


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


@pytest.fixture(scope="module")
def arms(law):
    """(stage 2 alone, with the follower pass) on the walled lot airport."""
    from auto_patch_v2.airport import road_ramp as rr
    from auto_patch_v2.airport.road_ramp import WallPiece
    from auto_patch_v2.pipeline import lot_follow as lf
    from auto_patch_v2.solve import design as dz
    mp = pytest.MonkeyPatch()
    walls = (WallPiece(wt.WALL, 3.0, "wall.obj#comp0"),)
    try:
        mp.setattr(rr, "wall_pieces", lambda _ap, _cfg=None: walls)
        base = wt._solve(wt._lot_airport(), law)
        inner = dz.solve_design

        def with_follow(pm, cs, law_, *a, **kw):
            kw["follow_rewrite"] = lambda cs_x, z: lf.lot_follow_rewrite(pm, cs_x, z)
            return inner(pm, cs, law_, *a, **kw)
        import auto_patch_v2.solve as sv
        mp.setattr(sv, "solve_design", with_follow)
        follow = wt._solve(wt._lot_airport(), law)
    finally:
        mp.undo()
    return base, follow


def test_the_lot_level_map_pairs_the_lot_with_its_pad(arms):
    (pm, _sol, _rep), _f = arms
    rec = pm.road_terrace["lot_level"]
    assert rec["lots"] and rec["pairs"]
    pad_v = {v for f in pm.faces.values() if f.ref == "building2"
             for v in pm.ring_vertices(f.ring)}
    assert set(rec["pairs"].values()) <= pad_v


def test_the_follower_pass_levels_the_lot_to_its_pad_and_moves_nothing_else(arms):
    (pm0, sol0, _r0), (pm1, sol1, rep1) = arms
    assert rep1.follow_stage.get("kept") is True, rep1.follow_stage
    assert rep1.follow_stage["lot_level_rows"] > 0
    from auto_patch_v2.pipeline.lot_follow import _followers
    free = _followers(pm1)
    pairs = pm1.road_terrace["lot_level"]["pairs"]
    # same map, same stage 2: every non-follower is byte-identical
    assert len(sol0.z) == len(sol1.z)
    assert all(sol0.z[v] == sol1.z[v] for v in range(len(sol0.z)) if v not in free)
    lvl = [(v, q) for v, q in pairs.items() if v in free]
    assert lvl
    off0 = max(abs(sol0.z[v] - sol0.z[q]) for v, q in lvl)
    off1 = max(abs(sol1.z[v] - sol1.z[q]) for v, q in lvl)
    assert off0 > 0.5, off0                 # stage 2 alone: on its ground
    assert off1 <= 0.10, (off0, off1)       # the follower pass: at the pad


def test_no_lot_no_pass(law):
    """A map with no lot-level record: the rewrite returns None."""
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.pipeline.lot_follow import lot_follow_rewrite

    class _Pm:
        road_terrace: dict = {}
        faces: dict = {}
    assert lot_follow_rewrite(_Pm(), ConstraintSet.from_rows([]), (0.0,)) is None



def test_the_cap_window_is_every_cap_chain_from_a_constant():
    """A follower 10 m from a road held at 97 m under a 5 % cap may stand
    within 0.5 m of it, and one 10 m further within 1.0 m: the lot ramps AT
    its cap to the road and is flat at its pad beyond."""
    from auto_patch_v2.model.constraints import ConstraintSet, Diff, Source
    from auto_patch_v2.pipeline.lot_follow import _cap_windows
    src = Source("test", "common.roles longitudinal", ())
    cs = ConstraintSet.from_rows([Diff(0, 1, 0.05, 10.0, src), Diff(1, 2, 0.05, 10.0, src)])
    win = _cap_windows(cs, {0: 97.0}, {1, 2})
    assert win[1] == pytest.approx((96.5, 97.5))
    assert win[2] == pytest.approx((96.0, 98.0))
