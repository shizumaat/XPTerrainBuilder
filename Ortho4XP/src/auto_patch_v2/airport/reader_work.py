"""THE PACK READERS BESIDE EACH OTHER — the classification-free readers of
the planar stage as work-pool tasks (issue #362; owner RULINGS 2026-10-04x
(4)).

``planar/pack_reads`` reads the pack five times, each reader a pure function
of the airport's DEM, frame, mapped ways and DSF objects, the pack's placed
objects, the parsed resources and the law.  The readers named in
:data:`READERS` share NO at-grade state with the door wells and the sunken
roads: what they write on the build's ``ResourceCache`` is the parse memos
alone (``_geom`` / ``_comps`` / ``_range`` / ``_bounds`` — pure in the file),
and the one process-wide thing they touch is ``frame_entry``'s fallback-rung
count.  So they run in workers while the build's own process reads the doors
and the roads — the tunnel corridors + thin plates as one task, the wall
corridors as ONE TASK PER ANCHOR FAMILY (``wall_corridors.read_family``
reads nothing of another family; the intake is built here, in ``objects``
order, and ``wall_corridors.assemble`` takes the answers in sorted family
order, which is where the corridors' ``@k`` and the order of every refusal
line come from):

* the worker is handed the placed objects, the law, the airport WITHOUT its
  partition / groups / clusters (:class:`Stripped` — a reader that reached
  for one would trip, not read ``None``) and the DEM through
  ``dem_shared`` (the composed tiles in shared memory, never pickled);
* it parses the resources it needs itself, into a cache built as the
  build's is (same thickness, same input quantum) and seeded with the
  build's own per-resource extents, so its pre-screens open no file the
  serial pre-screen does not;
* it returns the task's records and stats, and the fallback rungs its
  unions took, which the build's process charges to its own count.

Nothing here decides anything.  With no pool, a pool that dies, inputs
that do not pickle or a reader that trips (:class:`ColdTile`,
:class:`StrippedField`), :meth:`Ahead.collect` hands back nothing for that
reader and ``pack_reads`` reads it on one core — the same computation.
"""
from __future__ import annotations

import dataclasses as _dc
import pickle
import time
import typing as _t

from . import frame_entry as _fe
from . import obj8 as _obj8
from .dem_shared import ColdTile, revive, share
from .pool import WorkPool, budget
from .thin_plates import read_plates
from .tunnel_objects import read_corridors
from .wall_corridors import assemble, read_family, wall_families, wall_reader

__all__ = ["READERS", "WALLS", "TUNNELS", "MIN_OBJECTS", "MAX_WORKERS", "Ahead", "Stripped", "StrippedField",
           "ReadWorker", "setup", "read", "begin"]

#: the wall corridors: ``(records, stats)``; a task is ``(WALLS, family
#: key, the members' positions in objects)``
WALLS = "walls"
#: the tunnel corridors, then the thin plates that skip the resources the
#: corridors admitted: ``(corridors, stats, plates, plate stats)``
TUNNELS = "tunnels"
READERS = (WALLS, TUNNELS)

#: A pack of fewer placed objects than this is read on one core: a worker
#: must parse its own copy of the resources, and on a small pack the readers
#: are done before it has (measured, the readers' own clock: HECA, 3,199
#: objects, 6.2 s on one core against 8.5 s beside workers; OTHH, 36,019,
#: 173.5 s against 94.0 s).  A cost rule only — the reading is the same.
MIN_OBJECTS = 10_000

#: The most workers the readers take, whatever the budget.  Every worker
#: parses its own copy of the resources its tasks read (~1.2 GB each at
#: OTHH), and while the door wells and the sunken roads are read by the
#: build's own process THEY are the stage's wall: past the few workers that
#: finish the wall families first, more only take the machine from them
#: (measured at OTHH on a shared machine, readers' own clock: 2 workers
#: 95.5 s, 4 workers 91.5 s, 18 workers 140.5 s — the parent's two readers
#: 93 / 88 / 127 s of it).  A cost rule only — the reading is the same.
MAX_WORKERS = 4

#: the airport fields no reader here opens, and that are megabytes to ship
_STRIPPED = ("partition", "groups", "clusters")


class StrippedField(LookupError):
    """A reader opened an airport field its worker was not handed."""


class Stripped:
    """What stands in a worker's airport for a field of :data:`_STRIPPED`:
    any use of it raises :class:`StrippedField`."""

    def __init__(self, name: str) -> None:
        object.__setattr__(self, "_name", name)

    def __reduce__(self):
        return (Stripped, (object.__getattribute__(self, "_name"),))

    def _trip(self, *_a, **_k):
        raise StrippedField(f"airport.{object.__getattribute__(self, '_name')} "
                            f"is not shipped to a pack-reader worker")

    def __getattr__(self, _name):
        self._trip()

    __iter__ = __len__ = __bool__ = __getitem__ = __contains__ = __call__ = _trip


@_dc.dataclass
class ReadWorker:
    """One worker's state: the readers' inputs, and its own parse."""

    airport: _t.Any
    objects: list
    law: _t.Any
    cache: _obj8.ResourceCache
    walls: _t.Any = None               # ``wall_corridors.WallReader``, lazily


def setup(airport, dem_token, objects, law, thickness_m: float, quantum_m: float,
          derived: dict, dump_dir: str) -> ReadWorker:
    """The pool's per-worker setup."""
    cache = _obj8.ResourceCache(thickness_m, quantum_m)
    cache.restore_derived(derived)
    _fe.set_offender_dump_dir(dump_dir)
    return ReadWorker(_dc.replace(airport, dem=revive(dem_token)), objects, law, cache)


def read(state: ReadWorker, task: tuple) -> tuple:
    """One task — ``(TUNNELS,)`` or ``(WALLS, family key, member positions)``
    — as ``("ok", reading, fallback rungs)``, or ``("serial", why)`` when it
    reached for something a worker does not hold (module doc): the build's
    process then makes that reader's reading itself."""
    a, oo, cache, law = state.airport, state.objects, state.cache, state.law
    _fe.reset_rung_counts()
    try:
        if task[0] == WALLS:
            if state.walls is None:
                state.walls = wall_reader(a, cache, law)
            got: tuple = read_family(state.walls, task[1], [oo[k] for k in task[2]])
        else:
            corridors, tstats = read_corridors(a, oo, cache, law)
            got = (corridors, tstats,
                   *read_plates(a, oo, cache, law, {c.resource for c in corridors}))
    except (ColdTile, StrippedField) as e:
        return ("serial", f"{type(e).__name__}: {e}")
    return ("ok", got, _fe.rung_counts())


class Ahead:
    """Readers a pool is working on.  :meth:`collect` waits (bounded, as
    every pool wait is), releases the workers and the shared DEM, charges
    the workers' fallback rungs here, says what the pool did (one
    ``[pool]`` line, so a stage read on one core cannot pass for a pooled
    one) and returns ``{reader: reading}`` — WITHOUT the readers the
    build's process must read itself."""

    def __init__(self, pool: WorkPool, shared, pending, tasks: list,
                 placements: int | None, out: _t.Callable[[str], None]) -> None:
        self._pool, self._shared, self._pending = pool, shared, pending
        self._tasks, self._placements, self._out = tasks, placements, out
        self._t0 = time.perf_counter()
        self.report: dict = {}

    def collect(self) -> dict:
        try:
            got = self._pending.collect()
        finally:
            self.close()
        rows: dict[str, list] = {}
        tripped: dict[str, str] = {}
        for task, row in zip(self._tasks, got or ()):
            if row[0] != "ok":
                tripped.setdefault(task[0], row[1])
                continue
            rows.setdefault(task[0], []).append(row[1])
            _fe.add_rung_counts(row[2])
        for kind, why in tripped.items():       # one tripped task: the whole reader
            self._out(f"[pool] pack reader '{kind}' is read on one core: {why}")
        out: dict = {}
        if got is not None:
            if TUNNELS in rows and TUNNELS not in tripped:
                out[TUNNELS] = rows[TUNNELS][0]
            if self._placements is not None and WALLS not in tripped:
                # the tasks are in sorted family order, and so are the answers
                walls, wstats = assemble(self._placements, rows.get(WALLS, ()))
                wstats.read_s = time.perf_counter() - self._t0
                out[WALLS] = (walls, wstats)
        self.report = dict(self._pool.report(), readers=sorted(out),
                           line=self._pool.line() + f" — pack readers beside the door "
                           f"wells: {', '.join(sorted(out)) or 'none'}")
        self._out(self.report["line"])
        return out

    def close(self) -> None:
        self._pool.close()
        if self._shared is not None:
            self._shared.close()
            self._shared = None


def begin(airport, objects: _t.Sequence, cache: _obj8.ResourceCache, law,
          kinds: _t.Sequence[str] = READERS, *, workers: int | None = None,
          out: _t.Callable[[str], None] = print) -> Ahead | None:
    """Start ``kinds`` in workers and return at once; ``None`` when no pool
    will answer (a budget of 1, a pack under :data:`MIN_OBJECTS`, inputs
    that do not pickle, no shared memory) — said through ``out`` unless it
    is simply the budget or the pack's size."""
    kinds = tuple(kinds)
    if (budget() if workers is None else int(workers)) < 2 or len(objects) < MIN_OBJECTS:
        return None
    tasks: list[tuple] = []
    weights: list[float] = []
    placements = None
    if WALLS in kinds:
        # THE INTAKE, here: ``objects`` order decides each family's members
        placements, fams = wall_families(objects, cache, law)
        tasks += [(WALLS, fk, ks) for fk, ks in fams]
        weights += [float(len(ks)) for _fk, ks in fams]
    if TUNNELS in kinds:
        tasks.append((TUNNELS,))
        weights.append(max(weights, default=0.0) + 1.0)     # one long task: first
    n = min(budget() if workers is None else int(workers), len(tasks), MAX_WORKERS)
    if n < 2:
        return None
    derived = {k: v for k, v in cache.derived_state().items() if k in ("range", "bounds")}
    shared = None
    try:
        lite = _dc.replace(airport, dem=None, **{f: Stripped(f) for f in _STRIPPED})
        shared, token = share(airport.dem)
        args = (lite, token, list(objects), law, cache.thickness_m,
                cache.input_quantum_m, derived, _fe.offender_dump_dir())
        pickle.dumps(args, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:                 # a twin's closure, no /dev/shm, …
        if shared is not None:
            shared.close()
        out(f"[pool] the pack readers stay on one core: their inputs do not "
            f"cross to a worker ({type(e).__name__}: {e})")
        return None
    pool = WorkPool(setup, args, workers=n, out=out)
    pending = pool.begin(read, tasks, weights=weights, what="pack readers", unit="tasks")
    if pending is None:
        pool.close()
        if shared is not None:
            shared.close()
        return None
    return Ahead(pool, shared, pending, tasks, placements, out)
