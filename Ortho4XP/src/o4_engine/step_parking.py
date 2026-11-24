"""A waiting step holds no slot (issues #2254, #2258): both halves.

CHILD.  :class:`ChildParking` is what ``O4_Step_Wait`` calls when every
thread of a tile's step is only waiting: it lends the machine slot back and
tells the parent (``StepWaiting``, consumed by the orchestrator and never
forwarded to a front end).  On resume it takes a slot again.  That wait is
bounded: the waiter may hold a cache lock another tile's slot is blocked on,
so past the bound the step goes on without a slot rather than risk a cycle.

PARENT.  The ``*_locked`` functions move a parked child out of its class
into :data:`WAITING_CLASS` (uncapped) and hand back its memory booking, so
a queued tile can start.  On resume the child returns to its class even if
that overfills it, the rule every hybrid step's swap follows: the class is
shut to new dispatches until it drains.

A parked child is still a process, so a pool of parked children could leave
the queue with no worker.  Up to :data:`EXTRA_WORKERS` workers are started
past the slot count while children are parked, and retired when idle.
"""
from __future__ import annotations

import os
import time

import O4_Machine_Slots as SLOTS
import O4_UI_Utils as UI

from .events import StepWaiting

__all__ = ["EXTRA_WORKERS", "RETAKE_WAIT_SECONDS", "WAITING_CLASS",
           "ChildParking", "extra_worker_wanted_locked", "held_class",
           "note_waiting_locked", "pool_full_locked",
           "retire_surplus_locked"]

#: the scheduler class of a step that only waits
WAITING_CLASS = "waiting"
#: the longest a resuming step waits for a machine slot
RETAKE_WAIT_SECONDS = 120.0
#: workers allowed past the slot count while children are parked
EXTRA_WORKERS = 4


class ChildParking:
    """The ``park`` / ``resume`` of one step in a worker process."""

    def __init__(self, emit, lat: int, lon: int) -> None:
        self._emit = emit
        self._lat = int(lat)
        self._lon = int(lon)
        self._lent = None

    def park(self) -> None:
        self._lent = SLOTS.lend_step()
        self._tell(True)

    def resume(self) -> None:
        deadline = time.monotonic() + RETAKE_WAIT_SECONDS
        lent, self._lent = self._lent, None
        SLOTS.retake_step(lent, give_up=lambda: (
            bool(UI.red_flag) or time.monotonic() >= deadline))
        self._tell(False)

    def _tell(self, waiting: bool) -> None:
        if os.environ.get(SLOTS.ENV_BUILD_WORKER):
            self._emit(StepWaiting(lat=self._lat, lon=self._lon,
                                   waiting=waiting))


def held_class(child):
    """The class ``child``'s step belongs to, parked or not."""
    if child.step_class == WAITING_CLASS:
        return getattr(child, "parked_class", None)
    return child.step_class


def note_waiting_locked(run, child, waiting: bool) -> bool:
    """Apply one ``StepWaiting``; True when a class or booking changed."""
    if waiting:
        return _park_locked(run, child)
    return _resume_locked(run, child)


def _park_locked(run, child) -> bool:
    if child.running_step is None or child.step_class in (None, WAITING_CLASS):
        return False
    held = child.step_class
    run._swap_class_locked(child, WAITING_CLASS)
    child.parked_class = held
    key = (child.tile, child.running_step)
    charged = run._memory_holders.pop(key, None)
    child.parked_memory = charged
    if charged is not None:
        run._memory_in_use = max(0.0, run._memory_in_use - charged)
    reservation = run._ledger_holds.pop(key, None)
    if reservation is not None:
        reservation.release()
    return True


def _resume_locked(run, child) -> bool:
    if child.step_class != WAITING_CLASS:
        return False
    held, child.parked_class = child.parked_class, None
    run._swap_class_locked(child, held)
    charged, child.parked_memory = child.parked_memory, None
    if charged is not None and child.running_step is not None:
        run._memory_holders[(child.tile, child.running_step)] = charged
        run._memory_in_use += charged
        run._reserve_on_ledger_locked(child, child.running_step, charged)
    return True


def _alive(run) -> list:
    return [child for child in run._children if not child.retired]


def _parked_count(children) -> int:
    return sum(1 for child in children if child.step_class == WAITING_CLASS)


def pool_full_locked(run) -> bool:
    """Do the children that are really working fill the slot count?"""
    working = sum(1 for child in _alive(run)
                  if child.tile is not None
                  and child.step_class != WAITING_CLASS)
    return working >= run._slots


def extra_worker_wanted_locked(run) -> bool:
    """Should one more worker start for the queue behind parked children?
    True books it (``run._parked_spawns``)."""
    alive = _alive(run)
    parked = _parked_count(alive)
    if not parked or not run._queue or run._finished or run._cancel_all:
        return False
    if any(child.tile is None and not child.cancelling for child in alive):
        return False
    spawning = run._parked_spawns
    if len(alive) + spawning >= run._slots + min(parked, EXTRA_WORKERS):
        return False
    run._parked_spawns = spawning + 1
    return True


def retire_surplus_locked(run) -> None:
    """Retire idle workers past the slot count once none is needed."""
    alive = _alive(run)
    surplus = len(alive) - run._slots
    if surplus <= 0 or (run._queue and _parked_count(alive)):
        return
    for child in alive:
        if surplus <= 0:
            break
        if child.tile is None and not child.cancelling:
            child.retire()
            surplus -= 1
