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


# ── cloudpoolreport (issue #412): the verify pool reports like the others ─

#: ``WorkPool.report``'s keys — the pack and planar pools' account
_KEYS = {"workers", "bound", "parallel", "fell_back", "reason", "wall_s", "tasks"}


def _ahead(**kw):
    said: list[str] = []
    told: list[dict] = []
    got = CW.outside_ahead(_faces(), TOL, MIN_D, out=said.append,
                           on_pool=told.append, **kw)
    return got, said, told


def test_a_pooled_reading_hands_its_account_and_says_its_line(monkeypatch):
    monkeypatch.setattr(CW, "MIN_CHORDS", 0)
    monkeypatch.setattr(CW, "CHUNK_CHORDS", 60)
    got, said, told = _ahead(workers=2)
    assert got is not None
    assert len(told) == 1 and set(told[0]) == _KEYS
    r = told[0]
    assert r["workers"] == 2 and r["bound"] == "pinned"
    assert r["parallel"] and not r["fell_back"] and r["reason"] == ""
    assert r["tasks"] > 0 and r["wall_s"] >= 0.0
    assert said == [f"[pool] workers 2 (bound: pinned): {r['tasks']} task(s) answered "
                    f"by workers in {r['wall_s']:.1f} s — verify: apron chords"]


def test_one_core_by_the_size_rule_or_the_budget_hands_no_account():
    for workers in (4, 1):                      # the size rule; the budget
        got, said, told = _ahead(workers=workers)
        assert got is None and said == [] and told == []


def test_a_pool_that_dies_hands_a_fell_back_account(monkeypatch):
    monkeypatch.setattr(CW, "MIN_CHORDS", 0)
    monkeypatch.setattr(CW, "CHUNK_CHORDS", 60)

    def dies(self, fn, tasks, **kw):
        self._give_up("twin: the workers died")
        return None
    monkeypatch.setattr(CW.WorkPool, "try_map", dies)
    got, said, told = _ahead(workers=2)
    assert got is None
    assert len(told) == 1 and set(told[0]) == _KEYS
    assert told[0]["fell_back"] and not told[0]["parallel"]
    assert told[0]["reason"] == "twin: the workers died" and told[0]["tasks"] == 0
    assert any(s.startswith("[pool] FELL BACK: twin: the workers died") for s in said)
    assert said[-1].endswith("FELL BACK (twin: the workers died) — verify: apron chords")


def test_rings_that_do_not_cross_hand_a_fell_back_account(monkeypatch):
    monkeypatch.setattr(CW, "MIN_CHORDS", 0)
    monkeypatch.setattr(CW, "CHUNK_CHORDS", 60)

    def no_shm(obj):
        raise OSError("no /dev/shm")
    monkeypatch.setattr(CW, "share_object", no_shm)
    got, said, told = _ahead(workers=2)
    assert got is None
    assert len(told) == 1 and set(told[0]) == _KEYS
    r = told[0]
    assert r["fell_back"] and not r["parallel"] and r["workers"] == 2 and r["tasks"] == 0
    assert "OSError: no /dev/shm" in r["reason"]
    assert len(said) == 1 and said[0].startswith("[pool] FELL BACK: ")


def test_the_verifier_threads_the_log_and_the_account(monkeypatch):
    monkeypatch.setattr(CW, "MIN_CHORDS", 0)
    monkeypatch.setattr(CW, "CHUNK_CHORDS", 60)
    p, shapes = _patch(monkeypatch)
    said: list[str] = []
    told: list[dict] = []
    assert W.read_chords_ahead(p, shapes, MIN_D, workers=2, out=said.append,
                               on_pool=told.append) == len(shapes)
    assert len(said) == 1 and len(told) == 1 and told[0]["parallel"]


def test_the_build_report_carries_the_verify_pool():
    """``pipeline/build.py`` hands the verify stage its own log and keeps
    the pool's account under ``report["pool"]["verify"]`` (``None`` when
    no pool was opened).  A source pin: no twin runs the whole pipeline."""
    import importlib
    import inspect
    B = importlib.import_module("auto_patch_v2.pipeline.build")
    C = importlib.import_module("auto_patch_v2.verify.census")
    for fn in (C.census_frame, C.census_patch):
        assert {"say", "on_pool"} <= set(inspect.signature(fn).parameters)
    assert {"out", "on_pool"} <= set(inspect.signature(W.within_shape).parameters)
    src = inspect.getsource(B.build)
    assert 'say=lambda m: _say("  " + m, out),' in src
    assert "on_pool=_vpool.append)" in src
    assert '"verify": _vpool[-1] if _vpool else None}' in src
