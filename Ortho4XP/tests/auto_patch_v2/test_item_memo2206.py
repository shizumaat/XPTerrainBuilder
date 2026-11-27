"""#2206 lane lprefix (spec ``docs/specs/stage1-prefix-reuse-20261127.md``):
the item answers held across the build's prefix runs are the fresh
readings -- held by content, served for equal content and never for
another, and turned over per run (``geom/item_memo``)."""
from __future__ import annotations

import math
import random

import numpy as np
import shapely
from auto_patch_v2.airport import road_profile as rp
from auto_patch_v2.geom import item_memo as im
from auto_patch_v2.geom.proportions import _inscribed_width, inscribed_width_m
from auto_patch_v2.planar import ground_chords as GC
from shapely.geometry import LineString, Polygon


def test_a_memo_keeps_this_run_and_the_one_before():
    m = im.ItemMemo("test")
    calls = []
    m.get(("a",), lambda: calls.append("a") or 1)
    im.next_run()
    assert m.get(("a",), lambda: calls.append("a2") or 2) == 1     # the run before
    im.next_run()
    im.next_run()                                                   # two runs on
    assert m.get(("a",), lambda: calls.append("a3") or 3) == 3
    assert calls == ["a", "a3"]


def test_the_bulk_mouth_test_is_the_point_test():
    rnd = random.Random(3)
    polys = [Polygon([(x, y), (x + 5, y), (x + 5, y + 3), (x, y + 3)])
             for x, y in ((rnd.uniform(0, 100), rnd.uniform(0, 100)) for _ in range(30))]
    near = GC.near_any(polys, 0.5)
    pts = [(rnd.uniform(-5, 105), rnd.uniform(-5, 105)) for _ in range(2000)]
    pts += [tuple(p.exterior.coords[0]) for p in polys]             # on a contact
    assert list(near.many(pts)) == [near(p) for p in pts]


def _ground(xs, ys):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    return 5.0 + 1.5 * np.sin(xs / 7.0) + 0.02 * ys


def _parts(ring, ground):
    """``(chords, tss, lens, z_all)`` as ``follow_ground`` reads the ring
    (sample 2 m, floor 4 m)."""
    chords = list(zip(ring, ring[1:], strict=False))
    tss, lens, xs, ys = [], [], [], []
    for (ax, ay), (bx, by) in chords:
        d = math.hypot(bx - ax, by - ay)
        ts = np.linspace(0.0, 1.0, max(3, math.ceil(d / 2.0) + 1)) \
            if d >= 8.0 and d > 2.0 else np.array([0.0, 1.0])
        tss.append(ts)
        lens.append(d)
        xs.append(ax + (bx - ax) * ts)
        ys.append(ay + (by - ay) * ts)
    return chords, tss, lens, ground(np.concatenate(xs), np.concatenate(ys))


def test_a_held_ring_is_the_fresh_ring():
    ramp = GC.Ramp(0.05, 0.08, 0.25)
    contacts = [Polygon([(-1, -1), (2, -1), (2, 2), (-1, 2)])]
    ring = [(0.0, 0.0), (80.0, 0.0), (80.0, 30.0), (0.0, 30.0), (0.0, 0.0)]
    heads = GC._mouths(GC.near_any(contacts, 0.5), ring[:-1])
    fresh = GC._followed(ring, *_parts(ring, _ground), heads, 0.3, 4.0, ramp)
    for _ in range(2):                       # computed, then held
        assert GC.follow_ground(ring, _ground, 0.3, 2.0, 4.0,
                                GC.near_any(contacts, 0.5), ramp) == fresh

    def lower(xs, ys):
        return _ground(xs, ys) * 0.5
    want = GC._followed(ring, *_parts(ring, lower), heads, 0.3, 4.0, ramp)
    assert GC.follow_ground(ring, lower, 0.3, 2.0, 4.0,
                            GC.near_any(contacts, 0.5), ramp) == want


def test_a_held_width_is_the_fresh_width():
    poly = Polygon([(0, 0), (40, 0), (40, 6), (12, 6), (12, 30), (0, 30)])
    assert inscribed_width_m(poly) == _inscribed_width(poly, 0.01)
    assert inscribed_width_m(Polygon(poly.exterior.coords)) == _inscribed_width(poly, 0.01)
    big = shapely.affinity.scale(poly, 2.0, 2.0)
    assert inscribed_width_m(big) == _inscribed_width(big, 0.01) != inscribed_width_m(poly)


def _profiles(z0: float):
    xy = np.array([(0.0, 0.0), (50.0, 0.0), (100.0, 10.0)])
    s = np.array([0.0, 50.0, 101.0])
    w = rp.Way(rp.OSM, "osm:1", xy, s, s * 0.0 + z0, s * 0.01 + z0)
    v = rp.Way(rp.ROUTE, "route:2", xy + 3.0, s, s * 0.0 + z0, s * 0.02 + z0)
    return rp.RoadProfiles(0.05, 10.0, 3.5, 20.0, (w, v)), w, v


def _fresh(prof, p, through):
    near = [prof.ways[i] for i in prof.ways_near(shapely.Point(p))]
    return prof._answer(p, 1.0, through, near, through + [(w, prof.radius_m) for w in near])


def test_a_held_answer_is_the_fresh_answer_with_this_runs_way():
    rnd = random.Random(5)
    pts = [(rnd.uniform(-10, 110), rnd.uniform(-15, 25)) for _ in range(300)]
    a, wa, va = _profiles(10.0)
    fresh = [_fresh(a, p, [(va, 6.0)]) for p in pts]
    first = [a.answer(p, 1.0, [(va, 6.0)]) for p in pts]
    b, wb, vb = _profiles(10.0)                      # another run, equal content
    again = [b.answer(p, 1.0, [(vb, 6.0)]) for p in pts]
    for f, x, y in zip(fresh, first, again, strict=True):
        assert (x.z, x.kind, x.ref, x.lateral_m, x.s, x.t) == \
            (y.z, y.kind, y.ref, y.lateral_m, y.s, y.t) == f[1:]
        assert x.way is None or any(x.way is w for w in (wa, va))
        assert y.way is None or any(y.way is w for w in (wb, vb))   # this run's way
    c, _wc, vc = _profiles(11.0)                      # other content: its own answers
    assert [c.answer(p, 1.0, [(vc, 6.0)]).z for p in pts] == \
        [_fresh(c, p, [(vc, 6.0)])[1] for p in pts]


def test_road_barriers_skip_only_roads_that_miss_the_part():
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar import terrain_edge as te
    law = Law.for_airport("SYNT")
    part = Polygon([(0, 0), (200, 0), (200, 60), (0, 60)])
    seed = Polygon([(0, -40), (200, -40), (200, -5), (0, -5)])
    crest = Polygon([(0, 50), (200, 50), (200, 58), (0, 58)])
    near = [LineString([(0, 62), (200, 62)]), (LineString([(10, 59), (190, 63)]), 3.0)]
    far = [(LineString([(0, 400), (200, 400)]), 4.0), LineString([(-90, 61), (-60, 61)])]
    got = te._road_barriers(part, seed, crest, [far[0], near[0], far[1], near[1]], law)
    want = te._road_barriers(part, seed, crest, near, law)
    assert got[2] == want[2] > 0
    assert [g.wkb for g in got[0]] == [g.wkb for g in want[0]]
    assert [g.wkb for g in got[1]] == [g.wkb for g in want[1]]
