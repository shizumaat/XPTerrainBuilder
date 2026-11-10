"""The order a run takes its queued tiles in: dispatch class and deadline
(flight manager / World spec 2026-11-10, §8.4).

A batch may carry ``klass`` (``P0`` departure / first window, ``P1``
build-ahead, ``P2`` destination, ``P3`` sharpening, ``P4`` alternate) and
``deadline`` (wall-clock seconds, ``time.time()``, by which it must be
built).  The queue is kept sorted by :func:`rank`: class first, then
deadline (earliest first), then arrival.  A batch with neither ranks as
:data:`USER_CLASS` with no deadline, so a run made only of the user's own
presses keeps today's first-in-first-out order (every key is equal and a
new tile goes behind its equals, :func:`place`).

The LAXITY GUARD (:func:`urgent`): a queued tile whose slack -- deadline
less now less its remaining estimate (high end) -- falls under one build's
length (its own estimate) is taken next whatever its class, so a long
build of a higher class does not starve it.

Pure: no I/O, no clock.
"""
from __future__ import annotations

import math
from typing import Callable, Hashable, Iterable, Optional

__all__ = ["CLASSES", "USER_CLASS", "rank", "place", "urgent"]

#: Dispatch classes, highest first (spec §8.4).
CLASSES = ("P0", "P1", "P2", "P3", "P4")
#: The class of a batch that names none: the user's own build ranks with
#: the destination, behind departure and build-ahead.
USER_CLASS = "P2"


def rank(klass: Optional[str] = None,
         deadline: Optional[float] = None) -> tuple:
    """The sort key of a batch's tiles (smaller goes first);
    ``ValueError`` for an unknown class."""
    klass = klass or USER_CLASS
    if klass not in CLASSES:
        raise ValueError(f"unknown dispatch class {klass!r} "
                         f"(known: {list(CLASSES)})")
    return (CLASSES.index(klass),
            math.inf if deadline is None else float(deadline))


def place(queue, item, key: tuple, key_of: Callable[[object], tuple]) -> None:
    """Insert ``item`` into the sorted ``queue`` (a deque or list) behind
    every item whose key is not greater than ``key``.  The common case --
    appended behind equals, as a plain press is -- costs nothing per
    queued item."""
    if not queue or key_of(queue[-1]) <= key:
        queue.append(item)
        return
    for index, other in enumerate(queue):
        if key_of(other) > key:
            queue.insert(index, item)
            return
    queue.append(item)                   # pragma: no cover (unreachable)


def urgent(entries: Iterable[tuple[Hashable, Optional[float],
                                   Optional[float]]],
           now: float) -> Optional[Hashable]:
    """The tile the laxity guard takes next, or ``None``: of ``entries``
    ``(tile, deadline, estimate_high_s)`` those with both, the one with
    the least slack among those whose slack is under their estimate."""
    best, best_slack = None, math.inf
    for tile, deadline, estimate in entries:
        if deadline is None or not estimate:
            continue
        slack = deadline - now - estimate
        if slack < estimate and slack < best_slack:
            best, best_slack = tile, slack
    return best
