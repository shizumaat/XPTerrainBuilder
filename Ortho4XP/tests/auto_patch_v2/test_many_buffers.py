"""``geom.many_buffers.buffers`` (#2206): the threaded buffers are the
serial calls' own bytes, one per distinct distance."""
import numpy as np
import shapely

from auto_patch_v2.geom.many_buffers import buffers


def _network():
    rng = np.random.default_rng(7)
    pts = rng.uniform(0.0, 2000.0, (400, 2))
    return shapely.unary_union(shapely.linestrings(
        [[p, p + rng.uniform(-60.0, 60.0, 2)] for p in pts]))


def test_threaded_buffers_are_the_serial_bytes():
    net = _network()
    dists = [9.5, 12.25, 9.5, 20.0, 15.0]
    got = buffers(net, dists, lambda g: g if g.is_valid else g.buffer(0.0))
    assert sorted(got) == [9.5, 12.25, 15.0, 20.0]
    for d, g in got.items():
        assert shapely.to_wkb(g) == shapely.to_wkb(net.buffer(d))


def test_one_distance_reads_serially():
    net = _network()
    assert shapely.to_wkb(buffers(net, [11.0])[11.0]) == shapely.to_wkb(net.buffer(11.0))
    assert buffers(net, []) == {}
