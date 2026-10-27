"""Start a worker PROCESS only after its machine slot is granted (#1225).

The per-airport ``ProcessPoolExecutor`` this replaces spawned its workers
as soon as the airports were submitted; each then queued for a machine
slot already resident (~2 GB of imports and DEM each) — 46 processes for
18 slots on the owner's machine, which locked it.  Here the tile's process
keeps the airports as plain queue entries, takes a slot from
:mod:`O4_Machine_Slots` (never waiting: a busy session leaves the rest
queued), and only then starts one single-use worker for that airport.  The
slot is given back after the worker has exited and been reaped, so the
memory it held is free before the next one starts.

Generic over the work: the caller says how to start one task's worker
(``start``), what to do with its finished future (``on_done``) and how to
tear its executor down (``teardown``).  Standard library plus the slots.
"""
from __future__ import annotations

import concurrent.futures as _cf
import time

import O4_Machine_Slots as _SLOTS

__all__ = ["run"]


def run(tasks, *, width: int, start, on_done, teardown, on_tick=None,
        on_wait=None, poll_s: float = 0.5) -> None:
    """Run every task in its own worker, at most ``width`` at once and
    never more than the session's free slots.

    ``start(task) -> (executor, future)`` is called only with a slot held;
    ``on_done(task, future)`` for each finished one; ``teardown(executor,
    future, task)`` before its slot is released (also for every worker
    still running when this exits abnormally); ``on_tick()`` once per poll;
    ``on_wait()`` once, the first time nothing of this run can start."""
    queue = list(tasks)
    running: dict = {}
    said = False
    try:
        while queue or running:
            while queue and len(running) < width:
                held = _SLOTS.try_take(1)
                if not held.count:
                    break
                task = queue.pop(0)
                try:
                    executor, future = start(task)
                except BaseException:
                    held.release()
                    raise
                running[future] = (executor, held, task)
            if queue and not running and not said and on_wait is not None:
                said = True
                on_wait()
            if running:
                done, _ = _cf.wait(list(running), timeout=poll_s,
                                   return_when=_cf.FIRST_COMPLETED)
            else:
                done = ()
                time.sleep(poll_s)
            if on_tick is not None:
                on_tick()
            for future in done:
                executor, held, task = running.pop(future)
                try:
                    teardown(executor, future, task)
                finally:
                    held.release()
                on_done(task, future)
    finally:
        for future, (executor, held, task) in running.items():
            try:
                teardown(executor, future, task)
            finally:
                held.release()
