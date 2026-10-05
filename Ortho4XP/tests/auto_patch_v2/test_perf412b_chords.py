"""Lane ``perf412b`` twin, R3 (issue #412): ``verify/chord_work`` — the
chords of an apron ring that leave its face.  The chunked reading is the
whole-ring reading the verifier made before, and the work pool's answer is
the serial answer at 2 and N workers; a small population and a budget of 1
are read on one core.
"""
from __future__ import annotations

import math
import os
import types

import numpy as np
import pytest

from auto_patch_v2.constraints.geometry import chords_covered, face_cover
from auto_patch_v2.verify import chord_work as CW
from auto_patch_v2.verify import within as W


# ── R3: the apron chords that leave their face ───────────────────────────

def _outside_before(xy, holes, tol, min_d) -> set[tuple[int, int]]:
    """``verify.within._chords_outside_face``'s body as it stood before
    the lane, over the ring and holes it read off the patch."""
    cover = face_cover(xy, holes, tol)
    if cover is None:
        return set()
    n = len(xy)
    pairs: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            (xa, ya), (xb, yb) = xy[i], xy[j]
            if math.hypot(xa - xb, ya - yb) >= min_d:
                pairs.append((i, j))
    ok = chords_covered(cover, [(xy[i], xy[j]) for i, j in pairs])
    return {pr for pr, k in zip(pairs, ok) if not k}


def _faces() -> list:
    """Apron-like rings: an L with a hole, a comb (most chords leave it), a
    convex ring (none does), a ring with a doubled vertex, a triangle and a
    degenerate two-vertex ring."""
    ell = [(0.0, 0.0), (120.0, 0.0), (120.0, 30.0), (90.0, 30.0), (60.0, 30.0),
           (30.0, 30.0), (30.0, 60.0), (30.0, 90.0), (30.0, 120.0), (0.0, 120.0),
           (0.0, 80.0), (0.0, 40.0)]
    comb: list = [(0.0, 0.0)]
    for k in range(12):
        comb += [(10.0 * k + 6.0, 0.0), (10.0 * k + 6.0, 40.0),
                 (10.0 * k + 9.0, 40.0), (10.0 * k + 9.0, 0.0)]
    comb += [(125.0, 0.0), (125.0, -10.0), (0.0, -10.0)]
    disc = [(float(50 * math.cos(t)), float(50 * math.sin(t)))
            for t in np.linspace(0.0, 2 * math.pi, 61)[:-1]]
    doubled = disc[:10] + [disc[9]] + disc[10:]
    return [(ell, [[(5.0, 5.0), (20.0, 5.0), (20.0, 20.0), (5.0, 20.0)]]),
            (comb, []), (disc, [[(-5.0, -5.0), (5.0, -5.0), (0.0, 6.0)]]),
            (doubled, []), (disc[:3], []), (disc[:2], [])]


TOL, MIN_D = 0.05, 0.1


def test_chunked_reading_is_the_whole_ring_reading():
    for xy, holes in _faces():
        want = _outside_before(xy, holes, TOL, MIN_D)
        got = CW.chords_outside(xy, holes, TOL, MIN_D)
        assert len(got) == len(set(got)) and set(got) == want
        cover = face_cover(xy, holes, TOL)
        if cover is None:
            continue
        for size in (1, 7, 50, 10 ** 9):
            parts = CW.chunks(len(xy), size)
            assert [a for a, _b, _w in parts] == [0] + [b for _a, b, _w in parts][:-1]
            assert parts[-1][1] == len(xy)
            rows = [pr for i0, i1, _w in parts
                    for pr in CW.rows_outside(cover, xy, MIN_D, i0, i1)]
            assert rows == got                   # the same pairs, the same order
    assert sum(len(_outside_before(xy, h, TOL, MIN_D)) for xy, h in _faces()) > 500


@pytest.mark.parametrize("n", [2, max(3, os.cpu_count() or 3)])
def test_pooled_chords_are_the_serial_chords(n, monkeypatch):
    monkeypatch.setattr(CW, "MIN_CHORDS", 0)
    monkeypatch.setattr(CW, "CHUNK_CHORDS", 60)
    faces = _faces()
    said: list[str] = []
    got = CW.outside_ahead(faces, TOL, MIN_D, workers=n, out=said.append)
    assert got == [CW.chords_outside(xy, holes, TOL, MIN_D) for xy, holes in faces]
    assert [set(g) for g in got] == [_outside_before(xy, h, TOL, MIN_D) for xy, h in faces]
    assert len(said) == 1 and said[0].startswith("[pool] workers ")
    assert "FELL BACK" not in said[0] and "verify: apron chords" in said[0]


def test_one_core_and_a_small_patch_read_nothing_ahead(monkeypatch):
    faces = _faces()
    said: list[str] = []
    assert CW.outside_ahead(faces, TOL, MIN_D, workers=1, out=said.append) is None
    assert CW.outside_ahead(faces, TOL, MIN_D, workers=4, out=said.append) is None  # small
    assert CW.outside_ahead(faces, TOL, MIN_D, out=said.append) is None  # the suite pins 1
    assert said == []


class _Law:
    """Just what ``snap_margin_m`` reads is patched below; a stand-in."""


def _patch(monkeypatch):
    monkeypatch.setattr(W, "snap_margin_m", lambda law: TOL)
    shapes = [types.SimpleNamespace(key=k, xy=tuple(xy)) for k, (xy, _h) in enumerate(_faces())]
    feats = [types.SimpleNamespace(feature="gap_interior_ring", host=k, xy=tuple(h))
             for k, (_xy, hs) in enumerate(_faces()) for h in hs]
    feats.append(types.SimpleNamespace(feature="crown_spine", host=0, xy=((1.0, 1.0),)))
    return types.SimpleNamespace(law=_Law(), shapes=shapes, features=feats), shapes


def test_the_verifier_reads_the_same_set_serial_and_ahead(monkeypatch):
    monkeypatch.setattr(CW, "MIN_CHORDS", 0)
    monkeypatch.setattr(CW, "CHUNK_CHORDS", 60)
    want = [_outside_before(xy, h, TOL, MIN_D) for xy, h in _faces()]
    p, shapes = _patch(monkeypatch)
    assert W.read_chords_ahead(p, shapes, MIN_D) == 0          # the suite pins 1
    assert [W.chords_outside_face(p, sh, MIN_D) for sh in shapes] == want
    p2, shapes2 = _patch(monkeypatch)
    assert W.read_chords_ahead(p2, shapes2, MIN_D, workers=2) == len(shapes2)
    monkeypatch.setattr(W, "_chords_outside_face", None)       # the memo answers
    assert [W.chords_outside_face(p2, sh, MIN_D) for sh in shapes2] == want
    assert W.read_chords_ahead(p2, shapes2, MIN_D, workers=2) == 0   # nothing left
