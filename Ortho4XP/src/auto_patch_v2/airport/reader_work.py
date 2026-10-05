"""THE PACK READERS BESIDE EACH OTHER — the classification-free readers of
the planar stage as work-pool tasks (issue #362; owner RULINGS 2026-10-04x
(4)).

``planar/pack_reads`` reads the pack five times, each reader a pure function
of the airport's DEM, frame, mapped ways and DSF objects, the pack's placed
objects, the parsed resources and the law.  Here they are tasks, and every
reader's answers are put together in the order one loop met them:

* the tunnel corridors + thin plates: ONE task;
* the wall corridors: one task per ANCHOR FAMILY (``wall_family.
  read_family`` reads nothing of another family; the intake is built here,
  in ``objects`` order, and ``wall_family.assemble`` takes the answers
  in sorted family order, which is where the corridors' ``@k`` and the
  order of every refusal line come from);
* the sunken roads: one task per anchor family, the same way
  (``sunken_roads.road_families`` / ``read_family`` / ``assemble``);
* the door wells, in two steps.  The sill-witness SWEEP is per placement:
  the build's own process screens the placements (it holds every extent)
  and the screened ones go out :data:`WITS_CHUNK` to a task, first, beside
  the tunnels.  Then one task per anchor FAMILY — handed its witness rows,
  and of every other family's the one thing it reads: which components of
  its members' resources are a sill witness anywhere — at the head of the
  queue, the wall and the road families behind them (the two largest door
  families are the longest tasks of the stage).

What a reader leaves on the build's ``ResourceCache``:

* the wall corridors and the tunnels: the parse memos alone (``_geom`` /
  ``_comps`` / ``_range`` / ``_bounds`` — pure in the file);
* the door wells and the sunken roads: the AT-GRADE read — ``cache.grade``
  and the three memos the basin pass reads after them.  Each of their tasks
  returns its ``grade_ledger.Ledger`` and :meth:`Ahead.settle` replays the
  ledgers on the build's cache in the order one core reads (the doors'
  families, then the roads'), so the stats, the memos and every later
  charge are what one core leaves;
* the one process-wide thing: ``frame_entry``'s fallback-rung count.  ONE
  RULE: a rung is charged to the build's count exactly where a reading it
  belongs to is TAKEN.  :func:`read` hands a task's rungs over in its row
  and leaves its worker's count at zero at every exit, so the pool itself
  brings none home; :class:`Ahead` charges a row's rungs only when its
  reader's pooled reading is the one used — at :meth:`Ahead.collect` for
  the walls and the tunnels, at a successful :meth:`Ahead.settle` for the
  at-grade readers, whose entries' rungs go with the entry's first charge
  (``grade_ledger.replay``).  A reader the build re-reads (one tripped
  family, a refused replay) counts its own rungs there and its rows' are
  dropped: none twice, none lost.

A worker is handed the placed objects, the law, the airport WITHOUT its
partition / groups / clusters (:class:`Stripped` — a reader that reached for
one would trip, not read ``None``) and the DEM through ``dem_shared`` (the
composed tiles in shared memory, never pickled); it parses the resources it
needs itself, into a cache built as the build's is (same thickness, same
input quantum) and seeded with the build's own per-resource extents, so its
pre-screens open no file the serial pre-screen does not.

Nothing here decides anything.  With no pool, a pool that dies, inputs
that do not pickle, a reader that trips (:class:`ColdTile`,
:class:`StrippedField`) or an at-grade read that cannot be replayed
(``grade_ledger.Unreplayable``), that reader is handed back unread and
``pack_reads`` reads it on one core — the same computation.
"""
from __future__ import annotations

import dataclasses as _dc
import pickle
import time
import typing as _t

from . import door_wells as _dw
from . import frame_entry as _fe
from . import grade_ledger as _gl
from . import obj8 as _obj8
from . import sunken_roads as _sr
from .dem_shared import ColdTile, revive, share
from .pool import WorkPool, budget
from .thin_plates import read_plates
from .tunnel_objects import read_corridors
from .wall_family import assemble, read_family, wall_families, wall_reader

__all__ = ["READERS", "WALLS", "TUNNELS", "DOORS", "ROADS", "WITS", "WITS_CHUNK",
           "MIN_OBJECTS", "MAX_WORKERS",
           "Ahead", "Stripped", "StrippedField", "ReadWorker", "setup", "read", "begin"]

#: the wall corridors: ``(records, stats)``; a task is ``(WALLS, family
#: key, the members' positions in objects)``
WALLS = "walls"
#: the tunnel corridors, then the thin plates that skip the resources the
#: corridors admitted: ``(corridors, stats, plates, plate stats)``
TUNNELS = "tunnels"
#: the door wells: ``(wells, stats)``; a task is ``(DOORS, the family's
#: witness rows as (position in objects, witness, component index), the
#: members' positions, {resource: the indices of its witness components})``
DOORS = "doors"
#: the sunken roads: ``(roads, stats)``; a task is ``(ROADS, the members'
#: positions in objects)``
ROADS = "roads"
READERS = (WALLS, TUNNELS, DOORS, ROADS)
#: the door wells' sweep: ``(DoorStats of the chunk, [(position in objects,
#: witness, component index), …])``; a task is ``(WITS, the screened
#: placements' positions)``
WITS = "wits"
#: screened placements per sweep task (OTHH: 371 screened, 0.03-0.1 s each)
WITS_CHUNK = 8
#: the readers of the at-grade read (module doc)
_AT_GRADE = (DOORS, ROADS)

#: A pack of fewer placed objects than this is read on one core: a worker
#: must parse its own copy of the resources, and on a small pack the readers
#: are done before it has (measured, the readers' own clock: HECA, 3,199
#: objects, 6.2 s on one core against 8.5 s beside workers; OTHH, 36,019,
#: 173.5 s against 94.0 s).  A cost rule only — the reading is the same.
MIN_OBJECTS = 10_000

#: The most workers the readers take, whatever the budget.  Every worker
#: parses its own copy of the resources its tasks read (~1.0-1.5 GB each at
#: OTHH) and makes its own copy of the at-grade entries its tasks share
#: with another worker's, so the work grows with the workers (user CPU 256 s
#: on one core, 375 s on 8, 478 s on 18) while the build's own process
#: still makes the intakes and the door screen: past 8, more take memory
#: and the machine and give nothing back.  Measured at OTHH on a shared
#: machine — all five readers' clock, then the peak resident memory of the
#: build + its workers.  With the door sweep in the build's process: 1
#: worker 189 s; 2 124 s / 8.7 GB; 4 65-69 s / 10.5 GB; 8 49-54 s /
#: 14.4 GB; 12 49 s; 18 56 s / 23.2 GB.  With the sweep on the pool: 4
#: 63.7 s; 8 45.1-47.9 s.  A cost rule only — the reading is the same.
MAX_WORKERS = 8

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
    walls: _t.Any = None               # ``wall_family.WallReader``, lazily
    roads: _t.Any = None               # ``sunken_roads.RoadReader``, lazily
    #: the sweep's per-component footprints and ``{resource: {id(component):
    #: its index}}`` — both live as long as this worker's parse
    wit_memo: dict = _dc.field(default_factory=dict)
    comp_index: dict = _dc.field(default_factory=dict)


def setup(airport, dem_token, objects, law, thickness_m: float, quantum_m: float,
          derived: dict, dump_dir: str) -> ReadWorker:
    """The pool's per-worker setup."""
    cache = _obj8.ResourceCache(thickness_m, quantum_m)
    cache.restore_derived(derived)
    _fe.set_offender_dump_dir(dump_dir)
    return ReadWorker(_dc.replace(airport, dem=revive(dem_token)), objects, law, cache)


def _door_family(state: ReadWorker, rows: list, members: list, shell: dict) -> tuple:
    """One door family in a worker: the witness components are named by
    their index in the resource (an ``id`` does not cross a process)."""
    oo, comps = state.objects, state.cache.components
    rd = _dw.door_reader(state.airport, state.cache, state.law,
                         {id(comps(res)[ci]) for res, cis in shell.items() for ci in cis})
    fam = [(oo[k], w, id(comps(oo[k].resolved)[ci])) for k, w, ci in rows]
    return _dw.read_family(rd, fam, [oo[k] for k in members])


def _sweep_chunk(state: ReadWorker, positions: list) -> tuple:
    """The sill witnesses of some screened placements, each component named
    by its index in the resource."""
    cache, stats, rows = state.cache, _dw.DoorStats(), []
    for k in positions:
        o = state.objects[k]
        index = state.comp_index.get(o.resolved)
        if index is None:
            index = state.comp_index[o.resolved] = {
                id(c): i for i, c in enumerate(cache.components(o.resolved))}
        rows += [(k, w, index[cid]) for _o, w, cid in _dw.witnesses_of(
            o, cache, state.airport.dem.z, state.law, stats, state.wit_memo)]
    return stats, rows


def _road_family(state: ReadWorker, members: list) -> tuple:
    """One road family in a worker.  The cover answers are kept for the
    TASK alone: each task then asks as a read of its own would, and the
    build's process drops the askings one read does not repeat
    (``grade_ledger.replay(once=True)``)."""
    if state.roads is None:
        state.roads = _sr.road_reader(state.airport, state.objects, state.cache, state.law)
    state.roads.cover = {}
    return _sr.read_family(state.roads, [state.objects[k] for k in members])


def read(state: ReadWorker, task: tuple) -> tuple:
    """One task (the shapes are beside :data:`WALLS` … :data:`ROADS`) as
    ``("ok", reading, fallback rungs, ledger)`` — the ledger ``None`` for a
    reader that makes no at-grade read, and its entries' rungs NOT in the
    rungs beside it — or ``("serial", why, ledger)`` when the task reached
    for something a worker does not hold (module doc): the build's process
    then makes that reader's reading itself."""
    a, oo, cache, law = state.airport, state.objects, state.cache, state.law
    _fe.reset_rung_counts()
    mark = _gl.begin(cache) if task[0] in _AT_GRADE else None
    try:
        if task[0] == WALLS:
            if state.walls is None:
                state.walls = wall_reader(a, cache, law)
            got: tuple = read_family(state.walls, task[1], [oo[k] for k in task[2]])
        elif task[0] == DOORS:
            got = _door_family(state, *task[1:])
        elif task[0] == ROADS:
            got = _road_family(state, task[1])
        elif task[0] == WITS:
            got = _sweep_chunk(state, task[1])
        else:
            corridors, tstats = read_corridors(a, oo, cache, law)
            got = (corridors, tstats,
                   *read_plates(a, oo, cache, law, {c.resource for c in corridors}))
    except (ColdTile, StrippedField) as e:
        _fe.reset_rung_counts()                # the build's own read will count them
        return ("serial", f"{type(e).__name__}: {e}", _ledger(cache, mark, True))
    led = _ledger(cache, mark, False)
    rungs = _fe.rung_counts()
    _fe.reset_rung_counts()      # handed over here (or dropped): ``pool._run`` takes none home
    if isinstance(led, str):
        return ("serial", led, None)
    return ("ok", got, rungs if led is None else led.own_rungs(rungs), led)


def _ledger(cache, mark, tripped: bool):
    """The task's ledger (``None`` without a mark); of a TRIPPED task the
    entries alone — another task of this worker may have hit them — and
    ``None`` when it has none to give; of a task that cannot be replayed,
    the reason."""
    if mark is None:
        return None
    try:
        led = _gl.end(cache, mark)
    except _gl.Unreplayable as e:
        return None if tripped else f"Unreplayable: {e}"
    if tripped:
        led.touches = []
    return led


class Ahead:
    """Readers a pool is working on.  :meth:`collect` makes the door wells'
    sweep and hands their families out, waits (bounded, as every pool wait
    is), releases the workers and the shared DEM, charges the workers'
    fallback rungs here, says what the pool did (one ``[pool]`` line, so a
    stage read on one core cannot pass for a pooled one) and returns
    ``{reader: reading}`` — WITHOUT the readers the build's process must
    read itself, and without the at-grade readers, which :meth:`settle`
    hands over one at a time."""

    def __init__(self, pool: WorkPool, shared, parts: list, later: tuple, kinds: tuple,
                 inputs: tuple, counts: dict, out: _t.Callable[[str], None]) -> None:
        self._pool, self._shared, self._parts = pool, shared, parts
        self._later, self._kinds, self._out = later, kinds, out
        self._airport, self._objects, self._cache, self._law = inputs
        self._counts = counts                    # {reader: placements its intake read}
        self._t0 = time.perf_counter()
        self._held: dict = {}             # {at-grade reader: (reading, ledgers, rungs)}
        self._entries: tuple[dict, dict] = ({}, {})
        self.report: dict = {}

    def _doors(self) -> tuple:
        """The door wells' two steps (module doc): ``(the sweep's stats, its
        rungs, why the doors are read on one core or "")``.  The door
        families — and the wall and road families held back for them — are
        handed out here, whatever became of the sweep."""
        oo, cache = self._objects, self._cache
        stats = _dw.DoorStats()
        dem_z = self._airport.dem.z
        hot = [k for k, o in enumerate(oo) if _dw.screened(o, cache, dem_z, self._law, stats)]
        sweep = self._pool.try_map(
            read, [(WITS, hot[i:i + WITS_CHUNK]) for i in range(0, len(hot), WITS_CHUNK)],
            what="door wells: sill witnesses", unit="chunks")
        why = next((row[1] for row in sweep or () if row[0] != "ok"), "")
        tasks: list[tuple] = []
        rungs: list = []
        if sweep is not None and not why:
            wits = []
            shell: dict[str, set[int]] = {}
            for _ok, (part, rows), taken, _led in sweep:
                stats.sill_witnesses += part.sill_witnesses
                stats.basin_gate_components += part.basin_gate_components
                stats.witness_degenerate.extend(part.witness_degenerate)
                rungs.append(taken)
                for k, w, ci in rows:
                    wits.append((oo[k], w, ci))
                    shell.setdefault(oo[k].resolved, set()).add(ci)
            pos = {id(o): k for k, o in enumerate(oo)}
            tasks = [(DOORS, [(pos[id(o)], w, ci) for o, w, ci in fam],
                      [pos[id(m)] for m in members],
                      {r: sorted(shell[r])
                       for r in sorted({m.resolved for m in members} & set(shell))})
                     for _fk, fam, members in _dw.door_families(oo, wits)]
        later, weights = self._later
        first = max(weights, default=0.0) + 1.0          # the door families: first
        tasks = tasks + later
        if sweep is not None and tasks:
            self._parts.append((tasks, self._pool.begin(
                read, tasks, what="pack readers", unit="tasks",
                weights=[first + len(t[1]) + len(t[2]) for t in tasks[:len(tasks) - len(later)]]
                + weights)))
        elif sweep is None:
            self._parts.append((tasks, None))            # no pool is left
        return stats, rungs, why

    def collect(self) -> dict:
        doors = None
        tasks: list = []
        got: list | None = []
        try:
            if DOORS in self._kinds:
                doors = self._doors()
            for part, pending in self._parts:
                more = pending.collect() if pending is not None else None
                got = None if got is None or more is None else got + more
                tasks += part
        finally:
            self.close()
        rows: dict[str, list] = {}
        tripped: dict[str, str] = {DOORS: doors[2]} if doors is not None and doors[2] else {}
        every: list = []
        for task, row in zip(tasks, got or ()):
            if row[-1] is not None:
                every.append(row[-1])
            if row[0] != "ok":
                tripped.setdefault(task[0], row[1])
                continue
            rows.setdefault(task[0], []).append(row)
        for kind, why in tripped.items():       # one tripped task: the whole reader
            self._out(f"[pool] pack reader '{kind}' is read on one core: {why}")
        out: dict = {}
        mine: list[str] = []
        if got is not None:
            for kind in self._kinds:
                if kind in tripped:
                    continue
                # the tasks are in sorted family order, and so are the answers
                readings = [row[1] for row in rows.get(kind, ())]
                rungs = [row[2] for row in rows.get(kind, ())]
                if kind not in _AT_GRADE:           # taken here (module doc)
                    for r in rungs:
                        _fe.add_rung_counts(r)
                if kind == TUNNELS:
                    out[TUNNELS] = readings[0]
                elif kind == WALLS:
                    out[WALLS] = assemble(self._counts[WALLS], readings)
                elif kind == ROADS:
                    self._held[ROADS] = (_sr.assemble(self._counts[ROADS], readings),
                                         [row[3] for row in rows.get(kind, ())], rungs)
                elif kind == DOORS:
                    self._held[DOORS] = (_dw.assemble(doors[0], readings),
                                         [row[3] for row in rows.get(kind, ())],
                                         doors[1] + rungs)
                mine.append(kind)
            self._entries = _gl.made(every)
            for kind in (WALLS, DOORS, ROADS):
                reading = out.get(kind) or self._held.get(kind, (None,))[0]
                if reading is not None:
                    reading[1].read_s = time.perf_counter() - self._t0
        self.report = dict(self._pool.report(), readers=sorted(mine))
        self._say()
        self._out(self.report["line"])
        return out

    def _say(self) -> None:
        self.report["line"] = (self._pool.line() + " — pack readers: "
                               + (", ".join(self.report["readers"]) or "none"))

    def settle(self, kind: str) -> tuple | None:
        """The reading of an at-grade reader (:data:`DOORS`, :data:`ROADS`)
        with its at-grade read replayed on the build's cache — to be asked
        in the order one core reads them, each BEFORE the next is read or
        settled — or ``None`` when the build's process must read it."""
        held = self._held.pop(kind, None)
        if held is None:
            return None
        try:
            _gl.replay(self._cache, held[1], self._entries, once=kind == ROADS)
        except _gl.Unreplayable as e:
            self._out(f"[pool] pack reader '{kind}' is read on one core: {e}")
            self.report["readers"].remove(kind)
            self._say()
            return None
        for r in held[2]:                           # taken here (module doc)
            _fe.add_rung_counts(r)
        return held[0]

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
    is simply the budget or the pack's size.  The at-grade readers are
    started only on a cache whose read can be replayed
    (``grade_ledger.replayable``)."""
    kinds = tuple(k for k in kinds if k not in _AT_GRADE or _gl.replayable(cache))
    if (budget() if workers is None else int(workers)) < 2 or len(objects) < MIN_OBJECTS:
        return None
    tasks: list[tuple] = []
    weights: list[float] = []
    counts: dict[str, int] = {}
    if WALLS in kinds:
        # THE INTAKE, here: ``objects`` order decides each family's members
        counts[WALLS], fams = wall_families(objects, cache, law)
        tasks += [(WALLS, fk, ks) for fk, ks in fams]
        weights += [float(len(ks)) for _fk, ks in fams]
    if ROADS in kinds:
        counts[ROADS], fams = _sr.road_families(objects, cache, law)
        tasks += [(ROADS, ks) for _fk, ks in fams]
        weights += [float(len(ks)) for _fk, ks in fams]
    if TUNNELS in kinds:
        tasks.append((TUNNELS,))
        weights.append(max(weights, default=0.0) + 1.0)     # one long task: first
    # the door wells are handed out by :meth:`Ahead._doors`, and with them
    # the families held back here: only the tunnels start at once
    later: tuple[list, list] = ([], [])
    n = min(budget() if workers is None else int(workers),
            len(tasks) + (DOORS in kinds), MAX_WORKERS)
    if DOORS in kinds:
        held = [k for k, t in enumerate(tasks) if t[0] != TUNNELS]
        later = ([tasks[k] for k in held], [weights[k] for k in held])
        tasks, weights = [t for t in tasks if t[0] == TUNNELS], None
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
    return Ahead(pool, shared, [(tasks, pending)], later, kinds,
                 (airport, objects, cache, law), counts, out)
