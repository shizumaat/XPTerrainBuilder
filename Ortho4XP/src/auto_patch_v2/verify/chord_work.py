"""THE APRON CHORDS THAT LEAVE THEIR FACE — the verify stage's one pooled
reading (issue #412; RULINGS 2026-09-05ae(1) is the law it reads).

``within_shape`` asks, of every apron ring, which of its NON-ADJACENT
chords leave the face (``constraints.geometry.face_cover`` at the snap
tolerance).  That is every vertex pair of the ring through one
``covered_by`` — at HECA 285 rings and most of the verify stage's wall.
Each chord's answer is a function of the ring, its holes, the tolerance and
the minimum spacing and of nothing else, so the rows of a ring are handed
to the work pool (``airport/pool.py``) in chunks and put back together in
ring order:

* :func:`rows_outside` is THE reading — the chords starting at rows
  ``[i0, i1)`` of one ring.  The serial reader (:func:`chords_outside`) asks
  it for the whole ring; a worker (:func:`read`) asks it for one chunk.
  One spelling, so the pooled answer is the serial answer by construction.
  It asks the generator's own sound pre-screen first
  (``constraints.geometry.chord_midpoints_hit``, as ``constraints/apron.py``
  does): a chord whose midpoint misses the cover is not covered, and at
  HECA that settles 1.42 M of the 1.72 M chords in 0.1 s;
* :func:`outside_ahead` cuts every ring into chunks of about
  :data:`CHUNK_CHORDS` chords, maps them and returns each ring's chords in
  the order the serial loop lists them — or ``None`` when no pool answers
  (a budget of 1, a population under :data:`MIN_CHORDS`, a pool that
  dies), and the caller reads the rings itself: the same computation.

A worker reads the rings and their holes once, from shared memory (the
pool's setup), and builds each ring's cover the first time a chunk of it
arrives.  Nothing
here decides anything, and no worker count reaches a row or a report.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..airport.pool import WorkPool, budget_bound, share_object, shared_object
from ..constraints.geometry import chord_midpoints_hit, chords_covered, face_cover

XY = tuple[float, float]
#: one ring and its hole rings
Face = tuple[_t.Sequence[XY], _t.Sequence[_t.Sequence[XY]]]

__all__ = ["Face", "MIN_CHORDS", "CHUNK_CHORDS", "MAX_WORKERS", "ChordWorker",
           "rows_outside", "chords_outside", "ring_chords", "chunks", "setup",
           "read", "outside_ahead"]

#: A patch whose apron rings hold fewer chords than this between them is
#: read on one core: the workers must start first, and under about 130,000
#: chords the rings are read before they have (measured over subsets of
#: three airports' rings, one core against 8 workers: 51,000 chords 0.26 s
#: against 0.68 s; 102,000 0.46 / 0.69; 134,000 1.12 / 0.99; 204,000 1.24 /
#: 0.82; 268,000 3.03 / 1.36; 408,000 2.04 / 0.86).  Set above the crossing:
#: a build's workers start slower than a tool's.  A cost rule only — the
#: reading is the same.
MIN_CHORDS = 250_000

#: chords per task: small enough that the largest ring (HECA: 1,563
#: vertices, 1.22 M chords) is spread over every worker, large enough that
#: a task is not its own pickling
CHUNK_CHORDS = 40_000

#: The most workers this reading takes, whatever the budget: past 8 the
#: seconds are the workers' start and more of them give nothing back.
#: Measured, the reading's own clock in seconds and the peak resident
#: memory of the process and its workers — HECA (285 rings, 1.72 M chords):
#: 1 worker 4.30 / 0.5 GB; 2 2.78 / 0.5; 4 1.77 / 0.6; 8 1.29 / 1.0; 12 1.25
#: / 1.4; 18 1.32 / 1.9.  OTHH (117 rings, 0.49 M): 4.76, 2.86, 2.05, 1.84,
#: 1.85, 1.97.  KCLT (148 rings, 0.45 M): 4.55, 2.77, 1.82, 1.47, 1.50, 1.62.
#: A cost rule only; it reads ``cap`` as the pool's deciding bound.
MAX_WORKERS = 8


def ring_chords(n: int) -> int:
    """How many non-adjacent chords a ring of ``n`` vertices has."""
    return n * (n - 3) // 2 if n > 3 else 0


def rows_outside(cover, xy: _t.Sequence[XY], min_d: float,
                 i0: int, i1: int) -> list[tuple[int, int]]:
    """The index pairs ``(i, j)``, ``i0 <= i < i1`` and ``j >= i + 2``, of
    the ring's non-adjacent chords at least ``min_d`` long that ``cover``
    does NOT cover — in ``(i, j)`` order.  ONE ``covered_by`` over the
    chunk's chords."""
    n = len(xy)
    ii: list[int] = []
    jj: list[int] = []
    for i in range(i0, i1):
        xa, ya = xy[i]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            xb, yb = xy[j]
            if math.hypot(xa - xb, ya - yb) >= min_d:
                ii.append(i)
                jj.append(j)
    if not ii:
        return []
    pts = np.asarray(xy, float)
    seg = np.stack([pts[ii], pts[jj]], axis=1)
    # the SOUND pre-screen first (``chord_midpoints_hit``: a chord whose
    # midpoint misses the cover is not covered); the full predicate judges
    # the survivors alone
    live = np.flatnonzero(chord_midpoints_hit(cover, seg))
    inside = np.zeros(len(seg), dtype=bool)
    inside[live] = chords_covered(cover, seg[live])
    return [(i, j) for i, j, k in zip(ii, jj, inside.tolist()) if not k]


def chords_outside(xy: _t.Sequence[XY], holes: _t.Sequence[_t.Sequence[XY]],
                   tol_m: float, min_d: float) -> list[tuple[int, int]]:
    """Every chord of one ring that leaves its face — the serial reading;
    none for a degenerate face (``face_cover`` is ``None``)."""
    cover = face_cover(xy, holes, tol_m)
    if cover is None:
        return []
    return rows_outside(cover, xy, min_d, 0, len(xy))


def chunks(n: int, size: int) -> list[tuple[int, int, int]]:
    """A ring of ``n`` vertices as ``(i0, i1, chords)`` row ranges of about
    ``size`` chords each, covering ``[0, n)`` in order (``chords`` counts
    every ``j >= i + 2``: the weight, never the answer)."""
    out: list[tuple[int, int, int]] = []
    i0 = held = 0
    for i in range(n):
        held += max(0, n - i - 2)
        if held >= size:
            out.append((i0, i + 1, held))
            i0, held = i + 1, 0
    if i0 < n:
        out.append((i0, n, held))
    return out


class ChordWorker:
    """One worker's state: the rings, and the covers it has built."""

    def __init__(self, faces: _t.Sequence[Face], tol_m: float, min_d: float) -> None:
        self.faces, self.tol_m, self.min_d = faces, tol_m, min_d
        self._covers: dict[int, object] = {}

    def cover(self, k: int):
        if k not in self._covers:
            self._covers[k] = face_cover(*self.faces[k], self.tol_m)
        return self._covers[k]


def setup(spec: _t.Mapping[str, tuple], tol_m: float, min_d: float) -> ChordWorker:
    """The pool's per-worker setup: the rings come through shared memory
    (``pool.share_object``) — pickled into every worker's start-up pipe
    they made the workers start one after the other."""
    return ChordWorker(shared_object(spec), tol_m, min_d)


def read(state: ChordWorker, task: tuple[int, int, int]) -> np.ndarray:
    """One task ``(ring, i0, i1)``: :func:`rows_outside` of that chunk, as
    an ``(m, 2)`` index array (HECA sends 1.56 M pairs home: an array
    crosses the pipe as one buffer, a list of tuples one object at a time)."""
    k, i0, i1 = task
    cover = state.cover(k)
    rows = [] if cover is None else rows_outside(cover, state.faces[k][0],
                                                 state.min_d, i0, i1)
    return np.asarray(rows, dtype=np.int32).reshape(-1, 2)


def outside_ahead(faces: _t.Sequence[Face], tol_m: float, min_d: float, *,
                  workers: int | None = None,
                  out: _t.Callable[[str], None] = print
                  ) -> list[list[tuple[int, int]]] | None:
    """``[chords_outside(*face, tol_m, min_d) for face in faces]`` from the
    work pool, or ``None`` when the caller is to read them itself (module
    doc).  ``workers`` pins the count (a twin, a tool arm)."""
    total = sum(ring_chords(len(xy)) for xy, _holes in faces)
    allowed, bound = budget_bound() if workers is None else (int(workers), "pinned")
    if allowed < 2 or total < MIN_CHORDS:
        return None
    tasks: list[tuple[int, int, int]] = []
    weights: list[float] = []
    for k, (xy, _holes) in enumerate(faces):
        for i0, i1, held in chunks(len(xy), CHUNK_CHORDS):
            tasks.append((k, i0, i1))
            weights.append(float(held))
    n = min(allowed, len(tasks), MAX_WORKERS)
    if n < allowed:                    # this module's own bounds decided
        bound = "cap" if n == MAX_WORKERS else "tasks"
    if n < 2:
        return None
    try:
        shared = share_object([(tuple(xy), [tuple(h) for h in holes])
                               for xy, holes in faces])
    except Exception as e:             # no shared memory: the same reading, here
        out(f"[pool] the apron chords stay on one core: their rings do not "
            f"cross to a worker ({type(e).__name__}: {e})")
        return None
    with shared, WorkPool(setup, (shared.spec, tol_m, min_d), workers=n, out=out,
                          bound=bound) as pool:
        got = pool.try_map(read, tasks, weights=weights,
                           what="verify: apron chords", unit="chunks")
        out(pool.line() + " — verify: apron chords")
    if got is None:
        return None
    merged: list[list[tuple[int, int]]] = [[] for _ in faces]
    for (k, _i0, _i1), rows in zip(tasks, got):
        merged[k].extend(map(tuple, rows.tolist()))
    return merged
