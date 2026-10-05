"""THE WORK POOL — one airport's build on every core (issue #362; owner
RULINGS 2026-10-04x (4): "everything as parallel as possible").

ONE helper for every stage that has independent work per member, per
resource, per placement or per cluster.  A stage opens a pool, hands it
tasks, and gets the answers back IN INPUT ORDER; whether they were computed
here or in workers is invisible in the result.

The contract a caller relies on:

* **spawn**, always.  The build already runs inside the airport pool's
  spawned child (the v1 wrapper's driver), whose workers are not daemonic,
  so this pool nests under it; a daemonic parent cannot have children and
  reads as a budget of 1.  The frozen engine re-enters through
  ``freeze_support`` exactly as the airport pool does.  Task functions and
  the setup are MODULE-LEVEL functions of statically imported modules (a
  frozen build sees no other kind).
* **a core budget** (:func:`budget`): ``cores // share`` where ``share`` is
  how many airport builds run beside this one (:func:`set_share`, called by
  the airport pool's worker initializer with the pool's own worker count,
  which already honours the airport-pool knob).  :func:`configure` pins it.
  A worker's own budget is 1: pools never nest inside this pool.
* **a memory budget too** (:func:`budget_bound`): every worker parses its
  own resources, so the workers are also bounded by the machine's physical
  memory — this build's share of it, less :data:`PARENT_RESERVE_GB`, at
  :data:`WORKER_ALLOWANCE_GB` a worker.  Never below 1: a machine without
  the room runs the stage on one core, the same computation.  Which bound
  decided (``cores`` / ``share`` / ``memory`` / ``tasks`` / ``pinned``) is
  in :meth:`WorkPool.report` and on the ``[pool]`` line.
* **the suite pins 1** (``tests/conftest.py`` calls ``configure(1)``): the
  engine never guesses that it is under test — a library importing pytest
  must not serialise a production build.
* **ordered results**: :meth:`WorkPool.try_map` returns ``[fn(state, t) for
  t in tasks]`` whatever order the workers finished in.
* **worker state once per worker**: ``setup(*setup_args)`` runs in each
  worker when it starts and its return value is the ``state`` every task
  receives.  Ship law tables and paths; let a worker read what it needs
  itself.  Never ship a parsed pack or a DEM.
* **nothing answers → ``None``**: with a budget of 1, a pool that cannot
  start, a worker that dies, or no completion inside ``stall_s``,
  :meth:`WorkPool.try_map` tears the pool down on a deadline, says so, and
  returns ``None`` — the caller runs its serial code, which is the same
  computation.  :meth:`WorkPool.map` does that for a caller with no
  separate serial spelling.  An exception RAISED BY A TASK is the stage's
  own error and is re-raised here unchanged.
* **the heartbeat keeps ticking**: completions are recorded on
  ``model.pulse`` (``what done/n unit``); the wait wakes every
  :data:`TICK_S`.
* **big arrays are SHARED, never pickled per task**: the parent puts them
  in :class:`SharedArrays` (one shared-memory block each, copied once) and
  ships its small ``spec``; a worker calls :func:`attach` and reads the same
  pages.  The parent closes it when the map is done.
* **a count kept per process comes home**: the §51 (3) union fallback
  rungs (``frame_entry.rung_counts``, the planar report's
  ``union_fallback_rungs``) a worker took are returned with its answers and
  added to this process's, so the report reads the same count wherever the
  union ran.
* **every wait is bounded**: the result wait by ``stall_s``, the teardown by
  :data:`TEARDOWN_S` (then ``terminate``, then ``kill``).
* **a caller with work of its own** takes the map in two halves:
  :meth:`WorkPool.begin` submits and returns a :class:`Pending`, the caller
  does its own part, :meth:`Pending.collect` is the same bounded wait.

What crosses the pipe is the caller's to keep small: a task and its answer
are pickled, so return the rows the consumer keeps, never placed geometry.
"""
from __future__ import annotations

import concurrent.futures as _cf
import ctypes
import itertools
import multiprocessing as _mp
import os
import pickle
import sys
import time
import typing as _t

import numpy as np
from multiprocessing import shared_memory as _shm

from . import frame_entry as _fe
from ..model import pulse as _pulse

__all__ = ["WorkPool", "Pending", "SharedArrays", "attach", "budget", "budget_bound",
           "physical_ram_gb", "PARENT_RESERVE_GB", "WORKER_ALLOWANCE_GB", "configure",
           "set_share", "share_object", "shared_object", "spec_key",
           "TICK_S", "TEARDOWN_S", "STALL_S"]

#: seconds between wake-ups of a result wait (the heartbeat's grain)
TICK_S = 1.0
#: seconds a closing pool may take before its workers are terminated
TEARDOWN_S = 5.0
#: seconds without ONE completed task before a map is declared stalled
STALL_S = 900.0
#: ``ProcessPoolExecutor`` refuses more workers than this on Windows
WINDOWS_MAX_WORKERS = 61

#: THE MEMORY LAW of the pool (module doc), in GiB.  Kept HERE and not in a
#: law table: the tables are hashed into the partition cache key
#: (``law_tables_digest``), and how many workers a machine can afford must
#: never enter a digest.
#:
#: What the build's own process is left, whatever the workers take —
#: measured at OTHH, the largest airport of the battery (sweep sw1040, cold):
#: the build's process stood at 7.5-10.8 GB resident while its pools ran
#: (pack stage and planar readers; 5.7-6.8 GB in the reader arm alone).
PARENT_RESERVE_GB = 11.0
#: What one worker may take — measured at OTHH: the largest worker of the
#: pack pool and of the planar readers stood at 1.25-2.0 GB resident
#: (27.6 GB summed over 20 processes in the pack pool, ~15 GB in the planar
#: pool).
WORKER_ALLOWANCE_GB = 2.0

_explicit: list = [None]
_share: list = [1]
#: the state ``setup`` built in THIS process when it is a pool worker
_STATE: list = [None]


def configure(workers: int | None) -> None:
    """Pin the budget (``None`` returns it to the derived one).  The knob
    for a test, a tool arm and a memory-constrained run."""
    _explicit[0] = None if workers is None else max(1, int(workers))


def set_share(n: int) -> None:
    """``n`` airport builds share this machine (the airport pool's worker
    count): each takes ``cores // n``."""
    _share[0] = max(1, int(n))


class _MemoryStatusEx(ctypes.Structure):
    """``MEMORYSTATUSEX`` (Windows ``GlobalMemoryStatusEx``)."""

    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def physical_ram_gb() -> float | None:
    """This machine's physical memory in GiB, or ``None`` where it cannot
    be read (the memory bound then does not apply)."""
    try:
        if sys.platform == "win32":
            st = _MemoryStatusEx()
            st.dwLength = ctypes.sizeof(st)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return None
            total = int(st.ullTotalPhys)
        else:
            total = int(os.sysconf("SC_PHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, ValueError):
        return None
    return total / 2.0 ** 30 if total > 0 else None


def budget_bound() -> tuple[int, str]:
    """``(workers a pool opened in this process may run, the bound that
    decided)`` — ``pinned`` (:func:`configure`, a worker, a daemonic
    process), ``memory``, ``share`` (the cores, shared with the airport
    builds beside this one) or ``cores``."""
    if _explicit[0] is not None:
        return _explicit[0], "pinned"
    try:
        if _mp.current_process().daemon:
            return 1, "pinned"             # a daemonic process has no children
    except Exception:
        return 1, "pinned"
    share = _share[0]
    by_cores = max(1, (os.cpu_count() or 1) // share)
    ram = physical_ram_gb()
    if ram is not None:
        by_memory = max(1, int((ram / share - PARENT_RESERVE_GB) // WORKER_ALLOWANCE_GB))
        if by_memory < by_cores:
            return by_memory, "memory"
    return by_cores, "share" if share > 1 else "cores"


def budget() -> int:
    """How many workers a pool opened in this process may run."""
    return budget_bound()[0]


def _boot(setup, setup_args, dump_dir: str = "") -> None:
    """Worker initializer: no pool inside a pool; the build's offender dump
    armed here as it is there (``frame_entry.set_offender_dump_dir`` — a
    union that falls to a rung in a worker is dumped as one that falls in
    the build's process is); build the state once."""
    _explicit[0] = 1
    _fe.set_offender_dump_dir(dump_dir)
    _STATE[0] = setup(*setup_args) if setup is not None else None


def _run(fn, chunk):
    """One submitted unit: ``fn`` over a chunk of tasks, in order — and
    the union fallback rungs this worker took doing it (module doc)."""
    state = _STATE[0]
    _fe.reset_rung_counts()
    return [fn(state, t) for t in chunk], _fe.rung_counts()


class WorkPool:
    """A lazily started spawn pool with a per-worker state (module doc).

    ``workers`` defaults to :func:`budget`; the processes start on the
    first :meth:`try_map` that has work, so a stage that revives its
    product from a cache pays nothing for having opened one.  Use as a
    context manager; :meth:`close` is bounded and idempotent."""

    def __init__(self, setup: _t.Callable | None = None,
                 setup_args: tuple = (), *, workers: int | None = None,
                 out: _t.Callable[[str], None] = print,
                 stall_s: float = STALL_S, bound: str | None = None) -> None:
        allowed, why = budget_bound()
        self.workers = allowed if workers is None else max(1, int(workers))
        #: the bound that decided ``workers`` (:func:`budget_bound`'s, or
        #: the caller's own — ``tasks`` when it asked for fewer than the
        #: budget because it has no more work to hand out)
        self.bound = bound or (why if workers is None or self.workers >= allowed else "tasks")
        if sys.platform == "win32":       # the executor's own ceiling there
            self.workers = min(self.workers, WINDOWS_MAX_WORKERS)
        self._setup, self._args = setup, tuple(setup_args)
        self._out, self._stall = out, float(stall_s)
        self._ex: _cf.ProcessPoolExecutor | None = None
        self._dead = False
        #: why no pool answers (``""`` while one does): the budget, or what
        #: made it give up — said through ``out`` AND kept for the report
        self.reason = "" if self.workers > 1 else "budget 1"
        self.fell_back = False
        #: seconds spent waiting on workers, and tasks answered by them
        self.wall_s = 0.0
        self.tasks_done = 0

    # ── life cycle ───────────────────────────────────────────────────────
    @property
    def parallel(self) -> bool:
        """Will the next map be answered by workers?"""
        return self.workers > 1 and not self._dead

    def __enter__(self) -> "WorkPool":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self) -> None:            # a stage that raised past its close
        try:
            self.close()
        except Exception:
            pass

    def _start(self) -> bool:
        if self._ex is not None:
            return True
        try:
            self._ex = _cf.ProcessPoolExecutor(
                max_workers=self.workers, mp_context=_mp.get_context("spawn"),
                initializer=_boot,
                initargs=(self._setup, self._args, _fe.offender_dump_dir()))
        except Exception as e:            # no semaphores, no fork budget, …
            self._give_up(f"could not start ({type(e).__name__}: {e})")
            return False
        return True

    def _give_up(self, why: str) -> None:
        self._dead = True
        self.fell_back, self.reason = True, why
        self._out(f"[pool] FELL BACK: {why} — this stage continues on one core")
        self.close()

    def report(self) -> dict:
        """What the pool did, for the stage's report: ``workers`` it was
        allowed and the ``bound`` that decided them, whether it is still
        ``parallel``, whether it ``fell_back``
        and the ``reason`` (also ``"budget 1"`` for a pool that was never
        one), the seconds spent waiting on workers and the ``tasks`` THEY
        answered.  A clock and a head count — never part of a digest."""
        return {"workers": self.workers, "bound": self.bound, "parallel": self.parallel,
                "fell_back": self.fell_back, "reason": self.reason,
                "wall_s": round(self.wall_s, 3), "tasks": self.tasks_done}

    def line(self) -> str:
        """:meth:`report` as one build-log line."""
        r = self.report()
        how = (f"FELL BACK ({r['reason']})" if r["fell_back"]
               else "serial (budget 1)" if not r["parallel"]
               else f"{r['tasks']} task(s) answered by workers in {r['wall_s']:.1f} s")
        return f"[pool] workers {r['workers']} (bound: {r['bound']}): {how}"

    def close(self) -> None:
        """Release the workers within :data:`TEARDOWN_S` (never an
        unbounded join)."""
        ex, self._ex = self._ex, None
        if ex is None:
            return
        procs = list((getattr(ex, "_processes", None) or {}).values())
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        deadline = time.monotonic() + TEARDOWN_S
        for step in ("join", "terminate", "kill"):
            for p in procs:
                try:
                    if step == "join":
                        p.join(max(0.0, deadline - time.monotonic()))
                    elif p.is_alive():
                        getattr(p, step)()
                        p.join(1.0)
                except Exception:
                    pass

    # ── the map ──────────────────────────────────────────────────────────
    def try_map(self, fn: _t.Callable, tasks: _t.Sequence, *,
                weights: _t.Sequence[float] | None = None, chunk: int = 1,
                what: str = "", unit: str = "") -> list | None:
        """``[fn(state, t) for t in tasks]`` computed by the workers, in
        INPUT order — or ``None`` when no pool answers (module doc), and
        the caller runs its serial code.

        ``weights`` (one per task) submits the heaviest first so a long
        task does not start last; it never changes the result order.
        ``chunk`` groups that many consecutive tasks into one submission
        (thousands of tiny tasks)."""
        tasks = list(tasks)
        if not tasks:
            return []
        pending = self.begin(fn, tasks, weights=weights, chunk=chunk, what=what, unit=unit)
        return None if pending is None else pending.collect()

    def begin(self, fn: _t.Callable, tasks: _t.Sequence, *,
              weights: _t.Sequence[float] | None = None, chunk: int = 1,
              what: str = "", unit: str = "") -> "Pending | None":
        """:meth:`try_map` in two halves, for a caller with work of its OWN
        to do beside the workers: the tasks are submitted here and
        :meth:`Pending.collect` waits for them (the same bounded wait, the
        same ``None``).  ``None`` here when no pool answers."""
        tasks = list(tasks)
        if not self.parallel or not self._start():
            return None
        chunk = max(1, int(chunk))
        spans = [(i, min(i + chunk, len(tasks))) for i in range(0, len(tasks), chunk)]
        order = list(range(len(spans)))
        if weights is not None:
            w = [float(sum(weights[a:b])) for a, b in spans]
            order.sort(key=lambda k: (-w[k], k))
        try:
            futs = {self._ex.submit(_run, fn, tasks[a:b]): (a, b)
                    for a, b in (spans[k] for k in order)}
        except _cf.BrokenExecutor as e:
            self._give_up(f"{what or 'map'}: a worker died ({e})")
            return None
        except BaseException:
            self.close()                           # never leave workers behind
            raise
        return Pending(self, futs, len(tasks), what, unit)

    def _collect(self, p: "Pending") -> list | None:
        t0 = time.perf_counter()
        out: list = [None] * p.n
        prev = _pulse.current()
        what, unit, futs = p.what, p.unit, p.futs
        try:
            pending, done_n, last = set(futs), 0, time.monotonic()
            while pending:
                _pulse.tick(what or "pool", done_n, p.n, unit)
                done, pending = _cf.wait(pending, timeout=TICK_S,
                                         return_when=_cf.FIRST_COMPLETED)
                if not done:
                    if time.monotonic() - last > self._stall:
                        self._give_up(f"{what or 'map'}: no task finished in "
                                      f"{self._stall:.0f} s")
                        return None
                    continue
                last = time.monotonic()
                for f in done:
                    a, b = futs[f]
                    out[a:b], rungs = f.result()   # a task's own error re-raises
                    _fe.add_rung_counts(rungs)
                    done_n += b - a
        except _cf.BrokenExecutor as e:
            self._give_up(f"{what or 'map'}: a worker died ({e})")
            return None
        except BaseException:
            self.close()                           # never leave workers behind
            raise
        finally:
            _pulse.tick(*prev) if prev else _pulse.clear()
            self.wall_s += time.perf_counter() - t0
        self.tasks_done += p.n
        return out

    def map(self, fn: _t.Callable, tasks: _t.Sequence, local: _t.Any, **kw) -> list:
        """:meth:`try_map`, with the serial answer computed HERE over
        ``local`` (this process's own state) when no pool answers."""
        got = self.try_map(fn, tasks, **kw)
        if got is not None:
            return got
        return [fn(local, t) for t in _pulse.each(list(tasks), kw.get("what") or "pool",
                                                 kw.get("unit", ""))]


class Pending:
    """Tasks a pool is working on (:meth:`WorkPool.begin`).
    :meth:`collect` is the second half of :meth:`WorkPool.try_map`: the
    answers in INPUT order, or ``None`` when the pool stopped answering —
    once; a second call returns what the first did."""

    def __init__(self, pool: WorkPool, futs: dict, n: int, what: str, unit: str) -> None:
        self.pool, self.futs, self.n = pool, futs, n
        self.what, self.unit = what, unit
        self._got: list | None = None
        self._done = False

    def collect(self) -> list | None:
        if not self._done:
            try:
                self._got = self.pool._collect(self)
            finally:
                self._done = True
        return self._got


# ── arrays every worker reads, shipped once ──────────────────────────────

class SharedArrays:
    """Named numpy arrays in shared memory (module doc).  ``spec`` is what
    a task carries: ``{name: (block name, dtype, shape, serial)}`` —
    ``serial`` is this process's id and a count of the sets it has shared,
    so two sets are never the same spec even where the system hands a
    later one an earlier one's block name (:func:`spec_key`).  Raises
    ``OSError`` when the machine will not give the memory — the caller
    then runs its serial code.  Use as a context manager; :meth:`close`
    unlinks the blocks."""

    def __init__(self, arrays: _t.Mapping[str, np.ndarray]) -> None:
        self._blocks: list = []
        self.spec: dict[str, tuple[str, str, tuple]] = {}
        self.nbytes = 0
        serial = (os.getpid(), next(_SERIAL))
        try:
            for name, arr in arrays.items():
                arr = np.ascontiguousarray(arr)
                blk = _shm.SharedMemory(create=True, size=max(1, arr.nbytes))
                self._blocks.append(blk)
                np.ndarray(arr.shape, arr.dtype, buffer=blk.buf)[...] = arr
                self.spec[name] = (blk.name, arr.dtype.str, tuple(arr.shape), serial)
                self.nbytes += arr.nbytes
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> "SharedArrays":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        blocks, self._blocks = self._blocks, []
        for blk in blocks:
            for step in (blk.close, blk.unlink):
                try:
                    step()
                except Exception:
                    pass


#: counts the array sets THIS process has shared (``SharedArrays.spec``)
_SERIAL = itertools.count(1)


def spec_key(spec: _t.Mapping[str, tuple]) -> tuple:
    """What makes a ``spec`` THIS set of arrays and no other: every block's
    name AND its serial.  Anything a worker keeps per spec (the attachment
    here, :func:`shared_object`, a caller's own derivation from it) is
    keyed on this, never on the block name alone — a name can come round
    again within one worker's life, a serial cannot."""
    return tuple(sorted((k, v[0], v[3]) for k, v in spec.items()))


#: the ONE spec this process is attached to: ``[key, blocks, arrays]``
_ATTACHED: list = [None, [], {}]


def attach(spec: _t.Mapping[str, tuple]) -> dict[str, np.ndarray]:
    """The arrays of a :class:`SharedArrays` ``spec`` as READ-ONLY views,
    attached once per process (the previous spec is released)."""
    key = spec_key(spec)
    if _ATTACHED[0] != key:
        for blk in _ATTACHED[1]:
            try:
                blk.close()
            except Exception:
                pass
        blocks, arrays = [], {}
        for name, (block, dtype, shape, _serial) in spec.items():
            try:
                blk = _shm.SharedMemory(name=block, track=False)
            except TypeError:              # an interpreter before 3.13
                blk = _shm.SharedMemory(name=block)
            blocks.append(blk)
            arr = np.ndarray(tuple(shape), np.dtype(dtype), buffer=blk.buf)
            arr.flags.writeable = False
            arrays[name] = arr
        _ATTACHED[:] = [key, blocks, arrays]
    return _ATTACHED[2]


# ── one object every task of a map reads, shipped once ───────────────────

def share_object(obj: _t.Any) -> SharedArrays:
    """``obj`` pickled ONCE into shared memory, for a map whose every task
    reads the same thing (a cluster's bodies, a unit's footprints): a task
    carries the small ``.spec`` and its worker calls :func:`shared_object`.
    Raises as :class:`SharedArrays` does — the caller then runs serial."""
    raw = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    return SharedArrays({"pickle": np.frombuffer(raw, dtype=np.uint8)})


#: the object of the ONE spec this process last read: ``[key, object]``
_OBJECT: list = [None, None]


def shared_object(spec: _t.Mapping[str, tuple]) -> _t.Any:
    """The object behind a :func:`share_object` ``spec``, unpickled once
    per process (the previous one is dropped)."""
    key = spec_key(spec)
    if _OBJECT[0] != key:
        _OBJECT[:] = [key, pickle.loads(attach(spec)["pickle"].tobytes())]
    return _OBJECT[1]
