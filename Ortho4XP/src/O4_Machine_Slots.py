"""THE MACHINE WORKER BUDGET — one slot pool for every heavy process of an
engine session (issue #1225).

Tiles build in separate worker processes, each tile's auto-patch starts one
process per airport, and each airport's work pool starts more: nine tiles
at once put 40+ airport processes and their pools on a 128 GB machine and
exhausted it.  Nothing tied the count to the memory the machine has, or to
the other tiles of the run.

This module is that tie.  An engine session owns ONE pool of ``capacity``
slots, a directory of slot files every process of the session finds through
:data:`ENV_DIR` (inherited down the whole process tree).  A process holds a
slot by holding an OS lock on one slot file — released by the system when
the holder exits, however it exits, so a killed build never leaks a slot.

* an airport build takes ONE slot before it starts (:func:`take`, which
  waits for a free one: an airport beyond the budget queues);
* a work pool takes a slot per worker it starts (:func:`try_take`, which
  never waits: a pool gets what is free, and with fewer than two runs its
  stage serially in the process that already holds a slot);
* a tile's heavy step (vector, mesh/Triangle4XP, masks, DSF + imagery,
  overlays) holds ONE slot for its own process (:func:`step`), lent back
  while the process only waits on airport workers it starts
  (:func:`lend`); a DDS conversion pool takes a slot per extra worker.

A worker PROCESS is started only after its slot is granted: nothing waits
resident for a slot (#1225, second report: every airport of a tile was
spawned up front and queued for a slot at ~2 GB each).

``capacity`` (:func:`capacity`) is ``min(cores - reserved, memory slots)``:
the memory the machine could hand out when the session started, less the
headroom of :data:`BUDGET`, at :data:`BUDGET`'s per-worker estimate,
sampled ONCE per session.  What is LIVE is the memory-pressure gate
(:func:`memory_admits`): before a new slot is granted free memory is read
again, and below the headroom nothing new starts until it recovers —
unless the session holds no slot at all (one process always runs).  A
process that finds no session (a command-line tile, the harness) opens its
own with the same rule.

:func:`lower_priority` runs the engine below the user's applications (nice
10 / Windows below-normal, inherited by every child) and :func:`qos_command`
starts a worker under the macOS utility QoS clamp, so the window server and
input stay responsive however busy the build is.

Standard library only (with :mod:`O4_Parallel_Utils`' memory probes): the
airport pool, the tile driver and the orchestrator all import it.
"""
from __future__ import annotations

import atexit
import contextlib
import os
import shutil
import sys
import tempfile
import time

import O4_Parallel_Utils as _PU

if sys.platform == "win32":                # module level: a freezer sees it
    import msvcrt as _oslock
else:
    import fcntl as _oslock

__all__ = ["BUDGET", "ENV_DIR", "ENV_CAPACITY", "ENV_UNGATED", "Held", "capacity",
           "ensure_session", "lend", "lower_priority", "memory_admits",
           "qos_command", "session_capacity", "step", "try_take", "take"]

#: the session's slot directory and its capacity, inherited by every child
ENV_DIR = "O4_MACHINE_SLOTS_DIR"
ENV_CAPACITY = "O4_MACHINE_SLOTS"
#: set only by a session that proves MECHANICS, not the machine (the pool
#: self-check, the tests): its explicit capacity is not shrunk by the live
#: memory gate.  A real build never sets it.
ENV_UNGATED = "O4_MACHINE_SLOTS_UNGATED"

#: THE BUDGET LAW (gigabytes / fractions).  Kept here, not in an auto-patch
#: law table: those are hashed into the partition cache key, and how many
#: workers a machine affords must never enter a digest.
#:
#: ``worker_gb`` — what one heavy process (an airport build, or one worker
#: of its pool) is budgeted.  Provenance: a live auto-patch solve held
#: 2.55 GB resident (HECA, ``o4_engine.parallel.STEP_MEMORY_ESTIMATES_GB``),
#: pool workers 1.25-2.0 GB at OTHH (``airport.pool.WORKER_ALLOWANCE_GB``);
#: idle airport workers were seen at ~2 GB on the owner's machine (#1225).
#: Rounded UP to 3.0.  No per-airport peak is recorded anywhere yet; refine
#: this when one is.
#: ``headroom_fraction`` / ``headroom_min_gb`` — what is kept free for the
#: operating system, the app and the user's other work: the larger of
#: 15 % of physical memory and 8 GB (owner, #1225).
#: ``reserved_cores`` — cores never given to the build (owner, #1225:
#: "cores - 2"), so the window server and input always have one.
BUDGET = {
    "worker_gb": 3.0,
    "headroom_fraction": 0.15,
    "headroom_min_gb": 8.0,
    "reserved_cores": 2,
}

#: the nice value :func:`lower_priority` sets (POSIX), and the variable
#: that marks a process tree already lowered
NICE = 10
ENV_PRIORITY = "O4_ENGINE_PRIORITY_LOWERED"

#: seconds between attempts of a :func:`take` that is waiting
POLL_S = 0.5


def capacity(cores: int, total_gb: float, available_gb: float,
             budget: dict = BUDGET) -> int:
    """Slots a machine of ``cores`` logical cores, ``total_gb`` physical and
    ``available_gb`` free-or-reclaimable memory affords — never below 1
    (a machine without the room still builds, one process at a time)."""
    by_memory = int((available_gb - _headroom(total_gb, budget))
                    // budget["worker_gb"])
    by_cores = int(cores) - int(budget.get("reserved_cores", 0))
    return max(1, min(by_cores, by_memory))


def _headroom(total_gb: float, budget: dict = BUDGET) -> float:
    return max(budget["headroom_fraction"] * total_gb, budget["headroom_min_gb"])


def memory_admits(budget: dict = BUDGET) -> bool:
    """THE LIVE GATE: may one more heavy process start now?  Free memory
    is read afresh (``O4_Parallel_Utils`` caches it two seconds) and must
    keep the headroom after one more worker's estimate (always yes in a
    session that set :data:`ENV_UNGATED`)."""
    if os.environ.get(ENV_UNGATED):
        return True
    total = _PU.machine_memory_gigabytes()
    return (_PU.machine_available_memory_gigabytes() - budget["worker_gb"]
            >= _headroom(total, budget))


def _measured_capacity() -> int:
    return capacity(_PU.machine_core_count(), _PU.machine_memory_gigabytes(),
                    _PU.machine_available_memory_gigabytes())


def ensure_session() -> tuple[str, int]:
    """``(slot directory, capacity)`` of this process's session — the one
    inherited through :data:`ENV_DIR`, or a new one published in
    ``os.environ`` so every child started from here shares it.  An explicit
    :data:`ENV_CAPACITY` without a directory pins the capacity."""
    path = os.environ.get(ENV_DIR, "")
    if path and os.path.isdir(path):
        return path, _capacity_from_env()
    try:
        cap = max(1, int(os.environ.get(ENV_CAPACITY, "")))
    except ValueError:
        cap = _measured_capacity()
    path = tempfile.mkdtemp(prefix="o4-slots-")
    atexit.register(shutil.rmtree, path, True)
    os.environ[ENV_DIR] = path
    os.environ[ENV_CAPACITY] = str(cap)
    return path, cap


def _capacity_from_env() -> int:
    try:
        return max(1, int(os.environ.get(ENV_CAPACITY, "")))
    except ValueError:
        return 1


def session_capacity() -> int:
    """The session's capacity (:func:`ensure_session` opens one if needed)."""
    return ensure_session()[1]


class Held:
    """Slots this process holds; :meth:`release` (or the context exit, or
    the process's exit) gives them back."""

    def __init__(self, fds: list) -> None:
        self._fds = list(fds)

    @property
    def count(self) -> int:
        return len(self._fds)

    def release(self) -> None:
        fds, self._fds = self._fds, []
        for fd in fds:
            _unlock(fd)

    def __enter__(self) -> "Held":
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass


def _lock(path: str):
    """An open descriptor holding ``path``'s lock, or ``None`` when another
    process (or another descriptor of this one) holds it."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return None
    try:
        if sys.platform == "win32":
            _oslock.locking(fd, _oslock.LK_NBLCK, 1)
        else:
            _oslock.flock(fd, _oslock.LOCK_EX | _oslock.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def _unlock(fd) -> None:
    try:
        if sys.platform == "win32":
            os.lseek(fd, 0, os.SEEK_SET)
            _oslock.locking(fd, _oslock.LK_UNLCK, 1)
    except OSError:
        pass
    try:
        os.close(fd)                       # closing releases a flock
    except OSError:
        pass


def try_take(n: int) -> Held:
    """Up to ``n`` free slots, at once and never waiting (possibly none).

    Under memory pressure (:func:`memory_admits` false) nothing is granted
    — except one slot when the whole session holds none, so the build
    always progresses."""
    path, cap = ensure_session()
    if n <= 0:
        return Held([])
    pressed = not memory_admits()
    want = cap if pressed else n           # pressed: count the free ones
    fds: list = []
    start = os.getpid() % cap              # spread the scans
    for k in range(cap):
        if len(fds) >= want:
            break
        fd = _lock(os.path.join(path, "slot-%d" % ((start + k) % cap)))
        if fd is not None:
            fds.append(fd)
    if pressed:
        keep = 1 if len(fds) == cap else 0  # the session is idle: one runs
        for fd in fds[keep:]:
            _unlock(fd)
        fds = fds[:keep]
    return Held(fds)


def take(n: int = 1, *, poll_s: float = POLL_S, on_wait=None,
         give_up=None) -> Held:
    """``min(n, capacity)`` slots, waiting until they are free — the queue
    of every heavy process beyond the budget.  A partial take is given back
    before the next attempt (two waiters never hold half each).
    ``on_wait()`` is called once, when the first attempt finds no room;
    ``give_up()`` true (a cancel) ends the wait with nothing held."""
    want = max(1, min(int(n), session_capacity()))
    said = False
    while True:
        held = try_take(want)
        if held.count >= want:
            return held
        held.release()
        if give_up is not None and give_up():
            return Held([])
        if not said and on_wait is not None:
            said = True
            on_wait()
        time.sleep(poll_s)


#: the slot this process's current heavy step holds (:func:`step`)
_STEP: list = []


@contextlib.contextmanager
def step(*, on_wait=None, give_up=None):
    """Hold ONE slot for this process's heavy step (nested: the outer one
    covers it).  The process waits here, light, until the slot is free."""
    if _STEP:
        yield _STEP[0]
        return
    held = take(1, on_wait=on_wait, give_up=give_up)
    _STEP.append(held)
    try:
        yield held
    finally:
        _STEP.clear()
        held.release()


@contextlib.contextmanager
def lend():
    """Give this process's step slot back while it only WAITS on worker
    processes it starts (each takes its own), and take it again after —
    a tile holding its slot while its airports queue for one would
    deadlock a full session."""
    held = _STEP[0] if _STEP else None
    if held is None or not held.count:
        yield
        return
    held.release()
    try:
        yield
    finally:
        again = take(1)
        held._fds, again._fds = again._fds, []     # the step owns it again


def lower_priority() -> None:
    """Run this process — and every child it starts afterwards, which
    inherits it — below the user's applications: nice :data:`NICE` on
    POSIX, ``BELOW_NORMAL_PRIORITY_CLASS`` on Windows.  Once per process
    tree; never raises."""
    if os.environ.get(ENV_PRIORITY):
        return
    os.environ[ENV_PRIORITY] = "1"
    try:
        if sys.platform == "win32":
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000)
        elif os.getpriority(os.PRIO_PROCESS, 0) < NICE:
            os.setpriority(os.PRIO_PROCESS, 0, NICE)
    except Exception:
        pass


_TASKPOLICY = "/usr/sbin/taskpolicy"


def qos_command(command: list) -> list:
    """``command`` started under the macOS utility QoS clamp (inherited by
    its children) when ``taskpolicy`` exists; unchanged elsewhere."""
    if sys.platform == "darwin" and os.path.exists(_TASKPOLICY):
        return [_TASKPOLICY, "-c", "utility"] + list(command)
    return list(command)
