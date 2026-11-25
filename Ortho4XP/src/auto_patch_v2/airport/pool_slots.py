"""THE POOL'S MACHINE SLOTS — a work pool's workers run only on slots it
holds, and the slots its workers leave idle go back (issue #2267).

A pool takes one machine slot per worker when it starts
(``O4_Machine_Slots``, #1225).  It used to keep them all until it closed:
MMUN's pack partition held 12 for four minutes — through its serial
derivations between maps and the tail of each map, with most workers
idle — while light steps of other tiles waited 100-155 s for one slot.

Here the pool's tasks are SUBMITTED only as its slots allow
(:class:`Feeder`): at most one running task per held slot, so a slot
given back is a core given back, never an oversubscribed one.  The
:class:`SlotBook` is the slots it holds:

* **idle slots go back** — between maps and in a map's tail, the slots
  above the running tasks are released at once;
* **a waiter is served** — while another process of the session waits for
  a slot (``O4_Machine_Slots.slot_waiters``) the pool gives back one slot
  per waiter as its tasks finish, down to :func:`yield_floor` (half its
  workers): a pool is never starved by the steps it yields to;
* **pressure sheds** — while the machine's memory pressure stops this
  session starting work (``O4_Machine_Slots.memory_pressed``: another
  application needs the memory) the pool gives back its slots as its
  tasks finish, down to :func:`yield_floor`, and takes none (owner
  2026-11-25T18:12Z: "scale back if other apps start");
* **slots come back** — with queued tasks and no waiter the pool takes
  free slots again, never waiting and never above its worker count;
* **the build's own slot** — while the build's process only waits in a
  collect, its own slot runs one task of that map even when the pool holds
  none, so a map always progresses.

Scheduling only: which worker answers a task never changes its answer, and
answers are assembled in input order (``pool.WorkPool``).
"""
from __future__ import annotations

import threading
import time
import typing as _t

import O4_Machine_Slots as _slots

__all__ = ["SlotBook", "Feeder", "Job", "yield_floor", "LOOK_S"]

#: seconds between looks at the session's waiters and free slots
LOOK_S = 0.25


def yield_floor(workers: int) -> int:
    """The slots a pool keeps while other processes wait: half its
    workers, at least one."""
    return max(1, int(workers) // 2)


class SlotBook:
    """The machine slots a pool's workers run on (module doc)."""

    def __init__(self, held: "_slots.Held", workers: int, label: str = "",
                 waiters: _t.Callable[[], int] | None = None,
                 pressed: _t.Callable[[], bool] | None = None,
                 clock: _t.Callable[[], float] = time.monotonic) -> None:
        self._grants = [held]
        self.workers = max(1, int(workers))
        self.label = label
        self.per_gb = held.gb if held.gb > 0.0 else None
        self._waiters_of, self._clock = waiters, clock
        self._pressed_of = pressed
        self._seen = (-1.0, 0)                 # (when, waiters) last read
        self._felt = (-1.0, False)             # (when, pressed) last read
        self._next_take = 0.0
        #: slots given back to waiters, and idle slots given back
        self.yielded = 0
        self.idled = 0

    @property
    def count(self) -> int:
        return sum(g.count for g in self._grants)

    def waiters(self) -> int:
        """The session's waiting takes, read at most every :data:`LOOK_S`."""
        now = self._clock()
        if now - self._seen[0] >= LOOK_S:
            read = self._waiters_of or _slots.slot_waiters
            self._seen = (now, int(read()))
        return self._seen[1]

    def pressed(self) -> bool:
        """The machine's memory pressure, read at most every :data:`LOOK_S`."""
        now = self._clock()
        if now - self._felt[0] >= LOOK_S:
            read = self._pressed_of or _slots.memory_pressed
            self._felt = (now, bool(read()))
        return self._felt[1]

    def fit(self, busy: int, queued: int) -> int:
        """Hold the slots for ``busy`` running and ``queued`` waiting tasks
        (module doc); how many more tasks may start now."""
        want = min(self.workers, busy + queued)
        waiting = self.waiters()
        if waiting:
            want = min(want, max(yield_floor(self.workers), self.count - waiting))
        pressed = self.pressed()
        if pressed:
            want = min(want, yield_floor(self.workers))
        held = self.count
        if held > max(want, busy):
            self._shed(held - max(want, busy), yielded=bool(waiting) and queued > 0)
        elif held < want and not pressed and self._clock() >= self._next_take:
            got = _slots.try_take(want - held, gb=self.per_gb, what=self.label)
            if got.count:
                self._grants.append(got)
            else:
                got.release()
                self._next_take = self._clock() + LOOK_S
        return max(0, min(queued, self.count - busy))

    def _shed(self, k: int, yielded: bool) -> None:
        for grant in reversed(self._grants):
            if k <= 0:
                break
            gone = grant.shed(k)
            k -= gone
            if yielded:
                self.yielded += gone
            else:
                self.idled += gone
        self._grants = [g for g in self._grants if g.count] or self._grants[:1]

    def settle(self, per_gb: float) -> None:
        """Lower every slot's reservation to ``per_gb`` (``Held.settle``);
        later takes reserve that much."""
        for grant in self._grants:
            grant.settle(per_gb)
        self.per_gb = min(per_gb, self.per_gb) if self.per_gb else per_gb

    def release(self) -> None:
        for grant in self._grants:
            grant.release()
        self._grants = self._grants[:1]


class Job:
    """One map's tasks for a :class:`Feeder`: the spans still to submit
    (``queue``, in submission order) and the futures submitted
    (``futs``: future → span)."""

    def __init__(self, queue: list, submit: _t.Callable[[tuple], _t.Any]) -> None:
        self.queue = list(queue)
        self.futs: dict = {}
        self.submit = submit
        #: submitted and not yet finished (pruned at each pump)
        self.running: set = set()
        #: submitted since the collect last looked (it drains this)
        self.new: list = []
        #: the build's process waits in this job's collect (its slot is free)
        self.collecting = False
        #: what stopped the feeding (a broken executor), raised by the collect
        self.error: BaseException | None = None


class Feeder:
    """Submits the jobs' tasks as the :class:`SlotBook` allows (module
    doc); with no book (a pinned or isolating pool) everything at once."""

    def __init__(self, book: SlotBook | None) -> None:
        self.book = book
        self.lock = threading.RLock()
        self._jobs: list[Job] = []
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._closed = False

    def add(self, job: Job) -> None:
        with self.lock:
            self._jobs.append(job)
            self.pump()
        if self.book is not None and self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name="o4-pool-feeder")
            self._thread.start()

    def wake(self, *_a) -> None:
        self._wake.set()

    def busy(self) -> int:
        """Tasks running now, over every job."""
        with self.lock:
            for job in self._jobs:
                job.running = {f for f in job.running if not f.done()}
            return sum(len(j.running) for j in self._jobs)

    def pump(self) -> None:
        """Submit what the slots allow now; give back idle slots."""
        with self.lock:
            if self._closed:
                return
            busy = self.busy()
            self._jobs = [j for j in self._jobs if j.queue or j.running]
            queued = sum(len(j.queue) for j in self._jobs if j.error is None)
            if self.book is None:
                room = queued
            else:
                room = self.book.fit(busy, queued)
            for job in self._jobs:
                if job.error is not None or not job.queue:
                    continue
                own = len(job.running)
                n = min(len(job.queue), room)
                if n == 0 and job.collecting and own == 0:
                    n = 1                       # on the build's own slot
                room -= min(room, n)
                for _ in range(n):
                    span = job.queue.pop(0)
                    try:
                        fut = job.submit(span)
                    except BaseException as e:   # a broken executor
                        job.queue.insert(0, span)
                        job.error = e
                        break
                    job.futs[fut] = span
                    job.running.add(fut)
                    job.new.append(fut)
                    fut.add_done_callback(self.wake)

    def _run(self) -> None:
        while not self._closed:
            self._wake.wait(LOOK_S)
            self._wake.clear()
            if self._closed:
                break
            try:
                self.pump()
            except Exception:                  # never kill the feeder
                pass

    def close(self) -> None:
        self._closed = True
        self._wake.set()
        with self.lock:
            self._jobs = []
