"""The steps a parallel run holds for memory, oldest first (issue #2101).

Until #2101 a heavy step the memory gate refused simply lost its turn: the
next dispatch sweep admitted any later step that fitted, so a 57 GB vector
step (a tile whose history solved seven airports at once) waited behind a
stream of smaller steps for as long as the queue kept feeding them — the
owner's +47+012 sat 50 minutes while KATL, queued later, ran.

This module is the run's book of those waits, in the order each step was
FIRST refused.  The scheduler (``o4_engine.parallel``) reads the oldest
pending one as a RESERVATION: while it waits, no other step with a memory
projection starts unless the memory left over still holds the waiter
(FIFO).  Running steps are never paused; they finish, the run's committed
memory drains, and the waiter is admitted — at the latest when nothing
else holds memory (the scheduler's one-step rule), so a wait is bounded
by the steps already running.

Each wait also carries what the front ends show on the tile's row
(``events.MemoryWait``): the projection, the memory free now, and whose
memory it waits for — the machine's (another application holds it) or
the run's own (its other steps' projections fill the budget).  The words
are written here, once, for both apps.

Standard library only; no locking (the scheduler holds its own lock).
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["REASON_MACHINE", "REASON_RUN", "Wait", "MemoryWaits",
           "wait_message"]

#: the step waits for memory the MACHINE does not have free (live check)
REASON_MACHINE = "machine"
#: the step waits for the run's own other steps to give memory back
REASON_RUN = "run"


@dataclass(frozen=True)
class Wait:
    """One held step: its projection, the memory free when last checked
    (gigabytes) and the reason code."""

    needed_gb: float
    free_gb: float
    reason: str


def wait_message(needed_gb: float, free_gb: float, reason: str) -> str:
    """The sentence a tile's row shows while its step waits."""
    head = ("Waiting for memory: needs about %.0f GB, %.0f GB free."
            % (needed_gb, max(0.0, free_gb)))
    if reason == REASON_MACHINE:
        return head + (" Quitting X-Plane or another large application"
                       " frees memory.")
    return head + " It starts when this build's running steps finish."


class MemoryWaits:
    """The run's held steps keyed ``(tile, step_key)``, oldest first."""

    def __init__(self):
        self._waits: dict = {}     # insertion order = first refusal

    def note(self, key, needed_gb, free_gb, reason) -> bool:
        """Record (or refresh) a refusal; True when the step is new here."""
        new = key not in self._waits
        self._waits[key] = Wait(float(needed_gb), float(free_gb), reason)
        return new

    def clear(self, key) -> bool:
        """Forget a step (admitted, or no longer pending); True if held."""
        return self._waits.pop(key, None) is not None

    def oldest(self, is_pending):
        """``(key, Wait)`` of the oldest step still pending — ``is_pending
        (key)`` says so — or ``None``.  Steps no longer pending (their tile
        was stopped or re-planned) are dropped on the way."""
        for key in list(self._waits):
            if is_pending(key):
                return key, self._waits[key]
            del self._waits[key]
        return None

    def snapshot(self) -> dict:
        """``{key: Wait}`` now, for the announcer outside the lock."""
        return dict(self._waits)

    def __contains__(self, key) -> bool:
        return key in self._waits

    def __bool__(self) -> bool:
        return bool(self._waits)
