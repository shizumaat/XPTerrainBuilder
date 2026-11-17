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
the run's own: either its running steps fill the budget (the row says how
much they hold of how much), or an older held step reserves the room
(the row names that step: "Waiting behind ...", lane lmemwait 2026-11-17
— the owner saw "needs about 0 GB, 36 GB free" with no cause).  The words
are written here, once, for both apps; the wire shape is unchanged.

Standard library only; no locking (the scheduler holds its own lock).
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["REASON_MACHINE", "REASON_RUN", "MemoryWaits",
           "wait_message"]

#: the step waits for memory the MACHINE does not have free (live check)
REASON_MACHINE = "machine"
#: the step waits for the run's own other steps to give memory back
REASON_RUN = "run"


@dataclass(frozen=True)
class _Wait:
    """One held step: its projection, the memory free when last checked
    (gigabytes), the reason code, and for a ``REASON_RUN`` wait what holds
    it — ``behind`` (the reserving step, "+25+055 vector") or the run's
    committed ``in_use_gb`` of its ``budget_gb``."""

    needed_gb: float
    free_gb: float
    reason: str
    behind: str = ""
    in_use_gb: float = 0.0
    budget_gb: float = 0.0


def _gb(gigabytes: float) -> str:
    """A size for the row: one decimal under 10 GB (never "about 0 GB")."""
    gigabytes = max(0.0, gigabytes)
    return ("%.1f" if gigabytes < 10.0 else "%.0f") % gigabytes


def wait_message(needed_gb: float, free_gb: float, reason: str,
                 behind: str = "", in_use_gb: float = 0.0,
                 budget_gb: float = 0.0) -> str:
    """The sentence a tile's row shows while its step waits."""
    if reason == REASON_RUN and behind:
        return ("Waiting behind %s, which needs its memory first (this"
                " step needs about %s GB, %s GB free)."
                % (behind, _gb(needed_gb), _gb(free_gb)))
    head = ("Waiting for memory: needs about %s GB, %s GB free."
            % (_gb(needed_gb), _gb(free_gb)))
    if reason == REASON_MACHINE:
        return head + (" Quitting X-Plane or another large application"
                       " frees memory.")
    if budget_gb > 0.0:
        return head + (" This build's running steps hold %s of the %s GB"
                       " it may use; it starts when one of them finishes."
                       % (_gb(in_use_gb), _gb(budget_gb)))
    return head + " It starts when this build's running steps finish."


class MemoryWaits:
    """The run's held steps keyed ``(tile, step_key)``, oldest first."""

    def __init__(self):
        self._waits: dict = {}     # insertion order = first refusal

    def note(self, key, needed_gb, free_gb, reason, behind="",
             in_use_gb=0.0, budget_gb=0.0) -> bool:
        """Record (or refresh) a refusal; True when the step is new here."""
        new = key not in self._waits
        self._waits[key] = _Wait(float(needed_gb), float(free_gb), reason,
                                 behind, float(in_use_gb), float(budget_gb))
        return new

    def clear(self, key) -> bool:
        """Forget a step (admitted, or no longer pending); True if held."""
        return self._waits.pop(key, None) is not None

    def oldest(self, is_pending):
        """``(key, _Wait)`` of the oldest step still pending — ``is_pending
        (key)`` says so — or ``None``.  Steps no longer pending (their tile
        was stopped or re-planned) are dropped on the way."""
        for key in list(self._waits):
            if is_pending(key):
                return key, self._waits[key]
            del self._waits[key]
        return None

    def snapshot(self) -> dict:
        """``{key: _Wait}`` now, for the announcer outside the lock."""
        return dict(self._waits)

    def __contains__(self, key) -> bool:
        return key in self._waits

    def __bool__(self) -> bool:
        return bool(self._waits)
