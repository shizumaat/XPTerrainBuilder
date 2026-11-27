"""The DSF point pools of one tile, with rollover at the 16-bit limit.

A DSF triangle names each of its points as ``(pool, index)`` and both are
16-bit words, so a pool holds at most 65,536 points.  The writer mirrors each
geometric quadtree pool once per texturing band and copies a node into a band
pool once per terrain that uses it, so a band pool can outgrow its geometric
pool (a 50,000-node bucket touched by several terrains, or a bucket held at
``QUAD_MAX_LEVEL``).  :meth:`DsfPointPools.slot` therefore opens an overflow
pool -- same plane count, same scale/offset (its geometric pool) -- when the
current one is full, instead of writing an index that does not fit (#2092).
A tile that never fills a pool gets exactly the pools it always had.
"""
import array

import numpy

__all__ = ["DsfPointPools"]


class DsfPointPools:
    """Band pools ``base = idx_pool + band * geometric_nbr`` plus overflow.

    ``points[k]`` is pool ``k``'s node-major ``array("H")``, ``length[k]`` its
    point count, ``plane[k]`` its plane count, ``geometric[k]`` the geometric
    pool whose scale/offset it uses.  Pools ``k >= len(planes)`` are overflow
    pools, appended in the order they were opened.
    """

    # A point index (and a pool index) is an unsigned 16-bit word in every
    # DSF triangle command.
    MAX_POINTS = 1 << 16

    def __init__(self, geometric_nbr, planes, max_points=None):
        self.max_points = self.MAX_POINTS if max_points is None else max_points
        self.points = [array.array("H") for _ in planes]
        self.length = [0] * len(planes)
        self.plane = [int(p) for p in planes]
        self.geometric = [k % geometric_nbr for k in range(len(planes))]
        self._current = {}

    def __len__(self):
        return len(self.points)

    def slot(self, base):
        """``(pool, position)`` for one new point of band pool ``base``.

        The caller extends ``points[pool]`` with the point's ``plane[pool]``
        words.  A full pool hands over to a fresh overflow pool.
        """
        pool = self._current.get(base, base)
        if self.length[pool] >= self.max_points:
            pool = self._open_overflow(pool)
            self._current[base] = pool
        position = self.length[pool]
        self.length[pool] += 1
        return (pool, position)

    def slots(self, bases):
        """``(pools, positions)``: :meth:`slot` of each band pool of
        ``bases`` in turn, as int64 arrays -- the same answers.  When no
        band pool fills up, one count per band pool stands for the calls
        (#850); otherwise each point takes :meth:`slot` in order."""
        bases = numpy.asarray(bases, dtype=numpy.int64)
        (band, inverse, counts) = numpy.unique(
            bases, return_inverse=True, return_counts=True)
        current = [self._current.get(base, base) for base in band.tolist()]
        start = [self.length[pool] for pool in current]
        if any(first + count > self.max_points
               for (first, count) in zip(start, counts.tolist(), strict=True)):
            answers = numpy.array([self.slot(base) for base in bases.tolist()],
                                  dtype=numpy.int64).reshape(-1, 2)
            return (answers[:, 0], answers[:, 1])
        order = numpy.argsort(inverse, kind="stable")
        rank = numpy.empty(len(bases), dtype=numpy.int64)
        rank[order] = (numpy.arange(len(bases))
                       - numpy.repeat(numpy.cumsum(counts) - counts, counts))
        for (pool, first, count) in zip(current, start, counts.tolist(),
                                       strict=True):
            self.length[pool] = first + count
        return (numpy.asarray(current, dtype=numpy.int64)[inverse],
                numpy.asarray(start, dtype=numpy.int64)[inverse] + rank)

    def _open_overflow(self, full):
        if len(self.points) >= self.MAX_POINTS:
            raise OverflowError("DSF needs more than 65,536 point pools")
        self.points.append(array.array("H"))
        self.length.append(0)
        self.plane.append(self.plane[full])
        self.geometric.append(self.geometric[full])
        return len(self.points) - 1
