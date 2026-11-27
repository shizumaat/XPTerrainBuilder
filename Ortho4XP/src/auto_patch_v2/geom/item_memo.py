"""ONE ANSWER PER ITEM CONTENT, ACROSS THE BUILD'S PREFIX RUNS (#2206,
spec ``docs/specs/stage1-prefix-reuse-20261127.md``).

A build runs its prefix more than once -- the main pass, stage 1's
ribbon-free map, the one late map (``pipeline/prefix``) -- and some passes
inside it answer many small ITEMS (a ring, a zone part, a polygon) whose
answer is a pure function of the item's own VALUE: the late map's rings,
zone parts and faces are the main pass's wherever no late cell reaches
them.  A pass-level memo cannot serve them (the passes read the whole
classification, which differs; MEASURED KATL, the spec's census); an item
memo can.

:class:`ItemMemo` holds ``key -> answer`` where the key IS the item's
content (coordinates, WKB bytes, the DEM answers it was handed, the law's
numbers), compared by ``==`` -- no digest can collide and no identity is
trusted (``model/map_memo``'s rule, RULINGS 2026-11-24d; this one lives in
the LEAF so ``geom`` itself may hold answers).  It keeps the
answers of the CURRENT and the PREVIOUS prefix run (:func:`next_run`,
called once per ``run_prefix``), so the late map reads the main pass's and
nothing outlives two runs.  A function memoised here reads nothing but its
key: never the DEM (a cached build's DEM witness names every question a
record asked, ``pipeline/front_cache``; a memo that skipped a DEM read
would hide it), never a registry or a module flag.  Answers are shared:
the caller treats them as read-only (immutable geometries, tuples)."""
from __future__ import annotations

import typing as _t

__all__ = ["ItemMemo", "next_run"]

#: every memo, so :func:`next_run` turns them all over at once
_ALL: "list[ItemMemo]" = []
_MISSING = object()


class ItemMemo:
    """``key -> answer`` for the current and the previous prefix run
    (module docstring); ``cap`` bounds the current run's entries (past it
    the run starts afresh: a pathological airport never grows the
    process)."""

    def __init__(self, name: str, cap: int = 500_000) -> None:
        self.name, self.cap = name, int(cap)
        self._now: dict = {}
        self._before: dict = {}
        #: served / computed since import -- a diagnostic, published nowhere
        self.reads = {"hit": 0, "miss": 0}
        _ALL.append(self)

    def get(self, key: _t.Hashable, compute: _t.Callable[[], _t.Any]) -> _t.Any:
        """The answer held for ``key``, else ``compute()``'s, held."""
        got = self._now.get(key, _MISSING)
        if got is _MISSING:
            got = self._before.get(key, _MISSING)
            if got is not _MISSING:
                self._now[key] = got
        if got is not _MISSING:
            self.reads["hit"] += 1
            return got
        self.reads["miss"] += 1
        got = compute()
        if len(self._now) >= self.cap:
            self._now.clear()
        self._now[key] = got
        return got

    def turn(self) -> None:
        """A new prefix run: the current answers become the previous."""
        self._before, self._now = self._now, {}

    def clear(self) -> None:
        """Hold nothing (a test's clean slate)."""
        self._before, self._now = {}, {}


def next_run() -> None:
    """A prefix run begins (``pipeline/prefix.run_prefix``): every memo
    keeps the run before this one and drops the one before that."""
    for memo in _ALL:
        memo.turn()
