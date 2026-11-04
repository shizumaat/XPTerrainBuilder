"""STAGE 1'S MAP IS BEING DERIVED (master 2026-10-20; #1214 round 7): the one
flag the pieces that are stage 2's read to stay off stage 1's map.

``pipeline/stage_one_map.stage_one_problem`` derives stage 1's map under
:func:`stage_one`; a reader asks :func:`deriving`.  The door-line pads
(``constraints/door_pad``) and a group's lower level
(``planar/group_low``) are stage 2's, priced against stage 1's solved
airside: neither may lead it.

The pack decks go the other way (deck redesign §1, ONE derivation for both
maps): stage 1's map is derived under :func:`from_full`, and its planar
build and its anchors read the FULL map's decks and anchor levels
(:func:`full_map`) — never re-derived on the ribbon-free classification
(KIAH round 3: ``obj24551`` anchored 28.440 on the full map, 28.619 on
stage 1's; a station with no stage-1 twin solved 0.26 m off its deck).
"""
from __future__ import annotations

import contextlib
import typing as _t

__all__ = ["stage_one", "deriving", "from_full", "full_map"]

_DERIVING: list[bool] = []
_FULL: list = []


@contextlib.contextmanager
def stage_one() -> _t.Iterator[None]:
    """Stage 1's map is derived inside this block."""
    _DERIVING.append(True)
    try:
        yield
    finally:
        _DERIVING.pop()


def deriving() -> bool:
    """Whether stage 1's map is being derived (:func:`stage_one`)."""
    return bool(_DERIVING)


@contextlib.contextmanager
def from_full(pm_full) -> _t.Iterator[None]:
    """Stage 1's map is derived inside this block from ``pm_full``'s decks
    and deck anchors (module doc)."""
    _FULL.append(pm_full)
    try:
        yield
    finally:
        _FULL.pop()


def full_map():
    """The full map stage 1's map is derived from (:func:`from_full`), or
    ``None`` outside one."""
    return _FULL[-1] if _FULL else None
