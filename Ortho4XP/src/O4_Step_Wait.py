"""Slots follow real work: a step that only WAITS gives its slots back
(issues #2254, #2258).

A tile's step holds a machine slot and a scheduler class token (osm,
compute).  Holding them is right while the step works.  While it only waits
for a file another tile is downloading, a retry backoff or a cache lock
another process holds, the same tokens keep other tiles off idle cores.

A step opens one :func:`step_scope`.  Its first thread is a MEMBER, and a
thread it starts for the step's own work joins with :func:`step_thread`.
A member marks what it does not spend working:

* :func:`waiting`: blocked on something outside this step;
* :func:`joining`: blocked on another member of this step, which by itself
  says nothing (that member may be working);
* :func:`working`: inside a wait, a stretch of real work.

The step PARKS when every member is waiting or joining and at least one is
waiting, and RESUMES as soon as one is not.  A member leaving a wait returns
only after the resume, so it never works without its slots.  Threads that
are not members (imagery downloads under their own token) are not counted,
and outside a scope every call here is a no-op.

Standard library only, so the lowest core modules may import it.
"""
from __future__ import annotations

import contextlib
import functools
import threading
from typing import Callable, Iterator, Optional

__all__ = ["joining", "step_scope", "step_thread", "waiting", "working"]

#: serialises the membership and the park/resume transitions
_GUARD = threading.Lock()
#: set on a thread running a park/resume callback: its own waits (a slot,
#: a ledger lock) are part of the transition
_LOCAL = threading.local()


class _Scope:
    """One step's members and what each is doing."""

    def __init__(self, park: Callable[[], None],
                 resume: Callable[[], None]) -> None:
        self.park = park
        self.resume = resume
        self.members = {threading.get_ident()}
        self.waiting: dict = {}            # thread -> nesting depth
        self.joining: dict = {}            # thread -> nesting depth
        self.parked = False
        self.ended = False

    def settle(self) -> None:
        """Park or resume to match the members (caller holds the guard)."""
        if self.ended:
            return
        idle = all(t in self.waiting or t in self.joining
                   for t in self.members)
        should_park = idle and any(t in self.members for t in self.waiting)
        if should_park == self.parked:
            return
        self.parked = should_park
        _LOCAL.transition = True
        try:
            (self.park if should_park else self.resume)()
        except Exception:
            pass                           # a wait never fails the build
        finally:
            _LOCAL.transition = False


_current: Optional[_Scope] = None


@contextlib.contextmanager
def step_scope(park: Callable[[], None],
               resume: Callable[[], None]) -> Iterator[None]:
    """The running step: ``park()`` / ``resume()`` are called on the
    transitions.  Nested: the outer scope covers the block."""
    global _current
    with _GUARD:
        if _current is not None:
            outer = True
        else:
            outer = False
            scope = _current = _Scope(park, resume)
    if outer:
        yield
        return
    try:
        yield
    finally:
        with _GUARD:
            scope.ended = True
            _current = None


def _member_scope() -> Optional[_Scope]:
    """The scope this thread counts in, if any."""
    if getattr(_LOCAL, "transition", False):
        return None
    scope = _current
    if scope is None or threading.get_ident() not in scope.members:
        return None
    return scope


@contextlib.contextmanager
def _marked(table_name: str) -> Iterator[None]:
    """This thread is in the scope's ``table_name`` for the block."""
    scope = _member_scope()
    if scope is None:
        yield
        return
    me = threading.get_ident()
    table = getattr(scope, table_name)
    with _GUARD:
        table[me] = table.get(me, 0) + 1
        scope.settle()
    try:
        yield
    finally:
        with _GUARD:
            table[me] -= 1
            if not table[me]:
                del table[me]
            scope.settle()


def waiting() -> "contextlib._GeneratorContextManager":
    """The block waits on something outside this step."""
    return _marked("waiting")


def joining() -> "contextlib._GeneratorContextManager":
    """The block waits on another member of this step."""
    return _marked("joining")


@contextlib.contextmanager
def working() -> Iterator[None]:
    """Real work inside a :func:`waiting` block: the step holds its slots
    for this block, and goes back to waiting after it."""
    scope = _member_scope()
    me = threading.get_ident()
    if scope is None or me not in scope.waiting:
        yield
        return
    with _GUARD:
        depth = scope.waiting.pop(me)
        scope.settle()
    try:
        yield
    finally:
        with _GUARD:
            scope.waiting[me] = depth
            scope.settle()


def step_thread(task: Callable) -> Callable:
    """``task``, run on a new thread as a member of the current step."""
    scope = _member_scope()
    if scope is None:
        return task

    @functools.wraps(task)
    def run(*args, **kwargs):
        me = threading.get_ident()
        with _GUARD:
            scope.members.add(me)
        try:
            return task(*args, **kwargs)
        finally:
            with _GUARD:
                scope.members.discard(me)
                scope.settle()
    return run
