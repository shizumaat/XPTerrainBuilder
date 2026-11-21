"""Twins for lane ``lfast1`` (#2206, ``docs/specs/fastest-pipeline-spec.md``).

6a. every stage solve leaves ONE clock record (label, columns, the parts)
    and the planar build its laps; the surface is the one solved without a
    collector (clocks are output-only).
1.  ``verify/nearest.FirstNearest`` answers ``min``'s index exactly — the
    first point at the minimum, ties and duplicates included.
"""
from __future__ import annotations

import random

import pytest

from auto_patch_v2.model import clocks
from auto_patch_v2.solve import solve_design
from auto_patch_v2.verify.nearest import SCAN_BELOW, FirstNearest

from test_flatpad128v3 import _arm, built, law  # noqa: F401  (fixtures)


# ── 6a ──────────────────────────────────────────────────────────────────

def test_each_stage_solve_leaves_one_clock_record_and_moves_nothing(law, built):  # noqa: F811
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    sol0, _r0 = solve_design(pm, cs, lw)
    with clocks.collecting() as recs:
        sol, _rep = solve_design(pm, cs, lw)
    assert sol.z == sol0.z
    labels = [r["label"] for r in recs]
    assert any(lb.startswith("stage1") for lb in labels)
    assert any(lb.startswith("stage2") for lb in labels)
    for r in recs:
        assert r["columns"] >= 0 and r["total_s"] >= 0.0
    full = [r for r in recs if r["columns"]]
    assert full and all(set(clocks.PARTS) <= set(r) for r in full)
    by = clocks.summary(recs)
    assert sum(s["solves"] for s in by.values()) == len(recs)


def test_no_collector_records_nothing_and_tags_name_the_purpose():
    clocks.note({"label": "x"})                      # no collector: dropped
    with clocks.collecting() as recs:
        with clocks.tag("pin_yield trial"):
            clocks.note({"label": clocks.label("stage2")})
    assert recs == [{"label": "stage2/pin_yield trial"}]


def test_the_planar_build_carries_its_laps(law, built):  # noqa: F811
    from test_flatpad128v3 import _airport, _cells
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.planar.build import build
    _pm, st = build(_airport(law), Classification(tuple(_cells()), (), {}, ()), law)
    assert {"objects", "arrangement", "shapes"} <= set(st.step_s)


# ── 1 ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", [3, SCAN_BELOW + 1, 2000])
def test_first_nearest_is_mins_index_with_ties(n):
    rng = random.Random(n)
    # a coarse lattice makes exact ties common; duplicates included
    pts = [(rng.randint(0, 40) * 0.5, rng.randint(0, 40) * 0.5) for _ in range(n)]
    pts += pts[: n // 5]
    near = FirstNearest(pts)
    for _ in range(3000):
        x, y = rng.randint(-4, 84) * 0.25, rng.randint(-4, 84) * 0.25
        want = min(range(len(pts)), key=lambda i: (pts[i][0] - x) ** 2 + (pts[i][1] - y) ** 2)
        assert near.index(x, y) == want


def test_first_nearest_reads_the_callers_points():
    recs = [((float(i), 0.0), f"cap{i}") for i in range(200)]
    near = FirstNearest(recs, lambda e: e[0])
    assert recs[near.index(10.4, 3.0)][1] == "cap10"
    assert recs[near.index(10.5, 0.0)][1] == "cap10"    # a tie: the first
    with pytest.raises(ValueError):
        FirstNearest([]).index(0.0, 0.0)


