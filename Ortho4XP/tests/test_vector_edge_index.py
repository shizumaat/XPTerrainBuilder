"""Twins for the vector step's edge index and encroachment fast paths.

``O4_Vector_Utils.Edge_Index`` removes stock ``rtree``'s per-call Python
(two ctypes round-trips for the index type and dimension, a rebuilt
coordinate array, a re-validated ordering) and ``are_encroached`` takes
``ab`` / ``norm_ab`` from its caller instead of recomputing them per
candidate edge.  Neither may change a single emitted byte, and BOTH are
order-sensitive in a way that is invisible locally: the order
``intersection`` hands back candidate edges decides which encroachment
``insert_edge`` resolves first, hence which node ids get minted, hence
the bytes of ``Data+XX+YYY.node``.

So these are DISABLED-VS-ENABLED twins, not smoke tests:

* the id list AND ITS ORDER, against stock ``rtree.index.Index``, across
  inserts, deletes and re-inserts;
* ``are_encroached`` against the pre-change expression, spelled out here
  as the reference, over random and degenerate configurations;
* a whole ``Vector_Map`` — its ``.node`` and ``.poly`` files, byte for
  byte — built with the fast path on and with it off.

Headless: no engine config, no DEM, no network, no shared repo.
"""
import os
import random
import sys

import numpy
import pytest
from rtree import index

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import O4_Vector_Utils as VECT  # noqa: E402


# ── the reference: are_encroached exactly as it was before the change ──
def _are_encroached_reference(a, b, c, d):
    ab = b - a
    dc = c - d
    pnorm = numpy.linalg.norm(ab) * numpy.linalg.norm(dc)
    ac = c - a
    ab_dot_dc = numpy.dot(ab, dc)
    if ((a == d).all() or (b == c).all()) and ab_dot_dc < 0.9999 * pnorm:
        return False
    if ((a == c).all() or (b == d).all()) and ab_dot_dc > -0.9999 * pnorm:
        return False
    eps = 1e-8
    oneminuseps = 1.0 - eps
    A = numpy.column_stack((ab, dc))
    if abs(numpy.linalg.det(A)) > eps * pnorm:
        [alpha, beta] = numpy.linalg.solve(A, ac)
        return (
            (alpha >= 0 and alpha <= 1)
            and (beta >= 0 and beta <= 1)
            and (
                (alpha > eps and alpha < oneminuseps)
                or (beta > eps and beta < oneminuseps)
            )
            and (alpha, beta)
        )
    elif abs(ab[0] * ac[1] - ab[1] * ac[0]) > eps * numpy.linalg.norm(
            ab) * numpy.linalg.norm(ac):
        return False
    else:
        g_idx = numpy.argmax(abs(ab))
        d_idx = numpy.argmax(abs(dc))
        alpha0, alpha1 = ac[g_idx] / ab[g_idx], (d - a)[g_idx] / ab[g_idx]
        beta0, beta1 = ac[d_idx] / dc[d_idx], (c - b)[d_idx] / dc[d_idx]
        return (
            (alpha0 > eps or alpha1 > eps)
            and (alpha0 < oneminuseps or alpha1 < oneminuseps)
            and (alpha0, alpha1, beta0, beta1)
        )


def _boxes(n, rng):
    out = []
    for _ in range(n):
        x0, x1 = sorted((rng.random(), rng.random()))
        y0, y1 = sorted((rng.random(), rng.random()))
        out.append((x0, y0, x1, y1))
    return out


def test_the_fast_path_is_actually_taken_for_the_vector_maps_index():
    """A silently-disabled fast path would pass every other test here."""
    assert VECT.Edge_Index().fast_path is True
    assert VECT.Vector_Map().ebbox.fast_path is True


def test_intersection_ids_matches_stock_rtree_ids_AND_ORDER():
    rng = random.Random(20260813)
    boxes = _boxes(400, rng)
    fast, stock = VECT.Edge_Index(), index.Index()
    for i, box in enumerate(boxes):
        fast.insert(i, box)
        stock.insert(i, box)
    # ... then churn it the way insert_edge does: delete an entry and put
    # two back, so the trees have a split/reinsert history, not just a
    # bulk load.
    for i in range(0, 200, 7):
        fast.delete(i, boxes[i])
        stock.delete(i, boxes[i])
        for k, half in enumerate(_boxes(2, rng)):
            fast.insert(1000 + i * 2 + k, half)
            stock.insert(1000 + i * 2 + k, half)

    for query in _boxes(200, rng) + [(0, 0, 1, 1), (0.5, 0.5, 0.5, 0.5)]:
        assert list(fast.intersection_ids(query)) == \
            list(stock.intersection(query)), query


def test_intersection_ids_matches_the_objects_true_order_it_replaced():
    """insert_edge used to read ids off ``objects=True`` Items."""
    rng = random.Random(4321)
    boxes = _boxes(300, rng)
    idx = VECT.Edge_Index()
    for i, box in enumerate(boxes):
        idx.insert(i, box)
    for query in _boxes(100, rng):
        assert list(idx.intersection_ids(query)) == \
            [hit.id for hit in idx.intersection(query, objects=True)]


def test_the_index_falls_back_when_the_fast_path_does_not_apply():
    rng = random.Random(99)
    boxes = _boxes(50, rng)
    idx = VECT.Edge_Index()
    idx.fast_path = False           # as a non-2D / TPR index would be
    for i, box in enumerate(boxes):
        idx.insert(i, box)
    assert sorted(idx.intersection_ids((0, 0, 1, 1))) == list(range(50))
    idx.delete(0, boxes[0])
    assert 0 not in list(idx.intersection_ids((0, 0, 1, 1)))


def test_are_encroached_equals_the_pre_change_expression():
    rng = random.Random(2026)
    vmap = VECT.Vector_Map()
    pts = [numpy.array([rng.choice([0.0, 0.25, 0.5, rng.random()]),
                        rng.choice([0.0, 0.25, 0.5, rng.random()])])
           for _ in range(600)]
    checked = 0
    for i in range(0, len(pts) - 3, 2):
        a, b, c, d = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        if (a == b).all() or (c == d).all():
            continue        # degenerate input the caller never produces
        expected = _are_encroached_reference(a, b, c, d)
        assert vmap.are_encroached(a, b, c, d) == expected
        # ... and with the hoisted invariants the caller now passes in
        assert vmap.are_encroached(
            a, b, c, d, ab=b - a,
            norm_ab=numpy.linalg.norm(b - a)) == expected
        checked += 1
    assert checked > 100


@pytest.mark.parametrize("shared", ["a==d", "b==c", "a==c", "b==d"])
def test_are_encroached_shared_endpoint_cases_match(shared):
    """The four early-exit tests — the ones insert_way hits constantly."""
    rng = random.Random(7)
    vmap = VECT.Vector_Map()
    for _ in range(200):
        a = numpy.array([rng.random(), rng.random()])
        b = numpy.array([rng.random(), rng.random()])
        c = numpy.array([rng.random(), rng.random()])
        d = numpy.array([rng.random(), rng.random()])
        if shared == "a==d":
            d = a.copy()
        elif shared == "b==c":
            c = b.copy()
        elif shared == "a==c":
            c = a.copy()
        else:
            d = b.copy()
        assert vmap.are_encroached(a, b, c, d) == \
            _are_encroached_reference(a, b, c, d)


def test_the_writers_f_string_spells_what_the_join_spelled():
    """``write_node_file`` swapped ``"{:.9f}".format(v)`` for ``f"{v:.9f}"``.

    Same call underneath (``format(v, '.9f')``) — held here over the value
    kinds the node dict actually carries, numpy scalars included, because
    a single differing digit is a differing ``.node`` file.
    """
    rng = random.Random(11)
    values = [0.0, -0.0, 1.0, 0.5, 1e-9, 5e-10, -1e-9, 1234.5678901234,
              1 / 3, 2 ** -20, 99999.9999999999]
    values += [rng.uniform(-200, 200) for _ in range(2000)]
    values += [rng.uniform(0, 1) for _ in range(2000)]
    for v in values:
        assert f"{v:.9f}" == "{:.9f}".format(v)
        nv = numpy.float64(v)
        assert f"{nv:.9f}" == "{:.9f}".format(nv) == f"{v:.9f}"
    for i in (0, 1, -1, 7, 1234567, 2 ** 40):
        assert f"{i}" == str(i)


def _built_map(rng_seed, fast):
    """A Vector_Map with crossing ways, built with the fast path on/off."""
    rng = random.Random(rng_seed)
    vmap = VECT.Vector_Map()
    if not fast:
        vmap.ebbox.fast_path = False
    for _ in range(120):
        n = rng.randint(2, 6)
        way = numpy.array(
            [[rng.random(), rng.random(), rng.random() * 100.0]
             for _ in range(n)])
        vmap.insert_way(way, rng.choice(["WATER", "SEA", "RUNWAY"]),
                        check=True)
    # a grid, so the random ways are cut in many places
    for k in range(1, 8):
        x = k / 8.0
        vmap.insert_way(numpy.array([[x, 0.0, 0.0], [x, 1.0, 0.0]]),
                        "DUMMY", check=True)
        vmap.insert_way(numpy.array([[0.0, x, 0.0], [1.0, x, 0.0]]),
                        "DUMMY", check=True)
    vmap.snap_to_grid(9)
    return vmap


def test_a_whole_vector_map_is_byte_identical_with_the_fast_path_off(
        tmp_path):
    """THE gate, in miniature: same .node and .poly bytes either way."""
    written = {}
    for fast in (True, False):
        vmap = _built_map(31337, fast)
        node = tmp_path / f"fast_{fast}.node"
        poly = tmp_path / f"fast_{fast}.poly"
        vmap.write_node_file(str(node))
        vmap.write_poly_file(str(poly))
        written[fast] = (node.read_bytes(), poly.read_bytes())
    assert written[True][0] == written[False][0], ".node bytes differ"
    assert written[True][1] == written[False][1], ".poly bytes differ"
    assert len(written[True][0]) > 1000, "the fixture built nothing"
