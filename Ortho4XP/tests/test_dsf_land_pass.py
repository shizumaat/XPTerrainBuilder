"""The full_ortho land pass on arrays (``O4_DSF_Land_Pass``, issue #850).

Its bytes are guarded by the pinned-base A/B of ``test_dsf_texture_modes``
and the committed fixture of ``test_mesh_dsf_oracle``; here:

* ``DsfPointPools.slots`` answers what one ``slot`` call per point answers,
  rollover included;
* the sort helpers answer what ``numpy.argsort(kind="stable")`` and
  ``numpy.unique`` answer;
* the texture coordinates are ``O4_Geo_Utils.st_coord``'s, rounded;
* a full_ortho tile whose band pools roll over still builds, every land
  triangle drawn once.
"""
import copy
import queue
import random

import numpy

import O4_DSF_Land_Pass as LANDPASS
import O4_DSF_Pools as POOLS
import O4_DSF_Utils as DSF
import O4_Geo_Utils as GEO
import test_dsf_texture_modes as MODES

stub_elevation = MODES.stub_elevation


def _assert_slots_match(pools, bases):
    walked = copy.deepcopy(pools)
    expected = [walked.slot(base) for base in bases]
    (pool, position) = pools.slots(numpy.asarray(bases, dtype=numpy.int64))
    assert list(zip(pool.tolist(), position.tolist(), strict=True)) == expected
    assert pools.length == walked.length
    assert pools.plane == walked.plane
    assert pools.geometric == walked.geometric


def test_slots_match_slot_without_rollover():
    rng = random.Random(850)
    pools = POOLS.DsfPointPools(4, [7] * 4 + [9] * 4 + [7] * 4)
    for base in range(12):
        for _ in range(rng.randrange(5)):
            pools.slot(base)
    _assert_slots_match(pools, [rng.randrange(12) for _ in range(500)])


def test_slots_match_slot_through_rollover():
    rng = random.Random(2092)
    pools = POOLS.DsfPointPools(3, [7, 7, 7, 9, 9, 9], max_points=20)
    for _ in range(25):
        pools.slot(4)
    _assert_slots_match(pools, [rng.randrange(6) for _ in range(300)])
    assert len(pools) > 6


def test_slots_of_nothing():
    pools = POOLS.DsfPointPools(1, [7])
    (pool, position) = pools.slots([])
    assert len(pool) == len(position) == 0
    assert pools.length == [0]


def test_stable_order_and_first_seen():
    rng = numpy.random.default_rng(850)
    for key in (rng.integers(0, 40, 5000),
                rng.integers(-(1 << 62), 1 << 62, 3000),  # the argsort path
                numpy.zeros(1, dtype=numpy.int64)):
        order = LANDPASS._stable_order(key)
        assert order.tolist() == numpy.argsort(key, kind="stable").tolist()
        (first, label) = LANDPASS._first_seen(key)
        (_, ref_first, ref_label) = numpy.unique(
            key, return_index=True, return_inverse=True)
        assert first.tolist() == ref_first.tolist()
        assert label.tolist() == ref_label.ravel().tolist()


def test_st_words_are_st_coord_rounded():
    rng = random.Random(1990)
    (lons, lats, texture) = ([], [], [])
    for _ in range(4000):
        zoomlevel = rng.choice((16, 17, 18, 19))
        lat = rng.uniform(-60, 70)
        lon = rng.uniform(-179, 179)
        (til_x, til_y) = GEO.wgs84_to_orthogrid(lat, lon, zoomlevel)
        lons.append(lon)
        lats.append(lat)
        texture.append((til_x, til_y, zoomlevel))
    nodes = numpy.arange(len(lons))
    (s, t) = LANDPASS._st_words(nodes, numpy.array(texture), lons, lats)
    for n in range(len(lons)):
        (es, et) = GEO.st_coord(lats[n], lons[n], *texture[n], "BI")
        assert (int(s[n]), int(t[n])) == (int(round(es * 65535)),
                                          int(round(et * 65535)))


@MODES._DSFTOOL
def test_full_ortho_rollover_builds(tmp_path, monkeypatch, stub_elevation):
    side, lon0, lat0, step = 24, 10.001, 50.001, 0.05 / 24
    verts = [(lon0 + i * step, lat0 + j * step)
             for j in range(side) for i in range(side)]
    tris = []
    for j in range(side - 1):
        for i in range(side - 1):
            a = j * side + i + 1
            (b, c, d) = (a + 1, a + side + 1, a + side)
            tris.append((a, b, c, 0))
            tris.append((a, c, d, 0))
    build_dir = MODES._prepare_build_dir(tmp_path)
    MODES._write_mesh(build_dir, verts, tris)
    real_init = POOLS.DsfPointPools.__init__
    monkeypatch.setattr(
        POOLS.DsfPointPools, "__init__",
        lambda self, nbr, planes, max_points=None:
            real_init(self, nbr, planes, max_points=64))
    opened = []
    real_open = POOLS.DsfPointPools._open_overflow
    monkeypatch.setattr(
        POOLS.DsfPointPools, "_open_overflow",
        lambda self, full: opened.append(full) or real_open(self, full))

    assert DSF.build_dsf(MODES._make_tile(build_dir, "full_ortho"),
                         queue.Queue()) == 1

    assert opened, "no band pool rolled over: the fixture is too small"
    dump = MODES.DECODE.decode_dsf(MODES._emitted_dsf(build_dir))
    land = [p for p in dump.patches if p.terrain_path.startswith("terrain/")]
    assert {p.plane_count for p in land} == {7}
    assert sum(p.triangle_count for p in land) == len(tris)


def test_cliff_shade_unique_edges_is_unique_rows():
    import O4_Cliff_Shade as SHADE
    rng = numpy.random.default_rng(2096)
    for dtype in (numpy.int32, numpy.int64):
        edges = rng.integers(0, 3000, (20000, 2)).astype(dtype)
        edges.sort(axis=1)
        got = SHADE._unique_edges(edges, 3000)
        want = numpy.unique(edges, axis=0)
        assert got.dtype == want.dtype
        assert numpy.array_equal(got, want)
