"""#2206 (RULINGS 2026-11-24d): the late derive reads back the main pass's
answers wherever their inputs are EQUAL -- held by content
(``model/map_memo``), never by identity, and equal to a fresh
reading."""
from __future__ import annotations

import random
import types

from auto_patch_v2.constraints import junction_mesh as jm
from auto_patch_v2.constraints import taxi
from auto_patch_v2.constraints.stretches import AxisIndex
from auto_patch_v2.model.map_memo import ContentSlots

_AXES = (
    (((0.0, 0.0), (400.0, 0.0), (400.0, 300.0)), 0.015, 0.015),
    (((0.0, 120.0), (380.0, 140.0)), 0.03, 0.015),
    (((200.0, -50.0), (210.0, 400.0)), 0.015, 0.02),
)


def _pts(n: int, seed: int) -> list[tuple[float, float]]:
    rnd = random.Random(seed)
    return [(rnd.uniform(-60.0, 460.0), rnd.uniform(-60.0, 360.0)) for _ in range(n)]


def test_content_slots_serve_equal_content_and_keep_the_last_few():
    slots: ContentSlots[object] = ContentSlots(2)
    a = slots.get((1, (2.0, 3.0)), object)
    assert slots.get((1, (2.0, 3.0)), object) is a          # equal, not identical, key
    b = slots.get((2,), object)
    slots.get((3,), object)                                  # evicts the oldest, (1, ...)
    assert slots.get((2,), object) is b
    assert slots.get((1, (2.0, 3.0)), object) is not a
    assert slots.reads == {"hit": 2, "miss": 4}


def test_a_held_box_answer_is_the_fresh_reading():
    held = AxisIndex(_AXES, 30.0)
    pts = _pts(200, 1)
    pairs = list(zip(pts[:-1], pts[1:], strict=True))
    first = [held.box_bound(xa, ya, xb, yb) for (xa, ya), (xb, yb) in pairs]
    again = [held.box_bound(xa, ya, xb, yb) for (xa, ya), (xb, yb) in pairs]
    fresh = [AxisIndex(_AXES, 30.0).box_bound(xa, ya, xb, yb)
             for (xa, ya), (xb, yb) in pairs]
    assert first == again == fresh
    assert len(held._boxes) == len(set(pairs))


def _view(xy: dict, cell: float):
    law = types.SimpleNamespace(tables=types.SimpleNamespace(emit=types.SimpleNamespace(
        within_shape=types.SimpleNamespace(withdrawn_chord_min_m=cell))))
    return types.SimpleNamespace(xy=xy, law=law)


def _stretches(ids_of_axes):
    return types.SimpleNamespace(items=tuple(
        types.SimpleNamespace(vertices=vs, cap_l=cl, cap_t=ct) for vs, cl, ct in ids_of_axes))


def test_equal_stretches_under_other_vertex_ids_share_one_index():
    taxi._INDEXES.clear()
    xy_a, xy_b, st_a, st_b = {}, {}, [], []
    for k, (pts, cl, ct) in enumerate(_AXES):
        ids_a = tuple(10 * k + j for j in range(len(pts)))
        ids_b = tuple(1000 + 7 * k + j for j in range(len(pts)))   # a renumbered map
        xy_a.update(zip(ids_a, pts, strict=True))
        xy_b.update(zip(ids_b, pts, strict=True))
        st_a.append((ids_a, cl, ct))
        st_b.append((ids_b, cl, ct))
    first = taxi.axis_index(_view(xy_a, 30.0), _stretches(st_a))
    assert taxi.axis_index(_view(xy_b, 30.0), _stretches(st_b)) is first
    # a moved stretch vertex, or another cell, is another index
    xy_c = dict(xy_b)
    xy_c[1000] = (0.0, 0.001)
    assert taxi.axis_index(_view(xy_c, 30.0), _stretches(st_b)) is not first
    assert taxi.axis_index(_view(xy_b, 25.0), _stretches(st_b)) is not first
    taxi._INDEXES.clear()


def test_triangle_boxes_read_from_the_memo_equal_the_fresh_boxes():
    pts = _pts(60, 2)
    vw = types.SimpleNamespace(xy=dict(enumerate(pts)))
    tris = [(k, k + 1, k + 2) for k in range(0, 57, 3)]
    axes = [(list(p), cl, ct) for p, cl, ct in _AXES[:2]]
    fallback = [(list(p), cl, ct) for p, cl, ct in _AXES]
    fresh_a = jm.triangle_boxes(vw, axes, tris)
    fresh_f = jm.triangle_boxes(vw, [], tris, fallback, (0.02, 0.03))
    memo_a: dict = {}
    memo_f: dict = {}
    for _ in range(2):          # filled, then read back
        assert jm.triangle_boxes(vw, axes, tris, memo=memo_a) == fresh_a
        assert jm.triangle_boxes(vw, [], tris, fallback, (0.02, 0.03), memo={},
                                 memo_fallback=memo_f) == fresh_f
    assert len(memo_a) == len(tris) and len(memo_f) == len(tris)


def test_same_keys_by_identity_and_holds_its_object():
    from auto_patch_v2.model.map_memo import Same
    a, b = [1], [1]
    assert Same(a) == Same(a) and hash(Same(a)) == hash(Same(a))
    assert Same(a) != Same(b)               # equal value, another object


def _seeds_site(tmp_path):
    from test_level_seeds1852 import _station
    from test_two_pads1214 import _airport
    A = _airport(_station(), tmp_path, ground=lambda x, y: 26.0)
    A.osm_ways = []
    A.dsf_objects = ()
    A.frame.transformers = lambda: ((lambda lon, lat: (lon, lat)), (lambda x, y: (y, x)))
    return A


def _cell(ring, role):
    return types.SimpleNamespace(ring=ring, holes=(), role=role)


def test_the_late_derives_level_seeds_are_the_main_passs(tmp_path):
    """The planar build's wiring (``held_read`` under ``seeds_key``): a
    groundside cell more (the late derive's gap piece) is served the held
    seeds; an airside cell changed is read afresh; both equal a plain
    read."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar import level_regions as LR
    from auto_patch_v2.planar.pack_reads import held_read
    from test_level_seeds1852 import AIR
    law = Law.for_airport("ZZZZ")
    A = _seeds_site(tmp_path)
    apron = _cell(tuple(AIR.exterior.coords)[:-1], "apron")
    piece = _cell(((600.0, 0.0), (650.0, 0.0), (650.0, 40.0)), "service_road")
    base = types.SimpleNamespace(cells=[apron])
    late = types.SimpleNamespace(cells=[apron, piece])
    moved = types.SimpleNamespace(cells=[_cell(((400.0, 100.0), (500.0, 100.0),
                                                (500.0, 131.0), (400.0, 130.0)), "apron")])
    cache, objects = types.SimpleNamespace(placed={}), []
    reads: list = []

    def seeds(cl):
        return held_read(A, objects, cache, law, LR.seeds_key(A, cl, law),
                         lambda: reads.append(1) or LR.level_seeds(A, cl, law, cache))
    got = seeds(base)
    assert got[0] and got == LR.level_seeds(A, base, law, None)
    assert seeds(late) == got and len(reads) == 1
    assert seeds(moved) == LR.level_seeds(A, moved, law, None) and len(reads) == 2


def _graph(perm: list[int]):
    """A centreline 0-1-2-3 (stations) and three leaves hopping onto it,
    every vertex renamed ``perm[v]`` (the late map's other numbering)."""
    import numpy as np
    from auto_patch_v2.constraints import routes as R
    xy = {0: (0.0, 0.0), 1: (100.0, 0.0), 2: (200.0, 10.0), 3: (300.0, 0.0),
          4: (50.0, 20.0), 5: (150.0, -15.0), 6: (310.0, 25.0)}
    edges = [(0, 1, R.CENTRELINE), (1, 2, R.CENTRELINE), (2, 3, R.CENTRELINE),
             (4, 0, R.LATERAL), (5, 2, R.LATERAL), (6, 3, R.LATERAL)]
    n = len(xy)
    a = np.array([min(perm[u], perm[v]) for u, v, _k in edges], np.int64)
    b = np.array([max(perm[u], perm[v]) for u, v, _k in edges], np.int64)
    ln = np.array([((xy[u][0] - xy[v][0]) ** 2 + (xy[u][1] - xy[v][1]) ** 2) ** 0.5
                   for u, v, _k in edges])
    station = np.zeros(n, bool)
    station[[perm[v] for v in (0, 1, 2, 3)]] = True
    g = R.RouteGraph(n=n, nodes=frozenset(range(n)), a=a, b=b, length=ln,
                     cap=np.full(len(edges), 0.015),
                     kind=np.array([k for _u, _v, k in edges]), station=station)
    planar = types.SimpleNamespace(vertices={perm[v]: types.SimpleNamespace(xy=p)
                                             for v, p in xy.items()})
    return g, planar


def test_an_equal_route_graph_under_other_ids_is_read_back_exactly(monkeypatch):
    from auto_patch_v2.constraints import routes as R
    walks: list = []
    real = R.dijkstra
    monkeypatch.setattr(R, "dijkstra",
                        lambda *a, **k: walks.append(list(k["indices"])) or real(*a, **k))
    ring = [0, 4, 1, 5, 2, 3, 6]
    g1, p1 = _graph(list(range(7)))
    R._PAIRS_MEMO.clear()
    R._HELD_PRICING.clear()
    first = R.route_pairs(g1, [ring], labels=R.walk_labels(p1, g1))
    perm = [1, 2, 3, 4, 5, 6, 0]       # every id moves; vertex 6's pairs flip
    g2, p2 = _graph(perm)
    ring2 = [perm[v] for v in ring]
    n_walks = len(walks)
    served = R.route_pairs(g2, [ring2], labels=R.walk_labels(p2, g2))
    walked = sum(len(w) for w in walks[n_walks:]) // 2      # two walks per source
    R._PAIRS_MEMO.clear()
    fresh = R.route_pairs(g2, [ring2])
    assert first and list(served.items()) == list(fresh.items())   # values and order
    # vertex 6 (now 0) is walked again: its pairs ran from the other end
    assert walked == 1
