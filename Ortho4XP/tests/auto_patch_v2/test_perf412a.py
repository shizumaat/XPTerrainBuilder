"""#412 — THREE SAME-ANSWER SHORTCUTS IN THE CONSTRAINT GENERATORS, twinned.

Each of these removes work without touching one output value, so each twin
states the OLD reading in the test and asserts ``==`` against it (order
included), never ``approx``:

* R1 ``pad_frontage_gs.groundside_frontage`` reads the whole-map
  ``pads.pad_fronts_airside`` ONCE, not once per pad polygon.
* R2 ``stretches.AxisIndex._tied`` measures only the segments binned
  within ``d0 + tie_m`` of the point — the whole-index scan's list.
* R5 ``routes.route_pairs`` is memoised by CONTENT in two slots, so the
  emit's read of the first map's table survives the ribbon-free pass and
  the ``with_pin_yield`` replacement of the map object.

Offline and synthetic — no corpus, no network.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import random

import pytest

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints import pad_frontage_gs, routes as R, taxi
from auto_patch_v2.constraints.pads import _pad_polys, pad_fronts_airside
from auto_patch_v2.constraints.stretches import AxisIndex
from auto_patch_v2.law import Law
from auto_patch_v2.planar.build import build

from test_taxi_route_pairs import hook  # noqa: F401  (the hook-stub fixture)
from test_v2frontage import _airport, _cells
from test_v2frontagestep import _StepDem


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── R1 ────────────────────────────────────────────────────────────────────

def test_the_groundside_relation_derives_the_pad_frontage_once(law, monkeypatch):
    airport = _airport(law, _StepDem(0.5))
    pm, _st = build(airport, Classification(tuple(_cells(second_pad=True)), (), {}, ()), law)
    assert len(_pad_polys(pm, law)) >= 2
    calls = []

    def counted(planar, law_):
        calls.append(1)
        return pad_fronts_airside(planar, law_)
    monkeypatch.setattr(pad_frontage_gs, "pad_fronts_airside", counted)
    rel = pad_frontage_gs.groundside_frontage(pm, law)
    assert len(calls) == 1
    # the relation is the per-pad reading's: every leader is a pad the test
    # names airside-fronting, read here the way the comprehension read it
    leaders = {row[0] for rows in rel.values() for row in rows}
    assert leaders and leaders <= {p[0] for p in _pad_polys(pm, law)
                                   if p[0] in pad_fronts_airside(pm, law)}


# ── R2 ────────────────────────────────────────────────────────────────────

def _whole_scan(ix: AxisIndex, x: float, y: float, d0: float):
    """The reading ``_tied`` replaced, verbatim: every segment, in order."""
    out = []
    for ax, ay, ux, uy, ln, cl, ct in ix.segs:
        t = max(0.0, min(ln, (x - ax) * ux + (y - ay) * uy))
        if abs(math.hypot(x - (ax + t * ux), y - (ay + t * uy)) - d0) <= ix.tie_m:
            out.append((ux, uy, cl, ct))
    return out


def _axes(rng: random.Random):
    """Stretches with CORNERS, shared ENDS, crossings, a duplicate and long
    segments spanning many cells — every way two segments tie at a point."""
    axes = [([(0.0, 0.0), (300.0, 0.0), (300.0, 240.0), (0.0, 240.0)], 0.015, 0.015),
            ([(150.0, -200.0), (150.0, 500.0)], 0.03, 0.015),          # crosses both
            ([(300.0, 0.0), (700.0, 400.0)], 0.02, 0.01),              # shares a corner
            ([(0.0, 0.0), (300.0, 0.0)], 0.01, 0.02),                  # a duplicate
            ([(-900.0, 37.0), (2100.0, 41.0)], 0.0125, 0.015)]         # spans the grid
    for _ in range(40):
        x, y = rng.uniform(-800, 1800), rng.uniform(-800, 1800)
        pts = [(x, y)]
        for _k in range(rng.randint(1, 6)):
            x, y = x + rng.uniform(-120, 120), y + rng.uniform(-120, 120)
            pts.append((x, y))
        axes.append((pts, rng.choice((0.01, 0.015, 0.03)), rng.choice((0.01, 0.015))))
    return axes


@pytest.mark.parametrize("cell", [3.0, 15.0, 60.0])
def test_the_tied_segments_are_the_whole_scans_element_for_element(cell):
    rng = random.Random(412)
    ix = AxisIndex(_axes(rng), cell)
    pts = [(300.0, 0.0), (150.0, 0.0), (150.0, 240.0), (0.0, 0.0), (310.0, -10.0),
           (150.0, 39.0), (5000.0, -4000.0), (-2500.0, 9000.0)]
    pts += [(a[0] + dx, a[1] + dy) for a in (s[:2] for s in ix.segs[::7])
            for dx, dy in ((0.0, 0.0), (0.25, -0.25))]
    pts += [(rng.uniform(-1000, 2200), rng.uniform(-1000, 2200)) for _ in range(1500)]
    pruned = tied = 0
    for x, y in pts:
        d0 = ix._nearest(x, y)[0]
        for d in (d0, 0.0, d0 + 0.5 * ix.tie_m, 7.5, 120.0, 1e5):
            got = ix._tied(x, y, d)
            assert got == _whole_scan(ix, x, y, d)
            tied += len(got) > 1
            pruned += len(ix._within(x, y, d + ix.tie_m)) < len(ix.segs)
    assert tied > 0 and pruned > 0          # both the tie and the shortcut are exercised
    # ascending and duplicate-free: the order the whole scan visits them in
    ks = list(ix._within(310.0, -10.0, 25.0))
    assert ks == sorted(set(ks))


def test_a_block_covering_the_grid_is_the_whole_index():
    ix = AxisIndex(_axes(random.Random(1)), 15.0)
    assert list(ix._within(0.0, 0.0, 1e7)) == list(range(len(ix.segs)))


# ── R5 ────────────────────────────────────────────────────────────────────

@pytest.fixture()
def clean_memo():
    R._PAIRS_MEMO.clear()
    before = dict(R._PAIRS_READS)
    yield lambda: {k: R._PAIRS_READS[k] - before[k] for k in before}
    R._PAIRS_MEMO.clear()



def test_the_route_table_survives_a_replaced_map_and_a_second_map(hook, law, clean_memo):  # noqa: F811
    airport, pm = hook
    first = taxi.taxi_pair_routes(pm, law, airport)
    assert any(pp.budget is not None for pp in first)
    assert clean_memo() == {"hit": 0, "miss": 1}
    g = R.routes(pm, law, airport)
    nodes = sorted(g.nodes)
    # the ribbon-free pass: ANOTHER table priced in between (other groups)
    other = R.route_pairs(g, [nodes[: len(nodes) // 2]])
    assert clean_memo() == {"hit": 0, "miss": 2} and other
    # ``emit.road_join.with_pin_yield``: a NEW map object, two join fields swapped
    v = nodes[0]
    pm2 = _dc.replace(pm, road_coverage_join={v: 701.0}, road_join_yield={v: (700.0, 701.0)})
    assert pm2 is not pm
    again = taxi.taxi_pair_routes(pm2, law, airport)
    assert clean_memo() == {"hit": 1, "miss": 2}        # served, not re-priced
    assert again == first


def test_the_route_table_key_is_the_content_it_is_priced_from(hook, law, clean_memo):  # noqa: F811
    airport, pm = hook
    g = R.routes(pm, law, airport)
    groups = [sorted(g.nodes)]
    a = R.route_pairs(g, groups)
    assert R.route_pairs(g, [list(reversed(groups[0]))]) is a      # same cut groups
    # a copy of the graph with EQUAL arrays is the same content
    assert R.route_pairs(_dc.replace(g, cap=g.cap.copy()), groups) is a
    # a different cap is a different budget matrix: priced afresh, and differs
    b = R.route_pairs(_dc.replace(g, cap=g.cap * 2.0), groups)
    assert b is not a and list(b) == list(a)
    assert [d for d, _ in b.values()] == [d for d, _ in a.values()]
    assert [w for _, w in b.values()] != [w for _, w in a.values()]
    # fewer groups: fewer pairs
    c = R.route_pairs(g, [groups[0][:3]])
    assert c is not a and set(c) < set(a)
    assert clean_memo() == {"hit": 2, "miss": 3}
    # TWO slots, most recent kept: ``a`` was pushed out by ``b`` then ``c``
    assert len(R._PAIRS_MEMO) == R._PAIRS_SLOTS
    assert R.route_pairs(g, groups) is not a
    assert R.route_pairs(g, groups) == a
