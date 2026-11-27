"""THE ROUTE PRICING'S WALKS ON THE WORK POOL (#2206; the pricing is
``routes.route_pairs``, RULINGS 2026-09-05ab).

``route_pairs`` walks two Dijkstras over the whole route graph from every
source it has not read back from an equal graph -- MEASURED KATL (#2206
lperf/lvec profiles): ~115 s of ``taxi.taxi_pair_routes``.  A source's row
is a function of the graph and the source alone, so the sources are handed
to the work pool (``airport/pool.py``) in chunks and each worker sends home
only the columns the source pairs with (its groups' members above it):

* :func:`rows` is THE reading -- one chunk of sources through both walks,
  each source's ``[(lengths, budgets), ...]`` at its columns.  The serial
  pricing and a worker both ask it, so the pooled answer is the serial
  answer by construction (the same floats: a Dijkstra row does not depend
  on which other sources share its call);
* :func:`walk_rows` maps the chunks, or reads them here when no pool
  answers (a budget of 1, fewer than :data:`MIN_WALKS` sources, a pool that
  dies) -- the same computation.

The graph's two CSR matrices cross to the workers once, through shared
memory (the pool's setup).  Nothing here decides anything, and no worker
count reaches a row or a report."""
from __future__ import annotations

import typing as _t

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from ..airport.pool import SharedArrays, WorkPool, attach, budget_bound

__all__ = ["MIN_WALKS", "MAX_WORKERS", "rows", "setup", "read", "walk_rows"]

#: Fewer sources than this are walked on one core: the workers must start
#: first (about a second each to import), and a small graph's walks are done
#: before they have.  A cost rule only -- the reading is the same.
MIN_WALKS = 2048

#: The most workers this reading takes: each holds two ``chunk x 2n`` rows
#: blocks (KATL: about 0.4 GB a worker).  A cost rule only.
MAX_WORKERS = 8

Cols = _t.Sequence[np.ndarray]
Row = list[tuple[np.ndarray, np.ndarray]]


def rows(m: csr_matrix, wb: csr_matrix, idx: _t.Sequence[int],
         cols: _t.Sequence[Cols]) -> list[Row]:
    """THE READING: per source of ``idx``, ``[(D[s, c], B[s, c]) for c in
    its cols]`` -- ``D`` the shortest length, ``B`` the least budget
    (``routes.route_pairs``)."""
    D = dijkstra(m, directed=True, indices=list(idx))
    B = dijkstra(wb, directed=True, indices=list(idx))
    return [[(D[i, c], B[i, c]) for c in cs] for i, cs in enumerate(cols)]


def _arrays(m: csr_matrix, wb: csr_matrix) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for name, g in (("m", m), ("wb", wb)):
        out[f"{name}.data"], out[f"{name}.indices"], out[f"{name}.indptr"] = \
            g.data, g.indices, g.indptr
        out[f"{name}.shape"] = np.asarray(g.shape, np.int64)
    return out


def setup(spec: _t.Mapping[str, tuple]) -> tuple[csr_matrix, csr_matrix]:
    """The pool's per-worker setup: the two matrices off shared memory
    (copied once: a worker's own writable arrays, the same values)."""
    a = attach(spec)

    def one(name: str) -> csr_matrix:
        shape = tuple(int(v) for v in a[f"{name}.shape"])
        return csr_matrix((a[f"{name}.data"].copy(), a[f"{name}.indices"].copy(),
                           a[f"{name}.indptr"].copy()), shape=shape)
    return one("m"), one("wb")


def read(state: tuple[csr_matrix, csr_matrix],
         task: tuple[_t.Sequence[int], _t.Sequence[Cols]]) -> list[Row]:
    """One task ``(sources, their cols)``: :func:`rows`."""
    return rows(state[0], state[1], *task)


def walk_rows(m: csr_matrix, wb: csr_matrix, walk: _t.Sequence[int],
              cols: _t.Mapping[int, Cols], chunk: int, *,
              workers: int | None = None,
              out: _t.Callable[[str], None] = print) -> dict[int, Row]:
    """``{s: rows(m, wb, [s], [cols[s]])[0] for s in walk}``, walked in
    chunks of ``chunk`` sources -- on the work pool when one answers
    (module doc), here otherwise.  ``workers`` pins the count (a twin)."""
    spans = [list(walk[c0:c0 + chunk]) for c0 in range(0, len(walk), chunk)]
    tasks = [(idx, [cols[s] for s in idx]) for idx in spans]
    got = None
    allowed, bound = budget_bound() if workers is None else (int(workers), "pinned")
    n = min(allowed, len(tasks), MAX_WORKERS)
    if n >= 2 and (workers is not None or len(walk) >= MIN_WALKS):
        if n < allowed:
            bound = "cap" if n == MAX_WORKERS else "tasks"
        try:
            shared = SharedArrays(_arrays(m, wb))
        except OSError as e:           # no shared memory: the same reading, here
            out(f"[pool] FELL BACK: the route graph does not cross to a worker "
                f"({type(e).__name__}: {e}) — constraints: route walks stay on one core")
        else:
            with shared, WorkPool(setup, (shared.spec,), workers=n, out=out,
                                  bound=bound) as pool:
                got = pool.try_map(read, tasks, what="constraints: route walks",
                                   unit="chunks")
                out(pool.line() + " — constraints: route walks")
    if got is None:
        got = [rows(m, wb, *t) for t in tasks]
    return {s: r for (idx, _c), rr in zip(tasks, got, strict=True)
            for s, r in zip(idx, rr, strict=True)}
