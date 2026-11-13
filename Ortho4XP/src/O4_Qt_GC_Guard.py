"""Keep CPython 3.14.0-3.14.4's incremental GC off the Qt app's stacks (#2059).

The crash: a worker thread segfaults in the cyclic GC (``mark_stacks``)
while the GUI thread waits for the GIL inside a PySide6 wrapper's dealloc.
Three defects meet; none crashes alone:

1. CPython 3.14's ``CALL_BUILTIN_O`` (``p.setPen(QColor(...))`` -- shiboken
   methods are builtin methods) closes its argument while the argument's
   stack slot is still inside ``frame->stackpointer``.
2. Shiboken's ``SbkDeallocWrapperCommon`` frees the Python object
   (``deallocData`` -> tp_free) and THEN releases the GIL to run the C++
   destructor.  For that moment the GUI thread's visible stack holds a
   pointer to freed memory.
3. The incremental collector of 3.14.0-3.14.4 marks every thread's frame
   stacks (``mark_stacks``) from whichever thread runs the collection, so
   a worker that collects in that window reads the freed object.

3.13 (the shipped Windows/Linux builds) and 3.14.5+ (incremental GC
reverted) never walk another thread's stack.  On an affected interpreter
this module turns the automatic collector off and collects from a GUI
thread timer instead, with the two collections that do not walk stacks:
young (``gc.collect(0)``) when the young generation is over its threshold,
and full (``gc.collect()``) at most every ``FULL_EVERY_S`` seconds of
activity.  The timer runs on the GUI thread, so the GUI thread is never
mid-dealloc when it collects, and neither collection reads another
thread's stack.  Elsewhere ``install`` does nothing.
"""

import gc
import sys
import time

FIXED_IN = (3, 14, 5)  # incremental GC reverted (generational, no mark_stacks)
TICK_MS = 1000
FULL_EVERY_S = 300.0

__all__ = ["affected", "install"]

# PySide holds a connected bound method weakly: without this reference the
# collector is freed as install() returns and the timer calls nothing.
_INSTALLED = []


def affected(version=None) -> bool:
    """True for the interpreters whose collector walks other threads' stacks."""
    v = tuple((version or sys.version_info)[:3])
    return (3, 14, 0) <= v < FIXED_IN


class _SafeCollector:
    """The automatic collector's job, done with stack-free collections."""

    def __init__(self, gc_module=gc, clock=time.monotonic):
        self._gc = gc_module
        self._clock = clock
        self._last_full = clock()
        self.collections = 0

    def tick(self) -> str:
        """One timer tick: 'young', 'full' or '' (nothing due)."""
        if self._gc.get_count()[0] < self._gc.get_threshold()[0]:
            return ""
        if self._clock() - self._last_full >= FULL_EVERY_S:
            self._last_full = self._clock()
            self._gc.collect()
            self.collections += 1
            return "full"
        self._gc.collect(0)
        self.collections += 1
        return "young"


def install(app, *, force=False, tick_ms=TICK_MS):
    """Disable automatic GC and start the GUI-thread collector on ``app``.

    Call on the GUI thread, before worker threads start.  Returns the
    collector (its QTimer as ``.timer``), or None when the interpreter is
    not affected and nothing was changed.
    """
    if not (force or affected()):
        return None
    from PySide6.QtCore import QTimer

    gc.disable()
    collector = _SafeCollector()
    timer = QTimer(app)
    timer.timeout.connect(collector.tick)
    timer.start(tick_ms)
    collector.timer = timer
    _INSTALLED.append(collector)
    return collector
