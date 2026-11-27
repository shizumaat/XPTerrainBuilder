"""A step's side task, run beside the step's own work on a machine slot of
its own (issue #1264: one tile used one core while Triangle4XP ran).

The step's process holds one slot for itself (``O4_Machine_Slots.step``);
work it starts beside that takes another slot first, never waiting
(:func:`O4_Machine_Slots.try_take`).  With none free, :func:`beside`
answers ``None`` and the caller runs the task inline, as before.

A task that mostly WAITS (network answers) uses no core: ``needs_core=False``
starts it without a slot, always.  A pure-Python task beside the step's own
Python work only takes turns with it on the interpreter lock; it gains only
beside an external process or a wait (the mesh step starts the hairline
report after its own input conversion, beside Triangle4XP).
"""
from __future__ import annotations

import threading

import O4_Machine_Slots as MACHINE_SLOTS

__all__ = ["beside"]


class _NoSlot:
    """What a task that holds no slot gives back."""

    def release(self) -> None:
        pass


class _Beside:
    """A task running in a thread; :meth:`result` waits for it, gives its
    slot back and returns (or raises) what the task did."""

    def __init__(self, held, task, args) -> None:
        self._held = held
        self._value = None
        self._error = None
        self._thread = threading.Thread(
            target=self._run, args=(task, args), daemon=True)
        self._thread.start()

    def _run(self, task, args) -> None:
        try:
            self._value = task(*args)
        except BaseException as error:            # handed to result()
            self._error = error
        finally:
            self._held.release()

    def result(self):
        self._thread.join()
        if self._error is not None:
            raise self._error
        return self._value


def beside(task, *args, what: str = "",
           needs_core: bool = True) -> "_Beside | None":
    """``task(*args)`` started in a thread on a free machine slot, or
    ``None`` (nothing started) when no slot is free.  ``needs_core=False``
    (a task that waits, not computes) starts it at once, holding none."""
    if not needs_core:
        return _Beside(_NoSlot(), task, args)
    held = MACHINE_SLOTS.try_take(1, what=what)
    if not held.count:
        held.release()
        return None
    return _Beside(held, task, args)
