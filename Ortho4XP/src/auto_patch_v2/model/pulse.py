"""THE PULSE — what a long v2 stage is doing right now (issue #136).

Output-only and near-free: the stages RECORD their activity here (a tuple
assignment per loop item) and never print.  Whoever wants a sign of life
reads :func:`current` on its own clock — the engine's time-gated heartbeat
(the v1 wrapper's ``progress.Heartbeat``) is the one reader, so a per-object loop
never becomes a per-object print storm.  :func:`mark` announces a sub-stage
boundary the ``out`` lines do not carry (the structures read ends INSIDE
``planar.build``), to whoever :func:`listen`\\ s.

Nothing here touches geometry: a build with or without a listener or a
reader is byte-identical.  The v2 package reads no environment and imports
no v1 code (``tests/auto_patch_v2/test_model.py``); this module keeps both.
"""
from __future__ import annotations

import typing as _t

#: ``(what, i, n, unit)`` of the innermost live activity, or ``None``.
_state: list = [None]
_listeners: list[_t.Callable[[str], None]] = []


def tick(what: str | None, i: int | None = None, n: int | None = None,
         unit: str = "") -> None:
    """Record the current activity (``what`` alone for a step with no
    count; ``None`` clears it)."""
    _state[0] = None if what is None else (what, i, n, unit)


def current() -> tuple | None:
    """The live ``(what, i, n, unit)``, or ``None``."""
    return _state[0]


def clear() -> None:
    _state[0] = None


def each(items: _t.Iterable, what: str, unit: str = "") -> _t.Iterator:
    """Iterate ``items`` unchanged, recording ``what i/n unit`` per item;
    the outer activity is restored when the loop ends (nesting-safe)."""
    seq = items if hasattr(items, "__len__") else list(items)
    n = len(seq)
    prev = _state[0]
    try:
        for i, x in enumerate(seq):
            _state[0] = (what, i, n, unit)
            yield x
    finally:
        _state[0] = prev


def describe(state: tuple | None = None) -> str:
    """``door wells: sill witnesses 412/1,318 objects`` (1-based), or the
    bare ``what`` when there is no count; ``""`` when idle."""
    s = current() if state is None else state
    if not s:
        return ""
    what, i, n, unit = s
    if i is None or n is None:
        return str(what)
    return f"{what} {min(i + 1, n):,}/{n:,}" + (f" {unit}" if unit else "")


def mark(stage: str) -> None:
    """A sub-stage boundary (``"structures"``: the structure reads are done
    and the planar arrangement begins).  Listeners never raise into a build."""
    clear()
    for fn in list(_listeners):
        try:
            fn(stage)
        except Exception:
            pass


def listen(fn: _t.Callable[[str], None]) -> _t.Callable[[], None]:
    """Register a :func:`mark` listener; returns its remover."""
    _listeners.append(fn)

    def _remove() -> None:
        try:
            _listeners.remove(fn)
        except ValueError:
            pass
    return _remove
