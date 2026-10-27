"""STAGE 1'S MAP IS BEING DERIVED (master 2026-10-20; #1214 round 7): the one
flag the pieces that are stage 2's read to stay off stage 1's map.

``pipeline/stage_one_map.stage_one_problem`` derives stage 1's map under
:func:`stage_one`; a reader asks :func:`deriving`.  The door-line pads
(``constraints/door_pad``) and a group's lower level
(``planar/group_low``) are stage 2's, priced against stage 1's solved
airside: neither may lead it.
"""
from __future__ import annotations

import contextlib
import typing as _t

__all__ = ["stage_one", "deriving"]

_DERIVING: list[bool] = []


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
