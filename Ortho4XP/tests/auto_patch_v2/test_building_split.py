"""The building split (RULINGS 2026-11-27h; spec building-envelope §2):
the lattice supercover, the run regions and roofed enclosures, and the
split's classes on a synthetic plan."""
from __future__ import annotations

import numpy as np

from auto_patch_v2.airport.building_split import Params, PieceTable, split
from auto_patch_v2.geom import plan_lattice as pl
from auto_patch_v2.geom.underside_map import supercover

PRM = Params(0.5, 1, 2.5, 0.9, 0.5, 0.95, 2.5)


def _cells(xy, step=0.5):
    _t, i, a, b = supercover(np.asarray(xy, float), step)
    return {(int(r), int(j)) for r, s, e in zip(i, a, b) for j in range(s, e + 1)}


def test_supercover_marks_every_cell_a_triangle_meets():
    # a thin diagonal sliver crosses cells a centre sampler misses
    got = _cells([[(0.1, 0.1), (4.9, 4.9), (4.9, 4.91)]])
    assert {(k, k) for k in range(10)} <= got
    # a zero-area triangle is the segment it degenerates to
    seg = _cells([[(0.2, 0.2), (2.2, 0.2), (1.2, 0.2)]])
    assert seg == {(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)}
    # a point marks its cell
    assert _cells([[(1.3, 2.6), (1.3, 2.6), (1.3, 2.6)]]) == {(5, 2)}


def test_supercover_is_exact_for_a_square():
    sq = [[(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)], [(0.0, 0.0), (2.0, 2.0), (0.0, 2.0)]]
    got = _cells(sq)
    assert {(i, j) for i in range(4) for j in range(4)} <= got
    assert all(0 <= i <= 4 and 0 <= j <= 4 for i, j in got)


def test_regions_link_eight_and_two_cell():
    i = np.array([0, 1, 3], np.int64)
    a = np.array([0, 1, 3], np.int64)
    lab, n = pl.run_regions(i, a, a.copy(), 1)
    assert n == 2 and lab[0] == lab[1] != lab[2]
    _lab2, n2 = pl.run_regions(i, a, a.copy(), 2)
    assert n2 == 1


def test_roofed_fill_takes_only_covered_holes():
    m = np.zeros((7, 7), bool)
    m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = True
    i, a, b = pl._mask_runs(m, 10, 20)
    lab = np.zeros(len(i), np.int64)
    (_ri, ra, rb, _rl), _j, c = pl.roofed_fill(
        i, a, b, lab, 1, lambda _c, a0, b0, h, w: np.ones((h, w), bool), 0.9)
    assert c["roofed"] == 1 and int((rb - ra + 1).sum()) == 49
    (_ri, ra, rb, _rl), _j, c = pl.roofed_fill(
        i, a, b, lab, 1, lambda _c, a0, b0, h, w: np.zeros((h, w), bool), 0.9)
    assert c["unroofed"] == 1 and int((rb - ra + 1).sum()) == 24


def _table(pieces):
    tx, tt, to = [], [], []
    for k, pc in enumerate(pieces):
        for tr in pc["tris"]:
            v = np.asarray(tr, float)
            tx.append(v[:, :2])
            tt.append(v[:, 2].max())
            to.append(k)

    def col(key, dt):
        return np.asarray([p[key] for p in pieces], dt)
    return PieceTable(np.arange(len(pieces)), col("member", np.int64), col("anchor", np.int64),
                      col("h", float), col("deck", bool), np.zeros(len(pieces), bool),
                      col("footed", bool), col("top", float),
                      np.asarray([min(v[2] for tr in p["tris"] for v in tr) for p in pieces]),
                      np.asarray(tx), np.asarray(tt), np.asarray(to, np.int64))


def _wall(a, b, h):
    (x0, y0), (x1, y1) = a, b
    return [[(x0, y0, 0.0), (x1, y1, 0.0), (x1, y1, h)], [(x0, y0, 0.0), (x1, y1, h), (x0, y0, h)]]


def _plate(x0, y0, x1, y1, z):
    return [[(x0, y0, z), (x1, y0, z), (x1, y1, z)], [(x0, y0, z), (x1, y1, z), (x0, y1, z)]]


def _ring(x0, y0, x1, y1, h, member):
    return [{"tris": _wall(a, b, h), "h": h, "member": member, "anchor": 0, "deck": False,
             "footed": True, "top": h}
            for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                         ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)))]


def _leaf(tris, member, anchor=0, deck=False, footed=True, top=0.0):
    return {"tris": tris, "h": 0.0, "member": member, "anchor": anchor, "deck": deck,
            "footed": footed, "top": top}


def test_split_classes():
    ps = _ring(0, 0, 20, 20, 5, 0)                                     # A walls 0-3
    ps.append(_leaf(_plate(0, 0, 20, 20, 5), 0, footed=False, top=5))  # 4 roof
    ps.append(_leaf(_plate(1, 1, 19, 19, 0), 1))                       # 5 floor, other file
    ps.append(_leaf(_plate(1, 1, 10, 10, -6), 3, anchor=1, deck=True, footed=False,
                    top=-6))                                           # 6 basement deck
    ps += _ring(20.3, 0, 30, 10, 4, 4)                                 # B 0.3 m off A: 7-10
    ps += _ring(32, 0, 40, 10, 4, 5)                                   # C 2 m off: 11-14
    ps.append(_leaf(_plate(50, 50, 60, 60, 0), 6))                     # 15 far
    ps.append(_leaf(_plate(15, 15, 25, 25, 0.1), 0))                   # 16 A's file, astride
    s = split(_table(ps), PRM, contacts=[(0, 16)])
    assert s.of[0] == s.of[7] == 0                                     # under 0.5 m: one
    assert s.of[11] == 11 and 15 not in s.of                           # 2 m: two; far: none
    # a basement deck of another anchor inside the roofed hall moves with it
    assert {s.kind[q] for q in (4, 5, 6)} == {"interior"} and s.of[6] == 0
    assert s.kind[16] == "attached"                                    # B8
    assert [b.id for b in s.buildings] == [0, 11]
    assert s.buildings[0].anchors == (0, 1)


def test_sheet_joins_two_buildings():
    ps = _ring(0, 0, 10, 10, 5, 0) + _ring(14, 0, 24, 10, 5, 1)
    ps.append(_leaf(_plate(0, 0, 24, 10, 6), 2, footed=False, top=6))  # 8: roofs both
    s = split(_table(ps), PRM)
    assert s.kind[8] == "sheet" and s.of[0] == s.of[4] == 0
    ps[-1] = _leaf(_plate(0, 0, 24, 10, 6), 2, footed=True, top=6)     # footed: no link
    s = split(_table(ps), PRM)
    assert s.of[4] == 4 and 8 not in s.of


def test_split_is_order_free():
    ps = _ring(0, 0, 20, 20, 5, 0) + _ring(32, 0, 40, 10, 4, 1)
    a, b = split(_table(ps), PRM), split(_table(ps), PRM)
    assert a.of == b.of and np.array_equal(a.runs, b.runs)
