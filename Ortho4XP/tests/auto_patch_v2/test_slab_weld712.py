"""Issue #712 twin (owner RULINGS 2026-10-10o (B)): a base-slab piece and
the pack gap piece beside it are welded across the stand-off in the last
stage — one hard row per slab rim vertex against the nearest pack-piece
vertex within the follow reach, at the slab's role cap.  Hermetic."""
from __future__ import annotations

import types

from auto_patch_v2.constraints.gap_follow import reach_m
from auto_patch_v2.constraints.slab_weld import RULING, slab_weld_rows
from auto_patch_v2.law import Law


def _map(gap_m):
    # a slab piece x 0..10 and a pack lot x 10+gap .. 30, both 10 m deep
    xy = {0: (0, 0), 1: (10, 0), 2: (10, 10), 3: (0, 10),
          4: (10 + gap_m, 0), 5: (30, 0), 6: (30, 10), 7: (10 + gap_m, 10)}
    verts = {k: types.SimpleNamespace(xy=p) for k, p in xy.items()}
    faces = {0: types.SimpleNamespace(id=0, ref="gap:9", role="parking_lot",
                                      ring=(0, 1, 2, 3), holes=()),
             1: types.SimpleNamespace(id=1, ref="gap:3/s0", role="groundside_pavement",
                                      ring=(4, 5, 6, 7), holes=())}
    return types.SimpleNamespace(vertices=verts, faces=faces,
                                 ring_vertices=lambda cyc: tuple(cyc))


def _cl():
    cell = lambda ref, ev: types.SimpleNamespace(ref=ref, evidence=ev)
    return types.SimpleNamespace(cells=(cell("gap:9", {"base_slab": 1.0}),
                                        cell("gap:3/s0", {})))


def test_the_slab_rim_welds_to_the_lot_across_the_stand_off():
    law = Law.load()
    rows, rep = slab_weld_rows(_map(1.5), law, _cl(), {})
    assert rep == {"pairs": 2, "slab_faces": 1}
    assert {(r.a, r.b) for r in rows} == {(1, 4), (2, 7)}
    assert all(r.source.ruling == RULING and r.d == 1.5 for r in rows)
    # hard: the head is in the law's hard set
    assert RULING.split("(")[0].strip() in law.tables.emit.design.hard_rulings


def test_beyond_the_follow_reach_or_on_a_constant_nothing_is_welded():
    law = Law.load()
    far = reach_m(law) + 1.0
    assert slab_weld_rows(_map(far), law, _cl(), {})[0] == []
    rows, _rep = slab_weld_rows(_map(1.5), law, _cl(), {4: 93.0})
    assert {(r.a, r.b) for r in rows} == {(2, 7)}


def test_an_elevated_decks_ground_is_never_welded():
    law = Law.load()
    cell = lambda ref, ev: types.SimpleNamespace(ref=ref, evidence=ev)
    cl = types.SimpleNamespace(cells=(cell("gap:9", {"base_slab": 1.0, "base_slab_deck": 1.0}),
                                      cell("gap:3/s0", {})))
    assert slab_weld_rows(_map(1.5), law, cl, {})[0] == []
