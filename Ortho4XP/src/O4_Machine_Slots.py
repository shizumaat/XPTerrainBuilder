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
  stage serially in the process that already holds a slot).

``capacity`` (:func:`capacity`) is ``min(cores, memory slots)``: the memory
the machine could hand out when the session started, less the OS headroom
of :data:`BUDGET`, at :data:`BUDGET`'s per-worker estimate.  Sampled ONCE
per session (re-sampling it while the session's own workers run would let
the run's consumption shrink its own budget).  A process that finds no
session (a command-line tile, the harness) opens its own with the same
rule, so a lone tile on a big machine runs as wide as before.

Standard library only (with :mod:`O4_Parallel_Utils`' memory probes): the
airport pool, the tile driver and the orchestrator all import it.
"""
from __future__ import annotations

import atexit
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

__all__ = ["BUDGET", "ENV_DIR", "ENV_CAPACITY", "Held", "capacity",
           "ensure_session", "session_capacity", "try_take", "take"]

#: the session's slot directory and its capacity, inherited by every child
ENV_DIR = "O4_MACHINE_SLOTS_DIR"
ENV_CAPACITY = "O4_MACHINE_SLOTS"

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
#: operating system, the app and the tile steps outside the slots: the
#: larger of 15 % of physical memory and 4 GB.
BUDGET = {
    "worker_gb": 3.0,
    "headroom_fraction": 0.15,
    "headroom_min_gb": 4.0,
}

#: seconds between attempts of a :func:`take` that is waiting
POLL_S = 0.5


def capacity(cores: int, total_gb: float, available_gb: float,
             budget: dict = BUDGET) -> int:
    """Slots a machine of ``cores`` logical cores, ``total_gb`` physical and
    ``available_gb`` free-or-reclaimable memory affords — never below 1
    (a machine without the room still builds, one process at a time)."""
    headroom = max(budget["headroom_fraction"] * total_gb, budget["headroom_min_gb"])
    by_memory = int((available_gb - headroom) // budget["worker_gb"])
    return max(1, min(int(cores), by_memory))


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
    """Up to ``n`` free slots, at once and never waiting (possibly none)."""
    path, cap = ensure_session()
    fds: list = []
    start = os.getpid() % cap              # spread the scans
    for k in range(cap):
        if len(fds) >= n:
            break
        fd = _lock(os.path.join(path, "slot-%d" % ((start + k) % cap)))
        if fd is not None:
            fds.append(fd)
    return Held(fds)


def take(n: int = 1, *, poll_s: float = POLL_S, on_wait=None) -> Held:
    """``min(n, capacity)`` slots, waiting until they are free — the queue
    of every heavy process beyond the budget.  A partial take is given back
    before the next attempt (two waiters never hold half each).
    ``on_wait()`` is called once, when the first attempt finds no room."""
    want = max(1, min(int(n), session_capacity()))
    said = False
    while True:
        held = try_take(want)
        if held.count >= want:
            return held
        held.release()
        if not said and on_wait is not None:
            said = True
            on_wait()
        time.sleep(poll_s)
